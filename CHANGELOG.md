# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

**Pipeline / data**

- Activity `gear_id` on analysis CSVs; shoe mileage = `TRACKED_GEAR` baseline + summed activity miles by `gear_id`.
- `StravaClient.get_activity_zones` and per-HR-zone time columns (`hr_zone_1_sec` … `hr_zone_5_sec`).

**Dashboard**

- **Metrics** page: Achievements, Key Indicators, Inspect, and **Shoes**.
- **Training**: Races strip (with chart diamonds), elevation chart, HR Zones stack + last-week donut, and 80:20 ⓘ.
- **Fitness**: elevation-adjusted aerobic efficiency; Fitness & Freshness (TRIMP → Banister Fitness / Fatigue / Form).
- **Performance**: Personal Records cards above the race scatter.

### Changed

**Pipeline / data**

- Easy/hard metrics (`%_easy`, `mt_min_easy`, `mt_min_hard`) use Strava heartrate **zones** (Z1–Z2 easy, remaining zones moderate/hard) instead of a fixed HR stream threshold.

**Dashboard**

- Renamed pages: Training Overview → **Training**, Training Insights → **Fitness**, Race Results → **Performance**.
- Moved Key Indicators from Training Overview onto **Metrics**. Chart homes: HR Zones → Training (after elevation); mileage heatmap → Training expander. Fitness order: Avg HR by Pace → Aerobic Efficiency → Fitness & Freshness.
- **Training** polish: shared race strip, wider bar charts, horizontal Easy→Hard 80:20 legend, in-progress hatching, earthy palette.
- **Fitness** Avg HR by Pace: multi-select pace bands, trend-only rolling lines, elevation residual vs ft/mi, HTML title + ⓘ, fixed darker=faster colors.
- **Fitness** Aerobic Efficiency: line + markers + dashed trend; Fitness & Freshness Form as shaded area; aligned gutters/ⓘ after titles.
- **Performance**: transparent Race History table; row selection highlights the scatter; chart width matches the table.
- Week hovers use Mon–Sun date ranges; nav **On this page** sits under the page list.

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
