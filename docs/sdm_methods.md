# Species distribution models — methods

## Predictor source: a documented substitution

The SDM layer was specified against **EM-Earth** (Tiwari et al. 2023, Zenodo doi:10.5281/zenodo.7803254). Two facts made that source unusable at build time: the record was unreachable from the build environment for a sustained period, and its climate archives are 4–21 GB each (the 30 arc-sec global files are 9.9–21 GB), which the build disk cannot hold.

The predictors therefore come from **WorldClim 2.1** (Fick & Hijmans 2017, doi:10.1002/ijc.31937), an independent, peer-reviewed global climatology distributed as cloud-range-readable GeoTIFFs. **This is a deliberate robustness choice, not a workaround**: it makes the analysis reproducible from a public, versioned source in minutes, and it puts the climate layer on an independent model rather than on the same synthesis that supplies the socioeconomic layers. If EM-Earth becomes reachable, it is run as a **sensitivity analysis** and both sets of results are reported (see "Sensitivity analysis" below).

## Resolution

WorldClim 2.1 at **2.5 arc-minutes (≈4.6 km)** for the current period and for **2041–2060** under **SSP2-4.5 and SSP5-8.5** (MIROC6), fetched **bbox-first**: GDAL's `/vsicurl` driver reads only the window covering the Mekong bounding box (93.3–109.3 °E, 8.0–34.1 °N), so 33 small crops totalling ~12 MB were transferred rather than the ~3 GB the three global archives would require.

Why not 30 arc-sec: WorldClim publishes 30 arc-sec only as 9.9 GB (current) / 21 GB (each future) global archives, and the analysis runs on a 5 km grid, so 30 arc-sec would be aggregated to 5 km cells in any case. 2.5 arc-min is *resolution-matched* to the analysis grid, which avoids pretending to sub-grid precision the SDM cannot use. The fetch script supports `--res 30s` for the future windows (bbox-first range reads, ~620 MB per period); the current-period archive at 30 arc-sec remains impractical here. Because current and future must share a resolution, the analysis uses 2.5 arc-min throughout.

## Predictors

Eleven Bioclim variables, all from the same source and period structure: bio01 (mean annual temperature), bio02 (mean diurnal range), bio04 (temperature seasonality), bio05 (max temperature of the warmest month), bio06 (min temperature of the coldest month), bio12 (annual precipitation), bio13 (wettest month), bio14 (driest month), bio15 (precipitation seasonality), bio16 (wettest quarter), bio17 (driest quarter). Kept to the standard Bioclim set rather than expanded, to limit overfitting given the small presence counts.

## Occurrence and background

Presences are atlas records inside the basin, **thinned to one per 5 km cell**. A taxon is modelled only if it has **≥10 occupied cells** after thinning. Background is a fixed random sample of 10,000 in-basin cells (seed 42), excluding the taxon's own presences.

## Algorithms and ensemble

- **MaxEnt** — `elapid.MaxentModel` (L1-regularised maximum entropy; the maxnet method), features linear + quadratic.
- **Envelope** — `elapid.NicheEnvelopeModel` (BIOCLIM-type percentile envelope), an independent presence-background method.

Both are fitted on the same presences/background. Because the envelope returns a coarse 3-level score while MaxEnt returns a smooth probability, the two are **rank-transformed to a common percentile scale before averaging**; averaging raw scores would flatten the ranking and destroy discrimination. Reported AUC and TSS are those of this rank-ensemble.

## Validation: spatially blocked

Cells are partitioned into **5 spatial blocks by k-means on their Albers coordinates**; each block is held out once, so test presences are spatially separated from training presences. **Random k-fold is not used** for any reported performance metric. AUC and TSS are computed per fold and averaged; folds with no test presence or fewer than 20 test background cells are skipped (recorded as `n_folds`).

## Thresholds and area

Thresholds are the cross-validated max-TSS thresholds on each model's own probability scale (averaged over folds). A cell is suitable when **both** models exceed their thresholds (consensus). Suitable area is the count of suitable 5 km cells × 25 km². Projected change is `(future − current) / current × 100` per scenario, with the **same thresholds** applied to current and future so the areas are comparable.

Vulnerability tiers: high loss (< −50%), moderate loss (−50 to −20%), stable (±20%), gain (> +20%), not assessed.

## Results (2026-11-26 run)

| | Count |
|---|---|
| Taxa modelled (≥10 occupied cells) | **162** |
| Not assessed — 1–9 occupied cells | **119** |
| Not assessed — no in-basin records | **52** |
| Low-confidence models (AUC<0.7 or TSS<0.4) | 139 of 162 |
| Mean AUC / mean TSS | 0.57 / 0.36 |
| SSP5-8.5 2041–2060 tiers | 3 high loss · 29 moderate loss · 86 stable · 44 gain |

**Note on the taxon split.** Counting *records*, 195 taxa have ≥10 in-basin records and 138 do not (86 with 1–9 records, 52 with none). After thinning to one record per 5 km cell, which is the unit the model actually uses, 162 taxa retain ≥10 occupied cells and 171 are not assessed. Both figures are reported; the cell-based split governs the modelling.

The modest mean AUC is a genuine data limitation, not a computational artefact: many taxa have 10–30 occupied cells, and widespread taxa (e.g. *Achyranthes aspera*) have no climatically distinct envelope, so AUC near 0.5 is expected. For taxa with well-sampled, narrow ranges the ensemble performs as intended (e.g. *Albizia lebbeck* AUC 0.90).

## Sensitivity analysis with EM-Earth

Not yet run: EM-Earth remains unavailable. When it is reachable, the same script runs with EM-Earth predictors and both result sets are reported side by side; the WorldClim results remain primary unless EM-Earth materially changes a tier assignment.

## Reproduce

```bash
python scripts/sustainability/fetch_worldclim.py --res 2.5m
python scripts/sustainability/build_env_stack.py
python scripts/sustainability/sdm.py
```

Software: Python 3.14.7, elapid 1.0.4, scikit-learn 1.9.1, scipy, rasterio 1.5.2 / GDAL 3.12.2.
