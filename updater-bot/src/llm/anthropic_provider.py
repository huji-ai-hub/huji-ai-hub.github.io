"""Claude implementation of LLMProvider. Uses prompt caching on the system prompt."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

import anthropic

from . import prompts
from .provider import LLMProvider, NewsDraft, NewsVerdict, RelevanceVerdict, StaleDateVerdict

log = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        classifier_model: str,
        content_model: str,
        max_tokens: int = 4096,
        max_retries: int = 3,
    ):
        self.client = anthropic.Anthropic(api_key=api_key, max_retries=max_retries)
        self.classifier_model = classifier_model
        self.content_model = content_model
        self.max_tokens = max_tokens

    # ---- public methods --------------------------------------------------

    def assess_relevance(
        self,
        existing_content: str,
        source_id: str,
        title: str,
        url: str,
        published_at: str | None,
        meta: dict[str, Any],
    ) -> RelevanceVerdict:
        user = prompts.RELEVANCE_PROMPT_TEMPLATE.format(
            existing_content=existing_content[:8000],
            source_id=source_id,
            title=title,
            url=url,
            published_at=published_at or "(unknown)",
            meta_json=json.dumps(meta, sort_keys=True),
        )
        text = self._call(self.content_model, user)
        return _parse_json(text, RelevanceVerdict)

    def classify_stale_date(self, date_str: str, context: str) -> StaleDateVerdict:
        user = prompts.STALE_DATE_CLASSIFY_TEMPLATE.format(date=date_str, context=context)
        text = self._call(self.classifier_model, user, max_tokens=512)
        return _parse_json(text, StaleDateVerdict)

    def generate_commit_message(self, file_path: str, source_id: str, reason: str) -> str:
        user = prompts.COMMIT_MESSAGE_TEMPLATE.format(
            file_path=file_path, source_id=source_id, reason=reason
        )
        text = self._call(self.classifier_model, user, max_tokens=128)
        # Strip quotes / extra whitespace if the model added any.
        return text.strip().strip('"').splitlines()[0][:120]

    def classify_news_item(
        self,
        title: str,
        url: str,
        content_snippet: str,
        source_id: str,
    ) -> NewsVerdict:
        user = prompts.NEWS_CLASSIFY_TEMPLATE.format(
            source_id=source_id,
            title=title,
            url=url,
            content_snippet=(content_snippet or "(none)")[:1500],
        )
        text = self._call(self.classifier_model, user, max_tokens=400)
        return _parse_json(text, NewsVerdict)

    def draft_news_card(
        self,
        title: str,
        url: str,
        content_snippet: str,
        source_id: str,
        source_name: str,
        available_images: list[str],
    ) -> NewsDraft:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        user = prompts.NEWS_DRAFT_TEMPLATE.format(
            source_id=source_id,
            source_name=source_name,
            title=title,
            url=url,
            content_snippet=(content_snippet or "(none)")[:2000],
            today=today,
            available_images="\n".join(f"  - {img}" for img in available_images) or "  (none available)",
        )
        text = self._call(self.content_model, user, max_tokens=4000)
        return _parse_json(text, NewsDraft)

    # ---- internals --------------------------------------------------------

    def _call(self, model: str, user_message: str, max_tokens: int | None = None) -> str:
        # System prompt is identical across calls — cache_control on it lets the
        # API serve cached prefix tokens at ~10% cost on subsequent requests.
        # See shared/prompt-caching.md: any byte-change in the prefix invalidates
        # downstream, so SYSTEM_PROMPT must NOT interpolate timestamps or per-call data.
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                resp = self.client.messages.create(
                    model=model,
                    max_tokens=max_tokens or self.max_tokens,
                    system=[
                        {
                            "type": "text",
                            "text": prompts.SYSTEM_PROMPT,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    messages=[{"role": "user", "content": user_message}],
                )
                for block in resp.content:
                    if block.type == "text":
                        return block.text
                return ""
            except (anthropic.APIConnectionError, anthropic.APIStatusError) as e:
                last_err = e
                # Exponential backoff (SDK already retries inside, this catches what slips through).
                wait = 2**attempt
                log.warning("LLM call failed (attempt %d): %s; sleeping %ds", attempt + 1, e, wait)
                time.sleep(wait)
        raise RuntimeError(f"LLM call failed after retries: {last_err}")


def _parse_json(text: str, model_cls):
    """Parse JSON out of an LLM response, tolerating markdown code fences."""
    text = text.strip()
    if text.startswith("```"):
        # Strip ``` or ```json fences.
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM did not return valid JSON: {text[:200]}") from e
    return model_cls.model_validate(data)
