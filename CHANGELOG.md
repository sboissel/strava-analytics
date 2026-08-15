# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Shoe mileage on **Metrics** from activity `gear_id` sums plus `TRACKED_GEAR` baselines (no Strava gear endpoint / `strava_gear.csv`).
- Unit tests for gear mileage aggregation (`tests/src/test_gear.py`) and dashboard shoe UI (`tests/dashboard/test_gear_ui.py`).
- **Metrics** dashboard page with **Achievements**, **Key Indicators**, Inspect, and **Shoes** mileage.
- **Training** **Races** marker strip under Controls: cool-gray squares for training periods, gold diamonds for race periods, and an ⓘ legend; gold diamonds also mark race periods on the 80:20, mileage, and elevation charts.
- Summed **elevation** chart (ft) on Training, on the same period axis as 80:20 and mileage.
- 100% stacked **Heart Rate Zones** area chart on **Fitness** (`hr_zone_1_sec` … `hr_zone_5_sec` summed per Show By period), with a **last-week** SVG donut in the shared right plot gutter under the Zone legend (latest completed Mon–Sun ISO week; per-zone hover/focus tooltips with %, and duration via `format_time`).
- Elevation-adjusted **aerobic efficiency** line chart on **Fitness** (non-race runs; residual of mph/bpm vs ft/mi, median by Show By period), with an ⓘ in the shared right plot gutter (formula, elevation residual, and median-by-period aggregation on hover/focus).
- `StravaClient.get_activity_zones` and per-HR-zone time-in-seconds columns on `data/strava_run_analysis.csv` (`hr_zone_1_sec` … `hr_zone_5_sec`).
- `gear_id` column on activity analysis CSVs (from Strava summary `gear_id`, or nested `gear.id` when present).

### Changed

- Renamed the **Training Insights** page to **Fitness** (`training_insights.py` → `fitness.py`).
- Fitness chart order is Average HR by Pace, then Aerobic Efficiency, then Heart Rate Zones (efficiency is a separate chart; the dual-axis overlay on HR-by-pace is removed).
- Fitness Average HR, Aerobic Efficiency, and Heart Rate Zones share identical plot margins (`l=80`, `r=168`) and x-domain so X axes align across the legend / info gutter.
- Fitness Aerobic Efficiency chart heading omits “(elevation-adjusted)”; the Y-axis title is **Aerobic Efficiency** (`standoff=32`), with elevation details only in the right-gutter ⓘ tooltip.
- Fitness Pace Range multiselect uses pale teal selected chips (Streamlit `primaryColor`, not default red), ~90% Controls width (wider than Show By’s 75%) so “Choose options” fits; chips wrap and grow height with no min-width floor, and single-selection height hugs the chip (collapsed filter input, no blank second row).
- Fitness Controls / Avg HR column keep SHOWING and LATEST ACTIVITY aligned without clipping (`overflow` no longer hidden on the meta column).
- Fitness pace-bin line colors are fixed across the full bin list (darker = faster).
- Fitness chart hovers (Average HR and Heart Rate Zones) show ISO week ranges as abbreviated dates when Show By is Week (e.g. `Jan 5, 2026 - Jan 11, 2026`).
- Per-HR-zone run columns store seconds (`hr_zone_1_sec` … `hr_zone_5_sec`) instead of percent of time.
- Shoe mileage is baseline + sum of activity `distance_miles` by `gear_id` instead of the Strava gear API distance.
- Easy/hard run metrics (`%_easy`, `mt_min_easy`, `mt_min_hard`) now come from Strava activity heartrate **zones** (zones 1–2 = easy, remaining buckets = moderate/hard) instead of a fixed HR stream threshold.
- Training charts use a sampled 5-swatch earthy palette (slate goal lines, teal mileage, gold race markers, peach Easy, terracotta Hard); elevation stays muted purple (`#8575A8`) since the strip has no purple.
- Moved Key Indicators off **Training** onto **Metrics**; Training focuses on 80:20 compliance, mileage, and elevation trends.
- Renamed the **Training Overview** page to **Training** (`training_overview.py` → `training.py`); renamed CSS `--sticky-race-strip-top` to `--race-strip-scroll-margin-top`.
- Metrics section nav no longer includes Inspect (the expander remains on the page). Left-nav **On this page** jumps sit as a separate block below the page list, with extra space and a thin grey hairline above the heading.
- Replaced per-chart race overlays with the shared **Races** strip plus chart-top diamond markers.
- Training charts (80:20, mileage heatmap, elevation heatmap) share plot alignment; the unfinished current period uses gray hatching and a “Week/Day/… in progress” hover note.

### Removed

- Mileage heatmap from **Fitness**; it remains on **Training** as an expander.
- `StravaClient.get_gear`, gear CSV sync (`update_gear_mileage_csv`), and `data/strava_gear.csv`.

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
