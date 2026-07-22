import requests
import pandas as pd
import time
import numpy as np
import os
from pathlib import Path
from collections import defaultdict
from tqdm import tqdm

REPO_ROOT = Path(__file__).resolve().parents[1]
tqdm.pandas()

# ========================
# CONFIG
# ========================
CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
AUTH_TOKEN = "52ee9669003a01f2987624ae78bcbde81200490f"
REFRESH_TOKEN = os.environ["REFRESH_TOKEN"]

TEMPO_HR = 140
HR_ZONES = {
    "zone_1": (0, 127),
    "zone_2": (128, 139),
    "zone_3": (140, 151),
    "zone_4": (152, 164),
    "zone_5": (165, 250)
}
ZONE_WEIGHTS = {
    "zone_1": 0.3,
    "zone_2": 0.6,
    "zone_3": 1.0,
    "zone_4": 1.5,
    "zone_5": 2.0
}

MILE_METERS = 1609.34
FEET_METERS  = 0.3048
last_id = open(REPO_ROOT / "data" / "highest_activity_id.txt", "r").read().strip()

# ========================
# AUTH: refresh token
# ========================
def refresh_access_token(refresh_token):
    url = "https://www.strava.com/oauth/token"

    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": "fab4916a59557227d50a6eb0633d2e856cc0ad3c"
    }

    res = requests.post(url, data=payload)
    res.raise_for_status()
    return res.json()


# ========================
# GET ACTIVITIES
# ========================
def get_strava_activities(access_token):
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
#  ZONAL RUNNING FITNESS SCORE (ZRFS)
# ========================

def compute_zrfs(streams):

    dist = np.array(streams["distance"]["data"])
    hr = np.array(streams["heartrate"]["data"])
    time_s = np.array(streams["time"]["data"])

    altitude = streams.get("altitude", {}).get("data", None)
    if altitude is not None:
        altitude = np.array(altitude)

    if len(dist) < 10 or len(hr) < 10:
        return None

    # -------------------------
    # 1. TOTALS
    # -------------------------
    total_dist = dist[-1]  # meters
    total_time = time_s[-1]  # seconds

    speed = total_dist / (total_time + 1e-6)  # m/s

    # -------------------------
    # 2. HR ZONE LOAD
    # -------------------------
    zone_time = {z: 0 for z in HR_ZONES.keys()}

    for h in hr:
        for z, (low, high) in HR_ZONES.items():
            if low <= h <= high:
                zone_time[z] += 1
                break

    hr_load = sum(zone_time[z] * ZONE_WEIGHTS[z] for z in zone_time)

    # normalize by time → intensity
    hr_intensity = hr_load / (len(hr) + 1e-6)

    # -------------------------
    # 3. EFFICIENCY (NEW CORE)
    # -------------------------
    efficiency = speed / (hr_intensity + 1e-6)

    # -------------------------
    # 4. HR DRIFT
    # -------------------------
    half = len(hr) // 2
    drift = np.mean(hr[half:]) - np.mean(hr[:half])
    drift_factor = drift / 50

    # -------------------------
    # 5. ALTITUDE
    # -------------------------
    if altitude is not None:
        alt_diff = np.diff(altitude)
        elev_gain = np.sum(np.clip(alt_diff, 0, None))
        grade = elev_gain / (total_dist + 1e-6)

        elev_factor = 1 + 0.03 * grade
    else:
        elev_factor = 1.0

    # -------------------------
    # 6. FINAL SCORE
    # -------------------------
    zrfs = efficiency * elev_factor * (1 - drift_factor)

    return zrfs

# ========================
# VO2MAX ESTIMATION
# ========================

HR_MAX = 178
K_GRADE = 5   # grade impact scaling

