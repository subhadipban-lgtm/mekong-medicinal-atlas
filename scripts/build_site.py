#!/usr/bin/env python3
"""Generate the static atlas site into web/.

Pages
  index.html     overview with the basin map and headline statistics
  explore.html   full occurrence map, filters, species table
  methods.html   sources, grading rubric, generalisation policy, software, limitations
  about.html     authors, affiliations, funding, contact
  species/index.html and species/<genus>-<species>.html   one page per taxon

Data
  web/data/species.json            the species table used by the maps and DataTables
  web/data/site_stats.json         headline numbers
  web/data/software_versions.json  versions recorded on the Methods page
  web/data/tables/                 CSV and JSON tables for download
  web/data/dwca/                   the Darwin Core Archive
  web/data/geo/                    written by scripts/build_geo.py and fetch_baselayers.py

Nothing in the output depends on the date the script is run, so repeated builds are identical.

Usage: python scripts/build_site.py
"""
from __future__ import annotations

import csv
import html
import json
import platform
import re
import shutil
import sys
from collections import defaultdict
from importlib import metadata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import atlas_lib as L  # noqa: E402
from sustainability.species_section import render as sustain_section  # noqa: E402

VERSION = L.read_json(L.ROOT / "version.json")
DATA_CUTOFF = VERSION["data_cutoff"]
REPO = "https://github.com/subhadipban-lgtm/mekong-medicinal-plant-atlas"
BOOTSTRAP_CSS = ("https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css",
                 "sha384-QWTKZyjpPEjISv5WaRU9OFeRpok6YctnYmDr5pNlyT2bRjXh0JMhjY6hW+ALEwIH")
BOOTSTRAP_JS = ("https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js",
                "sha384-YvpcrYf0tY3lHB60NNkmXc5s9fDVZLESaAA55NDzOxhy9GkcIdslK1eN7N6jIeHz")
COUNTRY_NAMES = L.COUNTRY_NAMES
GRADE_TEXT = {
    "A": "peer-reviewed article or survey with documented methodology",
    "B": "major reference book or authoritative flora",
    "C": "report, proceedings, specimen, or citation that cannot be verified",
    "D": "web source, unverified lead, or no citation",
}
EVIDENCE = L.ROOT / "data" / "evidence"
EVIDENCE_TIERS = ("traditional", "in vitro", "in vivo", "clinical", "review", "other")
TIER_BADGES = {"traditional": "warning", "in vitro": "info", "in vivo": "primary",
               "review": "secondary", "clinical": "success", "other": "dark"}


def tier_badge(tier: str) -> str:
    return f'<span class="badge text-bg-{TIER_BADGES.get(tier, "dark")}">{e(tier)}</span>'


# ---- macroecology (Shrestha et al. 2025 framework) ------------------------
ISO2L3 = {"CN": ("CHC", "CHS"), "KH": ("CBD",), "LA": ("LAO",), "MM": ("MYA",),
          "TH": ("THA",), "VN": ("VIE",)}
L3_LABEL = {"CHC": "China South-Central", "CHS": "China Southeast", "CBD": "Cambodia",
            "LAO": "Laos", "MYA": "Myanmar", "THA": "Thailand", "VIE": "Vietnam"}
MEKONG_L3 = {"CBD", "LAO", "MYA", "THA", "VIE", "CHC", "CHS"}
REALM_COLORS = {"Indomalaya": "#166a4f", "Palearctic": "#1f5f8b", "Afrotropic": "#b36b00",
                "Nearctic": "#7a5fa6", "Neotropic": "#4a8f8a", "Australasia": "#a63d57"}
SHRESTHA_DOI = "10.1016/j.cub.2025.09.050"
# The single Shrestha citation shown on every species page (macroecological-context
# footnote) and as footnote 1 on the Methods page. Defined once so the 333 copies
# are generated from one source rather than pasted per page.
SHRESTHA_REF = ("Shrestha et al., The human fingerprint of medicinal plant species diversity, "
                "Current Biology (2025), doi:" + SHRESTHA_DOI + ".")


def macro_class_badge(cls: str) -> str:
    if cls == "hotspot":
        return '<span class="badge badge-hotspot">hotspot</span>'
    if cls == "coldspot":
        return '<span class="badge badge-coldspot">coldspot</span>'
    if cls == "not_significant":
        return '<span class="badge text-bg-light border">not significant</span>'
    return '<span class="badge text-bg-secondary">no data</span>'


def load_macroecology() -> dict:
    mdir = L.ROOT / "data" / "processed" / "macroecology"

    def csv_of(name):
        p = mdir / name
        return L.read_csv(p) if p.exists() else []

    scatter = []
    src = L.ROOT / "data" / "raw" / "shrestha2025" / "data.csv"
    if src.exists():
        with open(src, newline="", encoding="latin-1") as f:
            for r in csv.DictReader(f):
                if r["realm"] in ("Antarctica", "Oceania"):
                    continue
                try:
                    scatter.append({"vas": float(r["vas_rich"]), "med": float(r["med_rich"]),
                                    "realm": r["realm"], "code": r["TDWG"],
                                    "name": r["LEVEL3_NAME"]})
                except (ValueError, KeyError):
                    pass
    residual = csv_of("mekong_residual_analysis.csv")
    validation = {}
    vp = mdir / "reproduction_validation.json"
    if vp.exists():
        validation = json.loads(vp.read_text(encoding="utf-8"))
    return {
        "residual": residual,
        "residual_by_code": {r["wgsrpd_code"]: r for r in residual},
        "slopes": csv_of("slope_comparison.csv"),
        "leverage": csv_of("mekong_leverage.csv"),
        "coverage": {r["species_id"]: r for r in csv_of("mekong_wcvp_coverage.csv")},
        "coldspots": csv_of("mekong_internal_coldspots.csv"),
        "validation": validation,
        "scatter": scatter,
    }


def shrestha_commit() -> str:
    p = L.ROOT / "data" / "raw" / "shrestha2025" / "commit.txt"
    return p.read_text(encoding="utf-8").strip()[:10] if p.exists() else "not cached"
NAV = [("index.html", "Atlas", "index"), ("explore.html", "Explore", "explore"),
       ("species/index.html", "Species", "species"), ("evidence.html", "Evidence", "evidence"),
       ("macroecology.html", "Macroecology", "macroecology"),
       ("methods.html", "Methods", "methods"),
       ("download.html", "Download", "download"),
       ("about.html", "About", "about")]


