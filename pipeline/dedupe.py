"""Dedup via content hashing, backed by a JSON seen-store.

The same meeting shows up on the calendar, the agenda feed, Patch, and maybe the
newsletter. We hash title+host+body-prefix and drop anything we've emitted before.
The store is pruned to keep it from growing without bound.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from adapters.base import Item

log = logging.getLogger("pipeline.dedupe")

_KEEP_DAYS = 120


def _load(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:  # noqa: BLE001
        return {}


def _prune(seen: dict[str, str]) -> dict[str, str]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=_KEEP_DAYS)
    out = {}
    for h, iso in seen.items():
        try:
            if datetime.fromisoformat(iso) >= cutoff:
                out[h] = iso
        except Exception:  # noqa: BLE001
            out[h] = iso
    return out


def dedupe_within(items: list[Item]) -> list[Item]:
    """Collapse cross-source duplicates WITHIN a single run — the same meeting via the
    calendar + Patch + newsletter should appear once.

    Deliberately does NOT consult the seen-store: the published page is a current-state
    snapshot, not an incremental feed. An item that already ran yesterday still belongs
    on today's page if it's still current; the seen-store is only for the email's
    "what's new" (see select_new)."""
    out: list[Item] = []
    hashes: set[str] = set()
    titles: set[str] = set()
    for it in items:
        h = it.compute_hash()
        # Title key catches the same meeting arriving from calendar + agenda + inbox
        # with identical titles but different bodies (which the content hash misses).
        tkey = re.sub(r"\s+", " ", it.title or "").strip().lower()
        if h in hashes or (tkey and tkey in titles):
            continue
        hashes.add(h)
        if tkey:
            titles.add(tkey)
        out.append(it)
    log.info("dedupe(within-run): %d in -> %d unique", len(items), len(out))
    return out


def select_new(items: list[Item], seen_path: Path) -> list[Item]:
    """The subset not emitted on a prior run — the email's "what's new" set. The page
    does NOT use this (it shows all current items). Items must already have a
    content_hash (dedupe_within sets it)."""
    seen = _load(seen_path)
    return [it for it in items if it.content_hash and it.content_hash not in seen]


def commit(items: list[Item], seen_path: Path) -> None:
    """Record emitted items so they won't reappear. Call after a successful run."""
    seen = _prune(_load(seen_path))
    now_iso = datetime.now(timezone.utc).isoformat()
    for it in items:
        if it.content_hash:
            seen[it.content_hash] = now_iso
    seen_path.parent.mkdir(parents=True, exist_ok=True)
    seen_path.write_text(json.dumps(seen, indent=0))
    log.info("dedupe store now holds %d hashes", len(seen))
