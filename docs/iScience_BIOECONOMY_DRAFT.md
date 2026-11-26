# iScience manuscript additions — bioeconomy layer (draft, ready to paste)

All numbers are traceable to `data/processed/bioeconomy_profiles.csv`,
`data/processed/bioeconomy_priority_summary.csv`, `data/processed/evidence_manifest.json`,
`data/processed/conservation_trade.csv` and the committed scripts
(`scripts/build_bioeconomy.py`, `docs/bioeconomy_priority_rule.md`). No number below is
invented; every derived figure names the query that produced it.

## Methods — Bioeconomy extraction

For each of the 333 atlas taxa we record eight bioeconomy fields (value-chain type, trade
exposure, certification readiness, livelihood dependence, equity flag, valuation method,
market-price proxy, and a derived priority tier) following a fixed coding protocol
(`scripts/build_bioeconomy.py`; field definitions in `data/dictionary_bioeconomy.csv`;
sources in `docs/bioeconomy_sources.csv`). Two value-chain studies were retrieved for this
coding pass: the Cao Bang Geopark jiaogulan value-chain analysis (Ngo et al., PLOS ONE 2025,
doi:10.1371/journal.pone.0324746) and the Naban River Watershed wild medicinal-plant study
(Bucher et al., Ethnobotany Research and Applications 2020, doi:10.32859/ERA.19.21.1-12).
Coding was restricted to taxa covered by these two studies; **neither study covers any of the
333 atlas taxa** (they concern *Gynostemma pentaphyllum*, *Asparagus filicinus*,
*A. subscandens*, *Paris polyphylla*, *Stemona tuberosa* and *Tacca chantrieri*). Consequently
every coded field is the documented value `unknown`, by rule rather than by omission. No value
was imputed and no indirect inference was drawn from the pharmacology corpus. The priority tier
is derived, never coded: a taxon is *high* only when it has a documented trade exposure (CITES
listing, BioTrade programme support or export-commodity status), a documented moderate-or-high
livelihood dependence, and an applicable certification standard (GACP or FairWild); any
`unknown` input forces the tier to `unknown`. Confidence is recorded per row (`coded_confidence`),
every row carries the coding agent identifier (`coded_by`) and awaits human review
(`reviewed_by`). Market prices are recorded only where a source states value, currency and
unit, and date together; they are labelled proxies, never valuations, and are never aggregated
into a total. No per-species bioprospecting value is claimed; published per-plant bioprospecting
ranges (roughly US$200–US$2M) are cited in the literature only as context.

## Results — Bioeconomy readiness of the pilot taxa

- **Priority tiers**: of the 20 pilot taxa, 0 are high, 0 medium, 0 low and 20 unknown
  (source: `bioeconomy_priority_summary.csv`).
- **CITES-listed**: 2 of the 20 pilot taxa are CITES Appendix II in the atlas register
  (*Aquilaria crassna*, *Dalbergia cochinchinensis*; source: `conservation_trade.csv`).
  These listings are recorded as per-taxon pointers in the bioeconomy notes but are not copied
  into `trade_exposure` because the coding pass is restricted to the two value-chain studies.
- **BioTrade-supported**: 0 of 20.
- **GACP- or FairWild-eligible**: 0 of 20 (every certification readiness is `unknown`, because
  `wild_cultivated_status` is unrecorded for all 333 taxa).
- **Overlap with molecular coherence**: defined for this analysis as the five pilot taxa with
  the most seeded compounds (A. crassna 12, D. cochinchinensis 9, S. dulcis 9, A. marmelos 7,
  A. heterophyllus 7; query: top-5 `n_compounds` in `evidence_manifest.json`), none of the five
  has a high bioeconomy priority tier (0/5; overlap = 0).

The result of this pass is therefore a fully documented *absence of evidence*, not evidence of
absence: the screening layer's schema, derivation rule and source register are complete, and
the layer reports `unknown` for every taxon until value-chain studies covering atlas taxa are
retrieved.

## Discussion

