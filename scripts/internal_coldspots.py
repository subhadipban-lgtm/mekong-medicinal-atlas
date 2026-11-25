#!/usr/bin/env python3
"""Internal (sub-national) coldspot analysis - the atlas's novel extension.

Shrestha et al. identify hotspots/coldspots at botanical-country scale; the
atlas has occurrence data at province scale. Here the same medicinal ~
vascular model is fitted at admin-1 (GBIF stateProvince) scale:

  vascular_diversity  = GBIF vascular-plant species count per province
                        (data/raw/admin1_vascular.json, taxonKey=6 harvest)
  medicinal_diversity = distinct atlas taxa with occurrence records in the
                        province (documented medicinal flora)

Residuals classify provinces as hotspot/coldspot/not significant; the
cross-reference with the Shrestha human-occupancy layer (L3 resolution,
reused as published) flags coldspots in long-occupied areas as fieldwork
priorities: under-documentation is more plausible there than ecological
scarcity.

Outputs:
  data/processed/macroecology/mekong_internal_coldspots.csv
  data/geo/internal_coldspots_mekong.geojson (Natural Earth admin-1 join)
"""
from __future__ import annotations

import csv
import json
import math
import unicodedata
from pathlib import Path

from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[1]
VASC = ROOT / "data" / "raw" / "admin1_vascular.json"
OCC = ROOT / "data" / "processed" / "occurrences.csv"
SRC = ROOT / "data" / "raw" / "shrestha2025" / "data.csv"
OUT = ROOT / "data" / "processed" / "macroecology"
GEO = ROOT / "data" / "geo"
ADMIN1 = ROOT / "data" / "raw" / "ne_admin1" / "ne_10m_admin_1_states_provinces.shp"

ISO2L3 = {"KH": "CBD", "LA": "LAO", "MM": "MYA", "TH": "THA", "VN": "VIE", "CN": "CHC"}

# GBIF stateProvince values that are regions/directions, not provinces
REGION_JUNK = {"northern", "northeastern", "north", "eastern", "central",
               "southern", "southeastern", "southwestern", "western",
               "northwestern", "peninsular", "peninsula", "tonkin", "annam",
               "cochinchina", "siam", "northeast", "southwest", "southeast",
               "unknown", "east", "west", "south", "northeasternregion",
               "southwesternregion", "northernregion", "centralregion"}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    for w in ("province", "prov.", "changwat", "prefecture", "city", "state",
              "special administrative region", "municipality", "capital",
              "metropolitan", "tinh", "thanh pho"):
        s = s.replace(w, "")
    return "".join(ch for ch in s if ch.isalnum())


def load_human() -> dict[str, float]:
    out = {}
    with open(SRC, newline="", encoding="latin-1") as f:
        for r in csv.DictReader(f):
            try:
                out[r["TDWG"]] = float(r["Human"])
            except (ValueError, TypeError):
                out[r["TDWG"]] = float("nan")
    return out


