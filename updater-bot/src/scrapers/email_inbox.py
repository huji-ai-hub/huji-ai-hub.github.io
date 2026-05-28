"""Read forwarded emails from the bot's Gmail inbox via IMAP.

The bot has a dedicated Gmail (`huji.ai.hub.bot.inbox@gmail.com`) that
receives forwarded HUJI marketing emails, Scholar Alerts, conference
announcements, and any other curated content a human routes to it.

Why IMAP and not Gmail API:
  - No OAuth app registration needed (just an App Password).
  - Works from any host without setup.
  - Standard protocol, dependency-free (stdlib `imaplib`).

Why this beats HTML scraping:
  - Cloudflare/F5 anti-bot walls don't apply to email.
  - Items are already editorially curated (a human chose to forward them).
  - Signal-to-noise is much higher than blind scraping.

Newsletter splitting:
  HUJI marketing emails ("חדשות העברית") are newsletters with 6+ stories
  per email. If we treat one email as one item, the classifier sees a mixed
  blob (war + bacteria + AI + archaeology) and rejects it as "not specifically
  AI". So we detect newsletter structure and emit one ScrapedItem per story,
  each with the real article URL, story title, and story snippet. The
  classifier then judges each story on its own merits.

Dedupe strategy:
  - Single-item email: stable ID from Message-ID header.
  - Newsletter story: stable ID from a hash of the article URL, so the
    same story forwarded twice (or once via newsletter + once via sitemap)
    doesn't double-propose.

Time-window strategy: fetch only emails received in the last N days
(configurable, default 14). Manifest handles dedupe; the time window
keeps the IMAP fetch small.
"""

from __future__ import annotations

import email
import hashlib
import imaplib
import logging
import re
import urllib.parse as _urllib_parse
from datetime import datetime, timedelta, timezone
from email.message import Message
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup

from ..config import SourceConfig, Secrets
from . import ScrapedItem, ScrapeResult

log = logging.getLogger(__name__)

SOURCE_ID = "email_inbox"

DEFAULT_IMAP_HOST = "imap.gmail.com"
DEFAULT_IMAP_PORT = 993
DEFAULT_FOLDER = "INBOX"
DEFAULT_SINCE_DAYS = 14

# URL patterns that point to a real HUJI news article. An anchor matching
# this inside a newsletter email is treated as a "story link": each one
# becomes its own ScrapedItem so the classifier judges each story on its
# own (not the mixed-topic newsletter blob).
#
# We deliberately match the pattern ANYWHERE in the URL (not just at the
# start) so links wrapped in marketing-platform redirectors still match.
# Example: marketing emails commonly wrap real URLs in tracking links like
# "https://savion.huji.ac.il/r/?id=xyz&url=https://new.huji.ac.il/news/..."
# or "https://email.huji.ac.il/track/click?u=...&p=new.huji.ac.il%2Fnews%2F..."
# The substring search handles both directly-encoded and URL-encoded forms.
#
# Covers Hebrew (/news/<slug>) and English (/en/news/<slug>) variants,
# plus /page/ which HUJI also uses for some research stories.
_STORY_URL_RE = re.compile(
    r"new\.huji\.ac\.il(?:/|%2F)(?:en(?:/|%2F))?(?:news|page)(?:/|%2F)[^\s\"'>?#&]+",
    re.IGNORECASE,
)

# Pull the actual article URL out of a marketing-platform tracking link,
# so the ScrapedItem's url field points at the real article (not the
# tracker). See _resolve_story_url().

# Link text we should NEVER treat as a story title: it's just the CTA.
# Used to skip "Read more" anchors when picking out the story headline.
_CTA_LINK_TEXT = {
    "read more", "read the article", "read article",
    "learn more", "continue reading",
    "המשך לקרוא", "קראו עוד", "להמשך הקריאה", "לקריאת הכתבה",
    "לכתבה המלאה", "לכתבה", "לקריאה",
}


