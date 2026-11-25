# Harmonization methods — sustainability layers

**Status:** grid and occurrence assignment complete; the environmental stack is assembled when the five large Zenodo archives finish downloading (see `docs/zenodo7803254_inventory.md`).

## Analysis grid

- **Resolution:** 5 km. Justification: it resolves cultivation suitability at district scale (a district is tens of km across); at 31,922 in-basin cells it keeps the SDM computation tractable for 333 taxa with an ensemble of algorithms; and it is coarser than the climate and population-count rasters (30 arc-sec ≈ 1 km) so those are downsampled conservatively rather than upscaled. It is finer than the SSP population projections (1/8° ≈ 14 km), which are therefore upscaled by nearest-neighbour allocation to the grid — documented as the coarsest input.
- **Projection:** basin-tuned Albers equal-area conic, `+proj=aea +lat_1=10 +lat_2=30 +lat_0=18.75 +lon_0=102 +datum=WGS84 +units=m +no_defs`. Equal-area is mandatory because every downstream quantity (suitable area, feasible area, density) is an area; Web Mercator is never used for calculation.
- **Cell catalogue:** `data/processed/grid_cells.csv` (cell_id, row, col, Albers x/y, WGS84 centre, area). Basin mask raster: `data/processed/basin_grid.tif` (1 = cell centre inside the basin boundary of Tiwari et al., doi:10.5281/zenodo.7622998). Cell area is 25 km² by construction; the mask yields 31,922 cells and 798,050 km², consistent with the published basin area.
- **Rasterization rule:** a cell is in-basin when its centre falls inside the boundary. Edge cells are thereby conservative at the rim; the method is deterministic and scripted (`scripts/sustainability/build_grid.py`).

## Occurrence assignment

Each published occurrence (153,798 records; the grade-D records stay excluded) is projected to Albers and assigned to the cell containing it (`scripts/sustainability/build_grid.py` → `data/processed/occurrence_grid_assignment.csv`). Flags: `in_basin` (cell centre in basin), and records outside the grid bbox are counted but not assigned. Result: 14,115 records in in-basin cells across **281 taxa**; 195 taxa have ≥10 in-basin records and enter the SDM; 86 taxa have 1–9 and 52 have none — both groups are reported "not assessed (insufficient data)" for SDM, never silently modelled.

## Per-variable resampling to the 5 km grid

| Layer | Source resolution | Resampling | Rationale |
|---|---|---|---|
| EM-Earth precipitation, temperature (hist. + projected) | 30 arc-sec (pending verification) | bilinear | continuous fields |
| GLEAM ET, soil moisture | 0.25° (pending verification) | bilinear | continuous fields |
| ESA CCI / C3S land cover | 300 m | mode (dominant class), tie → most common basin-wide | categorical |
| GPW population counts | 30 arc-sec | sum (people conserved) | counts |
| GDP PPP | 30 arc-sec | bilinear on log1p then inverse (skewed) | continuous, heavy-tailed |
| FAO GMIA irrigated fraction | 5 arc-min | bilinear | continuous fraction |
| CIFOR wetland class | ~120 m | mode | categorical |
| SSP population/GDP projections | 1/8° | nearest-neighbour to cells, then area-scaled | coarse source; allocation only |
| DEM | 30 arc-sec | bilinear | continuous |

Every step is scripted in `scripts/sustainability/`; no manual GIS edits. All rasters are reprojected to the Albers CRS before resampling (`rasterio.warp`), so no resampling ever happens in a non-equal-area CRS.

## The stack

`data/processed/env_stack_5000m.tif` will hold one band per variable, with `data/processed/env_stack_bands.csv` giving band order, variable, units, source archive and temporal window. A single band file (not 30 separate GeoTIFFs) keeps the SDM I/O simple and the band metadata auditable.

## Software

Python 3.14.7 (pinned venv); rasterio 1.5.2 / GDAL 3.12.2; pyproj 3.8.0; shapely 2.2.0; numpy; scikit-learn 1.9.1. Versions are recorded again in `docs/sustainability_environment.md` before the SDM runs.
