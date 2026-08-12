"""Data loading and period aggregation for the Runner's Dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd
import streamlit as st

try:
    from . import _bootstrap  # noqa: F401
except ImportError:
    import _bootstrap  # noqa: F401

from strava_analytics.activity_utils import last_full_week_bounds

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"

PeriodGrain = Literal["Day", "Week", "Month", "Year"]

PERIOD_CONFIG: dict[PeriodGrain, dict[str, int | str]] = {
    "Day": {"count": 30, "showing": "Last 30 days"},
    "Week": {"count": 20, "showing": "Last 20 weeks"},
    "Month": {"count": 20, "showing": "Last 20 months"},
    "Year": {"count": 10, "showing": "Last 10 years"},
}


def _load_runs_uncached(data_dir: Path) -> pd.DataFrame:
    """Load run analysis rows with parsed dates and numeric fields."""
    path = data_dir / "strava_run_analysis.csv"
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    df = df.dropna(subset=["date"]).copy()
    for col in ("distance_miles", "%_easy", "mt_min_easy", "mt_min_hard"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.sort_values("date")


@st.cache_data(show_spinner=False)
def _load_runs_cached(csv_mtime: float, data_dir_str: str) -> pd.DataFrame:
    return _load_runs_uncached(Path(data_dir_str))


def load_runs(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Load run analysis rows with parsed dates and numeric fields.

    Parameters
    ----------
    data_dir : pathlib.Path, optional
        Directory containing ``strava_run_analysis.csv``. Defaults to the
        repository ``data`` folder.

    Returns
    -------
    pandas.DataFrame
        Run rows sorted by activity date with parsed timestamps and numeric
        columns for distance and heart-rate metrics.

    Raises
    ------
    FileNotFoundError
        If the run analysis CSV is missing from ``data_dir``.
    """
    path = data_dir / "strava_run_analysis.csv"
    mtime = path.stat().st_mtime if path.exists() else 0.0
    return _load_runs_cached(mtime, str(data_dir))


def latest_activity_label(df: pd.DataFrame) -> str:
    """Return the latest activity date as M/D/YYYY.

    Parameters
    ----------
    df : pandas.DataFrame
        Run dataframe with a ``date`` column.

    Returns
    -------
    str
        Formatted latest date, or ``"—"`` when ``df`` is empty.
    """
    if df.empty:
        return "—"
    latest = df["date"].max()
    return f"{latest.month}/{latest.day}/{latest.year}"


def format_full_date(ts: pd.Timestamp) -> str:
    """Format a timestamp as a full calendar date.

    Parameters
    ----------
    ts : pandas.Timestamp
        Timestamp to format.

    Returns
    -------
    str
        Full date string such as ``January 1, 2026``.
    """
    stamp = pd.Timestamp(ts)
    if stamp.tzinfo is not None:
        stamp = stamp.tz_convert("UTC")
    return f"{stamp.strftime('%B')} {stamp.day}, {stamp.year}"


def format_full_month(ts: pd.Timestamp) -> str:
    """Format a timestamp as full month and year.

    Parameters
    ----------
    ts : pandas.Timestamp
        Timestamp to format.

    Returns
    -------
    str
        Month and year string such as ``January 2026``.
    """
    return f"{ts.strftime('%B')} {ts.year}"


def normalize_utc(ts: pd.Timestamp) -> pd.Timestamp:
    """Normalize a timestamp to UTC midnight.

    Parameters
    ----------
    ts : pandas.Timestamp
        Timestamp to normalize.

    Returns
    -------
    pandas.Timestamp
        UTC-normalized timestamp at midnight.
    """
    stamp = pd.Timestamp(ts)
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize("UTC")
    else:
        stamp = stamp.tz_convert("UTC")
    return stamp.normalize()


