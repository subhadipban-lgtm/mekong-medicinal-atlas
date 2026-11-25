#!/usr/bin/env bash
# Download the front-end libraries at pinned versions into web/assets/vendor and verify them
# against scripts/vendor_checksums.txt. Run with --update to (re)write the checksum file.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/web/assets/vendor"
SUMS="$ROOT/scripts/vendor_checksums.txt"

LEAFLET=1.9.4
CLUSTER=1.5.3
JQUERY=3.7.1
DT=2.1.8
DTBS5=2.1.8
U=https://unpkg.com

files=(
  "leaflet/leaflet.js|$U/leaflet@$LEAFLET/dist/leaflet.js"
  "leaflet/leaflet.css|$U/leaflet@$LEAFLET/dist/leaflet.css"
  "leaflet/images/layers.png|$U/leaflet@$LEAFLET/dist/images/layers.png"
  "leaflet/images/layers-2x.png|$U/leaflet@$LEAFLET/dist/images/layers-2x.png"
  "leaflet/images/marker-icon.png|$U/leaflet@$LEAFLET/dist/images/marker-icon.png"
  "leaflet/images/marker-icon-2x.png|$U/leaflet@$LEAFLET/dist/images/marker-icon-2x.png"
  "leaflet/images/marker-shadow.png|$U/leaflet@$LEAFLET/dist/images/marker-shadow.png"
  "markercluster/leaflet.markercluster.js|$U/leaflet.markercluster@$CLUSTER/dist/leaflet.markercluster-src.js"
  "markercluster/MarkerCluster.css|$U/leaflet.markercluster@$CLUSTER/dist/MarkerCluster.css"
  "markercluster/MarkerCluster.Default.css|$U/leaflet.markercluster@$CLUSTER/dist/MarkerCluster.Default.css"
  "jquery/jquery.min.js|$U/jquery@$JQUERY/dist/jquery.min.js"
  "datatables/dataTables.min.js|$U/datatables.net@$DT/js/dataTables.min.js"
  "datatables/dataTables.min.css|$U/datatables.net-dt@$DT/css/dataTables.dataTables.min.css"
  "datatables/dataTables.bootstrap5.min.js|$U/datatables.net-bs5@$DTBS5/js/dataTables.bootstrap5.min.js"
  "datatables/dataTables.bootstrap5.min.css|$U/datatables.net-bs5@$DTBS5/css/dataTables.bootstrap5.min.css"
)

for entry in "${files[@]}"; do
  path="${entry%%|*}"; url="${entry##*|}"
  mkdir -p "$(dirname "$DEST/$path")"
  curl -fsSL --retry 3 -m 120 -o "$DEST/$path" "$url" || { echo "FAILED $url" >&2; exit 1; }
done

if [[ "${1:-}" == "--update" ]]; then
  : > "$SUMS"
  for entry in "${files[@]}"; do
    path="${entry%%|*}"
    (cd "$DEST" && shasum -a 256 "$path") >> "$SUMS"
  done
  echo "wrote $SUMS"
fi
(cd "$DEST" && shasum -a 256 -c "$SUMS" --quiet) && echo "vendor assets verified ($(wc -l < "$SUMS" | tr -d ' ') files)"
