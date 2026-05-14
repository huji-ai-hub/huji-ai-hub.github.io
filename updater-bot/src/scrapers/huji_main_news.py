"""Scrape new.huji.ac.il news via sitemap + per-article OG metadata.

The HUJI main site is a JS-hydrated SPA. The static HTML for an article only
contains nav stubs and meta tags, NOT the article body. But every article has
proper Open Graph metadata server-rendered (title, description, image), which
is plenty for the bot to propose a news card. The reader clicks through to
the original article for the full read.

Architecture:
1. Fetch sitemap.xml (always server-rendered XML, never JS).
2. Filter to URLs containing /news/ — those are the article pages.
3. Sort by <lastmod> descending; keep the most recent N (configurable).
4. For each new URL (per manifest), fetch the article page and pull
   <meta property="og:title">, og:description, og:image, og:url.
5. Return as ScrapedItems for the LLM to judge.

Generalized: the same scraper handles multiple HUJI subsites if you point
config.toml at a different sitemap.xml. Pass a different source_id per call.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup

from ..config import SourceConfig
from . import ScrapedItem, ScrapeResult
from ._http import client

log = logging.getLogger(__name__)

# Default sitemap if config.url omitted or doesn't end in .xml.
DEFAULT_SITEMAP_URL = "https://new.huji.ac.il/sitemap.xml"


def scrape(source_id: str, cfg: SourceConfig) -> ScrapeResult:
    result = ScrapeResult(source_id=source_id)
    sitemap_url = cfg.url or DEFAULT_SITEMAP_URL
    max_items = cfg.max_items or 10

    # Step 1: pull the sitemap.
    with client(browser_ua=True) as http:
        try:
            resp = http.get(sitemap_url)
            resp.raise_for_status()
        except Exception as e:
            result.error = f"sitemap fetch failed: {e}"
            return result

        # Step 2 + 3: parse, filter to /news/, sort by lastmod desc.
        try:
            news_entries = _extract_news_entries(resp.text)
        except ET.ParseError as e:
            result.error = f"sitemap parse failed: {e}"
            return result

        if not news_entries:
            log.warning("%s: sitemap had no /news/ URLs", source_id)
            return result

        news_entries = news_entries[:max_items]
        log.info("%s: sitemap surfaced %d news URLs", source_id, len(news_entries))

        # Step 4: fetch each, extract OG metadata.
        for url, lastmod in news_entries:
            try:
                page_resp = http.get(url)
                page_resp.raise_for_status()
            except Exception as e:
                log.warning("%s: skip %s (fetch failed: %s)", source_id, url, e)
                continue

            meta = _extract_og(page_resp.text)
            if not meta.get("title"):
                continue

            # Don't double-count items that just redirect to the CS school site
            # (we explicitly dropped CS as a source — it's behind F5 anti-bot).
            canonical = meta.get("url", url)
            host = urlparse(canonical).netloc
            if "cs.huji.ac.il" in host:
                log.info("%s: skip %s (canonical points to cs.huji.ac.il)", source_id, url)
                continue

            item_id = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

            result.items.append(
                ScrapedItem(
                    id=item_id,
                    title=meta["title"][:300],
                    url=canonical,
                    content=meta.get("description", "")[:2000],
                    published_at=lastmod,
                    meta={
                        "source_url": sitemap_url,
                        "source_host": "new.huji.ac.il",
                        "image": meta.get("image"),
                    },
                )
            )

    return result


def _extract_news_entries(sitemap_xml: str) -> list[tuple[str, str | None]]:
    """Return [(url, lastmod_iso_or_none)] for /news/ URLs, sorted lastmod desc."""
    root = ET.fromstring(sitemap_xml)
    # Sitemaps use a namespace; strip it for simpler XPath.
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    entries: list[tuple[str, str | None]] = []

    for url_el in root.findall(".//sm:url", ns):
        loc_el = url_el.find("sm:loc", ns)
        if loc_el is None or not loc_el.text:
            continue
        url = loc_el.text.strip()
        if "/news/" not in url:
            continue

        lastmod_el = url_el.find("sm:lastmod", ns)
        lastmod = lastmod_el.text.strip() if (lastmod_el is not None and lastmod_el.text) else None
        entries.append((url, lastmod))

    # Sort by lastmod descending, missing-lastmod sinks to the bottom.
    def sort_key(entry: tuple[str, str | None]) -> tuple[int, str]:
        _, lm = entry
        if not lm:
            return (0, "")
        try:
            # Sitemaps usually use ISO 8601 with TZ; lexical sort works for that.
            return (1, lm)
        except Exception:
            return (0, "")

    entries.sort(key=sort_key, reverse=True)
    return entries


def _extract_og(html: str) -> dict[str, str]:
    """Pull og:* and meta description from a page. Server-rendered even on SPAs."""
    soup = BeautifulSoup(html, "lxml")
    out: dict[str, str] = {}

    for tag in soup.find_all("meta"):
        prop = tag.get("property") or tag.get("name") or ""
        content = tag.get("content")
        if not content:
            continue
        if prop == "og:title":
            out["title"] = content.strip()
        elif prop == "og:description":
            out["description"] = content.strip()
        elif prop == "og:image":
            out["image"] = content.strip()
        elif prop == "og:url":
            out["url"] = content.strip()
        elif prop == "description" and "description" not in out:
            out["description"] = content.strip()

    # Fallback to <title> if og:title missing.
    if "title" not in out:
        title_el = soup.find("title")
        if title_el and title_el.text:
            out["title"] = title_el.text.strip()

    return out
