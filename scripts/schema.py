#!/usr/bin/env python3
"""The atlas schema, written once and used for two things:

  1. docs/data_dictionary.md is rendered from it, so every field in every table has a definition,
     a unit where one applies, and an allowed-value list or range;
  2. scripts/qa_checks.py validates the real data against it (QA gate 7).

A field is (name, type, unit, allowed, definition).
  type     string | text | int | float | bool | json-list | json-object | date
  allowed  a list of permitted values ("" permits empty)  |  "a..b" numeric range  |  "re:pattern"
           | "empty" (reserved, must be blank) | "fk:table.field" | "fk-list:table.field" | "*" any text
"""
from __future__ import annotations

COUNTRY = ["CN", "TH", "VN", "LA", "KH", "MM"]
GRADES = ["A", "B", "C", "D"]
CITES = ["I", "II", "III", "not listed", "unknown"]
IUCN_CODES = ["CR", "EN", "VU", "NT", "LC", "DD", "CR/EN"]
ASSESSMENT = ["IUCN", "unstated (workbook statement)", "national red list", "specialist literature",
              "unconfirmed", "not stated", "not assessed", "GBIF iucnRedListCategory"]
MATCH_TYPES = ["EXACT", "FUZZY", "HIGHERRANK", "MANUAL", ""]
COUNTRY_LIST = "re:((" + "|".join(COUNTRY) + r")(,(" + "|".join(COUNTRY) + r"))*)?"
COUNT_LIST = "re:((" + "|".join(COUNTRY) + r"):\d+(;(" + "|".join(COUNTRY) + r"):\d+)*)?"