def scrape(cfg: SourceConfig, secrets: Secrets) -> ScrapeResult:
    result = ScrapeResult(source_id=SOURCE_ID)

    if not secrets.bot_inbox_email or not secrets.bot_inbox_app_password:
        result.error = (
            "BOT_INBOX_EMAIL or BOT_INBOX_APP_PASSWORD env var not set. "
            "Set both as repo secrets to enable the email_inbox scraper."
        )
        return result

    host = cfg.imap_host or DEFAULT_IMAP_HOST
    folder = cfg.folder or DEFAULT_FOLDER
    since_days = cfg.since_days or DEFAULT_SINCE_DAYS
    max_items = cfg.max_items or 25

    since_date = datetime.now(timezone.utc) - timedelta(days=since_days)
    # IMAP SINCE wants format like "01-Jan-2026"
    since_str = since_date.strftime("%d-%b-%Y")

    try:
        with imaplib.IMAP4_SSL(host, DEFAULT_IMAP_PORT) as imap:
            try:
                imap.login(secrets.bot_inbox_email, secrets.bot_inbox_app_password)
            except imaplib.IMAP4.error as e:
                result.error = f"IMAP login failed: {e}"
                return result

            status, _ = imap.select(folder)
            if status != "OK":
                result.error = f"IMAP select {folder!r} failed: {status}"
                return result

            status, data = imap.search(None, "SINCE", since_str)
            if status != "OK":
                result.error = f"IMAP search failed: {status}"
                return result

            msg_ids = data[0].split() if data and data[0] else []
            log.info(
                "%s: %d emails since %s in folder %s",
                SOURCE_ID, len(msg_ids), since_str, folder,
            )

            # Newest-first, capped to max_items. IMAP returns oldest-first
            # numeric sequence IDs, so reverse before slicing.
            msg_ids = list(reversed(msg_ids))[:max_items]

            for msg_id in msg_ids:
                items = _fetch_and_parse(imap, msg_id)
                result.items.extend(items)

    except Exception as e:
        result.error = f"IMAP session error: {e}"
        return result

    log.info(
        "%s: produced %d items (after newsletter splitting)",
        SOURCE_ID, len(result.items),
    )
    return result


