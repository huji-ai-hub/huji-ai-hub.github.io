"""Turn raw scraper output + checker findings into Proposal objects."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from ..checkers import Finding
from ..config import ReviewConfig
from ..llm.provider import LLMProvider
from ..scrapers import ScrapedItem, ScrapeResult
from ..site.faculty import FacultyEntry
from ..state import Manifest
from .models import Proposal

log = logging.getLogger(__name__)


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
