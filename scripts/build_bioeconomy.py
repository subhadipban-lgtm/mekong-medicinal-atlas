#!/usr/bin/env python3
"""Build the bioeconomy layer.

Outputs
  data/processed/bioeconomy_profiles.csv         one row per atlas taxon (all 333)
  data/processed/bioeconomy_priority_summary.csv per tier: count and the species_id list
  data/processed/bioeconomy_priority_cells.geojson
                                                  grid-cell counts of high-priority taxa
                                                  (empty FeatureCollection while none exists)

The layer is a screening layer, not a valuation. Nothing is imputed. `unknown` is written
whenever no cited source supports a coding.

Scope of this coding pass (narrowed by the project owner on 2026-11-26): only taxa covered by
the two designated value-chain studies may be coded — the Cao Bang Geopark jiaogulan study
(BIOSRC-001, *Gynostemma pentaphyllum*) and the Naban River Watershed study (BIOSRC-002,
*Asparagus filicinus*, *A. subscandens*, *Paris polyphylla*, *Stemona tuberosa*,
*Tacca chantrieri*). Neither study covers any of the 333 atlas taxa, so every coded field is
`unknown` and `bioeconomy_profile_available` is False everywhere.

Facts documented elsewhere in the atlas (a CITES appendix, a wild/cultivated status) are NOT
copied into the coded fields, because the coding rule does not allow a source outside the two
designated studies. They are recorded as note pointers for a later coding pass.

`bioeconomy_priority_tier` and `bioeconomy_profile_available` are derived, per
docs/bioeconomy_priority_rule.md.

The species_master rows are updated in place with:
  bioeconomy_profile_available, bioeconomy_priority_tier, bioeconomy_source_ids
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import atlas_lib as L  # noqa: E402

BIOSRC_CONSULTED = ["BIOSRC-001", "BIOSRC-002", "BIOSRC-003", "BIOSRC-005"]
CITES_LISTED = {"I", "II", "III"}
TIERS = ("high", "medium", "low", "unknown")

# Field | type | definition | allowed values / units | required | source requirement
DICTIONARY = [
    ("species_id", "string", "Join key to the atlas taxon (species_master.csv).", "sp_[a-z0-9_]+", "yes",
     "n/a — the key"),
    ("value_chain_type", "string", "Dominant marketing channel documented in a value-chain study.",
     "wild-informal / wild-formal / cultivated-informal / cultivated-formal / mixed / unknown", "yes",
     "A value-chain study that names the taxon and its channel (BIOSRC-001 or BIOSRC-002)."),
    ("trade_exposure", "string", "Documented commercial trade status.",
     "CITES-listed / BioTrade-supported / export-commodity / domestic-only / no-trade-data / unknown", "yes",
     "A trade study, a CITES listing or a BioTrade programme document that names the taxon."),
    ("certification_readiness", "string", "Certification standard applicable to the taxon's production mode.",
     "GACP-eligible / FairWild-eligible / both / neither / unknown", "yes",
     "Derived from wild_cultivated_status by the documented rule; needs no separate source."),
    ("livelihood_dependence", "string", "Documented reliance of households on income from the taxon.",
     "high / moderate / low / unknown", "yes",
     "A household survey or value-chain study with a documented income share."),
    ("equity_flag", "string", "Documented benefit-distribution finding.",
     "equitable / inequitable / not-assessed / unknown", "yes",
     "A value-chain study or a documented benefit-sharing assessment; never inferred from trade status."),
    ("valuation_method", "string", "Kind of economic valuation available for the taxon.",
     "market-price / bioprospecting-estimate / none / unknown", "yes",
     "The valuation study, if any. No per-species bioprospecting value is ever computed."),
    ("market_price_proxy", "float", "A documented price observation. A proxy, not a valuation.",
     "numeric or null", "if the other three price fields are populated",
     "All four of value, currency+unit, date and source_id are required together."),
    ("market_price_currency_unit", "string", "Currency and unit of market_price_proxy.",
     "e.g. VND/kg, USD/kg dry", "if market_price_proxy is populated",
     "Stated in the price source."),
    ("market_price_date", "date", "Date of the price observation.", "ISO date (YYYY-MM-DD)",
     "if market_price_proxy is populated", "Stated in the price source."),
    ("market_price_source_id", "string", "Source id of the price observation.", "a bioeconomy source_id",
     "if market_price_proxy is populated", "docs/bioeconomy_sources.csv"),
    ("coded_confidence", "string", "Confidence in the coding of this row.", "high / medium / low", "yes",
     "Judgement of the coder, recorded on every row."),
    ("coded_by", "string", "Agent identifier that coded the row.", "free text", "yes", "n/a"),
    ("reviewed_by", "string", "Human reviewer, or 'pending'.", "free text or 'pending'", "yes", "n/a"),
    ("source_ids", "string", "Semicolon-separated bioeconomy source ids used for the row.",
     "semicolon-separated BIOSRC-* ids", "yes", "docs/bioeconomy_sources.csv"),
    ("bioeconomy_priority_tier", "string", "Derived priority tier.", "high / medium / low / unknown", "yes",
     "Derived by the rule in docs/bioeconomy_priority_rule.md; no separate source."),
    ("bioeconomy_profile_available", "bool", "True when at least one coded field is not 'unknown'.",
     "True / False", "yes", "Derived."),
    ("notes", "text", "Free-text provenance and any source pointers.", "free text", "optional", "n/a"),
]


def write_dictionary() -> None:
    rows = [{"field": f, "type": t, "definition": d, "allowed_values_or_units": a, "required": r,
             "source_requirement": s} for f, t, d, a, r, s in DICTIONARY]
    L.write_csv(L.ROOT / "data" / "dictionary_bioeconomy.csv", rows,
                fieldnames=["field", "type", "definition", "allowed_values_or_units", "required",
                            "source_requirement"])


def bioeconomy_profile_for(master_row: dict) -> dict:
    """One profile row. Only the two designated value-chain studies may code a taxon; neither
    covers any atlas taxon, so every coded field is `unknown`. Facts that are documented
    elsewhere in the atlas (a CITES appendix, a cultivation status) are recorded as note
    pointers, not as codings, so the layer never mixes sources the coding rule does not allow."""
    cites = (master_row.get("cites_appendix") or "unknown").strip()
    pointer = ""
    if cites in CITES_LISTED:
        pointer = (f" The atlas separately records CITES Appendix {cites} for this taxon "
                   "(conservation_trade.csv, SRC-004); that listing is NOT copied into "
                   "trade_exposure here, because the two designated value-chain studies do not "
                   "cover this taxon. It is available for a later coding pass.")
    return {
        "species_id": master_row["species_id"],
        "value_chain_type": "unknown",
        "trade_exposure": "unknown",
        "certification_readiness": "unknown",
        "livelihood_dependence": "unknown",
        "equity_flag": "unknown",
        "valuation_method": "unknown",
        "market_price_proxy": "",
        "market_price_currency_unit": "",
        "market_price_date": "",
        "market_price_source_id": "",
        "coded_confidence": "low",
        "coded_by": "zcode_2026-11-26",
        "reviewed_by": "pending",
        "source_ids": "; ".join(BIOSRC_CONSULTED),
        "notes": (
            "No value-chain evidence for this taxon: the two value-chain studies retrieved for "
            "this coding pass (BIOSRC-001 Cao Bang Geopark jiaogulan, Gynostemma pentaphyllum; "
            "BIOSRC-002 Naban River Watershed, Yunnan — Asparagus filicinus, A. subscandens, "
            "Paris polyphylla, Stemona tuberosa, Tacca chantrieri) cover none of the 333 atlas "
            "taxa. Every coded field is therefore `unknown` by rule, not by omission; no "
            "pharmacology-corpus inference was made and no bioprospecting value is claimed."
            + pointer
        ),
    }


def priority_tier(row: dict) -> str:
    t = row["trade_exposure"] in {"CITES-listed", "BioTrade-supported", "export-commodity"}
    low_dep = row["livelihood_dependence"] in {"high", "moderate"}
    cert = row["certification_readiness"] in {"GACP-eligible", "FairWild-eligible", "both"}
    inputs = (row["trade_exposure"], row["livelihood_dependence"], row["certification_readiness"])
    if any(v == "unknown" for v in inputs):
        return "unknown"
    n = sum([t, low_dep, cert])
    return {3: "high", 2: "medium", 1: "low", 0: "low"}[n]


def main() -> int:
    master = L.read_csv(L.PROCESSED / "species_master.csv")
    profiles = [bioeconomy_profile_for(r) for r in master]

    # Hard guard: a market-price proxy may never appear without currency/unit, date and source.
    for p in profiles:
        if p["market_price_proxy"].strip():
            if not (p["market_price_currency_unit"].strip() and p["market_price_date"].strip()
                    and p["market_price_source_id"].strip()):
                sys.exit(f"{p['species_id']}: market_price_proxy without currency/unit, date or source_id")
            float(p["market_price_proxy"])

    for p in profiles:
        p["bioeconomy_priority_tier"] = priority_tier(p)

    # Profile is "available" only when at least one substantive coding is documented.
    substantive = ("value_chain_type", "trade_exposure", "certification_readiness",
                   "livelihood_dependence", "equity_flag", "valuation_method", "market_price_proxy")
    for p in profiles:
        p["bioeconomy_profile_available"] = "True" if any(
            str(p[k]).strip() not in ("", "unknown") for k in substantive) else "False"

    fieldnames = [
        "species_id", "value_chain_type", "trade_exposure", "certification_readiness",
        "livelihood_dependence", "equity_flag", "valuation_method", "market_price_proxy",
        "market_price_currency_unit", "market_price_date", "market_price_source_id",
        "coded_confidence", "coded_by", "reviewed_by", "source_ids", "bioeconomy_priority_tier",
        "bioeconomy_profile_available", "notes",
    ]
    L.write_csv(L.PROCESSED / "bioeconomy_profiles.csv", profiles, fieldnames=fieldnames)

    summary = []
    for tier in TIERS:
        ids = [p["species_id"] for p in profiles if p["bioeconomy_priority_tier"] == tier]
        summary.append({"bioeconomy_priority_tier": tier, "count": len(ids),
                        "species_ids": ";".join(ids)})
    L.write_csv(L.PROCESSED / "bioeconomy_priority_summary.csv", summary,
                fieldnames=["bioeconomy_priority_tier", "count", "species_ids"])

    # Grid-cell counts of high-priority taxa, for the Explore overlay. High-priority taxa: none
    # in this release, so the layer is an empty FeatureCollection and the JS says so.
    high = {p["species_id"] for p in profiles if p["bioeconomy_priority_tier"] == "high"}
    cells = L.read_csv(L.PROCESSED / "grid_cells.csv") if (L.PROCESSED / "grid_cells.csv").exists() else []
    assignments = L.read_csv(L.PROCESSED / "occurrence_grid_assignment.csv") if (L.PROCESSED / "occurrence_grid_assignment.csv").exists() else []
    counts: dict[str, int] = {}
    if high and cells:
        cell_of = {a["species_id"]: set() for a in assignments if a["in_basin"] == "1"}
        for a in assignments:
            if a["in_basin"] == "1" and a["species_id"] in high:
                cell_of[a["species_id"]].add(a["cell_id"])
        cell_species: dict[str, set] = {}
        for sid, cs in cell_of.items():
            for c in cs:
                cell_species.setdefault(c, set()).add(sid)
        counts = {c: len(s) for c, s in cell_species.items()}
    by_id = {c["cell_id"]: c for c in cells}
    features = []
    for cell_id, count in counts.items():
        c = by_id.get(cell_id)
        if not c:
            continue
        lon, lat = float(c["center_lon"]), float(c["center_lat"])
        half = 0.0225
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [[
                [lon - half, lat - half], [lon + half, lat - half], [lon + half, lat + half],
                [lon - half, lat + half], [lon - half, lat - half]]]},
            "properties": {"cell_id": cell_id, "count_high": count},
        })
    geojson = {"type": "FeatureCollection", "name": "bioeconomy_priority_cells",
               "note": ("Count of high-priority bioeconomy taxa per 5 km in-basin cell. "
                        "A screening layer; 0 in this release because no taxon has a documented "
                        "high-priority bioeconomy tier. Not a value measure."),
               "features": features}
    (L.PROCESSED / "bioeconomy_priority_cells.geojson").write_text(
        json.dumps(geojson, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # Update species_master in place (idempotent): three new columns.
    available_by_id = {p["species_id"]: p for p in profiles}
    for row in master:
        p = available_by_id[row["species_id"]]
        row["bioeconomy_profile_available"] = p["bioeconomy_profile_available"]
        row["bioeconomy_priority_tier"] = p["bioeconomy_priority_tier"]
        row["bioeconomy_source_ids"] = p["source_ids"]
    L.write_csv(L.PROCESSED / "species_master.csv", master)

    tiers = {t: sum(1 for p in profiles if p["bioeconomy_priority_tier"] == t) for t in TIERS}
    n_avail = sum(1 for p in profiles if p["bioeconomy_profile_available"] == "True")
    write_dictionary()
    print(f"bioeconomy profiles: {len(profiles)} taxa | profile_available True: {n_avail} | tiers: {tiers}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
