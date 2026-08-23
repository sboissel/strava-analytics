"""Plotly chart builders for the Runner's Dashboard."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

import numpy as np
import pandas as pd
import plotly.graph_objects as go

try:
    from . import _bootstrap  # noqa: F401
except ImportError:
    import _bootstrap  # noqa: F401

from data import format_full_date, race_marker_hover_line
from pace_bins import PACE_BIN_OPTIONS
from race_data import RACE_TYPE_ORDER, ensure_race_pace_min
from theme import (
    CHART_TITLE_FONT_WEIGHT,
    CHART_TITLE_SIZE_PX,
    EASY_TARGET_FRAC,
    FITNESS_LEGEND_GUTTER_X_FRAC,
    FITNESS_PLOT_MARGIN_L_PX,
    FITNESS_PLOT_MARGIN_R_PX,
    FONT_BODY,
    INK,
    MUTED,
    RACE_STRIP_BG,
    TRAINING_PLOT_MARGIN_R_PX,
    miles_goal,
)

IN_PROGRESS_OPACITY = 0.5
# Gray hatch overlay (not outline/fade) for the unfinished current period —
# bar fill stays at full opacity; hatch marks the week as incomplete.
IN_PROGRESS_HATCH_SHAPE = "/"
IN_PROGRESS_HATCH_COLOR = "#9AA5AD"
PLOTLY_CONFIG = {"displayModeBar": False}


def _plotly_font_family() -> str:
    return FONT_BODY.replace('"', "")


# Locked Training plot box: race-week strip + 80:20 + mileage + elevation share
# the same left/right margins, category range, and bargap so markers sit on
# the vertical centerline of each period bar. Right margin is slim (no side
# legend). HR Zones keeps a separate Fitness-style L/R box (80/168) for its
# Zone legend + last-week pie gutter.
TRAINING_MARGIN_L = 78
TRAINING_MARGIN_R = TRAINING_PLOT_MARGIN_R_PX
TRAINING_MARGIN_T = 52
# Extra top margin on 80:20: HTML title + ⓘ band, then Easy / Moderate/Hard key.
# Larger than TRAINING_MARGIN_T so the legend clears the overlaid title row.
COMPLIANCE_MARGIN_T = 96
TRAINING_BARGAP = 0.28
TRAINING_OFFSETGROUP = "training-period"
TRAINING_XAXIS_DOMAIN = [0.0, 1.0]
RACE_STRIP_HEIGHT = 40
RACE_STRIP_MARGIN_T = 6
RACE_STRIP_MARGIN_B = 6
RACE_STRIP_PAPER_BG = "rgba(0,0,0,0)"
RACE_STRIP_SQUARE_SIZE = 4
RACE_STRIP_DIAMOND_SIZE = 9
RACE_STRIP_SQUARE_COLOR = "#9AA5AD"
RACE_STRIP_DIAMOND_COLOR = "#E3C677"
# Gold diamonds on Training bar charts (slightly larger than strip markers).
RACE_CHART_DIAMOND_SIZE = 10
# Lift diamonds above bar tops by this fraction of the chart's max bar height.
RACE_CHART_DIAMOND_Y_PAD_FRAC = 0.05
# Fitness line charts: lift by a fraction of the visible y-axis span so diamonds
# clear the line+marker points (residuals / load can be much smaller than bar tops).
RACE_LINE_CHART_DIAMOND_Y_PAD_FRAC = 0.14
# Training 80:20 series (theme EASY/HARD also color Achievements chrome).
# Earthy strip: peach Easy, terracotta Hard (not theme blue/orange).
TRAINING_EASY = "#E8A66C"
TRAINING_HARD = "#D87659"
# Training mileage/elevation series (not theme MILES / ELEVATION_PURPLE chrome).
# Mileage = muted teal from palette; elevation stays muted purple (no purple in
# the 5-swatch strip — #8575A8 still fits the vintage earthy set).
MILEAGE_BAR = "#509B8F"
ELEVATION_BAR = "#8575A8"
TRAINING_GOAL_LINE = "#2E4552"
# Sequential lavender heatmap for elevation bars (pale → Training purple).
ELEVATION_COLORSCALE = [
    [0.0, "#EBE7F2"],
    [1.0, ELEVATION_BAR],
]
# Sequential mileage heatmap (pale teal → Training teal).
MILEAGE_COLORSCALE = [
    [0.0, "#E8F2F0"],
    [1.0, MILEAGE_BAR],
]
# Sequential teal for Avg HR pace series (mileage family, line-readable).
# Light = slowest bin; dark = fastest bin. Sampled by index in the full
# canonical pace-bin list (not renormalized to the current selection).
PACE_HR_COLORSCALE = [
    [0.0, "#B7DDD8"],
    [0.5, MILEAGE_BAR],
    [1.0, "#1A4540"],
]
# HR zone 100% stacked area: cool/easy (Zone 1) → warm/hard (Zone 5).
# Reuses Training teal, gold, and terracotta; adds sage and deep red.
HR_ZONE_COLORS = (
    "#6B9B96",  # Zone 1 — cool sage-teal
    MILEAGE_BAR,  # Zone 2 — Training mileage teal
    RACE_STRIP_DIAMOND_COLOR,  # Zone 3 — muted gold
    TRAINING_HARD,  # Zone 4 — terracotta
    "#A33B3B",  # Zone 5 — deep warm red
)
HR_ZONE_STACKGROUP = "hr_zones"

# Bottom margin: angled period labels. Right margin: slim pad (bar charts) or
# Fitness/HR Zones legend gutter when those layouts override margin.r.
CHART_LAYOUT = dict(
    font=dict(family=_plotly_font_family(), color=INK, size=13),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=TRAINING_MARGIN_L, r=TRAINING_MARGIN_R, t=TRAINING_MARGIN_T, b=72),
    height=410,
)

# Vertical legend to the right of the plot (paper x > 1), clear of bars/grid.
LEGEND_OUTSIDE_RIGHT = dict(
    orientation="v",
    yanchor="top",
    y=1,
    x=1.02,
    xanchor="left",
    bgcolor="rgba(0,0,0,0)",
    borderwidth=0,
    font=dict(size=11, color=MUTED),
    itemsizing="constant",
    tracegroupgap=4,
)

# Fitness legends sit just past the plot (paper x = 1.02).
LEGEND_FITNESS_GUTTER = dict(
    LEGEND_OUTSIDE_RIGHT,
    x=1 + FITNESS_LEGEND_GUTTER_X_FRAC,
)

# Horizontal Easy / Moderate/Hard key under the HTML title band (not a side legend).
# y=1.0 (bottom-anchored) keeps the key just above the plot; COMPLIANCE_MARGIN_T
# clears compliance_info_html above it. traceorder + legendrank keep Easy first
# (stack still draws Easy at the base).
LEGEND_UNDER_TITLE = dict(
    orientation="h",
    yanchor="bottom",
    y=1.0,
    x=0,
    xanchor="left",
    bgcolor="rgba(0,0,0,0)",
    borderwidth=0,
    font=dict(size=11, color=MUTED),
    itemsizing="constant",
    tracegroupgap=16,
    traceorder="normal",
)

def _title(text: str) -> dict:
    return dict(
        text=text,
        font=dict(
            size=CHART_TITLE_SIZE_PX,
            color=INK,
            family=_plotly_font_family(),
            weight=CHART_TITLE_FONT_WEIGHT,
        ),
        x=0,
        xanchor="left",
        y=1,
        yanchor="top",
        pad=dict(t=6, b=8),
    )


def _hoverlabel() -> dict:
    return dict(bgcolor="white", font_size=12, font_family=_plotly_font_family())


def _period_tooltips(period_df: pd.DataFrame) -> list[str]:
    """Full-date hover labels aligned with period rows."""
    if "period_tooltip" in period_df.columns:
        return period_df["period_tooltip"].tolist()
    return period_df["period_label"].tolist()


def _in_progress_hover_note(grain: str) -> str:
    """Hover suffix for the unfinished current period (e.g. ``Week in progress``)."""
    return f"{grain} in progress"


def _bar_period_customdata(period_df: pd.DataFrame, grain: str) -> list[list[str]]:
    """Bar hover customdata: ``[period tooltip, optional in-progress HTML]``.

    Completed periods use an empty second field. The unfinished current period
    gets ``<br>{Grain} in progress`` so Plotly templates can append it between
    the date and the metric line without changing completed hovers.
    """
    tooltips = _period_tooltips(period_df)
    note_html = f"<br>{_in_progress_hover_note(grain)}"
    if "in_progress" not in period_df.columns:
        return [[tip, ""] for tip in tooltips]
    return [
        [tip, note_html if bool(in_prog) else ""]
        for tip, in_prog in zip(tooltips, period_df["in_progress"])
    ]


def compliance_title(grain: str) -> str:
    """Return the 80:20 compliance chart title for a period grain.

    Parameters
    ----------
    grain : str
        Period grain label.

    Returns
    -------
    str
        Chart title string for the selected grain.
    """
    return {
        "Day": "Daily 80:20 Compliance",
        "Week": "Weekly 80:20 Compliance",
        "Month": "Monthly 80:20 Compliance",
        "Year": "Yearly 80:20 Compliance",
    }.get(grain, "80:20 Compliance")


def mileage_title(grain: str) -> str:
    """Return the total mileage chart title for a period grain.

    Parameters
    ----------
    grain : str
        Period grain label.

    Returns
    -------
    str
        Chart title string for the selected grain.
    """
    return {
        "Day": "Daily Mileage",
        "Week": "Weekly Mileage",
        "Month": "Monthly Mileage",
        "Year": "Yearly Mileage",
    }.get(grain, "Mileage")


def elevation_title(grain: str) -> str:
    """Return the summed elevation chart title for a period grain.

    Parameters
    ----------
    grain : str
        Period grain label.

    Returns
    -------
    str
        Chart title string for the selected grain.
    """
    return {
        "Day": "Daily Elevation",
        "Week": "Weekly Elevation",
        "Month": "Monthly Elevation",
        "Year": "Yearly Elevation",
    }.get(grain, "Elevation")


RACE_EVENTS_TITLE = "Races"


def _period_xaxis(
    labels: list[str],
    grain: str,
    *,
    hover_labels: list[str] | None = None,
) -> dict:
    """X-axis with an explicit tick for every period (no auto-thinning).

    When ``hover_labels`` is set, those strings are the categorical x values
    (unified-hover header) while ``labels`` remain the visible tick text.
    """
    categories = hover_labels if hover_labels is not None else labels
    tickfont_size = 9 if grain == "Day" and len(labels) > 14 else 11
    return dict(
        title="",
        type="category",
        categoryorder="array",
        categoryarray=categories,
        tickmode="array",
        tickvals=categories,
        ticktext=labels,
        tickangle=-40,
        tickfont=dict(size=tickfont_size, color=MUTED),
        showticklabels=True,
        showgrid=False,
    )


def _training_margin(
    grain: str,
    label_count: int,
    *,
    top: int | None = None,
    bottom: int | None = None,
) -> dict:
    """Shared left/right plot box; optional top/bottom for the race-week strip."""
    base = _chart_margin(grain, label_count)
    return dict(
        l=TRAINING_MARGIN_L,
        r=TRAINING_MARGIN_R,
        t=TRAINING_MARGIN_T if top is None else top,
        b=base["b"] if bottom is None else bottom,
        autoexpand=False,
    )


def _training_xaxis(
    labels: list[str], grain: str, *, show_tick_labels: bool = True
) -> dict:
    """Period x-axis locked so Training figures share the same plot domain."""
    axis = _period_xaxis(labels, grain)
    n_labels = len(labels)
    axis.update(
        automargin=False,
        fixedrange=True,
        constrain="domain",
        domain=list(TRAINING_XAXIS_DOMAIN),
        anchor="y",
        showticklabels=show_tick_labels,
    )
    if n_labels:
        # Category bars/markers share integer centers; lock the same slot range
        # so a 56px strip cannot drift vs the 410px charts below.
        axis["range"] = [-0.5, n_labels - 0.5]
    if not show_tick_labels:
        axis["ticks"] = ""
        axis["tickangle"] = 0
    return axis


def _training_yaxis(**kwargs) -> dict:
    """Y-axis with automargin off so left plot edges stay aligned."""
    axis = dict(automargin=False, fixedrange=True, zeroline=False)
    axis.update(kwargs)
    return axis


def _heatmap_axis(labels: list[str], *, tickangle: int = 0, side: str | None = None) -> dict:
    """Heatmap axis with an explicit tick for every label (no auto-thinning).

    Grid/zero lines stay off: NaN mileage cells are transparent in Plotly, so
    axis lines would otherwise stroke through empty cells as black lines.
    """
    tickfont_size = 9 if len(labels) > 14 else 10 if len(labels) > 10 else 11
    axis = dict(
        title="",
        type="category",
        categoryorder="array",
        categoryarray=labels,
        tickmode="array",
        tickvals=labels,
        ticktext=labels,
        tickangle=tickangle,
        tickfont=dict(size=tickfont_size, color=MUTED),
        showticklabels=True,
        showgrid=False,
        zeroline=False,
        showline=False,
    )
    if side is not None:
        axis["side"] = side
    return axis


def _chart_margin(grain: str, label_count: int) -> dict:
    """Extra bottom margin when many angled day labels are shown."""
    if grain == "Day" and label_count > 14:
        return dict(l=TRAINING_MARGIN_L, r=TRAINING_MARGIN_R, t=TRAINING_MARGIN_T, b=96)
    return CHART_LAYOUT["margin"]


PACE_HR_HEIGHT = 384
HR_ZONES_HEIGHT = 384
AEROBIC_EFFICIENCY_HEIGHT = 384
FITNESS_FRESHNESS_HEIGHT = 384
RACE_RESULTS_HEIGHT = 410

# Shared Fitness plot box: Fitness & Freshness, Average HR, and Aerobic
# Efficiency share the same L/R margins and x-domain so X axes line up.
# HR Zones (on Training) reuses the same 168px right deadspan for Zone legend
# + last-week pie. Shortest width is set by the legend column; Efficiency
# matches that right gutter (title ⓘ is HTML inline, not a side legend).
FITNESS_MARGIN_L = FITNESS_PLOT_MARGIN_L_PX  # 80 — shared Y title / tick column
FITNESS_MARGIN_R = FITNESS_PLOT_MARGIN_R_PX  # 168 — legend deadspan
FITNESS_MARGIN_T = 72
# Avg HR by Pace heading + rolling subtitle live in HTML (``pace_hr_title_html``);
# Plotly title is blank so top margin matches AE / F&F (X-axis alignment).
PACE_HR_MARGIN_T = FITNESS_MARGIN_T
FITNESS_MARGIN_B = 72
FITNESS_MARGIN_B_DENSE = 96
FITNESS_XAXIS_DOMAIN = [0.0, 1.0]

# Fitness & Freshness series (slate / terracotta / teal — not purple-on-white).
FITNESS_CTL_COLOR = "#2E4552"
FATIGUE_ATL_COLOR = TRAINING_HARD
FORM_TSB_COLOR = MILEAGE_BAR
# Form area fill (tozeroy): translucent so Fitness/Fatigue lines stay readable.
FORM_TSB_FILL_OPACITY = 0.28

# Trailing rolling mean over Show By periods (Avg HR by Pace trend-only;
# Aerobic Efficiency dashed companion).
PACE_HR_TREND_WINDOWS = {
    "Day": 5,
    "Week": 4,
    "Month": 3,
    "Year": 3,
}
PACE_HR_TREND_WINDOW_DEFAULT = 4
PACE_HR_TREND_LINE_WIDTH = 2
EFFICIENCY_TREND_LINE_WIDTH = 1.5
EFFICIENCY_TREND_OPACITY = 0.55

PACE_HR_MARGIN = dict(
    l=FITNESS_MARGIN_L,
    r=FITNESS_MARGIN_R,
    t=PACE_HR_MARGIN_T,
    b=FITNESS_MARGIN_B,
    autoexpand=False,
)
HR_ZONES_MARGIN = dict(
    l=FITNESS_MARGIN_L,
    r=FITNESS_MARGIN_R,
    t=FITNESS_MARGIN_T,
    b=FITNESS_MARGIN_B,
    autoexpand=False,
)
AEROBIC_EFFICIENCY_MARGIN = dict(
    l=FITNESS_MARGIN_L,
    r=FITNESS_MARGIN_R,
    t=FITNESS_MARGIN_T,
    b=FITNESS_MARGIN_B,
    autoexpand=False,
)
FITNESS_FRESHNESS_MARGIN = dict(
    l=FITNESS_MARGIN_L,
    r=FITNESS_MARGIN_R,
    t=FITNESS_MARGIN_T,
    b=FITNESS_MARGIN_B,
    autoexpand=False,
)
# Performance scatter: right gutter only needs short race-type labels
# ("Marathon", "PR") — not the Fitness 168px legend/info deadspan — so
# plot + legend span the same overall width as the Race History table.
RACE_RESULTS_LEGEND_GUTTER_PX = 96
RACE_RESULTS_MARGIN = dict(
    l=66, r=RACE_RESULTS_LEGEND_GUTTER_PX, t=52, b=72, autoexpand=False
)
PACE_HR_MARGIN_DENSE = dict(
    l=FITNESS_MARGIN_L,
    r=FITNESS_MARGIN_R,
    t=PACE_HR_MARGIN_T,
    b=FITNESS_MARGIN_B_DENSE,
    autoexpand=False,
)
HR_ZONES_MARGIN_DENSE = dict(
    l=FITNESS_MARGIN_L,
    r=FITNESS_MARGIN_R,
    t=FITNESS_MARGIN_T,
    b=FITNESS_MARGIN_B_DENSE,
    autoexpand=False,
)
AEROBIC_EFFICIENCY_MARGIN_DENSE = dict(
    l=FITNESS_MARGIN_L,
    r=FITNESS_MARGIN_R,
    t=FITNESS_MARGIN_T,
    b=FITNESS_MARGIN_B_DENSE,
    autoexpand=False,
)
FITNESS_FRESHNESS_MARGIN_DENSE = dict(
    l=FITNESS_MARGIN_L,
    r=FITNESS_MARGIN_R,
    t=FITNESS_MARGIN_T,
    b=FITNESS_MARGIN_B_DENSE,
    autoexpand=False,
)
# Distance from Y tick labels to the rotated axis title. Shared by every
# Fitness chart so the three stacked Y titles keep the same left rhythm.
FITNESS_Y_TITLE_STANDOFF = 32
AEROBIC_EFFICIENCY_Y_TITLE_STANDOFF = FITNESS_Y_TITLE_STANDOFF
FITNESS_FRESHNESS_Y_TITLE_STANDOFF = FITNESS_Y_TITLE_STANDOFF


def _fitness_margin(grain: str, label_count: int, *, dense: dict, normal: dict) -> dict:
    """Shared Fitness L/R plot box; denser bottom when many day labels."""
    if grain == "Day" and label_count > 14:
        return dense
    return normal


def _pace_hr_margin(grain: str, label_count: int) -> dict:
    """HR line chart: right margin for the pace-bin legend."""
    return _fitness_margin(
        grain, label_count, dense=PACE_HR_MARGIN_DENSE, normal=PACE_HR_MARGIN
    )


def _aerobic_efficiency_margin(grain: str, label_count: int) -> dict:
    """Efficiency line: same right gutter as siblings (no side legend)."""
    return _fitness_margin(
        grain,
        label_count,
        dense=AEROBIC_EFFICIENCY_MARGIN_DENSE,
        normal=AEROBIC_EFFICIENCY_MARGIN,
    )


def _fitness_freshness_margin(grain: str, label_count: int) -> dict:
    """Fitness & Freshness: right gutter for the series legend."""
    return _fitness_margin(
        grain,
        label_count,
        dense=FITNESS_FRESHNESS_MARGIN_DENSE,
        normal=FITNESS_FRESHNESS_MARGIN,
    )


def _hr_zones_margin(grain: str, label_count: int) -> dict:
    """HR-zone stacked area: right margin for Zone legend (+ HTML last-week pie)."""
    return _fitness_margin(
        grain, label_count, dense=HR_ZONES_MARGIN_DENSE, normal=HR_ZONES_MARGIN
    )


def _fitness_xaxis(
    labels: list[str],
    grain: str,
    *,
    hover_labels: list[str] | None = None,
    show_tick_labels: bool = True,
) -> dict:
    """Period x-axis locked so Fitness figures share the same plot domain."""
    axis = _period_xaxis(labels, grain, hover_labels=hover_labels)
    n_labels = len(labels)
    axis.update(
        automargin=False,
        fixedrange=True,
        constrain="domain",
        domain=list(FITNESS_XAXIS_DOMAIN),
        anchor="y",
        showticklabels=show_tick_labels,
    )
    if n_labels:
        # Category bars/markers share integer centers; lock the same slot range
        # so the race-week strip cannot drift vs the Fitness charts below.
        axis["range"] = [-0.5, n_labels - 0.5]
    if not show_tick_labels:
        axis["ticks"] = ""
        axis["tickangle"] = 0
    return axis


def _fitness_strip_margin(grain: str, label_count: int) -> dict:
    """Race-week strip margins aligned to the Fitness plot box."""
    return dict(
        l=FITNESS_MARGIN_L,
        r=FITNESS_MARGIN_R,
        t=RACE_STRIP_MARGIN_T,
        b=RACE_STRIP_MARGIN_B,
        autoexpand=False,
    )


def _heatmap_margin(*, x_tickangle: int) -> dict:
    """Top x-axis labels sit below the title inside margin.t."""
    top = 88 if x_tickangle else 68
    bottom = 36 if x_tickangle else 28
    return dict(l=56, r=24, t=top, b=bottom, autoexpand=False)


def _bar_opacities(period_df: pd.DataFrame, *, base: float = 1.0) -> list[float]:
    """Per-point opacity: dim the in-progress calendar period (non-bar charts)."""
    if "in_progress" not in period_df.columns:
        return [base] * len(period_df)
    return [
        base * IN_PROGRESS_OPACITY if bool(in_prog) else base
        for in_prog in period_df["in_progress"]
    ]


def _in_progress_bar_pattern_shapes(period_df: pd.DataFrame) -> list[str]:
    """Per-bar hatch shape: pattern only on the unfinished current period."""
    if "in_progress" not in period_df.columns:
        return [""] * len(period_df)
    return [
        IN_PROGRESS_HATCH_SHAPE if bool(in_prog) else ""
        for in_prog in period_df["in_progress"]
    ]


def _in_progress_bar_pattern(period_df: pd.DataFrame) -> dict:
    """Gray hatch over normal fill colors for the unfinished period."""
    return dict(
        shape=_in_progress_bar_pattern_shapes(period_df),
        fgcolor=IN_PROGRESS_HATCH_COLOR,
        fillmode="overlay",
    )


def _format_miles_goal(goal: float) -> str:
    """Clean goal label: integer when whole, otherwise one decimal."""
    if abs(goal - round(goal)) < 1e-9:
        return str(int(round(goal)))
    return f"{goal:.1f}"


def _race_period_hover_details(period_df: pd.DataFrame) -> list[str]:
    """Hover body for each period: name + type, or name + miles for Other."""
    if period_df.empty:
        return []
    if "race_hover" in period_df.columns:
        hover_col = period_df["race_hover"].fillna("").astype(str)
    else:
        hover_col = pd.Series([""] * len(period_df), index=period_df.index)
    if "race_names" in period_df.columns:
        names = period_df["race_names"].fillna("").astype(str)
    else:
        names = pd.Series([""] * len(period_df), index=period_df.index)
    race_types = _race_strip_types(period_df)
    if "race_distance_miles" in period_df.columns:
        distances = period_df["race_distance_miles"]
    else:
        distances = pd.Series([None] * len(period_df), index=period_df.index)

    details: list[str] = []
    for prebuilt, name, race_type, dist in zip(
        hover_col, names, race_types, distances, strict=True
    ):
        text = prebuilt.strip()
        if text:
            details.append(text)
        else:
            details.append(race_marker_hover_line(name, race_type, dist))
    return details


def _race_line_y_tops(*columns: pd.Series) -> list[float]:
    """Per-period max y among aligned series (for line-chart diamond placement)."""
    if not columns:
        return []
    frame = pd.concat([col.astype(float) for col in columns], axis=1)
    return frame.max(axis=1, skipna=True).fillna(0.0).tolist()


def _race_diamond_y_positions(
    period_df: pd.DataFrame,
    y_tops: pd.Series | list[float],
    *,
    y_axis_range: tuple[float, float] | None = None,
) -> tuple[list[str], list[float], list[str]]:
    """Return race-period diamond x labels, y positions, and hover bodies."""
    if period_df.empty or "is_race_period" not in period_df.columns:
        return [], [], []
    is_race = period_df["is_race_period"].fillna(False).astype(bool)
    if not bool(is_race.any()):
        return [], [], []

    ys = pd.Series(y_tops, index=period_df.index, dtype=float)
    if y_axis_range is not None:
        y_lo, y_hi = y_axis_range
        pad = max(float(y_hi) - float(y_lo), 1e-9) * RACE_LINE_CHART_DIAMOND_Y_PAD_FRAC
    else:
        y_max = float(ys.fillna(0.0).max()) if len(ys) else 0.0
        pad = y_max * RACE_CHART_DIAMOND_Y_PAD_FRAC
    race = period_df.loc[is_race]
    labels = race["period_label"].astype(str).tolist()
    y_vals = (ys.loc[is_race].fillna(0.0).astype(float) + pad).tolist()
    hover = _race_period_hover_details(race)
    return labels, y_vals, hover


def _extend_y_range_for_race_diamonds(
    y_min: float,
    y_max: float,
    period_df: pd.DataFrame,
    y_tops: pd.Series | list[float],
) -> tuple[float, float]:
    """Ensure a line chart's y-axis top clears race diamonds placed above markers."""
    _, y_vals, _ = _race_diamond_y_positions(
        period_df, y_tops, y_axis_range=(y_min, y_max)
    )
    if not y_vals:
        return y_min, y_max
    span = max(float(y_max) - float(y_min), 1e-9)
    headroom = span * 0.02
    return y_min, max(float(y_max), max(y_vals) + headroom)


