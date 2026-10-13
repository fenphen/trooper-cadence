# 📍 Broward Live

One map of Broward County, Florida: **live webcams and traffic cameras**, with city boundaries,
demographics, crime and economic layers being added in phases.

**▶ Open it:** https://fenphen.github.io/trooper-cadence/broward/

- Street map by default, **🛰 Satellite** toggle for the Google Earth look, light and dark themes.
- Click a pin to see a snapshot or watch the stream in a side panel. Traffic cameras are FDOT
  snapshots that refresh every few seconds; beach, marina and other cams stream from their owners
  (YouTube or the owner's player). Cams whose owners block embedding open on the source site.
- Filter by camera type and by city; search by name or road. Every camera has a shareable link.
- **Cities**: boundaries and names; click a city for its population, income, home values, age, housing, poverty, education and race/ethnicity (Census ACS), plus how many cameras it has.
- **Demographics**: shade the map by any of those measures, by city or by neighborhood (census tract), with a legend.
- **Crime**: incident pins or a heat map with date range, category chips and the city filter. Each pin shows the offense, date, block and source.
- **Businesses**: shade cities or ZIP codes by how many businesses are mapped there, filter by type (restaurants, retail, health care, auto, offices…), and zoom in to see the individual businesses. Official Census establishment counts by industry sector per ZIP when the Census key is set.

## Phases

| Phase | Layer | Status |
|---|---|---|
| 1 | Cameras: FDOT/FL511 traffic cams + public beach, pier, marina, port, airport, weather, nature and attraction cams | **building** |
| 2 | City boundaries, demographics (population, income, age, housing, race/ethnicity) from the Census ACS | **live** (figures need the Census key below) |
| 3 | Crime: incident pins with type, date and source link where an agency publishes them, heat view, date and type filters; county/city annual statistics (FDLE) elsewhere | planned |
| 4 | Economy: largest employers, unemployment, home values by city | planned |
| 5 | Palm Beach, Miami-Dade and Collier counties with the same code | planned |

## One-time setup: Census API key
The demographic figures come from the Census Bureau's API, which needs a free key. Get one at
<https://api.census.gov/data/key_signup.html> (instant, by email), then in GitHub open
**Settings → Secrets and variables → Actions → New repository secret**, name `CENSUS_API_KEY`,
paste the key. The next nightly run (or **Actions → Refresh Broward map data → Run workflow**)
fills in `data/demographics.json`. Until then the map shows boundaries without shading.

## How the data stays fresh

`scripts/build_geo.py` fetches city boundaries (Broward County GIS), census tracts (TIGERweb), ACS
figures and BLS unemployment. `scripts/build_cams.py` fetches the FDOT camera list, merges it with the
hand-kept list in `data/manual_cams.json`, assigns each camera to a city, and writes `data/cams.json`. A GitHub Action
(`.github/workflows/broward-data.yml`) runs it every morning and commits the result, so the page
is static and free to host but the list never goes stale.

To add a camera, edit `data/manual_cams.json` (name, city, lat, lon, type, kind, src, page) or open
an issue with the link.

## Files

- `index.html`: the page (Leaflet + OpenStreetMap/CARTO tiles + Esri imagery, no API keys)
- `data/cams.json`: generated camera list; `data/manual_cams.json`: curated non-FDOT cams
- `scripts/build_cams.py`: the nightly builder
