"""Pace HR and mileage heatmap data for Training Insights."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

try:
    from . import _bootstrap  # noqa: F401
except ImportError:
    import _bootstrap  # noqa: F401

from data import (
    DATA_DIR,
    PERIOD_CONFIG,
    PeriodGrain,
    _format_full_date,
    _format_full_month,
    _reference_end,
    current_period_key,
    filter_to_recent_periods,
    generate_period_index,
    load_runs,
)

MONTH_COLUMNS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
HEATMAP_MONTH_YEARS = 10
HEATMAP_WEEK_MONTHS = 24
HEATMAP_DAY_MONTHS = 12

HEATMAP_SHOWING: dict[PeriodGrain, str] = {
    "Year": "Last 10 years",
    "Month": "Last 10 years × months",
    "Week": "Last 2 years",
    "Day": "Last 1 year",
}


def heatmap_showing_label(grain: PeriodGrain) -> str:
    """Human-readable date window for the mileage heatmap layout."""
    return HEATMAP_SHOWING.get(grain, "")
WEEK_COLUMNS = ["W1", "W2", "W3", "W4", "W5"]
DAY_COLUMNS = [str(day) for day in range(1, 32)]


def _normalize_as_of(runs: pd.DataFrame, as_of: pd.Timestamp | None) -> pd.Timestamp:
    end = as_of or _reference_end(runs)
    if end.tzinfo is None:
        end = end.tz_localize("UTC")
    else:
        end = end.tz_convert("UTC")
    return end.normalize()


def _filter_runs_in_window(
    runs: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp
) -> pd.DataFrame:
    if runs.empty:
        return runs
    return runs.loc[(runs["date"] >= start) & (runs["date"] < end)].copy()


def _month_tooltip_label(month_key: str) -> str:
    """Full month label from a YYYY-MM key (e.g. March 2026)."""
    return _format_full_month(pd.Timestamp(f"{month_key}-01", tz="UTC"))


def _day_tooltip_label(month_key: str, day: int) -> str:
    """Full calendar date from month key and day-of-month (e.g. March 14, 2026)."""
    year_str, _month_str = month_key.split("-")
    month_name = _format_full_month(pd.Timestamp(f"{month_key}-01", tz="UTC")).split()[0]
    return f"{month_name} {day}, {year_str}"


def _month_row_labels(start: pd.Timestamp, count: int) -> tuple[list[str], list[str]]:
    """Return display labels and YYYY-MM keys for `count` months ending at `start`'s month."""
    month_starts = pd.date_range(
        start=start.replace(day=1),
        periods=count,
        freq="MS",
        tz=start.tz,
    )
    y_labels = [d.strftime("%b, %y") for d in month_starts]
    month_keys = [d.strftime("%Y-%m") for d in month_starts]
    return y_labels, month_keys


