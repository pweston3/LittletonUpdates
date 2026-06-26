"""Summarization.

With an API key: Claude Sonnet writes a short rollup intro for the digest and a
one-line summary per kept item. Without a key: summaries fall back to a trimmed
first sentence, and the rollup is a plain count. Either way the digest renders.

Copyright note: summaries are original paraphrase, never quoted source text.
"""
from __future__ import annotations

import json
import logging
import re

from adapters.base import Item

log = logging.getLogger("pipeline.summarize")

_ITEM_SYSTEM = """Write a one-sentence, plain-language summary of each Littleton, MA news item
for a busy resident. Be specific and factual. Use your own words — never copy phrases from
the source. No preamble. Return ONLY a JSON array of strings, same order as input."""

_ROLLUP_SYSTEM = """You write the opening line of a daily Littleton, MA civic briefing.
Given the day's items (with categories and relevance), write 2-3 sentences that orient the
reader to what matters most today: lead with the highest-stakes item (a vote, hearing,
deadline, or major decision), then note the broad shape of the rest. Plain, warm, factual.
No bullet points, no headers, no quoting source text."""


def _first_sentence(text: str, limit: int = 200) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    m = re.split(r"(?<=[.!?])\s+", text)
    return (m[0] if m else text)[:limit]


def summarize_items(items: list[Item], *, model: str, api_key: str) -> None:
    if not items:
        return
    if not api_key:
        for it in items:
            it.summary = _first_sentence(it.body or it.title)
        return
    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key)
        payload = [{"title": it.title, "text": it.body[:600]} for it in items]
        resp = client.messages.create(
            model=model,
            max_tokens=1500,
            system=_ITEM_SYSTEM,
            messages=[{"role": "user", "content": json.dumps(payload)}],
        )
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        text = text.replace("```json", "").replace("```", "").strip()
        summaries = json.loads(text)
        for it, s in zip(items, summaries):
            it.summary = str(s)[:280]
    except Exception as exc:  # noqa: BLE001
        log.warning("item summarize failed (%s); using fallback", exc)
        for it in items:
            if not it.summary:
                it.summary = _first_sentence(it.body or it.title)


def rollup(items: list[Item], *, model: str, api_key: str) -> str:
    if not items:
        return "No new Littleton items today."
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
             "deadlines": it.deadlines}
            for it in sorted(items, key=lambda x: x.relevance, reverse=True)[:20]
        ]
        resp = client.messages.create(
            model=model,
            max_tokens=400,
            system=_ROLLUP_SYSTEM,
            messages=[{"role": "user", "content": json.dumps(payload)}],
        )
        return "".join(b.text for b in resp.content if b.type == "text").strip()
    except Exception as exc:  # noqa: BLE001
        log.warning("rollup failed (%s); using fallback", exc)
        return f"{len(items)} new Littleton item(s) today."
