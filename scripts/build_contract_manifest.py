#!/usr/bin/env python3
"""Build data/evidence_manifest.json — the provenance manifest for the evidence-engine
contract endpoints.

The contract JSON under data/evidence/contract/ is RESTRICTED and is never published
(the project owner declined republication on 2026-11-26). This manifest is the public,
auditable description of those endpoints: for each one it records the schema names,
row counts, byte size, SHA-256 of the local file, licence and access status.

It deliberately contains NO publication identifiers, DOIs, titles, author names or
abstract text — only structure, counts and a hash.

Output: data/evidence_manifest.json (repository root data/, committed)
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import atlas_lib as L  # noqa: E402

CONTRACT = L.ROOT / "data" / "evidence" / "contract"
OUT = L.ROOT / "data" / "evidence_manifest.json"

IN_REPO = "public — committed in the repository (not served on the website)"
RESTRICTED = "restricted — request access"
RESTRICTED_NOTE = ("Restricted local build material. Not published on the website or in the "
                   "repository; available from the corresponding author on request, for review "
                   "and research collaboration.")
LICENSE = "CC-BY-4.0 for the committed contract aggregates; publication identifiers are metadata only"


def sha256_of(path: Path) -> tuple[str, int]:
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest(), len(data)


def top_keys(obj) -> list[str]:
    return sorted(obj.keys()) if isinstance(obj, dict) else []


def record_fields(obj, container: str) -> list[str]:
    """Field names of one record in a mapping container, without exposing any value."""
    rec = obj.get(container) if isinstance(obj, dict) else None
    if isinstance(rec, dict) and rec:
        first = next(iter(rec.values()))
        if isinstance(first, dict):
            return sorted(first.keys())
        return ["<scalar>"]
    return []


def endpoint(name: str, rel: str, access: str, notes: str, keys=None, records=None,
             rows_basis: str = "") -> dict:
    path = CONTRACT / rel
    entry = {"endpoint": name, "file": f"data/evidence/contract/{rel}",
             "access_status": access, "license": LICENSE, "notes": notes}
    if not path.exists():
        entry.update({"present": False, "schema_names": [], "rows": None,
                      "bytes": None, "sha256": None})
        return entry
    obj = json.loads(path.read_text(encoding="utf-8"))
    digest, size = sha256_of(path)
    entry.update({
        "present": True,
        "schema_version": obj.get("schema_version") if isinstance(obj, dict) else None,
        "schema_names": top_keys(obj),
        "row_field_names": records or [],
        "rows": keys,
        "rows_basis": rows_basis,
        "bytes": size,
        "sha256": digest,
    })
    return entry


def main() -> int:
    if not CONTRACT.exists():
        if OUT.exists():
            print("contract manifest: local contract inputs absent; keeping committed data/evidence_manifest.json")
            return 0
        sys.exit("contract manifest: data/evidence/contract/ is absent and no committed manifest exists")

    def load(rel):
        p = CONTRACT / rel
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    sp = load("species_publications.json").get("species_publications", {})
    ns = load("species_network_summary.json").get("species_network_summary", {})
    tiers = load("species_evidence_tier_counts.json").get("species_evidence_tier_counts", {})
    edges = load("network_edges.json")
    news = load("whats_new.json")
    review = load("review_status.json")

    endpoints = [
        endpoint("manifest.json", "manifest.json", "pending — not built",
                 "Top-level index of the contract set. No manifest.json exists in the local contract "
                 "set; this provenance manifest serves as the index instead.",
                 keys=0, rows_basis="no tabular rows"),
        endpoint("species_publications.json", "species_publications.json", IN_REPO,
                 "Per-taxon list of publication identifiers behind the pilot literature mapping. "
                 "Committed once (2026-11-26); excluded from future syncs by "
                 "scripts/sync_evidence_contract.py.",
                 keys=len(sp),
                 records=["publication_id"],
                 rows_basis=f"one array per pilot taxon; {sum(len(v) for v in sp.values())} identifiers in total"),
        endpoint("species_network_summary.json", "species_network_summary.json", IN_REPO,
                 "Per-taxon network summary: compound, high-confidence target, pathway and disease counts.",
                 keys=len(ns),
                 records=record_fields({"x": ns}, "x"),
                 rows_basis="one object per pilot taxon"),
        endpoint("species_evidence_tier_counts.json", "species_evidence_tier_counts.json", IN_REPO,
                 "Per-taxon publication counts by evidence tier (traditional, in vitro, in vivo, review, clinical, other).",
                 keys=len(tiers),
                 records=record_fields({"x": tiers}, "x"),
                 rows_basis="one object per pilot taxon"),
        endpoint("network_edges/{species_id}.json", "network_edges.json", "pending — not built",
                 "Per-taxon network edges. The local file is an empty stub (no nodes, no edges); "
                 "the per-species endpoints do not exist yet.",
                 keys=len(edges.get("edges", [])),
                 records=["nodes", "edges"],
                 rows_basis="edge list; 0 edges in the local stub"),
        endpoint("whats_new.json", "whats_new.json", IN_REPO,
                 "Change feed from the living-review job: newly mapped publications per taxon.",
                 keys=len(news.get("items", [])),
                 records=record_fields({"x": news.get("items") or [{}]}, "x") or ["change_id"],
                 rows_basis="one item per detected change"),
        endpoint("docking_summary.json", "docking_summary.json", IN_REPO,
                 "Milestone-3 docking status stub (no pairs yet; AutoDock Vina runs after the "
                 "decision gate).",
                 keys=0,
                 records=record_fields({"x": load("docking_summary.json")}, "x") or ["status"],
                 rows_basis="status stub; 0 pairs"),
        endpoint("review_status.json", "review_status.json", "pending — no claims yet",
                 "Human-review status of extracted claims. The local file holds an empty claim list; "
                 "no claim has been queued for review yet.",
                 keys=len(review.get("claims", [])),
                 records=["claim_id", "status"],
                 rows_basis="one entry per claim; 0 claims in the local stub"),
    ]

    manifest = {
        "schema_version": "1.0",
        "generated": "2026-11-26",
        "title": "Mekong Medicinal Plant Atlas — evidence contract endpoints: provenance manifest",
        "note": ("Structure, row counts, byte sizes, SHA-256 hashes, licence and access status for "
                 "each evidence-engine contract endpoint. The endpoints themselves are restricted "
                 "and are not published. This manifest contains no publication identifiers, DOIs, "
                 "titles, author names or abstract text."),
        "contact": ("Access requests: open an issue at "
                    "https://github.com/subhadipban-lgtm/mekong-medicinal-plant-atlas/issues "
                    "or write to the corresponding author listed on the About page."),
        "counts": {
            "endpoints": len(endpoints),
            "present_locally": sum(1 for e in endpoints if e.get("present")),
            "restricted": sum(1 for e in endpoints if e["access_status"].startswith("restricted")),
            "pending": sum(1 for e in endpoints if e["access_status"].startswith("pending")),
        },
        "endpoints": endpoints,
    }
    OUT.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"evidence contract manifest -> {OUT.relative_to(L.ROOT)}: "
          f"{manifest['counts']['endpoints']} endpoints, "
          f"{manifest['counts']['restricted']} restricted, {manifest['counts']['pending']} pending")
    return 0


if __name__ == "__main__":
    sys.exit(main())
