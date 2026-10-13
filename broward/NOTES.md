# Broward Live: data source notes (for phases 2 to 4)

Collected 2026-10-13. Most of these could not be fetched from the build sandbox (network policy),
so verify each on first use. The nightly GitHub Action has normal internet access.

## Cameras (phase 1, in place)
- FL511 list JSON: `GET https://fl511.com/List/GetData/Cameras?query=<DataTables JSON>&lang=en`, 100 rows/page,
  `recordsTotal` ~4,960 statewide; rows have `id, county, roadway, direction, location, latLng.geography.wellKnownText,
  images[{id,imageUrl,videoUrl,disabled,blocked}]`. Map layer: `GET https://fl511.com/map/mapIcons/Cameras` (`item2[].itemId,
  location=[lat,lon]`). Single camera: `/map/data/Cameras/{id}`.
- Snapshot JPEG: `https://fl511.com/map/Cctv/{imageId}` (cached ~1 min, hot-linkable). Alt: ArcGIS layer
  `services.arcgis.com/3wFbqsFPLeKqOlIK/.../FL511_Traffic_Cameras/FeatureServer/0` with `IMAGE` = `images-dis.divas.cloud/DGI/chan-N_h.jpg`.
- Live HLS needs a token handshake (`/Camera/GetVideoUrl` then divas.cloud POST) plus Referer headers: not possible from a
  static site. We link to `https://fl511.com/map#camera-{id}` instead. A Cloudflare Worker could broker it later.
- Terms: FL511 says personal, non-commercial use; credit "FDOT / FL511", poll gently, don't archive images. Consider asking
  FDOT District 4 ITS for written OK.
- Seeded from the open-source fl-traffic project's packed dataset (2026-10-10): 496 Broward sites.

## Boundaries and demographics (phase 2)
- Broward GIS org `JMAJrTsHNLrSsWf5`: `RIRP_Municipalities` (Sept 2023) or `QAlert_Cities_Multipart_Polys` (Apr 2025):
  `https://services.arcgis.com/JMAJrTsHNLrSsWf5/ArcGIS/rest/services/RIRP_Municipalities/FeatureServer/0/query?where=1%3D1&outFields=*&outSR=4326&f=geojson`
  Fallback: TIGERweb Places layer 4 with a Broward bbox; or `cb_2024_12_place_500k.zip`.
- Tracts: `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Tracts_Blocks/MapServer/0/query?where=STATE%3D%2712%27%20AND%20COUNTY%3D%27011%27&outFields=GEOID,NAME&outSR=4326&f=geojson`
- ACS 2024 5-year, no key needed under 500 calls/day. Places are not nested under county: pull `for=place:*&in=state:12`
  and filter by GEOID. Variables: B01003_001E pop, B19013_001E income, B01002_001E median age, B25077_001E home value,
  B25003_001E/_003E renters, B17001_001E/_002E poverty, B15003_001E + _022E.._025E bachelor's+, B03002 race/ethnicity.
- BLS LAUS Broward unemployment: `https://api.bls.gov/publicAPI/v2/timeseries/data/LAUCN120110000000003?latest=true`.
- Largest employers: Broward ACFR "Principal Employers" table (broward.org/accounting/FinancialReports) and GFL Alliance;
  transcribe yearly into employers.json.

## Crime (phase 3), per agency
- Plantation PD: own ArcGIS `https://pgis.plantation.org/arcgis/rest/services/Maps/crimeEvent/MapServer` (90-day window,
  daily). Easiest; accumulate nightly.
- Fort Lauderdale PD: Socrata `fortlauderdale.data.socrata.com` ("Incidents" since 2015; may be stale since the 2023 RMS
  change, check `rowsUpdatedAt`). Monthly Excel on flpd.gov as backup.
- BSO (unincorporated + Deerfield, Pompano, Weston, Tamarac, Oakland Park, Lauderdale Lakes, North Lauderdale, Parkland,
  Cooper City, Dania Beach, Pembroke Park, West Park, LBTS, SW Ranches): `https://bsocrimes.sheriff.org/` (ArcGIS app; find
  the FeatureServer in page source) and CrimeMapping.com `map/fl/browardcounty`.
- Hollywood PD and Lauderhill PD (org 655): CrimeMapping.com. Undocumented POST API (`/map/GetOrganizations`,
  `/Map/CrimeIncidents_Read`), WAF-protected, block-level addresses, ~6 months.
- Margate, Hallandale Beach (and probably Pembroke Pines, Miramar, Coral Springs, Davie): LexisNexis Community Crime Map.
  Its terms forbid scraping/redistribution: show aggregates only, or skip.
- No feed found: Sunrise, Coconut Creek, Wilton Manors, Lighthouse Point, Seminole PD. Use FDLE FIBRS annual tables
  (`https://www.fdle.state.fl.us/cjab/fibrs`) for city/agency totals. CityProtect has no Broward agencies.
