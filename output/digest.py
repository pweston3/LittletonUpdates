"""Render the digest as a single self-contained HTML page.

Design: "Littleton Signal" — a broadsheet civic front page on dotted cream paper
(#ECE3CC) with a navy masthead (#102A54), a gold bird mark, a gold/navy hazard
torn-edge, and the signature hard offset shadows (navy under gold boxes, gold
under navy). Newsreader serif headlines, Public Sans labels, Libre Caslon
wordmark; gold accent (#F4B41A) with per-category colors and a green relevance /
red TODAY accent. Two columns: lead story + colored card-grid sections on the
left; a gold Deadline Ledger and navy "This Week in Town" on the right.

The same HTML is written to docs/index.html (GitHub Pages) and archived by date,
and reused as the email body. All time logic is in America/New_York.
"""
from __future__ import annotations

import html
import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from adapters.base import Item, strip_date_suffix

log = logging.getLogger("output.digest")

_NY = ZoneInfo("America/New_York")  # cron runs in UTC; the page is for local readers


def _today_ny() -> date:
    return datetime.now(_NY).date()


_CAT_LABELS = {
    "elections": "Elections & Town Meeting", "town_hall": "Town Hall",
    "development": "Development", "schools": "Schools",
    "conservation": "Conservation", "public_safety": "Public Safety",
    "utility": "Utility & Water", "community": "Community",
    "news": "In the Press", "other": "Around Town",
}
_CAT_ORDER = ["elections", "town_hall", "development", "schools", "conservation",
              "public_safety", "utility", "news", "community", "other"]
_CAT_ACCENT = {
    "elections": "#7A4E06", "town_hall": "#102A54", "development": "#2C5BA6",
    "schools": "#C8881A", "conservation": "#2E7D5B", "public_safety": "#B3472D",
    "utility": "#2A7E8C", "community": "#A3946F", "news": "#5C574D", "other": "#5C574D",
}
# Text color on the accent-colored label pill (dark text on light accents).
_CAT_INK = {"schools": "#1A1408", "community": "#1A1408"}


def _short_src(name: str) -> str:
    """Shorten a feed name for the card source pill: 'X — official news' -> 'X'."""
    return re.split(r"\s+—\s+| \(", name or "", maxsplit=1)[0].strip().upper()


def _clean_deadline(label: str) -> str:
    """De-shout and trim a raw deadline sentence for the ledger / This Week."""
    s = re.sub(r"\s+", " ", label or "").strip()
    s = re.sub(r"^final reminder!?:?\s*", "", s, flags=re.I)
    s = re.sub(r"\s+(will close on|closes on|close on|due by|on)\s*$", "", s, flags=re.I)
    letters = [c for c in s if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) / len(letters) > 0.6:
        s = s.capitalize()
    return s[:48].strip()

_FONTS = ("https://fonts.googleapis.com/css2?"
          "family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;0,6..72,700;0,6..72,800;"
          "1,6..72,400;1,6..72,500&"
          "family=Public+Sans:wght@400;600;700;800&"
          "family=Libre+Caslon+Text:wght@400;700&display=swap")

