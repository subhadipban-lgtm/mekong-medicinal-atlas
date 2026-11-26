# Evidence revision report — 2026-11-26

Status: correction in progress. Scientific validation and submission gates have not passed. All public evidence counts remain provisional.

## Completed corrections

- The audited stale worktree was removed after explicit user approval; no content was merged.
- The pre-audit Results draft is quarantined in the private engine. ChEMBL returned 148 real assay rows for the bounded ten-compound probe; all remain unreviewed.
- The dam GeoJSON is restored, missing map assets produce visible errors, and referenced GeoJSON paths are checked at build time. Homepage and Sustainability now agree that SDM results are exploratory. Bioeconomy states that 333 taxa are not assessed. Risk tables show occurrence/use-data confidence, with summary cards and collapsible sections.
- The classifier uses bounded patterns, confidence and review flags for negated, mixed and special-publication text. The concentration/HPLC regression probe returns in vitro. Existing registers were reclassified separately; details remain in the private engine.
- Source grading no longer grants A for unverified journal formatting or author–year inheritance. Species grade requires two distinct bibliographically resolved DOI sources in the same category. Before: A 296, B 22, C 15, D 0. After: A 93, B 0, C 0, D 240. D now includes insufficient verified sources; it is not evidence of scientific absence. See grading_diff.md and the per-taxon distribution on Methods.
- Source verification, study design and claim support are separate in evidence_source_assessment.csv. A resolved DOI identifies a publication; it does not verify peer review, taxon relevance, an assay or efficacy. Citation conflicts remain recorded.
- The historical natural-products report was archived privately and its unsupported absence/novelty and cross-assay potency-ranking claims rewritten. See claims_rewrite.md. Historical counts are explicitly provisional. The site carries the standing uneven-coverage caveat.
- SDM scenario rows and species summaries carry AUC, TSS and confidence. Of 162 models, 139 are low-confidence and 23 meet both performance thresholds. The confidence-bearing suitability export accompanies the original numeric cell arrays. No suitability surface is currently rendered in the public map, so map hatching is not applicable to this build; any future surface display must carry confidence. No scores or projections were recalculated.
- Methods, Data and About distinguish build QA from scientific claim verification. Existing QA gates are unchanged.
- A pagination defect in the private engine read Europe PMC nextCursorMark from resultList instead of the response root. The function and regression test are corrected. Historical “full corpus” counts must not be interpreted as complete retrieval.

The public aggregate manifest now separately exposes 17,787 provisional candidate rows from the historical 20-taxon corpus alongside the 2,317-row seed slice. No titles, abstracts or publication identifiers are exported in this manifest. The full register contains the seed slice; they must not be summed. This is an increase in visible retrieval coverage, not an increase in verified evidence. The existing QA gate 14 deliberately retains its historical seed-count check and is not scientific validation.

## Remaining gates

The all-333-taxon literature expansion is running with scientific names, retained synonyms and explicit pagination/error logs. Drive-source reconciliation found additional MPIC/Laphookhieo candidates, workbook review/quality-issue sheets and GMS extraction fields that require reconciliation. Raw publication data remains private and is not automatically accepted as evidence.

The 50-paper stratified audit has been sampled but has not passed paper-level verification. No agreement percentage or human kappa is claimed. Grading source design/claim adjudication, final validated aggregate manifest, regenerated human review queue and correction of all historical manuscript claims remain gated by that audit. No manuscript, Zenodo deposit or submission package has been prepared under these provisional counts.

## Preserved properties

In-basin versus outside-basin separation, citation conflicts, sensitive-coordinate generalisation, modelling substitutions, the bioeconomy unknown/null outcome, and explicit limitations are retained. Harvest, hydrological and climate numeric scores were not recalculated in this correction pass.
