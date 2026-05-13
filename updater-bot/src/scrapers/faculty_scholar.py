"""Scrape each faculty member's Google Scholar page for recent publications.

Scholar HTML is brittle. If the parser fails for >50% of faculty, the scraper
returns an error rather than a partial garbage result.
"""

from __future__ import annotations

import logging
import re
import time

import httpx
from bs4 import BeautifulSoup

from ..config import SourceConfig
from ..site.faculty import FacultyEntry
from . import ScrapedItem, ScrapeResult
from ._http import client

log = logging.getLogger(__name__)

SOURCE_ID = "faculty_scholar"


def scrape(faculty: list[FacultyEntry], cfg: SourceConfig) -> ScrapeResult:
    result = ScrapeResult(source_id=SOURCE_ID)
    interval = cfg.request_interval_sec or 2.0
    max_pubs = cfg.max_publications or 10

    with_scholar = [f for f in faculty if f.scholar]
    if not with_scholar:
        return result

    successes = 0
    with client() as http:
        for entry in with_scholar:
            try:
                items = _scrape_one(http, entry, max_pubs)
                result.items.extend(items)
                successes += 1
            except Exception as e:
                log.warning("faculty_scholar: failed for %s: %s", entry.slug, e)
            time.sleep(interval)

    # Bail loudly if more than half failed — Scholar likely changed its DOM.
    if successes < len(with_scholar) / 2:
        result.error = (
            f"only {successes}/{len(with_scholar)} faculty parsed successfully; "
            "Scholar HTML may have changed"
        )
        result.items = []

    return result


def _scrape_one(http: httpx.Client, entry: FacultyEntry, max_pubs: int) -> list[ScrapedItem]:
    assert entry.scholar is not None
    resp = http.get(entry.scholar)
    if resp.status_code >= 400:
        raise RuntimeError(f"HTTP {resp.status_code}")

    soup = BeautifulSoup(resp.text, "lxml")
    items: list[ScrapedItem] = []

    # Scholar's publication rows are <tr class="gsc_a_tr">. Inside:
    #   .gsc_a_at = title link, .gsc_a_h = year (whitespace-padded)
    rows = soup.select("tr.gsc_a_tr")[:max_pubs]
    for row in rows:
        title_el = row.select_one(".gsc_a_at")
        year_el = row.select_one(".gsc_a_h")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        href = title_el.get("href", "")
        year_text = year_el.get_text(strip=True) if year_el else ""
        year_match = re.search(r"(19|20)\d{2}", year_text)
        year = int(year_match.group()) if year_match else None

        # Stable ID: faculty + title slug. Avoids re-proposing the same pub on tiny title edits.
        slug_part = re.sub(r"\W+", "-", title.lower()).strip("-")[:60]
        items.append(
            ScrapedItem(
                id=f"{entry.slug}:{slug_part}",
                title=title,
                url="https://scholar.google.com" + href if href.startswith("/") else href,
                published_at=str(year) if year else None,
                content="",
                meta={
                    "faculty_slug": entry.slug,
                    "faculty_name": entry.name,
                    "year": year,
                },
            )
        )

    return items
