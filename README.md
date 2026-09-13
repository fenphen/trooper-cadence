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

# 🏠 Homefront HQ

`homefront.html` — a second, unrelated game in the same repo: a **tiny-task decluttering
game for a real house**. Phone-first, no accounts, no server.

Once this branch is on the Pages branch it serves at `…/trooper-cadence/homefront.html`.

## The idea
Decluttering stalls because every job sounds like a whole weekend. So nothing here is
bigger than one sitting — "the junk drawer", "shelf 1 of the garage", "pull ten things
you haven't worn in a year". **298 tasks across 18 zones**, each worth points.

## How it works
- **Give me one thing** — say how long you've got (5 / 15 / 30 / all-in) and it picks a
  job for you, weighted toward the messiest zones, the boss zone, and things slipping
  past their cadence. Decision fatigue is the actual enemy.
- **Today's work order** — three picks a day: one quick, one declutter, one upkeep.
- **Two kinds of task.** *One & done* declutter jobs stay done and fill the zone's
  progress bar. *Upkeep* jobs (laundry, dog nails, gutters) come back on their own
  cadence and show up under **Falling behind** when they slip.
- **Ranks & medals** — 20 ranks from Recruit to Keeper of the Clear Floor, 22 medals,
  daily streaks, and bonuses for the first task of the day and for stringing several together.
- **Zones**: the garage (boss zone, 1.4× points), six rooms upstairs, three down,
  two cars, two dogs, outside & house systems, laundry and a daily reset.
- **Two players** — everyone on one phone shares the house progress but keeps their own
  points, rank and streak; there's a weekly scoreboard. Open the page on a second phone
  and that player gets a fresh house of their own.
- **Rename everything** — dogs, cars, kids' rooms, any zone. Add your own tasks per zone.
- **Backup / restore** via a copy-paste code, for moving to another phone.

Progress lives in `localStorage` on the device. No build step, no dependencies.
