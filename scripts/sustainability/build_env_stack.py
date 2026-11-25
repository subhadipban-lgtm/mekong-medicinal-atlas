#!/usr/bin/env python3
"""Build the harmonised environmental stack on the 5 km basin grid.

Inputs (all local, in the repository):
  data/raw/worldclim/worldclim_2.5m_{baseline,ssp245,ssp585}_bio{01,02,04,12,15}.tif
  data/raw/zenodo7803254/Wetlands/.../TROP-SUBTROP_WetlandV3b_2016_CIFOR_Mekong.tif
  data/raw/zenodo7803254/IrrigatedArea/.../gmia_v5_aei_pct.tif
  data/raw/zenodo7622998/lulc/LULC/C3S-LC-L4-LCCS-Map-300m-P1Y-2020-v2.1.1.tif
  data/processed/basin_grid.tif   (grid definition)

Outputs:
  data/processed/env_stack_5000m.tif   one band per variable (see BANDS)
  data/processed/env_stack_bands.csv   band metadata: variable, units, resampling, source

Resampling follows docs/harmonization_methods.md: bilinear for continuous climate fields and
fractions, mode for categorical land cover. Everything is reprojected into the basin-tuned Albers
equal-area CRS of the grid, so no resampling ever happens in a geographic CRS.

Water availability substitutes for GLEAM
----------------------------------------
The GLEAM evapotranspiration and soil-moisture archives (Zenodo 7803254 ET.zip, SoilMoiture.zip)
were never retrievable, so PET is estimated with the Hargreaves equation from WorldClim
temperature (bio1 mean temperature, bio2 mean diurnal range) and aridity is precipitation minus PET.
That is stated in docs/cultivation_methods.md as a documented substitution.

Usage: python scripts/sustainability/build_env_stack.py
"""
from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import atlas_lib as L  # noqa: E402

RAW = L.RAW
WC = RAW / "worldclim"
WET = RAW / "zenodo7803254" / "Wetlands" / "Wetlands" / "CIFOR_Gumbricht_2017" / "TROP-SUBTROP_WetlandV3b_2016_CIFOR_Mekong.tif"
IRR = (RAW / "zenodo7803254" / "IrrigatedArea" / "IrrigatedArea" / "FAO" /
       "1. Area equipped for irrigation expressed as percentage of total area" / "gmia_v5_aei_pct.tif")
LULC = (RAW / "zenodo7622998" / "lulc" / "LULC" /
        "C3S-LC-L4-LCCS-Map-300m-P1Y-2020-v2.1.1.tif")


def grid_profile():
    with rasterio.open(L.PROCESSED / "basin_grid.tif") as ds:
        return ds.profile.copy(), ds.transform, ds.width, ds.height, ds.crs, ds.read(1)


def resample(path: Path, transform, width, height, crs, method: Resampling) -> np.ndarray:
    out = np.full((height, width), np.nan, dtype="float32")
    with rasterio.open(path) as src:
        reproject(source=rasterio.band(src, 1), destination=out, src_transform=src.transform,
                  src_crs=src.crs, dst_transform=transform, dst_crs=crs,
                  resampling=method, src_nodata=src.nodata, dst_nodata=np.nan)
    return out


def hargreaves_pet(bio1: np.ndarray, bio2: np.ndarray, lat: np.ndarray) -> np.ndarray:
    """Hargreaves PET (mm/day averaged to annual mm) from mean temperature and diurnal range.

    Ra (extraterrestrial radiation) is computed per row latitude; the factor 0.0023 and the +17.8
    offset are Hargreaves & Samani (1985). Reported as annual total (mm/yr).
    """
    ra = np.zeros_like(lat)
    dr = 1 + 0.033 * math.cos(2 * math.pi * 200 / 365)
    dec = 0.409 * math.sin(2 * math.pi * 200 / 365 - 1.39)
    for i in range(lat.shape[0]):
        p = np.radians(lat[i, :])
        ws = np.arccos(np.clip(-np.tan(p) * math.tan(dec), -1, 1))
        ra[i] = (24 * 60 / math.pi) * 0.0820 * dr * (ws * np.sin(p) * math.sin(dec)
                                                     + np.cos(p) * math.cos(dec) * np.sin(ws))
    pet_day = 0.0023 * ra * (bio1 + 17.8) * np.sqrt(np.maximum(bio2, 0.1))
    return np.maximum(pet_day, 0) * 365.0


