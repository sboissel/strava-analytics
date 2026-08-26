"""Race results loading and PR logic for the Performance page."""

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
    aggregate_period_metrics,
    annotate_race_periods,
    current_period_key,
    format_full_date,
    latest_activity_label,
    load_runs,
    normalize_utc,
    with_period_columns,
)
from strava_analytics.activities import hr_zone_sec_columns, race_distance_label

RACE_TYPE_ORDER = ["5k", "5M", "10k", "Half", "Marathon", "Other"]
PRS_ONLY_FILTER = "PRs only"
# Weeks ending on the race's ISO week for Performance build-up compare.
RACE_BUILDUP_WEEKS_BY_TYPE: dict[str, int] = {
    "5k": 8,
    "5M": 8,
    "10k": 10,
    "Half": 12,
    "Marathon": 16,
}
RACE_BUILDUP_WEEKS_DEFAULT = 12
# Show HR pies only when HR-covered miles exceed this share of total
# pre-race training mileage (else "Insufficient HR data").
RACE_BUILDUP_HR_COVERAGE_MIN = 0.10
# Bump when derived race columns change so Streamlit cache invalidates.
_RACE_LOADER_VERSION = 2


def race_buildup_weeks(race_type: str | None) -> int:
    """Return the pre-race comparison window length for a race type.

    Parameters
    ----------
    race_type : str or None
        Normalized race type such as ``"Half"`` or ``"Marathon"``.

    Returns
    -------
    int
        Number of ISO weeks ending on race week. Unknown types use
        ``RACE_BUILDUP_WEEKS_DEFAULT``.
    """
    if race_type is None:
        return RACE_BUILDUP_WEEKS_DEFAULT
    key = str(race_type).strip()
    return int(RACE_BUILDUP_WEEKS_BY_TYPE.get(key, RACE_BUILDUP_WEEKS_DEFAULT))


RACE_BUILDUP_TITLE_BY_TYPE: dict[str, str] = {
    "5k": "5K",
    "5M": "5M",
    "10k": "10K",
    "Half": "HALF MARATHON",
    "Marathon": "MARATHON",
    "Other": "RACE",
}


def race_buildup_comparison_title(race_type: str | None) -> str:
    """Return an uppercase section title for the race compare header."""
    key = str(race_type or "").strip()
    label = RACE_BUILDUP_TITLE_BY_TYPE.get(key, key.upper() or "RACE")
    return f"{label} RACE COMPARISON"


def race_compare_short_name(row: pd.Series) -> str:
    """Short race label for the build-up summary (e.g. ``Nice 2026``).

    Drops trailing distance words and a trailing dash-suffix, then appends the
    race year when it is not already in the name.
    """
    import re

    name = str(row.get("name") or "").strip() or "Race"
    short = re.split(r"\s+[-–—]\s+", name, maxsplit=1)[0].strip()
    short = re.sub(
        r"\s+(half(?:\s+marathon)?|marathon|10k|5k|5m|5\s*miler)\s*$",
        "",
        short,
        flags=re.IGNORECASE,
    ).strip() or name
    date_raw = row.get("date")
    try:
        year = int(pd.Timestamp(date_raw).year)
    except (TypeError, ValueError):
        return short
    if str(year) not in short:
        return f"{short} {year}"
    return short


