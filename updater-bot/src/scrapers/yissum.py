"""Scrape Yissum, HUJI's tech-transfer arm, for news items.

Yissum is the company that turns HUJI research into commercial products and
joint ventures. Their /news/ page surfaces deal announcements, university-
industry partnerships, and AI/ML startup news from the HUJI research base.

The page mixes editorial text with embedded LinkedIn post snippets, so the
scraper takes a defensive approach: pull every link with substantive anchor
text from the news section. The downstream LLM filter decides what's actually
news-worthy.
"""

from __future__ import annotations

import hashlib
import logging
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from ..config import SourceConfig
from . import ScrapedItem, ScrapeResult
from ._http import client

log = logging.getLogger(__name__)

SOURCE_ID = "yissum"


def scrape(cfg: SourceConfig) -> ScrapeResult:
    result = ScrapeResult(source_id=SOURCE_ID)
    url = cfg.url
    if not url:
        result.error = "no URL configured"
        return result
    max_items = cfg.max_items or 20

    with client() as http:
        try:
            resp = http.get(url)
            resp.raise_for_status()
        except Exception as e:
            result.error = f"fetch failed: {e}"
            return result

    soup = BeautifulSoup(resp.text, "lxml")
    seen_urls: set[str] = set()

    # Drop nav junk: focus on links with text >= 25 chars, skip footer + nav menu.
    candidates = soup.select("a[href]")

    for link_el in candidates:
        href = link_el.get("href", "").strip()
        text = link_el.get_text(strip=True)
        if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
            continue
        if not text or len(text) < 25:
            continue

        # Normalize relative URLs.
        if href.startswith("/"):
            href = "https://www.yissum.co.il" + href

        if href in seen_urls:
            continue
        seen_urls.add(href)
        if len(result.items) >= max_items:
            break

        host = urlparse(href).netloc
        # We want yissum.co.il content + their LinkedIn embeds (which carry the
        # actual news copy in the anchor text).
        if host not in {"www.yissum.co.il", "yissum.co.il", "www.linkedin.com", "linkedin.com"}:
            continue

        item_id = hashlib.sha256(href.encode("utf-8")).hexdigest()[:16]
        result.items.append(
            ScrapedItem(
                id=item_id,
                title=text[:200],
                url=href,
                content=text,
                meta={"source_url": url, "source_host": host},
            )
        )

    return result
