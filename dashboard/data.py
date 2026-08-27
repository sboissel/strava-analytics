"""Data loading and period aggregation for the Runner's Dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import streamlit as st

try:
    from . import _bootstrap  # noqa: F401
except ImportError:
    import _bootstrap  # noqa: F401

from strava_analytics.activities import hr_zone_sec_columns, last_full_week_bounds
from strava_analytics.csv_io import activity_analysis_paths
from strava_analytics.gear import gear_mileage_from_activities
from theme import LONGEST_RUN_GOAL, WEEKLY_MILES_GOAL

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"

PeriodGrain = Literal["Day", "Week", "Month", "Year"]

# Year grain is a fixed calendar window, not a rolling lookback, so early
# years (including all of 2016) stay on the yearly Training/Fitness charts.
YEARLY_START_YEAR = 2016

PERIOD_CONFIG: dict[PeriodGrain, dict[str, int | str]] = {
    "Day": {"count": 30, "showing": "Last 30 days"},
    "Week": {"count": 20, "showing": "Last 20 weeks"},
    "Month": {"count": 20, "showing": "Last 20 months"},
    "Year": {"showing": "Since 2016"},
}


def _coerce_race_flag(series: pd.Series) -> pd.Series:
    """Normalize CSV race flags to boolean.

    Parameters
    ----------
    series : pandas.Series
        Raw ``race`` column from run analysis (bool, string, or mixed).

    Returns
    -------
    pandas.Series
        Boolean series; only explicit true-like values are ``True``.
    """
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    text = series.astype(str).str.strip().str.lower()
    return text.isin(("true", "1", "yes"))


def _load_runs_uncached(data_dir: Path) -> pd.DataFrame:
    """Load run analysis rows with parsed dates and numeric fields."""
    path = data_dir / "strava_run_analysis.csv"
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    df = df.dropna(subset=["date"]).copy()
    for col in (
        "distance_miles",
        "%_easy",
        "mt_min_easy",
        "mt_min_hard",
        "elevation_gain_ft",
        "avg_hr",
        "avg_pace_sec",
        *hr_zone_sec_columns(),
    ):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "race" in df.columns:
        df["race"] = _coerce_race_flag(df["race"])
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
        columns for distance, pace, heart rate, elevation, and a boolean
        ``race`` flag.

    Raises
    ------
    FileNotFoundError
        If the run analysis CSV is missing from ``data_dir``.
    """
    path = data_dir / "strava_run_analysis.csv"
    mtime = path.stat().st_mtime if path.exists() else 0.0
    return _load_runs_cached(mtime, str(data_dir))


def _activity_distances_for_gear(data_dir: Path) -> pd.DataFrame:
    """Load ``gear_id`` / ``distance_miles`` from per-type analysis CSVs."""
    frames: list[pd.DataFrame] = []
    for path in activity_analysis_paths(data_dir):
        if not path.exists():
            continue
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        if "gear_id" not in df.columns or "distance_miles" not in df.columns:
            continue
        frames.append(df[["gear_id", "distance_miles"]])
    if not frames:
        return pd.DataFrame(columns=["gear_id", "distance_miles"])
    return pd.concat(frames, ignore_index=True)


def _analysis_csv_mtime(data_dir: Path) -> float:
    mtimes = [
        path.stat().st_mtime
        for path in activity_analysis_paths(data_dir)
        if path.exists()
    ]
    return max(mtimes) if mtimes else 0.0


def _load_gear_uncached(data_dir: Path) -> pd.DataFrame:
    """Compute shoe mileage from activity ``gear_id`` sums plus baselines."""
    return gear_mileage_from_activities(_activity_distances_for_gear(data_dir))


@st.cache_data(show_spinner=False)
def _load_gear_cached(csv_mtime: float, data_dir_str: str) -> pd.DataFrame:
    return _load_gear_uncached(Path(data_dir_str))


