#!/usr/bin/env python3
"""
HNT Daily Burn Public Cache v1.3.0

Execute a fresh, deliberately small Dune SQL wrapper around public query 3342070,
wait for it to finish, retrieve the result, and publish app-friendly JSON files.

Important design points:
- No dependency on an old/expired cached execution.
- The wrapper asks Dune for only the newest HISTORY_DAYS daily rows.
- HISTORY_DAYS defaults to 30.
- MAX_ROWS defaults to 1000 and remains a hard result-read ceiling.
- The Dune API key stays in GitHub Actions Secrets.
- The code never sets ignore_max_credits_per_request=true.

Dune Query View note:
The source public query is invoked as query_<id>. Dune executes that upstream query
when the wrapper runs. The wrapper limits the produced result to the newest 30 rows;
actual execution compute is still determined by Dune and the source query. Keep your
Dune account's query-cost/spend guardrails enabled as the execution safety guardrail.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

SOURCE_QUERY_ID = os.environ.get("DUNE_SOURCE_QUERY_ID", "3342070").strip()
DUNE_API_KEY = os.environ.get("DUNE_API_KEY", "").strip()
OUT_DIR = Path(os.environ.get("OUT_DIR", "site"))
HISTORY_DAYS = max(1, int(os.environ.get("HISTORY_DAYS", "30")))
MAX_ROWS = max(1, int(os.environ.get("MAX_ROWS", "1000")))
STALE_AFTER_DAYS = max(0, int(os.environ.get("STALE_AFTER_DAYS", "2")))
CACHE_VERSION = os.environ.get("CACHE_VERSION", "1.3.0").strip() or "1.3.0"
DUNE_PERFORMANCE = os.environ.get("DUNE_PERFORMANCE", "medium").strip().lower()
POLL_SECONDS = max(1, int(os.environ.get("POLL_SECONDS", "5")))
MAX_WAIT_SECONDS = max(30, int(os.environ.get("MAX_WAIT_SECONDS", "600")))

if DUNE_PERFORMANCE not in {"small", "medium", "large"}:
    DUNE_PERFORMANCE = "medium"

DATE_CANDIDATES = [
    "date", "day", "block_date", "burn_date", "dt",
    "block_day", "timestamp", "time"
]

VALUE_CANDIDATES = [
    "hnt_burned", "hnt_burnt", "hnt_burn", "burned_hnt", "burnt_hnt",
    "daily_hnt_burned", "daily_hnt_burnt", "hnt_amount", "amount_hnt",
    "amount"
]

TERMINAL_STATES = {
    "QUERY_STATE_COMPLETED",
    "QUERY_STATE_COMPLETED_PARTIAL",
    "QUERY_STATE_FAILED",
    "QUERY_STATE_CANCELED",
    "QUERY_STATE_CANCELLED",
    "QUERY_STATE_EXPIRED",
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def write_json(filename: str, value):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / filename).write_text(json.dumps(value, indent=2), encoding="utf-8")


def fail(message: str, raw=None, execution_id=None, execution_cost_credits=None):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    status = {
        "schema_version": 3,
        "cache_version": CACHE_VERSION,
        "ok": False,
        "status": "error",
        "message": message,
        "generated_at_utc": now_iso(),
        "source_query_id": SOURCE_QUERY_ID,
        "history_days": HISTORY_DAYS,
        "max_rows": MAX_ROWS,
        "dune_performance": DUNE_PERFORMANCE,
        "execution_id": execution_id,
        "execution_cost_credits": execution_cost_credits,
    }
    write_json("status.json", status)
    write_json(f"status-v{CACHE_VERSION}.json", status)
    if raw is not None:
        write_json("last-error-response.json", raw)
    print(message, file=sys.stderr)
    sys.exit(1)


def request_json(url: str, method="GET", payload=None, purpose="request", timeout=60):
    if not DUNE_API_KEY:
        fail("DUNE_API_KEY is missing. Add it as a GitHub Actions repository secret.")

    data = None
    headers = {
        "X-DUNE-API-KEY": DUNE_API_KEY,
        "Accept": "application/json",
        "User-Agent": f"hnt-burn-cache/{CACHE_VERSION}",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
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
        detail = f" Dune response: {json.dumps(parsed, ensure_ascii=False)[:2500]}" if parsed else ""
        fail(f"Dune {purpose} failed: HTTP {exc.code} {exc.reason}.{detail}", parsed)
    except urllib.error.URLError as exc:
        fail(f"Dune {purpose} failed: network error: {exc.reason}")
    except Exception as exc:
        fail(f"Dune {purpose} failed: {exc}")


def build_wrapper_sql(source_query_id: str, history_days: int) -> str:
    """Return enough newest rows to publish N settled daily values.

    Today and yesterday are deliberately excluded from the public cache.
    Therefore request HISTORY_DAYS + 2 source rows, then locally keep the
    30-day window ending on the day before yesterday (T-2).
    """
    qid = "".join(ch for ch in str(source_query_id) if ch.isdigit())
    if not qid or qid != str(source_query_id):
        raise ValueError("DUNE_SOURCE_QUERY_ID must contain digits only")
    row_limit = min(max(1, history_days + 2), MAX_ROWS)
    return (
        f"SELECT *\n"
        f"FROM query_{qid}\n"
        f"ORDER BY 1 DESC\n"
        f"LIMIT {row_limit}"
    )


def execute_fresh_query():
    sql = build_wrapper_sql(SOURCE_QUERY_ID, HISTORY_DAYS)
    payload = {
        "sql": sql,
        "performance": DUNE_PERFORMANCE,
    }
    print(
        f"Submitting fresh Dune execution: source query={SOURCE_QUERY_ID}, "
        f"source rows={min(HISTORY_DAYS + 2, MAX_ROWS)} (publish through T-2), engine={DUNE_PERFORMANCE}."
    )
    raw = request_json(
        "https://api.dune.com/api/v1/sql/execute",
        method="POST",
        payload=payload,
        purpose="SQL execution submission",
        timeout=60,
    )
    execution_id = raw.get("execution_id")
    if not execution_id:
        fail("Dune accepted no usable execution_id.", raw)
    return execution_id, sql, raw


def poll_execution(execution_id: str):
    deadline = time.monotonic() + MAX_WAIT_SECONDS
    last = None
    while time.monotonic() < deadline:
        last = request_json(
            f"https://api.dune.com/api/v1/execution/{execution_id}/status",
            purpose="execution status",
            timeout=60,
        )
        state = last.get("state")
        cost = last.get("execution_cost_credits")
        print(f"Dune execution state={state}; credits={cost if cost is not None else 'pending'}")

        if state in TERMINAL_STATES or last.get("is_execution_finished") is True:
            if state == "QUERY_STATE_COMPLETED":
                return last
            if state == "QUERY_STATE_COMPLETED_PARTIAL":
                fail(
                    "Dune returned a partial execution result; refusing to publish incomplete data.",
                    last,
                    execution_id=execution_id,
                    execution_cost_credits=cost,
                )
            err = last.get("error") or {}
            detail = err.get("message") if isinstance(err, dict) else str(err)
            fail(
                f"Dune execution ended in {state}. {detail or 'No further error detail was returned.'}",
                last,
                execution_id=execution_id,
                execution_cost_credits=cost,
            )
        time.sleep(POLL_SECONDS)

    fail(
        f"Dune execution did not finish within {MAX_WAIT_SECONDS} seconds.",
        last,
        execution_id=execution_id,
        execution_cost_credits=(last or {}).get("execution_cost_credits"),
    )


def get_execution_result(execution_id: str):
    # The executed SQL already returns at most HISTORY_DAYS rows. MAX_ROWS is a
    # second, user-requested hard ceiling on the API read itself.
    params = urllib.parse.urlencode({"limit": MAX_ROWS})
    return request_json(
        f"https://api.dune.com/api/v1/execution/{execution_id}/results?{params}",
        purpose="execution result read",
        timeout=60,
    )


def normalize_date(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        try:
            return date.fromisoformat(text[:10]).isoformat()
        except ValueError:
            pass
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


def process_rows(rows, today_utc=None):
    if not rows:
        raise ValueError("Dune returned no result rows.")

    date_col, value_col, all_columns = pick_columns(rows)
    if not date_col or not value_col:
        raise ValueError(
            "Could not identify the date/HNT-burn columns. "
            f"Columns returned were: {all_columns}"
        )

    today_utc = today_utc or datetime.now(timezone.utc).date()
    latest_publishable_day = today_utc - timedelta(days=2)
    first_day = latest_publishable_day - timedelta(days=HISTORY_DAYS - 1)

    per_day = {}
    skipped = 0
    for row in rows:
        d = normalize_date(row.get(date_col))
        v = normalize_number(row.get(value_col))
        if d is None or v is None:
            skipped += 1
            continue
        parsed_date = date.fromisoformat(d)
        # Strict safety check: never publish today or yesterday. The cache is
        # the settled 30-day window ending on the day before yesterday (T-2).
        if parsed_date < first_day or parsed_date > latest_publishable_day:
            skipped += 1
            continue
        per_day[d] = per_day.get(d, 0.0) + v

    if not per_day:
        raise ValueError(
            f"No usable rows fell inside the settled {HISTORY_DAYS}-day window "
            f"from {first_day.isoformat()} through {latest_publishable_day.isoformat()}."
        )

    daily = [
        {"date": d, "hnt_burned": round(per_day[d], 9)}
        for d in sorted(per_day.keys())
    ][-HISTORY_DAYS:]
    return daily, date_col, value_col, skipped, first_day


def main():
    execution_id, sql, submit_raw = execute_fresh_query()
    status_raw = poll_execution(execution_id)
    execution_cost = status_raw.get("execution_cost_credits")

    raw = get_execution_result(execution_id)
    rows = ((raw.get("result") or {}).get("rows") or [])
    try:
        daily, date_col, value_col, skipped, first_day = process_rows(rows)
    except ValueError as exc:
        fail(
            str(exc),
            raw,
            execution_id=execution_id,
            execution_cost_credits=execution_cost,
        )

    today_utc = datetime.now(timezone.utc).date()
    latest = daily[-1]
    latest_date = date.fromisoformat(latest["date"])
    age_days = (today_utc - latest_date).days
    stale = age_days > STALE_AFTER_DAYS

    expected_latest_date = (today_utc - timedelta(days=2)).isoformat()
    latest_complete = latest
    generated = now_iso()

    output = {
        "schema_version": 3,
        "cache_version": CACHE_VERSION,
        "ok": True,
        "status": "stale" if stale else "fresh",
        "source_query_id": SOURCE_QUERY_ID,
        "generated_at_utc": generated,
        "history_days": HISTORY_DAYS,
        "requested_from_date": first_day.isoformat(),
        "max_rows_per_result_read": MAX_ROWS,
        "source": {
            "provider": "Dune",
            "mode": "fresh_sql_execution_query_view",
            "source_query_id": SOURCE_QUERY_ID,
            "wrapper_rows_requested": min(HISTORY_DAYS + 2, MAX_ROWS),
            "wrapper_ordering": "ORDER BY first source column DESC",
            "dune_performance": DUNE_PERFORMANCE,
            "execution_id": execution_id,
            "execution_state": status_raw.get("state"),
            "execution_cost_credits": execution_cost,
            "execution_submitted_at": status_raw.get("submitted_at"),
            "execution_started_at": status_raw.get("execution_started_at"),
            "execution_ended_at": status_raw.get("execution_ended_at"),
            "execution_expires_at": status_raw.get("expires_at"),
            "detected_date_column": date_col,
            "detected_burn_column": value_col,
            "result_total_row_count": ((raw.get("result") or {}).get("metadata") or {}).get("total_row_count"),
        },
        "latest_available_date": latest["date"],
        "latest_complete_date": latest_complete["date"],
        "expected_latest_date": expected_latest_date,
        "settlement_lag_days": 2,
        "latest_age_days": age_days,
        "stale_after_days": STALE_AFTER_DAYS,
        "row_count": len(daily),
        "skipped_source_rows": skipped,
        "data": daily,
    }

    status = {
        "schema_version": 3,
        "cache_version": CACHE_VERSION,
        "ok": True,
        "status": output["status"],
        "message": (
            "Feed is current enough for use."
            if not stale
            else "The newly executed source produced an old latest date. Do not treat it as current."
        ),
        "source_query_id": SOURCE_QUERY_ID,
        "generated_at_utc": generated,
        "history_days": HISTORY_DAYS,
        "row_count": len(daily),
        "latest_available_date": latest["date"],
        "latest_complete_date": latest_complete["date"],
        "expected_latest_date": expected_latest_date,
        "settlement_lag_days": 2,
        "latest_age_days": age_days,
        "execution_id": execution_id,
        "execution_cost_credits": execution_cost,
        "dune_performance": DUNE_PERFORMANCE,
    }

    latest_doc = {
        "schema_version": 3,
        "cache_version": CACHE_VERSION,
        "ok": True,
        "status": output["status"],
        **latest,
        "generated_at_utc": generated,
    }
    latest_complete_doc = {
        "schema_version": 3,
        "cache_version": CACHE_VERSION,
        "ok": True,
        "status": output["status"],
        **latest_complete,
        "generated_at_utc": generated,
    }
    version_doc = {
        "cache_version": CACHE_VERSION,
        "schema_version": 3,
        "history_days": HISTORY_DAYS,
        "settlement_lag_days": 2,
        "source_query_id": SOURCE_QUERY_ID,
        "mode": "fresh_sql_execution_query_view",
        "generated_at_utc": generated,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Stable aliases for existing clients.
    write_json("hnt-burn.json", output)
    write_json("latest.json", latest_doc)
    write_json("latest-complete.json", latest_complete_doc)
    write_json("status.json", status)
    write_json("version.json", version_doc)

    # Versioned files prevent old browser/app caches from being mistaken for this build.
    write_json(f"hnt-burn-v{CACHE_VERSION}.json", output)
    write_json(f"latest-v{CACHE_VERSION}.json", latest_doc)
    write_json(f"latest-complete-v{CACHE_VERSION}.json", latest_complete_doc)
    write_json(f"status-v{CACHE_VERSION}.json", status)

    print(
        f"Published {len(daily)} daily rows. Latest={latest['date']} "
        f"({latest['hnt_burned']} HNT), execution credits={execution_cost}, "
        f"status={output['status']}, cache_version={CACHE_VERSION}."
    )


if __name__ == "__main__":
    main()
