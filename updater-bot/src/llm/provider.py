"""Abstract LLM interface. Swap providers by changing one config value."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class RelevanceVerdict(BaseModel):
    worth_proposing: bool
    confidence: float
    reason: str
    proposed_change_type: str  # "frontmatter" | "body_append" | "body_replace" | "comment" | "none"
    new_content_snippet: str = ""


class StaleDateVerdict(BaseModel):
    is_stale: bool
    confidence: float
    reason: str


class LLMProvider(ABC):
    """Minimal surface — extend only when callers actually need more."""

    @abstractmethod
    def assess_relevance(
        self,
        existing_content: str,
        source_id: str,
        title: str,
        url: str,
        published_at: str | None,
        meta: dict[str, Any],
    ) -> RelevanceVerdict: ...

    @abstractmethod
    def classify_stale_date(self, date_str: str, context: str) -> StaleDateVerdict: ...

    @abstractmethod
    def generate_commit_message(self, file_path: str, source_id: str, reason: str) -> str: ...