def _week_of_month(monday: pd.Timestamp) -> int:
    """Monday-based week slot within a calendar month (1-5)."""
    return min(((monday.day - 1) // 7) + 1, 5)


def _load_pace_runs_uncached(data_dir: Path) -> pd.DataFrame:
    """Merge pace-bin seconds/HR with run dates."""
    path = data_dir / "strava_run_pace_analysis.csv"
    pace = pd.read_csv(path)
    runs = load_runs(data_dir)[["activity_id", "date"]]
    merged = pace.merge(runs, on="activity_id", how="inner")
    merged["date"] = pd.to_datetime(merged["date"], utc=True, errors="coerce")
    merged = merged.dropna(subset=["date"]).sort_values("date")
    for col in merged.columns:
        if col.startswith(("seconds_", "avg_hr_")):
            merged[col] = pd.to_numeric(merged[col], errors="coerce")
    return merged


@st.cache_data(show_spinner=False)
def _load_pace_runs_cached(csv_mtime: float, runs_mtime: float, data_dir_str: str) -> pd.DataFrame:
    return _load_pace_runs_uncached(Path(data_dir_str))


def load_pace_analysis(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Alias for load_pace_runs (pace analysis rows with activity dates)."""
    return load_pace_runs(data_dir)


def load_pace_runs(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Load pace analysis rows merged with activity dates."""
    pace_path = data_dir / "strava_run_pace_analysis.csv"
    runs_path = data_dir / "strava_run_analysis.csv"
    pace_mtime = pace_path.stat().st_mtime if pace_path.exists() else 0.0
    runs_mtime = runs_path.stat().st_mtime if runs_path.exists() else 0.0
    return _load_pace_runs_cached(pace_mtime, runs_mtime, str(data_dir))


def aggregate_pace_hr_by_period(
    pace_runs: pd.DataFrame,
    grain: PeriodGrain,
    bin_key: str,
    *,
    as_of: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Distance-normalized average HR for a pace bin, aggregated by calendar period."""
    seconds_col = f"seconds_{bin_key}"
    hr_col = f"avg_hr_{bin_key}"
    n = int(PERIOD_CONFIG[grain]["count"])
    end = as_of
    if end is None:
        end = _reference_end(pace_runs)
    elif end.tzinfo is None:
        end = end.tz_localize("UTC")
    else:
        end = end.tz_convert("UTC")
    end = end.normalize()

    full_index = generate_period_index(grain, end, n)
    current_key = current_period_key(grain, end)

    if pace_runs.empty or seconds_col not in pace_runs.columns:
        out = full_index.copy()
        out["avg_hr"] = np.nan
        out["in_progress"] = out["period_key"] == current_key
        return out[["period_key", "period_label", "period_tooltip", "avg_hr", "in_progress"]]

    work = filter_to_recent_periods(pace_runs, grain)
    work[seconds_col] = pd.to_numeric(work[seconds_col], errors="coerce").fillna(0.0)
    work[hr_col] = pd.to_numeric(work[hr_col], errors="coerce")
    valid = (work[seconds_col] > 0) & work[hr_col].notna() & np.isfinite(work[hr_col])
    work["_hr_weight"] = 0.0
    work.loc[valid, "_hr_weight"] = work.loc[valid, hr_col] * work.loc[valid, seconds_col]

    grouped = (
        work.groupby(["_period_key", "_period_label"], as_index=False)
        .agg(hr_weight=("_hr_weight", "sum"), seconds=(seconds_col, "sum"))
        .rename(columns={"_period_key": "period_key", "_period_label": "period_label"})
    )
    grouped["avg_hr"] = np.where(
        grouped["seconds"] > 0,
        grouped["hr_weight"] / grouped["seconds"],
        np.nan,
    )

    merged = full_index.merge(
        grouped[["period_key", "avg_hr"]],
        on="period_key",
        how="left",
    )
    merged["in_progress"] = merged["period_key"] == current_key
    return merged[["period_key", "period_label", "period_tooltip", "avg_hr", "in_progress"]]


def _year_matrix(
    runs: pd.DataFrame, *, as_of: pd.Timestamp | None = None
) -> tuple[np.ndarray, list[str], list[str], np.ndarray]:
    """Horizontal heatmap: one total-miles row with years as columns."""
    end = _normalize_as_of(runs, as_of)
    n = int(PERIOD_CONFIG["Year"]["count"])
    full_index = generate_period_index("Year", end, n)
    x_labels = full_index["period_label"].tolist()
    year_keys = full_index["period_key"].tolist()
    y_labels = ["Miles"]
    matrix = np.full((1, len(x_labels)), np.nan)
    tooltips = np.full((1, len(x_labels)), "", dtype=object)
    for x_idx, year_key in enumerate(year_keys):
        tooltips[0, x_idx] = year_key

    period_runs = filter_to_recent_periods(runs, "Year")
    if period_runs.empty:
        return matrix, y_labels, x_labels, tooltips

    grouped = (
        period_runs.groupby("_period_key", as_index=False)["distance_miles"]
        .sum()
        .rename(columns={"_period_key": "period_key"})
    )
    key_to_miles = dict(zip(grouped["period_key"], grouped["distance_miles"], strict=False))
    for x_idx, year_key in enumerate(year_keys):
        if year_key in key_to_miles:
            matrix[0, x_idx] = float(key_to_miles[year_key])
    return matrix, y_labels, x_labels, tooltips


def _month_calendar_matrix(
    runs: pd.DataFrame, *, as_of: pd.Timestamp | None = None
) -> tuple[np.ndarray, list[str], list[str], np.ndarray]:
    """Year × month mileage grid for the last 10 calendar years."""
    end = _normalize_as_of(runs, as_of)
    full_index = generate_period_index("Year", end, HEATMAP_MONTH_YEARS)
    years = [int(k) for k in full_index["period_key"].tolist()]
    y_labels = [str(y) for y in years]
    matrix = np.full((len(years), len(MONTH_COLUMNS)), np.nan)
    tooltips = np.full((len(years), len(MONTH_COLUMNS)), "", dtype=object)
    for y_idx, year in enumerate(years):
        for m_idx in range(len(MONTH_COLUMNS)):
            tooltips[y_idx, m_idx] = _format_full_month(
                pd.Timestamp(year=year, month=m_idx + 1, day=1, tz="UTC")
            )

    if runs.empty:
        return matrix, y_labels, MONTH_COLUMNS, tooltips

    year_set = set(years)
    work = runs.loc[runs["date"].dt.year.isin(year_set)].copy()
    if work.empty:
        return matrix, y_labels, MONTH_COLUMNS, tooltips

    work["year"] = work["date"].dt.year
    work["month"] = work["date"].dt.month
    grouped = (
        work.groupby(["year", "month"], as_index=False)["distance_miles"]
        .sum()
        .rename(columns={"distance_miles": "miles"})
    )
    for _, row in grouped.iterrows():
        y_idx = years.index(int(row["year"]))
        m_idx = int(row["month"]) - 1
        matrix[y_idx, m_idx] = float(row["miles"])
    return matrix, y_labels, MONTH_COLUMNS, tooltips


def _week_month_matrix(
    runs: pd.DataFrame, *, as_of: pd.Timestamp | None = None
) -> tuple[np.ndarray, list[str], list[str], np.ndarray]:
    """Week-of-month × month grid for the last 24 months (2 years)."""
    end = _normalize_as_of(runs, as_of)
    month_end = end.replace(day=1) + pd.offsets.MonthBegin(1)
    month_start = end.replace(day=1) - pd.DateOffset(months=HEATMAP_WEEK_MONTHS - 1)
    x_labels, month_keys = _month_row_labels(month_start, HEATMAP_WEEK_MONTHS)
    y_labels = WEEK_COLUMNS
    matrix = np.full((len(WEEK_COLUMNS), len(month_keys)), np.nan)
    tooltips = np.full((len(WEEK_COLUMNS), len(month_keys)), "", dtype=object)
    for w_idx, week_label in enumerate(WEEK_COLUMNS):
        for x_idx, month_key in enumerate(month_keys):
            tooltips[w_idx, x_idx] = f"{_month_tooltip_label(month_key)} · {week_label}"

    window_runs = _filter_runs_in_window(runs, month_start, month_end)
    if window_runs.empty:
        return matrix, y_labels, x_labels, tooltips

    iso = window_runs["date"].dt.isocalendar()
    week_key = iso.year.astype(str) + "-" + iso.week.astype(str).str.zfill(2)
    monday = window_runs["date"] - pd.to_timedelta(iso.day - 1, unit="D")
    work = window_runs.assign(_week_key=week_key, _monday=monday)
    weekly = (
        work.groupby("_week_key", as_index=False)
        .agg(miles=("distance_miles", "sum"), monday=("_monday", "first"))
    )
    weekly["_month_key"] = weekly["monday"].dt.strftime("%Y-%m")
    weekly["_week_idx"] = weekly["monday"].map(lambda m: _week_of_month(m) - 1)

    for _, row in weekly.iterrows():
        month_key = row["_month_key"]
        if month_key not in month_keys:
            continue
        x_idx = month_keys.index(month_key)
        w_idx = int(row["_week_idx"])
        if 0 <= w_idx < len(WEEK_COLUMNS):
            matrix[w_idx, x_idx] = float(row["miles"])
    return matrix, y_labels, x_labels, tooltips


def _day_month_matrix(
    runs: pd.DataFrame, *, as_of: pd.Timestamp | None = None
) -> tuple[np.ndarray, list[str], list[str], np.ndarray]:
    """Month × day-of-month grid for the last 12 months."""
    end = _normalize_as_of(runs, as_of)
    month_end = end.replace(day=1) + pd.offsets.MonthBegin(1)
    month_start = end.replace(day=1) - pd.DateOffset(months=HEATMAP_DAY_MONTHS - 1)
    y_labels, month_keys = _month_row_labels(month_start, HEATMAP_DAY_MONTHS)
    matrix = np.full((len(month_keys), len(DAY_COLUMNS)), np.nan)
    tooltips = np.full((len(month_keys), len(DAY_COLUMNS)), "", dtype=object)
    for y_idx, month_key in enumerate(month_keys):
        for d_idx, day_str in enumerate(DAY_COLUMNS):
            tooltips[y_idx, d_idx] = _day_tooltip_label(month_key, int(day_str))

    window_runs = _filter_runs_in_window(runs, month_start, month_end)
    if window_runs.empty:
        return matrix, y_labels, DAY_COLUMNS, tooltips

    work = window_runs.copy()
    work["_month_key"] = work["date"].dt.strftime("%Y-%m")
    work["_day_idx"] = work["date"].dt.day - 1
    grouped = (
        work.groupby(["_month_key", "_day_idx"], as_index=False)["distance_miles"]
        .sum()
    )
    for _, row in grouped.iterrows():
        month_key = row["_month_key"]
        if month_key not in month_keys:
            continue
        y_idx = month_keys.index(month_key)
        d_idx = int(row["_day_idx"])
        if 0 <= d_idx < len(DAY_COLUMNS):
            matrix[y_idx, d_idx] = float(row["distance_miles"])
    return matrix, y_labels, DAY_COLUMNS, tooltips


def mileage_heatmap_matrix(
    runs: pd.DataFrame,
    grain: PeriodGrain,
    *,
    as_of: pd.Timestamp | None = None,
) -> tuple[np.ndarray, list[str], list[str], str, np.ndarray]:
    """Build heatmap matrix, axis labels, title, and tooltip labels for the selected grain."""
    titles = {
        "Day": "Daily Mileage by Month (Last 12 Months)",
        "Week": "Weekly Mileage by Month (Last 2 Years)",
        "Month": "Monthly Mileage by Year (Last 10 Years)",
        "Year": "Yearly Mileage Heatmap",
    }
    title = titles.get(grain, "Mileage Heatmap")

    if grain == "Year":
        matrix, y_labels, x_labels, tooltips = _year_matrix(runs, as_of=as_of)
    elif grain == "Month":
        matrix, y_labels, x_labels, tooltips = _month_calendar_matrix(runs, as_of=as_of)
    elif grain == "Week":
        matrix, y_labels, x_labels, tooltips = _week_month_matrix(runs, as_of=as_of)
    else:
        matrix, y_labels, x_labels, tooltips = _day_month_matrix(runs, as_of=as_of)
    return matrix, y_labels, x_labels, title, tooltips
