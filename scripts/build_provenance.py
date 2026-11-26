#!/usr/bin/env python3
"""Evidence-grade provenance export.

One row per atlas taxon: the taxon's best evidence grade (from species_master)
and the number of independent sources behind its ethnobotanical use and
pharmacology records.

Counting rule: a source is a distinct citation. The source_id column carries
coarse register buckets (uniformly "SRC-001; SRC-014") and would report 2
sources for every taxon, so it is not usable as the count. The source_citation
column holds the actual citation(s); a single cell can cite several works
separated by "; " (e.g. "ASEAN 2024 ...; DeFilipps & Krupnick 2018"), so cells
are split on semicolon-followed-by-space — the volume separator in "2023;16(4)"
has no space and is therefore not split.

The count feeds the Methods-page transparency paragraph and the per-grade
median column, so a reviewer can see how many independent sources sit behind a
grade-A assignment.

Output: data/processed/evidence_grade_provenance.csv
Columns: species_id, accepted_name, grade, n_sources, source_ids, notes
"""
from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import atlas_lib as L  # noqa: E402


def distinct_ids(value: str) -> set[str]:
    return {s.strip() for s in (value or "").replace(";", ",").split(",") if s.strip()}


def main() -> int:
    summary = L.read_json(L.PROCESSED / "evidence_summary.json")
    if summary.get("per_taxon_sources"):
        L.write_csv(L.PROCESSED / "evidence_grade_provenance.csv", summary["per_taxon_sources"])
        print("Preserved verified-source provenance and per-tier distributions")
        return 0
    raise RuntimeError("Rebuild evidence grades before provenance; legacy citation-string counts are not verified sources")
    master = {r["species_id"]: r for r in L.read_csv(L.PROCESSED / "species_master.csv")}
    citations: dict[str, set[str]] = defaultdict(set)
    register_ids: dict[str, set[str]] = defaultdict(set)
    for table in ("uses", "pharmacology"):
        for r in L.read_csv(L.PROCESSED / f"{table}.csv"):
            sid = r["species_id"]
            for part in re.split(r";\s+", (r.get("source_citation") or "").strip()):
                if part.strip():
                    citations[sid].add(part.strip())
            register_ids[sid] |= distinct_ids(r.get("source_id", ""))

    rows = []
    for sid, sp in sorted(master.items(), key=lambda kv: kv[1]["accepted_name"].lower()):
        n = len(citations.get(sid, set()))
        rows.append({
            "species_id": sid,
            "accepted_name": sp["accepted_name"],
            "grade": sp["evidence_grade"],
            "n_sources": n,
            "source_ids": "; ".join(sorted(register_ids.get(sid, set()))),
            "notes": "low-redundancy: a single independent source" if n <= 1 else "",
        })
    L.write_csv(L.PROCESSED / "evidence_grade_provenance.csv", rows)

    single = sum(1 for r in rows if r["n_sources"] <= 1)
    print(f"evidence_grade_provenance: {len(rows)} taxa; {single} supported by a single source")
    return 0


if __name__ == "__main__":
    sys.exit(main())