def main() -> int:
    profile, transform, width, height, crs, mask = grid_profile()
    inbasin = mask == 1
    cells = L.read_csv(L.PROCESSED / "grid_cells.csv")
    lat = np.full((height, width), np.nan, dtype="float32")
    lon = np.full((height, width), np.nan, dtype="float32")
    for c in cells:
        r, cc = int(c["row"]), int(c["col"])
        lat[r, cc] = float(c["center_lat"])
        lon[r, cc] = float(c["center_lon"])

    bands: list[tuple[str, str, str, np.ndarray, str]] = []
    for period in ("baseline", "ssp245", "ssp585"):
        for band, name in ((1, "bio01"), (2, "bio02"), (4, "bio04"), (5, "bio05"), (6, "bio06"),
                           (12, "bio12"), (13, "bio13"), (14, "bio14"), (15, "bio15"),
                           (16, "bio16"), (17, "bio17")):
            path = WC / f"worldclim_2.5m_{period}_bio{band:02d}.tif"
            arr = resample(path, transform, width, height, crs, Resampling.bilinear)
            arr[~inbasin] = np.nan
            units = {"bio01": "degC", "bio02": "degC", "bio04": "dimensionless (CV x100)",
                     "bio05": "degC", "bio06": "degC", "bio12": "mm/yr", "bio13": "mm",
                     "bio14": "mm", "bio15": "dimensionless (CV)", "bio16": "mm",
                     "bio17": "mm"}[name]
            bands.append((f"{name}_{period}", units, "bilinear", arr,
                          f"WorldClim 2.1 {period} (2.5 arc-min) bio{band}"))
            if period == "baseline" and name == "bio01":
                b1 = arr
            if period == "baseline" and name == "bio02":
                b2 = arr
            if period == "baseline" and name == "bio12":
                b12 = arr

    pet = hargreaves_pet(np.nan_to_num(b1, nan=20.0), np.nan_to_num(b2, nan=8.0), np.nan_to_num(lat, nan=20.0))
    pet[~inbasin] = np.nan
    bands.append(("pet_annual_baseline", "mm/yr", "derived", pet, "Hargreaves (1985) from WorldClim bio01+bio02"))
    aridity = b12 - pet
    aridity[~inbasin] = np.nan
    bands.append(("precip_minus_pet_baseline", "mm/yr", "derived", aridity, "bio12 - PET"))

    # Wetland class codes averaged directly would be meaningless; resample a presence mask instead
    # so the value is the fraction of each 5 km cell under wetland.
    with rasterio.open(WET) as src:
        codes = src.read(1)
        presence = ((codes > 0) & (codes != src.nodata)).astype("float32")
        wet_profile = src.profile
    wet = np.full((height, width), np.nan, dtype="float32")
    reproject(source=presence, destination=wet, src_transform=wet_profile["transform"],
              src_crs=wet_profile["crs"], dst_transform=transform, dst_crs=crs,
              resampling=Resampling.average, src_nodata=None, dst_nodata=np.nan)
    wet = np.where(np.isfinite(wet), wet, 0.0)
    wet[~inbasin] = np.nan
    bands.append(("wetland_fraction_baseline", "fraction 0-1", "average of presence mask", wet,
                  "CIFOR wetland V3b 2016"))

    irr = resample(IRR, transform, width, height, crs, Resampling.bilinear)
    irr[~inbasin] = np.nan
    bands.append(("irrigated_pct_baseline", "percent", "bilinear", irr, "FAO GMIA v5"))

    lc = resample(LULC, transform, width, height, crs, Resampling.mode)
    lc[~inbasin] = np.nan
    bands.append(("landcover_class_2020", "ESA CCI class code", "mode", lc, "C3S-LCCS 2020 300 m"))

    out_profile = dict(profile)
    out_profile.update(count=len(bands), dtype="float32", compress="lzw", nodata=np.nan)
    with rasterio.open(L.PROCESSED / "env_stack_5000m.tif", "w", **out_profile) as ds:
        for i, (_name, _u, _r, arr, _src) in enumerate(bands, start=1):
            ds.write(arr.astype("float32"), i)
            ds.set_band_description(i, _name)

    with (L.PROCESSED / "env_stack_bands.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["band", "variable", "units", "resampling", "source"])
        for i, (name, units, method, _arr, src) in enumerate(bands, start=1):
            w.writerow([i, name, units, method, src])

    print(f"env stack: {len(bands)} bands on {width}x{height} grid, {int(inbasin.sum())} in-basin cells")
    for i, (name, _u, _m, arr, _s) in enumerate(bands, start=1):
        v = arr[np.isfinite(arr)]
        print(f"  {i:2d} {name:34} n={v.size:6d} mean={v.mean():10.2f} min={v.min():9.2f} max={v.max():9.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
