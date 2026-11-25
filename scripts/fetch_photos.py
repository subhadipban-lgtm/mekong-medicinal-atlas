#!/usr/bin/env python3
"""Fetch a CC-licensed photo for every atlas taxon from iNaturalist.

For each accepted name the iNaturalist taxa API is queried; the first species-rank result with a
default photo under an open licence is kept (CC0, CC-BY, CC-BY-SA and their NC variants). Taxa
without such a photo get none — the site shows no image rather than an unlicensed one. Each photo
carries the photographer attribution, the licence code and the iNaturalist taxon id, all of which
the species page displays.

The result is cached in data/raw/inat_photos.json; existing entries are not fetched again.

Usage: python scripts/fetch_photos.py [--force]
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

CACHE = L.RAW / "inat_photos.json"
API = "https://api.inaturalist.org/v1/taxa"
UA = "mekong-medicinal-plant-atlas/1.0 (https://github.com/subhadipban-lgtm/mekong-medicinal-plant-atlas)"
OPEN = {"cc0", "cc-by", "cc-by-sa", "cc-by-nc", "cc-by-nc-sa", "cc-by-nd", "cc-by-nc-nd"}


def get(url: str):
    delay = 2.0
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError) as e:
            if isinstance(e, urllib.error.HTTPError) and e.code == 404:
                return None
            if attempt == 5:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 60)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="refetch taxa that already have a cached answer")
    args = ap.parse_args()
    cache = L.read_json(CACHE) if CACHE.exists() and not args.force else {}
    todo = [r for r in L.read_csv(L.PROCESSED / "species_master.csv") if r["taxon_rank"] == "species" and r["species_id"] not in cache]
    print(f"taxa to look up: {len(todo)} (cached answers: {len(cache)})", flush=True)
    for i, r in enumerate(todo, 1):
        name = r["accepted_name"]
        try:
            data = get(API + "?" + urllib.parse.urlencode({"q": name, "rank": "species", "per_page": 3}))
            results = [t for t in (data or {}).get("results", []) if t.get("rank") == "species"]
            pick = next((t for t in results if (t.get("name") or "").lower() == name.lower()), results[0] if results else None)
            photo = (pick or {}).get("default_photo") or {}
            licence = (photo.get("license_code") or "").lower()
            if photo.get("url") and licence in OPEN:
                cache[r["species_id"]] = {
                    "url": photo.get("medium_url") or photo.get("url"), "square": photo.get("square_url"),
                    "license": licence, "attribution": " ".join((photo.get("attribution") or "").split()),
                    "inat_id": pick.get("id"), "inat_name": pick.get("name"),
                    "name_matches": (pick.get("name") or "").lower() == name.lower(),
                    "checkedAt": datetime.now(timezone.utc).date().isoformat()}
            else:
                cache[r["species_id"]] = {"url": None, "license": licence or "none", "checkedAt": datetime.now(timezone.utc).date().isoformat()}
        except Exception as e:
            print(f"  FAILED {name}: {e}", flush=True)
            continue
        if i % 25 == 0 or i == len(todo):
            L.write_json(CACHE, cache)
            print(f"  {i}/{len(todo)}", flush=True)
        time.sleep(1.0)  # iNaturalist asks clients to keep below one request per second
    L.write_json(CACHE, cache)
    with_photo = sum(1 for v in cache.values() if v.get("url"))
    exact = sum(1 for v in cache.values() if v.get("url") and v.get("name_matches"))
    print(f"taxa with a CC photo: {with_photo} ({exact} where the iNaturalist name equals the accepted name)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