def _fetch_and_parse(imap: imaplib.IMAP4_SSL, msg_id: bytes) -> list[ScrapedItem]:
    """Fetch one message, return zero or more ScrapedItems.

    Returns multiple items if the email is detected as a newsletter
    (2+ HUJI news article links inside); returns a single item if it's
    a normal email. Uses BODY.PEEK so we don't mark as read.
    """
    status, data = imap.fetch(msg_id, "(BODY.PEEK[])")
    if status != "OK" or not data or not isinstance(data[0], tuple):
        log.warning("%s: fetch failed for msg %s", SOURCE_ID, msg_id)
        return []

    raw = data[0][1]
    msg = email.message_from_bytes(raw)

    subject = _decode_header(msg.get("Subject", "")).strip()
    sender = _decode_header(msg.get("From", "")).strip()
    date_raw = msg.get("Date", "")
    message_id_hdr = msg.get("Message-ID", "").strip()

    if not subject:
        return []

    if message_id_hdr:
        email_item_id = hashlib.sha256(message_id_hdr.encode("utf-8")).hexdigest()[:16]
    else:
        email_item_id = hashlib.sha256(raw).hexdigest()[:16]

    published_iso = _parse_date(date_raw)

    base_meta = {
        "source_host": "email_inbox",
        "sender": sender,
        "raw_date": date_raw,
        "message_id": message_id_hdr,
        "email_subject": subject,
    }

    # Try newsletter splitting first. Needs HTML body, not text/plain.
    html_body = _extract_html(msg)
    if html_body:
        # Two strategies in order:
        #   1. Pattern-based: anchor URLs that contain /news/<slug>. Works
        #      when emails contain direct HUJI links (rare for HUJI marketing,
        #      common for forwarded news from other sources).
        #   2. Structural: image+text+link clusters, regardless of URL
        #      pattern. Works for HUJI marketing emails that wrap everything
        #      in webversion.net trackers.
        stories = _parse_newsletter_stories(html_body)
        if len(stories) < 2 and _looks_like_huji_newsletter(sender, html_body):
            log.info(
                "%s: pattern splitter found %d stories; running structural splitter on %r",
                SOURCE_ID, len(stories), subject[:60],
            )
            stories = _parse_structural_newsletter(html_body)
            log.info(
                "%s: structural splitter produced %d stories",
                SOURCE_ID, len(stories),
            )
            # If we still have nothing, dump a window of the raw HTML
            # around the first webversion.net anchor so we can inspect
            # the actual layout offline. One window per email is plenty.
            if not stories:
                idx = html_body.lower().find("webversion.net/")
                if idx >= 0:
                    window_start = max(0, idx - 800)
                    window_end = min(len(html_body), idx + 1600)
                    snippet = html_body[window_start:window_end]
                    # Newlines kill log readability; collapse to spaces.
                    snippet = " ".join(snippet.split())
                    log.info(
                        "%s: failing-newsletter HTML window (chars %d-%d, total %d): %s",
                        SOURCE_ID, window_start, window_end, len(html_body), snippet,
                    )
        if len(stories) >= 2:
            log.info(
                "%s: newsletter detected (%d stories) in %r",
                SOURCE_ID, len(stories), subject[:60],
            )
            items: list[ScrapedItem] = []
            seen_urls: set[str] = set()
            for story in stories:
                if story["url"] in seen_urls:
                    continue
                seen_urls.add(story["url"])
                # Stable ID: hash of the article URL, so the same story
                # via two sources (newsletter + sitemap) dedupes.
                story_id = hashlib.sha256(story["url"].encode("utf-8")).hexdigest()[:16]
                items.append(ScrapedItem(
                    id=story_id,
                    title=story["title"][:300],
                    url=story["url"],
                    content=story["content"][:6000],
                    published_at=published_iso,
                    meta={
                        **base_meta,
                        "newsletter_email_id": email_item_id,
                        "story_image": story.get("image"),
                    },
                ))
            return items

    # Fallback: single-item email (not a newsletter, or splitter found <2 stories).
    body_text = _extract_body(msg)
    pseudo_url = f"mid:{message_id_hdr or email_item_id}"

    return [ScrapedItem(
        id=email_item_id,
        title=subject[:300],
        url=pseudo_url,
        content=body_text[:6000],
        published_at=published_iso,
        meta=base_meta,
    )]


def _parse_newsletter_stories(html: str) -> list[dict]:
    """Detect repeating story blocks in a newsletter email's HTML.

    Strategy: every story in a HUJI newsletter has a "Read more" link
    pointing to new.huji.ac.il/news/<slug>. Walk up from each such anchor
    to find the surrounding story block, then pull out the title text,
    summary text, and lead image from inside that block.

    Returns a list of dicts with: url, title, content, image.
    Empty list = "not a newsletter, fall back to single-item behavior."
    """
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")

    # Find all anchors that point to a real HUJI news article. We search
    # the FULL URL (after percent-decoding) so links wrapped in marketing
    # platform tracking redirectors still match.
    story_anchors: list[tuple[object, str]] = []  # (anchor, resolved_article_url)
    all_hrefs_sample: list[str] = []  # for diagnostic logging
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href and len(all_hrefs_sample) < 5:
            all_hrefs_sample.append(href[:150])
        article_url = _resolve_story_url(href)
        if article_url:
            story_anchors.append((a, article_url))

    if len(story_anchors) < 2:
        # Diagnostic: log a few sample hrefs so we can see what patterns
        # we're failing to match. Quiet on real newsletters (only fires
        # when splitting doesn't happen). Lets future-Ella debug without
        # piping IMAP creds anywhere.
        if all_hrefs_sample:
            log.info(
                "%s: no newsletter structure detected (found %d HUJI-news anchors out of %d total). Sample hrefs: %s",
                SOURCE_ID, len(story_anchors), len(soup.find_all("a", href=True)),
                " | ".join(all_hrefs_sample),
            )
        return []

    stories: list[dict] = []
    seen_urls: set[str] = set()

    for anchor, resolved_url in story_anchors:
        # Normalize: drop trailing fragment/query so HE + EN variants of the
        # same article dedupe properly.
        url = resolved_url.split("#")[0].split("?")[0].rstrip("/")
        if url in seen_urls:
            continue

        block = _find_story_container(anchor)
        if block is None:
            continue

        title = _extract_story_title(block, anchor)
        if not title:
            continue

        content = _extract_story_text(block, anchor)
        image = _extract_story_image(block)

        seen_urls.add(url)
        stories.append({
            "url": url,
            "title": title,
            "content": content,
            "image": image,
        })

    return stories


