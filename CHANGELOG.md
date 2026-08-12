# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] — 2026-08-12

### Added

- Streamlit **Runner's Dashboard** (`dashboard/`) with three pages: **Training Overview** (KPIs, 80:20 compliance, mileage charts), **Training Insights** (pace-bin HR trends and mileage heatmaps), and **Race Results** (finish-time/pace scatter chart, PR markers, race history table, and filters).
- Shared dashboard modules for data loading, Plotly charts, theme/CSS, and navigation.
- Dashboard unit tests under `tests/dashboard/` for `data`, `insights_data`, and `race_data`.

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
