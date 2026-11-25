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
problems = schema.validate(tables)
fields = sum(len(v) for v in schema.TABLES.values())
print(f"dictionary written: {len(schema.TABLES)} tables, {fields} fields, {len(schema.GEO_LAYERS)} layers")
print(f"schema validation: {sum(len(v) for v in tables.values())} rows checked, {len(problems)} violations")
for problem in problems[:25]:
    print("  ", problem)
sys.exit(1 if problems else 0)
