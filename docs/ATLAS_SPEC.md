# Mekong Medicinal Atlas — map and interface specification

## Design intent
One map, eleven switchable layers, one species drawer. A researcher opens it, filters to (say) *Zingiberaceae* + *antidiabetic* + *Cambodia/Laos*, and gets adefensible list to work from. Every point and every claim links back to a source ID.

## Layers (toggleable)

| # | Layer | Data source | Encoding |
|---|---|---|---|
| 1 | Species richness | `atlas_layers.json → species_richness` | graduated country fill (TH/LA/VN/KH/MM/CN) |
| 2 | Occurrence density | GBIF country counts (species_master.csv) | choropleth of counts per basin country; no point layer published |
| 3 | Use categories | `uses.csv` aggregated | 10 ailment classes, categorical palette |
| 4 | Conservation status | `conservation_trade.csv` | IUCN colour scale (CR/EN/VU/NT/LC/DD) |
| 5 | CITES appendix | `conservation_trade.csv` | I / II / III outline |
| 6 | Chemistry classes | `pharmacology.csv` + `atlas_layers.json → chemistry` | categorical; top 15 classes + "other" |
| 7 | Pharmacological activity | `atlas_layers.json → pharmacology` | bubble per activity class |
| 8 | Cultivation / wild status | `species_master.csv` (`life_form`, `wild_cultivated_status`) | fill pattern |
| 9 | Market / trade level | workbook trade flags | high/medium/low |
| 10 | Source coverage | `atlas_layers.json → source_coverage` | choropleth of sources per country |
| 11 | Evidence tier | `in_tier1/2/3` flags | T1/T2/T3/none |

## Base map
Tile: CARTO raster basemap (basemaps.cartocdn.com) with the project API key; the key is public by nature and should be domain-restricted in the CARTO dashboard. Basin boundary overlay: MRC Mekong Basin boundary (see SOURCES_REQUIRING_MANUAL_ACCESS.md #7) — until obtained, show country polygons with a note that basin intersection is unverified.

## Interaction
- Pan/zoom; click a point → side drawer with: accepted name, family, tier flags, occurrence count per country, GBIF link, WFO link, GBIF taxon key, synonyms (expandable), uses (list, with source IDs), pharmacology rows, conservation flags, evidence grade.
- Filter panel: country · family · tier · use category · activity class · CITES/IUCN · has coordinates.
- Export: filtered CSV + GeoJSON of the current view.

## Non-goals
- No species distribution modelling (MaxEnt etc.) — needs a DOI-citable full GBIF download; the sampled point set was discarded.
- No inference of use from phylogeny.
- No download of paywalled full texts.

## Build
Static site preferred: single `index.html` + Leaflet + the CSV/GeoJSON/JSON in `data/`. No backend required. Deployable to GitHub Pages or the existing `teaco-platform` hosting.
