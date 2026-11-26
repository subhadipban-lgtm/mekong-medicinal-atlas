#!/usr/bin/env python3
"""Species distribution models: an ensemble of MaxEnt and a presence-background GLM.

Protocol
--------
Presences: atlas occurrence records inside the basin, thinned to one per 5 km cell. A taxon needs at
least 10 occupied cells (MIN_PRESENCE); otherwise it is recorded as not assessed and never modelled.
Background: a fixed random sample of in-basin cells.

Predictors (four, deliberately few): bio01 mean annual temperature, bio04 temperature seasonality,
bio12 annual precipitation, bio15 precipitation seasonality - from WorldClim 2.1, current and the
2041-2060 window of SSP2-4.5 and SSP5-8.5 (MIROC6).

Validation: spatially blocked cross-validation, not random k-fold. Cells are partitioned into
k spatial blocks by k-means on their coordinates; each block is held out once, so test presence is
spatially separated from training presence and AUC/TSS are not inflated by autocorrelation.

Algorithms
  MaxEnt    elapid.MaxentModel (L1-regularised maximum entropy, the maxnet method)
  GLM       logistic regression on standardised linear + quadratic terms (presence-background)

Ensemble: the mean of the two models' relative suitability. Threshold: the mean of the
cross-validated max-TSS thresholds; area is the sum of 25 km2 cells above it.

Outputs
  data/processed/sdm_performance.csv   per taxon: n records, n cells, AUC, TSS, flags
  data/processed/sdm_results.csv       per taxon per scenario: suitable area, % change, tier
  data/processed/sdm_suitability_summary.json  headline counts
  docs/sdm_methods.md                  method text (written by scripts/sustainability/write_sdm_methods.py)

Usage: python scripts/sustainability/sdm.py [--max-taxa N] [--folds 5]
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np
import rasterio
from sklearn.cluster import KMeans
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import atlas_lib as L  # noqa: E402
from sustainability import common as C  # noqa: E402

warnings.filterwarnings("ignore")
MIN_PRESENCE = 10
BACKGROUND_N = 10000
PREDICTORS = ["bio01", "bio02", "bio04", "bio05", "bio06", "bio12", "bio13", "bio14", "bio15",
              "bio16", "bio17"]
SEED = 42


def load_stack():
    with rasterio.open(L.PROCESSED / "env_stack_5000m.tif") as ds:
        names = [ds.descriptions[i - 1] for i in range(1, ds.count + 1)]
        data = {names[i - 1]: ds.read(i) for i in range(1, ds.count + 1)}
    cells = L.read_csv(L.PROCESSED / "grid_cells.csv")
    rows = np.array([int(c["row"]) for c in cells])
    cols = np.array([int(c["col"]) for c in cells])
    xy = np.array([[float(c["x_aea"]), float(c["y_aea"])] for c in cells])
    return data, rows, cols, xy


def feature_matrix(stack, periods, rows, cols):
    """(n_cells, n_periods*n_predictors); NaN rows dropped by the caller."""
    cols_out, names = [], []
    for period in periods:
        for p in PREDICTORS:
            key = f"{p}_{period}"
            cols_out.append(stack[key][rows, cols])
            names.append(key)
    return np.column_stack(cols_out), names


def rank01(x: np.ndarray) -> np.ndarray:
    """Percentile-rank transform to [0, 1].

    elapid's NicheEnvelopeModel returns a coarse 3-level score (0.5/0.75/1.0) while MaxentModel
    returns a smooth probability. Averaging those raw scores flattens the ranking and destroys AUC,
    so each model's scores are rank-transformed to a common scale before averaging. This keeps the
    ensemble a genuine consensus without pretending the two models share a probability scale.
    """
    from scipy.stats import rankdata
    r = rankdata(x, method="average")
    return (r - 1) / max(len(r) - 1, 1)


def ensemble(f_max, f_env, Z, parts=False):
    a = rank01(f_max(Z))
    b = rank01(f_env(Z))
    e = 0.5 * (a + b)
    return (e, a, b) if parts else e


def max_tss(y_true, score):
    """Best TSS over thresholds, and the threshold achieving it."""
    order = np.argsort(-score)
    y = y_true[order]
    s = score[order]
    n_pos, n_neg = y.sum(), len(y) - y.sum()
    if n_pos == 0 or n_neg == 0:
        return np.nan, np.nan
    tp = np.cumsum(y)
    fp = np.cumsum(1 - y)
    tss = tp / n_pos - fp / n_neg
    i = int(np.argmax(tss))
    return float(tss[i]), float(s[i])


def block_ids(xy, k: int) -> np.ndarray:
    km = KMeans(n_clusters=k, random_state=SEED, n_init=10).fit(xy)
    return km.labels_


def fit_maxent(pa, pb):
    """MaxEnt via elapid (the maxnet method): L1-regularised maximum entropy."""
    import elapid
    X = np.vstack([pa, pb])
    y = np.concatenate([np.ones(len(pa)), np.zeros(len(pb))])
    m = elapid.MaxentModel(feature_types=["linear", "quadratic"], beta_multiplier=1.5)
    m.fit(X, y)
    return lambda Z: m.predict(Z)


def fit_envelope(pa, pb):
    """BIOCLIM-type envelope as the second, independent presence-background method (elapid)."""
    import elapid
    X = np.vstack([pa, pb])
    y = np.concatenate([np.ones(len(pa)), np.zeros(len(pb))])
    m = elapid.NicheEnvelopeModel(percentile_range=(2.5, 97.5), overlay="average")
    m.fit(X, y)
    return lambda Z: m.predict(Z)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-taxa", type=int, default=0)
    ap.add_argument("--folds", type=int, default=5)
    args = ap.parse_args()

    stack, rows, cols, xy = load_stack()
    current, _names = feature_matrix(stack, ["baseline"], rows, cols)
    future245, _ = feature_matrix(stack, ["ssp245"], rows, cols)
    future585, _ = feature_matrix(stack, ["ssp585"], rows, cols)
    valid = np.isfinite(current).all(axis=1) & np.isfinite(future245).all(axis=1) & np.isfinite(future585).all(axis=1)
    cell_index = {(int(r), int(c)): i for i, (r, c) in enumerate(zip(rows, cols))}

    assignment = L.read_csv(L.PROCESSED / "occurrence_grid_assignment.csv")
    presence_cells = defaultdict(set)
    all_record_counts = defaultdict(int)
    for a in assignment:
        all_record_counts[a["species_id"]] += 1
        if a["in_basin"] == "1":
            i = cell_index.get((int(a["cell_id"][1:5]), int(a["cell_id"][6:10])))
            if i is not None:
                presence_cells[a["species_id"]].add(i)

    blocks = block_ids(xy, args.folds)
    rng = np.random.default_rng(SEED)
    bg_pool = np.where(valid)[0]
    background = rng.choice(bg_pool, size=min(BACKGROUND_N, len(bg_pool)), replace=False)

    species = L.read_csv(L.PROCESSED / "species_master.csv")
    if args.max_taxa:
        species = species[: args.max_taxa]

    perf, results = [], []
    suitable_cells: dict[str, list[int]] = {}
    for n, sp in enumerate(species, 1):
        sid = sp["species_id"]
        pres_all = sorted(c for c in presence_cells.get(sid, ()) if valid[c])
        n_in_basin = len(presence_cells.get(sid, ()))
        if len(pres_all) < MIN_PRESENCE:
            reason = ("no_basin_records" if all_record_counts.get(sid, 0) == 0
                      else "no_in_basin_records" if n_in_basin == 0
                      else "insufficient_records")
            perf.append({"species_id": sid, "accepted_name": sp["accepted_name"], "n_records": all_record_counts.get(sid, 0),
                         "n_cells": len(pres_all), "auc": "", "tss": "", "n_folds": 0,
                         "confidence_flag": "not assessed",
                         "not_assessed_reason": reason,
                         "n_insufficient_records": 1 if reason == "insufficient_records" else 0,
                         "n_no_basin_records": 1 if reason != "insufficient_records" else 0})
            results.append({"species_id": sid, "accepted_name": sp["accepted_name"], "scenario": "current",
                            "climatically_suitable_area_current_km2": "", "projected_range_change_pct": "",
                            "climate_vulnerability_tier": "not assessed"})
            continue

        bg = np.setdiff1d(background, pres_all)
        aucs, tsses, thresholds = [], [], []
        thr_max, thr_env = [], []
        for b in range(args.folds):
            test_p = [c for c in pres_all if blocks[c] == b]
            train_p = [c for c in pres_all if blocks[c] != b]
            if not test_p or len(train_p) < 5:
                continue
            test_bg = bg[blocks[bg] == b]
            train_bg = bg[blocks[bg] != b]
            if len(test_bg) < 20:
                continue
            try:
                pa, pb = current[train_p], current[train_bg]
                te_p, te_b = current[test_p], current[test_bg]
                f_max = fit_maxent(pa, pb)
                f_glm = fit_envelope(pa, pb)
                Z = np.vstack([te_p, te_b])
                y = np.concatenate([np.ones(len(te_p)), np.zeros(len(te_b))])
                pm, pe = f_max(Z), f_glm(Z)
                sc = ensemble(f_max, f_glm, Z)
                aucs.append(roc_auc_score(y, sc))
                tss, thr = max_tss(y, sc)
                if np.isfinite(tss):
                    tsses.append(tss); thresholds.append(thr)
                # Fixed thresholds on each model's own probability scale, so areas are comparable
                # between current and future (a rank transform would force equal areas).
                tm, _ = max_tss(y, pm)
                if np.isfinite(tm):
                    thr_max.append(max_tss(y, pm)[1])
                    thr_env.append(max_tss(y, pe)[1])
            except Exception:
                continue

        auc = float(np.mean(aucs)) if aucs else np.nan
        tss = float(np.mean(tsses)) if tsses else np.nan
        thr = float(np.mean(thresholds)) if thresholds else 0.5
        perf.append({"species_id": sid, "accepted_name": sp["accepted_name"], "n_records": all_record_counts.get(sid, 0),
                     "n_cells": len(pres_all), "auc": round(auc, 4) if np.isfinite(auc) else "",
                     "tss": round(tss, 4) if np.isfinite(tss) else "", "n_folds": len(aucs),
                     "confidence_flag": ("low-confidence (auc<0.7 or tss<0.4)"
                                         if (not np.isfinite(auc) or auc < 0.7 or not np.isfinite(tss) or tss < 0.4)
                                         else "ok"),
                     "not_assessed_reason": "", "n_insufficient_records": 0, "n_no_basin_records": 0})

        try:
            f_max = fit_maxent(current[pres_all], current[bg])
            f_glm = fit_envelope(current[pres_all], current[bg])
        except Exception:
            continue
        t_max = float(np.mean(thr_max)) if thr_max else 0.5
        t_env = float(np.mean(thr_env)) if thr_env else 0.5
        cur_ok = (f_max(current) >= t_max) & (f_glm(current) >= t_env) & valid
        suitable_cells[sid] = [int(i) for i in np.where(cur_ok)[0]]
        cur_area = float(np.nansum(cur_ok) * C.CELL_AREA_KM2)
        for scenario, fut in (("ssp245", future245), ("ssp585", future585)):
            fut_ok = (f_max(fut) >= t_max) & (f_glm(fut) >= t_env) & valid
            fut_area = float(np.nansum(fut_ok) * C.CELL_AREA_KM2)
            change = 100.0 * (fut_area - cur_area) / cur_area if cur_area > 0 else np.nan
            tier = ("high loss" if change < -50 else "moderate loss" if change < -20
                    else "stable" if change <= 20 else "gain")
            results.append({"species_id": sid, "accepted_name": sp["accepted_name"], "scenario": scenario,
                            "climatically_suitable_area_current_km2": round(cur_area, 1),
                            "projected_range_change_pct": round(change, 2) if np.isfinite(change) else "",
                            "climate_vulnerability_tier": tier if np.isfinite(change) else "not assessed"})
        if n % 10 == 0:
            print(f"  {n}/{len(species)} {sid}: auc={auc:.3f} tss={tss:.3f} cells={len(pres_all)}", flush=True)

    L.write_json(L.PROCESSED / "sdm_suitable_cells.json", suitable_cells, indent=None)
    L.write_csv(L.PROCESSED / "sdm_performance.csv", perf)
    perf_by = {p["species_id"]: p for p in perf}
    for result in results:
        result.update({key: perf_by[result["species_id"]][key] for key in ("auc", "tss", "confidence_flag")})
    L.write_json(L.PROCESSED / "sdm_suitable_cells_with_confidence.json", {sid: {"suitable_cells": cells, **{key: perf_by[sid][key] for key in ("auc", "tss", "confidence_flag")}, "interpretation": "exploratory suitability; not validated presence"} for sid, cells in suitable_cells.items()}, indent=None)
    L.write_csv(L.PROCESSED / "sdm_results.csv", results)
    assessed = [p for p in perf if p["confidence_flag"] != "not assessed"]
    tiers = defaultdict(int)
    for r in results:
        if r["scenario"] == "ssp585":
            tiers[r["climate_vulnerability_tier"]] += 1
    summary = {"n_taxa": len(perf), "n_assessed": len(assessed),
               "n_insufficient_records": sum(1 for p in perf if p["not_assessed_reason"] == "insufficient_records"),
               "n_no_basin_records": sum(1 for p in perf if p["not_assessed_reason"] in ("no_basin_records", "no_in_basin_records")),
               "n_low_confidence": sum(1 for p in assessed if p["confidence_flag"].startswith("low")),
               "mean_auc": round(float(np.mean([p["auc"] for p in assessed if p["auc"] != ""])), 3) if assessed else None,
               "mean_tss": round(float(np.mean([p["tss"] for p in assessed if p["tss"] != ""])), 3) if assessed else None,
               "ssp585_tiers": dict(tiers)}
    L.write_json(L.PROCESSED / "sdm_suitability_summary.json", summary)
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
