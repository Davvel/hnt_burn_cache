# Changelog

## v1.3.0 - 2026-09-02

- Changed the settlement boundary from yesterday (T-1) to the day before yesterday (T-2).
- Today and yesterday are now always excluded from the published burn cache.
- Requests 32 newest Dune daily rows so that, after dropping T and T-1, a full 30 settled days can still be published.
- Added `expected_latest_date` and `settlement_lag_days: 2` to cache/status metadata.
- Updated offline tests to verify that a 2 September run ends on 31 August.

## v1.2.1 - 2026-08-31

- Changed API execution engine from `small` to `medium`.
- Fixes Dune HTTP 400: `This performance tier is not available with your subscription` when Small is requested programmatically.
- Keeps the same 30-row wrapper, `MAX_ROWS=1000`, detailed error reporting, and versioned browser-cache files.
- Invalid engine configuration now falls back to `medium` rather than `small`.

## v1.2.0 - 2026-08-31

- Replaced the expired-cache-only approach with a fresh Dune execution on every scheduled/manual refresh.
- Uses Dune `POST /api/v1/sql/execute`, which works with a `Read` API key.
- Executes a small wrapper around public query `3342070` and asks for only the newest 30 daily rows (`ORDER BY 1 DESC LIMIT 30`).
- Polls Dune's execution-status endpoint until the query completes; status polling itself does not consume credits.
- Fetches the completed execution using a hard `MAX_ROWS=1000` result-read ceiling.
- Keeps a strict local calendar check so only the last 30 UTC calendar days can be published.
- Defaults to Dune's `small` engine to favor lower credit usage.
- Publishes Dune's actual `execution_cost_credits` in `status.json` and `hnt-burn*.json` for easy monitoring.
- Keeps detailed Dune error responses in GitHub Actions logs.
- Bumped published JSON schema to version 3.
- Added v1.2.0 versioned public files while retaining stable aliases for existing clients.
- Browser status page now uses the v1.2.0 filename plus a changing cache-buster.

## v1.1.0 - 2026-08-31

- Tried to read only the last 30 calendar days from query `3342070`'s cached result.
- Added detailed HTTP error reporting, which revealed that the source execution had expired.