def compute_vo2max(streams):

    dist = np.array(streams["distance"]["data"])
    time_s = np.array(streams["time"]["data"])
    hr = np.array(streams["heartrate"]["data"])
    altitude = np.array(streams["altitude"]["data"])
    
    if len(dist) < 10:
        return None

    # -------------------------
    # 1. segment calculations
    # -------------------------
    d_dist = np.diff(dist)
    d_time = np.diff(time_s)
    d_hr = hr[:-1]

    speed = d_dist / (d_time + 1e-6)  # m/s

    # -------------------------
    # 2. grade adjustment
    # -------------------------
    if altitude is not None:
        d_alt = np.diff(altitude)

        grade = d_alt / (d_dist + 1e-6)

        # clip extreme grades (noise protection)
        grade = np.clip(grade, -0.3, 0.3)

        adj_speed = speed * (1 + K_GRADE * grade)

    else:
        adj_speed = speed

    # -------------------------
    # 3. convert to m/min
    # -------------------------
    speed_m_min = adj_speed * 60

    # -------------------------
    # 4. VO2 per segment
    # Daniels formula
    # -------------------------
    vo2 = -4.60 + 0.182258 * speed_m_min + 0.000104 * (speed_m_min ** 2)

    # -------------------------
    # 5. effort filter (important)
    # -------------------------
    effort = d_hr / HR_MAX

    valid = (effort > 0.65) & (effort < 0.9)

    if np.sum(valid) < 20:
        return None

    # -------------------------
    # 6. estimate VO2max
    # -------------------------
    vo2max_est = np.mean(vo2[valid] / effort[valid])

    return round(vo2max_est, 2)

# ========================
# RUNNING ZONES
# ========================
def classify_run(hr_stream):
    hr_stream = np.array(hr_stream)
    total = len(hr_stream)

    z1_2 = np.sum(hr_stream < 140)
    pct_easy = z1_2 / total

    avg_hr = np.mean(hr_stream)

    sustained_hard = np.sum(hr_stream >= 152)

    if pct_easy >= 0.75 and avg_hr < 145:
        return "easy"

    if pct_easy < 0.75 or sustained_hard > 600:
        return "hard"

    return "moderate"


# ========================
# PROCESS ACTIVITIES
# ========================
def speed_to_pace(speed_mps):
    if speed_mps == 0 or pd.isna(speed_mps):
        return None

    minutes, seconds = divmod(int(MILE_METERS / speed_mps), 60)

    return f"{minutes:02d}:{seconds:02d}"


def format_duration(seconds):
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def process_activities(activities, access_token):
    rows = []
    for idx, act in enumerate(tqdm(activities)):
        activity_id = act["id"]
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
            "max_pace": speed_to_pace(act["max_speed"]),
        }

        if act["type"] == "Run":
            row["race"] = True if act['workout_type']== 1 else False
            streams = get_streams(activity_id, ["heartrate","distance","altitude","time"], access_token)
            if "heartrate" in streams:
                row["run_type"] = classify_run(streams["heartrate"]["data"])
            
                if "distance" in streams and "altitude" in streams and "time" in streams:
                    row["zrfs"] = round(compute_zrfs(streams), 2)
                    row["vo2max"] = compute_vo2max(streams)

        if act["type"] in ["Ride", "Swim"]:
            streams = get_streams(activity_id, ["heartrate"], access_token)
            if "heartrate" in streams:
                row["run_type"] = classify_run(streams["heartrate"]["data"])

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
    
    # 4. Save
    if df.empty:
        print("No new activities to process.")
        exit()

    for activity_type in ["Run", "Ride", "Swim", "Hike"]:
        activity_df = df[df["type"] == activity_type]
        filename = REPO_ROOT / "data" / f"strava_{activity_type.lower()}_analysis.csv"
        activity_df = pd.concat([activity_df, pd.read_csv(filename)], axis=0).drop_duplicates(subset=["activity_id"])
        activity_df.to_csv(filename, index=False)
        print(f"Saved: {filename}")

    with open(REPO_ROOT / "data" / "highest_activity_id.txt", "w") as f:
        f.write(df['activity_id'].max().astype(str))