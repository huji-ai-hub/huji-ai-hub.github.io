"""Shared HTTP client.

Uses `curl_cffi` (Chrome-impersonating libcurl) instead of `httpx` so that
hosts behind Cloudflare's IP/TLS-fingerprint anti-bot wall (notably Yissum's
RSS at yissum.co.il) will actually serve us a response when we run from
GitHub Actions IPs. `httpx` was getting 403 on Yissum from cloud IPs even
with a desktop-Chrome User-Agent string, because Cloudflare checks the
TLS handshake fingerprint as well; curl_cffi replays the Chrome handshake
verbatim so it looks like a real Chrome browser at the TLS layer.

We expose the same surface as before:
    with client(browser_ua=True) as http:
        resp = http.get(url)
        resp.raise_for_status()
        resp.text

The `browser_ua` flag now controls whether we impersonate Chrome (True) or
send the polite huji-ai-hub-bot UA with a generic curl handshake (False).
For sources that are happy with anonymous polite bots (most HUJI .ac.il
hosts), pass browser_ua=False. For Cloudflare-walled hosts, True.
"""

from __future__ import annotations

from contextlib import contextmanager

from curl_cffi import requests as curl_requests

# Polite identifier we'd ideally use everywhere. Some hosts (Yissum behind
# Cloudflare) return 403 when User-Agent doesn't look browser-like AND the
# TLS handshake isn't a real browser's; we handle both by passing
# impersonate="chrome" in client() when browser_ua=True.
USER_AGENT = "huji-ai-hub-bot/0.1 (+https://github.com/huji-ai-hub/huji-ai-hub.github.io)"

# Default request timeout in seconds (connect + read combined; curl_cffi
# uses a single number, not the httpx Timeout split).
DEFAULT_TIMEOUT = 20.0


class _Session:
    """Thin shim that mimics the bits of httpx.Client our scrapers use.

    Scrapers call `http.get(url)` and read `.status_code`, `.text`,
    `.raise_for_status()`. curl_cffi's Response already has all three;
    we just route .get through the right impersonation profile.
    """

    def __init__(self, *, impersonate: str | None, headers: dict, timeout: float):
        self._impersonate = impersonate
        self._headers = headers
        self._timeout = timeout

    def get(self, url: str, **kwargs):
        # Merge any per-call headers/timeout overrides on top of the
        # session defaults.
        headers = {**self._headers, **(kwargs.pop("headers", {}) or {})}
        timeout = kwargs.pop("timeout", self._timeout)
        return curl_requests.get(
            url,
            headers=headers,
            timeout=timeout,
            impersonate=self._impersonate,
            allow_redirects=True,
            **kwargs,
        )

    def close(self):
        # curl_cffi.requests is stateless at module level; nothing to close.
        return None


@contextmanager
def client(*, browser_ua: bool = False, **overrides):
    """Yield a session object scrapers can use to issue GETs.

    - browser_ua=True: TLS-handshake impersonates Chrome AND sends a
      Chrome User-Agent string. Use for Cloudflare-walled hosts.
    - browser_ua=False: sends the polite bot UA over a default libcurl
      handshake. Use for HUJI .ac.il and friendly RSS endpoints.
    """
    if browser_ua:
        impersonate = "chrome"
        ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        )
    else:
        impersonate = None
        ua = USER_AGENT

    headers = {"User-Agent": ua, **overrides.pop("headers", {})}
    timeout = overrides.pop("timeout", DEFAULT_TIMEOUT)

    session = _Session(impersonate=impersonate, headers=headers, timeout=timeout)
    try:
        yield session
    finally:
        session.close()