_CSS = """
:root{
  --paper:#ECE3CC; --card:#FBF7EC; --ink:#1A1408; --muted:#5C574D; --faint:#9A8F70;
  --hair:#CDBF9E; --gold:#F4B41A; --gold-deep:#C8881A; --navy:#102A54; --navy-2:#0B1D3E;
  --green:#2E7D5B; --red:#B3472D;
  --serif:"Newsreader",Georgia,"Times New Roman",serif;
  --sans:"Public Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
  --display:"Libre Caslon Text","Newsreader",Georgia,serif;
}
*{box-sizing:border-box}
body{margin:0;color:var(--ink);font-family:var(--sans);line-height:1.5;
  background-color:var(--paper);
  background-image:radial-gradient(rgba(26,20,8,.07) 1.4px,transparent 1.5px);
  background-size:24px 24px;-webkit-font-smoothing:antialiased}
a{color:inherit}
.eyebrow{font-weight:800;font-size:13px;letter-spacing:.16em;text-transform:uppercase}
.in{max-width:1200px;margin:0 auto;padding:0 30px}

/* ── masthead ─────────────────────────────────────────────── */
.mast{background:var(--navy);color:#fff;padding:20px 0 0}
.mast .eyebrow{color:var(--gold);margin-bottom:10px}
.mast-row{display:flex;align-items:center;justify-content:space-between;gap:18px;
  flex-wrap:wrap;padding-bottom:20px}
.brand{display:flex;align-items:center;gap:16px}
.mark{flex:0 0 auto}
.wordmark{font-family:var(--display);font-weight:700;font-size:46px;line-height:1;color:#fff}
.tagline{font-weight:800;font-size:11px;letter-spacing:.22em;text-transform:uppercase;
  color:var(--gold);margin-top:8px}
.badge{display:flex;align-items:center;gap:14px;background:var(--gold);color:var(--navy);
  border:2px solid #d89d10;border-radius:12px;padding:10px 18px}
.badge .n{font-family:var(--display);font-weight:700;font-size:38px;line-height:.85;text-align:center}
.badge .n small{display:block;font-family:var(--sans);font-weight:800;font-size:9px;letter-spacing:.12em}
.badge .lab{font-weight:800;font-size:11px;letter-spacing:.1em;text-transform:uppercase;
  border-left:2px solid rgba(16,42,84,.3);padding-left:14px;line-height:1.35}
.badge .lab b{display:block;font-size:16px;letter-spacing:0;text-transform:none;margin-top:3px}
.navband{background:var(--navy-2)}
.nav{display:flex;gap:11px;flex-wrap:wrap;padding:13px 0}
.nav a{font-weight:700;font-size:13.5px;color:#cdd6e6;text-decoration:none;padding:8px 17px;
  border-radius:8px;border:1px solid rgba(205,214,230,.22)}
.nav a.on{background:var(--gold);color:var(--navy);border-color:var(--gold)}
.torn{height:8px;background:repeating-linear-gradient(45deg,var(--gold) 0 9px,var(--navy) 9px 18px)}

/* ── layout ───────────────────────────────────────────────── */
.wrap{max-width:1200px;margin:0 auto;padding:36px 30px 80px}
.grid{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:38px;align-items:start;margin:0 0 40px}
@media (max-width:820px){.grid{grid-template-columns:1fr}}

/* lead story */
.lead{background:var(--card);border:2px solid var(--ink);box-shadow:11px 11px 0 var(--navy)}
.lead-img{position:relative;height:300px;border-bottom:2px solid var(--ink);
  background:repeating-linear-gradient(-45deg,#e9dfc6 0 15px,#e0d5b7 15px 30px)}
.pill{font-weight:800;font-size:12px;letter-spacing:.1em;text-transform:uppercase;
  background:var(--gold);color:var(--navy);padding:7px 14px;border-radius:4px}
.lead-img .pill{position:absolute;left:26px;bottom:24px}
.lead-body{padding:28px 32px 30px}
.lead h1{font-family:var(--serif);font-weight:800;font-size:40px;line-height:1.08;
  letter-spacing:-.01em;margin:0 0 16px}
.lead h1 a{text-decoration:none}
.deck{font-family:var(--serif);font-size:19px;line-height:1.58;color:#3a342a;margin:0 0 22px}
.byline{display:flex;gap:16px;align-items:center;flex-wrap:wrap;font-size:13px;color:var(--muted);
  border-top:1px solid var(--hair);padding-top:16px}
.src{background:#e6dcc2;color:#5c574d;font-weight:700;font-size:11px;padding:4px 9px;border-radius:4px}
.rel{color:var(--green);font-weight:700}
.read{margin-left:auto;font-weight:800;letter-spacing:.04em;text-transform:uppercase;font-size:12px;
  text-decoration:none;border-bottom:2px solid var(--gold);padding-bottom:3px}

/* category sections — colored card grid */
.section{margin:0 0 38px}
.section>h2{font-weight:800;font-size:15px;letter-spacing:.12em;text-transform:uppercase;
  color:var(--ink);display:flex;align-items:center;gap:11px;margin:0 0 12px}
.section>h2 .sq{width:13px;height:13px;background:var(--cat,#5C574D);flex:0 0 auto}
.section>h2 .cnt{font-weight:700;font-size:12px;letter-spacing:0;text-transform:none;color:var(--faint)}
.section>.crule{height:2px;background:var(--ink);opacity:.16;margin:0 0 18px}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(244px,1fr));gap:20px}
.card{background:var(--card);border:2px solid var(--ink);box-shadow:6px 6px 0 var(--cat,#5C574D);
  padding:15px 17px 16px;display:flex;flex-direction:column}
.klabel{display:flex;justify-content:space-between;align-items:center;gap:8px}
.kcat{background:var(--cat,#5C574D);color:var(--catink,#fff);font-weight:800;font-size:9.5px;
  letter-spacing:.08em;text-transform:uppercase;padding:4px 8px;border-radius:3px}
.kr{color:var(--faint);font-weight:700;font-size:10px;letter-spacing:.06em;text-transform:uppercase}
.khed{font-family:var(--serif);font-weight:700;font-size:18px;line-height:1.24;margin:12px 0 0}
.khed a{text-decoration:none}
.kbrief{font-family:var(--serif);font-size:13.5px;line-height:1.5;color:#5c574d;margin:8px 0 0}
.kfoot{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:auto;padding-top:14px}
.ksrc{border:1px solid var(--hair);color:var(--muted);font-weight:700;font-size:9.5px;letter-spacing:.06em;
  text-transform:uppercase;padding:5px 8px;border-radius:4px}
.kopen{font-weight:800;font-size:10px;letter-spacing:.06em;text-transform:uppercase;text-decoration:none;
  border-bottom:2px solid var(--gold);padding-bottom:3px;white-space:nowrap}
.recordings .khed{font-weight:600;font-size:16px}

/* ── sidebar ──────────────────────────────────────────────── */
.side{display:flex;flex-direction:column;gap:30px}
.box-label{font-weight:800;font-size:12px;letter-spacing:.14em;text-transform:uppercase;margin:0 0 12px}
.ledger{background:var(--gold);color:var(--navy);box-shadow:9px 9px 0 var(--navy);
  border-radius:5px;padding:18px 20px}
.ledger .box-label{color:#3f2c05}
.ledger ul{list-style:none;margin:0;padding:0}
.ledger li{display:flex;align-items:center;gap:12px;padding:6px 0}
.ledger li+li{border-top:1px solid rgba(16,42,84,.16)}
.ledger .what{font-family:var(--serif);font-weight:600;font-size:18px;flex:1;line-height:1.25}
.ledger .when{flex:0 0 auto;background:var(--red);color:#fff;font-weight:800;font-size:11px;
  letter-spacing:.06em;text-transform:uppercase;padding:5px 11px;border-radius:5px;white-space:nowrap}
.thisweek{background:var(--navy);color:#eef1f7;border:2px solid var(--gold);
  box-shadow:9px 9px 0 var(--gold);border-radius:5px;padding:18px 20px}
.thisweek .box-label{color:var(--gold)}
.thisweek ul{list-style:none;margin:0;padding:0}
.thisweek li{display:flex;gap:16px;padding:8px 0;align-items:baseline}
.thisweek li+li{border-top:1px solid rgba(244,180,26,.16)}
.thisweek .dt{flex:0 0 52px;color:var(--gold);font-weight:700;font-size:13px}
.thisweek .nm{font-family:var(--serif);font-size:17px;line-height:1.25}
.thisweek .nm.lead-meet{font-weight:700}
.thisweek .empty{color:#aeb9cf;font-size:13px}

.foot{max-width:1200px;margin:0 auto;padding:0 30px 50px}
.foot .ft{border-top:2px solid var(--ink);padding-top:14px;font-size:12px;color:var(--muted);
  display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px}

/* ── hover / motion ───────────────────────────────────────── */
.card,.nav a,.khed a,.lead h1 a,.read,.lead{
  transition:transform .16s ease,box-shadow .16s ease,color .15s ease,
    background .15s ease,border-color .15s ease}
.card:hover{transform:translate(-3px,-3px);box-shadow:9px 9px 0 var(--cat,#102A54)}
.lead:hover{box-shadow:14px 14px 0 var(--navy)}
.nav a:hover{background:rgba(244,180,26,.16);border-color:var(--gold);color:#fff}
.khed a:hover,.lead h1 a:hover{color:var(--gold-deep)}
.read:hover{border-bottom-color:var(--ink);color:var(--ink)}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""

_MARK = ('<svg class="mark" width="42" height="42" viewBox="0 0 100 100" '
         'xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><g fill="#F4B41A">'
         '<ellipse cx="26" cy="46" rx="9.5" ry="13" transform="rotate(-22 26 46)"/>'
         '<ellipse cx="44" cy="34" rx="10" ry="14"/>'
         '<ellipse cx="62" cy="34" rx="10" ry="14"/>'
         '<ellipse cx="80" cy="46" rx="9.5" ry="13" transform="rotate(22 80 46)"/>'
         '<path d="M53 54c-15 0-27 11-27 25 0 10 8 16 18 15 6-1 7-3 11-3s5 2 11 3'
         'c10 1 18-5 18-15 0-14-12-25-27-25z"/></g></svg>')


def _esc(s: str) -> str:
    return html.escape(s or "")


def _rel_date(d: date, today: date) -> str:
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
        return "Today"
    if n == 1:
        return "Tomorrow"
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


def _partition(items: list[Item], today: date):
    """Sort items by time → (upcoming, past_lctv, undated, dropped). Only dated
    MEETING/EVENT-type items (non-LCTV) before today are dropped; news,
    announcements, and undated items are always kept."""
    upcoming, past_lctv, undated, dropped = [], [], [], []
    for it in items:
        ev = it.event_date
        is_rec = _is_recording(it)
        is_meeting_event = it.item_type in {"meeting", "hearing", "event", "agenda"}
        if (ev and ev >= today) or _future_deadlines(it, today):
            upcoming.append(it)
        elif is_rec and ev and ev <= today:
            past_lctv.append(it)
        elif is_meeting_event and not is_rec and ev and ev < today:
            dropped.append(it)
        else:
            undated.append(it)
    return upcoming, past_lctv, undated, dropped


def _is_meeting(it: Item) -> bool:
    return (it.item_type in {"meeting", "hearing", "event"}
            or any(w in it.title.lower() for w in ("board", "committee", "commission",
                                                   "meeting", "hearing", "town meeting")))


def _next_meeting(upcoming: list[Item], today: date):
    cands = [(it.event_date, it) for it in upcoming
             if it.event_date and it.event_date >= today
             and not _is_recording(it) and _is_meeting(it)]
    if not cands:
        return None
    cands.sort(key=lambda x: x[0])
    return cands[0]


# ── piece renderers ───────────────────────────────────────────

def _lead_html(it: Item) -> str:
    cat = _CAT_LABELS.get(it.category, it.category).upper()
    title = _esc(it.title)
    head = f'<a href="{_esc(it.url)}">{title}</a>' if it.url else title
    deck = f'<p class="deck">{_esc(it.summary)}</p>' if it.summary else ""
    read = f'<a class="read" href="{_esc(it.url)}">Read the source →</a>' if it.url else ""
    return (f'<article class="lead">'
            f'<div class="lead-img"><span class="pill">Today\'s lead · {_esc(cat)}</span></div>'
            f'<div class="lead-body"><h1>{head}</h1>{deck}'
            f'<div class="byline"><span class="src">{_esc(it.source_name)}</span>'
            f'{read}</div></div></article>')


def _card_html(it: Item, today: date) -> str:
    title = _esc(it.title)
    hed = f'<a href="{_esc(it.url)}">{title}</a>' if it.url else title
    brief = f'<p class="kbrief">{_esc(it.summary)}</p>' if it.summary else ""
    klabel = _esc(_CAT_LABELS.get(it.category, it.category).upper())
    when = (_esc(_rel_date(it.event_date, today).capitalize())
            if it.event_date and it.event_date >= today else "")
    kr = f'<span class="kr">{when}</span>' if when else ""
    accent = _CAT_ACCENT.get(it.category, "#5C574D")
    catink = _CAT_INK.get(it.category, "#FFFFFF")
    opn = f'<a class="kopen" href="{_esc(it.url)}">Open →</a>' if it.url else ""
    foot = (f'<div class="kfoot"><span class="ksrc">{_esc(_short_src(it.source_name))}</span>'
            f'{opn}</div>')
    return (f'<article class="card" style="--cat:{accent};--catink:{catink}">'
            f'<div class="klabel"><span class="kcat">{klabel}</span>{kr}</div>'
            f'<h3 class="khed">{hed}</h3>{brief}{foot}</article>')


def _section_html(cat: str, items: list[Item], today: date) -> str:
    cards = "".join(_card_html(it, today) for it in items)
    accent = _CAT_ACCENT.get(cat, "#5C574D")
    n = len(items)
    return (f'<section class="section" id="cat-{cat}" style="--cat:{accent}">'
            f'<h2><span class="sq"></span>{_esc(_CAT_LABELS.get(cat, cat))}'
            f'<span class="cnt">{n} update{"s" if n != 1 else ""}</span></h2>'
            f'<div class="crule"></div><div class="cards">{cards}</div></section>')


def _ledger_html(items: list[Item], today: date) -> str:
    rows, seen = [], set()
    for it in items:
        for d, dd in _future_deadlines(it, today):
            key = (d.isoformat(), dd.get("label", it.title)[:40])
            if key in seen:
                continue
            seen.add(key)
            rows.append((d, dd.get("label", it.title)))
    if not rows:
        return ""
    rows.sort(key=lambda x: x[0])
    lis = "".join(
        f'<li><span class="what">{_esc(_clean_deadline(strip_date_suffix(label) or label))}</span>'
        f'<span class="when">{_esc(_countdown(d, today))}</span></li>'
        for d, label in rows[:6]
    )
    return f'<div class="ledger"><div class="box-label">Deadline ledger</div><ul>{lis}</ul></div>'


def _thisweek_html(items: list[Item], today: date) -> str:
    horizon = today + timedelta(days=7)
    rows, seen = [], set()
    for it in items:
        ev = it.event_date
        if ev and today <= ev <= horizon and not _future_deadlines(it, today):
            label = strip_date_suffix(it.title) or it.title
            k = (ev, label[:50])
            if k not in seen:
                seen.add(k); rows.append((ev, "event", label))
        for d, dd in _future_deadlines(it, today):
            if d <= horizon:
                label = dd.get("label", it.title)
                k = (d, "deadline", label[:40])
                if k not in seen:
                    seen.add(k); rows.append((d, "deadline", _clean_deadline(strip_date_suffix(label) or label)))
    rows.sort(key=lambda x: x[0])
    if not rows:
        inner = '<li><span class="empty">Nothing on the public calendar in the next 7 days.</span></li>'
    else:
        lis = []
        for d, kind, label in rows:
            cls = "nm lead-meet" if kind == "deadline" else "nm"
            lis.append(f'<li><span class="dt">{d.strftime("%b %-d")}</span>'
                       f'<span class="{cls}">{_esc(label)}</span></li>')
        inner = "".join(lis)
    return f'<div class="thisweek"><div class="box-label">This week in town</div><ul>{inner}</ul></div>'


def build_html(items: list[Item], rollup_text: str, health: dict) -> str:
    today = _today_ny()

    unhealthy = [s for s, info in health.get("sources", {}).items()
                 if info.get("zero_runs", 0) >= health.get("alert_runs", 3)]
    if unhealthy:
        log.warning("health: %d source(s) quiet for >= %s runs: %s",
                    len(unhealthy), health.get("alert_runs", 3), ", ".join(unhealthy))

    upcoming, past_lctv, undated, dropped = _partition(items, today)
    if dropped:
        log.info("partition: archived %d stale dated meeting/event item(s)", len(dropped))

    main_items = sorted(upcoming + undated, key=lambda x: x.relevance, reverse=True)
    lead = main_items[0] if main_items else None
    rest = main_items[1:] if main_items else []

    by_cat: dict[str, list[Item]] = {}
    for it in rest:
        by_cat.setdefault(it.category, []).append(it)
    present = [c for c in _CAT_ORDER if by_cat.get(c)]
    sections = "".join(_section_html(c, by_cat[c], today) for c in present)

    recordings = ""
    if past_lctv:
        past_lctv.sort(key=lambda x: x.event_date or today, reverse=True)
        rows = "".join(_card_html(it, today) for it in past_lctv)
        n = len(past_lctv)
        recordings = ('<section class="section recordings" style="--cat:#5C574D">'
                      '<h2><span class="sq"></span>Recent meetings — watch the recording'
                      f'<span class="cnt">{n} recording{"s" if n != 1 else ""}</span></h2>'
                      f'<div class="crule"></div><div class="cards">{rows}</div></section>')

    nm = _next_meeting(upcoming, today)
    badge = ""
    if nm:
        d, it = nm
        days = (d - today).days
        if days == 0:
            n_html = '<span class="n" style="font-size:22px">Today</span>'
        elif days == 1:
            n_html = '<span class="n">1<small>Day</small></span>'
        else:
            n_html = f'<span class="n">{days}<small>Days</small></span>'
        badge = (f'<div class="badge">{n_html}'
                 f'<span class="lab">Next meeting<b>{d.strftime("%a, %b %-d")}</b></span></div>')

    nav = ['<a class="on" href="#top">All</a>']
    nav += [f'<a href="#cat-{c}">{_esc(_CAT_LABELS.get(c, c))}</a>' for c in present]
    nav_html = "".join(nav)

    eyebrow = f'{today.strftime("%A · %B %-d, %Y").upper()} · 01460'
    shown = len(main_items) + len(past_lctv)
    lead_block = (_lead_html(lead) if lead else
                  '<p style="color:var(--muted)">No current items today — check back tomorrow.</p>')

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Littleton Signal — {today.strftime('%b %-d')}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{_FONTS}" rel="stylesheet">
<style>{_CSS}</style></head>
<body><a id="top"></a>
<header class="mast"><div class="in">
  <div class="eyebrow">{_esc(eyebrow)}</div>
  <div class="mast-row">
    <div class="brand"><div><div class="wordmark">Littleton Signal</div>
      <div class="tagline">Home of the Tigers</div></div></div>
    {badge}
  </div></div>
  <div class="navband"><div class="in"><nav class="nav">{nav_html}</nav></div></div>
</header>
<div class="torn"></div>
<main class="wrap">
  <div class="grid">
    <div class="main">{lead_block}</div>
    <aside class="side">{_ledger_html(upcoming, today)}{_thisweek_html(upcoming, today)}</aside>
  </div>
  {sections}{recordings}
</main>
<footer class="foot"><div class="ft"><span>{shown} item(s) on today's page</span>
  <span>Updated {today.strftime('%B %-d, %Y')}</span></div></footer>
</body></html>"""


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
    links = "".join(f'<li><a href="{f}">{f[:-5]}</a></li>' for f in files)
    (archive_dir / "index.html").write_text(
        f"""<!doctype html><html><head><meta charset="utf-8">
<title>Littleton Signal — archive</title>
<style>body{{font-family:Georgia,serif;max-width:560px;margin:48px auto;padding:0 20px;
color:#1A1408;background:#ECE3CC}}h1{{font-size:24px}}a{{color:#C8881A}}
ul{{list-style:none;padding:0}}li{{padding:6px 0;border-bottom:1px solid #CDBF9E;
font-family:ui-monospace,Menlo,monospace;font-size:14px}}</style></head>
<body><h1>Littleton Signal — archive</h1><ul>{links}</ul></body></html>"""
    )
