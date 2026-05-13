"""Typed Proposal model: the unit of work between detection and git."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ChangeType = Literal[
    "frontmatter",
    "body_append",
    "body_replace",
    "new_file",
    "comment",
]


class Proposal(BaseModel):
    source_id: str
    item_id: str  # for manifest dedupe
    file_path: str
    change_type: ChangeType
    old_content: str | None = None
    new_content: str
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)
    raw_evidence: dict[str, Any] = Field(default_factory=dict)
    commit_message: str = ""  # filled in by builder before applier runs
