"""Shared HTTP client. Polite UA, sane timeout."""

from __future__ import annotations

import httpx

USER_AGENT = "huji-ai-hub-bot/0.1 (+https://github.com/huji-ai-hub/huji-ai-hub.github.io)"

DEFAULT_TIMEOUT = httpx.Timeout(20.0, connect=5.0)


def client(**overrides) -> httpx.Client:
    return httpx.Client(
        timeout=overrides.pop("timeout", DEFAULT_TIMEOUT),
        headers={"User-Agent": USER_AGENT, **overrides.pop("headers", {})},
        follow_redirects=True,
        **overrides,
    )
