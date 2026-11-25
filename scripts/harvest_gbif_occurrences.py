#!/usr/bin/env python3
"""Harvest georeferenced GBIF occurrences for every species-level atlas taxon.

Records are pulled from the GBIF occurrence search API (one taxon at a time,
300 records per page) for the six basin countries. A field subset of each
record is stored verbatim, per taxon, as gzipped JSON under
data/raw/gbif_occurrences/. The harvest is resume-safe: a taxon whose
checkpoint exists is skipped, so an interrupted run continues where it stopped.

Usage: python scripts/harvest_gbif_occurrences.py [--taxon-key K ...] [--force]
"""
from __future__ import annotations

import argparse
import csv
import gzip
import http.client
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPECIES_MASTER = ROOT / "data" / "processed" / "species_master.csv"
OUT_DIR = ROOT / "data" / "raw" / "gbif_occurrences"
SUMMARY = OUT_DIR / "_harvest_summary.json"

API = "https://api.gbif.org/v1/occurrence/search"
COUNTRIES = ["TH", "LA", "VN", "KH", "MM", "CN"]
PAGE = 300
UA = "mekong-medicinal-plant-atlas/1.0 (https://github.com/subhadipban-lgtm/mekong-medicinal-plant-atlas)"
FIELDS = [
    "key", "occurrenceID", "basisOfRecord", "eventDate", "year", "month", "day",
    "scientificName", "acceptedScientificName", "acceptedTaxonKey", "taxonKey", "taxonRank",
    "kingdom", "family", "genus", "species",
    "decimalLatitude", "decimalLongitude", "coordinateUncertaintyInMeters", "coordinatePrecision",
    "geodeticDatum", "country", "countryCode", "stateProvince", "county", "locality",
    "recordedBy", "identifiedBy", "occurrenceStatus", "establishmentMeans", "associatedReferences",
    "license", "rightsHolder", "institutionCode", "collectionCode", "catalogNumber",
    "datasetKey", "datasetName", "publishingOrgKey", "publishingCountry",
    "iucnRedListCategory", "issue", "taxonomicStatus", "mediaType", "dateIdentified",
]


def log(msg: str) -> None:
    print(f"[{datetime.now(timezone.utc):%H:%M:%S}] {msg}", flush=True)


def fetch_json(url: str, retries: int = 8):
    delay = 2.0
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                retry_after = e.headers.get("Retry-After")
                wait = max(float(retry_after) if retry_after else 0.0, delay)
                log(f"    HTTP {e.code}; retrying in {wait:.0f}s")
                time.sleep(wait)
                delay = min(delay * 2, 90)
                continue
            raise
        except (OSError, http.client.HTTPException, json.JSONDecodeError) as e:
            if attempt < retries:
                log(f"    network error {e}; retrying in {delay:.0f}s")
                time.sleep(delay)
                delay = min(delay * 2, 90)
                continue
            raise
    raise RuntimeError("unreachable")


def page_url(taxon_key: int, offset: int) -> str:
    params = [("taxonKey", taxon_key)]
    params += [("country", c) for c in COUNTRIES]
    params += [("hasCoordinate", "true"), ("hasGeospatialIssue", "false"),
               ("limit", PAGE), ("offset", offset)]
    return API + "?" + urllib.parse.urlencode(params)


def harvest(taxon_key: int) -> dict:
    records: list[dict] = []
    offset, expected, pages = 0, 0, 0
    while True:
        data = fetch_json(page_url(taxon_key, offset))
        expected = data.get("count", 0)
        results = data.get("results", [])
        records.extend({f: rec.get(f) for f in FIELDS} for rec in results)
        pages += 1
        offset += len(results)
        if not results or data.get("endOfRecords", True) or offset >= expected:
            break
        time.sleep(0.15)
    return {
        "taxonKey": taxon_key,
        "countReported": expected,
        "recordsFetched": len(records),
        "pages": pages,
        "harvestedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "records": records,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--taxon-key", type=int, action="append", help="harvest only these taxon keys")
    ap.add_argument("--force", action="store_true", help="re-harvest even if a checkpoint exists")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(SPECIES_MASTER.open(encoding="utf-8")))
    targets: list[tuple[int, str]] = []
    for r in rows:
        key = r.get("gbif_taxon_key") or ""
        # Genus/family-level entries are skipped: their occurrences would mix in non-target taxa.
        if not key or r.get("gbif_match_type") == "HIGHERRANK":
            continue
        if args.taxon_key and int(key) not in args.taxon_key:
            continue
        targets.append((int(key), r["species_id"]))

    summary: dict = {}
    if SUMMARY.exists() and not args.force:
        summary = json.loads(SUMMARY.read_text())

    done = [k for k, _ in targets if (OUT_DIR / f"{k}.json.gz").exists() and str(k) in summary]
    log(f"taxa in scope: {len(targets)} | already checkpointed: {len(done)} | to fetch: {len(targets) - len(done)}")
    failed: list[int] = []
    for i, (key, species_id) in enumerate(targets, 1):
        path = OUT_DIR / f"{key}.json.gz"
        if path.exists() and str(key) in summary and not args.force:
            continue
        try:
            payload = harvest(key)
        except Exception as e:
            log(f"  FAILED taxon {key} ({species_id}): {e}")
            failed.append(key)
            continue
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        meta = {k: v for k, v in payload.items() if k != "records"}
        meta["speciesId"] = species_id
        summary[str(key)] = meta
        SUMMARY.write_text(json.dumps(summary, indent=1), encoding="utf-8")
        flag = "" if payload["recordsFetched"] == payload["countReported"] else "  [count mismatch]"
        log(f"  {i:3d}/{len(targets)} {species_id:34} {payload['recordsFetched']:6d} records, {payload['pages']} page(s){flag}")

    total = sum(v.get("recordsFetched", 0) for v in summary.values())
    log(f"done: {len(summary)} taxa checkpointed, {total} records, {len(failed)} failed")
    if failed:
        log("re-run the script to retry failed taxa (checkpoints make it resume-safe)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
