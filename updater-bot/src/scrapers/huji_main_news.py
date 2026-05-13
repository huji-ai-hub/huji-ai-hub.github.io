"""Scrape the HUJI main marketing site news pages.

Generalized so the same module can scrape multiple HUJI URLs (Hebrew or English),
parameterized by the source_id passed in. The Hebrew main news page
(`new.huji.ac.il/חדשות-0`) is JS-hydrated and the article links surface as
hashed text in the static HTML, but we still pull what we can: substantive
links with internal hrefs that look like article URLs. The downstream LLM
pass decides whether each item is news-worthy.
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


def scrape(source_id: str, cfg: SourceConfig) -> ScrapeResult:
    result = ScrapeResult(source_id=source_id)
    url = cfg.url
    if not url:
        result.error = "no URL configured"
        return result
    max_items = cfg.max_items or 15

    base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

    with client() as http:
        try:
            resp = http.get(url)
            resp.raise_for_status()
        except Exception as e:
            result.error = f"fetch failed: {e}"
            return result

    soup = BeautifulSoup(resp.text, "lxml")
    seen_urls: set[str] = set()

    # Heuristic 1: any link with substantive anchor text (filters out nav/footer).
    # Heuristic 2: prefer hrefs containing "/node/" or "/article/" (Drupal article paths).
    for link_el in soup.select("a[href]"):
        href = link_el.get("href", "").strip()
        text = link_el.get_text(strip=True)
        if not href or href.startswith("#") or href.startswith("mailto:"):
            continue
        if href.startswith("/"):
            href = base + href
        if not href.startswith("http"):
            continue
        if href in seen_urls:
            continue

        # Skip obvious nav links: too short, or text looks like a hex hash (JS hydration placeholder).
        if len(text) < 15:
            continue
        if _looks_like_hex_hash(text):
            continue
        # Stay on the same domain to avoid pulling random external links.
        if urlparse(href).netloc != urlparse(url).netloc:
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
                content=text,
                meta={"source_url": url},
            )
        )

    return result


def _looks_like_hex_hash(s: str) -> bool:
    """JS-rendered placeholders surface as 32-char hex strings in the static HTML."""
    if len(s) != 32:
        return False
    try:
        int(s, 16)
        return True
    except ValueError:
        return False
