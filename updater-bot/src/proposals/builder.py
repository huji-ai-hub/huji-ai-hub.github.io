"""Turn raw scraper output + checker findings into Proposal objects."""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

from ..checkers import Finding
from ..config import ReviewConfig
from ..llm.provider import LLMProvider, NewsDraft
from ..scrapers import ScrapedItem, ScrapeResult
from ..site.faculty import FacultyEntry
from ..state import Manifest
from .models import Proposal

log = logging.getLogger(__name__)

# Source IDs that should be routed through the news pipeline (not the
# faculty-bio pipeline). Anything not in here is ignored by build_news_proposals.
NEWS_SOURCE_IDS = {"yissum", "huji_main_news_he", "huji_main_ai_news", "email_inbox"}

# Source-id -> human display name for "Originally reported by" attribution.
NEWS_SOURCE_LABELS = {
    "yissum": "Yissum",
    "huji_main_news_he": "HUJI News",
    "huji_main_ai_news": "HUJI News",
    "email_inbox": "HUJI Marketing",
}


def build_from_scrapes(
    scrape_results: list[ScrapeResult],
    faculty: list[FacultyEntry],
    llm: LLMProvider,
    manifest: Manifest,
    review_cfg: ReviewConfig,
) -> list[Proposal]:
    proposals: list[Proposal] = []
    by_slug = {f.slug: f for f in faculty}

    for sr in scrape_results:
        if not sr.ok:
            log.warning("skipping scraper %s due to error: %s", sr.source_id, sr.error)
            continue

        for item in sr.items:
            if not manifest.is_new(sr.source_id, item.id):
                continue

            faculty_slug = item.meta.get("faculty_slug")
            target = by_slug.get(faculty_slug) if faculty_slug else None
            if target is None:
                # Items not tied to a specific faculty file are out of scope for v1.
                continue

            try:
                verdict = llm.assess_relevance(
                    existing_content=target.body,
                    source_id=sr.source_id,
                    title=item.title,
                    url=item.url,
                    published_at=item.published_at,
                    meta=item.meta,
                )
            except Exception as e:
                log.warning("LLM relevance call failed for %s/%s: %s", sr.source_id, item.id, e)
                continue

            if not verdict.worth_proposing or verdict.confidence < review_cfg.min_confidence:
                continue
            if verdict.proposed_change_type == "none":
                continue

            proposals.append(
                _make_proposal(sr.source_id, item, target, verdict)
            )

    return proposals


