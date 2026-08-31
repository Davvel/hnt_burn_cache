#!/usr/bin/env python3
"""Offline smoke tests for v1.2.1 helpers. No Dune credits are used."""
import importlib.util
import os
from datetime import date
from pathlib import Path

os.environ.setdefault("MAX_ROWS", "1000")
os.environ.setdefault("HISTORY_DAYS", "30")
os.environ.setdefault("CACHE_VERSION", "1.2.1")
os.environ.setdefault("DUNE_SOURCE_QUERY_ID", "3342070")
os.environ.setdefault("DUNE_PERFORMANCE", "medium")

p = Path(__file__).parent / "fetch_burn.py"
spec = importlib.util.spec_from_file_location("fetch_burn", p)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

sql = m.build_wrapper_sql("3342070", 30)
assert sql == "SELECT *\nFROM query_3342070\nORDER BY 1 DESC\nLIMIT 30", sql
assert "LIMIT 1000" not in sql

rows = [
    {"day": "2026-08-31 00:00:00.000 UTC", "hnt_burned": "100.5"},
    {"day": "2026-08-30 00:00:00.000 UTC", "hnt_burned": 200.25},
    {"day": "2026-08-01 00:00:00.000 UTC", "hnt_burned": 999.0},
]

d, v, cols = m.pick_columns(rows)
assert d == "day", (d, cols)
assert v == "hnt_burned", (v, cols)
assert m.normalize_date(rows[0][d]) == "2026-08-31"
assert m.normalize_number(rows[1][v]) == 200.25

daily, date_col, value_col, skipped, first_day = m.process_rows(
    rows, today_utc=date(2026, 8, 31)
)
assert first_day.isoformat() == "2026-08-02"
assert [r["date"] for r in daily] == ["2026-08-30", "2026-08-31"]
assert skipped == 1
assert date_col == "day"
assert value_col == "hnt_burned"

print("v1.2.1 offline smoke tests passed.")