SPECIES_MASTER = [
    ("species_id", "string", "n/a", "re:sp_[a-z0-9_]+", "Stable identifier: sp_ plus the normalised workbook name."),
    ("accepted_name", "string", "n/a", "*", "Scientific name accepted in the GBIF backbone (genus and species, without authors)."),
    ("scientific_name_authorship", "string", "n/a", "*", "Author string of the accepted name, as given by GBIF."),
    ("family", "string", "n/a", "*", "Family in the GBIF backbone."),
    ("genus", "string", "n/a", "*", "Genus of the accepted name."),
    ("taxon_rank", "string", "n/a", ["species", "genus"], "Resolution of the workbook entry. Four entries name only a genus."),
    ("synonyms", "json-list", "n/a", "*", "Synonyms of the taxon in the GBIF backbone."),
    ("common_names_json", "json-list", "n/a", "*", "Reserved for English common names; empty because none are verified yet."),
    ("local_names_json", "json-object", "n/a", "*", "Reserved for local names in Khmer, Lao, Thai, Vietnamese, Burmese and Chinese; empty pending the Tier-2 reference books."),
    ("countries_present", "string", "n/a", COUNTRY_LIST, "Basin countries in which the workbook reports the species (ISO 3166-1 alpha-2)."),
    ("mekong_basin_presence", "string", "n/a", "*", "How basin presence is known: workbook country list, GBIF country-level records, or unknown."),
    ("life_form", "string", "n/a", ["Tree", "Shrub", "Herb", "Climber", "Herb (epiphyte)", "Alga", "unknown"], "Life form as recorded in the workbook."),
    ("parts_used", "string", "n/a", "*", "Plant parts used, as recorded in the workbook."),
    ("habitat", "string", "n/a", "empty", "Reserved; no habitat data verified."),
    ("wild_cultivated_status", "string", "n/a", ["wild", "cultivated", "both", "unknown"], "Whether the species is wild, cultivated or both."),
    ("iucn_status_verbatim", "text", "n/a", "*", "Threat status as written in the workbook trade sheet."),
    ("iucn_category_code", "string", "n/a", IUCN_CODES + [""], "IUCN Red List category, from the workbook where it names IUCN, otherwise from GBIF."),
    ("threat_category_reported", "string", "n/a", IUCN_CODES + [""], "Category words found in the threat statement, whatever their basis."),
    ("assessment_basis", "string", "n/a", ASSESSMENT, "Who assessed the category: IUCN, a national red list, specialist literature, or unconfirmed."),
    ("national_status", "text", "n/a", "*", "National red-list statement, when the workbook gives one."),
    ("cites_status_verbatim", "text", "n/a", "*", "CITES and national regulatory status as written in the workbook."),
    ("cites_appendix", "string", "n/a", CITES, "CITES appendix in which the species is listed."),
    ("trade_status", "text", "n/a", "*", "Trade pressure as described in the workbook."),
    ("source_ids", "string", "n/a", "fk-list:references.source_id", "Identifiers of the sources contributing to the row."),
    ("evidence_grade", "string", "n/a", GRADES, "Best evidence grade among the species' use and pharmacology records."),
    ("gbif_taxon_key", "string", "n/a", "re:\\d*", "GBIF backbone usage key."),
    ("gbif_match_type", "string", "n/a", MATCH_TYPES, "How the workbook name was matched to GBIF; MANUAL marks the nine names resolved by hand."),
    ("gbif_confidence", "string", "n/a", "re:\\d*", "Confidence of the GBIF name match (0-100)."),
    ("gbif_count_api_by_country", "string", "n/a", COUNT_LIST, "All GBIF records per basin country from occurrence/count, including records without coordinates."),
    ("gbif_count_api_total", "int", "records", "0..", "Sum of gbif_count_api_by_country."),
    ("in_tier1", "bool", "n/a", "*", "Species appears in the workbook's ethnobotanical inventory."),
    ("in_tier2", "bool", "n/a", "*", "Species has extract assay rows in the workbook."),
    ("in_tier3", "bool", "n/a", "*", "Species has isolated-compound rows in the workbook."),
    ("wfo_accepted_name", "string", "n/a", "*", "Name accepted in the World Flora Online backbone."),
    ("wfo_family", "string", "n/a", "*", "Family in the World Flora Online backbone."),
    ("wfo_status", "string", "n/a", "*", "Taxonomic status in World Flora Online (Accepted, Unchecked)."),
    ("gbif_vs_wfo", "string", "n/a", ["agree", "differ", "no_wfo_match"], "Whether GBIF and World Flora Online agree on genus and species."),
    ("same_gbif_taxon_as", "string", "n/a", "re:(sp_[a-z0-9_]+)?", "Set when two workbook names are one accepted species; points to the entry that keeps the occurrence records."),
    ("notes", "text", "n/a", "*", "Free notes."),
    ("iucn_category_code_gbif", "string", "n/a", IUCN_CODES[:6] + [""], "Most severe IUCN category that GBIF attaches to the species' records."),
    ("n_occurrence_records", "int", "records", "0..", "Published occurrence records of the species in the six basin countries."),
    ("n_occurrence_in_basin", "int", "records", "0..", "Published records that fall inside the Mekong basin boundary."),
    ("n_occurrence_outside_basin", "int", "records", "0..", "Published records that fall outside the basin boundary."),
    ("n_occurrence_specimen", "int", "records", "0..", "Published records based on preserved, living or material specimens."),
    ("n_occurrence_generalised", "int", "records", "0..", "Published records whose coordinates were generalised."),
    ("occurrence_by_country", "string", "n/a", COUNT_LIST, "Published records per basin country."),
    ("occurrence_countries", "string", "n/a", COUNTRY_LIST, "Basin countries with at least one published record."),
    ("sensitive_species", "string", "n/a", ["yes", "no"], "Species is threatened or CITES-listed and has published records."),
    ("sensitivity_reason", "string", "n/a", "*", "Why the species is treated as sensitive."),
]

