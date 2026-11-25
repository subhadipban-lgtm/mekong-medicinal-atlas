# Sources requiring manual access or user action

These cannot be pulled programmatically from this environment. Ordered by value.

| # | Source | What's needed | Why it matters |
|---|---|---|---|
| 1 | **Lancang-Mekong Traditional Medicine Resources Database** (lmsjk.ynutcm.edu.cn) | Browser session; possibly registration. No public API documented. | Tier-1 taxonomic + chemical + pharmacological coverage for the basin; would fill local names (zh/lo/km/th/vi/my) and TCM-usage fields we currently lack entirely. |
| 2 | **Nguyễn Văn Dương — Medicinal Plants of Vietnam, Cambodia, and Laos (1993)** | Print or library scan; copyright. | Backbone for Vietnamese/Khmer/Lao vernacular names and habitat notes. |
| 3 | **Nguyễn Minh Khôi — Atlas of Medicinal Plants in Vietnam / Atlas cây thuốc Việt Nam (2022)** | Print or library scan; copyright. | Modern Vietnamese monographs + photographs; would anchor the `local_names_json` `vi` field. |
| 4 | **Thorel — Agriculture and Ethnobotany of the Mekong Basin (1866–68)** | Archive.org / Bibliothèque nationale de France scan; public domain. | Historical baseline; also the only source for some pre-1900 vernacular names. |
| 5 | **IUCN Red List API** | Free API token (register at api.iucnredlist.org) | Would let us verify all 16 trade-flagged species + fill `iucn_status` for the rest programmatically instead of workbook-only. |
| 6 | **GBIF download key (DOI-citable occurrence download)** | Free GBIF account → request download of predicate `country IN (TH,LA,VN,KH,MM,CN) AND taxon in backbone of 333 keys` | Replaces the rate-limited sample with a full, DOI-citable occurrence set. ~222k records expected. |
| 7 | **Mekong River Commission basin boundary polygon** (MRC / GMS Atlas of the Environment, ADB/UNEP) | Shapefile/GeoJSON download from MRC or ADB | Required to turn `basin_intersection_flag` from `country_only` into a true polygon intersection for the ~222k occurrences. |
| 8 | **National Red Data Books** — Laos (2008), Cambodia (2008/2021), Myanmar (2012), Vietnam (2007), Thailand (2018) | Print/PDF per country | National protection status for species not yet flagged (e.g. *Coscinium fenestratum* is reported as "critically endangered" in specialist literature but not in our workbook). |
| 9 | **National pharmacopoeias** — Vietnam, China, Thailand, Laos, Cambodia, Myanmar | Print/institutional access | QC marker compounds and official monographs for the QC layer (currently empty). |
| 10 | **POWO / WFO web portals** | Manual spot-check of ~30 flagged names | API blocked (Cloudflare). WFO backbone used instead; POWO would give independent confirmation for the 9 manually-resolved GBIF names. |
| 11 | **Ethnobotanical field surveys** (Khmer/Lao/Thai/Vietnamese-language papers) | Scopus/Web of Science or library access | Would populate `ethnic_group` in uses.csv — currently blank throughout. |

## What we did **not** do (and why)

- Did **not** scrape any paywalled publisher site or use Sci-Hub/proxies.
- Did **not** treat GBIF occurrence density as a proxy for "medicinal importance" — occurrence ≠ use.
- Did **not** infer pharmacology from phylogeny. Every activity claim traces to an assay row in the workbook, which itself traces to a cited paper.
