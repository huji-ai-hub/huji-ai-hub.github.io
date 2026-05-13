"""Scrape the HUJI CS school news page."""

from __future__ import annotations

import hashlib
import logging

from bs4 import BeautifulSoup

from ..config import SourceConfig
from . import ScrapedItem, ScrapeResult
from ._http import client

log = logging.getLogger(__name__)

SOURCE_ID = "huji_cs_news"


def scrape(cfg: SourceConfig) -> ScrapeResult:
    result = ScrapeResult(source_id=SOURCE_ID)
    url = cfg.url
    if not url:
        result.error = "no URL configured"
        return result
    max_items = cfg.max_items or 25

    with client() as http:
        try:
            resp = http.get(url)
            resp.raise_for_status()
        except Exception as e:
            result.error = f"fetch failed: {e}"
            return result

    soup = BeautifulSoup(resp.text, "lxml")

    # The HUJI CS news page exact selectors must be verified on first run; this
    # is a defensive generic approach: any <article>, or any link inside an <h2>/<h3>.
    candidates = soup.select("article, h2 a, h3 a, .news-item, .views-row")[:max_items]
    seen_urls: set[str] = set()

    for el in candidates:
        link_el = el if el.name == "a" else el.find("a")
        if not link_el or not link_el.get("href"):
            continue
        href = link_el.get("href")
        if href.startswith("/"):
            href = "https://www.cs.huji.ac.il" + href
        if href in seen_urls:
            continue
        seen_urls.add(href)

        title = link_el.get_text(strip=True) or "(untitled)"
        item_id = hashlib.sha256(href.encode("utf-8")).hexdigest()[:16]

        result.items.append(
            ScrapedItem(
                id=item_id,
                title=title,
                url=href,
                meta={"source_url": url},
            )
        )

    return result
