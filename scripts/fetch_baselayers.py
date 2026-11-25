#!/usr/bin/env python3
"""Fetch and convert the atlas geospatial baselayers.

Basin boundary (published, CC-BY 4.0)
  Zenodo record 7622998, file _SupplementalData.zip -> Shapefile_Mekong_Boundary.*
  96 catchment polygons in EPSG:4326, dissolved into one boundary.
  Chain: SRTM 3 arc-second basin mask -> Dang et al. (2022), Sci Total Environ
  831:154833 -> Tiwari et al. Zenodo data paper deposit (DOI 10.5281/zenodo.7622998).

River centreline, fallback (published, public domain)
  Natural Earth 1:10m rivers and lake centrelines, feature "Mekong".

River centreline, primary (NOT published)
  WWF-Laos feature service on ArcGIS Online. No licence is stated for this
  layer, so it is only fetched here to be validated and fingerprinted; the
  website renders it directly from the publisher's service at run time and the
  Natural Earth line is the committed fallback.

Usage: python scripts/fetch_baselayers.py
"""
from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import shapefile
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "baselayers"
GEO = ROOT / "data" / "geo"

ZENODO_DOI = "10.5281/zenodo.7622998"
ZENODO_URL = f"https://zenodo.org/records/7622998/files/_SupplementalData.zip?download=1"
ZENODO_SHA256 = "a3417e9298d42d217293ff4e4f170b081ae9141a674143ecf3095260a9e8bfae"
ZENODO_CITATION = ("Tiwari, A. et al. A synthesis of hydroclimatic, ecological, and socioeconomic data "
                   "for transdisciplinary research in the Mekong. Zenodo. "
                   f"https://doi.org/{ZENODO_DOI}")
BASIN_DERIVED_FROM = ("Dang, H., Pokhrel, Y., Shin, S., Stelly, J., Ahlquist, D., & Du Bui, D. (2022). "
                      "Hydrologic balance and inundation dynamics of Southeast Asia's largest inland lake "
                      "altered by hydropower dams in the Mekong River basin. "
                      "Science of The Total Environment, 831, 154833.")

DISPLAY_TOLERANCE_DEG = 0.001
NE_URL = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
          "ne_10m_rivers_lake_centerlines.geojson")
NE_VERSION_TAG = "v5.1.2"
NE_URL = NE_URL.replace("/master/", f"/{NE_VERSION_TAG}/")
NE_COUNTRIES_URL = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
                    "ne_110m_admin_0_countries.geojson")

WWF_ITEM_ID = "dcfa38b28bc247dca5ee94828eed1df6"
WWF_QUERY = ("https://services1.arcgis.com/RTK5Unh1Z71JKIiR/ArcGIS/rest/services/Mekong_River_/FeatureServer/0/"
             "query?where=1%3D1&outFields=*&f=geojson")

UA = "mekong-medicinal-plant-atlas/1.0 (https://github.com/subhadipban-lgtm/mekong-medicinal-plant-atlas)"


def download(url: str, dest: Path) -> None:
    if dest.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=180) as r, dest.open("wb") as fh:
        while chunk := r.read(1 << 20):
            fh.write(chunk)


def rounded(obj, nd: int = 5):
    if isinstance(obj, (list, tuple)):
        return [rounded(x, nd) for x in obj]
    return round(float(obj), nd)


def geojson_of(geom, props: dict, extra: dict) -> dict:
    gj = mapping(geom)
    return {"type": "FeatureCollection", **extra, "features": [
        {"type": "Feature", "properties": props,
         "geometry": {"type": gj["type"], "coordinates": rounded(gj["coordinates"])}}]}


def build_basin() -> dict:
    zpath = RAW / "zenodo7622998_SupplementalData.zip"
    download(ZENODO_URL, zpath)
    digest = hashlib.sha256(zpath.read_bytes()).hexdigest()
    if digest != ZENODO_SHA256:
        sys.exit(f"Zenodo archive checksum changed: {digest} (expected {ZENODO_SHA256}); review before reuse")
    shp_dir = RAW / "mekong_boundary"
    shp_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zpath) as zf:
        for member in zf.namelist():
            if "/Shapefile/Shapefile_Mekong_Boundary." in member:
                zf.extract(member, shp_dir)
    shp = next(shp_dir.rglob("Shapefile_Mekong_Boundary.shp"))
    reader = shapefile.Reader(str(shp))
    prj = shp.with_suffix(".prj").read_text()
    if "WGS_1984" not in prj or "Degree" not in prj:
        sys.exit(f"unexpected projection: {prj}")
    polys = [shape(s.__geo_interface__) for s in reader.shapes()]
    basin = unary_union(polys)
    n_in = sum(len(s.points) for s in reader.shapes())
    out = geojson_of(basin, {"id": "mekong_basin"}, {
        "name": "mekong_basin",
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "attribution": f"Mekong River basin boundary: {ZENODO_CITATION} (CC-BY 4.0). Derived from {BASIN_DERIVED_FROM}",
        "source_doi": ZENODO_DOI,
        "crs": "EPSG:4326 (WGS 84)",
    })
    (GEO / "mekong_basin.geojson").write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    # Display copy: topology-preserving simplification, visually indistinguishable at atlas scale.
    display = basin.simplify(DISPLAY_TOLERANCE_DEG, preserve_topology=True)
    out_display = geojson_of(display, {"id": "mekong_basin"}, {
        "name": "mekong_basin_display",
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "attribution": out["attribution"],
        "derived_from": "mekong_basin.geojson",
        "simplification_tolerance_deg": DISPLAY_TOLERANCE_DEG,
    })
    (GEO / "mekong_basin_display.geojson").write_text(json.dumps(out_display, separators=(",", ":")), encoding="utf-8")
    b = basin.bounds
    return {"input_polygons": len(polys), "input_vertices": n_in,
            "output_vertices": sum(len(ring.coords) for poly in (basin.geoms if basin.geom_type == "MultiPolygon" else [basin])
                                   for ring in [poly.exterior, *poly.interiors]),
            "geometry_type": basin.geom_type,
            "bbox": [round(b[0], 3), round(b[1], 3), round(b[2], 3), round(b[3], 3)],
            "area_sq_deg": round(basin.area, 3)}


