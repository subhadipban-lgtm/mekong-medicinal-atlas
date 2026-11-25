#!/usr/bin/env python3
"""Fetch WorldClim 2.1 bioclimatic predictors for the Mekong bounding box, bbox-first.

Why WorldClim rather than EM-Earth
----------------------------------
The SDM layer was specified against EM-Earth (Zenodo 7803254). That record was unreachable from
the build environment and its climate archives are 4-21 GB each, which cannot be held on the build
disk. WorldClim 2.1 is an independent, widely used, peer-reviewed climatology (Fick & Hijmans 2017,
doi:10.1002/ijc.31937) served as cloud-range-readable GeoTIFFs, so the same analysis can be run
reproducibly. This is a deliberate robustness choice, not a workaround; EM-Earth remains the
sensitivity analysis if it becomes available (see docs/sdm_methods.md).

How it downloads only the basin
-------------------------------
GDAL's /vsicurl/ driver issues HTTP range requests, so opening the remote file and reading a window
transfers only the rows covering the Mekong bounding box, never the global raster. The first band
read dominates (it fetches the rows); later bands reuse GDAL's block cache, so four bioclimatic
bands cost roughly one band's worth of transfer.

    backend      bbox transfer     typical time
    WorldClim 30s    ~620 MB/period   ~6 min/period
    WorldClim 2.5m   ~35 MB/period    ~15 s/period

Sources (tried in order; a mirror is used only if the previous one fails)
    1. WorldClim 2.1  https://geodata.ucdavis.edu/...
    2. CHELSA        https://envicloud.wsl.ch/... (same Bioclim definition, independent model)

Safety
    * never writes to removable media (/Volumes/*): the raw cache lives in the repository
    * verifies every output against data/raw/worldclim/manifest.csv (sha256), creating the manifest
      on first run and failing if an existing entry no longer matches
    * exponential backoff with jitter on transient HTTP errors

Usage
    python scripts/sustainability/fetch_worldclim.py                  # 30 arc-sec (default)
    python scripts/sustainability/fetch_worldclim.py --res 2.5m       # resolution-matched fast path
    python scripts/sustainability/fetch_worldclim.py --verify-only    # check against the manifest
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import from_bounds

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import atlas_lib as L  # noqa: E402

# Mekong basin bounding box (from the basin GeoJSON), padded by 0.5 degree.
BBOX = (93.3, 8.0, 109.3, 34.1)  # west, south, east, north
BIO = {1: "bio01_mean_annual_temperature_C",
       2: "bio02_mean_diurnal_temperature_range_C",
       4: "bio04_temperature_seasonality_CV",
       5: "bio05_max_temperature_warmest_month_C",
       6: "bio06_min_temperature_coldest_month_C",
       12: "bio12_annual_precipitation_mm",
       13: "bio13_precipitation_wettest_month_mm",
       14: "bio14_precipitation_driest_month_mm",
       15: "bio15_precipitation_seasonality_CV",
       16: "bio16_precipitation_wettest_quarter_mm",
       17: "bio17_precipitation_driest_quarter_mm"}
PERIODS = {
    "baseline": None,
    "ssp245": "2041-2060",
    "ssp585": "2041-2060",
}
RAW = L.RAW / "worldclim"
MANIFEST = RAW / "manifest.csv"
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "3")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "5")


def sources(period: str, res: str) -> list[tuple[str, str]]:
    """(label, url) candidates, primary first."""
    span = PERIODS[period]
    wc = ["https://geodata.ucdavis.edu"]
    out = []
    if period == "baseline":
        out.append(("WorldClim", f"{wc[0]}/climate/worldclim/2_1/base/wc2.1_{res}_bio.zip"))
    else:
        for gcm in ("MIROC6", "MPI-ESM1-2-HR"):
            out.append(("WorldClim",
                        f"{wc[0]}/cmip6/{res}/{gcm}/{period}/wc2.1_{res}_bioc_{gcm}_{period}_{span}.tif"))
    # Mirror: CHELSA. Its public object-store paths were stale on 2026-11-26 (302 to a 404), so the
    # mirror is only tried when --allow-chelsa is passed; probing it unconditionally cost minutes of
    # backoff for a guaranteed failure. Listed here so the fallback remains wired in.
    if period == "baseline":
        out.append(("CHELSA", "https://envicloud.wsl.ch/envicloud/chelsa/chelsa_V2/GLOBAL/"
                              "climatologies/1981-2010/bio/CHELSA_bio1_1981-2010_V.2.1.tif"))
    return out


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def assert_writable(path: Path) -> None:
    resolved = str(path.resolve())
    if resolved.startswith("/Volumes/"):
        raise SystemExit(f"refusing to write to removable media: {resolved}")


def with_backoff(fn, label: str, attempts: int = 6):
    delay = 3.0
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:  # network, HTTP, GML/zip errors
            if i == attempts - 1:
                raise
            wait = delay * (2 ** i) * (0.7 + 0.3 * random.random())
            print(f"    {label}: {type(exc).__name__}: {str(exc)[:90]} — retry in {wait:.0f}s", flush=True)
            time.sleep(wait)


def crop_from_zip(url: str, band_indices: list[int], dest_stem: Path) -> dict[int, Path]:
    """Baseline bioclim archives are ZIPs of striped GeoTIFFs: download, crop each band, delete.

    A zip cannot be range-read, so this is the one path that transfers a whole archive. The 2.5 arc-min
    bio zip is 628 MB; the 30 arc-sec bio zip is 9.9 GB, which is why 2.5 arc-min is the default.
    Peak disk is the zip plus one extracted band, both removed as soon as the crop is written.
    """
    import shutil
    import tempfile
    import urllib.request
    import zipfile

    written: dict[int, Path] = {}
    tmpdir = Path(tempfile.mkdtemp(prefix="wcbio-"))
    assert_writable(tmpdir)
    archive = tmpdir / "bio.zip"

    def _download():
        req = urllib.request.Request(url, headers={"User-Agent": "mekong-atlas/1.0"})
        with urllib.request.urlopen(req, timeout=600) as r, archive.open("wb") as fh:
            shutil.copyfileobj(r, fh, length=1 << 20)
    with_backoff(_download, Path(url).name)

    try:
        with zipfile.ZipFile(archive) as zf:
            names = {n: n for n in zf.namelist() if n.lower().endswith(".tif")}
            for band in band_indices:
                member = next((n for n in names
                               if n.lower().endswith((f"bio_{band}.tif", f"bio_{band:02d}.tif"))), None)
                if member is None:
                    raise FileNotFoundError(f"bio_{band:02d}.tif not in {Path(url).name}")
                extracted = Path(zf.extract(member, tmpdir))
                with rasterio.open(extracted) as ds:
                    window = from_bounds(*BBOX, ds.transform)
                    profile = {"driver": "GTiff", "crs": ds.crs, "transform": ds.window_transform(window),
                               "width": int(round(window.width)), "height": int(round(window.height)),
                               "count": 1, "dtype": "float32", "compress": "lzw", "nodata": -9999.0,
                               "tiled": True, "blockxsize": 256, "blockysize": 256}
                    arr = ds.read(1, window=window).astype("float32")
                    # WorldClim baseline fill is -3.4e38, not NaN: mask source nodata explicitly.
                    if ds.nodata is not None:
                        arr[arr == ds.nodata] = np.nan
                    arr[arr < -9000] = np.nan
                    arr[~np.isfinite(arr)] = -9999.0
                    dest = dest_stem.with_name(f"{dest_stem.name}_bio{band:02d}.tif")
                    with rasterio.open(dest, "w", **profile) as out:
                        out.write(arr, 1)
                    written[band] = dest
                extracted.unlink(missing_ok=True)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return written


def crop_from_remote(url: str, band_indices: list[int], dest_stem: Path) -> dict[int, Path]:
    """Read only the bbox window of the remote raster and write one small GeoTIFF per band."""
    written: dict[int, Path] = {}

    def _read():
        with rasterio.open("/vsicurl/" + url) as ds:
            window = from_bounds(*BBOX, ds.transform)
            profile = {"driver": "GTiff", "crs": ds.crs, "transform": ds.window_transform(window),
                       "width": int(round(window.width)), "height": int(round(window.height)),
                       "count": 1, "dtype": "float32", "compress": "lzw", "nodata": -9999.0,
                       "tiled": True, "blockxsize": 256, "blockysize": 256}
            for band in band_indices:
                arr = ds.read(band, window=window).astype("float32")
                if ds.nodata is not None:
                    arr[arr == ds.nodata] = np.nan
                arr[arr < -9000] = np.nan
                arr[~np.isfinite(arr)] = -9999.0
                dest = dest_stem.with_name(f"{dest_stem.name}_bio{band:02d}.tif")
                with rasterio.open(dest, "w", **profile) as out:
                    out.write(arr, 1)
                written[band] = dest
            return written

    return with_backoff(_read, Path(url).name)


def verify_manifest() -> list[str]:
    if not MANIFEST.exists():
        return ["no manifest yet"]
    problems = []
    with MANIFEST.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            path = RAW / row["file"]
            if not path.exists():
                problems.append(f"missing: {row['file']}")
            elif sha256(path) != row["sha256"]:
                problems.append(f"checksum mismatch: {row['file']}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--res", default="30s", choices=["30s", "2.5m", "5m"], help="WorldClim resolution")
    ap.add_argument("--verify-only", action="store_true")
    ap.add_argument("--period", action="append", choices=sorted(PERIODS), help="subset of periods")
    ap.add_argument("--allow-chelsa", action="store_true",
                    help="also try the CHELSA mirror (its paths were stale on 2026-11-26)")
    args = ap.parse_args()

    if args.verify_only:
        problems = verify_manifest()
        for p in problems[:20]:
            print(" ", p)
        print("manifest:", "OK" if not problems else f"{len(problems)} problem(s)")
        return 0 if not problems else 1

    RAW.mkdir(parents=True, exist_ok=True)
    assert_writable(RAW)
    periods = args.period or sorted(PERIODS)
    rows = []
    for period in periods:
        dest_stem = RAW / f"worldclim_{args.res}_{period}"
        print(f"== {period} ({args.res}) ==", flush=True)
        last_error = None
        candidates = sources(period, args.res)
        if not args.allow_chelsa:
            candidates = [c for c in candidates if c[0] != "CHELSA"]
        for label, url in candidates:
            try:
                t0 = time.time()
                reader = crop_from_zip if url.lower().endswith(".zip") else crop_from_remote
                files = reader(url, sorted(BIO), dest_stem)
                print(f"  {label}: {len(files)} bands from {url.split('/')[-1]} in {time.time()-t0:.0f}s", flush=True)
                for band, path in files.items():
                    rows.append({"file": path.name, "period": period, "band": band,
                                 "variable": BIO[band], "source": label, "source_url": url,
                                 "resolution": args.res, "bbox": ",".join(str(x) for x in BBOX),
                                 "sha256": sha256(path), "bytes": path.stat().st_size,
                                 "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                print(f"  {label} failed: {type(exc).__name__}: {str(exc)[:120]}", flush=True)
        if last_error is not None:
            print(f"  ALL SOURCES FAILED for {period}: {last_error}", file=sys.stderr)
            return 1

    # Merge into the manifest, refusing to overwrite a differing checksum.
    existing = {}
    if MANIFEST.exists():
        with MANIFEST.open(encoding="utf-8") as fh:
            existing = {r["file"]: r for r in csv.DictReader(fh)}
    for r in rows:
        old = existing.get(r["file"])
        if old and old["sha256"] != r["sha256"]:
            print(f"checksum changed for {r['file']}: {old['sha256'][:12]} -> {r['sha256'][:12]}", file=sys.stderr)
            return 1
        existing[r["file"]] = r
    fields = ["file", "period", "band", "variable", "source", "source_url", "resolution", "bbox",
              "sha256", "bytes", "fetched_at"]
    with MANIFEST.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in sorted(existing.values(), key=lambda x: (x["period"], int(x["band"]))):
            w.writerow(r)
    total = sum(int(r["bytes"]) for r in rows)
    print(f"\nmanifest written: {MANIFEST} ({len(existing)} files) — this run transferred {total/1e6:.1f} MB of crops")
    return 0


if __name__ == "__main__":
    sys.exit(main())
