#!/usr/bin/env python3
"""
Builds the CampusPulse Power BI project (PBIP) from the CSVs in ./data.

Output: ./powerbi/CampusPulse.pbip  + the .Report and .SemanticModel folders.
Open the .pbip in Power BI Desktop, set the DataFolder parameter to the folder
holding the CSVs, and refresh.

    python3 build_pbip.py

Stdlib only. Deterministic. Every JSON file is written UTF-8 without BOM,
which Power BI requires for externally edited PBIP files.
"""

import argparse
import hashlib
import json
import os
import shutil

import pbip_model
import pbip_pages
import pbip_report
import pbip_theme

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "powerbi")
PROJECT = "CampusPulse"
DEFAULT_DATA_FOLDER = r"C:\CampusPulse\data"
BASE_THEME = "CY24SU10"

SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/"
S_PBIP = SCHEMA + "pbip/pbipProperties/1.0.0/schema.json"
S_PBIR = SCHEMA + "item/report/definitionProperties/2.0.0/schema.json"
S_PBISM = SCHEMA + "item/semanticModel/definitionProperties/1.0.0/schema.json"
S_PLATFORM = SCHEMA + "gitIntegration/platformProperties/2.0.0/schema.json"


def stable_guid(*parts):
    h = hashlib.md5("|".join(map(str, parts)).encode()).hexdigest()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


written = []


def wjson(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # UTF-8 with no BOM, LF endings - required for hand-edited PBIP files.
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")
    written.append(path)


def platform(item_type, display):
    return {
        "$schema": S_PLATFORM,
        "metadata": {"type": item_type, "displayName": display},
        "config": {"version": "2.0",
                   "logicalId": stable_guid(PROJECT, item_type)},
    }


def find_base_theme():
    """Ship Microsoft's base theme alongside the report so the reference
    resolves without depending on the reader's Desktop build."""
    for root in ("/tmp/claude-0", "/home/user"):
        for dirpath, _, files in os.walk(root):
            if f"{BASE_THEME}.json" in files and "BaseThemes" in dirpath:
                return os.path.join(dirpath, f"{BASE_THEME}.json")
    return None


def main(out=OUT, data_folder=DEFAULT_DATA_FOLDER):
    global written
    written = []
    if os.path.isdir(out):
        shutil.rmtree(out)

    report_dir = os.path.join(out, f"{PROJECT}.Report")
    model_dir = os.path.join(out, f"{PROJECT}.SemanticModel")

    # ---------------------------------------------------------- semantic model
    print("Building semantic model...")
    model = pbip_model.build_model(default_folder=data_folder)
    # Power BI writes currency masks with an escaped dollar and a negative /
    # zero branch; match that so numbers format the same as a native report.
    for t in model["model"]["tables"]:
        for m in t.get("measures", []):
            fs = m.get("formatString", "")
            if fs.startswith("$"):
                body = fs[1:]
                m["formatString"] = f"\\${body};(\\${body});\\${body}"
        t["lineageTag"] = stable_guid("table", t["name"])
        for c in t["columns"]:
            c["lineageTag"] = stable_guid("col", t["name"], c["name"])
        for m in t.get("measures", []):
            m["lineageTag"] = stable_guid("measure", t["name"], m["name"])
    for e in model["model"].get("expressions", []):
        e["lineageTag"] = stable_guid("expr", e["name"])
        if isinstance(e.get("expression"), list) and len(e["expression"]) == 1:
            e["expression"] = e["expression"][0]
    model["compatibilityLevel"] = 1567
    model.pop("name", None)

    wjson(os.path.join(model_dir, "model.bim"), model)
    wjson(os.path.join(model_dir, "definition.pbism"),
          {"$schema": S_PBISM, "version": "4.2", "settings": {}})
    wjson(os.path.join(model_dir, ".platform"),
          platform("SemanticModel", PROJECT))

    n_meas = sum(len(t.get("measures", [])) for t in model["model"]["tables"])
    print(f"  {len(model['model']['tables'])} tables, "
          f"{len(model['model']['relationships'])} relationships, "
          f"{n_meas} measures")

    # ------------------------------------------------------------------ report
    print("Building report...")
    pages = pbip_pages.build_pages()
    report_json, pages_json, version_json, built = pbip_report.build_report(
        pages, model, pbip_theme.THEME_FILE, BASE_THEME)

    defn = os.path.join(report_dir, "definition")
    wjson(os.path.join(defn, "report.json"), report_json)
    wjson(os.path.join(defn, "version.json"), version_json)
    wjson(os.path.join(defn, "pages", "pages.json"), pages_json)

    n_vis = 0
    for page_json, visuals in built:
        pdir = os.path.join(defn, "pages", page_json["name"])
        wjson(os.path.join(pdir, "page.json"), page_json)
        for vis_name, vis_json in visuals:
            wjson(os.path.join(pdir, "visuals", vis_name, "visual.json"),
                  vis_json)
            n_vis += 1
    print(f"  {len(built)} pages, {n_vis} visuals")

    wjson(os.path.join(report_dir, "definition.pbir"),
          {"$schema": S_PBIR, "version": "4.0",
           "datasetReference": {"byPath": {
               "path": f"../{PROJECT}.SemanticModel"}}})
    wjson(os.path.join(report_dir, ".platform"), platform("Report", PROJECT))

    # -------------------------------------------------------------- resources
    theme_path = os.path.join(report_dir, "StaticResources",
                              "RegisteredResources", pbip_theme.THEME_FILE)
    wjson(theme_path, pbip_theme.build_theme())

    src = find_base_theme()
    dst = os.path.join(report_dir, "StaticResources", "SharedResources",
                       "BaseThemes", f"{BASE_THEME}.json")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if src:
        shutil.copyfile(src, dst)
        written.append(dst)
        print(f"  bundled base theme {BASE_THEME}")
    else:
        print(f"  WARNING: base theme {BASE_THEME}.json not found to bundle; "
              "Power BI will fall back to its built-in copy")

    # ------------------------------------------------------------- project file
    wjson(os.path.join(out, f"{PROJECT}.pbip"),
          {"$schema": S_PBIP, "version": "1.0",
           "artifacts": [{"report": {"path": f"{PROJECT}.Report"}}],
           "settings": {"enableAutoRecovery": True}})

    with open(os.path.join(out, ".gitignore"), "w", encoding="utf-8",
              newline="\n") as f:
        f.write("**/.pbi/localSettings.json\n**/.pbi/cache.abf\n")

    total = sum(os.path.getsize(p) for p in written)
    print(f"\nWrote {len(written)} files ({total/1024:.0f} KB) to {out}")
    print(f"  DataFolder default: {data_folder}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=OUT, help="output folder for the project")
    ap.add_argument("--data-folder", default=DEFAULT_DATA_FOLDER,
                    help="default value baked into the DataFolder parameter")
    a = ap.parse_args()
    main(a.out, a.data_folder)
