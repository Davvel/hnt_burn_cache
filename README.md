# HNT Daily Burn Public Cache — v1.1.0

This repository turns Dune query **3342070** (`Daily HNT Token Burned Amount`) into a tiny public JSON feed for the HNT Monitor app.

## What changed in v1.1.0

The cache no longer asks Dune for thousands of historical rows and then trims them locally.

Each refresh now does:

1. A **1-row schema probe** to discover the public query's date and HNT-burn column names.
2. A second Dune read using **server-side filtering for only the last 30 calendar days**.
3. The data request has a hard `MAX_ROWS=1000` safety cap and requests only the two required columns.
4. The published JSON is also checked locally and limited to at most 30 daily entries.

Dune documents that filtering, column selection, sorting and `limit` are supported on the latest-result endpoint. This project still uses the latest cached result only; it does **not** execute the Dune SQL query.

## Architecture

Dune cached query result
→ GitHub Actions (once per day)
→ GitHub Pages
→ public JSON
→ HNT Monitor app

The Android/PWA app never receives the Dune API key.

## Dune cost controls

Workflow settings:

```text
HISTORY_DAYS=30
MAX_ROWS=1000
```

The actual data request is filtered on Dune's server to the last 30 days. The 1,000-row value is only a hard ceiling; for a daily aggregate query the normal response should be around 30 rows.

Keep your Dune account's **per-read credit limit** at the value you selected (for example 25 credits). The script does not bypass that limit.

## Published files

Versioned endpoints for this package:

```text
/hnt-burn-v1.1.0.json
/latest-v1.1.0.json
/latest-complete-v1.1.0.json
/status-v1.1.0.json
/version.json
```

Stable aliases are also generated for compatibility:

```text
/hnt-burn.json
/latest.json
/latest-complete.json
/status.json
```

The status page itself reads the **versioned** history file and adds a changing `?cb=` query parameter, so browsers should not keep showing an old deployment.

## Replace your existing GitHub repository files

1. Unzip this package.
2. Copy **all contents** into your local `hnt_burn_cache` repository, replacing existing files when prompted.
3. Do **not** delete the repository's `.git` folder. It is GitHub Desktop's local repository metadata.
4. The `.github` folder in this package is different from `.git` and must remain; it contains the GitHub Actions workflow.
5. Commit the changes in GitHub Desktop and push to `main`.
6. Your existing GitHub repository secret named `DUNE_API_KEY` remains in GitHub; it is not stored in this ZIP and does not need to be recreated.
7. Go to GitHub → **Actions → Refresh HNT burn cache → Run workflow**.

## If the workflow fails again

The updated script now prints Dune's response body for HTTP errors. For example, instead of only:

```text
HTTP Error 412: Precondition Failed
```

GitHub Actions should also show Dune's explanation, which will make the next diagnosis much easier.

## GitHub Pages

Repository Settings → Pages → Build and deployment → **Source: GitHub Actions**.

The workflow runs every day at **03:17 Europe/Malta time** and can also be run manually.

## Public cache fields

`hnt-burn-v1.1.0.json` includes:

- `cache_version: "1.1.0"`
- `schema_version: 2`
- `history_days: 30`
- `requested_from_date`
- `max_rows_per_data_request: 1000`
- `row_count`
- `latest_available_date`
- `latest_complete_date`
- `data` — at most 30 daily rows

## Browser/app cache busting

For new app code, prefer the versioned URL:

```text
.../hnt-burn-v1.1.0.json
```

If you want to guarantee a fresh HTTP read in a browser or mobile client, append a changing query parameter when refreshing:

```text
.../hnt-burn-v1.1.0.json?cb=TIMESTAMP
```

The web status page already does this automatically.

## Security

Never put `DUNE_API_KEY` in source code, JSON files, the APK/PWA, screenshots, or Git commits. Keep it only in GitHub Actions → Repository secrets.