def _add_race_week_diamonds(
    fig: go.Figure,
    period_df: pd.DataFrame,
    y_tops: pd.Series | list[float],
    *,
    y_axis_range: tuple[float, float] | None = None,
) -> None:
    """Overlay gold diamonds slightly above race-period bar tops (no dashed vlines).

    ``y_tops`` must align with ``period_df`` rows (stacked total for 80:20,
    bar height for mileage/elevation, line high-water mark for Fitness lines).
    Diamonds sit at ``top + pad`` where ``pad`` is a fraction of either the
    chart y-axis span (``y_axis_range``) or ``max(y_tops)`` for bar charts.
    Uses the same categorical x as the top race-week strip. Hover shows race
    name + type (or miles for Other); no legend entry.
    """
    labels, y_vals, hover = _race_diamond_y_positions(
        period_df, y_tops, y_axis_range=y_axis_range
    )
    if not labels:
        return

    fig.add_trace(
        go.Scatter(
            x=labels,
            y=y_vals,
            mode="markers",
            marker=dict(
                symbol="diamond",
                size=RACE_CHART_DIAMOND_SIZE,
                color=RACE_STRIP_DIAMOND_COLOR,
                line=dict(width=0),
            ),
            customdata=hover,
            hovertemplate="<b>%{customdata}</b><extra></extra>",
            showlegend=False,
            cliponaxis=False,
        )
    )


