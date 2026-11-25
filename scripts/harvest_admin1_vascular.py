#!/usr/bin/env python3
"""Harvest GBIF vascular-plant species counts per admin-1 province.

Network harvest (not part of the default offline build). Uses GBIF's own
stateProvince facet values as the admin-1 unit - those are the units the
internal-coldspot analysis runs on; the Natural Earth polygons are joined
best-effort by name afterwards.

Output: data/raw/admin1_vascular.json
{
  "countries": { "TH": [ {"province": ..., "records": n, "species": m}, ... ] },
  "harvested": "YYYY-MM-DD"
}
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "admin1_vascular.json"
BASE = "https://api.gbif.org/v1/occurrence/search"
UA = {"User-Agent": "mekong-atlas/0.9 (research; contact: ami.subhadipbanerjee@gmail.com)"}
COUNTRIES = ["TH", "VN", "CN", "KH", "LA", "MM"]
SLEEP = 1.1
RETRIES = 4
MIN_RECORDS = 300  # below this, stateProvince values are noise, not provinces


def get(params: dict) -> dict:
    for attempt in range(RETRIES):
        url = f"{BASE}?{urllib.parse.urlencode(params)}"
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(4 * (attempt + 1))
                continue
            raise
        except Exception:
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"failed after retries: {params}")


def main() -> int:
    out = {"countries": {}, "harvested": time.strftime("%Y-%m-%d")}
    for c in COUNTRIES:
        data = get({"taxonKey": 6, "country": c, "facet": "stateProvince",
                    "facetLimit": 1000, "limit": 0})
        facets = {(f.get("name") or ""): f["count"]
                  for f in (data.get("facets") or [{}])[0].get("counts", [])}
        # GBIF stateProvince is extremely noisy (typos, Thai-script variants,
        # localities). Keep only values that look like real provinces:
        # >= MIN_RECORDS records, >= 4 characters, no parentheses/brackets.
        real = {p: n for p, n in facets.items()
                if n >= MIN_RECORDS and len(p.strip()) >= 4
                and not any(ch in p for ch in "()[]()")}
        print(f"{c}: {len(facets)} facet values -> {len(real)} kept "
              f"(records >= {MIN_RECORDS})", flush=True)
        rows = []
        for i, (prov, nrec) in enumerate(real.items()):
            sp = get({"taxonKey": 6, "country": c, "stateProvince": prov,
                      "facet": "speciesKey", "facetLimit": 10000, "limit": 0})
            counts = (sp.get("facets") or [{}])[0].get("counts", [])
            nsp = len(counts)
            truncated = len(counts) >= 10000
            rows.append({"province": prov, "records": nrec, "species": nsp,
                         "species_truncated": truncated})
            print(f"{c} {prov[:30]:30s} records={nrec:9d} species={nsp:6d}"
                  f"{' TRUNCATED' if truncated else ''}", flush=True)
            time.sleep(SLEEP)
        out["countries"][c] = rows
        print(f"== {c}: {len(rows)} provinces", flush=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"written {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
