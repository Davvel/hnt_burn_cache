#!/usr/bin/env python3
"""
Fetch only the recent HNT daily-burn rows from the latest cached result of a
public Dune query and publish small app-friendly JSON files.

IMPORTANT:
- This DOES NOT execute/refresh the Dune query.
- It only calls GET /api/v1/query/{query_id}/results.
- A 1-row schema probe is used first so the script can discover the query's
  date and HNT-burn column names safely.
- The actual data request is filtered server-side to the last HISTORY_DAYS
  (30 by default), requests only the detected date/value columns, and has a
  hard MAX_ROWS cap (1000 by default).
- The Dune API key stays in GitHub Actions Secrets.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

DUNE_QUERY_ID = os.environ.get("DUNE_QUERY_ID", "3342070").strip()
DUNE_API_KEY = os.environ.get("DUNE_API_KEY", "").strip()
OUT_DIR = Path(os.environ.get("OUT_DIR", "site"))
HISTORY_DAYS = max(1, int(os.environ.get("HISTORY_DAYS", "30")))
MAX_ROWS = max(1, int(os.environ.get("MAX_ROWS", "1000")))
STALE_AFTER_DAYS = int(os.environ.get("STALE_AFTER_DAYS", "2"))
CACHE_VERSION = os.environ.get("CACHE_VERSION", "1.1.0").strip() or "1.1.0"

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
        "schema_version": 2,
        "cache_version": CACHE_VERSION,
        "ok": False,
        "status": "error",
        "message": message,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "query_id": DUNE_QUERY_ID,
        "history_days": HISTORY_DAYS,
        "max_rows": MAX_ROWS,
    }
    (OUT_DIR / "status.json").write_text(
        json.dumps(status, indent=2), encoding="utf-8"
    )
    (OUT_DIR / f"status-v{CACHE_VERSION}.json").write_text(
        json.dumps(status, indent=2), encoding="utf-8"
    )
    if raw is not None:
        (OUT_DIR / "last-error-response.json").write_text(
            json.dumps(raw, indent=2, default=str), encoding="utf-8"
        )
    print(message, file=sys.stderr)
    sys.exit(1)


def dune_request(params, purpose):
    """Read the latest cached Dune result. Never executes the query."""
    if not DUNE_API_KEY:
        fail("DUNE_API_KEY is missing. Add it as a GitHub Actions repository secret.")

    query_string = urllib.parse.urlencode(params)
    url = f"https://api.dune.com/api/v1/query/{DUNE_QUERY_ID}/results"
    if query_string:
        url += f"?{query_string}"

    req = urllib.request.Request(
        url,
        headers={
            "X-DUNE-API-KEY": DUNE_API_KEY,
            "Accept": "application/json",
            "User-Agent": f"hnt-burn-cache/{CACHE_VERSION}",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""

        parsed = None
        if body:
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                parsed = {"response_text": body[:4000]}

        detail = ""
        if parsed:
            detail = f" Dune response: {json.dumps(parsed, ensure_ascii=False)[:2000]}"

        fail(
            f"Dune {purpose} request failed: HTTP {exc.code} {exc.reason}.{detail}",
            parsed,
        )
    except urllib.error.URLError as exc:
        fail(f"Dune {purpose} request failed: network error: {exc.reason}")
    except Exception as exc:
        fail(f"Dune {purpose} request failed: {exc}")


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
        for key in keys:
            lk = key.lower()
            if "hnt" in lk and ("burn" in lk or "burnt" in lk or "burned" in lk):
                value_col = key
                break

    if value_col is None:
        for key in keys:
            if key == date_col:
                continue
            successes = sum(normalize_number(r.get(key)) is not None for r in rows[:20])
            if successes >= max(1, min(3, len(rows[:20]))):
                value_col = key
                break

    return date_col, value_col, keys


def dune_identifier(name: str) -> str:
    """Quote a Dune result-column identifier only when necessary."""
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        return name
    return '"' + name.replace('"', '""') + '"'


def build_recent_params(date_col: str, value_col: str, start_date: str):
    date_id = dune_identifier(date_col)
    value_id = dune_identifier(value_col)
    return {
        # User-requested hard cap. The date filter should normally return ~30 rows.
        "limit": MAX_ROWS,
        # Dune applies this on the server, so old history is not transferred.
        "filters": f"{date_id} >= '{start_date}'",
        # Only transfer the two fields the cache needs.
        "columns": f"{date_id},{value_id}",
        "sort_by": f"{date_id} asc",
    }


def write_json(filename: str, value):
    (OUT_DIR / filename).write_text(json.dumps(value, indent=2), encoding="utf-8")


def main():
    # Tiny one-row read to discover column names. This avoids guessing whether
    # the public query uses date/day/block_date/etc. It does not fetch history.
    probe = dune_request({"limit": 1}, "schema probe")
    probe_rows = ((probe.get("result") or {}).get("rows") or [])
    if not probe_rows:
        fail("Dune returned no rows during the 1-row schema probe.", probe)

    date_col, value_col, all_columns = pick_columns(probe_rows)
    if not date_col or not value_col:
        fail(
            "Could not identify the date/HNT-burn columns from the schema probe. "
            f"Columns returned were: {all_columns}",
            probe,
        )

    today_utc = datetime.now(timezone.utc).date()
    first_day = today_utc - timedelta(days=HISTORY_DAYS - 1)

    # Actual data read: server-side filter to the last 30 calendar days,
    # max 1000 rows, and only the detected date/value columns.
    raw = dune_request(
        build_recent_params(date_col, value_col, first_day.isoformat()),
        f"last-{HISTORY_DAYS}-days data",
    )

    rows = ((raw.get("result") or {}).get("rows") or [])
    if not rows:
        fail(
            f"Dune returned no rows for the last {HISTORY_DAYS} days "
            f"starting {first_day.isoformat()}.",
            raw,
        )

    # If Dune returns more than one row per day, sum them.
    # Also enforce the 30-day window locally as a second safety check.
    per_day = {}
    skipped = 0
    for row in rows:
        d = normalize_date(row.get(date_col))
        v = normalize_number(row.get(value_col))
        if d is None or v is None:
            skipped += 1
            continue
        parsed_date = date.fromisoformat(d)
        if parsed_date < first_day or parsed_date > today_utc:
            skipped += 1
            continue
        per_day[d] = per_day.get(d, 0.0) + v

    if not per_day:
        fail(
            f"No usable rows after parsing '{date_col}' and '{value_col}' "
            f"inside the last {HISTORY_DAYS} days.",
            raw,
        )

    daily = [
        {"date": d, "hnt_burned": round(per_day[d], 9)}
        for d in sorted(per_day.keys())
    ]

    # Strictly keep at most HISTORY_DAYS daily entries even if the source has
    # duplicate/odd dates or the query semantics change later.
    daily = daily[-HISTORY_DAYS:]

    latest = daily[-1]
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
        "schema_version": 2,
        "cache_version": CACHE_VERSION,
        "ok": True,
        "status": "stale" if stale else "fresh",
        "query_id": DUNE_QUERY_ID,
        "generated_at_utc": generated,
        "history_days": HISTORY_DAYS,
        "requested_from_date": first_day.isoformat(),
        "max_rows_per_data_request": MAX_ROWS,
        "source": {
            "provider": "Dune",
            "query_id": DUNE_QUERY_ID,
            "endpoint_mode": "latest_cached_result_only",
            "server_side_filtered": True,
            "schema_probe_rows": 1,
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
        "schema_version": 2,
        "cache_version": CACHE_VERSION,
        "ok": True,
        "status": output["status"],
        "message": (
            "Feed is current enough for use."
            if not stale
            else "Dune's cached query result appears stale. Do not treat it as current."
        ),
        "query_id": DUNE_QUERY_ID,
        "generated_at_utc": generated,
        "history_days": HISTORY_DAYS,
        "row_count": len(daily),
        "latest_available_date": latest["date"],
        "latest_complete_date": latest_complete["date"],
        "latest_age_days": age_days,
        "source_execution_id": execution_id,
        "source_execution_submitted_at": submitted_at,
    }

    latest_doc = {
        "schema_version": 2,
        "cache_version": CACHE_VERSION,
        "ok": True,
        "status": output["status"],
        **latest,
        "generated_at_utc": generated,
    }
    latest_complete_doc = {
        "schema_version": 2,
        "cache_version": CACHE_VERSION,
        "ok": True,
        "status": output["status"],
        **latest_complete,
        "generated_at_utc": generated,
    }
    version_doc = {
        "cache_version": CACHE_VERSION,
        "schema_version": 2,
        "history_days": HISTORY_DAYS,
        "generated_at_utc": generated,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Stable aliases for existing app clients.
    write_json("hnt-burn.json", output)
    write_json("latest.json", latest_doc)
    write_json("latest-complete.json", latest_complete_doc)
    write_json("status.json", status)
    write_json("version.json", version_doc)

    # Versioned aliases to avoid browser confusion between package revisions.
    write_json(f"hnt-burn-v{CACHE_VERSION}.json", output)
    write_json(f"latest-v{CACHE_VERSION}.json", latest_doc)
    write_json(f"latest-complete-v{CACHE_VERSION}.json", latest_complete_doc)
    write_json(f"status-v{CACHE_VERSION}.json", status)

    print(
        f"Published {len(daily)} daily rows (last {HISTORY_DAYS} days only). "
        f"Latest={latest['date']} ({latest['hnt_burned']} HNT), "
        f"status={output['status']}, cache_version={CACHE_VERSION}."
    )


if __name__ == "__main__":
    main()
