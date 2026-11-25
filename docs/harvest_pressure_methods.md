# Harvest-pressure index — methods

**What it is.** A screening proxy for the relative potential collection pressure on atlas taxa, computed per 5 km analysis cell and summarised per species. It is **not measured offtake** and is labelled as such on the site and in the manuscript.

## Definition

`harvest_pressure = norm(population_density_2050) × norm(species_richness) × norm(local_use_score)`

- **population_density_2050** — SSP2 population projection for 2050 (Jones & O'Neill, SEDAC, 1/8°, doi:10.7927/m30p-j498; via Zenodo 7803254 `SocioEconomic/Pupulation_Projections/ssp2_POP.txt`), allocated to the nearest 5 km cell and divided by the cell area (25 km²), then `log1p`-transformed before normalisation. 2050 is chosen to stay temporally aligned with the climate-analysis window.
- **species_richness** — the number of atlas taxa with at least one published occurrence in the cell (in-basin cells only).
- **local_use_score** — per species, the evidence-grade-weighted count of independent use records in the atlas: grade A = 3, B = 2, C = 1, D = 0.5, summed over the species' `uses.csv` rows. **Restriction:** only taxa with at least one use record carry a positive score; taxa without use records score 0. 281 of 333 taxa have at least one use record and enter the summary.

Each factor is min-max normalised over the in-basin cells (only positive values participate). Cells without any atlas taxon have richness 0 and therefore pressure 0 by construction — the index measures pressure on the species the atlas records, not general plant harvesting.

## Tiers

Quantiles over in-basin cells with positive pressure (computed 2026-11-25): q50 = 0.0018, q75 = 0.0049, q90 = 0.0139.
`low` ≤ q50 · `moderate` (q50, q75] · `high` (q75, q90] · `very high` > q90.
Per-species class uses the same thresholds applied to the species' mean pressure across the cells where it occurs.

## Inputs and outputs

- Inputs: `data/processed/occurrence_grid_assignment.csv`, `data/processed/uses.csv`, SSP2 grid (raw, Expansion drive).
- Outputs: `data/processed/harvest_pressure.tif` (float32, Albers 5 km, NaN outside the basin), `data/processed/harvest_pressure_summary.csv`.

## Limitations (shown on the site too)

- Population is SSP2-2050, one scenario only; the index does not vary by SSP.
- The 1/8° source is coarse (≈14 km) and is allocated to 5 km cells by nearest-neighbour; density within a cell is flat.
- Richness counts published records; sampling effort varies across the basin, so richness partially reflects collection effort.
- The use score weights grades but not the strength of the reported use.
- The index is a relative ranking, not a harvest-rate estimate.
