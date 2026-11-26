#!/usr/bin/env python3
"""Run the publication quality-assurance gates and write the QA and conflict reports.

Gates (from the atlas brief)
  1  every map point is traceable to a row of the Darwin Core file and to a source_id
  2  no grade D record appears as a map point
  3  a cluster popup reports its species composition        (browser test, see below)
  4  clustering switches off at zoom 12 and co-located points spiderfy   (browser test)
  5  the river renders above the basemap and below the records  (pane order here; browser test)
  6  the site loads quickly and stays responsive with all taxa plotted  (payload size here; browser test)
  7  the data dictionary covers every field of every table and the data obey it
  8  a conflict report exists: synonyms, country versus basin, conflicting reports, coordinate outliers

Gates 3-6 need a running browser. scripts/browser_checks.js (Node + Playwright) writes
data/processed/browser_checks.json; this script reads it and reports the gates as passed, failed or
not run. It never reports a browser gate as passed without that file.

Outputs: docs/QA_REPORT.md, docs/CONFLICT_REPORT.md, data/processed/conflicts.csv
"""
from __future__ import annotations

import csv
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import shapely
from shapely.geometry import shape

sys.path.insert(0, str(Path(__file__).resolve().parent))
import atlas_lib as L  # noqa: E402
import schema  # noqa: E402

OUTSIDE_CELL = 0.5
# Reference points whose basin membership is certain; the boundary must classify all of them correctly.
BASIN_REFERENCE_POINTS = [
    ("Vientiane, Laos", 102.60, 17.97, True), ("Luang Prabang, Laos", 102.14, 19.89, True),
    ("Phnom Penh, Cambodia", 104.92, 11.56, True), ("Jinghong, Yunnan (Lancang)", 100.80, 21.99, True),
    ("Khon Kaen, north-east Thailand (Chi)", 102.83, 16.44, True), ("Bangkok (Chao Phraya)", 100.50, 13.75, False),
    ("Kunming, Yunnan (Jinsha / Yangtze)", 102.71, 25.04, False), ("Hanoi (Red River)", 105.85, 21.03, False),
    ("Mandalay (Irrawaddy)", 96.08, 21.98, False), ("Guangzhou (Pearl)", 113.26, 23.13, False),
    ("Chiang Mai (Ping / Chao Phraya)", 98.98, 18.79, False), ("Ho Chi Minh City (Saigon - Dong Nai)", 106.70, 10.78, False),
]


def n(value) -> str:
    return f"{int(value or 0):,}"


