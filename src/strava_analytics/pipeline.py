"""Pipeline orchestration for refreshing Strava data and writing CSVs."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from strava_analytics.activities import process_activities
from strava_analytics.client import REPO_ROOT, StravaClient
from strava_analytics.csv_io import (
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

    if df.empty:
        print("No new activities to process.")
    else:
        update_activity_analysis_csvs(df, data_dir)
        write_last_activity_id(data_dir, df["activity_id"].max())

        pace_output = data_dir / "strava_run_pace_analysis.csv"
        update_run_pace_analysis_csv(pace_summaries, pace_output)
        print(f"Saved run pace summary: {pace_output}")

    weekly_output = data_dir / "activities_last_week.csv"
    save_activities_last_week(data_dir, weekly_output)
    print(f"Saved weekly summary: {weekly_output}")


if __name__ == "__main__":
    main()
