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

from strava_analytics.activities import last_full_week_bounds
from theme import LONGEST_RUN_GOAL, WEEKLY_MILES_GOAL

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


def _load_gear_uncached(data_dir: Path) -> pd.DataFrame:
    """Load shoe/gear mileage rows from ``strava_gear.csv``."""
    columns = ["gear_id", "name", "type", "mileage", "status"]
    path = data_dir / "strava_gear.csv"
    if not path.exists():
        return pd.DataFrame(columns=columns)

    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    if df.empty:
        return pd.DataFrame(columns=columns)

    out = pd.DataFrame(
        {
            "gear_id": df.get("gear_id", pd.Series(dtype=str)).astype(str).str.strip(),
            "name": df.get("name", pd.Series(dtype=str)).astype(str).str.strip(),
            "type": df.get("type", pd.Series(dtype=str)).astype(str).str.strip(),
            "mileage": pd.to_numeric(df.get("mileage"), errors="coerce"),
            "status": df.get("status", pd.Series(dtype=str))
            .astype(str)
            .str.strip()
            .str.lower(),
        }
    )
    out = out.loc[out["gear_id"] != ""].copy()
    out["mileage"] = out["mileage"].fillna(0.0)
    out["status"] = out["status"].replace({"": "active"})
    return out.reset_index(drop=True)


@st.cache_data(show_spinner=False)
def _load_gear_cached(csv_mtime: float, data_dir_str: str) -> pd.DataFrame:
    return _load_gear_uncached(Path(data_dir_str))


