#!/usr/bin/env python3
"""Build the geography + demographics files for Broward Live (phase 2). Standard library only.

Outputs (all in broward/data/):
  cities.geojson        municipal boundaries (+ unincorporated), simplified, property "name"
  tracts.geojson        census tracts for Broward (FIPS 12011), simplified, property "geoid"
  demographics.json     ACS 5-year figures per city and per tract, BLS unemployment, metadata

Sources are keyless public APIs; see NOTES.md. Each step falls back or keeps the previous file.
"""
from __future__ import annotations

import json
import math
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
UA = "BrowardLive/0.1 (+https://github.com/fenphen/trooper-cadence; hobby map)"

CITIES = ["Coconut Creek", "Cooper City", "Coral Springs", "Dania Beach", "Davie", "Deerfield Beach", "Fort Lauderdale",
          "Hallandale Beach", "Hillsboro Beach", "Hollywood", "Lauderdale-by-the-Sea", "Lauderdale Lakes", "Lauderhill",
          "Lazy Lake", "Lighthouse Point", "Margate", "Miramar", "North Lauderdale", "Oakland Park", "Parkland",
          "Pembroke Park", "Pembroke Pines", "Plantation", "Pompano Beach", "Sea Ranch Lakes", "Southwest Ranches",
          "Sunrise", "Tamarac", "West Park", "Weston", "Wilton Manors"]
BBOX = "-80.95,25.94,-80.03,26.36"

