# HNT Daily Burn Public Cache — v1.5.1

## Performance tier compatibility update

The supplied v1.5.0 code already sends valid JSON containing performance=medium.
Dune documents medium as valid, but the supplied run rejected it with HTTP 400
Invalid performance tier. That log alone does not establish the underlying reason.

v1.5.1 sets DUNE_PERFORMANCE=auto and omits the optional performance field from
raw SQL submission. This lets Dune use its default. It does not send the literal
value auto to Dune, retry with a larger engine, or substitute old query results.

This is a compatibility workaround, not a confirmed account-level fix. Offline
checks passed; an authenticated GitHub Actions run is required to verify it.
If the default request is also rejected, check API execution access and available
engines for the Dune account/team that owns the API key. Contact Dune support if
needed. Changing JSON formatting alone will not fix an account restriction.

## Deployment

1. Extract this ZIP into your existing hnt_burn_cache repository folder.
2. Copy/replace its contents, including .github/workflows/refresh-hnt-burn.yml.
   Keep your existing .git folder. The ZIP does not contain Git history.
3. Commit and push the changes using GitHub Desktop.
4. Open GitHub Actions → Refresh HNT burn cache → Run workflow → Run workflow.
   Start a NEW run; re-running an old run uses its old commit.
5. Check the submission log says engine=auto and then returns execution states.
6. If it fails, share the new error text. Do not share DUNE_API_KEY.

Your existing GitHub repository secret DUNE_API_KEY is still used.

## Cache policy (unchanged)

Every run executes fresh SQL wrapping public query 3342070:

```sql
SELECT *
FROM query_3342070
ORDER BY 1 DESC
LIMIT 32
```

With HISTORY_DAYS=30, the cache includes today (possibly partial), yesterday,
and 30 days ending at T-2 when the source provides those rows. The app should
filter dates to today minus two days and use the newest 30 matching rows.
The result limit bounds returned rows, not upstream execution compute.
Keep Dune spending and query-cost guardrails enabled.

Stable endpoints remain hnt-burn.json, latest.json, latest-complete.json,
status.json, and version.json. New versioned files use v1.5.1.

If a run fails before deployment, the currently published Pages site is unchanged.

## Offline verification

```bash
python scripts/test_parser.py
python scripts/test_submission.py
```

Checks cover the existing 32-row cache/T-2 behavior, HTTP submission without a
tier override, explicit tier selection, and HTTP 400/401 failure handling.
No live Dune query is executed by these checks.
