"""Pipeline orchestration for refreshing Strava data and writing CSVs."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

# Allow `python src/strava_analytics/pipeline.py` without installing the package.
# Prefer: PYTHONPATH=src python -m strava_analytics.pipeline
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from strava_analytics.activities import process_activities
from strava_analytics.client import REPO_ROOT, StravaClient
from strava_analytics.csv_io import (
    backfill_location_from_summaries,
    save_activities_last_week,
    update_activity_analysis_csvs,
    update_run_pace_analysis_csv,
    write_last_activity_id,
)


def main(data_dir: Optional[Path] = None) -> None:
    """Run the Strava analytics pipeline.

    Parameters
    ----------
    data_dir : pathlib.Path, optional
        Directory for activity CSVs and the last-activity-id file. Defaults to
        ``data`` under the repository root.
    """
    data_dir = data_dir or (REPO_ROOT / "data")

    client = StravaClient.from_env(data_dir=data_dir)
    client.refresh_access_token()
    print("Token refreshed")

    print("Getting activities...")
    activities = client.get_activities()

    print(f"Processing {len(activities)} activities...")
    df, pace_summaries = process_activities(
        activities,
        client.get_streams,
        client.last_activity_id,
        client.get_activity_zones,
    )

    # Always refresh analysis CSV schemas (e.g. new location columns) even when
    # there are no new rows, so older type files are not left on a stale header.
    update_activity_analysis_csvs(df, data_dir)

    # List pages include activities at/below the watermark. Patch empty GPS on
    # those already-synced rows (common after adding start_lat/start_lng) without
    # re-fetching streams or lowering highest_activity_id.
    filled = backfill_location_from_summaries(activities, data_dir)
    if filled:
        print(f"Backfilled start_lat/start_lng on {filled} existing row(s).")

    if df.empty:
        print("No new activities to process.")
    else:
        write_last_activity_id(data_dir, df["activity_id"].max())

        pace_output = data_dir / "strava_run_pace_analysis.csv"
        update_run_pace_analysis_csv(pace_summaries, pace_output)
        print(f"Saved run pace summary: {pace_output}")

    weekly_output = data_dir / "activities_last_week.csv"
    save_activities_last_week(data_dir, weekly_output)
    print(f"Saved weekly summary: {weekly_output}")


if __name__ == "__main__":
    main()
