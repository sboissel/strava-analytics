import requests
import pandas as pd
import time
import numpy as np
import os
from pathlib import Path
from collections import defaultdict
from tqdm import tqdm
from datetime import date, timedelta

REPO_ROOT = Path(__file__).resolve().parents[1]
tqdm.pandas()

# ========================
# CONFIG
# ========================
CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
AUTH_TOKEN = os.environ["AUTH_TOKEN"]
REFRESH_TOKEN = os.environ["REFRESH_TOKEN"]

MILE_METERS = 1609.34
FEET_METERS  = 0.3048
HR_EASY_THRESHOLD = 142
last_id = open(REPO_ROOT / "data" / "highest_activity_id.txt", "r").read().strip()

# ========================
# AUTH: refresh token
# ========================
def refresh_access_token(refresh_token):
    """Refresh the Strava access token using the configured refresh token.

    Raises:
        RuntimeError: If Strava rejects the refresh request.
    """
    url = "https://www.strava.com/oauth/token"

    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }

    res = requests.post(url, data=payload, timeout=30)
    if res.status_code != 200:
        raise RuntimeError(f"Strava token refresh failed: {res.status_code} {res.text[:200]}")
    return res.json()


# ========================
# GET ACTIVITIES
# ========================
def get_strava_activities(access_token):
    """Fetch athlete activities from the Strava API.

    The function walks the paginated API until it reaches the latest known
    activity ID or the API stops returning results.
    """
    activities = []
    page = 1

    headers = {"Authorization": f"Bearer {access_token}"}

    while True:
        url = "https://www.strava.com/api/v3/athlete/activities"
        params = {"per_page": 100, "page": page}

        res = requests.get(url, headers=headers, params=params)
        res.raise_for_status()

        data = res.json()

        if not data:
            break

        activities.extend(data)
        print(f"Pulled page {page} ({len(activities)} activities)")
        
        if last_id in [str(act["id"]) for act in data]:
            break

        page += 1
        time.sleep(1)

    return activities


# ========================
# GET STREAMS (pace, HR, elevation)
# ========================
def get_streams(activity_id, streams, access_token):
    """Retrieve one or more Strava activity streams for a given activity.

    Args:
        activity_id: The Strava activity identifier.
        streams: One or more stream names such as "distance" or "heartrate".
        access_token: A valid Strava API access token.

    Returns:
        A JSON-like payload from the Strava streams endpoint.

    Raises:
        RuntimeError: If the API request fails.
    """
    url = f"https://www.strava.com/api/v3/activities/{activity_id}/streams"

    headers = {"Authorization": f"Bearer {access_token}"}

    params = {
        "keys": ",".join(streams),
        "key_by_type": "true"
    }

    res = requests.get(url, headers=headers, params=params)

    if res.status_code != 200:
        return {}

    return res.json()

# ========================
# RUNNING HR THRESHOLD STATS
# ========================
def compute_hr_easy_stats(hr_stream, time_stream, threshold=HR_EASY_THRESHOLD):
    """Summarize easy versus hard running time from HR and time streams.

    The helper estimates the share of elapsed time spent below the easy HR
    threshold and returns the equivalent minutes for easy and hard segments.
    """
    hr_array = np.array(hr_stream, dtype=float)
    time_array = np.array(time_stream, dtype=float)

    if len(hr_array) == 0 or len(time_array) == 0:
        return None, None, None

    if len(hr_array) != len(time_array):
        min_len = min(len(hr_array), len(time_array))
        hr_array = hr_array[:min_len]
        time_array = time_array[:min_len]

    valid_mask = np.isfinite(hr_array) & np.isfinite(time_array)
    if not np.any(valid_mask):
        return None, None, None

    durations = np.diff(np.r_[0, time_array[valid_mask]])
    hr_valid = hr_array[valid_mask]

    if len(durations) != len(hr_valid):
        min_len = min(len(durations), len(hr_valid))
        durations = durations[:min_len]
        hr_valid = hr_valid[:min_len]

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
# PROCESS ACTIVITIES
# ========================
def is_fake_activity_id(activity_id):
    if activity_id is None or pd.isna(activity_id):
        return False
    return str(activity_id).strip().upper().startswith("FAKE")


