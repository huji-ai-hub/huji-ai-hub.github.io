"""Checkers — run against the live site or against scraped data.

Each checker returns a list of Findings. The proposal builder turns Findings
into Proposals.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Finding(BaseModel):
    checker_id: str
    kind: str  # e.g. "dead_link", "missing_faculty", "extra_faculty", "stale_date"
    severity: str = "medium"  # "low" | "medium" | "high"
    description: str
    file_path: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
