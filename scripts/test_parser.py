#!/usr/bin/env python3
"""Offline smoke tests for parser and recent-result request helpers."""
import importlib.util
import os
from pathlib import Path

# Make tests deterministic for configuration-derived helpers.
os.environ.setdefault("MAX_ROWS", "1000")
os.environ.setdefault("HISTORY_DAYS", "30")
os.environ.setdefault("CACHE_VERSION", "1.1.0")

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

params = m.build_recent_params("day", "hnt_burned", "2026-08-02")
assert params["limit"] == 1000
assert params["filters"] == "day >= '2026-08-02'"
assert params["columns"] == "day,hnt_burned"
assert params["sort_by"] == "day asc"

print("Offline parser/request smoke test passed.")
