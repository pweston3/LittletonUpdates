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
from datetime import datetime, timezone
from pathlib import Path

from adapters.base import Item

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
  .ledger{background:#1d1d14}
}
"""


def _dot_class(r: int) -> str:
    return "hi" if r >= 70 else "mid" if r >= 50 else ""


def _esc(s: str) -> str:
    return html.escape(s or "")


def _ledger_html(items: list[Item]) -> str:
    rows = []
    for it in items:
        for d in it.deadlines:
            rows.append((d["date"], d.get("label", it.title), it.url))
    if not rows:
        return ""
    rows.sort(key=lambda x: x[0])
    seen, lis = set(), []
    for date, label, url in rows:
        key = (date, label[:40])
        if key in seen:
            continue
        seen.add(key)
        try:
            pretty = datetime.fromisoformat(date).strftime("%b %-d")
        except Exception:
            pretty = date
        what = f'<a href="{_esc(url)}">{_esc(label)}</a>' if url else _esc(label)
        lis.append(f'<li><span class="when">{pretty}</span><span class="what">{what}</span></li>')
    if not lis:
        return ""
    return ('<div class="ledger"><h2>Deadline ledger</h2><ul>'
            + "".join(lis) + "</ul></div>")


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
    items = sorted(items, key=lambda x: x.relevance, reverse=True)
    today = datetime.now(timezone.utc).astimezone()
    dateline = f"Littleton, Mass · 01460 · {today.strftime('%A, %B %-d, %Y')}"

    ledger = _ledger_html(items)

    # group by category, preserving the configured order
    by_cat: dict[str, list[Item]] = {}
    for it in items:
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
                        'No new items cleared the relevance threshold today.</p></div>')

    # health footer
    unhealthy = [s for s, info in health.get("sources", {}).items()
                 if info.get("zero_runs", 0) >= health.get("alert_runs", 3)]
    health_line = (f'<span class="bad">⚠ {len(unhealthy)} source(s) quiet: '
                   f'{", ".join(unhealthy)}</span>') if unhealthy else "All sources reporting."

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
  {ledger}
  {''.join(sections)}
  <div class="foot">
    {len(items)} item(s) · generated {today.strftime('%Y-%m-%d %H:%M %Z')}
    <div class="health">{health_line}</div>
  </div>
</div></body></html>"""


def write(items: list[Item], rollup_text: str, health: dict,
          docs_dir: Path, archive_dir: Path) -> Path:
    html_doc = build_html(items, rollup_text, health)
    docs_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")

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
