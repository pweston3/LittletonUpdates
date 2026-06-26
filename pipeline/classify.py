"""Classification + relevance scoring.

With an API key: one Claude Haiku call per batch assigns category, type, and a
0-100 relevance score per item, guided by the relevance_profile.

Without a key: a transparent keyword heuristic does the same job more crudely, so
the pipeline always produces a usable digest.
"""
from __future__ import annotations

import json
import logging

from adapters.base import CATEGORIES, ITEM_TYPES, Item

log = logging.getLogger("pipeline.classify")

_SYSTEM = """You triage local-government news items for a resident of Littleton, Massachusetts.
For each item return category, type, and a 0-100 relevance score.

category one of: {cats}
type one of: {types}

Relevance reflects how much this matters to an engaged Littleton resident who tracks
town governance, development, schools, conservation, and budgets. Score HIGH (75-100)
for: votes, town meeting warrants, public hearings, deadlines, budget/override decisions,
and anything matching the priority topics. Score LOW (0-30) for: routine job postings,
generic event promos, and off-topic chatter. Items about a different Littleton (Colorado,
New Hampshire) score 0.

Priority topics (boost these): {high}
Secondary topics: {medium}

Each input item has an integer "i". Return ONLY a JSON array with one object per
item, echoing that "i" so results map back even if order shifts. Include every i.
No prose:
[{{"i": 0, "category": "...", "type": "...", "relevance": 0-100}}]"""


def _heuristic(item: Item, profile: dict) -> tuple[str, str, int]:
    text = f"{item.title} {item.body}".lower()
    high = [k.lower() for k in profile.get("high", [])]
    medium = [k.lower() for k in profile.get("medium", [])]

    score = 25
    if any(k in text for k in high):
        score = 80
    elif any(k in text for k in medium):
        score = 55

    # crude type/category cues
    itype = "news"
    if "agenda" in text:
        itype = "agenda"
    elif "minutes" in text:
        itype = "minutes"
    elif "public hearing" in text or "hearing" in text:
        itype = "hearing"; score = max(score, 70)
    elif "deadline" in text or "due " in text:
        itype = "deadline"; score = max(score, 70)
    elif "vote" in text or "election" in text or "warrant" in text:
        itype = "vote"; score = max(score, 75)
    elif "meeting" in text:
        itype = "meeting"

    cat = item.category or "other"
    for key, words in {
        "schools": ("school", "superintendent", "student", "sepac"),
        "development": ("planning board", "zoning", "special permit", "development", "mepa"),
        "conservation": ("conservation", "wetland", "trail", "lake", "open space"),
        "public_safety": ("police", "fire", "emergency"),
        "elections": ("election", "ballot", "town meeting", "warrant", "override"),
        "utility": ("lelwd", "water main", "outage", "electric"),
    }.items():
        if any(w in text for w in words):
            cat = key
            break
    return cat, itype, min(score, 100)


def _llm(items: list[Item], profile: dict, model: str, api_key: str) -> list[tuple[str, str, int] | None]:
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    payload = [
        {"i": n, "title": it.title, "text": it.body[:500], "source": it.source_name}
        for n, it in enumerate(items)
    ]
    system = _SYSTEM.format(
        cats=", ".join(CATEGORIES),
        types=", ".join(ITEM_TYPES),
        high="; ".join(profile.get("high", [])),
        medium="; ".join(profile.get("medium", [])),
    )
    # One compact JSON object per item (~30-40 tokens each); size the ceiling to
    # the batch so a large day's items don't truncate the array and silently fall
    # back to the heuristic. Capped to stay non-streaming and under HTTP timeouts.
    max_tokens = min(16000, 64 * len(items) + 500)
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": json.dumps(payload)}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    text = text.replace("```json", "").replace("```", "").strip()
    data = json.loads(text)
    # Map by the echoed index so a dropped/merged item only loses itself (filled
    # by the heuristic downstream), instead of discarding the whole batch.
    out: list[tuple[str, str, int] | None] = [None] * len(items)
    for n, d in enumerate(data):
        idx = d.get("i", n)
        if not isinstance(idx, int) or not 0 <= idx < len(items):
            continue
        cat = d.get("category", "other")
        out[idx] = (
            cat if cat in CATEGORIES else "other",
            d.get("type", "news") if d.get("type") in ITEM_TYPES else "news",
            int(d.get("relevance", 0)),
        )
    return out


def classify(items: list[Item], profile: dict, *, model: str, api_key: str) -> list[Item]:
    if not items:
        return items
    results: list[tuple[str, str, int] | None] | None = None
    if api_key:
        try:
            results = _llm(items, profile, model, api_key)
            missing = sum(1 for r in results if r is None)
            if missing:
                log.info("llm classified %d/%d; heuristic fills the other %d",
                         len(items) - missing, len(items), missing)
        except Exception as exc:  # noqa: BLE001
            log.warning("llm classify failed (%s); using heuristic", exc)
            results = None

    for n, it in enumerate(items):
        if results and results[n] is not None:
            it.category, it.item_type, it.relevance = results[n]
        else:
            it.category, it.item_type, it.relevance = _heuristic(it, profile)
        # apply per-source weight nudge
        it.relevance = max(0, min(100, it.relevance + it._weight if hasattr(it, "_weight") else it.relevance))
    return items
