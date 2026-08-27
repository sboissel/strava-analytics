# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.5.2] — 2026-08-26

### Fixed

**Dashboard**

- **Streamlit Cloud**: `AttributeError` on `_bootstrap.ensure_sys_path` from a stale/wrong `_bootstrap` in `sys.modules`; entrypoint and pages now load `_bootstrap.py` by absolute file path and replace the cached module.
- **Streamlit Cloud**: `ImportError` for `compare_race_type_options` (and related Performance exports) when a stale `race_data` object still pointed at the correct file path; bootstrap now reloads `race_data` from disk when required attrs are missing.

**Pipeline / data**

- GitLab daily sync: stop ignoring CI-managed `data/` CSVs so `git add data/` can commit updates for Streamlit Cloud (v1.5.0 had ignored the whole `data/` tree).

## [1.5.1] — 2026-08-26

### Fixed

**Dashboard**

- **Streamlit Cloud**: Performance (and other) pages failed with `ImportError` on `from race_data import …` when Streamlit reset `sys.path` after the entrypoint while caching `_bootstrap`; pages now re-apply dashboard/`src` path setup on every load.

## [1.5.0] — 2026-08-26

### Added

**Dashboard**

- **Performance**: Race Build-Up Comparison — side-by-side pre-race training for two races of the same type (weekly mileage, HR-zone shares, easy:hard mix, and summary metrics with deltas).
- **Performance**: type-aware build-up windows, HR coverage gates for zone charts, and shared mileage axis scaling for fair compare.

### Changed

**Dashboard**

- Theme and UI helpers for build-up panels, delta tables, and HR pie summaries on Performance.

## [1.4.0] — 2026-08-22

### Added

**Dashboard**

- **Fitness**: Races strip under Controls (same legend and period markers as Training) plus gold race diamonds on all three charts.
- **Fitness**: sidebar **Races** jump target on the Fitness page.

### Changed

**Dashboard**

- **Fitness**: Average HR, Aerobic Efficiency, and Fitness & Freshness share a locked category x-axis range so period ticks line up across the stack.
- **Fitness**: race diamonds on Aerobic Efficiency and Fitness & Freshness sit farther above line markers; the y-axis extends when a race falls at a chart peak so diamonds stay in view.
- **Fitness & Freshness**: legend shows lines only (markers remain on the plot).
- **Metrics**: Easy:Hard Last Week and 30 Days gauge colors turn green at **≥80%** easy (80:20 target); band thresholds are 80 / 70 / 60 / 50.

### Fixed

**Dashboard**

- **Streamlit Cloud**: Fitness page import error when the repo-root `data/` CSV directory shadowed `dashboard/data.py` on `sys.path`.

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
