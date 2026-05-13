"""Smoke tests for the proposal builder + applier."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.checkers import Finding
from src.config import ReviewConfig
from src.llm.provider import LLMProvider, NewsDraft, NewsVerdict, RelevanceVerdict, StaleDateVerdict
from src.proposals import applier, builder
from src.proposals.models import Proposal
from src.scrapers import ScrapedItem, ScrapeResult
from src.site.faculty import FacultyEntry
from src.state import Manifest


class FakeLLM(LLMProvider):
    def __init__(self, verdict: RelevanceVerdict | None = None):
        self.verdict = verdict or RelevanceVerdict(
            worth_proposing=True,
            confidence=0.9,
            reason="new pub looks relevant",
            proposed_change_type="body_append",
            new_content_snippet="New publication: A test paper (2026).",
        )

    def assess_relevance(self, *args, **kwargs) -> RelevanceVerdict:
        return self.verdict

    def classify_stale_date(self, date_str: str, context: str) -> StaleDateVerdict:
        return StaleDateVerdict(is_stale=True, confidence=0.8, reason="past tense, past date")

    def generate_commit_message(self, file_path, source_id, reason) -> str:
        return f"feat({Path(file_path).stem}): updater bot test"

    def classify_news_item(self, *args, **kwargs) -> NewsVerdict:
        return NewsVerdict(is_newsworthy=True, confidence=0.9, reason="test")

    def draft_news_card(self, *args, **kwargs) -> NewsDraft:
        return NewsDraft(
            slug="2026-05-13-test-item",
            title="Test", titleHe="בדיקה",
            summary="Test summary.", summaryHe="תקציר בדיקה.",
            body="Body paragraph.", bodyHe="פסקה.",
            seoTitle="Test | HUJI AI Hub", seoTitleHe="בדיקה | מרכז AI",
            seoDescription="Test description.", seoDescriptionHe="תיאור בדיקה.",
            keywords=["test"], keywordsHe=["בדיקה"], tags=["test"],
            image=None,
        )


def test_builder_skips_seen_items(tmp_path):
    fpath = tmp_path / "test-person.md"
    fpath.write_text("---\nname: Test\ntitle: Dr.\nlab: Lab\n---\nbody text\n")

    entry = FacultyEntry(
        slug="test-person", path=fpath,
        name="Test Person", title="Dr.", lab="Lab",
    )
    item = ScrapedItem(id="seen-id", title="t", url="u",
                       meta={"faculty_slug": "test-person"})
    sr = ScrapeResult(source_id="faculty_scholar", items=[item])

    manifest = Manifest()
    manifest.mark_seen("faculty_scholar", ["seen-id"])

    proposals = builder.build_from_scrapes(
        [sr], [entry], FakeLLM(), manifest, ReviewConfig()
    )
    assert proposals == []


def test_builder_creates_proposal_for_new_item(tmp_path):
    fpath = tmp_path / "test-person.md"
    fpath.write_text("---\nname: Test\ntitle: Dr.\nlab: Lab\n---\nexisting body\n")

    entry = FacultyEntry(
        slug="test-person", path=fpath,
        name="Test Person", title="Dr.", lab="Lab",
        body="existing body",
    )
    item = ScrapedItem(id="new-id", title="t", url="u",
                       meta={"faculty_slug": "test-person"})
    sr = ScrapeResult(source_id="faculty_scholar", items=[item])

    proposals = builder.build_from_scrapes(
        [sr], [entry], FakeLLM(), Manifest(), ReviewConfig(min_confidence=0.5)
    )
    assert len(proposals) == 1
    p = proposals[0]
    assert p.source_id == "faculty_scholar"
    assert p.confidence == 0.9
    assert p.change_type == "body_append"


def test_builder_drops_low_confidence():
    entry = FacultyEntry(
        slug="x", path=Path("x.md"), name="X", title="Dr.", lab="L",
    )
    item = ScrapedItem(id="i", title="t", url="u", meta={"faculty_slug": "x"})
    sr = ScrapeResult(source_id="faculty_scholar", items=[item])

    low_llm = FakeLLM(RelevanceVerdict(
        worth_proposing=True, confidence=0.3,
        reason="meh", proposed_change_type="body_append",
        new_content_snippet="x",
    ))

    proposals = builder.build_from_scrapes(
        [sr], [entry], low_llm, Manifest(), ReviewConfig(min_confidence=0.5)
    )
    assert proposals == []


def test_applier_appends_body(tmp_path):
    f = tmp_path / "person.md"
    f.write_text("---\nname: Test\ntitle: Dr.\nlab: L\n---\noriginal body\n")

    p = Proposal(
        source_id="x", item_id="i", file_path="person.md",
        change_type="body_append",
        new_content="appended line",
        reason="r", confidence=0.9,
    )
    applier.apply(p, tmp_path)

    out = f.read_text()
    assert "original body" in out
    assert "appended line" in out


def test_applier_writes_comment_only_once(tmp_path):
    f = tmp_path / "person.md"
    f.write_text("---\nname: Test\ntitle: Dr.\nlab: L\n---\nbody\n")
    p = Proposal(
        source_id="x", item_id="i", file_path="person.md",
        change_type="comment",
        new_content="<!-- bot:flag dup -->",
        reason="r", confidence=0.9,
    )
    applier.apply(p, tmp_path)
    applier.apply(p, tmp_path)
    assert f.read_text().count("<!-- bot:flag dup -->") == 1


def test_applier_refuses_path_outside_repo(tmp_path):
    p = Proposal(
        source_id="x", item_id="i", file_path="../escape.md",
        change_type="body_append",
        new_content="x", reason="r", confidence=0.9,
    )
    with pytest.raises(ValueError):
        applier.apply(p, tmp_path)


def test_findings_become_comment_proposals():
    f = Finding(
        checker_id="dead_links", kind="dead_link", severity="high",
        description="Dead link: http://x returned 404",
        file_path="research-areas/biomed.md",
        evidence={"url": "http://x", "http_status": 404},
    )
    proposals = builder.build_from_findings([f], FakeLLM())
    assert len(proposals) == 1
    assert proposals[0].change_type == "comment"
    assert proposals[0].confidence >= 0.9


def test_news_pipeline_emits_new_file_proposal():
    item = ScrapedItem(
        id="news-1",
        title="Yissum announces $50M AI deal",
        url="https://www.yissum.co.il/news/some-deal",
        content="Deal announced today between Yissum and X for AI tech.",
    )
    sr = ScrapeResult(source_id="yissum", items=[item])

    proposals = builder.build_news_proposals(
        [sr], FakeLLM(), Manifest(), ReviewConfig(min_confidence=0.5),
        available_images=["/images/foo.jpg"],
    )
    assert len(proposals) == 1
    p = proposals[0]
    assert p.change_type == "new_file"
    assert p.file_path.startswith("src/content/news/")
    assert p.file_path.endswith(".md")
    # Em dashes must be scrubbed by the builder.
    assert "—" not in p.new_content
    # YAML frontmatter delimiters present.
    assert p.new_content.startswith("---\n")
    assert "\n---\n" in p.new_content
    # Source URL captured for attribution.
    assert "yissum.co.il" in p.new_content


def test_news_pipeline_skips_seen_items():
    item = ScrapedItem(id="seen-news", title="t", url="u", content="x")
    sr = ScrapeResult(source_id="yissum", items=[item])
    manifest = Manifest()
    manifest.mark_seen("yissum", ["seen-news"])

    proposals = builder.build_news_proposals(
        [sr], FakeLLM(), manifest, ReviewConfig(min_confidence=0.5),
        available_images=[],
    )
    assert proposals == []


def test_news_pipeline_ignores_non_news_sources():
    item = ScrapedItem(id="i", title="t", url="u", content="x")
    sr = ScrapeResult(source_id="faculty_scholar", items=[item])
    proposals = builder.build_news_proposals(
        [sr], FakeLLM(), Manifest(), ReviewConfig(min_confidence=0.5),
    )
    assert proposals == []


def test_news_slug_sanitizer_handles_garbage():
    assert builder._sanitize_slug("Foo Bar BAZ!!!") == "foo-bar-baz"
    assert builder._sanitize_slug("---hello---world---") == "hello-world"
    assert builder._sanitize_slug("2026-05-13-תוכנית-ai") == "2026-05-13-ai"


def test_news_scrub_replaces_em_dashes():
    s = "Hello—world. Also—this."
    out = builder._scrub(s)
    assert "—" not in out
    assert "world" in out
