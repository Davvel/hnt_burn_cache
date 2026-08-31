# HNT Daily Burn Public Cache — v1.2.1

This repository publishes a tiny public JSON feed containing the latest **30 days of daily HNT burned** for the HNT Monitor app.

## Why v1.2.1 exists

v1.1.0 correctly tried to read only recent rows, but Dune returned:

```text
query execution result already expired
```

v1.2.1 keeps the v1.2.0 fresh-execution design and fixes the engine selection. v1.2.0 no longer depends on somebody else's still-live cached execution. Each GitHub Action run starts a **fresh Dune execution**, waits for it to finish, reads the small result, and then publishes it to GitHub Pages.

The previous v1.2.0 build requested the `small` engine through the API. Dune rejected that with `This performance tier is not available with your subscription`. Dune documents Medium as the default engine for programmatic/API executions, so v1.2.1 uses `medium`.

## What the Dune execution does

The code executes this small DuneSQL wrapper:

```sql
SELECT *
FROM query_3342070
ORDER BY 1 DESC
LIMIT 30
```

Query `3342070` is `Daily HNT Token Burned Amount`, so one result row represents one daily value. The wrapper therefore asks for the **30 newest daily rows**, not thousands of historical rows.

The API result read has an additional hard ceiling:

```text
MAX_ROWS=1000
```

The script then performs a second local date check and refuses to publish dates outside the current 30-day UTC calendar window.

### Important Dune cost note

Dune Query Views execute their upstream query when called. Therefore, although this wrapper returns only the latest 30 rows, the compute cost of the underlying public query is still determined by Dune and the source SQL. Keep the **global per-query cost cap** enabled in your Dune account. The script never bypasses Dune's credit guardrails.

After each successful run, `execution_cost_credits` is written into the public status JSON so you can see what the execution actually cost.

## Architecture

```text
Dune public query 3342070
        ↓ fresh execution
Dune wrapper: newest 30 rows only
        ↓
GitHub Actions (daily)
        ↓
GitHub Pages JSON cache
        ↓
HNT Monitor app / all users
```

Your users never call Dune directly and never receive your Dune API key.

## Dune configuration

Your existing GitHub repository secret remains:

```text
DUNE_API_KEY
```

The key needs only **Read** scope for Dune's Execute SQL endpoint.

Workflow defaults:

```text
DUNE_SOURCE_QUERY_ID=3342070
HISTORY_DAYS=30
MAX_ROWS=1000
DUNE_PERFORMANCE=medium
MAX_WAIT_SECONDS=600
```

## Published files

Versioned v1.2.1 endpoints:

```text
/hnt-burn-v1.2.1.json
/latest-v1.2.1.json
/latest-complete-v1.2.1.json
/status-v1.2.1.json
/version.json
```

Stable compatibility aliases are also produced:

```text
/hnt-burn.json
/latest.json
/latest-complete.json
/status.json
```

The versioned URLs plus `?cb=TIMESTAMP` browser cache-busting prevent an old deployment from being confused with the current build.

## Replace your existing GitHub repository files

1. Unzip this package.
2. Copy **everything inside** it into your existing local `hnt_burn_cache` repository.
3. Choose **Replace** when Windows asks about existing files.
4. Do **not** delete the hidden `.git` folder in your existing repository.
5. The `.github` folder from this package **must** replace/update the existing `.github` folder; it contains the workflow.
6. Open GitHub Desktop.
7. Commit the changes, for example: `HNT Burn Cache v1.2.1 - use Medium API engine`.
8. Click **Push origin**.
9. On github.com, verify `VERSION.txt` says `1.2.1`.
10. Go to **Actions → Refresh HNT burn cache → Run workflow**.

Your `DUNE_API_KEY` secret is stored by GitHub and is not inside this ZIP, so replacing repository files does not remove it.

## What to look for in GitHub Actions

The v1.2.1 step is named:

```text
Execute fresh HNT burn query and fetch last 30 days
```

During execution you should see lines similar to:

```text
Submitting fresh Dune execution: source query=3342070, latest rows=30, engine=medium.
Dune execution state=QUERY_STATE_PENDING; credits=pending
Dune execution state=QUERY_STATE_EXECUTING; credits=pending
Dune execution state=QUERY_STATE_COMPLETED; credits=...
Published ... daily rows...
```

If Dune rejects or fails the query, the workflow prints Dune's detailed response rather than only a generic HTTP code.

## Security

Never place `DUNE_API_KEY` in source code, JSON, the APK/PWA, screenshots, or commits. Keep it only in **GitHub repository secrets**.
