#!/usr/bin/env python3
"""Mirror the evidence-engine integration contract from api-service.

Fetches /contract/manifest.json, validates each contract file (valid JSON and
schema_version == EXPECTED), and writes them to data/evidence/contract/.
Exits non-zero (with the errors on stderr) if validation fails, so the calling
GitHub Action can open an Issue and skip the commit.

Only aggregate contract files are fetched (publication IDs + tier counts); no
abstracts or other restricted engine inputs.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

API_BASE = os.environ.get("API_BASE", "https://api-service-dyzfz7h7lq-uc.a.run.app")
EXPECTED = os.environ.get("EXPECTED_SCHEMA", "1.0")
OUT = Path(os.environ.get("CONTRACT_OUT", "data/evidence/contract"))


def main() -> int:
    with urllib.request.urlopen(f"{API_BASE}/contract/manifest.json", timeout=30) as r:
        manifest = json.loads(r.read())
    files = [f["file"] for f in manifest.get("files", [])]
    print("manifest files:", files)
    errors, payloads = [], {}
    for name in files:
        try:
            with urllib.request.urlopen(f"{API_BASE}/contract/{name}", timeout=30) as r:
                obj = json.loads(r.read())
        except Exception as e:
            errors.append(f"{name}: fetch/parse failed ({e})"); continue
        if obj.get("schema_version") != EXPECTED:
            errors.append(f"{name}: schema_version {obj.get('schema_version')!r} != {EXPECTED!r}"); continue
        payloads[name] = obj
    if errors:
        print("CONTRACT VALIDATION FAILED:", file=sys.stderr)
        for e in errors:
            print(" -", e, file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    for name, obj in payloads.items():
        (OUT / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(payloads)} contract files to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
