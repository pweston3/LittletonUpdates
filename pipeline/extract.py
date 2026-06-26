"""Deadline & date extraction.

Two jobs, both pure-Python (regex + dateutil, no LLM):
  - deadlines[]: every "deadline/hearing/vote on <date>" pair, for the ledger.
  - event_date: the ONE date an item is primarily about (a meeting/hearing), so
    the page can tell past from future. Prefer the date in the title (LCTV/board
    items look like "Select Board - June 22, 2026"); fall back to the strongest
    dated event in the body; leave None for pure news with no single event.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from adapters.base import Item, DATE_RE

log = logging.getLogger("pipeline.extract")

_NY = ZoneInfo("America/New_York")

# Any actionable/dated thing -> feeds the deadline ledger.
_TRIGGERS = re.compile(
    r"(deadline|due|comment period|public hearing|hearing|vote|election|"
    r"town meeting|warrant|closes?|submit by|applications? (?:close|due))",
    re.IGNORECASE,
)

# A calendar EVENT cue near a date in the body. Paired with a FUTURE-date filter in
# _event_date_for: a recap of a past meeting ("met on April 30", "at the June 22
# meeting") names a past date and is ignored, so recaps/news stay undated; an agenda
# notice ("meeting on July 1", "will meet July 1") names a future date and is captured.
_EVENT_TRIGGERS = re.compile(
    r"(meeting|meets|will\s+meet|public\s+hearing|hearing|forum|town\s+meeting|"
    r"scheduled|workshop|session|join\s+us|agenda)",
    re.IGNORECASE,
)


def _parse_date_obj(raw: str) -> date | None:
    try:
        from dateutil import parser as dparser  # lazy import

        dt = dparser.parse(raw, default=datetime(datetime.now().year, 1, 1))
        return dt.date()
    except Exception:  # noqa: BLE001
        return None


def _to_date_iso(raw: str) -> str | None:
    d = _parse_date_obj(raw)
    return d.isoformat() if d else None


def _event_date_for(it: Item, today: date) -> date | None:
    """Primary event date. The TITLE date wins outright (LCTV/agenda items ARE that
    meeting — past dates kept so recordings resolve). Otherwise, a FUTURE date in the
    body next to an event cue (an agenda notice); past body dates are ignored so a
    recap stays undated. None when there's no single dated event."""
    m = DATE_RE.search(it.title)
    if m:
        d = _parse_date_obj(m.group(1))
        if d:
            return d
    for sent in re.split(r"(?<=[.!?])\s+", it.body or ""):
        if not _EVENT_TRIGGERS.search(sent):
            continue
        for dm in DATE_RE.finditer(sent):
            d = _parse_date_obj(dm.group(1))
            if d and d >= today:
                return d
    return None


def extract(items: list[Item]) -> list[Item]:
    today = datetime.now(_NY).date()
    for it in items:
        text = f"{it.title}. {it.body}"
        seen: set[str] = set()
        for sent in re.split(r"(?<=[.!?])\s+", text):
            if not _TRIGGERS.search(sent):
                continue
            for m in DATE_RE.finditer(sent):
                key = _to_date_iso(m.group(1))
                if not key or key in seen:
                    continue
                seen.add(key)
                kind = _TRIGGERS.search(sent).group(1).lower()
                label = re.sub(r"\s+", " ", sent).strip()[:160]
                it.deadlines.append({"date": key, "kind": kind, "label": label})

        it.event_date = _event_date_for(it, today)

        if it.deadlines or it.event_date:
            log.info("extracted %d deadline(s)%s from %s", len(it.deadlines),
                     f" + event {it.event_date}" if it.event_date else "", it.source_id)
    return items