def compliance_chart(period_df: pd.DataFrame, grain: str) -> go.Figure:
    """Build a 100% stacked easy vs hard mileage compliance chart.

    Heading comes from ``compliance_info_html`` (title + inline ⓘ); blank Plotly
    title plus ``COMPLIANCE_MARGIN_T`` leave room for the Easy / Moderate/Hard
    key under that HTML title band (no overlap).

    Parameters
    ----------
    period_df : pandas.DataFrame
        Aggregated period metrics from ``aggregate_period_metrics``.
    grain : str
        Period grain label used for axis formatting.

    Returns
    -------
    plotly.graph_objects.Figure
        Stacked bar chart with an 80% easy target line.
    """
    fig = go.Figure()
    labels = [] if period_df.empty else period_df["period_label"].tolist()
    if period_df.empty:
        fig.update_layout(
            title=_title(""),
            xaxis=_training_xaxis(labels, grain),
            yaxis=_training_yaxis(),
            **{**CHART_LAYOUT, "margin": _training_margin(grain, 0, top=COMPLIANCE_MARGIN_T)},
        )
        return fig

    customdata = _bar_period_customdata(period_df, grain)
    # Full fill opacity; gray hatch on the unfinished current period.
    in_progress_pattern = _in_progress_bar_pattern(period_df)
    fig.add_trace(
        go.Bar(
            name="Easy",
            x=labels,
            y=period_df["easy_frac"],
            offsetgroup=TRAINING_OFFSETGROUP,
            alignmentgroup=TRAINING_OFFSETGROUP,
            # Leave cornerradius unset on Easy (square join). Explicit 0 would be the
            # first stack radius Plotly applies and would flatten the whole column.
            marker=dict(
                color=TRAINING_EASY,
                pattern=in_progress_pattern,
            ),
            legendrank=1,
            customdata=customdata,
            hovertemplate=(
                "<b>%{customdata[0]}</b>%{customdata[1]}"
                "<br>Easy: %{y:.0%}<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Bar(
            name="Moderate/Hard",
            x=labels,
            y=period_df["hard_frac"],
            offsetgroup=TRAINING_OFFSETGROUP,
            alignmentgroup=TRAINING_OFFSETGROUP,
            # First set cornerradius in the stack → rounds outer column tops (~mileage).
            marker=dict(
                color=TRAINING_HARD,
                pattern=in_progress_pattern,
                cornerradius=5,
            ),
            legendrank=2,
            customdata=customdata,
            hovertemplate=(
                "<b>%{customdata[0]}</b>%{customdata[1]}"
                "<br>Moderate/Hard: %{y:.0%}<extra></extra>"
            ),
        )
    )
    fig.add_hline(
        y=EASY_TARGET_FRAC,
        line_width=1,
        line_color=TRAINING_GOAL_LINE,
        annotation_text="Goal: 80% easy",
        annotation_font=dict(size=12, color=MUTED),
        annotation_position="top left",
        annotation_bgcolor="rgba(255,255,255,0.35)",
    )
    fig.update_layout(
        title=_title(""),
        barmode="stack",
        showlegend=True,
        legend=LEGEND_UNDER_TITLE,
        yaxis=_training_yaxis(
            title=dict(text="Fraction of mileage", font=dict(size=12, color=MUTED)),
            range=[0, 1.08],
            tickformat=".1f",
            gridcolor="rgba(21,32,40,0.08)",
        ),
        xaxis=_training_xaxis(labels, grain),
        bargap=TRAINING_BARGAP,
        bargroupgap=0,
        hoverlabel=_hoverlabel(),
        **{
            **CHART_LAYOUT,
            "margin": _training_margin(grain, len(labels), top=COMPLIANCE_MARGIN_T),
        },
    )
    stack_tops = period_df["easy_frac"].fillna(0.0) + period_df["hard_frac"].fillna(0.0)
    _add_race_week_diamonds(fig, period_df, stack_tops)
    return fig


def mileage_chart(period_df: pd.DataFrame, grain: str) -> go.Figure:
    """Build a total mileage bar chart with a solid ``MILEAGE_BAR`` fill.

    The calendar mileage heatmap (Training expander)
    uses ``mileage_heatmap_chart`` with ``MILEAGE_COLORSCALE``. Keeping
    the main bars solid preserves alignment with the race-week strip,
    80:20, and elevation charts.

    Parameters
    ----------
    period_df : pandas.DataFrame
        Aggregated period metrics from ``aggregate_period_metrics``.
    grain : str
        Period grain label used for goal scaling and axis formatting.

    Returns
    -------
    plotly.graph_objects.Figure
        Bar chart with a scaled mileage goal line.
    """
    title = mileage_title(grain)
    fig = go.Figure()
    labels = [] if period_df.empty else period_df["period_label"].tolist()
    if period_df.empty:
        fig.update_layout(
            title=_title(title),
            xaxis=_training_xaxis(labels, grain),
            yaxis=_training_yaxis(),
            showlegend=False,
            **{**CHART_LAYOUT, "margin": _training_margin(grain, 0)},
        )
        return fig

    customdata = _bar_period_customdata(period_df, grain)
    totals = period_df["total_miles"].fillna(0.0)
    mile_values = totals.tolist()
    goal = miles_goal(grain)
    fig.add_trace(
        go.Bar(
            x=labels,
            y=mile_values,
            offsetgroup=TRAINING_OFFSETGROUP,
            alignmentgroup=TRAINING_OFFSETGROUP,
            marker=dict(
                color=MILEAGE_BAR,
                pattern=_in_progress_bar_pattern(period_df),
                cornerradius=5,
                opacity=0.92,
            ),
            customdata=customdata,
            hovertemplate=(
                "<b>%{customdata[0]}</b>%{customdata[1]}"
                "<br>%{y:.1f} miles<extra></extra>"
            ),
            showlegend=False,
        )
    )
    fig.add_hline(
        y=goal,
        line_width=1,
        line_color=TRAINING_GOAL_LINE,
        annotation_text=f"Goal: {_format_miles_goal(goal)} miles",
        annotation_font=dict(size=12, color=MUTED),
        annotation_position="top left",
        annotation_bgcolor="rgba(255,255,255,0.35)",
    )
    y_max = max(float(totals.max()), goal) * 1.18
    y_max = max(y_max, 5)
    fig.update_layout(
        title=_title(title),
        showlegend=False,
        yaxis=_training_yaxis(
            title=dict(text="Total Miles", font=dict(size=12, color=MUTED)),
            range=[0, y_max],
            gridcolor="rgba(21,32,40,0.08)",
        ),
        xaxis=_training_xaxis(labels, grain),
        bargap=TRAINING_BARGAP,
        bargroupgap=0,
        hoverlabel=_hoverlabel(),
        **{**CHART_LAYOUT, "margin": _training_margin(grain, len(labels))},
    )
    _add_race_week_diamonds(fig, period_df, totals)
    return fig


def _race_strip_types(period_df: pd.DataFrame) -> pd.Series:
    """Primary race type per period; empty string when the column is absent."""
    if "race_type" not in period_df.columns:
        return pd.Series([""] * len(period_df), index=period_df.index)
    return period_df["race_type"].fillna("").astype(str)


def _race_strip_label_gutter(*, margin_l: int = TRAINING_MARGIN_L) -> dict:
    """Transparent fill for the left label column (paper pixels, not plot)."""
    return dict(
        type="rect",
        xref="paper",
        yref="paper",
        xsizemode="pixel",
        xanchor=0,
        x0=0,
        x1=margin_l,
        y0=0,
        y1=1,
        fillcolor=RACE_STRIP_BG,
        line=dict(width=0),
        layer="below",
    )


def _race_strip_bg_shapes(n_labels: int, *, margin_l: int = TRAINING_MARGIN_L) -> list[dict]:
    """Transparent strip shapes: label gutter + timeline; not full paper width."""
    shapes = [_race_strip_label_gutter(margin_l=margin_l)]
    if n_labels:
        shapes.append(_race_strip_compact_bg(n_labels))
    return shapes


def _race_strip_compact_bg(n_labels: int) -> dict:
    """Transparent fill from the first through last category slot.

    Ends at the last marker's slot so the slim Training right margin is not
    covered. Category range stays ``[-0.5, n-0.5]``.
    """
    return dict(
        type="rect",
        xref="x",
        yref="paper",
        x0=-0.5,
        x1=n_labels - 0.5,
        y0=0,
        y1=1,
        fillcolor=RACE_STRIP_BG,
        line=dict(width=0),
        layer="below",
    )


def race_weeks_chart(
    period_df: pd.DataFrame,
    grain: str,
    *,
    plot: Literal["training", "fitness"] = "training",
) -> go.Figure:
    """Build a compact race-period marker strip aligned to the page x-axis.

    Non-race periods are small cool-gray squares. Race periods are larger
    muted-gold diamonds (one race color for every type). Hover shows each race
    name with its type, or miles when the type is Other.

    Parameters
    ----------
    period_df : pandas.DataFrame
        Period metrics with ``is_race_period`` and optional ``race_names``,
        ``race_type``, and ``race_hover``.
    grain : str
        Period grain label used for axis formatting.
    plot : {"training", "fitness"}, optional
        Margin and x-axis profile for the charts below the strip.

    Returns
    -------
    plotly.graph_objects.Figure
        Marker strip with the same category x-axis as the charts below.
    """
    fig = go.Figure()
    labels = [] if period_df.empty else period_df["period_label"].tolist()
    fitness_plot = plot == "fitness"
    margin_l = FITNESS_MARGIN_L if fitness_plot else TRAINING_MARGIN_L
    if fitness_plot:
        strip_margin = _fitness_strip_margin(grain, len(labels))
        xaxis_fn = _fitness_xaxis
    else:
        strip_margin = _training_margin(
            grain,
            len(labels),
            top=RACE_STRIP_MARGIN_T,
            bottom=RACE_STRIP_MARGIN_B,
        )
        xaxis_fn = _training_xaxis
    strip_layout = {
        **CHART_LAYOUT,
        "height": RACE_STRIP_HEIGHT,
        "margin": strip_margin,
        "showlegend": False,
        "title": dict(text=""),
        # Keep the plot domain full-width (same L/R margins as charts below).
        # Paper, plot, and strip shapes are transparent so charts show through.
        "plot_bgcolor": RACE_STRIP_PAPER_BG,
        "paper_bgcolor": RACE_STRIP_PAPER_BG,
        "hovermode": "closest",
        "shapes": _race_strip_bg_shapes(len(labels), margin_l=margin_l),
    }
    if not fitness_plot:
        strip_layout.update(
            barmode="overlay",
            bargap=TRAINING_BARGAP,
            bargroupgap=0,
        )
    yaxis = (
        dict(
            automargin=False,
            fixedrange=True,
            zeroline=False,
            range=[0, 1],
            showticklabels=False,
            showgrid=False,
            ticks="",
            title=dict(text=""),
        )
        if fitness_plot
        else _training_yaxis(
            range=[0, 1],
            showticklabels=False,
            showgrid=False,
            ticks="",
            title=dict(text=""),
            zeroline=False,
        )
    )
    if period_df.empty:
        fig.update_layout(
            xaxis=xaxis_fn(labels, grain, show_tick_labels=False),
            yaxis=yaxis,
            **strip_layout,
        )
        return fig

    if "is_race_period" in period_df.columns:
        is_race = period_df["is_race_period"].fillna(False).astype(bool)
    else:
        is_race = pd.Series([False] * len(period_df), index=period_df.index)

    tooltips = _period_tooltips(period_df)
    race_details = _race_period_hover_details(period_df)
    hover = []
    for tip, flag, detail in zip(tooltips, is_race, race_details, strict=True):
        if flag:
            hover.append((tip, detail))
        else:
            hover.append((tip, "No race"))
    colors = [
        RACE_STRIP_DIAMOND_COLOR if flag else RACE_STRIP_SQUARE_COLOR
        for flag in is_race
    ]
    symbols = ["diamond" if flag else "square" for flag in is_race]
    sizes = [
        RACE_STRIP_DIAMOND_SIZE if flag else RACE_STRIP_SQUARE_SIZE for flag in is_race
    ]
    opacities = _bar_opacities(period_df)
    if not fitness_plot:
        fig.add_trace(
            go.Bar(
                x=labels,
                y=[1.0] * len(period_df),
                offsetgroup=TRAINING_OFFSETGROUP,
                alignmentgroup=TRAINING_OFFSETGROUP,
                marker=dict(color="rgba(0,0,0,0)", line=dict(width=0)),
                hoverinfo="skip",
                showlegend=False,
            )
        )
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=[0.5] * len(period_df),
            mode="markers",
            marker=dict(
                color=colors,
                symbol=symbols,
                size=sizes,
                opacity=opacities,
                line=dict(width=0),
            ),
            customdata=hover,
            hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<extra></extra>",
            showlegend=False,
            cliponaxis=False,
        )
    )
    fig.update_layout(
        yaxis=yaxis,
        xaxis=xaxis_fn(labels, grain, show_tick_labels=False),
        hoverlabel=_hoverlabel(),
        **strip_layout,
    )
    return fig


