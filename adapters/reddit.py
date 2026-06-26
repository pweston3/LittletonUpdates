"""Reddit adapter. Reddit's .rss search endpoints still work without an API key.

"Littleton" alone is noisy (Littleton CO/NH dominate), so every result must pass
a Massachusetts-context gate before it counts.
"""
from __future__ import annotations

import logging
import re
from urllib.parse import quote_plus

import feedparser

from .base import Item, clean_text

log = logging.getLogger("adapters.reddit")

# A result keeps only if it shows a Massachusetts signal and no competing-state signal.
_MA_SIGNAL = re.compile(
    r"\b(massachusetts|mass\.?|\bMA\b|01460|middlesex|nashoba|"
    r"acton|westford|chelmsford|boxborough|ayer|harvard\s+ma)\b",
    re.IGNORECASE,
)
_OTHER_STATE = re.compile(
    r"\b(colorado|\bCO\b|denver|new\s+hampshire|\bNH\b|north\s+carolina|"
    r"\bNC\b|littleton\s+co|littleton\s+nh)\b",
    re.IGNORECASE,
)


def _build_url(params: dict) -> str:
    query = quote_plus(params.get("query", "Littleton"))
    timeframe = params.get("timeframe", "week")
    if params.get("restrict_subreddit") and params.get("subreddit"):
        sub = params["subreddit"]
        return (
            f"https://www.reddit.com/r/{sub}/search.rss"
            f"?q={query}&restrict_sr=on&sort=new&t={timeframe}"
        )
    return f"https://www.reddit.com/search.rss?q={query}&sort=new"


def _is_ma(text: str) -> bool:
    return bool(_MA_SIGNAL.search(text)) and not _OTHER_STATE.search(text)


def fetch(source: dict, user_agent: str, timeout: int = 20) -> list[Item]:
    url = _build_url(source.get("params", {}))
    feedparser.USER_AGENT = user_agent  # Reddit blocks generic/empty UAs
    try:
        parsed = feedparser.parse(url)
    except Exception as exc:  # noqa: BLE001
        log.warning("reddit fetch failed for %s: %s", source["id"], exc)
        return []

    items: list[Item] = []
    for e in parsed.entries:
        title = clean_text(getattr(e, "title", ""), 400)
        body = clean_text(getattr(e, "summary", ""))
        if not _is_ma(f"{title} {body}"):
            continue  # drop the other Littletons
        items.append(
            Item(
                source_id=source["id"],
                source_name=source["name"],
                tier=source.get("tier", 8),
                url=getattr(e, "link", url),
                title=title or "(untitled reddit post)",
                body=body,
                raw_id=getattr(e, "id", "") or getattr(e, "link", ""),
            )
        )
    log.info("reddit %s -> %d MA-relevant items", source["id"], len(items))
    return items
