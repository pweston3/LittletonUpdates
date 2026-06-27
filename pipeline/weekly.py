"""Weekly Edition — "The Week in Littleton".

Once per ISO week (and refreshed on the configured weekly day) this asks Claude to
write a narrative editorial over the week's items: an evocative headline + dek, a
handful of themed sections in flowing prose, a pull quote, and "threads to watch".
The result is persisted to state/editions.json so the daily page's marquee can show
the current edition, the editorial gets its own page, and prior weeks accumulate
into a Past Editions archive.

Degrades cleanly: with no API key (or on a generation failure) it returns whatever
edition is already stored, or None — the daily page then falls back to a plain
"today" marquee.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path

log = logging.getLogger("pipeline.weekly")

_MEETING_TYPES = {"meeting", "hearing", "event", "agenda"}
# Kicker colors cycled across the editorial's themed sections (match the design).
_KICKER_COLORS = ["#C8881A", "#2E7D5B", "#2A7E8C", "#2C5BA6", "#102A54", "#B3472D"]

_SYSTEM = """You are the editor of the Littleton Signal, an unofficial, community-run daily
civic briefing for Littleton, Massachusetts. Write this week's editorial — "The Week in
Littleton" — as warm, plain-language local journalism that synthesizes the week's items
into themes, NOT a list. You may only state facts present in the items; never invent
names, numbers, votes, or quotes. Group related items; find the throughline.

Return ONLY a JSON object (no prose, no code fences) with exactly these keys:
{
  "headline": "evocative and concrete, <= 12 words",
  "dek": "one-sentence italic standfirst that captures the week's mood",
  "lede": "opening paragraph (3-5 sentences) that sets up the week's defining story",
  "sections": [
    {"kicker": "2-4 word section label", "body": "1-2 paragraphs of flowing prose"}
  ],
  "pull_quote": "one short, striking sentence drawn from the week's throughline",
  "threads": ["short forward-looking item to watch", "...", "..."]
}
Aim for 3-5 sections. Keep the whole thing tight and readable."""


def _iso_tag(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def _range_label(today: date) -> str:
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    if monday.month == sunday.month:
        return f"{monday:%B} {monday.day}–{sunday.day}, {sunday.year}"
    return f"{monday:%b} {monday.day} – {sunday:%b} {sunday.day}, {sunday.year}"


def _stats(items: list, today: date) -> dict:
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    deadline_dates, meetings = set(), set()
    for it in items:
        for dd in getattr(it, "deadlines", []) or []:
            try:
                if date.fromisoformat(dd["date"]) >= today:
                    deadline_dates.add(dd["date"])
            except Exception:  # noqa: BLE001
                continue
        # "meetings" = distinct public meetings actually happening this ISO week,
        # not every calendar/agenda row (which would balloon the count).
        if it.item_type in _MEETING_TYPES and it.event_date and monday <= it.event_date <= sunday:
            meetings.add(re.sub(r"\s+", " ", it.title.lower()).strip()[:60])
    return {
        "items": len(items),
        "meetings": len(meetings),
        "sources": len({it.source_name for it in items}),
        "deadlines": len(deadline_dates),
    }


def _source_labels(items: list) -> list[str]:
    """Friendly, deduped source labels for the 'sources synthesized' chips."""
    out, seen = [], set()
    for it in items:
        raw = (it.source_name or "").split(" — ")[0].split(" (")[0].strip()
        if raw and raw.lower() not in seen:
            seen.add(raw.lower())
            out.append(raw)
    return out[:10]


def _load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except Exception:  # noqa: BLE001
        return []


def _generate(items: list, today: date, *, model: str, api_key: str) -> dict | None:
    payload = [
        {"title": it.title, "summary": it.summary or "", "category": it.category,
         "when": it.event_date.isoformat() if it.event_date else ""}
        for it in sorted(items, key=lambda x: x.relevance, reverse=True)[:40]
    ]
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=model, max_tokens=2600, system=_SYSTEM,
            messages=[{"role": "user", "content": json.dumps({
                "week": _range_label(today), "items": payload})}],
        )
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        text = text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text)
    except Exception as exc:  # noqa: BLE001
        log.warning("weekly edition generation failed: %s", exc)
        return None

    sections = []
    for n, s in enumerate(data.get("sections", [])):
        kicker = (s.get("kicker") or "").strip()
        body = (s.get("body") or "").strip()
        if kicker and body:
            sections.append({"kicker": kicker, "body": body,
                             "color": _KICKER_COLORS[n % len(_KICKER_COLORS)]})
    if not data.get("headline") or not sections:
        log.warning("weekly edition came back empty/malformed; skipping")
        return None

    return {
        "iso": _iso_tag(today),
        "date": today.isoformat(),
        "range_label": _range_label(today),
        "headline": data["headline"].strip(),
        "dek": (data.get("dek") or "").strip(),
        "lede": (data.get("lede") or "").strip(),
        "sections": sections,
        "pull_quote": (data.get("pull_quote") or "").strip(),
        "threads": [t.strip() for t in data.get("threads", []) if t.strip()][:4],
        "stats": _stats(items, today),
        "sources": _source_labels(items),
    }


def current_edition(items: list, *, model: str, api_key: str, today: date,
                    state_path: Path, weekly_day: int = 6) -> tuple[dict | None, list[dict]]:
    """Return (current_edition, all_editions). Generates a new edition once per ISO
    week, and refreshes on `weekly_day` (Mon=0..Sun=6) so the end-of-week read reflects
    the full week. Returns the stored edition unchanged on other days."""
    editions = _load(state_path)
    cur_iso = _iso_tag(today)
    latest = editions[-1] if editions else None

    need = (latest is None
            or latest.get("iso") != cur_iso
            or (today.weekday() == weekly_day and latest.get("date") != today.isoformat()))

    if need and api_key:
        edition = _generate(items, today, model=model, api_key=api_key)
        if edition:
            # Replace a same-week entry, else append.
            editions = [e for e in editions if e.get("iso") != cur_iso]
            editions.append(edition)
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps(editions, indent=1))
            log.info("weekly edition %s generated (%d sections)",
                     cur_iso, len(edition["sections"]))
            return edition, editions

    return latest, editions
