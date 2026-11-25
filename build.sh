#!/usr/bin/env bash
# Build the Mekong Medicinal Plant Atlas from the raw inputs.
#
#   ./build.sh                 rebuild everything that does not need the network
#   ./build.sh --with-harvest  also re-run the network harvests (GBIF, references, photos, WFO)
#   ./build.sh --site-only     only regenerate the site pages from the current processed tables
#
# Steps, in order (each is a script under scripts/):
#   harvest (optional)  harvest_gbif_backbone.py, harvest_gbif_occurrences.py, fetch_baselayers.py,
#                       fetch_photos.py, resolve_references_crossref.py, fetch_wfo.R
#   build               build_tables.py -> build_dictionary.py -> grade_evidence.py -> build_dwc.py
#                       -> build_geo.py -> build_site.py
#   check               qa_checks.py (gates 1,2,7,8 and those needing no browser), browser_checks.js
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
command -v "$PYTHON" >/dev/null || { echo "python not found; set PYTHON=..." >&2; exit 1; }
run() { echo; echo "== $* =="; "$@"; }

WITH_HARVEST=0
SITE_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --with-harvest) WITH_HARVEST=1 ;;
    --site-only) SITE_ONLY=1 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

if [[ $SITE_ONLY -eq 0 ]]; then
  if [[ $WITH_HARVEST -eq 1 ]]; then
    run "$PYTHON" scripts/harvest_gbif_backbone.py
    run "$PYTHON" scripts/harvest_gbif_occurrences.py
    run "$PYTHON" scripts/fetch_baselayers.py
    run bash scripts/vendor_assets.sh
    run "$PYTHON" scripts/fetch_photos.py
    run "$PYTHON" scripts/resolve_references_crossref.py
    if command -v Rscript >/dev/null; then run Rscript scripts/fetch_wfo.R; else echo "Rscript not found: skipping the World Flora Online match (data/raw/wfo_match.csv is reused)"; fi
  fi
  run "$PYTHON" scripts/build_tables.py
  run "$PYTHON" scripts/build_dictionary.py
  run "$PYTHON" scripts/grade_evidence.py
  run "$PYTHON" scripts/build_dwc.py
  run "$PYTHON" scripts/build_geo.py
  if [ -f data/raw/shrestha2025/data.csv ]; then run "$PYTHON" scripts/macroecology.py; else echo "skipping macroecology: data/raw/shrestha2025/data.csv missing"; fi
  if [ -f data/raw/wcvp/wcvp_names.csv ]; then run "$PYTHON" scripts/wcvp_match.py; else echo "skipping WCVP matching: data/raw/wcvp/wcvp_names.csv missing"; fi
  if [ -f data/raw/ne_admin1/ne_10m_admin_1_states_provinces.shp ]; then run "$PYTHON" scripts/macroecology_layers.py; else echo "skipping macroecology layers: Natural Earth admin-1 missing"; fi
  if [ -f data/raw/admin1_vascular.json ]; then run "$PYTHON" scripts/internal_coldspots.py; else echo "skipping internal coldspots: data/raw/admin1_vascular.json missing (run scripts/harvest_admin1_vascular.py)"; fi
fi
run "$PYTHON" scripts/build_site.py
run "$PYTHON" scripts/qa_checks.py
if command -v node >/dev/null; then run node scripts/browser_checks.js; run "$PYTHON" scripts/qa_checks.py; else echo "node not found: skipping the browser checks"; fi

echo
echo "Site written to web/. Serve it locally with:"
echo "  python3 -m http.server -d web 8000"
echo "then open http://127.0.0.1:8000/"
