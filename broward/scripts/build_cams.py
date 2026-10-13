#!/usr/bin/env python3
"""Build broward/data/cams.json: FDOT/FL511 traffic cameras in Broward + the curated list.

Runs nightly in GitHub Actions (see .github/workflows/broward-data.yml). Standard library only.

Sources, in order:
  1. fl511.com list JSON (undocumented, what the FL511 site itself uses), paged 100 at a time.
  2. Fallback: the public ArcGIS "FL511_Traffic_Cameras" layer, filtered to Broward.
  3. If both fail or return suspiciously few cameras, keep the FDOT cameras already in cams.json.
Snapshots are hot-linked from https://fl511.com/map/Cctv/<imageId> (FL511 caches ~1 min). Live
video needs a token flow that a static site cannot do, so each camera links to FL511's own player.

Usage:
  python build_cams.py                 # normal nightly build
  python build_cams.py --seed FILE     # import FDOT cams from a packed fl-traffic cameras.json
  python build_cams.py --offline       # skip all network (merge manual cams with existing FDOT)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
OUT = DATA / "cams.json"
MANUAL = DATA / "manual_cams.json"
BOUNDARIES = DATA / "cities.geojson"   # optional (phase 2); used to assign a city to each camera

UA = "BrowardLive/0.1 (+https://github.com/fenphen/trooper-cadence; hobby map, nightly list only)"
MIN_FDOT = 350          # fewer than this means the feed broke; keep yesterday's list
BBOX = (-80.95, 25.94, -80.03, 26.36)   # lon_min, lat_min, lon_max, lat_max (Broward with margin)
FL511_LIST = "https://fl511.com/List/GetData/Cameras"
FL511_ICONS = "https://fl511.com/map/mapIcons/Cameras"
ARCGIS = ("https://services.arcgis.com/3wFbqsFPLeKqOlIK/arcgis/rest/services/FL511_Traffic_Cameras/FeatureServer/0/query"
          "?where=COUNTY%3D%27Broward%27&outFields=*&outSR=4326&f=json&resultRecordCount=2000")

DIRS = {"N": "Northbound", "S": "Southbound", "E": "Eastbound", "W": "Westbound", "NB": "Northbound", "SB": "Southbound",
        "EB": "Eastbound", "WB": "Westbound"}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def get(url: str, timeout: int = 30, headers: dict | None = None) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json,text/html;q=0.9,*/*;q=0.8", **(headers or {})})
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read()
                if body[:2] == b"\x1f\x8b":
                    import gzip
                    body = gzip.decompress(body)
                return body
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"GET {url}: {last}")


def in_bbox(lat: float, lon: float) -> bool:
    return BBOX[1] <= lat <= BBOX[3] and BBOX[0] <= lon <= BBOX[2]


def nice_direction(d: str | None) -> str:
    if not d:
        return ""
    d = d.strip()
    return DIRS.get(d.upper(), d)


def strip_html(s: str | None) -> str:
    return re.sub(r"<[^>]+>", "", s or "").strip()


# ---------------------------------------------------------------- FL511

def fl511_query(start: int) -> str:
    q = {"columns": [{"data": None, "name": ""}, {"name": "sortOrder", "s": True}, {"name": "region", "s": True},
                     {"name": "county", "s": True}, {"name": "roadway", "s": True}, {"name": "location", "s": True},
                     {"name": "direction", "s": True}, {"data": 7, "name": ""}],
         "order": [{"column": 1, "dir": "asc"}], "start": start, "length": 100, "search": {"value": ""}}
    return FL511_LIST + "?query=" + urllib.parse.quote(json.dumps(q, separators=(",", ":"))) + "&lang=en"


def fetch_fl511() -> list[dict]:
    rows: dict[int, dict] = {}
    start, total = 0, None
    while total is None or start < total:
        data = json.loads(get(fl511_query(start), headers={"X-Requested-With": "XMLHttpRequest"}))
        total = int(data.get("recordsTotal") or 0)
        for r in data.get("data", []):
            try:
                rows[int(r["id"])] = r
            except (KeyError, ValueError, TypeError):
                continue
        if not data.get("data"):
            break
        start += 100
        time.sleep(0.25)
    log(f"FL511 list: {len(rows)} rows statewide (recordsTotal={total})")
    icons: dict[int, tuple[float, float]] = {}
    try:
        for it in json.loads(get(FL511_ICONS)).get("item2", []):
            try:
                icons[int(it["itemId"])] = (float(it["location"][0]), float(it["location"][1]))
            except (KeyError, ValueError, TypeError, IndexError):
                pass
    except Exception as e:  # noqa: BLE001
        log("FL511 icons layer unavailable:", e)
    out = []
    for sid, r in rows.items():
        county = strip_html(r.get("county"))
        latlon = icons.get(sid)
        if not latlon:
            m = re.search(r"POINT \(([-\d.]+) ([-\d.]+)\)", ((r.get("latLng") or {}).get("geography") or {}).get("wellKnownText", ""))
            if m:
                latlon = (float(m.group(2)), float(m.group(1)))
        if not latlon:
            continue
        lat, lon = latlon
        if county != "Broward" and not (not county and in_bbox(lat, lon)):
            continue
        images = [im for im in (r.get("images") or []) if not im.get("disabled") and not im.get("blocked")]
        if not images:
            continue
        im = images[0]
        out.append(make_fdot(sid, int(im.get("id") or sid), lat, lon, strip_html(r.get("roadway")), nice_direction(strip_html(r.get("direction"))),
                             strip_html(r.get("location")), bool((im.get("videoUrl") or "").strip()), strip_html(r.get("city")) or None))
    return out


def fetch_arcgis() -> list[dict]:
    feats = json.loads(get(ARCGIS)).get("features", [])
    out, seen = [], set()
    for f in feats:
        a = f.get("attributes") or {}
        img = a.get("IMAGE") or ""
        if img in seen:
            continue
        seen.add(img)
        try:
            lat, lon = float(a["LATITUDE"]), float(a["LONGITUDE"])
        except (KeyError, ValueError, TypeError):
            continue
        sid = a.get("ID")
        out.append({"id": f"fdot-{sid}", "name": f"{a.get('HIGHWAY') or ''} {nice_direction(a.get('DIRECTION'))}: {a.get('DESCRIPT') or ''}".strip(),
                    "operator": "FDOT / FL511", "city": None, "lat": round(lat, 5), "lon": round(lon, 5), "type": "traffic", "kind": "image",
                    "src": img, "refresh": 20, "page": f"https://fl511.com/map#camera-{sid}", "road": a.get("HIGHWAY"), "has_feed": True})
    log(f"ArcGIS layer: {len(out)} Broward cameras")
    return out


def make_fdot(sid: int, image_id: int, lat: float, lon: float, road: str, direction: str, location: str, has_feed: bool, city: str | None) -> dict:
    loc = location
    # FL511 location strings like "75-0.41-SB" or "0517N_75_Alligator_Alley_M052" are internal codes
    if re.fullmatch(r"[\d.]+-[\d.]+-[NSEW]B?", loc) or "_" in loc:
        mm = re.search(r"-([\d.]+)-", loc) or re.search(r"M(\d+)", loc)
        loc = f"mile marker {mm.group(1)}" if mm else loc
    name = f"{road} {direction}".strip()
    if loc and loc.lower() != name.lower():
        name = f"{name}: {loc}" if name else loc
    return {"id": f"fdot-{sid}", "name": name, "operator": "FDOT / FL511", "city": city, "lat": round(lat, 5), "lon": round(lon, 5),
            "type": "traffic", "kind": "image", "src": f"https://fl511.com/map/Cctv/{image_id}", "refresh": 20,
            "page": f"https://fl511.com/map#camera-{sid}", "road": road, "has_feed": has_feed}


def seed_from_packed(path: Path) -> list[dict]:
    """Import from the fl-traffic project's packed cameras.json (used once to bootstrap)."""
    d = json.loads(path.read_text("utf-8"))
    roads, counties, nofeed = d["roads"], d["counties"], set(d.get("noFeed") or [])
    bi = counties.index("Broward")
    out = []
    for row in d["cameras"]:
        sid, lon, lat, ri, direction, loc, ci = row[:7]
        if ci != bi:
            continue
        images = row[7] if len(row) > 7 else [sid]
        out.append(make_fdot(sid, images[0], lat, lon, roads[ri], nice_direction(direction), loc, images[0] not in nofeed, None))
    log(f"seeded {len(out)} Broward FDOT cameras from {path.name} (generated {d.get('generated')})")
    return out


