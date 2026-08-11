import requests
import pandas as pd
import time
import numpy as np
import os
from pathlib import Path
from tqdm import tqdm
from typing import Any, Dict, List, Sequence, Union

from strava_analytics.fitness_utils import (
    MILE_METERS,
    _drop_header_like_rows,
    compute_hr_easy_stats,
    compute_run_pace_summary_from_streams,
    format_duration,
    is_fake_activity_id,
    pace_seconds_from_speed,
    pace_to_seconds,
    run_pace_columns,
    save_activities_last_week,
    speed_to_pace,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
tqdm.pandas()

# ========================
# CONFIG
# ========================
CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
REFRESH_TOKEN = os.environ["REFRESH_TOKEN"]

FEET_METERS = 0.3048
last_id = open(REPO_ROOT / "data" / "highest_activity_id.txt", "r").read().strip()

# ========================
# AUTH: refresh token
# ========================
def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    """Refresh the Strava access token using the configured refresh token.

    Parameters
    ----------
    refresh_token : str
        The Strava refresh token to exchange for a new access token.

    Returns
    -------
    dict
        A dictionary containing the token payload returned by the Strava OAuth endpoint.

    Raises
    ------
    RuntimeError
        If Strava rejects the refresh request.
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
def get_strava_activities(access_token: str) -> List[Dict[str, Any]]:
    """Fetch athlete activities from the Strava API.

    Parameters
    ----------
    access_token : str
        A valid Strava API access token.

    Returns
    -------
    list[dict]
        A list of activity dictionaries returned by the Strava athlete activities endpoint.
    """
    activities = []
    page = 1

    headers = {"Authorization": f"Bearer {access_token}"}

    while True:
        # Fetch one page of activities at a time until we hit the last known activity.
        url = "https://www.strava.com/api/v3/athlete/activities"
        params = {"per_page": 100, "page": page}

        res = requests.get(url, headers=headers, params=params)
        res.raise_for_status()

        data = res.json()

        if not data:
            break

        activities.extend(data)
        print(f"Pulled page {page} ({len(activities)} activities)")

        # Stop early once the latest known activity appears in the current page.
        if last_id in [str(act["id"]) for act in data]:
            break

        page += 1
        time.sleep(1)

    return activities


# ========================
# GET STREAMS (pace, HR, elevation)
# ========================
def get_streams(activity_id: Union[int, str], streams: Sequence[str], access_token: str) -> Dict[str, Any]:
    """Retrieve one or more Strava activity streams for a given activity.

    Parameters
    ----------
    activity_id : int or str
        The Strava activity identifier.
    streams : sequence of str
        One or more stream names such as "distance" or "heartrate".
    access_token : str
        A valid Strava API access token.

    Returns
    -------
    dict
        A dictionary payload from the Strava streams endpoint.

    Raises
    ------
    RuntimeError
        If the API request fails.
    """
    url = f"https://www.strava.com/api/v3/activities/{activity_id}/streams"

    headers = {"Authorization": f"Bearer {access_token}"}

    params = {
        "keys": ",".join(streams),
        "key_by_type": "true"
    }

    res = requests.get(url, headers=headers, params=params)

    if res.status_code != 200:
        raise RuntimeError(f"Strava streams request failed: {res.status_code} {res.text[:200]}")

    return res.json()


# ========================
# PROCESS ACTIVITIES
# ========================
def update_run_pace_analysis_csv(activity_df: pd.DataFrame, access_token: str, output_path: Path) -> None:
    """Update the run pace analysis CSV with the latest activity summaries.

    Parameters
    ----------
    activity_df : pandas.DataFrame
        A dataframe containing processed activity rows.
    access_token : str
        A valid Strava API access token.
    output_path : pathlib.Path
        Destination CSV file for the pace summaries.

    Returns
    -------
    None
        This function does not return a value.
    """
    if activity_df.empty:
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

    # Merge the existing CSV rows with the newly computed summaries and keep the latest value per activity.
    combined = pd.concat([existing_df, new_df], ignore_index=True, sort=False)
    combined = combined.drop_duplicates(subset=["activity_id"], keep="last")
    combined = combined.reindex(columns=columns)
    combined.to_csv(output_path, index=False)


def process_activities(activities: Sequence[Dict[str, Any]], access_token: str) -> pd.DataFrame:
    """Process Strava activities into a dataframe of enriched activity rows.

    Parameters
    ----------
    activities : sequence of dict
        Raw activity records returned from the Strava API.
    access_token : str
        A valid Strava API access token.

    Returns
    -------
    pandas.DataFrame
        A dataframe containing the enriched activity data.
    """
    rows = []
    for idx, act in enumerate(tqdm(activities)):
        activity_id = act["id"]
        if is_fake_activity_id(activity_id):
            continue
        if activity_id == int(last_id): # skip the pagination boundary activity
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
