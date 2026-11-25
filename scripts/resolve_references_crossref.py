#!/usr/bin/env python3
"""Resolve bibliographic citations in uses.csv and pharmacology.csv.

A citation earns grade A only if it can be confirmed as a peer-reviewed article. This script
tries, in order: a DOI printed in the citation (Crossref), a PMID or PMC id (NCBI E-utilities), then a
Crossref bibliographic query that adds the species name as a disambiguator. A candidate is
accepted only when the first-author surname and the year agree and, in addition, either the named
journal agrees or the species appears in the title. That keeps an unrelated paper by a different
"Yeo 2018" from being accepted, without rejecting national surveys whose titles name no species.
A resolved article must also be about plants or natural products, which catches a printed DOI
that points at an unrelated paper.

Crossref rate-limits anonymous clients, so citations that rule-based grading already classifies
as a book, report or web page are not sent to Crossref at all.

Results are cached in data/raw/reference_resolution.json. Identifier lookups are keyed by the
citation; query lookups are keyed by citation and species, because the same review cited for two
species is a different query.

Usage: python scripts/resolve_references_crossref.py [--limit N]
"""
from __future__ import annotations

import http.client
import json
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import atlas_lib as L  # noqa: E402

CACHE = L.RAW / "reference_resolution.json"
UA = "mekong-medicinal-plant-atlas/1.0 (https://github.com/subhadipban-lgtm/mekong-medicinal-plant-atlas)"
DOI_RE = re.compile(r"10\.\d{4,9}/[^\s;,)\]]+")
PMID_RE = re.compile(r"\bPMID[\s:]*(\d{4,9})", re.IGNORECASE)
PMCID_RE = re.compile(r"\bPMC(\d{4,9})\b", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(19[5-9]\d|20[0-2]\d)\b")
# A resolved article must concern plants or their chemistry.
TOPIC_TERMS = [
    "plant", "herb", "medicin", "phyto", "ethnobot", "ethnomed", "extract", "compound", "flavon", "alkaloid",
    "terpen", "phenol", "lignan", "coumarin", "saponin", "steroid", "xanthone", "quinone", "essential oil",
    "natural product", "constituent", "anti-", "antioxid", "cytotox", "pharmac", "bioactiv", "leaves", "leaf",
    "root", "bark", "rhizome", "seed", "fruit", "genus", "species", "biodivers", "flora", "traditional",
    "taxonom", "vouchered", "conservation", "crop", "aromatic", "oil", "resin", "latex", "glycoside", "tannin",
    "chromone", "chalcone", "stilbene", "anthocyan", "caroten", "polysacchar", "triterp", "diterp", "sesquiterp",
    "monoterp", "herbal", "drug", "hepatoprotect", "antimicrob", "antidiabet", "inflamm",
]
BOOK_RE = re.compile(r"\bpress\b|publish|secretariat|\bvol\.?\s*\d|atlas of|flora of|handbook|pharmacopoeia|"
                     r"monograph|herbal & medicinal plants|encyclopedia|encyclopaedia|compendium|\bbook\b", re.I)
REPORT_RE = re.compile(r"proceedings|conference|workshop|symposium|\breport\b|ministry|department of|\binstitute\b|"
                       r"\biucn\b|traffic|\bcites\b|\bfao\b|\bundp\b|\bwwf\b|\bproject\b|\bmeeting\b|"
                       r"technical paper|newsletter", re.I)
WEB_RE = re.compile(r"https?://|www\.|\.(?:com|org|net)\b|website|wikipedia|accessed|\bblog\b|facebook|youtube", re.I)


def norm(text: str) -> str:
    return " ".join((text or "").split())


def surname(citation: str) -> str:
    first = re.sub(r"\bet\s*al\.?", "", re.split(r"[,;]", citation)[0], flags=re.IGNORECASE)
    m = re.match(r"\s*([A-Za-zÀ-ÿ'\-]+)", first)
    return (m.group(1) if m else "").lower()


def journal_token(citation: str) -> str:
    """First significant word of the journal named after the year, or '' for bare author-year cites."""
    m = YEAR_RE.search(citation)
    if not m:
        return ""
    rest = re.split(r"\d", citation[m.end():], maxsplit=1)[0]
    rest = re.split(r"doi:|pmid|pmc", rest, flags=re.IGNORECASE)[0]
    words = re.findall(r"[A-Za-z]{4,}", rest)
    return words[0].lower() if words else ""


def has_identifier(citation: str) -> bool:
    return bool(DOI_RE.search(citation) or PMID_RE.search(citation) or PMCID_RE.search(citation))


def worth_querying(citation: str) -> bool:
    """Rule-based grading settles books, reports and web pages without a Crossref request."""
    return not (WEB_RE.search(citation) or BOOK_RE.search(citation) or REPORT_RE.search(citation))


def get_json(url: str, retries: int = 6, pause: float = 2.0):
    delay = pause
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(max(float(e.headers.get("Retry-After") or 0), 15 if e.code == 429 else delay))
                delay = min(delay * 2, 120)
                continue
            return None
        except (OSError, http.client.HTTPException, json.JSONDecodeError):
            if attempt < retries:
                time.sleep(delay)
                delay = min(delay * 2, 120)
                continue
            return None
    return None


def crossref_candidate(item: dict) -> dict:
    authors = item.get("author") or []
    family = ((authors[0].get("family") or authors[0].get("name") or "") if authors else "").lower()
    year = ""
    for k in ("published", "issued", "published-print", "published-online", "created"):
        parts = (item.get(k) or {}).get("date-parts") or []
        if parts and parts[0] and parts[0][0]:
            year = str(parts[0][0])
            break
    return {"doi": (item.get("DOI") or "").lower(), "type": item.get("type", ""),
            "title": norm((item.get("title") or [""])[0]),
            "container": norm((item.get("container-title") or [""])[0] or ""),
            "year": year, "first_author": family, "score": item.get("score")}


def surname_matches(candidate_first: str, cited: str) -> bool:
    """'khin aung' matches a cited 'Aung'; hyphenated names match on either part."""
    tokens = candidate_first.replace("-", " ").split()
    return bool(tokens) and (cited in tokens or tokens[-1] == cited or tokens[0] == cited)


def check(cand: dict, citation: str, species_words: list[str], by_identifier: bool) -> tuple[str, str]:
    """(hard reason to reject, soft note about a transcription error in the citation).

    For a lookup by printed identifier the article itself is evidence, so a wrong journal or a
    wrong first author in the citation is only a note, as long as author mismatch is covered by the
    species appearing in the title. For a search query the journal or species is what identifies the
    paper, so the same mismatches are hard rejections.
    """
    if cand.get("type") == "component":
        return "figure/table deposit, not the article", ""
    if not cand.get("doi") and not cand.get("title"):
        return "incomplete record", ""
    title = cand.get("title", "").lower()
    species_in_title = any(w in title for w in species_words)
    years = YEAR_RE.findall(citation)
    year, cited = cand.get("year", ""), ""
    # Online-first publication often dates an article a year before its issue: accept a one-year
    # difference in either direction, but only when the species named in the citation is in the title.
    try:
        adjacent = species_in_title and years and abs(int(year) - int(years[0])) == 1
    except ValueError:
        adjacent = False
    year_ok = bool(year) and (year in years or adjacent)
    if years and year and not year_ok:
        return f"year differs ({year})", ""
    if not species_in_title and not any(term in title for term in TOPIC_TERMS):
        return f"resolved article is not about plants or natural products ({cand['title'][:50]})", ""
    author_ok = surname_matches(cand.get("first_author", ""), surname(citation))
    token = journal_token(citation)
    journal_ok = not token or token in cand.get("container", "").lower()
    if by_identifier:
        if not author_ok and not species_in_title:
            return f"first author differs ({cand.get('first_author', '')}) and species not in title", ""
        return "", "; ".join(n for n, bad in (("first author differs from the citation", not author_ok),
                                              (f"journal differs from the citation ({cand['container'][:40]})", not journal_ok)) if bad)
    if not author_ok:
        return f"first author differs ({cand.get('first_author', '')})", ""
    if not journal_ok:
        return f"journal differs ({cand['container'][:40]})", ""
    if not token and not species_in_title and not has_identifier(citation):
        # Author and year alone identify the paper, so the species must appear in its title.
        return "species not in title (ambiguous)", ""
    return "", ""


def via_doi(doi: str) -> tuple[dict | None, str]:
    data = get_json("https://api.crossref.org/works/" + urllib.parse.quote(doi))
    if not data:
        return None, "DOI not found in Crossref"
    return crossref_candidate(data["message"]), ""


EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"


def ncbi_summaries(db: str, ids: set[str]) -> dict[str, dict]:
    """Record summaries from NCBI E-utilities for a set of PubMed (db=pubmed) or PMC (db=pmc) ids.

    E-utilities accept 200 identifiers per request, so every printed PMID and PMC id in the atlas
    is fetched in a handful of requests. Europe PMC answers the same question one id at a time
    and was taking 15-60 seconds per request.
    """
    out: dict[str, dict] = {}
    ordered = sorted(ids)
    for i in range(0, len(ordered), 200):
        data = get_json(f"{EUTILS}?db={db}&id={','.join(ordered[i:i + 200])}&retmode=json")
        result = (data or {}).get("result") or {}
        for uid in result.get("uids", []):
            r = result.get(uid) or {}
            if r.get("error"):
                continue
            doi = next((a.get("value", "") for a in (r.get("articleids") or []) if a.get("idtype") == "doi"), "")
            if not doi:
                m = re.search(r"doi:\s*(\S+)", r.get("elocationid") or "")
                doi = m.group(1) if m else ""
            year = re.search(r"\d{4}", r.get("pubdate") or "")
            authors = r.get("authors") or []
            out[uid] = {"doi": doi.lower(), "type": "journal-article",
                        "title": norm(re.sub(r"<[^>]+>", "", r.get("title") or "")).rstrip("."),
                        "container": norm(r.get("fulljournalname") or r.get("source") or ""),
                        "year": year.group(0) if year else "",
                        "first_author": norm(authors[0].get("name", "") if authors else "").split(" ")[0].lower(),
                        "score": None}
        time.sleep(0.4)  # NCBI allows anonymous clients 3 requests per second
    return out


def via_query(citation: str, species: str) -> tuple[dict, str]:
    data = get_json("https://api.crossref.org/works?" + urllib.parse.urlencode(
        {"query.bibliographic": f"{citation} {species}", "rows": 5}))
    best, best_reason = None, "no candidates"
    for item in (data or {}).get("message", {}).get("items", []):
        cand = crossref_candidate(item)
        reason, _ = check(cand, citation, species_words_of(species), by_identifier=False)
        if not reason:
            return cand, ""
        if best is None and reason != "figure/table deposit, not the article":
            best, best_reason = cand, reason
    return best or {}, best_reason


def species_words_of(species: str) -> list[str]:
    return [w.lower() for w in re.findall(r"[a-z]{4,}", species)]


def resolve(citation: str, species: str, pm: dict) -> dict:
    citation = norm(citation)
    sw = species_words_of(species)
    problems: list[str] = []
    pmid, pmcid, doi = PMID_RE.search(citation), PMCID_RE.search(citation), DOI_RE.search(citation)
    cand = None
    if doi:
        cand, problem = via_doi(doi.group(0).rstrip(".,;)"))
        if cand is None:
            problems.append(f"printed DOI rejected: {problem}")
    elif pmid or pmcid:
        cand = pm["pubmed"].get(pmid.group(1)) if pmid else pm["pmc"].get(pmcid.group(1))
        if cand is None:
            problems.append("printed PMID/PMC rejected: identifier not found in PubMed/PMC")
    if cand:
        reason, note = check(cand, citation, sw, by_identifier=True)
        if not reason:
            kind = "doi" if doi else "pmid"
            return {"status": f"resolved_{kind}", **cand, "reason": "", "citation_issue": note,
                    "printed_id_problem": ""}
        problems.append(("printed DOI rejected: " if doi else "printed PMID/PMC rejected: ") + reason)
    if not worth_querying(citation):
        return {"status": "unresolved", "reason": "book, report or web citation; graded by rule",
                "printed_id_problem": "; ".join(problems)}
    best, reason = via_query(citation, species)
    return {"status": "resolved_query" if best and not reason else "unresolved", **best,
            "reason": reason, "citation_issue": "", "printed_id_problem": "; ".join(problems)}


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=0, help="resolve at most N uncached lookups (for testing)")
    args = ap.parse_args()
    species_name = {r["species_id"]: r["accepted_name"] for r in L.read_csv(L.PROCESSED / "species_master.csv")}
    todo: dict[str, str] = {}
    for table in ("uses.csv", "pharmacology.csv"):
        for r in L.read_csv(L.PROCESSED / table):
            species = species_name.get(r["species_id"], "")
            for part in (r.get("source_citation") or "").split(";"):
                part = norm(part)
                if len(part) >= 8:
                    todo.setdefault(part if has_identifier(part) else f"{part}||{species}", species)
    cache = L.read_json(CACHE) if CACHE.exists() else {}
    pending = [k for k in todo if k not in cache]
    print(f"lookups: {len(todo)} | cached: {len(todo) - len(pending)} | to run: {len(pending)}", flush=True)
    if args.limit:
        pending = pending[:args.limit]
    today = datetime.now(timezone.utc).date().isoformat()

    def species_of(key: str) -> str:
        return key.split("||", 1)[1] if "||" in key else todo[key]

    pmids = {m.group(1) for k in todo if (m := PMID_RE.search(k))}
    pmcids = {m.group(1) for k in todo if (m := PMCID_RE.search(k))}
    pm = {"pubmed": ncbi_summaries("pubmed", pmids), "pmc": ncbi_summaries("pmc", pmcids)}
    print(f"  PubMed ids: {len(pmids)} ({len(pm['pubmed'])} found) | PMC ids: {len(pmcids)} ({len(pm['pmc'])} found)", flush=True)

    # One request at a time, spaced out: Crossref rate-limits anonymous clients.
    for i, key in enumerate(pending, 1):
        cache[key] = resolve(key.split("||", 1)[0], species_of(key), pm) | {"checkedAt": today}
        if i % 25 == 0 or i == len(pending):
            L.write_json(CACHE, cache)
            print(f"  {i}/{len(pending)}", flush=True)
        time.sleep(1.5 + random.random())
    L.write_json(CACHE, cache)
    print("status:", dict(Counter(v["status"] for v in cache.values())))
    print("types:", dict(Counter(v.get("type") for v in cache.values() if v["status"].startswith("resolved"))))
    print("unresolved reasons:", dict(Counter(v.get("reason", "")[:44] for v in cache.values()
                                              if v["status"] == "unresolved").most_common(8)))
    print("printed identifier problems:", sum(1 for v in cache.values() if v.get("printed_id_problem")),
          "| citation errors noted:", sum(1 for v in cache.values() if v.get("citation_issue")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
