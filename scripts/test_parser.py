#!/usr/bin/env python3
"""Offline smoke tests for v1.4.0 helpers. No Dune credits are used."""
import importlib.util
import os
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("MAX_ROWS", "1000")
os.environ.setdefault("HISTORY_DAYS", "30")
os.environ.setdefault("CACHE_VERSION", "1.4.0")
os.environ.setdefault("DUNE_SOURCE_QUERY_ID", "3342070")
os.environ.setdefault("DUNE_PERFORMANCE", "medium")

p = Path(__file__).parent / "fetch_burn.py"
spec = importlib.util.spec_from_file_location("fetch_burn", p)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

sql = m.build_wrapper_sql("3342070", 30)
assert sql == "SELECT *\nFROM query_3342070\nORDER BY 1 DESC\nLIMIT 32", sql
assert "LIMIT 1000" not in sql

# On 2026-09-04 the cache includes Sep 3 (T-1), while the app should display
# only through Sep 2 (T-2). 31 cache rows give the app 30 settled days.
today = date(2026, 9, 4)
rows = []
for i in range(32):
    d = today - timedelta(days=i)
    rows.append({"day": f"{d.isoformat()} 00:00:00.000 UTC", "hnt_burned": 100 + i})

# Add an old row that must also be excluded.
rows.append({"day": "2026-07-01 00:00:00.000 UTC", "hnt_burned": 999.0})

d, v, cols = m.pick_columns(rows)
assert d == "day", (d, cols)
assert v == "hnt_burned", (v, cols)

daily, date_col, value_col, skipped, first_day = m.process_rows(rows, today_utc=today)
assert first_day.isoformat() == "2026-08-04", first_day
assert len(daily) == 31, len(daily)
assert daily[0]["date"] == "2026-08-04", daily[0]
assert daily[-1]["date"] == "2026-09-03", daily[-1]
assert all(r["date"] != "2026-09-04" for r in daily)
assert skipped == 2, skipped  # today + old row
assert date_col == "day"
assert value_col == "hnt_burned"

# The app can hide T-1 and still has exactly 30 rows through T-2.
display_cutoff = (today - timedelta(days=2)).isoformat()
display_rows = [r for r in daily if r["date"] <= display_cutoff]
assert len(display_rows) == 30, len(display_rows)
assert display_rows[-1]["date"] == "2026-09-02", display_rows[-1]

print("v1.4.0 offline smoke tests passed: cache through T-1; 30 display rows through T-2.")
