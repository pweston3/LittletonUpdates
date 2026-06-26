"""Campus Suite news scraper.

Several Littleton institutions — notably Littleton Public Schools — run on the
Campus Suite CMS, which exposes no public RSS: news lives in server-rendered
HTML (a JS app hydrates it, but the markup is already present without JS). This
adapter fetches a news-list page and parses Campus Suite's stable
`cs-li-default-*` article blocks into Items.

Each block yields a title, a teaser body, and the article permalink (whose ULID
is a stable dedup id). The list view carries no publish date, so items arrive
with published=None — handled downstream (the extract step still mines dates out
of the body text). If the layout changes, fetch() returns [] and the health
check flags the source, same as a dead feed.
"""
from __future__ import annotations

import html
import logging
import re

import requests

from .base import Item, clean_text

log = logging.getLogger("adapters.campussuite")

# One news item per `cs-li-default-wrap`; split on the class marker (12 on the
# live LPS page, vs. no other occurrences — safe boundary).
_WRAP = 'class="cs-li-default-wrap"'
_TITLE = re.compile(
    r'cs-li-default-title"[^>]*>\s*<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', re.S
)
# The body div's first <p> is the teaser; the link <p> that follows carries a class.
_BODY = re.compile(r'cs-li-default-body"[^>]*>\s*<p>(.*?)</p>', re.S)


def _parse_block(block: str) -> Item | None:
    m_title = _TITLE.search(block)
    if not m_title:
        return None
    href = html.unescape(m_title.group(1)).strip()
    title = clean_text(html.unescape(m_title.group(2)), 400)
    if not href or not title:
        return None
    m_body = _BODY.search(block)
    body = clean_text(html.unescape(m_body.group(1))) if m_body else ""
    return href, title, body  # type: ignore[return-value]


def fetch(source: dict, user_agent: str, timeout: int = 20) -> list[Item]:
    url = source.get("url", "")
    if not url:
        log.info("skipping %s: no url configured", source["id"])
        return []
    try:
        resp = requests.get(url, headers={"User-Agent": user_agent}, timeout=timeout)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        log.warning("campussuite fetch failed for %s: %s", source["id"], exc)
        return []

    blocks = resp.text.split(_WRAP)[1:]
    items: list[Item] = []
    seen: set[str] = set()
    for block in blocks:
        parsed = _parse_block(block)
        if not parsed:
            continue
        href, title, body = parsed
        if href in seen:
            continue
        seen.add(href)
        items.append(
            Item(
                source_id=source["id"],
                source_name=source["name"],
                tier=source.get("tier", 0),
                url=href,
                title=title,
                body=body,
                raw_id=href,
            )
        )

    if not items:
        log.warning(
            "campussuite: parsed 0 items for %s (%s) — layout may have changed",
            source["id"], url,
        )
    else:
        log.info("campussuite %s -> %d items", source["id"], len(items))
    return items
