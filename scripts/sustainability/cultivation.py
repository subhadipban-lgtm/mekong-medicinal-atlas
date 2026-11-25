#!/usr/bin/env python3
"""Cultivation suitability: the intersection of climate, water and already-converted land.

Screening only. This is not an agronomic recommendation; field validation with local extension
services is required before any cultivation decision.

Water availability (substitutes for GLEAM)
------------------------------------------
The GLEAM evapotranspiration and soil-moisture archives were never retrievable, so water
availability is built from WorldClim precipitation and a Hargreaves PET estimate already in the
environmental stack:
    water_index = mean( norm(bio12) , norm(bio12 - PET) , norm(wetland_fraction) )
where norm is min-max over in-basin cells. bio12 is water supply, bio12-PET is the climatic water
balance, and wetland fraction marks persistently wet ground. The irrigated-area layer is reported
alongside but not summed into the index, because irrigation is managed water, not a natural
endowment.

Cultivation suitability per taxon =
    climatically suitable (current SDM consensus) AND water_index >= median AND land cover not forest

Land cover: ESA CCI / C3S 2020 (300 m) resampled to the grid. Forest and flooded-forest classes
(50-100 tree cover, 160-180 flooded vegetation) are excluded so the surface never targets intact
habitat.

Feasibility classes (share of the climatically suitable range that is cultivable):
high >= 50%; moderate 25-50%; low 5-25%; not feasible < 5%.

Outputs: data/processed/water_availability.tif, data/processed/cultivation_summary.csv,
         data/processed/cultivation_suitability_summary.json
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import rasterio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import atlas_lib as L  # noqa: E402
from sustainability import common as C  # noqa: E402

FOREST_CLASSES = set(range(50, 110)) | {160, 170, 180}


def norm01(a, ok):
    v = a[np.isfinite(a) & ok]
    if v.size == 0 or v.max() == v.min():
        return np.zeros_like(a)
    out = np.zeros_like(a)
    sel = np.isfinite(a) & ok
    out[sel] = (a[sel] - v.min()) / (v.max() - v.min())
    return out


def main() -> int:
    with rasterio.open(L.PROCESSED / "env_stack_5000m.tif") as ds:
        names = [ds.descriptions[i - 1] for i in range(1, ds.count + 1)]
        stack = {n: ds.read(i) for i, n in enumerate(names, start=1)}
        profile = ds.profile.copy()
        transform, crs = ds.transform, ds.crs
    with rasterio.open(L.PROCESSED / "basin_grid.tif") as ds:
        inbasin = ds.read(1) == 1

    precip = stack["bio12_baseline"]
    aridity = stack["precip_minus_pet_baseline"]
    wetland = stack["wetland_fraction_baseline"]
    landcover = stack["landcover_class_2020"]

    water = (norm01(precip, inbasin) + norm01(aridity, inbasin) + norm01(wetland, inbasin)) / 3.0
    water[~inbasin] = np.nan
    water_thr = float(np.nanmedian(water))
    water_ok = water >= water_thr

    forest = np.isin(np.round(np.nan_to_num(landcover, nan=-1)).astype(int), list(FOREST_CLASSES))
    converted = inbasin & ~forest

    wprof = dict(profile, count=1, dtype="float32", compress="lzw", nodata=np.nan)
    with rasterio.open(L.PROCESSED / "water_availability.tif", "w", **wprof) as ds:
        ds.write(water.astype("float32"), 1)

    cells = L.read_csv(L.PROCESSED / "grid_cells.csv")
    idx_to_cell = [(int(c["row"]), int(c["col"])) for c in cells]
    suitable = L.read_json(L.PROCESSED / "sdm_suitable_cells.json")

    perf = {r["species_id"]: r for r in L.read_csv(L.PROCESSED / "sdm_performance.csv")}
    rows = []
    for sid, cells_ok in suitable.items():
        cur_area = len(cells_ok) * C.CELL_AREA_KM2
        if cur_area <= 0:
            continue
        # Exact intersection: climatically suitable AND water-available AND converted (non-forest) land.
        ok = [i for i in cells_ok if water_ok[idx_to_cell[i]] and converted[idx_to_cell[i]]]
        feasible = len(ok) * C.CELL_AREA_KM2
        frac = feasible / cur_area
        # Class by the share of the taxon's climatically suitable range that is cultivable, which is
        # more informative than an absolute area (absolute areas scale with range size).
        klass = ("high" if frac >= 0.50 else "moderate" if frac >= 0.25
                 else "low" if frac >= 0.05 else "not feasible")
        rows.append({"species_id": sid,
                     "accepted_name": perf.get(sid, {}).get("accepted_name", ""),
                     "climatically_suitable_area_current_km2": round(cur_area, 1),
                     "cultivation_feasible_area_km2": round(feasible, 1),
                     "converted_water_available_fraction": round(frac, 4),
                     "cultivation_feasibility_class": klass,
                     "water_availability_threshold": round(water_thr, 4),
                     "screening_note": "screening only; agronomic validation required"})
    L.write_csv(L.PROCESSED / "cultivation_summary.csv", rows)
    counts = defaultdict(int)
    for r in rows:
        counts[r["cultivation_feasibility_class"]] += 1
    out = {"n_taxa": len(rows), "water_index_threshold": round(water_thr, 4),
           "cells_water_available": int((water_ok & inbasin).sum()),
           "cells_converted_non_forest": int((converted & inbasin).sum()),
           "feasibility_classes": dict(counts),
           "note": "screening output; not an agronomic recommendation"}
    L.write_json(L.PROCESSED / "cultivation_suitability_summary.json", out)
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
