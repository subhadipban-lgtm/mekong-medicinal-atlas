# Zenodo deposit plan and checklist

The atlas releases under **concept DOI `10.5281/zenodo.24525568`** (current version DOI
`10.5281/zenodo.24525569`, v0.9.0, deposited 2026-11-25). `data/processed/zenodo_registry.csv`
is the machine-readable register the Data tab renders; every dataset listed there must appear
in a deposit or carry a "DOI pending" plan. No DOI is invented before a deposit exists.

## Deposit order for the next release (v1.0.0)

Deposit in this order, one record per group, each versioned under the concept DOI where it
already exists and created under a new concept DOI where it does not:

1. **Raw** (already on Zenodo, not re-deposited): Tiwari et al. `10.5281/zenodo.7622998`
   (basin boundary) and `10.5281/zenodo.7803254` (hydroclimatic/socioeconomic synthesis,
   5 km grid inputs); Shrestha et al. 2025 (source deposit for the macroecology reproduction).
   These stay external; the atlas cites them.
2. **Processed core** — species_master, uses, pharmacology, conservation_trade, references,
   occurrences_published + Darwin Core Archive, occurrence_summary_by_species: **already in
   v0.9.0**. v1.0.0 re-deposits the updated files as a new version of the same record
   (version DOI changes; concept DOI `10.5281/zenodo.24525568` unchanged).
3. **New processed tables** — bioeconomy_profiles, bioeconomy_priority_summary,
   sustainability_harvest_pressure, sustainability_hydrological_fragmentation,
   macroecology_residuals, macroecology_slope_comparison, evidence_grade_provenance:
   new v1.0.0 deposit (new concept DOI, or attached to the atlas concept DOI as an additional
   record — decide before uploading; the registry is updated with the minted DOI after upload).
4. **Contract manifest** — `data/evidence_manifest.json` (structure, counts and hashes only):
   deposit with the v1.0.0 tables. The contract endpoints it describes stay restricted and are
   never uploaded.
5. **Bioeconomy documentation** — `docs/bioeconomy_sources.csv`,
   `docs/bioeconomy_priority_rule.md`, `data/dictionary_bioeconomy.csv`: attach to the
   bioeconomy deposit as readme/dictionary files.

## Per-dataset metadata to include (checklist)

- **Title**: "Mekong Medicinal Plant Atlas: <dataset name> (version <v>)"
- **Authors**: Banerjee, Subhadip; Charoensub, Rawiwan — Medicinal Plant Innovation Centre,
  Mae Fah Luang University, Chiang Rai, Thailand 57100
- **Description**: the description column of `zenodo_registry.csv`
- **Keywords**: Mekong; medicinal plants; <dataset keywords>; atlas; bioeconomy (where relevant)
- **Related identifiers**: GitHub repository (isSupplementTo);
  Tiwari et al. `10.5281/zenodo.7622998` (references); `10.1002/aps3.11388` (references);
  for bioeconomy: `10.1371/journal.pone.0324746` and `10.32859/ERA.19.21.1-12` (references)
- **Licence**: CC-BY-4.0 for compiled tables; CC-BY-NC-4.0 for the occurrence compilation
  (each record keeps its own licence)
- **Version**: 1.0.0

## What must NOT be deposited

- `data/evidence/` beyond `contract/` (publications.csv with titles and abstracts,
  species_compound.csv, search logs) — restricted; access on request only.
- `data/evidence/contract/species_publications.json` (publication identifiers) — excluded
  from future contract syncs; deposit only the structure manifest `data/evidence_manifest.json`.
- The source workbook — not licensed for redistribution.
- Raw GBIF/WFO/WCVP downloads — link their DOIs instead of re-hosting.

## Registry maintenance rule

After any successful Zenodo upload, update `data/processed/zenodo_registry.csv` with the
minted version DOI and flip `deposit_status` to `deposited`. The build fails if a dataset on
the Data tab is missing from the registry, so a deposit can never be silently skipped.
