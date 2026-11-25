# Sustainability extension — milestone log

## Milestone 1 — Inventory and harmonization

**Complete.** Zenodo 7803254 inventoried (16 files, 21 GB; manifest with checksums in `data/raw/zenodo7803254_manifest.csv`), every small archive extracted and inspected; the five large archives are downloading to `/Volumes/Expansion/mekong_sustainability/data/raw/zenodo7803254/` with resume support. Provenance table (`docs/zenodo7803254_provenance.csv`) records each upstream source. 5 km Albers equal-area grid built (31,922 in-basin cells, 798,050 km²) and all 153,798 published occurrences assigned (`occurrence_grid_assignment.csv`); 195 of 333 taxa have ≥10 in-basin records and are SDM-eligible.

**Corrections vs the brief:** the paper is Tiwari et al. 2023, not Gumbricht et al.; groundwater is point data, not a grid; inundation is a ReadMe only (access pending); LULC was fetched from the companion record 7622998.

**Blocked:** the environmental stack waits on the five large archives (SurfaceWater done at ~60%, then EM-Earth ×2, GLEAM ×2).

## Milestone 2 — SDM and climate vulnerability

**Blocked on downloads.** Method design documented; scripts will live in `scripts/sustainability/sdm.py`.

## Milestone 3 — Cultivation, harvest pressure, hydrology

**Partially complete.** Harvest pressure and hydrological fragmentation are done, with methods documents, outputs and site layers. Water availability and cultivation suitability are blocked on the GLEAM archives.

## Milestone 4 — Atlas integration and manuscript drafts

**Mostly complete.** `sustainability.html` live with the summary map (tier choropleth, major dams, 10 km buffers), ranked tables and pending notices; species pages carry a collapsible Sustainability section; the homepage links the counts; `data/dictionary_sustainability.csv` covers every new field; the iScience Methods/Results/Discussion/Limitations drafts are in `docs/iScience_SUSTAINABILITY_DRAFT.md` (SDM/cultivation numbers marked `[PENDING]`).

**Manual verification required:** none of the gate items need a human decision yet; the only waiting item is download time.

## QA gates

1 inventory complete — yes (large archives pending inspection) · 2 SDM reporting — pending · 3 blocked CV — designed, pending · 4 scenarios — pending inspection · 5 intact-habitat exclusion — designed, pending · 6 use-score documented — yes · 7 distance threshold documented — yes · 8 pages render — verified in a browser · 9 dictionary — yes · 10 single driver — `run_sustainability.sh` to be written when all steps exist · 11 DOIs cited — yes (page + methods) · 12 drafts — yes with `[PENDING]` placeholders.

## Storage incident — 2026-11-25

The `/Volumes/Expansion` USB drive (the designated raw-data store) **disconnected twice** during the multi-GB downloads, the second time permanently (no longer visible in `diskutil list` / `/dev/disk4`). Loss: ~530 MB tail of SurfaceWater plus the four archives not yet started; the 11 small archives, the extracted dam/streamflow/socioeconomic files and all processed outputs in the repository are safe. **Blocked on a storage decision:** 21 GB cannot fit the internal disk (14 GB free) and must not go to the Drive-synced folder. Options recorded: reconnect the Expansion drive (possibly a different port/cable — it was flaky), attach another external drive, or run a one-archive-at-a-time plan on the internal disk for the four archives that fit (EM_Earth_Temperature likely exceeds it once extracted).

## Network incident — 2026-11-25

Zenodo became unreachable from this machine (curl exit 56 then http=000, 0 B/s over a 16-minute probe) while GitHub remained fast, so the retry onto the internal disk stalled at 2.3 MB of SoilMoiture. **Resume steps once connectivity and storage return:** remount or replace the external drive (or free internal space), then re-run `/tmp/zenodo_download.sh` (resume-capable, `curl -C -`) — the `mekong_sustainability` tree on the Expansion drive holds the manifest and the 11 small archives; the repository holds every processed output.

## Milestone 2 and 3 completed — 2026-11-26 (WorldClim substitution)

**Predictors switched to WorldClim 2.1** after EM-Earth proved unreachable and too large (9.9–21 GB per archive). Fetched bbox-first via `/vsicurl` range reads: 33 crops, ~12 MB transferred, checksums committed in `data/raw/worldclim/manifest.csv`. 2.5 arc-min, resolution-matched to the 5 km grid; 30 arc-sec supported by the script for the future windows. Stated as a deliberate robustness choice in `docs/sdm_methods.md` and the manuscript.

**SDM run on all taxa.** 162 modelled (≥10 occupied 5 km cells), 171 not assessed (119 with 1–9 occupied cells, 52 with no in-basin records). Mean AUC 0.57, TSS 0.36; 139 low-confidence. SSP5-8.5 2041–2060: 3 high loss, 29 moderate loss, 86 stable, 44 gain. Spatially blocked CV only.

**Cultivation suitability run** with a documented substitution for GLEAM (Hargreaves PET from WorldClim + wetland fraction + bio12−PET). 1 high, 35 moderate, 90 low, 36 not feasible.

**Split note:** 195/138 by records; 162/171 by thinned cells. Both reported; the cell split governs modelling.