def elevation_chart(period_df: pd.DataFrame, grain: str) -> go.Figure:
    """Build a summed elevation bar chart in feet.

    Bars use a sequential heatmap (pale tint → ``ELEVATION_BAR``). No
    colorbar: ``showscale=False`` keeps the plot box aligned with the
    other Training charts. Achievements keep ``ELEVATION_PURPLE``.

    Parameters
    ----------
    period_df : pandas.DataFrame
        Aggregated period metrics from ``aggregate_period_metrics``.
    grain : str
        Period grain label used for axis formatting.

    Returns
    -------
    plotly.graph_objects.Figure
        Bar chart of total elevation gain per period, in feet.
    """
    title = elevation_title(grain)
    fig = go.Figure()
    labels = [] if period_df.empty else period_df["period_label"].tolist()
    if period_df.empty:
        fig.update_layout(
            title=_title(title),
            xaxis=_training_xaxis(labels, grain),
            yaxis=_training_yaxis(),
            showlegend=False,
            **{**CHART_LAYOUT, "margin": _training_margin(grain, 0)},
        )
        return fig

    if "total_elevation_ft" in period_df.columns:
        totals = period_df["total_elevation_ft"].fillna(0.0)
    else:
        totals = pd.Series([0.0] * len(period_df), index=period_df.index)
    customdata = _bar_period_customdata(period_df, grain)
    elev_values = totals.tolist()
    fig.add_trace(
        go.Bar(
            x=labels,
            y=elev_values,
            offsetgroup=TRAINING_OFFSETGROUP,
            alignmentgroup=TRAINING_OFFSETGROUP,
            marker=dict(
                color=elev_values,
                colorscale=ELEVATION_COLORSCALE,
                cmin=0,
                cmax=max(float(totals.max()), 1.0),
                showscale=False,
                pattern=_in_progress_bar_pattern(period_df),
                cornerradius=5,
                opacity=0.92,
            ),
            customdata=customdata,
            hovertemplate=(
                "<b>%{customdata[0]}</b>%{customdata[1]}"
                "<br>%{y:,.0f} ft<extra></extra>"
            ),
            showlegend=False,
        )
    )
    y_max = max(float(totals.max()) * 1.18, 100.0)
    fig.update_layout(
        title=_title(title),
        showlegend=False,
        yaxis=_training_yaxis(
            title=dict(text="Elevation (ft)", font=dict(size=12, color=MUTED)),
            range=[0, y_max],
            tickformat=",.0f",
            gridcolor="rgba(21,32,40,0.08)",
        ),
        xaxis=_training_xaxis(labels, grain),
        bargap=TRAINING_BARGAP,
        bargroupgap=0,
        hoverlabel=_hoverlabel(),
        **{**CHART_LAYOUT, "margin": _training_margin(grain, len(labels))},
    )
    _add_race_week_diamonds(fig, period_df, totals)
    return fig


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    """Parse a ``#RRGGBB`` color into 0–255 RGB components."""
    value = color.removeprefix("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _rgb_to_hex(r: float, g: float, b: float) -> str:
    """Format RGB components as ``#RRGGBB``."""
    return "#{:02X}{:02X}{:02X}".format(
        max(0, min(255, int(round(r)))),
        max(0, min(255, int(round(g)))),
        max(0, min(255, int(round(b)))),
    )


def _colorscale_at(colorscale: Sequence[Sequence[object]], t: float) -> str:
    """Interpolate a Plotly-style hex colorscale at ``t`` in ``[0, 1]``."""
    t = min(1.0, max(0.0, float(t)))
    stops = [(float(stop), str(color)) for stop, color in colorscale]
    for t_stop, color in stops:
        if abs(t - t_stop) < 1e-12:
            return color
    if t <= stops[0][0]:
        return stops[0][1]
    if t >= stops[-1][0]:
        return stops[-1][1]
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t0 <= t <= t1:
            span = t1 - t0
            frac = 0.0 if span == 0 else (t - t0) / span
            r0, g0, b0 = _hex_to_rgb(c0)
            r1, g1, b1 = _hex_to_rgb(c1)
            return _rgb_to_hex(
                r0 + frac * (r1 - r0),
                g0 + frac * (g1 - g0),
                b0 + frac * (b1 - b0),
            )
    return stops[-1][1]


def pace_hr_bin_color_map(
    ordered_bins: Sequence[str] | None = None,
) -> dict[str, str]:
    """Return a fixed color for every pace bin in the canonical ordered list.

    Colors are sampled from ``PACE_HR_COLORSCALE`` by index in the full list
    (fastest → darkest). Selection never changes a bin's assigned color.

    Parameters
    ----------
    ordered_bins : sequence of str or None
        Pace-bin identities ordered fastest → slowest. Defaults to Fitness
        display labels from ``PACE_BIN_OPTIONS``.

    Returns
    -------
    dict of str to str
        ``bin_id → #RRGGBB`` for every entry in ``ordered_bins``.
    """
    bins = (
        list(ordered_bins)
        if ordered_bins is not None
        else [label for label, _key in PACE_BIN_OPTIONS]
    )
    count = len(bins)
    if count <= 0:
        return {}
    if count == 1:
        return {bins[0]: _colorscale_at(PACE_HR_COLORSCALE, 1.0)}
    return {
        bin_id: _colorscale_at(PACE_HR_COLORSCALE, 1.0 - i / (count - 1))
        for i, bin_id in enumerate(bins)
    }


def pace_hr_series_colors(
    selected: Sequence[str],
    *,
    ordered_bins: Sequence[str] | None = None,
) -> list[str]:
    """Look up fixed pace-bin colors for the selected series.

    Does not renormalize among the selection: a lone slow bin keeps its light
    teal; Under 7:00 stays darkest whether alone or with others.

    Parameters
    ----------
    selected : sequence of str
        Pace-bin labels (or keys) for the series being drawn, typically
        ordered fastest → slowest.
    ordered_bins : sequence of str or None
        Full canonical ordered list used to build the fixed color map.

    Returns
    -------
    list of str
        ``#RRGGBB`` colors, one per selected series.
    """
    if not selected:
        return []
    color_map = pace_hr_bin_color_map(ordered_bins)
    fallback = _colorscale_at(PACE_HR_COLORSCALE, 0.5)
    return [color_map.get(bin_id, fallback) for bin_id in selected]


def _pace_labels_for_title(pace_labels: str | Sequence[str]) -> list[str]:
    """Normalize a pace-label argument to a list of display strings."""
    if isinstance(pace_labels, str):
        return [pace_labels] if pace_labels else []
    return [label for label in pace_labels if label]


def pace_hr_title(grain: str, pace_labels: str | Sequence[str] = ()) -> str:
    """Return the pace-vs-HR line chart title for selected pace bins.

    Parameters
    ----------
    grain : str
        Period grain label.
    pace_labels : str or sequence of str
        Human-readable pace-bin label(s).

    Returns
    -------
    str
        Chart title string for the selected pace range(s).
    """
    labels = _pace_labels_for_title(pace_labels)
    if len(labels) == 1:
        return f"Average HR for {labels[0]} min/mile pace"
    return "Average HR by Pace Range"


def pace_hr_trend_window(grain: str) -> int:
    """Return the rolling-mean window (periods) for Avg HR pace trends.

    Windows match the Show By grain so weekly charts use a ~month smooth
    (4 weeks) while day / month / year stay in a 3–5 period band.

    Parameters
    ----------
    grain : str
        Period grain label (``Day``, ``Week``, ``Month``, ``Year``).

    Returns
    -------
    int
        Trailing window length in calendar periods.
    """
    return int(PACE_HR_TREND_WINDOWS.get(grain, PACE_HR_TREND_WINDOW_DEFAULT))


def pace_hr_trend_subtitle(grain: str) -> str:
    """Return the on-chart rolling-window label for Avg HR by Pace.

    Always-visible subtitle copy (not hover-only), e.g. ``4-week rolling
    average`` when Show By is Week.

    Parameters
    ----------
    grain : str
        Period grain label (``Day``, ``Week``, ``Month``, ``Year``).

    Returns
    -------
    str
        Grain-appropriate trailing-window phrase.
    """
    window = pace_hr_trend_window(grain)
    return f"{window}-{_grain_period_unit(grain)} rolling average"


def _pace_hr_rolling_mean(values: pd.Series, window: int) -> pd.Series:
    """Trailing rolling mean of average HR; early periods use a partial window."""
    numeric = pd.to_numeric(values, errors="coerce")
    return numeric.rolling(window=max(int(window), 1), min_periods=1).mean()


def heatmap_title(grain: str) -> str:
    """Return the mileage heatmap title for a period grain.

    Parameters
    ----------
    grain : str
        Period grain label.

    Returns
    -------
    str
        Chart title string for the selected grain.
    """
    return {
        "Day": "Daily Mileage by Month",
        "Week": "Weekly Mileage by Month",
        "Month": "Monthly Mileage by Year",
        "Year": "Yearly Mileage",
    }.get(grain, "Mileage")


def _efficiency_axis_range(residuals: pd.Series) -> tuple[float, float]:
    """Pad an elevation-adjusted efficiency residual range around zero."""
    finite = residuals.dropna()
    if finite.empty:
        return -0.01, 0.01
    span = float(finite.max()) - float(finite.min())
    pad = max(span * 0.15, 1e-4)
    y_min = min(float(finite.min()), 0.0) - pad
    y_max = max(float(finite.max()), 0.0) + pad
    if y_max <= y_min:
        y_max = y_min + 1e-4
    return y_min, y_max


def _grain_period_unit(grain: str) -> str:
    """Singular period noun for trend hover copy (day / week / …)."""
    return {
        "Day": "day",
        "Week": "week",
        "Month": "month",
        "Year": "year",
    }.get(grain, "period")


def pace_hr_line_chart(
    series: Sequence[tuple[str, pd.DataFrame]],
    grain: str,
    *,
    period_df: pd.DataFrame | None = None,
) -> go.Figure:
    """Build an average heart-rate trend chart for selected pace bins.

    Each selected pace bin draws one solid trailing rolling-mean trend
    (no raw Avg HR series) so multi-bin selections stay readable. Window
    length follows ``pace_hr_trend_window`` for the grain; the same window
    appears as a muted HTML subtitle via ``pace_hr_title_html`` (Plotly
    title is blank). Legend labels are the pace-bin names. Hover shows
    the period (unified x header), that period's Avg HR, and the rolling
    mean — without the series name.

    Colors come from a fixed per-bin map on ``PACE_HR_COLORSCALE`` (full
    list: darker = faster), not from the current selection alone.

    Parameters
    ----------
    series : sequence of (str, pandas.DataFrame)
        ``(pace_label, period_df)`` pairs from ``aggregate_pace_hr_by_period``,
        ordered fastest to slowest.
    grain : str
        Period grain label used for axis formatting and trend window.
    period_df : pandas.DataFrame, optional
        Period index with ``is_race_period`` for gold race-week diamonds.
        Defaults to the first non-empty series frame when omitted.

    Returns
    -------
    plotly.graph_objects.Figure
        Multi-trace line chart of smoothed average heart rate by period.
    """
    # Heading + rolling subtitle come from ``pace_hr_title_html``; keep top
    # margin so the plot domain matches Aerobic Efficiency / F&F.
    pace_labels = [label for label, _ in series]
    fig = go.Figure()
    frames = [df for _, df in series if df is not None and not df.empty]
    if not series or not frames:
        fig.update_layout(title=_title(""), showlegend=False, **CHART_LAYOUT)
        return fig

    axis_df = frames[0]
    labels = axis_df["period_label"].tolist()
    tooltips = _period_tooltips(axis_df)
    race_df = period_df if period_df is not None else axis_df

    colors = pace_hr_series_colors(pace_labels)
    all_hr: list[pd.Series] = []
    all_trends: list[pd.Series] = []
    trend_window = pace_hr_trend_window(grain)
    grain_unit = _grain_period_unit(grain)
    multi_pace = sum(
        1
        for _, period_df in series
        if period_df is not None
        and not period_df.empty
        and "avg_hr" in period_df.columns
    ) > 1
    # Period label on x matches sibling Fitness charts; tooltip in hover body.
    trend_label = f"{trend_window}-{grain_unit} avg"

    for (pace_label, bin_df), color in zip(series, colors):
        if bin_df.empty or "avg_hr" not in bin_df.columns:
            continue
        avg_hr = bin_df["avg_hr"]
        trend = _pace_hr_rolling_mean(avg_hr, trend_window)
        all_hr.append(avg_hr)
        all_trends.append(trend)
        trace_tooltips = _period_tooltips(bin_df)
        pace_suffix = f"<br>{pace_label}" if multi_pace else ""
        hovertemplate = (
            "<b>%{customdata[0]}</b><br>"
            "Avg HR: %{customdata[1]:.0f} bpm<br>"
            f"{trend_label}: %{{y:.0f}} bpm"
            f"{pace_suffix}"
            "<extra></extra>"
        )
        fig.add_trace(
            go.Scatter(
                x=labels,
                y=_nan_to_none(trend),
                mode="lines",
                name=pace_label,
                legendgroup=pace_label,
                line=dict(color=color, width=PACE_HR_TREND_LINE_WIDTH),
                connectgaps=False,
                customdata=[
                    [tip, None if pd.isna(hr) else float(hr)]
                    for tip, hr in zip(trace_tooltips, avg_hr, strict=True)
                ],
                hovertemplate=hovertemplate,
                hoverlabel=dict(namelength=0),
            )
        )

    finite = pd.concat(all_hr, ignore_index=True).dropna() if all_hr else pd.Series(dtype=float)
    y_min = float(finite.min()) - 5 if not finite.empty else 120.0
    y_max = float(finite.max()) + 5 if not finite.empty else 180.0
    y_min = max(y_min, 100.0)
    y_max = max(y_max, y_min + 10.0)

    fig.update_layout(
        title=_title(""),
        showlegend=True,
        legend=LEGEND_FITNESS_GUTTER,
        yaxis=dict(
            title=dict(
                text="Average HR (bpm)",
                font=dict(size=12, color=MUTED),
                standoff=FITNESS_Y_TITLE_STANDOFF,
            ),
            range=[y_min, y_max],
            gridcolor="rgba(21, 32, 40, 0.08)",
            zeroline=False,
            automargin=False,
            fixedrange=True,
        ),
        xaxis=_fitness_xaxis(labels, grain),
        hovermode="x unified",
        hoverlabel={**_hoverlabel(), "namelength": 0},
        **{
            **CHART_LAYOUT,
            "height": PACE_HR_HEIGHT,
            "margin": _pace_hr_margin(grain, len(labels)),
        },
    )
    if all_trends:
        _add_race_week_diamonds(
            fig,
            race_df,
            _race_line_y_tops(*all_trends),
        )
    return fig



def hr_zones_title(grain: str) -> str:
    """Return the HR-zone stacked area chart title for a period grain.

    Parameters
    ----------
    grain : str
        Period grain label.

    Returns
    -------
    str
        Chart title string for the selected grain.
    """
    return {
        "Day": "Daily Heart Rate Zones",
        "Week": "Weekly Heart Rate Zones",
        "Month": "Monthly Heart Rate Zones",
        "Year": "Yearly Heart Rate Zones",
    }.get(grain, "Heart Rate Zones")


def _nan_to_none(values: pd.Series) -> list[float | None]:
    """Convert a numeric series to Plotly y values, using ``None`` for gaps."""
    return [None if pd.isna(v) else float(v) for v in values]


def hr_zones_stacked_area_chart(
    period_df: pd.DataFrame,
    grain: str,
) -> go.Figure:
    """Build a 100% stacked area chart of HR-zone time by period.

    Each period's ``zone_1_pct`` … ``zone_5_pct`` already sum to 100 when HR
    data exists. Periods with no zone time use ``None`` so the stack gaps
    instead of drawing a fake 0% band. The last completed Mon–Sun week pie is
    rendered beside this chart in the Training right gutter (see
    ``hr_zones_last_week_pie_html``), under the Zone legend.

    Parameters
    ----------
    period_df : pandas.DataFrame
        Period aggregates from ``aggregate_hr_zones_by_period``.
    grain : str
        Period grain label used for axis formatting.

    Returns
    -------
    plotly.graph_objects.Figure
        Stacked area chart with y-axis 0–100%.
    """
    title = hr_zones_title(grain)
    fig = go.Figure()
    labels = [] if period_df.empty else period_df["period_label"].tolist()
    tooltips = [] if period_df.empty else _period_tooltips(period_df)
    hover_x = tooltips if tooltips else labels
    axis_layout = dict(
        title=_title(title),
        legend=LEGEND_OUTSIDE_RIGHT,
        yaxis=dict(
            title=dict(text="Percent of HR time", font=dict(size=12, color=MUTED)),
            range=[0, 100],
            ticksuffix="%",
            gridcolor="rgba(21, 32, 40, 0.08)",
            zeroline=False,
            automargin=False,
            fixedrange=True,
        ),
        xaxis=_fitness_xaxis(labels, grain, hover_labels=hover_x or None),
        hovermode="x unified",
        hoverlabel=_hoverlabel(),
        **{
            **CHART_LAYOUT,
            "height": HR_ZONES_HEIGHT,
            "margin": _hr_zones_margin(grain, len(labels)),
        },
    )
    if period_df.empty:
        fig.update_layout(**axis_layout)
        return fig

    for idx, color in enumerate(HR_ZONE_COLORS, start=1):
        col = f"zone_{idx}_pct"
        if col in period_df.columns:
            y_vals = _nan_to_none(period_df[col])
        else:
            y_vals = [None] * len(period_df)
        fig.add_trace(
            go.Scatter(
                x=hover_x,
                y=y_vals,
                name=f"Zone {idx}",
                mode="lines",
                line=dict(width=0.5, color=color),
                fillcolor=color,
                stackgroup=HR_ZONE_STACKGROUP,
                connectgaps=False,
                customdata=tooltips,
                hovertemplate=f"Zone {idx}: %{{y:.0f}}%<extra></extra>",
            )
        )
    fig.update_layout(**axis_layout)
    return fig


def aerobic_efficiency_title(grain: str) -> str:
    """Return the aerobic-efficiency chart title for a period grain.

    Elevation adjustment is explained in the Fitness title ⓘ tooltip, not in
    the chart heading or Y-axis title.

    Parameters
    ----------
    grain : str
        Period grain label.

    Returns
    -------
    str
        Chart title string for the selected grain.
    """
    return {
        "Day": "Daily Aerobic Efficiency",
        "Week": "Weekly Aerobic Efficiency",
        "Month": "Monthly Aerobic Efficiency",
        "Year": "Yearly Aerobic Efficiency",
    }.get(grain, "Aerobic Efficiency")


def _efficiency_hover_number(value: object, spec: str) -> str:
    """Format a hover number, using an em dash when missing."""
    if value is None or (isinstance(value, float) and np.isnan(value)) or pd.isna(value):
        return "—"
    return format(float(value), spec)


def aerobic_efficiency_line_chart(period_df: pd.DataFrame, grain: str) -> go.Figure:
    """Build a line + markers + trend chart of elevation-adjusted efficiency residuals.

    Y values are OLS residuals of ``efficiency ~ ft/mi`` (mph per bpm).
    Period medians draw as lines+markers; a dashed trailing rolling-mean
    **Trend** uses the same Show By window as Avg HR by Pace
    (``pace_hr_trend_window``). Missing periods use ``None`` so the series gaps
    instead of drawing zero. Legend entries are line-only (visible markers stay
    on the plot via a hidden ``lines+markers`` trace plus a line legend proxy).

    Parameters
    ----------
    period_df : pandas.DataFrame
        Period aggregates from ``aggregate_aerobic_efficiency_by_period``.
    grain : str
        Period grain label used for axis formatting and trend window.

    Returns
    -------
    plotly.graph_objects.Figure
        Scatter + trend of median residual by calendar period.
    """
    # Heading comes from ``aerobic_efficiency_info_html`` (title + inline ⓘ);
    # keep top margin so the plot domain matches siblings.
    fig = go.Figure()
    y_title = dict(
        text="Aerobic Efficiency",
        font=dict(size=12, color=MUTED),
        standoff=AEROBIC_EFFICIENCY_Y_TITLE_STANDOFF,
    )
    if period_df.empty:
        fig.update_layout(title=_title(""), **CHART_LAYOUT)
        fig.update_layout(
            yaxis=dict(
                title=y_title,
                zeroline=True,
                zerolinecolor="rgba(21, 32, 40, 0.18)",
                gridcolor="rgba(21, 32, 40, 0.08)",
                automargin=False,
                fixedrange=True,
            ),
            xaxis=_fitness_xaxis([], grain),
            height=AEROBIC_EFFICIENCY_HEIGHT,
            margin=_aerobic_efficiency_margin(grain, 0),
        )
        return fig

    labels = period_df["period_label"].tolist()
    tooltips = _period_tooltips(period_df)
    residuals = (
        period_df["residual"] if "residual" in period_df.columns else pd.Series(dtype=float)
    )
    y_vals = _nan_to_none(residuals)
    efficiencies = (
        period_df["efficiency"]
        if "efficiency" in period_df.columns
        else pd.Series(np.nan, index=period_df.index)
    )
    climbs = (
        period_df["elev_ft_per_mile"]
        if "elev_ft_per_mile" in period_df.columns
        else pd.Series(np.nan, index=period_df.index)
    )
    customdata = [
        [
            tip,
            _efficiency_hover_number(resid, ".4f"),
            _efficiency_hover_number(eff, ".4f"),
            _efficiency_hover_number(climb, ".0f"),
        ]
        for tip, resid, eff, climb in zip(
            tooltips, residuals, efficiencies, climbs, strict=True
        )
    ]
    opacities = _bar_opacities(period_df)
    # Plot shows lines+markers; legend uses a line-only proxy (Plotly has no
    # legend-without-markers for scatter lines+markers). Same pattern as Race
    # Results PR star legend proxy.
    ae_legend_group = "Aerobic Efficiency"
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=y_vals,
            mode="lines+markers",
            name="Aerobic Efficiency",
            legendgroup=ae_legend_group,
            showlegend=False,
            line=dict(color=ELEVATION_BAR, width=2),
            marker=dict(color=ELEVATION_BAR, size=7, opacity=opacities),
            connectgaps=False,
            customdata=customdata,
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Adj. efficiency: %{customdata[1]}<br>"
                "Raw: %{customdata[2]} mph/bpm<br>"
                "Climb: %{customdata[3]} ft/mi"
                "<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="lines",
            name="Aerobic Efficiency",
            legendgroup=ae_legend_group,
            showlegend=True,
            line=dict(color=ELEVATION_BAR, width=2),
            hoverinfo="skip",
        )
    )
    trend_window = pace_hr_trend_window(grain)
    grain_unit = _grain_period_unit(grain)
    trend = _pace_hr_rolling_mean(residuals, trend_window)
    r, g, b = _hex_to_rgb(ELEVATION_BAR)
    trend_color = f"rgba({r}, {g}, {b}, {EFFICIENCY_TREND_OPACITY})"
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=_nan_to_none(trend),
            mode="lines",
            name="Trend",
            legendgroup="Trend",
            showlegend=True,
            line=dict(
                color=trend_color,
                width=EFFICIENCY_TREND_LINE_WIDTH,
                dash="dash",
            ),
            connectgaps=False,
            hovertemplate=(
                f"Trend ({trend_window}-{grain_unit} avg): %{{y:.4f}}<extra></extra>"
            ),
        )
    )
    y_min, y_max = _efficiency_axis_range(
        pd.concat([residuals, trend], ignore_index=True)
    )
    line_tops = _race_line_y_tops(residuals, trend)
    diamond_axis = (y_min, y_max)
    y_min, y_max = _extend_y_range_for_race_diamonds(
        y_min, y_max, period_df, line_tops
    )
    fig.update_layout(
        title=_title(""),
        showlegend=True,
        legend=LEGEND_FITNESS_GUTTER,
        yaxis=dict(
            title=y_title,
            range=[y_min, y_max],
            zeroline=True,
            zerolinecolor="rgba(21, 32, 40, 0.18)",
            gridcolor="rgba(21, 32, 40, 0.08)",
            # Fixed shared FITNESS_MARGIN_L — do not let automargin grow l alone.
            automargin=False,
            fixedrange=True,
        ),
        xaxis=_fitness_xaxis(labels, grain),
        hoverlabel=_hoverlabel(),
        **{
            **CHART_LAYOUT,
            "height": AEROBIC_EFFICIENCY_HEIGHT,
            "margin": _aerobic_efficiency_margin(grain, len(labels)),
        },
    )
    _add_race_week_diamonds(
        fig,
        period_df,
        line_tops,
        y_axis_range=diamond_axis,
    )
    return fig


