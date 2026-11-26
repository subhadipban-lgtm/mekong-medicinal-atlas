# Inventory coverage and expansion

Audit date: 2026-11-26. The atlas retains 333 curated taxa. No new taxa were inferred from aggregate counts.

## Source audit

| Source | Observed content | Use in expansion |
|---|---|---|
| [Study repository](https://github.com/nawalshrestha/med_plants) | Country-level richness and covariates plus R scripts; no species membership file in the inspected root | Context and model reproduction only |
| [Zenodo 14765689](https://zenodo.org/records/14765689) | `all_angiosperms_native_distribution.rds`, 28.3 MB | Regional distribution reference; not a medicinal-use register |
| [Study methods](https://www.sciencedirect.com/science/article/pii/S0960982225012503) | Medicinal membership derived from MPNS v12; supplements listed as figures and human-occupancy references | Exact medicinal list still needed for reproduction |
| [Kew MPNS services](https://www.kew.org/science/our-science/science-services/medicinal-plant-names-services) | Tailored data subsets offered | Obtain a versioned export with reuse terms and source citations |
| [MPNS version page](https://mpns.science.kew.org/mpns-portal/version) | Current portal identifies v15 | Keep a current expansion separate from the study's v12 baseline |

No bulk medicinal list was downloaded. No contact request was sent. Public portal access does not establish availability or permission to redistribute a bulk export.

## Inclusion workflow

1. Obtain the study's medicinal membership table or a versioned MPNS export. Preserve source taxon IDs, original names, medicinal references, version, access date and reuse terms.
2. Reconcile against accepted WCVP names and the existing atlas. Retain synonym mappings, flag homonyms, and avoid counting duplicate accepted taxa. Do not automatically promote genus records into species.
3. Intersect regional distributions with the seven relevant botanical countries to produce candidates, not confirmed basin taxa.
4. Check specimen/occurrence coordinates against the basin polygon, or review an explicit basin-local floristic source. Record introduced/cultivated status separately from native status.
5. Keep medicinal use recorded elsewhere separate from medicinal use documented in the Mekong basin. Do not infer local communities, indications, efficacy or chemistry from medicinal-list membership.
6. Review provenance and taxonomic/geographic conflicts before changing species_master or generating public species pages. Unresolved candidates stay outside the published inventory count.
7. Recalculate coverage and province-level models only after inclusion review; compare results against the existing curated baseline and assess documentation effort.

## Interpretation

Regional counts overlap and are not a completeness denominator for the basin. Province-level coldspots are exploratory documentation patterns from a limited inventory. They cannot distinguish under-documentation from biological scarcity without additional evidence.

## Next required input

A species-level medicinal membership export, ideally the study's version, with accepted-name identifiers and medicinal references. Kew's tailored-data service or the paper's lead contact are the documented routes. Contacting either requires a separate instruction to send a request.
