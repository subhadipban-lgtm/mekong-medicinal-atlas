#!/usr/bin/env python3
"""Render docs/data_dictionary.md from the schema in scripts/schema.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import atlas_lib as L  # noqa: E402
import schema  # noqa: E402

L.DOCS.mkdir(parents=True, exist_ok=True)
(L.DOCS / "data_dictionary.md").write_text(schema.render_dictionary(), encoding="utf-8")
tables = {name: L.read_csv(L.PROCESSED / name) for name in schema.TABLES if (L.PROCESSED / name).exists()}

# Machine-readable union for the Data tab: data/dictionary_atlas.csv mirrors the rendered
# dictionary so the Data catalog can union every dictionary_*.csv file into one filterable table.
_atlas_rows = []
for _table, _fields in schema.TABLES.items():
    for _name, _dtype, _unit, _allowed, _definition in _fields:
        _allowed_txt = schema._allowed_text(_allowed) if hasattr(schema, "_allowed_text") else str(_allowed)
        _atlas_rows.append({
            "table": _table.removesuffix(".csv"),
            "field": _name, "type": _dtype, "units": _unit,
            "allowed_values": _allowed_txt, "definition": _definition,
            "source_requirement": "see docs/data_dictionary.md",
        })
L.write_csv(L.ROOT / "data" / "dictionary_atlas.csv", _atlas_rows,
            fieldnames=["table", "field", "type", "units", "allowed_values", "definition",
                        "source_requirement"])
problems = schema.validate(tables)
fields = sum(len(v) for v in schema.TABLES.values())
print(f"dictionary written: {len(schema.TABLES)} tables, {fields} fields, {len(schema.GEO_LAYERS)} layers")
print(f"schema validation: {sum(len(v) for v in tables.values())} rows checked, {len(problems)} violations")
for problem in problems[:25]:
    print("  ", problem)
sys.exit(1 if problems else 0)
