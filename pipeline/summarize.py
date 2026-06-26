"""Summarization.

Meeting-type items (a board meeting / hearing with a known event_date) get a
deterministic, tense-correct one-liner — no LLM, so there's nothing to hallucinate
("is scheduled to meet" on a recording of a past meeting). Everything else gets a
Claude Sonnet one-line summary, with a first-sentence fallback when there's no key.
The rollup intro is always Claude (it's the editorial voice), but it's told today's
date and each item's past/future status so it stops calling old events "upcoming."

Copyright note: summaries are original paraphrase, never quoted source text.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from adapters.base import Item, strip_date_suffix

log = logging.getLogger("pipeline.summarize")

_NY = ZoneInfo("America/New_York")

_ITEM_SYSTEM = """Write a one-sentence, plain-language summary of each Littleton, MA news item
for a busy resident. Be specific and factual. Use your own words — never copy phrases from
the source. No preamble. Return ONLY a JSON array of strings, same order as input."""

_ROLLUP_SYSTEM = """You write the opening of a daily Littleton, MA civic briefing.
Today is {today}. Each item carries an event_date and an is_past flag: an event dated
before today has ALREADY happened — describe it in the PAST tense and never call it
"scheduled," "upcoming," or "will meet." Lead with what is genuinely ahead (a future vote,
hearing, deadline, or decision); then note the broad shape of the rest. Plain, warm,
factual. 2-3 sentences. No bullet points, no headers, no quoting source text."""


def _today_ny() -> date:
    return datetime.now(_NY).date()


def _first_sentence(text: str, limit: int = 200) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    m = re.split(r"(?<=[.!?])\s+", text)
    return (m[0] if m else text)[:limit]


def _is_recording(it: Item) -> bool:
    return "youtube.com" in (it.url or "") or "youtu.be" in (it.url or "")


def _meeting_summary(it: Item, today: date) -> str | None:
    """Deterministic, tense-correct line for a dated meeting/hearing. None otherwise."""
    ev = it.event_date
    if ev is None:
        return None
    if not (_is_recording(it) or it.item_type in {"meeting", "agenda", "hearing"}):
        return None
    board = strip_date_suffix(it.title) or it.title
    when = ev.strftime("%b %-d")
    # An LCTV upload is always a recording of a meeting that already happened.
    if _is_recording(it) and ev <= today:
        return f"Watch the recording: {board} met {when}"
    if ev >= today:
        return f"Upcoming: {board}, {ev.strftime('%a')} {when}"
    return f"{board} met {when}"


def summarize_items(items: list[Item], *, model: str, api_key: str) -> None:
    if not items:
        return
    today = _today_ny()

    # Meeting-type items get a deterministic line; only the rest go to the LLM.
    rest: list[Item] = []
    for it in items:
        det = _meeting_summary(it, today)
        if det:
            it.summary = det
        else:
            rest.append(it)
    if not rest:
        return

    if not api_key:
        for it in rest:
            it.summary = _first_sentence(it.body or it.title)
        return
    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key)
        payload = [{"title": it.title, "text": it.body[:600]} for it in rest]
        resp = client.messages.create(
            model=model,
            max_tokens=1500,
            system=_ITEM_SYSTEM,
            messages=[{"role": "user", "content": json.dumps(payload)}],
        )
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        text = text.replace("```json", "").replace("```", "").strip()
        summaries = json.loads(text)
        for it, s in zip(rest, summaries):
            it.summary = str(s)[:280]
    except Exception as exc:  # noqa: BLE001
        log.warning("item summarize failed (%s); using fallback", exc)
        for it in rest:
            if not it.summary:
                it.summary = _first_sentence(it.body or it.title)


def rollup(items: list[Item], *, model: str, api_key: str) -> str:
    if not items:
        return "No new Littleton items today."
    today = _today_ny()
    if not api_key:
        cats = {}
        for it in items:
            cats[it.category] = cats.get(it.category, 0) + 1
        parts = ", ".join(f"{n} {c.replace('_', ' ')}" for c, n in sorted(cats.items()))
        return f"{len(items)} new item(s) today: {parts}."
    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key)
        payload = [
            {"title": it.title, "category": it.category, "relevance": it.relevance,
             "event_date": it.event_date.isoformat() if it.event_date else None,
             "is_past": bool(it.event_date and it.event_date < today),
             "deadlines": it.deadlines}
            for it in sorted(items, key=lambda x: x.relevance, reverse=True)[:20]
        ]
        resp = client.messages.create(
            model=model,
            max_tokens=400,
            system=_ROLLUP_SYSTEM.format(today=today.strftime("%A, %B %-d, %Y")),
            messages=[{"role": "user", "content": json.dumps(payload)}],
        )
        return "".join(b.text for b in resp.content if b.type == "text").strip()
    except Exception as exc:  # noqa: BLE001
        log.warning("rollup failed (%s); using fallback", exc)
        return f"{len(items)} new Littleton item(s) today."
