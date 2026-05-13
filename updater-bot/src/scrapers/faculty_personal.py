"""Scrape each faculty member's personal site for changes."""

from __future__ import annotations

import hashlib
import logging
import time
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from ..config import SourceConfig
from ..site.faculty import FacultyEntry
from . import ScrapedItem, ScrapeResult
from ._http import client

log = logging.getLogger(__name__)

SOURCE_ID = "faculty_personal"


def scrape(faculty: list[FacultyEntry], cfg: SourceConfig) -> ScrapeResult:
    result = ScrapeResult(source_id=SOURCE_ID)
    skip_domains = set(cfg.skip_domains or [])
    interval = cfg.request_interval_sec or 1.0

    with client() as http:
        for entry in faculty:
            if not entry.website:
                continue
            host = urlparse(entry.website).netloc
            if host in skip_domains:
                continue
            try:
                item = _scrape_one(http, entry)
                if item:
                    result.items.append(item)
            except Exception as e:
                log.warning("faculty_personal: failed for %s: %s", entry.slug, e)
            time.sleep(interval)

    return result


def _scrape_one(http: httpx.Client, entry: FacultyEntry) -> ScrapedItem | None:
    assert entry.website is not None
    resp = http.get(entry.website)
    if resp.status_code >= 400:
        return None

    soup = BeautifulSoup(resp.text, "lxml")
    title = (soup.title.string.strip() if soup.title and soup.title.string else "") or entry.name
    h1 = soup.find("h1")
    main_heading = h1.get_text(strip=True) if h1 else ""

    # Hash the page body so we can tell if it materially changed.
    body_text = soup.get_text(" ", strip=True)[:5000]
    content_hash = hashlib.sha256(body_text.encode("utf-8")).hexdigest()[:16]

    return ScrapedItem(
        id=f"{entry.slug}:{content_hash}",
        title=title,
        url=entry.website,
        content=main_heading,
        meta={
            "faculty_slug": entry.slug,
            "faculty_name": entry.name,
            "page_hash": content_hash,
            "http_status": resp.status_code,
        },
    )
