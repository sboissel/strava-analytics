"""CSV persistence helpers for activity analysis and sync cursor state."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np
import pandas as pd

from strava_analytics.activities import hr_zone_sec_columns, run_pace_columns, week_summary_bounds

LAST_ACTIVITY_ID_FILENAME = "highest_activity_id.txt"


def last_activity_id_path(data_dir: Path) -> Path:
    """Return the path to the saved last-activity-id file."""
    return data_dir / LAST_ACTIVITY_ID_FILENAME


def read_last_activity_id(data_dir: Path) -> str:
    """Read the last known activity ID from disk."""
    path = last_activity_id_path(data_dir)
    if not path.exists():
        return "0"
    return path.read_text().strip()


def write_last_activity_id(data_dir: Path, activity_id: Union[int, str]) -> None:
    """Persist the last known activity ID to disk."""
    last_activity_id_path(data_dir).write_text(str(activity_id))


ACTIVITY_TYPES = ("Run", "Ride", "Swim", "Hike")

WEEKLY_SUMMARY_COLUMNS = [
    "type",
    "date",
    "distance_miles",
    "moving_time_min",
    "elapsed_time_min",
    "elevation_gain_ft",
    "avg_pace",
    "avg_pace_sec",
    "max_pace",
    "max_pace_sec",
    "avg_hr",
    "max_hr",
    "%_easy",
    "mt_min_easy",
    "mt_min_hard",
]


def activity_analysis_columns(activity_type: str) -> List[str]:
    """Return the output columns for a given activity-type analysis CSV.

    Parameters
    ----------
    activity_type : str
        The activity type, such as ``Run`` or ``Ride``.

    Returns
    -------
    list[str]
        Column names to write for that activity type.
    """
    base_columns = [
        "activity_id",
        "name",
        "type",
        "gear_id",
        "date",
        "distance_miles",
        "moving_time_min",
        "elapsed_time_min",
        "elevation_gain_ft",
        "avg_pace",
        "avg_pace_sec",
        "max_pace",
        "max_pace_sec",
    ]
    if activity_type == "Run":
        return base_columns + [
            "avg_hr",
            "max_hr",
            "%_easy",
            "mt_min_easy",
            "mt_min_hard",
            *hr_zone_sec_columns(),
            "race",
            "race_distance",
        ]
    return base_columns


def activity_analysis_paths(
    output_dir: Path,
    activity_types: Sequence[str] = ACTIVITY_TYPES,
) -> List[Path]:
    """Return the per-type analysis CSV paths under ``output_dir``."""
    return [output_dir / f"strava_{activity_type.lower()}_analysis.csv" for activity_type in activity_types]


def update_activity_analysis_csvs(
    activity_df: pd.DataFrame,
    output_dir: Path,
    activity_types: Sequence[str] = ACTIVITY_TYPES,
) -> None:
    """Merge processed activities into per-type analysis CSVs.

    Parameters
    ----------
    activity_df : pandas.DataFrame
        Newly processed activity rows.
    output_dir : pathlib.Path
        Directory containing ``strava_<type>_analysis.csv`` files.
    activity_types : sequence of str, optional
        Activity types to update. Defaults to run, ride, swim, and hike.

    Returns
    -------
    None
        This function does not return a value.
    """
    if activity_df.empty:
        return

    for activity_type, filename in zip(
        activity_types, activity_analysis_paths(output_dir, activity_types)
    ):
        typed_df = activity_df[activity_df["type"] == activity_type]
        if typed_df.empty:
            continue

        if filename.exists():
            existing_df = pd.read_csv(filename, dtype=str, keep_default_na=False)
            existing_df = _drop_header_like_rows(existing_df)
        else:
            existing_df = pd.DataFrame(columns=activity_analysis_columns(activity_type))
        typed_df = pd.concat([typed_df, existing_df], axis=0, sort=False)
        typed_df["activity_id"] = typed_df["activity_id"].astype(str)
        typed_df = typed_df.drop_duplicates(subset=["activity_id"])
        typed_df = typed_df.drop(columns=["zrfs", "vo2max"], errors="ignore")
        typed_df = typed_df.reindex(columns=activity_analysis_columns(activity_type))
        typed_df.to_csv(filename, index=False)
        print(f"Saved: {filename}")


def update_run_pace_analysis_csv(pace_summaries: Sequence[Dict[str, Any]], output_path: Path) -> None:
    """Update the run pace analysis CSV with precomputed pace summaries.

    Parameters
    ----------
    pace_summaries : sequence of dict
        Pace-bin summary rows produced while processing run activities.
    output_path : pathlib.Path
        Destination CSV file for the pace summaries.

    Returns
    -------
    None
        This function does not return a value.
    """
    if not pace_summaries:
        return

    new_df = pd.DataFrame(pace_summaries)
    columns = run_pace_columns()

    if output_path.exists():
        existing_df = pd.read_csv(output_path, dtype=str, keep_default_na=False)
        existing_df = _drop_header_like_rows(existing_df)
        existing_df = existing_df.reindex(columns=columns, fill_value=np.nan)
    else:
        existing_df = pd.DataFrame(columns=columns)

    # Merge the existing CSV rows with the newly computed summaries and keep the latest value per activity.
    combined = pd.concat([existing_df, new_df], ignore_index=True, sort=False)
    combined = combined.drop_duplicates(subset=["activity_id"], keep="last")
    combined = combined.reindex(columns=columns)
    combined.to_csv(output_path, index=False)


def _drop_header_like_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Remove repeated header rows that sometimes appear in exported CSV files.

    Parameters
    ----------
    df : pandas.DataFrame
        A dataframe read from a CSV export.

    Returns
    -------
    pandas.DataFrame
        A cleaned dataframe with header-like rows removed.
    """
    if df.empty:
        return df

    df = df.loc[:, ~df.columns.str.contains(r"^Unnamed", na=False)]
    if df.empty:
        return df

    expected = [str(col) for col in df.columns]

    def is_header_like_row(row):
        values = ["" if pd.isna(value) else str(value).strip() for value in row.tolist()]
        return values == expected

    df = df.loc[~df.apply(is_header_like_row, axis=1)].copy()

    if "date" in df.columns:
        df["date"] = df["date"].astype(str).str.strip()
        df = df.loc[df["date"].str.lower() != "date"].copy()

    return df


