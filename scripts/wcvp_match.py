#!/usr/bin/env python3
"""Cross-reference the 333 atlas taxa against WCVP (and MPNS, when it returns).

WCVP: data/raw/wcvp/wcvp_names.csv (pipe-delimited, 1.45M rows), streamed in
two passes - the file is 300 MB and must not be held in memory.
MPNS v12: mpns.science.kew.org was serving a Cloudflare 5xx error on
2026-11-25; status recorded per row as access pending (operating rule: log
and proceed, never fabricate).

Outputs (data/processed/macroecology/):
  mekong_wcvp_coverage.csv          species_id, match status, wcvp ids
  mekong_taxonomy_reconciliation.csv accepted_name -> wcvp accepted name
"""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "macroecology"
WCVP = ROOT / "data" / "raw" / "wcvp" / "wcvp_names.csv"
MASTER = ROOT / "data" / "processed" / "species_master.csv"

MPNS_NOTE = "mpns.science.kew.org unavailable (Cloudflare 5xx) on 2026-11-25; access pending"


def main() -> int:
    targets: dict[str, str] = {}   # lowercased name -> species_id
    atlas: dict[str, dict] = {}
    with open(MASTER, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            atlas[r["species_id"]] = r
            name = r["accepted_name"].strip().lower()
            if name:
                targets[name] = r["species_id"]

    found: dict[str, list[dict]] = {}
    with open(WCVP, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="|")
        for r in reader:
            low = (r.get("taxon_name") or "").strip().lower()
            if low in targets:
                found.setdefault(targets[low], []).append({
                    "plant_name_id": r.get("plant_name_id", ""),
                    "taxon_name": r.get("taxon_name", ""),
                    "taxon_status": r.get("taxon_status", ""),
                    "accepted_plant_name_id": r.get("accepted_plant_name_id", ""),
                    "family": r.get("family", ""),
                    "taxon_rank": r.get("taxon_rank", ""),
                })

    # second pass: resolve accepted names for non-Accepted matches
    need = {c["accepted_plant_name_id"] for v in found.values()
            for c in v if c["accepted_plant_name_id"] and c["accepted_plant_name_id"] != c["plant_name_id"]}
    accepted_names: dict[str, str] = {}
    if need:
        with open(WCVP, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="|")
            for r in reader:
                pid = r.get("plant_name_id", "")
                if pid in need:
                    accepted_names[pid] = r.get("taxon_name", "")

    coverage_map: dict[str, dict] = {}
    for sid in sorted(atlas):
        r = atlas[sid]
        name = r["accepted_name"]
        cands = found.get(sid, [])
        row = {
            "species_id": sid, "accepted_name": name,
            "in_wcvp": "0", "wcvp_name_id": "", "wcvp_accepted_name": "",
            "wcvp_status": "", "match_type": "no_match", "wcvp_family": "",
            "in_mpns": "", "mpns_name_id": "", "notes": "",
        }
        if not cands:
            row["notes"] = ("genus-level atlas row" if r.get("taxon_rank") == "genus"
                            else "no WCVP name match") + f"; {MPNS_NOTE}"
        else:
            accepted = [c for c in cands if c["taxon_status"] == "Accepted"]
            others = [c for c in cands if c["taxon_status"] != "Accepted"]
            pick = accepted[0] if accepted else others[0]
            if len(accepted) > 1:
                row["notes"] = f"homonym: {len(accepted)} Accepted WCVP rows"
            acc_id = pick["accepted_plant_name_id"]
            acc_name = (accepted_names.get(acc_id, "")
                        if acc_id and acc_id != pick["plant_name_id"] else pick["taxon_name"])
            row.update({
                "in_wcvp": "1", "wcvp_name_id": pick["plant_name_id"],
                "wcvp_accepted_name": acc_name,
                "wcvp_status": pick["taxon_status"],
                "match_type": "exact" if pick["taxon_status"] == "Accepted" else "synonym",
                "wcvp_family": pick["family"],
            })
            row["notes"] = (row["notes"] + "; " if row["notes"] else "") + MPNS_NOTE
        coverage_map[sid] = row

    # genus+species fallback for unmatched species-level rows, then a
    # spelling-variant probe (edit distance <= 1 on the species epithet)
    unmatched = [sid for sid, r in coverage_map.items()
                 if r["match_type"] == "no_match"
                 and atlas[sid].get("taxon_rank") == "species"]
    if unmatched:
        def edit1(a, b):
            if abs(len(a) - len(b)) > 1:
                return False
            i = j = diffs = 0
            while i < len(a) and j < len(b):
                if a[i] != b[j]:
                    diffs += 1
                    if diffs > 1:
                        return False
                    if len(a) >= len(b):
                        i += 1
                    if len(a) <= len(b):
                        j += 1
                else:
                    i += 1
                    j += 1
            return True

        want = {sid: tuple(atlas[sid]["accepted_name"].lower().split(maxsplit=1))
                for sid in unmatched}
        variants: dict[str, dict] = {}
        with open(WCVP, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="|")
            for r in reader:
                g = (r.get("genus") or "").lower()
                s = (r.get("species") or "").lower()
                for sid, (wg, ws) in want.items():
                    if g == wg and ws and s and edit1(ws, s):
                        variants[sid] = {
                            "plant_name_id": r.get("plant_name_id", ""),
                            "taxon_name": r.get("taxon_name", ""),
                            "taxon_status": r.get("taxon_status", ""),
                            "accepted_plant_name_id": r.get("accepted_plant_name_id", ""),
                            "family": r.get("family", ""),
                            "taxon_rank": r.get("taxon_rank", ""),
                        }
        for sid, v in variants.items():
            row = coverage_map[sid]
            acc_id = v["accepted_plant_name_id"]
            acc_name = (accepted_names.get(acc_id, "")
                        if acc_id and acc_id != v["plant_name_id"] else v["taxon_name"])
            row.update({
                "in_wcvp": "1", "wcvp_name_id": v["plant_name_id"],
                "wcvp_accepted_name": acc_name,
                "wcvp_status": v["taxon_status"],
                "match_type": "spelling_variant",
                "wcvp_family": v["family"],
            })
            row["notes"] = (f'closest WCVP name {v["taxon_name"]}; verify spelling; ' + MPNS_NOTE)

    recon_rows = []
    for sid in sorted(atlas):
        row = coverage_map[sid]
        recon_rows.append({
            "species_id": sid, "accepted_name": row["accepted_name"],
            "wcvp_accepted_name": row["wcvp_accepted_name"],
            "wcvp_name_id": row["wcvp_name_id"],
            "relationship": ("same" if row["match_type"] == "exact" else
                             "synonym" if row["match_type"] in ("synonym", "spelling_variant")
                             else "unresolved"),
            "notes": row["notes"],
        })
    coverage_rows = list(coverage_map.values())

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "mekong_wcvp_coverage.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(coverage_rows[0].keys()))
        w.writeheader()
        w.writerows(coverage_rows)
    with open(OUT / "mekong_taxonomy_reconciliation.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(recon_rows[0].keys()))
        w.writeheader()
        w.writerows(recon_rows)

    n_in = sum(1 for r in coverage_rows if r["in_wcvp"] == "1")
    n_syn = sum(1 for r in coverage_rows if r["match_type"] == "synonym")
    n_out = sum(1 for r in coverage_rows if r["match_type"] == "no_match")
    print(f"coverage: {n_in}/{len(coverage_rows)} in WCVP "
          f"({n_in - n_syn} exact accepted, {n_syn} via synonym, {n_out} unmatched)")
    print(f"written: mekong_wcvp_coverage.csv, mekong_taxonomy_reconciliation.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
