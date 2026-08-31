#!/usr/bin/env python3
"""
Renders the page spec in pbip_pages.py into PBIR report files.

Formats and $schema versions are copied from a real Power BI Desktop save
(Feb 2025 build: report/1.2.0 + page/1.3.0 + visualContainer/1.5.0), which is
old enough that any current Desktop opens it and new enough to carry
everything used here. Verified against Microsoft's published JSON schemas.
"""

import hashlib
import re

SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/"
S_VISUAL = SCHEMA + "item/report/definition/visualContainer/1.5.0/schema.json"
S_PAGE = SCHEMA + "item/report/definition/page/1.3.0/schema.json"
S_PAGES = SCHEMA + "item/report/definition/pagesMetadata/1.0.0/schema.json"
S_REPORT = SCHEMA + "item/report/definition/report/1.2.0/schema.json"
S_VERSION = SCHEMA + "item/report/definition/versionMetadata/1.0.0/schema.json"

# Visual kind -> visualType id. Checked against Microsoft's report theme
# schema (whose visualStyles keys are the visual type ids) and against 486
# real visual.json files from Microsoft's own sample reports in PBIR form.
VISUAL_TYPE = {
    "card": "card",
    "multiRowCard": "multiRowCard",
    "kpi": "kpi",
    "barChart": "barChart",                       # stacked bar
    "columnChart": "columnChart",                 # stacked column
    "clusteredBarChart": "clusteredBarChart",
    "clusteredColumnChart": "clusteredColumnChart",
    "lineChart": "lineChart",
    "areaChart": "areaChart",
    "lineClusteredColumnComboChart": "lineClusteredColumnComboChart",
    "pieChart": "pieChart",
    "donutChart": "donutChart",
    "treemap": "treemap",
    "funnel": "funnel",
    "gauge": "gauge",
    "waterfallChart": "waterfallChart",
    "ribbonChart": "ribbonChart",
    "scatterChart": "scatterChart",
    "map": "map",
    "tableEx": "tableEx",                         # Table
    "pivotTable": "pivotTable",                   # Matrix
    "slicer": "slicer",
    "textbox": "textbox",
    "narrative": "aiNarratives",                  # Smart narrative
    "keyDrivers": "keyDriversVisual",             # Key influencers
    "decompositionTree": "decompositionTreeVisual",
}

FIELD_RE = re.compile(r"^(\w+)\[(.+)\]$")
NAME_OK = re.compile(r"^[\w-]{1,50}$")


def vname(*parts):
    """20 hex chars, matching Desktop's own visual naming."""
    return hashlib.md5("|".join(map(str, parts)).encode()).hexdigest()[:20]


def lit(value):
    """A Power BI literal expression. Strings carry inner single quotes."""
    if isinstance(value, bool):
        v = "true" if value else "false"
    elif isinstance(value, int):
        v = f"{value}L"
    elif isinstance(value, float):
        v = f"{value}D"
    else:
        v = "'" + str(value).replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": v}}}


def card(**props):
    """One formatting card -> [{"properties": {...}}]"""
    return [{"properties": {k: lit(v) for k, v in props.items()}}]


def field_expr(field, measure_home):
    """'Table[col]' or '[Measure]' -> (fieldJson, queryRef, nativeRef)."""
    if field.startswith("["):
        prop = field[1:-1]
        entity = measure_home.get(prop)
        if entity is None:
            raise KeyError(f"measure not found in model: {prop}")
        return ({"Measure": {"Expression": {"SourceRef": {"Entity": entity}},
                             "Property": prop}},
                f"{entity}.{prop}", prop)
    m = FIELD_RE.match(field)
    entity, prop = m.group(1), m.group(2)
    return ({"Column": {"Expression": {"SourceRef": {"Entity": entity}},
                        "Property": prop}},
            f"{entity}.{prop}", prop)


