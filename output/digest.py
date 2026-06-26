"""Render the digest as a single self-contained HTML page.

Design: a civic "dispatch" for Littleton (01460). Ink-on-paper with one oxide-red
accent reserved for priority and deadlines; Georgia display over a system sans
body, monospace datelines/tags. The signature element is the Deadline Ledger
pinned to the top — the dated, actionable items are the whole point.

The same HTML is written to docs/index.html (GitHub Pages) and archived by date,
and reused as the email body.
"""
from __future__ import annotations

import html
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from adapters.base import Item, strip_date_suffix

_NY = ZoneInfo("America/New_York")  # cron runs in UTC; the page is for local readers


def _today_ny() -> date:
    return datetime.now(_NY).date()

log = logging.getLogger("output.digest")

_CAT_LABELS = {
    "town_hall": "Town Hall", "schools": "Schools", "development": "Development",
    "conservation": "Conservation", "public_safety": "Public Safety",
    "elections": "Elections & Town Meeting", "utility": "Utility",
    "community": "Community", "news": "In the Press", "other": "Other",
}
_CAT_ORDER = ["elections", "town_hall", "development", "schools", "conservation",
              "public_safety", "utility", "news", "community", "other"]

_CSS = """
:root{
  --ink:#1b1c18; --paper:#f6f4ee; --line:#d9d4c7; --muted:#6f6c60;
  --accent:#a63223; --accent-soft:#f0e2de; --chip:#ececdf;
}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
  line-height:1.5;-webkit-font-smoothing:antialiased}
.wrap{max-width:680px;margin:0 auto;padding:32px 22px 64px}
.dateline{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
.masthead{font-family:Georgia,"Times New Roman",serif;font-weight:700;
  font-size:34px;line-height:1.05;letter-spacing:-.01em;margin:6px 0 2px}
.masthead .accent{color:var(--accent)}
.rule{height:2px;background:var(--ink);margin:14px 0 0}
.rule.thin{height:1px;background:var(--line)}
.rollup{font-family:Georgia,"Times New Roman",serif;font-size:18px;line-height:1.55;
  margin:22px 0 26px}
.ledger{border:1px solid var(--line);border-left:3px solid var(--accent);
  background:#fff;padding:14px 16px;margin:0 0 30px}
.ledger h2{font-size:12px;letter-spacing:.12em;text-transform:uppercase;
  margin:0 0 10px;color:var(--accent)}
.ledger ul{margin:0;padding:0;list-style:none}
.ledger li{display:flex;gap:12px;padding:5px 0;border-top:1px dotted var(--line)}
.ledger li:first-child{border-top:none}
.ledger .when{font-family:ui-monospace,Menlo,monospace;font-size:12px;
  font-weight:700;white-space:nowrap;min-width:78px}
.ledger .what{font-size:13px;color:#36352d}
.week{border:1px solid var(--ink);background:#fff;padding:16px 18px;margin:0 0 26px}
.week h2{font-family:Georgia,"Times New Roman",serif;font-size:18px;font-weight:700;
  margin:0 0 12px;letter-spacing:-.01em}
.week ul{margin:0;padding:0;list-style:none}
.week li{display:flex;gap:14px;padding:7px 0;border-top:1px dotted var(--line);align-items:baseline}
.week li:first-child{border-top:none}
.week .when{font-family:ui-monospace,Menlo,monospace;font-size:12px;font-weight:700;
  color:var(--accent);white-space:nowrap;min-width:92px;text-transform:capitalize}
.week .what{font-size:14px;color:var(--ink)}
.week .kind{font-family:ui-monospace,Menlo,monospace;font-size:10px;color:var(--muted);
  text-transform:uppercase;letter-spacing:.05em;margin-left:6px}
.week .empty{color:var(--muted);font-size:14px;font-family:inherit}
.section.recordings > h2{color:var(--muted)}
.section{margin:0 0 30px}
.section > h2{font-size:13px;letter-spacing:.1em;text-transform:uppercase;
  color:var(--muted);margin:0 0 4px;display:flex;justify-content:space-between}
.item{padding:13px 0;border-top:1px solid var(--line)}
.item.lead{border-top:none}
.item .head{display:flex;align-items:baseline;gap:9px}
.dot{width:8px;height:8px;border-radius:50%;flex:0 0 8px;margin-top:6px;background:var(--line)}
.dot.hi{background:var(--accent)} .dot.mid{background:#caa64a}
.item a.title{color:var(--ink);text-decoration:none;font-weight:600;font-size:16px}
.item a.title:hover{text-decoration:underline}
.item .summary{margin:4px 0 0 17px;color:#3b3a31;font-size:14px}
.meta{margin:6px 0 0 17px;display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.chip{font-family:ui-monospace,Menlo,monospace;font-size:10px;letter-spacing:.05em;
  text-transform:uppercase;background:var(--chip);color:var(--muted);
  padding:2px 6px;border-radius:2px}
.chip.type{background:var(--accent-soft);color:var(--accent)}
.score{font-family:ui-monospace,Menlo,monospace;font-size:10px;color:var(--muted)}
.foot{margin-top:40px;padding-top:14px;border-top:2px solid var(--ink);
  font-size:12px;color:var(--muted)}
.foot .health{margin-top:8px}
.foot .bad{color:var(--accent)}
a{color:var(--accent)}
@media (prefers-color-scheme:dark){
  :root{--ink:#ece9df;--paper:#16160f;--line:#36352b;--muted:#9a978a;
    --accent:#e0795f;--accent-soft:#2a201c;--chip:#23231a}
  .ledger,.item a.title{background:transparent}
  .ledger,.week{background:#1d1d14}
}
"""


