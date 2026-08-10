# strava-analytics

This repository collects Strava activity exports, enriches them with pace and HR summaries, and writes CSV files for weekly analysis and run pace breakdowns.

## What the pipeline does

The main script in [python/strava.py](python/strava.py) refreshes a Strava API token, downloads recent activities, processes each activity, and writes several CSV files into the [data](data) folder:

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
python python/strava.py
```

The script will refresh the access token, fetch activities, and rewrite the CSV outputs in the data directory.

## Running the tests

```bash
pytest
```

## Notes

- Fake or placeholder activity IDs are skipped automatically.
- The pipeline is designed to fail loudly for genuine Strava API/auth issues so that bad data is not silently written.
- The pace-bin logic groups runs into fixed pace ranges such as `700_730` and `830_900` based on seconds per mile.
