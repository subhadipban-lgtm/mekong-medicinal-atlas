# Data paper — DRAFT (version 0.1, 2026-11-25)

**Title (working):** A species-level, evidence-graded, and macroecologically
contextualized atlas of Mekong Basin medicinal plants: extending the Shrestha
et al. global framework to sub-national resolution with a linked
pharmacological evidence base

**Authors:** Subhadip Banerjee (Mae Fah Luang University, Thailand; project
lead) — *author list, order, affiliations to be confirmed.*

**Abstract.** We present the Mekong Medicinal Plant Atlas, a versioned,
source-cited regional data product covering 333 medicinal plant taxa of the
six Mekong basin countries, with (1) evidence-graded ethnobotanical and
pharmacological records, (2) a pilot evidence engine mapping 2,317
publications (20 taxa), 119 compounds (103 with PubChem structures) and a
living-review pipeline, and (3) a macroecological layer that reproduces the
Shrestha et al. 2025 global residual analysis of medicinal plant diversity
on the authors' published data and extends it to sub-national (province)
scale. All seven botanical countries containing the basin exceed their
vascular-diversity expectation (residuals +994 to +2,195 medicinal species;
six of seven significant at p < 0.05); the extension to ~250 provinces
identifies internal coldspots — provinces with significantly negative
residuals in long-occupied areas — as fieldwork priorities. The atlas is a
static site (no backend) with a JSON integration contract and per-species
pages that interlink global taxonomy (WCVP), occurrence evidence (GBIF),
literature evidence and macroecological context.

---

## 1. Background & Summary

[Draft: Mekong = steepest realm slope context, documentation gaps, Cambodia
under-documentation hypothesis, what the atlas adds over the global paper.]

## 2. Methods

### 2.1 Study extent and taxonomic scope
333 taxa from the basin workbook spine; join key `species_id`; one genus-level
alga flagged as such.

### 2.2 Data sources and acquisition
- Species spine + evidence records: project workbook (per-row citations);
  re-graded by the atlas grading pipeline.
- Occurrences: GBIF occurrence API (open-licensed, DOI-citable download to
  replace the API snapshot at release).
- Taxonomy: GBIF backbone + World Flora Online; **WCVP** (sftp.kew.org,
  retrieved 2026-11-25) for the macroecological backbone — 332/333 atlas
  taxa match (295 exact accepted, 37 via synonym, 1 spelling variant; 1
  genus-level alga unmatched).
- Medicinal/vascular country data: Shrestha et al. 2025 repository
  (`nawalshrestha/med_plants`, data.csv) reused with commit hash recorded;
  Zenodo 10.5281/zenodo.14765689 (CC-BY-4.0).
- Human occupancy: reused from the Shrestha dataset at its published
  (botanical-country) resolution — not re-derived.
- Language points: Glottolog (Zenodo 24104033).
- Boundaries: WGSRPD level-3 (tdwg/wgsrpd), Natural Earth 10m admin-1
  (public domain).
- MPNS v12: **access pending** (mpns.science.kew.org unavailable 2026-11-25);
  MPNS-derived country values come via the Shrestha dataset.

