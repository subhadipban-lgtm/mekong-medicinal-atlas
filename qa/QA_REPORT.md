# QA Report — Mekong Medicinal Atlas (2026-11-24)

## 0. Public-build scope (2026-11-24)

This public build excludes: (a) point-level occurrence records (the 13,399-row sample was rate-limited and alphabet-biased; only country-level `occurrence/count` totals are published), and (b) any MFU lab-worksheet material, which is internal to Mae Fah Luang University and is not redistributed. Everything below describes the full local dataset unless marked otherwise.

## 1. Taxonomy

| Check | Result |
|---|---|
| Names submitted to GBIF backbone | 333 (100% of spine) |
| GBIF EXACT match | 323 (97.0%) |
| GBIF FUZZY | 1 (`euphoria longana` → *Dimocarpus longan*, conf 99) |
| Manual resolutions | 9 — all logged in `data/raw/gbif_match_raw.json` with `matchType=MANUAL` |
| Mean GBIF confidence | 98.1 |
| Genus-level entries not forced to species | 2 (`Aglaia`, `Erythrina`) — flagged, not silently upgraded |
| WFO backbone match | **pending** — see `docs/wfo_reconciliation.md` |

### Manual GBIF resolutions (all need POWO spot-check)
| Workbook name | GBIF accepted | Note |
|---|---|---|
| `euphoria longana` | *Dimocarpus longan* Lour. | synonym |
| `hedyotis diffusa` | *Scleromitrion diffusum* (Willd.) R.J.Wang | GBIF backbone accepts this; POWO may differ |
| `holarrhena antidysenterica` | *Holarrhena pubescens* (Buch.-Ham.) Wall. ex G.Don | synonym |
| `polygonum chinense` | *Persicaria chinensis* (L.) H.Gross | synonym |
| `scoparia dulcis` | *Scoparia dulcis* L. | multiple GBIF copies; first accepted used |
| `solanum indicum` | *Solanum indicum* L. | GBIF lists as synonym; treated as accepted here — **needs POWO check** |
| `strychnos nux` | *Strychnos nux-vomica* L. | truncated epithet in workbook |
| `aglaia` | *Aglaia* Lour. (genus) | workbook entry is genus-level |
| `erythrina` | *Erythrina* L. (genus) | workbook entry is genus-level |

## 2. Occurrences

| Check | Result |
|---|---|
| Point-level sample | 13,399 (withheld from public repo) |
| Unique species with ≥1 occurrence | 303 / 333 |
| GBIF occurrence counts (all 333 species × 6 countries) | 222,280 total |
| Zero-island (0,0) coordinates | 79 / 13,399 (0.6%) — flagged and excluded |
| Out-of-range lat/lon | 0 |
| Missing license | 0 (all rows carry GBIF per-record license) |
| Countries (sample) | CN 4,285 · TH 4,047 · VN 2,232 · LA 1,034 · KH 992 · MM 809 |
| 429 rate-limit losses during sampling | ~40% of species×country cells — **sample is biased toward early-alphabet species** |

**Action required:** request a GBIF download DOI to replace the sample with the full, citable occurrence set. The sample is adequate for mapping density but not for absence inference.

## 3. Ethnobotany / pharmacology

| Check | Result |
|---|---|
| Use records | 207 across 205 species |
| Uncategorised uses | 38 (`other`) — need manual categorisation |
| `ethnic_group` populated | **0 / 207** — not in workbook; requires Tier-2 literature |
| Preparation / administration | not populated — workbook does not carry these fields |
| Pharmacology rows | 690 (290 extract assays + 400 isolated compounds) |
| Potency with numeric value + unit | 105 / 290 extract rows (36%) |
| Evidence grade | all A (inherited from workbook Tier 2/3, which cite primary literature) |

## 4. Conservation

16 species carry trade/threat flags from the workbook. **None of these were verified against a live IUCN API** (token not available). Values are reproduced from `6_Trade_CITES` and flagged for spot-check. Notably:

- *Panax vietnamensis* — EN (Vietnam Red Book) but **not CITES-listed** (only P. ginseng and P. quinquefolius are Appendix II).
- *Eurycoma longifolia* — assessed LC despite heavy illegal harvest; the LC status does not reflect pressure.
- *Coscinium fenestratum* — reported critically endangered in specialist literature, **not** CITES-listed; workbook does not flag it.
- *Aquilaria crassna*, *Dalbergia cochinchinensis* — CITES Appendix II.

