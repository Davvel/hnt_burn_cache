# HNT Daily Burn Public Cache — v1.3.0

This repository publishes a public JSON feed containing **30 settled daily HNT burn values** for the HNT Monitor app.

## v1.3.0 settlement rule

The cache deliberately does **not** publish today or yesterday. The newest eligible day is always the **day before yesterday (T-2)**.

Example: if the workflow runs on **2 September 2026**, the newest cache day is **31 August 2026**. This gives the upstream Dune data an additional full day to settle before the value is treated as complete.

To keep a full 30-day public history after excluding today and yesterday, the Dune wrapper asks for 32 source rows:

```sql
SELECT *
FROM query_3342070
ORDER BY 1 DESC
LIMIT 32
```

The Python script then keeps only the 30-day UTC window ending at T-2. It rejects both T and T-1 even if Dune returns them.

## Architecture

```text
Dune public query 3342070
        ↓ fresh execution, newest 32 rows
GitHub Actions
        ↓ discard today + yesterday
30 settled daily values ending at T-2
        ↓
GitHub Pages JSON cache
        ↓
HNT Monitor app / all users
```

## Workflow defaults

```text
DUNE_SOURCE_QUERY_ID=3342070
HISTORY_DAYS=30
MAX_ROWS=1000
DUNE_PERFORMANCE=medium
MAX_WAIT_SECONDS=600
CACHE_VERSION=1.3.0
```

The scheduled workflow may still run at 03:17 Malta time because the result no longer depends on yesterday being fully settled.

## Published files

Versioned v1.3.0 endpoints:

```text
/hnt-burn-v1.3.0.json
/latest-v1.3.0.json
/latest-complete-v1.3.0.json
/status-v1.3.0.json
/version.json
```

Stable aliases remain:

```text
/hnt-burn.json
/latest.json
/latest-complete.json
/status.json
```

`latest.json` and `latest-complete.json` now normally identify the same T-2 record because the public dataset contains settled days only.

The main/status JSON also exposes:

```text
expected_latest_date
settlement_lag_days: 2
```

This makes it explicit what date the proxy expected to publish.

## Install / upgrade

1. Unzip this package.
2. Copy everything inside it over your existing local repository.
3. Replace existing files when prompted, but **do not delete your existing `.git` folder**.
4. The packaged `.github` folder should update your workflow.
5. Commit in GitHub Desktop, for example: `HNT Burn Cache v1.3.0 - settle at T-2`.
6. Push origin.
7. In GitHub, open **Actions → Refresh HNT burn cache → Run workflow** once to test it.
8. Check `status.json` and confirm `latest_available_date` is the day before yesterday.

Your `DUNE_API_KEY` remains stored in GitHub Secrets and is not included in this ZIP.

## Security / Dune cost

The proxy still performs a fresh Dune SQL execution and uses the `medium` API engine. The result read remains capped at 1000 rows. Keep your Dune account query-cost/spend guardrails enabled; the API key must remain only in GitHub repository secrets.
