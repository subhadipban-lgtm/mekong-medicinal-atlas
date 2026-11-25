# Mekong Medicinal Plant Atlas: occurrence records of medicinal plant taxa in the Mekong River basin

*Data paper draft — version 0.9.0, data as of 2026-11-24. Structured after the GBIF data paper template and the GBIF Metadata Profile. The dataset DOI is not yet minted; it will be added here and in `data/dwc/eml.xml` at the first archived release.*

## Authors

Subhadip Banerjee^1,^*

^1^ Mae Fah Luang University, Chiang Rai, Thailand. ^*^ Corresponding author. *Author list, order and affiliations to be finalised before submission.*

## Abstract

We present a derived occurrence dataset and an interactive atlas for medicinal plants of the Mekong River basin, covering Cambodia, China (Yunnan and Guangxi), Laos, Myanmar, Thailand and Vietnam. A species list of 333 taxa was assembled from a survey of the regional ethnobotanical and phytochemical literature and reconciled against the GBIF backbone and the World Flora Online backbone. For each species-level taxon we harvested georeferenced records from the GBIF occurrence API and retained those with an open licence, a recognised basis of record and verifiable metadata, giving 153,798 published records from 147 GBIF datasets. Each record was tested against a published Mekong basin boundary: 16,143 records fall inside the basin and 137,655 lie in the same countries but outside the watershed. Coordinates of species assessed as threatened or listed in CITES are generalised (3,788 records). The dataset is accompanied by 207 ethnobotanical use records and 690 pharmacological records, each graded A–D by how well its citation could be confirmed, and by a static web atlas.

## Introduction

The Mekong basin sustains a large and widely traded medicinal flora, but the evidence for it is scattered across national floras, local surveys and pharmacological papers that rarely agree on names or coverage. Two problems follow. First, occurrence and use are usually reported at country level, which is a poor proxy for occurrence in the watershed. Second, the strength of the evidence behind a reported use varies from a peer-reviewed survey to an unverified web page, and this is seldom stated. This dataset addresses both: it separates basin occurrence from country occurrence, and it attaches an evidence grade and a source to every claim.

## Data description

- **Occurrence records** (`data/dwc/dwca.zip`, Darwin Core Archive): 153,798 records in 34 Darwin Core terms.
- **Species master** (`species_master.csv`): 333 taxa, with accepted and synonymous names, family, life form, conservation status and occurrence counts by country and basin position.
- **Ethnobotanical uses** (`uses.csv`): 207 records, with ailment category, part used and source.
- **Pharmacology** (`pharmacology.csv`): 690 records of extract assays and isolated compounds.
- **Conservation and trade** (`conservation_trade.csv`): 16 statements with IUCN category and its basis, CITES appendix and trade notes.
- **GeoJSON layers** (`data/geo/`): basin boundary, river centreline, country outlines and occurrence layers.

## Sampling methods

**Species list.** The master list of 333 taxa was compiled from the literature survey on medicinal plant use in the six basin countries; 333 taxa have an ethnobotanical record, 333 have extract assay data and 333 have isolated-compound data. Names were matched to the GBIF backbone (with documented manual resolutions for nine names) and to World Flora Online (`WorldFlora`, Kindt 2020). The two backbones agree on genus and species for 292 of 333 taxa and differ for 41, mostly recent generic recircumscriptions. Where the workbook lists both a synonym and the accepted name of one species (7 taxa), occurrence records are kept under the accepted name only.

**Occurrences.** For each species-level taxon we queried the GBIF occurrence search API (`hasCoordinate=true`, `hasGeospatialIssue=false`) for the six countries, fetching every page. 153,800 records were harvested. A record was kept if it carried an open licence, a recognised `basisOfRecord` and either an `occurrenceID` or an institution code with a catalogue number; 153,798 passed and 2 did not.

**Basin position.** Each record was tested against the Mekong basin boundary from the Zenodo deposit of Tiwari et al. (doi:10.5281/zenodo.7622998, CC-BY-4.0), 96 catchment polygons dissolved and reprojected to EPSG:4326. Reference places with certain membership are classified correctly (inside: Vientiane, Luang Prabang, Phnom Penh, Jinghong, Khon Kaen; outside: Bangkok, Kunming, Hanoi, Mandalay, Guangzhou, Chiang Mai, Ho Chi Minh City).

