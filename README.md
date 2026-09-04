# HNT Daily Burn Public Cache — v1.5.0

This repository publishes HNT daily burn data for the HNT Monitor app.

## v1.5.0 rule

The cache now **stores yesterday (T-1)** but never stores today's partial value.
The HNT Monitor app should continue to **display only through the day before yesterday (T-2)**.

Example: on **4 September 2026**:

- Cache contains data through **3 September**.
- `latest.json` points to **3 September**.
- `latest-complete.json` points to **2 September**.
- The mobile graph should hide 3 September and display through **2 September**.

The cache keeps 31 rows: yesterday plus 30 older settled days. Therefore the app still has a full 30-day graph after hiding yesterday.

## Dune wrapper

```sql
SELECT *
FROM query_3342070
ORDER BY 1 DESC
LIMIT 32
```

The 32 source rows cover today + yesterday + 30 older days. Python rejects today and publishes up to 31 rows ending at T-1.

## Workflow defaults

```text
DUNE_SOURCE_QUERY_ID=3342070
HISTORY_DAYS=30
MAX_ROWS=1000
DUNE_PERFORMANCE=medium
MAX_WAIT_SECONDS=600
CACHE_VERSION=1.4.0
```

## Published files

Stable aliases:

```text
/hnt-burn.json
/latest.json
/latest-complete.json
/status.json
/version.json
```

Versioned endpoints:

```text
/hnt-burn-v1.5.0.json
/latest-v1.5.0.json
/latest-complete-v1.5.0.json
/status-v1.5.0.json
```

## Upgrade

1. Copy the package contents over the existing repository.
2. Keep the existing `.git` folder.
3. Commit and push to GitHub.
4. Run **Actions → Refresh HNT burn cache → Run workflow** once.
5. On 4 Sep, for example, verify that `latest_available_date` is 3 Sep and `latest_complete_date` is 2 Sep.

Your `DUNE_API_KEY` remains in GitHub Secrets and is not included in this package.


## v1.5.0 cache policy
Every run is a full rebuild from Dune. The published cache includes today, even though today may be partial, plus yesterday and enough history for the app to show 30 complete days ending at T-2. The mobile app should filter the `data` array to `date <= today - 2 days` and take the newest 30 matching rows.
