# Bioeconomy priority-tier rule

`bioeconomy_priority_tier` is derived, not coded. It is computed by `scripts/build_bioeconomy.py`
from three inputs in `data/processed/bioeconomy_profiles.csv`:

1. **trade_exposure** ∈ {`CITES-listed`, `BioTrade-supported`, `export-commodity`} → condition T
2. **livelihood_dependence** ∈ {`high`, `moderate`} → condition L
3. **certification_readiness** ∈ {`GACP-eligible`, `FairWild-eligible`, `both`} → condition C

| Rule | Tier |
|---|---|
| T ∧ L ∧ C | `high` |
| exactly two of {T, L, C} | `medium` |
| exactly one or none of {T, L, C} | `low` |
| any of the three inputs is `unknown` | `unknown` |

## How the three inputs are populated in this release

The project owner narrowed the coding scope on 2026-11-26: **only taxa covered by the Cao Bang
Geopark jiaogulan study (BIOSRC-001) and the Naban River Watershed study (BIOSRC-002) may be
coded; all other taxa are `unknown`.** Neither study covers any of the 333 atlas taxa (the Cao
Bang study covers *Gynostemma pentaphyllum*; the Naban study covers *Asparagus filicinus*,
*A. subscandens*, *Paris polyphylla*, *Stemona tuberosa* and *Tacca chantrieri*). Therefore all
three inputs are `unknown` for every taxon in this release:

- `trade_exposure`: **`unknown` for every taxon.** Several atlas taxa carry a documented CITES
  appendix (recorded in `conservation_trade.csv`, source SRC-004), but that is not copied into
  `trade_exposure` here, because the coding rule restricts codings to the two designated
  value-chain studies. It is noted per taxon in `notes` as a pointer for a later coding pass.
- `livelihood_dependence`: **`unknown` for every taxon** — no documented income-dependence figure
  exists for any atlas taxon in the two designated studies, and no indirect inference was made
  from the pharmacology corpus.
- `certification_readiness`: **`unknown` for every taxon**, because `wild_cultivated_status` is
  `unknown` throughout `species_master.csv`. The derivation rule is retained for future use:
  `cultivated` or `mixed` → `GACP-eligible`; `wild` → `FairWild-eligible`; `both` → `both`;
  `neither` when the species is not traded; `unknown` when cultivation status is unknown.

## Consequence in this release

Every taxon in the atlas therefore has at least one of the three inputs `unknown`, so every
`bioeconomy_priority_tier` is `unknown`. This is the correct outcome given the evidence, not a
placeholder. `bioeconomy_priority_summary.csv` records the tier counts explicitly (0 high,
0 medium, 0 low, 333 unknown). Any non-zero count would indicate the rule had been applied to
inputs that are not documented.

## How the tier would change with evidence

A taxon moves out of `unknown` only when all three inputs are documented from a cited source,
e.g. a documented BioTrade-supported value chain plus a documented high/moderate income share
plus a documented cultivation or wild status. Prices are never used as a tier input.
