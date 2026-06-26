# Littleton Signal — local-intelligence agent

An autonomous daily briefing on Littleton, MA: town-hall meetings, agendas, votes,
deadlines, development filings, school news, conservation, and local chatter —
gathered from every reachable source, deduped, ranked by relevance, summarized,
and published as a webpage + email.

It runs on a GitHub Actions cron with no server to maintain. The compute and the
published page both live on GitHub.

This is **Phase 1**: the RSS / Reddit / YouTube / inbox spine plus the full
pipeline. The harder adapters (warrant PDFs, MEPA scraping) are structured but
left for Phase 2 — see the roadmap.

---

## How it works

```
sources.yaml ─▶ adapters ─▶ dedupe ─▶ classify ─▶ extract ─▶ threshold
                                                                   │
        email ◀─ render digest ◀─ summarize ◀────────────────────┘
                      │
                  docs/ (GitHub Pages) + docs/archive/
```

- **Adapters** (`adapters/`) each turn one source type into a common `Item`:
  `rss` (News Flash, Patch, Substack, Conservation Trust, LELWD, schools),
  `reddit` (search `.rss` with a Massachusetts-context gate so the Colorado and
  New Hampshire Littletons drop out), `youtube` (LCTV channel feed + optional
  meeting transcripts), `inbox` (IMAP — the **primary** route for town content,
  since the CivicPlus site blocks automated fetching), and `pdf` (warrants —
  Phase 2).
- **dedupe** hashes title + host + body-prefix against a committed seen-store, so
  the same meeting arriving via calendar + Patch + newsletter only appears once.
- **classify** assigns category / type / a 0–100 relevance score. With an API key
  it's one Claude Haiku call per batch guided by `relevance_profile`; without a
  key it falls back to a keyword heuristic, so a digest is always produced.
- **extract** pulls dates next to deadline/vote/hearing language into a structured
  ledger.
- **summarize** writes a daily rollup + one-line per-item summaries (Claude
  Sonnet, with a first-sentence fallback). Summaries are original paraphrase.
- **digest** renders one self-contained HTML page → `docs/index.html`, archived by
  date, and reused as the email body.

---

## Quick start

```bash
git clone <your-repo> && cd littleton-agent
pip install -r requirements.txt

# Smoke-test the whole pipeline offline (no secrets, no network):
python run.py --sample
open docs/index.html

# A real run (uses whatever secrets are set; degrades gracefully without them):
python run.py
```

### Make it autonomous

1. Push this repo to GitHub.
2. **Settings → Pages → Source: GitHub Actions.**
3. Add secrets/vars (**Settings → Secrets and variables → Actions**):

   | name | type | purpose |
   |---|---|---|
   | `ANTHROPIC_API_KEY` | secret | LLM classify + summarize (optional but recommended) |
   | `IMAP_USER` / `IMAP_PASSWORD` | secret | the mailbox the agent **reads** (Gmail app password) |
   | `SMTP_USER` / `SMTP_PASSWORD` | secret | the account that **sends** the digest |
   | `EMAIL_ENABLED` | variable | `true` to send email |
   | `DIGEST_TO` | variable | recipient(s), comma-separated |
   | `SITE_BASE_URL` | variable | your Pages URL, for archive links |

4. The workflow (`.github/workflows/digest.yml`) runs daily at 11:00 UTC
   (≈6–7am ET) and on demand via the Actions tab.

### The inbox is the town's main pipe

Because `littletonma.org` blocks automated fetching, the highest-signal town
content comes by **email push**, not scraping:

1. Create a dedicated Gmail (e.g. `littleton.signal@gmail.com`).
2. On the town site, **Notify Me** → subscribe to Agendas, Calendars, all News
   Flash categories, Bids, Jobs; and sign up for **CivicReady** alerts.
3. Forward anything from the human-only tiers (the "What's going on?" Facebook
   group, Nextdoor) into that inbox.
4. Set `IMAP_USER`/`IMAP_PASSWORD` to it. The `inbox` adapter reads unseen mail.

---

## Configuring sources

Everything is in `sources.yaml`. To add a feed: copy a block, set `kind: rss`,
point `url` at the feed, set a `weight`. To tune what's "important," edit
`relevance_profile.high` / `.medium`. To change how inclusive the digest is, move
`defaults.relevance_threshold` (lower = more items).

Sources marked `enabled: false` are either waiting on a value (the CivicPlus RSS
`ModID`/`CID`, copied from `littletonma.org/rss.aspx` in a browser) or are
`kind: manual` (human-forward only).

---

## Phase 2 — what's next

- **Warrant / agenda PDFs**: `adapters/pdf_docs.py` already extracts text; Phase 2
  adds discovery of which PDFs to pull from the Document Portal + Agenda Center.
- **MEPA Environmental Monitor**: scrape EEA filings (King Street Common = EEA
  #16921) for comment deadlines.
- **CivicPlus RSS**: fill the `ModID`/`CID` values, or keep leaning on the inbox.
- **Weekly digest mode** + a Monday open-threads review.
- **Calendar push**: write extracted deadlines/votes to Google Calendar.

---

## Notes

- Runs with zero secrets (LLM + email degrade to fallbacks). Add the API key first
  for materially better classification and summaries.
- `state/seen.json` and `state/health.json` are committed back each run; the health
  file flags any source that goes quiet several runs in a row (local-gov sites
  change layouts without warning).
- Respect source terms: the `manual` tier exists precisely because Facebook groups
  and Nextdoor can't be scraped within their terms.