def _looks_like_huji_newsletter(sender: str, html: str) -> bool:
    """Heuristic: is this email a HUJI marketing newsletter?

    Triggered by sender domain (savion.huji.ac.il + marketing prefix) and
    by structural fingerprint (lots of webversion.net tracker links + lots
    of images = the email-marketing-platform shape).

    The sender check is the strong signal. Structural fingerprint catches
    forwarded copies where the From: header is Ella's Gmail, not HUJI's.
    """
    sender_lower = sender.lower()
    if "savion.huji.ac.il" in sender_lower:
        return True
    if "marketing" in sender_lower and "huji.ac.il" in sender_lower:
        return True
    # Forwarded: the original sender appears inside the body.
    if "marketing@savion.huji.ac.il" in html.lower():
        return True
    # Structural: lots of webversion.net trackers = bulk email tool.
    if html.lower().count("webversion.net/") >= 5:
        return True
    return False


# Non-story URLs commonly found in HUJI newsletter chrome (top/bottom of email,
# social-media row, "view in browser" link, unsubscribe footer). The structural
# splitter skips anchors with these characteristics so junk doesn't become a card.
_NON_STORY_URL_PARTS = (
    "myaccount.google.com", "accounts.google.com",
    "facebook.com", "twitter.com/", "x.com/",
    "youtube.com", "linkedin.com", "instagram.com",
    "tiktok.com", "telegram.me", "t.me/",
    "unsubscribe", "/preferences", "mailto:", "tel:",
    "javascript:", "/whatsapp", "wa.me/",
)

_NON_STORY_LINK_TEXTS = {
    "subscribe", "unsubscribe", "view in browser", "web version",
    "להסיר מרשימת התפוצה", "להסיר", "לצפייה בדפדפן",
    "facebook", "twitter", "linkedin", "instagram", "youtube",
}


def _is_real_image(img) -> bool:
    """Skip 1x1 tracking pixels and tiny icons."""
    src = (img.get("src") or "").strip()
    if not src or src.startswith("data:"):
        return False
    w = str(img.get("width", "")).strip()
    h = str(img.get("height", "")).strip()
    if w in ("1", "0") or h in ("1", "0"):
        return False
    return True


