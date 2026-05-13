"""Updater bot entry point.

Run weekly via GitHub Actions; can also be run locally with --dry-run.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.checkers import dead_links, roster_diff, stale_dates
from src.config import Config, load_config
from src.git.pr import open_pr
from src.git.repo import GitRepo
from src.llm.anthropic_provider import AnthropicProvider
from src.llm.provider import LLMProvider
from src.proposals import applier, builder
from src.proposals.models import Proposal
from src.scrapers import ScrapeResult
from src.scrapers import faculty_personal, faculty_scholar, huji_cs_news, huji_main_news
from src.site import faculty as faculty_io
from src.site.content_paths import ContentPaths
from src.state import Manifest

REPO_ROOT = Path(__file__).resolve().parent.parent
BOT_USER_NAME = "huji-ai-hub-bot"
BOT_USER_EMAIL = "huji-ai-hub-bot@users.noreply.github.com"

log = logging.getLogger("updater")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="HUJI AI Hub updater bot")
    p.add_argument("--dry-run", action="store_true", help="Don't open a PR; print summary")
    p.add_argument("--config", type=Path, default=None, help="Path to config.toml")
    return p.parse_args()


def setup_logging() -> None:
    level = logging.INFO
    fmt = os.environ.get("LOG_FORMAT", "text")
    if fmt == "json":
        # Minimal JSON formatter — enough for GitHub Actions log parsing.
        class JsonFormatter(logging.Formatter):
            def format(self, record):
                return json.dumps({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "level": record.levelname,
                    "logger": record.name,
                    "msg": record.getMessage(),
                })
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logging.basicConfig(level=level, handlers=[handler])
    else:
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            stream=sys.stdout,
        )


def main() -> int:
    setup_logging()
    args = parse_args()
    cfg = load_config(args.config, dry_run=args.dry_run)

    if not cfg.schedule.enabled:
        log.info("schedule.enabled=false in config; exiting without doing anything")
        return 0

    paths = ContentPaths.from_repo_root(
        REPO_ROOT, cfg.site.faculty_dir, cfg.site.data_dir
    )
    manifest = Manifest.load(paths.state_file)
    log.info("loaded manifest: %d sources tracked", len(manifest.sources))

    faculty_list = faculty_io.load_all(paths.faculty_dir)
    log.info("loaded %d faculty entries from site", len(faculty_list))

    # ---- 1. Scrape -------------------------------------------------------
    scrape_results = run_scrapers(cfg, faculty_list)

    # ---- 2. Check --------------------------------------------------------
    findings = run_checkers(cfg, faculty_list, paths)

    # ---- 3. Build proposals (LLM filtering happens here) -----------------
    llm = AnthropicProvider(
        api_key=cfg.secrets.anthropic_api_key,
        classifier_model=cfg.llm.classifier_model,
        content_model=cfg.llm.content_model,
        max_tokens=cfg.llm.max_tokens,
        max_retries=cfg.llm.max_retries,
    )
    proposals = builder.build_from_scrapes(
        scrape_results, faculty_list, llm, manifest, cfg.review
    )
    proposals += builder.build_from_findings(findings, llm)
    proposals = builder.cap_to_limit(proposals, cfg.review.max_changes_per_pr)
    log.info("built %d proposals after LLM filtering and cap", len(proposals))

    if not proposals:
        log.info("no changes proposed — nothing to do")
        _persist_manifest(scrape_results, manifest, paths.state_file, cfg.dry_run)
        return 0

    builder.fill_commit_messages(proposals, llm)

    # ---- 4. Apply --------------------------------------------------------
    if cfg.dry_run:
        _print_dry_run(proposals)
        _dump_artifact(proposals)
        return 0

    branch = _branch_name(cfg.github.branch_prefix)
    repo = GitRepo(REPO_ROOT, cfg.secrets.github_token, cfg.github.repo)
    repo.configure_identity(BOT_USER_NAME, BOT_USER_EMAIL)
    repo.checkout_new_branch(branch, base=cfg.github.base_branch)

    applied_paths: list[Path] = []
    for p in proposals:
        try:
            edited = applier.apply(p, REPO_ROOT)
            applied_paths.append(edited)
            repo.stage([edited])
            if repo.has_staged_changes():
                repo.commit(p.commit_message)
            manifest.mark_seen(p.source_id, [p.item_id])
        except Exception as e:
            log.error("failed to apply proposal %s: %s", p.item_id, e)

    # Commit the manifest update on the same branch.
    manifest.save(paths.state_file)
    repo.stage([paths.state_file])
    if repo.has_staged_changes():
        repo.commit("chore(state): update updater-bot manifest")

    # ---- 5. Push + PR ----------------------------------------------------
    try:
        repo.push(branch)
    except Exception as e:
        log.error("push failed: %s", e)
        _dump_artifact(proposals)
        return 1

    pr_url = open_pr(
        token=cfg.secrets.github_token,
        repo_slug=cfg.github.repo,
        branch=branch,
        base=cfg.github.base_branch,
        proposals=proposals,
    )
    if pr_url is None:
        log.error("PR creation returned no URL")
        _dump_artifact(proposals)
        return 1
    log.info("done — PR: %s", pr_url)
    return 0


def run_scrapers(cfg: Config, faculty_list) -> list[ScrapeResult]:
    results: list[ScrapeResult] = []
    src = cfg.sources

    if src.get("huji_cs_news") and src["huji_cs_news"].enabled:
        try:
            results.append(huji_cs_news.scrape(src["huji_cs_news"]))
        except Exception as e:
            log.error("huji_cs_news scraper crashed: %s", e)

    if src.get("huji_main_ai_news") and src["huji_main_ai_news"].enabled:
        try:
            results.append(huji_main_news.scrape(src["huji_main_ai_news"]))
        except Exception as e:
            log.error("huji_main_news scraper crashed: %s", e)

    if src.get("faculty_personal") and src["faculty_personal"].enabled:
        try:
            results.append(faculty_personal.scrape(faculty_list, src["faculty_personal"]))
        except Exception as e:
            log.error("faculty_personal scraper crashed: %s", e)

    if src.get("faculty_scholar") and src["faculty_scholar"].enabled:
        try:
            results.append(faculty_scholar.scrape(faculty_list, src["faculty_scholar"]))
        except Exception as e:
            log.error("faculty_scholar scraper crashed: %s", e)

    for r in results:
        if r.ok:
            log.info("scraper %s: %d items", r.source_id, len(r.items))
        else:
            log.warning("scraper %s: error: %s", r.source_id, r.error)
    return results


def run_checkers(cfg: Config, faculty_list, paths: ContentPaths):
    findings = []
    chk = cfg.checkers

    if chk.get("dead_links") and chk["dead_links"].enabled:
        try:
            findings.extend(dead_links.check(cfg.site.live_url, chk["dead_links"]))
        except Exception as e:
            log.error("dead_links checker crashed: %s", e)

    if chk.get("roster_diff") and chk["roster_diff"].enabled:
        huji_url = (cfg.sources.get("huji_cs_faculty") and cfg.sources["huji_cs_faculty"].url) \
            or "https://www.cs.huji.ac.il/people/faculty"
        try:
            findings.extend(
                roster_diff.check(huji_url, faculty_list, chk["roster_diff"])
            )
        except Exception as e:
            log.error("roster_diff checker crashed: %s", e)

    if chk.get("stale_dates") and chk["stale_dates"].enabled:
        try:
            findings.extend(stale_dates.check(paths.all_markdown(), chk["stale_dates"]))
        except Exception as e:
            log.error("stale_dates checker crashed: %s", e)

    log.info("checkers produced %d findings", len(findings))
    return findings


def _branch_name(prefix: str) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"{prefix}-{today}"


def _print_dry_run(proposals: list[Proposal]) -> None:
    print(f"\n=== DRY RUN: {len(proposals)} proposed changes ===\n")
    for p in proposals:
        print(f"[{p.confidence:.2f}] {p.source_id} → {p.file_path}")
        print(f"   commit: {p.commit_message}")
        print(f"   reason: {p.reason}")
        print()


def _dump_artifact(proposals: list[Proposal]) -> None:
    """If we couldn't open the PR, drop a JSON file so a human can recover."""
    out = REPO_ROOT / "updater-bot" / "state" / "last-run-artifact.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps([p.model_dump() for p in proposals], indent=2),
        encoding="utf-8",
    )
    log.info("wrote recovery artifact to %s", out)


def _persist_manifest(
    scrape_results: list[ScrapeResult],
    manifest: Manifest,
    state_file: Path,
    dry_run: bool,
) -> None:
    """When no proposals are made, still mark scraped items as seen so we don't
    keep re-evaluating them. In dry-run, don't touch disk."""
    if dry_run:
        return
    for r in scrape_results:
        if r.ok:
            manifest.mark_seen(r.source_id, [item.id for item in r.items])
    manifest.save(state_file)


if __name__ == "__main__":
    sys.exit(main())
