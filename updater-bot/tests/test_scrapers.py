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

        result = huji_main_news.scrape("huji_main_news_he", cfg)

    assert not result.ok
    assert "fetch failed" in (result.error or "")


def test_yissum_scraper_parses_rss_feed():
    """Yissum scraper parses standard WordPress RSS, extracts title/link/pubDate."""
    from src.scrapers import yissum

    rss = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
      <channel>
        <title>Yissum</title>
        <link>https://www.yissum.co.il</link>
        <item>
          <title>Harvard and HUJI joining forces to advance NeuroAI</title>
          <link>https://www.yissum.co.il/news/harvard-huji-neuroai/</link>
          <pubDate>Wed, 14 May 2026 09:00:00 +0000</pubDate>
          <description><![CDATA[A landmark partnership between Harvard and the Hebrew University focused on neuroscience-inspired AI.]]></description>
          <content:encoded><![CDATA[<p>The two universities will share research staff, datasets, and computing resources to advance NeuroAI.</p>]]></content:encoded>
        </item>
        <item>
          <title>$430M exit built by HUJI Applied Physics grads</title>
          <link>https://www.yissum.co.il/news/430m-exit/</link>
          <pubDate>Tue, 13 May 2026 12:00:00 +0000</pubDate>
          <description>Acquisition closes after 7 years of growth.</description>
        </item>
      </channel>
    </rss>"""
    cfg = SourceConfig(enabled=True, url="https://www.yissum.co.il/rss", max_items=10)

    with patch("src.scrapers.yissum.client") as mock_client_factory:
        mock_http = MagicMock()
        mock_http.get.return_value = _mock_response(rss)
        mock_client_factory.return_value.__enter__.return_value = mock_http

        result = yissum.scrape(cfg)

    assert result.ok
    assert len(result.items) == 2
    titles = [it.title for it in result.items]
    assert any("Harvard and HUJI" in t for t in titles)
    assert any("$430M exit" in t for t in titles)
    # content:encoded should win over description when both present
    harvard = next(it for it in result.items if "Harvard" in it.title)
    assert "share research staff" in harvard.content
    # pubDate parsed to ISO
    assert harvard.published_at and harvard.published_at.startswith("2026-05-14")


def test_huji_main_news_sitemap_to_og_metadata():
    """HUJI scraper walks sitemap → fetches each article → extracts OG meta."""
    from src.scrapers import huji_main_news

    sitemap = """<?xml version="1.0" encoding="UTF-8" ?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url>
        <loc>https://new.huji.ac.il/about</loc>
        <lastmod>2026-01-01</lastmod>
      </url>
      <url>
        <loc>https://new.huji.ac.il/news/recent-ai-breakthrough</loc>
        <lastmod>2026-05-12</lastmod>
      </url>
      <url>
        <loc>https://new.huji.ac.il/news/older-piece</loc>
        <lastmod>2025-09-01</lastmod>
      </url>
    </urlset>"""

    article_html = """<!DOCTYPE html>
    <html><head>
      <meta property="og:title" content="HUJI scientists publish breakthrough on causal AI" />
      <meta property="og:description" content="The work, published in Nature, advances our understanding of causal inference in deep learning." />
      <meta property="og:image" content="https://new.huji.ac.il/sites/default/files/article-hero.jpg" />
      <meta property="og:url" content="https://new.huji.ac.il/news/recent-ai-breakthrough" />
      <title>fallback title</title>
    </head><body></body></html>"""

    cfg = SourceConfig(enabled=True, url="https://new.huji.ac.il/sitemap.xml", max_items=5)

    def get_side_effect(url, *args, **kwargs):
        if url.endswith("sitemap.xml"):
            return _mock_response(sitemap)
        return _mock_response(article_html)

    with patch("src.scrapers.huji_main_news.client") as mock_client_factory:
        mock_http = MagicMock()
        mock_http.get.side_effect = get_side_effect
        mock_client_factory.return_value.__enter__.return_value = mock_http

        result = huji_main_news.scrape("huji_main_news_he", cfg)

    assert result.ok
    # Only /news/ URLs (2 of 3 entries) should be fetched as articles.
    assert len(result.items) == 2
    titles = [it.title for it in result.items]
    assert all("breakthrough on causal AI" in t for t in titles)
    # OG description landed in content
    assert all("Nature" in it.content for it in result.items)
    # Sorted lastmod desc — most recent first
    assert "recent-ai-breakthrough" in result.items[0].url


def test_huji_main_news_skips_cs_huji_redirects():
    """When an article's og:url points back to cs.huji.ac.il (F5-blocked),
    skip it — we can't reach the canonical content."""
    from src.scrapers import huji_main_news

    sitemap = """<?xml version="1.0" encoding="UTF-8" ?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://new.huji.ac.il/news/cs-redirect</loc><lastmod>2026-05-01</lastmod></url>
    </urlset>"""

    article_html = """<html><head>
      <meta property="og:title" content="CS school program page" />
      <meta property="og:url" content="http://www.cs.huji.ac.il/he/page/10573" />
    </head><body></body></html>"""

    cfg = SourceConfig(enabled=True, url="https://new.huji.ac.il/sitemap.xml", max_items=5)

    def get_side_effect(url, *args, **kwargs):
        if url.endswith("sitemap.xml"):
            return _mock_response(sitemap)
        return _mock_response(article_html)

    with patch("src.scrapers.huji_main_news.client") as mock_client_factory:
        mock_http = MagicMock()
        mock_http.get.side_effect = get_side_effect
        mock_client_factory.return_value.__enter__.return_value = mock_http

        result = huji_main_news.scrape("huji_main_news_he", cfg)

    assert result.ok
    assert len(result.items) == 0
