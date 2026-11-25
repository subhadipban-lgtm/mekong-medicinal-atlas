#!/usr/bin/env python3
"""Hydrological fragmentation: distance from each occurrence to the nearest major dam.

Dam registry: Tiwari et al. 2023 (Zenodo 7803254), 483 dams with coordinates from the WLE Greater
Mekong Dams Observatory. A dam counts as major when height >= 15 m or installed capacity >= 15 MW
(an operational subset of the ICOLD "large dam" definition; the registry gives height and capacity
for most but not all records, and dams missing both are excluded from the major set).

For every published in-basin occurrence we compute the great-circle distance to the nearest major
dam. A species is then classified by the share of its occurrences within 10 km of a major dam:

  high (>50%) | moderate (20-50%) | low (<20%) | none (0 occurrences in basin -> not assessed)

The 10 km threshold is a coarse buffer justified as: (1) the registry records reservoirs, not the
full inundated river length, so a wider buffer approximates downstream and riparian effects near
the dam wall; (2) it matches the 5 km analysis cell so the index is not dominated by sub-cell
noise. This is explicitly a distance-based proxy: it does not model flow alteration, sediment
trapping or groundwater drawdown (see docs/hydrological_methods.md).

Outputs: data/processed/hydrological_fragmentation.csv, docs/hydrological_methods.md
"""
from __future__ import annotations

import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import atlas_lib as L  # noqa: E402

THRESHOLD_KM = 10.0
MAJOR_HEIGHT_M = 15.0
MAJOR_CAPACITY_MW = 15.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def num(v):
    """Registry values arrive as strings, floats or 'None'/'n/a'."""
    if v is None:
        return None
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def main() -> int:
    dams = L.read_csv(L.PROCESSED / "mekong_dams.csv")
    major = []
    for d in dams:
        h, cap = num(d.get("height_m")), num(d.get("capacity_mw"))
        if h is not None and h >= MAJOR_HEIGHT_M:
            major.append(d)
        elif cap is not None and cap >= MAJOR_CAPACITY_MW:
            major.append(d)
    print(f"dams: {len(dams)} in registry; {len(major)} major (height >= {MAJOR_HEIGHT_M} m or capacity >= {MAJOR_CAPACITY_MW} MW)")

    occ = [r for r in L.read_csv(L.PROCESSED / "occurrences_published.csv")]
    in_basin = [r for r in occ if r["basin_flag"] == "in_basin"]
    per_species = defaultdict(list)
    for r in in_basin:
        lat, lon = float(r["decimalLatitude"]), float(r["decimalLongitude"])
        best = min(haversine_km(lat, lon, float(d["lat"]), float(d["lon"])) for d in major)
        per_species[r["species_id"]].append(best)

    rows = []
    for sid, dists in sorted(per_species.items()):
        within = sum(1 for x in dists if x <= THRESHOLD_KM)
        pct = 100.0 * within / len(dists)
        klass = "high" if pct > 50 else "moderate" if pct >= 20 else "low"
        rows.append({
            "species_id": sid,
            "n_occurrences_in_basin": len(dists),
            "n_within_10km_major_dam": within,
            "pct_within_10km_major_dam": round(pct, 2),
            "mean_distance_to_nearest_major_dam_km": round(sum(dists) / len(dists), 3),
            "hydrological_vulnerability_class": klass,
        })
    L.write_csv(L.PROCESSED / "hydrological_fragmentation.csv", rows)
    classes = Counter(r["hydrological_vulnerability_class"] for r in rows)
    names = {s["species_id"]: s["accepted_name"] for s in L.read_csv(L.PROCESSED / "species_master.csv")}
    high = sorted((r for r in rows if r["hydrological_vulnerability_class"] == "high"),
                  key=lambda r: -r["pct_within_10km_major_dam"])[:12]
    print(f"species assessed: {len(rows)} | classes: {dict(classes)}")
    for r in high:
        print(f"   {names.get(r['species_id'], r['species_id']):34} {r['pct_within_10km_major_dam']:5.1f}% within 10 km")
    return 0


if __name__ == "__main__":
    sys.exit(main())
