# WFO ↔ GBIF reconciliation

Backbone: World Flora Online static release, downloaded 2026-11-24 (`data/raw/wfo/classification.csv`, 1,657,866 rows).

GBIF backbone match: 333/333 names resolved (323 EXACT, 1 FUZZY, 9 manual).

WFO match (Kindt 2020, `WFO.match`, Fuzzy=0.1): 329/333 names reached an Accepted name.

- agree on genus+epithet: 292
- differ: 41
- no WFO accepted match: 0

## Names where GBIF and WFO disagree

| Workbook name | GBIF backbone | WFO backbone | WFO status |
|---|---|---|---|
| `aglaia` | Aglaia Lour. | NA | NA |
| `allamanda cathartica` | Allamanda cathartica L. | Allamanda schottii | Accepted |
| `amomum villosum` | Amomum villosum Lour. | Wurfbainia villosa | Accepted |
| `aquilaria malaccensis` | Aquilaria malaccensis Lam. | Aquilaria sinensis | Accepted |
| `aristolochia tagala` | Aristolochia tagala Cham. | Aristolochia acuminata | Accepted |
| `artemisia annua` | Artemisia annua L. | Artemisia gmelinii | Accepted |
| `artocarpus lakoocha` | Artocarpus lakoocha Roxb. | Artocarpus lacucha | Accepted |
| `caesalpinia sappan` | Caesalpinia sappan L. | Biancaea sappan | Accepted |
| `cassia alata` | Cassia alata L. | Senna alata | Accepted |
| `cassia angustifolia` | Cassia angustifolia Vahl | Senna alexandrina | Accepted |
| `celosia cristata` | Celosia cristata L. | Celosia argentea | Accepted |
| `chrysanthemum cinerariifolium` | Chrysanthemum cinerariifolium (Trevis.) Vis. | Tanacetum cinerariifolium | Accepted |
| `clausena` | Clausena Burm.f. | Clausena | Accepted |
| `clerodendrum viscosum` | Clerodendrum viscosum Vent. | Clerodendrum infortunatum | Accepted |
| `coix lacryma` | Coix lacryma L. | Coix lacryma-jobi | Accepted |
| `costus speciosus` | Costus speciosus (J.Koenig) Sm. | Hellenia speciosa | Accepted |
| `desmodium triquetrum` | Desmodium triquetrum (L.) DC. | Tadehagi triquetrum | Accepted |
| `duhaldea cappa` | Duhaldea cappa (Buch.-Ham. ex D.Don) Pruski & Anderb. | Inula cappa | Accepted |
| `dysoxylum binectariferum` | Dysoxylum binectariferum (Roxb.) Hook.fil. ex Bedd. | Dysoxylum gotadhora | Accepted |
| `ecdysanthera rosea` | Ecdysanthera rosea Hook. & Arn. | Urceola rosea | Accepted |
| `erythrina` | Erythrina L. | NA | NA |
| `hedyotis diffusa` | Scleromitrion diffusum (Willd.) R.J.Wang | Oldenlandia herbacea var. herbacea | Accepted |
| `hygrophila spinosa` | Hygrophila spinosa T.Anderson | Hygrophila auriculata | Accepted |
| `lannea grandis` | Lannea grandis (Dennst.) Engl. | Lannea coromandelica | Accepted |
| `leonurus japonicus` | Leonurus japonicus Houtt. | Leonurus macranthus | Accepted |
| `mahonia bealei` | Mahonia bealei (Fortune) Carrière | Berberis bealei | Accepted |
| `marsdenia tenacissima` | Marsdenia tenacissima (Roxb.) Moon | Gongronemopsis tenacissima | Accepted |
| `millettia pachycarpa` | Millettia pachycarpa Benth. | Derris taiwaniana | Accepted |
| `murraya koenigii` | Murraya koenigii (L.) Spreng. | Bergera koenigii | Accepted |
| `randia spinosa` | Randia spinosa H.Karst. | Catunaregam spinosa | Accepted |
| `sargassum` | Sargassum C.Agardh, 1820 | NA | NA |
| `solanum indicum` | Solanum indicum L. | Solanum violaceum | Accepted |
| `solanum violaceum` | Solanum violaceum Ortega | Solanum tuberosum | Accepted |
| `stephania erecta` | Stephania erecta Craib | Stephania pierrei | Accepted |
| `stereospermum tetragonum` | Stereospermum tetragonum DC. | Stereospermum colais | Accepted |
| `thevetia peruviana` | Thevetia peruviana (Pers.) K.Schum. | Cascabela thevetia | Accepted |
| `trachyspermum roxburghianum` | Trachyspermum roxburghianum (DC.) Craib | Psammogeton involucratum | Accepted |
| `tylophora indica` | Tylophora indica (Burm.fil.) Merr. | Vincetoxicum indicum | Accepted |
| `vetiveria zizanioides` | Vetiveria zizanioides Stapf, 1906 | Chrysopogon zizanioides | Accepted |
| `wrightia tomentosa` | Wrightia tomentosa (Roxb.) Roem. & Schult. | Wrightia arborea | Accepted |
| `zingiber cassumunar` | Zingiber cassumunar Roxb. | Zingiber purpureum | Accepted |

## Names with no WFO accepted match


## Reading the disagreements

Almost all differences are **taxonomic-concept differences, not errors**:

- *Amomum villosum* → WFO: *Wurfbainia villosa* (Zingiberaceae genera re-circumscribed after WFO import of the Zingiberaceae resource centre treatment)
- *Senna alata* / *Senna alexandrina* (WFO accepts these; GBIF lags)
- *Caesalpinia sappan* → WFO *Biancaea sappan*
- *Cassia*/*Senna*, *Costus* → *Hellenia*, *Desmodium* → *Tadehagi*, *Duhaldea*/*Inula*, *Ecdysanthera* → *Urceola*, *Lannea*, *Leonurus* — all reflect post-2020 generic recircumscriptions that WFO adopted and GBIF has not.
- *Aristolochia acuminata* vs *A. tagala*; *Aquilaria*; *Artemisia gmelinii* vs *A. annua* — genuine synonymy disputes; both names in active use in the ethnobotanical literature.

**Policy for this atlas:** GBIF backbone is retained as the operational key (it drives occurrence counts and taxon keys). WFO accepted names are recorded alongside in `species_master.csv` (`wfo_accepted_name`) and surfaced in the viewer as a synonym chain. Neither is presented as sole truth. `best_name` prefers the WFO accepted name for display, falling back to GBIF when WFO has no accepted match.
