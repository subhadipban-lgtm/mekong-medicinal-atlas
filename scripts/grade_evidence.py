#!/usr/bin/env python3
"""Apply the atlas evidence-grading rubric to every use, pharmacology and species record.

Rubric (also published on the Methods page):
  A  peer-reviewed journal article, or a peer-reviewed survey with a documented methodology
  B  major reference book or authoritative flora, with a named author or publisher and a date
  C  local report, proceedings, herbarium specimen, or a citation that cannot be verified
  D  general web source, unverified lead, or no citation at all

A row citing several sources takes the best grade among them. A species takes the best grade of
its rows. Grade A requires the article to be confirmed (DOI, PMID/PMC, or a Crossref match on
author + year + journal or species) or the citation to be a complete journal reference.

Evidence quality and citation accuracy are graded separately. When a printed identifier resolves
to an on-topic article of the cited year about the cited species, the evidence is confirmed (A)
even if the citation misspells the journal or the first author; the error is recorded in
`citation_issue` for the QA report. An identifier that resolves to a different article, or to
nothing, leaves the row unverified (C).

Inputs:  data/processed/{uses,pharmacology,species_master}.csv, data/raw/reference_resolution.json
Outputs: the same three tables with evidence_grade / grade_basis / resolved_doi filled in, and
         data/processed/evidence_summary.json
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
        return "A", f"confirmed by {how}: peer-reviewed article"
    if t in BOOK_TYPES:
        return "B", f"confirmed by {how}: {t}"
    if t in REPORT_TYPES:
        return "C", f"confirmed by {how}: {t}"
    return "", ""


def rule_based(part: str) -> tuple[str, str]:
    if WEB_RE.search(part):
        return "D", "web source named in citation"
    if BOOK_RE.search(part):
        return "B", "reference book named in citation"
    if REPORT_RE.search(part):
        return "C", "report or proceedings named in citation"
    if journal_token(part):
        return "A", "complete journal citation (not confirmed through Crossref)"
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
    if not r or r.get("reason") in ("species not in title (ambiguous)", "no candidates"):
        key = (surname(part), (YEAR_RE.findall(part) or [""])[0])
        if key in inherited and journal_token(part) == "":
            return "A", "same author and year as a confirmed article", inherited[key]
    return (*rule_based(part), "")


def grade_row(citation: str, res: dict, inherited: dict, species: str) -> tuple[str, str, str]:
    parts = [p.strip() for p in (citation or "").split(";") if len(p.strip()) >= 8]
    if not parts:
        return "D", "no citation recorded", ""
    graded = sorted((grade_citation(p, res, inherited, species) for p in parts), key=lambda g: BEST[g[0]])
    g, basis, doi = graded[0]
    others = [x[1] for x in graded[1:]]
    return g, basis + (f" (other citations: {'; '.join(others)[:120]})" if others else ""), doi


def main() -> int:
    cache = L.RAW / "reference_resolution.json"
    res = L.read_json(cache) if cache.exists() else {}
    # An author-year pair that maps to exactly one confirmed article lets bare "Surname 2018" cites inherit it.
    works: dict[tuple[str, str], set[str]] = defaultdict(set)
    for cite, r in res.items():
        if r.get("status", "").startswith("resolved") and r.get("type") == "journal-article" and r.get("doi"):
            years = YEAR_RE.findall(cite)
            if years:
                works[(surname(cite), years[0])].add(r["doi"])
    inherited = {k: next(iter(v)) for k, v in works.items() if len(v) == 1}

    name = {r["species_id"]: r["accepted_name"] for r in L.read_csv(L.PROCESSED / "species_master.csv")}
    summary: dict[str, Counter] = {"uses.csv": Counter(), "pharmacology.csv": Counter()}
    bases: dict[str, Counter] = {"uses.csv": Counter(), "pharmacology.csv": Counter()}
    issues: list[dict] = []
    per_species: dict[str, str] = defaultdict(lambda: "D")
    for table in ("uses.csv", "pharmacology.csv"):
        rows = L.read_csv(L.PROCESSED / table)
        for r in rows:
            species = name.get(r["species_id"], "")
            g, basis, doi = grade_row(r.get("source_citation", ""), res, inherited, species)
            r.update(evidence_grade=g, grade_basis=basis, resolved_doi=doi)
            summary[table][g] += 1
            bases[table][re.sub(r"\(other citations.*", "", basis).split("; ")[0][:72]] += 1
            if "citation error" in basis or "was wrong" in basis or "verify" in basis:
                issues.append({"table": table, "row_id": r.get("use_id") or r.get("pharma_id"),
                               "species_id": r["species_id"], "citation": r.get("source_citation", ""),
                               "grade": g, "note": basis.split(" (other")[0]})
            if BEST[g] < BEST[per_species[r["species_id"]]]:
                per_species[r["species_id"]] = g
        L.write_csv(L.PROCESSED / table, rows)

    species = L.read_csv(L.PROCESSED / "species_master.csv")
    for r in species:
        r["evidence_grade"] = per_species.get(r["species_id"], "D")
    L.write_csv(L.PROCESSED / "species_master.csv", species)

    out = {
        "rubric": {"A": "peer-reviewed article or survey with documented methodology",
                   "B": "major reference book or authoritative flora",
                   "C": "report, proceedings, specimen, or unverifiable citation",
                   "D": "web source, unverified lead, or no citation"},
        "rows_by_grade": {k: dict(sorted(v.items())) for k, v in summary.items()},
        "basis_counts": {k: dict(v.most_common()) for k, v in bases.items()},
        "species_by_grade": dict(sorted(Counter(r["evidence_grade"] for r in species).items())),
        "citation_issues": issues,
        "lookups": dict(Counter(r.get("status", "") for r in res.values())),
    }
    L.write_json(L.PROCESSED / "evidence_summary.json", out)
    for k, v in summary.items():
        print(f"{k}: {dict(sorted(v.items()))}")
    print("species:", out["species_by_grade"], "| lookups:", out["lookups"])
    print("citation errors / unverified identifiers logged:", len(issues))
    return 0


if __name__ == "__main__":
    sys.exit(main())
