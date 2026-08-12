"""Activity enrichment and CSV helpers for pace, heart-rate, and weekly summaries."""

import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd
from tqdm import tqdm

MILE_METERS = 1609.34
FEET_METERS = 0.3048
HR_EASY_THRESHOLD = 142

PACE_BIN_LABELS = [
    "under_700",
    "700_730",
    "730_800",
    "800_830",
    "830_900",
    "900_930",
    "930_1000",
    "1000_1030",
    "1030_1100",
    "1100_1130",
    "over_1130",
]


# ========================
# RUNNING HR THRESHOLD STATS
# ========================
def compute_hr_easy_stats(
    hr_stream: Sequence[float],
    time_stream: Sequence[float],
    threshold: float = HR_EASY_THRESHOLD,
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Summarize easy versus hard running time from HR and time streams.

    Parameters
    ----------
    hr_stream : sequence of float
        Heart-rate values for the activity.
    time_stream : sequence of float
        Time values aligned to the heart-rate stream.
    threshold : float, optional
        Heart rates strictly below this value are treated as easy; values at or
        above it are hard.

    Returns
    -------
    tuple
        A tuple of percentage easy time, easy minutes, and hard minutes.

    The helper estimates the share of elapsed time spent below the easy HR
    threshold and returns the equivalent minutes for easy and hard segments.
    """
    hr_array = np.array(hr_stream, dtype=float)
    time_array = np.array(time_stream, dtype=float)

    if len(hr_array) == 0 or len(time_array) == 0:
        return None, None, None

    if len(hr_array) != len(time_array):
        # Trim to the shared length so the arrays stay aligned.
        min_len = min(len(hr_array), len(time_array))
        hr_array = hr_array[:min_len]
        time_array = time_array[:min_len]

    # Keep only samples where both HR and time are finite (drop NaN/inf gaps).
    valid_mask = np.isfinite(hr_array) & np.isfinite(time_array)
    if not np.any(valid_mask):
        return None, None, None

    # Convert the time stream into elapsed durations between consecutive samples.
    durations = np.diff(np.r_[0, time_array[valid_mask]])
    hr_valid = hr_array[valid_mask]

    total_duration_s = np.sum(durations)
    if total_duration_s <= 0:
        return None, None, None

    easy_mask = hr_valid < threshold
    easy_duration_s = np.sum(durations[easy_mask])
    hard_duration_s = np.sum(durations[~easy_mask])

    pct_easy = round((easy_duration_s / total_duration_s) * 100, 1)
    mt_min_easy = round(easy_duration_s / 60, 1)
    mt_min_hard = round(hard_duration_s / 60, 1)

    return pct_easy, mt_min_easy, mt_min_hard


# ========================
# PACE / DURATION HELPERS
# ========================
def speed_to_pace_seconds(speed_mps: Optional[float]) -> Optional[int]:
    """Convert a speed in meters per second to seconds per mile.

    Parameters
    ----------
    speed_mps : float, optional
        Speed expressed in meters per second.

    Returns
    -------
    int or None
        The equivalent pace in seconds per mile, or None when the speed is invalid.
    """
    if speed_mps == 0 or pd.isna(speed_mps):
        return None

    return int(MILE_METERS / speed_mps)


def format_time(seconds: Optional[Union[int, float]], *, include_hours: bool = True) -> Optional[str]:
    """Format a duration in seconds as a time string.

    Parameters
    ----------
    seconds : int or float, optional
        A duration expressed in seconds.
    include_hours : bool, optional
        When True, format as HH:MM:SS. When False, format as MM:SS.

    Returns
    -------
    str or None
        The formatted time string, or None when ``seconds`` is missing/invalid.
    """
    if seconds is None or pd.isna(seconds):
        return None

    total_seconds = int(seconds)
    minutes, secs = divmod(total_seconds, 60)
    if include_hours:
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def pace_bin_for_seconds(pace_seconds: float) -> str:
    """Map an elapsed pace in seconds per mile to the configured pace bin.

    Parameters
    ----------
    pace_seconds : float
        The pace in seconds per mile.

    Returns
    -------
    str
        The pace bin label for the provided pace.
    """
    if pace_seconds < 420:
        return "under_700"
    if pace_seconds <= 449:
        return "700_730"
    if pace_seconds <= 479:
        return "730_800"
    if pace_seconds <= 509:
        return "800_830"
    if pace_seconds <= 539:
        return "830_900"
    if pace_seconds <= 569:
        return "900_930"
    if pace_seconds <= 599:
        return "930_1000"
    if pace_seconds <= 629:
        return "1000_1030"
    if pace_seconds <= 659:
        return "1030_1100"
    if pace_seconds <= 689:
        return "1100_1130"
    return "over_1130"


def run_pace_columns() -> List[str]:
    """Return the canonical column order for run pace analysis output.

    Returns
    -------
    list[str]
        A list of column names for the run pace summary output.
    """
    columns = ["activity_id"]
    for label in PACE_BIN_LABELS:
        columns.append(f"seconds_{label}")
        columns.append(f"avg_hr_{label}")
    return columns


def compute_run_pace_summary_from_streams(
    activity_id: int,
    distance_meters: Sequence[float],
    time_seconds: Sequence[float],
    hr_values: Sequence[float],
) -> Optional[Dict[str, Any]]:
    """Aggregate per-pace-bin elapsed time and average HR for a run.

    Parameters
    ----------
    activity_id : int
        The Strava activity identifier.
    distance_meters : sequence of float
        Distance values for the run stream.
    time_seconds : sequence of float
        Time values aligned to the distance stream.
    hr_values : sequence of float
        Heart-rate values aligned to the stream.

    Returns
    -------
    dict or None
        A summary dictionary keyed by pace bin, or None when insufficient data is available.

    The function converts distance/time deltas into pace bins and summarizes
    the total time spent in each bin alongside the average HR observed in that
    segment.
    """
    if not distance_meters or not time_seconds or not hr_values:
        return None

    distance_arr = np.asarray(distance_meters, dtype=float)
    time_arr = np.asarray(time_seconds, dtype=float)
    hr_arr = np.asarray(hr_values, dtype=float)

    shared_len = min(len(distance_arr), len(time_arr), len(hr_arr))
    if shared_len < 2:
        return None

    elapsed_by_bin = {label: 0.0 for label in PACE_BIN_LABELS}
    hr_weighted_by_bin = {label: 0.0 for label in PACE_BIN_LABELS}
    hr_valid_seconds_by_bin = {label: 0.0 for label in PACE_BIN_LABELS}

    for idx in range(1, shared_len):
        # Compare consecutive points to derive a segment pace and associated HR.
        prev_distance = distance_arr[idx - 1]
        curr_distance = distance_arr[idx]
        prev_time = time_arr[idx - 1]
        curr_time = time_arr[idx]
        hr_value = hr_arr[idx]

        # Skip segments with non-finite distance/time; allow missing HR (nan) for pace-only bins.
        if not np.isfinite(prev_distance) or not np.isfinite(curr_distance):
            continue
        if not np.isfinite(prev_time) or not np.isfinite(curr_time):
            continue
        if not np.isfinite(hr_value):
            hr_value = np.nan

        delta_distance = curr_distance - prev_distance
        delta_time = curr_time - prev_time
        if delta_distance <= 0 or delta_time <= 0:
            continue

        # Convert distance/time deltas into a pace expressed in seconds per mile.
        pace_seconds = delta_time / (delta_distance / MILE_METERS)
        label = pace_bin_for_seconds(pace_seconds)
        elapsed_by_bin[label] += delta_time

        if np.isfinite(hr_value):
            hr_weighted_by_bin[label] += hr_value * delta_time
            hr_valid_seconds_by_bin[label] += delta_time

    if not any(elapsed_by_bin.values()):
        # Nothing usable was accumulated, so skip the row.
        return None

    summary = {"activity_id": activity_id}
    for label in PACE_BIN_LABELS:
        total_seconds = elapsed_by_bin[label]
        summary[f"seconds_{label}"] = int(round(total_seconds)) if total_seconds > 0 else 0
        if hr_valid_seconds_by_bin[label] > 0:
            summary[f"avg_hr_{label}"] = round(hr_weighted_by_bin[label] / hr_valid_seconds_by_bin[label], 1)
        else:
            summary[f"avg_hr_{label}"] = np.nan

    return summary


def _activity_base_row(act: Dict[str, Any]) -> Dict[str, Any]:
    """Build the shared activity row fields from a raw Strava activity payload."""
    avg_pace_sec = speed_to_pace_seconds(act["average_speed"])
    max_pace_sec = speed_to_pace_seconds(act["max_speed"])
    return {
        "activity_id": act["id"],
        "name": act["name"],
        "type": act["type"],
        "date": act["start_date"],
        "distance_miles": round(act["distance"] / MILE_METERS, 2),
        "moving_time_min": format_time(act["moving_time"], include_hours=True),
        "elapsed_time_min": format_time(act["elapsed_time"], include_hours=True),
        "elevation_gain_ft": round(act["total_elevation_gain"] / FEET_METERS, 2),
        "avg_pace": format_time(avg_pace_sec, include_hours=False),
        "avg_pace_sec": avg_pace_sec,
        "max_pace": format_time(max_pace_sec, include_hours=False),
        "max_pace_sec": max_pace_sec,
        "race": None,
    }


def _enrich_run_from_streams(
    row: Dict[str, Any],
    activity_id: Any,
    get_streams: Callable[[Union[int, str], Sequence[str]], Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Enrich a run row with HR stats and return an optional pace summary."""
    streams = get_streams(activity_id, ["heartrate", "distance", "time"])
    hr_stream = streams.get("heartrate", {}).get("data", [])
    distance_stream = streams.get("distance", {}).get("data", [])
    time_stream = streams.get("time", {}).get("data", [])

    if hr_stream and time_stream:
        pct_easy, mt_min_easy, mt_min_hard = compute_hr_easy_stats(hr_stream, time_stream)
        if pct_easy is not None:
            row["%_easy"] = pct_easy
            row["mt_min_easy"] = mt_min_easy
            row["mt_min_hard"] = mt_min_hard
        row["avg_hr"] = round(float(np.mean(hr_stream)), 1)
        row["max_hr"] = int(np.max(hr_stream))

    if distance_stream and time_stream and hr_stream:
        return compute_run_pace_summary_from_streams(
            activity_id, distance_stream, time_stream, hr_stream
        )
    return None


def process_activities(
    activities: Sequence[Dict[str, Any]],
    get_streams: Callable[[Union[int, str], Sequence[str]], Dict[str, Any]],
    last_activity_id: str,
) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    """Process Strava activities into enriched rows and run pace summaries.

    Parameters
    ----------
    activities : sequence of dict
        Raw activity records returned from the Strava API.
    get_streams : callable
        Function used to fetch activity streams, typically ``StravaClient.get_streams``.
    last_activity_id : str
        Activities with an ID at or below this value are skipped.

    Returns
    -------
    tuple
        A dataframe of enriched activity rows and a list of run pace summaries.
        Streams are fetched once per run and reused for both outputs.
    """
    rows = []
    pace_summaries = []
    for act in tqdm(activities):
        activity_id = act["id"]
        if activity_id <= int(last_activity_id):  # skip already-processed activities
            continue

        row = _activity_base_row(act)

        if act["type"] == "Run":
            row["race"] = True if act["workout_type"] == 1 else False
            summary = _enrich_run_from_streams(row, activity_id, get_streams)
            if summary is not None:
                pace_summaries.append(summary)
            time.sleep(1)  # avoid rate limit after stream fetch

        rows.append(row)

    return pd.DataFrame(rows), pace_summaries


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

        existing_df = pd.read_csv(filename, dtype=str, keep_default_na=False)
        existing_df = _drop_header_like_rows(existing_df)
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


def week_summary_bounds(as_of: Optional[pd.Timestamp] = None) -> Tuple[pd.Timestamp, pd.Timestamp]:
    """Return the ``[start, end)`` window used for the weekly activity summary.

    Monday through Saturday uses the previous calendar week (Monday-Sunday).
    Sunday uses the current calendar week (Monday-Sunday).

    Parameters
    ----------
    as_of : pandas.Timestamp, optional
        Reference timestamp. Defaults to the current UTC time.

    Returns
    -------
    tuple
        Inclusive week start (Monday 00:00 UTC) and exclusive week end
        (following Monday 00:00 UTC).
    """
    as_of = as_of or pd.Timestamp.now(tz="UTC")
    if as_of.tzinfo is None:
        as_of = as_of.tz_localize("UTC")
    else:
        as_of = as_of.tz_convert("UTC")

    today = as_of.normalize()
    weekday = today.dayofweek  # Monday=0 ... Sunday=6

    if weekday == 6:  # Sunday: current week Mon-Sun
        week_start = today - pd.Timedelta(days=6)
        week_end = today + pd.Timedelta(days=1)
    else:  # Monday-Saturday: previous week Mon-Sun
        last_sunday = today - pd.Timedelta(days=weekday + 1)
        week_start = last_sunday - pd.Timedelta(days=6)
        week_end = last_sunday + pd.Timedelta(days=1)

    return week_start, week_end


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