USES = [
    ("use_id", "string", "n/a", "re:use_[a-z0-9_-]+_r\\d+_\\d+", "Stable identifier built from the species and the worksheet row."),
    ("species_id", "string", "n/a", "fk:species_master.species_id", "Species the use is reported for."),
    ("country", "string", "n/a", "*", "Basin countries the source reports the use from, or mekong-region."),
    ("ethnic_group", "string", "n/a", "empty", "Reserved; the workbook does not record ethnic groups."),
    ("ailment_category", "string", "n/a", ["gastrointestinal", "respiratory", "dermatological", "musculoskeletal", "metabolic",
                                            "infectious", "reproductive", "neurological", "cardiovascular", "genitourinary", "other"],
     "Use category assigned from the use text by a fixed keyword rule (scripts/build_tables.py)."),
    ("specific_use", "text", "n/a", "*", "Use as recorded in the workbook."),
    ("used_part", "string", "n/a", "*", "Plant part used, as recorded."),
    ("preparation", "string", "n/a", "empty", "Reserved; preparation is not recorded in the workbook."),
    ("administration", "string", "n/a", "empty", "Reserved; route of administration is not recorded."),
    ("source_id", "string", "n/a", "fk-list:references.source_id", "Identifiers of the sources of the record."),
    ("evidence_grade", "string", "n/a", GRADES, "Evidence grade A-D under the atlas rubric."),
    ("source_citation", "text", "n/a", "*", "Citation as printed in the workbook."),
    ("grade_basis", "text", "n/a", "*", "How the grade was decided."),
    ("resolved_doi", "string", "n/a", "*", "DOI of the confirmed article, when one was resolved."),
    ("notes", "text", "n/a", "empty", "Reserved."),
]

PHARMACOLOGY = [
    ("pharma_id", "string", "n/a", "re:pha_(ext|cmp)_[a-z0-9_-]+_r\\d+", "Stable identifier; ext = extract assay, cmp = isolated compound."),
    ("species_id", "string", "n/a", "fk:species_master.species_id", "Species the record concerns."),
    ("record_type", "string", "n/a", ["extract_assay", "isolated_compound"], "Kind of record."),
    ("reported_activity", "text", "n/a", "*", "Activity as reported in the workbook."),
    ("chemical_constituents", "string", "n/a", "*", "Compound and its class for isolated-compound records."),
    ("extract_or_fraction", "string", "n/a", "*", "Extract or fraction tested."),
    ("plant_part", "string", "n/a", "*", "Plant part extracted."),
    ("assay_or_study_type", "text", "n/a", "*", "Assay or model used."),
    ("potency_verbatim", "string", "n/a", "*", "Potency as printed in the workbook; nq where only a qualitative result was reported."),
    ("potency_value", "float", "see potency_unit", "*", "Numeric potency where the workbook gives one."),
    ("potency_unit", "string", "n/a", "*", "Unit of potency_value."),
    ("potency_status", "string", "n/a", ["quantified", "qualitative", "nq", ""], "Whether the source reported a number."),
    ("source_id", "string", "n/a", "fk-list:references.source_id", "Identifiers of the sources of the record."),
    ("evidence_grade", "string", "n/a", GRADES, "Evidence grade A-D under the atlas rubric."),
    ("source_citation", "text", "n/a", "*", "Citation as printed in the workbook."),
    ("grade_basis", "text", "n/a", "*", "How the grade was decided."),
    ("resolved_doi", "string", "n/a", "*", "DOI of the confirmed article, when one was resolved."),
    ("notes", "text", "n/a", "empty", "Reserved."),
]

