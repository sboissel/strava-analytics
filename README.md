# strava-analytics

[![pipeline status](https://gitlab.com/sandrineboissel/strava-analytics/badges/main/pipeline.svg)](https://gitlab.com/sandrineboissel/strava-analytics/-/commits/main)
[![coverage report](https://gitlab.com/sandrineboissel/strava-analytics/badges/main/coverage.svg)](https://gitlab.com/sandrineboissel/strava-analytics/-/commits/main)
[![version](https://img.shields.io/gitlab/v/tag/sandrineboissel/strava-analytics?sort=semver&label=version)](https://gitlab.com/sandrineboissel/strava-analytics/-/tags)

This repository collects Strava activity exports, enriches them with pace and HR summaries, and writes CSV files for weekly analysis and run pace breakdowns.

Versioning follows [Semantic Versioning](https://semver.org/); see [CHANGELOG.md](CHANGELOG.md).

## What the pipeline does

The main script in [`src/strava_analytics/strava.py`](src/strava_analytics/strava.py) refreshes a Strava API token, downloads recent activities, processes each activity, and writes several CSV files into the [data](data) folder:

- [data/strava_run_analysis.csv](data/strava_run_analysis.csv): run-specific enrichment including pace, HR, and easy/hard time metrics
- [data/strava_ride_analysis.csv](data/strava_ride_analysis.csv): ride exports
- [data/strava_swim_analysis.csv](data/strava_swim_analysis.csv): swim exports
- [data/strava_hike_analysis.csv](data/strava_hike_analysis.csv): hike exports
- [data/strava_run_pace_analysis.csv](data/strava_run_pace_analysis.csv): per-run pace-bin summaries keyed by activity ID
- [data/activities_last_week.csv](data/activities_last_week.csv): a rolling 7-day summary of recent activity data

## Requirements

- Python 3.11+
- The following Python packages:
  - pandas
  - numpy
  - requests
  - tqdm

## Environment variables

The script expects these environment variables to be defined before it runs:

- `CLIENT_ID`
- `CLIENT_SECRET`
- `REFRESH_TOKEN`

## Running the pipeline

From the repository root:

```bash
PYTHONPATH=src python -m strava_analytics.strava
```

The script will refresh the access token, fetch activities, and rewrite the CSV outputs in the data directory.

## Weekly GitLab sync

A scheduled GitLab CI job runs the pipeline every Sunday night and commits updated files under [`data/`](data) back to `main`.

### 1. CI/CD variables

In GitLab → **Settings → CI/CD → Variables**, add (masked / protected as appropriate):

| Variable | Purpose |
| -------- | ------- |
| `CLIENT_ID` | Strava OAuth client ID |
| `CLIENT_SECRET` | Strava OAuth client secret |
| `REFRESH_TOKEN` | Strava refresh token |
| `CI_PUSH_TOKEN` | Project access token with `write_repository` (used to push data commits; job token is not enough for protected `main`) |

Create the push token under **Settings → Access tokens** (role: Maintainer, scope: `write_repository`).

### 2. Pipeline schedule

In GitLab → **Build → Pipeline schedules**:

1. Create a schedule targeting `main`.
2. Cron: `0 23 * * 0` (Sunday 23:00), timezone `Europe/Paris`.
3. Save, then use **Play** once to verify after the variables are set.

The `sync` job runs only for scheduled pipelines; the `test` job still runs on normal pushes.

## Runner's Dashboard

**Live app:** [https://strava-analytics-sboissel.streamlit.app/](https://strava-analytics-sboissel.streamlit.app/)

A Streamlit app under [`dashboard/`](dashboard) mirrors the Tableau training overview (with Insights and Race pages stubbed for next).

```bash
pip install -r requirements.txt -r requirements-dev.txt
streamlit run dashboard/streamlit_app.py
```

### Streamlit Community Cloud

Hosted at [strava-analytics-sboissel.streamlit.app](https://strava-analytics-sboissel.streamlit.app/) from GitHub via [share.streamlit.io](https://share.streamlit.io):

| Setting | Value |
| ------- | ----- |
| Repository | `sboissel/strava-analytics` |
| Branch | `main` |
| Main file | `dashboard/streamlit_app.py` |
| Python | 3.11 |
| Secrets | None required (reads committed CSVs in `data/`) |

Data updates when the GitLab weekly sync commits to `main` and the GitLab→GitHub mirror pushes. See [DEPLOY.md](DEPLOY.md).

## Running the tests

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

Tests live under `tests/src/` (pipeline modules) and `tests/dashboard/` (Streamlit dashboard modules), with filenames matching the modules they cover (`test_data.py` → `dashboard/data.py`, etc.).

With coverage:

```bash
pytest --cov=strava_analytics --cov-report=term-missing
```

## Notes

- The pipeline is designed to fail loudly for genuine Strava API/auth issues so that bad data is not silently written.
- The pace-bin logic groups runs into fixed pace ranges such as `700_730` and `830_900` based on seconds per mile.