def load_gear(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Load shoe mileage for tracked gear from activity analysis CSVs.

    Mileage is each shoe's ``TRACKED_GEAR`` baseline plus the sum of
    ``distance_miles`` for activities with a matching ``gear_id``.

    Parameters
    ----------
    data_dir : pathlib.Path, optional
        Directory containing ``strava_*_analysis.csv`` files. Defaults to the
        repository ``data`` folder.

    Returns
    -------
    pandas.DataFrame
        Columns ``gear_id``, ``name``, ``type``, ``mileage``, and ``status``.
    """
    return _load_gear_cached(_analysis_csv_mtime(data_dir), str(data_dir))


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


def _format_short_date(ts: pd.Timestamp) -> str:
    """Format a timestamp as an abbreviated calendar date.

    Parameters
    ----------
    ts : pandas.Timestamp
        Timestamp to format.

    Returns
    -------
    str
        Abbreviated date such as ``Jan 1, 2026``.
    """
    stamp = pd.Timestamp(ts)
    if stamp.tzinfo is not None:
        stamp = stamp.tz_convert("UTC")
    return f"{stamp.strftime('%b')} {stamp.day}, {stamp.year}"


def format_week_range_short(monday: pd.Timestamp) -> str:
    """Format an ISO week Monday as a short Mon–Sun range.

    Parameters
    ----------
    monday : pandas.Timestamp
        Monday (ISO day 1) of the week.

    Returns
    -------
    str
        Range such as ``Jan 1, 2026 - Jan 7, 2026``.
    """
    monday = pd.Timestamp(monday)
    if monday.tzinfo is not None:
        monday = monday.tz_convert("UTC")
    sunday = monday + pd.Timedelta(days=6)
    return f"{_format_short_date(monday)} - {_format_short_date(sunday)}"


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
    """Return a hover label for a sortable period key.

    Parameters
    ----------
    period_key : str
        Sortable period identifier for the selected grain.
    grain : PeriodGrain
        Calendar aggregation grain (``Day``, ``Week``, ``Month``, or ``Year``).

    Returns
    -------
    str
        Human-readable tooltip label for chart hovers. Week grain is the ISO
        Mon–Sun range with abbreviated months (``Jan 5, 2026 - Jan 11, 2026``).
    """
    if grain == "Day":
        return format_full_date(pd.Timestamp(period_key, tz="UTC"))
    if grain == "Week":
        year_str, week_str = period_key.split("-")
        monday = pd.Timestamp.fromisocalendar(int(year_str), int(week_str), 1).tz_localize("UTC")
        return format_week_range_short(monday)
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


def period_count(grain: PeriodGrain, end: pd.Timestamp) -> int:
    """Return how many calendar periods the dashboard window includes.

    Day, week, and month grains use a rolling lookback from ``PERIOD_CONFIG``.
    Year grain is a fixed window from ``YEARLY_START_YEAR`` through the
    calendar year of ``end`` (inclusive).

    Parameters
    ----------
    grain : PeriodGrain
        Calendar aggregation grain.
    end : pandas.Timestamp
        Reference end date for the period window.

    Returns
    -------
    int
        Number of periods to include. Always at least 1.
    """
    if grain == "Year":
        years = int(normalize_utc(end).year) - YEARLY_START_YEAR + 1
        return max(1, years)
    return int(PERIOD_CONFIG[grain]["count"])


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
    n = period_count(grain, end)
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
    count: int | None = None,
) -> pd.DataFrame:
    """Aggregate miles, elevation, and easy/hard mileage shares by period.

    Parameters
    ----------
    df : pandas.DataFrame
        Run dataframe with distance, elevation, and easy-percentage columns.
    grain : PeriodGrain
        Calendar aggregation grain.
    as_of : pandas.Timestamp, optional
        Reference end date for the period window. Defaults to the latest activity.
    count : int, optional
        Number of periods to include. Defaults to ``period_count(grain, end)``.

    Returns
    -------
    pandas.DataFrame
        One row per period with mileage totals, summed elevation in feet,
        easy/hard HR miles and unaccounted miles, easy/hard fractions of HR
        miles (NaN when the period has no HR coverage), and an
        ``in_progress`` flag for the current calendar period.
    """
    end = normalize_utc(as_of) if as_of is not None else reference_end(df)
    n = int(count) if count is not None else period_count(grain, end)
    if n < 1:
        raise ValueError("count must be >= 1")

    full_index = generate_period_index(grain, end, n)

    current_key = current_period_key(grain, end)

    if df.empty:
        out = full_index.copy()
        out["total_miles"] = 0.0
        out["total_elevation_ft"] = 0.0
        out["easy_miles"] = 0.0
        out["hard_miles"] = 0.0
        out["unaccounted_miles"] = 0.0
        out["easy_frac"] = np.nan
        out["hard_frac"] = np.nan
        out["in_progress"] = out["period_key"] == current_key
        return out

    work = with_period_columns(df.copy(), grain)
    keep_keys = set(full_index["period_key"])
    work = work.loc[work["_period_key"].isin(keep_keys)]
    if "distance_miles" not in work.columns:
        work["distance_miles"] = 0.0
    if "%_easy" not in work.columns:
        work["%_easy"] = np.nan
    if "elevation_gain_ft" not in work.columns:
        work["elevation_gain_ft"] = 0.0
    else:
        work["elevation_gain_ft"] = pd.to_numeric(
            work["elevation_gain_ft"], errors="coerce"
        ).fillna(0.0)

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
            total_elevation_ft=("elevation_gain_ft", "sum"),
        )
        .rename(columns={"_period_key": "period_key", "_period_label": "period_label"})
    )

    hr_total = grouped["easy_miles"] + grouped["hard_miles"]
    # NaN fractions → Plotly omits the stacked bar (no fake 0% / 100% easy).
    grouped["easy_frac"] = np.nan
    grouped["hard_frac"] = np.nan
    positive = hr_total > 0
    grouped.loc[positive, "easy_frac"] = grouped.loc[positive, "easy_miles"] / hr_total[positive]
    grouped.loc[positive, "hard_frac"] = grouped.loc[positive, "hard_miles"] / hr_total[positive]
    grouped["unaccounted_miles"] = (
        grouped["total_miles"] - grouped["easy_miles"] - grouped["hard_miles"]
    ).clip(lower=0.0)

    merged = full_index.merge(
        grouped[
            [
                "period_key",
                "total_miles",
                "easy_miles",
                "hard_miles",
                "unaccounted_miles",
                "easy_frac",
                "hard_frac",
                "total_elevation_ft",
            ]
        ],
        on="period_key",
        how="left",
    )
    merged["total_miles"] = merged["total_miles"].fillna(0.0)
    merged["total_elevation_ft"] = merged["total_elevation_ft"].fillna(0.0)
    merged["easy_miles"] = merged["easy_miles"].fillna(0.0)
    merged["hard_miles"] = merged["hard_miles"].fillna(0.0)
    merged["unaccounted_miles"] = merged["unaccounted_miles"].fillna(0.0)
    # Leave easy_frac / hard_frac as NaN when the period has no HR miles.
    merged["in_progress"] = merged["period_key"] == current_key
    return merged[
        [
            "period_key",
            "period_label",
            "period_tooltip",
            "total_miles",
            "total_elevation_ft",
            "easy_miles",
            "hard_miles",
            "unaccounted_miles",
            "easy_frac",
            "hard_frac",
            "in_progress",
        ]
    ]


# Longest distance wins when a period has several races; ties use this order.
_RACE_TYPE_PRIORITY = {
    "Marathon": 5,
    "Half": 4,
    "10k": 3,
    "5M": 2,
    "5k": 1,
    "Other": 0,
}


def _normalize_period_race_type(value: object) -> str:
    """Return a race type label, defaulting to Other."""
    text = str(value).strip() if value is not None and not pd.isna(value) else ""
    return text if text else "Other"


def format_race_miles_label(miles: object) -> str:
    """Format miles for Training race-marker hover (1–2 decimal places).

    Parameters
    ----------
    miles : object
        Distance in miles.

    Returns
    -------
    str
        Label such as ``"12.4 mi"`` or ``"6.21 mi"``, or ``"—"`` when missing.
    """
    if miles is None or (isinstance(miles, float) and pd.isna(miles)):
        return "—"
    try:
        value = float(miles)
    except (TypeError, ValueError):
        return "—"
    tenth = round(value, 1)
    if abs(value - tenth) < 1e-6:
        return f"{tenth:.1f} mi"
    return f"{value:.2f} mi"


def race_marker_hover_line(
    name: object,
    race_type: object,
    distance_miles: object = None,
) -> str:
    """Build one race marker hover line: name + type, or name + miles for Other.

    Known buckets (5k, Half, Marathon, …) append the type. ``Other`` (or a
    missing type) appends distance in miles instead of the word ``Other``.
    """
    if name is None or (isinstance(name, float) and pd.isna(name)):
        label = ""
    else:
        label = str(name).strip()
    if not label or label.lower() == "nan":
        label = "Race"
    rtype = _normalize_period_race_type(race_type)
    if rtype == "Other":
        miles_txt = format_race_miles_label(distance_miles)
        if miles_txt != "—":
            return f"{label}<br>{miles_txt}"
        return label
    return f"{label}<br>{rtype}"


def period_race_hover_text(group: pd.DataFrame) -> str:
    """Join per-race hover lines for every race in a period group."""
    if group.empty:
        return "Race"
    lines: list[str] = []
    has_type = "race_type" in group.columns
    has_dist = "distance_miles" in group.columns
    has_name = "name" in group.columns
    for _, row in group.iterrows():
        name = row["name"] if has_name else ""
        rtype = row["race_type"] if has_type else "Other"
        dist = row["distance_miles"] if has_dist else None
        lines.append(race_marker_hover_line(name, rtype, dist))
    return "<br>".join(lines) if lines else "Race"


def _primary_race_type(group: pd.DataFrame) -> str:
    """Pick one race type for a period: longest distance, then type priority."""
    if group.empty:
        return "Other"
    if "race_type" in group.columns:
        types = group["race_type"].map(_normalize_period_race_type)
    else:
        types = pd.Series(["Other"] * len(group), index=group.index)
    if "distance_miles" in group.columns:
        dist = pd.to_numeric(group["distance_miles"], errors="coerce").fillna(-1.0)
    else:
        dist = pd.Series([-1.0] * len(group), index=group.index)
    rank = types.map(_RACE_TYPE_PRIORITY).fillna(0)
    order = pd.DataFrame({"dist": dist, "rank": rank}, index=group.index)
    top_idx = order.sort_values(["dist", "rank"], ascending=False).index[0]
    return str(types.loc[top_idx])


def annotate_race_periods(
    period_df: pd.DataFrame,
    races: pd.DataFrame,
    grain: PeriodGrain,
) -> pd.DataFrame:
    """Flag periods that contain at least one race activity.

    A race period is the calendar day, ISO week, month, or year (matching
    ``grain``) that contains a race activity date. Races are the same rows
    used by Performance (``race`` is true on run analysis).

    When a period contains multiple races, ``race_names`` lists every name
    and ``race_type`` is the primary type: longest ``distance_miles``, with
    ties broken by Marathon > Half > 10k > 5M > 5k > Other. ``race_hover``
    lists each race as name + type, or name + miles when the type is Other.

    Parameters
    ----------
    period_df : pandas.DataFrame
        Period index from ``aggregate_period_metrics``.
    races : pandas.DataFrame
        Race rows with a ``date`` column and optional ``name``, ``race_type``,
        and ``distance_miles``.
    grain : PeriodGrain
        Calendar aggregation grain used for ``period_df``.

    Returns
    -------
    pandas.DataFrame
        Copy of ``period_df`` with ``is_race_period``, ``race_names``,
        ``race_type``, and ``race_hover``.
    """
    out = period_df.copy()
    out["is_race_period"] = False
    out["race_names"] = ""
    out["race_type"] = ""
    out["race_hover"] = ""
    if out.empty or races.empty or "date" not in races.columns:
        return out

    work = races.dropna(subset=["date"]).copy()
    work["date"] = pd.to_datetime(work["date"], utc=True, errors="coerce")
    work = work.dropna(subset=["date"])
    if work.empty:
        return out

    keys, _ = _period_key_and_label(work["date"], grain)
    work["_period_key"] = keys
    if "name" in work.columns:
        names = work["name"].fillna("").astype(str).str.strip()
    else:
        names = pd.Series([""] * len(work), index=work.index)
    work["_race_name"] = names

    name_by_key = work.groupby("_period_key")["_race_name"].agg(
        lambda series: " · ".join(name for name in series if name)
    )
    type_by_key = pd.Series(
        {
            key: _primary_race_type(group)
            for key, group in work.groupby("_period_key")
        }
    )
    hover_by_key = pd.Series(
        {
            key: period_race_hover_text(group)
            for key, group in work.groupby("_period_key")
        }
    )
    out["is_race_period"] = out["period_key"].isin(name_by_key.index)
    out["race_names"] = out["period_key"].map(name_by_key).fillna("")
    out["race_type"] = out["period_key"].map(type_by_key).fillna("")
    out["race_hover"] = out["period_key"].map(hover_by_key).fillna("")
    return out


RACE_PERIOD_ANNOTATION_COLUMNS = (
    "is_race_period",
    "race_names",
    "race_type",
    "race_hover",
)


def merge_race_period_annotations(
    period_df: pd.DataFrame,
    annotated: pd.DataFrame,
) -> pd.DataFrame:
    """Copy race-period columns from ``annotate_race_periods`` onto another frame.

    Parameters
    ----------
    period_df : pandas.DataFrame
        Period rows keyed by ``period_key`` (e.g. pace HR or efficiency).
    annotated : pandas.DataFrame
        Output of ``annotate_race_periods`` for the same grain/window.

    Returns
    -------
    pandas.DataFrame
        ``period_df`` with race annotation columns merged by ``period_key``.
    """
    out = period_df.copy()
    if annotated.empty or out.empty:
        for col in RACE_PERIOD_ANNOTATION_COLUMNS:
            if col not in out.columns:
                out[col] = False if col == "is_race_period" else ""
        return out

    cols = [col for col in RACE_PERIOD_ANNOTATION_COLUMNS if col in annotated.columns]
    payload = annotated[["period_key", *cols]]
    out = out.drop(columns=[col for col in cols if col in out.columns], errors="ignore")
    out = out.merge(payload, on="period_key", how="left")
    out["is_race_period"] = out["is_race_period"].fillna(False).astype(bool)
    for col in ("race_names", "race_type", "race_hover"):
        if col in out.columns:
            out[col] = out[col].fillna("").astype(str)
    return out


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
    / Insights, which use the dataset max date as ``as_of``.
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