def build_river_fallback() -> dict:
    nepath = RAW / f"ne_10m_rivers_lake_centerlines_{NE_VERSION_TAG}.geojson"
    download(NE_URL, nepath)
    ne = json.loads(nepath.read_text(encoding="utf-8"))
    # Natural Earth splits the river into a lower "Mekong" and an upper "Lancang" feature.
    feats = [f for f in ne["features"]
             if f["properties"].get("name_en") == "Mekong" or f["properties"].get("name") == "Mekong"]
    if len(feats) != 2:
        sys.exit(f"expected two Natural Earth features (Mekong + Lancang), found {len(feats)}")
    geom = unary_union([shape(f["geometry"]) for f in feats])
    out = geojson_of(geom, {"name": "Mekong"}, {
        "name": "mekong_river_naturalearth",
        "license": "Public domain (https://www.naturalearthdata.com/about/terms-of-use/)",
        "attribution": f"Mekong River centreline: Natural Earth 1:10m rivers and lake centerlines, {NE_VERSION_TAG} (public domain)",
        "source_url": NE_URL, "natural_earth_version": NE_VERSION_TAG,
    })
    (GEO / "mekong_river_naturalearth.geojson").write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    coords = [c for line in (geom.geoms if geom.geom_type == "MultiLineString" else [geom]) for c in line.coords]
    return {"features_merged": [f["properties"].get("name") for f in feats],
            "vertices": len(coords), "length_sq_deg": round(geom.length, 3),
            "bbox": [round(v, 3) for v in geom.bounds],
            "source_sha256": hashlib.sha256(nepath.read_bytes()).hexdigest()}


def build_country_outlines(ne_version_tag: str) -> dict:
    """Unfilled outlines of every country touching the region, for orientation only.

    Countries are deliberately not shaded: the atlas reports basin presence, and shading a whole
    country would claim its records lie inside the basin when most do not.
    """
    nepath = RAW / f"ne_110m_admin_0_countries_{ne_version_tag}.geojson"
    download(NE_COUNTRIES_URL.replace("/master/", f"/{ne_version_tag}/"), nepath)
    kept = []
    for f in json.loads(nepath.read_text(encoding="utf-8"))["features"]:
        g = shape(f["geometry"])
        b = g.bounds
        if b[2] < 88 or b[0] > 116 or b[3] < 3 or b[1] > 37:
            continue
        props = f["properties"]
        f["properties"] = {"name": props.get("NAME"), "iso_a3": props.get("ADM0_A3")}
        kept.append(f)
    out = {"type": "FeatureCollection", "name": "countries_outline",
           "license": "Public domain (https://www.naturalearthdata.com/about/terms-of-use/)",
           "attribution": f"Country outlines: Natural Earth 1:110m admin_0 countries, {ne_version_tag} (public domain)",
           "features": kept}
    (GEO / "countries_outline.geojson").write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    return {"countries": len(kept), "source_sha256": hashlib.sha256(nepath.read_bytes()).hexdigest()}


def fingerprint_wwf() -> dict:
    """Fetch the WWF centreline to validate it; never copied into the published tree."""
    path = RAW / "mekong_river_wwf_arcgis.geojson"
    try:
        download(WWF_QUERY, path)
        gj = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # the atlas does not depend on this layer; record and continue
        return {"status": "unavailable", "error": str(e)}
    geoms = [shape(f["geometry"]) for f in gj["features"]]
    line = unary_union(geoms)
    coords = [c for line_ in (line.geoms if hasattr(line, "geoms") else [line]) for c in line_.coords]
    return {
        "status": "ok",
        "service_item_id": WWF_ITEM_ID,
        "query_url": WWF_QUERY,
        "owner_display": "WWF-Laos account on ArcGIS Online",
        "licence": "not stated",
        "redistribution": "no - rendered from the publisher's service at run time only",
        "features": len(gj["features"]), "vertices": len(coords),
        "length_sq_deg": round(line.length, 3),
        "bbox": [round(v, 3) for v in line.bounds],
        "response_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def main() -> int:
    GEO.mkdir(parents=True, exist_ok=True)
    basin = build_basin()
    river_ne = build_river_fallback()
    outlines = build_country_outlines(NE_VERSION_TAG)
    river_wwf = fingerprint_wwf()
    prov = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mekong_basin.geojson": {**basin, "license": "CC-BY-4.0", "doi": ZENODO_DOI,
                                 "citation": ZENODO_CITATION, "derived_from": BASIN_DERIVED_FROM,
                                 "source_file": "data/raw/baselayers/zenodo7622998_SupplementalData.zip",
                                 "source_sha256": ZENODO_SHA256},
        "mekong_river_naturalearth.geojson": river_ne,
        "countries_outline.geojson": outlines,
        "mekong_river_wwf_arcgis (runtime only, not published)": river_wwf,
    }
    (GEO / "_layer_provenance.json").write_text(json.dumps(prov, indent=2), encoding="utf-8")
    for k, v in prov.items():
        if k != "generatedAt":
            print(f"{k}: {json.dumps(v)[:230]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
