# CampusPulse — Power BI project (PBIP)

A ready-built Power BI file for the synthetic dataset in `data/`: the model,
the relationships, 109 DAX measures, a custom theme, and a six-page report with
112 visuals including three AI visuals.

## Open it

Clone or extract this repo to **`C:\CampusPulse`** — the `DataFolder` parameter
is pre-set to `C:\CampusPulse\social-media-dataset\data`, so with that location
there is nothing to configure:

```powershell
cd C:\
git clone https://github.com/fenphen/trooper-cadence.git CampusPulse
```

Use a **local disk**, not a Google Drive / OneDrive virtual drive. Power BI's
data-loading engine runs in a separate process that often cannot resolve virtual
drive letters, and you get `Could not find a part of the path` for every file at
once even though Explorer shows them. Publish from a local copy; sync the
finished `.pbix` afterwards if you want it shared.

1. Open **`powerbi/CampusPulse.pbip`** in Power BI Desktop (File → Open, or
   double-click).
2. If you put the project anywhere other than `C:\CampusPulse`, set the
   **`DataFolder`** parameter from **Home → Transform data → Manage parameters**
   to the folder holding the CSVs. A trailing slash is fine either way.
3. **Home → Refresh.** Roughly 700,000 rows load in well under a minute.
4. Save as `.pbix` when you want a single file to publish
   (**File → Save as → .pbix**), then publish to the Power BI service as usual.

> **Why PBIP and not .pbix?** A `.pbix` is a binary container holding a
> *compiled* VertiPaq database, which can only be produced by Power BI itself.
> PBIP is Microsoft's open, text-based project format and is the only form a
> complete model + report can be authored in outside Desktop. Opening the
> `.pbip` and saving as `.pbix` gives you the binary in two clicks.

If Desktop offers to upgrade the report format when you open or save, accept —
that just rewrites the JSON to your build's current schema version.

## What's in the model

**17 tables, 19 relationships, 109 measures.** Relationships are already built,
`dim_date` is marked as the date table, geography columns are tagged so maps
work, `month_name` sorts by `month_num`, and PII columns (`email`, `phone`,
`hashed_email`, `mobile_advertising_id`) are hidden from the field list but
still in the model, so the privacy lesson can reveal them.

Measures are grouped into display folders — Volume, Rates, Video, Interaction,
Advertising, Late night on the engagement table; Delivery, Money, Efficiency on
campaigns; Reach and Privacy settings on accounts.

### Two modelling decisions worth explaining to students

Both are deliberate, and both are good discussion material about why a data
model is a design artifact rather than a transcription of the source files.

**The bridge tables filter in both directions.** `bridge_user_segments` and
`bridge_user_interests` are set to bidirectional so that picking a segment or an
interest filters the students, and therefore filters every fact about them.
That is what makes the Segment slicer work everywhere.

**`dim_campaigns[primary_segment_id]` is deliberately *not* related to
`dim_segments`.** Because the bridge already filters students in both
directions, adding that relationship would give `dim_segments` two live routes
into `fact_ad_exposures` — one through `dim_campaigns`, one through the bridge
via `dim_users` — and Power BI rejects models with ambiguous filter paths. The
column is still there as a lookup. Ask students to add the relationship and read
the error; it is the clearest possible demonstration of why ambiguity matters.

A related consequence worth pointing out: the **Platform** slicer filters
activity and account metrics, but not `[Panel Size]`. Platform reaches students
only through `dim_platform_profiles`, which filters one way. Use `[Adoption %]`
when you want "share of students on this platform". Making that relationship
bidirectional would introduce exactly the ambiguity described above — another
worthwhile experiment.

## The report

| Page | What it answers |
|---|---|
| **Audience 360** | Who the 2,000 students are — map of campuses, class year, gender, housing, majors, platform adoption |
| **Screen Time & Behavior** | Daily minutes by platform, hour-of-day curves, video completion and forwarding, late-night share by chronotype |
| **Segment Marketplace** | The rate card: 12 packaged audiences with member counts, match strength, CPM, and reach-vs-price scatter |
| **Campaign Performance** | Spend, CTR, CPM, CPA, ROAS by campaign and platform, plus a decomposition tree on conversions |
| **Network & Influence** | Friendship graph stats, followers vs engagement rate, micro-influencer table, key influencers on creator level |
| **The Privacy Lens** | Where all 165 columns came from, sensitivity by table, opt-in rates, and the inferred political label |

Every page has five slicers across the top and a row of KPI cards, so students
can cross-filter immediately without building anything.

**AI visuals included:** Smart Narrative on five pages (it writes its own
summary of whatever is on screen and re-writes it as you filter), Key
Influencers on Network & Influence (what predicts being a content creator), and
a Decomposition Tree on Campaign Performance (break conversions down by
campaign, platform, objective, vertical — and let it pick "high value" splits
for you).

## Rebuilding

```bash
python3 generate_data.py    # regenerate the CSVs
python3 build_pbip.py       # rebuild the PBIP from the CSVs
python3 verify_pbip.py      # 2,002 correctness checks
```

`build_pbip.py` reads the real CSV headers, so column data types and the
partition definitions always match the data. Editing the report in Desktop and
saving writes back to the same folder — but a rebuild overwrites it, so copy
your work out first.

The build is split into `pbip_model.py` (tables, relationships, measures),
`pbip_pages.py` (page and visual layout), `pbip_report.py` (PBIR rendering),
and `pbip_theme.py` (colors and fonts).

## How this was validated

Neither Power BI Desktop nor Windows exists in the environment this was built
in, so **the file has never been opened in Power BI.** Instead it was checked
two ways:

- **Schema validation** — all 126 JSON files validate against Microsoft's
  published Fabric/PBIP JSON schemas, and the custom theme validates against the
  official report-theme schema (August 2026 build, exploration version 5.76).
- **Semantic validation** — `verify_pbip.py` runs 2,002 checks for the failure
  modes a schema cannot see: every field reference resolving to a real table,
  column or measure; measures wrapped as `Measure` and columns as `Column`;
  every measure attributed to the table that actually owns it; no ambiguous
  relationship paths; no measure sharing a name with a column on its own
  table (Tabular refuses to build the model); page and visual folder names
  matching their `name`
  properties and the `[\w-]{1,50}` rule Power BI silently enforces; visuals
  inside the canvas; partition column counts matching the CSVs; UTF-8 without
  BOM.

File formats and visual type identifiers were taken from Microsoft's own
published JSON schemas and from real Desktop-written PBIP sample projects,
not from memory.

That said, schema conformance is necessary but not sufficient. If something
does misbehave, the most likely candidates are the three AI visuals and the
classic `map` visual (Microsoft is steering people toward Azure Map; swap it if
your build objects). Deleting a single misbehaving visual costs nothing — the
model and the other 111 visuals are independent of it.