def fitness_freshness_title(grain: str) -> str:
    """Return the Fitness & Freshness chart title for a period grain.

    Parameters
    ----------
    grain : str
        Period grain label.

    Returns
    -------
    str
        Chart title string for the selected grain.
    """
    return {
        "Day": "Daily Fitness & Freshness",
        "Week": "Weekly Fitness & Freshness",
        "Month": "Monthly Fitness & Freshness",
        "Year": "Yearly Fitness & Freshness",
    }.get(grain, "Fitness & Freshness")


def _fitness_freshness_axis_range(
    fitness: pd.Series, fatigue: pd.Series, form: pd.Series
) -> tuple[float, float]:
    """Return a padded Y range covering Fitness, Fatigue, and Form."""
    frames = [s.dropna() for s in (fitness, fatigue, form) if s is not None]
    finite = pd.concat(frames, ignore_index=True) if frames else pd.Series(dtype=float)
    if finite.empty:
        return -20.0, 60.0
    y_min = float(finite.min())
    y_max = float(finite.max())
    pad = max((y_max - y_min) * 0.12, 5.0)
    return y_min - pad, y_max + pad


def fitness_form_fatigue_line_chart(period_df: pd.DataFrame, grain: str) -> go.Figure:
    """Build Fitness / Fatigue lines and Form area at Show By period ends.

    Heading comes from ``fitness_freshness_info_html`` (title + inline ⓘ);
    Plotly title stays empty so the plot domain matches Fitness siblings. Form
    is drawn first as a ``tozeroy`` fill (behind), then Fitness and Fatigue as
    lines on top; legend order stays Fitness / Fatigue / Form via ``legendrank``.
    Plot traces use lines+markers; the legend uses line-only proxies (same
    pattern as Aerobic Efficiency).

    Parameters
    ----------
    period_df : pandas.DataFrame
        Period aggregates from ``aggregate_fitness_form_fatigue_by_period``.
    grain : str
        Period grain label used for axis formatting.

    Returns
    -------
    plotly.graph_objects.Figure
        Fitness and Fatigue lines over a Form shaded area (fill to zero).
    """
    fig = go.Figure()
    y_title = dict(
        text="Load / balance",
        font=dict(size=12, color=MUTED),
        standoff=FITNESS_FRESHNESS_Y_TITLE_STANDOFF,
    )
    if period_df.empty:
        fig.update_layout(title=_title(""), **CHART_LAYOUT)
        fig.update_layout(
            yaxis=dict(
                title=y_title,
                zeroline=True,
                zerolinecolor="rgba(21, 32, 40, 0.18)",
                gridcolor="rgba(21, 32, 40, 0.08)",
                automargin=False,
                fixedrange=True,
            ),
            xaxis=_fitness_xaxis([], grain),
            height=FITNESS_FRESHNESS_HEIGHT,
            margin=_fitness_freshness_margin(grain, 0),
            showlegend=False,
        )
        return fig

    labels = period_df["period_label"].tolist()
    tooltips = _period_tooltips(period_df)
    opacities = _bar_opacities(period_df)
    fitness = period_df["fitness"] if "fitness" in period_df.columns else pd.Series(dtype=float)
    fatigue = period_df["fatigue"] if "fatigue" in period_df.columns else pd.Series(dtype=float)
    form = period_df["form"] if "form" in period_df.columns else pd.Series(dtype=float)
    loads = (
        period_df["load"]
        if "load" in period_df.columns
        else pd.Series(np.nan, index=period_df.index)
    )

    form_r, form_g, form_b = _hex_to_rgb(FORM_TSB_COLOR)
    form_fill = f"rgba({form_r}, {form_g}, {form_b}, {FORM_TSB_FILL_OPACITY})"
    # Form shade first (behind); positive above zero and negative below both fill.
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=_nan_to_none(form),
            mode="lines+markers",
            name="Form",
            legendgroup="Form",
            showlegend=False,
            line=dict(color=FORM_TSB_COLOR, width=2),
            marker=dict(color=FORM_TSB_COLOR, size=7, opacity=opacities),
            fill="tozeroy",
            fillcolor=form_fill,
            connectgaps=False,
            customdata=[[tip] for tip in tooltips],
            hovertemplate="Form: %{y:.1f}<extra></extra>",
            legendrank=3,
        )
    )

    line_specs = (
        ("Fitness", fitness, FITNESS_CTL_COLOR, 1),
        ("Fatigue", fatigue, FATIGUE_ATL_COLOR, 2),
    )
    for name, values, color, legendrank in line_specs:
        if name == "Fitness":
            customdata = [
                [tip, _efficiency_hover_number(load, ".1f")]
                for tip, load in zip(tooltips, loads, strict=True)
            ]
            hovertemplate = (
                "<b>%{customdata[0]}</b><br>"
                "Fitness: %{y:.1f}<br>"
                "Period load: %{customdata[1]}"
                "<extra></extra>"
            )
        else:
            customdata = [[tip] for tip in tooltips]
            hovertemplate = f"{name}: %{{y:.1f}}<extra></extra>"
        fig.add_trace(
            go.Scatter(
                x=labels,
                y=_nan_to_none(values),
                mode="lines+markers",
                name=name,
                legendgroup=name,
                showlegend=False,
                line=dict(color=color, width=2),
                marker=dict(color=color, size=7, opacity=opacities),
                connectgaps=False,
                customdata=customdata,
                hovertemplate=hovertemplate,
                legendrank=legendrank,
            )
        )

    for name, _values, color, legendrank in line_specs:
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="lines",
                name=name,
                legendgroup=name,
                showlegend=True,
                line=dict(color=color, width=2),
                hoverinfo="skip",
                legendrank=legendrank,
            )
        )
    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="lines",
            name="Form",
            legendgroup="Form",
            showlegend=True,
            line=dict(color=FORM_TSB_COLOR, width=2),
            hoverinfo="skip",
            legendrank=3,
        )
    )

    y_min, y_max = _fitness_freshness_axis_range(fitness, fatigue, form)
    line_tops = _race_line_y_tops(fitness, fatigue, form)
    diamond_axis = (y_min, y_max)
    y_min, y_max = _extend_y_range_for_race_diamonds(
        y_min, y_max, period_df, line_tops
    )
    fig.update_layout(
        title=_title(""),
        showlegend=True,
        legend=LEGEND_FITNESS_GUTTER,
        yaxis=dict(
            title=y_title,
            range=[y_min, y_max],
            zeroline=True,
            zerolinecolor="rgba(21, 32, 40, 0.18)",
            gridcolor="rgba(21, 32, 40, 0.08)",
            automargin=False,
            fixedrange=True,
        ),
        xaxis=_fitness_xaxis(labels, grain),
        hovermode="x unified",
        hoverlabel=_hoverlabel(),
        **{
            **CHART_LAYOUT,
            "height": FITNESS_FRESHNESS_HEIGHT,
            "margin": _fitness_freshness_margin(grain, len(labels)),
        },
    )
    _add_race_week_diamonds(
        fig,
        period_df,
        line_tops,
        y_axis_range=diamond_axis,
    )
    return fig