def save_activities_last_week(
    data_dir: Path,
    output_path: Path,
    as_of: Optional[pd.Timestamp] = None,
) -> pd.DataFrame:
    """Create a weekly summary of activity exports for the configured week window.

    Monday through Saturday returns the previous Mon-Sun week. Sunday returns
    the current Mon-Sun week.

    Parameters
    ----------
    data_dir : pathlib.Path
        Directory containing the per-type ``strava_<type>_analysis.csv`` files.
    output_path : pathlib.Path
        Destination CSV file for the weekly summary.
    as_of : pandas.Timestamp, optional
        Reference timestamp for choosing the week window. Defaults to now (UTC).

    Returns
    -------
    pandas.DataFrame
        A dataframe containing the weekly activity summary.

    This is used to produce the weekly CSV consumed by the analytics workflow.
    """
    frames = []
    for filename in activity_analysis_paths(data_dir):
        if not filename.exists():
            continue
        df = pd.read_csv(filename, dtype=str, keep_default_na=False)
        df = _drop_header_like_rows(df)
        if "date" not in df.columns:
            continue
        frames.append(df)

    if not frames:
        # Create an empty weekly summary schema when no input files are available.
        combined = pd.DataFrame(columns=WEEKLY_SUMMARY_COLUMNS)
    else:
        combined = pd.concat(frames, ignore_index=True, sort=False)

    if "date" in combined.columns:
        combined["date"] = pd.to_datetime(combined["date"], errors="coerce", utc=True)
        combined = combined.dropna(subset=["date"]).copy()
        start_dt, end_dt = week_summary_bounds(as_of)
        combined = combined[
            (combined["date"] >= start_dt) &
            (combined["date"] < end_dt)
        ]
        combined = combined.sort_values("date", ascending=True).reset_index(drop=True)
        combined["date"] = combined["date"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    combined = combined.reindex(columns=WEEKLY_SUMMARY_COLUMNS)
    combined.to_csv(output_path, index=False, mode="w")
    return combined
