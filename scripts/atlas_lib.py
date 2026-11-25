"""Shared helpers for the Mekong Medicinal Plant Atlas build scripts."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
GEO = ROOT / "data" / "geo"
DWC = ROOT / "data" / "dwc"
WEB = ROOT / "web"
DOCS = ROOT / "docs"

WORKBOOK = RAW / "workbook" / "MEKONG_BASIN_NATURAL_PRODUCTS_2026-11-24.xlsx"
BASIN_COUNTRIES = ["CN", "TH", "VN", "LA", "KH", "MM"]
COUNTRY_NAMES = {"CN": "China", "TH": "Thailand", "VN": "Vietnam", "LA": "Laos",
                 "KH": "Cambodia", "MM": "Myanmar"}

# Author abbreviations and taxonomic noise that must not enter a join key.
_AUTHOR = re.compile(
    r"\b(l|camb|sp|spp|species|roxb|blume|benth|hook|thomson|king|miq|planch|"
    r"corner|turner|wahl|poir|ham|finet|gagnep|lour|merr|wall|jack|christm|"
    r"roscoe|d\.?c|hassk|burm|auct|sensu|ex)\b\.?", re.IGNORECASE)


def normalize_species(name: str | None) -> str | None:
    """'*Melia azedarach* Roxb.' -> 'melia azedarach'.

    Lowercased, italics stripped, composite '/'-names reduced to the first,
    parentheticals removed, authority abbreviations and punctuation dropped,
    truncated to genus + epithet.
    """
    if not name or not str(name).strip():
        return None
    s = str(name).replace("*", "").split("/")[0]
    s = re.sub(r"\(.*?\)", " ", s)
    s = _AUTHOR.sub(" ", s.lower())
    s = re.sub(r"[^a-z ]", " ", s)
    parts = s.split()
    if len(parts) < 2:
        return parts[0] if parts else None
    return " ".join(parts[:2])


def species_id(normalized: str) -> str:
    """Stable key: 'melia azedarach' -> 'sp_melia_azedarach'."""
    return "sp_" + normalized.replace(" ", "_")


def slug(normalized: str) -> str:
    """Page slug: 'melia azedarach' -> 'melia-azedarach'."""
    return normalized.replace(" ", "-")


def read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else []
    with Path(path).open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, obj, indent: int | None = 2) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=indent), encoding="utf-8")


def load_workbook_sheets(path: Path = WORKBOOK) -> dict[str, list[dict]]:
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheets: dict[str, list[dict]] = {}
    for name in wb.sheetnames:
        it = wb[name].iter_rows(values_only=True)
        try:
            hdr = next(it)
        except StopIteration:
            sheets[name] = []
            continue
        sheets[name] = [{h: r[i] for i, h in enumerate(hdr) if h}
                        for r in it if any(c is not None and str(c).strip() for c in r)]
    wb.close()
    return sheets
