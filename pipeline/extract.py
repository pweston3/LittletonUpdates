"""Deadline & date extraction.

Turns "comment deadline is April 1", "public hearing on June 25", "vote on the
override" into structured {date, label, kind} entries so the digest can surface a
ledger of what's coming up. Pure-Python regex + dateutil; no LLM needed.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from adapters.base import Item

log = logging.getLogger("pipeline.extract")

_TRIGGERS = re.compile(
    r"(deadline|due|comment period|public hearing|hearing|vote|election|"
    r"town meeting|warrant|closes?|submit by|applications? (?:close|due))",
    re.IGNORECASE,
)

# matches "April 1", "April 1, 2026", "4/1/2026", "June 25th"
_DATE = re.compile(
    r"\b("
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?"
    r"|\d{1,2}/\d{1,2}/\d{2,4}"
    r")\b",
    re.IGNORECASE,
)


def _to_date(raw: str) -> datetime | None:
    try:
        from dateutil import parser as dparser  # lazy import

        dt = dparser.parse(raw, default=datetime(datetime.now().year, 1, 1))
        return dt.replace(tzinfo=timezone.utc)
    except Exception:  # noqa: BLE001
        return None


def extract(items: list[Item]) -> list[Item]:
    for it in items:
        text = f"{it.title}. {it.body}"
        seen: set[str] = set()
        for sent in re.split(r"(?<=[.!?])\s+", text):
            if not _TRIGGERS.search(sent):
                continue
            for m in _DATE.finditer(sent):
                raw = m.group(1)
                dt = _to_date(raw)
                if not dt:
                    continue
                key = dt.date().isoformat()
                if key in seen:
                    continue
                seen.add(key)
                kind = _TRIGGERS.search(sent).group(1).lower()
                label = re.sub(r"\s+", " ", sent).strip()[:160]
                it.deadlines.append({"date": key, "kind": kind, "label": label})
        if it.deadlines:
            log.info("extracted %d date(s) from %s", len(it.deadlines), it.source_id)
    return items
