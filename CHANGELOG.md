# Changelog

## v1.1.0 - 2026-08-31

- Changed Dune retrieval to fetch only the last 30 calendar days server-side.
- Added a 1-row schema probe so the public query's date/value column names do not have to be guessed.
- Set the Dune data-read hard cap to 1,000 rows.
- Requests only the detected date and HNT-burn columns for the 30-day data read.
- Improved Dune HTTP error reporting, including the response body for errors such as HTTP 412.
- Added `cache_version` and schema version 2 to published JSON.
- Added versioned public JSON filenames (`*-v1.1.0.json`) while retaining stable aliases.
- Added `version.json` and `VERSION.txt`.
- The status page uses versioned JSON plus a cache-busting query string to avoid stale browser content.
