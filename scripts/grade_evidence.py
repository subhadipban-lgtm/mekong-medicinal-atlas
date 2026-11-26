#!/usr/bin/env python3
"""Grade source provenance independently of study design and claim support.
A/B/C source types require resolved metadata; a species requires two distinct
verified sources of the same type. D means insufficient verified sources.
Resolution is bibliographic verification, never verification of a plant claim.
"""
from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import atlas_lib as L  # noqa: E402
from resolve_references_crossref import BOOK_RE, REPORT_RE, WEB_RE, YEAR_RE, has_identifier, journal_token, surname  # noqa: E402

BEST = {"A": 0, "B": 1, "C": 2, "D": 3}
BOOK_TYPES = {"book", "book-chapter", "monograph", "edited-book", "reference-book", "reference-entry"}
REPORT_TYPES = {"proceedings-article", "report", "report-component", "dissertation", "dataset", "standard"}


def norm(text: str) -> str:
    return " ".join((text or "").split())


def by_type(r: dict) -> tuple[str, str]:
    how = r["status"].replace("resolved_", "")
    t = r.get("type", "")
    if t == "journal-article":
        return "A", f"bibliographic metadata resolved by {how}: journal article; claim support not assessed"
    if t in BOOK_TYPES:
        return "B", f"confirmed by {how}: {t}"
    if t in REPORT_TYPES:
        return "C", f"confirmed by {how}: {t}"
    return "", ""


def rule_based(part: str) -> tuple[str, str]:
    if WEB_RE.search(part):
        return "D", "web source named in citation"
    if BOOK_RE.search(part):
        return "C", "named reference book; bibliographic verification pending"
    if REPORT_RE.search(part):
        return "C", "report or proceedings named in citation"
    if journal_token(part):
        return "C", "journal citation not independently confirmed"
    return "C", "citation too incomplete to confirm peer review"


def grade_citation(part: str, res: dict, inherited: dict, species: str) -> tuple[str, str, str]:
    """(grade, basis, doi) for one citation string."""
    part = norm(part)
    r = res.get(part) or (res.get(f"{part}||{species}") if not has_identifier(part) else None)
    if r and r.get("status", "").startswith("resolved"):
        g, basis = by_type(r)
        if g:
            if r.get("printed_id_problem"):
                basis += "; the printed identifier was wrong and the article was found by search"
            if r.get("citation_issue"):
                basis += f"; citation error: {r['citation_issue']}"
            return g, basis, r.get("doi", "")
    if r and r.get("printed_id_problem"):
        return "C", r["printed_id_problem"][:200] + " - verify", ""
    return (*rule_based(part), "")


def grade_row(citation: str, res: dict, inherited: dict, species: str) -> tuple[str, str, str]:
    parts = [p.strip() for p in re.split(r";\s+", citation or "") if len(p.strip()) >= 8]
    if not parts:
        return "D", "no citation recorded", ""
    graded = sorted((grade_citation(p, res, inherited, species) for p in parts), key=lambda g: BEST[g[0]])
    g, basis, doi = graded[0]
    others = [x[1] for x in graded[1:]]
    return g, basis + (f" (other citations: {'; '.join(others)[:120]})" if others else ""), doi