def build_news_proposals(
    scrape_results: list[ScrapeResult],
    llm: LLMProvider,
    manifest: Manifest,
    review_cfg: ReviewConfig,
    available_images: list[str] | None = None,
    max_drafts: int = 3,
) -> list[Proposal]:
    """Find news-worthy scraped items and ask Claude to draft full bilingual cards.

    Pipeline:
    1. Filter to scrape sources flagged as news (NEWS_SOURCE_IDS).
    2. Skip items already seen (manifest dedupe).
    3. Cheap LLM classifier per item: is_newsworthy?
    4. Sort surviving items by classifier confidence, take top max_drafts.
    5. For each survivor, expensive LLM call to draft the full bilingual card.
    6. Emit a `new_file` Proposal targeting src/content/news/<slug>.md.
    """
    proposals: list[Proposal] = []
    images = available_images or []

    # Step 1+2: collect candidate items across all news sources.
    candidates: list[tuple[ScrapeResult, ScrapedItem]] = []
    for sr in scrape_results:
        if sr.source_id not in NEWS_SOURCE_IDS:
            continue
        if not sr.ok:
            log.warning("news pipeline: skipping %s (error: %s)", sr.source_id, sr.error)
            continue
        for item in sr.items:
            if not manifest.is_new(sr.source_id, item.id):
                continue
            candidates.append((sr, item))

    if not candidates:
        log.info("news pipeline: 0 candidates after dedupe")
        return proposals

    log.info("news pipeline: %d candidates to classify", len(candidates))

    # Step 3: classify each candidate (cheap call).
    scored: list[tuple[float, ScrapeResult, ScrapedItem, str]] = []
    for sr, item in candidates:
        try:
            verdict = llm.classify_news_item(
                title=item.title,
                url=item.url,
                content_snippet=item.content,
                source_id=sr.source_id,
            )
        except Exception as e:
            log.warning("news classify failed for %s/%s: %s", sr.source_id, item.id, e)
            continue
        if not verdict.is_newsworthy or verdict.confidence < review_cfg.min_confidence:
            # INFO-level so we see rejection reasons in the GitHub Actions log.
            # Cheap to log; invaluable when debugging "why did the bot reject
            # this clearly-AI story" without having to re-run with debug on.
            log.info(
                "news classify REJECT %s/%s (conf=%.2f) title=%r reason=%s",
                sr.source_id, item.id, verdict.confidence,
                item.title[:80], verdict.reason,
            )
            continue
        log.info(
            "news classify ACCEPT %s/%s (conf=%.2f) title=%r reason=%s",
            sr.source_id, item.id, verdict.confidence,
            item.title[:80], verdict.reason,
        )
        scored.append((verdict.confidence, sr, item, verdict.reason))

    log.info("news pipeline: %d items survived classifier", len(scored))

    # Step 4: top-N by confidence.
    scored.sort(key=lambda x: x[0], reverse=True)
    scored = scored[:max_drafts]

    # Step 5+6: draft + build proposal for each survivor.
    used_slugs: set[str] = set()
    for confidence, sr, item, reason in scored:
        try:
            draft = llm.draft_news_card(
                title=item.title,
                url=item.url,
                content_snippet=item.content,
                source_id=sr.source_id,
                source_name=NEWS_SOURCE_LABELS.get(sr.source_id, sr.source_id),
                available_images=images,
            )
        except Exception as e:
            log.warning("news draft failed for %s/%s: %s", sr.source_id, item.id, e)
            continue

        # Sanitize slug, ensure uniqueness within this run.
        slug = _sanitize_slug(draft.slug)
        if not slug:
            log.warning("news draft for %s produced empty slug, skipping", item.url)
            continue
        # If slug collides with another draft this run, add a short suffix.
        original_slug = slug
        suffix = 2
        while slug in used_slugs:
            slug = f"{original_slug}-{suffix}"
            suffix += 1
        used_slugs.add(slug)
        draft.slug = slug

        markdown = _render_news_markdown(
            draft=draft,
            sourceUrl=item.url,
            sourceName=NEWS_SOURCE_LABELS.get(sr.source_id, sr.source_id),
        )

        proposals.append(
            Proposal(
                source_id=sr.source_id,
                item_id=item.id,
                file_path=f"src/content/news/{slug}.md",
                change_type="new_file",
                old_content=None,
                new_content=markdown,
                reason=f"News pipeline: {reason}",
                confidence=confidence,
                raw_evidence={
                    "scraped_url": item.url,
                    "scraped_title": item.title,
                    "draft_slug": slug,
                    **item.meta,
                },
            )
        )

    log.info("news pipeline: produced %d proposals", len(proposals))
    return proposals


def _sanitize_slug(s: str) -> str:
    """Force a slug to lowercase ASCII kebab-case. Strip anything else."""
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9-]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:80]


def _render_news_markdown(
    draft: NewsDraft,
    sourceUrl: str,
    sourceName: str,
) -> str:
    """Build the full markdown file: YAML frontmatter + English body."""
    today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    frontmatter: dict = {
        "slug": draft.slug,
        "title": _scrub(draft.title),
        "titleHe": _scrub(draft.titleHe),
        "summary": _scrub(draft.summary),
        "summaryHe": _scrub(draft.summaryHe),
        "date": today_iso,
        # Default new bot items to featured=true so they surface on the
        # homepage when the PR merges. The PR review IS the human gate;
        # if a reviewer doesn't want it on the homepage, they un-feature
        # it in the PR diff before merging. Previously this was False,
        # which meant every accepted item required a manual flip later.
        "featured": True,
        "tags": list(draft.tags or []),
        "sourceUrl": sourceUrl,
        "sourceName": sourceName,
        "seoTitle": _scrub(draft.seoTitle),
        "seoTitleHe": _scrub(draft.seoTitleHe),
        "seoDescription": _scrub(draft.seoDescription),
        "seoDescriptionHe": _scrub(draft.seoDescriptionHe),
        "keywords": list(draft.keywords or []),
        "keywordsHe": list(draft.keywordsHe or []),
        "needsReview": True,
        "needsReviewNote": "Bot-drafted from external source. Verify facts and translation before merging.",
        "bodyHe": _scrub(draft.bodyHe),
    }
    if draft.image:
        frontmatter["image"] = draft.image

    yaml_block = yaml.safe_dump(
        frontmatter,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=1000,
    )

    return f"---\n{yaml_block}---\n\n{_scrub(draft.body).strip()}\n"


