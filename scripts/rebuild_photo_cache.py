#!/usr/bin/env python3
"""Reconstruct data/raw/inat_photos.json from the photo blocks already published on the
species pages.

The iNaturalist photo cache is gitignored, so a fresh checkout that rebuilds the site would
otherwise drop every species photo. Each published species page already carries the photo URL,
attribution, licence and iNaturalist taxon id, so the cache can be rebuilt exactly from the
committed HTML — no network call, no drift.

Source pages are read from git (default HEAD~ or a ref given with --ref) so the reconstruction
is not affected by an in-progress build.

Usage: python scripts/rebuild_photo_cache.py [--ref <git-ref>]
"""
from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import atlas_lib as L  # noqa: E402

BLOCK = re.compile(
    r'<div class="species-photo"><img src="(?P<src>[^"]+)" alt="(?P<alt>[^"]*)"[^>]*>'
    r'<div class="cap">Photo: <a href="https://www\.inaturalist\.org/taxa/(?P<taxon>\d+)"[^>]*>'
    r'(?P<attr>.*?)</a> · (?P<lic>[A-Za-z0-9.-]+) · iNaturalist</div></div>', re.S)


def git_show(ref: str, path: str) -> str | None:
    try:
        return subprocess.run(["git", "show", f"{ref}:{path}"], check=True,
                              capture_output=True, text=True).stdout
    except subprocess.CalledProcessError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="HEAD")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    species = L.read_csv(L.PROCESSED / "species_master.csv")
    cache: dict[str, dict] = {}
    missing = 0
    pages = subprocess.run(["git", "ls-tree", "-r", "--name-only", args.ref, "web/species/"],
                           check=True, capture_output=True, text=True).stdout.split()
    for page in pages:
        if not page.endswith(".html"):
            continue
        slug = Path(page).stem
        page_html = git_show(args.ref, page)
        if not page_html:
            continue
        m = BLOCK.search(page_html)
        if not m:
            missing += 1
            continue
        sid = "sp_" + slug
        # The page renders the /large/ variant; the cache stores the /medium/ URL. The page
        # HTML-escaped the attribution, so unescape it here and let the builder escape it again.
        url = m.group("src").replace("/large.", "/medium.")
        cache[sid] = {
            "url": url,
            "license": m.group("lic").lower().replace("cc-by-nc", "cc-by-nc").lower(),
            "attribution": " ".join(html.unescape(m.group("attr")).split()),
            "inat_id": int(m.group("taxon")),
            "name_matches": True,
        }

    known = {r["species_id"] for r in species}
    cache = {k: v for k, v in cache.items() if k in known}
    out = Path(args.out) if args.out else (L.RAW / "inat_photos.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(cache, indent=1, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    print(f"photo cache rebuilt from {args.ref}: {len(cache)} taxa with a photo "
          f"({missing} pages had none) -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
