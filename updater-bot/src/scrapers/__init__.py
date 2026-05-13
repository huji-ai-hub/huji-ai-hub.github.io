"""Scrapers — one file per source. All return ScrapeResult."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class ScrapedItem(BaseModel):
    id: str
    title: str
    url: str
    published_at: str | None = None
    content: str = ""
    meta: dict[str, Any] = Field(default_factory=dict)


class ScrapeResult(BaseModel):
    source_id: str
    fetched_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    items: list[ScrapedItem] = Field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None
