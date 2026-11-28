# Local database inventory — verified 2026-11-27

Scan scope: the project team's local and cloud storage copies. Name patterns covered the
requested set (PSC-db, DrSC-db, Dr. Duke's, IMPPAT, COCONUT, BIAdb, NaturAr, TBACdb) plus the
chemistry databases already used by other projects. Sizes below are real file sizes.
Storage locations are kept in a private copy of this note and are not published.

## Present and usable — natural-product / phytochemistry corpora

| Database | Local copy | What | Size / rows | Licence |
|---|---|---|---|---|
| COCONUT 10-2024 | yes | zip of CSV | 188.3 MB | CC BY 4.0 |
| **COCONUT 10-2025 — preferred** | yes | raw CSV, 44 cols incl. `organisms`, `collections`, `dois`, `synonyms`, `cas` | 682.7 MB | CC BY 4.0 |
| COCONUT lite 08-2026 | yes (2 copies) | raw CSV, 40 cols | 576.9 MB | CC BY 4.0 |
| COCONUT lite 09-2026 | yes | zip | 199.1 MB | CC BY 4.0 |
| **IMPPAT 3.0** | yes (with SOURCE.md + MANIFEST.sha256) | 3 batch TSVs: Plant_Information, Chemical_Information, Phytochemical_Plant_Association | 4,155 plants / 18,315 phytochemicals / 196,221 associations | CC BY-NC-ND 4.0 |
| **LOTUS** | yes | `lotus_smiles.txt` structure dump | 276,517 structures | CC0 |
| **Dr. Duke's** | yes | 4 per-species chemical tables (A. paniculata, C. rotundus, T. bellirica, T. chebula) + raw HTML + `concentrations.csv` | 232 chemical rows, 85 with ppm values | US Gov work, public domain |
| NPAtlas | yes | TSV 34 cols / JSON | 36,455 rows; JSON 475.6 MB | CC0 (NPAtlas) |
| CMNPD 1.0 | yes | table / activity table | 31,562 compounds; 13,163 activity rows | see NAR paper |
| GNPS libraries | yes | 4 JSON libraries (main, NIH NP, NIH NP round 2 pos/neg) | 589.7 / 58.0 / 86.0 / 9.2 MB | CC0 |

The COCONUT lite releases carry 40 columns: they keep every structure/physchem/NP-classifier field
but drop `organisms`, `collections`, `dois`, `synonyms`, `cas`, and add a surrogate `id`. Organism
attribution is what links a compound to a plant, so the lite dumps cannot support plant-compound
mapping. Use the 10-2025 full CSV.

## Present and usable — chemistry / reaction reference corpora

| Database | What | Rows | Status |
|---|---|---|---|
| ChEBI release 257 | full SDF dump `chebi.sdf.gz` | 199,902 entries, 146.3 MB gz | acquired |
| Rhea release 143 | TSV bundle | 19,005 directed reactions | acquired (TSV subset) |
| MetaNetX / MNXref | `reac_xref.tsv` + compound xref | 478,486 reactions, 80.8 MB | acquired |
| RetroRules 3.1.0 | metacore / envipath | — | BLOCKED (registration) |

## Requested but not held locally and not fetchable

| Database | Finding |
|---|---|
| PSC-db | no local files; host `www.psc-db.com` does not respond (HTTP 000) |
| DrSC-db | no files, no host resolved |
| NaturAr | no files; `natnar.com.ar` unreachable (HTTP 000) |
| TBACdb | no files found |
| BIAdb | no files; `bioinformatics.cimap.res.in/BIAdb/` unreachable (HTTP 000) |
| SuperNatural 3.0 | only a SOURCE.md placeholder held locally — BLOCKED, server connection-level failure |
| COCONUT full 08-2026 | the local copy is a 246-byte truncated placeholder, not a usable dump |

## Live-fetch status probed 2026-11-27

- `cb.imsc.res.in/imppat` → 200. Batch TSVs are at `/imppat/images/Batch_Download/*.tsv` (10 files incl. 2D/3D SDF, targets, bioactivities, formulations). This is the only one of the requested sources still openly downloadable.
- `phytochem.nal.usda.gov` → 200, per-plant CSV route `/plant-chemicals-csv-export/<id>?_format=csv`.
- `coconut.naturalproducts.net` → 200; the API is COCONUT 2.0 at `/api/molecules` and `/api/molecules/search` but both return `401 Unauthenticated`. Use the CSV/zip dumps instead.
- PSC-db, BIAdb, NaturAr, SuperNatural → not reachable.

## Recommendation

Use the local COCONUT lite 08-2026 CSV plus the IMPPAT batch TSVs as the natural-product layer for
the Mekong resource. Both are already held locally; no new fetch or API key needed. For
compound-level overlap the NPAtlas TSV (36,455 rows, CC0) is the cleanest permissive cross-check.
