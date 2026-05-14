"""Scrape Yissum (HUJI's tech-transfer arm) news via RSS.

Yissum runs WordPress and exposes a standard RSS feed at /rss (and /feed).
RSS is purpose-built for crawlers, so:
  - Cloudflare bot protection that blocks the HTML pages doesn't apply
  - Each <item> already has a clean title, link, summary, and pubDate
  - No HTML parsing fragility, no JS hydration issues

If the feed ever moves or breaks, the URL is configurable in config.toml.
The downstream LLM still gets to judge each item on AI relevance.
"""

from __future__ import annotations

import hashlib
import logging
import re
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

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
    max_items = cfg.max_items or 25

    # Browser UA in case Cloudflare cares about that on the RSS endpoint too.
    # (RSS endpoints are usually crawler-friendly, but cheap insurance.)
    with client(browser_ua=True) as http:
        try:
            resp = http.get(url)
            resp.raise_for_status()
        except Exception as e:
            result.error = f"fetch failed: {e}"
            return result

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as e:
        result.error = f"RSS parse failed: {e}"
        return result

    # Standard RSS 2.0: <rss><channel><item>...
    items = root.findall(".//channel/item") or root.findall(".//item")
    if not items:
        log.warning("yissum RSS contained no <item> elements")
        return result

    for item_el in items[:max_items]:
        title = _text(item_el, "title")
        link = _text(item_el, "link")
        description = _text(item_el, "description")
        pub_date = _text(item_el, "pubDate")
        # WordPress also includes content:encoded — fuller text. Namespace-aware lookup.
        content_encoded = _text(item_el, "{http://purl.org/rss/1.0/modules/content/}encoded")

        if not link or not title:
            continue

        # Stable ID per article URL — survives feed reordering.
        item_id = hashlib.sha256(link.encode("utf-8")).hexdigest()[:16]

        # Use the richest body text available for the LLM to read.
        body = _strip_html(content_encoded or description or "")

        published_iso = _parse_rfc822(pub_date)

        result.items.append(
            ScrapedItem(
                id=item_id,
                title=title.strip()[:300],
                url=link.strip(),
                content=body[:4000],
                published_at=published_iso,
                meta={
                    "source_url": url,
                    "source_host": "yissum.co.il",
                    "raw_published": pub_date,
                },
            )
        )

    return result


def _text(parent: ET.Element, tag: str) -> str:
    el = parent.find(tag)
    return (el.text or "") if el is not None else ""


def _strip_html(html: str) -> str:
    """Quick-and-dirty: remove tags, collapse whitespace. RSS descriptions are
    short and self-contained so we don't need a real HTML parser here."""
    if not html:
        return ""
    # Strip script/style first so we don't keep their text content.
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Strip remaining tags.
    text = re.sub(r"<[^>]+>", " ", html)
    # Decode common entities.
    text = (
        text.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#039;", "'")
        .replace("&nbsp;", " ")
    )
    # Collapse whitespace.
    return re.sub(r"\s+", " ", text).strip()


def _parse_rfc822(s: str) -> str | None:
    """RSS pubDate is RFC 822, e.g. 'Wed, 14 May 2026 09:00:00 +0000'."""
    if not s:
        return None
    try:
        return parsedate_to_datetime(s).isoformat()
    except (TypeError, ValueError):
        return None
