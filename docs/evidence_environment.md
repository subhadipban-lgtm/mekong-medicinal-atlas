# Evidence-engine environment

The evidence-engine layer (publication search, compound resolution, contract JSONs) runs in a
separate private repository (`mekong-evidence-engine`) and on a GCP schedule. This document pins
what the atlas needs to know about that environment; it does not expose engine code or inputs.

- **Engine interpreter/runtime**: Python 3.14 (engine services run under Docker on GCP
  Cloud Run; the docker image pins Python 3.14).
- **Key dependencies**: Europe PMC REST API, Crossref, OpenAlex, PubChem PUG REST — all public
  HTTP APIs; no keys are stored in the atlas repository.
- **Restricted inputs**: `data/evidence/**` (publications.csv, species_compound.csv,
  search_log.csv, contract/*.json, prisma_flow.json) are gitignored and never committed or
  published. The committed public artefact is the numbers-only
  `data/processed/evidence_manifest.json`, plus the structure-only
  `data/evidence_manifest.json` (schema names, row counts, SHA-256, licence, access status —
  no identifiers).
- **Contract publication (2026-11-26 policy)**: the aggregate contract files under
  `data/evidence/contract/` (publication identifiers, tier counts, network summary counts,
  status stubs — no abstracts, titles or full text) are committed in the public repository.
  The website serves no `/data/evidence/` endpoint (anonymous requests return 404).
  `species_publications.json` is excluded from future syncs by
  `scripts/sync_evidence_contract.py`, and the scheduled contract sync is disabled
  (`.github/workflows/sync-evidence.yml` runs on `workflow_dispatch` only).
- **Restricted inputs**: `data/evidence/` beyond `contract/` (publications.csv with titles and
  abstracts, species_compound.csv, search logs) stays gitignored and unpublished.
- **Access requests**: open an issue at
  https://github.com/subhadipban-lgtm/mekong-medicinal-plant-atlas/issues quoting the endpoint
  name and its SHA-256 from `data/evidence_manifest.json`.
