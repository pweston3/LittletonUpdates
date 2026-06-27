"""Render the Weekly Edition ("The Week in Littleton") and the Past Editions archive.

`write()` emits, under docs/:
  - week.html               — the current edition (the daily marquee links here)
  - editions/<iso>.html     — an archived copy of every stored edition
  - past-editions.html      — the index the marquee's "Browse all past editions" links to

Pure rendering from the edition dicts produced by pipeline.weekly; no network.
"""
from __future__ import annotations

import logging
from pathlib import Path

from output.digest import _FONTS, _esc

log = logging.getLogger("output.editions")

_CSS = """
:root{--paper:#efe7d6;--card:#fbf7ec;--ink:#15120c;--muted:#5c574d;--navy:#102A54;
  --gold:#F4B41A;--gold-deep:#b48a17;--green:#2E7D5B;--hair:#cdbf9e;
  --serif:"Newsreader",Georgia,serif;--sans:"Public Sans",-apple-system,Helvetica,Arial,sans-serif;
  --display:"Libre Caslon Text","Newsreader",Georgia,serif}
*{box-sizing:border-box}
html,body{margin:0;padding:0;-webkit-font-smoothing:antialiased}
body{font-family:var(--sans);color:#1b1813;line-height:1.5;background-color:var(--paper);
  background-image:radial-gradient(#e2d8bf 1.1px,transparent 1.1px);background-size:21px 21px}
a{color:inherit}
.mini{background:var(--navy);border-bottom:4px solid var(--gold)}
.mini .in{max-width:1080px;margin:0 auto;padding:12px clamp(16px,4vw,40px);display:flex;
  align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.mini .wm{font-family:var(--display);font-size:21px;color:#fff}
.mini .rt{display:flex;align-items:center;gap:16px}
.mini .back{font-weight:700;font-size:10px;letter-spacing:.1em;text-transform:uppercase;
  color:#cdd6e6;text-decoration:none}
.mini .tag{font-weight:800;font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--gold)}
.wrap{max-width:1080px;margin:0 auto;padding:0 clamp(16px,4vw,40px) 60px}
.ehead{text-align:center;padding:clamp(28px,5vw,48px) 0 22px;border-bottom:3px double var(--navy)}
.ehead .kx{font-weight:800;font-size:11px;letter-spacing:.24em;text-transform:uppercase;color:var(--gold-deep)}
.ehead h1{font-family:var(--serif);font-weight:600;font-size:clamp(30px,5.4vw,54px);line-height:1.04;
  letter-spacing:-.015em;color:var(--ink);margin:16px auto 0;max-width:16ch}
.ehead .dek{font-family:var(--serif);font-style:italic;font-size:clamp(16px,2vw,21px);line-height:1.5;
  color:var(--muted);margin:14px auto 0;max-width:48ch}
.ehead .by{display:inline-flex;align-items:center;gap:10px;margin-top:20px;font-weight:700;font-size:11px;
  letter-spacing:.06em;text-transform:uppercase;color:#6b6557}
.ehead .by span{width:24px;height:1px;background:var(--hair)}
.body{display:flex;flex-wrap:wrap;gap:clamp(24px,4vw,52px);margin-top:30px;align-items:flex-start}
.essay{flex:2 1 440px;min-width:0}
.essay p{font-family:var(--serif);font-size:clamp(16px,1.7vw,19px);line-height:1.62;color:#2a261d;margin:0}
.essay p+p{margin-top:18px}
.essay .drop::first-letter{font-family:var(--display);font-size:clamp(54px,9vw,82px);line-height:.78;
  color:var(--navy);float:left;margin:6px 12px -4px 0}
.kicker{font-weight:800;font-size:11px;letter-spacing:.16em;text-transform:uppercase;margin:30px 0 10px}
.pq{margin:30px 0;padding:18px 0 18px 24px;border-left:4px solid var(--gold)}
.pq p{font-family:var(--serif);font-style:italic;font-weight:500;font-size:clamp(20px,2.6vw,27px);
  line-height:1.32;color:var(--navy)}
.aside{flex:1 1 250px;display:flex;flex-direction:column;gap:16px}
.bx{border:1.5px solid #1a1408;border-radius:5px;padding:18px 20px}
.bx .bl{font-weight:800;font-size:10px;letter-spacing:.16em;text-transform:uppercase}
.bx.nums{background:var(--navy);color:#fff;box-shadow:5px 5px 0 var(--gold)}
.bx.nums .bl{color:var(--gold)}
.bx.nums .row{display:flex;align-items:baseline;justify-content:space-between;gap:10px;padding-bottom:9px;
  border-bottom:1px solid rgba(255,255,255,.12)}
.bx.nums .row:last-child{border-bottom:0;padding-bottom:0}
.bx.nums .n{font-weight:800;font-size:26px;color:var(--gold)}
.bx.nums .lab{font-weight:600;font-size:11px;line-height:1.3;text-align:right;color:#cdd6e6}
.bx.nums .rows{margin-top:14px;display:flex;flex-direction:column;gap:11px}
.bx.threads{background:var(--card);box-shadow:5px 5px 0 var(--gold-deep)}
.bx.threads .bl{color:var(--navy)}
.bx.threads .t{display:flex;gap:10px;margin-top:12px}
.bx.threads .t:first-of-type{margin-top:13px}
.bx.threads .ar{color:#C8881A;font-weight:800;font-size:13px}
.bx.threads .tx{font-family:var(--serif);font-size:14px;line-height:1.4;color:#2a261d}
.bx.src{background:var(--card);box-shadow:5px 5px 0 var(--green)}
.bx.src .bl{color:var(--navy)}
.bx.src .chips{margin-top:12px;display:flex;flex-wrap:wrap;gap:7px}
.bx.src .chip{font-weight:700;font-size:9px;letter-spacing:.04em;text-transform:uppercase;color:#4a4334;
  border:1px solid var(--hair);border-radius:3px;padding:5px 8px}
.made{margin-top:34px;padding-top:18px;border-top:3px double var(--navy);display:flex;flex-wrap:wrap;
  gap:14px;align-items:center;justify-content:space-between}
.made .blurb{font-family:var(--serif);font-style:italic;font-size:14px;line-height:1.5;color:#6b6557;max-width:560px}
.made .hot{font-weight:700;font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:var(--gold-deep)}
/* past editions */
.plist{margin-top:30px;display:flex;flex-direction:column;gap:16px}
.ped{display:block;text-decoration:none;background:var(--card);border:1.5px solid #1a1408;border-radius:5px;
  padding:18px 20px;box-shadow:5px 5px 0 var(--navy);transition:transform .13s ease,box-shadow .13s ease}
.ped:hover{transform:translate(-2px,-2px);box-shadow:7px 7px 0 var(--gold-deep)}
.ped .kx{font-weight:800;font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--gold-deep)}
.ped h2{font-family:var(--serif);font-weight:600;font-size:22px;line-height:1.2;color:var(--ink);margin:7px 0 0}
.ped .dek{font-family:var(--serif);font-style:italic;font-size:15px;color:var(--muted);margin:6px 0 0}
.ped .meta{font-weight:600;font-size:11px;color:#9a937f;margin-top:9px}
.ptitle{text-align:center;padding:clamp(28px,5vw,44px) 0 8px}
.ptitle h1{font-family:var(--serif);font-weight:600;font-size:clamp(28px,4vw,40px);color:var(--ink);margin:0}
.ptitle .kx{font-weight:800;font-size:11px;letter-spacing:.24em;text-transform:uppercase;color:var(--gold-deep);margin-bottom:12px}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""


def _mini(active: str) -> str:
    return (
        '<div class="mini"><div class="in">'
        '<span class="wm">Littleton Signal</span>'
        '<div class="rt"><a class="back" href="index.html">&larr; Today\'s briefing</a>'
        f'<span class="tag">{active}</span></div>'
        '</div></div>'
    )


def _edition_page_html(ed: dict) -> str:
    secs = []
    body_paras = ed.get("lede", "")
    lede = f'<p class="drop">{_esc(body_paras)}</p>' if body_paras else ""
    for s in ed["sections"]:
        secs.append(f'<div class="kicker" style="color:{_esc(s["color"])}">{_esc(s["kicker"])}</div>'
                    f'<p>{_esc(s["body"])}</p>')
    pq = (f'<blockquote class="pq"><p>{_esc(ed["pull_quote"])}</p></blockquote>'
          if ed.get("pull_quote") else "")
    # Place the pull quote after the first themed section for rhythm.
    essay = lede + (secs[0] if secs else "") + pq + "".join(secs[1:])

    st = ed.get("stats", {})
    num_rows = "".join(
        f'<div class="row"><span class="n">{st.get(k, 0)}</span>'
        f'<span class="lab">{lab}</span></div>'
        for k, lab in (("items", "items gathered"), ("meetings", "public meetings"),
                       ("sources", "sources read"), ("deadlines", "resident deadlines"))
    )
    threads = "".join(
        f'<div class="t"><span class="ar">&rarr;</span><span class="tx">{_esc(t)}</span></div>'
        for t in ed.get("threads", [])
    ) or '<div class="t"><span class="tx">—</span></div>'
    chips = "".join(f'<span class="chip">{_esc(s)}</span>' for s in ed.get("sources", []))

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>The Week in Littleton — {_esc(ed['range_label'])}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{_FONTS}" rel="stylesheet"><style>{_CSS}</style></head><body>
{_mini("Weekly Edition")}
<div class="wrap">
  <header class="ehead">
    <div class="kx">The Week in Littleton · {_esc(ed['range_label'])}</div>
    <h1>{_esc(ed['headline'])}</h1>
    {f'<p class="dek">{_esc(ed["dek"])}</p>' if ed.get('dek') else ''}
    <div class="by"><span></span>Compiled by Littleton Signal across {st.get('sources', 0)} sources<span></span></div>
  </header>
  <div class="body">
    <article class="essay">{essay}</article>
    <aside class="aside">
      <div class="bx nums"><div class="bl">The week by the numbers</div><div class="rows">{num_rows}</div></div>
      <div class="bx threads"><div class="bl">Threads to watch</div>{threads}</div>
      {f'<div class="bx src"><div class="bl">Sources synthesized</div><div class="chips">{chips}</div></div>' if chips else ''}
    </aside>
  </div>
  <div class="made">
    <div class="blurb">This weekly read is gathered automatically from across the town's sources,
      deduplicated, and drafted with AI, then organized into one plain-language summary.
      Unofficial, and not affiliated with the Town of Littleton.</div>
    <div class="hot">Home of the Tigers</div>
  </div>
</div></body></html>"""


