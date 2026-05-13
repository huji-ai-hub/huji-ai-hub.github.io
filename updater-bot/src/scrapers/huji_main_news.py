"""Scrape HUJI main marketing site for AI-related news."""

from __future__ import annotations

import hashlib
import logging

from bs4 import BeautifulSoup

from ..config import SourceConfig
from . import ScrapedItem, ScrapeResult
from ._http import client

log = logging.getLogger(__name__)

SOURCE_ID = "huji_main_ai_news"


def scrape(cfg: SourceConfig) -> ScrapeResult:
    result = ScrapeResult(source_id=SOURCE_ID)
    url = cfg.url
    if not url:
        result.error = "no URL configured"
        return result
    max_items = cfg.max_items or 15

    with client() as http:
        try:
            resp = http.get(url)
            resp.raise_for_status()
        except Exception as e:
            result.error = f"fetch failed: {e}"
            return result

    soup = BeautifulSoup(resp.text, "lxml")
    seen_urls: set[str] = set()

    for link_el in soup.select("a"):
        href = link_el.get("href", "")
        if not href or href.startswith("#") or href.startswith("mailto:"):
            continue
        if href.startswith("/"):
            href = "https://new.huji.ac.il" + href
        text = link_el.get_text(strip=True)
        if len(text) < 15:  # filter out nav links
            continue
        if href in seen_urls:
            continue
        seen_urls.add(href)
        if len(result.items) >= max_items:
            break

        item_id = hashlib.sha256(href.encode("utf-8")).hexdigest()[:16]
        result.items.append(
            ScrapedItem(
                id=item_id,
                title=text[:200],
                url=href,
                meta={"source_url": url},
            )
        )

    return result
