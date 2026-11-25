#!/usr/bin/env python3
"""Macroecology layer 1: reproduce the Shrestha et al. 2025 residual analysis
at Mekong scale, plus the realm slope comparison.

Shrestha et al. 2025, Current Biology, doi:10.1016/j.cub.2025.09.050.
Reused data: data/raw/shrestha2025/data.csv (369 WGSRPD L3 botanical
countries). Reused code: their mixed-effect_model.R / diff_slope.R /
residual_histogram.R (scripts kept alongside in data/raw/shrestha2025/).

Model reproduced here: med_rich ~ vas_rich, ordinary least squares over all
botanical countries except Antarctica and Oceania (their exclusion).
Significance follows their residual_histogram.R: |residual| > 1.96 * sd
(two-tailed p < 0.05 under normality); the CSV also reports the normal
approximation of the two-tailed p. All computations are stdlib-only so the
build stays reproducible in the pinned Python 3.14.7 environment.

Outputs (data/processed/macroecology/):
  mekong_residual_analysis.csv
  slope_comparison.csv
  mekong_leverage.csv
  reproduction_validation.json  (QA gate 1: our residuals vs their column)
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "raw" / "shrestha2025" / "data.csv"
OUT = ROOT / "data" / "processed" / "macroecology"

EXCLUDED_REALMS = {"Antarctica", "Oceania"}

# Mekong-relevant WGSRPD L3 units (China South-Central holds Yunnan;
# China Southeast holds Guangxi; Hainan is out of scope). Cambodia is CBD
# in WGSRPD (KHM is its ISO country code, not its botanical-country code).
MEKONG_CODES = ("CBD", "LAO", "MYA", "THA", "VIE", "CHC", "CHS")


def load() -> list[dict]:
    with open(SRC, newline="", encoding="latin-1") as f:
        rows = [r for r in csv.DictReader(f)]
    for r in rows:
        for k in ("med_rich", "vas_rich", "Human", "glottolog", "Area",
                  "Clim.PC1", "Clim.PC2", "MAT_ANO", "MAT_STD", "residuals"):
            try:
                r[k] = float(r[k])
            except (ValueError, TypeError):
                r[k] = float("nan")
    return [r for r in rows if r["realm"] not in EXCLUDED_REALMS
            and not (math.isnan(r["med_rich"]) or math.isnan(r["vas_rich"]))]


def ols(xs, ys):
    n = len(xs)
    xm, ym = sum(xs) / n, sum(ys) / n
    sxx = sum((x - xm) ** 2 for x in xs)
    sxy = sum((x - xm) * (y - ym) for x, y in zip(xs, ys))
    slope = sxy / sxx
    intercept = ym - slope * xm
    fitted = [intercept + slope * x for x in xs]
    resid = [y - f for y, f in zip(ys, fitted)]
    sse = sum(r * r for r in resid)
    # residual standard error under a simple linear model
    sigma2 = sse / (n - 2)
    se_slope = math.sqrt(sigma2 / sxx)
    return {
        "n": n, "intercept": intercept, "slope": slope, "se_slope": se_slope,
        "fitted": fitted, "residuals": resid, "sxx": sxx,
    }


def main() -> int:
    rows = load()
    xs = [r["vas_rich"] for r in rows]
    ys = [r["med_rich"] for r in rows]
    model = ols(xs, ys)
    resid_sd = math.sqrt(sum(r * r for r in model["residuals"]) / (len(rows) - 1))

    mekong = []
    for r in rows:
        if r["TDWG"] not in MEKONG_CODES:
            continue
        i = rows.index(r)
        z = model["residuals"][i] / resid_sd
        p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
        if model["residuals"][i] > 0 and p < 0.05:
            cls = "hotspot"
        elif model["residuals"][i] < 0 and p < 0.05:
            cls = "coldspot"
        else:
            cls = "not_significant"
        mekong.append({
            "botanical_country": r["LEVEL3_NAME"],
            "wgsrpd_code": r["TDWG"],
            "vascular_diversity": r["vas_rich"],
            "medicinal_diversity": r["med_rich"],
            "predicted_medicinal_diversity": round(model["fitted"][i], 1),
            "residual": round(model["residuals"][i], 1),
            "residual_p_value": round(p, 5),
            "classification": cls,
        })

    # realm slopes (their diff_slope.R: lm(med_rich ~ vas_rich) per realm)
    realms = {}
    for realm in sorted({r["realm"] for r in rows}):
        sub = [r for r in rows if r["realm"] == realm]
        m = ols([r["vas_rich"] for r in sub], [r["med_rich"] for r in sub])
        realms[realm] = {
            "realm": realm, "n": m["n"], "slope": round(m["slope"], 5),
            "se": round(m["se_slope"], 5),
            "ci_low": round(m["slope"] - 1.96 * m["se_slope"], 5),
            "ci_high": round(m["slope"] + 1.96 * m["se_slope"], 5),
            "intercept": round(m["intercept"], 2),
        }

    # Mekong units' position within the Indomalaya line (leverage)
    indo = [r for r in rows if r["realm"] == "Indomalaya"]
    im = ols([r["vas_rich"] for r in indo], [r["med_rich"] for r in indo])
    leverage_rows = []
    for r in mekong:
        rec = next((x for x in indo if x["TDWG"] == r["wgsrpd_code"]), None)
        if rec is None:
            continue
        xi = rec["vas_rich"]
        hat = 1 / im["n"] + (xi - sum(x["vas_rich"] for x in indo) / im["n"]) ** 2 / im["sxx"]
        fitted = im["intercept"] + im["slope"] * xi
        leverage_rows.append({
            "botanical_country": r["botanical_country"],
            "wgsrpd_code": r["wgsrpd_code"],
            "vascular_diversity": xi,
            "medicinal_diversity": rec["med_rich"],
            "indomalaya_fitted": round(fitted, 1),
            "indomalaya_residual": round(rec["med_rich"] - fitted, 1),
            "leverage": round(hat, 5),
        })

    # QA gate 1: how well do our med~vas residuals reproduce their published
    # residuals column? (Their column may come from the richer mixed model;
    # report both correlations.)
    their = [r["residuals"] for r in rows]
    ours = model["residuals"]
    def corr(a, b):
        n = len(a)
        ma, mb = sum(a) / n, sum(b) / n
        va = sum((x - ma) ** 2 for x in a)
        vb = sum((x - mb) ** 2 for x in b)
        cv = sum((x - ma) * (y - mb) for x, y in zip(a, b))
        return cv / math.sqrt(va * vb)
    # also compare with residuals of the full fixed-effects lm (all predictors,
    # complete cases only - their mixed model ran on na.omit rows)
    keys = ["Clim.PC1", "Clim.PC2", "MAT_ANO", "MAT_STD", "Human", "vas_rich", "glottolog"]
    comp = [(i, r) for i, r in enumerate(rows)
            if all(not math.isnan(r[k]) for k in keys)]
    idx = [i for i, _ in comp]
    X = [[comp[j][1][k] for k in keys] + [1.0] for j in range(len(comp))]
    yc = [ys[i] for i in idx]
    A = [[sum(X[i][j] * X[i][k] for i in range(len(comp))) for k in range(len(keys) + 1)]
         for j in range(len(keys) + 1)]
    b = [sum(X[i][j] * yc[i] for i in range(len(comp))) for j in range(len(keys) + 1)]
    # solve A beta = b
    n_ = len(b)
    M = [A[i][:] + [b[i]] for i in range(n_)]
    for col in range(n_):
        piv = max(range(col, n_), key=lambda r_: abs(M[r_][col]))
        M[col], M[piv] = M[piv], M[col]
        pv = M[col][col]
        for j in range(col, n_ + 1):
            M[col][j] /= pv
        for r_ in range(n_):
            if r_ != col and M[r_][col]:
                f = M[r_][col]
                for j in range(col, n_ + 1):
                    M[r_][j] -= f * M[col][j]
    beta = [M[i][n_] for i in range(n_)]
    full_resid = [yc[i] - sum(X[i][j] * beta[j] for j in range(n_)) for i in range(len(comp))]
    their_c = [their[i] for i in idx]

    validation = {
        "n_countries_modelled": len(rows),
        "corr_med_vas_residuals_vs_published": round(corr(ours, their), 6),
        "corr_full_lm_residuals_vs_published": round(corr(full_resid, their_c), 6),
        "mean_abs_diff_med_vas_vs_published": round(
            sum(abs(a - b_) for a, b_ in zip(ours, their)) / len(rows), 3),
        "indomalaya_slope": realms["Indomalaya"]["slope"],
        "indomalaya_is_steepest": realms["Indomalaya"]["slope"]
        == max(v["slope"] for v in realms.values()),
        "published_notes": "their residuals column in data.csv; closest match wins",
    }

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "mekong_residual_analysis.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(mekong[0].keys()))
        w.writeheader()
        w.writerows(mekong)
    with open(OUT / "slope_comparison.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(realms["Indomalaya"].keys()))
        w.writeheader()
        w.writerows(realms.values())
    with open(OUT / "mekong_leverage.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(leverage_rows[0].keys()))
        w.writeheader()
        w.writerows(leverage_rows)
    with open(OUT / "reproduction_validation.json", "w") as f:
        json.dump(validation, f, indent=2)

    for r in mekong:
        print(f'{r["wgsrpd_code"]:4s} {r["botanical_country"]:22s} '
              f'vas={r["vascular_diversity"]:5.0f} med={r["medicinal_diversity"]:5.0f} '
              f'pred={r["predicted_medicinal_diversity"]:6.0f} '
              f'resid={r["residual"]:7.1f} p={r["residual_p_value"]:.3f} {r["classification"]}')
    print("\nrealm slopes (med ~ vas):")
    for realm in sorted(realms, key=lambda k: -realms[k]["slope"]):
        v = realms[realm]
        print(f'  {realm:14s} slope={v["slope"]:.4f} [{v["ci_low"]:.4f}, {v["ci_high"]:.4f}] n={v["n"]}')
    print("\nvalidation:", json.dumps(validation, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
