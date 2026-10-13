#!/usr/bin/env python3
"""Build broward/data/crime.json from agencies that publish incident-level data (phase 3).

Sources (all keyless), each wrapped so one failure never blocks the others:
  * Plantation PD: ArcGIS MapServer "Maps/crimeEvent" (90-day window, daily). We accumulate.
  * Fort Lauderdale PD: Socrata open data portal (incident dataset found via the catalog API).
  * BSO (Broward Sheriff's Office): bsocrimes.sheriff.org is an ArcGIS web app; we look for its
    FeatureServer URL in the page source and query it if found.
Incidents are kept for 400 days and deduplicated by id, so history grows past each source's window.
Standard library only.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
OUT = DATA / "crime.json"
UA = "BrowardLive/0.1 (+https://github.com/fenphen/trooper-cadence; hobby map, nightly)"
KEEP_DAYS = 400
BBOX = (-80.95, 25.94, -80.03, 26.36)

CATEGORIES = [  # (category, regex on the agency's type text)
    ("Homicide", r"homicide|murder|manslaughter"),
    ("Sexual assault", r"sex|rape"),
    ("Robbery", r"robbery"),
    ("Assault", r"assault|battery"),
    ("Vehicle break-in", r"burglary.*(vehicle|conveyance|auto)|vehicle.*(burglar|break)|theft from (motor )?vehicle"),
    ("Vehicle theft", r"motor vehicle theft|auto theft|stolen vehicle|vehicle theft|grand theft auto"),
    ("Burglary", r"burglar|breaking"),
    ("Theft", r"theft|larceny|shoplift|retail"),
    ("Vandalism", r"vandal|criminal mischief|damage"),
    ("Drugs", r"drug|narcotic|marijuana|cocaine"),
    ("Weapons", r"weapon|firearm|shooting|shots"),
    ("Fraud", r"fraud|forgery|counterfeit|identity|scam"),
    ("DUI", r"dui|driving under"),
    ("Arson", r"arson"),
    ("Disturbance", r"disturb|disorderly|trespass|loiter"),
]


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def get(url: str, timeout: int = 60, headers: dict | None = None) -> bytes:
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
    raise RuntimeError(f"GET {url[:140]}: {last}")


BROWSER = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
           "Accept-Language": "en-US,en;q=0.9"}


def get_json(url: str, **kw):
    body = get(url, **kw)
    try:
        return json.loads(body)
    except ValueError as e:
        raise RuntimeError(f"not JSON ({e}); body starts {body[:200]!r}") from e


def categorize(text: str) -> str:
    t = (text or "").lower()
    for cat, rx in CATEGORIES:
        if re.search(rx, t):
            return cat
    return "Other"


def parse_date(v) -> str | None:
    """Accepts epoch ms, ISO strings, 'MM/DD/YYYY HH:MM', returns ISO date-time (UTC-naive ok)."""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        try:
            return datetime.fromtimestamp(v / 1000 if v > 1e11 else v, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M")
        except (OverflowError, OSError, ValueError):
            return None
    s = str(v).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M", "%m/%d/%Y"):
        try:
            return datetime.strptime(s[:26] if "." in s else s, fmt).strftime("%Y-%m-%dT%H:%M")
        except ValueError:
            continue
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    return m.group(1) + "T00:00" if m else None


def in_bbox(lat, lon) -> bool:
    try:
        return BBOX[1] <= float(lat) <= BBOX[3] and BBOX[0] <= float(lon) <= BBOX[2]
    except (TypeError, ValueError):
        return False


def pick(d: dict, *patterns: str):
    """First value whose key matches any regex (case-insensitive)."""
    for pat in patterns:
        for k, v in d.items():
            if re.search(pat, k, re.I) and v not in (None, ""):
                return v
    return None


# ---------------------------------------------------------------- Plantation

def plantation() -> tuple[list[dict], dict]:
    base = "https://pgis.plantation.org/arcgis/rest/services/Maps/crimeEvent/MapServer"
    hdr = {**BROWSER, "Referer": "https://pgis.plantation.org/crime/"}
    info = get_json(base + "?f=pjson", headers=hdr)
    layers = info.get("layers") or []
    log(f"Plantation: layers {[(l.get('id'), l.get('name')) for l in layers]}")
    out = []
    for layer in layers or [{"id": 0}]:
        lid = layer.get("id", 0)
        url = f"{base}/{lid}/query?where=1%3D1&outFields=*&outSR=4326&f=geojson&resultRecordCount=5000"
        try:
            gj = get_json(url, headers=hdr)
        except Exception as e:  # noqa: BLE001
            log(f"Plantation layer {lid}: {e}")
            continue
        feats = gj.get("features") or []
        if feats:
            log(f"Plantation layer {lid}: {len(feats)} features; fields: {list((feats[0].get('properties') or {}).keys())[:25]}")
        for f in feats:
            p = f.get("properties") or {}
            g = f.get("geometry") or {}
            coords = g.get("coordinates") if g.get("type") == "Point" else None
            if not coords:
                continue
            lon, lat = coords[0], coords[1]
            if not in_bbox(lat, lon):
                continue
            typ = str(pick(p, r"^(offense|crime|incident).*(type|desc|class)", r"description", r"type", r"offense", r"crime") or "")
            date = parse_date(pick(p, r"date|time|occur|report"))
            cid = str(pick(p, r"case|incident.?(no|num|id)|report.?(no|num)|^objectid$|^id$") or f"{lat},{lon},{date}")
            out.append({"id": f"plantation-{cid}", "agency": "Plantation PD", "city": "Plantation", "date": date, "type": typ,
                        "category": categorize(typ), "address": str(pick(p, r"address|block|location|street") or ""),
                        "lat": round(float(lat), 5), "lon": round(float(lon), 5), "url": "https://pgis.plantation.org/crime/"})
    return out, {"name": "Plantation PD", "source": "https://pgis.plantation.org/crime/", "kind": "arcgis", "window": "90 days, updated daily"}


# ---------------------------------------------------------------- Fort Lauderdale (Socrata)

def fort_lauderdale() -> tuple[list[dict], dict]:
    domain = "fortlauderdale.data.socrata.com"
    cat = get_json(f"https://api.us.socrata.com/api/catalog/v1?domains={domain}&search_context={domain}&only=datasets&limit=100")
    results = cat.get("results") or []
    log(f"FLL Socrata catalog: {[(r['resource']['id'], r['resource']['name'], r['resource'].get('updatedAt','')[:10]) for r in results][:40]}")
    cands = [r for r in results if re.search(r"incident|crime|offense", r["resource"]["name"], re.I) and not re.search(r"call|cfs|fire|ems", r["resource"]["name"], re.I)]
    if not cands:
        raise RuntimeError("no incident dataset in the catalog")
    cands.sort(key=lambda r: r["resource"].get("updatedAt", ""), reverse=True)
    res = cands[0]["resource"]
    ds = res["id"]
    cols = [(c, str(t).lower().replace(" ", "_")) for c, t in zip(res.get("columns_field_name") or [], res.get("columns_datatype") or [])]
    log(f"FLL dataset {ds} '{res['name']}' updated {res.get('updatedAt')}; columns {cols[:40]}")
    date_col = next((c for c, t in cols if t in ("calendar_date", "floating_timestamp") and re.search(r"date|time|occur|report", c, re.I)), None) or next((c for c, t in cols if t in ("calendar_date", "floating_timestamp")), None)
    newest = None
    if date_col:
        mx = get_json(f"https://{domain}/resource/{ds}.json?$select=max({date_col})%20as%20m")
        newest = parse_date((mx[0] or {}).get("m")) if mx else None
    log(f"FLL date column {date_col}, newest record {newest}")
    anchor = datetime.strptime(newest[:10], "%Y-%m-%d") if newest else datetime.now(timezone.utc).replace(tzinfo=None)
    since = (anchor - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%dT00:00:00")
    q = f"https://{domain}/resource/{ds}.json?$limit=50000" + (f"&$where={urllib.parse.quote(date_col)}%20%3E%20%27{since}%27&$order={urllib.parse.quote(date_col)}%20DESC" if date_col else "")
    rows = get_json(q)
    log(f"FLL rows: {len(rows)}; sample: {json.dumps(rows[0])[:400] if rows else 'none'}")
    out = []
    for r in rows:
        lat = pick(r, r"^lat", r"latitude")
        lon = pick(r, r"^lon", r"longitude")
        loc = pick(r, r"location|geocoded|point|geom")
        if (lat is None or lon is None) and isinstance(loc, dict):
            if loc.get("type") == "Point" and loc.get("coordinates"):
                lon, lat = loc["coordinates"][0], loc["coordinates"][1]
            elif "latitude" in loc:
                lat, lon = loc.get("latitude"), loc.get("longitude")
        if not in_bbox(lat, lon):
            continue
        typ = str(pick(r, r"offense|crime|incident.*(type|desc|cat)|description|type|charge|nature") or "")
        date = parse_date(r.get(date_col) if date_col else pick(r, r"date|time"))
        cid = str(pick(r, r"case|incident.?(no|num|id)|report.?(no|num)|^id$|objectid") or f"{lat},{lon},{date}")
        out.append({"id": f"fll-{cid}", "agency": "Fort Lauderdale PD", "city": "Fort Lauderdale", "date": date, "type": typ, "category": categorize(typ),
                    "address": str(pick(r, r"address|block|location_desc|street") or ""), "lat": round(float(lat), 5), "lon": round(float(lon), 5),
                    "url": f"https://{domain}/d/{ds}"})
    stale = newest and newest[:10] < (datetime.now(timezone.utc) - timedelta(days=60)).strftime("%Y-%m-%d")
    return out, {"name": "Fort Lauderdale PD", "source": f"https://{domain}/d/{ds}", "kind": "socrata", "newest": newest, "historical": bool(stale),
                 "window": f"city open-data dataset '{res['name']}'" + (f"; the city stopped updating it in {newest[:7]}" if stale else "")}


# ---------------------------------------------------------------- BSO (discovery)

def bso() -> tuple[list[dict], dict]:
    html = get("https://bsocrimes.sheriff.org/", timeout=90, headers=BROWSER).decode("utf-8", "replace")
    urls = sorted(set(re.findall(r"https?://[\w./-]*arcgis[\w./-]*/(?:FeatureServer|MapServer)[\w/]*", html)))
    apps = sorted(set(re.findall(r"[\"'](?:appid|webmap|id)[\"']?\s*[:=]\s*[\"']([0-9a-f]{32})", html)))
    scripts = sorted(set(re.findall(r"src=[\"']([^\"']+\.js)", html)))[:15]
    log(f"BSO page: {len(html)} bytes; service urls {urls}; app ids {apps}; scripts {scripts}")
    for aid in apps[:3]:
        try:
            item = get_json(f"https://www.arcgis.com/sharing/rest/content/items/{aid}/data?f=json")
            found = sorted(set(re.findall(r"https?://[\w./-]+/(?:FeatureServer|MapServer)(?:/\d+)?", json.dumps(item))))
            log(f"BSO app {aid}: services {found}")
            urls.extend(found)
        except Exception as e:  # noqa: BLE001
            log(f"BSO app {aid}: {e}")
    out = []
    for u in urls:
        base = u.rstrip("/")
        if not re.search(r"/\d+$", base):
            base += "/0"
        try:
            gj = get_json(f"{base}/query?where=1%3D1&outFields=*&outSR=4326&f=geojson&resultRecordCount=5000")
        except Exception as e:  # noqa: BLE001
            log(f"BSO {base}: {e}")
            continue
        feats = gj.get("features") or []
        log(f"BSO {base}: {len(feats)} features; fields {list((feats[0].get('properties') or {}).keys())[:25] if feats else []}")
        for f in feats:
            p = f.get("properties") or {}
            g = f.get("geometry") or {}
            if g.get("type") != "Point":
                continue
            lon, lat = g["coordinates"][0], g["coordinates"][1]
            if not in_bbox(lat, lon):
                continue
            typ = str(pick(p, r"offense|crime|incident.*(type|desc)|description|type|nature") or "")
            date = parse_date(pick(p, r"date|time|occur|report"))
            cid = str(pick(p, r"case|incident.?(no|num|id)|report.?(no|num)|^objectid$|^id$") or f"{lat},{lon},{date}")
            out.append({"id": f"bso-{cid}", "agency": "Broward Sheriff's Office", "city": str(pick(p, r"city|munic|district|zone") or ""), "date": date, "type": typ,
                        "category": categorize(typ), "address": str(pick(p, r"address|block|location|street") or ""), "lat": round(float(lat), 5), "lon": round(float(lon), 5),
                        "url": "https://bsocrimes.sheriff.org/"})
        if out:
            break
    if not urls:
        raise RuntimeError("no ArcGIS service found in the BSO page (it may load its config from a script)")
    return out, {"name": "Broward Sheriff's Office", "source": "https://bsocrimes.sheriff.org/", "kind": "arcgis", "window": "see source"}


# ---------------------------------------------------------------- main

def main() -> int:
    prev = json.loads(OUT.read_text("utf-8")) if OUT.exists() else {"incidents": [], "agencies": []}
    incidents: dict[str, dict] = {i["id"]: i for i in prev.get("incidents", [])}
    agencies: dict[str, dict] = {a["name"]: a for a in prev.get("agencies", [])}
    for fn in (plantation, fort_lauderdale, bso):
        try:
            rows, meta = fn()
        except Exception as e:  # noqa: BLE001
            log(f"{fn.__name__}: FAILED: {e}")
            continue
        fresh = [r for r in rows if r.get("date")]
        for r in fresh:
            incidents[r["id"]] = r
        meta.update({"fetched": len(rows), "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "ok": True})
        agencies[meta["name"]] = meta
        log(f"{meta['name']}: {len(rows)} incidents this run")
    newest_by_agency: dict[str, str] = {}
    for i in incidents.values():
        if i.get("date"):
            newest_by_agency[i["agency"]] = max(newest_by_agency.get(i["agency"], ""), i["date"])
    def keep(i):
        n = newest_by_agency.get(i["agency"])
        if not n:
            return False
        start = (datetime.strptime(n[:10], "%Y-%m-%d") - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
        return (i.get("date") or "") >= start
    kept = [i for i in incidents.values() if keep(i)]
    kept.sort(key=lambda i: i.get("date") or "", reverse=True)
    for a in agencies.values():
        a["count"] = sum(1 for i in kept if i["agency"] == a["name"])
    out = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "keep_days": KEEP_DAYS,
           "agencies": sorted(agencies.values(), key=lambda a: a["name"]), "incidents": kept}
    OUT.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False) + "\n", "utf-8")
    log(f"wrote crime.json: {len(kept)} incidents from {len(agencies)} agencies")
    return 0


if __name__ == "__main__":
    sys.exit(main())
