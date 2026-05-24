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

Dedupe strategy: each email gets a stable ID from its Message-ID header.
The manifest tracks seen IDs the same way as any other scraper, so a
re-run that pulls the same emails doesn't re-propose anything.

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
                item = _fetch_and_parse(imap, msg_id)
                if item is not None:
                    result.items.append(item)

    except Exception as e:
        result.error = f"IMAP session error: {e}"
        return result

    return result


def _fetch_and_parse(imap: imaplib.IMAP4_SSL, msg_id: bytes) -> ScrapedItem | None:
    """Fetch one message, parse headers + body, return a ScrapedItem.

    Uses BODY.PEEK so we don't mark the message as read on the server.
    The manifest handles dedupe; we don't want IMAP state to drift.
    """
    status, data = imap.fetch(msg_id, "(BODY.PEEK[])")
    if status != "OK" or not data or not isinstance(data[0], tuple):
        log.warning("%s: fetch failed for msg %s", SOURCE_ID, msg_id)
        return None

    raw = data[0][1]
    msg = email.message_from_bytes(raw)

    subject = _decode_header(msg.get("Subject", "")).strip()
    sender = _decode_header(msg.get("From", "")).strip()
    date_raw = msg.get("Date", "")
    message_id_hdr = msg.get("Message-ID", "").strip()

    if not subject:
        return None

    # Build a stable item ID. Prefer the email's own Message-ID; fall back
    # to a hash of the raw bytes so we still get something stable.
    if message_id_hdr:
        item_id = hashlib.sha256(message_id_hdr.encode("utf-8")).hexdigest()[:16]
    else:
        item_id = hashlib.sha256(raw).hexdigest()[:16]

    body = _extract_body(msg)

    # Pseudo-URL: emails don't have URLs, but the news pipeline expects one.
    # Use a `mid:` scheme with the message ID so it's at least addressable.
    # The card's actual sourceUrl comes from links inside the email body,
    # which the LLM drafter extracts.
    pseudo_url = f"mid:{message_id_hdr or item_id}"

    published_iso = _parse_date(date_raw)

    return ScrapedItem(
        id=item_id,
        title=subject[:300],
        url=pseudo_url,
        content=body[:6000],
        published_at=published_iso,
        meta={
            "source_host": "email_inbox",
            "sender": sender,
            "raw_date": date_raw,
            "message_id": message_id_hdr,
        },
    )


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


def _extract_body(msg: Message) -> str:
    """Return the best plaintext body from an email. Multipart-aware.

    Prefers text/plain over text/html; falls back to HTML with tags stripped.
    Skips attachments. Decodes Content-Transfer-Encoding (quoted-printable
    and base64 are handled by email.message.get_payload(decode=True)).
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
