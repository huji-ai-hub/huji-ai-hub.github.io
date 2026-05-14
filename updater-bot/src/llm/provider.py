"""Abstract LLM interface. Swap providers by changing one config value."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


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


class NewsVerdict(BaseModel):
    """Cheap classifier output: is this scraped link a real, news-worthy item?"""
    is_newsworthy: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str


class NewsDraft(BaseModel):
    """Full bilingual news card produced by the content model.

    Slug must be kebab-case and date-prefixed (e.g. ``2026-05-13-yissum-deal``).
    Body fields hold markdown (paragraphs separated by blank lines, headers OK).
    """
    slug: str
    title: str
    titleHe: str
    summary: str
    summaryHe: str
    body: str          # English markdown body
    bodyHe: str        # Hebrew markdown body
    seoTitle: str
    seoTitleHe: str
    seoDescription: str
    seoDescriptionHe: str
    keywords: list[str] = Field(default_factory=list)
    keywordsHe: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    image: str | None = None  # path under /public, e.g. "/images/foo.jpg"


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

    @abstractmethod
    def classify_news_item(
        self,
        title: str,
        url: str,
        content_snippet: str,
        source_id: str,
    ) -> NewsVerdict: ...

    @abstractmethod
    def draft_news_card(
        self,
        title: str,
        url: str,
        content_snippet: str,
        source_id: str,
        source_name: str,
        available_images: list[str],
    ) -> NewsDraft: ...
