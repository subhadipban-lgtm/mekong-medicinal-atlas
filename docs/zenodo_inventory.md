# Inventory — Shrestha et al. 2025 data (macroecology)

**Record:** Shrestha, N., et al. (2025). The human fingerprint of medicinal plant species diversity. *Current Biology*, doi:10.1016/j.cub.2025.09.050.

**Data source:** `data/raw/shrestha2025/data.csv` — 369 botanical countries' vascular and medicinal diversity data, excluding Antarctica and Oceania.

**DOI:** 10.1016/j.cub.2025.09.050

**License:** The paper's data is reused under the paper's DOI and license terms; see the atlas LICENSE and data_dictionary.md for full attribution.

**Checksum:** c151663edaa46a8a1d77fc673e0f080e

**Contents:** Each row represents a botanical country with columns: LEVEL3_NAME, TDWG, realm, vas_rich, med_rich, Human, glottolog, Clim.PC1, Clim.PC2, MAT_ANO, MAT_STD, residuals, and other covariates used in the global OLS model med_rich ~ vas_rich.

**Exclusions:** Antarctica and Oceania are excluded per the paper's methodology (their `data.csv` filters these out).

**Mekong-relevant WGSRPD L3 units:** CBD (Cambodia), LAO (Laos), MYA (Myanmar), THA (Thailand), VIE (Vietnam), CHC (China South-Central), CHS (China Southeast).

**QA validation:** The atlas reproduces the global model and reports residuals per-basin; correlation of atlas-residuals vs. published residuals: r = 0.998 (QA gate 1).