# ---------------------------------------------------------------- city assignment (point in polygon, no dependencies)

def point_in_ring(lon: float, lat: float, ring: list) -> bool:
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def point_in_geom(lon: float, lat: float, geom: dict) -> bool:
    t, c = geom.get("type"), geom.get("coordinates") or []
    polys = c if t == "MultiPolygon" else [c] if t == "Polygon" else []
    for poly in polys:
        if poly and point_in_ring(lon, lat, poly[0]) and not any(point_in_ring(lon, lat, hole) for hole in poly[1:]):
            return True
    return False


def assign_cities(cams: list[dict]) -> None:
    if not BOUNDARIES.exists():
        return
    gj = json.loads(BOUNDARIES.read_text("utf-8"))
    feats = []
    for f in gj.get("features", []):
        props = f.get("properties") or {}
        name = props.get("name") or props.get("NAME") or props.get("CITY") or props.get("MUNICIPALITY")
        if name and f.get("geometry"):
            feats.append((name, f["geometry"]))
    n = 0
    for c in cams:
        if c.get("city"):
            continue
        for name, geom in feats:
            if point_in_geom(c["lon"], c["lat"], geom):
                c["city"] = name
                n += 1
                break
        else:
            c["city"] = "Unincorporated Broward"
    log(f"assigned a city to {n} cameras from {BOUNDARIES.name}")


