"""Decompose multi-topic recap posts into their constituent topics.

Sean Aherne's "Last Week on School Committee" posts each cover several separate
matters — a budget vote, a teachers' contract, an appointment, a building
project — but arrive as one item, producing a row of near-identical "School
Committee" cards while the real substance stays buried in the body.

This step asks Claude to split a recap into its distinct topics (each a headline
+ one-sentence summary + category) and REPLACES the recap with those topic items.
They then flow through the normal classify → extract → threshold → render path,
landing under their proper sections (a budget topic in Town Hall, a school topic
in Schools, etc.). Stale recaps (older than the window) are dropped — a months-old
recap of a long-past meeting has no current value. Degrades to a no-op without a key.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from adapters.base import Item, CATEGORIES, clean_text

log = logging.getLogger("pipeline.decompose")

# Sources whose posts are multi-topic recaps worth splitting.
_RECAP_SOURCES = {"sean_for_littleton"}
_MIN_BODY = 250          # below this there's nothing to decompose
_MAX_AGE_DAYS = 45       # older recaps are stale — drop rather than surface

_SYSTEM = """You split a Littleton, MA civic recap post into the distinct topics it covers.
A single recap (e.g. a "Last Week on School Committee" post) usually spans several separate
matters — a budget vote, a contract, an appointment, a building project, a policy change,
an election or warrant item. Pull each out as its own entry.

Return ONLY a JSON array of 2-6 objects, in importance order, each:
  {{"headline": "specific and concrete, <=70 chars", "summary": "one factual sentence in your
  own words, never quoting", "category": "one of: {cats}"}}

Each object must be a substantive, separate matter the post actually discusses. Fold in
pleasantries/housekeeping; never invent anything not in the text."""


def _age_days(it: Item, now: datetime) -> int | None:
    if not it.published:
        return None
    try:
        return (now - it.published).days
    except Exception:  # noqa: BLE001 (naive/aware mismatch etc.)
        return None


def _is_recap(it: Item) -> bool:
    return it.source_id in _RECAP_SOURCES and len(it.body or "") >= _MIN_BODY


def _topics(it: Item, model: str, api_key: str) -> list[Item]:
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model,
        max_tokens=1200,
        system=_SYSTEM.format(cats=", ".join(CATEGORIES)),
        messages=[{"role": "user",
                   "content": json.dumps({"title": it.title, "text": (it.body or "")[:4000]})}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    text = text.replace("```json", "").replace("```", "").strip()
    data = json.loads(text)
    out: list[Item] = []
    for n, d in enumerate(data):
        head = clean_text(str(d.get("headline", "")), 120)
        if not head:
            continue
        cat = d.get("category", "other")
        topic = Item(
            source_id=it.source_id, source_name=it.source_name, tier=it.tier,
            url=it.url, title=head, body=clean_text(str(d.get("summary", "")), 280),
            published=it.published, raw_id=f"{it.raw_id}#{n}",
            category=cat if cat in CATEGORIES else "other",
        )
        topic.compute_hash()
        out.append(topic)
    return out


def decompose(items: list[Item], *, model: str, api_key: str) -> list[Item]:
    if not api_key:
        return items
    now = datetime.now(timezone.utc)
    # Diagnostic: body sizes of recap-source items. Full posts (content:encoded) are
    # thousands of chars; if CI sees only ~50-80, the runner is getting truncated feeds.
    recaps = [it for it in items if it.source_id in _RECAP_SOURCES]
    if recaps:
        log.info("recap diagnostic: %d recap-source item(s); body sizes (top): %s",
                 len(recaps), sorted((len(it.body or "") for it in recaps), reverse=True)[:8])
    out: list[Item] = []
    for it in items:
        if not _is_recap(it):
            out.append(it)
            continue
        age = _age_days(it, now)
        if age is not None and age > _MAX_AGE_DAYS:
            continue  # stale recap — drop
        try:
            topics = _topics(it, model, api_key)
        except Exception as exc:  # noqa: BLE001
            log.warning("decompose failed for %s (%s); keeping original", it.raw_id, exc)
            topics = None
        if topics:
            log.info("decomposed '%s' -> %d topics", it.title[:48], len(topics))
            out.extend(topics)
        else:
            out.append(it)  # fall back to the original recap
    return out
