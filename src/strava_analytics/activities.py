"""Activity enrichment: pace, heart-rate, race labels, and week windows."""

import time
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd
from tqdm import tqdm

MILE_METERS = 1609.34
FEET_METERS = 0.3048
HR_ZONE_COUNT = 5

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
# RUNNING HR ZONE STATS
# ========================
def hr_zone_sec_columns(zone_count: int = HR_ZONE_COUNT) -> List[str]:
    """Return canonical per-HR-zone time-in-seconds column names."""
    return [f"hr_zone_{idx}_sec" for idx in range(1, zone_count + 1)]


def _empty_hr_zone_stats(zone_count: int = HR_ZONE_COUNT) -> Dict[str, Optional[float]]:
    """Return null easy/hard and per-zone time-in-seconds fields."""
    stats: Dict[str, Optional[float]] = {
        "%_easy": None,
        "mt_min_easy": None,
        "mt_min_hard": None,
    }
    for column in hr_zone_sec_columns(zone_count):
        stats[column] = None
    return stats


def compute_hr_zone_stats(
    zones: Sequence[Dict[str, Any]],
    zone_count: int = HR_ZONE_COUNT,
) -> Dict[str, Optional[float]]:
    """Summarize easy/hard time and per-zone seconds from Strava zones.

    Parameters
    ----------
    zones : sequence of dict
        Activity zone objects from ``GET /activities/{id}/zones``. Only the
        ``type == "heartrate"`` object is used; pace/power zones are ignored.
    zone_count : int, optional
        Number of ``hr_zone_N_sec`` columns to emit (padded with ``None`` when
        fewer buckets are present). Defaults to 5.

    Returns
    -------
    dict
        ``%_easy``, ``mt_min_easy``, ``mt_min_hard``, and ``hr_zone_1_sec`` …
        ``hr_zone_{zone_count}_sec``. Values are ``None`` when heartrate zones
        are missing or total bucket time is zero.

    Easy time is the sum of the first two heartrate distribution buckets;
    moderate/hard is the sum of the remaining buckets. Easy/hard percentages
    use the sum of all bucket ``time`` values (seconds) as the denominator.
    Per-zone columns store those bucket ``time`` values as-is.
    """
    empty = _empty_hr_zone_stats(zone_count)
    hr_section = next((section for section in zones if section.get("type") == "heartrate"), None)
    if hr_section is None:
        return empty

    buckets = hr_section.get("distribution_buckets") or []
    if not buckets:
        return empty

    times = [float(bucket.get("time") or 0.0) for bucket in buckets]
    total_duration_s = float(sum(times))
    if total_duration_s <= 0:
        return empty

    easy_duration_s = float(sum(times[:2]))
    hard_duration_s = float(sum(times[2:]))

    stats: Dict[str, Optional[float]] = {
        "%_easy": round((easy_duration_s / total_duration_s) * 100, 1),
        "mt_min_easy": round(easy_duration_s / 60, 1),
        "mt_min_hard": round(hard_duration_s / 60, 1),
    }
    for idx in range(zone_count):
        column = f"hr_zone_{idx + 1}_sec"
        if idx < len(times):
            stats[column] = times[idx]
        else:
            stats[column] = None
    return stats


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


def extract_gear_id(act: Mapping[str, Any]) -> str:
    """Return the Strava gear id from a summary or detail activity payload.

    Prefers the summary ``gear_id`` field (avoids N+1 detail fetches). Falls
    back to nested ``gear.id`` when present (detail responses).
    """
    gear_id = act.get("gear_id")
    if gear_id is not None and str(gear_id).strip():
        return str(gear_id).strip()

    gear = act.get("gear")
    if isinstance(gear, Mapping):
        nested = gear.get("id")
        if nested is not None and str(nested).strip():
            return str(nested).strip()
    return ""