CONSERVATION = [
    ("conservation_id", "string", "n/a", "re:con_[a-z0-9_-]+", "Stable identifier."),
    ("species_id", "string", "n/a", "re:sp_[a-z0-9_]+", "Species the statement concerns."),
    ("species_verbatim", "text", "n/a", "*", "Name as written in the trade sheet."),
    ("iucn_status", "text", "n/a", "*", "Threat statement as written."),
    ("iucn_category_code", "string", "n/a", IUCN_CODES + [""], "IUCN category where the statement names IUCN."),
    ("threat_category_reported", "string", "n/a", IUCN_CODES + [""], "Category words found in the statement."),
    ("assessment_basis", "string", "n/a", ASSESSMENT, "Who assessed the category."),
    ("cites_appendix", "string", "n/a", CITES, "CITES appendix."),
    ("cites_status_verbatim", "text", "n/a", "*", "CITES and regulatory statement as written."),
    ("national_status", "text", "n/a", "*", "National red-list statement."),
    ("trade_notes", "text", "n/a", "*", "Trade pressure as written."),
    ("source_id", "string", "n/a", "fk-list:references.source_id", "Identifiers of the sources."),
    ("in_spine", "string", "n/a", ["yes", "no"], "Whether the row joins to a species in species_master."),
    ("scope_flag", "text", "n/a", "*", "Why a row that is not a species-level spine entry is kept."),
    ("notes", "text", "n/a", "*", "Source as written in the trade sheet."),
]

REFERENCES = [
    ("source_id", "string", "n/a", "re:SRC-\\d{3}", "Stable source identifier."),
    ("full_citation", "text", "n/a", "*", "Citation of the source."),
    ("source_type", "string", "n/a", "*", "Kind of source (database, book, gis, peer_reviewed, ...)."),
    ("url_or_doi", "string", "n/a", "*", "URL, DOI or local reference of the source."),
    ("access_date", "date", "n/a", "*", "Date the source was last accessed; blank where access is pending."),
    ("license", "string", "n/a", "*", "Licence or terms of the source."),
    ("reliability_tier", "string", "n/a", GRADES + ["n/a"], "Grade the rubric assigns to this type of source; n/a for infrastructure."),
    ("notes", "text", "n/a", "*", "How the source is used and any access restriction."),
]

OCCURRENCE_SUMMARY = [
    ("species_id", "string", "n/a", "fk:species_master.species_id", "Species."),
    ("accepted_name", "string", "n/a", "*", "Accepted name."),
    ("n_occurrence_records", "int", "records", "0..", "Published records in the six basin countries."),
    ("n_occurrence_in_basin", "int", "records", "0..", "Published records inside the basin boundary."),
    ("n_occurrence_outside_basin", "int", "records", "0..", "Published records outside the basin boundary."),
    ("n_occurrence_specimen", "int", "records", "0..", "Specimen-based published records."),
    ("n_occurrence_generalised", "int", "records", "0..", "Published records with generalised coordinates."),
    ("occurrence_by_country", "string", "n/a", COUNT_LIST, "Published records per basin country."),
]

BASIS = ["PRESERVED_SPECIMEN", "MATERIAL_SAMPLE", "LIVING_SPECIMEN", "FOSSIL_SPECIMEN", "HUMAN_OBSERVATION",
         "MACHINE_OBSERVATION", "OBSERVATION", "OCCURRENCE", "MATERIAL_CITATION"]
