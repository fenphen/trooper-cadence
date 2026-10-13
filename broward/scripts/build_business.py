#!/usr/bin/env python3
"""Business layer data (phase 4): where the businesses are, by type.

Two complementary sources:
  * OpenStreetMap (Overpass API): every mapped shop, restaurant, office, clinic, hotel, etc. in Broward,
    as points with a coarse business group. Free, no key, community-maintained (so not complete, but
    excellent for "what is actually on this street"). Counted per city and per ZIP.
  * Census ZIP Code Business Patterns (ZBP) and County Business Patterns (CBP): the official count of
    establishments per ZIP code by industry sector (NAICS). Needs CENSUS_API_KEY. Complete, but ~2 years old.

Outputs: data/business.json (summaries) and data/business_points.json (OSM points, compact arrays).
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
UA = "BrowardLive/0.1 (+https://github.com/fenphen/trooper-cadence; hobby map, nightly)"
BBOX = (25.94, -80.95, 26.36, -80.03)   # south, west, north, east (Overpass order)
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter", "https://overpass.private.coffee/api/interpreter"]

AMENITY_FOOD = {"restaurant", "cafe", "bar", "pub", "fast_food", "ice_cream", "food_court", "biergarten", "nightclub"}
AMENITY_HEALTH = {"pharmacy", "dentist", "doctors", "clinic", "hospital", "veterinary", "nursing_home", "social_facility"}
AMENITY_AUTO = {"fuel", "car_wash", "car_rental", "car_repair", "charging_station", "parking_garage"}
AMENITY_FINANCE = {"bank", "atm", "bureau_de_change", "money_transfer"}
AMENITY_EDU = {"school", "college", "university", "kindergarten", "childcare", "language_school", "driving_school", "music_school", "training"}
AMENITY_OTHER = {"cinema", "theatre", "casino", "marketplace", "post_office", "laundry", "dry_cleaning", "gym", "coworking_space", "events_venue", "conference_centre", "studio"}
AMENITIES = AMENITY_FOOD | AMENITY_HEALTH | AMENITY_AUTO | AMENITY_FINANCE | AMENITY_EDU | AMENITY_OTHER
GROCERY = {"supermarket", "convenience", "grocery", "greengrocer", "bakery", "butcher", "deli", "seafood", "wholesale", "frozen_food", "health_food", "farm"}
LEISURE = {"fitness_centre", "sports_centre", "marina", "golf_course", "bowling_alley", "escape_game", "trampoline_park", "water_park", "amusement_arcade", "dance"}
TOURISM = {"hotel", "motel", "guest_house", "hostel", "apartment", "attraction", "museum", "zoo", "theme_park", "aquarium", "gallery"}

SECTOR_LABELS = {  # NAICS 2-digit sectors, short names for the UI
    "11": "Agriculture", "21": "Mining", "22": "Utilities", "23": "Construction", "31-33": "Manufacturing", "42": "Wholesale trade",
    "44-45": "Retail trade", "48-49": "Transportation & warehousing", "51": "Information", "52": "Finance & insurance",
    "53": "Real estate", "54": "Professional & technical services", "55": "Management of companies", "56": "Admin, support & waste services",
    "61": "Education", "62": "Health care & social assistance", "71": "Arts, entertainment & recreation", "72": "Accommodation & food services",
    "81": "Other services", "99": "Unclassified", "00": "All sectors",
}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def http(url: str, data: bytes | None = None, timeout: int = 240, headers: dict | None = None) -> bytes:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, "Accept": "application/json,*/*", **(headers or {})})
    last = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read()
                if body[:2] == b"\x1f\x8b":
                    import gzip
                    body = gzip.decompress(body)
                return body
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"{url[:100]}: {last}")


# ---------------------------------------------------------------- point in polygon

def _ring(lon, lat, r):
    inside = False
    j = len(r) - 1
    for i in range(len(r)):
        xi, yi, xj, yj = r[i][0], r[i][1], r[j][0], r[j][1]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def pip(lon, lat, geom) -> bool:
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    return any(p and _ring(lon, lat, p[0]) and not any(_ring(lon, lat, h) for h in p[1:]) for p in polys)


class Index:
    """Crude grid index over polygons so 20k points don't take forever."""
    def __init__(self, features: list, key: str):
        self.items = []
        for f in features:
            g = f.get("geometry")
            if not g:
                continue
            xs, ys = [], []
            polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
            for p in polys:
                for pt in p[0]:
                    xs.append(pt[0]); ys.append(pt[1])
            self.items.append((min(xs), min(ys), max(xs), max(ys), g, f["properties"][key]))

    def find(self, lon, lat):
        for x0, y0, x1, y1, g, name in self.items:
            if x0 <= lon <= x1 and y0 <= lat <= y1 and pip(lon, lat, g):
                return name
        return None