def _activity_base_row(act: Dict[str, Any]) -> Dict[str, Any]:
    """Build the shared activity row fields from a raw Strava activity payload."""
    avg_pace_sec = speed_to_pace_seconds(act["average_speed"])
    max_pace_sec = speed_to_pace_seconds(act["max_speed"])
    return {
        "activity_id": act["id"],
        "name": act["name"],
        "type": act["type"],
        "gear_id": extract_gear_id(act),
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
    get_activity_zones: Callable[[Union[int, str]], Sequence[Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    """Enrich a run row with HR stats/zones and return an optional pace summary."""
    streams = get_streams(activity_id, ["heartrate", "distance", "time"])
    hr_stream = streams.get("heartrate", {}).get("data", [])
    distance_stream = streams.get("distance", {}).get("data", [])
    time_stream = streams.get("time", {}).get("data", [])

    if hr_stream:
        row["avg_hr"] = round(float(np.mean(hr_stream)), 1)
        row["max_hr"] = int(np.max(hr_stream))

    zone_stats = compute_hr_zone_stats(get_activity_zones(activity_id))
    for key, value in zone_stats.items():
        if value is not None:
            row[key] = value

    if distance_stream and time_stream and hr_stream:
        return compute_run_pace_summary_from_streams(
            activity_id, distance_stream, time_stream, hr_stream
        )
    return None


def process_activities(
    activities: Sequence[Dict[str, Any]],
    get_streams: Callable[[Union[int, str], Sequence[str]], Dict[str, Any]],
    last_activity_id: str,
    get_activity_zones: Callable[[Union[int, str]], Sequence[Dict[str, Any]]],
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
    get_activity_zones : callable
        Function used to fetch activity zones, typically
        ``StravaClient.get_activity_zones``.

    Returns
    -------
    tuple
        A dataframe of enriched activity rows and a list of run pace summaries.
        Streams and zones are fetched once per new run and reused for outputs.
    """
    rows = []
    pace_summaries = []
    for act in tqdm(activities):
        activity_id = act["id"]
        if activity_id <= int(last_activity_id):  # skip already-processed activities
            continue

        row = _activity_base_row(act)

        if act["type"] == "Run":
            is_race = act["workout_type"] == 1
            row["race"] = is_race
            row["race_distance"] = race_distance_label(row["distance_miles"], is_race)
            summary = _enrich_run_from_streams(
                row, activity_id, get_streams, get_activity_zones
            )
            if summary is not None:
                pace_summaries.append(summary)
            time.sleep(1)  # avoid rate limit after stream/zones fetches

        rows.append(row)

    return pd.DataFrame(rows), pace_summaries


def last_full_week_bounds(as_of: Optional[pd.Timestamp] = None) -> Tuple[pd.Timestamp, pd.Timestamp]:
    """Return ``[start, end)`` for the most recent completed Mon–Sun week.

    Unlike ``week_summary_bounds``, this always uses the previous full calendar
    week (Mon 00:00 UTC through the following Mon 00:00 UTC exclusive), even on
    Sundays when the current week is still in progress.
    """
    as_of = as_of or pd.Timestamp.now(tz="UTC")
    if as_of.tzinfo is None:
        as_of = as_of.tz_localize("UTC")
    else:
        as_of = as_of.tz_convert("UTC")

    today = as_of.normalize()
    weekday = int(today.dayofweek)
    last_sunday = today - pd.Timedelta(days=weekday + 1)
    week_start = last_sunday - pd.Timedelta(days=6)
    week_end = last_sunday + pd.Timedelta(days=1)
    return week_start, week_end


def race_distance_label(distance_miles: float, is_race: bool) -> Optional[str]:
    """Map race activity distance to a standard race-distance bucket."""
    if not is_race:
        return None
    if distance_miles >= 25.5:
        return "Marathon"
    if 12.0 <= distance_miles <= 14.5:
        return "Half"
    if 2.8 <= distance_miles <= 3.5:
        return "5k"
    return "Other"


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

