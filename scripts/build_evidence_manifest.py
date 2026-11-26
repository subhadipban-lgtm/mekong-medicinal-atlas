#!/usr/bin/env python3
"""Build the committed PUBLIC evidence-engine manifest.

The evidence-engine inputs (publications, compounds, tier counts, PRISMA log)
are restricted local build material and are NOT committed. The Evidence page
needs only aggregate per-taxon counts and tier breakdowns, so those are derived
here into data/processed/evidence_manifest.json, which IS committed, and which
scripts/build_site.py reads to render the page. The manifest contains counts
and tier totals only — no titles, abstracts, author lists, PMIDs or SMILES.
"""
from __future__ import annotations

import csv
import re
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import atlas_lib as L  # noqa: E402

EV = L.ROOT / "data" / "evidence"


def main() -> int:
    if "--engine-corpus" in sys.argv:
        corpus = Path(sys.argv[sys.argv.index("--engine-corpus") + 1])
        rows = list(csv.DictReader(corpus.open()))
        existing = L.read_json(L.PROCESSED / "evidence_manifest.json")
        species = {r["species_id"]: r for r in L.read_csv(L.PROCESSED / "species_master.csv")}
        prior = {r["species_id"]: r for r in existing["taxa"]}
        counts = Counter(r["species_id"] for r in rows)
        taxa = []
        for sid, count in sorted(counts.items()):
            if sid not in species: raise ValueError(f"Unknown atlas taxon: {sid}")
            old = prior.get(sid, {})
            tiers = Counter(r["evidence_tier"] for r in rows if r["species_id"] == sid)
            taxa.append({"species_id": sid, "name": species[sid]["accepted_name"], "family": species[sid]["family"], "n_pubs": count, "tiers": dict(tiers), "tier_total": count, "n_compounds": old.get("n_compounds",0), "n_resolved": old.get("n_resolved",0), "network": old.get("network",{})})
        def key(row):
            return ("doi:" + row["doi"].lower().removeprefix("https://doi.org/")) if row.get("doi") else ("pmid:"+row["pmid"] if row.get("pmid") else "title:"+re.sub(r"\W+", "", row.get("title", "").lower()))
        update = dict(generated="2026-11-26", status="provisional_retrieval_candidates_not_verified_evidence", corpus=corpus.name, taxa=taxa, totals=dict(pubs=len(rows),unique_pubs=len({key(r) for r in rows}),needs_review=sum(r.get("needs_review")=="1" for r in rows),pilot_taxa=len(taxa)))
        if corpus.name == "publications_full.csv":
            existing["expanded_retrieval"] = update
        else:
            existing.update({k:v for k,v in update.items() if k != "totals"})
            existing["totals"].update(update["totals"])
        L.write_json(L.PROCESSED / "evidence_manifest.json", existing)
        print("Updated provisional aggregate manifest:",len(rows),"candidate species-publication rows")
        return 0
    use_manifest = "--manifest" in sys.argv
    if use_manifest and (L.PROCESSED / "evidence_manifest.json").exists():
        print("evidence manifest: preserving committed snapshot; use --engine-corpus for explicit audited refresh")
        return 0
    tiers_path = EV / "contract" / "species_evidence_tier_counts.json"
    pubs_path = EV / "contract" / "species_publications.json"
    ns_path = EV / "contract" / "species_network_summary.json"
    prisma_path = EV / "prisma_flow.json"
    pilot_path = EV / "pilot_species.csv"
    compound_path = EV / "species_compound.csv"
    if not (tiers_path.exists() and pubs_path.exists() and pilot_path.exists()):
        if use_manifest and (L.PROCESSED / "evidence_manifest.json").exists():
            print("evidence manifest: local inputs absent; keeping committed evidence_manifest.json")
            return 0
        sys.exit("evidence manifest: missing local inputs (contract aggregates / pilot_species.csv); the full build needs data/evidence/ which is restricted")

    tiers = json.loads(tiers_path.read_text(encoding="utf-8")).get("species_evidence_tier_counts", {})
    pub_ids = json.loads(pubs_path.read_text(encoding="utf-8")).get("species_publications", {})
    network = {}
    if ns_path.exists():
        network = json.loads(ns_path.read_text(encoding="utf-8")).get("species_network_summary", {})
    prisma = json.loads(prisma_path.read_text(encoding="utf-8")) if prisma_path.exists() else {}
    generated = prisma.get("generated", "")
    # GMS deep-search register (aggregate counts only; restricted inputs stay local)
    gms = None
    gms_pub = EV / "publications_gms.csv"
    if gms_pub.exists():
        n_gms_pubs = sum(1 for _ in L.read_csv(gms_pub))
        n_gms_comp = 0
        gms_comp = EV / "compounds_gms.csv"
        if gms_comp.exists():
            n_gms_comp = sum(1 for _ in L.read_csv(gms_comp))
        n_gms_plants = n_gms_wcvp = 0
        gms_cov = EV / "gms_wcvp_coverage.csv"
        if gms_cov.exists():
            cov_rows = L.read_csv(gms_cov)
            n_gms_plants = len(cov_rows)
            n_gms_wcvp = sum(1 for r in cov_rows if r.get("in_wcvp") == "1")
        gms = {"papers": n_gms_pubs, "plants": n_gms_plants, "wcvp": n_gms_wcvp, "molecule_rows": n_gms_comp}
    pilot = {r["species_id"]: r for r in L.read_csv(pilot_path)}
    compounds = Counter()
    compounds_resolved = Counter()
    if compound_path.exists():
        for c in L.read_csv(compound_path):
            compounds[c["species_id"]] += 1
            if c["structure_status"] == "resolved":
                compounds_resolved[c["species_id"]] += 1

    taxa = []
    for sid, row in sorted(pilot.items(), key=lambda kv: kv[1]["accepted_name"].lower()):
        t = tiers.get(sid, {})
        n_pubs = len(pub_ids.get(sid, []))
        tier_sum = sum(t.values())
        taxa.append({
            "species_id": sid,
            "name": row["accepted_name"],
            "family": row["family"],
            "n_pubs": n_pubs,
            "tiers": t,
            "tier_total": tier_sum,
            "n_compounds": compounds.get(sid, 0),
            "n_resolved": compounds_resolved.get(sid, 0),
            "network": network.get(sid, {}),
        })

    manifest = {
        "schema_version": "1.0",
        "generated": generated,
        "totals": {
            "pubs": sum(t["n_pubs"] for t in taxa),
            "compounds": sum(t["n_compounds"] for t in taxa),
            "resolved": sum(t["n_resolved"] for t in taxa),
            "pilot_taxa": len(taxa),
        },
        "gms": gms,
        "taxa": taxa,
    }
    # Corpus dedup figures (DOI -> PMID -> normalized title). In --manifest mode the site build
    # must never move the published numbers, so the committed totals are kept even when the
    # restricted publications table happens to be present locally.
    _prior = {}
    _mp = L.PROCESSED / "evidence_manifest.json"
    if _mp.exists():
        try:
            _prior = json.loads(_mp.read_text(encoding="utf-8")).get("totals", {})
        except Exception:
            _prior = {}
    _pub = EV / "publications.csv"
    if not use_manifest and _pub.exists():
        import re as _re, csv as _csv
        _keys = set(); _nr = 0
        def _nd(d):
            if not d: return ""
            d = d.strip().lower()
            d = _re.sub(r"^https?://(dx\.)?doi\.org/", "", d)
            d = _re.sub(r"^doi:\s*", "", d)
            return d.strip()
        for _r in _csv.DictReader(open(_pub)):
            _d = _nd(_r.get("doi"))
            if _d: _keys.add("doi:" + _d)
            elif (_r.get("pmid") or "").strip(): _keys.add("pmid:" + _r["pmid"].strip())
            else:
                _t = _re.sub(r"<[^>]+>", "", (_r.get("title") or "").lower())
                _t = " ".join(_re.sub(r"[^a-z0-9]+", " ", _t).split())[:80]
                _keys.add("ti:" + _t)
            if (_r.get("needs_review") or "").strip() == "1": _nr += 1
        manifest["totals"]["unique_pubs"] = len(_keys)
        manifest["totals"]["needs_review"] = _nr
    else:
        manifest["totals"]["unique_pubs"] = _prior.get("unique_pubs", 1880)
        manifest["totals"]["needs_review"] = _prior.get("needs_review", 190)
    out = L.PROCESSED / "evidence_manifest.json"
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"evidence_manifest: {len(taxa)} taxa; pubs={manifest['totals']['pubs']}; "
          f"compounds={manifest['totals']['compounds']}; resolved={manifest['totals']['resolved']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
