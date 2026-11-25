#!/usr/bin/env python3
"""Build the map layers from the published occurrence records.

Two populations are published, because they answer different questions:

data/geo/occurrences.geojson
  Every published record that falls INSIDE the Mekong basin boundary: one point per Darwin Core
  record. This is the atlas's core evidence and it is not thinned.

data/geo/occurrences_outside_basin.geojson
  Records from the six basin countries that fall OUTSIDE the basin. They show where a species
  occurs in the same country but in another watershed, and are generalised to one point per
  species per 0.5-degree cell (about 55 km) because there are far too many to cluster smoothly.

data/geo/species/<slug>.geojson
  Both sets for one species, for its species page.

Species names are resolved by the pages from data/species.json, so features carry only ids.
Written to data/geo/ and copied to web/data/geo/.

Usage: python scripts/build_geo.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import atlas_lib as L  # noqa: E402

OUTSIDE_CELL_DEG = 0.5
Q = {"high": 0, "medium": 1, "low": 2}


def specimen(r: dict) -> int:
    return int(r["basisOfRecord"] in ("PRESERVED_SPECIMEN", "MATERIAL_SAMPLE", "LIVING_SPECIMEN"))


def point(lon: float, lat: float, props: dict) -> dict:
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": props}


def record_feature(r: dict) -> dict:
    return point(float(r["decimalLongitude"]), float(r["decimalLatitude"]), {
        "id": r["species_id"], "g": r["evidence_grade"], "s": specimen(r), "q": r["coordinate_quality_flag"],
        "gen": int(r["generalized"] == "yes"), "c": r["countryCode"], "k": r["gbif_key"], "n": 1})


def grouped_features(records: list[dict], cell: float) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in records:
        groups[(r["species_id"], round(float(r["decimalLatitude"]) / cell), round(float(r["decimalLongitude"]) / cell))].append(r)
    out = []
    for _, members in sorted(groups.items()):
        first = members[0]
        out.append(point(float(first["decimalLongitude"]), float(first["decimalLatitude"]), {
            "id": first["species_id"], "g": first["evidence_grade"],
            "s": int(sum(specimen(m) for m in members) * 2 >= len(members)),
            "q": min((m["coordinate_quality_flag"] for m in members), key=lambda f: Q[f]),
            "gen": int(any(m["generalized"] == "yes" for m in members)), "c": first["countryCode"],
            "k": first["gbif_key"], "n": len(members)}))
    return out


def dump(obj) -> str:
    return json.dumps(obj, separators=(",", ":"))


def main() -> int:
    published = [r for r in L.read_csv(L.PROCESSED / "occurrences.csv") if r["evidence_grade"] != "D"]
    inside = [r for r in published if r["basin_flag"] == "in_basin"]
    outside = [r for r in published if r["basin_flag"] != "in_basin"]
    inside_fc = {"type": "FeatureCollection", "name": "occurrences_in_basin",
                 "note": "One point per published Darwin Core record inside the Mekong basin boundary.",
                 "features": [record_feature(r) for r in inside]}
    outside_fc = {"type": "FeatureCollection", "name": "occurrences_outside_basin", "cell_size_degrees": OUTSIDE_CELL_DEG,
                  "record_count": len(outside),
                  "note": (f"Records of the six basin countries outside the basin boundary, generalised to one point per "
                           f"species per {OUTSIDE_CELL_DEG}-degree cell; n is the number of records behind each point."),
                  "features": grouped_features(outside, OUTSIDE_CELL_DEG)}

    by_species_in, by_species_out = defaultdict(list), defaultdict(list)
    for r in inside:
        by_species_in[r["species_id"]].append(record_feature(r))
    for f in outside_fc["features"]:
        by_species_out[f["properties"]["id"]].append(f)

    for dest in (L.GEO, L.WEB / "data" / "geo"):
        (dest / "species").mkdir(parents=True, exist_ok=True)
        (dest / "occurrences.geojson").write_text(dump(inside_fc), encoding="utf-8")
        (dest / "occurrences_outside_basin.geojson").write_text(dump(outside_fc), encoding="utf-8")
        for sid in sorted(set(by_species_in) | set(by_species_out)):
            fc = {"type": "FeatureCollection", "features": by_species_in.get(sid, []) + by_species_out.get(sid, [])}
            (dest / "species" / f"{sid[3:]}.geojson").write_text(dump(fc), encoding="utf-8")

    summary = {
        "inside_basin": {"records": len(inside), "points": len(inside_fc["features"]),
                         "species": len(by_species_in), "by_country": dict(Counter(r["countryCode"] for r in inside))},
        "outside_basin": {"records": len(outside), "points": len(outside_fc["features"]), "cell_size_degrees": OUTSIDE_CELL_DEG,
                          "by_country": dict(Counter(f["properties"]["c"] for f in outside_fc["features"]))},
        "species_with_map_data": len(set(by_species_in) | set(by_species_out)),
    }
    L.write_json(L.GEO / "_occurrence_geo_summary.json", summary)
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
