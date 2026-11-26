# Mekong Medicinal Plant Atlas

An interactive, source-cited atlas of medicinal plants of the Mekong River basin, published as a static website and a Darwin Core dataset.

**Live site:** https://subhadipban-lgtm.github.io/mekong-medicinal-plant-atlas/ · **Version:** 0.9.0 (data as of 2026-11-24) · **Dataset DOI: not yet minted**

The atlas covers Cambodia, China (Yunnan and Guangxi), Laos, Myanmar, Thailand and Vietnam. It brings together, for each taxon:

- **Distribution** — where its records are, separating records inside the Mekong basin from records in the same countries but outside the basin.
- **Ethnobotany** — recorded medicinal uses, with the ailment category, the part used and the source.
- **Pharmacology** — extract assays and isolated compounds, with the reported activity, assay, potency and source.
- **Conservation** — IUCN category (with its basis), CITES appendix and trade notes.
- **Evidence grade** — an A–D grade on every record saying how the claim is supported.

## What is on the site

| Page | Content |
|---|---|
| `index.html` | Overview with the basin map and headline statistics |
| `explore.html` | Full occurrence map with clustering and filters, and a searchable species table |
| `species/index.html`, `species/<name>.html` | One page per taxon: distribution map, ethnobotany, pharmacology, conservation, external links, citation |
| `harvest_pressure.html` → `sustainability.html` | Harvest-pressure and hydrological-fragmentation indices, with the summary map |
| `methods.html` | Sources, the grading rubric, the coordinate generalisation policy, software versions, limitations |
| `data.html` | The data catalog: every dataset with schema, licence, version and Zenodo DOI; the live contract manifest |
| `about.html` | Authorship, funding and contact |

The old `download.html` now redirects to `data.html`; datasets are archived on Zenodo
(concept DOI 10.5281/zenodo.24525568), not served from the site.

## The data

| Table | Rows | Grain |
|---|---|---|
| `data/processed/species_master.csv` | 333 | one row per accepted taxon |
| `data/processed/uses.csv` | 207 | one ethnobotanical use record |
| `data/processed/pharmacology.csv` | 690 | one extract assay or isolated compound |
| `data/processed/conservation_trade.csv` | 16 | one conservation or trade statement |
| `data/processed/bioeconomy_profiles.csv` | 333 | one bioeconomy screening profile per taxon (all `unknown` in this release) |
| `data/processed/bioeconomy_priority_summary.csv` | 4 | priority-tier counts and species lists |
| `data/processed/zenodo_registry.csv` | 16 | one catalogued dataset with licence, version and Zenodo DOI or deposit plan |
| `data/processed/references.csv` | 19 | one source |
| `data/processed/occurrences.csv` | about 154,000 | one harvested GBIF record (published records marked) |
| `data/processed/occurrence_summary_by_species.csv` | 333 | occurrence counts per taxon |
| `data/dwc/dwca.zip` | — | Darwin Core Archive of the published occurrence records |
| `data/geo/*.geojson` | — | basin boundary, river, country outlines, occurrence layers |

Every field is defined in [`docs/data_dictionary.md`](docs/data_dictionary.md). The schema in `scripts/schema.py` both generates that document and validates the data against it.

## How to rebuild it

```bash
./build.sh                 # rebuild from the current raw inputs (no network)
./build.sh --with-harvest  # also re-run the GBIF, reference and photo harvests
python3 -m http.server -d web 8000   # then open http://127.0.0.1:8000/
```

`build.sh` runs: table build → data dictionary → evidence grading → Darwin Core archive → map layers → site pages → QA gates. Every step is a script in `scripts/`; no step is a manual edit.

### Pipeline scripts

| Script | Purpose |
|---|---|
| `harvest_gbif_backbone.py` | Match every name to the GBIF backbone; store names, synonyms and country occurrence counts |
| `harvest_gbif_occurrences.py` | Harvest georeferenced occurrence records for every species-level taxon |
| `fetch_baselayers.py` | Basin boundary (Zenodo), river centreline (WWF service / Natural Earth fallback), country outlines |
| `fetch_wfo.R` | Match names against the World Flora Online backbone with `WorldFlora` |
| `fetch_photos.py` | CC-licensed iNaturalist photos, name-verified, with attribution |
| `resolve_references_crossref.py` | Confirm each citation through Crossref and NCBI E-utilities |
| `build_tables.py` | Build the five core tables from the workbook and the backbones |
| `grade_evidence.py` | Apply the A–D evidence rubric to every record |
| `build_dwc.py` | Generalise sensitive coordinates, test each point against the basin, write the Darwin Core Archive |
| `build_geo.py` | Build the map layers (in-basin records in full; outside-basin records generalised) |
| `build_dictionary.py` | Render the data dictionary from the schema and validate the data against it |
| `build_site.py` | Generate the pages and the map data |
| `qa_checks.py` | Run the publication gates and write the QA and conflict reports |
| `browser_checks.js` | Test the map in a real browser over the Chrome DevTools Protocol |

## Method in brief

1. **Names** are matched to the GBIF backbone and to World Flora Online; the two are reconciled, and disagreements are kept rather than hidden (`docs/wfo_gbif_reconciliation.md`). Seven workbook names are synonyms of others also in the list; occurrence records are kept under one entry and the synonym page links to it.
2. **Occurrences** are harvested from GBIF for the six countries, then filtered to records with an open licence, a recognised basis of record and verifiable metadata.
3. **Coordinates of threatened species** are generalised: 0.1° for Critically Endangered, 0.01° for Endangered, Vulnerable or CITES Appendix I–II, with the locality text removed.
4. **Every record is tested against the Mekong basin boundary.** Roughly a tenth of the published records fall inside the basin; the rest are in the same countries but another watershed. The map shows the two separately.
5. **Evidence** for uses and pharmacology is graded by confirming each citation (DOI, PMID/PMC, or a Crossref match), and any citation that is wrong is corrected and recorded.

## Licensing

- Compiled tables and code: CC-BY 4.0, except where a source says otherwise.
- Occurrence archive: CC-BY-NC-4.0, because it includes CC-BY-NC records; each record keeps its own licence.
- Basin boundary: CC-BY 4.0 (Tiwari et al., doi:10.5281/zenodo.7622998). Natural Earth layers: public domain.
- Photos: iNaturalist, under the licence shown on each image.
- The source workbook is a research compilation and is not redistributed.

## Findings worth knowing

- Country-level counts overstate basin presence. Of about 154,000 published records, only roughly 16,000 fall inside the basin; China's count is dominated by records far outside the Lancang watershed.
- Several identifiers printed in the source workbook point to the wrong article or journal; these are corrected, and both the printed identifier and the correct article are recorded.
- *Scoparia dulcis* and *Solanum indicum* have no georeferenced GBIF records, though both are listed in the workbook.
- The two most-traded species, *Aquilaria crassna* and *Dalbergia cochinchinensis*, are CITES Appendix II, so their records are generalised.
- Two workbook entries have conflicting synonyms (*Hygrophila auriculata* / *spinosa*, *Stephania erecta* / *pierrei*); both names are kept, with records under the accepted one.

## Repository layout

```
data/raw/         raw downloads (GBIF, WFO backbone, baselayers, photos, reference cache)
data/processed/   the five core tables, the occurrence table and summaries
data/geo/         GeoJSON layers
data/dwc/         Darwin Core Archive (occurrence.txt, meta.xml, eml.xml, dwca.zip)
docs/             data dictionary, reconciliation notes, QA report, conflict report, data paper draft
scripts/          the build pipeline
sources/          the source register
web/              the website (published to GitHub Pages)
```