def window_mask(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    """Return rows with date in ``[start, end)``.

    Parameters
    ----------
    df : pandas.DataFrame
        Run dataframe with a ``date`` column.
    start : pandas.Timestamp
        Inclusive window start.
    end : pandas.Timestamp
        Exclusive window end.

    Returns
    -------
    pandas.Series
        Boolean mask selecting rows inside the window.
    """
    return (df["date"] >= start) & (df["date"] < end)


def _format_mdy_label(dates: pd.Series) -> pd.Series:
    """Format timestamps as abbreviated month-day-year (e.g. Jan 6, 26)."""
    return dates.dt.strftime("%b ") + dates.dt.day.astype(str) + dates.dt.strftime(", %y")


def period_tooltip_label(period_key: str, grain: PeriodGrain) -> str:
    """Return a full-date hover label for a sortable period key.

    Parameters
    ----------
    period_key : str
        Sortable period identifier for the selected grain.
    grain : PeriodGrain
        Calendar aggregation grain (``Day``, ``Week``, ``Month``, or ``Year``).

    Returns
    -------
    str
        Human-readable tooltip label for chart hovers.
    """
    if grain == "Day":
        return format_full_date(pd.Timestamp(period_key, tz="UTC"))
    if grain == "Week":
        year_str, week_str = period_key.split("-")
        monday = pd.Timestamp.fromisocalendar(int(year_str), int(week_str), 1).tz_localize("UTC")
        return format_full_date(monday)
    if grain == "Month":
        return format_full_month(pd.Timestamp(f"{period_key}-01", tz="UTC"))
    return period_key


def with_period_columns(df: pd.DataFrame, grain: PeriodGrain) -> pd.DataFrame:
    """Attach sortable period key and label columns used by aggregators.

    Parameters
    ----------
    df : pandas.DataFrame
        Run dataframe with a ``date`` column.
    grain : PeriodGrain
        Calendar aggregation grain.

    Returns
    -------
    pandas.DataFrame
        Copy of ``df`` with ``_period_key`` and ``_period_label`` columns.
    """
    if df.empty:
        return df
    work = df.copy()
    key, label = _period_key_and_label(work["date"], grain)
    work["_period_key"] = key
    work["_period_label"] = label
    return work


def _period_key_and_label(dates: pd.Series, grain: PeriodGrain) -> tuple[pd.Series, pd.Series]:
    """Map timestamps to sortable period keys and display labels."""
    if grain == "Day":
        key = dates.dt.strftime("%Y-%m-%d")
        label = _format_mdy_label(dates)
        return key, label
    if grain == "Week":
        iso = dates.dt.isocalendar()
        key = iso.year.astype(str) + "-" + iso.week.astype(str).str.zfill(2)
        monday = dates - pd.to_timedelta(iso.day - 1, unit="D")
        label = _format_mdy_label(monday)
        return key, label
    if grain == "Month":
        key = dates.dt.strftime("%Y-%m")
        label = dates.dt.strftime("%b, %y")
        return key, label
    key = dates.dt.strftime("%Y")
    label = dates.dt.strftime("%Y")
    return key, label


def current_period_key(grain: PeriodGrain, as_of: pd.Timestamp) -> str:
    """Return the period key for the calendar period containing ``as_of``.

    Parameters
    ----------
    grain : PeriodGrain
        Calendar aggregation grain.
    as_of : pandas.Timestamp
        Reference timestamp.

    Returns
    -------
    str
        Sortable period key for the containing calendar period.
    """
    as_of = normalize_utc(as_of)
    key, _ = _period_key_and_label(pd.Series([as_of]), grain)
    return key.iloc[0]


def reference_end(df: pd.DataFrame) -> pd.Timestamp:
    """Return the latest activity date normalized to UTC midnight.

    Parameters
    ----------
    df : pandas.DataFrame
        Run dataframe with a ``date`` column.

    Returns
    -------
    pandas.Timestamp
        Latest activity date in UTC, or the current UTC date when ``df`` is empty.
    """
    if df.empty:
        return pd.Timestamp.now(tz="UTC").normalize()
    return normalize_utc(df["date"].max())


def generate_period_index(
    grain: PeriodGrain, end: pd.Timestamp, count: int
) -> pd.DataFrame:
    """Build ordered period keys and labels for the last N calendar periods.

    Parameters
    ----------
    grain : PeriodGrain
        Calendar aggregation grain.
    end : pandas.Timestamp
        End of the period range.
    count : int
        Number of calendar periods to include.

    Returns
    -------
    pandas.DataFrame
        Frame with ``period_key``, ``period_label``, and ``period_tooltip`` columns.
    """
    end = end.normalize()
    if grain == "Day":
        dates = pd.date_range(end=end, periods=count, freq="D", tz=end.tz)
    elif grain == "Week":
        week_start = end - pd.Timedelta(days=int(end.dayofweek))
        dates = pd.date_range(end=week_start, periods=count, freq="7D", tz=end.tz)
    elif grain == "Month":
        month_start = end.replace(day=1)
        dates = pd.date_range(end=month_start, periods=count, freq="MS", tz=end.tz)
    else:
        year_start = end.replace(month=1, day=1)
        dates = pd.date_range(end=year_start, periods=count, freq="YS", tz=end.tz)

    keys, labels = _period_key_and_label(pd.Series(dates), grain)
    tooltips = keys.map(lambda k: period_tooltip_label(k, grain))
    return pd.DataFrame(
        {
            "period_key": keys.to_numpy(),
            "period_label": labels.to_numpy(),
            "period_tooltip": tooltips.to_numpy(),
        }
    )


def filter_to_recent_periods(df: pd.DataFrame, grain: PeriodGrain) -> pd.DataFrame:
    """Keep rows belonging to the last N calendar periods for the selected grain.

    Parameters
    ----------
    df : pandas.DataFrame
        Run dataframe with a ``date`` column.
    grain : PeriodGrain
        Calendar aggregation grain.

    Returns
    -------
    pandas.DataFrame
        Filtered copy containing only rows in the configured recent window.
    """
    if df.empty:
        return df

    end = reference_end(df)
    n = int(PERIOD_CONFIG[grain]["count"])
    keep_keys = set(generate_period_index(grain, end, n)["period_key"])

    work = df.copy()
    key, label = _period_key_and_label(work["date"], grain)
    work["_period_key"] = key
    work["_period_label"] = label
    return work.loc[work["_period_key"].isin(keep_keys)].copy()


def aggregate_period_metrics(
    df: pd.DataFrame,
    grain: PeriodGrain,
    *,
    as_of: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Aggregate miles and easy/hard mileage shares by period label.

    Parameters
    ----------
    df : pandas.DataFrame
        Run dataframe with distance and easy-percentage columns.
    grain : PeriodGrain
        Calendar aggregation grain.
    as_of : pandas.Timestamp, optional
        Reference end date for the period window. Defaults to the latest activity.

    Returns
    -------
    pandas.DataFrame
        One row per period with mileage totals, easy/hard fractions, and an
        ``in_progress`` flag for the current calendar period.
    """
    n = int(PERIOD_CONFIG[grain]["count"])
    end = normalize_utc(as_of) if as_of is not None else reference_end(df)

    full_index = generate_period_index(grain, end, n)

    current_key = current_period_key(grain, end)

    if df.empty:
        out = full_index.copy()
        out["total_miles"] = 0.0
        out["easy_frac"] = 0.0
        out["hard_frac"] = 0.0
        out["in_progress"] = out["period_key"] == current_key
        return out

    work = with_period_columns(df.copy(), grain)
    keep_keys = set(full_index["period_key"])
    work = work.loc[work["_period_key"].isin(keep_keys)]
    if "distance_miles" not in work.columns:
        work["distance_miles"] = 0.0
    if "%_easy" not in work.columns:
        work["%_easy"] = np.nan

    has_hr = work["%_easy"].notna() & work["distance_miles"].notna()
    work["easy_miles"] = 0.0
    work["hard_miles"] = 0.0
    work.loc[has_hr, "easy_miles"] = work.loc[has_hr, "distance_miles"] * (
        work.loc[has_hr, "%_easy"] / 100.0
    )
    work.loc[has_hr, "hard_miles"] = work.loc[has_hr, "distance_miles"] - work.loc[has_hr, "easy_miles"]

    grouped = (
        work.groupby(["_period_key", "_period_label"], as_index=False)
        .agg(
            total_miles=("distance_miles", "sum"),
            easy_miles=("easy_miles", "sum"),
            hard_miles=("hard_miles", "sum"),
        )
        .rename(columns={"_period_key": "period_key", "_period_label": "period_label"})
    )

    hr_total = grouped["easy_miles"] + grouped["hard_miles"]
    grouped["easy_frac"] = 0.0
    grouped["hard_frac"] = 0.0
    positive = hr_total > 0
    grouped.loc[positive, "easy_frac"] = grouped.loc[positive, "easy_miles"] / hr_total[positive]
    grouped.loc[positive, "hard_frac"] = grouped.loc[positive, "hard_miles"] / hr_total[positive]

    merged = full_index.merge(
        grouped[["period_key", "total_miles", "easy_frac", "hard_frac"]],
        on="period_key",
        how="left",
    )
    merged["total_miles"] = merged["total_miles"].fillna(0.0)
    merged["easy_frac"] = merged["easy_frac"].fillna(0.0)
    merged["hard_frac"] = merged["hard_frac"].fillna(0.0)
    merged["in_progress"] = merged["period_key"] == current_key
    return merged[
        [
            "period_key",
            "period_label",
            "period_tooltip",
            "total_miles",
            "easy_frac",
            "hard_frac",
            "in_progress",
        ]
    ]


def easy_hard_ratio_label(df: pd.DataFrame) -> tuple[str, float | None]:
    """Return easy:hard display string and easy percentage for coloring.

    Parameters
    ----------
    df : pandas.DataFrame
        Run dataframe with ``mt_min_easy`` and ``mt_min_hard`` columns.

    Returns
    -------
    tuple[str, float or None]
        Display ratio such as ``"80:20"`` and the easy percentage, or ``("—", None)``
        when heart-rate minutes are unavailable.
    """
    if df.empty or "mt_min_easy" not in df.columns or "mt_min_hard" not in df.columns:
        return "—", None
    easy = df["mt_min_easy"].fillna(0).sum()
    hard = df["mt_min_hard"].fillna(0).sum()
    total = easy + hard
    if total <= 0:
        return "—", None
    easy_pct = 100.0 * easy / total
    hard_pct = 100.0 - easy_pct
    return f"{round(easy_pct)}:{round(hard_pct)}", easy_pct


def key_indicators(df: pd.DataFrame, as_of: pd.Timestamp | None = None) -> dict[str, object]:
    """Compute easy:hard and mileage KPI values for overview cards.

    Parameters
    ----------
    df : pandas.DataFrame
        Run dataframe with date, distance, and heart-rate minute columns.
    as_of : pandas.Timestamp, optional
        Reference date for week and month windows. Defaults to the latest activity.

    Returns
    -------
    dict[str, object]
        Keys ``eh_last_week``, ``eh_last_month``, and ``miles_last_week`` with
        ratio tuples and weekly mileage totals.
    """
    if df.empty:
        return {
            "eh_last_week": ("—", None),
            "eh_last_month": ("—", None),
            "miles_last_week": 0.0,
        }

    as_of = normalize_utc(as_of or df["date"].max())
    week_start, week_end = last_full_week_bounds(as_of)

    month_start = as_of - pd.Timedelta(days=30)
    month_end = as_of + pd.Timedelta(days=1)

    last_week = df.loc[window_mask(df, week_start, week_end)]
    last_month = df.loc[window_mask(df, month_start, month_end)]

    return {
        "eh_last_week": easy_hard_ratio_label(last_week),
        "eh_last_month": easy_hard_ratio_label(last_month),
        "miles_last_week": float(
            last_week["distance_miles"].fillna(0).sum()
            if "distance_miles" in last_week.columns
            else 0.0
        ),
    }
