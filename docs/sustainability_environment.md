# Sustainability-layer environment (harvest pressure & hydrological risk)

Pinned environment for the harvest-pressure and hydrological-fragmentation layers
(`scripts/sustainability/`).

- **Interpreter**: Python 3.14.7 (the same pinned interpreter as the rest of the atlas build).
- **Packages**: numpy, rasterio, shapely, pyproj (geospatial stack); see the Methods page's
  software table for the exact versions recorded at build time.
- **Inputs**:
  - 5 km Albers equal-area grid: built by `scripts/sustainability/build_grid.py`
    (31,922 in-basin cells).
  - Population projection (SSP2 2050, SEDAC) and the dam registry: Tiwari et al., Zenodo
    `10.5281/zenodo.7803254` (CC-BY-4.0); the raw archives live outside the repository
    (`/Volumes/Expansion/mekong_sustainability/…`) and are never committed.
  - WorldClim 2.1 (2.5 arc-min) was substituted for the EM-Earth layers when the external
    drive disconnected mid-download; the substitution is documented in `docs/sdm_methods.md`
    and `docs/cultivation_methods.md`.
- **Outputs**: `data/processed/harvest_pressure_summary.csv`,
  `data/processed/hydrological_fragmentation.csv`, the per-cell rasters and the web map layers.
  Methods: `docs/harvest_pressure_methods.md`, `docs/hydrological_methods.md`.
- **Reproduce**: `scripts/sustainability/run_sustainability.sh` (requires the Zenodo 7803254
  archives and the WorldClim substitution noted above).
