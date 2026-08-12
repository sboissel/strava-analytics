"""Race results loading and PR logic for the Race Results page."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

try:
    from . import _bootstrap  # noqa: F401
except ImportError:
    import _bootstrap  # noqa: F401

from data import DATA_DIR, format_full_date, latest_activity_label, load_runs, normalize_utc
from strava_analytics.activities import race_distance_label

RACE_TYPE_ORDER = ["5k", "5M", "10k", "Half", "Marathon", "Other"]
PRS_ONLY_FILTER = "PRs only"
# Bump when derived race columns change so Streamlit cache invalidates.
_RACE_LOADER_VERSION = 2


def parse_duration_minutes(value: object) -> float | None:
    """Parse duration strings into total minutes.

    Parameters
    ----------
    value : object
        Duration value, typically ``H:MM:SS``, ``HH:MM:SS``, or ``M:SS``.

    Returns
    -------
    float or None
        Total elapsed minutes, or ``None`` when the value is missing or invalid.
    """
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
    """Format min/mile pace from elapsed minutes and distance.

    Parameters
    ----------
    minutes : float or None
        Elapsed time in minutes.
    distance_miles : float or None
        Race distance in miles.

    Returns
    -------
    str
        Pace string such as ``"7:30"``, or ``"—"`` when inputs are invalid.
    """
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
    """Flag fastest elapsed time per race type.

    Parameters
    ----------
    df : pandas.DataFrame
        Race dataframe with ``race_type`` and ``elapsed_min`` columns.

    Returns
    -------
    pandas.DataFrame
        Copy of ``df`` with an ``is_pr`` boolean column. Rows with race type
        ``"Other"`` are never marked as PRs.
    """
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
    races = _add_pace_columns(races)
    races = mark_personal_records(races)
    return races.sort_values("date", ascending=False).reset_index(drop=True)


def _add_pace_columns(races: pd.DataFrame) -> pd.DataFrame:
    """Compute numeric and display pace columns from elapsed time and distance."""
    if races.empty:
        return races

    out = races.copy()
    if "elapsed_min" not in out.columns and "elapsed_time_min" in out.columns:
        out["elapsed_min"] = out["elapsed_time_min"].map(parse_duration_minutes)

    valid_pace = (
        out["elapsed_min"].notna()
        & out["distance_miles"].notna()
        & (out["distance_miles"] > 0)
    )
    out["pace_min"] = np.nan
    out.loc[valid_pace, "pace_min"] = (
        out.loc[valid_pace, "elapsed_min"] / out.loc[valid_pace, "distance_miles"]
    )
    out["elapsed_pace"] = [
        format_pace_from_minutes(elapsed, dist)
        for elapsed, dist in zip(out["elapsed_min"], out["distance_miles"], strict=False)
    ]
    return out


def ensure_race_pace_min(races: pd.DataFrame) -> pd.DataFrame:
    """Backfill ``pace_min`` when missing from cached race data.

    Parameters
    ----------
    races : pandas.DataFrame
        Race dataframe that may lack a ``pace_min`` column.

    Returns
    -------
    pandas.DataFrame
        Copy with ``pace_min`` and ``elapsed_pace`` populated when missing.
    """
    if races.empty or "pace_min" in races.columns:
        return races
    return _add_pace_columns(races)


@st.cache_data(show_spinner=False)
def _load_race_results_cached(
    csv_mtime: float, data_dir_str: str, loader_version: int
) -> pd.DataFrame:
    del loader_version
    return _load_race_results_uncached(Path(data_dir_str))


def load_race_results(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Load race activities with parsed times, types, and PR flags.

    Parameters
    ----------
    data_dir : pathlib.Path, optional
        Directory containing ``strava_run_analysis.csv``. Defaults to the
        repository ``data`` folder.

    Returns
    -------
    pandas.DataFrame
        Race rows sorted by date descending with parsed elapsed time, pace,
        normalized race type, and PR flags.
    """
    path = data_dir / "strava_run_analysis.csv"
    mtime = path.stat().st_mtime if path.exists() else 0.0
    return _load_race_results_cached(mtime, str(data_dir), _RACE_LOADER_VERSION)


def race_type_options(races: pd.DataFrame) -> list[str]:
    """Return race-type filter options for the controls panel.

    Parameters
    ----------
    races : pandas.DataFrame
        Race dataframe with a ``race_type`` column.

    Returns
    -------
    list[str]
        Options starting with ``"All"`` and ``"PRs only"``, followed by known
        race types present in the data.
    """
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
    """Apply race type and inclusive date-range filters.

    Parameters
    ----------
    races : pandas.DataFrame
        Race dataframe to filter.
    race_type : str, optional
        Race type filter, ``"All"``, ``"PRs only"``, or a specific type.
        Defaults to ``"All"``.
    start : pandas.Timestamp, optional
        Inclusive start of the date range.
    end : pandas.Timestamp, optional
        Inclusive end of the date range.

    Returns
    -------
    pandas.DataFrame
        Filtered races sorted by date ascending.
    """
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
    """Return min and max race dates for date-picker defaults.

    Parameters
    ----------
    races : pandas.DataFrame
        Race dataframe with a ``date`` column.

    Returns
    -------
    tuple[pandas.Timestamp, pandas.Timestamp]
        Normalized UTC start and end dates, or today's date twice when empty.
    """
    if races.empty:
        today = pd.Timestamp.now(tz="UTC").normalize()
        return today, today
    start = races["date"].min()
    end = races["date"].max()
    return start.normalize(), end.normalize()


def race_summary_meta(races: pd.DataFrame) -> str:
    """Return a short summary line for the controls panel.

    Parameters
    ----------
    races : pandas.DataFrame
        Race dataframe with a ``date`` column.

    Returns
    -------
    str
        Count and latest-activity summary, or ``"No races"`` when empty.
    """
    if races.empty:
        return "No races"
    count = len(races)
    noun = "race" if count == 1 else "races"
    return f"{count} {noun} · latest {latest_activity_label(races)}"


def _race_table_date(series: pd.Series) -> pd.Series:
    """Naive UTC datetimes for sortable Date column display."""
    return series.dt.tz_convert("UTC").dt.tz_localize(None).dt.normalize()


def race_table_rows(races: pd.DataFrame) -> pd.DataFrame:
    """Build display columns for the race results table.

    Parameters
    ----------
    races : pandas.DataFrame
        Filtered race dataframe.

    Returns
    -------
    pandas.DataFrame
        Table-ready columns sorted by date ascending.
    """
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
