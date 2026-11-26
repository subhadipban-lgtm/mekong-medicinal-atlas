# Bioeconomy / Data catalog release — milestone summaries

Branch: `bioeconomy/data-catalog`. All milestones below reflect the state at each commit on
that branch; QA gates 1–14 all pass at the final state.

## Milestone 1 — Bioeconomy extraction (complete)

- `data/processed/bioeconomy_profiles.csv` — one row per atlas taxon (333), full schema; every
  coded field is `unknown`, `bioeconomy_profile_available = False` for all taxa.
- `data/processed/bioeconomy_priority_summary.csv` — tier counts (high 0 / medium 0 / low 0 /
  unknown 333) and per-tier species lists.
- `data/processed/bioeconomy_priority_cells.geojson` — grid-cell counts of high-priority taxa
  (an empty FeatureCollection in this release).
- `data/dictionary_bioeconomy.csv` — every field, type, definition, allowed values, source
  requirement.
- `docs/bioeconomy_sources.csv` — BIOSRC-001..012 register with retrieval dates and licences.
- `docs/bioeconomy_priority_rule.md` — the documented tier derivation.
- `species_master.csv` gained `bioeconomy_profile_available`, `bioeconomy_priority_tier`,
  `bioeconomy_source_ids`; `scripts/schema.py` validates the new fields and the two new tables.

**Key finding (not a defect):** per the narrowed coding scope (only taxa covered by the Cao Bang
Geopark jiaogulan study, PLOS ONE 10.1371/journal.pone.0324746, and the Naban River Watershed
study, ERA 10.32859/ERA.19.21.1-12), **zero of the 333 atlas taxa are covered** — the studies
concern *Gynostemma pentaphyllum*, *Asparagus filicinus*, *A. subscandens*, *Paris polyphylla*,
*Stemona tuberosa* and *Tacca chantrieri*. The layer therefore reports `unknown` everywhere by
rule; no imputation, no pharmacology-corpus inference, no per-species valuation. Documented
CITES appendices (e.g. *Aquilaria crassna*, *Dalbergia cochinchinensis*) are recorded as
per-taxon note pointers for a later coding pass.

## Milestone 2 — Site integration (complete)

- Species pages: collapsible **Bioeconomy** section under the Sustainability section; every
  taxon renders the documented "No bioeconomy profile available for this taxon." line (the full
  table renderer is wired for when a profile exists).
- Explore map: **Bioeconomy priority** overlay toggle, off by default, lazily loads the cell
  layer, with a legend stating it is a count of taxa, not a value. Browser-verified.
- Homepage: stat card "0 taxa in the high-priority bioeconomy tier" (computed from the CSV),
  linking to the Data tab.
- Methods: "Bioeconomy extraction" subsection with sources, rules, derivation and the
  screening-layer limitation.

## Milestone 3 — Data tab (complete)

- `web/data.html` built by `build_site.py::data()`: Overview, dataset catalog (16 datasets from
  `zenodo_registry.csv`), live contract section (real status per endpoint, SHA-256, contact
  line), filterable data dictionary (union of `data/dictionary_*.csv`), per-dataset citations
  with BibTeX, provenance and reproducibility, contact and issues.
- Nav entry "Data" added after Methods on every page; "Download" removed.
- Build fails if a catalogued dataset has no registry row, no licence, no version, or an
  invalid DOI; "DOI pending — contact corresponding author" is the only permitted non-DOI.
- The manifest replaces the live-contract requirement:
  `data/evidence_manifest.json` records, per contract endpoint, schema names, row counts, byte
  size, SHA-256, licence and access status (restricted — request access / pending). No PMIDs,
  DOIs, titles or abstract text. The restricted contract files are not published.

## Milestone 4 — Download retirement (complete)

- `download.html` is a three-line redirect stub (meta refresh + canonical + message).
- `copy_downloads()` and the Download page builder are deleted; `web/data/tables/` and
  `web/data/dwca/` are removed from the site and the repository — datasets live on Zenodo only.
- Every generated page swept: no `download.html` references, no in-site `href` to a
  `.csv/.json/.geojson/.tif/.graphml/.sdf/.xml` file (build-time guard `scan_download_links`),
  and no "pending" wording outside the Data tab's DOI-pending context.
- Repaired two pre-existing defects found during the sweep: the species index and "Same species
  as" links pointed at the site root (broken because of the `<base href="../">`) — now
  `species/<slug>.html`; and the harvest-pressure page (`sustainability.html`) was dropped from
  the build on main while the homepage still linked it — the page is restored and nav-labelled
  "Harvest pressure & hydrological risk".

## Milestone 5 — Zenodo registry and QA (complete, pending only the actual Zenodo uploads)

- `data/processed/zenodo_registry.csv`: 16 datasets; the six deposited in v0.9.0 carry the real
  DOIs (10.5281/zenodo.24525569 / concept …568); the rest carry "DOI pending — contact
  corresponding author" with a stated deposit plan. No DOI is invented.
- `docs/zenodo_deposit_plan.md`: deposit order (raw → processed → contract manifest →
  bioeconomy) and the per-dataset metadata checklist; states what must NOT be deposited.
- `docs/evidence_environment.md`, `docs/sustainability_environment.md` written for the Data
  tab's provenance section.
- `docs/iScience_BIOECONOMY_DRAFT.md`: Methods / Results / Discussion / Limitations / Data
  Records sections ready to paste; every number traceable to the CSV or a saved query.
- QA gates 1–14 PASS (local). Live verification (HTTP 200 for every touched page and the
  redirect stub) runs after the merge.

**Blocked / requires the owner:**
1. Actual Zenodo uploads for the ten "DOI pending" datasets (needs the owner's Zenodo account);
   the registry is updated with minted DOIs afterwards.
2. A value-chain study that covers atlas taxa, to move any profile out of `unknown` — or the
   decision to add the six studied species (*Gynostemma pentaphyllum*, *Asparagus filicinus*,
   *A. subscandens*, *Paris polyphylla*, *Stemona tuberosa*, *Tacca chantrieri*) to the atlas so
   the layer can be populated (flagged in the iScience draft before any Results section).
3. Author confirmation of the "Charoensub" spelling before any v1.0.0 deposit.