def pace_seconds_from_speed(speed_mps):
    if speed_mps == 0 or pd.isna(speed_mps):
        return None

    return int(MILE_METERS / speed_mps)


def pace_to_seconds(pace):
    if pace is None or pd.isna(pace):
        return None

    if isinstance(pace, (int, float)):
        return int(pace)

    if isinstance(pace, str):
        pace = pace.strip()
        if not pace:
            return None
        try:
            return int(float(pace))
        except ValueError:
            parts = pace.split(":")
            if len(parts) == 2:
                try:
                    minutes, seconds = parts
                    return int(minutes) * 60 + int(seconds)
                except ValueError:
                    return None

    return None


def speed_to_pace(speed_mps):
    pace_seconds = pace_seconds_from_speed(speed_mps)
    if pace_seconds is None:
        return None

    minutes, seconds = divmod(pace_seconds, 60)

    return f"{minutes:02d}:{seconds:02d}"


def format_duration(seconds):
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


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


def pace_bin_for_seconds(pace_seconds):
    """Map an elapsed pace in seconds per mile to the configured pace bin."""
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


def run_pace_columns():
    """Return the canonical column order for run pace analysis output."""
    columns = ["activity_id"]
    for label in PACE_BIN_LABELS:
        columns.append(f"seconds_{label}")
        columns.append(f"avg_hr_{label}")
    return columns


def compute_run_pace_summary_from_streams(activity_id, distance_meters, time_seconds, hr_values):
    """Aggregate per-pace-bin elapsed time and average HR for a run.

    The function converts distance/time deltas into pace bins and summarizes
    the total time spent in each bin alongside the average HR observed in that
    segment.
    """
    if activity_id is None:
        return None

    if distance_meters is None or time_seconds is None:
        return None

    distance_arr = np.asarray(distance_meters, dtype=float)
    time_arr = np.asarray(time_seconds, dtype=float)
    hr_arr = np.asarray(hr_values, dtype=float) if hr_values is not None else np.array([])

    if distance_arr.size == 0 or time_arr.size == 0 or hr_arr.size == 0:
        return None

    shared_len = min(len(distance_arr), len(time_arr), len(hr_arr))
    if shared_len < 2:
        return None

    elapsed_by_bin = {label: 0.0 for label in PACE_BIN_LABELS}
    hr_weighted_by_bin = {label: 0.0 for label in PACE_BIN_LABELS}
    hr_valid_seconds_by_bin = {label: 0.0 for label in PACE_BIN_LABELS}

    for idx in range(1, shared_len):
        prev_distance = distance_arr[idx - 1]
        curr_distance = distance_arr[idx]
        prev_time = time_arr[idx - 1]
        curr_time = time_arr[idx]
        hr_value = hr_arr[idx]

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

        pace_seconds = delta_time / (delta_distance / MILE_METERS)
        label = pace_bin_for_seconds(pace_seconds)
        elapsed_by_bin[label] += delta_time

        if np.isfinite(hr_value):
            hr_weighted_by_bin[label] += hr_value * delta_time
            hr_valid_seconds_by_bin[label] += delta_time

    if not any(elapsed_by_bin.values()):
        return None

    summary = {"activity_id": int(activity_id)}
    for label in PACE_BIN_LABELS:
        total_seconds = elapsed_by_bin[label]
        summary[f"seconds_{label}"] = int(round(total_seconds)) if total_seconds > 0 else 0
        if hr_valid_seconds_by_bin[label] > 0:
            summary[f"avg_hr_{label}"] = round(hr_weighted_by_bin[label] / hr_valid_seconds_by_bin[label], 1)
        else:
            summary[f"avg_hr_{label}"] = np.nan

    return summary