def build_visual(page, index, v, measure_home):
    kind = v["kind"]
    name = vname(page.name, index, kind)
    opts = v["opts"]

    visual = {"visualType": VISUAL_TYPE[kind]}
    objects = {}
    container = {}

    if kind == "textbox":
        runs = [{"value": opts["heading"],
                 "textStyle": {"fontFamily": "Segoe UI Semibold",
                               "fontSize": "20pt",
                               "color": opts.get("accent", "#252423")}}]
        paragraphs = [{"textRuns": runs}]
        if opts.get("sub"):
            paragraphs.append({"textRuns": [{
                "value": opts["sub"],
                "textStyle": {"fontFamily": "Segoe UI", "fontSize": "10pt",
                              "color": "#605E5C"}}]})
        objects["general"] = [{"properties": {"paragraphs": paragraphs}}]
        container["title"] = card(show=False)
        container["background"] = card(show=False)
    else:
        # aiNarratives binds no fields - it summarises the rest of the page.
        if v["roles"]:
            query_state = {}
            used_native = set()
            for role, fields in v["roles"].items():
                projections = []
                for f in fields:
                    fj, qref, native = field_expr(f, measure_home)
                    n = native
                    i = 1
                    while n in used_native:
                        n = f"{native}{i}"
                        i += 1
                    used_native.add(n)
                    projections.append({"field": fj, "queryRef": qref,
                                        "nativeQueryRef": n})
                query_state[role] = {"projections": projections}
            visual["query"] = {"queryState": query_state}

        if kind == "slicer":
            objects["data"] = card(mode=opts.get("mode", "Dropdown"))
            objects["header"] = card(show=True, text=opts.get("title", ""))
            container["title"] = card(show=False)
        elif opts.get("title"):
            container["title"] = card(show=True, text=opts["title"])

        if kind == "decompositionTree":
            objects["analysis"] = card(aiEnabled=True)
        if kind == "narrative":
            # Skip the "pick what to summarise" prompt so the narrative writes
            # itself from the rest of the page on first open.
            objects["narrativeSelection"] = card(dismissSelectionScreen=True)

    if objects:
        visual["objects"] = objects
    if container:
        visual["visualContainerObjects"] = container
    visual["drillFilterOtherVisuals"] = True

    assert NAME_OK.match(name), f"bad visual name {name}"
    return name, {
        "$schema": S_VISUAL,
        "name": name,
        "position": {"x": v["x"], "y": v["y"], "z": index * 1000,
                     "height": v["h"], "width": v["w"],
                     "tabOrder": index * 1000},
        "visual": visual,
    }


def build_page(page, measure_home):
    assert NAME_OK.match(page.name), f"bad page name {page.name}"
    visuals = [build_visual(page, i, v, measure_home)
               for i, v in enumerate(page.visuals)]
    page_json = {
        "$schema": S_PAGE,
        "name": page.name,
        "displayName": page.display,
        "displayOption": "FitToPage",
        "height": 720,
        "width": 1280,
    }
    return page_json, visuals


def build_report(pages, model, custom_theme_file, base_theme="CY24SU10"):
    measure_home = {}
    for t in model["model"]["tables"]:
        for m in t.get("measures", []):
            measure_home[m["name"]] = t["name"]

    report_json = {
        "$schema": S_REPORT,
        "themeCollection": {
            "baseTheme": {"name": base_theme, "reportVersionAtImport": "5.61",
                          "type": "SharedResources"},
            "customTheme": {"name": custom_theme_file,
                            "reportVersionAtImport": "5.61",
                            "type": "RegisteredResources"},
        },
        "layoutOptimization": "None",
        "resourcePackages": [
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": custom_theme_file, "path": custom_theme_file,
                        "type": "CustomTheme"}]},
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": base_theme,
                        "path": f"BaseThemes/{base_theme}.json",
                        "type": "BaseTheme"}]},
        ],
        "settings": {
            "useStylableVisualContainerHeader": True,
            "defaultDrillFilterOtherVisuals": True,
            "allowChangeFilterTypes": True,
            "useEnhancedTooltips": True,
        },
    }
    pages_json = {
        "$schema": S_PAGES,
        "pageOrder": [p.name for p in pages],
        "activePageName": pages[0].name,
    }
    version_json = {"$schema": S_VERSION, "version": "2.0.0"}
    built = [build_page(p, measure_home) for p in pages]
    return report_json, pages_json, version_json, built