def main() -> int:
    cache = L.RAW / "reference_resolution.json"
    res = L.read_json(cache) if cache.exists() else {}
    if not cache.exists():
        raise RuntimeError("Reference-resolution cache required; refusing to silently downgrade all sources")
    inherited = {}  # author-year inheritance is explicitly forbidden
    old_species = Counter(r["evidence_grade"] for r in L.read_csv(L.PROCESSED / "species_master.csv"))
    old_rows = {t: Counter(r["evidence_grade"] for r in L.read_csv(L.PROCESSED / t)) for t in ("uses.csv", "pharmacology.csv")}
    source_records = []
    verified = defaultdict(lambda: defaultdict(set))
    all_sources = defaultdict(set)
    name = {r["species_id"]: r["accepted_name"] for r in L.read_csv(L.PROCESSED / "species_master.csv")}
    summary: dict[str, Counter] = {"uses.csv": Counter(), "pharmacology.csv": Counter()}
    bases: dict[str, Counter] = {"uses.csv": Counter(), "pharmacology.csv": Counter()}
    issues: list[dict] = []
    per_species: dict[str, str] = defaultdict(lambda: "D")
    for table in ("uses.csv", "pharmacology.csv"):
        rows = L.read_csv(L.PROCESSED / table)
        for r in rows:
            species = name.get(r["species_id"], "")
            for part in re.split(r";\s+", r.get("source_citation", "")):
                part = norm(part)
                if not part: continue
                resolution = res.get(part) or res.get(f"{part}||{species}") or {}
                sg, sb, sd = grade_citation(part, res, {}, species)
                confirmed = resolution.get("status", "").startswith("resolved")
                source_key = ("doi:" + sd.lower()) if sd else "citation:" + part.lower()
                all_sources[r["species_id"]].add(source_key)
                if confirmed and sd and sg in "ABC": verified[r["species_id"]][sg].add(source_key)
                source_records.append({"species_id": r["species_id"], "table": table, "row_id": r.get("use_id") or r.get("pharma_id"), "source_key": source_key, "citation": part, "source_grade": sg, "source_verification": "bibliographic_metadata_resolved" if confirmed else "unverified", "study_design": "not_assessed", "claim_support": "not_assessed", "citation_issue": resolution.get("citation_issue", ""), "printed_id_problem": resolution.get("printed_id_problem", "")})
            g, basis, doi = grade_row(r.get("source_citation", ""), res, inherited, species)
            r.update(evidence_grade=g, grade_basis=basis, resolved_doi=doi)
            summary[table][g] += 1
            bases[table][re.sub(r"\(other citations.*", "", basis).split("; ")[0][:72]] += 1
            if "citation error" in basis or "was wrong" in basis or "verify" in basis:
                issues.append({"table": table, "row_id": r.get("use_id") or r.get("pharma_id"),
                               "species_id": r["species_id"], "citation": r.get("source_citation", ""),
                               "grade": g, "note": basis.split(" (other")[0]})

        L.write_csv(L.PROCESSED / table, rows)

    species = L.read_csv(L.PROCESSED / "species_master.csv")
    for r in species:
        r["evidence_grade"] = next((g for g in "ABC" if len(verified[r["species_id"]][g]) >= 2), "D")
    L.write_csv(L.PROCESSED / "species_master.csv", species)

    out = {
        "rubric": {"A": "resolved journal article metadata",
                   "B": "resolved book or reference metadata",
                   "C": "resolved report metadata (rows also include unverified citations)",
                   "D": "insufficient verified sources or web/no citation"},
        "rows_by_grade": {k: dict(sorted(v.items())) for k, v in summary.items()},
        "basis_counts": {k: dict(v.most_common()) for k, v in bases.items()},
        "species_by_grade": dict(sorted(Counter(r["evidence_grade"] for r in species).items())),
        "citation_issues": issues,
        "lookups": dict(Counter(r.get("status", "") for r in res.values())),
    }
    provenance = []
    for r in species:
        sid = r["species_id"]
        distribution = {g: len(verified[sid][g]) for g in "ABC"}
        provenance.append({"species_id": sid, "accepted_name": r["accepted_name"], "grade": r["evidence_grade"], "n_sources": len(all_sources[sid]), "n_verified_sources": sum(distribution.values()), "verified_A": distribution["A"], "verified_B": distribution["B"], "verified_C": distribution["C"], "source_ids": "; ".join(sorted(set().union(*verified[sid].values()))), "notes": "Bibliographic provenance only; study design and claim support not assessed. Species grade requires two distinct DOI sources of the same type; D includes insufficient verification."})
    out["species_rule"] = "highest source category with at least two distinct resolved DOIs; otherwise D (insufficient verification)"
    out["claim_support"] = "not_assessed"
    out["per_taxon_sources"] = provenance
    out["single_verified_source_share_by_grade"] = {g: {"taxa": sum(p["grade"] == g for p in provenance), "single_verified_source": sum(p["grade"] == g and p["n_verified_sources"] == 1 for p in provenance)} for g in "ABCD"}
    L.write_csv(L.PROCESSED / "evidence_source_assessment.csv", source_records)
    L.write_csv(L.PROCESSED / "evidence_grade_provenance.csv", provenance)
    report = ["# Grading correction", "", "Grades describe bibliographic provenance, not efficacy, experimental design, or verified claim support. Species require at least two distinct resolved DOI sources at the assigned category. Unverified books do not qualify. Repeated citations to one DOI count once. No author–year inheritance. Resolution cache recovered from the original atlas data directory; no new claim verification was inferred.", "", "| Table | Grade | Before | After |", "|---|---|---:|---:|"]
    for table, before, after in [("species", old_species, Counter(r["evidence_grade"] for r in species))] + [(t, old_rows[t], summary[t]) for t in summary]:
        report += [f"| {table} | {g} | {before[g]} | {after[g]} |" for g in "ABCD"]
    report += ["", "Source resolution establishes bibliographic identity only. Study design and claim-level support remain not_assessed in the source assessment export. A DOI does not prove peer review, species relevance or efficacy. Existing citation conflicts are preserved. Sources without resolved DOIs remain excluded from the species corroboration threshold until independently verified; this is a coverage limitation, not proof of poor evidence."]
    (L.ROOT / "docs/grading_diff.md").write_text("\n".join(report) + "\n")
    L.write_json(L.PROCESSED / "evidence_summary.json", out)
    for k, v in summary.items():
        print(f"{k}: {dict(sorted(v.items()))}")
    print("species:", out["species_by_grade"], "| lookups:", out["lookups"])
    print("citation errors / unverified identifiers logged:", len(issues))
    return 0


if __name__ == "__main__":
    sys.exit(main())