def race_buildup_training_periods(
    runs: pd.DataFrame,
    race_row: pd.Series,
    weeks: int,
    *,
    include_race_week: bool = False,
) -> pd.DataFrame:
    """Return pre-race weekly mileage periods for build-up compare.

    By default returns ``weeks`` ISO weeks ending the week before race week so
    summary stats and mileage charts do not mix race-day volume into the
    build-up window. Pass ``include_race_week=True`` to also include the race
    week with race-period diamond annotations.

    Parameters
    ----------
    runs : pandas.DataFrame
        Full run analysis frame.
    race_row : pandas.Series
        Race row with a ``date``.
    weeks : int
        Number of pre-race training weeks.
    include_race_week : bool, optional
        When True, append the race week and annotate it for diamond markers.

    Returns
    -------
    pandas.DataFrame
        Period metrics with ``in_progress`` cleared.
    """
    as_of = race_row["date"]
    n = max(int(weeks), 1)
    # Always fetch through race week, then optionally drop it.
    frame = aggregate_period_metrics(runs, "Week", as_of=as_of, count=n + 1)
    race_key = current_period_key("Week", normalize_utc(as_of))
    if include_race_week:
        out = frame.copy()
        race_frame = pd.DataFrame([race_row])
        race_frame["date"] = pd.to_datetime(
            race_frame["date"], utc=True, errors="coerce"
        )
        out = annotate_race_periods(out, race_frame, "Week")
    else:
        out = frame.loc[frame["period_key"] != race_key].copy()
        if len(out) > n:
            out = out.iloc[-n:].copy()
    out["in_progress"] = False
    return out.reset_index(drop=True)