## 5. Structural checks

- `species_id` is stable (slug of accepted name) and unique — 333/333 unique.
- Referential integrity: every `species_id` in `uses.csv`, `pharmacology.csv`, `conservation_trade.csv` resolves to `species_master.csv` — verified programmatically, 0 orphans.
- No duplicate `use_id` / `pharma_id` / `conservation_id`.

## 6. What is missing or unverified

1. **Basin polygon intersection** — `basin_intersection_flag` = `country_only` everywhere. Requires MRC/GMS boundary shapefile.
2. **Local names** — empty everywhere. Requires Tier-2 books.
3. **Ethnic groups** — empty. Requires Tier-2/3 literature.
4. **WFO reconciliation** — pending; GBIF used as backbone in the interim.
5. **IUCN/CITES live verification** — pending token.
6. **Full GBIF download** — pending user GBIF account action.
7. **QC/pharmacopoeia layer** — empty; requires national pharmacopoeias.
8. **Genomics layer** — not attempted; NCBI probe found hits for ~18 taxa but assemblies were not fetched.

## 7. Verdict

**Usable as a research scaffold now.** Not yet a citable atlas: the taxonomy needs WFO sign-off, the occurrence layer needs a DOI-backed full download, and local names need the Tier-2 books. None of these require new science — they require access.

---

## Addendum — WFO reconciliation and conservation rows (2026-11-24, later)

### WFO World Flora Online match (Kindt 2020, `WorldFlora` R package v1.14.5)

Backbone: static WFO snapshot downloaded 2026-11-24 from `files.worldfloraonline.org` (`classification.csv`, 1,657,866 rows; 453,167 accepted names). Match: `WFO.match(Fuzzy = 0.1)`.

| Result | Count |
|---|---|
| Names with ≥1 WFO row returned | 333 / 333 |
| Names with an **Accepted** WFO name | 329 / 333 |
| GBIF vs WFO agree (genus+epithet) | 292 |
| GBIF vs WFO differ | 41 |
| No WFO accepted match | 4 (`aglaia`, `erythrina` — genus-level; `sargassum` — genus-level; `curcuma xanthorrhiza` — recorded only as *Curcuma xanthorrhiza* D.Dietr., Unchecked, and the accepted *C. zanthorrhiza* Roxb. not matched by fuzzy 0.1) |

Full disagreement table: `docs/wfo_reconciliation.md`. Policy: GBIF remains the operational backbone (it drives occurrence keys); WFO accepted name is surfaced alongside as `wfo_accepted_name` in `species_master.csv`. Neither is presented as sole truth. 41 disagreements are mostly post-2020 generic recircumscriptions that WFO adopted (e.g. *Caesalpinia* → *Biancaea*, *Costus speciosus* → *Hellenia speciosa*, *Desmodium triquetrum* → *Tadehagi triquetrum*) — both names remain searchable.

### Conservation table (`conservation_trade.csv`)

Five of the 16 workbook trade rows are **not** spine species — they are genus-level aggregates or non-basin taxa kept for intelligence value. They are now flagged `in_spine=no` with a `scope_flag` explaining why, instead of being silently dropped or silently joined. The remaining 11 carry `in_spine=yes` and join to `species_master` on `species_id`.

| species_id | scope_flag |
|---|---|
| `sp_nardostachys_jatamansi` | not in 333-taxon spine |
| `sp_picrorhiza` | genus-level, not in spine |
| `sp_aquilaria_plantations` | aggregate row, not a taxon |
| `sp_vietnamese_medicinal` | aggregate row, not a taxon |
| `sp_dalbergia` | genus-level, not in spine |

### Occurrence sampling bias

~40% of species×country cells returned HTTP 429 from GBIF during sampling, so the 13,399-point sample is biased toward early-alphabet species and toward whatever GBIF served before limiting kicked in. **Do not use the sample for absence inference or density estimation.** Country-level occurrence totals in `species_master.csv` come from `occurrence/count` (not rate-limited in the same way) and are the reliable per-country figures (222,280 total).

### What a reviewer should check first
1. `docs/wfo_reconciliation.md` — 41 GBIF/WFO disagreements.
2. `species_master.csv` → `best_name` column (WFO-preferred display name) vs `accepted_name` (GBIF).
3. `data/raw/wfo_match.csv` — raw WFO output, unedited.
4. `sources/SOURCES_REQUIRING_MANUAL_ACCESS.md` — what is missing and why.



