# Inventory — Zenodo record 7803254 (sustainability source data)

**Record:** Tiwari, A.D., Pokhrel, Y., Kramer, D., Akhter, T., Tang, Q., Liu, J. (2023). A synthesis of hydroclimatic, ecological, and socioeconomic data for transdisciplinary research in the Mekong. *Scientific Data* 10:283, https://doi.org/10.1038/s41597-023-02193-0 · Zenodo https://doi.org/10.5281/zenodo.7803254 · CC-BY-4.0 · published 2023-01-20.

*Correction to the task brief:* the paper is Tiwari et al. 2023, not Gumbricht et al. — Gumbricht is the upstream source of the wetlands layer (CIFOR 2017). The record DOI given in the brief (10.5281/zenodo.7803254) is correct.

**Storage:** raw archives live on `/Volumes/Expansion/mekong_sustainability/data/raw/zenodo7803254/` (21 GB does not fit the Drive-backed repository and must not sync to Google Drive). The manifest is `data/raw/zenodo7803254_manifest.csv`; checksums are verified after download. Raw files are never modified.

| Archive | Size | Contents | Variable / units | Resolution | CRS | Nodata | Temporal | Upstream source |
|---|---|---|---|---|---|---|---|---|
| Dams.zip | 0.05 MB | `MekongDams_Tiwari_SDATA.xlsx` (486 dams) | dam attributes: function, status, year, total storage (FSL), height, installed capacity; lat/lon | point (lat/lon columns) | WGS84 (assumed) | n/a | construction years through 2019 | WLE / CGIAR Greater Mekong Dams Observatory |
| Streamflow.zip | 0.81 MB | 30 gauge txt series | discharge m³/s | point | n/a | n/a | variable per gauge | Mohammed 2018; Zhang 2020; Tang 2015 |
| GHG.zip | 0.98 MB | GHG_Emissions.txt | GHG emissions, annual per cell | grid (lat/lon rows) | WGS84 | n/a | annual | EDGAR, Crippa et al. 2019 |
| Groundwater.zip | 0.25 MB | borehole txt series | groundwater depth | point (delta boreholes) | n/a | n/a | variable | Duy 2021; Erban 2016; Fryar 2021 |
| IrrigatedArea.zip | 0.11 MB | gmia_v5_aei_pct.tif, gmia_v5_aei_ha.tif | % area equipped for irrigation; hectares per cell | 5 arc-min (0.0833°) | EPSG:4326 | -3.4e38 | v5 (2005 ref.) | FAO GMIA v5 |
| CropYield.zip | 0.65 MB | FAOSTAT xls ×4 countries | crop yield | admin country | n/a | n/a | series | FAOSTAT (2022-12-26) |
| CropCalendar.zip | 2.93 MB | GEOGLAM shapefile | crop calendars (sowing/harvest windows) | vector | per .prj | n/a | v1.0 | GEOGLAM EW Calendars |
| Wetlands.zip | 2.73 MB | CIFOR wetland raster + Tootchi 2019 | wetland extent class | 0.0011° (~120 m) | EPSG:4326 | -128 (int8) | 2016 (CIFOR) | CIFOR Gumbricht 2017; Tootchi 2019 (PANGAEA) |
| SocioEconomic.zip | 13.0 MB | GDP rasters, GPW population rasters, SSP projection txt | GDP PPP 2011 Int$; population counts; SSP1–5 population & GDP | 30 arc-sec (GDP, GPW); 1/8° (projections) | EPSG:4326 | -3.4e38 (float32) | 1990–2015 GDP; 2000–2020 GPW; 2000–2100 projections | Kummu 2020; GPW v4 (SEDAC); Jones & O'Neill (SEDAC) |
| _SupplementalData.zip | 1.97 MB | Mekong_DEM.tif; basin boundary shapefile | elevation m | 30 arc-sec | EPSG:4326 | -32768 (int16) | static | SRTM |
| Inundation.zip | <0.01 MB | ReadMe only | — **access pending** | — | — | — | — | GIEMS d15 v1.0 (upstream) |
| LULC.zip *(companion record 7622998)* | 55.3 MB | annual land-cover maps | ESA CCI land-cover classes (categorical) | 300 m | EPSG:4326 | per-class | 1992–2015 (CCI v2.0.7); 2016–2020 (C3S v2.1.1) | ESA CCI / C3S |
| SurfaceWater.zip | 4767 MB | *pending inspection* | surface water extent | — | — | — | — | — |
| EM_Earth_Temperature.zip | 7334 MB | *pending inspection* | temperature, historical + projected | — | — | — | — | EM-Earth |
| EM_Earth_Precipitation.zip | 4079 MB | *pending inspection* | precipitation, historical + projected | — | — | — | — | EM-Earth |
| ET.zip | 2631 MB | *pending inspection* | evapotranspiration | — | — | — | — | GLEAM |
| SoilMoiture.zip | 2199 MB | *pending inspection* | soil moisture | — | — | — | — | GLEAM |

**Gaps against the brief's checklist**
- *Groundwater* is point time series (delta boreholes), not a continuous grid → the water-availability index can use it only as a regional qualifier, not a gridded term.
- *Inundation* archive contains only a ReadMe → access pending (GIEMS d15 v1.0).
- *Country administrative boundaries* are not in the record → the atlas already uses Natural Earth (public domain); noted for completeness.
- *LULC* is not in record 7803254 → fetched from the companion record 7622998 (same authors, same paper, CC-BY-4.0); provenance recorded.

The five large archives are downloaded with resume (`curl -C -`) in the background and their rows will be filled in when inspection completes. Checksums (md5 from the record) are re-verified after download.
