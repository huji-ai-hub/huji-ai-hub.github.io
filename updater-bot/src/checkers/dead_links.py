"""Crawl the live site, flag dead links."""

from __future__ import annotations

import logging
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..config import CheckerConfig
from ..scrapers._http import client
from . import Finding

log = logging.getLogger(__name__)

CHECKER_ID = "dead_links"


def check(live_url: str, cfg: CheckerConfig) -> list[Finding]:
    timeout = cfg.timeout_sec or 10
    ignore = set(cfg.ignore_statuses or [])
    skip_domains = set(cfg.external_skip or [])
    findings: list[Finding] = []

    with client(timeout=timeout) as http:
        try:
            resp = http.get(live_url)
            resp.raise_for_status()
        except Exception as e:
            log.warning("dead_links: could not load %s: %s", live_url, e)
            return findings

        soup = BeautifulSoup(resp.text, "lxml")
        urls: set[str] = set()
        for tag, attr in (("a", "href"), ("img", "src")):
            for el in soup.find_all(tag):
                v = el.get(attr)
                if not v or v.startswith(("#", "mailto:", "javascript:")):
                    continue
                full = urljoin(live_url, v)
                host = urlparse(full).netloc
                if host in skip_domains:
                    continue
                urls.add(full)

        for url in sorted(urls):
            try:
                head = http.head(url, follow_redirects=True)
                status = head.status_code
                # Some servers reject HEAD; retry as GET if so.
                if status in (405, 501):
                    head = http.get(url)
                    status = head.status_code
            except Exception as e:
                findings.append(
                    Finding(
                        checker_id=CHECKER_ID,
                        kind="dead_link",
                        severity="medium",
                        description=f"Network error fetching {url}: {e}",
                        evidence={"url": url, "error": str(e)},
                    )
                )
                continue

            if status >= 400 and status not in ignore:
                findings.append(
                    Finding(
                        checker_id=CHECKER_ID,
                        kind="dead_link",
                        severity="high" if status in (404, 410) else "medium",
                        description=f"Dead link: {url} returned HTTP {status}",
                        evidence={"url": url, "http_status": status},
                    )
                )

    return findings
