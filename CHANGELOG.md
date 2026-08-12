# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] — 2026-08-12

### Added

- Streamlit **Race Results** page with finish-time scatter chart, PR star markers, race history table, and type/date filters.
- Chart toggle between **Finish Times** and **Pace** on Race Results.
- Richer race chart tooltips (date, name, time, distance, pace, type).

### Changed

- Dashboard module cleanup: shared data helpers, consolidated nav/CSS, removed dead code.
- README updated for dashboard layout and `PYTHONPATH=.:src`.

### Fixed

- Streamlit Cloud `KeyError` from bootstrap imports and missing CSV columns.
- Pace chart `KeyError` when cached race data lacked `pace_min`.

## [1.1.0] — 2026-08-12

### Added

- Weekly GitLab CI sync job that runs the Strava pipeline on a Sunday-night schedule and commits updated `data/` files back to `main`.

## [1.0.0] — 2026-08-12

### Added

- Base release of the Strava analytics pipeline.
- `StravaClient` for OAuth token refresh, activity pagination, and stream fetches.
- Activity enrichment helpers for HR easy/hard stats, pace bins, CSV merges, and weekly summaries.
- Unit tests for `activity_utils` and `strava` modules.
- GitLab CI test job with coverage reporting and README pipeline/coverage badges.