def update_run_pace_analysis_csv(activity_df, access_token, output_path):
    if activity_df is None or activity_df.empty:
        return

    run_df = activity_df[activity_df["type"] == "Run"].copy()
    if run_df.empty:
        return

    rows = []
    for activity_id in run_df["activity_id"].dropna().astype(int).tolist():
        streams = get_streams(activity_id, ["distance", "time", "heartrate"], access_token)
        if not streams:
            continue

        distance_values = streams.get("distance", {}).get("data", [])
        time_values = streams.get("time", {}).get("data", [])
        hr_values = streams.get("heartrate", {}).get("data", [])

        if not distance_values or not time_values or not hr_values:
            continue

        summary = compute_run_pace_summary_from_streams(activity_id, distance_values, time_values, hr_values)
        if summary is not None:
            rows.append(summary)

    if not rows:
        return

    new_df = pd.DataFrame(rows)
    columns = run_pace_columns()

    if output_path.exists():
        existing_df = pd.read_csv(output_path, dtype=str, keep_default_na=False)
        existing_df = _drop_header_like_rows(existing_df)
        existing_df = existing_df.reindex(columns=columns, fill_value=np.nan)
    else:
        existing_df = pd.DataFrame(columns=columns)

    combined = pd.concat([existing_df, new_df], ignore_index=True, sort=False)
    combined = combined.drop_duplicates(subset=["activity_id"], keep="last")
    combined = combined.reindex(columns=columns)
    combined.to_csv(output_path, index=False)


def process_activities(activities, access_token):
    rows = []
    for idx, act in enumerate(tqdm(activities)):
        activity_id = act["id"]
        if is_fake_activity_id(activity_id):
            continue
        if activity_id <= int(last_id): # skip already processed
            continue

        row = {
            "activity_id": activity_id,
            "name": act["name"],
            "type": act["type"],
            "date": act["start_date"],
            "distance_miles": round(act["distance"] / MILE_METERS, 2),
            "moving_time_min": format_duration(act["moving_time"]),
            "elapsed_time_min": format_duration(act["elapsed_time"]),
            "elevation_gain_ft": round(act["total_elevation_gain"]/FEET_METERS, 2),
            "avg_pace": speed_to_pace(act["average_speed"]),
            "avg_pace_sec": pace_seconds_from_speed(act["average_speed"]),
            "max_pace": speed_to_pace(act["max_speed"]),
            "max_pace_sec": pace_seconds_from_speed(act["max_speed"]),
            "race": None,
        }

        if act["type"] == "Run":
            row["race"] = True if act['workout_type']== 1 else False
            streams = get_streams(activity_id, ["heartrate","distance","altitude","time"], access_token)
            if "heartrate" in streams and "time" in streams:
                hr_stream = streams["heartrate"]["data"]
                time_stream = streams["time"]["data"]
                pct_easy, mt_min_easy, mt_min_hard = compute_hr_easy_stats(hr_stream, time_stream)
                if pct_easy is not None:
                    row["%_easy"] = pct_easy
                    row["mt_min_easy"] = mt_min_easy
                    row["mt_min_hard"] = mt_min_hard
                if hr_stream:
                    row["avg_hr"] = round(float(np.mean(hr_stream)), 1)
                    row["max_hr"] = int(np.max(hr_stream))

        if act["type"] in ["Ride", "Swim"]:
            streams = get_streams(activity_id, ["heartrate"], access_token)
            if "heartrate" in streams:
                row["race"] = None

        rows.append(row)

        time.sleep(1)  # avoid rate limit

    return pd.DataFrame(rows)


def _drop_header_like_rows(df):
    """Remove repeated header rows that sometimes appear in exported CSV files."""
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


