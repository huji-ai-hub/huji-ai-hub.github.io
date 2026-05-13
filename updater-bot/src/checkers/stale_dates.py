"""Find date strings in content files that describe past-tense future events."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from pathlib import Path

from ..config import CheckerConfig
from . import Finding

log = logging.getLogger(__name__)

CHECKER_ID = "stale_dates"

# Patterns for "future-tense" wording near a date.
_FUTURE_HINTS = re.compile(
    r"\b(upcoming|will be held|will take place|registration opens|register by|"
    r"join us|save the date|schedule[ds]? for|to be held)\b",
    re.IGNORECASE,
)

_DATE_PATTERNS = [
    # ISO: 2025-10-15
    re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"),
    # 15 October 2025 / 15 Oct 2025
    re.compile(
        r"\b(\d{1,2})\s+"
        r"(January|February|March|April|May|June|July|August|September|October|November|December|"
        r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
        r"(\d{4})\b",
        re.IGNORECASE,
    ),
]

_MONTH_TO_NUM = {
    m.lower(): i + 1
    for i, m in enumerate(
        ["January", "February", "March", "April", "May", "June",
         "July", "August", "September", "October", "November", "December"]
    )
}
_MONTH_TO_NUM.update({m[:3].lower(): n for m, n in list(_MONTH_TO_NUM.items())})


def check(markdown_files: list[Path], cfg: CheckerConfig) -> list[Finding]:
    today = date.today()
    threshold = cfg.past_threshold_days or 1
    findings: list[Finding] = []

    for path in markdown_files:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as e:
            log.debug("stale_dates: skipping %s: %s", path, e)
            continue

        for match, parsed_date in _find_dates(text):
            days_past = (today - parsed_date).days
            if days_past < threshold:
                continue

            ctx_start = max(0, match.start() - 100)
            ctx_end = min(len(text), match.end() + 100)
            context = text[ctx_start:ctx_end].replace("\n", " ")

            if _FUTURE_HINTS.search(context):
                findings.append(
                    Finding(
                        checker_id=CHECKER_ID,
                        kind="stale_date",
                        severity="medium" if days_past < 90 else "low",
                        description=(
                            f"Past-dated event still described in future tense in {path.name} "
                            f"({parsed_date.isoformat()}, {days_past} days ago)"
                        ),
                        file_path=str(path),
                        evidence={
                            "date": parsed_date.isoformat(),
                            "matched_text": match.group(0),
                            "context": context,
                            "needs_classification": False,
                        },
                    )
                )
            elif days_past < 365:
                # Ambiguous — bot will optionally ask the LLM to classify in the
                # proposal stage. Still surface it but mark it as needing review.
                findings.append(
                    Finding(
                        checker_id=CHECKER_ID,
                        kind="stale_date",
                        severity="low",
                        description=(
                            f"Past date in {path.name} ({parsed_date.isoformat()}); "
                            "tense is ambiguous"
                        ),
                        file_path=str(path),
                        evidence={
                            "date": parsed_date.isoformat(),
                            "matched_text": match.group(0),
                            "context": context,
                            "needs_classification": True,
                        },
                    )
                )

    return findings


def _find_dates(text: str):
    for pat in _DATE_PATTERNS:
        for m in pat.finditer(text):
            try:
                if pat.pattern.startswith(r"\b(\d{4})-"):
                    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                else:
                    d = int(m.group(1))
                    mo = _MONTH_TO_NUM[m.group(2).lower()]
                    y = int(m.group(3))
                yield m, datetime(y, mo, d).date()
            except (ValueError, KeyError):
                continue
