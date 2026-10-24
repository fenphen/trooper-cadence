# 🎺 Trooper Cadence

A retro-arcade marching-band rhythm game in a single self-contained HTML file.
Inspired by the Western-cavalry drill-corps look (sand, crimson & gold).

**▶ Play it:** https://fenphen.github.io/trooper-cadence/

## How to play
- Crimson beat markers march in from the right toward the gold line.
- **◄ Left foot** / **► Right foot** — tap each marker in time as it crosses the line.
- Alternate left/right to hold the cadence and build your combo.
- Every 20-combo triggers the **Sunburst** payoff. Don't let **Corps Morale** hit zero.
- **Space / tap** to start & restart · **M** to mute · on phones use the on-screen **L / R** pads.

No build step, no dependencies — just open `index.html` in any browser.

*Fan tribute to the marching-arts aesthetic. Not affiliated with any organization.*

---

# 🐾 Toasty & Sonny's Big Adventure

A **family dog-care and training game** for two dogs. Everyone in the house earns points for caring for the pups (brushing, a timed 2‑minute belly rub, walks, teeth, fresh water…) and for training them, and the family's points move Toasty and Sonny along an adventure trail from the backyard to the Summit.

**▶ Play it:** https://fenphen.github.io/trooper-cadence/bigadventure/

- **Daily training quest per dog:** three exercises picked each day from a 16‑skill tree (name game, sit, down, stay, come, leave it, drop it, place, loose‑leash walking, tricks…), each with **sets × reps**, a treat count and a plain‑English how‑to. Reps grow as the dog levels up; new skills unlock as the basics get solid.
- **Care & love checklist** with points, per‑day limits and timers for belly rubs and play.
- **Gamified:** levels per skill, quest bonuses, family and personal streaks, 18 badges, a weekly and all‑time family leaderboard and a 13‑stop adventure trail.
- **Family sync:** optional, free Firebase Realtime Database so all four phones share one game (instructions in Settings). Without it each phone keeps its own scores; backups can be exported and merged.
- Works on iPhone and Android as a home‑screen app (PWA), offline once installed.

File: `bigadventure/index.html` (self‑contained, no build step).

---

# 🔎 Mention Finder

A second, separate tool in this repo: find **recent Reddit posts and comments that mention a name, place or website**, however people spelled it.

**▶ Use it:** https://fenphen.github.io/trooper-cadence/mention-finder/

- Type `bestbuy.com` and it also searches `bestbuy`, `bestbuy dot com`, and common misspellings like `bsetbuy`. It also spots near-misses in results, like "Best Buy" and "bestbyu".
- **🎤 Voice search:** tap the mic and say something like "best buy dot com and price match but not refund" or "chewy or petco". Spoken "and", "or", "but not", "without" and "quote … end quote" become search operators. You can also dictate the report summary and notes. Works in Chrome, Edge and Safari (including phones); the mic is hidden in browsers without speech support, such as Firefox.
- Combine searches with **AND**, **OR** and **NOT**, or tap the buttons: `bestbuy.com AND "price match" NOT refund`, `chewy OR petco`, `amazon -prime`.
- Searches **all of Reddit's history by default** ("any time"), or narrow it to the past hour, day, week, month or year. **Load older results** keeps paging back in time. Sort by newest, oldest first or most upvoted, limit to a subreddit, and switch on auto-refresh (every 3 min, with new results marked).
- Tap a username to see the account's age and karma. Brand-new accounts are highlighted.
- **⚑ Flag** anything inappropriate. Then **Review & export** to add notes and a summary, and export as a printable report / PDF, CSV, JSON, or text to paste into a report form. Each item includes its permalink, UTC times, capture time and a SHA-256 fingerprint. The panel links to Reddit's reporting, NCMEC CyberTipline, FBI tips, IC3 and FTC.
- **Copy share link** saves the whole search, including extra spellings you added, in the URL.

**Phase 1 (now):** since late May 2026, Reddit refuses anonymous data requests from other websites, so the page doesn't try. Instead it:
- leads with one-tap buttons that run your exact search (every spelling, AND/NOT) on Reddit's own site (posts and comments) and on Google;
- shows archive matches in the page when it can: posts linking to a website, anywhere on Reddit, from [Arctic Shift](https://arctic-shift.photon-reddit.com/). Enter a subreddit in "In r/" for full keyword search of posts and comments there. Comments also come from [PullPush](https://pullpush.io) when it's up. Archives can be days behind.

**Phase 2:** live results inside the page, through the small server in [`server/`](server/README.md), which uses Reddit's official API. Setting it up takes a Reddit-approved API app and a free Cloudflare account; follow [`server/README.md`](server/README.md), then put the server's address in `mention-finder/config.js`.
Files: `mention-finder/index.html` (page), `mention-finder/variants.js` (spelling and query engine), `mention-finder/report.js` (exports).

---

# 📈 Signal Watch

A **learning dashboard** for four stocks of your choice (NVIDIA, Tesla, Apple and SpaceX by default). Nothing is bought or sold.

**▶ Open it:** https://fenphen.github.io/trooper-cadence/stocks/

- Each tile shows the latest price, including **pre‑market and after‑hours** trades, with a tag for the session and the change from the regular close. Prices refresh every minute.
- A **green BUY / red SELL / amber HOLD** badge, computed the way technical traders do: five textbook indicators (trend vs. 50/200‑bar averages, MACD, RSI, Bollinger Bands, golden/death cross) each vote, and the score decides.
- **Hover or tap the price** for the full readout: every indicator's value and a plain‑English line on what a technical trader would be thinking about it.
- **1h / 2h / 4h / 1D** buttons change the time frame for the chart and the signal. **Show chart** opens price with SMA 20/50/200 and Bollinger Bands, an RSI panel and a MACD panel, with a crosshair tooltip and a table view.
- Tap **✎** on a tile to swap in another stock: pick from two dozen popular names or search by ticker or company name.
- The SpaceX tile uses the ticker **SPCX**; if the feed has no data for it, the tile says so.
- Prices come from free public feeds straight from the browser (Yahoo Finance via a relay, then Stooq for daily bars); it falls back to data saved on the device, then to clearly labelled sample data. Add a free Twelve Data key under **Data settings** for a steadier feed.

File: `stocks/index.html` (self‑contained, no build step).

---

# 🖨️ Home Hub

A **printer, scanner and network status page for the house**, served from an always-on Windows PC
and bookmarked on every other computer and phone. Finds the HP printers by itself, shows status and
ink levels, wakes them, prints a test page or any PDF/image, scans to PDF from the browser, lists every
device on the LAN, and (optionally) reads the TP-Link Deco mesh.

Setup and details: [`homehub/README.md`](homehub/README.md). It runs on your LAN, not on GitHub Pages.