def _past_index_html(editions: list[dict]) -> str:
    cards = []
    for ed in reversed(editions):  # newest first
        href = f"editions/{_esc(ed['iso'])}.html"
        dek = f'<div class="dek">{_esc(ed["dek"])}</div>' if ed.get("dek") else ""
        st = ed.get("stats", {})
        cards.append(
            f'<a class="ped" href="{href}"><div class="kx">{_esc(ed["range_label"])}</div>'
            f'<h2>{_esc(ed["headline"])}</h2>{dek}'
            f'<div class="meta">{st.get("items", 0)} items · '
            f'{st.get("meetings", 0)} meetings · '
            f'{st.get("sources", 0)} sources</div></a>'
        )
    body = "".join(cards) or '<p style="color:var(--muted);text-align:center">No editions yet.</p>'
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Littleton Signal — Past Editions</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{_FONTS}" rel="stylesheet"><style>{_CSS}</style></head><body>
{_mini("Past Editions")}
<div class="wrap">
  <div class="ptitle"><div class="kx">Archive</div><h1>Past Weekly Editions</h1></div>
  <div class="plist">{body}</div>
</div></body></html>"""


def write(current: dict | None, editions: list[dict], docs_dir: Path) -> None:
    if not editions:
        return
    ed_dir = docs_dir / "editions"
    ed_dir.mkdir(parents=True, exist_ok=True)
    for ed in editions:
        (ed_dir / f"{ed['iso']}.html").write_text(_edition_page_html(ed))
    latest = current or editions[-1]
    (docs_dir / "week.html").write_text(_edition_page_html(latest))
    (docs_dir / "past-editions.html").write_text(_past_index_html(editions))
    log.info("editions written: week.html + %d archived + past-editions.html", len(editions))