# ---------------------------------------------------------------- OSM

def classify(t: dict) -> tuple[str, str] | None:
    """Returns (group, kind) or None if not a business."""
    if "shop" in t:
        k = t["shop"]
        if k in ("yes", "no", "vacant"):
            return ("Retail", "shop")
        if k in GROCERY:
            return ("Grocery & food stores", k)
        if k in ("car", "car_repair", "car_parts", "tyres", "motorcycle", "boat", "car_wash"):
            return ("Auto & marine", k)
        if k in ("hairdresser", "beauty", "massage", "tattoo", "nails", "cosmetics", "perfumery"):
            return ("Beauty & personal care", k)
        return ("Retail", k)
    a = t.get("amenity")
    if a in AMENITY_FOOD:
        return ("Restaurants & bars", a)
    if a in AMENITY_HEALTH or "healthcare" in t:
        return ("Health care", a or t.get("healthcare"))
    if a in AMENITY_AUTO:
        return ("Auto & marine", a)
    if a in AMENITY_FINANCE:
        return ("Finance", a)
    if a in AMENITY_EDU:
        return ("Education & childcare", a)
    if a in AMENITY_OTHER:
        return ("Services & entertainment", a)
    if "office" in t:
        o = t["office"]
        if o in ("lawyer", "accountant", "financial", "insurance", "estate_agent", "financial_advisor", "tax_advisor"):
            return ("Professional services", o)
        return ("Offices", o)
    if "craft" in t:
        return ("Trades & crafts", t["craft"])
    if t.get("tourism") in TOURISM:
        return ("Hotels & attractions", t["tourism"])
    if t.get("leisure") in LEISURE:
        return ("Fitness & recreation", t["leisure"])
    if t.get("industrial") or t.get("landuse") == "industrial" and t.get("name"):
        return ("Industrial", t.get("industrial") or "industrial")
    return None


def osm_points() -> list[dict]:
    s, w, n, e = BBOX
    bb = f"({s},{w},{n},{e})"
    q = f"""[out:json][timeout:240];
(
  nwr["shop"]{bb};
  nwr["amenity"~"^({'|'.join(sorted(AMENITIES))})$"]{bb};
  nwr["office"]{bb};
  nwr["craft"]{bb};
  nwr["healthcare"]{bb};
  nwr["tourism"~"^({'|'.join(sorted(TOURISM))})$"]{bb};
  nwr["leisure"~"^({'|'.join(sorted(LEISURE))})$"]{bb};
);
out center tags;"""
    data = None
    for ep in OVERPASS:
        try:
            raw = http(ep, data=urllib.parse.urlencode({"data": q}).encode(), timeout=300)
            data = json.loads(raw)
            log(f"Overpass {ep}: {len(data.get('elements', []))} elements")
            break
        except Exception as ex:  # noqa: BLE001
            log(f"Overpass {ep} failed: {ex}")
    if not data:
        raise RuntimeError("all Overpass endpoints failed")
    out = []
    for el in data.get("elements", []):
        t = el.get("tags") or {}
        c = classify(t)
        if not c:
            continue
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lon = el.get("lon") or (el.get("center") or {}).get("lon")
        if lat is None or lon is None:
            continue
        out.append({"id": f"{el['type'][0]}{el['id']}", "lat": round(lat, 5), "lon": round(lon, 5), "group": c[0], "kind": c[1],
                    "name": t.get("name") or t.get("brand") or "", "addr": " ".join(x for x in (t.get("addr:housenumber"), t.get("addr:street")) if x),
                    "zip_tag": t.get("addr:postcode", "")[:5]})
    return out


# ---------------------------------------------------------------- Census ZBP / CBP

