# Littleton, MA — Local Intelligence Source Registry

A complete inventory of sources for the autonomous Littleton-news agent, organized by tier and tagged with the ingestion method each source supports. This is the working draft of what becomes the agent's `sources.yaml`.

## Ingestion legend

- **[PUSH]** — email/text via the town's Notify Me or CivicReady systems (read from a dedicated inbox; the most reliable route)
- **[RSS]** — RSS/Atom feed
- **[iCAL]** — calendar export (iCal/ICS)
- **[YT-RSS]** — YouTube channel RSS (with auto-caption transcripts)
- **[SUBSTACK]** — Substack RSS
- **[SCRAPE]** — HTML page, monitored via change-detection
- **[PDF]** — PDF document, extracted on change
- **[STATE-ALERT]** — subscription/alert on a state government tool
- **[MANUAL]** — human-forward only (ToS or access constraints; you skim and forward to the inbox)

> **Design note:** The CivicPlus town site blocks automated fetching at the robots level. Email push (Notify Me + CivicReady) is therefore the primary ingestion path for everything town-related; RSS/iCal are the backup; page-scraping is last resort.

---

## Tier 1 — Town of Littleton (CivicPlus backbone)

`littletonma.org` and `ma-littleton.civicplus.com` are the same site (public name vs. host).

- **Notify Me** — subscribe a dedicated inbox to: Agendas, Calendars, News Flash (all categories), Bid Postings, Job Opportunities, department alerts. **[PUSH]** — *primary route*
- **CivicReady** — emergency / public-safety alerts (separate system). **[PUSH]**
- **News Flash — Town News & Announcements** (`CivicAlerts.aspx?CID=1`) **[PUSH][RSS]**
- **News Flash — Littleton Spotlights** **[PUSH][RSS]**
- **News Flash — Town Clerk News** **[PUSH][RSS]**
- **News Flash — Parks & Rec Spotlight** **[PUSH][RSS]**
- **Meeting Calendar** (`/calendar.aspx`) — the event spine **[iCAL][RSS]**
- **Agenda Center** (`/AgendaCenter`) — per-board agendas & minutes **[PUSH][RSS]**
- **Monthly Town Newsletter** (`/1212`) — PDF archive **[PDF]**
- **Document Management Public Portal** (via `/880/Town-Meetings`) — Town Meeting warrants, reports, minutes archive (searchable) **[SCRAPE][PDF]**
- **Town Clerk / Elections** (`/1418/Elections---2026`) — warrants, ballot questions, election dates, results **[PUSH][SCRAPE]**