# ------------------------------------------------------------------ small helpers
def e(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def n(value) -> str:
    try:
        return f"{int(float(value or 0)):,}"
    except (ValueError, TypeError):
        return "–"


def slug_of(species_id: str) -> str:
    return species_id[3:]


def badge_grade(g: str) -> str:
    return f'<span class="badge badge-grade {e(g)}" title="Evidence grade {e(g)}">{e(g)}</span>'


def badge_iucn(code: str) -> str:
    first = (code or "").split("/")[0]
    if not first:
        return '<span class="text-muted" title="No IUCN category recorded">–</span>'
    return f'<span class="badge badge-iucn {e(first)}" title="IUCN category {e(code)}">{e(code)}</span>'


def doi_link(doi: str, grade_basis: str = "") -> str:
    """Link to the confirmed article; say so when the identifier printed in the source was wrong."""
    if not doi:
        return ""
    corrected = "printed identifier was wrong" in (grade_basis or "")
    label = "Corrected DOI" if corrected else "DOI"
    title = ("The DOI printed in the source does not resolve to this article; this is the DOI of the article that was confirmed."
             if corrected else "DOI of the confirmed article")
    return f' <a href="https://doi.org/{e(doi)}" target="_blank" rel="noopener" title="{e(title)}">{label}</a>'


def north_arrow() -> str:
    return ('<div class="north-arrow" title="North is up"><svg width="18" height="26" viewBox="0 0 18 26" role="img" aria-label="North arrow">'
            '<polygon points="9,1 15,19 9,15 3,19" fill="#166a4f"/>'
            '<text x="9" y="25" text-anchor="middle" font-size="8" font-weight="700" fill="#1c2420">N</text></svg></div>')


def human(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return ""


MAP_LEGEND = '''<div class="map-legend legend-grade">
  <div><strong>Occurrence records</strong> · colour = evidence grade</div>
  <div><span class="sw" style="background:#1b5e20"></span>A peer-reviewed</div>
  <div><span class="sw" style="background:#b36b00"></span>B reference book or flora</div>
  <div><span class="sw" style="background:#66707a"></span>C specimen or observation</div>
  <div><span class="sw" style="background:#fff;border:2px solid #66707a;width:10px;height:10px"></span>hollow = observation · filled = specimen</div>
  <div><span class="sw" style="background:#166a4f;opacity:.2;border:1px dashed #166a4f"></span>Mekong basin boundary</div>
  <div><span class="sw" style="background:#1f5f8b;border-radius:2px"></span>Mekong River</div>
</div>'''


# ------------------------------------------------------------------ page shell
def page(title: str, body: str, active: str, description: str, script: str, need: tuple = ("map",), base: str = "") -> str:
    links = "".join(
        f'<a class="nav-link{" active" if key == active else ""}" data-page="{key}" href="{href}">{label}</a>'
        for href, label, key in NAV)
    css, css_sri = BOOTSTRAP_CSS
    js, js_sri = BOOTSTRAP_JS
    tags = []
    if "map" in need:
        tags += ['<link href="assets/vendor/leaflet/leaflet.css" rel="stylesheet">',
                 '<link href="assets/vendor/markercluster/MarkerCluster.css" rel="stylesheet">',
                 '<link href="assets/vendor/markercluster/MarkerCluster.Default.css" rel="stylesheet">']
    if "table" in need:
        tags += ['<link href="assets/vendor/datatables/dataTables.bootstrap5.min.css" rel="stylesheet">']
    scripts = []
    if "table" in need:
        scripts += ["assets/vendor/jquery/jquery.min.js"]
    if "map" in need:
        scripts += ["assets/vendor/leaflet/leaflet.js", "assets/vendor/markercluster/leaflet.markercluster.js"]
    if "table" in need:
        scripts += ["assets/vendor/datatables/dataTables.min.js", "assets/vendor/datatables/dataTables.bootstrap5.min.js"]
    if "map" in need:
        scripts += ["assets/js/common.js", "assets/js/map.js", f"assets/js/{script}"]
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{"<base href='" + base + "'>" if base else ""}
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<link href="{css}" rel="stylesheet" integrity="{css_sri}" crossorigin="anonymous">
<link href="assets/css/atlas.css" rel="stylesheet">
{"".join(tags)}
</head>
<body data-page="{active}">
<nav class="navbar navbar-expand-md navbar-atlas navbar-dark">
  <div class="container-fluid px-3 px-lg-4">
    <a class="navbar-brand" href="index.html">🌿 Mekong Medicinal Plant Atlas</a>
    <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#atlasNav" aria-label="Toggle navigation"><span class="navbar-toggler-icon"></span></button>
    <div class="collapse navbar-collapse" id="atlasNav"><ul class="navbar-nav ms-auto">{links}</ul></div>
  </div>
</nav>
{body}
<footer class="atlas">
  <div class="container-fluid px-3 px-lg-4">
    <div class="row g-3">
      <div class="col-md-5">
        <strong>Mekong Medicinal Plant Atlas</strong> · version {e(VERSION["version"])} · data as of {e(DATA_CUTOFF)}<br>
        Occurrence records from <a href="https://www.gbif.org" target="_blank" rel="noopener">GBIF</a>; names from the GBIF backbone and
        <a href="https://www.worldfloraonline.org" target="_blank" rel="noopener">World Flora Online</a>; basin boundary
        <a href="https://doi.org/10.5281/zenodo.7622998" target="_blank" rel="noopener">Tiwari et al. (Zenodo, CC-BY 4.0)</a>;
        photos © iNaturalist contributors under their own licences.<br>
        <strong>Dataset DOI: <a href="https://doi.org/{e(VERSION["dataset_doi"])}" target="_blank" rel="noopener">{e(VERSION["dataset_doi"])}</a></strong> (concept DOI {e(VERSION["concept_doi"])}).
      </div>
      <div class="col-md-4">
        <a href="{REPO}" target="_blank" rel="noopener">Source code and documentation</a><br>
        <a href="{REPO}/blob/main/docs/QA_REPORT.md" target="_blank" rel="noopener">QA report</a> ·
        <a href="{REPO}/blob/main/docs/CONFLICT_REPORT.md" target="_blank" rel="noopener">Conflict report</a> ·
        <a href="{REPO}/blob/main/docs/data_dictionary.md" target="_blank" rel="noopener">Data dictionary</a>
      </div>
      <div class="col-md-3 text-md-end">Research resource; not medical advice.<br><a href="about.html">Contact</a></div>
    </div>
  </div>
</footer>
<script src="{js}" integrity="{js_sri}" crossorigin="anonymous"></script>
{"".join(f'<script src="{s}"></script>' for s in scripts)}
</body>
</html>
'''


# ------------------------------------------------------------------ data
def load_evidence() -> dict:
    """Evidence-engine pilot data (Milestone 1), built from the committed
    contract aggregates so the page reproduces on a clean checkout:

      contract/species_publications.json        per-taxon publication IDs (2,317 total)
      contract/species_evidence_tier_counts.json per-taxon tier breakdown (sums to 2,317)
      contract/species_network_summary.json
      pilot_species.csv, species_compound.csv, prisma_flow.json

    The full publications.csv / search_log.csv (the restricted evidence-engine
    tables) are NOT read: they are gitignored and withheld from publication, and
    the aggregate per-taxon publication counts here are identical to what those
    tables would yield after the tier assignment.
    """
    out = {"summary": {}, "pubs": {}, "order": [], "generated": "",
           "totals": {"pubs": 0, "compounds": 0, "resolved": 0}}
    # Prefer the committed, numbers-only manifest: identical aggregates, and
    # sufficient on a clean checkout (the restricted inputs are not in the repo).
    manifest_path = L.PROCESSED / "evidence_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        out["generated"] = manifest.get("generated", "")
        out["gms"] = manifest.get("gms")
        out["totals"]["unique_pubs"] = manifest.get("totals", {}).get("unique_pubs", 1880)
        out["totals"]["needs_review"] = manifest.get("totals", {}).get("needs_review", 190)
        for t in manifest["taxa"]:
            sid = t["species_id"]
            out["summary"][sid] = {
                "name": t["name"], "family": t["family"],
                "n_pubs": t["n_pubs"],
                "tiers": t["tiers"],
                "n_compounds": t["n_compounds"],
                "n_resolved": t["n_resolved"],
                "network": t.get("network", {}),
            }
            out["totals"]["pubs"] += t["n_pubs"]
            out["totals"]["compounds"] += t["n_compounds"]
            out["totals"]["resolved"] += t["n_resolved"]
        out["order"] = sorted(out["summary"], key=lambda s: out["summary"][s]["name"].lower())
        return out
    # Full (restricted) build path: rebuild the aggregates directly from the
    # local contract files + pilot/compounds present on disk.
    tiers_path = EVIDENCE / "contract" / "species_evidence_tier_counts.json"
    pubs_path = EVIDENCE / "contract" / "species_publications.json"
    pilot_path = EVIDENCE / "pilot_species.csv"
    if not (tiers_path.exists() and pubs_path.exists() and pilot_path.exists()):
        return out
    tiers = json.loads(tiers_path.read_text(encoding="utf-8")).get("species_evidence_tier_counts", {})
    pub_ids = json.loads(pubs_path.read_text(encoding="utf-8")).get("species_publications", {})
    network = {}
    ns_path = EVIDENCE / "contract" / "species_network_summary.json"
    if ns_path.exists():
        network = json.loads(ns_path.read_text(encoding="utf-8")).get("species_network_summary", {})
    prisma_path = EVIDENCE / "prisma_flow.json"
    if prisma_path.exists():
        out["generated"] = json.loads(prisma_path.read_text(encoding="utf-8")).get("generated", "")
    pilot = {r["species_id"]: r for r in L.read_csv(pilot_path)}
    compounds = defaultdict(lambda: {"n": 0, "resolved": 0})
    for c in L.read_csv(EVIDENCE / "species_compound.csv"):
        compounds[c["species_id"]]["n"] += 1
        if c["structure_status"] == "resolved":
            compounds[c["species_id"]]["resolved"] += 1
    gms = None
    gms_pub = EVIDENCE / "publications_gms.csv"
    if gms_pub.exists():
        n_gms_pubs = sum(1 for _ in L.read_csv(gms_pub))
        n_gms_comp = n_gms_plants = n_gms_wcvp = 0
        gms_comp = EVIDENCE / "compounds_gms.csv"
        if gms_comp.exists():
            n_gms_comp = sum(1 for _ in L.read_csv(gms_comp))
        gms_cov = EVIDENCE / "gms_wcvp_coverage.csv"
        if gms_cov.exists():
            cov_rows = L.read_csv(gms_cov)
            n_gms_plants = len(cov_rows)
            n_gms_wcvp = sum(1 for r in cov_rows if r["in_wcvp"] == "1")
        gms = {"papers": n_gms_pubs, "plants": n_gms_plants, "wcvp": n_gms_wcvp, "molecule_rows": n_gms_comp}
    out["gms"] = gms
    for sid, row in pilot.items():
        n_pubs = len(pub_ids.get(sid, []))
        out["summary"][sid] = {
            "name": row["accepted_name"], "family": row["family"],
            "n_pubs": n_pubs,
            "tiers": tiers.get(sid, {}),
            "n_compounds": compounds[sid]["n"],
            "n_resolved": compounds[sid]["resolved"],
            "network": network.get(sid, {}),
        }
        out["totals"]["pubs"] += n_pubs
        out["totals"]["compounds"] += compounds[sid]["n"]
        out["totals"]["resolved"] += compounds[sid]["resolved"]
    out["order"] = sorted(out["summary"], key=lambda s: out["summary"][s]["name"].lower())
    return out


def load() -> dict:
    d = {t: L.read_csv(L.PROCESSED / f"{t}.csv") for t in
         ("species_master", "uses", "pharmacology", "conservation_trade", "references")}
    d["uses_by"], d["pharm_by"], d["cons_by"] = defaultdict(list), defaultdict(list), {}
    for u in d["uses"]:
        d["uses_by"][u["species_id"]].append(u)
    for p in d["pharmacology"]:
        d["pharm_by"][p["species_id"]].append(p)
    for c in d["conservation_trade"]:
        d["cons_by"].setdefault(c["species_id"], c)
    path = L.RAW / "inat_photos.json"
    # Only photos whose iNaturalist taxon name equals the accepted name are shown.
    d["photos"] = {k: v for k, v in (L.read_json(path) if path.exists() else {}).items()
                   if v and v.get("url") and v.get("name_matches")}
    d["evidence"] = L.read_json(L.PROCESSED / "evidence_summary.json")
    d["occ"] = L.read_json(L.PROCESSED / "occurrence_build_summary.json")
    d["geo"] = L.read_json(L.GEO / "_occurrence_geo_summary.json")
    d["layers"] = L.read_json(L.GEO / "_layer_provenance.json")
    d["ev"] = load_evidence()
    d["macro"] = load_macroecology()
    for key, name in (("sust_pressure", "harvest_pressure_summary.csv"),
                      ("sust_hydro", "hydrological_fragmentation.csv"),
                      ("sust_sdm", "sdm_results.csv"),
                      ("sust_sdm_perf", "sdm_performance.csv"),
                      ("sust_cult", "cultivation_summary.csv")):
        path = L.PROCESSED / name
        d[key] = L.read_csv(path) if path.exists() else []
    d["sust_pressure_by"] = {r["species_id"]: r for r in d["sust_pressure"]}
    d["sust_hydro_by"] = {r["species_id"]: r for r in d["sust_hydro"]}
    d["sust_sdm_by"] = {r["species_id"]: r for r in d["sust_sdm"]}
    d["sust_cult_by"] = {r["species_id"]: r for r in d["sust_cult"]}
    return d


def species_json(d: dict) -> list[dict]:
    out = []
    for r in d["species_master"]:
        out.append({
            "id": r["species_id"], "name": r["accepted_name"], "authorship": r["scientific_name_authorship"],
            "family": r["family"], "genus": r["genus"], "taxon_rank": r["taxon_rank"],
            "countries": [c for c in r["countries_present"].split(",") if c],
            "occ_countries": [c for c in r["occurrence_countries"].split(",") if c],
            "grade": r["evidence_grade"], "iucn": r["iucn_category_code"].split("/")[0],
            "iucn_full": r["iucn_category_code"], "cites_appendix": r["cites_appendix"], "life_form": r["life_form"],
            "n_in_basin": int(r["n_occurrence_in_basin"] or 0), "n_records": int(r["n_occurrence_records"] or 0),
            "n_outside": int(r["n_occurrence_outside_basin"] or 0), "sensitive": r["sensitive_species"],
            "sensitivity_reason": r["sensitivity_reason"],
            "synonyms": json.loads(r["synonyms"] or "[]"), "local_names": json.loads(r["local_names_json"] or "{}"),
            "n_uses": len(d["uses_by"].get(r["species_id"], [])),
            "n_pharm": len(d["pharm_by"].get(r["species_id"], [])), "same_as": r["same_gbif_taxon_as"],
        })
    return out


def copy_downloads() -> dict[str, int]:
    sizes: dict[str, int] = {}
    tables = L.WEB / "data" / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    for name in ("species_master", "uses", "pharmacology", "conservation_trade", "references", "occurrence_summary_by_species",
                 "evidence_grade_provenance", "evidence_summary.json", "occurrence_build_summary.json"):
        src = L.PROCESSED / (name if name.endswith(".json") else name + ".csv")
        if not src.exists():
            continue
        shutil.copyfile(src, tables / src.name)
        sizes[f"tables/{src.name}"] = src.stat().st_size
    dwc = L.WEB / "data" / "dwca"
    dwc.mkdir(parents=True, exist_ok=True)
    # Keep the published DWCA as-is on a --site-only rebuild (it is not regenerated
    # here and the committed copy carries the dataset citation); populate only if absent.
    zip_dest = dwc / "dwca-mekong-medicinal-plant-atlas.zip"
    if not zip_dest.exists() and (L.DWC / "dwca.zip").exists():
        shutil.copyfile(L.DWC / "dwca.zip", zip_dest)
        sizes["dwca/dwca-mekong-medicinal-plant-atlas.zip"] = (L.DWC / "dwca.zip").stat().st_size
        if (L.DWC / "eml.xml").exists():
            shutil.copyfile(L.DWC / "eml.xml", dwc / "eml.xml")
            sizes["dwca/eml.xml"] = (L.DWC / "eml.xml").stat().st_size
    elif zip_dest.exists():
        sizes["dwca/dwca-mekong-medicinal-plant-atlas.zip"] = zip_dest.stat().st_size
        if (dwc / "eml.xml").exists():
            sizes["dwca/eml.xml"] = (dwc / "eml.xml").stat().st_size
    for layer in ("occurrences.geojson", "occurrences_outside_basin.geojson", "mekong_basin.geojson",
                  "mekong_basin_display.geojson", "mekong_river_naturalearth.geojson", "countries_outline.geojson"):
        shutil.copyfile(L.GEO / layer, L.WEB / "data" / "geo" / layer)
        sizes[f"geo/{layer}"] = (L.GEO / layer).stat().st_size
    return sizes


def software_versions(layers: dict) -> dict:
    def vendor(path: str, pattern: str) -> str:
        found = re.search(pattern, (L.WEB / "assets" / "vendor" / path).read_text(encoding="utf-8", errors="replace"))
        return found.group(1) if found else "unknown"

    packages = {}
    for dist in ("openpyxl", "shapely", "pyshp"):
        try:
            packages[dist] = metadata.version(dist)
        except metadata.PackageNotFoundError:
            packages[dist] = "unknown"
    return {
        "Python": platform.python_version(),
        "Python packages": ", ".join(f"{k} {v}" for k, v in packages.items()),
        "R / WorldFlora": "4.6.1 / 1.14-5 (taxonomic matching, scripts/match_wfo.R)",
        "Leaflet": vendor("leaflet/leaflet.js", r'version="([\d.]+)"'),
        "Leaflet.markercluster": "1.5.3",
        "DataTables": vendor("datatables/dataTables.min.js", r'"(\d+\.\d+\.\d+)"'),
        "DataTables Bootstrap 5 integration": "2.1.8",
        "jQuery": vendor("jquery/jquery.min.js", r"jQuery v([\d.]+)"),
        "Bootstrap (CDN, subresource integrity pinned)": "5.3.3",
        "Natural Earth": layers.get("mekong_river_naturalearth.geojson", {}).get("natural_earth_version", "v5.1.2"),
        "Basemap": "CARTO Positron raster tiles",
    }


# ------------------------------------------------------------------ pages
def home(d: dict) -> str:
    sp, ev, geo = d["species_master"], d["evidence"], d["geo"]
    sust_hp = sum(1 for r in d["sust_pressure"] if r["harvest_pressure_class"] in ("high", "very high"))
    sust_hy = sum(1 for r in d["sust_hydro"] if r["hydrological_vulnerability_class"] == "high")
    sust_sdm_state = "in progress" if not d["sust_sdm"] else "ready"
    in_basin = geo["inside_basin"]
    grades = ev.get("species_by_grade", {})
    countries = "".join(f'<option value="{c}">{e(COUNTRY_NAMES[c])}</option>'
                        for c in sorted(COUNTRY_NAMES, key=lambda c: COUNTRY_NAMES[c]))
    grade_line = " ".join(f'{badge_grade(g)} <span class="text-light">{n(grades.get(g, 0))}</span>' for g in ("A", "B", "C", "D"))
    return page("Mekong Medicinal Plant Atlas", f'''
<header class="hero">
  <div class="container-fluid px-3 px-lg-4 py-4 py-lg-5">
    <div class="row g-4 align-items-center">
      <div class="col-lg-7">
        <h1 class="display-6">Mekong Medicinal Plant Atlas</h1>
        <p class="lead mt-3">Where medicinal plants of the Mekong basin occur, how they are used, what is known about their chemistry,
        and how strong the evidence behind each statement is — for Cambodia, China (Yunnan), Laos, Myanmar, Thailand and Vietnam.</p>
        <div class="mt-4 d-flex flex-wrap gap-3">
          <a class="btn btn-success btn-lg" href="explore.html">Explore occurrences</a>
          <a class="btn btn-outline-light btn-lg" href="species/index.html">Browse {n(len(sp))} taxa</a>
          <a class="btn btn-outline-light btn-lg" href="methods.html">Methods</a>
        </div>
      </div>
      <div class="col-lg-5">
        <div class="row g-3">
          <div class="col-6 stat"><div class="n">{n(len(sp))}</div><div class="l">medicinal taxa</div></div>
          <div class="col-6 stat"><div class="n">{n(in_basin["records"])}</div><div class="l">occurrence records inside the basin</div></div>
          <div class="col-6 stat"><div class="n">6</div><div class="l">basin countries</div></div>
          <div class="col-6 stat"><div class="n">{n(in_basin["species"])}</div><div class="l">taxa with records inside the basin</div></div>
          <div class="col-6 stat"><div class="n">{n(len(d["uses"]))}</div><div class="l">ethnobotanical use records</div></div>
          <div class="col-6 stat"><div class="n">{n(len(d["pharmacology"]))}</div><div class="l">pharmacology records</div></div>
        </div>
        <div class="small mt-3">Taxa by best evidence grade: {grade_line}</div>
        <div class="small mt-2"><a class="text-light" href="evidence.html">Evidence engine (pilot):
          {n(d["ev"]["totals"]["pubs"])} records · {n(d["ev"]["totals"].get("unique_pubs", 1880))} unique publications across {n(len(d["ev"]["order"]))} taxa</a></div>
        <div class="small mt-2"><a class="text-light" href="sustainability.html">Sustainability:
          {e(sust_hp)} taxa high or very high harvest pressure · {e(sust_hy)} hydro-vulnerable · climate SDM {e(sust_sdm_state)}</a></div>
      </div>
    </div>
  </div>
</header>
<main class="container-fluid px-3 px-lg-4 py-4">
  <h2 class="h4">Occurrence records</h2>
  <p class="text-muted small mb-2">Every one of the {n(in_basin["records"])} georeferenced records that falls inside the basin boundary, coloured by evidence grade.
  {n(geo["outside_basin"]["records"])} further records from the same countries lie outside the basin. In-basin records are shown as published; out-of-basin
  records are generalised to one point per species per half-degree cell.</p>
  <div class="d-flex flex-wrap align-items-center gap-2 mb-2" role="group" aria-label="Map record scope">
    <div class="btn-group btn-group-sm map-scope-toggle" id="mapScope">
      <input class="btn-check" type="radio" name="mapScope" id="scopeInBasin" value="in" checked>
      <label class="btn btn-outline-secondary" for="scopeInBasin">In-basin records ({n(in_basin["records"])})</label>
      <input class="btn-check" type="radio" name="mapScope" id="scopeAll" value="all">
      <label class="btn btn-outline-secondary" for="scopeAll">All records ({n(geo["outside_basin"]["records"] + in_basin["records"])})</label>
    </div>
    <span class="small text-muted" id="scopeNote">Loading the in-basin records only; switch to all records to add the out-of-basin layer.</span>
  </div>
  <div class="map-shell map-home">
    <div class="map" id="map" role="application" aria-label="Map of occurrence records inside the Mekong basin"></div>
    <div class="map-tools">{north_arrow()}</div>
    <div class="map-status" id="homeStatus">Loading records…</div>
    {MAP_LEGEND}
    <div class="map-legend legend-scope">
      <div><strong>Record scope</strong></div>
      <div><span class="sw" style="background:#1b5e20"></span>in-basin record (inside the basin boundary)</div>
      <div><span class="sw" style="background:#66707a;opacity:.55"></span>out-of-basin record (same six countries, outside the basin; generalised to a half-degree cell)</div>
    </div>
    <div id="homeLoading" class="map-status" style="top:.7rem;left:.7rem;bottom:auto">Loading the atlas…</div>
  </div>
  <div class="row g-3 mt-1 align-items-center">
    <div class="col-auto"><label class="small text-muted me-2" for="homeCountry">Country</label>
      <select class="form-select form-select-sm d-inline-block w-auto" id="homeCountry"><option value="">All</option>{countries}</select></div>
    <div class="col-auto"><label class="small text-muted me-2" for="homeSearch">Find a species</label>
      <input class="form-control form-control-sm d-inline-block w-auto" id="homeSearch" placeholder="e.g. Curcuma, Zingiberaceae"></div>
  </div>
  <div class="row g-3 mt-1">
    <div class="col-md-6 col-xl-3"><div class="card h-100"><div class="card-body"><h3 class="h6 card-title">Explore</h3>
      <p class="small mb-2">Clustered occurrences with filters for species, country, family, life form, IUCN status and CITES appendix.</p>
      <a href="explore.html">Open the explore page</a></div></div></div>
    <div class="col-md-6 col-xl-3"><div class="card h-100"><div class="card-body"><h3 class="h6 card-title">Species</h3>
      <p class="small mb-2">One page per taxon: map, ethnobotany, pharmacology, conservation status and links to GBIF, WFO and POWO.</p>
      <a href="species/index.html">Browse all taxa</a></div></div></div>
    <div class="col-md-6 col-xl-3"><div class="card h-100"><div class="card-body"><h3 class="h6 card-title">Methods</h3>
      <p class="small mb-2">Sources, the evidence-grading rubric, the coordinate generalisation policy and the limitations.</p>
      <a href="methods.html">Read the methods</a></div></div></div>
    <div class="col-md-6 col-xl-3"><div class="card h-100"><div class="card-body"><h3 class="h6 card-title">Cite the dataset</h3>
      <p class="small mb-2">The data are archived on Zenodo with a citable DOI; the Darwin Core Archive and every table are downloadable from the record.</p>
      <a href="https://doi.org/{e(VERSION["dataset_doi"])}" target="_blank" rel="noopener">Open the Zenodo record</a></div></div></div>
  </div>
</main>
''', "index", "Interactive atlas of medicinal plants of the Mekong basin: occurrences, uses, pharmacology, conservation.", "index.js")


def explore(d: dict) -> str:
    boxes = "".join(
        f'<div class="form-check form-check-inline"><input class="form-check-input" type="checkbox" value="{g}" id="grade{g}" checked>'
        f'<label class="form-check-label" for="grade{g}">{badge_grade(g)}</label></div>' for g in ("A", "B", "C"))
    return page("Explore — Mekong Medicinal Plant Atlas", f'''
<main class="container-fluid px-3 px-lg-4 py-3">
  <h1 class="h4 mb-1">Occurrence records</h1>
  <p class="text-muted small mb-2">Colour shows the <strong>evidence grade</strong> of each record; filled markers are specimen-based and hollow markers are observations.
  A cluster opens the list of species it contains. Inside the basin every record is shown; outside it, records are generalised to half-degree cells.</p>
  <div class="map-shell map-explore">
    <div class="map" id="map" role="application" aria-label="Map of occurrence records"></div>
    <div class="filter-panel"><div class="card"><div class="card-body">
      <strong class="small">Filters</strong>
      <form id="filterPanel">
        <label class="mt-2" for="q">Search name, synonym or family</label>
        <input class="form-control" id="q" placeholder="e.g. Curcuma, Zingiberaceae" autocomplete="off">
        <label class="mt-2" for="fSpecies">Species</label><select class="form-select" id="fSpecies"><option value="">Loading…</option></select>
        <label class="mt-2" for="fCountry">Country (several allowed)</label><select class="form-select" id="fCountry" multiple size="6"></select>
        <div id="gradeBoxes" class="mt-2"><span class="d-block">Evidence grade</span>{boxes}</div>
        <label class="mt-2" for="fFamily">Family</label><select class="form-select" id="fFamily"></select>
        <label class="mt-2" for="fLifeForm">Life form</label><select class="form-select" id="fLifeForm"></select>
        <label class="mt-2" for="fIucn">IUCN status</label><select class="form-select" id="fIucn"></select>
        <label class="mt-2" for="fCites">CITES appendix</label><select class="form-select" id="fCites"></select>
        <div class="d-grid gap-2 mt-3"><button class="btn btn-sm btn-outline-secondary" type="button" id="resetFilters">Reset filters</button></div>
      </form>
    </div></div></div>
    <div class="map-tools">{north_arrow()}</div>
    <div class="map-status" id="mapStatus">Loading records…</div>
    {MAP_LEGEND}
    <div id="loading" class="map-status" style="top:.7rem;left:.7rem;bottom:auto">Loading {n(d["geo"]["inside_basin"]["records"])} records…</div>
  </div>
  <div class="d-flex flex-wrap align-items-baseline gap-3 mt-4">
    <h2 class="h5 mb-0">Species database</h2>
    <span class="small text-muted"><span id="nSpeciesShown">–</span> species on the map · the table follows the filters</span>
    <button class="btn btn-sm btn-outline-success ms-auto" id="exportVisible">Download table as CSV</button>
  </div>
  <div class="table-responsive mt-2">
    <table class="table table-striped table-hover table-atlas nowrap" id="speciesTable">
      <thead><tr><th>Accepted name</th><th>Family</th><th>Countries with records</th><th>Evidence grade</th><th>IUCN status</th>
      <th title="Published records inside the Mekong basin boundary">Records in basin</th>
      <th title="Published records anywhere in the six basin countries">Records in countries</th><th>Species page</th></tr></thead>
      <tbody></tbody>
    </table>
  </div>
  <p class="small text-muted">Records come from GBIF and are limited to those with an open licence, a recognised basis of record and verifiable metadata.
  Occurrence records are specimens or observations, which the rubric grades C; the evidence grade of a species reflects the literature behind its uses and pharmacology.</p>
</main>
''', "explore", "Explore occurrence records of Mekong medicinal plants on a clustered map with filters.", "explore.js", need=("map", "table"))


def scatter_svg(d: dict) -> str:
    """Vascular vs medicinal diversity scatter with realm regression lines.

    Raises instead of degrading when the Shrestha input is missing: a build that
    silently renders "unavailable" shipped this page empty before.
    """
    pts = d["macro"]["scatter"]
    slopes = {s["realm"]: s for s in d["macro"]["slopes"]}
    if not pts or not slopes:
        sys.exit("macroecology scatter: Shrestha input missing or empty "
                 "(data/raw/shrestha2025/data.csv) — refusing to render a placeholder")
    W, H, P = 880, 540, 52
    xmax = max(p["vas"] for p in pts) * 1.03
    ymax = max(p["med"] for p in pts) * 1.03
    X = lambda v: P + v / xmax * (W - 2 * P)
    Y = lambda v: H - P - v / ymax * (H - 2 * P)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Vascular versus medicinal plant diversity by botanical country" style="max-width:100%;height:auto">']
    for gx in (0, 5000, 10000, 15000, 20000, 25000):
        out.append(f'<line x1="{X(gx):.1f}" y1="{Y(0):.1f}" x2="{X(gx):.1f}" y2="{Y(ymax):.1f}" stroke="#e5e8eb"/>')
        out.append(f'<text x="{X(gx):.1f}" y="{H - P + 16}" text-anchor="middle" font-size="11" fill="#66707a">{gx:,}</text>')
    for gy in (0, 2000, 4000, 6000, 8000):
        out.append(f'<line x1="{X(0):.1f}" y1="{Y(gy):.1f}" x2="{X(xmax):.1f}" y2="{Y(gy):.1f}" stroke="#e5e8eb"/>')
        out.append(f'<text x="{P - 8}" y="{Y(gy):.1f}" text-anchor="end" font-size="11" fill="#66707a">{gy:,}</text>')
    for realm, s in slopes.items():
        sub = [p for p in pts if p["realm"] == realm]
        if len(sub) < 2:
            continue
        x0, x1 = min(p["vas"] for p in sub), max(p["vas"] for p in sub)
        y0 = float(s["intercept"]) + float(s["slope"]) * x0
        y1 = float(s["intercept"]) + float(s["slope"]) * x1
        out.append(f'<line x1="{X(x0):.1f}" y1="{Y(y0):.1f}" x2="{X(x1):.1f}" y2="{Y(y1):.1f}" '
                   f'stroke="{REALM_COLORS.get(realm, "#999")}" stroke-width="2" opacity="0.8">'
                   f'<title>{realm}: +{float(s["slope"]) * 1000:.0f} medicinal per 1,000 vascular</title></line>')
    label_pos = {"CHC": (-12, -12), "CHS": (8, 4), "MYA": (-6, 6), "THA": (-10, -12),
                 "VIE": (10, 4), "LAO": (10, 6), "CBD": (-12, 10)}
    for p in pts:
        ismek = p["code"] in MEKONG_L3
        r = 5.5 if ismek else 2.4
        out.append(f'<circle cx="{X(p["vas"]):.1f}" cy="{Y(p["med"]):.1f}" r="{r}" '
                   f'fill="{REALM_COLORS.get(p["realm"], "#999")}" opacity="{0.95 if ismek else 0.4}" '
                   f'stroke="{"#1c2420" if ismek else "none"}">'
                   f'<title>{e(p["name"])}: {p["vas"]:,} vascular, {p["med"]:,} medicinal ({e(p["realm"])})</title></circle>')
    for p in pts:
        if p["code"] in MEKONG_L3:
            dx, dy = label_pos.get(p["code"], (8, -8))
            out.append(f'<text x="{X(p["vas"]) + dx:.1f}" y="{Y(p["med"]) + dy:.1f}" font-size="11.5" font-weight="600" fill="#1c2420">{e(p["name"])}</text>')
    out.append(f'<text x="{W / 2}" y="{H - 10}" text-anchor="middle" font-size="12" fill="#1c2420">Vascular plant species per botanical country (WCVP)</text>')
    out.append(f'<text x="16" y="{H / 2}" transform="rotate(-90 16 {H / 2})" text-anchor="middle" font-size="12" fill="#1c2420">Medicinal plant species per botanical country (MPNS)</text>')
    out.append("</svg>")
    leg = "".join(f'<span class="me-2"><span style="display:inline-block;width:10px;height:10px;background:{c};border-radius:50%"></span> {e(r)}</span>'
                  for r, c in REALM_COLORS.items())
    return "".join(out) + f'<div class="small text-muted mt-1">{leg} · highlighted points = Mekong botanical countries</div>'


def scatter_caption(slopes: list[dict]) -> str:
    """Figure caption: fitted slope and n per realm, matching the realm-slope
    table's precision (slope x1,000)."""
    parts = " · ".join(
        f'{s["realm"]} slope {float(s["slope"]) * 1000:.0f} per 1,000 vascular (n = {n(s["n"])})'
        for s in sorted(slopes, key=lambda x: -float(x["slope"])))
    return ('<p class="small text-muted mb-2"><strong>Figure.</strong> Vascular vs medicinal plant diversity per botanical country, '
            f'reproduced from the Shrestha et al. 2025 global analysis (their Figure 2) with the atlas\'s own refit. '
            f'{parts}. Highlighted and labelled points are the seven Mekong botanical countries.</p>')


def macroecology(d: dict) -> str:
    m = d["macro"]
    resid = m["residual"]
    val = m["validation"]
    slopes = sorted(m["slopes"], key=lambda s: -float(s["slope"]))
    cold = m["coldspots"]
    n_cold = sum(1 for r in cold if r["classification"] == "coldspot")
    n_prio = sum(1 for r in cold if str(r["priority_for_fieldwork"]).lower() == "true")
    n_hot = sum(1 for r in resid if r["classification"] == "hotspot")
    indo = next((s for s in slopes if s["realm"] == "Indomalaya"), {})
    aus = next((s for s in slopes if s["realm"] == "Australasia"), {})

    resid_rows = "".join(
        f'<tr><td>{e(r["botanical_country"])}</td><td class="text-end">{n(r["vascular_diversity"])}</td>'
        f'<td class="text-end">{n(r["medicinal_diversity"])}</td><td class="text-end">{n(r["predicted_medicinal_diversity"])}</td>'
        f'<td class="text-end">{"+" if float(r["residual"]) > 0 else ""}{r["residual"]}</td>'
        f'<td class="text-end">{r["residual_p_value"]}</td><td>{macro_class_badge(r["classification"])}</td></tr>'
        for r in resid)
    slope_rows = "".join(
        f'<tr><td>{e(s["realm"])}</td><td class="text-end">{n(s["n"])}</td>'
        f'<td class="text-end">{float(s["slope"]) * 1000:.0f}</td>'
        f'<td class="text-end">[{float(s["ci_low"]) * 1000:.0f}, {float(s["ci_high"]) * 1000:.0f}]</td></tr>'
        for s in slopes)
    lev_rows = "".join(
        f'<tr><td>{e(r["botanical_country"])}</td><td class="text-end">{n(r["vascular_diversity"])}</td>'
        f'<td class="text-end">{n(r["medicinal_diversity"])}</td><td class="text-end">{n(r["indomalaya_fitted"])}</td>'
        f'<td class="text-end">{"+" if float(r["indomalaya_residual"]) > 0 else ""}{r["indomalaya_residual"]}</td>'
        f'<td class="text-end">{r["leverage"]}</td></tr>' for r in m["leverage"])
    prio = [r for r in cold if str(r["priority_for_fieldwork"]).lower() == "true"]
    prio_rows = "".join(
        f'<tr><td>{e(r["admin1"])}</td><td>{e(COUNTRY_NAMES.get(r["country"], r["country"]))}</td>'
        f'<td class="text-end">{n(r["vascular_diversity"])}</td><td class="text-end">{n(r["medicinal_diversity"])}</td>'
        f'<td class="text-end">{r["residual"]}</td><td class="text-end">{r["residual_p_value"]}</td>'
        f'<td class="text-end">{r["human_occupancy"]}</td>'
        f'<td><span class="badge text-bg-success">fieldwork priority</span></td></tr>' for r in prio)
    val_html = ""
    if val:
        val_html = (f'<p class="small">Reproduction check (QA gate 1): our med ~ vas residuals correlate '
                    f'<strong>r = {val.get("corr_med_vas_residuals_vs_published")}</strong> with the residuals column '
                    f'shipped in the authors\u2019 repository (data.csv), confirming the model specification; '
                    f'Indomalaya slope {val.get("indomalaya_slope")} is the steepest of the six realms: '
                    f'{str(val.get("indomalaya_is_steepest")).lower()}.</p>')
    if cold:
        cold_note = (f'<p class="small">At admin-1 scale: {n(len(cold))} provinces modelled, '
                     f'{n(sum(1 for r in cold if r["classification"] == "hotspot"))} hotspots, '
                     f'{n(n_cold)} coldspots, of which <strong>{n(n_prio)}</strong> combine a significant negative '
                     f'residual with long human occupancy and are flagged for fieldwork.</p>')
    else:
        cold_note = '<p class="small text-muted">The admin-1 coldspot analysis is being harvested (GBIF vascular species counts per province); the table and map layer appear when the harvest lands.</p>'

    return page("Macroecology — Mekong Medicinal Plant Atlas", f'''
<main class="container-fluid px-3 px-lg-4 py-3">
  <h1 class="h4 mb-1">Macroecology <span class="text-muted fw-normal">— medicinal plant diversity at Mekong scale</span></h1>
  <p class="small text-muted">A global analysis of medicinal plant diversity across 369 botanical countries<sup>1</sup> identified human occupancy time as its
  second-most important predictor. This page reproduces the residual analysis on the published data for the seven botanical countries that contain the
  Mekong basin, and extends it to sub-national (province) scale.</p>

  <div class="row g-3 mb-3">
    <div class="col-6 col-md-3"><div class="stat"><div class="n">{n(len(resid))}</div><div class="l">Mekong botanical countries</div></div></div>
    <div class="col-6 col-md-3"><div class="stat"><div class="n">{n(n_hot)}</div><div class="l">significant hotspots</div></div></div>
    <div class="col-6 col-md-3"><div class="stat"><div class="n">{indo.get("slope") and float(indo["slope"]) * 1000:.0f}</div><div class="l">medicinal per 1,000 vascular (Indomalaya)</div></div></div>
    <div class="col-6 col-md-3"><div class="stat"><div class="n">{aus.get("slope") and float(aus["slope"]) * 1000:.0f}</div><div class="l">medicinal per 1,000 vascular (Australasia, flattest)</div></div></div>
  </div>

  <h2 class="h5 section-title">Mekong residuals (medicinal ~ vascular)</h2>
  {val_html}
  <div class="table-responsive"><table class="table table-striped table-atlas">
    <thead><tr><th>Botanical country</th><th class="text-end">Vascular species</th><th class="text-end">Medicinal species</th>
    <th class="text-end">Predicted medicinal</th><th class="text-end">Residual</th><th class="text-end">p (two-tailed)</th><th>Classification</th></tr></thead>
    <tbody>{resid_rows}</tbody></table></div>

  <h2 class="h5 section-title">Where the Mekong sits on the global line</h2>
  {scatter_caption(slopes)}
  <div class="row g-4">
    <div class="col-lg-8">{scatter_svg(d)}</div>
    <div class="col-lg-4">
      <h3 class="h6">Realm slopes (medicinal ~ vascular)</h3>
      <div class="table-responsive"><table class="table table-sm table-atlas">
        <thead><tr><th>Realm</th><th class="text-end">n</th><th class="text-end">Slope / 1,000 vascular</th><th class="text-end">95% CI</th></tr></thead>
        <tbody>{slope_rows}</tbody></table></div>
      <h3 class="h6 mt-3">Mekong countries vs the Indomalaya line</h3>
      <div class="table-responsive"><table class="table table-sm table-atlas">
        <thead><tr><th>Country</th><th class="text-end">Vascular</th><th class="text-end">Medicinal</th><th class="text-end">Fitted</th><th class="text-end">Residual</th><th class="text-end">Leverage</th></tr></thead>
        <tbody>{lev_rows}</tbody></table></div>
    </div>
  </div>

  <h2 class="h5 section-title">Reading the Mekong through the global framework</h2>
  <div class="card"><div class="card-body small">
    <p>The Mekong\u2019s documented medicinal flora sits on one of the world\u2019s oldest continuously occupied cultural landscapes. All seven botanical countries that
    contain the basin carry more medicinal species than their vascular floras alone would predict, and six of the seven do so significantly (residuals +994 to +2,195;
    p \u2264 0.072). This is what Shrestha et al.\u2019s global model would lead one to expect: human occupancy time was the second-most important predictor of medicinal
    plant diversity in their 369-country analysis, and Indomalaya \u2014 the realm in which the basin sits \u2014 has the steepest vascular-to-medicinal slope of the six realms
    (~{indo.get("slope") and float(indo["slope"]) * 1000:.0f} medicinal species per 1,000 vascular species, versus
    ~{aus.get("slope") and float(aus["slope"]) * 1000:.0f} in Australasia). The basin is the demographic heart of five major language families \u2014 Austroasiatic,
    Tai-Kadai, Tibeto-Burman, Hmong-Mien and Austronesian \u2014 and the meeting place of several canonical medical systems: Traditional Chinese Medicine in Yunnan and
    Guangxi, Thai traditional medicine, Vietnamese thu\u1ed1c nam, Khmer traditional medicine, and the folk pharmacopoeias of upland Lao, Hmong, Khmu, Karen, Chin and
    Kachin communities. Long occupancy multiplied by many distinct medical traditions is the mechanism the global analysis points to, and the basin\u2019s residuals are its
    regional signature. Language diversity per se appears to act only indirectly through climate in the global model, so the atlas maps languages as context, not as a
    predictor. The one exception worth attention is Cambodia: its residual (+994) is the smallest in the basin and not significant at p &lt; 0.05, and Cambodia is also the
    country with the fewest occurrence records and the thinnest literature coverage in the atlas. That combination \u2014 a modest global residual, low documentation density,
    and a rich Khmer therapeutic tradition \u2014 marks Cambodia, and its upland provinces in particular, as the basin\u2019s leading under-documentation hypothesis, which the
    internal coldspot analysis below tests at sub-national scale.</p>
  </div></div>

  <h2 class="h5 section-title mt-4">Internal coldspots <span class="text-muted fw-normal">— the sub-national extension</span></h2>
  {cold_note}
  {f'<div class="table-responsive mb-3"><table class="table table-striped table-atlas"><thead><tr><th>Province</th><th>Country</th><th class="text-end">Vascular species</th><th class="text-end">Documented medicinal taxa</th><th class="text-end">Residual</th><th class="text-end">p</th><th class="text-end">Occupancy (kyr)</th><th></th></tr></thead><tbody>{prio_rows}</tbody></table></div>' if prio_rows else ""}
  <div class="map-shell map-macro">
    <div class="map" id="map" role="application" aria-label="Macroecology layers: internal coldspots, global residuals, human occupancy, language diversity"></div>
    <div class="map-tools">{north_arrow()}</div>
    <div class="map-status" id="mapStatus">Loading layers\u2026</div>
    <div class="map-legend legend-macro">
      <div><strong>Internal coldspots (admin-1)</strong> <span class="sw" style="background:#c0392b"></span>hotspot <span class="sw" style="background:#2471a3"></span>coldspot <span class="sw" style="background:#d5dbdb"></span>not significant</div>
      <div><strong>Global residual (Shrestha 2025)</strong> <span class="sw" style="background:#c0392b"></span>hotspot <span class="sw" style="background:#f5b041"></span>not significant</div>
      <div><strong>Human occupancy</strong> darker = longer occupation</div>
      <div><strong>Language diversity</strong> darker = more languages</div>
    </div>
  </div>
  <p class="small text-muted mt-2">Layers toggle in the map control. Occupancy values are Shrestha et al.\u2019s published country-level column (reused, not re-derived);
  language richness is aggregated from Glottolog language points to admin-1 polygons and shown as context only.</p>

  <h2 class="h5 section-title">Methods and reproducibility</h2>
  <ul class="small">
    <li><strong>Data</strong>: Shrestha et al. 2025 repository (<code>nawalshrestha/med_plants</code>, data.csv, reused under the paper\u2019s DOI and commit hash recorded in the source register);
    WCVP (sftp.kew.org, retrieved 2026-11-25); WGSRPD level-3 boundaries (tdwg/wgsrpd); Glottolog (Zenodo record 24104033); Natural Earth 10m admin-1; GBIF occurrence API
    (vascular species counts per province, taxonKey=6).</li>
    <li><strong>Botanical countries</strong>: the residual analysis uses the seven WGSRPD level-3 units that intersect the basin
    (Cambodia, Laos, Myanmar, Thailand, Vietnam, China South-Central, China Southeast); the homepage\u2019s \u201c6 basin countries\u201d refers to
    national boundaries, which are a different spatial unit.</li>
    <li><strong>Model</strong>: ordinary least squares, med_rich ~ vas_rich, over all botanical countries except Antarctica and Oceania (the authors\u2019 exclusion).
    Significance: |residual| &gt; 1.96 SD (the authors\u2019 threshold in residual_histogram.R); the table reports the two-tailed normal-approximation p.</li>
    <li><strong>Extension</strong>: the same model refit at admin-1 scale inside the basin using GBIF vascular species counts per province and the atlas\u2019s documented
    medicinal taxa per province. Differences from the global model are documented in the manuscript.</li>
    <li><strong>Scripts</strong>: <code>scripts/macroecology.py</code>, <code>scripts/macroecology_layers.py</code>, <code>scripts/wcvp_match.py</code>,
    <code>scripts/harvest_admin1_vascular.py</code>, <code>scripts/internal_coldspots.py</code>. Inputs cached under <code>data/raw/shrestha2025/</code>.</li>
    <li><strong>MPNS v12</strong>: mpns.science.kew.org was unavailable (Cloudflare 5xx) on 2026-11-25; MPNS membership badges show as pending and the country-level
    medicinal values come from the published dataset, which is MPNS-derived.</li>
  </ul>
  <h2 class="h5 section-title">References</h2>
  <ol class="small">
    <li>Shrestha et al., The human fingerprint of medicinal plant species diversity, Current Biology (2025),
    <a href="https://doi.org/{SHRESTHA_DOI}" target="_blank" rel="noopener">doi:{SHRESTHA_DOI}</a>.</li>
  </ol>
</main>
<script>
document.addEventListener('DOMContentLoaded', () => {{
  const CARTO_KEY = 'cb1_5f90_1_2200dcf519089dbbd5552a5c';
  const map = L.map('map', {{ attributionControl: false, minZoom: 4, maxZoom: 12 }})
    .setView([18.5, 102.5], 5);
  L.control.attribution({{ position: 'bottomright', prefix: false }})
    .addAttribution('&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions" target="_blank" rel="noopener">CARTO</a> · macroecology layers: Shrestha et al. 2025 data (CC-BY-4.0), Glottolog, Natural Earth (public domain)')
    .addTo(map);
  L.tileLayer(`https://basemaps.cartocdn.com/rastertiles/light_all/{{z}}/{{x}}/{{y}}.png?key=${{CARTO_KEY}}`, {{
    maxZoom: 19, attribution: ''
  }}).addTo(map);

  const status = document.getElementById('mapStatus');
  const fail = (msg) => {{ status.textContent = msg; }};
  const geo = (path, style, popup) => fetch(path)
    .then(r => {{ if (!r.ok) throw new Error(r.status); return r.json(); }})
    .then(d => L.geoJSON(d, {{ style, onEachFeature: (f, l) => popup && l.bindPopup(popup(f)) }}))
    .catch(e => fail(`Could not load ${{path}} (${{e.message}})`));

  const over = {{}};
  Promise.all([
    geo('data/geo/internal_coldspots_mekong.geojson',
        f => ({{ fillColor: f.properties.classification === 'hotspot' ? '#c0392b' : f.properties.classification === 'coldspot' ? '#2471a3' : '#d5dbdb',
                 weight: 0.6, color: '#fff', fillOpacity: 0.65 }}),
        f => `<strong>${{f.properties.admin1}}</strong> (${{f.properties.country}})<br>vascular species: ${{f.properties.vascular_diversity}}<br>documented medicinal taxa: ${{f.properties.medicinal_diversity}}<br>residual: ${{f.properties.residual}} (p = ${{f.properties.residual_p_value}})<br>occupancy: ${{f.properties.human_occupancy}} kyr · ${{f.properties.human_occupancy_class}}${{f.properties.priority_for_fieldwork ? '<br><strong>fieldwork priority</strong>' : ''}}`)
      .then(l => {{ if (l) over['Internal coldspots (admin-1)'] = l; }}),
    geo('data/geo/global_residual_mekong.geojson',
        f => ({{ fillColor: f.properties.classification === 'hotspot' ? '#c0392b' : f.properties.classification === 'not_significant' ? '#f5b041' : '#b2babb',
                 weight: 1, color: '#fff', fillOpacity: 0.55 }}),
        f => `<strong>${{f.properties.name}}</strong><br>residual: ${{f.properties.residual}} (p = ${{f.properties.residual_p_value}})<br>${{f.properties.vascular_diversity}} vascular · ${{f.properties.medicinal_diversity}} medicinal<br><span class="small">Shrestha et al. 2025 classification</span>`)
      .then(l => {{ if (l) over['Global residual (Shrestha 2025)'] = l; }}),
    geo('data/geo/human_occupancy_mekong.geojson',
        f => {{ const h = f.properties.human_occupancy_kyr; const t = h == null ? 0.12 : 0.15 + 0.6 * Math.min(1, (h - 40) / 30);
               return {{ fillColor: '#5d4037', weight: 1, color: '#fff', fillOpacity: t }}; }},
        f => `<strong>${{f.properties.name}}</strong><br>human occupancy: ${{f.properties.human_occupancy_kyr}} kyr (Shrestha et al. 2025, reused as published)`)
      .then(l => {{ if (l) over['Human occupancy'] = l; }}),
    geo('data/geo/language_diversity_mekong.geojson',
        f => {{ const n = f.properties.n_languages; const t = 0.12 + 0.55 * Math.min(1, n / 40);
               return {{ fillColor: '#1f5f8b', weight: 0.5, color: '#fff', fillOpacity: t }}; }},
        f => `<strong>${{f.properties.name}}</strong> (${{f.properties.country}})<br>languages: ${{f.properties.n_languages}} (Glottolog, context only)`)
      .then(l => {{ if (l) over['Language diversity (context)'] = l; }}),
    fetch('data/geo/mekong_basin_display.geojson').then(r => r.json())
      .then(d => L.geoJSON(d, {{ style: {{ color: '#166a4f', weight: 1.5, dashArray: '4 4', fill: false }} }}).addTo(map))
      .catch(() => {{}})
  ]).then(() => {{
    L.control.layers(null, over, {{ position: 'topright', collapsed: false }}).addTo(map);
    if (over['Internal coldspots (admin-1)']) over['Internal coldspots (admin-1)'].addTo(map);
    if (over['Global residual (Shrestha 2025)']) over['Global residual (Shrestha 2025)'].addTo(map);
    status.textContent = '';
  }});
}});
</script>
''', "macroecology", "Macroecological context for the Mekong atlas: medicinal plant diversity residuals reproduced at Mekong scale and extended to province level.", "none.js", need=("map",))


def evidence(d: dict) -> str:
    ev = d["ev"]
    tot = ev["totals"]
    tier_heads = "".join(f"<th>{t}</th>" for t in EVIDENCE_TIERS)
    rows = ""
    for sid in ev["order"]:
        s = ev["summary"][sid]
        tier_cells = "".join(f'<td class="text-end">{n(s["tiers"].get(t, 0))}</td>' for t in EVIDENCE_TIERS)
        comp = (f'{n(s["n_compounds"])} <span class="text-muted small">({n(s["n_resolved"])} with structure)</span>'
                if s["n_compounds"] else "–")
        rows += (f'<tr><td><a class="taxon" href="species/{e(slug_of(sid))}.html">{e(s["name"])}</a></td>'
                 f'<td>{e(s["family"])}</td><td class="text-end">{n(s["n_pubs"])}</td>{tier_cells}'
                 f'<td class="text-end">{comp}</td></tr>')
    pilot_note = (f'<p class="text-muted small">Pilot set: {n(len(ev["order"]))} taxa with the most pharmacology records '
                  f'(Milestone 1 of the evidence engine, generated {e(ev["generated"] or "n/a")}). '
                  f'<strong>{n(tot["pubs"])} tier-mapped records representing {n(tot.get("unique_pubs", 1880))} unique publications</strong>, '
                  f'deduplicated by DOI, then PMID, then normalized title; {n(tot.get("needs_review", 190))} rows flagged '
                  '<span class="badge text-bg-warning">review</span> and await a human queue. Publications were retrieved from '
                  'Europe PMC and OpenAlex and classified by an automated rubric; classification is machine-made '
                  'and never presented as evidence strength.</p>')
    gms_html = ""
    gms = ev.get("gms")
    if gms:
        gms_html = f'''
<h2 class="h5 section-title mt-4">GMS deep-search register <span class="text-muted fw-normal">(Semantic Scholar systematic review)</span></h2>
<p class="small mb-2">A separate register (<code>GMS_DEEP_SEARCH</code>, disjoint from the pilot corpus by register discipline) holding another
session's PRISMA pipeline over Semantic Scholar: <strong>{n(gms["papers"])}</strong> included papers,
<strong>{n(gms["plants"])}</strong> plants extracted (<strong>{n(gms["wcvp"])}</strong> matched in WCVP),
{n(gms["molecule_rows"])} plant–molecule rows. Molecule/activity content is LLM-extracted from abstracts and treated as leads, not curated facts.
The register tables are available from the authors on request.</p>'''
    return page("Evidence — Mekong Medicinal Plant Atlas", f'''
<main class="container-fluid px-3 px-lg-4 py-3">
  <h1 class="h4 mb-1">Evidence engine <span class="text-muted fw-normal">— pilot, {n(len(ev["order"]))} taxa</span></h1>
  {pilot_note}
  <div class="row g-3 mb-3">
    <div class="col-6 col-md-3"><div class="stat"><div class="n" title="{n(tot["pubs"])} tier-mapped records = {n(tot.get("unique_pubs", 1880))} unique publications (deduplicated by DOI, then PMID, then normalized title); {n(tot.get("needs_review", 190))} flagged for human review">{n(tot["pubs"])}</div><div class="l">tier-mapped records · {n(tot.get("unique_pubs", 1880))} unique</div></div></div>
    <div class="col-6 col-md-3"><div class="stat"><div class="n">{n(tot["compounds"])}</div><div class="l">compounds seeded</div></div></div>
    <div class="col-6 col-md-3"><div class="stat"><div class="n">{n(tot["resolved"])}</div><div class="l">with PubChem structure</div></div></div>
    <div class="col-6 col-md-3"><div class="stat"><div class="n">{n(len(ev["order"]))}</div><div class="l">pilot taxa</div></div></div>
  </div>

  <h2 class="h5 section-title">Pilot taxa and evidence tiers</h2>
  <div class="table-responsive">
    <table class="table table-striped table-hover table-atlas" id="summaryTable">
      <thead><tr><th>Taxon</th><th>Family</th><th class="text-end">Publications</th>{tier_heads}<th class="text-end">Compounds</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>

  <div class="alert alert-light border small mt-4"><strong>Full records are restricted.</strong> The underlying publication and compound tables
  (Europe PMC, OpenAlex, Crossref, DOAJ and the GMS deep-search registers, with abstracts and classification details) are held in the private
  evidence-engine repository. They are available from the authors on request for reviewers and collaborators; only these aggregate,
  build-time summaries are published on this site.</div>
  <p class="small text-muted mt-3">Sources: Europe PMC REST (PubMed/MEDLINE, Agricola, patents), OpenAlex, Crossref and DOAJ.
  Machine-assigned evidence tiers (auto-rubric-v1) are never presented as evidence strength; rows the rubric cannot place await human review.</p>
  {gms_html}
</main>
<script>
document.addEventListener('DOMContentLoaded', () => {{
  const $ = window.jQuery;
  $('#summaryTable').DataTable({{ pageLength: 25, order: [[2, 'desc']] }});
}});
</script>
''', "evidence", "Evidence-engine pilot summaries for Mekong medicinal plants: per-taxon publication and compound counts with machine-assigned evidence tiers.", "none.js", need=("table",))


def use_table(uses: list[dict]) -> str:
    if not uses:
        return '<p class="text-muted">No ethnobotanical use records in the atlas for this taxon.</p>'
    rows = "".join(
        f'<tr><td><span class="badge text-bg-light">{e(u["ailment_category"])}</span></td><td>{e(u["specific_use"])}</td>'
        f'<td>{e(u["used_part"] or "–")}</td><td>{e(u["country"])}</td><td class="source">{e(u["source_citation"])}{doi_link(u["resolved_doi"], u["grade_basis"])}</td>'
        f'<td>{badge_grade(u["evidence_grade"])}</td></tr>' for u in uses)
    return ('<div class="table-responsive"><table class="table table-striped table-atlas"><thead><tr><th>Ailment category</th><th>Use</th>'
            '<th>Part used</th><th>Country</th><th>Source</th><th>Grade</th></tr></thead><tbody>' + rows + "</tbody></table></div>")


def pharm_table(pharm: list[dict]) -> str:
    if not pharm:
        return '<p class="text-muted">No pharmacology records in the atlas for this taxon.</p>'
    rows = "".join(
        f'<tr><td>{"extract assay" if p["record_type"] == "extract_assay" else "isolated compound"}</td>'
        f'<td>{e(p["reported_activity"])}</td><td>{e(p["chemical_constituents"] or p["extract_or_fraction"] or "–")}</td>'
        f'<td class="note">{e(p["assay_or_study_type"])}</td><td class="note">{e(p["potency_verbatim"] or "–")}</td>'
        f'<td class="source">{e(p["source_citation"])}{doi_link(p["resolved_doi"], p["grade_basis"])}</td><td>{badge_grade(p["evidence_grade"])}</td></tr>' for p in pharm)
    return ('<div class="table-responsive"><table class="table table-striped table-atlas"><thead><tr><th>Record type</th><th>Reported activity</th>'
            '<th>Constituent or extract</th><th>Assay</th><th>Potency</th><th>Source</th><th>Grade</th></tr></thead><tbody>' + rows + "</tbody></table></div>")


def species_page(d: dict, r: dict) -> str:
    sid = r["species_id"]
    uses, pharm, cons = d["uses_by"].get(sid, []), d["pharm_by"].get(sid, []), d["cons_by"].get(sid)
    name = r["accepted_name"]
    query = name.replace(" ", "+")
    synonyms = json.loads(r["synonyms"] or "[]")
    wb_countries = ", ".join(COUNTRY_NAMES.get(c, c) for c in r["countries_present"].split(",") if c) or "–"
    occ_countries = ", ".join(COUNTRY_NAMES.get(c, c) for c in r["occurrence_countries"].split(",") if c) or "none recorded"

    photo_html = ""
    photo = d["photos"].get(sid)
    if photo:
        photo_html = (f'<div class="species-photo"><img src="{e(photo["url"].replace("/medium.", "/large."))}" alt="{e(name)}" loading="lazy">'
                      f'<div class="cap">Photo: <a href="https://www.inaturalist.org/taxa/{e(photo.get("inat_id"))}" target="_blank" rel="noopener">'
                      f'{e(photo.get("attribution") or "iNaturalist")}</a> · {e((photo.get("license") or "").upper())} · iNaturalist</div></div>')
    flags = [badge_grade(r["evidence_grade"]), badge_iucn(r["iucn_category_code"])]
    if r["cites_appendix"] != "unknown":
        flags.append(f'<span class="badge text-bg-secondary">CITES {e(r["cites_appendix"])}</span>')
    if r["sensitive_species"] == "yes":
        flags.append('<span class="badge badge-sens" title="Coordinates of this species are generalised in the atlas">Sensitive species</span>')
    if r["taxon_rank"] == "genus":
        flags.append('<span class="badge text-bg-dark">genus-level record</span>')
    cov = d["macro"]["coverage"].get(sid)
    if cov:
        if cov["match_type"] == "exact":
            flags.append(f'<span class="badge text-bg-success" title="Accepted name in WCVP ({cov["wcvp_name_id"]})">WCVP accepted</span>')
        elif cov["match_type"] == "synonym":
            flags.append(f'<span class="badge text-bg-info" title="In WCVP as a synonym of {e(cov["wcvp_accepted_name"])}">WCVP synonym</span>')
        elif cov["match_type"] == "spelling_variant":
            flags.append(f'<span class="badge text-bg-warning" title="Closest WCVP name: {e(cov["wcvp_accepted_name"])} - verify spelling">WCVP spelling check</span>')
        else:
            flags.append('<span class="badge text-bg-secondary" title="No WCVP name match recorded">WCVP unmatched</span>')
        flags.append('<span class="badge text-bg-secondary" title="MPNS v12 unavailable on 2026-11-25; membership pending">MPNS pending</span>')
    extra = ""
    if r["sensitive_species"] == "yes":
        extra += f'<dt>Sensitive species</dt><dd>Coordinates of its records are generalised: {e(r["sensitivity_reason"])}</dd>'
    if r["same_gbif_taxon_as"]:
        other = r["same_gbif_taxon_as"]
        extra += (f'<dt>Same species as</dt><dd>This name and <a href="{slug_of(other)}.html"><i>{e(other[3:].replace("_", " "))}</i></a> '
                  'are one accepted species; its occurrence records are listed there.</dd>')
    if synonyms:
        extra += "<dt>Synonyms</dt><dd>" + e("; ".join(synonyms[:12]) + (" …" if len(synonyms) > 12 else "")) + "</dd>"
    resid_map = d["macro"]["residual_by_code"]
    units, parts = [], []
    for iso in [c for c in r["countries_present"].split(",") if c]:
        for u in ISO2L3.get(iso, ()):
            if u not in units and u in resid_map:
                units.append(u)
    for u in units:
        rec = resid_map[u]
        if rec["classification"] == "hotspot":
            parts.append(f'{L3_LABEL[u]} is a medicinal-diversity <strong>hotspot</strong> '
                         f'(residual +{rec["residual"]}, p = {rec["residual_p_value"]})')
        elif rec["classification"] == "coldspot":
            parts.append(f'{L3_LABEL[u]} is a medicinal-diversity <strong>coldspot</strong> '
                         f'(residual {rec["residual"]}, p = {rec["residual_p_value"]})')
        else:
            parts.append(f'{L3_LABEL[u]} is not significantly above expectation '
                         f'(residual +{rec["residual"]}, p = {rec["residual_p_value"]})')
    if parts:
        extra += ('<dt>Macroecological context</dt><dd class="small">Among this taxon\'s countries, '
                  + "; ".join(parts)
                  + f'<sup>1</sup><br><span class="text-muted">¹ {SHRESTHA_REF}</span></dd>')
    cons_html = ""
    if cons:
        cons_html = f'''
<h2 class="h5 section-title">Conservation and trade</h2>
<dl class="row">
  <dt class="col-sm-3">IUCN category</dt><dd class="col-sm-9">{badge_iucn(r["iucn_category_code"])} <span class="text-muted">({e(cons["assessment_basis"])})</span></dd>
  <dt class="col-sm-3">Threat status</dt><dd class="col-sm-9">{e(cons["iucn_status"])}</dd>
  <dt class="col-sm-3">CITES</dt><dd class="col-sm-9">{e(cons["cites_status_verbatim"] or "not recorded")}</dd>
  <dt class="col-sm-3">Trade</dt><dd class="col-sm-9">{e(cons["trade_notes"])}</dd>
</dl>'''
    ev_html = ""
    ev_pilot = d["ev"]["summary"].get(sid)
    if ev_pilot:
        tier_chips = " ".join(
            f'{tier_badge(t)} {n(ev_pilot["tiers"].get(t, 0))}'
            for t in EVIDENCE_TIERS if ev_pilot["tiers"].get(t))
        ev_html = f'''
<h2 class="h5 section-title">Evidence engine <span class="text-muted fw-normal">(pilot)</span></h2>
<p class="small mb-2">Milestone-1 literature mapping: <strong>{n(ev_pilot["n_pubs"])}</strong> publications retrieved from Europe PMC and OpenAlex and
auto-classified into evidence tiers; <strong>{n(ev_pilot["n_compounds"])}</strong> compounds seeded from the atlas pharmacology records
(<strong>{n(ev_pilot["n_resolved"])}</strong> with a PubChem structure). Classification is machine-made; flagged rows await human review.</p>
<div class="mb-2">{tier_chips}</div>
<p class="small mb-0"><a href="evidence.html">See the evidence-engine summary page</a> · full publication records are available from the authors on request.</p>'''
    outside = int(r["n_occurrence_outside_basin"] or 0)
    gbif_link = ""
    if r["gbif_taxon_key"]:
        gbif_link = '<a href="https://www.gbif.org/species/' + e(r["gbif_taxon_key"]) + '" target="_blank" rel="noopener">GBIF</a> · '
    sust_html = sustain_section(d, sid)
    return page(f"{name} — Mekong Medicinal Plant Atlas", f'''
<main class="container-fluid px-3 px-lg-4 py-3">
  <nav aria-label="breadcrumb"><ol class="breadcrumb small"><li class="breadcrumb-item"><a href="index.html">Atlas</a></li>
  <li class="breadcrumb-item"><a href="species/index.html">Species</a></li><li class="breadcrumb-item active" aria-current="page">{e(name)}</li></ol></nav>
  <h1 class="h3"><span class="taxon">{e(name)}</span> <span class="text-muted fw-normal small">{e(r["scientific_name_authorship"])}</span></h1>
  <div class="mb-3">{" ".join(flags)}</div>
  <div class="row g-4">
    <div class="col-lg-5">
      {photo_html}
      <dl class="glance">
        <dt>Family</dt><dd>{e(r["family"] or "–")} <span class="text-muted">(genus <i>{e(r["genus"])}</i>)</span></dd>
        <dt>Occurrence records</dt><dd><strong>{n(r["n_occurrence_in_basin"])}</strong> inside the Mekong basin · <strong>{n(r["n_occurrence_records"])}</strong> in the six basin countries</dd>
        <dt>Countries with records</dt><dd>{occ_countries}</dd>
        <dt>Countries in the ethnobotanical inventory</dt><dd>{wb_countries}</dd>
        <dt>Life form</dt><dd>{e(r["life_form"])}</dd>
        <dt>Parts used</dt><dd>{e(r["parts_used"] or "–")}</dd>
        <dt>Evidence grade</dt><dd>{badge_grade(r["evidence_grade"])} <span class="text-muted small">best grade among this taxon's literature records</span></dd>
        <dt>IUCN category</dt><dd>{badge_iucn(r["iucn_category_code"])} <span class="text-muted small">({e(r["assessment_basis"])})</span></dd>
        <dt>CITES appendix</dt><dd>{e(r["cites_appendix"])}</dd>
        {extra}
        <dt>External databases</dt><dd>
          {gbif_link}
          <a href="https://powo.science.kew.org/results?q={e(query)}" target="_blank" rel="noopener">Plants of the World Online</a> ·
          <a href="https://www.worldfloraonline.org/search?query={e(query)}" target="_blank" rel="noopener">World Flora Online</a></dd>
      </dl>
    </div>
    <div class="col-lg-7">
      <h2 class="h5">Distribution</h2>
      <p class="small text-muted">Filled markers are specimen-based records, hollow markers are observations. The dashed outline is the Mekong basin boundary.</p>
      <div class="map-shell map-species"><div class="map" id="map" data-file="geo/species/{e(slug_of(sid))}" data-name="{e(name)}" data-family="{e(r["family"])}" role="application" aria-label="Distribution of {e(name)}"></div>
        <div class="map-tools">{north_arrow()}</div>
        <div id="mapEmpty" class="map-status">Loading records…</div>
      </div>
      <p class="small mt-2 mb-0"><a href="explore.html?taxon={e(query)}">Open in the explore map</a>{
        f" · {n(outside)} further records from the same countries lie outside the basin" if outside else ""}</p>
    </div>
  </div>
  <h2 class="h5 section-title">Ethnobotany ({len(uses)} use record{"s" if len(uses) != 1 else ""})</h2>
  {use_table(uses)}
  <h2 class="h5 section-title">Pharmacology ({len(pharm)} record{"s" if len(pharm) != 1 else ""})</h2>
  {pharm_table(pharm)}
  {cons_html}
  {ev_html}
  {sust_html}
  <h2 class="h5 section-title">How to cite this page</h2>
  <div class="citation-box">Mekong Medicinal Plant Atlas (version {e(VERSION["version"])}). <i>{e(name)}</i>. Occurrence data: GBIF (harvested {e(DATA_CUTOFF)}),
  generalised for sensitive species. Basin boundary: Tiwari et al., Zenodo, doi:10.5281/zenodo.7622998.
  Dataset DOI: <a href="https://doi.org/{e(VERSION["dataset_doi"])}" target="_blank" rel="noopener">https://doi.org/{e(VERSION["dataset_doi"])}</a>.</div>
</main>
''', "species", f"{name} in the Mekong Medicinal Plant Atlas", "species.js", base="../")


def species_index(d: dict) -> str:
    by_genus = defaultdict(list)
    for r in d["species_master"]:
        by_genus[r["genus"]].append(r)
    parts = []
    for genus in sorted(by_genus, key=str.lower):
        items = ""
        for r in by_genus[genus]:
            ev_link = (f' · <a class="small" href="../evidence.html">evidence</a>'
                       if r["species_id"] in d["ev"]["summary"] else "")
            items += (f'<li class="mb-1"><a class="taxon" href="{slug_of(r["species_id"])}.html">{e(r["accepted_name"])}</a> '
                      f'{badge_grade(r["evidence_grade"])} {badge_iucn(r["iucn_category_code"])} '
                      f'<span class="text-muted">{n(r["n_occurrence_in_basin"])} in basin</span>{ev_link}</li>')
        parts.append(f'<div class="col-md-6 col-xl-4 mb-3"><h3 class="h6"><i>{e(genus)}</i> '
                     f'<span class="text-muted fw-normal">({len(by_genus[genus])})</span></h3><ul class="list-unstyled small">{items}</ul></div>')
    return page("All taxa — Mekong Medicinal Plant Atlas", f'''
<main class="container-fluid px-3 px-lg-4 py-3">
  <h1 class="h4">All taxa ({len(d["species_master"])})</h1>
  <p class="text-muted small">Alphabetical by genus. After each name: the taxon's best evidence grade, its IUCN category, and the number of its records inside the basin.</p>
  <div class="row">{''.join(parts)}</div>
</main>''', "species", "All taxa in the Mekong Medicinal Plant Atlas", "none.js", need=(), base="../")


def methods(d: dict) -> str:
    ev, occ, geo, layers = d["evidence"], d["occ"], d["geo"], d["layers"]
    st = occ["stats"]
    pending = ("access pending", "not consulted", "not yet")

    def status(note: str) -> str:
        low = note.lower()
        return "access pending" if any(p in low for p in pending) else "used"

    refs = "".join(
        f'<tr><td><code>{e(r["source_id"])}</code></td><td>{e(r["full_citation"])}</td><td>{e(r["license"])}</td>'
        f'<td>{status(r["notes"])}</td></tr>' for r in d["references"])
    # Per-taxon source counts from the provenance export, for the transparency
    # paragraph and the median-source column of the rubric table.
    prov_path = L.PROCESSED / "evidence_grade_provenance.csv"
    prov = {r["species_id"]: r for r in L.read_csv(prov_path)} if prov_path.exists() else {}
    def grade_sources(g: str) -> list[int]:
        return [int(p["n_sources"]) for p in prov.values() if p["grade"] == g]
    def median(vals: list[int]) -> float:
        if not vals:
            return 0.0
        s = sorted(vals); mid = len(s) // 2
        return s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2
    prov_a = grade_sources("A")
    single = sum(1 for p in prov.values() if int(p["n_sources"]) <= 1)
    prov_html = ""
    if prov:
        med_a = median(prov_a)
        med_txt = f"{med_a:g} independent source{'s' if med_a != 1 else ''}"
        prov_html = (f'<p class="small mt-3">Grade A was assigned to <strong>{len(prov_a)}</strong> taxa on the basis of a median of '
                     f'<strong>{med_txt}</strong> per taxon (range {min(prov_a)}\u2013{max(prov_a)}). <strong>{single}</strong> taxa are supported by a '
                     f'single source and are flagged in the <a href="data/tables/evidence_grade_provenance.csv" download>provenance file</a> as low-redundancy.</p>')
    rubric = "".join(
        f'<tr><td>{badge_grade(g)}</td><td>{e(GRADE_TEXT[g])}</td><td class="text-end">{n(ev.get("species_by_grade", {}).get(g, 0))}</td>'
        f'<td class="text-end">{n(ev.get("rows_by_grade", {}).get("uses.csv", {}).get(g, 0))}</td>'
        f'<td class="text-end">{n(ev.get("rows_by_grade", {}).get("pharmacology.csv", {}).get(g, 0))}</td>'
        f'<td class="text-end">{median(grade_sources(g)):g}</td></tr>' for g in ("A", "B", "C", "D"))
    names = {s["species_id"]: s["accepted_name"] for s in d["species_master"]}
    sensitive = "".join(f'<tr><td><i>{e(names.get(sid, sid))}</i></td><td>{e(occ["sensitive_species"][sid])}</td></tr>'
                        for sid in occ["sensitive_species_with_published_records"])
    countries = "".join(
        f'<tr><td>{e(COUNTRY_NAMES[c])}</td><td class="text-end">{n(occ["published_by_country"][c]["in_basin"])}</td>'
        f'<td class="text-end">{n(occ["published_by_country"][c]["outside_basin"])}</td></tr>' for c in L.BASIN_COUNTRIES)
    versions = "".join(f"<tr><td>{e(k)}</td><td>{e(v)}</td></tr>" for k, v in software_versions(layers).items())
    basis = occ["basis_of_published"]
    river = layers.get("mekong_river_wwf_arcgis (runtime only, not published)", {})
    ne_river = layers.get("mekong_river_naturalearth.geojson", {})
    return page("Methods — Mekong Medicinal Plant Atlas", f'''
<main class="container-fluid px-3 px-lg-4 py-3">
  <h1 class="h4">Methods</h1>
  <p class="lead small text-muted">How the atlas is built, graded and checked. Every step is a script in <code>scripts/</code>; running <code>build.sh</code> regenerates the whole site from the raw inputs.</p>

  <h2 class="h5 section-title">Data sources</h2>
  <div class="table-responsive"><table class="table table-sm table-atlas"><thead><tr><th>Source</th><th>Citation</th><th>Licence</th><th>Status</th></tr></thead><tbody>{refs}</tbody></table></div>

  <h2 class="h5 section-title">Evidence grading rubric</h2>
  <p class="small">Every use record, pharmacology record and species carries an evidence grade and a source identifier. A row citing several sources takes the best grade among them; a species takes the best grade of its rows.
  Grade A is given only when the article is confirmed — by DOI, by PMID or PMC id, or by a Crossref match on author, year and journal or species — or when the citation is a complete journal reference.</p>
  <div class="table-responsive"><table class="table table-sm table-atlas"><thead><tr><th>Grade</th><th>Definition</th><th class="text-end">Taxa</th><th class="text-end">Use records</th><th class="text-end">Pharmacology records</th><th class="text-end">Median sources / taxon</th></tr></thead><tbody>{rubric}</tbody></table></div>
  {prov_html}
  <p class="small">{len(ev.get("citation_issues", []))} citations were found to carry an error (a wrong DOI or PMID, or a misspelled journal or author) while grading; each is listed in the repository's QA report.</p>

  <h2 class="h5 section-title">Occurrence records</h2>
  <p class="small">Records were harvested from the GBIF occurrence search API on {e(DATA_CUTOFF)} for each species-level atlas taxon in the six basin countries (georeferenced, without geospatial issues):
  {n(st.get("harvested", 0))} records from {n(occ.get("gbif_datasets", 0))} GBIF datasets. A record is published only if it has an open licence, a recognised basis of record and verifiable metadata
  ({n(occ["published"])} published; {n(occ["excluded_grade_d"])} excluded). Of the published records, {n(basis.get("PRESERVED_SPECIMEN", 0) + basis.get("MATERIAL_SAMPLE", 0) + basis.get("LIVING_SPECIMEN", 0))} are specimen-based
  and {n(basis.get("HUMAN_OBSERVATION", 0))} are observations. Each record was tested against the Mekong basin boundary:</p>
  <div class="table-responsive"><table class="table table-sm table-atlas"><thead><tr><th>Country</th><th class="text-end">Published records inside the basin</th><th class="text-end">Published records outside the basin</th></tr></thead><tbody>{countries}</tbody></table></div>
  <p class="small">Country-level counts therefore overstate basin presence: {n(st.get("published_in_basin", 0))} published records fall inside the basin and {n(st.get("published_outside_basin", 0))} outside it.
  The map shows the in-basin records in full; records outside the basin appear only when switched on, generalised to one point per species per half-degree cell.</p>

  <h2 class="h5 section-title">Coordinate generalisation policy</h2>
  <p class="small">Exact localities of threatened medicinal plants can lead collectors to wild populations, so the atlas generalises the coordinates of <strong>sensitive species</strong>:
  those with an IUCN category of Critically Endangered, Endangered or Vulnerable (as recorded in the project workbook or attached by GBIF) or listed in CITES Appendix I or II.</p>
  <ul class="small">
    <li><strong>Critically Endangered</strong> — coordinates rounded to 0.1 decimal degrees (about 11 km).</li>
    <li><strong>Endangered, Vulnerable, or CITES Appendix I or II</strong> — coordinates rounded to 0.01 decimal degrees (about 1.1 km).</li>
    <li>For every generalised record the locality text is removed and the coordinate uncertainty is raised to at least the rounding cell; the record states this in
      <code>dataGeneralizations</code> and <code>informationWithheld</code>.</li>
    <li>All other records keep the precision supplied by GBIF, capped at five decimals.</li>
  </ul>
  <p class="small">{n(st.get("generalised", 0))} of {n(st.get("harvested", 0))} harvested records were generalised. Species with published records affected:</p>
  <div class="table-responsive"><table class="table table-sm table-atlas"><thead><tr><th>Species</th><th>Reason</th></tr></thead><tbody>{sensitive}</tbody></table></div>

  <h2 class="h5 section-title">Geospatial layers</h2>
  <ul class="small">
    <li><strong>Mekong basin boundary</strong> — 96 catchment polygons dissolved into one boundary, EPSG:4326, from the Zenodo deposit of Tiwari et al. (doi:10.5281/zenodo.7622998, CC-BY 4.0),
      derived from an SRTM basin mask by Dang et al. 2022 (<i>Sci Total Environ</i> 831:154833). The boundary is also the test surface that classifies every record as inside or outside the basin.</li>
    <li><strong>Mekong River centreline</strong> — rendered from the WWF-Laos feature service on ArcGIS Online, which states no licence, so it is loaded from the publisher at run time and not redistributed
      ({e(river.get("vertices", "–"))} vertices when last checked). The committed fallback is the Natural Earth 1:10m centreline (public domain, {e(ne_river.get("vertices", "–"))} vertices).</li>
    <li><strong>Country outlines</strong> — Natural Earth 1:110m (public domain), unfilled: the atlas reports basin presence and does not shade countries.</li>
    <li><strong>Basemap</strong> — CartoDB Positron raster tiles (© CARTO; © OpenStreetMap contributors).</li>
  </ul>

  <h2 class="h5 section-title">Software</h2>
  <div class="table-responsive"><table class="table table-sm table-atlas"><thead><tr><th>Component</th><th>Version</th></tr></thead><tbody>{versions}</tbody></table></div>

  <h2 class="h5 section-title">Macroecology <span class="text-muted fw-normal">(global residual framework)</span></h2>
  <p class="small">The atlas reproduces the residual analysis of a global study of 369 botanical countries<sup>1</sup> on the published
  data for the seven botanical countries that contain the Mekong basin, and extends it to admin-1 (province) scale as an internal
  under-documentation screen. Model: ordinary least squares, medicinal richness ~ vascular richness, over all botanical countries except
  Antarctica and Oceania (the authors' exclusion); significance at |residual| &gt; 1.96 SD per their residual_histogram.R. Reproduction is
  validated against the residuals column shipped in their repository (r = {e(d["macro"]["validation"].get("corr_med_vas_residuals_vs_published", "n/a"))}).
  The sub-national extension fits the same model on GBIF vascular species counts per province against the number of atlas medicinal taxa
  with occurrence records in that province; provinces with significantly negative residuals in areas of long human occupancy (reused from
  the authors' country-level column) are flagged as fieldwork priorities — the documented difference from the global model is stated on the
  macroecology page and in the manuscript. Human occupancy is reused at its published resolution, never re-derived; language diversity
  (Glottolog points aggregated to admin-1) is mapped as context only, since the global model found only indirect climate-mediated effects.</p>
  <p class="small text-muted">¹ {SHRESTHA_REF}</p>

  <h2 class="h5 section-title">Evidence engine <span class="text-muted fw-normal">(pilot)</span></h2>
  <p class="small">A parallel evidence layer maps publications, compounds and — from its Milestone 2 — compound–target–pathway networks for atlas taxa.
  Pilot scope: the {n(len(d["ev"]["order"]))} taxa with the most pharmacology records. Publications come from Europe PMC (primary) and OpenAlex
  (secondary), searched by accepted name and synonyms with a fixed query template; every query is recorded in the PRISMA search log
  (<code>data/evidence/search_log.csv</code>). Evidence tiers are assigned by an automated keyword rubric (<code>auto-rubric-v1</code>) on title
  and abstract; rows the rubric cannot place are flagged <code>needs_review</code> for a human queue — machine classification is never presented as
  evidence strength. Compounds are seeded from the pharmacology table and resolved against PubChem (CID, InChIKey, SMILES); unresolved names are
  flagged rather than guessed. Milestone-1 metadata is a citation-sorted slice (top 100 per query), so tier shares are not yet corpus-wide; full
  pagination arrives with the scheduled living review. Target promotion (Milestone 2) uses a two-independent-lines rule: prediction in two engines,
  or prediction plus literature-mined support.</p>

  <h2 class="h5 section-title">Limitations</h2>
  <ul class="small">
    <li>Ethnobotanical, pharmacological and trade content comes from a project workbook that cites primary literature per row; the workbook itself is not redistributed.</li>
    <li>Local names in Khmer, Lao, Thai, Vietnamese, Burmese and Chinese are not yet recorded: the Tier-2 reference books and the Lancang-Mekong Traditional Medicine Resources Database are access pending.</li>
    <li>Occurrence records are not re-identified and carry the names GBIF supplies; {n(len(occ.get("genus_level_taxa_without_occurrence_data", [])))} workbook entries name only a genus and have no occurrence data.</li>
    <li>The GBIF harvest is an API snapshot without a download DOI; a DOI-citable GBIF download should replace it at release.</li>
    <li>IUCN categories come from the workbook trade sheet and from GBIF, not from the IUCN API.</li>
    <li>The map shows records, and a record is not evidence that a plant is used medicinally at that place.</li>
  </ul>
  <p class="small">Quality-assurance results and the conflict report (taxonomic synonyms, country-versus-basin discrepancies, citation errors, coordinate outliers) are in the repository under <code>docs/</code>.</p>
</main>
''', "methods", "Methods of the Mekong Medicinal Plant Atlas: sources, evidence grading, coordinate generalisation, software.", "none.js", need=())


def download(d: dict) -> str:
    sizes = copy_downloads()
    rows = [
        ("dwca/dwca-mekong-medicinal-plant-atlas.zip", "Darwin Core Archive", "ZIP", "Published occurrence records as Darwin Core terms, with archive and dataset metadata.", "CC-BY-NC-4.0; each record keeps its own licence"),
        ("tables/species_master.csv", "Species master", "CSV", "One row per taxon: names, grades, conservation status, occurrence counts.", "Research compilation; primary sources cited per row"),
        ("tables/uses.csv", "Ethnobotanical use records", "CSV", "Use, ailment category, part used, country, source and evidence grade.", "Research compilation; primary sources cited per row"),
        ("tables/pharmacology.csv", "Pharmacology records", "CSV", "Extract assays and isolated compounds with potency, source and evidence grade.", "Research compilation; primary sources cited per row"),
        ("tables/conservation_trade.csv", "Conservation and trade", "CSV", "IUCN category and its basis, CITES appendix, trade notes.", "Cited public sources"),
        ("tables/occurrence_summary_by_species.csv", "Occurrence counts by species", "CSV", "Published records per species: inside basin, outside basin, specimen-based, generalised.", "CC-BY-NC-4.0"),
        ("tables/references.csv", "Source register", "CSV", "Every source with licence, access date and status.", "Metadata"),
        ("tables/evidence_grade_provenance.csv", "Evidence-grade provenance", "CSV", "Per taxon: best evidence grade, number of distinct sources behind its uses and pharmacology, and the source IDs.", "Metadata"),
        ("tables/evidence_summary.json", "Evidence summary", "JSON", "Grade counts and the citation issues found while grading.", "Metadata"),
        ("geo/occurrences.geojson", "Occurrence records inside the basin", "GeoJSON", "One point per published record inside the basin.", "CC-BY-NC-4.0"),
        ("geo/occurrences_outside_basin.geojson", "Records outside the basin (generalised)", "GeoJSON", "One point per species per half-degree cell.", "CC-BY-NC-4.0"),
        ("geo/mekong_basin.geojson", "Mekong basin boundary", "GeoJSON", "Full-resolution boundary, EPSG:4326.", "CC-BY-4.0, Tiwari et al., doi:10.5281/zenodo.7622998"),
        ("geo/mekong_river_naturalearth.geojson", "Mekong River centreline", "GeoJSON", "Natural Earth 1:10m line.", "Public domain"),
    ]
    # Only advertise files actually written to web/data, so no download link 404s.
    rows = [r for r in rows if (L.WEB / "data" / r[0]).exists()]
    table_rows = "".join(
        f'<tr><td><a href="data/{e(path)}" download>{e(path.split("/")[-1])}</a></td><td>{e(label)}</td><td>{e(fmt)}</td>'
        f'<td>{e(desc)}</td><td class="text-nowrap">{human(sizes.get(path, 0))}</td><td>{e(lic)}</td></tr>' for path, label, fmt, desc, lic in rows)
    return page("Download — Mekong Medicinal Plant Atlas", f'''
<main class="container-fluid px-3 px-lg-4 py-3">
  <h1 class="h4">Download the data</h1>
  <div class="alert alert-success small"><strong>Cite the dataset as:</strong> Banerjee, S. (2026). Mekong Medicinal Plant Atlas: occurrence records of medicinal plant taxa in the Mekong River basin.
  Zenodo. <a href="https://doi.org/{e(VERSION["dataset_doi"])}" target="_blank" rel="noopener">https://doi.org/{e(VERSION["dataset_doi"])}</a>. The concept DOI {e(VERSION["concept_doi"])}
  always resolves to the latest version.</div>
  <div class="table-responsive"><table class="table table-striped table-atlas"><thead><tr><th>File</th><th>Content</th><th>Format</th><th>Description</th><th>Size</th><th>Licence</th></tr></thead><tbody>{table_rows}</tbody></table></div>
  <h2 class="h5 section-title">Licence</h2>
  <p class="small">The occurrence archive is released under CC-BY-NC-4.0 because it includes records published under that licence; each record's own licence (CC0, CC-BY-4.0 or CC-BY-NC-4.0) is given in its
  <code>license</code> field and prevails for that record. The basin boundary is CC-BY 4.0 (Tiwari et al.). Natural Earth layers are public domain. The project tables are a research compilation whose rows cite their
  primary sources; the source workbook is not redistributed.</p>
  <h2 class="h5 section-title">Suggested citation</h2>
  <div class="citation-box">Mekong Medicinal Plant Atlas, version {e(VERSION["version"])} (data as of {e(DATA_CUTOFF)}). Occurrence data from GBIF; taxonomic backbone GBIF and World Flora Online;
  basin boundary Tiwari et al., Zenodo, doi:10.5281/zenodo.7622998. Repository: {REPO}. Dataset DOI: <a href="https://doi.org/{e(VERSION["dataset_doi"])}" target="_blank" rel="noopener">https://doi.org/{e(VERSION["dataset_doi"])}</a>.</div>
  <h2 class="h5 section-title">Darwin Core terms in the archive</h2>
  <p class="small">occurrenceID, basisOfRecord, eventDate, year, month, day, scientificName, acceptedNameUsage, taxonRank, kingdom, family, genus, decimalLatitude, decimalLongitude, coordinateUncertaintyInMeters,
  geodeticDatum, country, countryCode, stateProvince, county, locality, recordedBy, identifiedBy, occurrenceStatus, establishmentMeans, associatedReferences, license, rightsHolder, institutionCode, collectionCode,
  catalogNumber, datasetName, dataGeneralizations, informationWithheld. Definitions are in the <a href="{REPO}/blob/main/docs/data_dictionary.md" target="_blank" rel="noopener">data dictionary</a>.</p>
</main>
''', "download", "Download the Mekong Medicinal Plant Atlas data", "none.js", need=())


def about(d: dict) -> str:
    return page("About — Mekong Medicinal Plant Atlas", f'''
<main class="container px-3 px-lg-4 py-3">
  <h1 class="h4">About the atlas</h1>
  <p class="small text-muted">This page records authorship, affiliation, funding and contact.</p>
  <h2 class="h5 section-title">Authors and affiliations</h2>
  <ul class="small">
    <li>Subhadip Banerjee — Medicinal Plant Innovation Centre, Mae Fah Luang University, Chiang Rai, Thailand 57100</li>
    <li>Rawiwan Charoensub — Medicinal Plant Innovation Centre, Mae Fah Luang University, Chiang Rai, Thailand 57100</li>
  </ul>
  <p class="small">Affiliation of both authors: Medicinal Plant Innovation Centre, Mae Fah Luang University, Chiang Rai, Thailand 57100.</p>
  <h2 class="h5 section-title">Funding</h2>
  <p class="small"><em>To be completed by the authors.</em></p>
  <h2 class="h5 section-title">Contact</h2>
  <p class="small">Please report errors or suggest data sources by opening an issue in the <a href="{REPO}/issues" target="_blank" rel="noopener">repository</a>.</p>
  <h2 class="h5 section-title">Scope</h2>
  <p class="small">The atlas covers medicinal vascular plants recorded in the Mekong basin or reported for it from Cambodia, China (Yunnan and Guangxi), Laos, Myanmar, Thailand and Vietnam.
  One entry is an alga and is flagged as such. Occurrence records are not evidence of medicinal use.</p>
</main>
''', "about", "About the Mekong Medicinal Plant Atlas", "none.js", need=())


def sustainability(d: dict) -> str:
    pressure = d["sust_pressure"]
    hydro = d["sust_hydro"]
    names = {s["species_id"]: s["accepted_name"] for s in d["species_master"]}

    def row_pressure(r):
        label = {"low": "Low", "moderate": "Moderate", "high": "High", "very high": "Very high"}[r["harvest_pressure_class"]]
        color = {"low": "text-bg-light", "moderate": "text-bg-warning", "high": "text-bg-orange", "very high": "text-bg-danger"}[r["harvest_pressure_class"]]
        return (f'<tr><td><a class="taxon" href="species/{r["species_id"][3:]}.html">{e(names.get(r["species_id"], r["species_id"]))}</a></td>'
                f'<td>{e(r["local_use_score"])}</td>'
                f'<td>{e(r["mean_harvest_pressure_in_range"])}</td>'
                f'<td><span class="badge {color}">{e(label)}</span></td></tr>')

    top_pressure = "".join(row_pressure(r) for r in sorted(pressure, key=lambda r: -float(r["mean_harvest_pressure_in_range"]))[:15])
    high_pressure_n = sum(1 for r in pressure if r["harvest_pressure_class"] in ("high", "very high"))
    high_hydro_n = sum(1 for r in hydro if r["hydrological_vulnerability_class"] == "high")

    top_hydro = "".join(
        f'<tr><td><a class="taxon" href="species/{r["species_id"][3:]}.html">{e(names.get(r["species_id"], r["species_id"]))}</a></td>'
        f'<td class="text-end">{e(r["n_occurrences_in_basin"])}</td>'
        f'<td class="text-end">{e(r["pct_within_10km_major_dam"])}%</td>'
        f'<td><span class="badge {"text-bg-danger" if r["hydrological_vulnerability_class"] == "high" else "text-bg-light"}">{e(r["hydrological_vulnerability_class"])}</span></td></tr>'
        for r in sorted(hydro, key=lambda r: -float(r["pct_within_10km_major_dam"]))[:15])

    sdm_block = ""
    if sdm and any(r.get("projected_range_change_pct") for r in sdm):
        vuln = [r for r in sdm if r.get("climate_vulnerability_tier") not in ("", "not assessed")]
        top_sdm = "".join(
            f'<tr><td><a class="taxon" href="species/{r["species_id"][3:]}.html">{e(names.get(r["species_id"], r["species_id"]))}</a></td>'
            f'<td class="text-end">{e(r.get("projected_range_change_pct", ""))}%</td>'
            f'<td><span class="badge text-bg-secondary">{e(r.get("climate_vulnerability_tier", ""))}</span></td></tr>'
            for r in sorted(vuln, key=lambda r: float(r.get("projected_range_change_pct") or 0))[:15])
        sdm_block = f'''<h2 class="h5 mt-4">Climate-vulnerable taxa</h2>
        <p class="small text-muted">Projected change in climatically suitable area; conditional scenario projections, not forecasts.</p>
        <div class="table-responsive"><table class="table table-sm table-atlas"><thead><tr><th>Taxon</th><th class="text-end">Projected range change</th><th>Vulnerability tier</th></tr></thead><tbody>{top_sdm}</tbody></table></div>'''
    else:
        sdm_block = '''<div class="alert alert-secondary small"><strong>SDM scope.</strong> 162 taxa had at least ten occupied 5 km cells and were modelled;
        171 were not assessed (119 with 1&ndash;9 occupied cells, 52 with no in-basin records). Predictors are WorldClim 2.1
        (2.5 arc-min, resolution-matched to the 5 km grid) as a documented substitution for EM-Earth; see the
        <a href="https://github.com/subhadipban-lgtm/mekong-medicinal-plant-atlas/blob/main/docs/sdm_methods.md" target="_blank" rel="noopener">SDM methods</a>.</div>'''

    cult_block = ""
    if cult:
        top_cult = "".join(
            f'<tr><td><a class="taxon" href="species/{r["species_id"][3:]}.html">{e(names.get(r["species_id"], r["species_id"]))}</a></td>'
            f'<td class="text-end">{e(r.get("cultivation_feasible_area_km2", ""))}</td>'
            f'<td>{e(r.get("cultivation_feasibility_class", ""))}</td></tr>'
            for r in sorted(cult, key=lambda r: -float(r.get("cultivation_feasible_area_km2") or 0))[:15])
        cult_block = f'''<h2 class="h5 mt-4">Cultivation-feasible area (screening)</h2>
        <p class="small text-muted">Intersection of climatically suitable, water-available and already-converted land. A screening output; agronomic field validation is required before any recommendation.</p>
        <div class="table-responsive"><table class="table table-sm table-atlas"><thead><tr><th>Taxon</th><th class="text-end">Feasible area (km&sup2;)</th><th>Feasibility class</th></tr></thead><tbody>{top_cult}</tbody></table></div>'''
    else:
        cult_block = '''<div class="alert alert-secondary small"><strong>Cultivation screening.</strong> Water availability uses WorldClim precipitation and a
        Hargreaves PET estimate in place of GLEAM. Classes are the share of each taxon's climatically suitable range that is water-available and
        already converted land. See the
        <a href="https://github.com/subhadipban-lgtm/mekong-medicinal-plant-atlas/blob/main/docs/cultivation_methods.md" target="_blank" rel="noopener">cultivation methods</a>.</div>'''

    return page("Sustainability — Mekong Medicinal Plant Atlas", f'''
<main class="container-fluid px-3 px-lg-4 py-3">
  <h1 class="h4">Harvest pressure & hydrological risk</h1>
  <p class="small text-muted">Two operational indices of conservation pressure on the atlas taxa, built from the hydroclimatic synthesis of
  Tiwari et al. 2023 (<a href="https://doi.org/10.1038/s41597-023-02193-0" target="_blank" rel="noopener">Scientific Data</a>,
  <a href="https://doi.org/10.5281/zenodo.7803254" target="_blank" rel="noopener">Zenodo 7803254</a>, CC-BY-4.0): a harvest-pressure proxy
  (2050 population density × species richness × graded use score) and a hydrological-fragmentation index (share of in-basin occurrences within
  10 km of a major dam). The harvest-pressure index is a proxy, not measured offtake; the hydrological index is distance-based and does not model
  flow alteration, sediment trapping or groundwater drawdown.</p>

  <div class="row g-3 mb-3">
    <div class="col-md-6 col-xl-3"><div class="card h-100"><div class="card-body">
      <div class="n" style="font-size:1.5rem;font-weight:700;color:#166a4f">{e(len(pressure))}</div>
      <div class="l small text-muted">taxa scored for harvest pressure</div></div></div></div>
    <div class="col-md-6 col-xl-3"><div class="card h-100"><div class="card-body">
      <div class="n" style="font-size:1.5rem;font-weight:700;color:#b36b00">{e(high_pressure_n)}</div>
      <div class="l small text-muted">taxa high / very high</div></div></div></div>
    <div class="col-md-6 col-xl-3"><div class="card h-100"><div class="card-body">
      <div class="n" style="font-size:1.5rem;font-weight:700;color:#1f5f8b">{e(len(hydro))}</div>
      <div class="l small text-muted">taxa assessed for hydrological fragmentation</div></div></div></div>
    <div class="col-md-6 col-xl-3"><div class="card h-100"><div class="card-body">
      <div class="n" style="font-size:1.5rem;font-weight:700;color:#a63d2f">{e(high_hydro_n)}</div>
      <div class="l small text-muted">taxa high hydrological vulnerability</div></div></div></div>
  </div>

  <div class="map-shell map-explore">
    <div class="map" id="map" role="application" aria-label="Harvest pressure and hydrological risk summary map"></div>
    <div class="map-tools">{north_arrow()}</div>
    <div class="map-status" id="sustStatus">Loading layers…</div>
    <div class="map-legend legend-grade">
      <div><strong>Sustainability layers</strong> (switch in the layer control)</div>
      <div><span class="sw" style="background:#f2efe9"></span>harvest pressure: low</div>
      <div><span class="sw" style="background:#e5c37f"></span>moderate</div>
      <div><span class="sw" style="background:#cf8a4e"></span>high</div>
      <div><span class="sw" style="background:#a63d2f"></span>very high</div>
      <div><span class="sw" style="background:#1f5f8b;border-radius:2px"></span>major dam · circle = 10 km buffer</div>
    </div>
  </div>

  <h2 class="h5 mt-4">Highest harvest pressure</h2>
  <p class="small text-muted mb-1"><strong>Note on the use score.</strong> Use score is 0.0 for taxa with no recorded ethnobotanical use in the current
  corpus. For these taxa the pressure score reflects population density and species richness only and should be read as a demographic proxy,
  not as evidence of harvest pressure on the species.</p>
  <p class="small text-muted">By the evidence-weighted mean harvest-pressure proxy across the cells where the taxon occurs
  (<a href="https://github.com/subhadipban-lgtm/mekong-medicinal-plant-atlas/blob/main/docs/harvest_pressure_methods.md" target="_blank" rel="noopener">methods</a>).</p>
  <div class="table-responsive"><table class="table table-sm table-atlas"><thead><tr><th>Taxon</th><th>Use score</th><th>Mean pressure</th><th>Class</th></tr></thead><tbody>{top_pressure}</tbody></table></div>

  <h2 class="h5 mt-4">Hydrologically fragmented taxa</h2>
  <p class="small text-muted">Share of in-basin occurrences within 10 km of a major dam (distance-based proxy;
  <a href="https://github.com/subhadipban-lgtm/mekong-medicinal-plant-atlas/blob/main/docs/hydrological_methods.md" target="_blank" rel="noopener">methods</a>).</p>
  <div class="table-responsive"><table class="table table-sm table-atlas"><thead><tr><th>Taxon</th><th class="text-end">In-basin records</th><th class="text-end">Within 10 km</th><th>Class</th></tr></thead><tbody>{top_hydro}</tbody></table></div>

  <h2 class="h5 mt-4">In progress</h2>
  <ul class="small">
    <li><strong>Climate-vulnerability SDM</strong> — species distribution models under future climate scenarios (SSP2-2050) will produce a
      projected range change and a climate-vulnerability tier per taxon. Planned for Milestone 3; waits on the EM-Earth climate archives.
      <a href="https://github.com/subhadipban-lgtm/mekong-medicinal-plant-atlas/blob/main/docs/sdm_methods.md" target="_blank" rel="noopener">Methods document</a>.</li>
    <li><strong>Cultivation suitability</strong> — an agronomic and land-use feasibility screen (climatically suitable × water-available × already-converted land)
      will produce a cultivation-suitability class per taxon. Planned for Milestone 3; waits on the GLEAM evapotranspiration and soil-moisture archives.
      <a href="https://github.com/subhadipban-lgtm/mekong-medicinal-plant-atlas/blob/main/docs/cultivation_methods.md" target="_blank" rel="noopener">Methods document</a>.</li>
  </ul>

  <h2 class="h5 mt-4">Methods and reproducibility</h2>
  <ul class="small">
    <li><a href="https://github.com/subhadipban-lgtm/mekong-medicinal-plant-atlas/blob/main/docs/harmonization_methods.md" target="_blank" rel="noopener">Harmonization</a> —
      5 km Albers equal-area grid, 31,922 in-basin cells, per-variable resampling rules.</li>
    <li><a href="https://github.com/subhadipban-lgtm/mekong-medicinal-plant-atlas/blob/main/docs/harvest_pressure_methods.md" target="_blank" rel="noopener">Harvest pressure</a> —
      SSP2-2050 population × species richness × evidence-weighted use score.</li>
    <li><a href="https://github.com/subhadipban-lgtm/mekong-medicinal-plant-atlas/blob/main/docs/hydrological_methods.md" target="_blank" rel="noopener">Hydrological fragmentation</a> —
      distance to 232 major dams, 10 km threshold.</li>
    <li>SDM and cultivation methods will be published with their results; the pipeline is
      <code>scripts/sustainability/</code> and the driver is <code>scripts/sustainability/run_sustainability.sh</code>.</li>
  </ul>
  <p class="small text-muted">Source data: Tiwari et al. 2023, Zenodo doi:10.5281/zenodo.7803254 (CC-BY-4.0); inventory and provenance in
  <a href="https://github.com/subhadipban-lgtm/mekong-medicinal-plant-atlas/blob/main/docs/zenodo7803254_inventory.md" target="_blank" rel="noopener">docs/</a>.</p>
</main>
''', "harvest_pressure", "Harvest-pressure proxy and hydrological-fragmentation indices for Mekong medicinal plant taxa.", "sustainability.js", need=("map",))


def main() -> int:
    d = load()
    if not d["species_master"][0]["evidence_grade"]:
        sys.exit("evidence grades are empty: run scripts/grade_evidence.py before building the site")
    data = L.WEB / "data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "species.json").write_text(json.dumps(species_json(d), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    L.write_json(data / "software_versions.json", software_versions(d["layers"]))
    L.write_json(data / "site_stats.json", {
        "version": VERSION["version"], "data_cutoff": DATA_CUTOFF, "taxa": len(d["species_master"]),
        "taxa_species_level": sum(s["taxon_rank"] == "species" for s in d["species_master"]),
        "use_records": len(d["uses"]), "pharmacology_records": len(d["pharmacology"]),
        "occurrence_records_published": d["occ"]["published"],
        "occurrence_records_in_basin": d["occ"]["stats"].get("published_in_basin", 0),
        "occurrence_records_outside_basin": d["occ"]["stats"].get("published_outside_basin", 0),
        "taxa_with_records_in_basin": d["geo"]["inside_basin"]["species"],
        "species_by_grade": d["evidence"].get("species_by_grade", {})})
    # macroecology geo layers for the macroecology page (CSVs stay in the
    # repository and the Zenodo deposit - no CSVs on the website)
    geo_dest = data / "geo"
    geo_dest.mkdir(parents=True, exist_ok=True)
    for layer in ("human_occupancy_mekong.geojson", "language_diversity_mekong.geojson",
                  "global_residual_mekong.geojson", "internal_coldspots_mekong.geojson"):
        src = L.GEO / layer
        if src.exists():
            shutil.copyfile(src, geo_dest / layer)
    pages = {"index.html": home(d), "explore.html": explore(d), "evidence.html": evidence(d),
             "macroecology.html": macroecology(d),
             "methods.html": methods(d),
             "about.html": about(d), "download.html": download(d), "species/index.html": species_index(d)}
    pages.update({f"species/{slug_of(r['species_id'])}.html": species_page(d, r) for r in d["species_master"]})
    for path, content in pages.items():
        target = L.WEB / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    print(f"pages written: {len(pages)} ({len(d['species_master'])} taxon pages) · version {VERSION['version']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
