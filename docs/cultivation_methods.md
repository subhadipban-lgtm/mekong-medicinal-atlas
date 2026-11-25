# Cultivation suitability — methods

**Screening only. This is not an agronomic recommendation.** Field validation with local extension services is required before any cultivation decision.

## Water availability — a documented substitution

The brief specified a water index from GLEAM evapotranspiration and soil moisture. Those archives (Zenodo 7803254 `ET.zip` 2.6 GB, `SoilMoiture.zip` 2.2 GB) were never retrievable, and the record's groundwater layer is point borehole data, not a grid. The index is therefore built from WorldClim precipitation and a PET estimate:

    water_index = mean( norm(bio12), norm(bio12 − PET), norm(wetland_fraction) )

- **bio12** — WorldClim annual precipitation (water supply).
- **bio12 − PET** — climatic water balance; **PET from Hargreaves (1985)** using WorldClim bio01 (mean temperature) and bio02 (mean diurnal range) and latitude-derived extraterrestrial radiation.
- **wetland_fraction** — share of each 5 km cell under wetland (CIFOR wetland V3b 2016), marking persistently wet ground.

`norm` is min-max over in-basin cells. The FAO irrigated-area layer (GMIA v5) is reported alongside but **not** summed into the index, because irrigation is managed water rather than a natural endowment. Cells above the median water index are treated as water-available (15,961 in-basin cells).

## Cultivation suitability

A cell is cultivable for a taxon when it is:
1. **climatically suitable** under the current SDM consensus (from `sdm_suitable_cells.json`), **and**
2. **water-available** (above the water-index median), **and**
3. **not intact habitat** — the ESA CCI/C3S 2020 land cover (300 m, mode-resampled) is not a forest or flooded-vegetation class (50–100 tree cover, 160–180 flooded).

Classes are the share of the taxon's climatically suitable range that is cultivable (more informative than absolute area, which simply scales with range size): high ≥ 50%, moderate 25–50%, low 5–25%, not feasible < 5%.

## Results (2026-11-26)

162 assessed taxa: 1 high, 35 moderate, 90 low, 36 not feasible. 15,961 cells are water-available and 18,677 are converted non-forest land.

## Limitations

- PET is a Hargreaves estimate, not measured evapotranspiration; it ignores humidity, wind and radiation beyond extraterrestrial values.
- The water index is a static screening surface; it does not model irrigation infrastructure, groundwater access or seasonal timing.
- Land cover is a 2020 snapshot; "converted" includes cropland and mosaic classes that may still hold remnant habitat.
- The suitability surface is the climate consensus of two correlative models, with all the SDM limitations.
- Outputs are screening priorities for field validation, never planting advice.