def _parse_structural_newsletter(html: str) -> list[dict]:
    """Structure-based splitter for HUJI marketing newsletters.

    HUJI newsletters arrive as deeply-nested Outlook/Word-style HTML tables
    where each story is its own inner <table> or <tr> with: real image,
    title text, blurb, and a webversion.net "Read more" anchor. Stories
    don't share a parent until the outer ~600px-wide email table.

    Strategy: scan every <tr> / <td> / <table> in the document for ones
    that look like a single story: contain a real (non-tracking-pixel)
    image AND at least one webversion.net anchor AND text in the 60-1500
    char range (longer = wrapping container, shorter = decorative cell).
    Each match becomes one story. Dedupe by URL and by title.

    Returns a list of dicts: {url, title, content, image}.

    Heavily diagnostic: counters + sample reject traces in one INFO line.
    """
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")

    stories: list[dict] = []
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()

    # Counters: containers rejected at each filter stage. INFO-logged at end.
    rej = {
        "no_real_image": 0,
        "no_story_anchor": 0,
        "text_too_short": 0,
        "text_too_long": 0,
        "no_title": 0,
        "title_too_short": 0,
        "title_junk": 0,
        "url_dup": 0,
        "title_dup": 0,
        "accepted": 0,
    }
    sample_rejects: list[str] = []  # short trace of why each rejected container failed

    def trace(reason: str, extra: str = "") -> None:
        if len(sample_rejects) < 8:
            sample_rejects.append(f"{reason}|{extra[:120]}")

    # Walk every plausible single-story container. tr / td / table are
    # the shapes Outlook/Word-style email HTML uses.
    candidates = soup.find_all(["tr", "td", "table"])

    for container in candidates:
        # Must have a real image (not a 1x1 tracking pixel).
        real_imgs = [img for img in container.find_all("img") if _is_real_image(img)]
        if not real_imgs:
            rej["no_real_image"] += 1
            continue

        # Must have at least one webversion.net (or similar tracker) anchor
        # that isn't junk. We're permissive on URL pattern because trackers
        # are opaque.
        story_anchors = []
        for a in container.find_all("a", href=True):
            href = a["href"].strip()
            if not href:
                continue
            href_lower = href.lower()
            if any(p in href_lower for p in _NON_STORY_URL_PARTS):
                continue
            link_text = _clean(a.get_text(separator=" ")).lower()
            if link_text in _NON_STORY_LINK_TEXTS:
                continue
            # webversion.net is the HUJI tracker domain; allow any non-junk
            # external URL too to handle other newsletter platforms.
            story_anchors.append(a)
        if not story_anchors:
            rej["no_story_anchor"] += 1
            continue

        text = _clean(container.get_text(separator=" "))
        text_len = len(text)
        if text_len < 60:
            rej["text_too_short"] += 1
            continue
        # Wrapping containers (the whole email, the 600px main table) have
        # thousands of chars. Single stories are usually 80-800 chars.
        # 1500 gives buffer for stories with long Hebrew descriptions.
        if text_len > 1500:
            rej["text_too_long"] += 1
            continue

        # Title: the longest non-CTA-shaped text snippet inside.
        title = _extract_best_title(container)
        if not title:
            rej["no_title"] += 1
            trace("no_title", f"tag={container.name} tlen={text_len}")
            continue
        if len(title) < 8:
            rej["title_too_short"] += 1
            trace("title_short", f"title={title!r}")
            continue
        if title.lower() in _NON_STORY_LINK_TEXTS:
            rej["title_junk"] += 1
            continue

        # Use the first non-junk webversion link as the story URL.
        url = story_anchors[0]["href"].strip().split("#")[0].rstrip("/")
        title_key = title.lower()[:120]
        if url in seen_urls:
            rej["url_dup"] += 1
            continue
        if title_key in seen_titles:
            rej["title_dup"] += 1
            continue
        seen_urls.add(url)
        seen_titles.add(title_key)

        # Story image = first real image in the container.
        image = real_imgs[0].get("src", "").strip() or None

        rej["accepted"] += 1
        stories.append({
            "url": url,
            "title": title,
            "content": text[:6000],
            "image": image,
        })

    log.info(
        "%s: structural container outcomes: %s; samples: %s",
        SOURCE_ID,
        ", ".join(f"{k}={v}" for k, v in rej.items() if v),
        " || ".join(sample_rejects) if sample_rejects else "(none)",
    )

    return stories


def _extract_best_title(container) -> str:
    """Find the most title-like string anywhere inside the container.

    Looks at headings first, then bold/strong text. Returns the longest
    candidate that's not a CTA / junk text and is reasonable length.
    """
    candidates: list[str] = []

    # Headings get strong preference.
    for tag_name in ("h1", "h2", "h3", "h4"):
        for h in container.find_all(tag_name):
            text = _clean(h.get_text(separator=" "))
            if text and 8 <= len(text) <= 200:
                candidates.append(text)
    if candidates:
        # Return longest heading.
        return max(candidates, key=len)

    # Fall back to bold-styled text (HUJI titles are often styled bold +
    # colored, with no semantic heading tag).
    for tag_name in ("strong", "b"):
        for s in container.find_all(tag_name):
            text = _clean(s.get_text(separator=" "))
            if text and 8 <= len(text) <= 200 and text.lower() not in _CTA_LINK_TEXT:
                candidates.append(text)
    if candidates:
        return max(candidates, key=len)

    # Last resort: longest <p> or <span> text in the right size range.
    for tag_name in ("p", "span", "td"):
        for el in container.find_all(tag_name):
            text = _clean(el.get_text(separator=" "))
            if text and 10 <= len(text) <= 200 and text.lower() not in _CTA_LINK_TEXT:
                candidates.append(text)
    if candidates:
        return max(candidates, key=len)

    return ""