def _format_miles(value: float | None, *, unit: bool = False) -> str:
    """Format mileage to one decimal; optional `` mi`` suffix."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    text = f"{float(value):.1f}"
    return f"{text} mi" if unit else text


def easy_hard_ratio_from_pct(easy_pct: float | None) -> tuple[str, float | None]:
    """Format an easy-% share as a KPI display string.

    Parameters
    ----------
    easy_pct : float or None
        Easy running percentage (0–100), or ``None`` when HR data is missing.

    Returns
    -------
    tuple[str, float or None]
        Display like ``"72% : 28%"`` and the easy percentage, or ``("—", None)``.
    """
    if easy_pct is None or (isinstance(easy_pct, float) and pd.isna(easy_pct)):
        return "—", None
    easy = int(round(float(easy_pct)))
    hard = max(0, 100 - easy)
    return f"{easy}% : {hard}%", float(easy_pct)


def format_pace_min_per_mile(pace_min: float | None) -> str:
    """Format min/mile pace as ``m:ss/mi``, or an em dash when missing."""
    if pace_min is None or pace_min <= 0 or pd.isna(pace_min):
        return "—"
    total_sec = int(round(float(pace_min) * 60.0))
    minutes, seconds = divmod(abs(total_sec), 60)
    return f"{minutes}:{seconds:02d}/mi"


def _format_miles_delta(delta: float | None, *, unit: bool = False) -> str:
    """Format signed mileage delta; optional `` mi`` suffix."""
    if delta is None or pd.isna(delta):
        return "—"
    sign = "+" if delta >= 0 else "−"
    text = f"{sign}{abs(float(delta)):.1f}"
    return f"{text} mi" if unit else text


def _format_pace_delta(delta_min: float | None) -> str:
    """Format pace delta in minutes; negative means Race B is faster."""
    if delta_min is None or pd.isna(delta_min):
        return "—"
    total_sec = int(round(float(delta_min) * 60.0))
    sign = "+" if total_sec > 0 else "−" if total_sec < 0 else ""
    minutes, seconds = divmod(abs(total_sec), 60)
    return f"{sign}{minutes}:{seconds:02d}/mi"


def _avg_pace_minutes_from_window(window: pd.DataFrame) -> float | None:
    """Distance-weighted average pace (min/mi) from pre-race run rows."""
    if (
        window.empty
        or "avg_pace_sec" not in window.columns
        or "distance_miles" not in window.columns
    ):
        return None
    pace = pd.to_numeric(window["avg_pace_sec"], errors="coerce")
    dist = pd.to_numeric(window["distance_miles"], errors="coerce")
    valid = pace.notna() & (pace > 0) & dist.notna() & (dist > 0)
    if not valid.any():
        return None
    total_sec = float((pace.loc[valid] * dist.loc[valid]).sum())
    total_miles = float(dist.loc[valid].sum())
    if total_miles <= 0:
        return None
    return (total_sec / total_miles) / 60.0


def race_buildup_side_stats(
    runs: pd.DataFrame,
    race_row: pd.Series,
    weeks: int,
) -> dict[str, float | None]:
    """Compute build-up stats for one race (race week excluded).

    Returns
    -------
    dict
        Keys: ``avg_weekly_miles``, ``avg_runs_per_week``, ``peak_week_miles``,
        ``longest_run_miles``, ``easy_pct``, ``avg_pace_min``.
    """
    n_weeks = max(int(weeks), 1)
    training = race_buildup_training_periods(runs, race_row, weeks)
    if training.empty:
        avg_weekly = None
        avg_runs = None
        peak_week = None
        easy_pct = None
        period_keys: set[str] = set()
    else:
        miles = training["total_miles"].fillna(0.0)
        avg_weekly = float(miles.mean())
        peak_week = float(miles.max())
        easy_miles = (
            training["easy_frac"].fillna(0.0) * training["total_miles"].fillna(0.0)
        ).sum()
        hard_miles = (
            training["hard_frac"].fillna(0.0) * training["total_miles"].fillna(0.0)
        ).sum()
        hr_total = float(easy_miles + hard_miles)
        easy_pct = (100.0 * float(easy_miles) / hr_total) if hr_total > 0 else None
        period_keys = set(training["period_key"].astype(str))
        # Denominator is the configured window length so empty weeks pull the
        # average down (same idea as avg weekly mileage over the full index).
        avg_runs = 0.0

    longest = None
    avg_pace_min = None
    if not runs.empty and period_keys:
        work = with_period_columns(runs.copy(), "Week")
        race_key = current_period_key("Week", normalize_utc(race_row["date"]))
        in_window = work["_period_key"].astype(str).isin(period_keys)
        # Belt-and-suspenders: never count race-week activities for training stats.
        not_race_week = work["_period_key"].astype(str) != race_key
        window = work.loc[in_window & not_race_week]
        if avg_runs is not None:
            avg_runs = float(len(window)) / float(n_weeks)
        if "distance_miles" in window.columns:
            window_miles = pd.to_numeric(window["distance_miles"], errors="coerce").dropna()
            if not window_miles.empty:
                longest = float(window_miles.max())
        avg_pace_min = _avg_pace_minutes_from_window(window)

    return {
        "avg_weekly_miles": avg_weekly,
        "avg_runs_per_week": avg_runs,
        "peak_week_miles": peak_week,
        "longest_run_miles": longest,
        "easy_pct": easy_pct,
        "avg_pace_min": avg_pace_min,
    }


def _race_buildup_pre_race_runs(
    runs: pd.DataFrame,
    race_row: pd.Series,
    weeks: int,
) -> pd.DataFrame:
    """Return run rows in the pre-race window (race week excluded)."""
    training = race_buildup_training_periods(runs, race_row, weeks)
    if training.empty or runs.empty or "distance_miles" not in runs.columns:
        return pd.DataFrame()
    period_keys = set(training["period_key"].astype(str))
    race_key = current_period_key("Week", normalize_utc(race_row["date"]))
    work = with_period_columns(runs.copy(), "Week")
    in_window = work["_period_key"].astype(str).isin(period_keys)
    not_race_week = work["_period_key"].astype(str) != race_key
    return work.loc[in_window & not_race_week].copy()


def _hr_zone_distance_mask(work: pd.DataFrame) -> pd.Series:
    """True for rows with positive distance and usable HR-zone seconds."""
    sec_cols = hr_zone_sec_columns()
    if any(col not in work.columns for col in sec_cols):
        return pd.Series(False, index=work.index)
    zone_total = work[sec_cols].sum(axis=1, min_count=1)
    distance = pd.to_numeric(work["distance_miles"], errors="coerce")
    return (
        zone_total.notna()
        & (zone_total > 0)
        & distance.notna()
        & (distance > 0)
    )


def race_buildup_hr_mileage_coverage(
    runs: pd.DataFrame,
    race_row: pd.Series,
    weeks: int,
) -> dict[str, float]:
    """HR-zone mileage coverage over pre-race weeks (excludes race week).

    ``hr_miles`` uses the same usable-zone definition as the build-up pie.
    ``coverage`` is ``hr_miles / total_miles``, or ``0.0`` when total is 0.

    Returns
    -------
    dict
        ``total_miles``, ``hr_miles``, and ``coverage`` (0–1).
    """
    work = _race_buildup_pre_race_runs(runs, race_row, weeks)
    empty = {"total_miles": 0.0, "hr_miles": 0.0, "coverage": 0.0}
    if work.empty:
        return empty

    sec_cols = hr_zone_sec_columns()
    if any(col not in work.columns for col in sec_cols):
        return empty

    for col in sec_cols:
        work[col] = pd.to_numeric(work[col], errors="coerce")
    work["distance_miles"] = pd.to_numeric(work["distance_miles"], errors="coerce")
    positive_dist = work["distance_miles"].notna() & (work["distance_miles"] > 0)
    total_miles = float(work.loc[positive_dist, "distance_miles"].sum())
    hr_mask = _hr_zone_distance_mask(work)
    hr_miles = float(work.loc[hr_mask, "distance_miles"].sum())
    coverage = (hr_miles / total_miles) if total_miles > 0 else 0.0
    return {
        "total_miles": total_miles,
        "hr_miles": hr_miles,
        "coverage": float(coverage),
    }


def race_buildup_hr_coverage_sufficient(
    coverage: dict[str, float] | None,
) -> bool:
    """True when HR-covered miles exceed the build-up display threshold."""
    if coverage is None:
        return False
    try:
        frac = float(coverage.get("coverage", 0.0))
    except (TypeError, ValueError, AttributeError):
        return False
    return frac > RACE_BUILDUP_HR_COVERAGE_MIN


def race_buildup_mileage_hr_zone_shares(
    runs: pd.DataFrame,
    race_row: pd.Series,
    weeks: int,
) -> dict[str, float] | None:
    """Mileage-weighted HR-zone shares over pre-race weeks (excludes race week).

    Each activity with zone seconds and distance contributes its miles to zones
    in proportion to time spent in each zone. Returns ``None`` when the window
    has no usable HR-zone + mileage data.

    Returns
    -------
    dict or None
        ``zone_1_pct`` … ``zone_5_pct`` (0–100) and ``zone_1_miles`` …
        ``zone_5_miles`` when data exists.
    """
    work = _race_buildup_pre_race_runs(runs, race_row, weeks)
    if work.empty:
        return None
    sec_cols = hr_zone_sec_columns()
    if any(col not in work.columns for col in sec_cols):
        return None

    for col in sec_cols:
        work[col] = pd.to_numeric(work[col], errors="coerce")
    work["distance_miles"] = pd.to_numeric(work["distance_miles"], errors="coerce")
    work["_hr_zone_total"] = work[sec_cols].sum(axis=1, min_count=1)
    work = work.loc[_hr_zone_distance_mask(work)]
    if work.empty:
        return None

    miles = np.zeros(len(sec_cols), dtype=float)
    for _, row in work.iterrows():
        total_sec = float(row["_hr_zone_total"])
        dist = float(row["distance_miles"])
        for idx, col in enumerate(sec_cols):
            sec = float(row[col]) if pd.notna(row[col]) else 0.0
            miles[idx] += dist * (sec / total_sec)

    grand = float(miles.sum())
    if grand <= 0:
        return None

    out: dict[str, float] = {}
    for idx, zone_miles in enumerate(miles, start=1):
        out[f"zone_{idx}_miles"] = float(zone_miles)
        out[f"zone_{idx}_pct"] = float(zone_miles) / grand * 100.0
    out["total_miles"] = grand
    return out


def race_buildup_compare_rows(
    runs: pd.DataFrame,
    race_a: pd.Series,
    race_b: pd.Series,
    weeks: int,
) -> list[dict[str, str]]:
    """Build display rows for the Race A / Race B / Δ summary table.

    All training metrics exclude the race week, including average pace.
    """
    stats_a = race_buildup_side_stats(runs, race_a, weeks)
    stats_b = race_buildup_side_stats(runs, race_b, weeks)

    def _delta(a: float | None, b: float | None) -> float | None:
        if a is None or b is None:
            return None
        return float(b) - float(a)

    return [
        {
            "metric": "Avg weekly mileage",
            "race_a": _format_miles(stats_a["avg_weekly_miles"]),
            "race_b": _format_miles(stats_b["avg_weekly_miles"]),
            "delta": _format_miles_delta(
                _delta(stats_a["avg_weekly_miles"], stats_b["avg_weekly_miles"])
            ),
        },
        {
            "metric": "Avg runs/week",
            "race_a": _format_miles(stats_a["avg_runs_per_week"]),
            "race_b": _format_miles(stats_b["avg_runs_per_week"]),
            "delta": _format_miles_delta(
                _delta(stats_a["avg_runs_per_week"], stats_b["avg_runs_per_week"])
            ),
        },
        {
            "metric": "Peak week",
            "race_a": _format_miles(stats_a["peak_week_miles"], unit=True),
            "race_b": _format_miles(stats_b["peak_week_miles"], unit=True),
            "delta": _format_miles_delta(
                _delta(stats_a["peak_week_miles"], stats_b["peak_week_miles"]),
                unit=True,
            ),
        },
        {
            "metric": "Longest run",
            "race_a": _format_miles(stats_a["longest_run_miles"], unit=True),
            "race_b": _format_miles(stats_b["longest_run_miles"], unit=True),
            "delta": _format_miles_delta(
                _delta(stats_a["longest_run_miles"], stats_b["longest_run_miles"]),
                unit=True,
            ),
        },
        {
            "metric": "Avg pace",
            "race_a": format_pace_min_per_mile(stats_a["avg_pace_min"]),
            "race_b": format_pace_min_per_mile(stats_b["avg_pace_min"]),
            "delta": _format_pace_delta(
                _delta(stats_a["avg_pace_min"], stats_b["avg_pace_min"])
            ),
        },
    ]


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


RACE_TABLE_DISPLAY_COLUMNS = [
    "Name",
    "Date",
    "Race Type",
    "Miles",
    "Time",
    "Pace",
    "PR",
]


def race_table_rows(races: pd.DataFrame) -> pd.DataFrame:
    """Build display columns for the race results table.

    Parameters
    ----------
    races : pandas.DataFrame
        Filtered race dataframe.

    Returns
    -------
    pandas.DataFrame
        Table-ready columns sorted by date ascending. Includes a hidden
        ``activity_id`` key for chart selection wiring; UI should omit it from
        ``column_order`` / ``column_config``.
    """
    columns = ["activity_id", *RACE_TABLE_DISPLAY_COLUMNS]
    if races.empty:
        return pd.DataFrame(columns=columns)

    display = races.sort_values("date", ascending=True).copy()
    if "activity_id" in display.columns:
        activity_ids = display["activity_id"].astype(str)
    else:
        activity_ids = pd.Series([""] * len(display), index=display.index, dtype=str)
    return pd.DataFrame(
        {
            "activity_id": activity_ids,
            "Name": display["name"],
            "Date": _race_table_date(display["date"]),
            "Race Type": display["race_type"],
            "Miles": display["distance_miles"],
            "Time": display["elapsed_time_min"].fillna("—"),
            "Pace": display["elapsed_pace"],
            "PR": display["is_pr"].map(lambda pr: "🏆" if pr else ""),
        }
    ).reset_index(drop=True)


def fastest_races_by_type(races: pd.DataFrame) -> pd.DataFrame:
    """Return the fastest race per type, excluding ``Other``.

    Parameters
    ----------
    races : pandas.DataFrame
        Race dataframe with ``race_type``, ``elapsed_min``, and ``date``.

    Returns
    -------
    pandas.DataFrame
        One row per non-``Other`` race type present in ``races``, ordered by
        ``RACE_TYPE_ORDER`` (unknown types last, A–Z). Ties on finish time keep
        the most recent race.
    """
    if races.empty or "race_type" not in races.columns:
        return races.iloc[0:0].copy()

    eligible = races.loc[
        (races["race_type"].notna())
        & (races["race_type"] != "Other")
        & races["elapsed_min"].notna()
    ].copy()
    if eligible.empty:
        return eligible.iloc[0:0].copy()

    eligible = eligible.sort_values(
        ["elapsed_min", "date"],
        ascending=[True, False],
        kind="mergesort",
    )
    best = eligible.groupby("race_type", sort=False, as_index=False).first()

    known = [t for t in RACE_TYPE_ORDER if t != "Other"]
    order = {t: i for i, t in enumerate(known)}
    extras = sorted(set(best["race_type"]) - set(known))
    for i, race_type in enumerate(extras, start=len(known)):
        order[race_type] = i
    best["_ord"] = best["race_type"].map(order)
    return (
        best.sort_values("_ord", kind="mergesort")
        .drop(columns=["_ord"])
        .reset_index(drop=True)
    )


def compare_race_type_options(races: pd.DataFrame) -> list[str]:
    """Return race types that have at least two races for side-by-side compare.

    Parameters
    ----------
    races : pandas.DataFrame
        Race dataframe with a ``race_type`` column.

    Returns
    -------
    list[str]
        Types in ``RACE_TYPE_ORDER`` (then extras A–Z) with two or more races.
    """
    if races.empty or "race_type" not in races.columns:
        return []
    counts = races["race_type"].dropna().astype(str).value_counts()
    ordered = [t for t in RACE_TYPE_ORDER if int(counts.get(t, 0)) >= 2]
    extras = sorted(t for t in counts.index if t not in RACE_TYPE_ORDER and int(counts[t]) >= 2)
    return ordered + extras


def race_option_label(row: pd.Series) -> str:
    """Build a dropdown label for one race, marking personal records.

    Parameters
    ----------
    row : pandas.Series
        Race row with ``name``, ``date``, and ``is_pr``.

    Returns
    -------
    str
        Label such as ``"🏆 PR · Boston Marathon · April 15, 2024"``.
    """
    name = str(row.get("name") or "").strip() or "Race"
    date_raw = row.get("date")
    try:
        date_label = format_full_date(date_raw) if date_raw is not None else "—"
    except (TypeError, ValueError):
        date_label = "—"
    prefix = "🏆 PR · " if bool(row.get("is_pr")) else ""
    return f"{prefix}{name} · {date_label}"


def race_compare_choices(
    races: pd.DataFrame, race_type: str
) -> list[tuple[str, str]]:
    """Return ``(label, activity_id)`` pairs for one race type.

    Parameters
    ----------
    races : pandas.DataFrame
        Full race dataframe.
    race_type : str
        Race type to include.

    Returns
    -------
    list[tuple[str, str]]
        Choices sorted by date descending. Labels are unique; duplicate names
        keep the date (and activity id suffix when still ambiguous).
    """
    if races.empty or not race_type:
        return []
    subset = races.loc[races["race_type"] == race_type].copy()
    if subset.empty:
        return []
    subset = subset.sort_values("date", ascending=False, kind="mergesort")
    if "activity_id" not in subset.columns:
        subset["activity_id"] = subset.index.astype(str)

    labels = [race_option_label(row) for _, row in subset.iterrows()]
    ids = [str(v).strip() for v in subset["activity_id"].tolist()]
    counts = pd.Series(labels).value_counts()
    unique_labels: list[str] = []
    for label, activity_id in zip(labels, ids, strict=True):
        if int(counts[label]) > 1:
            unique_labels.append(f"{label} · {activity_id}")
        else:
            unique_labels.append(label)
    return list(zip(unique_labels, ids, strict=True))


def race_row_by_activity_id(races: pd.DataFrame, activity_id: str) -> pd.Series | None:
    """Return the race row for ``activity_id``, or ``None`` when missing."""
    if races.empty or "activity_id" not in races.columns or not activity_id:
        return None
    match = races.loc[races["activity_id"].astype(str) == str(activity_id)]
    if match.empty:
        return None
    return match.iloc[0]
