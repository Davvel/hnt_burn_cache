# HNT Daily Burn Public Cache

This repository turns a Dune daily HNT-burn query into a tiny public JSON feed for an Android app.

## Architecture

Dune (API key hidden in GitHub Secret)
→ GitHub Actions (once per day)
→ GitHub Pages
→ public JSON
→ HNT Monitor app

The Android app never receives the Dune API key.

## Important limitation

This project calls:

`GET /api/v1/query/{query_id}/results`

That endpoint retrieves the **latest cached execution** on Dune. It does **not** execute or refresh the Dune SQL query.

The default query is:

- Dune query ID: `3342070`
- Title: `Daily HNT Token Burned Amount`

If Dune stops refreshing that query, this cache will mark the result as `stale`. It will not silently pretend an old value is current.

## Files published

After the workflow runs, GitHub Pages serves:

- `/latest-complete.json` — safest endpoint for the app; latest completed UTC day
- `/latest.json` — newest row present in Dune, possibly today's incomplete value
- `/hnt-burn.json` — full daily series returned by the query
- `/status.json` — feed health/freshness
- `/` — simple human-readable status page

Example `latest-complete.json`:

```json
{
  "ok": true,
  "status": "fresh",
  "date": "2026-08-30",
  "hnt_burned": 1234.567,
  "generated_at_utc": "2026-08-31T01:17:00+00:00"
}
```

## Step-by-step setup

### 1. Create a Dune account and API key

Create a free Dune account and generate an API key with Read access.

Do not place the API key in this repository or in the Android app.

Dune currently documents 2,500 included credits/month on its Free plan. Set the account's extra-credit/spend limit to `$0` if you want to ensure no additional billing can occur.

### 2. Create a GitHub repository

Create a new repository, for example:

`hnt-burn-cache`

A public repository is simplest for GitHub Pages on GitHub Free.

### 3. Upload this package

Unzip this package and copy all files into the repository.

The important paths are:

```text
.github/workflows/refresh-hnt-burn.yml
scripts/fetch_burn.py
site/index.html
```

Commit and push to the `main` branch.

### 4. Add the Dune key as a GitHub Secret

On GitHub:

1. Open the repository.
2. Go to **Settings**.
3. Open **Secrets and variables → Actions**.
4. Click **New repository secret**.
5. Name it exactly:

   `DUNE_API_KEY`

6. Paste your Dune API key as the value.
7. Save it.

The workflow reads it as `secrets.DUNE_API_KEY`; it is never written to the public files.

### 5. Enable GitHub Pages

In the repository:

1. Go to **Settings → Pages**.
2. Under **Build and deployment**, set **Source** to **GitHub Actions**.

### 6. Run the first refresh manually

1. Open the repository's **Actions** tab.
2. Choose **Refresh HNT burn cache**.
3. Click **Run workflow**.
4. Choose the `main` branch.
5. Run it.

When the run completes, the deployment job shows the GitHub Pages URL.

### 7. Test the public endpoints

Open the Pages URL.

Then test:

```text
https://YOUR-GITHUB-NAME.github.io/hnt-burn-cache/latest-complete.json
https://YOUR-GITHUB-NAME.github.io/hnt-burn-cache/status.json
https://YOUR-GITHUB-NAME.github.io/hnt-burn-cache/hnt-burn.json
```

Use `latest-complete.json` in the Android app when you only need yesterday's completed daily burn.

Use `hnt-burn.json` when you need a chart/history.

### 8. Automatic daily refresh

The workflow runs every day at **03:17 Europe/Malta time**.

The unusual minute (`:17`) is intentional because GitHub notes that scheduled workflows can be delayed during high load, especially around the start of the hour.

You can also press **Run workflow** at any time for a manual fetch.

## What happens if Dune is stale?

The script compares the newest returned daily date with today's UTC date.

By default:

- 0–2 days old → `fresh`
- more than 2 days old → `stale`

Check:

`/status.json`

The Android app should display/accept the last value but can label it stale, or refuse to update trading analytics from it.

## Changing the Dune query

Edit:

`.github/workflows/refresh-hnt-burn.yml`

and change:

```yaml
DUNE_QUERY_ID: "3342070"
```

The Python parser attempts to auto-detect the date and HNT-burn columns, so most daily-result queries should work without code changes.

If it cannot identify the columns, the Action fails and writes a useful error message in the workflow log.

## Android usage

For a single completed daily burn, GET:

`.../latest-complete.json`

Pseudo-response handling:

```kotlin
data class HntBurnLatest(
    val ok: Boolean,
    val status: String,
    val date: String,
    val hnt_burned: Double
)
```

For the 30-day chart, GET `hnt-burn.json`, then keep the last 30 entries in `data`.

Because GitHub Pages is a normal HTTPS static site, no Dune credentials are needed in the APK.

## Cost controls

To make this effectively zero-cash-cost:

1. Use Dune Free.
2. Set Dune extra spend limit to `$0`.
3. Fetch only once per day, plus occasional manual testing.
4. Do not let every Android installation call Dune directly.
5. Keep the API key only in GitHub Actions Secrets.

The Dune result-read endpoint still consumes included credits, so "free" here means staying inside the included Free-plan credits with additional spending disabled.

## Security

Safe to publish:

- HNT daily burn values
- Dune query ID
- GitHub Pages files

Never publish:

- `DUNE_API_KEY`
- a screenshot showing the API key
- the key in Android source/resources
- the key in Git commits

If a key is accidentally committed, revoke it in Dune and create a new one.
