"""Compare site faculty list vs the live HUJI CS faculty page."""

from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher

from bs4 import BeautifulSoup

from ..config import CheckerConfig
from ..scrapers._http import client
from ..site.faculty import FacultyEntry, slugify
from . import Finding

log = logging.getLogger(__name__)

CHECKER_ID = "roster_diff"


def check(
    huji_faculty_url: str,
    site_faculty: list[FacultyEntry],
    cfg: CheckerConfig,
) -> list[Finding]:
    threshold = cfg.name_match_threshold or 0.85
    findings: list[Finding] = []

    huji_names = _fetch_huji_names(huji_faculty_url)
    if not huji_names:
        log.warning("roster_diff: could not fetch HUJI faculty list")
        return findings

    site_names = [(e.slug, e.name) for e in site_faculty]
    huji_normed = [_normalize(n) for n in huji_names]

    # In site, not on HUJI page → may have left.
    for slug, name in site_names:
        normed = _normalize(name)
        if not _fuzzy_in(normed, huji_normed, threshold):
            findings.append(
                Finding(
                    checker_id=CHECKER_ID,
                    kind="extra_faculty",
                    severity="medium",
                    description=(
                        f"{name} is on the site but not found on HUJI CS faculty page; "
                        "verify whether they've left."
                    ),
                    file_path=f"site/src/content/faculty/{slug}.md",
                    evidence={"name": name, "slug": slug},
                )
            )

    # On HUJI page, not in site → likely missing.
    site_normed = [_normalize(n) for _, n in site_names]
    for original, normed in zip(huji_names, huji_normed):
        if not _fuzzy_in(normed, site_normed, threshold):
            slug = slugify(original)
            findings.append(
                Finding(
                    checker_id=CHECKER_ID,
                    kind="missing_faculty",
                    severity="medium",
                    description=(
                        f"{original} is on the HUJI CS faculty page but not in the site."
                    ),
                    file_path=f"site/src/content/faculty/{slug}.md",
                    evidence={"name": original, "slug": slug, "source_url": huji_faculty_url},
                )
            )

    return findings


def _fetch_huji_names(url: str) -> list[str]:
    with client() as http:
        try:
            resp = http.get(url)
            resp.raise_for_status()
        except Exception as e:
            log.warning("roster_diff: fetch failed: %s", e)
            return []

    soup = BeautifulSoup(resp.text, "lxml")
    # Generic: name-like text inside common faculty card patterns.
    candidates: list[str] = []
    for sel in [".faculty-member", ".person", ".views-row", "article"]:
        for el in soup.select(sel):
            h = el.find(["h2", "h3", "h4"])
            if h:
                candidates.append(h.get_text(strip=True))

    # Fallback: any heading that looks like a name.
    if not candidates:
        for h in soup.find_all(["h2", "h3"]):
            text = h.get_text(strip=True)
            if 2 <= len(text.split()) <= 5:
                candidates.append(text)

    return [c for c in candidates if c]


def _normalize(name: str) -> str:
    s = re.sub(r"^(prof\.?|dr\.?)\s+", "", name.strip(), flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s)
    return s.lower()


def _fuzzy_in(needle: str, haystack: list[str], threshold: float) -> bool:
    return any(SequenceMatcher(None, needle, h).ratio() >= threshold for h in haystack)