def _resolve_story_url(href: str) -> str | None:
    """Return the canonical https://new.huji.ac.il/news/<slug> URL embedded
    in `href`, or None if no match. Handles three cases:

      1. Direct link:    https://new.huji.ac.il/news/foo
      2. Tracker with the article URL in a query parameter (percent-encoded):
         https://savion.huji.ac.il/r/?id=x&url=https%3A%2F%2Fnew.huji.ac.il%2Fnews%2Ffoo
      3. Tracker that just contains the article URL inline (no encoding):
         https://email.huji.ac.il/c/eJxNjU.../new.huji.ac.il/news/foo
    """
    if not href:
        return None

    # First try the raw href (case 1 and case 3).
    m = _STORY_URL_RE.search(href)
    if m:
        # Reconstruct a clean https://new.huji.ac.il/... URL. Strip any
        # percent-encoded slashes back to real ones.
        extracted = m.group(0).replace("%2F", "/").replace("%2f", "/")
        return "https://" + extracted

    # Then try percent-decoded (case 2: URL hidden inside a query param).
    try:
        decoded = _urllib_parse.unquote(href)
    except Exception:
        decoded = href
    if decoded != href:
        m = _STORY_URL_RE.search(decoded)
        if m:
            extracted = m.group(0).replace("%2F", "/").replace("%2f", "/")
            return "https://" + extracted

    return None


def _find_story_container(anchor) -> object | None:
    """Walk up from a story link to find the smallest per-story container.

    HUJI newsletters use table-based layout: each story sits in its own
    <td> (or <div>) with an image + title + blurb + CTA. We want THAT
    cell, NOT the wrapping <table> that holds every story (which would
    return the same container for every anchor and lose per-story
    boundaries).

    Strategy: walk up looking for the FIRST per-story-cell-shaped node:
    a <td>/<div>/<li> that contains both an <img> and meaningful text.
    Stop there. Do not climb past it into the table.
    """
    node = anchor
    for _ in range(10):  # Bounded climb; don't walk all the way to <body>.
        parent = node.parent
        if parent is None or parent.name in ("body", "html"):
            break
        node = parent
        # The first per-story cell wins. Image presence is the cheap
        # signal that we're inside a story block (not a list-of-links
        # block at the bottom of the email).
        #
        # Include <tr> because HUJI newsletters frequently put the image
        # in a left <td> and the title+CTA in a right <td>, so the
        # smallest container holding both is the <tr> wrapping them.
        if node.name in ("td", "tr", "div", "li") and node.find("img") is not None:
            text_len = len(node.get_text(strip=True))
            if text_len > 20:
                # Sanity ceiling: if the "container" holds more than 2000
                # characters of text, it's the wrapping table-of-stories,
                # not a single story cell. Keep walking.
                if text_len < 2000:
                    return node
    # No per-story container found; fall back to whatever we ended at
    # if it has some text. Worst case we'll get a too-broad block but
    # _parse_newsletter_stories will dedupe by URL so we don't double-emit.
    if node and len(node.get_text(strip=True)) > 30:
        return node
    return None


def _extract_story_title(block, anchor) -> str:
    """Find the best title-like string in a story block.

    Heuristic order:
      1. <h1>-<h4> inside the block
      2. <strong> or <b> with reasonably-long text
      3. The first non-CTA short line of text in the block
    """
    for tag_name in ("h1", "h2", "h3", "h4"):
        h = block.find(tag_name)
        if h:
            text = _clean(h.get_text(separator=" "))
            if text and len(text) > 4:
                return text

    for tag_name in ("strong", "b"):
        for s in block.find_all(tag_name):
            text = _clean(s.get_text(separator=" "))
            if text and 5 <= len(text) <= 200 and text.lower() not in _CTA_LINK_TEXT:
                return text

    # Fallback: first text-bearing element that's not the CTA link.
    anchor_text = _clean(anchor.get_text(separator=" ")).lower()
    for el in block.descendants:
        if getattr(el, "name", None) in (None, "br"):
            continue
        text = _clean(el.get_text(separator=" ")) if hasattr(el, "get_text") else ""
        if not text or len(text) < 8 or len(text) > 200:
            continue
        if text.lower() in _CTA_LINK_TEXT or text.lower() == anchor_text:
            continue
        return text

    return ""


