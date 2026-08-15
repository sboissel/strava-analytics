"""Pace HR, HR-zone, and aerobic-efficiency data for Fitness, plus mileage heatmaps."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

try:
    from . import _bootstrap  # noqa: F401
except ImportError:
    import _bootstrap  # noqa: F401

from strava_analytics.activities import HR_ZONE_COUNT, hr_zone_sec_columns

from data import (
    DATA_DIR,
    PERIOD_CONFIG,
    PeriodGrain,
    format_full_date,
    format_full_month,
    format_week_range_short,
    normalize_utc,
    reference_end,
    current_period_key,
    filter_to_recent_periods,
    generate_period_index,
    load_runs,
    window_mask,
    with_period_columns,
)

HR_ZONE_PCT_COLUMNS = [f"zone_{idx}_pct" for idx in range(1, HR_ZONE_COUNT + 1)]

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
    """Return the human-readable heatmap date window for a grain.

    Parameters
    ----------
    grain : PeriodGrain
        Calendar aggregation grain.

    Returns
    -------
    str
        Description of the heatmap layout window, or an empty string when unknown.
    """
    return HEATMAP_SHOWING.get(grain, "")
WEEK_COLUMNS = ["Week 1", "Week 2", "Week 3", "Week 4", "Week 5"]
DAY_COLUMNS = [str(day) for day in range(1, 32)]


def _normalize_as_of(runs: pd.DataFrame, as_of: pd.Timestamp | None) -> pd.Timestamp:
    return normalize_utc(as_of or reference_end(runs))


def _filter_runs_in_window(
    runs: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp
) -> pd.DataFrame:
    if runs.empty:
        return runs
    return runs.loc[window_mask(runs, start, end)].copy()


def _month_tooltip_label(month_key: str) -> str:
    """Full month label from a YYYY-MM key (e.g. March 2026)."""
    return format_full_month(pd.Timestamp(f"{month_key}-01", tz="UTC"))


def _day_tooltip_label(month_key: str, day: int) -> str:
    """Full calendar date from month key and day-of-month (e.g. March 14, 2026)."""
    year_str, _month_str = month_key.split("-")
    month_name = format_full_month(pd.Timestamp(f"{month_key}-01", tz="UTC")).split()[0]
    return f"{month_name} {day}, {year_str}"


def _month_row_labels(
    start: pd.Timestamp,
    count: int,
    *,
    label_fmt: str = "%b, %y",
) -> tuple[list[str], list[str]]:
    """Return display labels and YYYY-MM keys for `count` months ending at `start`'s month."""
    month_starts = pd.date_range(
        start=start.replace(day=1),
        periods=count,
        freq="MS",
        tz=start.tz,
    )
    y_labels = [d.strftime(label_fmt) for d in month_starts]
    month_keys = [d.strftime("%Y-%m") for d in month_starts]
    return y_labels, month_keys


