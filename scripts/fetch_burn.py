#!/usr/bin/env python3
"""
Fetch the latest cached result of a public Dune query and publish a small,
app-friendly HNT daily burn cache.

IMPORTANT:
- This DOES NOT execute/refresh the Dune query.
- It only calls GET /api/v1/query/{query_id}/results.
- The Dune API key stays in GitHub Actions Secrets.
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

DUNE_QUERY_ID = os.environ.get("DUNE_QUERY_ID", "3342070").strip()
DUNE_API_KEY = os.environ.get("DUNE_API_KEY", "").strip()
OUT_DIR = Path(os.environ.get("OUT_DIR", "site"))
MAX_ROWS = int(os.environ.get("MAX_ROWS", "5000"))
STALE_AFTER_DAYS = int(os.environ.get("STALE_AFTER_DAYS", "2"))

DATE_CANDIDATES = [
    "date", "day", "block_date", "burn_date", "dt",
    "block_day", "timestamp", "time"
]

VALUE_CANDIDATES = [
    "hnt_burned", "hnt_burnt", "hnt_burn", "burned_hnt", "burnt_hnt",
    "daily_hnt_burned", "daily_hnt_burnt", "hnt_amount", "amount_hnt",
    "amount"
]


def fail(message: str, raw=None):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    status = {
        "ok": False,
        "status": "error",
        "message": message,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "query_id": DUNE_QUERY_ID,
    }
    (OUT_DIR / "status.json").write_text(
        json.dumps(status, indent=2), encoding="utf-8"
    )
    if raw is not None:
        (OUT_DIR / "last-error-response.json").write_text(
            json.dumps(raw, indent=2, default=str), encoding="utf-8"
        )
    print(message, file=sys.stderr)
    sys.exit(1)


def dune_get_latest():
    if not DUNE_API_KEY:
        fail("DUNE_API_KEY is missing. Add it as a GitHub Actions repository secret.")

    params = urllib.parse.urlencode({
        "limit": MAX_ROWS,
    })
    url = f"https://api.dune.com/api/v1/query/{DUNE_QUERY_ID}/results?{params}"

    req = urllib.request.Request(
        url,
        headers={
            "X-DUNE-API-KEY": DUNE_API_KEY,
            "Accept": "application/json",
            "User-Agent": "hnt-burn-cache/1.0",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except Exception as exc:
        fail(f"Dune request failed: {exc}")


def normalize_date(value):
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    # Fast path: YYYY-MM-DD...
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        try:
            return date.fromisoformat(text[:10]).isoformat()
        except ValueError:
            pass

    # ISO timestamp
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt.date().isoformat()
    except ValueError:
        return None


def normalize_number(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def pick_columns(rows):
    keys = list(rows[0].keys())
    lower_to_original = {k.lower(): k for k in keys}

    date_col = None
    for candidate in DATE_CANDIDATES:
        if candidate in lower_to_original:
            date_col = lower_to_original[candidate]
            break

    if date_col is None:
        # Prefer a column whose values parse as dates.
        for key in keys:
            successes = sum(normalize_date(r.get(key)) is not None for r in rows[:20])
            if successes >= max(1, min(3, len(rows[:20]))):
                date_col = key
                break

    value_col = None
    for candidate in VALUE_CANDIDATES:
        if candidate in lower_to_original:
            value_col = lower_to_original[candidate]
            break

    if value_col is None:
        # Prefer columns mentioning HNT + burn.
        for key in keys:
            lk = key.lower()
            if "hnt" in lk and ("burn" in lk or "burnt" in lk or "burned" in lk):
                value_col = key
                break

    if value_col is None:
        # Last-resort: first mostly-numeric non-date column.
        for key in keys:
            if key == date_col:
                continue
            successes = sum(normalize_number(r.get(key)) is not None for r in rows[:20])
            if successes >= max(1, min(3, len(rows[:20]))):
                value_col = key
                break

    return date_col, value_col, keys


def main():
    raw = dune_get_latest()

    rows = ((raw.get("result") or {}).get("rows") or [])
    if not rows:
        fail("Dune returned no result rows.", raw)

    date_col, value_col, all_columns = pick_columns(rows)
    if not date_col or not value_col:
        fail(
            "Could not identify the date/HNT-burn columns automatically. "
            f"Columns returned were: {all_columns}",
            raw,
        )

    # If Dune returns more than one row per day, sum them.
    per_day = {}
    skipped = 0
    for row in rows:
        d = normalize_date(row.get(date_col))
        v = normalize_number(row.get(value_col))
        if d is None or v is None:
            skipped += 1
            continue
        per_day[d] = per_day.get(d, 0.0) + v

    if not per_day:
        fail(
            f"No usable rows after parsing columns '{date_col}' and '{value_col}'.",
            raw,
        )

    daily = [
        {"date": d, "hnt_burned": round(per_day[d], 9)}
        for d in sorted(per_day.keys())
    ]

    latest = daily[-1]
    today_utc = datetime.now(timezone.utc).date()
    latest_date = date.fromisoformat(latest["date"])
    age_days = (today_utc - latest_date).days
    stale = age_days > STALE_AFTER_DAYS

    # Prefer yesterday-or-earlier as "complete", because today's burn may still be growing.
    cutoff = (today_utc - timedelta(days=1)).isoformat()
    completed = [r for r in daily if r["date"] <= cutoff]
    latest_complete = completed[-1] if completed else latest

    execution_id = raw.get("execution_id")
    submitted_at = raw.get("submitted_at")
    expires_at = raw.get("expires_at")
    state = raw.get("state")
    generated = datetime.now(timezone.utc).isoformat()

    output = {
        "schema_version": 1,
        "ok": True,
        "status": "stale" if stale else "fresh",
        "query_id": DUNE_QUERY_ID,
        "generated_at_utc": generated,
        "source": {
            "provider": "Dune",
            "query_id": DUNE_QUERY_ID,
            "endpoint_mode": "latest_cached_result_only",
            "execution_id": execution_id,
            "execution_state": state,
            "execution_submitted_at": submitted_at,
            "execution_expires_at": expires_at,
            "detected_date_column": date_col,
            "detected_burn_column": value_col,
        },
        "latest_available_date": latest["date"],
        "latest_complete_date": latest_complete["date"],
        "latest_age_days": age_days,
        "stale_after_days": STALE_AFTER_DAYS,
        "row_count": len(daily),
        "skipped_source_rows": skipped,
        "data": daily,
    }

    status = {
        "ok": True,
        "status": output["status"],
        "message": (
            "Feed is current enough for use."
            if not stale
            else "Dune's cached query result appears stale. Do not treat it as current."
        ),
        "query_id": DUNE_QUERY_ID,
        "generated_at_utc": generated,
        "latest_available_date": latest["date"],
        "latest_complete_date": latest_complete["date"],
        "latest_age_days": age_days,
        "source_execution_id": execution_id,
        "source_execution_submitted_at": submitted_at,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "hnt-burn.json").write_text(
        json.dumps(output, indent=2), encoding="utf-8"
    )
    (OUT_DIR / "latest.json").write_text(
        json.dumps({
            "ok": True,
            "status": output["status"],
            **latest,
            "generated_at_utc": generated,
        }, indent=2),
        encoding="utf-8",
    )
    (OUT_DIR / "latest-complete.json").write_text(
        json.dumps({
            "ok": True,
            "status": output["status"],
            **latest_complete,
            "generated_at_utc": generated,
        }, indent=2),
        encoding="utf-8",
    )
    (OUT_DIR / "status.json").write_text(
        json.dumps(status, indent=2), encoding="utf-8"
    )

    print(
        f"Published {len(daily)} daily rows. "
        f"Latest={latest['date']} ({latest['hnt_burned']} HNT), "
        f"status={output['status']}."
    )


if __name__ == "__main__":
    main()
