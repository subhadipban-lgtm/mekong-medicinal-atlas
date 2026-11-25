#!/usr/bin/env python3
"""Turn the raw GBIF harvest into graded, generalised, Darwin Core occurrence data.

For every harvested record this script decides:
  evidence grade        C = open licence + recognised basis of record + verifiable metadata
                        D = anything else (kept out of the published dataset)
  sensitivity           a species is sensitive if it carries an IUCN category of CR, EN or VU (in the
                        workbook trade sheet or in GBIF's category for its records) or is listed in
                        CITES Appendix I or II. Its coordinates are generalised:
                          CR            -> rounded to 0.1 decimal degrees, locality text removed
                          EN, VU, CITES -> rounded to 0.01 decimal degrees, locality text removed
                        Sensitivity is decided per species in a first pass, so every record of a
                        sensitive species is treated the same way.
  basin position        inside / outside the Mekong basin boundary (point in polygon)
  coordinate quality    high / medium / low, from coordinate uncertainty and precision

Outputs
  data/processed/occurrences.csv              all harvested records, DwC terms + atlas flags
  data/processed/occurrence_summary_by_species.csv
  data/processed/occurrence_build_summary.json
  data/dwc/occurrence.txt                     published records (grade C), Darwin Core terms only
  data/dwc/meta.xml, eml.xml, dwca.zip        Darwin Core Archive and GBIF-style metadata
  species_master.csv                          occurrence counts, GBIF IUCN category, sensitivity flag

Usage: python scripts/build_dwc.py
"""
from __future__ import annotations

import gzip
import json
import math
import re
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import shapely
from shapely.geometry import shape

sys.path.insert(0, str(Path(__file__).resolve().parent))
import atlas_lib as L  # noqa: E402

HARVEST = L.RAW / "gbif_occurrences"
DWC_TERMS = [
    "occurrenceID", "basisOfRecord", "eventDate", "year", "month", "day", "scientificName",
    "acceptedNameUsage", "taxonRank", "kingdom", "family", "genus", "decimalLatitude", "decimalLongitude",
    "coordinateUncertaintyInMeters", "geodeticDatum", "country", "countryCode", "stateProvince", "county",
    "locality", "recordedBy", "identifiedBy", "occurrenceStatus", "establishmentMeans", "associatedReferences",
    "license", "rightsHolder", "institutionCode", "collectionCode", "catalogNumber", "datasetName",
    "dataGeneralizations", "informationWithheld",
]
ATLAS_FLAGS = ["species_id", "evidence_grade", "coordinate_quality_flag", "basin_flag", "generalized",
               "sensitivity_reason", "gbif_key", "dataset_key", "iucn_red_list_category_gbif", "source_id"]
RECOGNISED_BASIS = {"PRESERVED_SPECIMEN", "MATERIAL_SAMPLE", "LIVING_SPECIMEN", "FOSSIL_SPECIMEN",
                    "HUMAN_OBSERVATION", "MACHINE_OBSERVATION", "OBSERVATION", "OCCURRENCE"}
OPEN_LICENCE = re.compile(r"creativecommons\.org/(?:licenses/|publicdomain/)", re.I)
IUCN_SEVERITY = ["CR", "EN", "VU", "NT", "LC", "DD"]
GENERALISE_DEG = {"CR": 0.1, "EN": 0.01, "VU": 0.01}
UNCERTAINTY_FOR = {0.1: 11000, 0.01: 1100}  # metres: about the half-width of the rounding cell
DATASET_LICENSE = "https://creativecommons.org/licenses/by-nc/4.0/legalcode"
REPO_URL = "https://github.com/subhadipban-lgtm/mekong-medicinal-plant-atlas"


def s(v) -> str:
    return "" if v is None else str(v).strip()


def decimals_of(value: str) -> int:
    return len(value.split(".")[1]) if "." in value else 0


def record_grade(rec: dict) -> str:
    """Occurrence records are specimens or observations, which the rubric places at grade C."""
    verifiable = bool(s(rec.get("occurrenceID"))) or bool(s(rec.get("institutionCode")) and s(rec.get("catalogNumber")))
    if (OPEN_LICENCE.search(s(rec.get("license"))) and s(rec.get("basisOfRecord")).upper() in RECOGNISED_BASIS
            and verifiable):
        return "C"
    return "D"


