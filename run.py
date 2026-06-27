#!/usr/bin/env python3
"""Littleton local-intelligence agent — orchestrator.

Pipeline:
  load config + sources
    -> run each enabled adapter (collect raw items)
    -> dedupe against the seen-store
    -> classify (category / type / relevance)
    -> extract dates & deadlines
    -> drop items below the relevance threshold
    -> enrich kept LCTV items with transcripts
    -> summarize (per-item + daily rollup)
    -> render digest -> docs/ (GitHub Pages) + archive
    -> email it (optional)
    -> commit seen-store + update source health

Runs end-to-end with no secrets (LLM + email degrade gracefully). Use
`python run.py --sample` to exercise the pipeline offline with mock items.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

import config as cfg
from adapters import rss, reddit, youtube, inbox, pdf_docs, campussuite
from adapters.base import Item, now_utc
from pipeline import dedupe, decompose, classify, extract, summarize, weekly
from output import digest, email_send, editions

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("run")


def load_sources() -> dict:
    with open(cfg.SOURCES_FILE) as f:
        return yaml.safe_load(f)


def run_adapters(spec: dict, ua: str) -> list[Item]:
    items: list[Item] = []
    for src in spec.get("sources", []):
        if not src.get("enabled"):
            continue
        kind = src.get("kind")
        try:
            if kind == "rss":
                got = rss.fetch(src, ua, cfg.HTTP_TIMEOUT)
            elif kind == "reddit":
                got = reddit.fetch(src, ua, cfg.HTTP_TIMEOUT)
            elif kind == "youtube":
                got = youtube.fetch(src, ua, cfg.HTTP_TIMEOUT)
            elif kind == "inbox":
                got = inbox.fetch(src, cfg, cfg.HTTP_TIMEOUT)
            elif kind == "pdf":
                got = pdf_docs.fetch(src, ua, cfg.HTTP_TIMEOUT)
            elif kind == "campussuite":
                got = campussuite.fetch(src, ua, cfg.HTTP_TIMEOUT)
            else:
                continue  # manual / unknown
        except Exception as exc:  # noqa: BLE001
            log.warning("adapter error (%s): %s", src["id"], exc)
            got = []
        # stamp per-source weight onto items for the classifier nudge
        for it in got:
            it._weight = int(src.get("weight", 0))
        items.extend(got)
    return items


def update_health(spec: dict, raw: list[Item]) -> dict:
    """Track per-source yield; flag sources quiet N runs in a row."""
    health = {}
    if cfg.HEALTH_FILE.exists():
        try:
            health = json.loads(cfg.HEALTH_FILE.read_text())
        except Exception:  # noqa: BLE001
            health = {}
    counts: dict[str, int] = {}
    for it in raw:
        counts[it.source_id] = counts.get(it.source_id, 0) + 1

    sources = health.get("sources", {})
    for src in spec.get("sources", []):
        if not src.get("enabled") or src.get("kind") == "manual":
            continue
        sid = src["id"]
        info = sources.get(sid, {"zero_runs": 0})
        if counts.get(sid, 0) == 0:
            info["zero_runs"] = info.get("zero_runs", 0) + 1
        else:
            info["zero_runs"] = 0
            info["last_yield"] = now_utc().isoformat()
        sources[sid] = info
    health = {"sources": sources, "alert_runs": cfg.ZERO_YIELD_ALERT_RUNS,
              "last_run": now_utc().isoformat()}
    cfg.HEALTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    cfg.HEALTH_FILE.write_text(json.dumps(health, indent=2))
    return health


def sample_items() -> list[Item]:
    """Offline mock items so the pipeline can be smoke-tested without network."""
    return [
        Item(source_id="town_calendar", source_name="Town Calendar", tier=1,
             url="https://www.littletonma.org/Calendar.aspx?EID=1",
             title="Planning Board Public Hearing: King Street Common (Lupoli) — June 25",
             body="The Planning Board will hold a public hearing on the King Street Common "
                  "mixed-use development. Written comments are due by June 24, 2026. "
                  "EEA #16921. Special permit and stormwater permit under review."),
        Item(source_id="town_notify_inbox", source_name="Notify Me", tier=1,
             url="",
             title="Special Town Meeting warrant posted — vote on Shaker Lane override",
             body="A Special Town Meeting will vote on the Shaker Lane school project "
                  "debt exclusion override. Town Meeting is scheduled for October 5, 2026."),
        Item(source_id="sean_for_littleton", source_name="Sean for Littleton", tier=3,
             url="https://seanforlittleton.substack.com/p/recap",
             title="School Committee recap: superintendent transition and FY27 budget",
             body="Recap of the latest School Committee meeting. Dr. Caira begins July 1. "
                  "The committee discussed a revised budget after a request to cut $600,000."),
        Item(source_id="reddit_massachusetts", source_name="Reddit r/massachusetts", tier=8,
             url="https://www.reddit.com/r/massachusetts/comments/x",
             title="Anyone been to the new spot on Great Road in Littleton MA?",
             body="Thinking of checking out the new place in Littleton, Massachusetts. "
                  "Worth the drive from Acton?"),
        Item(source_id="lelwd", source_name="LELWD", tier=4,
             url="https://www.lelwd.com/news",
             title="Littleton Drives Electric EV rebate program update",
             body="LELWD announced updates to its EV charging rebate. Applications close "
                  "August 1, 2026."),
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true",
                    help="run offline with mock items (no network/secrets)")
    args = ap.parse_args()

    spec = load_sources()
    defaults = spec.get("defaults", {})
    profile = spec.get("relevance_profile", {})
    ua = defaults.get("user_agent", "littleton-agent/0.1")
    threshold = int(defaults.get("relevance_threshold", 45))
    classify_model = defaults.get("classify_model", "claude-haiku-4-5")
    rollup_model = defaults.get("rollup_model", "claude-sonnet-4-6")

    # 1. collect
    raw = sample_items() if args.sample else run_adapters(spec, ua)
    log.info("collected %d raw items", len(raw))
    health = update_health(spec, raw) if not args.sample else {"sources": {}, "alert_runs": 3}

    # 2. collapse same-run duplicates only. The seen-store no longer gates the page —
    #    the page is a current-state snapshot, so a still-current item from a prior run
    #    stays on it. (The seen-store now only feeds the email's "what's new" at step 10.)
    fresh = dedupe.dedupe_within(raw)

    # 2b. split multi-topic recap posts into their constituent, categorized topics
    fresh = decompose.decompose(fresh, model=classify_model, api_key=cfg.ANTHROPIC_API_KEY)

    # 3. classify + 4. extract
    fresh = classify.classify(fresh, profile,
                              model=classify_model, api_key=cfg.ANTHROPIC_API_KEY)
    fresh = extract.extract(fresh)

    # 5. threshold
    kept = [it for it in fresh if it.relevance >= threshold]
    log.info("%d/%d items cleared relevance >= %d", len(kept), len(fresh), threshold)

    # 6. transcripts for kept LCTV items
    for it in kept:
        if it.source_id.startswith("lctv") and it.url:
            youtube.enrich_transcript(it)

    # 7. summarize
    summarize.summarize_items(kept, model=rollup_model, api_key=cfg.ANTHROPIC_API_KEY)
    rollup_text = summarize.rollup(kept, model=rollup_model, api_key=cfg.ANTHROPIC_API_KEY)

    # 7b. weekly edition — generate/refresh "The Week in Littleton" (skipped in sample)
    edition, all_editions = (None, [])
    if not args.sample:
        today_ny = datetime.now(ZoneInfo("America/New_York")).date()
        edition, all_editions = weekly.current_edition(
            kept, model=rollup_model, api_key=cfg.ANTHROPIC_API_KEY,
            today=today_ny, state_path=cfg.SEEN_FILE.parent / "editions.json")

    # 8. render — daily page + weekly edition + past-editions archive
    digest.write(kept, rollup_text, health, cfg.DOCS_DIR, cfg.ARCHIVE_DIR, edition=edition)
    editions.write(edition, all_editions, cfg.DOCS_DIR)
    html_doc = (cfg.DOCS_DIR / "index.html").read_text()

    # 9. email
    email_send.send(html_doc, cfg, len(kept))

    # 10. seen-store: the page already shows every current item, so the store no longer
    #     filters it — it only tracks what's NEW since the last run (the email's
    #     "what's new" signal). Commit so that stays accurate. Skip in sample mode.
    if not args.sample:
        new = dedupe.select_new(kept, cfg.SEEN_FILE)
        log.info("%d of %d page items are new since last run", len(new), len(kept))
        dedupe.commit(kept, cfg.SEEN_FILE)

    log.info("done: %d items in today's digest", len(kept))
    return 0


if __name__ == "__main__":
    sys.exit(main())