def main() -> int:
    if not VASC.exists():
        raise SystemExit("run scripts/harvest_admin1_vascular.py first")
    human = load_human()
    vasc = json.loads(VASC.read_text(encoding="utf-8"))

    # medicinal (atlas taxa) per province from occurrence records
    med: dict[tuple[str, str], set] = {}
    with open(OCC, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            key = (r["countryCode"] or "", norm(r["stateProvince"]))
            if not key[1]:
                continue
            name = (r.get("acceptedNameUsage") or r.get("scientificName") or "").strip()
            if name:
                med.setdefault(key, set()).add(name.lower())

    rows = []
    cn_scope = {"yunnan", "guangxi"}  # the atlas CN scope is Yunnan + Guangxi
    best: dict[tuple[str, str], dict] = {}
    for iso, provs in vasc["countries"].items():
        for p in provs:
            key = (iso, norm(p["province"]))
            if key[1] in REGION_JUNK:
                continue
            if p.get("species_truncated"):
                continue  # >10k species facets; censored, unusable for richness
            if iso == "CN" and key[1] not in cn_scope:
                continue
            cur = best.get(key)
            if cur is None or p["species"] > cur["vascular_diversity"]:
                best[key] = {
                    "country": iso, "admin1": p["province"],
                    "vascular_diversity": p["species"],
                    "medicinal_diversity": len(med.get(key, set())),
                    "human_occupancy": human.get(ISO2L3.get(iso, ""), None),
                }
    rows = list(best.values())

    # fit medicinal ~ vascular at admin-1 scale
    n = len(rows)
    xs = [r["vascular_diversity"] for r in rows]
    ys = [r["medicinal_diversity"] for r in rows]
    xm, ym = sum(xs) / n, sum(ys) / n
    sxx = sum((x - xm) ** 2 for x in xs)
    slope = sum((x - xm) * (y - ym) for x, y in zip(xs, ys)) / sxx
    intercept = ym - slope * xm
    resid = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
    resid_sd = math.sqrt(sum(r * r for r in resid) / (n - 1))
    occ_med = sorted(human.get(ISO2L3.get(c, ""), 0) for c in
                     {r["country"] for r in rows})
    occ_hi = occ_med[len(occ_med) // 2] if occ_med else 0

    for i, r in enumerate(rows):
        z = resid[i] / resid_sd
        p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
        if resid[i] > 0 and p < 0.05:
            cls = "hotspot"
        elif resid[i] < 0 and p < 0.05:
            cls = "coldspot"
        else:
            cls = "not_significant"
        r.update({
            "predicted_medicinal_diversity": round(intercept + slope * xs[i], 1),
            "residual": round(resid[i], 1),
            "residual_p_value": round(p, 5),
            "human_occupancy_class": ("high" if r["human_occupancy"] is not None
                                      and r["human_occupancy"] >= occ_hi else "low"),
            "classification": cls,
            "priority_for_fieldwork": bool(cls == "coldspot"
                                           and r["human_occupancy"] is not None
                                           and r["human_occupancy"] >= occ_hi),
        })

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "mekong_internal_coldspots.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # join to Natural Earth admin-1 polygons for the choropleth
    import shapefile
    sf = shapefile.Reader(str(ADMIN1))
    fields = [f[0] for f in sf.fields[1:]]
    i_admin, i_name = fields.index("admin"), fields.index("name")
    poly_key = {}
    for sr in sf.shapeRecords():
        admin = sr.record[i_admin].lower()
        if not any(c in admin for c in ("cambodia", "laos", "myanmar", "thailand",
                                        "vietnam", "china")):
            continue
        poly_key[norm(sr.record[i_name])] = (sr.record[i_name], sr.record[i_admin],
                                             shape(sr.shape.__geo_interface__))

    feats, unmatched = [], []
    for r in rows:
        k = norm(r["admin1"])
        hit = poly_key.get(k)
        if hit is None:  # containment fallback
            for pk, (nm, ad, geom) in poly_key.items():
                if k and (k in pk or pk in k):
                    hit = (nm, ad, geom)
                    break
        if hit is None:
            unmatched.append(r["admin1"])
            continue
        nm, ad, geom = hit
        feats.append({
            "type": "Feature",
            "properties": {k: r[k] for k in
                           ("admin1", "country", "vascular_diversity",
                            "medicinal_diversity", "residual", "residual_p_value",
                            "human_occupancy", "human_occupancy_class",
                            "classification", "priority_for_fieldwork")},
            "geometry": geom.__geo_interface__,
        })
    GEO.mkdir(parents=True, exist_ok=True)
    (GEO / "internal_coldspots_mekong.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":")),
        encoding="utf-8")

    n_cold = sum(1 for r in rows if r["classification"] == "coldspot")
    n_prio = sum(1 for r in rows if r["priority_for_fieldwork"])
    print(f"provinces: {n} | hotspots {sum(1 for r in rows if r['classification']=='hotspot')} "
          f"| coldspots {n_cold} | priority fieldwork {n_prio} | unmatched polys {len(unmatched)}")
    print(f"admin-1 model: med ~ {slope:.5f} * vas + {intercept:.1f}")
    if unmatched:
        print("unmatched (CSV only, no polygon):", unmatched[:10])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
