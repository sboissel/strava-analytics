"""Race results loading and PR logic for the Race Results page."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

try:
    from . import _bootstrap  # noqa: F401
except ImportError:
    import _bootstrap  # noqa: F401

from data import DATA_DIR, format_full_date, latest_activity_label, load_runs, normalize_utc
from strava_analytics.activity_utils import race_distance_label

RACE_TYPE_ORDER = ["5k", "5M", "10k", "Half", "Marathon", "Other"]
PRS_ONLY_FILTER = "PRs only"


def parse_duration_minutes(value: object) -> float | None:
    """Parse H:MM:SS, HH:MM:SS, or M:SS strings into total minutes."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    parts = text.split(":")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return None
    if len(nums) == 3:
        hours, minutes, seconds = nums
    elif len(nums) == 2:
        hours = 0
        minutes, seconds = nums
    else:
        return None
    return hours * 60.0 + minutes + seconds / 60.0


def format_pace_from_minutes(minutes: float | None, distance_miles: float | None) -> str:
    """Format min/mile pace from elapsed minutes and distance."""
    if (
        minutes is None
        or pd.isna(minutes)
        or distance_miles is None
        or pd.isna(distance_miles)
        or distance_miles <= 0
    ):
        return "—"
    pace_sec = int(round((minutes * 60.0) / float(distance_miles)))
    pace_min, pace_s = divmod(pace_sec, 60)
    return f"{pace_min}:{pace_s:02d}"


def _normalize_race_type(raw: object, distance_miles: float | None) -> str:
    """Map CSV race_distance to a display bucket, falling back to distance rules."""
    if raw is not None and not (isinstance(raw, float) and pd.isna(raw)):
        text = str(raw).strip()
        if text and text.lower() != "nan":
            return text
    if distance_miles is not None and not pd.isna(distance_miles):
        label = race_distance_label(float(distance_miles), True)
        if label:
            return label
    return "Other"


def mark_personal_records(df: pd.DataFrame) -> pd.DataFrame:
    """Flag fastest elapsed time per race type (excluding Other)."""
    if df.empty:
        out = df.copy()
        out["is_pr"] = False
        return out

    out = df.copy()
    out["is_pr"] = False
    eligible = out["race_type"] != "Other"
    if not eligible.any():
        return out

    min_by_type = (
        out.loc[eligible]
        .groupby("race_type")["elapsed_min"]
        .transform("min")
    )
    out.loc[eligible, "is_pr"] = out.loc[eligible, "elapsed_min"] == min_by_type
    return out


def _load_race_results_uncached(data_dir: Path) -> pd.DataFrame:
    runs = load_runs(data_dir)
    if runs.empty or "race" not in runs.columns:
        return pd.DataFrame()

    races = runs.loc[runs["race"].astype(str).str.lower() == "true"].copy()
    if races.empty:
        return races

    races["date"] = pd.to_datetime(races["date"], utc=True, errors="coerce")
    races = races.dropna(subset=["date"]).copy()
    races["race_type"] = [
        _normalize_race_type(row.get("race_distance"), row.get("distance_miles"))
        for _, row in races.iterrows()
    ]
    races["elapsed_min"] = races["elapsed_time_min"].map(parse_duration_minutes)
    races["elapsed_pace"] = [
        format_pace_from_minutes(elapsed, dist)
        for elapsed, dist in zip(races["elapsed_min"], races["distance_miles"], strict=False)
    ]
    races = mark_personal_records(races)
    return races.sort_values("date", ascending=False).reset_index(drop=True)


@st.cache_data(show_spinner=False)
def _load_race_results_cached(csv_mtime: float, data_dir_str: str) -> pd.DataFrame:
    return _load_race_results_uncached(Path(data_dir_str))


def load_race_results(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Load race activities with parsed times, types, and PR flags."""
    path = data_dir / "strava_run_analysis.csv"
    mtime = path.stat().st_mtime if path.exists() else 0.0
    return _load_race_results_cached(mtime, str(data_dir))


def race_type_options(races: pd.DataFrame) -> list[str]:
    """Return filter options with All first, then known types present in data."""
    options = ["All", PRS_ONLY_FILTER]
    if races.empty:
        return options + RACE_TYPE_ORDER
    present = set(races["race_type"].dropna().unique())
    for race_type in RACE_TYPE_ORDER:
        if race_type in present:
            options.append(race_type)
    for race_type in sorted(present - set(RACE_TYPE_ORDER)):
        options.append(race_type)
    return options


def filter_race_results(
    races: pd.DataFrame,
    *,
    race_type: str = "All",
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Apply race type and inclusive date-range filters."""
    if races.empty:
        return races

    out = races.copy()
    if race_type and race_type != "All":
        if race_type == PRS_ONLY_FILTER:
            out = out.loc[out["is_pr"]]
        else:
            out = out.loc[out["race_type"] == race_type]

    if start is not None:
        start_ts = normalize_utc(pd.Timestamp(start))
        out = out.loc[out["date"] >= start_ts]

    if end is not None:
        end_ts = normalize_utc(pd.Timestamp(end))
        out = out.loc[out["date"] <= end_ts + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)]

    return out.sort_values("date").reset_index(drop=True)


def race_date_bounds(races: pd.DataFrame) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Return min/max race dates for slider defaults."""
    if races.empty:
        today = pd.Timestamp.now(tz="UTC").normalize()
        return today, today
    start = races["date"].min()
    end = races["date"].max()
    return start.normalize(), end.normalize()


def race_summary_meta(races: pd.DataFrame) -> str:
    """Short meta line for controls panel."""
    if races.empty:
        return "No races"
    count = len(races)
    noun = "race" if count == 1 else "races"
    return f"{count} {noun} · latest {latest_activity_label(races)}"


def _race_table_date(series: pd.Series) -> pd.Series:
    """Naive UTC datetimes for sortable Date column display."""
    return series.dt.tz_convert("UTC").dt.tz_localize(None).dt.normalize()


def race_table_rows(races: pd.DataFrame) -> pd.DataFrame:
    """Display columns for the race results table (default sort: date ascending)."""
    columns = ["Name", "Date", "Race Type", "Miles", "Time", "Pace", "PR"]
    if races.empty:
        return pd.DataFrame(columns=columns)

    display = races.sort_values("date", ascending=True).copy()
    return pd.DataFrame(
        {
            "Name": display["name"],
            "Date": _race_table_date(display["date"]),
            "Race Type": display["race_type"],
            "Miles": display["distance_miles"],
            "Time": display["elapsed_time_min"].fillna("—"),
            "Pace": display["elapsed_pace"],
            "PR": display["is_pr"].map(lambda pr: "🏆" if pr else ""),
        }
    )
