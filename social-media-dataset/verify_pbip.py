#!/usr/bin/env python3
"""
Checks the generated PBIP for the failure modes a JSON-schema check cannot see:
dangling field references, Column/Measure mix-ups, illegal page or visual names,
ambiguous relationship paths, and partitions that disagree with the CSVs.

    python3 verify_pbip.py

Exits non-zero if anything fails.
"""

import csv
import json
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "powerbi")
DATA = os.path.join(HERE, "data")
PROJECT = "CampusPulse"
NAME_RE = re.compile(r"^[\w-]{1,50}$")

problems = []
checks = 0


def check(ok, msg):
    global checks
    checks += 1
    if not ok:
        problems.append(msg)


def main():
    model = json.load(open(os.path.join(
        OUT, f"{PROJECT}.SemanticModel", "model.bim"), encoding="utf-8"))
    m = model["model"]

    columns = {t["name"]: {c["name"] for c in t["columns"]} for t in m["tables"]}
    measures = {}
    for t in m["tables"]:
        for meas in t.get("measures", []):
            check(meas["name"] not in measures,
                  f"duplicate measure name {meas['name']}")
            measures[meas["name"]] = t["name"]

    # ---- 1. measure DAX only references things that exist ------------------
    for t in m["tables"]:
        for meas in t.get("measures", []):
            for tbl, col in re.findall(r"(\w+)\[([^\]]+)\]", meas["expression"]):
                check(tbl in columns, f"{meas['name']}: unknown table {tbl}")
                if tbl in columns:
                    check(col in columns[tbl] or col in measures,
                          f"{meas['name']}: unknown column {tbl}[{col}]")
            for ref in re.findall(r"(?<![\w\]])\[([^\]]+)\]", meas["expression"]):
                check(ref in measures or any(ref in cs for cs in columns.values()),
                      f"{meas['name']}: unresolved reference [{ref}]")

    # ---- 2. relationships point at real columns ---------------------------
    for r in m["relationships"]:
        for side in ("from", "to"):
            t, c = r[f"{side}Table"], r[f"{side}Column"]
            check(t in columns, f"relationship {r['name']}: unknown table {t}")
            check(t in columns and c in columns[t],
                  f"relationship {r['name']}: unknown column {t}[{c}]")

    # ---- 3. no ambiguous filter paths -------------------------------------
    # An edge is traversable dim->fact always, and fact->dim only when the
    # relationship is bidirectional. Two distinct paths between the same pair
    # of tables is what Power BI rejects.
    adj = defaultdict(set)
    for r in m["relationships"]:
        f, t = r["fromTable"], r["toTable"]
        adj[t].add(f)                                    # one side filters many
        if r.get("crossFilteringBehavior") == "bothDirections":
            adj[f].add(t)

    def count_paths(src, dst, seen, depth=0):
        if depth > 6:
            return 0
        if src == dst:
            return 1
        total = 0
        for nxt in adj[src]:
            if nxt in seen:
                continue
            total += count_paths(nxt, dst, seen | {nxt}, depth + 1)
            if total > 1:
                return total
        return total

    tables = list(columns)
    for a in tables:
        for b in tables:
            if a == b:
                continue
            n = count_paths(a, b, {a})
            check(n <= 1, f"ambiguous filter path: {n} routes from {a} to {b}")

    # ---- 4. partitions agree with the CSV headers -------------------------
    for t in m["tables"]:
        expr = "\n".join(t["partitions"][0]["source"]["expression"])
        csv_path = os.path.join(DATA, f"{t['name']}.csv")
        check(os.path.exists(csv_path), f"missing CSV for table {t['name']}")
        if not os.path.exists(csv_path):
            continue
        header = next(csv.reader(open(csv_path, encoding="utf-8")))
        declared = int(re.search(r"Columns=(\d+)", expr).group(1))
        check(declared == len(header),
              f"{t['name']}: partition says {declared} columns, CSV has {len(header)}")
        check([c["name"] for c in t["columns"]] == header,
              f"{t['name']}: model columns do not match CSV header order")

    # ---- 5. report: names, folders, field references -----------------------
    defn = os.path.join(OUT, f"{PROJECT}.Report", "definition")
    pages_meta = json.load(open(os.path.join(defn, "pages", "pages.json"),
                                encoding="utf-8"))
    page_dirs = sorted(d for d in os.listdir(os.path.join(defn, "pages"))
                       if os.path.isdir(os.path.join(defn, "pages", d)))
    check(sorted(pages_meta["pageOrder"]) == page_dirs,
          "pageOrder does not match the page folders on disk")
    check(pages_meta["activePageName"] in pages_meta["pageOrder"],
          "activePageName is not in pageOrder")

    n_visuals = 0
    for pd in page_dirs:
        pdir = os.path.join(defn, "pages", pd)
        pj = json.load(open(os.path.join(pdir, "page.json"), encoding="utf-8"))
        check(pj["name"] == pd, f"page {pd}: name does not match folder")
        check(bool(NAME_RE.match(pd)), f"page {pd}: illegal folder name")

        vdir = os.path.join(pdir, "visuals")
        seen_names = set()
        for vd in sorted(os.listdir(vdir)):
            n_visuals += 1
            vj = json.load(open(os.path.join(vdir, vd, "visual.json"),
                                encoding="utf-8"))
            check(vj["name"] == vd, f"visual {vd}: name does not match folder")
            check(bool(NAME_RE.match(vd)), f"visual {vd}: illegal folder name")
            check(vd not in seen_names, f"visual {vd}: duplicate name on {pd}")
            seen_names.add(vd)

            pos = vj["position"]
            check(pos["x"] >= 0 and pos["y"] >= 0
                  and pos["x"] + pos["width"] <= 1280
                  and pos["y"] + pos["height"] <= 720,
                  f"visual {vd} on {pd}: outside the 1280x720 canvas")

            qs = vj["visual"].get("query", {}).get("queryState", {})
            for role, state in qs.items():
                natives = set()
                for proj in state["projections"]:
                    fld = proj["field"]
                    kind = next(iter(fld))
                    entity = fld[kind]["Expression"]["SourceRef"]["Entity"]
                    prop = fld[kind]["Property"]
                    where = f"{pd}/{vd} role {role}"
                    if kind == "Measure":
                        check(prop in measures, f"{where}: unknown measure {prop}")
                        check(measures.get(prop) == entity,
                              f"{where}: measure {prop} attributed to {entity}, "
                              f"it lives on {measures.get(prop)}")
                    elif kind == "Column":
                        check(entity in columns,
                              f"{where}: unknown table {entity}")
                        check(entity in columns and prop in columns[entity],
                              f"{where}: unknown column {entity}[{prop}]")
                        check(prop not in measures,
                              f"{where}: {prop} is a measure but wrapped as Column")
                    check(proj["nativeQueryRef"] not in natives,
                          f"{where}: duplicate nativeQueryRef "
                          f"{proj['nativeQueryRef']}")
                    natives.add(proj["nativeQueryRef"])

    # ---- 6. encoding: UTF-8, no BOM --------------------------------------
    for root, _, files in os.walk(OUT):
        for fn in files:
            p = os.path.join(root, fn)
            with open(p, "rb") as f:
                head = f.read(3)
            check(head != b"\xef\xbb\xbf", f"{p}: has a UTF-8 BOM")

    print(f"{checks} checks run over {len(m['tables'])} tables, "
          f"{len(measures)} measures, {len(page_dirs)} pages, "
          f"{n_visuals} visuals")
    if problems:
        print(f"\n{len(problems)} PROBLEM(S):")
        for p in problems[:40]:
            print("  -", p)
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