def _week_of_month(monday: pd.Timestamp) -> int:
    """Monday-based week slot within a calendar month (1-5)."""
    return min(((monday.day - 1) // 7) + 1, 5)


def _monday_for_week_slot(month_key: str, week_idx: int) -> pd.Timestamp | None:
    """Return the ISO-week Monday for a week-of-month slot in ``YYYY-MM``."""
    month_start = pd.Timestamp(f"{month_key}-01", tz="UTC")
    for day in range(1, month_start.days_in_month + 1):
        candidate = month_start.replace(day=day)
        if int(candidate.dayofweek) != 0:
            continue
        if _week_of_month(candidate) - 1 == week_idx:
            return candidate
    return None


def _week_tooltip_label(month_key: str, week_idx: int) -> str:
    """Mon–Sun date range for a week-of-month heatmap cell."""
    monday = _monday_for_week_slot(month_key, week_idx)
    if monday is None:
        return f"{_month_tooltip_label(month_key)} · {WEEK_COLUMNS[week_idx]}"
    sunday = monday + pd.Timedelta(days=6)
    return f"{format_full_date(monday)} - {format_full_date(sunday)}"


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


def load_pace_runs(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Load pace analysis rows merged with activity dates.

    Parameters
    ----------
    data_dir : pathlib.Path, optional
        Directory containing pace and run analysis CSVs. Defaults to the
        repository ``data`` folder.

    Returns
    -------
    pandas.DataFrame
        Pace-bin seconds and average heart-rate columns joined to run dates.

    Raises
    ------
    FileNotFoundError
        If required CSV files are missing from ``data_dir``.
    """
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
    """Aggregate distance-normalized average HR for a pace bin by period.

    Parameters
    ----------
    pace_runs : pandas.DataFrame
        Pace analysis rows merged with activity dates.
    grain : PeriodGrain
        Calendar aggregation grain.
    bin_key : str
        Internal pace-bin key such as ``"800_830"``.
    as_of : pandas.Timestamp, optional
        Reference end date for the period window. Defaults to the latest activity.

    Returns
    -------
    pandas.DataFrame
        One row per period with ``avg_hr`` and an ``in_progress`` flag.
    """
    seconds_col = f"seconds_{bin_key}"
    hr_col = f"avg_hr_{bin_key}"
    n = int(PERIOD_CONFIG[grain]["count"])
    end = normalize_utc(as_of) if as_of is not None else reference_end(pace_runs)

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


def _empty_hr_zone_periods(
    full_index: pd.DataFrame, current_key: str
) -> pd.DataFrame:
    """Return the period index with NaN zone shares and an in-progress flag."""
    out = full_index.copy()
    for column in HR_ZONE_PCT_COLUMNS:
        out[column] = np.nan
    out["in_progress"] = out["period_key"] == current_key
    return out[
        ["period_key", "period_label", "period_tooltip", *HR_ZONE_PCT_COLUMNS, "in_progress"]
    ]


def aggregate_hr_zones_by_period(
    runs: pd.DataFrame,
    grain: PeriodGrain,
    *,
    as_of: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Sum HR-zone seconds by period and convert each period to a 100% stack.

    Periods with no HR-zone data (all-null columns, or a summed total of 0)
    keep ``NaN`` shares so charts can skip them instead of drawing a fake 0%
    stack.

    Parameters
    ----------
    runs : pandas.DataFrame
        Run analysis rows with ``date`` and ``hr_zone_1_sec`` … ``hr_zone_5_sec``.
    grain : PeriodGrain
        Calendar aggregation grain.
    as_of : pandas.Timestamp, optional
        Reference end date for the period window. Defaults to the latest activity.

    Returns
    -------
    pandas.DataFrame
        One row per period with ``zone_1_pct`` … ``zone_5_pct`` (0–100) and an
        ``in_progress`` flag.
    """
    n = int(PERIOD_CONFIG[grain]["count"])
    end = normalize_utc(as_of) if as_of is not None else reference_end(runs)
    full_index = generate_period_index(grain, end, n)
    current_key = current_period_key(grain, end)
    sec_cols = hr_zone_sec_columns()

    if runs.empty or any(col not in runs.columns for col in sec_cols):
        return _empty_hr_zone_periods(full_index, current_key)

    work = with_period_columns(runs.copy(), grain)
    keep_keys = set(full_index["period_key"])
    work = work.loc[work["_period_key"].isin(keep_keys)]
    if work.empty:
        return _empty_hr_zone_periods(full_index, current_key)

    for col in sec_cols:
        work[col] = pd.to_numeric(work[col], errors="coerce")
    # All-null rows stay NaN (not 0) so they do not invent a zero-second run.
    work["_hr_zone_total"] = work[sec_cols].sum(axis=1, min_count=1)
    valid = work["_hr_zone_total"].notna() & (work["_hr_zone_total"] > 0)
    work = work.loc[valid]
    if work.empty:
        return _empty_hr_zone_periods(full_index, current_key)

    for col in sec_cols:
        work[col] = work[col].fillna(0.0)

    grouped = (
        work.groupby(["_period_key", "_period_label"], as_index=False)[sec_cols]
        .sum()
        .rename(columns={"_period_key": "period_key", "_period_label": "period_label"})
    )
    grouped["_hr_zone_total"] = grouped[sec_cols].sum(axis=1)
    positive = grouped["_hr_zone_total"] > 0
    for idx, sec_col in enumerate(sec_cols, start=1):
        pct_col = f"zone_{idx}_pct"
        grouped[pct_col] = np.where(
            positive,
            grouped[sec_col] / grouped["_hr_zone_total"] * 100.0,
            np.nan,
        )

    merged = full_index.merge(
        grouped[["period_key", *HR_ZONE_PCT_COLUMNS]],
        on="period_key",
        how="left",
    )
    merged["in_progress"] = merged["period_key"] == current_key
    return merged[
        ["period_key", "period_label", "period_tooltip", *HR_ZONE_PCT_COLUMNS, "in_progress"]
    ]


def last_completed_iso_week_monday(as_of: pd.Timestamp) -> pd.Timestamp:
    """Return the Monday of the latest full ISO week before ``as_of``'s week.

    The current ISO week (even on Sunday) is treated as in progress, so this
    always returns the previous Monday–Sunday week.

    Parameters
    ----------
    as_of : pandas.Timestamp
        Reference instant (typically latest activity or "today").

    Returns
    -------
    pandas.Timestamp
        UTC Monday of the last completed Mon–Sun ISO week.
    """
    end = normalize_utc(as_of)
    iso = end.isocalendar()
    current_monday = pd.Timestamp.fromisocalendar(
        int(iso.year), int(iso.week), 1
    ).tz_localize("UTC")
    return current_monday - pd.Timedelta(days=7)


def last_full_week_hr_zone_shares(
    runs: pd.DataFrame,
    *,
    as_of: pd.Timestamp | None = None,
) -> dict[str, object]:
    """Aggregate HR-zone shares for the last completed Mon–Sun ISO week.

    Parameters
    ----------
    runs : pandas.DataFrame
        Run analysis rows with ``date`` and ``hr_zone_1_sec`` … ``hr_zone_5_sec``.
    as_of : pandas.Timestamp, optional
        Reference end date. Defaults to the latest activity.

    Returns
    -------
    dict
        Always includes ``week_key`` and ``week_label`` (Mon–Sun range). When
        that week has positive zone seconds, also includes ``zone_1_pct`` …
        ``zone_5_pct`` and ``zone_1_sec`` … ``zone_5_sec``; otherwise those
        keys are omitted (pie shows empty).
    """
    end = normalize_utc(as_of) if as_of is not None else reference_end(runs)
    monday = last_completed_iso_week_monday(end)
    sunday_exclusive = monday + pd.Timedelta(days=7)
    iso = monday.isocalendar()
    week_key = f"{int(iso.year)}-{int(iso.week):02d}"
    week_label = format_week_range_short(monday)
    out: dict[str, object] = {
        "week_key": week_key,
        "week_label": week_label,
    }
    sec_cols = hr_zone_sec_columns()

    if runs.empty or any(col not in runs.columns for col in sec_cols):
        return out

    work = runs.loc[window_mask(runs, monday, sunday_exclusive)].copy()
    if work.empty:
        return out

    for col in sec_cols:
        work[col] = pd.to_numeric(work[col], errors="coerce")
    work["_hr_zone_total"] = work[sec_cols].sum(axis=1, min_count=1)
    valid = work["_hr_zone_total"].notna() & (work["_hr_zone_total"] > 0)
    work = work.loc[valid]
    if work.empty:
        return out

    for col in sec_cols:
        work[col] = work[col].fillna(0.0)
    totals = work[sec_cols].sum(axis=0)
    grand = float(totals.sum())
    if grand <= 0:
        return out

    for idx, sec_col in enumerate(sec_cols, start=1):
        sec = float(totals[sec_col])
        out[f"zone_{idx}_sec"] = sec
        out[f"zone_{idx}_pct"] = sec / grand * 100.0
    return out


# Minimum distance (miles) before climb density is defined. Near-zero distance
# would send ft/mi to inf; those rows are dropped from the efficiency set.
CLIMB_DENSITY_MIN_DISTANCE_MILES = 1e-6

AEROBIC_EFFICIENCY_COLUMNS = (
    "period_key",
    "period_label",
    "period_tooltip",
    "residual",
    "efficiency",
    "elev_ft_per_mile",
    "in_progress",
)


def raw_aerobic_efficiency(avg_pace_sec, avg_hr):
    """Speed per heart rate: ``(3600 / avg_pace_sec) / avg_hr``.

    Units are miles/hour per bpm. Invalid or non-positive pace or HR yield
    ``NaN``.

    Parameters
    ----------
    avg_pace_sec : array-like
        Average pace in seconds per mile.
    avg_hr : array-like
        Average heart rate in beats per minute.

    Returns
    -------
    numpy.ndarray
        Aerobic efficiency, same shape as the broadcast inputs.
    """
    pace = np.asarray(avg_pace_sec, dtype=float)
    hr = np.asarray(avg_hr, dtype=float)
    pace, hr = np.broadcast_arrays(pace, hr)
    out = np.full(pace.shape, np.nan, dtype=float)
    valid = np.isfinite(pace) & np.isfinite(hr) & (pace > 0) & (hr > 0)
    np.divide(3600.0, pace, out=out, where=valid)
    np.divide(out, hr, out=out, where=valid)
    return out


def climb_density_ft_per_mile(elevation_gain_ft, distance_miles):
    """Elevation gain per mile: ``elevation_gain_ft / distance_miles``.

    Non-finite elevation is treated as 0 ft (flat). Distances at or below
    ``CLIMB_DENSITY_MIN_DISTANCE_MILES`` yield ``NaN``.

    Parameters
    ----------
    elevation_gain_ft : array-like
        Elevation gain in feet.
    distance_miles : array-like
        Distance in miles.

    Returns
    -------
    numpy.ndarray
        Feet per mile, same shape as the broadcast inputs.
    """
    elev = np.asarray(elevation_gain_ft, dtype=float)
    dist = np.asarray(distance_miles, dtype=float)
    elev, dist = np.broadcast_arrays(elev, dist)
    elev = np.where(np.isfinite(elev), elev, 0.0)
    out = np.full(dist.shape, np.nan, dtype=float)
    valid = np.isfinite(dist) & (dist > CLIMB_DENSITY_MIN_DISTANCE_MILES)
    np.divide(elev, dist, out=out, where=valid)
    return out


def efficiency_elevation_residuals(efficiency, elev_ft_per_mile):
    """OLS residual of ``efficiency ~ elevation_ft_per_mile``.

    Fits a line with intercept across finite pairs. Residual = observed −
    predicted; higher means more efficient than expected for that climb.
    Fewer than two finite points, or a degenerate fit, yields all ``NaN``.
    When climb density has no variance, predicted efficiency is the mean.

    Parameters
    ----------
    efficiency : array-like
        Raw aerobic efficiency (mph per bpm).
    elev_ft_per_mile : array-like
        Climb density in feet per mile.

    Returns
    -------
    numpy.ndarray
        Residuals aligned with the inputs.
    """
    y = np.asarray(efficiency, dtype=float)
    x = np.asarray(elev_ft_per_mile, dtype=float)
    y, x = np.broadcast_arrays(y, x)
    out = np.full(y.shape, np.nan, dtype=float)
    valid = np.isfinite(y) & np.isfinite(x)
    if int(valid.sum()) < 2:
        return out
    xv = x[valid]
    yv = y[valid]
    if np.allclose(xv, xv[0]):
        predicted = np.full(yv.shape, float(yv.mean()))
    else:
        slope, intercept = np.polyfit(xv, yv, 1)
        predicted = intercept + slope * xv
    out[valid] = yv - predicted
    return out


def _is_race_run(series: pd.Series) -> pd.Series:
    """True where ``race`` is an explicit true-like flag."""
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    text = series.astype(str).str.strip().str.lower()
    return text.isin(("true", "1", "yes"))


def eligible_aerobic_efficiency_runs(runs: pd.DataFrame) -> pd.DataFrame:
    """Non-race runs with valid pace, HR, and distance for efficiency.

    Parameters
    ----------
    runs : pandas.DataFrame
        Run analysis rows.

    Returns
    -------
    pandas.DataFrame
        Eligible rows with ``efficiency`` and ``elev_ft_per_mile`` columns.
    """
    required = ("avg_hr", "avg_pace_sec", "distance_miles")
    if runs.empty or any(col not in runs.columns for col in required):
        return pd.DataFrame(columns=[*runs.columns, "efficiency", "elev_ft_per_mile"])

    work = runs.copy()
    if "race" in work.columns:
        work = work.loc[~_is_race_run(work["race"])]
    if work.empty:
        return work.assign(efficiency=np.nan, elev_ft_per_mile=np.nan)

    elev = (
        work["elevation_gain_ft"]
        if "elevation_gain_ft" in work.columns
        else 0.0
    )
    work["efficiency"] = raw_aerobic_efficiency(work["avg_pace_sec"], work["avg_hr"])
    work["elev_ft_per_mile"] = climb_density_ft_per_mile(elev, work["distance_miles"])
    keep = (
        np.isfinite(work["efficiency"].to_numpy())
        & np.isfinite(work["elev_ft_per_mile"].to_numpy())
    )
    return work.loc[keep].copy()


def _empty_aerobic_efficiency_periods(
    full_index: pd.DataFrame, current_key: str
) -> pd.DataFrame:
    """Return the period index with NaN efficiency residuals."""
    out = full_index.copy()
    out["residual"] = np.nan
    out["efficiency"] = np.nan
    out["elev_ft_per_mile"] = np.nan
    out["in_progress"] = out["period_key"] == current_key
    return out[list(AEROBIC_EFFICIENCY_COLUMNS)]


def aggregate_aerobic_efficiency_by_period(
    runs: pd.DataFrame,
    grain: PeriodGrain,
    *,
    as_of: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Median elevation-adjusted aerobic-efficiency residual by period.

    Eligible non-race runs in the Fitness window get raw efficiency
    ``(3600 / avg_pace_sec) / avg_hr`` (mph per bpm). A linear fit
    ``efficiency ~ elevation_ft_per_mile`` is estimated on that set;
    each run's residual is observed − predicted. Periods aggregate the
    **median** residual (and median raw efficiency / ft/mi for hover).
    Periods with no eligible runs stay ``NaN`` so charts can gap.

    Parameters
    ----------
    runs : pandas.DataFrame
        Run analysis rows with date, pace, HR, distance, elevation, and race.
    grain : PeriodGrain
        Calendar aggregation grain.
    as_of : pandas.Timestamp, optional
        Reference end date for the period window. Defaults to the latest activity.

    Returns
    -------
    pandas.DataFrame
        One row per period with ``residual``, ``efficiency``,
        ``elev_ft_per_mile``, and ``in_progress``.
    """
    n = int(PERIOD_CONFIG[grain]["count"])
    end = normalize_utc(as_of) if as_of is not None else reference_end(runs)
    full_index = generate_period_index(grain, end, n)
    current_key = current_period_key(grain, end)

    eligible = eligible_aerobic_efficiency_runs(runs)
    if eligible.empty or "date" not in eligible.columns:
        return _empty_aerobic_efficiency_periods(full_index, current_key)

    work = with_period_columns(eligible, grain)
    keep_keys = set(full_index["period_key"])
    work = work.loc[work["_period_key"].isin(keep_keys)]
    if work.empty:
        return _empty_aerobic_efficiency_periods(full_index, current_key)

    work = work.copy()
    work["residual"] = efficiency_elevation_residuals(
        work["efficiency"].to_numpy(),
        work["elev_ft_per_mile"].to_numpy(),
    )
    grouped = (
        work.groupby(["_period_key", "_period_label"], as_index=False)
        .agg(
            residual=("residual", "median"),
            efficiency=("efficiency", "median"),
            elev_ft_per_mile=("elev_ft_per_mile", "median"),
        )
        .rename(columns={"_period_key": "period_key", "_period_label": "period_label"})
    )

    merged = full_index.merge(
        grouped[["period_key", "residual", "efficiency", "elev_ft_per_mile"]],
        on="period_key",
        how="left",
    )
    merged["in_progress"] = merged["period_key"] == current_key
    return merged[list(AEROBIC_EFFICIENCY_COLUMNS)]


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
            tooltips[y_idx, m_idx] = format_full_month(
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
    x_labels, month_keys = _month_row_labels(
        month_start, HEATMAP_WEEK_MONTHS, label_fmt="%b '%y"
    )
    y_labels = WEEK_COLUMNS
    # NaN = no such week slot in that month (e.g. no Week 5). Existing
    # Mon–Sun weeks start at 0.0 so zero-mile weeks paint on the colorscale.
    matrix = np.full((len(WEEK_COLUMNS), len(month_keys)), np.nan)
    tooltips = np.full((len(WEEK_COLUMNS), len(month_keys)), "", dtype=object)
    for w_idx, _week_label in enumerate(WEEK_COLUMNS):
        for x_idx, month_key in enumerate(month_keys):
            if _monday_for_week_slot(month_key, w_idx) is None:
                continue
            matrix[w_idx, x_idx] = 0.0
            tooltips[w_idx, x_idx] = _week_tooltip_label(month_key, w_idx)

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
    """Build mileage heatmap matrix, labels, title, and tooltips.

    Parameters
    ----------
    runs : pandas.DataFrame
        Run dataframe with ``date`` and ``distance_miles`` columns.
    grain : PeriodGrain
        Calendar aggregation grain selecting the heatmap layout.
    as_of : pandas.Timestamp, optional
        Reference end date for the heatmap window. Defaults to the latest activity.

    Returns
    -------
    tuple[numpy.ndarray, list[str], list[str], str, numpy.ndarray]
        Mileage matrix, y-axis labels, x-axis labels, chart title, and tooltip
        text matrix.
    """
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
