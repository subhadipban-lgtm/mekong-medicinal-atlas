#!/usr/bin/env python3
"""Build the human-review queue scaffold (Tier 1, Priority 2).

The actual decisions are human - this script emits the queue with all
needs_review publications and unresolved compounds, plus a fixed 20-row
double-review subsample for the Cohen's kappa protocol. The owner reviews
rows and fills reviewer_id / decision / corrected_tier / rationale; the
kappa computation script (engine/engine/review_kappa.py) then reports
inter-reviewer agreement on the double-reviewed subsample.

Outputs (atlas data/processed/review/):
  review_queue.csv       every pending row, empty decision fields
  double_review_sample.csv  20-row subsample (seed 42) for kappa
"""
import csv
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "review"
PUB = ROOT / "data" / "evidence" / "publications.csv"
COMP = ROOT / "data" / "evidence" / "compounds_unresolved.csv"

QUEUE_FIELDS = ["queue_id", "kind", "species_id", "publication_id", "title",
                "auto_tier", "auto_type", "reviewer_id", "decision",
                "corrected_tier", "rationale"]


def main() -> int:
    rows = []
    with open(PUB, newline="", encoding="utf-8") as f:
        for i, r in enumerate(csv.DictReader(f)):
            if r["needs_review"] != "1":
                continue
            rows.append({
                "queue_id": f"Q{i + 1:05d}", "kind": "publication",
                "species_id": r["species_id"], "publication_id": r["publication_id"],
                "title": r["title"][:180], "auto_tier": r["evidence_tier"],
                "auto_type": r["publication_type"], "reviewer_id": "",
                "decision": "", "corrected_tier": "", "rationale": "",
            })
    with open(COMP, newline="", encoding="utf-8") as f:
        for i, r in enumerate(csv.DictReader(f), start=1):
            rows.append({
                "queue_id": f"QC{i:05d}", "kind": "compound",
                "species_id": r["species_id"], "publication_id": "",
                "title": f"unresolved compound: {r['name']}", "auto_tier": "",
                "auto_type": "", "reviewer_id": "", "decision": "",
                "corrected_tier": "", "rationale": "",
            })
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "review_queue.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=QUEUE_FIELDS)
        w.writeheader()
        w.writerows(rows)
    rng = random.Random(42)
    pubs = [r for r in rows if r["kind"] == "publication"]
    sample = rng.sample(pubs, min(20, len(pubs)))
    with open(OUT / "double_review_sample.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=QUEUE_FIELDS)
        w.writeheader()
        w.writerows(sample)
    print(f"review_queue.csv: {len(rows)} rows "
          f"({len(pubs)} publications, {len(rows) - len(pubs)} compounds)")
    print(f"double_review_sample.csv: {len(sample)} rows (seed 42)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