def _dot_class(r: int) -> str:
    return "hi" if r >= 70 else "mid" if r >= 50 else ""


def _esc(s: str) -> str:
    return html.escape(s or "")


def _rel_date(d: date, today: date) -> str:
    """Plain relative date: today / tomorrow / this Thursday / in 5 days."""
    n = (d - today).days
    if n == 0:
        return "today"
    if n == 1:
        return "tomorrow"
    if n == -1:
        return "yesterday"
    if 2 <= n <= 6:
        return "this " + d.strftime("%A")
    if n == 7:
        return "next " + d.strftime("%A")
    if n > 0:
        return f"in {n} days"
    return f"{-n} days ago"


def _countdown(d: date, today: date) -> str:
    n = (d - today).days
    if n <= 0:
        return "closes today"
    if n == 1:
        return "closes tomorrow"
    return f"in {n} days"


def _is_recording(it: Item) -> bool:
    return "youtube.com" in (it.url or "") or "youtu.be" in (it.url or "")


def _future_deadlines(it: Item, today: date) -> list[tuple[date, dict]]:
    out = []
    for dd in it.deadlines:
        try:
            d = date.fromisoformat(dd["date"])
        except Exception:
            continue
        if d >= today:
            out.append((d, dd))
    return out


def _ledger_html(items: list[Item], today: date) -> str:
    """Future deadlines only, with a countdown."""
    rows = []
    for it in items:
        for d, dd in _future_deadlines(it, today):
            rows.append((d, dd.get("label", it.title), it.url))
    if not rows:
        return ""
    rows.sort(key=lambda x: x[0])
    seen, lis = set(), []
    for d, label, url in rows:
        key = (d.isoformat(), label[:40])
        if key in seen:
            continue
        seen.add(key)
        when = _countdown(d, today)
        what = f'<a href="{_esc(url)}">{_esc(label)}</a>' if url else _esc(label)
        lis.append(f'<li><span class="when">{_esc(when)}</span><span class="what">{what}</span></li>')
    if not lis:
        return ""
    return ('<div class="ledger"><h2>Upcoming deadlines</h2><ul>'
            + "".join(lis) + "</ul></div>")


def _thisweek_html(items: list[Item], today: date) -> str:
    """Lead block: meetings, hearings, and deadlines within the next 7 days."""
    horizon = today + timedelta(days=7)
    rows, seen = [], set()
    for it in items:
        ev = it.event_date
        if ev and today <= ev <= horizon:
            label = strip_date_suffix(it.title) or it.title
            k = (ev, "event", label[:60])
            if k not in seen:
                seen.add(k); rows.append((ev, "event", label, it.url))
        for d, dd in _future_deadlines(it, today):
            if d <= horizon:
                label = dd.get("label", it.title)[:100]
                k = (d, "deadline", label[:40])
                if k not in seen:
                    seen.add(k); rows.append((d, "deadline", label, it.url))
    rows.sort(key=lambda x: x[0])
    if not rows:
        inner = '<li><span class="empty">Nothing on the public calendar in the next 7 days.</span></li>'
    else:
        lis = []
        for d, kind, label, url in rows:
            what = f'<a href="{_esc(url)}">{_esc(label)}</a>' if url else _esc(label)
            tag = "" if kind == "event" else '<span class="kind">deadline</span>'
            lis.append(f'<li><span class="when">{_esc(_rel_date(d, today))}</span>'
                       f'<span class="what">{what}{tag}</span></li>')
        inner = "".join(lis)
    return f'<div class="week"><h2>This week in Littleton</h2><ul>{inner}</ul></div>'


def _item_html(it: Item, lead: bool = False) -> str:
    title = f'<a class="title" href="{_esc(it.url)}">{_esc(it.title)}</a>' if it.url \
        else f'<span class="title" style="font-weight:600;font-size:16px">{_esc(it.title)}</span>'
    summary = f'<div class="summary">{_esc(it.summary)}</div>' if it.summary else ""
    chips = [f'<span class="chip type">{_esc(it.item_type)}</span>',
             f'<span class="chip">{_esc(it.source_name)}</span>',
             f'<span class="score">rel {it.relevance}</span>']
    return (f'<div class="item{" lead" if lead else ""}">'
            f'<div class="head"><span class="dot {_dot_class(it.relevance)}"></span>'
            f'<div style="flex:1">{title}{summary}'
            f'<div class="meta">{"".join(chips)}</div></div></div></div>')


