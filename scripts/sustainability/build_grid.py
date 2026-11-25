#!/usr/bin/env python3
"""Build the common analysis grid and assign atlas occurrence records to it.

Grid choice (justified in docs/harmonization_methods.md):
  - 5 km, in a basin-tuned Albers equal-area conic projection (EPSG:102028-like; parameters below).
    Equal-area because every downstream metric is an area or a density; no Web Mercator anywhere.
  - 5 km resolves district-scale cultivation patterns while keeping the SDM stack for 333 taxa at
    about 32,000 cells, which an ensemble of 333 models can chew through in hours, not days.
  - It is finer than the population projections (1/8 deg) and coarser than the climate and
    population-count rasters (30 arc-sec), so resampling is conservative: downsampling (mean) for
    continuous layers, mode for categorical land cover.

Outputs (data/processed, and mirrored into web/data for the site):
  grid_cells.csv                  cell_id, row, col, center_lon, center_lat, area_km2, in_basin
  occurrence_grid_assignment.csv  occurrenceID -> cell_id with flags (outside basin, no cell, etc.)
  basin_grid.tif                  1 = in-basin cell (mask used to clip every environmental layer)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin
from pyproj import CRS, Transformer
from shapely.geometry import shape

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import atlas_lib as L  # noqa: E402

CELL_M = 5000.0
# Basin-tuned Albers equal-area conic: standard parallels bracketing the basin's latitudinal span.
CRS_NAME = "+proj=aea +lat_1=10 +lat_2=30 +lat_0=18.75 +lon_0=102 +datum=WGS84 +units=m +no_defs"


def main() -> int:
    basin = shape(json.loads((L.GEO / "mekong_basin.geojson").read_text())["features"][0]["geometry"])
    to_aea = Transformer.from_crs("EPSG:4326", CRS_NAME, always_xy=True)
    to_wgs = Transformer.from_crs(CRS_NAME, "EPSG:4326", always_xy=True)

    # Basin bounds in the analysis CRS.
    xs, ys = [], []
    geoms = basin.geoms if basin.geom_type == "MultiPolygon" else [basin]
    for geom in geoms:
        for lon, lat in zip(*geom.exterior.xy):
            x, y = to_aea.transform(lon, lat)
            xs.append(x); ys.append(y)
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)

    cols = int(np.ceil((x1 - x0) / CELL_M))
    rows = int(np.ceil((y1 - y0) / CELL_M))
    transform = from_origin(x0, y1, CELL_M, CELL_M)  # north-up: origin is the top-left corner
    mask = np.zeros((rows, cols), dtype=np.uint8)

    # Rasterise the basin: sample each cell centre; a cell counts as in-basin when its centre is.
    cells = []
    for r in range(rows):
        for c in range(cols):
            cx, cy = x0 + (c + 0.5) * CELL_M, y1 - (r + 0.5) * CELL_M
            lon, lat = to_wgs.transform(cx, cy)
            inside = bool(np.any(  # cheap containment test on the polygon grid is fine at 32k points
                _point_in(lon, lat, basin)
            ))
            if inside:
                mask[r, c] = 1
                cells.append((r, c, cx, cy, lon, lat))

    profile = {
        "driver": "GTiff", "width": cols, "height": rows, "count": 1, "dtype": "uint8",
        "crs": CRS_NAME, "transform": transform, "compress": "lzw", "nodata": 255,
    }
    with rasterio.open(L.PROCESSED / "basin_grid.tif", "w", **profile) as ds:
        ds.write(mask, 1)
    (L.WEB / "data").mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copyfile(L.PROCESSED / "basin_grid.tif", L.WEB / "data" / "basin_grid.tif")

    # Cell catalogue with per-cell area (constant in an equal-area projection).
    import math
    area_km2 = (CELL_M / 1000) ** 2
    L.write_csv(L.PROCESSED / "grid_cells.csv", [
        {"cell_id": f"r{r:04d}c{c:04d}", "row": r, "col": c,
         "x_aea": round(cx, 1), "y_aea": round(cy, 1),
         "center_lon": round(lon, 6), "center_lat": round(lat, 6),
         "area_km2": area_km2, "in_basin": 1}
        for r, c, cx, cy, lon, lat in cells])
    print(f"grid: {rows}x{cols} = {rows * cols} cells, {len(cells)} in-basin ({len(cells) * area_km2:,.0f} km2)")

    # Assign every published occurrence to a cell.
    occ = [r for r in L.read_csv(L.PROCESSED / "occurrences_published.csv")]
    out = []
    n_outside = n_bad = 0
    for rec in occ:
        lon, lat = float(rec["decimalLongitude"]), float(rec["decimalLatitude"])
        if not (lon and lat) or abs(lat) > 90:
            n_bad += 1
            continue
        x, y = to_aea.transform(lon, lat)
        if not (x0 <= x < x1 and y0 <= y < y1):
            n_outside += 1
            continue
        c = int((x - x0) / CELL_M)
        r = int((y1 - y) / CELL_M)
        out.append({"occurrenceID": rec["occurrenceID"], "species_id": rec["species_id"],
                    "cell_id": f"r{r:04d}c{c:04d}", "in_basin": int(mask[r, c]),
                    "basin_flag": rec["basin_flag"], "decimalLongitude": lon, "decimalLatitude": lat})
    L.write_csv(L.PROCESSED / "occurrence_grid_assignment.csv", out)
    n_in = sum(1 for o in out if o["in_basin"])
    print(f"occurrence assignment: {len(out)} assigned ({n_in} in-basin cells), "
          f"{n_outside} outside grid bbox, {n_bad} bad coordinates")
    return 0


def _point_in(lon: float, lat: float, poly) -> bool:
    from shapely.geometry import Point
    return poly.contains(Point(lon, lat)) or poly.touches(Point(lon, lat))


if __name__ == "__main__":
    sys.exit(main())
