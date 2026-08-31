#!/usr/bin/env python3
"""Small offline smoke test for parser helpers."""
import importlib.util
from pathlib import Path

p = Path(__file__).parent / "fetch_burn.py"
spec = importlib.util.spec_from_file_location("fetch_burn", p)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

rows = [
    {"day": "2026-08-29 00:00:00.000 UTC", "hnt_burned": "100.5"},
    {"day": "2026-08-30 00:00:00.000 UTC", "hnt_burned": 200.25},
]

d, v, cols = m.pick_columns(rows)
assert d == "day", (d, cols)
assert v == "hnt_burned", (v, cols)
assert m.normalize_date(rows[0][d]) == "2026-08-29"
assert m.normalize_number(rows[1][v]) == 200.25
print("Offline parser smoke test passed.")