def save_activities_last_week(activity_files, output_path):
    """Create a rolling 7-day summary of the latest activity exports.

    This is used to produce the weekly CSV consumed by the analytics workflow.
    """
    frames = []
    for filename in activity_files:
        df = pd.read_csv(filename, dtype=str, keep_default_na=False)
        df = _drop_header_like_rows(df)
        if "date" not in df.columns:
            continue
        if "activity_id" in df.columns:
            df = df[~df["activity_id"].map(lambda value: is_fake_activity_id(value))]
        frames.append(df)

    if not frames:
        combined = pd.DataFrame(columns=[
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
        ])
    else:
        combined = pd.concat(frames, ignore_index=True, sort=False)

    if "date" in combined.columns:
        combined["date"] = pd.to_datetime(combined["date"], errors="coerce", utc=True)
        combined = combined.dropna(subset=["date"]).copy()

    if "avg_pace_sec" not in combined.columns:
        combined["avg_pace_sec"] = np.nan
    if "max_pace_sec" not in combined.columns:
        combined["max_pace_sec"] = np.nan

    combined["avg_pace_sec"] = combined["avg_pace_sec"].fillna(combined["avg_pace"].apply(pace_to_seconds))
    combined["max_pace_sec"] = combined["max_pace_sec"].fillna(combined["max_pace"].apply(pace_to_seconds))

    if "date" in combined.columns:
        end_dt = pd.Timestamp.now(tz="UTC")
        start_dt = end_dt - pd.Timedelta(days=7)
        combined = combined[
            (combined["date"] >= start_dt) &
            (combined["date"] <= end_dt)
        ]
        combined = combined.sort_values("date", ascending=True).reset_index(drop=True)
        combined["date"] = combined["date"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    columns = [
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
    combined = combined.reindex(columns=columns)
    combined.to_csv(output_path, index=False, mode="w")
    return combined


# ========================
# RUN
# ========================
if __name__ == "__main__":

    # 1. Refresh token
    token_data = refresh_access_token(REFRESH_TOKEN)

    access_token = token_data["access_token"]

    print("Token refreshed")

    print(f"Getting activities...")
    # 2. Get activities
    activities = get_strava_activities(access_token)

    # 3. Process + enrich
    print(f"Processing {len(activities)} activities...")
    df = process_activities(activities, access_token)

    activity_file_paths = []
    for activity_type in ["Run", "Ride", "Swim", "Hike"]:
        filename = REPO_ROOT / "data" / f"strava_{activity_type.lower()}_analysis.csv"
        activity_file_paths.append(filename)

        if df.empty:
            continue

        activity_df = df[df["type"] == activity_type]
        activity_df = activity_df[~activity_df["activity_id"].map(lambda value: is_fake_activity_id(value))]
        existing_df = pd.read_csv(filename, dtype=str, keep_default_na=False)
        existing_df = _drop_header_like_rows(existing_df)
        if "activity_id" in existing_df.columns:
            existing_df = existing_df[~existing_df["activity_id"].map(lambda value: is_fake_activity_id(value))]
        activity_df = pd.concat([activity_df, existing_df], axis=0, sort=False).drop_duplicates(subset=["activity_id"])
        activity_df = activity_df.drop(columns=["zrfs", "vo2max"], errors="ignore")

        if "avg_pace_sec" not in activity_df.columns:
            activity_df["avg_pace_sec"] = np.nan
        if "max_pace_sec" not in activity_df.columns:
            activity_df["max_pace_sec"] = np.nan

        activity_df["avg_pace_sec"] = activity_df["avg_pace_sec"].fillna(activity_df["avg_pace"].apply(pace_to_seconds))
        activity_df["max_pace_sec"] = activity_df["max_pace_sec"].fillna(activity_df["max_pace"].apply(pace_to_seconds))

        if activity_type == "Run":
            output_columns = [
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
                "avg_hr",
                "max_hr",
                "%_easy",
                "mt_min_easy",
                "mt_min_hard",
                "race",
                "race_distance",
            ]
        else:
            output_columns = [
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

        activity_df = activity_df.reindex(columns=output_columns)
        activity_df.to_csv(filename, index=False)
        print(f"Saved: {filename}")

    if df.empty:
        print("No new activities to process.")
    else:
        with open(REPO_ROOT / "data" / "highest_activity_id.txt", "w") as f:
            f.write(df['activity_id'].max().astype(str))

    pace_output = REPO_ROOT / "data" / "strava_run_pace_analysis.csv"
    update_run_pace_analysis_csv(df, access_token, pace_output)
    print(f"Saved run pace summary: {pace_output}")

    weekly_output = REPO_ROOT / "data" / "activities_last_week.csv"
    weekly_df = save_activities_last_week(activity_file_paths, weekly_output)
    weekly_df.to_csv(weekly_output, index=False)
    print(f"Saved weekly summary: {weekly_output}")