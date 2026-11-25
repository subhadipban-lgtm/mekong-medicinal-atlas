#!/usr/bin/env python3
"""Macroecology map layers (Shrestha reuse + Glottolog context).

Writes data/geo/:
  human_occupancy_mekong.geojson   WGSRPD L3 polygons x Shrestha `Human`
  global_residual_mekong.geojson   WGSRPD L3 polygons x residual classification
  language_diversity_mekong.geojson admin-1 polygons x Glottolog language richness

The occupancy layer reuses Shrestha et al.'s published `Human` column at its
published resolution (WGSRPD L3) - it is NOT re-derived (operating rule).
Language points come from Glottolog (Zenodo 24104033); richness is aggregated
to Natural Earth admin-1 polygons and shown as context only (Shrestha et al.
found only indirect effects of language diversity, mediated by climate).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from shapely.geometry import Point, shape

ROOT = Path(__file__).resolve().parents[1]
GEO = ROOT / "data" / "geo"
SRC = ROOT / "data" / "raw" / "shrestha2025" / "data.csv"
WGSRPD = ROOT / "data" / "raw" / "wgsrpd" / "level3.geojson"
GLOTTOLOG = ROOT / "data" / "raw" / "glottolog" / "languoid.csv"
ADMIN1 = ROOT / "data" / "raw" / "ne_admin1" / "ne_10m_admin_1_states_provinces.shp"
RESID = ROOT / "data" / "processed" / "macroecology" / "mekong_residual_analysis.csv"

MEKONG_CODES = {"CBD": "Cambodia", "LAO": "Laos", "MYA": "Myanmar", "THA": "Thailand",
                "VIE": "Vietnam", "CHC": "China South-Central", "CHS": "China Southeast"}
MEKONG_ISO = {"KH", "LA", "MM", "TH", "VN", "CN"}


def load_shrestha() -> dict[str, dict]:
    out = {}
    with open(SRC, newline="", encoding="latin-1") as f:
        for r in csv.DictReader(f):
            out[r["TDWG"]] = r
    return out


def occupancy_and_residual_layers() -> None:
    sh = load_shrestha()
    resid = {}
    with open(RESID, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            resid[r["wgsrpd_code"]] = r
    geojson = json.loads(WGSRPD.read_text(encoding="utf-8"))
    occ = {"type": "FeatureCollection", "features": []}
    glb = {"type": "FeatureCollection", "features": []}
    for feat in geojson["features"]:
        code = feat["properties"]["LEVEL3_COD"]
        if code not in MEKONG_CODES:
            continue
        rec = sh.get(code, {})
        human = rec.get("Human", "")
        try:
            human = round(float(human), 1) if human != "" else None
        except (ValueError, TypeError):
            human = None
        r = resid.get(code, {})
        props_o = {"code": code, "name": MEKONG_CODES[code], "human_occupancy_kyr": human}
        props_g = {
            "code": code, "name": MEKONG_CODES[code],
            "classification": r.get("classification", "no_data"),
            "residual": r.get("residual", ""), "residual_p_value": r.get("residual_p_value", ""),
            "vascular_diversity": r.get("vascular_diversity", ""),
            "medicinal_diversity": r.get("medicinal_diversity", ""),
        }
        feat_o = dict(feat)
        feat_o["properties"] = props_o
        feat_g = dict(feat)
        feat_g["properties"] = props_g
        occ["features"].append(feat_o)
        glb["features"].append(feat_g)
    GEO.mkdir(parents=True, exist_ok=True)
    (GEO / "human_occupancy_mekong.geojson").write_text(
        json.dumps(occ, separators=(",", ":")), encoding="utf-8")
    (GEO / "global_residual_mekong.geojson").write_text(
        json.dumps(glb, separators=(",", ":")), encoding="utf-8")
    print(f"occupancy + global-residual layers: {len(occ['features'])} L3 units")


def language_layer() -> None:
    import shapefile
    sf = shapefile.Reader(str(ADMIN1))
    fields = [f[0] for f in sf.fields[1:]]
    i_admin, i_name = fields.index("admin"), fields.index("name")
    polys = []
    for sr in sf.shapeRecords():
        admin = sr.record[i_admin]
        country = admin.lower()
        if not any(c in country for c in
                   ("cambodia", "laos", "myanmar", "thailand", "vietnam", "china")):
            continue
        geom = shape(sr.shape.__geo_interface__).simplify(0.02, preserve_topology=False)
        polys.append((sr.record[i_name], admin, geom))

    counts = {i: 0 for i in range(len(polys))}
    with open(GLOTTOLOG, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["level"] != "language":
                continue
            ids = r.get("country_ids") or ""
            if not any(c in ids.split() for c in ("CN", "MM", "LA", "TH", "VN", "KH")):
                continue
            try:
                lat, lon = float(r["latitude"]), float(r["longitude"])
            except (ValueError, TypeError):
                continue
            pt = Point(lon, lat)
            for i, (_, _, geom) in enumerate(polys):
                if geom.contains(pt):
                    counts[i] += 1
                    break

    feats = []
    for i, (name, admin, geom) in enumerate(polys):
        feats.append({
            "type": "Feature",
            "properties": {"name": name, "country": admin, "n_languages": counts[i]},
            "geometry": geom.__geo_interface__,
        })
    GEO.mkdir(parents=True, exist_ok=True)
    (GEO / "language_diversity_mekong.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":")),
        encoding="utf-8")
    n_pos = sum(1 for _, _, g in polys if True)
    lang_total = sum(counts.values())
    print(f"language layer: {n_pos} admin-1 polygons, {lang_total} language-point assignments")


def main() -> int:
    occupancy_and_residual_layers()
    language_layer()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
