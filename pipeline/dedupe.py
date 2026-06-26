"""Dedup via content hashing, backed by a JSON seen-store.

The same meeting shows up on the calendar, the agenda feed, Patch, and maybe the
newsletter. We hash title+host+body-prefix and drop anything we've emitted before.
The store is pruned to keep it from growing without bound.
"""
from __future__ import annotations

import json
import logging
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


def filter_new(items: list[Item], seen_path: Path) -> list[Item]:
    seen = _load(seen_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    fresh: list[Item] = []
    batch_hashes: set[str] = set()
    for it in items:
        h = it.compute_hash()
        if h in seen or h in batch_hashes:
            continue
        batch_hashes.add(h)
        fresh.append(it)
    log.info("dedupe: %d in -> %d new", len(items), len(fresh))
    return fresh


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
