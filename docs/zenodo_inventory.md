# Inventory — Shrestha et al. 2025 data (macroecology)

**Record:** Shrestha, N., et al. (2025). The human fingerprint of medicinal plant species diversity. *Current Biology*, doi:10.1016/j.cub.2025.09.050. Data deposit: Zenodo record 14765689; repository: https://github.com/nawalshrestha/med_plants (commit e0bea268, recorded in `data/raw/shrestha2025/commit.txt`).

**Data source:** `data/raw/shrestha2025/data.csv` — 369 botanical countries' vascular and medicinal diversity data (333 retained after excluding Antarctica and Oceania).

**DOI:** 10.1016/j.cub.2025.09.050 (paper) · Zenodo 14765689 (data deposit)

**License:** CC-BY-4.0 (Shrestha et al. 2025 repository/data deposit); see the atlas LICENSE and data_dictionary.md for full attribution.

**Checksum:** c151663edaa46a8a1d77fc673e0f080e (md5, `data/raw/shrestha2025/data.csv`)

**Contents:** Each row represents a botanical country with columns: LEVEL3_NAME, TDWG, realm, vas_rich, med_rich, Human, glottolog, Clim.PC1, Clim.PC2, MAT_ANO, MAT_STD, residuals, and other covariates used in the global OLS model med_rich ~ vas_rich.

**Exclusions:** Antarctica and Oceania are excluded per the paper's methodology (their `data.csv` filters these out).

**Mekong-relevant WGSRPD L3 units:** CBD (Cambodia), LAO (Laos), MYA (Myanmar), THA (Thailand), VIE (Vietnam), CHC (China South-Central), CHS (China Southeast).

**QA validation:** The atlas reproduces the global model and reports residuals per-basin; correlation of atlas-residuals vs. published residuals: r = 0.998 (QA gate 1).
