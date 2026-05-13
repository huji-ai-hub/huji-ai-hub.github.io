"""Configuration loading. Validates config.toml + reads secrets from env."""

from __future__ import annotations

import os
import sys
import tomllib
from pathlib import Path

from pydantic import BaseModel, Field


class ScheduleConfig(BaseModel):
    cron: str = "0 3 * * 1"
    enabled: bool = True


class SiteConfig(BaseModel):
    live_url: str
    faculty_dir: str
    data_dir: str


class GitHubConfig(BaseModel):
    repo: str
    base_branch: str = "main"
    branch_prefix: str = "bot/auto-update"


class ReviewConfig(BaseModel):
    max_changes_per_pr: int = 20
    min_confidence: float = 0.5


class LLMConfig(BaseModel):
    provider: str = "anthropic"
    classifier_model: str = "claude-haiku-4-5"
    content_model: str = "claude-sonnet-4-6"
    max_tokens: int = 4096
    max_retries: int = 3


class SourceConfig(BaseModel):
    enabled: bool = True
    url: str | None = None
    max_items: int | None = None
    request_interval_sec: float | None = None
    max_publications: int | None = None
    skip_domains: list[str] = Field(default_factory=list)


class CheckerConfig(BaseModel):
    enabled: bool = True
    timeout_sec: int | None = None
    ignore_statuses: list[int] = Field(default_factory=list)
    external_skip: list[str] = Field(default_factory=list)
    name_match_threshold: float | None = None
    past_threshold_days: int | None = None


class Secrets(BaseModel):
    anthropic_api_key: str
    github_token: str


class Config(BaseModel):
    schedule: ScheduleConfig
    site: SiteConfig
    github: GitHubConfig
    review: ReviewConfig
    llm: LLMConfig
    sources: dict[str, SourceConfig]
    checkers: dict[str, CheckerConfig]
    secrets: Secrets
    dry_run: bool = False


def load_config(config_path: Path | None = None, dry_run: bool = False) -> Config:
    if config_path is None:
        config_path = Path(__file__).resolve().parent.parent / "config.toml"

    with config_path.open("rb") as f:
        raw = tomllib.load(f)

    # GITHUB_TOKEN is the local-dev convention; BOT_GITHUB_TOKEN is the Actions secret name.
    github_token = os.environ.get("BOT_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

    if not github_token:
        print("ERROR: BOT_GITHUB_TOKEN (or GITHUB_TOKEN) env var is required", file=sys.stderr)
        sys.exit(2)
    if not anthropic_key:
        print("ERROR: ANTHROPIC_API_KEY env var is required", file=sys.stderr)
        sys.exit(2)

    # Allow overriding the GitHub repo via env (handy for testing against a fork).
    if env_repo := os.environ.get("GITHUB_REPO"):
        raw["github"]["repo"] = env_repo

    return Config(
        **raw,
        secrets=Secrets(anthropic_api_key=anthropic_key, github_token=github_token),
        dry_run=dry_run or bool(os.environ.get("DRY_RUN")),
    )