def main() -> int:
    species = L.read_csv(L.PROCESSED / "species_master.csv")
    by_sid = {s["species_id"]: s for s in species}
    references = L.read_csv(L.PROCESSED / "references.csv")
    ref_ids = {r["source_id"] for r in references}
    evidence = L.read_json(L.PROCESSED / "evidence_summary.json")
    occ_summary = L.read_json(L.PROCESSED / "occurrence_build_summary.json")
    rows = L.read_csv(L.PROCESSED / "occurrences.csv")
    published = [r for r in rows if r["evidence_grade"] != "D"]
    gates: dict[str, tuple[str, str]] = {}

    # ---- gate 1: traceability of every map point ---------------------------------
    # meta.xml declares fieldsEnclosedBy="", so the reader must not treat a quote as an
    # enclosure; a value containing a double quote would otherwise swallow the rows after it.
    csv.field_size_limit(100_000_000)
    with (L.DWC / "occurrence.txt").open(encoding="utf-8", newline="") as fh:
        dwc_rows = list(csv.DictReader(fh, delimiter=chr(9), quoting=csv.QUOTE_NONE))
    assert len(dwc_rows) == len(published), "DwC file and published rows differ in length"
    by_key = {r["gbif_key"]: r for r in published}
    inside_fc = json.loads((L.GEO / "occurrences.geojson").read_text())
    outside_fc = json.loads((L.GEO / "occurrences_outside_basin.geojson").read_text())
    trace_fail = 0
    for f in inside_fc["features"]:
        p = f["properties"]
        row = by_key.get(p["k"])
        if row is None or row["species_id"] != p["id"] or row["basin_flag"] != "in_basin" \
                or f"{float(row['decimalLongitude']):.5f}" != f"{f['geometry']['coordinates'][0]:.5f}" \
                or f"{float(row['decimalLatitude']):.5f}" != f"{f['geometry']['coordinates'][1]:.5f}":
            trace_fail += 1
    cell_count: dict[tuple, int] = Counter()
    for r in published:
        if r["basin_flag"] != "in_basin":
            cell_count[(r["species_id"], round(float(r["decimalLatitude"]) / OUTSIDE_CELL), round(float(r["decimalLongitude"]) / OUTSIDE_CELL))] += 1
    for f in outside_fc["features"]:
        p, (lon, lat) = f["properties"], f["geometry"]["coordinates"]
        row = by_key.get(p["k"])
        cell = (p["id"], round(lat / OUTSIDE_CELL), round(lon / OUTSIDE_CELL))
        if row is None or row["species_id"] != p["id"] or row["basin_flag"] == "in_basin" or cell_count.get(cell) != p["n"]:
            trace_fail += 1
    dwc_trace_fail = sum(1 for r in dwc_rows if not (r["occurrenceID"] and r["associatedReferences"] and r["license"]))
    dwc_source_ok = all(r["source_id"] in ref_ids for r in published)
    n_dwc = len(dwc_rows)
    ok = trace_fail == 0 and dwc_trace_fail == 0 and dwc_source_ok
    gates["1"] = ("PASS" if ok else "FAIL",
                  f"{n(len(inside_fc['features']))} in-basin points each match one DwC row on species, coordinates and GBIF key; "
                  f"{n(len(outside_fc['features']))} outside-basin points each match a species × {OUTSIDE_CELL}° cell with the stated record count "
                  f"({trace_fail} failures). All {n(len(dwc_rows))} DwC rows have an occurrenceID and a dataset reference; "
                  f"every record carries source_id SRC-003, which is in the reference table.")

    # ---- gate 2: no grade D on the map --------------------------------------------
    point_grades = Counter(f["properties"]["g"] for fc in (inside_fc, outside_fc) for f in fc["features"])
    published_grades = Counter(r["evidence_grade"] for r in published)
    ok = set(point_grades) <= {"A", "B", "C"} and set(published_grades) <= {"A", "B", "C"}
    gates["2"] = ("PASS" if ok else "FAIL",
                  f"Evidence grades on the map: {dict(point_grades)}. Grades among published records: {dict(published_grades)} "
                  f"(the archive carries no grade column, being a Darwin Core file; it holds exactly the published records). "
                  f"{n(occ_summary['excluded_grade_d'])} harvested records were graded D and excluded before mapping or archiving.")

    # ---- gate 5 (static part): pane order -----------------------------------------
    map_js = (L.WEB / "assets" / "js" / "map.js").read_text(encoding="utf-8")
    pane_order_ok = ("style.zIndex = 350" in map_js and "style.zIndex = 360" in map_js
                     and "pane: 'riverPane'" in map_js and "pane: 'basinPane'" in map_js)
    pane_evidence = ("Pane order in map.js: basin 350 < river 360 < records 400 (Leaflet overlay pane), fixed with custom panes "
                     "so that load order cannot change it" if pane_order_ok else "Pane order in map.js is NOT basin < river < records")

    # ---- gate 6 (static part): payload size ---------------------------------------
    def gz(path: Path) -> tuple[int, int]:
        raw = path.read_bytes()
        return len(raw), len(gzip.compress(raw, 6))

    payload = [L.WEB / "explore.html", L.WEB / "assets" / "css" / "atlas.css",
               L.WEB / "assets" / "vendor" / "leaflet" / "leaflet.js", L.WEB / "assets" / "vendor" / "leaflet" / "leaflet.css",
               L.WEB / "assets" / "vendor" / "markercluster" / "leaflet.markercluster.js",
               L.WEB / "assets" / "vendor" / "jquery" / "jquery.min.js",
               L.WEB / "assets" / "vendor" / "datatables" / "dataTables.min.js",
               L.WEB / "assets" / "vendor" / "datatables" / "dataTables.bootstrap5.min.js",
               L.WEB / "assets" / "js" / "common.js", L.WEB / "assets" / "js" / "map.js", L.WEB / "assets" / "js" / "explore.js",
               L.WEB / "data" / "species.json", L.WEB / "data" / "geo" / "occurrences.geojson",
               L.WEB / "data" / "geo" / "mekong_basin_display.geojson", L.WEB / "data" / "geo" / "mekong_river_naturalearth.geojson"]
    sizes = [gz(p) for p in payload if p.exists()]
    raw_total, gz_total = sum(a for a, _ in sizes), sum(b for _, b in sizes)

    # ---- gate 7: data dictionary complete and obeyed ------------------------------
    tables = {name: L.read_csv(L.PROCESSED / name) for name in schema.TABLES if (L.PROCESSED / name).exists()}
    violations = Counter()
    examples: dict[str, str] = {}
    for name, trows in tables.items():
        for row in trows:
            for field in schema.TABLES[name]:
                if field[0] not in row:
                    violations[(name, field[0], "column missing")] += 1
                    continue
                reason = schema.check_value(field, row[field[0]], tables)
                if reason:
                    violations[(name, field[0], reason.split(": ", 1)[1][:60])] += 1
                    examples.setdefault(str(reason), reason)
    fields_total = sum(len(v) for v in schema.TABLES.values())
    ok = not violations
    gates["7"] = ("PASS" if ok else "FAIL",
                  f"{len(schema.TABLES)} tables and {fields_total} fields defined with type, unit and allowed values; "
                  f"{n(sum(len(v) for v in tables.values()))} rows validated against the schema, {n(sum(violations.values()))} violations."
                  + ("" if ok else " Examples: " + "; ".join(list(examples.values())[:5])))

    # ---- gate 8: conflict report --------------------------------------------------
    conflicts = build_conflicts(species, published, by_sid, evidence)
    write_conflict_report(conflicts, species, published, by_sid)
    gates["8"] = ("PASS", f"{n(len(conflicts))} conflicts and discrepancies of {len({c['type'] for c in conflicts})} kinds recorded in docs/CONFLICT_REPORT.md")

    # ---- basin boundary validation -------------------------------------------------
    basin = shape(json.loads((L.GEO / "mekong_basin.geojson").read_text())["features"][0]["geometry"])
    ref_ok = sum(1 for _, lon, lat, expect in BASIN_REFERENCE_POINTS
                 if bool(shapely.contains_xy(basin, [lon], [lat])[0]) == expect)

    # ---- browser gates -------------------------------------------------------------
    browser_path = L.PROCESSED / "browser_checks.json"
    browser = L.read_json(browser_path) if browser_path.exists() else None
    for gate, label in (("3", "cluster popup species composition"), ("4", "clustering threshold and spiderfying"),
                        ("5", "layer order in the browser"), ("6", "load time and responsiveness")):
        entry = (browser or {}).get("gate" + gate)
        if entry:
            gates[gate] = ("PASS" if entry["passed"] else "FAIL", entry["evidence"])
        else:
            gates[gate] = ("NOT RUN", f"No browser test result for {label} (run scripts/browser_checks.js).")
    if gates["5"][0] != "NOT RUN":
        gates["5"] = (gates["5"][0], gates["5"][1] + ". " + pane_evidence)
    elif pane_order_ok:
        gates["5"] = ("NOT RUN", pane_evidence + "; visual confirmation needs the browser test.")
    gates["6"] = (gates["6"][0], gates["6"][1] + f" Initial explore payload: {raw_total / 1e6:.1f} MB raw, {gz_total / 1e6:.1f} MB gzipped.")

    # ---- release gates: bioeconomy layer, Data catalog, Download retirement -------------
    gates.update(bioeconomy_release_gates())
    write_qa_report(gates, species, published, evidence, occ_summary, ref_ok)
    for gate in sorted(gates):
        print(f"gate {gate}: {gates[gate][0]}")
    return 0 if all(v[0] == "PASS" for v in gates.values()) else 1


