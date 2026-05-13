"""Map of where each kind of content lives in the site repo."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class ContentPaths:
    repo_root: Path
    faculty_dir: Path
    data_dir: Path
    state_file: Path

    @classmethod
    def from_repo_root(cls, repo_root: Path, faculty_rel: str, data_rel: str) -> "ContentPaths":
        return cls(
            repo_root=repo_root,
            faculty_dir=repo_root / faculty_rel,
            data_dir=repo_root / data_rel,
            state_file=repo_root / "updater-bot" / "state" / "manifest.json",
        )

    def all_markdown(self) -> list[Path]:
        """Every markdown file the bot might want to scan or edit."""
        out: list[Path] = []
        for d in (self.faculty_dir,):
            if d.exists():
                out.extend(sorted(d.glob("**/*.md")))
        return out
