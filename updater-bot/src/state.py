"""State manifest — what the bot has seen across runs.

Committed to the repo so the next run knows what's new (or already-rejected).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class SourceState:
    last_run: str | None = None
    seen_ids: list[str] = field(default_factory=list)
    # IDs the human explicitly closed without merging — never re-propose.
    dismissed_ids: list[str] = field(default_factory=list)


@dataclass
class Manifest:
    sources: dict[str, SourceState] = field(default_factory=dict)
    schema_version: int = 1

    @classmethod
    def load(cls, path: Path) -> "Manifest":
        if not path.exists():
            return cls()
        raw = json.loads(path.read_text())
        sources = {
            sid: SourceState(**state) for sid, state in raw.get("sources", {}).items()
        }
        return cls(sources=sources, schema_version=raw.get("schema_version", 1))

    def save(self, path: Path) -> None:
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "sources": {
                sid: {
                    "last_run": s.last_run,
                    "seen_ids": sorted(set(s.seen_ids)),
                    "dismissed_ids": sorted(set(s.dismissed_ids)),
                }
                for sid, s in self.sources.items()
            },
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    def get(self, source_id: str) -> SourceState:
        if source_id not in self.sources:
            self.sources[source_id] = SourceState()
        return self.sources[source_id]

    def mark_seen(self, source_id: str, item_ids: list[str]) -> None:
        state = self.get(source_id)
        state.seen_ids = sorted(set(state.seen_ids + item_ids))
        state.last_run = datetime.now(timezone.utc).isoformat()

    def is_new(self, source_id: str, item_id: str) -> bool:
        state = self.get(source_id)
        return item_id not in state.seen_ids and item_id not in state.dismissed_ids