def load_gear(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Load shoe mileage rows from ``strava_gear.csv``.

    Parameters
    ----------
    data_dir : pathlib.Path, optional
        Directory containing ``strava_gear.csv``. Defaults to the repository
        ``data`` folder.

    Returns
    -------
    pandas.DataFrame
        Columns ``gear_id``, ``name``, ``type``, ``mileage``, and ``status``.
    """
    path = data_dir / "strava_gear.csv"
    mtime = path.stat().st_mtime if path.exists() else 0.0
    return _load_gear_cached(mtime, str(data_dir))


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
        Keys ``eh_last_week``, ``eh_last_month``, ``miles_last_week``, and
        ``longest_run_30d`` with ratio tuples and mileage totals.
    """
    frames = kpi_window_frames(df, as_of=as_of)
    last_week = frames["week"]
    last_month = frames["month"]

    if last_month.empty or "distance_miles" not in last_month.columns:
        longest_run = None
    else:
        longest_run = float(last_month["distance_miles"].fillna(0).max())

    return {
        "eh_last_week": easy_hard_ratio_label(last_week),
        "eh_last_month": easy_hard_ratio_label(last_month),
        "miles_last_week": float(
            last_week["distance_miles"].fillna(0).sum()
            if not last_week.empty and "distance_miles" in last_week.columns
            else 0.0
        ),
        "longest_run_30d": longest_run,
    }


_FEET_PER_MILE = 5280.0


def _activity_name_at(df: pd.DataFrame, idx) -> str | None:
    """Return a stripped activity name at ``idx``, or ``None`` if missing."""
    if "name" not in df.columns:
        return None
    value = df.loc[idx, "name"]
    if pd.isna(value):
        return None
    name = str(value).strip()
    return name or None


def _calendar_year_totals(df: pd.DataFrame) -> tuple[int | None, float, float]:
    """Miles and elevation-miles for the calendar year of the latest activity.

    "This year" is the UTC calendar year of ``reference_end(df)``: the latest
    activity date, or today (UTC) when ``df`` is empty. That matches Training
    Overview / Insights, which use the dataset max date as ``as_of``.
    Activity start timestamps are filtered with ``date.year == this_year``.
    """
    if df.empty:
        return int(reference_end(df).year), 0.0, 0.0
    if "date" not in df.columns:
        return None, 0.0, 0.0
    year = int(reference_end(df).year)
    year_df = df.loc[df["date"].dt.year == year]
    miles = (
        float(year_df["distance_miles"].fillna(0).sum())
        if "distance_miles" in year_df.columns
        else 0.0
    )
    elev_ft = (
        float(year_df["elevation_gain_ft"].fillna(0).sum())
        if "elevation_gain_ft" in year_df.columns
        else 0.0
    )
    return year, miles, elev_ft / _FEET_PER_MILE


def lifetime_achievements(
    df: pd.DataFrame,
) -> dict:
    """Compute all-time achievement stats from the full run history.

    Parameters
    ----------
    df : pandas.DataFrame
        Run dataframe with ``distance_miles``, ``elevation_gain_ft``, and ``date``.
        Optional ``name`` is used for badge hover tooltips.

    Returns
    -------
    dict
        ``total_miles``, ``total_elevation_miles`` (``elevation_gain_ft`` / 5280),
        ``this_year`` (UTC calendar year of the latest activity; see
        ``_calendar_year_totals``), ``this_year_miles`` /
        ``this_year_elevation_miles``,
        ``best_week_miles`` / ``best_week_date`` / ``best_week_end`` (max ISO-week
        Mon–Sun mileage, that week's Monday 00:00 UTC, and Sunday),
        ``best_week_runs`` (list of ``{name, date, miles}`` for that week),
        ``longest_run_miles`` / ``longest_run_date`` / ``longest_run_name``, and
        ``most_elevation_ft`` / ``most_elevation_date`` / ``most_elevation_name``.
        Missing series or empty data yield ``0.0`` for totals, ``None`` for max
        stats / dates / names / ``this_year`` (when ``date`` is missing), and
        ``[]`` for ``best_week_runs``.
    """
    this_year, this_year_miles, this_year_elevation_miles = _calendar_year_totals(df)
    empty = {
        "total_miles": 0.0,
        "total_elevation_miles": 0.0,
        "this_year": this_year,
        "this_year_miles": this_year_miles,
        "this_year_elevation_miles": this_year_elevation_miles,
        "best_week_miles": None,
        "best_week_date": None,
        "best_week_end": None,
        "best_week_runs": [],
        "longest_run_miles": None,
        "longest_run_date": None,
        "longest_run_name": None,
        "most_elevation_ft": None,
        "most_elevation_date": None,
        "most_elevation_name": None,
    }
    if df.empty:
        return empty

    total_miles = (
        float(df["distance_miles"].fillna(0).sum())
        if "distance_miles" in df.columns
        else 0.0
    )
    total_elevation_ft = (
        float(df["elevation_gain_ft"].fillna(0).sum())
        if "elevation_gain_ft" in df.columns
        else 0.0
    )
    total_elevation_miles = total_elevation_ft / _FEET_PER_MILE

    most_elevation_ft: float | None = None
    most_elevation_date: pd.Timestamp | None = None
    most_elevation_name: str | None = None
    if "elevation_gain_ft" in df.columns and len(df):
        elev = df["elevation_gain_ft"].fillna(0)
        peak_idx = elev.idxmax()
        most_elevation_ft = float(elev.loc[peak_idx])
        if "date" in df.columns and pd.notna(df.loc[peak_idx, "date"]):
            most_elevation_date = pd.Timestamp(df.loc[peak_idx, "date"])
        most_elevation_name = _activity_name_at(df, peak_idx)

    if "distance_miles" not in df.columns:
        return {
            **empty,
            "total_miles": total_miles,
            "total_elevation_miles": total_elevation_miles,
            "most_elevation_ft": most_elevation_ft,
            "most_elevation_date": most_elevation_date,
            "most_elevation_name": most_elevation_name,
        }

    distances = df["distance_miles"].fillna(0)
    longest_run_miles: float | None = None
    longest_run_date: pd.Timestamp | None = None
    longest_run_name: str | None = None
    if len(distances):
        longest_idx = distances.idxmax()
        longest_run_miles = float(distances.loc[longest_idx])
        if "date" in df.columns and pd.notna(df.loc[longest_idx, "date"]):
            longest_run_date = pd.Timestamp(df.loc[longest_idx, "date"])
        longest_run_name = _activity_name_at(df, longest_idx)

    best_week_miles: float | None = None
    best_week_date: pd.Timestamp | None = None
    best_week_end: pd.Timestamp | None = None
    best_week_runs: list[dict] = []
    if "date" in df.columns:
        weekly = with_period_columns(df, "Week")
        if not weekly.empty and "_period_key" in weekly.columns:
            by_week = weekly.groupby("_period_key", sort=False)["distance_miles"].sum()
            if not by_week.empty:
                best_key = str(by_week.fillna(0).idxmax())
                best_week_miles = float(by_week.loc[best_key])
                # Attribute the badge to ISO-week Monday (not an arbitrary activity).
                year_str, week_str = best_key.split("-", 1)
                best_week_date = pd.Timestamp.fromisocalendar(
                    int(year_str), int(week_str), 1
                ).tz_localize("UTC")
                best_week_end = best_week_date + pd.Timedelta(days=6)
                week_rows = weekly.loc[
                    weekly["_period_key"].astype(str) == best_key
                ].sort_values("date")
                for _, row in week_rows.iterrows():
                    run_date = (
                        pd.Timestamp(row["date"])
                        if pd.notna(row.get("date"))
                        else None
                    )
                    name = None
                    if "name" in week_rows.columns and pd.notna(row.get("name")):
                        stripped = str(row["name"]).strip()
                        name = stripped or None
                    best_week_runs.append(
                        {
                            "name": name,
                            "date": run_date,
                            "miles": float(row["distance_miles"])
                            if pd.notna(row.get("distance_miles"))
                            else 0.0,
                        }
                    )

    return {
        "total_miles": total_miles,
        "total_elevation_miles": total_elevation_miles,
        "this_year": this_year,
        "this_year_miles": this_year_miles,
        "this_year_elevation_miles": this_year_elevation_miles,
        "best_week_miles": best_week_miles,
        "best_week_date": best_week_date,
        "best_week_end": best_week_end,
        "best_week_runs": best_week_runs,
        "longest_run_miles": longest_run_miles,
        "longest_run_date": longest_run_date,
        "longest_run_name": longest_run_name,
        "most_elevation_ft": most_elevation_ft,
        "most_elevation_date": most_elevation_date,
        "most_elevation_name": most_elevation_name,
    }


KPI_DETAIL_OPTIONS = {
    "eh_week": "Easy:Hard Last Week",
    "eh_month": "Easy:Hard 30 Days",
    "miles_week": "Miles Last Week",
    "longest_run": "Longest Run 30 Days",
}


def kpi_window_frames(
    df: pd.DataFrame, as_of: pd.Timestamp | None = None
) -> dict[str, pd.DataFrame | tuple[pd.Timestamp, pd.Timestamp]]:
    """Return current and prior week/month run frames for Metrics drill-downs."""
    empty = df.iloc[0:0].copy() if not df.empty else df.copy()
    if df.empty:
        today = normalize_utc(pd.Timestamp.now(tz="UTC"))
        week_start, week_end = last_full_week_bounds(today)
        month_end = today + pd.Timedelta(days=1)
        month_start = today - pd.Timedelta(days=30)
        return {
            "week": empty,
            "prior_week": empty,
            "month": empty,
            "prior_month": empty,
            "week_bounds": (week_start, week_end),
            "prior_week_bounds": (
                week_start - pd.Timedelta(days=7),
                week_start,
            ),
            "month_bounds": (month_start, month_end),
            "prior_month_bounds": (
                month_start - pd.Timedelta(days=30),
                month_start,
            ),
            "as_of": today,
        }

    as_of = normalize_utc(as_of or df["date"].max())
    week_start, week_end = last_full_week_bounds(as_of)
    prior_week_start = week_start - pd.Timedelta(days=7)
    month_end = as_of + pd.Timedelta(days=1)
    month_start = as_of - pd.Timedelta(days=30)
    prior_month_start = month_start - pd.Timedelta(days=30)

    return {
        "week": df.loc[window_mask(df, week_start, week_end)].copy(),
        "prior_week": df.loc[window_mask(df, prior_week_start, week_start)].copy(),
        "month": df.loc[window_mask(df, month_start, month_end)].copy(),
        "prior_month": df.loc[window_mask(df, prior_month_start, month_start)].copy(),
        "week_bounds": (week_start, week_end),
        "prior_week_bounds": (prior_week_start, week_start),
        "month_bounds": (month_start, month_end),
        "prior_month_bounds": (prior_month_start, month_start),
        "as_of": as_of,
    }


def _run_detail_table(runs: pd.DataFrame) -> pd.DataFrame:
    """Display columns for KPI drill-down run lists."""
    if runs.empty:
        return pd.DataFrame(columns=["Date", "Name", "Miles", "Easy min", "Hard min", "% Easy"])

    ordered = runs.sort_values("date", ascending=True)
    pct = (
        ordered["%_easy"]
        if "%_easy" in ordered.columns
        else pd.Series([None] * len(ordered), index=ordered.index)
    )
    return pd.DataFrame(
        {
            "Date": ordered["date"].dt.tz_convert("UTC").dt.tz_localize(None).dt.normalize(),
            "Name": ordered["name"] if "name" in ordered.columns else "",
            "Miles": ordered["distance_miles"].fillna(0.0).round(2)
            if "distance_miles" in ordered.columns
            else 0.0,
            "Easy min": ordered["mt_min_easy"].fillna(0.0).round(1)
            if "mt_min_easy" in ordered.columns
            else 0.0,
            "Hard min": ordered["mt_min_hard"].fillna(0.0).round(1)
            if "mt_min_hard" in ordered.columns
            else 0.0,
            "% Easy": pct.round(1),
        }
    )


def _daily_miles_table(runs: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """One row per calendar day in ``[start, end)`` with total miles."""
    days = pd.date_range(start=start, end=end - pd.Timedelta(days=1), freq="D", tz="UTC")
    if runs.empty or "distance_miles" not in runs.columns:
        return pd.DataFrame(
            {
                "Date": days.tz_localize(None),
                "Miles": [0.0] * len(days),
            }
        )

    work = runs.copy()
    work["_day"] = work["date"].dt.tz_convert("UTC").dt.normalize()
    grouped = work.groupby("_day", as_index=True)["distance_miles"].sum()
    miles = [float(grouped.get(day, 0.0)) for day in days]
    return pd.DataFrame({"Date": days.tz_localize(None), "Miles": [round(m, 2) for m in miles]})


def _eh_comparison_line(current: tuple[str, float | None], prior: tuple[str, float | None]) -> str:
    cur_label, cur_pct = current
    prior_label, prior_pct = prior
    if cur_pct is None and prior_pct is None:
        return "No easy:hard data for this window or the prior period."
    if prior_pct is None:
        return f"Current {cur_label}; no prior-period comparison available."
    if cur_pct is None:
        return f"Prior period was {prior_label}; no current easy:hard data."
    delta = cur_pct - prior_pct
    direction = "up" if delta > 0 else "down" if delta < 0 else "unchanged"
    if direction == "unchanged":
        return f"Same easy share as prior period ({prior_label} → {cur_label})."
    return (
        f"Easy share {direction} {abs(delta):.0f} pts vs prior period "
        f"({prior_label} → {cur_label})."
    )


def _miles_comparison_line(current: float, prior: float) -> str:
    delta = current - prior
    if abs(delta) < 0.05:
        return f"About even with the prior week ({prior:.2f} mi → {current:.2f} mi)."
    direction = "up" if delta > 0 else "down"
    return (
        f"Miles {direction} {abs(delta):.2f} vs prior week "
        f"({prior:.2f} mi → {current:.2f} mi)."
    )


def _pct_change_badge(
    current: float | None,
    prior: float | None,
    *,
    period_label: str,
) -> str | None:
    """Compact prior-period delta like ``↑ 12% vs previous week``.

    Returns ``None`` when a meaningful comparison is not available.
    """
    if current is None or prior is None:
        return None
    if prior == 0:
        if current == 0:
            return f"→ 0% vs {period_label}"
        return None

    change = ((float(current) - float(prior)) / float(prior)) * 100.0
    if abs(change) < 0.5:
        return f"→ 0% vs {period_label}"
    arrow = "↑" if change > 0 else "↓"
    return f"{arrow} {abs(change):.0f}% vs {period_label}"


def kpi_comparison_badges(
    df: pd.DataFrame, as_of: pd.Timestamp | None = None
) -> dict[str, str | None]:
    """Prior-period comparison strings for each Metrics KPI gauge."""
    frames = kpi_window_frames(df, as_of=as_of)
    week = frames["week"]
    prior_week = frames["prior_week"]
    month = frames["month"]
    prior_month = frames["prior_month"]
    assert isinstance(week, pd.DataFrame)
    assert isinstance(prior_week, pd.DataFrame)
    assert isinstance(month, pd.DataFrame)
    assert isinstance(prior_month, pd.DataFrame)

    _, eh_week_pct = easy_hard_ratio_label(week)
    _, prior_eh_week_pct = easy_hard_ratio_label(prior_week)
    _, eh_month_pct = easy_hard_ratio_label(month)
    _, prior_eh_month_pct = easy_hard_ratio_label(prior_month)

    miles_week = (
        float(week["distance_miles"].fillna(0).sum())
        if not week.empty and "distance_miles" in week.columns
        else 0.0
    )
    prior_miles_week = (
        float(prior_week["distance_miles"].fillna(0).sum())
        if not prior_week.empty and "distance_miles" in prior_week.columns
        else None
    )
    # Only compare miles when the prior week had activity (avoid divide-by-zero noise).
    if prior_week.empty:
        prior_miles_week = None

    longest = (
        float(month["distance_miles"].fillna(0).max())
        if not month.empty and "distance_miles" in month.columns
        else None
    )
    prior_longest = (
        float(prior_month["distance_miles"].fillna(0).max())
        if not prior_month.empty and "distance_miles" in prior_month.columns
        else None
    )

    return {
        "eh_week": _pct_change_badge(
            eh_week_pct, prior_eh_week_pct, period_label="previous week"
        ),
        "eh_month": _pct_change_badge(
            eh_month_pct, prior_eh_month_pct, period_label="previous 30 days"
        ),
        "miles_week": _pct_change_badge(
            miles_week, prior_miles_week, period_label="previous week"
        ),
        "longest_run": _pct_change_badge(
            longest, prior_longest, period_label="previous 30 days"
        ),
    }


def build_kpi_detail(
    df: pd.DataFrame,
    kpi_key: str,
    as_of: pd.Timestamp | None = None,
) -> dict[str, object]:
    """Build title, comparison, insight, and table payload for a Metrics KPI."""
    if kpi_key not in KPI_DETAIL_OPTIONS:
        raise KeyError(f"Unknown KPI key: {kpi_key}")

    frames = kpi_window_frames(df, as_of=as_of)
    week = frames["week"]
    prior_week = frames["prior_week"]
    month = frames["month"]
    prior_month = frames["prior_month"]
    week_bounds = frames["week_bounds"]
    assert isinstance(week, pd.DataFrame)
    assert isinstance(prior_week, pd.DataFrame)
    assert isinstance(month, pd.DataFrame)
    assert isinstance(prior_month, pd.DataFrame)
    assert isinstance(week_bounds, tuple)

    title = KPI_DETAIL_OPTIONS[kpi_key]

    if kpi_key == "eh_week":
        current = easy_hard_ratio_label(week)
        prior = easy_hard_ratio_label(prior_week)
        start, end = week_bounds
        return {
            "title": title,
            "window_label": f"{format_full_date(start)} – {format_full_date(end - pd.Timedelta(days=1))}",
            "comparison": _eh_comparison_line(current, prior),
            "insight": (
                f"Ratio {current[0]} across {len(week)} runs."
                if not week.empty
                else "No runs in the last full week."
            ),
            "table": _run_detail_table(week),
            "empty_message": "No runs in the last full Mon–Sun week.",
        }

    if kpi_key == "eh_month":
        current = easy_hard_ratio_label(month)
        prior = easy_hard_ratio_label(prior_month)
        start, end = frames["month_bounds"]
        assert isinstance(start, pd.Timestamp)
        return {
            "title": title,
            "window_label": f"{format_full_date(start)} – {format_full_date(end - pd.Timedelta(days=1))}",
            "comparison": _eh_comparison_line(current, prior),
            "insight": (
                f"Ratio {current[0]} across {len(month)} runs."
                if not month.empty
                else "No runs in the last 30 days."
            ),
            "table": _run_detail_table(month),
            "empty_message": "No runs in the last 30 days.",
        }

    if kpi_key == "miles_week":
        current_miles = float(week["distance_miles"].fillna(0).sum()) if not week.empty else 0.0
        prior_miles = (
            float(prior_week["distance_miles"].fillna(0).sum()) if not prior_week.empty else 0.0
        )
        start, end = week_bounds
        gap = WEEKLY_MILES_GOAL - current_miles
        insight = (
            f"{current_miles:.2f} mi toward the {WEEKLY_MILES_GOAL:.0f} mi weekly target "
            f"({'+' if gap < 0 else '−'}{abs(gap):.2f} mi)."
        )
        return {
            "title": title,
            "window_label": f"{format_full_date(start)} – {format_full_date(end - pd.Timedelta(days=1))}",
            "comparison": _miles_comparison_line(current_miles, prior_miles),
            "insight": insight,
            "table": _daily_miles_table(week, start, end),
            "empty_message": "No runs in the last full Mon–Sun week.",
        }

    # longest_run
    start, end = frames["month_bounds"]
    assert isinstance(start, pd.Timestamp)
    table = _run_detail_table(month)
    if not table.empty:
        table = table.sort_values("Miles", ascending=False).reset_index(drop=True)
    longest = None if table.empty else float(table.iloc[0]["Miles"])
    longest_name = None if table.empty else str(table.iloc[0]["Name"])
    if longest is None:
        insight = "No runs in the last 30 days."
    else:
        insight = (
            f"Longest: {longest_name} ({longest:.2f} mi); "
            f"target {LONGEST_RUN_GOAL:.0f} mi."
        )
    prior_longest = (
        float(prior_month["distance_miles"].fillna(0).max())
        if not prior_month.empty and "distance_miles" in prior_month.columns
        else None
    )
    if longest is None and prior_longest is None:
        comparison = "No longest-run comparison available."
    elif prior_longest is None:
        comparison = "No prior 30-day window to compare."
    elif longest is None:
        comparison = f"Prior 30 days longest was {prior_longest:.2f} mi."
    else:
        delta = longest - prior_longest
        direction = "up" if delta > 0 else "down" if delta < 0 else "unchanged"
        if direction == "unchanged":
            comparison = f"Matched the prior 30-day longest ({prior_longest:.2f} mi)."
        else:
            comparison = (
                f"Longest run {direction} {abs(delta):.2f} mi vs prior 30 days "
                f"({prior_longest:.2f} → {longest:.2f})."
            )

    return {
        "title": title,
        "window_label": f"{format_full_date(start)} – {format_full_date(end - pd.Timedelta(days=1))}",
        "comparison": comparison,
        "insight": insight,
        "table": table,
        "empty_message": "No runs in the last 30 days.",
    }

