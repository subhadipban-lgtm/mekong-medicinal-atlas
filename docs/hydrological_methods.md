# Hydrological fragmentation — methods

**What it is.** A distance-based screening of how many of a species' basin occurrences sit close to major dams. It is **not** a model of flow alteration, sediment trapping or groundwater drawdown.

## Data

Dam registry: Tiwari et al. 2023, Zenodo doi:10.5281/zenodo.7803254 (`Dams.zip` → `MekongDams_Tiwari_SDATA.xlsx`, 486 rows, WLE Greater Mekong Dams Observatory). 483 dams carry coordinates in the region.

**Major dam** = height ≥ 15 m OR installed capacity ≥ 15 MW (an operational subset of the ICOLD "large dam" definition). Dams missing both fields are excluded from the major set. 232 of 483 qualify.

## Metric

For every published in-basin occurrence (14,115 records) the great-circle distance to the nearest major dam is computed. Per species:

- `pct_within_10km_major_dam` — share of the species' in-basin occurrences within 10 km of a major dam.
- Class: **high** (>50%) · **moderate** (20–50%) · **low** (<20%).

**Threshold justification.** 10 km: (1) the registry records reservoirs, not the full inundated river length, so a buffer approximates near-dam riparian and downstream effects; (2) it matches the 5 km analysis cell, so the index is not dominated by sub-cell noise.

## Caveats

- Species with very few in-basin occurrences (n ≤ 5) produce noisy percentages; treat their class as indicative only. 6 of the 17 "high" species have n ≤ 3.
- Distance ignores dam size, reservoir area and flow regulation.
- No discharge or water-level series are used (they exist in the record for 30 gauges and could refine this in a follow-up).

## Outputs

- `data/processed/mekong_dams.csv` (483 dams), `data/geo/mekong_dams.geojson` (map overlay).
- `data/processed/hydrological_fragmentation.csv` (285 assessed species; 88 taxa without in-basin records are not assessed).