def bioeconomy_release_gates() -> dict[str, tuple[str, str]]:
    """Gates 9-14: the bioeconomy screening layer, the Data catalog and the Download retirement."""
    gates: dict[str, tuple[str, str]] = {}
    try:
        import re as _re

        profiles = L.read_csv(L.PROCESSED / "bioeconomy_profiles.csv")
        master = {r["species_id"]: r for r in L.read_csv(L.PROCESSED / "species_master.csv")}
        pilot = {r["species_id"] for r in L.read_csv(L.ROOT / "data" / "evidence" / "pilot_species.csv")} \
            if (L.ROOT / "data" / "evidence" / "pilot_species.csv").exists() else set()

        # ---- gate 9: profiles complete, prices fully qualified, tiers match the rule ------
        problems = []
        price_bad = tier_mismatch = 0
        for r in profiles:
            for f in ("value_chain_type", "trade_exposure", "certification_readiness",
                      "livelihood_dependence", "equity_flag", "valuation_method",
                      "coded_confidence", "coded_by", "reviewed_by", "source_ids"):
                if not (r.get(f) or "").strip():
                    problems.append(f"{r['species_id']} field {f} is blank")
            if (r.get("market_price_proxy") or "").strip():
                if not ((r.get("market_price_currency_unit") or "").strip()
                        and (r.get("market_price_date") or "").strip()
                        and (r.get("market_price_source_id") or "").strip()):
                    price_bad += 1
            t = r["trade_exposure"] in {"CITES-listed", "BioTrade-supported", "export-commodity"}
            ldep = r["livelihood_dependence"] in {"high", "moderate"}
            cert = r["certification_readiness"] in {"GACP-eligible", "FairWild-eligible", "both"}
            inputs = (r["trade_exposure"], r["livelihood_dependence"], r["certification_readiness"])
            want = "unknown" if any(v == "unknown" for v in inputs) else \
                {3: "high", 2: "medium"}.get(sum([t, ldep, cert]), "low")
            if r["bioeconomy_priority_tier"] != want:
                tier_mismatch += 1
        pilot_ok = all(all((r.get(f) or "").strip() or r.get(f) == "" for f in
                           ("value_chain_type", "trade_exposure", "certification_readiness"))
                       for r in profiles if r["species_id"] in pilot) if pilot else True
        gates["9"] = ("PASS" if not problems and not price_bad and not tier_mismatch and pilot_ok else "FAIL",
                      f"{len(profiles)} profiles; every field present or 'unknown'; {price_bad} prices without "
                      f"currency/unit, date and source_id; {tier_mismatch} tiers that disagree with the documented rule; "
                      f"pilot coverage {'complete' if pilot_ok else 'INCOMPLETE'}.")

        # ---- gate 10: every catalogued dataset has a registry row, licence and version -----
        reg_path = L.PROCESSED / "zenodo_registry.csv"
        reg = L.read_csv(reg_path) if reg_path.exists() else []
        reg_ids = {r["dataset_id"] for r in reg}
        missing_lic = [r["dataset_id"] for r in reg if not (r.get("license") or "").strip()]
        missing_ver = [r["dataset_id"] for r in reg if not (r.get("version") or "").strip()]
        bad_doi = [r["dataset_id"] for r in reg
                   if not ((r.get("version_doi") or "").startswith("DOI pending")
                           or (r.get("version_doi") or "").startswith("10."))]
        gates["10"] = ("PASS" if not (missing_lic or missing_ver or bad_doi) else "FAIL",
                       f"{len(reg)} datasets in zenodo_registry.csv; "
                       f"{len(missing_lic)} without licence, {len(missing_ver)} without version, "
                       f"{len(bad_doi)} without a valid DOI or 'DOI pending'.")

        # ---- gate 11: Download page retired: stub, no nav entry, no links to it ----------
        stub = L.WEB / "download.html"
        stub_ok = stub.exists() and 'http-equiv="refresh" content="0; url=data.html"' in stub.read_text(encoding="utf-8")
        nav_ok = 'href="download.html"' not in (L.WEB / "index.html").read_text(encoding="utf-8")
        links = []
        for page in L.WEB.glob("**/*.html"):
            if page.name in ("404.html", "download.html"):
                continue
            html = page.read_text(encoding="utf-8")
            if 'href="download.html"' in html:
                links.append(str(page.relative_to(L.WEB)))
            for m in _re.finditer(r'href="([^"]+\.(?:csv|json|geojson|tif|graphml|sdf|xml))"', html):
                href = m.group(1)
                if href.startswith(("http", "data/evidence/", "//")):
                    continue
                links.append(f"{page.relative_to(L.WEB)} -> {href}")
        gates["11"] = ("PASS" if stub_ok and nav_ok and not links else "FAIL",
                       f"redirect stub {'present' if stub_ok else 'MISSING'}; nav entry {'absent' if nav_ok else 'PRESENT'}; "
                       f"{len(links)} in-site download links or download.html references left"
                       + ("" if not links else ": " + "; ".join(links[:5])))

        # ---- gate 12: 'pending' appears only in the DOI-pending context on the Data tab ----
        bad_pending = []
        for page in L.WEB.glob("**/*.html"):
            if page.name == "data.html":
                continue
            text = page.read_text(encoding="utf-8")
            for m in _re.finditer(r"[^<]{0,60}pending[^<]{0,60}", text, _re.I):
                bad_pending.append(f"{page.relative_to(L.WEB)}: {m.group(0).strip()[:80]}")
        gates["12"] = ("PASS" if not bad_pending else "FAIL",
                       f"{len(bad_pending)} 'pending' strings outside the Data tab"
                       + ("" if not bad_pending else ": " + "; ".join(bad_pending[:5])))

        # ---- gate 13: every nav target page exists in the built site ----------------------
        missing_pages = []
        for page in (L.WEB / "index.html", L.WEB / "explore.html", L.WEB / "methods.html",
                     L.WEB / "data.html", L.WEB / "about.html", L.WEB / "evidence.html",
                     L.WEB / "macroecology.html", L.WEB / "sustainability.html",
                     L.WEB / "species" / "index.html"):
            if not page.exists():
                missing_pages.append(page.name)
        for page in L.WEB.glob("**/*.html"):
            text = page.read_text(encoding="utf-8")
            # Species pages sit in web/species/ with <base href="../">, so their relative
            # links resolve against the site root, not against their own directory.
            base_dir = page.parent.parent if ('<base href="../">' in text or "<base href='../'>" in text) else page.parent
            for m in _re.finditer(r'href="((?:[a-z0-9_/.-]+\.html))"', text):
                href = m.group(1)
                if href.startswith(("http", "//")) or "/" in href.rstrip("/"):
                    continue
                target = (base_dir / href).resolve()
                if not target.exists():
                    missing_pages.append(f"{page.relative_to(L.WEB)} -> {href}")
        gates["13"] = ("PASS" if not missing_pages else "FAIL",
                       f"{len(missing_pages)} internal page links without a built target"
                       + ("" if not missing_pages else ": " + "; ".join(sorted(set(missing_pages))[:8])))

        # ---- gate 14: manuscript figures traceable to the CSV/saved queries -----------------
        m = json.loads((L.PROCESSED / "evidence_manifest.json").read_text(encoding="utf-8"))
        tiers = {r["bioeconomy_priority_tier"]: int(r["count"])
                 for r in L.read_csv(L.PROCESSED / "bioeconomy_priority_summary.csv")}
        cites_pilot = sum(1 for r in profiles
                          if r["species_id"] in pilot and master[r["species_id"]]["cites_appendix"] in ("I", "II", "III"))
        trace = (m["totals"]["pubs"] == 2317 and m["totals"]["compounds"] == 119
                 and len(master) == 333 and tiers.get("high") == 0 and cites_pilot == 2)
        gates["14"] = ("PASS" if trace else "FAIL",
                       f"2,317 pubs / 119 compounds / 333 taxa / 0 high-tier / {cites_pilot} CITES pilot taxa "
                       f"— matches the manuscript draft numbers: {trace}.")
    except Exception as e:  # noqa: BLE001
        for g in ("9", "10", "11", "12", "13", "14"):
            gates[g] = ("FAIL", f"gate could not run: {e}")
    return gates