**Feed mechanics (resolved):**
- All RSS feeds are catalogued at **`littletonma.org/rss.aspx`** — the authoritative hub listing every News Flash category, the Calendar, and Agenda Center feeds.
- CivicEngage feed-URL form: `RSSFeed.aspx?ModID=<module>&CID=<category>`. The exact `ModID`/`CID` pairs must be copied off `rss.aspx` in a browser (the site's robots rule blocks automated reads of it — a ~2-minute build step). *You don't strictly need them: Notify Me email push carries the same content and is the recommended path.*
- Agenda/minutes file URLs follow a fixed pattern, e.g. `/AgendaCenter/ViewFile/Agenda/_MMDDYYYY-<id>` and `/AgendaCenter/ViewFile/Minutes/_MMDDYYYY-<id>` — useful for the PDF adapter.

---

## Tier 2 — Boards & committees (relevance weights)

All flow through Tier 1's Agenda Center + Calendar. Weight these **high** in the relevance profile:

- Select Board
- Planning Board (development, special permits)
- Conservation Commission (wetlands, open space)
- Finance Committee
- School Committee (+ subcommittees)
- Zoning Board of Appeals
- Community Preservation Committee
- Charter Committee (charter review — active)
- Permanent Municipal Building Committee
- Shaker Lane Building Committee (school project)
- Sustainability Committee
- Clean Lakes Committee

Weight **standard**: Board of Assessors, Board of Health, Historical Commission, Housing Authority, Council on Aging, Transportation Advisory Council, Affordable Housing Trust, Personnel Advisory Committee, Trust Fund Commission, Light & Water Commissioners (see Tier 4), DPW–Complete Streets.

---

## Tier 3 — Schools

- **Littleton Public Schools** — `littletonps.org`; runs on Campus Suite (separate CMS from the town's CivicPlus). District news stream: **`littletonps.org/about-our-district/district-news`** **[SCRAPE]** (check for Campus Suite RSS at build)
- **School Committee** — town page `/728` + `littletonps.org/school-committee`; recaps via Sean Aherne below **[PUSH][RSS]**
- **SEPAC** (Special Education Parent Advisory Council) — `littletonmasepac.org` **[SCRAPE]**
- **PTO Presidents Council** — `littletonpublicschools.net/pto-presidents-council-ppc` **[SCRAPE]**
- **Nashoba Valley Technical High School** (Westford; Littleton is a member town — budget/assessment impact) **[SCRAPE]**
- **Sean Aherne — "Sean for Littleton"** — `seanforlittleton.com` (School Committee member, term to 2028; his Substack with meeting recaps + the podcast are linked here) **[SUBSTACK][SCRAPE]** ← high-value citizen source
- **"Paws on Littleton Public Schools" podcast** — page on `littletonps.org/school-committee`; audio via LCTV (see Tier 6) **[YT-RSS][SCRAPE]**

---

## Tier 4 — Utility & independent town bodies

- **Littleton Electric Light & Water Departments (LELWD)** — `lelwd.com` — outages, rate changes, Green Rewards / EV / solar programs; elected commissioners meet monthly **[SCRAPE]** (+ commission meetings via Tier 1)
- **Reuben Hoar Library** — events, board, Houghton Historical Room, Genealogy Club **[SCRAPE]** (+ via Tier 1)
- **Littleton Housing Authority** — affordable-housing decisions (meets at the library) **[PUSH]** (via Tier 1)

---

## Tier 5 — Local news & citizen media

- **Patch — Littleton** (`patch.com/massachusetts/littleton-ma`) + **Patch AM** newsletter — aggregates town calendar + local items **[RSS][PUSH]**
- **Wicked Local / Eagle-Independent** (Gannett; `littleton@wickedlocal.com`) — thin coverage, catch what runs **[SCRAPE]**
- **Lowell Sun / Nashoba Valley Voice** — Littleton tag, regional stories **[RSS][SCRAPE]**
- **"Sean for Littleton"** (`seanforlittleton.com`) — (cross-ref Tier 3) **[SUBSTACK]**
- *Context only (not an ongoing feed):* Jenna Brownson (`jennabrownson.substack.com`, *GINNED UP*) — local political/police history
- *Skip:* NewsBreak (auto-aggregated, low signal)

---

## Tier 6 — Video (what was actually said)

- **LCTV YouTube channel** — meeting broadcasts + auto-caption transcripts. Channel ID `UC0zDRpamgVdB71XZsDd72_g`; feed: **`youtube.com/feeds/videos.xml?channel_id=UC0zDRpamgVdB71XZsDd72_g`** **[YT-RSS]** ← best video source
- **LCTV Castus VOD** (`littleton.vod.castus.tv`) **[SCRAPE]**
- **LCTV Facebook** (`/LittletonCommunityTV`) **[MANUAL]**
- **"01460 On The Go"** (LCTV conservation show) — via the YouTube channel **[YT-RSS]**

---

## Tier 7 — Official town social accounts

Enumerated on the town's "Social Media Links for Town Departments" post (`CivicAlerts.aspx?AID=17`).

- **Town of Littleton** — Facebook `/LittletonMA`, X `@TownofLittleton` **[MANUAL]**
- **Littleton Police** — Facebook `/LittletonMAPD` (most active town account, ~10.7k) **[MANUAL]**
- **Fire, Parks & Rec, Library**, and others per the AID=17 listing **[MANUAL]**

> Facebook Pages and X are increasingly login-walled for automated reading. Treat as best-effort; the town/PD usually cross-post to News Flash anyway.

---

## Tier 8 — Community discussion & social

### Reddit — automatable [RSS]

Reddit's `.rss` endpoints still work without an API key (which is impractical to obtain in 2026). "Littleton" alone is noisy — Littleton CO and NH dominate — so queries force MA context and the classifier drops the rest.

- Site-wide search: `https://www.reddit.com/search.rss?q=%22Littleton+MA%22+OR+%22Littleton+Massachusetts%22&sort=new` **[RSS]**
- Within r/massachusetts: `https://www.reddit.com/r/massachusetts/search.rss?q=Littleton&restrict_sr=on&sort=new&t=week` **[RSS]**
- Within r/boston (regional spillover): same pattern **[RSS]**
- At build, check for a live local sub (r/LittletonMA, r/MetroWest, r/Nashoba) and add its `/new/.rss` if active **[RSS]**
- Send a descriptive User-Agent and keep the cron modest to avoid rate-limit blocks. Relevance step requires a Massachusetts signal (MA / Massachusetts / a known Littleton place-name) to filter out the other Littletons.

### Facebook groups & Nextdoor — human-forward [MANUAL]

Meta closed group content to third-party tools, and scraping logged-in Facebook breaks its terms and triggers account blocks; private groups are fully sealed. These stay human-in-the-loop: you skim and forward notable posts to the agent's inbox.

- **"Littleton MA – What's going on?"** — `facebook.com/groups/littletonwhatsgoingon/` (likely private) **[MANUAL]**
- **Nextdoor — Littleton, MA** — `nextdoor.com/city/littleton--ma/` (distinct from Littleton CO). Neighborhood sub-areas include Fort Pond Association, Bumblebee Park, Forge Pond, Hartwell Ave, Nagog/Nashoba, Taylor Street. Top resident topics: gardening/landscape, home improvement/DIY, trails, local issues. Address-verified + heavily anti-automation. **[MANUAL]**
- **Buy Nothing Littleton, MA** (Facebook gift-economy group) — low news value, high neighbor activity **[MANUAL]**
- **Littleton Garden Club** Facebook (`/littletongarden.club`) **[MANUAL]**
- Any other resident / community Facebook groups you belong to **[MANUAL]**

> Much of these groups' hard news (closures, town announcements, school updates) already arrives via the town feeds, Patch, and the Police Facebook cross-posts. Their unique value is resident sentiment and chatter — the part that genuinely needs a human glance.

---

## Tier 9 — Civic, conservation & advocacy orgs

- **Littleton Conservation Trust** — `littletonconservationtrust.org` — trails, land stewardship, work parties, news **[SCRAPE]**
- **Sudbury Valley Trustees** — `svtweb.org` — owns Smith Conservation Land in Littleton; High-region land protection **[SCRAPE]**
- **New England Forestry Foundation** — owns Prouty Woods Community Forest **[SCRAPE]**
- **Littleton Historical Society** — `littletonhistoricalsociety.org` + Facebook (partner to the town Historical Commission) **[SCRAPE]**
- **Littleton Country Gardeners / Garden Club** **[MANUAL]**
- **Littleton Rotary Club**, **Littleton Lions Club** **[MANUAL]**
- **Indian Hill Music Center**, **Littleton Lyceum** — cultural **[SCRAPE]**
- **Littleton 250th Anniversary** — `littleton250th.com` — semiquincentennial events through 2026 **[SCRAPE]** ← active thread
- **Veterans:** American Legion Post 249, VFW Post 6556 (the Depot) **[MANUAL]**

---

## Tier 10 — State & regional (for the big projects)

These give date-stamped advance notice with hard comment/vote deadlines.

- **MEPA Environmental Monitor** (MA EEA) — development filings + comment deadlines; **King Street Common = EEA #16921** (Lupoli mixed-use). Published twice monthly **[STATE-ALERT][SCRAPE]**
- **MA DPH** — UMass Memorial Satellite Emergency Facility application **[SCRAPE]**
- **malegislature.gov — MyLegislature** — follow Littleton's delegation + specific bills/hearings with email alerts **[STATE-ALERT]**
  - **State Rep: James "Jim" Arciero** (D, 2nd Middlesex — Westford/Littleton/Chelmsford; House Chair, Transportation) — `malegislature.gov/Legislators/Profile/J_A1` · `repjamesarciero.com`
  - **State Senator: James "Jamie" Eldridge** (D, Middlesex & Worcester; Senate Chair, Revenue) — `malegislature.gov/Legislators/Profile/JBE0` · `senatoreldridge.com` (has a newsletter)
- **Secretary of the Commonwealth — electionstats** (`electionstats.state.ma.us`) — official results **[SCRAPE]**

---

## Live threads to pre-seed the relevance profile

Weight items mentioning these **up**:

- Shaker Lane school project + debt-exclusion override
- King Street Common (Lupoli, 550 King St / 410 Great Rd, EEA #16921)
- Bluebird Farm open-space development (359 King St)
- Charter Committee review
- UMass Memorial Satellite Emergency Facility
- Transfer-station fees & regulations
- Clean Lakes / Beaver Brook conservation
- Superintendent transition — Kelly Clenchy retiring; **Dr. Caira** appointed, effective July 1, 2026
- 250th anniversary events
- Rail trail / conservation land, Planning Board development decisions (your standing interests)

---

## Confirm-list — status

1. **State delegation** — ✅ **Resolved.** Rep. Jim Arciero + Sen. Jamie Eldridge (see Tier 10), both with `malegislature.gov` profiles for bill-following.
2. **Community groups** — ✅ **Resolved.** "What's going on?" FB group + Nextdoor Littleton MA + Buy Nothing + Garden Club (see Tier 8); all human-forward. Add any private groups you personally belong to.
3. **CivicPlus feed endpoints** — ◑ **Resolved as far as possible without a browser.** Feeds live at `littletonma.org/rss.aspx`; the form is `RSSFeed.aspx?ModID=&CID=`; the Agenda/Minutes file pattern is confirmed (see Tier 1). The one keyboard step left: open `rss.aspx` in a browser and copy the exact `ModID`/`CID` strings, *which you can skip entirely by using Notify Me email push.*
4. **LCTV YouTube channel** — ✅ **Resolved.** Channel ID `UC0zDRpamgVdB71XZsDd72_g` → `youtube.com/feeds/videos.xml?channel_id=UC0zDRpamgVdB71XZsDd72_g` (see Tier 6).
5. **Citizen newsletters/Substacks** — ✅ **Resolved.** `seanforlittleton.com` (Sean Aherne) is the standout; the citizen-media layer is concentrated there rather than spread across many blogs. Add any personal subscriptions that wouldn't surface in search.

**Net:** one optional, ~2-minute browser step remains (item 3), and it's bypassable. Everything else is locked.
