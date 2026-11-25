#!/usr/bin/env python3
"""Harvest-pressure proxy per grid cell and per species.

  harvest_pressure = norm(population_density_2050) * norm(species_richness) * norm(local_use_score)

- population_density_2050: SSP2 population projection for 2050 (Jones & O'Neill, SEDAC, 1/8 deg,
  from Zenodo 7803254 SocioEconomic/Pupulation_Projections/ssp2_POP.txt), allocated to the nearest
  5 km cell and divided by the cell area (25 km2).
- species_richness: the number of atlas taxa with at least one published record in the cell
  (occurrence_grid_assignment.csv, in-basin cells only).
- local_use_score: per species, the evidence-grade-weighted number of independent use records in
  the atlas (grade A = 3, B = 2, C = 1, D = 0.5). Restricted to taxa with at least one use record;
  taxa without use records score 0, and the restriction is stated everywhere the index is shown.

Each factor is min-max normalised over the in-basin cells (after log1p for population density).
Cells without any atlas taxon have richness 0 and therefore pressure 0 by construction - the index
measures pressure on the species the atlas records, not general harvesting.

Tiers (quantiles over cells with positive pressure):
  low 0-50% | moderate 50-75% | high 75-90% | very high 90-100%.

This is a proxy for potential collection pressure, NOT measured offtake; it is labelled as such on
the site and in the manuscript.

Outputs: data/processed/harvest_pressure.tif (float32, Albers grid),
         data/processed/harvest_pressure_summary.csv,
         docs/harvest_pressure_methods.md
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import atlas_lib as L  # noqa: E402

SSP2 = ("/Volumes/Expansion/mekong_sustainability/data/raw/zenodo7803254/extracted/SocioEconomic/"
        "SocioEconomic/Pupulation_Projections/ssp2_POP.txt")
GRADE_W = {"A": 3.0, "B": 2.0, "C": 1.0, "D": 0.5}


def load_pop_2050(path: str) -> list[tuple[float, float, float]]:
    """(lon, lat, population) triples for 2050. The grid file holds lon, lat, then years 2010..2100."""
    out = []
    with open(path) as fh:
        for line in fh:
            parts = line.split()
            if len(parts) < 12 or parts[0] in ("Longitude", "longitude", "#"):
                continue
            try:
                lon, lat = float(parts[0]), float(parts[1])
                pop = float(parts[6])  # 0-based: 2=2010 ... 6=2050
            except ValueError:
                continue
            if 95 <= lon <= 110 and 5 <= lat <= 35 and pop >= 0:
                out.append((lon, lat, pop))
    return out


def main() -> int:
    cells = L.read_csv(L.PROCESSED / "grid_cells.csv")
    cell_ids = {c["cell_id"]: c for c in cells}
    rows_n = max(int(c["row"]) for c in cells) + 1
    cols_n = max(int(c["col"]) for c in cells) + 1
    cell_xy = {(int(c["row"]), int(c["col"])): c["cell_id"] for c in cells}

    # -- population density ---------------------------------------------------------
    pop = load_pop_2050(SSP2)
    max_y = max(float(c["y_aea"]) for c in cells) + C.CELL_M / 2
    min_x = min(float(c["x_aea"]) for c in cells) - C.CELL_M / 2
    density = defaultdict(float)
    for lon, lat, p in pop:
        x, y = C.TO_XY.transform(lon, lat)
        col = int((x - min_x) / C.CELL_M)
        row = int((max_y - y) / C.CELL_M)
        if (row, col) in cell_xy:
            density[(row, col)] += p

    pop_arr = np.zeros((rows_n, cols_n), dtype=np.float32)
    for (r, c), p in density.items():
        pop_arr[r, c] = p / C.CELL_AREA_KM2  # people per km2

    # In-basin mask, so every normalization below is over basin cells only.
    mask = np.zeros((rows_n, cols_n), dtype=np.uint8)
    for c in cells:
        mask[int(c["row"]), int(c["col"])] = 1
    pop_arr[mask == 0] = 0

    # -- species richness and local use score --------------------------------------
    assignment = L.read_csv(L.PROCESSED / "occurrence_grid_assignment.csv")
    richness = Counter()
    for a in assignment:
        if a["in_basin"] == "1" and a["cell_id"] in cell_ids:
            richness[a["cell_id"]] += 1
    use_w = defaultdict(float)
    for u in L.read_csv(L.PROCESSED / "uses.csv"):
        use_w[u["species_id"]] += GRADE_W.get(u["evidence_grade"], 0.5)

    rich_arr = np.zeros((rows_n, cols_n), dtype=np.float32)
    use_arr = np.zeros((rows_n, cols_n), dtype=np.float32)
    species_in_cell = defaultdict(set)
    for a in assignment:
        if a["in_basin"] == "1" and a["cell_id"] in cell_ids:
            species_in_cell[a["cell_id"]].add(a["species_id"])
    for cell_id, sps in species_in_cell.items():
        c = cell_ids[cell_id]
        r, col = int(c["row"]), int(c["col"])
        rich_arr[r, col] = len(sps)
        use_arr[r, col] = math.log1p(sum(use_w[s] for s in sps))

    def norm01(a: np.ndarray) -> np.ndarray:
        a = np.where(mask == 1, a, 0.0)
        v = a[a > 0]
        if v.size == 0 or v.max() == v.min():
            return np.zeros_like(a)
        out = np.zeros_like(a)
        out[a > 0] = (a[a > 0] - v.min()) / (v.max() - v.min())
        return out

    p_dens = norm01(np.log1p(pop_arr))
    p_rich = norm01(rich_arr)
    p_use = norm01(use_arr)
    pressure = p_dens * p_rich * p_use

    # -- write the raster (masked to in-basin cells) -------------------------------
    pressure[mask == 0] = np.nan
    with rasterio.open(L.PROCESSED / "basin_grid.tif") as ds:
        transform, crs = ds.transform, ds.crs
    profile = {"driver": "GTiff", "width": cols_n, "height": rows_n, "count": 1, "dtype": "float32",
               "crs": crs, "transform": transform, "compress": "lzw", "nodata": np.nan}
    with rasterio.open(L.PROCESSED / "harvest_pressure.tif", "w", **profile) as ds:
        ds.write(pressure, 1)
    import shutil
    shutil.copyfile(L.PROCESSED / "harvest_pressure.tif", L.WEB / "data" / "harvest_pressure.tif")

    # -- tiers -----------------------------------------------------------------------
    pos = pressure[np.isfinite(pressure) & (pressure > 0)]
    q50, q75, q90 = (np.quantile(pos, q) for q in (0.50, 0.75, 0.90))

    def tier(v: float) -> str:
        if v <= 0:
            return "low"
        if v > q90:
            return "very high"
        if v > q75:
            return "high"
        if v > q50:
            return "moderate"
        return "low"

    # -- per-species summary ---------------------------------------------------------
    summary = []
    for sid in sorted(use_w):
        cells_of = {a["cell_id"] for a in assignment if a["species_id"] == sid and a["in_basin"] == "1"}
        vals = []
        for cell_id in cells_of:
            c = cell_ids.get(cell_id)
            if c:
                v = pressure[int(c["row"]), int(c["col"])]
                if np.isfinite(v):
                    vals.append(v)
        if not vals:
            continue
        mean_p = float(np.mean(vals))
        summary.append({"species_id": sid, "mean_harvest_pressure_in_range": round(mean_p, 6),
                        "harvest_pressure_class": tier(mean_p),
                        "n_cells": len(vals), "local_use_score": round(use_w[sid], 2)})
    L.write_csv(L.PROCESSED / "harvest_pressure_summary.csv", summary)

    import collections
    tiers = collections.Counter(s["harvest_pressure_class"] for s in summary)
    print(f"population points: {len(pop)} -> {len(density)} cells")
    print(f"pressure quantiles: q50={q50:.4f} q75={q75:.4f} q90={q90:.4f}")
    print(f"species summary: {len(summary)} taxa (with use records) by class: {dict(tiers)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