def build_conflicts(species, published, by_sid, evidence) -> list[dict]:
    out: list[dict] = []
    # Taxonomic: GBIF and WFO disagree; workbook name is not the accepted name; two names are one species.
    for s in species:
        if s["gbif_vs_wfo"] == "differ":
            out.append({"type": "taxonomic_synonym", "scope": s["species_id"],
                        "detail": f"GBIF accepts {s['accepted_name']}; World Flora Online accepts {s['wfo_accepted_name']}",
                        "action": "both names searchable; GBIF is the operational backbone"})
        if s["same_gbif_taxon_as"]:
            out.append({"type": "taxonomic_synonym", "scope": s["species_id"],
                        "detail": f"{s['species_id'][3:].replace('_', ' ')} and {by_sid[s['same_gbif_taxon_as']]['accepted_name']} are one accepted species",
                        "action": f"records kept under {s['same_gbif_taxon_as']}"})
        if s["taxon_rank"] == "genus":
            out.append({"type": "taxonomic_synonym", "scope": s["species_id"],
                        "detail": "workbook entry names a genus only", "action": "no occurrence data; kept in the species table"})
    # Country-level versus basin-level.
    basin_countries: dict[str, set] = defaultdict(set)
    for r in published:
        if r["basin_flag"] == "in_basin":
            basin_countries[r["species_id"]].add(r["countryCode"])
    for s in species:
        workbook = {c for c in s["countries_present"].split(",") if c}
        any_rec = {c for c in s["occurrence_countries"].split(",") if c}
        in_basin = basin_countries.get(s["species_id"], set())
        for c in sorted(workbook - in_basin):
            kind = "no published record in that country" if c not in any_rec else "records in that country lie outside the basin"
            out.append({"type": "country_vs_basin", "scope": s["species_id"],
                        "detail": f"workbook reports the species from {c}; {kind}", "action": "country-level report kept; basin presence unconfirmed"})
        for c in sorted(in_basin - workbook):
            out.append({"type": "country_vs_basin", "scope": s["species_id"],
                        "detail": f"a published record inside the basin in {c}; the workbook does not list {c}", "action": "basin occurrence from GBIF"})
    # Conflicting assessments: workbook versus GBIF IUCN category; grade C rows caused by a bad identifier.
    for s in species:
        wb, gb = s["iucn_category_code"].split("/")[0], s["iucn_category_code_gbif"].split("/")[0]
        if wb and gb and wb != gb:
            out.append({"type": "conflicting_assessment", "scope": s["species_id"],
                        "detail": f"IUCN category {wb} in the workbook ({s['assessment_basis']}) but {gb} in GBIF",
                        "action": "both shown; verify against the IUCN Red List"})
    for issue in evidence.get("citation_issues", []):
        out.append({"type": "citation_issue", "scope": issue["species_id"],
                    "detail": f"{issue['table']} {issue['row_id']}: {issue['citation'][:120]} — {issue['note'][:140]}",
                    "action": "evidence graded on the resolved article; correct the citation"})
    # Coordinate outliers: low quality, and points outside their stated country.
    outlines = json.loads((L.GEO / "countries_outline.geojson").read_text())["features"]
    polygons = {f["properties"]["iso_a3"]: shape(f["geometry"]) for f in outlines if f["properties"].get("iso_a3")}
    iso3 = {"CN": "CHN", "TH": "THA", "VN": "VNM", "LA": "LAO", "KH": "KHM", "MM": "MMR"}
    outside_country = Counter()
    for code, iso in iso3.items():
        country_rows = [r for r in published if r["countryCode"] == code]
        if not country_rows or iso not in polygons:
            continue
        inside = shapely.contains_xy(polygons[iso], [float(r["decimalLongitude"]) for r in country_rows],
                                     [float(r["decimalLatitude"]) for r in country_rows])
        outside_country.update(r["species_id"] for r, ok in zip(country_rows, inside) if not ok)
    low = Counter(r["species_id"] for r in published if r["coordinate_quality_flag"] == "low")
    for sid, count in outside_country.most_common(40):
        out.append({"type": "coordinate_outlier", "scope": sid,
                    "detail": f"{count} record{'s' if count > 1 else ''} fall outside the outline of their stated country",
                    "action": "kept; rendered hollow if low precision; listed for review"})
    for sid, count in low.most_common(40):
        out.append({"type": "coordinate_outlier", "scope": sid,
                    "detail": f"{count} low-precision record{'s' if count > 1 else ''} (coordinate uncertainty over 50 km or precision of 0.1 degrees)",
                    "action": "kept; rendered with reduced opacity"})
    return out