The atlas is designed to identify not only which Mekong medicinal plants are chemically
interesting but which are economically viable and socially embedded enough to support
cultivation and certification without undermining wild populations. In this first screening
pass the bioeconomy layer is deliberately empty: the two value-chain studies retrieved
(GMS-adjacent Cao Bang and Yunnan case studies) document that NTFP value chains in the region
capture real income for ethnic-minority collectors — the Cao Bang analysis reports jiaogulan
farmers capturing 33–80% of value added across channels, with value-added doubling worth
roughly US$2.8 per household — but none of the studied taxa is in the atlas, so no atlas taxon
can borrow those findings. BioTrade programme figures for the GMS are cited in the sources
register as context only. This is a screening framework awaiting its evidence, not a claim that
the basin's medicinal flora lacks commercial value: the atlas already records CITES-listed,
heavily traded taxa (agarwood, Siamese rosewood) whose documented trade status is available for
a future coding pass once the coding scope is widened by the authors.

## Limitations

- Bioeconomy data are sparse and heterogeneous; `unknown` is a real value, not a gap to be
  filled, and in this release it is the only value.
- Market-price proxies are not valuations; none is reported because no price with a stated
  currency, unit, date and source could be attached to an atlas taxon from the two designated
  studies.
- No per-species bioprospecting value is claimed.
- The pilot coding (20 taxa) is complete in the sense that every field is populated or
  explicitly `unknown`; the wider 333-taxon layer is a screening framework and is 100%
  `unknown` in this release.
- Equity flags are only recorded where a value-chain study or a documented benefit-sharing
  assessment exists; none exists for an atlas taxon, and no flag was inferred from trade status.
- Field validation of value-chain and livelihood data is required before any policy use.
- The restricted evidence-engine contract (publications, compounds, networks) is not published;
  its structure-only manifest (`data/evidence_manifest.json`) is.

## Data Records

| Dataset | Rows | Version | Zenodo version DOI | Concept DOI | Licence |
|---|---|---|---|---|---|
| species_master | 333 | 0.9.0 | 10.5281/zenodo.24525569 | 10.5281/zenodo.24525568 | CC-BY-4.0 |
| occurrences (CSV + DwC-A) | 153,798 | 0.9.0 | 10.5281/zenodo.24525569 | 10.5281/zenodo.24525568 | CC-BY-NC-4.0 (per record) |
| uses | 207 | 0.9.0 | 10.5281/zenodo.24525569 | 10.5281/zenodo.24525568 | CC-BY-4.0 |
| pharmacology | 690 | 0.9.0 | 10.5281/zenodo.24525569 | 10.5281/zenodo.24525568 | CC-BY-4.0 |
| conservation_trade | 16 | 0.9.0 | 10.5281/zenodo.24525569 | 10.5281/zenodo.24525568 | CC-BY-4.0 |
| bioeconomy_profiles | 333 | 1.0.0 | DOI pending † | DOI pending † | CC-BY-4.0 |
| bioeconomy_priority_summary | 4 | 1.0.0 | DOI pending † | DOI pending † | CC-BY-4.0 |
| sustainability_harvest_pressure | 281 | 1.0.0 | DOI pending † | DOI pending † | CC-BY-4.0 |
| sustainability_hydrological_fragmentation | 285 | 1.0.0 | DOI pending † | DOI pending † | CC-BY-4.0 |
| macroecology_residuals | 7 | 1.0.0 | DOI pending † | DOI pending † | CC-BY-4.0 |
| macroecology_slope_comparison | 6 | 1.0.0 | DOI pending † | DOI pending † | CC-BY-4.0 |
| evidence_grade_provenance | 333 | 1.0.0 | DOI pending † | DOI pending † | CC-BY-4.0 |
| evidence_contract_manifest | 7 endpoints | 1.0.0 | DOI pending † | DOI pending † | CC-BY-4.0 |
| publications_manifest | 2,317 | 1.0.0 | DOI pending † | DOI pending † | CC-BY-4.0 |
| compounds_manifest | 119 | 1.0.0 | DOI pending † | DOI pending † | CC-BY-4.0 |
| network_summary_manifest | 20 | 1.0.0 | DOI pending † | DOI pending † | CC-BY-4.0 |

† DOI pending at submission: the rows state the deposit plan in `zenodo_registry.csv`;
no DOI was invented. The evidence contract endpoints themselves are restricted and are not
deposited; only their structure-only manifest is.