def quality_flag(rec: dict, lat: str, lon: str) -> str:
    try:
        unc = float(rec.get("coordinateUncertaintyInMeters") or "nan")
    except ValueError:
        unc = math.nan
    prec = min(decimals_of(lat), decimals_of(lon))
    if prec <= 1 or (not math.isnan(unc) and unc > 50000):
        return "low"
    if prec == 2 or (not math.isnan(unc) and unc > 5000):
        return "medium"
    return "high"


def load(species_by_key: dict) -> list[tuple[dict, list[dict]]]:
    """(species row, records) for every harvested species-level taxon."""
    out = []
    for path in sorted(HARVEST.glob("*.json.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            payload = json.load(fh)
        sp = species_by_key.get(str(payload["taxonKey"]))
        if sp is not None and sp["taxon_rank"] != "genus" and not sp["same_gbif_taxon_as"]:
            out.append((sp, payload["records"]))
    return out


def decide_sensitivity(species: list[dict], taxa: list[tuple[dict, list[dict]]]) -> tuple[dict, dict]:
    """(species_id -> (reason, rounding step in degrees), species_id -> GBIF IUCN category)."""
    gbif_cat: dict[str, Counter] = defaultdict(Counter)
    for sp, records in taxa:
        for rec in records:
            cat = s(rec.get("iucnRedListCategory")).upper()
            if cat and cat != "NE":
                gbif_cat[sp["species_id"]][cat] += 1
    worst = {sid: next(c for c in IUCN_SEVERITY if cats.get(c)) for sid, cats in gbif_cat.items()}
    out: dict[str, tuple[str, float]] = {}
    for sp in species:
        sid = sp["species_id"]
        reported = set(sp["iucn_category_code"].split("/")) | set(sp["threat_category_reported"].split("/"))
        cited = sp["cites_appendix"] in ("I", "II")
        cats = [c for c in ("CR", "EN", "VU") if c in reported or c == worst.get(sid)]
        if "CR" in cats:
            out[sid] = ("IUCN Critically Endangered", GENERALISE_DEG["CR"])
        elif cats or cited:
            parts = [f"IUCN {cats[0]}"] if cats else []
            parts += [f"CITES Appendix {sp['cites_appendix']}"] if cited else []
            out[sid] = ("; ".join(parts), GENERALISE_DEG["EN"])
    return out, worst


def main() -> int:
    species = L.read_csv(L.PROCESSED / "species_master.csv")
    by_key = {r["gbif_taxon_key"]: r for r in species if r["gbif_taxon_key"]}
    taxa = load(by_key)
    skipped = sorted({r["species_id"] for r in species if r["taxon_rank"] == "genus"})
    sensitivity, worst = decide_sensitivity(species, taxa)
    basin = shape(json.loads((L.GEO / "mekong_basin.geojson").read_text(encoding="utf-8"))["features"][0]["geometry"])

    rows: list[dict] = []
    stats = Counter()
    for sp, records in taxa:
        sid = sp["species_id"]
        reason, step = sensitivity.get(sid, ("", 0.0))
        for rec in records:
            lat0, lon0 = s(rec.get("decimalLatitude")), s(rec.get("decimalLongitude"))
            try:
                lat_f, lon_f = float(lat0), float(lon0)
            except ValueError:
                stats["dropped_no_coordinate"] += 1
                continue
            if not (-90 <= lat_f <= 90 and -180 <= lon_f <= 180) or (lat_f == 0 and lon_f == 0):
                stats["dropped_invalid_coordinate"] += 1
                continue
            try:
                unc = float(rec.get("coordinateUncertaintyInMeters"))
            except (TypeError, ValueError):
                unc = 0.0
            if step:
                lat = f"{round(lat_f / step) * step:.4f}".rstrip("0").rstrip(".")
                lon = f"{round(lon_f / step) * step:.4f}".rstrip("0").rstrip(".")
                local = ""
                gen = f"coordinates rounded to {step} decimal degrees; locality removed"
                withheld = "exact locality and coordinates withheld for a threatened species"
                unc = max(unc, UNCERTAINTY_FOR[step])
            else:
                lat, lon = f"{lat_f:.5f}", f"{lon_f:.5f}"
                local, gen, withheld = s(rec.get("locality")), "", ""
            grade = record_grade(rec)
            dkey = s(rec.get("datasetKey"))
            rows.append({
                "occurrenceID": s(rec.get("occurrenceID")) or f"https://www.gbif.org/occurrence/{rec.get('key')}",
                "basisOfRecord": s(rec.get("basisOfRecord")),
                "eventDate": s(rec.get("eventDate")),
                "year": s(rec.get("year")), "month": s(rec.get("month")), "day": s(rec.get("day")),
                "scientificName": s(rec.get("scientificName")),
                "acceptedNameUsage": s(rec.get("acceptedScientificName")),
                "taxonRank": s(rec.get("taxonRank")).lower(),
                "kingdom": s(rec.get("kingdom")), "family": s(rec.get("family")), "genus": s(rec.get("genus")),
                "decimalLatitude": lat, "decimalLongitude": lon,
                "coordinateUncertaintyInMeters": "" if not unc else f"{unc:g}",
                "geodeticDatum": s(rec.get("geodeticDatum")) or "WGS84",
                "country": s(rec.get("country")), "countryCode": s(rec.get("countryCode")),
                "stateProvince": s(rec.get("stateProvince")), "county": s(rec.get("county")),
                "locality": local,
                "recordedBy": s(rec.get("recordedBy")), "identifiedBy": s(rec.get("identifiedBy")),
                "occurrenceStatus": {"DETECTED": "present", "PRESENT": "present", "ABSENT": "absent"}.get(
                    s(rec.get("occurrenceStatus")).upper(), s(rec.get("occurrenceStatus")).lower()),
                "establishmentMeans": s(rec.get("establishmentMeans")).lower(),
                "associatedReferences": f"https://www.gbif.org/dataset/{dkey}" if dkey else "",
                "license": s(rec.get("license")),
                "rightsHolder": s(rec.get("rightsHolder")) or s(rec.get("institutionCode")),
                "institutionCode": s(rec.get("institutionCode")), "collectionCode": s(rec.get("collectionCode")),
                "catalogNumber": s(rec.get("catalogNumber")), "datasetName": s(rec.get("datasetName")),
                "dataGeneralizations": gen, "informationWithheld": withheld,
                "species_id": sid, "evidence_grade": grade,
                "coordinate_quality_flag": quality_flag(rec, lat0, lon0),
                "basin_flag": "", "generalized": "yes" if step else "no",
                "sensitivity_reason": reason, "gbif_key": s(rec.get("key")), "dataset_key": dkey,
                "iucn_red_list_category_gbif": worst.get(sid, ""), "source_id": "SRC-003",
            })
            stats["harvested"] += 1
            stats["grade_" + grade] += 1
            stats["generalised" if step else "exact"] += 1

    # The basin test uses the generalised coordinate, the only one that is published.
    inside = shapely.contains_xy(basin, [float(r["decimalLongitude"]) for r in rows],
                                 [float(r["decimalLatitude"]) for r in rows])
    seen: set[str] = set()
    for r, ins in zip(rows, inside):
        r["basin_flag"] = "in_basin" if ins else "outside_basin"
        if r["occurrenceID"] in seen:  # a publisher reused an identifier; the GBIF URL is always unique
            r["occurrenceID"] = f"https://www.gbif.org/occurrence/{r['gbif_key']}"
        seen.add(r["occurrenceID"])
        if r["evidence_grade"] != "D":
            stats["published_in_basin" if ins else "published_outside_basin"] += 1

    L.write_csv(L.PROCESSED / "occurrences.csv", rows, DWC_TERMS + ATLAS_FLAGS)
    published = [r for r in rows if r["evidence_grade"] != "D"]
    # The full table includes grade-D records that were excluded from publication because they may
    # lack an open licence; this published-only table is the redistributable CSV. It is large and
    # stays out of git (see .gitignore); the Darwin Core archive tracks the same records.
    L.write_csv(L.PROCESSED / "occurrences_published.csv", published, DWC_TERMS + ATLAS_FLAGS)
    L.DWC.mkdir(parents=True, exist_ok=True)
    # The Darwin Core Archive convention is tab-separated, matching meta.xml. Tabs and line breaks
    # inside a value would break the file, so they are collapsed to spaces.
    with (L.DWC / "occurrence.txt").open("w", encoding="utf-8", newline="") as fh:
        fh.write("\t".join(DWC_TERMS) + "\n")
        for r in published:
            fh.write("\t".join(re.sub(r"[\t\r\n]+", " ", str(r.get(t, ""))) for t in DWC_TERMS) + "\n")
    write_archive(published)

    agg: dict[str, Counter] = defaultdict(Counter)
    for r in published:
        a = agg[r["species_id"]]
        a["n"] += 1
        a["in_basin" if r["basin_flag"] == "in_basin" else "outside_basin"] += 1
        a["n_" + r["countryCode"]] += 1
        a["generalised"] += r["generalized"] == "yes"
        a["specimen"] += r["basisOfRecord"] in ("PRESERVED_SPECIMEN", "MATERIAL_SAMPLE", "LIVING_SPECIMEN")
    for sp in species:
        sid, a, cat = sp["species_id"], agg.get(sp["species_id"], Counter()), worst.get(sp["species_id"], "")
        if not sp["iucn_category_code"] and cat:
            sp["iucn_category_code"], sp["assessment_basis"] = cat, "GBIF iucnRedListCategory"
        sp["iucn_category_code_gbif"] = cat
        sp["n_occurrence_records"] = a["n"]
        sp["n_occurrence_in_basin"] = a["in_basin"]
        sp["n_occurrence_outside_basin"] = a["outside_basin"]
        sp["n_occurrence_specimen"] = a["specimen"]
        sp["n_occurrence_generalised"] = a["generalised"]
        sp["occurrence_by_country"] = ";".join(f"{c}:{a['n_' + c]}" for c in L.BASIN_COUNTRIES if a["n_" + c])
        sp["occurrence_countries"] = ",".join(c for c in L.BASIN_COUNTRIES if a["n_" + c])
        sp["sensitive_species"] = "yes" if sid in sensitivity and a["n"] else "no"
        sp["sensitivity_reason"] = sensitivity.get(sid, ("", 0))[0]
    L.write_csv(L.PROCESSED / "species_master.csv", species)
    L.write_csv(L.PROCESSED / "occurrence_summary_by_species.csv", [{
        "species_id": sp["species_id"], "accepted_name": sp["accepted_name"],
        "n_occurrence_records": sp["n_occurrence_records"], "n_occurrence_in_basin": sp["n_occurrence_in_basin"],
        "n_occurrence_outside_basin": sp["n_occurrence_outside_basin"],
        "n_occurrence_specimen": sp["n_occurrence_specimen"],
        "n_occurrence_generalised": sp["n_occurrence_generalised"],
        "occurrence_by_country": sp["occurrence_by_country"]} for sp in species])

    by_country = {c: {"in_basin": sum(1 for r in published if r["countryCode"] == c and r["basin_flag"] == "in_basin"),
                      "outside_basin": sum(1 for r in published if r["countryCode"] == c and r["basin_flag"] != "in_basin")}
                  for c in L.BASIN_COUNTRIES}
    out = {"stats": dict(stats), "harvested": len(rows), "published": len(published),
                         "published_by_country": by_country,
                         "basis_of_published": dict(Counter(r["basisOfRecord"] for r in published)),
                         "licence_of_published": dict(Counter((r["license"] or "unspecified") for r in published)),
                         "gbif_datasets": len({r["dataset_key"] for r in published}),
                         "harvested_at": max((v.get("harvestedAt", "") for v in L.read_json(HARVEST / "_harvest_summary.json").values()), default="")[:10],
                         "excluded_grade_d": len(rows) - len(published),
                         "species_with_published_records": len(agg),
                         "sensitive_species": {k: v[0] for k, v in sorted(sensitivity.items())},
                         "sensitive_species_with_published_records": sorted(s for s in sensitivity if agg.get(s)),
                         "generalisation_rule": {"CR": "0.1 decimal degrees", "EN/VU/CITES I-II": "0.01 decimal degrees"},
                         "genus_level_taxa_without_occurrence_data": skipped}
    L.write_json(L.PROCESSED / "occurrence_build_summary.json", out)
    print(json.dumps(out["stats"]), "| published", out["published"])
    print("species with records:", out["species_with_published_records"], "| sensitive with records:",
          len(out["sensitive_species_with_published_records"]), "| genus-level skipped:", skipped)
    return 0


def esc(x: str) -> str:
    return x.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def write_archive(published: list[dict]) -> None:
    fields = "\n".join(f'        <field index="{i}" term="http://rs.tdwg.org/dwc/terms/{t}"/>'
                       for i, t in enumerate(DWC_TERMS, start=1))
    (L.DWC / "meta.xml").write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<archive xmlns="http://rs.tdwg.org/dwc/text/"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://rs.tdwg.org/dwc/text/ http://rs.tdwg.org/dwc/text/tdwg_dwc_text.xsd">
  <core encoding="UTF-8" linesTerminatedBy="\\n" fieldsTerminatedBy="\\t" fieldsEnclosedBy=""
           ignoreHeaderLines="1" rowType="http://rs.tdwg.org/dwc/terms/Occurrence">
    <files><location>occurrence.txt</location></files>
    <id index="0"/>
{fields}
  </core>
</archive>
''', encoding="utf-8")

    names = sorted({r["scientificName"] for r in published})
    families = sorted({r["family"] for r in published if r["family"]})
    lats = [float(r["decimalLatitude"]) for r in published]
    lons = [float(r["decimalLongitude"]) for r in published]
    years = sorted({r["year"] for r in published if r["year"]})
    n_gen = sum(1 for r in published if r["generalized"] == "yes")
    n_basin = sum(1 for r in published if r["basin_flag"] == "in_basin")
    n_datasets = len({r["dataset_key"] for r in published})
    title = ("Mekong Medicinal Plant Atlas: occurrence records of medicinal plant taxa in the "
             "Mekong River basin")
    abstract = (
        f"A derived occurrence dataset of {len(names)} medicinal plant names reported from the Mekong River basin "
        f"and the six basin countries (Cambodia, China, Laos, Myanmar, Thailand, Vietnam). It holds {len(published)} "
        f"georeferenced records harvested from the GBIF occurrence API on 2026-11-24 and filtered to records with an "
        f"open licence, a recognised basis of record and verifiable metadata. {n_basin} records fall inside the "
        f"Mekong basin boundary; the remainder are country-level records from the six basin countries. Coordinates of "
        f"species assessed as threatened or listed in CITES are generalised ({n_gen} records). The records originate "
        f"from {n_datasets} GBIF datasets and remain available from their publishers; this dataset is a filtered and "
        f"generalised derivative assembled for the Mekong Medicinal Plant Atlas. Records were not re-identified and "
        f"names are those supplied by GBIF.")
    temporal = ""
    if years:
        temporal = (f"    <temporalCoverage>\n      <rangeOfDates>\n"
                    f"        <beginDate><calendarDate>{years[0]}-01-01</calendarDate></beginDate>\n"
                    f"        <endDate><calendarDate>{years[-1]}-12-31</calendarDate></endDate>\n"
                    f"      </rangeOfDates>\n    </temporalCoverage>")
    family_xml = "\n".join(
        f"        <taxonomicClassification>\n          <taxonRankName>family</taxonRankName>\n"
        f"          <taxonRankValue>{esc(f)}</taxonRankValue>\n        </taxonomicClassification>" for f in families)
    eml = f'''<?xml version="1.0" encoding="UTF-8"?>
<eml:eml xmlns:eml="eml://ecoinformatics.org/eml-2.1.1"
         xmlns:dc="http://purl.org/dc/terms/"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="eml://ecoinformatics.org/eml-2.1.1 http://rs.gbif.org/schema/eml-gbif-profile/1.1/eml.xsd"
         packageId="{REPO_URL}/dwc" system="https://github.com" scope="system">
  <dataset>
    <alternateIdentifier>{REPO_URL}</alternateIdentifier>
    <title xml:lang="en">{esc(title)}</title>
    <creator>
      <organizationName>Mekong Medicinal Plant Atlas project</organizationName>
      <electronicMailAddress>see the atlas contact page</electronicMailAddress>
    </creator>
    <metadataProvider>
      <organizationName>Mekong Medicinal Plant Atlas project</organizationName>
      <onlineUrl>{REPO_URL}</onlineUrl>
    </metadataProvider>
    <pubDate>{datetime.now(timezone.utc).date().isoformat()}</pubDate>
    <language>en</language>
    <abstract>
      <para>{esc(abstract)}</para>
    </abstract>
    <keywordSet>
      <keyword>Mekong</keyword><keyword>medicinal plants</keyword><keyword>occurrence</keyword>
      <keyword>ethnobotany</keyword><keyword>Darwin Core</keyword>
    </keywordSet>
    <intellectualRights>
      <para>This dataset is made available under a Creative Commons Attribution-NonCommercial 4.0 International License (CC-BY-NC-4.0) because it includes records published under that licence. It also includes records published under CC0 and CC-BY 4.0; the licence of each record is given in its license field and prevails for that record.</para>
      <citation>{DATASET_LICENSE}</citation>
    </intellectualRights>
    <coverage>
      <geographicCoverage>
        <geographicDescription>Mekong River basin and the six basin countries: Cambodia, China, Laos, Myanmar, Thailand, Vietnam</geographicDescription>
        <boundingCoordinates>
          <westBoundingCoordinate>{min(lons)}</westBoundingCoordinate>
          <eastBoundingCoordinate>{max(lons)}</eastBoundingCoordinate>
          <northBoundingCoordinate>{max(lats)}</northBoundingCoordinate>
          <southBoundingCoordinate>{min(lats)}</southBoundingCoordinate>
        </boundingCoordinates>
      </geographicCoverage>
{temporal}
      <taxonomicCoverage>
        <generalTaxonomicCoverage>{len(names)} scientific names of vascular plants (and one alga) used as medicinal plants in the Mekong basin, in {len(families)} families; the full list is in the archive.</generalTaxographicCoverage>
        <taxonomicClassification>
          <taxonRankName>kingdom</taxonRankName>
          <taxonRankValue>Plantae</taxonRankValue>
{family_xml}
        </taxonomicClassification>
      </taxonomicCoverage>
    </coverage>
    <purpose>To document the recorded occurrence of medicinal plant taxa of the Mekong basin for the Mekong Medicinal Plant Atlas.</purpose>
    <methods>
      <methodStep><description>Records were retrieved from the GBIF occurrence search API (hasCoordinate=true, hasGeospatialIssue=false) for each species-level atlas taxon in the six basin countries on 2026-11-24 with scripts/harvest_gbif_occurrences.py.</description></methodStep>
      <methodStep><description>Records were kept only if they carry an open licence, a recognised basisOfRecord and either an occurrenceID or an institution code together with a catalogue number.</description></methodStep>
      <methodStep><description>Coordinates of species assessed as Critically Endangered were rounded to 0.1 decimal degrees; those of species assessed Endangered or Vulnerable, or listed in CITES Appendix I or II, were rounded to 0.01 decimal degrees. Locality text was removed from these records.</description></methodStep>
      <methodStep><description>Each record was tested against the Mekong basin boundary (Zenodo, doi:10.5281/zenodo.7622998). The archive holds records from the whole of the six basin countries.</description></methodStep>
      <qualityControl><description>No records were re-identified or georeferenced. Automated checks: duplicate occurrence identifiers replaced by GBIF URLs; zero and out-of-range coordinates removed; GBIF records flagged with geospatial issues excluded at query time.</description></qualityControl>
    </methods>
    <contact>
      <organizationName>Mekong Medicinal Plant Atlas project</organizationName>
      <onlineUrl>{REPO_URL}</onlineUrl>
    </contact>
  </dataset>
</eml:eml>
'''.replace("generalTaxographicCoverage", "generalTaxonomicCoverage")
    harvested_at = "2026-11-24"
    summary_path = HARVEST / "_harvest_summary.json"
    if summary_path.exists():
        harvested_at = max(v.get("harvestedAt", "") for v in json.loads(summary_path.read_text()).values())[:10]
    eml = eml.replace(f"<pubDate>{datetime.now(timezone.utc).date().isoformat()}</pubDate>", f"<pubDate>{harvested_at}</pubDate>")
    (L.DWC / "eml.xml").write_text(eml, encoding="utf-8")
    with zipfile.ZipFile(L.DWC / "dwca.zip", "w", zipfile.ZIP_DEFLATED) as zf:
        for name in ("meta.xml", "eml.xml", "occurrence.txt"):
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 24, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, (L.DWC / name).read_bytes())


if __name__ == "__main__":
    sys.exit(main())
