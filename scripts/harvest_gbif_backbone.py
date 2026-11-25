#!/usr/bin/env python3
"""Match every workbook species name to the GBIF backbone and store what the backbone says.

For each normalised workbook name:
  species/match        accepted name, usage key, match type and confidence
  species/{key}        the full backbone record (family, genus, authorship)
  species/{key}/synonyms
  occurrence/count     records per basin country, all records, with or without coordinates

Nine workbook names do not match cleanly. Each has a documented override below, tried only when the
plain match is not an exact or fuzzy species match; such matches are marked MANUAL.

Outputs (data/raw): gbif_match_raw.json, gbif_species_records.json, gbif_synonyms.json,
                    gbif_occurrence_counts.json

Usage: python scripts/harvest_gbif_backbone.py [--only name1,name2] [--skip-counts]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import atlas_lib as L  # noqa: E402
from build_tables import load_sheets, build_spine  # noqa: E402

API = "https://api.gbif.org/v1"
UA = "mekong-medicinal-plant-atlas/1.0 (https://github.com/subhadipban-lgtm/mekong-medicinal-plant-atlas)"
# workbook name -> kind, query, expected family, note.
#   kind "match":          species/match on the query
#   kind "search_species": species-rank search result, preferring Plantae and the expected family
#   kind "genus":          genus-rank search result, preferring Plantae and the expected family
OVERRIDES = {
    "aglaia": ("genus", "Aglaia", "Meliaceae", "Workbook entry names the genus only; backbone genus record."),
    "erythrina": ("genus", "Erythrina", "Fabaceae", "Workbook entry names the genus only; backbone genus record."),
    "clausena": ("genus", "Clausena", "Rutaceae", "Workbook entry names the genus only; backbone genus record."),
    "euphoria longana": ("match", "Dimocarpus longan", "", "Workbook uses the synonym Euphoria longana."),
    "hedyotis diffusa": ("match", "Scleromitrion diffusum", "", "Backbone places Hedyotis diffusa in Scleromitrion."),
    "holarrhena antidysenterica": ("match", "Holarrhena pubescens", "", "Backbone accepts Holarrhena pubescens."),
    "polygonum chinense": ("match", "Persicaria chinensis", "", "Backbone places Polygonum chinense in Persicaria."),
    "scoparia dulcis": ("search_species", "Scoparia dulcis", "Plantaginaceae", "Name matching returns several equal entries; the accepted species record is taken from search."),
    "solanum indicum": ("search_species", "Solanum indicum", "Solanaceae", "Name matching returns only the genus; the accepted species record is taken from search."),
    "strychnos nux": ("match", "Strychnos nux-vomica", "", "Workbook truncates the epithet."),
}


def get(url: str):
    delay = 2.0
    for attempt in range(7):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=40) as r:
                body = r.read()
            return json.loads(body) if body.strip().lstrip().startswith(b"{") else body.decode().strip()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code in (429, 500, 502, 503, 504) and attempt < 6:
                time.sleep(max(float(e.headers.get("Retry-After") or 0), delay))
                delay = min(delay * 2, 60)
                continue
            raise
        except (OSError, ValueError):
            if attempt < 6:
                time.sleep(delay)
                delay = min(delay * 2, 60)
                continue
            raise
    return None


def match(name: str) -> dict:
    plain = get(f"{API}/species/match?name={urllib.parse.quote(name)}&strict=false")
    if plain.get("matchType") in ("EXACT", "FUZZY") and (plain.get("confidence") or 0) >= 90:
        return plain
    if name not in OVERRIDES:
        return plain
    kind, query, family, note = OVERRIDES[name]
    if kind == "match":
        result = dict(get(f"{API}/species/match?name={urllib.parse.quote(query)}"))
    else:
        rank = "GENUS" if kind == "genus" else "SPECIES"
        data = get(f"{API}/species/search?q={urllib.parse.quote(query)}&rank={rank}&limit=50") or {}
        results = data.get("results", [])
        same_name = [r for r in results if (r.get("canonicalName") or "").lower() == query.lower()]
        in_family = [r for r in same_name if r.get("kingdom") == "Plantae" and (not family or r.get("family") == family)]
        accepted = [r for r in in_family if r.get("taxonomicStatus") == "ACCEPTED"]
        pick = (accepted or in_family or same_name or results or [None])[0]
        if pick is None:
            return plain
        result = {**pick, "usageKey": pick.get("key"), "matchType": "MANUAL", "confidence": None}
    result["matchType"] = "MANUAL"
    result["manualNote"] = note
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="comma-separated workbook names (for testing)")
    ap.add_argument("--skip-counts", action="store_true", help="do not query occurrence counts")
    args = ap.parse_args()
    names = sorted(row["spine_name"] for row in build_spine(load_sheets()).values())
    if args.only:
        wanted = {x.strip() for x in args.only.split(",")}
        names = [x for x in names if x in wanted]

    matches: dict[str, dict] = {}
    records: dict[str, dict] = {}
    synonyms: dict[str, list] = {}
    counts: dict[str, dict] = {}
    for i, name in enumerate(names, 1):
        try:
            m = match(name)
            key = m.get("usageKey")
            matches[name] = m
            if key:
                records[str(key)] = get(f"{API}/species/{key}")
                syn = get(f"{API}/species/{key}/synonyms?limit=50") or {}
                synonyms[str(key)] = [s.get("scientificName") for s in syn.get("results", []) if s.get("scientificName")]
                if not args.skip_counts and m.get("rank") == "SPECIES":
                    counts[str(key)] = {}
                    for country in L.BASIN_COUNTRIES:
                        value = get(f"{API}/occurrence/count?taxonKey={key}&country={country}")
                        counts[str(key)][country] = int(value) if str(value).isdigit() else None
                        time.sleep(0.05)
            print(f"  {i:3d}/{len(names)} {name:30} -> {m.get('scientificName') or '-':45} "
                  f"{m.get('matchType')} {m.get('confidence') if m.get('confidence') is not None else ''}", flush=True)
        except Exception as e:
            print(f"  FAILED {name}: {e}", flush=True)
            return 1
        time.sleep(0.1)

    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    L.RAW.mkdir(parents=True, exist_ok=True)
    merge = {"gbif_match_raw.json": matches, "gbif_species_records.json": records,
             "gbif_synonyms.json": synonyms, "gbif_occurrence_counts.json": counts}
    for filename, new in merge.items():
        if not new:
            continue
        path = L.RAW / filename
        # A partial run (--only) updates the entries it looked up and leaves the others untouched.
        old = L.read_json(path) if path.exists() else {}
        old.update(new)
        L.write_json(path, old)
    (L.RAW / "_gbif_backbone_harvest.json").write_text(json.dumps(
        {"harvestedAt": stamp, "names": len(names), "overrides": {k: v[3] for k, v in OVERRIDES.items()}}, indent=2))
    print(f"done: {len(names)} names, {len(records)} backbone records, {len(counts)} taxa with counts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
