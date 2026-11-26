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
- **Live endpoints**: the contract JSON is served from `/data/evidence/` only where an endpoint
  is genuinely public. In this release all contract endpoints are restricted: an anonymous
  request returns 404, and access is by request to the corresponding author
  (see the Data tab, section 3).
- **Access requests**: open an issue at
  https://github.com/subhadipban-lgtm/mekong-medicinal-plant-atlas/issues quoting the endpoint
  name and its SHA-256 from `data/evidence_manifest.json`.
