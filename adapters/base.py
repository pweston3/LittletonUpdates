"""Common item schema + helpers shared by every adapter.

One Item == one thing that happened (a meeting posted, an article, a Reddit
thread, an email). Adapters return raw Items; the pipeline fills the enrichment
fields (hash, category, type, relevance, summary, deadlines).
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timezone
from typing import Any


# Shared date matcher: "April 1", "June 25th", "June 22, 2026", "4/1/2026".
DATE_RE = re.compile(
    r"\b("
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?"
    r"|\d{1,2}/\d{1,2}/\d{2,4}"
    r")\b",
    re.IGNORECASE,
)


def strip_date_suffix(title: str) -> str:
    """'Select Board - June 22, 2026' -> 'Select Board'. Leaves dateless titles alone."""
    m = DATE_RE.search(title or "")
    if not m:
        return (title or "").strip()
    base = title[: m.start()].strip(" -–—,·|:\t").strip()
    return base or title.strip()


CATEGORIES = [
    "town_hall",      # boards, committees, meetings, town admin
    "schools",        # LPS, School Committee, SEPAC
    "development",    # planning, zoning, large projects, MEPA
    "conservation",   # ConCom, land, trails, lakes
    "public_safety",  # police, fire, emergency
    "elections",      # warrants, ballots, votes, town meeting
    "utility",        # LELWD, water, outages
    "community",      # events, civic orgs, resident chatter
    "news",           # press coverage
    "other",
]

ITEM_TYPES = [
    "agenda", "minutes", "hearing", "meeting", "deadline", "vote",
    "election", "announcement", "event", "news", "discussion",
]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def clean_text(s: str | None, limit: int = 4000) -> str:
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)          # strip HTML tags
    s = re.sub(r"&[a-z]+;", " ", s)         # crude entity strip
    s = re.sub(r"\s+", " ", s).strip()
    return s[:limit]


@dataclass
class Item:
    source_id: str
    source_name: str
    tier: int
    url: str
    title: str
    body: str = ""
    published: datetime | None = None    # for LCTV this is the UPLOAD time, not the meeting
    event_date: date | None = None       # the meeting/hearing/deadline the item is ABOUT
    fetched: datetime = field(default_factory=now_utc)
    raw_id: str = ""

    # enrichment (filled by the pipeline)
    content_hash: str = ""
    category: str = "other"
    item_type: str = "news"
    relevance: int = 0
    summary: str = ""
    deadlines: list[dict[str, Any]] = field(default_factory=list)

    def compute_hash(self) -> str:
        """Stable identity for dedup. Title + host + first chunk of body."""
        host = re.sub(r"^https?://(www\.)?", "", self.url).split("/")[0]
        basis = f"{self.title.strip().lower()}|{host}|{self.body[:160].strip().lower()}"
        self.content_hash = hashlib.sha1(basis.encode("utf-8")).hexdigest()
        return self.content_hash

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["published"] = self.published.isoformat() if self.published else None
        d["event_date"] = self.event_date.isoformat() if self.event_date else None
        d["fetched"] = self.fetched.isoformat()
        return d