def census_business() -> dict | None:
    key = os.environ.get("CENSUS_API_KEY", "").strip()
    if not key:
        log("ZBP/CBP: CENSUS_API_KEY not set; skipping")
        return None
    out: dict = {}
    for year in (2023, 2022, 2021):
        try:
            rows = json.loads(http(f"https://api.census.gov/data/{year}/cbp?get=ESTAB,EMP,NAICS2017_LABEL&for=county:011&in=state:12&NAICS2017=*&key={key}"))
            hdr = rows[0]
            sectors = {}
            for r in rows[1:]:
                d = dict(zip(hdr, r))
                code = d.get("NAICS2017", "")
                if code in SECTOR_LABELS:
                    sectors[code] = {"label": SECTOR_LABELS[code], "estab": int(d.get("ESTAB") or 0), "emp": int(d.get("EMP") or 0)}
            out["cbp"] = {"year": year, "sectors": sectors}
            log(f"CBP {year}: {len(sectors)} sectors, total estab {sectors.get('00', {}).get('estab')}")
            break
        except Exception as ex:  # noqa: BLE001
            log(f"CBP {year} failed: {ex}")
    for year in (2023, 2022, 2021):
        try:
            zips: dict = {}
            # ZBP has no state nesting in every vintage; ask for all ZIPs in the state and keep Broward ones (330xx-333xx)
            for form in (f"for=zip%20code:*&in=state:12", f"for=zipcode:*&in=state:12", f"for=zip%20code:*"):
                try:
                    rows = json.loads(http(f"https://api.census.gov/data/{year}/zbp?get=ESTAB,NAICS2017_LABEL&NAICS2017=*&{form}&key={key}", timeout=300))
                    break
                except Exception as ex:  # noqa: BLE001
                    log(f"ZBP {year} {form}: {ex}")
                    rows = None
            if not rows:
                continue
            hdr = rows[0]
            zkey = next((h for h in hdr if "zip" in h.lower()), None)
            for r in rows[1:]:
                d = dict(zip(hdr, r))
                z = str(d.get(zkey, ""))
                if not (z.startswith("330") or z.startswith("331") or z.startswith("333")):
                    continue
                code = d.get("NAICS2017", "")
                if code not in SECTOR_LABELS:
                    continue
                zips.setdefault(z, {})[code] = int(d.get("ESTAB") or 0)
            out["zbp"] = {"year": year, "zips": zips}
            log(f"ZBP {year}: {len(zips)} Broward-area ZIPs")
            break
        except Exception as ex:  # noqa: BLE001
            log(f"ZBP {year} failed: {ex}")
    return out or None


# ---------------------------------------------------------------- main

def main() -> int:
    cities = json.loads((DATA / "cities.geojson").read_text("utf-8")) if (DATA / "cities.geojson").exists() else None
    zctas = json.loads((DATA / "zctas.geojson").read_text("utf-8")) if (DATA / "zctas.geojson").exists() else None
    ci = Index(cities["features"], "name") if cities else None
    zi = Index(zctas["features"], "zip") if zctas else None
    prev_pts = DATA / "business_points.json"
    try:
        pts = osm_points()
    except Exception as ex:  # noqa: BLE001
        log("OSM failed:", ex)
        pts = json.loads(prev_pts.read_text("utf-8")).get("points", []) if prev_pts.exists() else []
        pts = [dict(zip(("lat", "lon", "group", "kind", "name", "city", "zip"), p)) for p in pts]
    by_city: dict = {}
    by_zip: dict = {}
    groups: dict = {}
    compact = []
    for p in pts:
        city = p.get("city") or (ci.find(p["lon"], p["lat"]) if ci else None) or ""
        z = p.get("zip") or (zi.find(p["lon"], p["lat"]) if zi else None) or p.get("zip_tag") or ""
        groups[p["group"]] = groups.get(p["group"], 0) + 1
        for key, table in ((city, by_city), (z, by_zip)):
            if key:
                t = table.setdefault(key, {"total": 0, "groups": {}})
                t["total"] += 1
                t["groups"][p["group"]] = t["groups"].get(p["group"], 0) + 1
        compact.append([p["lat"], p["lon"], p["group"], p.get("kind", ""), p.get("name", ""), city, z])
    (DATA / "business_points.json").write_text(json.dumps({"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "fields": ["lat", "lon", "group", "kind", "name", "city", "zip"], "points": compact}, separators=(",", ":"), ensure_ascii=False) + "\n", "utf-8")
    census = census_business()
    prev = json.loads((DATA / "business.json").read_text("utf-8")) if (DATA / "business.json").exists() else {}
    out = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "osm": {"count": len(compact), "groups": dict(sorted(groups.items(), key=lambda kv: -kv[1])), "by_city": by_city, "by_zip": by_zip,
                   "note": "OpenStreetMap, community-mapped; counts are what has been mapped, not an official register"},
           "census": census or prev.get("census"), "sector_labels": SECTOR_LABELS}
    (DATA / "business.json").write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False) + "\n", "utf-8")
    log(f"wrote business.json: {len(compact)} OSM points, {len(by_city)} cities, {len(by_zip)} zips; census: {'yes' if census else 'no'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
