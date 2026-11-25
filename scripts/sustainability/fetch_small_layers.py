#!/usr/bin/env python3
"""Fetch the small supporting layers (dams, wetlands, irrigation, land cover) into the repository.

Writes data/raw/zenodo7803254/ and data/raw/zenodo7622998/lulc/ (both gitignored), extracts them in
place, and records sha256 for each archive in data/raw/small_layers_manifest.csv (committed).

These layers are the non-climate inputs to the sustainability analysis: the dam registry, wetland
extent, FAO irrigated area, and the ESA CCI/C3S land-cover series used to exclude intact habitat
from the cultivation-suitability surface.
"""
from __future__ import annotations

import csv
import hashlib
import io
import sys
import time
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import atlas_lib as L  # noqa: E402

RAW = L.RAW
UA = "mekong-atlas/1.0"
SMALL = ["Dams.zip", "Groundwater.zip", "IrrigatedArea.zip", "Wetlands.zip", "SocioEconomic.zip",
         "_SupplementalData.zip", "Streamflow.zip"]
LULC = ("https://zenodo.org/records/7622998/files/LULC.zip?download=1")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def get(url: str, attempts: int = 5) -> bytes:
    delay = 4.0
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=900) as r:
                return r.read()
        except Exception as exc:
            if i == attempts - 1:
                raise
            print(f"    {Path(url).name}: {type(exc).__name__} — retry in {delay:.0f}s", flush=True)
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("unreachable")


def main() -> int:
    rows = []
    for group, base, names in (("7803254", "https://zenodo.org/records/7803254/files/", SMALL),
                               ("7622998-lulc", None, [])):
        for name in names:
            dest_dir = RAW / "zenodo7803254"
            dest_dir.mkdir(parents=True, exist_ok=True)
            path = dest_dir / name
            if not path.exists():
                url = f"{base}{name}?download=1"
                print(f"  fetching {name}", flush=True)
                data = get(url)
                path.write_bytes(data)
            data = path.read_bytes()
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                zf.extractall(dest_dir / name.replace(".zip", ""))
            rows.append({"archive": name, "record": "7803254", "bytes": len(data), "sha256": sha256(data),
                         "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    # Companion-record land cover
    lulc_dir = RAW / "zenodo7622998" / "lulc"
    lulc_dir.mkdir(parents=True, exist_ok=True)
    lulc_path = RAW / "zenodo7622998" / "LULC.zip"
    if not lulc_path.exists():
        print("  fetching LULC.zip (55 MB)", flush=True)
        lulc_path.write_bytes(get(LULC))
    data = lulc_path.read_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        zf.extractall(lulc_dir)
    rows.append({"archive": "LULC.zip", "record": "7622998", "bytes": len(data), "sha256": sha256(data),
                 "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})

    manifest = RAW / "small_layers_manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["archive", "record", "bytes", "sha256", "fetched_at"])
        w.writeheader(); w.writerows(rows)
    print(f"manifest: {manifest} ({len(rows)} archives, {sum(r['bytes'] for r in rows)/1e6:.0f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
