#!/usr/bin/env python3
"""Build the atlas base tables from raw inputs.

Inputs (data/raw):
  workbook/MEKONG_BASIN_NATURAL_PRODUCTS_*.xlsx   ethnobotany, assays, compounds, trade
  gbif_match_raw.json, gbif_species_records.json, gbif_synonyms.json   GBIF backbone
  gbif_occurrence_counts.json                     GBIF occurrence/count snapshot (all records)
  wfo_match.csv                                   WorldFlora::WFO.match output

Outputs (data/processed):
  species_master.csv, uses.csv, pharmacology.csv, conservation_trade.csv, references.csv
and sources/source_register.csv (the same register, written once).

Row identifiers are derived from the source worksheet row number, so they are stable
across rebuilds and cannot collide when a species occurs on several rows.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import atlas_lib as L  # noqa: E402

# Worksheet row (1-based, header = row 1) is added to each parsed row by load below.
NA, NS = L.normalize_species, L.species_id


def load_sheets() -> dict[str, list[dict]]:
    """Worksheet rows with their original Excel row number under key `_row`."""
    import openpyxl

    wb = openpyxl.load_workbook(L.WORKBOOK, read_only=True, data_only=True)
    out: dict[str, list[dict]] = {}
    for name in wb.sheetnames:
        rows = []
        for i, r in enumerate(wb[name].iter_rows(values_only=True), start=1):
            if i == 1:
                hdr = r
                continue
            if not any(c is not None and str(c).strip() for c in r):
                continue
            d = {h: r[j] for j, h in enumerate(hdr) if h}
            d["_row"] = i
            rows.append(d)
        out[name] = rows
    wb.close()
    return out


def s(v) -> str:
    return "" if v is None else str(v).strip()


def plain(v) -> str:
    """Workbook text without its markdown emphasis markers, for display."""
    return re.sub(r"\*", "", s(v))


# ---------------------------------------------------------------- ethnobotany categories
AILMENT_RULES = [
    ("gastrointestinal", ["digest", "stomach", "diarrho", "diarrh", "laxativ", "dysenter", "appetite", "gastric",
                          "ulcer", "intestine", "bowel", "emetic", "colic", "indigestion", "dyspepsia", "hepat",
                          "liver", "jaundice", "constipation", "colitis"]),
    ("respiratory", ["cough", "asthma", "bronch", "respirat", "cold", "throat", "tonsil", "expectorant", "sinus",
                     "pneumonia", "lung"]),
    ("dermatological", ["skin", "wound", "eczema", "scab", "burn", "lesion", "itch", "rash", "boil", "abscess", "dermat"]),
    ("musculoskeletal", ["rheuma", "joint", "arthritis", "muscle", "sprain", "backache", "gout", "pain"]),
    ("metabolic", ["diabet", "sugar", "glucose", "lipid", "cholesterol", "metabolic", "obesity"]),
    ("infectious", ["fever", "malaria", "infection", "antimicrobial", "antibacterial", "antiviral", "worm",
                    "parasite", "helminth", "dysentery"]),
    ("reproductive", ["menstrual", "menorrhagia", "amenorrho", "pregnan", "childbirth", "lactation", "fertility",
                      "aphrodisiac", "emmenagogue", "uter", "dysmenorrhea", "galactagogue"]),
    ("neurological", ["sedative", "sleep", "insomnia", "anxiety", "epilep", "headache", "neurolog", "calm",
                      "nervine", "migraine"]),
    ("cardiovascular", ["hypertension", "blood pressure", "cardiac", "heart", "circulat", "cardio"]),
    ("genitourinary", ["urin", "kidney", "bladder", "gonorrh", "cystitis", "renal"]),
]
AILMENT_CATEGORIES = [c for c, _ in AILMENT_RULES] + ["other"]


def categorize(text: str) -> str:
    t = text.lower()
    for cat, kws in AILMENT_RULES:
        if any(k in t for k in kws):
            return cat
    return "other"


# Category words as regexes: plain "endangered" must not match inside "critically endangered".
IUCN_WORDS = [("CR", r"critically\sendangered"), ("EN", r"(?<!critically\s)\bendangered\b"),
              ("VU", r"\bvulnerable\b"), ("NT", r"near\sthreatened"),
              ("LC", r"least\sconcern"), ("DD", r"data\sdeficient")]


def threat_status(text: str) -> tuple[str, str, str]:
    """(iucn_category_code, threat_category_reported, assessment_basis).

    A code is only reported as IUCN when the source says IUCN. National red lists and
    specialist statements keep their own category in `threat_category_reported` so they are
    not mistaken for global assessments. Unconfirmed statements yield no code.
    """
    t = s(text).replace("**", "")
    low = t.lower()
    if not t or t in ("—", "-"):
        return "", "", "not stated"
    if "not confirmed" in low:
        return "", "", "unconfirmed"
    found = [code for code, pattern in IUCN_WORDS if re.search(pattern, low)]
    reported = "/".join(dict.fromkeys(found))
    if "red data book" in low or "red book" in low or "red list" in low and "iucn" not in low:
        return "", reported, "national red list"
    if "iucn" in low:
        return reported, reported, "IUCN"
    if "described as" in low or "specialist" in low or "listed among" in low:
        return "", reported, "specialist literature"
    if reported:
        return reported, reported, "unstated (workbook statement)"
    return "", "", "not assessed"


def cites_code(text: str) -> str:
    low = s(text).lower()
    if "not cites-listed" in low or "not cites listed" in low:
        return "not listed"
    m = re.search(r"appendix\s+(i{1,3})\b", low)
    if m:
        return {"i": "I", "ii": "II", "iii": "III"}[m.group(1)]
    if "cites" in low:
        return "unknown"
    return "not listed"


# ---------------------------------------------------------------- species spine
def build_spine(sh: dict) -> dict[str, dict]:
    spine: dict[str, dict] = {}

    def get(norm: str, family: str = "") -> dict:
        row = spine.setdefault(NS(norm), {
            "species_id": NS(norm), "spine_name": norm, "genus": norm.split()[0], "family": "",
            "in_tier1": False, "in_tier2": False, "in_tier3": False, "assay_rows": 0, "compound_count": 0,
            "countries": "", "habit": "", "parts_used": ""})
        if family and not row["family"]:
            row["family"] = family
        return row

    for r in sh["1_Plants"]:
        n = NA(r.get("Species"))
        if not n:
            continue
        row = get(n, s(r.get("Family")))
        row.update(in_tier1=True, countries=s(r.get("Countries reported (basin)")),
                   habit=s(r.get("Habit")), parts_used=s(r.get("Parts used")))
    for r in sh["2_Extracts"]:
        n = NA(r.get("Species"))
        if n:
            get(n, s(r.get("Family")))["in_tier2"] = True
            spine[NS(n)]["assay_rows"] += 1
    for r in sh["3_Compounds"]:
        n = NA(r.get("Species"))
        if n:
            get(n, s(r.get("Family")))["in_tier3"] = True
            spine[NS(n)]["compound_count"] += 1
    return spine


def build_species_master(spine: dict, counts: dict) -> list[dict]:
    match = L.read_json(L.RAW / "gbif_match_raw.json")
    recs = L.read_json(L.RAW / "gbif_species_records.json")
    syns = L.read_json(L.RAW / "gbif_synonyms.json")
    by_name = {}
    for r in L.read_csv(L.RAW / "wfo_match.csv"):
        by_name.setdefault(r["spec.name"], []).append(r)
    wfo_best = {}
    for name, cands in by_name.items():
        acc = [c for c in cands if c.get("taxonomicStatus") == "Accepted"]
        wfo_best[name] = acc[0] if acc else (cands[0] if cands else None)

    trade: dict[str, dict] = {}
    for r in load_sheets()["6_Trade_CITES"]:
        n = NA(r.get("Species"))
        if n:
            trade[NS(n)] = r

    rows = []
    for sid, sp in sorted(spine.items()):
        name = sp["spine_name"]
        m = match.get(name, {})
        key = m.get("usageKey")
        rec = recs.get(str(key), {}) if key else {}
        full = rec.get("scientificName") or m.get("scientificName") or name
        canonical = rec.get("canonicalName") or m.get("canonicalName") or name
        authorship = full[len(canonical):].strip() if full.startswith(canonical) else ""
        occ = counts.get(str(key), {}) if key else {}
        occ_total = sum(v for v in occ.values() if isinstance(v, int)) if occ else 0
        t = trade.get(sid)
        w = wfo_best.get(name)
        g_bin = " ".join(full.split()[:2]).lower()
        w_bin = " ".join((w or {}).get("scientificName", "").split()[:2]).lower()
        countries = [c.strip().upper() for c in re.split(r"[;,]\s*", sp["countries"]) if c.strip()]
        countries = [({"CN-YN": "CN", "CN-GX": "CN"}.get(c, c)) for c in countries]
        countries = list(dict.fromkeys(countries))
        genus_level = len(name.split()) == 1
        rows.append({
            "species_id": sid,
            "accepted_name": canonical,
            "scientific_name_authorship": authorship,
            "family": rec.get("family") or m.get("family") or sp["family"],
            "genus": canonical.split()[0],
            "taxon_rank": "genus" if genus_level else "species",
            "synonyms": json.dumps(syns.get(str(key), []) if key else [], ensure_ascii=False),
            "common_names_json": "[]",
            "local_names_json": "{}",
            "countries_present": ",".join(countries),
            "mekong_basin_presence": "yes" if countries else (
                "GBIF records exist; country-level, basin intersection unverified" if occ_total > 0 else "unknown"),
            "life_form": sp["habit"] or "unknown",
            "parts_used": sp["parts_used"],
            "habitat": "",
            "wild_cultivated_status": "unknown",
            "iucn_status_verbatim": plain(t.get("Threat status")) if t else "",
            "iucn_category_code": (threat_status(t.get("Threat status"))[0] if t else ""),
            "threat_category_reported": (threat_status(t.get("Threat status"))[1] if t else ""),
            "assessment_basis": (threat_status(t.get("Threat status"))[2] if t else "not stated"),
            "national_status": (s(t.get("Threat status")).replace("**", "") if t and threat_status(t.get("Threat status"))[2] == "national red list" else ""),
            "cites_status_verbatim": plain(t.get("Regulatory / CITES")) if t else "",
            "cites_appendix": cites_code(t.get("Regulatory / CITES")) if t else "unknown",
            "trade_status": plain(t.get("Trade status")) if t else "",
            "source_ids": "SRC-001; SRC-002",
            "evidence_grade": "",
            "gbif_taxon_key": str(key) if key else "",
            "gbif_match_type": m.get("matchType", ""),
            "gbif_confidence": m.get("confidence", "") if m.get("confidence") is not None else "",
            "gbif_count_api_by_country": ";".join(f"{c}:{v}" for c, v in sorted(occ.items()) if isinstance(v, int)),
            "gbif_count_api_total": occ_total,
            "in_tier1": sp["in_tier1"], "in_tier2": sp["in_tier2"], "in_tier3": sp["in_tier3"],
            "wfo_accepted_name": (w or {}).get("scientificName", "") if w else "",
            "wfo_family": (w or {}).get("family", "") if w else "",
            "wfo_status": (w or {}).get("taxonomicStatus", "") if w else "",
            "gbif_vs_wfo": ("no_wfo_match" if not (w and w.get("scientificName"))
                            else "agree" if g_bin == w_bin else "differ"),
            "same_gbif_taxon_as": "",
            "notes": "Genus-level workbook entry; not identified to species." if genus_level else "",
        })
    # Two workbook names can resolve to one accepted species: both the synonym and the accepted name
    # may be listed. Their GBIF harvests then return the same occurrences, so the records must be
    # kept under one entry only. Grouping is by accepted taxon key, not by backbone key, because the
    # two names have different backbone keys (one accepted, one a synonym record).
    records = L.read_json(L.RAW / "gbif_species_records.json")
    def accepted_key(r: dict) -> str:
        d = records.get(str(r["gbif_taxon_key"])) or {}
        a = d.get("accepted")
        if isinstance(a, dict) and a.get("key"):
            return str(a["key"])
        return str(d.get("acceptedKey") or r["gbif_taxon_key"])

    groups: dict[str, list[dict]] = {}
    for r in rows:
        if r["gbif_taxon_key"]:
            groups.setdefault(accepted_key(r), []).append(r)
    for group in groups.values():
        if len(group) < 2:
            continue
        # The entry whose workbook name is already the accepted name keeps the occurrence records.
        primary = next((r for r in group if r["species_id"] == "sp_" + r["accepted_name"].lower().replace(" ", "_")), group[0])
        for r in group:
            if r is not primary:
                r["same_gbif_taxon_as"] = primary["species_id"]
                r["notes"] = "; ".join(x for x in (r["notes"], f"Same accepted species as {primary['accepted_name']}; "
                                                  "occurrence records are kept under that entry.") if x)
    return rows


def build_uses(sh: dict, spine: dict) -> list[dict]:
    rows = []
    for r in sh["1_Plants"]:
        n = NA(r.get("Species"))
        if not n or NS(n) not in spine:
            continue
        uses = s(r.get("Ethnomedical use(s)"))
        if not uses or uses.lower() in ("none", "na", "n/a", "-"):
            continue
        for i, u in enumerate([x.strip() for x in uses.split(";") if x.strip()], start=1):
            citation = s(r.get("Source citation"))[:300]
            rows.append({
                "use_id": f"use_{L.slug(n)}_r{r['_row']}_{i}",
                "species_id": NS(n),
                "country": s(r.get("Countries reported (basin)")) or "mekong-region",
                "ethnic_group": "",
                "ailment_category": categorize(u),
                "specific_use": u[:300],
                "used_part": s(r.get("Parts used"))[:120],
                "preparation": "",
                "administration": "",
                "source_id": "SRC-001" + ("; SRC-014" if citation else ""),
                "evidence_grade": "",
                "source_citation": citation,
                "grade_basis": "",
                "resolved_doi": "",
                "notes": "",
            })
    return rows


def build_pharmacology(sh: dict, spine: dict) -> list[dict]:
    rows = []
    for r in sh["2_Extracts"]:
        n = NA(r.get("Species"))
        if not n or NS(n) not in spine:
            continue
        ref = s(r.get("Reference"))
        value, unit = s(r.get("Value")), s(r.get("Unit"))
        try:
            pv = float(value) if value else ""
        except ValueError:
            pv = ""
        rows.append({
            "pharma_id": f"pha_ext_{L.slug(n)}_r{r['_row']}",
            "species_id": NS(n),
            "record_type": "extract_assay",
            "reported_activity": s(r.get("Activity")) or "activity reported (unspecified)",
            "chemical_constituents": "",
            "extract_or_fraction": s(r.get("Extract / fraction (solvent)")),
            "plant_part": s(r.get("Plant part")),
            "assay_or_study_type": s(r.get("Assay / model"))[:200],
            "potency_verbatim": s(r.get("Potency")),
            "potency_value": pv,
            "potency_unit": unit,
            "potency_status": s(r.get("Potency status")),
            "source_id": "SRC-001" + ("; SRC-014" if ref else ""),
            "evidence_grade": "",
            "source_citation": ref[:300],
            "grade_basis": "",
            "resolved_doi": "",
            "notes": "",
        })
    for r in sh["3_Compounds"]:
        n = NA(r.get("Species"))
        if not n or NS(n) not in spine:
            continue
        compound, cls = s(r.get("Compound")), s(r.get("Compound class"))
        ref, potency = s(r.get("Reference")), s(r.get("Potency"))
        rows.append({
            "pharma_id": f"pha_cmp_{L.slug(n)}_r{r['_row']}",
            "species_id": NS(n),
            "record_type": "isolated_compound",
            "reported_activity": s(r.get("Bioactivity (reported)")) or "bioactivity reported (unspecified)",
            "chemical_constituents": f"{compound} ({cls})" if compound and cls else (compound or cls),
            "extract_or_fraction": "",
            "plant_part": s(r.get("Plant part")),
            "assay_or_study_type": "isolated compound",
            "potency_verbatim": potency,
            "potency_value": "",
            "potency_unit": "",
            "potency_status": s(r.get("Potency status")),
            "source_id": "SRC-001" + ("; SRC-014" if ref else ""),
            "evidence_grade": "",
            "source_citation": ref[:300],
            "grade_basis": "",
            "resolved_doi": "",
            "notes": "",
        })
    return rows


def build_conservation(sh: dict, spine: dict) -> list[dict]:
    rows = []
    for r in sh["6_Trade_CITES"]:
        n = NA(r.get("Species"))
        if not n:
            continue
        sid, cites = NS(n), s(r.get("Regulatory / CITES"))
        in_spine = sid in spine
        rows.append({
            "conservation_id": f"con_{L.slug(n)}",
            "species_id": sid,
            "species_verbatim": s(r.get("Species")),
            "iucn_status": plain(r.get("Threat status")) or "not assessed",
            "iucn_category_code": threat_status(r.get("Threat status"))[0],
            "threat_category_reported": threat_status(r.get("Threat status"))[1],
            "assessment_basis": threat_status(r.get("Threat status"))[2],
            "cites_appendix": cites_code(cites),
            "cites_status_verbatim": plain(cites),
            "national_status": "",
            "trade_notes": plain(r.get("Trade status")),
            "source_id": "SRC-001" + ("; SRC-004" if "cites" in cites.lower() else ""),
            "in_spine": "yes" if in_spine else "no",
            "scope_flag": "" if in_spine else (
                "genus-level aggregate or non-spine taxon in the workbook trade sheet; kept for context, "
                "not joined to species tables"),
            "notes": s(r.get("Source"))[:300],
        })
    return rows


SOURCES = [
    ("SRC-001", "Mekong Basin Natural Products workbook (MEKONG_BASIN_NATURAL_PRODUCTS_2026-11-24.xlsx): sheets 1_Plants, "
     "2_Extracts, 3_Compounds, 4_Cross-tier, 5_Reviews, 6_Trade_CITES", "project_compilation",
     "local://data/raw/workbook (not redistributed; available from the authors on request)",
     "2026-11-24", "not licensed for redistribution", "n/a",
     "Internal research compilation. Every row cites its underlying source; grades are assigned to those citations, not to the workbook."),
    ("SRC-002", "GBIF Secretariat. GBIF Backbone Taxonomy. https://doi.org/10.15468/39omei", "database",
     "https://doi.org/10.15468/39omei", "2026-11-24", "CC-BY-4.0", "n/a",
     "Taxonomic backbone via species/match, species/{key} and synonyms endpoints."),
    ("SRC-003", "GBIF occurrence search API: georeferenced records of the atlas taxa in CN, TH, VN, LA, KH, MM", "database",
     "https://api.gbif.org/v1/occurrence/search", "2026-11-24", "per record (CC0, CC-BY-4.0, CC-BY-NC-4.0)", "n/a",
     "Harvested 2026-11-24 by scripts/harvest_gbif_occurrences.py; a DOI-citable GBIF download should replace it at release."),
    ("SRC-004", "CITES Appendices I, II and III. CITES Secretariat. https://cites.org/eng/app/appendices.php", "regulatory",
     "https://cites.org/eng/app/appendices.php", "2026-11-24", "public", "n/a", "As recorded in workbook sheet 6_Trade_CITES."),
    ("SRC-005", "IUCN Red List of Threatened Species. https://www.iucnredlist.org", "database",
     "https://www.iucnredlist.org", "2026-11-24", "(c) IUCN; cited, not redistributed", "n/a",
     "Categories as recorded in the workbook trade sheet and as served by GBIF (iucnRedListCategory); not queried against the IUCN API."),
    ("SRC-006", "World Flora Online taxonomic backbone, matched with R package WorldFlora 1.14-5 (Kindt 2020, "
     "https://doi.org/10.1002/aps3.11388)", "database", "https://www.worldfloraonline.org", "2026-11-24", "CC-BY-3.0", "n/a",
     "Static backbone classification.csv (1,657,866 rows); see docs/wfo_gbif_reconciliation.md."),
    ("SRC-007", "Plants of the World Online (POWO), Royal Botanic Gardens Kew. https://powo.science.kew.org", "database",
     "https://powo.science.kew.org", "2026-11-24", "CC-BY-3.0", "n/a",
     "Access pending: the API is not reachable programmatically from the build environment."),
    ("SRC-008", "Lancang-Mekong Traditional Medicine Resources Database. https://lmsjk.ynutcm.edu.cn", "database",
     "https://lmsjk.ynutcm.edu.cn", "", "unknown", "A",
     "Access pending: no public API; no data extracted yet. Intended Grade-A source for local names and uses."),
    ("SRC-009", "Nguyen Van Duong. Medicinal Plants of Vietnam, Cambodia, and Laos. Hanoi: Agriculture Publishing House, 1993.",
     "book", "", "", "copyright (print)", "B", "Access pending: not consulted."),
    ("SRC-010", "Nguyen Minh Khoi. Atlas of Medicinal Plants in Vietnam / Atlas cay thuoc Viet Nam. 2022.", "book",
     "", "", "copyright (print)", "B", "Access pending: not consulted."),
    ("SRC-011", "Thorel C. Agriculture and Ethnobotany of the Mekong Basin. Mekong Exploration Commission Report Vol. 4 (1866-1868).",
     "historical_report", "", "", "public domain", "B", "Access pending: not consulted."),
    ("SRC-012", "Wiart C. Medicinal Plants from the East. CRC Press.", "book", "", "", "copyright (print)", "B",
     "Access pending: not consulted."),
    ("SRC-013", "Greater Mekong Subregion Atlas of the Environment. Asian Development Bank / UNEP.", "report",
     "https://www.adb.org", "", "public", "B", "Not consulted in this build."),
    ("SRC-014", "Primary literature cited per row in the workbook (ethnobotanical surveys, phytochemical and pharmacological studies).",
     "peer_reviewed", "various", "2026-11-24", "varies", "A",
     "Each citation is graded individually by scripts/grade_evidence.py; DOIs resolved through Crossref where possible."),
    ("SRC-015", "Crossref REST API, https://api.crossref.org", "database", "https://api.crossref.org", "2026-11-24",
     "public metadata", "n/a", "Used to resolve bibliographic citations to DOIs and publication types."),
    ("SRC-016", "Natural Earth 1:10m rivers and lake centerlines (feature Mekong / Lancang), v5.1.2", "gis",
     "https://www.naturalearthdata.com", "2026-11-24", "public domain", "n/a",
     "Committed river centreline fallback, data/geo/mekong_river_naturalearth.geojson."),
    ("SRC-017", "Tiwari A. et al. A synthesis of hydroclimatic, ecological, and socioeconomic data for transdisciplinary "
     "research in the Mekong. Zenodo. doi:10.5281/zenodo.7622998", "gis", "https://doi.org/10.5281/zenodo.7622998",
     "2026-11-24", "CC-BY-4.0", "n/a",
     "Mekong basin boundary (Shapefile_Mekong_Boundary.shp, EPSG:4326), from Dang et al. 2022 Sci Total Environ 831:154833."),
    ("SRC-018", "WWF-Laos. Mekong River centreline, ArcGIS Online feature service (item dcfa38b28bc247dca5ee94828eed1df6).",
     "gis", "https://services1.arcgis.com/RTK5Unh1Z71JKIiR/ArcGIS/rest/services/Mekong_River_", "2026-11-24",
     "not stated", "n/a",
     "Rendered from the publisher's service at run time; not redistributed because no licence is stated."),
    ("SRC-019", "iNaturalist taxon API, https://api.inaturalist.org/v1/taxa (CC-licensed default photos)", "database",
     "https://api.inaturalist.org", "2026-11-24", "per photo (CC0, CC-BY, CC-BY-SA, CC-BY-NC, CC-BY-NC-SA)", "n/a",
     "Photos shown with per-image attribution; licence and photographer recorded per taxon."),
]


def main() -> int:
    sh = load_sheets()
    spine = build_spine(sh)
    counts_path = L.RAW / "gbif_occurrence_counts.json"
    counts = L.read_json(counts_path) if counts_path.exists() else {}
    species = build_species_master(spine, counts)
    uses, pharm, cons = build_uses(sh, spine), build_pharmacology(sh, spine), build_conservation(sh, spine)
    L.write_csv(L.PROCESSED / "species_master.csv", species)
    L.write_csv(L.PROCESSED / "uses.csv", uses)
    L.write_csv(L.PROCESSED / "pharmacology.csv", pharm)
    L.write_csv(L.PROCESSED / "conservation_trade.csv", cons)
    refs = [{"source_id": a, "full_citation": b, "source_type": c, "url_or_doi": d, "access_date": e,
             "license": f, "reliability_tier": g, "notes": h} for a, b, c, d, e, f, g, h in SOURCES]
    L.write_csv(L.PROCESSED / "references.csv", refs)
    L.write_csv(L.ROOT / "sources" / "source_register.csv", refs)
    print(f"species_master {len(species)} | uses {len(uses)} | pharmacology {len(pharm)} "
          f"({sum(r['record_type'] == 'extract_assay' for r in pharm)} extract, "
          f"{sum(r['record_type'] == 'isolated_compound' for r in pharm)} compound) | conservation {len(cons)} "
          f"({sum(r['in_spine'] == 'yes' for r in cons)} in spine) | references {len(refs)}")
    print("ailment:", dict(Counter(r["ailment_category"] for r in uses).most_common()))
    for r in cons:
        print(f"  {r['species_id']:28} iucn={r['iucn_category_code'] or '-':5} reported={r['threat_category_reported'] or '-':5} "
              f"basis={r['assessment_basis']:30} cites={r['cites_appendix']}")
    print("taxon_rank:", dict(Counter(r["taxon_rank"] for r in species)), "| gbif_vs_wfo:", dict(Counter(r["gbif_vs_wfo"] for r in species)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
