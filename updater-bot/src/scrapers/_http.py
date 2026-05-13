"""Shared HTTP client. Polite UA, sane timeout."""

from __future__ import annotations

import httpx

# Polite identifier we'd ideally use everywhere. Some hosts (Yissum behind
# Cloudflare) return 403 when User-Agent doesn't look browser-like, so
# scrapers can pick BROWSER_UA instead when they hit known anti-bot walls.
USER_AGENT = "huji-ai-hub-bot/0.1 (+https://github.com/huji-ai-hub/huji-ai-hub.github.io)"

# Standard desktop-Chrome string. Use only when the polite UA is being blocked
# by a bot wall on a host that's clearly OK with public scraping (e.g. a
# public news index page on a tech-transfer company site).
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)

DEFAULT_TIMEOUT = httpx.Timeout(20.0, connect=5.0)


def client(*, browser_ua: bool = False, **overrides) -> httpx.Client:
    ua = BROWSER_UA if browser_ua else USER_AGENT
    return httpx.Client(
        timeout=overrides.pop("timeout", DEFAULT_TIMEOUT),
        headers={"User-Agent": ua, **overrides.pop("headers", {})},
        follow_redirects=True,
        **overrides,
    )
