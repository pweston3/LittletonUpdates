"""Render the digest as a single self-contained HTML page.

Design: "Littleton Signal" — a broadsheet civic front page on dotted cream paper
(#efe7d6) with a sticky navy masthead (#102A54), a gold/navy hazard stripe, and the
signature hard offset shadows (gold under navy boxes, navy under gold). Newsreader
serif headlines, Public Sans labels, Libre Caslon wordmark; gold accent (#F4B41A)
with per-category colors. Above the fold: a Weekly Edition marquee (links to
week.html) beside a gold Deadline Ledger and navy "This Week in Town". Below: a
category filter bar and colored card-grid sections, with the top stories flagged
as Editor's picks.

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
  --paper:#efe7d6; --dots:#e2d8bf; --band:#e6dabf; --card:#fbf7ec; --ink:#15120c;
  --muted:#5c574d; --faint:#9a937f; --hair:#cdbf9e; --line:#1a1408;
  --gold:#F4B41A; --gold-deep:#C8881A; --gold-ink:#7a4e06; --navy:#102A54;
  --green:#2E7D5B; --red:#B3472D;
  --serif:"Newsreader",Georgia,"Times New Roman",serif;
  --sans:"Public Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
  --display:"Libre Caslon Text","Newsreader",Georgia,serif;
}
*{box-sizing:border-box}
body{margin:0;color:#1b1813;font-family:var(--sans);line-height:1.5;
  background-color:var(--paper);
  background-image:radial-gradient(var(--dots) 1.1px,transparent 1.1px);
  background-size:21px 21px;-webkit-font-smoothing:antialiased}
a{color:inherit}
::selection{background:var(--gold);color:#15120c}
.in{max-width:1180px;margin:0 auto;padding:0 clamp(16px,4vw,40px)}
.torn{height:7px;background:repeating-linear-gradient(-60deg,var(--navy) 0 11px,var(--gold) 11px 22px)}

/* ── header (sticky) ──────────────────────────────────────── */
.mast{position:sticky;top:0;z-index:20;background:var(--navy)}
.mast .in{display:flex;flex-wrap:wrap;align-items:center;gap:14px;padding-top:14px;padding-bottom:14px}
.brand{flex:1 1 auto;min-width:0}
.kicker{font-weight:800;font-size:10px;letter-spacing:.22em;text-transform:uppercase;color:var(--gold)}
.wordmark{font-family:var(--display);font-size:clamp(26px,4.4vw,36px);line-height:1;color:#fff;margin-top:7px}
.tagline{font-weight:700;font-size:9px;letter-spacing:.2em;text-transform:uppercase;color:#d6bd6a;margin-top:8px}
.cd{flex:0 0 auto;display:flex;align-items:center;gap:11px;text-decoration:none;
  background:var(--gold);border-radius:12px;padding:9px 14px}
.cd .d{font-weight:800;font-size:22px;line-height:1;color:var(--navy);text-align:center}
.cd .u{font-weight:700;font-size:8px;letter-spacing:.12em;text-transform:uppercase;color:var(--gold-ink);margin-top:3px}
.cd .l{border-left:1px solid rgba(122,78,6,.35);padding-left:11px}
.cd .t{font-weight:800;font-size:9px;letter-spacing:.1em;text-transform:uppercase;color:var(--gold-ink)}
.cd .w{font-weight:700;font-size:13px;line-height:1.2;color:#15120c;margin-top:3px}

/* ── above-the-fold band ──────────────────────────────────── */
.band{background:var(--band);
  box-shadow:inset 0 1px 0 rgba(255,255,255,.55),inset 0 -22px 30px -26px rgba(16,42,84,.35)}
.band .in{padding-top:26px;padding-bottom:36px}
.hero{display:flex;flex-wrap:wrap;gap:18px;align-items:flex-start}
.marq-col{flex:2 1 380px;display:flex;flex-direction:column;gap:13px}
.marq{position:relative;overflow:hidden;text-decoration:none;display:block;background:var(--navy);
  border-radius:5px;border:1.5px solid var(--line);box-shadow:7px 7px 0 var(--gold);padding:clamp(22px,3.4vw,40px)}
.marq .tags{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.marq .we{font-weight:800;font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--gold)}
.marq .dot{width:5px;height:5px;border-radius:50%;background:#3b5489}
.marq .wk{font-weight:700;font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:#aeb9cf}
.marq h1{font-family:var(--serif);font-weight:600;font-size:clamp(27px,3.9vw,42px);line-height:1.07;
  letter-spacing:-.015em;color:#fff;margin:14px 0 0;max-width:20ch}
.marq .dek{font-family:var(--serif);font-style:italic;font-size:clamp(15px,1.7vw,19px);line-height:1.5;
  color:#cdd6e6;margin:13px 0 0;max-width:52ch}
.marq .cta{display:flex;align-items:center;gap:18px;flex-wrap:wrap;margin-top:22px}
.marq .btn{display:inline-flex;align-items:center;gap:8px;font-weight:800;font-size:11px;letter-spacing:.05em;
  text-transform:uppercase;color:#15120c;background:var(--gold);border-radius:6px;padding:12px 17px}
.marq .stat{font-weight:600;font-size:11px;line-height:1.4;color:#8d99b3}
.past{align-self:flex-start;text-decoration:none;font-weight:800;font-size:11px;letter-spacing:.05em;
  text-transform:uppercase;color:#15120c;border-bottom:2px solid var(--gold);padding-bottom:2px}
.side{flex:1 1 280px;display:flex;flex-direction:column;gap:14px}
.box-label{font-weight:800;font-size:10px;letter-spacing:.16em;text-transform:uppercase}
.ledger{background:var(--gold);border-radius:5px;padding:18px 20px;border:1.5px solid var(--line);
  box-shadow:5px 5px 0 var(--navy)}
.ledger .box-label{color:var(--gold-ink)}
.ledger ul{list-style:none;margin:14px 0 0;padding:0;display:flex;flex-direction:column;gap:12px}
.ledger li{display:flex;justify-content:space-between;align-items:flex-start;gap:10px}
.ledger .what{font-family:var(--serif);font-size:16px;line-height:1.25;color:#15120c}
.ledger .when{white-space:nowrap;font-weight:800;font-size:11px;color:#fff;background:var(--red);
  padding:5px 9px;border-radius:6px}
.thisweek{background:var(--navy);border-radius:5px;padding:18px 20px;color:#fff;border:1.5px solid var(--line);
  box-shadow:5px 5px 0 var(--gold)}
.thisweek .box-label{color:var(--gold)}
.thisweek ul{list-style:none;margin:14px 0 0;padding:0;display:flex;flex-direction:column;gap:11px}
.thisweek li{display:flex;gap:12px;align-items:baseline}
.thisweek li.lead-row{padding-top:10px;border-top:1px solid rgba(255,255,255,.14)}
.thisweek .dt{font-weight:700;font-size:12px;color:var(--gold);min-width:46px}
.thisweek .nm{font-family:var(--serif);font-size:14.5px;color:#eef1f7}
.thisweek li.lead-row .nm{font-weight:600;color:#fff}
.thisweek .empty{color:#aeb9cf;font-size:13px}

/* ── main ─────────────────────────────────────────────────── */
.wrap{max-width:1180px;margin:0 auto;padding:0 clamp(16px,4vw,40px) 50px}
.filter{margin-top:42px;padding:13px 15px;background:var(--card);border:1.5px solid var(--line);
  border-radius:5px;box-shadow:4px 4px 0 var(--navy);display:flex;align-items:center;gap:9px;flex-wrap:wrap}
.filter .fl{font-weight:800;font-size:10px;letter-spacing:.16em;text-transform:uppercase;color:#9a8c66;margin-right:3px}
.chip{cursor:pointer;font-weight:700;font-size:11px;letter-spacing:.04em;padding:8px 14px;border-radius:4px;
  border:1.5px solid #d8cdb2;background:var(--card);color:#4a4334}
.chip.on{background:var(--gold);color:#15120c;border-color:var(--line)}

.section{margin-top:38px}
.section:first-of-type{margin-top:22px}
.section>h2{display:flex;align-items:center;gap:12px;margin:0}
.section>h2 .sq{width:11px;height:11px;border-radius:2px;background:var(--cat,#5C574D);flex:0 0 auto}
.section>h2 .ttl{font-weight:800;font-size:14px;letter-spacing:.14em;text-transform:uppercase;color:#15120c}
.section>h2 .cnt{font-weight:600;font-size:12px;color:var(--faint)}
.section>h2 .rule{flex:1;height:1px;background:#ddd6c7}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px;margin-top:16px}
.card{background:var(--card);border-radius:4px;border:1.5px solid var(--line);padding:15px 16px;
  display:flex;flex-direction:column;box-shadow:5px 5px 0 var(--cat,#5C574D)}
.card.pick{box-shadow:5px 5px 0 var(--gold)}
.klabel{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:9px}
.kl-left{display:flex;align-items:center;gap:7px;flex-wrap:wrap}
.kcat{font-weight:800;font-size:9px;letter-spacing:.1em;text-transform:uppercase;color:var(--catink,#fbf7ec);
  background:var(--cat,#5C574D);padding:4px 7px 3px;border-radius:3px}
.pickbadge{font-weight:800;font-size:8px;letter-spacing:.08em;text-transform:uppercase;color:var(--gold-ink);
  background:var(--gold);padding:4px 7px 3px;border-radius:3px}
.kr{font-weight:700;font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:var(--faint)}
.khed{font-family:var(--serif);font-weight:600;font-size:18px;line-height:1.2;color:#15120c;margin:0}
.khed a{text-decoration:none}
.kbrief{font-size:13px;line-height:1.5;color:#5c574d;margin:7px 0 0}
.kfoot{display:flex;align-items:center;gap:8px;margin-top:14px}
.ksrc{font-weight:700;font-size:9px;letter-spacing:.05em;text-transform:uppercase;color:#4a4334;
  border:1px solid var(--hair);border-radius:3px;padding:4px 8px}
.kopen{margin-left:auto;font-weight:800;font-size:10px;letter-spacing:.05em;text-transform:uppercase;
  text-decoration:none;color:#15120c;border-bottom:2px solid var(--gold);padding-bottom:1px;white-space:nowrap}

/* ── footer ───────────────────────────────────────────────── */
.foot{margin-top:44px;background:var(--navy);border-radius:5px;padding:24px clamp(18px,3vw,30px);
  color:#cdd6e6;border:1.5px solid var(--line);box-shadow:6px 6px 0 var(--gold-deep)}
.foot .row{display:flex;flex-wrap:wrap;gap:20px;align-items:center;justify-content:space-between}
.foot .wm{font-family:var(--display);font-size:22px;color:#fff}
.foot .tl{font-weight:700;font-size:9px;letter-spacing:.18em;text-transform:uppercase;color:#d6bd6a;margin-top:7px}
.foot .blurb{font-size:13px;line-height:1.5;margin-top:10px;max-width:440px}
.foot .count{font-weight:800;font-size:26px;color:var(--gold);text-align:right}
.foot .clab{font-weight:600;font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:#aeb9cf;margin-top:4px;text-align:right}
.foot .gen{margin-top:10px;font-size:11px;color:#7c89a3}

/* ── hover / motion ───────────────────────────────────────── */
.card,.marq,.khed a,.kopen,.cd,.past{transition:transform .13s ease,box-shadow .13s ease,color .15s ease}
.card:hover{transform:translate(-2px,-2px);box-shadow:8px 8px 0 var(--cat,#102A54)}
.card.pick:hover{box-shadow:8px 8px 0 var(--gold)}
.marq:hover{transform:translate(-2px,-2px);box-shadow:10px 10px 0 var(--gold)}
.khed a:hover{color:var(--gold-deep)}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""


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

def _marquee_html(edition: dict | None, rollup_text: str, daily_stats: dict) -> str:
    if edition:
        wk = f"The Week in Littleton · {_esc(edition['range_label'])}"
        head = _esc(edition["headline"])
        dek = _esc(edition.get("dek", ""))
        st = edition.get("stats", daily_stats)
        cta = '<span class="btn">Read the full editorial <span>→</span></span>'
        href, past = "week.html", '<a class="past" href="past-editions.html">Browse all past editions →</a>'
    else:
        wk, head = "Today's briefing", "This week in Littleton"
        dek = _esc((rollup_text or "")[:240])
        st, cta, href, past = daily_stats, "", "#filterbar", ""
    stat = (f'{st.get("items", 0)} items · {st.get("meetings", 0)} meetings · '
            f'{st.get("sources", 0)} sources')
    dek_html = f'<p class="dek">{dek}</p>' if dek else ""
    return (f'<div class="marq-col"><a class="marq" href="{href}">'
            f'<div class="tags"><span class="we">Weekly Edition</span>'
            f'<span class="dot"></span><span class="wk">{wk}</span></div>'
            f'<h1>{head}</h1>{dek_html}'
            f'<div class="cta">{cta}<span class="stat">{stat}</span></div></a>{past}</div>')


def _card_html(it: Item, today: date, pick: bool = False) -> str:
    title = _esc(it.title)
    hed = f'<a href="{_esc(it.url)}">{title}</a>' if it.url else title
    brief = f'<p class="kbrief">{_esc(it.summary)}</p>' if it.summary else ""
    klabel = _esc(_CAT_LABELS.get(it.category, it.category))
    when = (_esc(_rel_date(it.event_date, today).capitalize())
            if it.event_date and it.event_date >= today else "")
    kr = f'<span class="kr">{when}</span>' if when else ""
    accent = _CAT_ACCENT.get(it.category, "#5C574D")
    badge = '<span class="pickbadge">★ Editor\'s pick</span>' if pick else ""
    opn = f'<a class="kopen" href="{_esc(it.url)}">Open →</a>' if it.url else ""
    return (f'<article class="{"card pick" if pick else "card"}" style="--cat:{accent}">'
            f'<div class="klabel"><span class="kl-left"><span class="kcat">{klabel}</span>'
            f'{badge}</span>{kr}</div>'
            f'<h3 class="khed">{hed}</h3>{brief}'
            f'<div class="kfoot"><span class="ksrc">{_esc(_short_src(it.source_name))}</span>'
            f'{opn}</div></article>')


def _section_html(cat: str, items: list[Item], today: date, picks: set[int]) -> str:
    cards = "".join(_card_html(it, today, id(it) in picks) for it in items)
    accent = _CAT_ACCENT.get(cat, "#5C574D")
    n = len(items)
    return (f'<section class="section" id="cat-{cat}" data-cat="{cat}" style="--cat:{accent}">'
            f'<h2><span class="sq"></span><span class="ttl">{_esc(_CAT_LABELS.get(cat, cat))}</span>'
            f'<span class="cnt">{n} update{"s" if n != 1 else ""}</span>'
            f'<span class="rule"></span></h2>'
            f'<div class="cards">{cards}</div></section>')


def _filter_html(present: list[str]) -> str:
    chips = ['<button class="chip on" data-chip data-cat="all">All</button>']
    chips += [f'<button class="chip" data-chip data-cat="{c}">{_esc(_CAT_LABELS.get(c, c))}</button>'
              for c in present]
    return (f'<div class="filter" id="filterbar"><span class="fl">Filter</span>{"".join(chips)}</div>')


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
            lead = "town meeting" in label.lower()
            lis.append(f'<li class="{"lead-row" if lead else ""}">'
                       f'<span class="dt">{d.strftime("%b %-d")}</span>'
                       f'<span class="nm">{_esc(label)}</span></li>')
        inner = "".join(lis)
    return (f'<div class="thisweek" id="nextmeeting">'
            f'<div class="box-label">This week in town</div><ul>{inner}</ul></div>')


_FILTER_JS = """
(function(){
  var chips=[].slice.call(document.querySelectorAll('[data-chip]'));
  var secs=[].slice.call(document.querySelectorAll('main section[data-cat]'));
  function set(cat){
    secs.forEach(function(s){
      s.style.display=(cat==='all'||s.getAttribute('data-cat')===cat)?'':'none';
    });
    chips.forEach(function(c){c.className='chip'+(c.getAttribute('data-cat')===cat?' on':'');});
  }
  chips.forEach(function(c){
    c.addEventListener('click',function(){set(c.getAttribute('data-cat'));});
  });
})();
"""


def build_html(items: list[Item], rollup_text: str, health: dict,
               edition: dict | None = None) -> str:
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
    picks = {id(it) for it in main_items[:3]}  # Editor's picks — top 3 overall

    by_cat: dict[str, list[Item]] = {}
    for it in main_items:
        by_cat.setdefault(it.category, []).append(it)
    present = [c for c in _CAT_ORDER if by_cat.get(c)]
    sections = "".join(_section_html(c, by_cat[c], today, picks) for c in present)

    recordings = ""
    if past_lctv:
        past_lctv.sort(key=lambda x: x.event_date or today, reverse=True)
        rows = "".join(_card_html(it, today) for it in past_lctv)
        n = len(past_lctv)
        recordings = ('<section class="section" data-cat="recordings" style="--cat:#5C574D">'
                      '<h2><span class="sq"></span><span class="ttl">Recent meetings — recordings</span>'
                      f'<span class="cnt">{n} recording{"s" if n != 1 else ""}</span>'
                      f'<span class="rule"></span></h2><div class="cards">{rows}</div></section>')

    rendered = main_items + past_lctv
    daily_stats = {
        "items": len(rendered),
        "meetings": sum(1 for it in rendered if it.item_type in {"meeting", "hearing", "event", "agenda"}),
        "sources": len({it.source_name for it in rendered}),
    }

    nm = _next_meeting(upcoming, today)
    badge = ""
    if nm:
        d, _it = nm
        days = max(0, (d - today).days)
        badge = (f'<a class="cd" href="#nextmeeting">'
                 f'<div><div class="d">{days}</div><div class="u">days</div></div>'
                 f'<div class="l"><div class="t">Next meeting</div>'
                 f'<div class="w">{d.strftime("%a, %b %-d")}</div></div></a>')

    eyebrow = today.strftime("%A · %B %-d, %Y · 01460")
    main_block = (sections + recordings if (sections or recordings) else
                  '<p style="margin-top:42px;color:var(--muted)">No current items today — check back tomorrow.</p>')

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Littleton Signal — {today.strftime('%b %-d')}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{_FONTS}" rel="stylesheet">
<style>{_CSS}</style></head>
<body>
<header class="mast"><div class="in">
  <div class="brand"><div class="kicker">{_esc(eyebrow)}</div>
    <div class="wordmark">Littleton Signal</div>
    <div class="tagline">Home of the Tigers</div></div>
  {badge}
</div></header>
<div class="torn"></div>
<section class="band"><div class="in"><div class="hero">
  {_marquee_html(edition, rollup_text, daily_stats)}
  <div class="side">{_ledger_html(upcoming, today)}{_thisweek_html(upcoming, today)}</div>
</div></div></section>
<div class="torn"></div>
<main class="wrap">
  {_filter_html(present)}
  {main_block}
  <footer class="foot">
    <div class="row">
      <div><div class="wm">Littleton Signal</div>
        <div class="tl">Home of the Tigers · Littleton, MA</div>
        <div class="blurb">An unofficial, community-run daily briefing. Gathered each morning from
          the town website, LCTV, the schools, local news, and the Conservation Trust —
          deduped and summarized in plain language.</div></div>
      <div><div class="count">{daily_stats['items']}</div>
        <div class="clab">items today · {daily_stats['sources']} sources</div></div>
    </div>
    <div class="gen">Generated {today.strftime('%Y-%m-%d')} · Updates every morning · Not affiliated with the Town of Littleton.</div>
  </footer>
</main>
<script>{_FILTER_JS}</script>
</body></html>"""


def write(items: list[Item], rollup_text: str, health: dict,
          docs_dir: Path, archive_dir: Path, edition: dict | None = None) -> Path:
    html_doc = build_html(items, rollup_text, health, edition)
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
