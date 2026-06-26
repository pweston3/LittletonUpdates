"""LCTV (YouTube) adapter. Pulls the channel RSS, and — for items that clear the
relevance gate later — can pull the auto-caption transcript so meetings become
searchable/summarizable text rather than just a title.

Transcript fetching is lazy and optional: run.py calls enrich_transcript() only
on items it decides to keep, so we don't download captions for every video.
"""
from __future__ import annotations

import logging

import feedparser

from .base import Item, clean_text

log = logging.getLogger("adapters.youtube")

_FEED = "https://www.youtube.com/feeds/videos.xml?channel_id={cid}"


def fetch(source: dict, user_agent: str, timeout: int = 20) -> list[Item]:
    cid = source.get("params", {}).get("channel_id", "")
    if not cid:
        log.info("skipping %s: no channel_id", source["id"])
        return []
    feedparser.USER_AGENT = user_agent
    try:
        parsed = feedparser.parse(_FEED.format(cid=cid))
    except Exception as exc:  # noqa: BLE001
        log.warning("youtube fetch failed for %s: %s", source["id"], exc)
        return []

    items: list[Item] = []
    for e in parsed.entries:
        title = clean_text(getattr(e, "title", ""), 400)
        items.append(
            Item(
                source_id=source["id"],
                source_name=source["name"],
                tier=source.get("tier", 6),
                url=getattr(e, "link", ""),
                title=title or "(untitled video)",
                body=clean_text(getattr(e, "summary", "")),
                raw_id=getattr(e, "yt_videoid", "") or getattr(e, "id", ""),
            )
        )
    log.info("youtube %s -> %d videos", source["id"], len(items))
    return items


def enrich_transcript(item: Item, max_chars: int = 6000) -> None:
    """Best-effort: pull the auto-caption transcript into item.body.

    Requires youtube-transcript-api. Silently no-ops if unavailable or captions
    are missing/disabled.
    """
    video_id = item.raw_id or item.url.rsplit("=", 1)[-1]
    if not video_id:
        return
    try:
        from youtube_transcript_api import YouTubeTranscriptApi  # lazy import

        chunks = YouTubeTranscriptApi.get_transcript(video_id)
        text = " ".join(c.get("text", "") for c in chunks)
        if text:
            item.body = (item.body + " " + text).strip()[:max_chars]
            log.info("transcript added for %s (%d chars)", video_id, len(text))
    except Exception as exc:  # noqa: BLE001
        log.info("no transcript for %s: %s", video_id, exc)