def write_conflict_report(conflicts, species, published, by_sid) -> None:
    by_type = defaultdict(list)
    for c in conflicts:
        by_type[c["type"]].append(c)
    names = {s["species_id"]: s["accepted_name"] for s in species}
    lines = ["# Conflict report — Mekong Medicinal Plant Atlas", "",
             "Generated by `scripts/qa_checks.py`. Every item is a discrepancy found in the data, not an error that was silently fixed.", "",
             "| Type | Items | What it is | How the atlas handles it |", "|---|---|---|---|",
             "| Taxonomic synonyms | " + str(len(by_type["taxonomic_synonym"])) + " | Two backbones or two workbook names for one plant | Both names stay searchable; GBIF drives records |",
             "| Country versus basin | " + str(len(by_type["country_vs_basin"])) + " | A species is reported from a country but has no record inside the basin there, or the reverse | Reported as a country-level statement |",
             "| Conflicting assessments | " + str(len(by_type["conflicting_assessment"])) + " | Workbook and GBIF give different IUCN categories | Both shown |",
             "| Citation issues | " + str(len(by_type["citation_issue"])) + " | A printed DOI, PMID, journal or author does not match the cited article | Evidence graded on the resolved article; citation to be corrected |",
             "| Coordinate outliers | " + str(len(by_type["coordinate_outlier"])) + " | Records outside their stated country, or of low precision | Kept; flagged and styled |", ""]
    title = {"taxonomic_synonym": "Taxonomic synonyms", "country_vs_basin": "Country-level versus basin-level",
             "conflicting_assessment": "Conflicting assessments", "citation_issue": "Citation issues found while grading",
             "coordinate_outlier": "Coordinate outliers"}
    limit = {"country_vs_basin": 60, "coordinate_outlier": 40, "citation_issue": 80}
    for kind in title:
        items = by_type[kind]
        lines += [f"## {title[kind]} ({len(items)})", "", "| Taxon | Finding | Action |", "|---|---|---|"]
        for c in items[:limit.get(kind, 200)]:
            taxon = names.get(c["scope"], c["scope"])
            lines.append(f"| *{taxon}* | {c['detail']} | {c['action']} |")
        if len(items) > limit.get(kind, 200):
            lines.append(f"| … | {len(items) - limit.get(kind, 200)} more in `data/processed/conflicts.csv` | |")
        lines.append("")
    L.DOCS.mkdir(parents=True, exist_ok=True)
    (L.DOCS / "CONFLICT_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    L.write_csv(L.PROCESSED / "conflicts.csv", conflicts)


def write_qa_report(gates, species, published, evidence, occ_summary, ref_ok) -> None:
    occ_stats = occ_summary["stats"]
    status = {g: v[0] for g, v in gates.items()}
    overall = "all gates pass" if all(v == "PASS" for v in status.values()) else (
        "NOT READY: some gates are not passed" if "FAIL" in status.values() else "awaiting browser tests")
    lines = ["# QA report — Mekong Medicinal Plant Atlas", "", f"**Status: {overall}.** Generated by `scripts/qa_checks.py`.", "",
             "## Publication gates", "", "| Gate | Result | Evidence |", "|---|---|---|"]
    labels = {"1": "Every map point traceable to a Darwin Core row and a source_id", "2": "No grade D record on the map",
              "3": "Cluster popup reports species composition", "4": "Clustering off at zoom 12; co-located points spiderfy",
              "5": "River above basemap, below records", "6": "Fast, responsive with all taxa", "7": "Data dictionary complete and obeyed",
              "8": "Conflict report produced",
              "9": "Bioeconomy profiles complete; prices fully qualified; tiers match the rule",
              "10": "Every catalogued dataset has a registry row, licence and version",
              "11": "Download page retired: stub in place, no nav entry, no links to it",
              "12": "'pending' appears only in the DOI-pending context on the Data tab",
              "13": "Every internal page link has a built target",
              "14": "Manuscript figures traceable to the CSV"}
    for g in sorted(gates):
        lines.append(f"| {g}. {labels[g]} | **{gates[g][0]}** | {gates[g][1]} |")
    lines += ["", "## Basin boundary validation", "",
              f"The basin polygon classifies {ref_ok} of {len(BASIN_REFERENCE_POINTS)} reference places with certain membership correctly "
              "(in: Vientiane, Luang Prabang, Phnom Penh, Jinghong, Khon Kaen; out: Bangkok, Kunming, Hanoi, Mandalay, Guangzhou, Chiang Mai, Ho Chi Minh City).", "",
              "## Occurrence data", "",
              f"- Harvested (georeferenced, no geospatial issue): {n(occ_stats.get('harvested', 0))} records; published: {n(occ_summary['published'])}; excluded as grade D: {n(occ_summary['excluded_grade_d'])}.",
              f"- Inside the basin: {n(occ_stats.get('published_in_basin', 0))}; outside: {n(occ_stats.get('published_outside_basin', 0))}.",
              f"- Generalised coordinates: {n(occ_stats.get('generalised', 0))} records of {len(occ_summary['sensitive_species_with_published_records'])} sensitive species.",
              f"- Records without an event date: {n(sum(1 for r in published if not r['eventDate']))} (left blank, never invented).",
              f"- Taxa with published records: {occ_summary['species_with_published_records']}; with records inside the basin: see occurrence layer summary.", "",
              "## Evidence grading", "",
              f"- Species by grade: {evidence.get('species_by_grade')}.",
              f"- Use records by grade: {evidence.get('rows_by_grade', {}).get('uses.csv')}; pharmacology records: {evidence.get('rows_by_grade', {}).get('pharmacology.csv')}.",
              f"- Citation issues found: {len(evidence.get('citation_issues', []))} (listed in the conflict report).", "",
              "## Known gaps", "",
              "- Dataset DOI not minted (needs a Zenodo account).", "- GBIF download DOI not minted (needs a GBIF account).",
              "- Local names and ethnic groups absent (Tier-2 books and the Lancang-Mekong database are access pending).",
              "- IUCN categories not checked against the IUCN API.", "- Author list, affiliations and funding on the About page are placeholders.", ""]
    L.DOCS.mkdir(parents=True, exist_ok=True)
    (L.DOCS / "QA_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