def _extract_story_text(block, anchor) -> str:
    """Return the body text of the story, with the CTA link removed."""
    # Make a working copy so we can mutate without affecting siblings.
    copy = BeautifulSoup(str(block), "lxml")
    # Strip script/style noise.
    for tag in copy.find_all(["script", "style"]):
        tag.decompose()
    # Strip the CTA anchor (and clones of it) so it doesn't pollute snippet.
    cta_lower = _clean(anchor.get_text(separator=" ")).lower()
    for a in copy.find_all("a"):
        a_text = _clean(a.get_text(separator=" ")).lower()
        if a_text in _CTA_LINK_TEXT or a_text == cta_lower:
            a.decompose()

    text = copy.get_text(separator=" ")
    return _clean(text)


def _extract_story_image(block) -> str | None:
    """Return the first <img src> inside the block, if any. Skips 1x1
    tracking pixels and tiny icons by ignoring tiny declared widths."""
    for img in block.find_all("img"):
        src = (img.get("src") or "").strip()
        if not src or src.startswith("data:"):
            continue
        # Skip obvious tracking pixels: explicit width="1" or height="1".
        w = img.get("width", "")
        h = img.get("height", "")
        if w in ("1", "0") or h in ("1", "0"):
            continue
        return src
    return None


def _clean(s: str) -> str:
    """Collapse whitespace; trim."""
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip()


def _decode_header(value: str) -> str:
    """Decode RFC 2047 encoded headers like '=?utf-8?B?...?=' into plain text."""
    if not value:
        return ""
    try:
        parts = email.header.decode_header(value)
    except Exception:
        return value
    decoded = []
    for chunk, charset in parts:
        if isinstance(chunk, bytes):
            try:
                decoded.append(chunk.decode(charset or "utf-8", errors="replace"))
            except (LookupError, UnicodeDecodeError):
                decoded.append(chunk.decode("utf-8", errors="replace"))
        else:
            decoded.append(chunk)
    return "".join(decoded)


def _extract_html(msg: Message) -> str:
    """Return the text/html part of an email if present, else empty string.

    Newsletter splitting needs HTML structure: text/plain is a flattened
    blob that loses story boundaries.
    """
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disposition = (part.get("Content-Disposition") or "").lower()
            if "attachment" in disposition:
                continue
            if ctype == "text/html":
                return _decode_payload(part)
    elif msg.get_content_type() == "text/html":
        return _decode_payload(msg)
    return ""


def _extract_body(msg: Message) -> str:
    """Return the best plaintext body from an email. Multipart-aware.

    Prefers text/plain over text/html; falls back to HTML with tags stripped.
    Used only as the single-item fallback (non-newsletter emails).
    """
    text_part = None
    html_part = None

    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disposition = (part.get("Content-Disposition") or "").lower()
            if "attachment" in disposition:
                continue
            if ctype == "text/plain" and text_part is None:
                text_part = part
            elif ctype == "text/html" and html_part is None:
                html_part = part
    else:
        ctype = msg.get_content_type()
        if ctype == "text/plain":
            text_part = msg
        elif ctype == "text/html":
            html_part = msg

    if text_part is not None:
        return _decode_payload(text_part)

    if html_part is not None:
        html = _decode_payload(html_part)
        return _strip_html(html)

    return ""


def _decode_payload(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except (LookupError, UnicodeDecodeError):
        return payload.decode("utf-8", errors="replace")


def _strip_html(html: str) -> str:
    """Tag-strip + whitespace-collapse. Good enough for email bodies."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    return re.sub(r"\s+", " ", text).strip()


def _parse_date(s: str) -> str | None:
    """RFC 2822 date in Email headers, e.g. 'Wed, 14 May 2026 09:00:00 +0000'."""
    if not s:
        return None
    try:
        return parsedate_to_datetime(s).isoformat()
    except (TypeError, ValueError):
        return None