# Em dashes are forbidden anywhere in rendered site content (project rule).
# Strip them defensively in case the model slipped one through.
_EM_DASH_REPLACEMENTS = {
    "—": ", ",   # em dash
    "–": ", ",   # en dash (also forbidden as a workaround)
    "--": ", ",  # double-hyphen workaround
}


def _scrub(s: str) -> str:
    if not s:
        return s
    for bad, good in _EM_DASH_REPLACEMENTS.items():
        s = s.replace(bad, good)
    # Collapse any accidental ", , " sequences left over.
    s = re.sub(r"(,\s*){2,}", ", ", s)
    return s


def build_from_findings(findings: list[Finding], llm: LLMProvider) -> list[Proposal]:
    proposals: list[Proposal] = []

    for f in findings:
        if not f.file_path:
            continue
        # For ambiguous stale dates, ask the LLM to confirm before proposing.
        if f.kind == "stale_date" and f.evidence.get("needs_classification"):
            try:
                verdict = llm.classify_stale_date(
                    f.evidence.get("date", ""), f.evidence.get("context", "")
                )
            except Exception as e:
                log.warning("stale_date classify failed: %s", e)
                continue
            if not verdict.is_stale:
                continue
            confidence = verdict.confidence
            reason = f"{f.description} — LLM: {verdict.reason}"
        else:
            confidence = {"low": 0.5, "medium": 0.75, "high": 0.95}.get(f.severity, 0.5)
            reason = f.description

        # Deterministic ID — Python's built-in hash() is process-randomized so
        # using it would break manifest dedupe across runs.
        digest = hashlib.sha1(reason.encode("utf-8")).hexdigest()[:8]
        item_id = f"{f.checker_id}:{f.kind}:{f.file_path}:{digest}"
        new_content_comment = (
            f"<!-- bot:{f.checker_id} {f.kind}: {reason} (evidence: "
            f"{', '.join(f'{k}={v}' for k, v in f.evidence.items() if k != 'context')}) -->"
        )

        proposals.append(
            Proposal(
                source_id=f.checker_id,
                item_id=item_id,
                file_path=f.file_path,
                change_type="comment",
                old_content=None,
                new_content=new_content_comment,
                reason=reason,
                confidence=confidence,
                raw_evidence=f.evidence,
            )
        )

    return proposals


def fill_commit_messages(proposals: list[Proposal], llm: LLMProvider) -> None:
    """Populate proposal.commit_message in-place. Falls back to a deterministic
    string if the LLM call fails — never leave a commit without a message."""
    for p in proposals:
        try:
            p.commit_message = llm.generate_commit_message(p.file_path, p.source_id, p.reason)
        except Exception as e:
            log.warning("commit-message LLM call failed: %s", e)
            scope = Path(p.file_path).stem
            p.commit_message = f"chore({scope}): updater bot — {p.source_id}"


def cap_to_limit(proposals: list[Proposal], max_n: int) -> list[Proposal]:
    """Sort by confidence descending and trim to max_n."""
    return sorted(proposals, key=lambda p: p.confidence, reverse=True)[:max_n]


def _make_proposal(
    source_id: str,
    item: ScrapedItem,
    target: FacultyEntry,
    verdict,
) -> Proposal:
    file_path = str(target.path)
    if verdict.proposed_change_type == "body_append":
        new = (target.body.rstrip() + "\n\n" + verdict.new_content_snippet.strip() + "\n")
        old = target.body
    elif verdict.proposed_change_type == "body_replace":
        new = verdict.new_content_snippet.strip() + "\n"
        old = target.body
    else:
        # comment / frontmatter: applier handles the precise edit shape
        new = verdict.new_content_snippet
        old = None

    return Proposal(
        source_id=source_id,
        item_id=item.id,
        file_path=file_path,
        change_type=verdict.proposed_change_type,
        old_content=old,
        new_content=new,
        reason=verdict.reason,
        confidence=verdict.confidence,
        raw_evidence={
            "scraped_url": item.url,
            "scraped_title": item.title,
            **item.meta,
        },
    )