### 2.3 Evidence grading rubric
A-D grades per row with best-grade propagation; grade A requires confirmed
DOI/PMID/Crossref resolution. Machine classification (`auto-rubric-v1`) is
separated from evidence strength: 190 publication rows and 16 compound rows
await human review (review_queue.csv; 20-row double-review subsample for
Cohen's κ).

### 2.4 Literature search strategy and PRISMA log
Query template `(names) AND (medicinal OR ethnobotany OR phytochemistry OR
pharmacology OR "network pharmacology")`; names = accepted name + GBIF
synonyms (cleaned); chunked ≤4 names per query (EPMC parser limitation,
verified). Databases: Europe PMC (primary, full pagination), OpenAlex,
Crossref, DOAJ. Pending: Semantic Scholar (keyless 429), ThaiJo (per-journal
OAI), CNKI, Vietnam Journals Online (credentials). Every query logged
(query string, database, date, hits).

### 2.5 Evidence engine
Compounds: PubChem PUG REST (CID/InChIKey/SMILES), InChIKey join key,
`structure_status` flags. Target promotion (M2): two independent lines
(prediction in ≥2 engines, or prediction + literature support); every edge
carries `evidence_type`. Living review: weekly Cloud Run job (Europe PMC +
OpenAlex re-query, diff against baseline, `whats_new.json` feed); first
cycle recorded 2026-11-25.

### 2.6 Macroecological analysis
med_rich ~ vas_rich OLS over all botanical countries except Antarctica and
Oceania (authors' exclusion); significance |residual| > 1.96 SD (their
residual_histogram.R). Reproduction validated: our residuals correlate
r = 0.998 with the authors' published residuals column. Extension: same
model at admin-1 scale (GBIF vascular species counts per province vs atlas
documented medicinal taxa per province); differences documented; coldspot ×
occupancy cross-reference produces `priority_for_fieldwork` flags.

### 2.7 Coordinate generalization policy
[as on the Methods page: CR rounded 0.1°, EN/VU/CITES I-II 0.01°, locality
removed, uncertainty raised.]

### 2.8 Reproducibility
Pinned Python 3.14.7 environment; `build.sh` regenerates the site; every
analysis script is stdlib-only; inputs cached under `data/raw/` with
provenance READMEs; outputs date-partitioned in BigQuery
(`phyto-companion-prod.mekong_evidence`).

## 3. Data Records

[Table-by-table: species_master, uses, pharmacology, conservation_trade,
references, occurrences (DwC-A), evidence CSVs, macroecology CSVs, geo
layers, contract JSON — with field definitions referenced to
data_dictionary.md; DOIs to be minted at the first archived release.]

## 4. Technical Validation

- Taxonomic reconciliation: WCVP 332/333 (details above); WFO/GBIF backbone
  agreement 292/333 (41 differ, documented in wfo_reconciliation.md).
- Human review: queue of 206 rows; κ to be reported once the 20-row
  double-reviewed subsample is scored (pending owner review).
- Residual analysis diagnostics: r = 0.998 vs published residuals; Indomalaya
  slope 0.310 [0.261, 0.360] steepest of six realms (Australasia 0.106).
- Network pharmacology: evidence-type distribution to be reported at M2;
  ADMET/docking labelled as computational predictions.

## 5. Usage Notes

[How to cite individual species pages; how to reproduce the macroecological
analysis. The evidence-engine registers (publication corpus, compounds,
search logs, GMS deep-search) are restricted: aggregate summaries are
published on the atlas Evidence page, and the granular tables are shared
with reviewers on request. The atlas's own tables and occurrences remain
public via the Zenodo record.]

## 6. Code Availability

- Atlas: https://github.com/subhadipban-lgtm/mekong-medicinal-plant-atlas
- Evidence engine: **private repository** (restricted access); reviewers and
  collaborators receive read access from the authors on request. A
  restricted-access Zenodo DOI will be minted at the first engine release.
- Shrestha et al.: https://github.com/nawalshrestha/med_plants + Zenodo
  10.5281/zenodo.14765689
- Atlas Zenodo DOIs: version 10.5281/zenodo.24525569, concept
  10.5281/zenodo.24525568 (the atlas's own tables and occurrences; the
  evidence-engine registers are NOT included in the public deposit).

## 9. Limitations

- The pilot literature corpus (M1) was a citation-sorted slice; the full
  corpus build (EPMC full pagination + Crossref + DOAJ) replaces it;
  Semantic Scholar/ThaiJo/CNKI/VJO remain access pending.
- Machine-assigned evidence tiers: 206 rows pending human review.
- MPNS coverage bias is documented by Shrestha et al.; our MPNS membership
  checks are pending the MPNS v12 service.
- Internal coldspots use GBIF stateProvince as the admin-1 unit; province
  names are messy and variants were normalized conservatively.
- Human occupancy is country-level (as published); province-level
  cross-reference inherits the country value.
- Coordinates of threatened taxa are generalized.
- **Access**: the evidence-engine code and registers are restricted (private
  repository; granular tables available from the authors on request); only
  build-time aggregate summaries are published on the atlas site.
