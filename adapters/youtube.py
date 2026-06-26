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


def _condense(text: str, max_chars: int) -> str:
    """Fit a long transcript into max_chars while preserving the meeting's arc.

    A head-only truncation drops exactly the part that matters most — meetings
    back-load their votes and decisions. Instead we keep proportional slices from
    the start, middle, and end so the summarizer sees the agenda, the debate, and
    the resolution.
    """
    if len(text) <= max_chars:
        return text
    seg = (max_chars - 12) // 3  # room for two " […] " joiners
    mid = (len(text) - seg) // 2
    return f"{text[:seg]} […] {text[mid:mid + seg]} […] {text[-seg:]}"


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

        api = YouTubeTranscriptApi()
        if hasattr(api, "fetch"):  # youtube-transcript-api >= 1.0 (instance API)
            chunks = api.fetch(video_id, languages=["en", "en-US"]).to_raw_data()
        else:  # legacy 0.x static API
            chunks = YouTubeTranscriptApi.get_transcript(
                video_id, languages=["en", "en-US"]
            )
        text = " ".join(c.get("text", "") for c in chunks)
        if text:
            full = len(text)
            text = _condense(text, max_chars)
            item.body = (item.body + " " + text).strip()
            log.info(
                "transcript added for %s (%d chars%s)",
                video_id, full, " sampled→%d" % len(text) if full > max_chars else "",
            )
    except Exception as exc:  # noqa: BLE001
        log.info("no transcript for %s: %s", video_id, exc)