**Coordinate generalisation.** Species with an IUCN category of CR, or EN/VU, or listed in CITES Appendix I or II, had coordinates rounded to 0.1° or 0.01° respectively and their locality text removed; the coordinate uncertainty was raised to at least the rounding cell. 3,788 records across 15 species were generalised.

**Literature evidence.** Each use and pharmacology record carries a citation as printed in the source workbook. Citations were confirmed through Crossref or the NCBI E-utilities. A record is graded A when the article is confirmed peer-reviewed, B when it is a reference book or flora, C when it is a report or an unverifiable citation, and D when there is no usable citation. Occurrence records, being specimens or observations, are grade C by construction.

## Geographic coverage

Cambodia, China (Yunnan and Guangxi), Laos, Myanmar, Thailand and Vietnam. Bounding box of published records: west 75.010, east 133.523, south 5.750, north 51.730. Published records by country:

| Country | Inside basin | Outside basin |
|---|---|---|
| CN | 7,249 | 111,713 |
| TH | 3,911 | 18,186 |
| VN | 2,733 | 6,058 |
| LA | 1,369 | 23 |
| KH | 873 | 472 |
| MM | 8 | 1,203 |

## Taxonomic coverage

Vascular plants, plus one alga. 329 taxa are identified to species and 4 name only a genus. Names follow the GBIF backbone; synonyms are in `species_master.csv`. The widest-represented families are Acanthaceae, Zingiberaceae, Fabaceae, Rutaceae, Apocynaceae and Rubiaceae.

## Temporal coverage

Record dates span the earliest to the latest supplied by GBIF. Records without an event date were left blank rather than estimated. The dataset snapshot was taken on 2026-11-24.

## Quality control

- Every published record has an `occurrenceID`, a licence and a dataset reference; duplicate identifiers were replaced by their GBIF URL, and zero and out-of-range coordinates were removed.
- The archive is a valid Darwin Core Archive: `meta.xml` declares tab-separated fields with no enclosure character and the file parses to a constant 34 fields per row.
- Species sharing an accepted taxon key were detected by grouping on the accepted key rather than the backbone key, so synonym pairs do not double-count occurrences.
- Evidence grades were assigned by one script from confirmed citations; 59 citations were found to carry an error, and each is listed in the conflict report.
- The atlas passes the publication gates recorded in `docs/QA_REPORT.md`, tested in a real browser over the Chrome DevTools Protocol.

## Usage rights

Occurrence records: CC-BY-NC-4.0 as a compilation; each record keeps its own licence (CC0, CC-BY-4.0 or CC-BY-NC-4.0) in its `license` field. Compiled tables and code: CC-BY-4.0. Basin boundary: CC-BY-4.0. Natural Earth layers: public domain.

## Dataset description

- **Object name:** Mekong Medicinal Plant Atlas occurrence dataset
- **Format:** Darwin Core Archive (`data/dwc/dwca.zip`), with CSV and GeoJSON for the derived tables and layers
- **Distribution:** the repository and the atlas site
- **Licence:** CC-BY-NC-4.0 (occurrence archive)

## References

GBIF.org (2026) occurrence search API and GBIF Backbone Taxonomy; World Flora Online backbone (Kindt 2020, `WorldFlora`, doi:10.1002/aps3.11388); Tiwari et al., doi:10.5281/zenodo.7622998; Dang et al. (2022) *Science of the Total Environment* 831:154833. The 19 primary sources of the ethnobotanical and pharmacological records are listed in `data/processed/references.csv` and on the Methods page.

## Figures

1. Study area: the Mekong basin boundary, river centreline and six countries.
2. Occurrence map, coloured by evidence grade, with the basin boundary.
3. Occurrence records inside and outside the basin by country.
4. Species, use records and pharmacology records by evidence grade.

*Figures 1 and 2 are the live maps on the atlas; a static version can be exported from `web/` for submission.*