BOUNDARY_SOURCES = [
    ("Broward County GIS (QAlert_Cities_Multipart_Polys)",
     "https://services.arcgis.com/JMAJrTsHNLrSsWf5/ArcGIS/rest/services/QAlert_Cities_Multipart_Polys/FeatureServer/0/query?where=1%3D1&outFields=*&outSR=4326&f=geojson"),
    ("Broward County GIS (RIRP_Municipalities)",
     "https://services.arcgis.com/JMAJrTsHNLrSsWf5/ArcGIS/rest/services/RIRP_Municipalities/FeatureServer/0/query?where=1%3D1&outFields=*&outSR=4326&f=geojson"),
    ("Broward County GIS (OpenDataCityBoundaries)",
     "https://services.arcgis.com/JMAJrTsHNLrSsWf5/ArcGIS/rest/services/OpenDataCityBoundaries/FeatureServer/0/query?where=1%3D1&outFields=*&outSR=4326&f=geojson"),
    ("City of Fort Lauderdale GIS (MunicipalBoundaryCountywide)",
     "https://gis.fortlauderdale.gov/server/rest/services/MunicipalBoundaryCountywide/FeatureServer/0/query?where=1%3D1&outFields=*&outSR=4326&f=geojson"),
    ("Census TIGERweb incorporated places (bbox)",
     "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Places_CouSub_ConCity_SubMCD/MapServer/4/query?where=STATE%3D%2712%27&geometry=" + BBOX +
     "&geometryType=esriGeometryEnvelope&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=GEOID,NAME,BASENAME&outSR=4326&f=geojson"),
]
TRACT_SOURCES = [
    ("Census TIGERweb tracts (generalized)",
     "https://tigerweb.geo.census.gov/arcgis/rest/services/Generalized_ACS2024/Tracts_Blocks/MapServer/0/query?where=STATE%3D%2712%27%20AND%20COUNTY%3D%27011%27&outFields=GEOID,NAME,BASENAME&outSR=4326&f=geojson&resultRecordCount=2000"),
    ("Census TIGERweb tracts",
     "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Tracts_Blocks/MapServer/0/query?where=STATE%3D%2712%27%20AND%20COUNTY%3D%27011%27&outFields=GEOID,NAME,BASENAME&outSR=4326&f=geojson&resultRecordCount=2000"),
]
ACS_YEARS = [2024, 2023]
ACS_VARS = {
    "pop": "B01003_001E", "income": "B19013_001E", "age": "B01002_001E", "home_value": "B25077_001E",
    "hh": "B25003_001E", "renters": "B25003_003E", "pov_base": "B17001_001E", "pov": "B17001_002E",
    "ed_base": "B15003_001E", "ba": "B15003_022E", "ma": "B15003_023E", "prof": "B15003_024E", "phd": "B15003_025E",
    "race_total": "B03002_001E", "white": "B03002_003E", "black": "B03002_004E", "asian": "B03002_006E", "hispanic": "B03002_012E",
}
BLS = "https://api.bls.gov/publicAPI/v2/timeseries/data/LAUCN120110000000003?latest=true"


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json,*/*"})
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"GET {url[:120]}...: {last}")


def get_json(url: str):
    data = json.loads(get(url))
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(f"service error: {data['error']}")
    return data


# ---------------------------------------------------------------- geometry helpers

def simplify_ring(ring: list, tol: float) -> list:
    """Douglas-Peucker; keeps rings closed and never collapses below 4 points."""
    if len(ring) <= 4:
        return ring
    def dp(pts):
        if len(pts) < 3:
            return pts
        (x1, y1), (x2, y2) = pts[0], pts[-1]
        dx, dy = x2 - x1, y2 - y1
        den = math.hypot(dx, dy) or 1e-12
        best, idx = 0.0, 0
        for i in range(1, len(pts) - 1):
            x, y = pts[i]
            d = abs(dy * x - dx * y + x2 * y1 - y2 * x1) / den
            if d > best:
                best, idx = d, i
        if best > tol:
            return dp(pts[:idx + 1])[:-1] + dp(pts[idx:])
        return [pts[0], pts[-1]]
    pts = [tuple(p[:2]) for p in ring]
    if pts[0] == pts[-1]:
        # closed ring: split at the point farthest from the start so the chord is not degenerate
        far = max(range(1, len(pts) - 1), key=lambda i: (pts[i][0] - pts[0][0]) ** 2 + (pts[i][1] - pts[0][1]) ** 2)
        out = dp(pts[:far + 1])[:-1] + dp(pts[far:])
    else:
        out = dp(pts)
    if len(out) < 4:
        return ring
    if out[0] != out[-1]:
        out.append(out[0])
    return [[round(x, 5), round(y, 5)] for x, y in out]


def simplify_geom(geom: dict, tol: float) -> dict:
    t = geom.get("type")
    if t == "Polygon":
        rings = [simplify_ring(r, tol) for r in geom["coordinates"]]
        return {"type": "Polygon", "coordinates": [r for r in rings if len(r) >= 4]}
    if t == "MultiPolygon":
        polys = []
        for poly in geom["coordinates"]:
            rings = [simplify_ring(r, tol) for r in poly]
            rings = [r for r in rings if len(r) >= 4]
            if rings:
                polys.append(rings)
        return {"type": "MultiPolygon", "coordinates": polys}
    return geom


def ring_area(ring: list) -> float:
    a = 0.0
    for i in range(len(ring) - 1):
        a += ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1]
    return abs(a) / 2


def geom_area(geom: dict) -> float:
    if geom["type"] == "Polygon":
        return ring_area(geom["coordinates"][0]) if geom["coordinates"] else 0
    return sum(ring_area(p[0]) for p in geom["coordinates"] if p)


def centroid(geom: dict) -> tuple[float, float]:
    pts = []
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    for poly in polys:
        if poly:
            pts.extend(poly[0])
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)) if pts else (0, 0)


# ---------------------------------------------------------------- cities

def norm_city(raw: str) -> str | None:
    s = re.sub(r"\s+", " ", (raw or "")).strip()
    s = re.sub(r"\b(city|town|village) of\b", "", s, flags=re.I).strip()
    s = re.sub(r",? Florida$", "", s).strip()
    s = re.sub(r"\s+(city|town|village)$", "", s, flags=re.I).strip()
    key = s.lower().replace("-", " ").replace("by the sea", "by-the-sea").replace("ft.", "fort").replace("ft ", "fort ")
    for c in CITIES:
        if key == c.lower().replace("-", " ").replace("by the sea", "by-the-sea"):
            return c
    if "unincorporated" in key or "bmsd" in key or "municipal services" in key or key in ("broward", "broward county", "county"):
        return "Unincorporated Broward"
    return None


def build_cities() -> dict | None:
    for label, url in BOUNDARY_SOURCES:
        try:
            gj = get_json(url)
        except Exception as e:  # noqa: BLE001
            log(f"cities: {label} failed: {e}")
            continue
        feats = gj.get("features") or []
        if not feats:
            log(f"cities: {label} returned no features")
            continue
        # pick the property holding the city name
        sample = feats[0].get("properties") or {}
        name_key = None
        for k in sample:
            if re.search(r"name|city|munic|juris", k, re.I):
                vals = {norm_city(str((f.get("properties") or {}).get(k))) for f in feats}
                if len(vals - {None}) >= 20:
                    name_key = k
                    break
        if not name_key:
            log(f"cities: {label}: no usable name field in {list(sample)[:12]}")
            continue
        merged: dict[str, list] = {}
        for f in feats:
            name = norm_city(str((f.get("properties") or {}).get(name_key)))
            geom = f.get("geometry")
            if not name or not geom:
                continue
            polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]] if geom["type"] == "Polygon" else []
            merged.setdefault(name, []).extend(polys)
        out = []
        for name, polys in sorted(merged.items()):
            geom = simplify_geom({"type": "MultiPolygon", "coordinates": polys}, 0.00015)
            out.append({"type": "Feature", "properties": {"name": name, "area_deg2": round(geom_area(geom), 6)}, "geometry": geom})
        found = sorted(merged)
        missing = [c for c in CITIES if c not in merged]
        log(f"cities: {label}: {len(found)} municipalities ({len(feats)} features, name field '{name_key}'); missing: {missing}")
        if len(found) >= 25:
            return {"type": "FeatureCollection", "source": label, "generated": now(), "features": out}
    return None


# ---------------------------------------------------------------- tracts

def build_tracts() -> dict | None:
    for label, url in TRACT_SOURCES:
        try:
            gj = get_json(url)
        except Exception as e:  # noqa: BLE001
            log(f"tracts: {label} failed: {e}")
            continue
        feats = gj.get("features") or []
        if len(feats) < 100:
            log(f"tracts: {label}: only {len(feats)} features")
            continue
        out = []
        for f in feats:
            p = f.get("properties") or {}
            geoid = str(p.get("GEOID") or "")
            if not geoid.startswith("12011") or not f.get("geometry"):
                continue
            geom = simplify_geom(f["geometry"], 0.0001)
            out.append({"type": "Feature", "properties": {"geoid": geoid, "name": p.get("BASENAME") or p.get("NAME")}, "geometry": geom})
        log(f"tracts: {label}: {len(out)} tracts")
        return {"type": "FeatureCollection", "source": label, "generated": now(), "features": out}
    return None


# ---------------------------------------------------------------- ACS

def acs_rows(year: int, geo: str) -> list[list[str]]:
    url = f"https://api.census.gov/data/{year}/acs/acs5?get=NAME,{','.join(ACS_VARS.values())}&{geo}"
    return get_json(url)


def num(v) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if x <= -666666 else x


def shape(row: dict) -> dict:
    g = lambda k: num(row.get(ACS_VARS[k]))  # noqa: E731
    pop, hh, povb, edb, rt = g("pop"), g("hh"), g("pov_base"), g("ed_base"), g("race_total")
    pct = lambda a, b: round(100 * a / b, 1) if a is not None and b else None  # noqa: E731
    ba_plus = sum(x for x in (g("ba"), g("ma"), g("prof"), g("phd")) if x is not None)
    return {
        "population": int(pop) if pop is not None else None,
        "median_income": int(g("income")) if g("income") is not None else None,
        "median_age": g("age"),
        "median_home_value": int(g("home_value")) if g("home_value") is not None else None,
        "pct_renters": pct(g("renters"), hh),
        "pct_poverty": pct(g("pov"), povb),
        "pct_bachelors": pct(ba_plus, edb) if edb else None,
        "pct_white": pct(g("white"), rt), "pct_black": pct(g("black"), rt), "pct_asian": pct(g("asian"), rt), "pct_hispanic": pct(g("hispanic"), rt),
    }


def build_acs() -> dict | None:
    for year in ACS_YEARS:
        try:
            places = acs_rows(year, "for=place:*&in=state:12")
            tracts = acs_rows(year, "for=tract:*&in=state:12%20county:011")
            county = acs_rows(year, "for=county:011&in=state:12")
        except Exception as e:  # noqa: BLE001
            log(f"ACS {year} failed: {e}")
            continue
        def rows_to_dicts(rows):
            hdr = rows[0]
            return [dict(zip(hdr, r)) for r in rows[1:]]
        cities = {}
        for r in rows_to_dicts(places):
            name = norm_city(r["NAME"])
            if name:
                cities[name] = {"geoid": "12" + r["place"], **shape(r)}
        tr = {}
        for r in rows_to_dicts(tracts):
            tr[r["state"] + r["county"] + r["tract"]] = shape(r)
        cty = shape(rows_to_dicts(county)[0]) if len(county) > 1 else None
        log(f"ACS {year}: {len(cities)} cities, {len(tr)} tracts; missing cities: {[c for c in CITIES if c not in cities]}")
        return {"year": year, "label": f"ACS {year - 4}-{year} 5-year estimates", "cities": cities, "tracts": tr, "county": cty}
    return None


def build_bls() -> dict | None:
    try:
        d = get_json(BLS)
        s = d["Results"]["series"][0]["data"][0]
        return {"unemployment_rate": float(s["value"]), "period": f"{s['periodName']} {s['year']}", "series": "LAUCN120110000000003"}
    except Exception as e:  # noqa: BLE001
        log("BLS failed:", e)
        return None


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main() -> int:
    DATA.mkdir(exist_ok=True)
    cities = build_cities()
    if cities:
        (DATA / "cities.geojson").write_text(json.dumps(cities, separators=(",", ":")) + "\n", "utf-8")
        log(f"wrote cities.geojson ({(DATA / 'cities.geojson').stat().st_size // 1024} KB)")
    else:
        log("cities: all sources failed; keeping previous file" if (DATA / "cities.geojson").exists() else "cities: nothing written")
    tracts = build_tracts()
    if tracts:
        (DATA / "tracts.geojson").write_text(json.dumps(tracts, separators=(",", ":")) + "\n", "utf-8")
        log(f"wrote tracts.geojson ({(DATA / 'tracts.geojson').stat().st_size // 1024} KB)")
    demo_path = DATA / "demographics.json"
    prev = json.loads(demo_path.read_text("utf-8")) if demo_path.exists() else {}
    acs = build_acs() or prev.get("acs")
    bls = build_bls() or prev.get("bls")
    if acs or bls:
        demo_path.write_text(json.dumps({"generated": now(), "acs": acs, "bls": bls}, separators=(",", ":")) + "\n", "utf-8")
        log("wrote demographics.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