_ISO = r"-?\d{4}(-\d{2}(-\d{2}(T\d{2}(:\d{2}(:\d{2})?)?(\.\d+)?(Z|[+-]\d{2}:?\d{2})?)?)?)?"
# Blank is allowed: 5,542 records carry no date and the atlas does not invent one.
ISO_DATE = "re:(?:" + _ISO + "(?:/" + _ISO + ")?)?"
OCCURRENCES = [
    ("occurrenceID", "string", "n/a", "*", "Darwin Core. Identifier of the record; the publisher's, or its GBIF URL."),
    ("basisOfRecord", "string", "n/a", BASIS, "Darwin Core. Nature of the record."),
    ("eventDate", "string", "n/a", ISO_DATE, "Darwin Core. Date of the record at the precision the publisher gave; an ISO 8601 interval start/end for records spanning dates."),
    ("year", "int", "year", "1500..2100", "Darwin Core. Year of the record."),
    ("month", "int", "month", "1..12", "Darwin Core. Month of the record."),
    ("day", "int", "day of month", "1..31", "Darwin Core. Day of the record."),
    ("scientificName", "string", "n/a", "*", "Darwin Core. Name under which the record was published."),
    ("acceptedNameUsage", "string", "n/a", "*", "Darwin Core. Accepted name of the taxon in the GBIF backbone."),
    ("taxonRank", "string", "n/a", ["species", "subspecies", "variety", "genus", "form", "unranked", ""], "Darwin Core. Rank of scientificName."),
    ("kingdom", "string", "n/a", "*", "Darwin Core. Kingdom."),
    ("family", "string", "n/a", "*", "Darwin Core. Family."),
    ("genus", "string", "n/a", "*", "Darwin Core. Genus."),
    ("decimalLatitude", "float", "decimal degrees", "-90..90", "Darwin Core. Latitude in WGS 84, generalised for sensitive species."),
    ("decimalLongitude", "float", "decimal degrees", "-180..180", "Darwin Core. Longitude in WGS 84, generalised for sensitive species."),
    ("coordinateUncertaintyInMeters", "float", "metres", "0..", "Darwin Core. Horizontal uncertainty; never smaller than the generalisation cell."),
    ("geodeticDatum", "string", "n/a", ["WGS84", "EPSG:4326"], "Darwin Core. Geodetic datum of the coordinates."),
    ("country", "string", "n/a", "*", "Darwin Core. Country name."),
    ("countryCode", "string", "n/a", COUNTRY, "Darwin Core. ISO 3166-1 alpha-2 country code."),
    ("stateProvince", "string", "n/a", "*", "Darwin Core. First-order administrative division."),
    ("county", "string", "n/a", "*", "Darwin Core. Second-order administrative division."),
    ("locality", "text", "n/a", "*", "Darwin Core. Locality text; removed for sensitive species."),
    ("recordedBy", "string", "n/a", "*", "Darwin Core. Collector or observer."),
    ("identifiedBy", "string", "n/a", "*", "Darwin Core. Person who identified the record."),
    ("occurrenceStatus", "string", "n/a", ["present", "absent", ""], "Darwin Core. Presence or absence."),
    ("establishmentMeans", "string", "n/a", ["native", "introduced", "naturalised", "invasive", "managed", "uncertain", ""], "Darwin Core. Establishment means, where the publisher states one."),
    ("associatedReferences", "string", "n/a", "*", "Darwin Core. GBIF page of the dataset the record comes from."),
    ("license", "string", "n/a", "*", "Darwin Core. Licence of the record as published."),
    ("rightsHolder", "string", "n/a", "*", "Darwin Core. Rights holder."),
    ("institutionCode", "string", "n/a", "*", "Darwin Core. Institution holding the record."),
    ("collectionCode", "string", "n/a", "*", "Darwin Core. Collection code."),
    ("catalogNumber", "string", "n/a", "*", "Darwin Core. Catalogue number."),
    ("datasetName", "string", "n/a", "*", "Darwin Core. Name of the GBIF dataset."),
    ("dataGeneralizations", "text", "n/a", "*", "Darwin Core. Generalisation applied to the record."),
    ("informationWithheld", "text", "n/a", "*", "Darwin Core. Information withheld from the record."),
    # Atlas flags (not Darwin Core; these columns are not part of the archive)
    ("species_id", "string", "n/a", "fk:species_master.species_id", "Atlas. Species the record is assigned to."),
    ("evidence_grade", "string", "n/a", GRADES, "Atlas. C for records with an open licence, a recognised basis and verifiable metadata; D otherwise."),
    ("coordinate_quality_flag", "string", "n/a", ["high", "medium", "low"], "Atlas. Quality from coordinate precision and uncertainty."),
    ("basin_flag", "string", "n/a", ["in_basin", "outside_basin"], "Atlas. Whether the point falls inside the Mekong basin boundary."),
    ("generalized", "string", "n/a", ["yes", "no"], "Atlas. Whether the coordinates were generalised by the atlas."),
    ("sensitivity_reason", "string", "n/a", "*", "Atlas. Why the species is treated as sensitive."),
    ("gbif_key", "string", "n/a", "re:\\d+", "Atlas. GBIF occurrence key."),
    ("dataset_key", "string", "n/a", "re:[0-9a-f-]{36}", "Atlas. GBIF dataset key (UUID)."),
    ("iucn_red_list_category_gbif", "string", "n/a", ["CR", "EN", "VU", "NT", "LC", "DD", ""], "Atlas. IUCN category GBIF gives the species."),
    ("source_id", "string", "n/a", ["SRC-003"], "Atlas. Source register entry for GBIF records."),
]

