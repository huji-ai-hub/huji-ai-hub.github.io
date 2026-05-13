"""Smoke tests for scrapers — parse captured HTML, no live network."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx

from src.config import SourceConfig
from src.scrapers import faculty_personal, faculty_scholar, huji_cs_news
from src.site.faculty import FacultyEntry

FIXTURES = Path(__file__).parent / "fixtures"


def _mock_response(html: str, status: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status,
        text=html,
        request=httpx.Request("GET", "http://test"),
    )


def test_faculty_personal_parses_title_and_h1():
    html = (FIXTURES / "sample_faculty_page.html").read_text()
    entry = FacultyEntry(
        slug="test-person",
        path=Path("test-person.md"),
        name="Test Person",
        title="Dr.",
        lab="Test Lab",
        website="http://example.com/test-person",
    )
    cfg = SourceConfig(enabled=True, request_interval_sec=0)

    with patch("src.scrapers.faculty_personal.client") as mock_client_factory:
        mock_http = MagicMock()
        mock_http.get.return_value = _mock_response(html)
        mock_client_factory.return_value.__enter__.return_value = mock_http

        result = faculty_personal.scrape([entry], cfg)

    assert result.ok
    assert len(result.items) == 1
    assert result.items[0].meta["faculty_slug"] == "test-person"
    assert "Test Person" in result.items[0].title


def test_faculty_scholar_extracts_publications():
    html = (FIXTURES / "sample_scholar_page.html").read_text()
    entry = FacultyEntry(
        slug="test-person",
        path=Path("test-person.md"),
        name="Test Person",
        title="Dr.",
        lab="Test Lab",
        scholar="https://scholar.google.com/citations?user=ABC123",
    )
    cfg = SourceConfig(enabled=True, request_interval_sec=0, max_publications=10)

    with patch("src.scrapers.faculty_scholar.client") as mock_client_factory:
        mock_http = MagicMock()
        mock_http.get.return_value = _mock_response(html)
        mock_client_factory.return_value.__enter__.return_value = mock_http

        result = faculty_scholar.scrape([entry], cfg)

    assert result.ok
    titles = [it.title for it in result.items]
    assert any("Causal estimation" in t for t in titles)
    assert any("Decision making" in t for t in titles)
    assert all(it.meta["faculty_slug"] == "test-person" for it in result.items)


def test_huji_cs_news_extracts_articles():
    html = (FIXTURES / "sample_news_page.html").read_text()
    cfg = SourceConfig(enabled=True, url="https://www.cs.huji.ac.il/news", max_items=10)

    with patch("src.scrapers.huji_cs_news.client") as mock_client_factory:
        mock_http = MagicMock()
        mock_http.get.return_value = _mock_response(html)
        mock_client_factory.return_value.__enter__.return_value = mock_http

        result = huji_cs_news.scrape(cfg)

    assert result.ok
    assert len(result.items) >= 2
    titles = [it.title for it in result.items]
    assert any("AI lab" in t for t in titles)


def test_huji_main_news_handles_fetch_failure():
    """Scraper should return an error result, not raise."""
    from src.scrapers import huji_main_news

    cfg = SourceConfig(enabled=True, url="https://new.huji.ac.il/en/page/ai", max_items=5)
    with patch("src.scrapers.huji_main_news.client") as mock_client_factory:
        mock_http = MagicMock()
        mock_http.get.side_effect = httpx.ConnectError("boom")
        mock_client_factory.return_value.__enter__.return_value = mock_http

        result = huji_main_news.scrape(cfg)

    assert not result.ok
    assert "fetch failed" in (result.error or "")
