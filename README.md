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

# 🔎 Mention Finder

A second, separate tool in this repo: find **recent Reddit posts and comments that mention a name, place or website**, however people spelled it.

**▶ Use it:** https://fenphen.github.io/trooper-cadence/mention-finder/

- Type `bestbuy.com` and it also searches `bestbuy`, `bestbuy dot com`, and common misspellings like `bsetbuy`. It also spots near-misses in results, like "Best Buy" and "bestbyu".
- **🎤 Voice search:** tap the mic and say something like "best buy dot com and price match but not refund" or "chewy or petco". Spoken "and", "or", "but not", "without" and "quote … end quote" become search operators. You can also dictate the report summary and notes. Works in Chrome, Edge and Safari (including phones); the mic is hidden in browsers without speech support, such as Firefox.
- Combine searches with **AND**, **OR** and **NOT**, or tap the buttons: `bestbuy.com AND "price match" NOT refund`, `chewy OR petco`, `amazon -prime`.
- Sort by newest or most upvoted, limit to a subreddit, and switch on auto-refresh (every 3 min, with new results marked).
- Tap a username to see the account's age and karma. Brand-new accounts are highlighted.
- **⚑ Flag** anything inappropriate. Then **Review & export** to add notes and a summary, and export as a printable report / PDF, CSV, JSON, or text to paste into a report form. Each item includes its permalink, UTC times, capture time and a SHA-256 fingerprint. The panel links to Reddit's reporting, NCMEC CyberTipline, FBI tips, IC3 and FTC.
- **Copy share link** saves the whole search, including extra spellings you added, in the URL.

**Phase 1 (now):** since late May 2026, Reddit refuses anonymous data requests from other websites, so the page doesn't try. Instead it:
- leads with one-tap buttons that run your exact search (every spelling, AND/NOT) on Reddit's own site (posts and comments) and on Google;
- shows archive matches in the page when it can: posts linking to a website, anywhere on Reddit, from [Arctic Shift](https://arctic-shift.photon-reddit.com/). Enter a subreddit in "In r/" for full keyword search of posts and comments there. Comments also come from [PullPush](https://pullpush.io) when it's up. Archives can be days behind.

**Phase 2:** live results inside the page, through the small server in [`server/`](server/README.md), which uses Reddit's official API. Setting it up takes a Reddit-approved API app and a free Cloudflare account; follow [`server/README.md`](server/README.md), then put the server's address in `mention-finder/config.js`.
Files: `mention-finder/index.html` (page), `mention-finder/variants.js` (spelling and query engine), `mention-finder/report.js` (exports).