TABLES = {
    "species_master.csv": SPECIES_MASTER,
    "uses.csv": USES,
    "pharmacology.csv": PHARMACOLOGY,
    "conservation_trade.csv": CONSERVATION,
    "references.csv": REFERENCES,
    "occurrence_summary_by_species.csv": OCCURRENCE_SUMMARY,
    "occurrences.csv": OCCURRENCES,
}

GEO_LAYERS = [
    ("occurrences.geojson", "One point per published record inside the basin boundary.",
     [("id", "species_id of the species"), ("g", "evidence grade of the record"), ("s", "1 specimen-based, 0 observation"),
      ("q", "coordinate_quality_flag"), ("gen", "1 coordinates generalised by the atlas, 0 not"), ("c", "ISO country code"),
      ("k", "GBIF occurrence key of the record"), ("n", "always 1")]),
    ("occurrences_outside_basin.geojson", "One point per species per 0.5-degree cell for records outside the basin boundary.",
     [("id", "species_id"), ("g", "evidence grade"), ("s", "1 where most records behind the point are specimen-based"),
      ("q", "worst coordinate_quality_flag among the records"), ("gen", "1 if any record was generalised"),
      ("c", "ISO country code"), ("k", "GBIF occurrence key of one record"), ("n", "number of records behind the point")]),
    ("species/<slug>.geojson", "Both sets above for a single species.", "same properties as the two layers above"),
    ("mekong_basin.geojson", "Mekong basin boundary, full resolution (CC-BY 4.0).", "id"),
    ("mekong_basin_display.geojson", "Basin boundary simplified for display at 0.001 degrees.", "id"),
    ("mekong_river_naturalearth.geojson", "Mekong River centreline, public-domain fallback.", "name"),
    ("countries_outline.geojson", "Unfilled country outlines for orientation.", "name, iso_a3"),
]


RANGE = __import__("re").compile(r"-?\d*\.?\d*\.\.-?\d*\.?\d*")


def render_dictionary() -> str:
    out = ["# Data dictionary — Mekong Medicinal Plant Atlas", "",
           "Generated by `scripts/build_dictionary.py` from `scripts/schema.py`; do not edit by hand.",
           "`scripts/qa_checks.py` validates every table below against this schema.", "",
           "Conventions: UTF-8; ISO 8601 dates; country codes ISO 3166-1 alpha-2 "
           "(CN China, TH Thailand, VN Vietnam, LA Laos, KH Cambodia, MM Myanmar); "
           "stable identifiers built from species names and worksheet row numbers.", ""]
    for table, fields in TABLES.items():
        out += [f"## {table}", "", "| Field | Type | Unit | Allowed values / range | Definition |", "|---|---|---|---|---|"]
        for name, dtype, unit, allowed, definition in fields:
            allowed = _allowed_text(allowed)
            out.append(f"| `{name}` | {dtype} | {unit if unit != 'n/a' else ''} | {allowed} | {definition} |")
        out.append("")
    out += ["## Geospatial layers and per-species files (`data/geo/`)", "",
            "| File | Content | Feature properties |", "|---|---|---|"]
    for name, content, props in GEO_LAYERS:
        props = props if isinstance(props, str) else "; ".join(f"`{p}` {d}" for p, d in props)
        out.append(f"| `{name}` | {content} | {props} |")
    out += ["", "## Darwin Core Archive (`data/dwc/`)", "",
            "`dwca.zip` contains `meta.xml` (column-to-term mapping), `eml.xml` (dataset metadata) and `occurrence.txt` "
            "(the published records). `occurrence.txt` holds the 34 Darwin Core terms listed for `occurrences.csv` and "
            "nothing else; the atlas flags are not part of the archive.", ""]
    return "\n".join(out)