def mileage_heatmap_chart(
    matrix,
    y_labels: list[str],
    x_labels: list[str],
    *,
    title: str,
    grain: str,
    tooltip_matrix=None,
) -> go.Figure:
    """Build a calendar mileage heatmap using ``MILEAGE_COLORSCALE``.

    Shared by Fitness and the Training mileage expander. Cell
    colors run pale teal → ``MILEAGE_BAR`` so the matrix matches the
    Training mileage bar series (not elevation purple or traffic-light
    goal bands).

    Parameters
    ----------
    matrix : array-like
        Two-dimensional mileage values for heatmap cells.
    y_labels : list[str]
        Y-axis category labels.
    x_labels : list[str]
        X-axis category labels.
    title : str
        Chart title text.
    grain : str
        Period grain used to scale the mileage goal for ``zmax``.
    tooltip_matrix : array-like, optional
        Per-cell tooltip text aligned with ``matrix``.

    Returns
    -------
    plotly.graph_objects.Figure
        Calendar/matrix heatmap with the Training mileage palette.
    """
    fig = go.Figure()
    if matrix.size == 0 or not x_labels:
        fig.update_layout(title=_title(title), **CHART_LAYOUT)
        return fig

    z = np.asarray(matrix, dtype=float)
    goal = miles_goal(grain if grain in ("Day", "Week", "Month", "Year") else "Month")
    z_finite = z[np.isfinite(z)]
    z_max = float(z_finite.max()) if z_finite.size else goal
    z_max = max(z_max, goal * 1.15, 1.0)

    # Keep absent slots as NaN (transparent → plot_bgcolor). Keep z=0 as 0 so
    # zero-mile weeks paint the pale end of MILEAGE_COLORSCALE (not the page BG).
    heatmap_kwargs: dict = dict(
        z=z,
        x=x_labels,
        y=y_labels,
        colorscale=MILEAGE_COLORSCALE,
        zmin=0.0,
        zmax=z_max,
        hoverongaps=False,
        connectgaps=False,
        xgap=1,
        ygap=1,
        showscale=True,
        colorbar=dict(
            title=dict(text="Miles", side="right"),
            tickfont=dict(size=10, color=MUTED),
        ),
    )
    if tooltip_matrix is not None:
        heatmap_kwargs["customdata"] = np.asarray(tooltip_matrix, dtype=object)
        heatmap_kwargs["hovertemplate"] = "<b>%{customdata}</b><br>%{z:.1f} miles<extra></extra>"
    else:
        heatmap_kwargs["hovertemplate"] = "<b>%{y} · %{x}</b><br>%{z:.1f} miles<extra></extra>"

    fig.add_trace(go.Heatmap(**heatmap_kwargs))
    x_tickangle = -40 if len(x_labels) > 10 else 0
    yaxis = {
        **_heatmap_axis(y_labels),
        "autorange": "reversed",
    }
    if grain == "Year":
        yaxis["showticklabels"] = False
    heatmap_margin = _heatmap_margin(x_tickangle=x_tickangle)
    row_height = 28
    layout_kwargs = {
        k: v
        for k, v in CHART_LAYOUT.items()
        if k not in ("margin", "height", "plot_bgcolor", "paper_bgcolor")
    }
    fig.update_layout(
        title=_title(title),
        xaxis=_heatmap_axis(x_labels, tickangle=x_tickangle, side="top"),
        yaxis=yaxis,
        margin=heatmap_margin,
        height=max(
            240,
            row_height * len(y_labels)
            + heatmap_margin["t"]
            + heatmap_margin["b"]
            + 24,
        ),
        # Transparent paper/plot so the Training expander (and Insights page)
        # show .stApp through — solid BG looked cooler/darker on the page wash.
        # NaN/gap cells stay see-through (not SURFACE/white/black strokes).
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        hoverlabel=_hoverlabel(),
        **layout_kwargs,
    )
    return fig


