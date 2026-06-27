"""Generic RSS/Atom adapter. Covers News Flash, Patch, Substack, Conservation
Trust, LELWD, schools — anything with a feed. Returns raw Items.

feedparser handles RSS, Atom, and most malformed feeds. If a feed is unreachable
we return [] and let the orchestrator's health check flag it.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from time import mktime

import feedparser

from .base import Item, clean_text

log = logging.getLogger("adapters.rss")

# Substack serves bot/datacenter IPs an empty challenge page for the descriptive
# UA; a browser-like UA gets the public feed through. Scoped to substack.com only.
_BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def _parse_date(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        t = getattr(entry, key, None) or entry.get(key) if hasattr(entry, "get") else None
        if t:
            try:
                return datetime.fromtimestamp(mktime(t), tz=timezone.utc)
            except Exception:
                continue
    return None


def fetch(source: dict, user_agent: str, timeout: int = 20) -> list[Item]:
    url = source.get("url", "")
    if not url or "__FILL__" in url:
        log.info("skipping %s: feed url not configured", source["id"])
        return []

    feedparser.USER_AGENT = _BROWSER_UA if "substack.com" in url else user_agent
    try:
        parsed = feedparser.parse(url)
    except Exception as exc:  # noqa: BLE001
        log.warning("rss fetch failed for %s: %s", source["id"], exc)
        return []

    if getattr(parsed, "bozo", 0) and not parsed.entries:
        log.warning("rss feed unparseable/empty for %s (%s)", source["id"], url)
        return []

    items: list[Item] = []
    for e in parsed.entries:
        title = clean_text(getattr(e, "title", ""), 400)
        link = getattr(e, "link", "") or url
        summary = getattr(e, "summary", "") or getattr(e, "description", "") or ""
        content = ""
        if getattr(e, "content", None):
            content = e.content[0].get("value", "") or ""
        # Prefer the full post (content:encoded) when it's richer than the teaser
        # summary — Substack feeds put the whole recap there, which the decompose
        # step needs and which gives every feed better text to classify/summarize.
        body = clean_text(content if len(content) > len(summary) else summary)
        if not title and not body:
            continue
        items.append(
            Item(
                source_id=source["id"],
                source_name=source["name"],
                tier=source.get("tier", 0),
                url=link,
                title=title or "(untitled)",
                body=body,
                published=_parse_date(e),
                raw_id=getattr(e, "id", "") or link,
            )
        )
    log.info("rss %s -> %d items", source["id"], len(items))
    return items