def _allowed_text(allowed) -> str:
    if isinstance(allowed, (list, tuple)):
        return ", ".join(f"**{a}**" if a else "(blank)" for a in allowed)
    if allowed == "*":
        return "any text"
    if allowed == "empty":
        return "must be blank (reserved)"
    if allowed.startswith("fk-list:"):
        return "semicolon-separated " + allowed[8:] + " values"
    if allowed.startswith("fk:"):
        return "a " + allowed[3:]
    if allowed.startswith("re:"):
        return "regular expression `" + allowed[3:] + "`"
    return f"**{allowed}**"


def check_value(field: tuple, value: str, tables: dict[str, list[dict]]) -> str:
    """Return '' when the value is valid for the field, else a short reason."""
    import json
    import re

    name, dtype, _unit, allowed, _definition = field
    value = "" if value is None else str(value).strip()
    if isinstance(allowed, (list, tuple)):
        if value not in allowed:
            return f"{name}: {value!r} is not one of {list(allowed)[:8]}"
        if not value:
            return ""
    elif allowed == "empty" and value:
        return f"{name}: reserved field is not blank"
    elif allowed == "*" and not value:
        return ""
    if not value and dtype in ("int", "float", "json-list", "json-object", "date", "bool"):
        return ""
    try:
        if dtype == "int":
            if not re.fullmatch(r"-?\d+", value):
                return f"{name}: {value!r} is not an integer"
        elif dtype == "float":
            float(value)
        elif dtype == "bool" and value not in ("True", "False"):
            return f"{name}: {value!r} is not a Boolean"
        elif dtype == "json-list" and not isinstance(json.loads(value), list):
            return f"{name}: not a JSON list"
        elif dtype == "json-object" and not isinstance(json.loads(value), dict):
            return f"{name}: not a JSON object"
        elif dtype == "date" and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return f"{name}: {value!r} is not an ISO date"
    except ValueError:
        return f"{name}: {value!r} is not a {dtype}"
    if isinstance(allowed, str):
        if allowed.startswith("re:") and not re.fullmatch(allowed[3:], value):
            return f"{name}: {value!r} does not match {allowed[3:]}"
        if RANGE.fullmatch(allowed):
            low, high = allowed.split("..")
            number = float(value)
            if low and number < float(low) or high and number > float(high):
                return f"{name}: {value!r} is outside {allowed}"
        if allowed.startswith("fk:"):
            table_name, column = allowed[3:].split(".")
            if value and value not in {r.get(column) for r in tables.get(table_name + ".csv", [])}:
                return f"{name}: {value!r} is not in {allowed[3:]}"
        if allowed.startswith("fk-list:"):
            table_name, column = allowed[8:].split(".")
            known = {r.get(column) for r in tables.get(table_name + ".csv", [])}
            missing = [v for v in re.split(r";\s*", value) if v and v not in known]
            if missing:
                return f"{name}: {missing} are not in {table_name}.{column}"
    return ""


def validate(tables: dict[str, list[dict]]) -> list[str]:
    """Validate every cell of every table; returns a list of violations (empty when all pass)."""
    problems = []
    for table_name, rows in tables.items():
        fields = TABLES[table_name]
        names = [f[0] for f in fields]
        if rows:
            extra = [c for c in rows[0] if c not in names]
            missing = [c for c in names if c not in rows[0]]
            if extra:
                problems.append(f"{table_name}: columns not in the schema: {extra}")
            if missing:
                problems.append(f"{table_name}: schema columns absent from the table: {missing}")
        for i, row in enumerate(rows, start=2):
            for field in fields:
                if field[0] not in row:
                    continue
                reason = check_value(field, row[field[0]], tables)
                if reason:
                    problems.append(f"{table_name} row {i}: {reason}")
                    if len(problems) > 400:
                        return problems
    return problems
