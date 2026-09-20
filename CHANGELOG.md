# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

**Pipeline / data**

- Sierra Nevada Half plan (`data/plans/sierra_half.csv`): **Course map name**, **Course map url**, optional **Alt course map name (snow risk)**, and optional **Alt course map url**.

**Dashboard**

- **Training**: plan table **Planned course** column (course map name; links to Strava/course URL when present). Hover shows alternate course name in a CSS `.kpi-tooltip` when set; alt URL becomes a hyperlink in the tip.

### Changed

**Pipeline / data**

- Minor update to the November halves plan (`data/plans/november_halves.csv`).
- Sierra Nevada Half plan: run target elevations use smoothed GPX elevation for the trail in place of the previously reported values.

## [1.9.0] — 2026-09-16

### Added

**Dashboard**

- **Training**: weekday filter on Training plans (All / Mon–Sun) to list same-day sessions across weeks for week-over-week comparison (hides week-total rows when a day is selected).

### Changed

**Dashboard**

- **Training**: **Mileage** and **Elevation** plan vs actual bars now follow every Show By grain (Day / Week / Month / Year). Week still uses plan week totals; Day / Month / Year sum dated plan session miles and elevation into each period.

## [1.8.2] — 2026-09-16

### Fixed

**Dashboard**

- Sidebar version prefers checkout ``pyproject.toml`` (walk from ``dashboard/ui.py`` / package ``__init__``) over stale importlib / egg-info metadata so Streamlit Cloud and local installs no longer stick on an old release (e.g. v1.6.0).

## [1.8.1] — 2026-09-16

### Fixed

**Dashboard**

- Bootstrap reloads a stale Streamlit Cloud ``ui`` module when entrypoint exports ``hero_html`` / ``sidebar_version_html`` are missing (v1.8.0 mixed redeploy ImportError). Sidebar version falls back to ``pyproject.toml`` when ``strava_analytics`` is not importable.

## [1.8.0] — 2026-09-15

### Added

**Dashboard**

- **Training**: added Shoe column from training plan CSVs, with hover text when cell text underlined: estimated future mileage shown by taking current shoe mileage and summing future plan mileage. Shoe cell text colored to inidicate wear by estimated mileage (orange = 350+ miles, red = 400+ miles).
- **Training**: added Session Notes from training plan CSVs as hover text over Session cells, indicated by cell text underline.
- **Metrics**: shoe gauges show a shaded prepare band (350–400 mi); ⓘ tooltip documents the cues.

### Changed

**Dashboard**

- **Training**: updated how plans show by default (**Show this week only**) that hides additional weeks vs on toggle to **Show full training plan** toggle.
- **Training**: race session rows apply race text color to rows of race weeks.

## [1.7.0] — 2026-09-14

### Added

**Dashboard**

- **Training**: added collapsed Training plans section, listing `data/plans/*.csv` with totals by week and by date
- **Training**: added **Zoom to plan** to Control panel (`None` default + each loaded plan name) to select date range based on training plan dates.

### Changed

**Dashboard**

- **Training**: weekly **Mileage** and **Elevation** charts show plan vs actual grouped bars when Show By is Week and the selected period overlaps **any** loaded training plan (under `data/plans/`); otherwise they stay actual-only. 

**Pipeline / data**

- Sync-generated activity CSVs and `highest_activity_id.txt` moved from `data/` to [`data/activities/`](data/activities). 
- Added hand-authored training plans to `data/plans/`.

### Fixed

**Dashboard**

- Activity loaders (`load_runs`, `load_hikes`, `load_gear`, `load_pace_runs`, `load_race_results`) resolve legacy ``data/`` to ``data/activities/`` (stale Streamlit Cloud defaults) and return an empty frame instead of raising ``FileNotFoundError`` when the CSV is missing. Bootstrap reloads stale ``data`` / ``race_data`` modules whose loader defaults still point at ``data/``.
- Bootstrap reloads a stale Streamlit Cloud ``ui`` module when page-required exports are missing (e.g. Training ``render_training_plans``) or when ``data`` / ``race_data`` were refreshed.

## [1.6.0] — 2026-09-13

### Added

**Dashboard**

- **Hiking**: new page with highlight badges (all-time miles/elevation with YTD tooltips, longest hike, greatest elevation, most miles in a consecutive-day trip), Show By period miles/elevation bars, map drill-down, and grade-adjusted pace (GAP).
- **Hiking GAP**: ⓘ title hover (definition, formula, marker/trend key, caveats); open markers for 0 ft elevation; dual OLS trends (all points vs elev > 0) without a Plotly legend; hover elevation in feet.

**Pipeline / data**

- Activity analysis CSVs (run / ride / swim / hike) include `start_lat` and `start_lng` from Strava list/summary `start_latlng` when GPS is present on newly processed activities.
- Existing per-type CSVs are reindexed to the current schema even when a sync has no new rows of that type.
- Manual GitLab CI job to backfill `start_lat` / `start_lng` on historical activity CSVs from Strava summaries.

### Changed

**Dashboard**

- **Hiking GAP**: pace uses **moving time** (not elapsed time).

## [1.5.4] — 2026-09-07

### Added

**Dashboard**

- **Training / Fitness**: **Start / End** period controls (date or year inputs by grain) so charts use a custom inclusive window instead of a fixed lookback only.
- **Metrics**: **Latest activity** date under the page summary (same meta line as Training / Fitness).

### Changed

**Dashboard**

- **Training / Fitness**: Year grain defaults to a rolling **last 10 years** (replacing the fixed “since 2016” window); other grains keep their prior default lengths.
- **Training / Fitness**: Showing meta reads **`{N} weeks selected`** (or days / months / years), not “Last N …” or a date-span label.
- **Fitness**: Controls card widens (up to ~40rem) with equal filter columns and a **centered** vertical divider.
- **Metrics**: Shoes ⓘ definition is **total miles run in these shoes** (no baseline / gear-ID wording).

### Fixed

**Dashboard**

- **Training**: 80:20 chart lists **HR coverage** in the legend; Moderate/Hard hover uses the hard segment share (not the stack top ≈ 100%).

## [1.5.3] — 2026-08-27

### Changed

**Dashboard**

- **Training / Fitness**: Year grain is a fixed window **since 2016** (not a rolling last-N years), so early years stay on the charts.
- **Training**: HR Zones donut uses **week-to-date** zone shares instead of the last completed week.
- **Training**: 80:20 chart adds a thin gray **HR coverage** bar and richer hovers (easy / hard / unaccounted miles, coverage %).
- **Training**: Mileage and 80:20 **goal lines** draw as full-width shapes in front of bars; race diamonds clear the goal with a white halo and a minimum y pad.
- **Metrics**: Shoes tooltip clarifies baseline + gear-tagged activity miles.

## [1.5.2] — 2026-08-26

### Fixed

**Dashboard**

- **Streamlit Cloud**: `AttributeError` on `_bootstrap.ensure_sys_path` from a stale/wrong `_bootstrap` in `sys.modules`; entrypoint and pages now load `_bootstrap.py` by absolute file path and replace the cached module.
- **Streamlit Cloud**: `ImportError` for `compare_race_type_options` (and related Performance exports) when a stale `race_data` object still pointed at the correct file path; bootstrap now reloads `race_data` from disk when required attrs are missing.

**Pipeline / data**

- GitLab daily sync: do not ignore CI-managed `data/` exports (only scratch under `data/`), and stage explicit CSV/`highest_activity_id.txt` paths instead of `git add data/` (which fails when `data` is gitignored).

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