# ---------------------------------------------------------------- YouTube live id refresh

def refresh_youtube(cams: list[dict], offline: bool) -> None:
    for c in cams:
        page = c.get("youtube_live_page")
        if not page or offline or c.get("kind") != "youtube":
            continue
        try:
            html = get(page, timeout=20, headers={"Accept-Language": "en-US,en;q=0.8"}).decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            log(f"youtube live page failed for {c['name']}: {e}")
            continue
        m = re.search(r'<link rel="canonical" href="https://www\.youtube\.com/watch\?v=([A-Za-z0-9_-]{11})"', html)
        if m and '"isLive":true' in html or (m and "isLiveNow" in html):
            if c.get("src") != m.group(1):
                log(f"{c['name']}: live id {c.get('src')} -> {m.group(1)}")
                c["src"] = m.group(1)
        time.sleep(0.5)


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed")
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    previous = json.loads(OUT.read_text("utf-8")) if OUT.exists() else {"cams": []}
    prev_fdot = [c for c in previous.get("cams", []) if c.get("operator") == "FDOT / FL511"]
    source = "previous"
    fdot: list[dict] = prev_fdot
    if args.seed:
        fdot, source = seed_from_packed(Path(args.seed)), "seed"
    elif not args.offline:
        try:
            fdot, source = fetch_fl511(), "fl511"
        except Exception as e:  # noqa: BLE001
            log("FL511 failed:", e)
            try:
                fdot, source = fetch_arcgis(), "arcgis"
            except Exception as e2:  # noqa: BLE001
                log("ArcGIS failed:", e2)
        if len(fdot) < MIN_FDOT and prev_fdot:
            log(f"only {len(fdot)} FDOT cameras from {source}; keeping previous {len(prev_fdot)}")
            fdot, source = prev_fdot, "previous"
    fdot = [c for c in fdot if in_bbox(c["lat"], c["lon"])]

    manual = json.loads(MANUAL.read_text("utf-8")).get("cams", []) if MANUAL.exists() else []
    manual = [c for c in manual if isinstance(c.get("lat"), (int, float)) and isinstance(c.get("lon"), (int, float))]
    refresh_youtube(manual, args.offline)
    if not args.offline and manual:
        MANUAL.write_text(json.dumps({"_comment": json.loads(MANUAL.read_text("utf-8")).get("_comment", ""), "cams": manual}, indent=1) + "\n", "utf-8")

    cams = manual + sorted(fdot, key=lambda c: c["name"])
    assign_cities(cams)
    out = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "fdot_source": source,
           "counts": {"fdot": len(fdot), "manual": len(manual)}, "cams": cams}
    OUT.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False) + "\n", "utf-8")
    log(f"wrote {OUT} with {len(cams)} cameras (fdot={len(fdot)} from {source}, manual={len(manual)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