def build_html(items: list[Item], rollup_text: str, health: dict) -> str:
    today = _today_ny()

    # Source health is operational telemetry — log it for the Actions run, not the page.
    unhealthy = [s for s, info in health.get("sources", {}).items()
                 if info.get("zero_runs", 0) >= health.get("alert_runs", 3)]
    if unhealthy:
        log.warning("health: %d source(s) quiet for >= %s runs: %s",
                    len(unhealthy), health.get("alert_runs", 3), ", ".join(unhealthy))

    # Partition by time so past events never read as upcoming.
    upcoming, past_lctv, undated = [], [], []
    for it in items:
        ev = it.event_date
        is_rec = _is_recording(it)
        fut_dl = bool(_future_deadlines(it, today))
        if is_rec and ev and ev <= today and not fut_dl:
            past_lctv.append(it)            # LCTV upload = recording of a meeting already held
        elif (ev and ev >= today) or fut_dl:
            upcoming.append(it)
        elif ev and ev < today:
            continue                        # past, no ongoing value — only in the dated archive
        else:
            undated.append(it)              # news/announcements with no single event

    thisweek = _thisweek_html(upcoming, today)
    ledger = _ledger_html(upcoming, today)

    # Main sections: future-dated + undated news, by relevance, grouped by category.
    main_items = sorted(upcoming + undated, key=lambda x: x.relevance, reverse=True)
    by_cat: dict[str, list[Item]] = {}
    for it in main_items:
        by_cat.setdefault(it.category, []).append(it)
    sections = []
    for cat in _CAT_ORDER:
        bucket = by_cat.get(cat)
        if not bucket:
            continue
        rows = "".join(_item_html(it, lead=(n == 0)) for n, it in enumerate(bucket))
        sections.append(
            f'<div class="section"><h2><span>{_CAT_LABELS.get(cat, cat)}</span>'
            f'<span style="color:var(--line)">{len(bucket)}</span></h2>{rows}</div>'
        )
    if not sections:
        sections.append('<div class="section"><p style="color:var(--muted)">'
                        'No current items today — check back tomorrow.</p></div>')

    # Recent meetings you can still watch.
    recordings = ""
    if past_lctv:
        past_lctv.sort(key=lambda x: x.event_date or today, reverse=True)
        rows = "".join(_item_html(it, lead=(n == 0)) for n, it in enumerate(past_lctv))
        recordings = (
            '<div class="section recordings"><h2>'
            '<span>Recent meetings — watch the recording</span>'
            f'<span style="color:var(--line)">{len(past_lctv)}</span></h2>{rows}</div>'
        )

    shown = len(main_items) + len(past_lctv)
    dateline = f"Littleton, Mass · 01460 · {today.strftime('%A, %B %-d, %Y')}"

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Littleton Signal — {today.strftime('%b %-d')}</title>
<style>{_CSS}</style></head>
<body><div class="wrap">
  <div class="dateline">{_esc(dateline)}</div>
  <div class="masthead">Littleton <span class="accent">Signal</span></div>
  <div class="rule"></div>
  <div class="rollup">{_esc(rollup_text)}</div>
  {thisweek}
  {ledger}
  {''.join(sections)}
  {recordings}
  <div class="foot">
    {shown} item(s) · Updated {today.strftime('%B %-d, %Y')}
  </div>
</div></body></html>"""


def write(items: list[Item], rollup_text: str, health: dict,
          docs_dir: Path, archive_dir: Path) -> Path:
    html_doc = build_html(items, rollup_text, health)
    docs_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)
    today = _today_ny().strftime("%Y-%m-%d")

    (docs_dir / "index.html").write_text(html_doc)
    (archive_dir / f"{today}.html").write_text(html_doc)
    _write_archive_index(archive_dir)
    log.info("digest written: index.html + archive/%s.html", today)
    return docs_dir / "index.html"


def _write_archive_index(archive_dir: Path) -> None:
    files = sorted((p.name for p in archive_dir.glob("20*.html")), reverse=True)
    links = "".join(
        f'<li><a href="{f}">{f[:-5]}</a></li>' for f in files
    )
    (archive_dir / "index.html").write_text(
        f"""<!doctype html><html><head><meta charset="utf-8">
<title>Littleton Signal — archive</title>
<style>body{{font-family:Georgia,serif;max-width:560px;margin:48px auto;padding:0 20px;
color:#1b1c18;background:#f6f4ee}}h1{{font-size:24px}}a{{color:#a63223}}
ul{{list-style:none;padding:0}}li{{padding:6px 0;border-bottom:1px solid #d9d4c7;
font-family:ui-monospace,Menlo,monospace;font-size:14px}}</style></head>
<body><h1>Littleton Signal — archive</h1><ul>{links}</ul></body></html>"""
    )