RACE_TYPE_COLORS: dict[str, str] = {
    "5k": "#3A9D8F",
    "5M": "#4C78A8",
    "10k": "#7A6FA8",
    "Half": "#E3C677",
    "Marathon": "#C85C5C",
    "Other": "#9AA5AD",
}

# Stars extend past the circle bounding box at the same `size`; use a larger
# value so tips render fully and visually match size-9 circles.
PR_STAR_SIZE = 10
PR_LEGEND_STAR_SIZE = 9
PR_LEGEND_STAR_LINE_WIDTH = 1
PR_Y_PAD = 6.0
PR_PACE_Y_PAD = 0.5
# Selected race from Race History: larger marker + ink ring on top of type color.
RACE_HIGHLIGHT_SIZE = 16
RACE_HIGHLIGHT_PR_SIZE = 18
RACE_HIGHLIGHT_RING_WIDTH = 2.5
RACE_DIM_OPACITY = 0.32
RACE_DEFAULT_OPACITY = 0.92

RaceChartMetric = Literal["time", "pace"]


def _race_time_axis_ticks(min_minutes: float, max_minutes: float) -> tuple[list[float], list[str]]:
    """Build y-axis tick positions and h:mm labels for race finish times."""
    if min_minutes >= max_minutes:
        max_minutes = min_minutes + 30.0
    span = max_minutes - min_minutes
    if span <= 45:
        step = 5.0
    elif span <= 120:
        step = 10.0
    elif span <= 240:
        step = 15.0
    else:
        step = 30.0
    start = max(0.0, (min_minutes // step) * step)
    ticks: list[float] = []
    value = start
    while value <= max_minutes + step * 0.5:
        ticks.append(value)
        value += step
    labels = []
    for minutes in ticks:
        total_seconds = int(round(minutes * 60))
        hours, rem = divmod(total_seconds, 3600)
        mins, _secs = divmod(rem, 60)
        labels.append(f"{hours}:{mins:02d}" if hours > 0 else f"0:{mins:02d}")
    return ticks, labels


def _race_pace_axis_ticks(min_pace: float, max_pace: float) -> tuple[list[float], list[str]]:
    """Build y-axis tick positions and m:ss labels for pace in min/mile."""
    if min_pace >= max_pace:
        max_pace = min_pace + 1.0
    span = max_pace - min_pace
    if span <= 2.0:
        step = 0.25
    elif span <= 5.0:
        step = 0.5
    else:
        step = 1.0
    start = max(0.0, (min_pace // step) * step)
    ticks: list[float] = []
    value = start
    while value <= max_pace + step * 0.5:
        ticks.append(value)
        value += step
    labels = []
    for pace in ticks:
        total_seconds = int(round(pace * 60))
        mins, secs = divmod(total_seconds, 60)
        labels.append(f"{mins}:{secs:02d}")
    return ticks, labels


def _format_race_distance(miles: object) -> str:
    if miles is None or (isinstance(miles, float) and pd.isna(miles)):
        return "—"
    return f"{float(miles):.2f} mi"


def _race_hover_row(row: pd.Series, race_type: str) -> tuple[str, str, str, str, str, str]:
    return (
        format_full_date(row["date"]),
        row.get("name", ""),
        row.get("elapsed_time_min", ""),
        race_type,
        _format_race_distance(row.get("distance_miles")),
        row.get("elapsed_pace", "—") or "—",
    )


_RACE_HOVER_TEMPLATE = (
    "<b>%{customdata[0]}</b><br>"
    "%{customdata[1]}<br>"
    "Time: %{customdata[2]}<br>"
    "Distance: %{customdata[4]}<br>"
    "Pace: %{customdata[5]}<br>"
    "Type: %{customdata[3]}<extra></extra>"
)
_RACE_PR_HOVER_TEMPLATE = (
    "<b>%{customdata[0]}</b><br>"
    "%{customdata[1]}<br>"
    "Time: %{customdata[2]}<br>"
    "Distance: %{customdata[4]}<br>"
    "Pace: %{customdata[5]}<br>"
    "Type: %{customdata[3]}<br>"
    "PR<extra></extra>"
)


def race_results_scatter(
    races: pd.DataFrame,
    *,
    metric: RaceChartMetric = "time",
    highlight_activity_id: str | int | None = None,
) -> go.Figure:
    """Build a race finish-time or pace scatter chart over time.

    Parameters
    ----------
    races : pandas.DataFrame
        Filtered race dataframe with date, type, and metric columns.
    metric : {"time", "pace"}, optional
        Y-axis metric selection. Defaults to ``"time"``.
    highlight_activity_id : str or int or None, optional
        When set, emphasize the matching race marker (larger size + ink ring)
        and dim the other points.

    Returns
    -------
    plotly.graph_objects.Figure
        Scatter plot colored by race type with PR star markers.
    """
    if metric == "pace":
        title = "Pace"
        y_col = "pace_min"
        y_title = "Pace (min/mi)"
        y_pad_floor = 0.25
        y_pad_extra = PR_PACE_Y_PAD
        tick_fn = _race_pace_axis_ticks
    else:
        title = "Finish Times"
        y_col = "elapsed_min"
        y_title = "Race time (h:mm)"
        y_pad_floor = 5.0
        y_pad_extra = PR_Y_PAD
        tick_fn = _race_time_axis_ticks

    fig = go.Figure()
    if races.empty:
        fig.update_layout(
            title=_title(title),
            **{
                **CHART_LAYOUT,
                "height": RACE_RESULTS_HEIGHT,
                "margin": RACE_RESULTS_MARGIN,
            },
        )
        return fig

    if metric == "pace":
        races = ensure_race_pace_min(races)

    work = races.dropna(subset=[y_col]).copy()
    if work.empty:
        fig.update_layout(
            title=_title(title),
            **{
                **CHART_LAYOUT,
                "height": RACE_RESULTS_HEIGHT,
                "margin": RACE_RESULTS_MARGIN,
            },
        )
        return fig

    highlight_key = (
        None if highlight_activity_id is None else str(highlight_activity_id)
    )
    if "activity_id" in work.columns:
        work["_activity_key"] = work["activity_id"].astype(str)
    else:
        work["_activity_key"] = ""
    has_highlight = bool(
        highlight_key and (work["_activity_key"] == highlight_key).any()
    )
    marker_opacity = RACE_DIM_OPACITY if has_highlight else RACE_DEFAULT_OPACITY

    y_min = float(work[y_col].min())
    y_max = float(work[y_col].max())
    y_pad = max((y_max - y_min) * 0.12, y_pad_floor)
    y_range = [max(0.0, y_min - y_pad - y_pad_extra), y_max + y_pad]
    tickvals, ticktext = tick_fn(y_range[0], y_range[1])

    for race_type in RACE_TYPE_ORDER:
        subset = work.loc[(work["race_type"] == race_type) & (~work["is_pr"])]
        if subset.empty:
            continue
        hover = [_race_hover_row(row, race_type) for _, row in subset.iterrows()]
        fig.add_trace(
            go.Scatter(
                x=subset["date"],
                y=subset[y_col],
                mode="markers",
                name=race_type,
                marker=dict(
                    color=RACE_TYPE_COLORS.get(race_type, MUTED),
                    size=9,
                    line=dict(width=0),
                    opacity=marker_opacity,
                ),
                customdata=hover,
                hovertemplate=_RACE_HOVER_TEMPLATE,
            )
        )

    pr_rows = work.loc[work["is_pr"]]
    if not pr_rows.empty:
        pr_hover = [
            _race_hover_row(row, row.get("race_type", "")) for _, row in pr_rows.iterrows()
        ]
        pr_colors = [
            RACE_TYPE_COLORS.get(race_type, MUTED)
            for race_type in pr_rows["race_type"]
        ]
        fig.add_trace(
            go.Scatter(
                x=pr_rows["date"],
                y=pr_rows[y_col],
                mode="markers",
                name="PR",
                marker=dict(
                    symbol="star",
                    size=PR_STAR_SIZE,
                    color=pr_colors,
                    line=dict(width=0),
                    opacity=marker_opacity,
                ),
                customdata=pr_hover,
                hovertemplate=_RACE_PR_HOVER_TEMPLATE,
                showlegend=False,
            )
        )
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                name="PR",
                marker=dict(
                    symbol="star",
                    size=PR_LEGEND_STAR_SIZE,
                    color="white",
                    line=dict(width=PR_LEGEND_STAR_LINE_WIDTH, color="black"),
                ),
                showlegend=True,
                hoverinfo="skip",
            )
        )

    if has_highlight:
        hit = work.loc[work["_activity_key"] == highlight_key].iloc[0]
        race_type = str(hit.get("race_type", "") or "")
        is_pr = bool(hit.get("is_pr", False))
        color = RACE_TYPE_COLORS.get(race_type, MUTED)
        fig.add_trace(
            go.Scatter(
                x=[hit["date"]],
                y=[hit[y_col]],
                mode="markers",
                name="Selected",
                marker=dict(
                    symbol="star" if is_pr else "circle",
                    size=RACE_HIGHLIGHT_PR_SIZE if is_pr else RACE_HIGHLIGHT_SIZE,
                    color=color,
                    line=dict(width=RACE_HIGHLIGHT_RING_WIDTH, color=INK),
                    opacity=1.0,
                ),
                customdata=[_race_hover_row(hit, race_type)],
                hovertemplate=(
                    _RACE_PR_HOVER_TEMPLATE if is_pr else _RACE_HOVER_TEMPLATE
                ),
                showlegend=False,
            )
        )

    x_min = work["date"].min()
    x_max = work["date"].max()
    fig.update_layout(
        title=_title(title),
        legend={**LEGEND_OUTSIDE_RIGHT, "itemsizing": "trace"},
        hoverlabel=_hoverlabel(),
        xaxis=dict(
            title=dict(text="Date", font=dict(size=12, color=MUTED)),
            tickformat="%Y",
            dtick="M12",
            tickfont=dict(size=11, color=MUTED),
            showgrid=True,
            gridcolor="rgba(21, 32, 40, 0.08)",
            range=[x_min - pd.Timedelta(days=120), x_max + pd.Timedelta(days=120)],
        ),
        yaxis=dict(
            title=dict(
                text=y_title,
                font=dict(size=12, color=MUTED),
                standoff=18,
            ),
            tickmode="array",
            tickvals=tickvals,
            ticktext=ticktext,
            range=y_range,
            gridcolor="rgba(21, 32, 40, 0.08)",
            zeroline=False,
        ),
        **{
            **CHART_LAYOUT,
            "height": RACE_RESULTS_HEIGHT,
            "margin": RACE_RESULTS_MARGIN,
        },
    )
    return fig
