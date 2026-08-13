"""Plotly chart builders for the Runner's Dashboard."""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd
import plotly.graph_objects as go

try:
    from . import _bootstrap  # noqa: F401
except ImportError:
    import _bootstrap  # noqa: F401

from data import format_full_date, race_marker_hover_line
from race_data import RACE_TYPE_ORDER, ensure_race_pace_min
from theme import (
    CHART_TITLE_FONT_WEIGHT,
    CHART_TITLE_SIZE_PX,
    EASY,
    EASY_TARGET_FRAC,
    FONT_BODY,
    INK,
    MUTED,
    RACE_STRIP_BG,
    SURFACE,
    TRAFFIC_GREEN,
    TRAFFIC_ORANGE,
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
# the vertical centerline of each period bar.
TRAINING_MARGIN_L = 78
TRAINING_MARGIN_R = TRAINING_PLOT_MARGIN_R_PX
TRAINING_MARGIN_T = 52
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

# Bottom margin: angled period labels. Right margin: vertical legend outside plot.
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


def _period_xaxis(labels: list[str], grain: str) -> dict:
    """X-axis with an explicit tick for every period (no auto-thinning)."""
    tickfont_size = 9 if grain == "Day" and len(labels) > 14 else 11
    return dict(
        title="",
        type="category",
        categoryorder="array",
        categoryarray=labels,
        tickmode="array",
        tickvals=labels,
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
    """Heatmap axis with an explicit tick for every label (no auto-thinning)."""
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
RACE_RESULTS_HEIGHT = 410

# Bottom margin sized for angled period labels only (no legend).
PACE_HR_MARGIN = dict(l=60, r=48, t=72, b=72, autoexpand=False)
RACE_RESULTS_MARGIN = dict(l=66, r=168, t=52, b=72, autoexpand=False)
PACE_HR_MARGIN_DENSE = dict(l=60, r=48, t=72, b=96, autoexpand=False)


def _pace_hr_margin(grain: str, label_count: int) -> dict:
    """HR line chart: no legend, tighter bottom margin before the heatmap."""
    if grain == "Day" and label_count > 14:
        return PACE_HR_MARGIN_DENSE
    return PACE_HR_MARGIN


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


def _add_race_week_diamonds(
    fig: go.Figure,
    period_df: pd.DataFrame,
    y_tops: pd.Series | list[float],
) -> None:
    """Overlay gold diamonds slightly above race-period bar tops (no dashed vlines).

    ``y_tops`` must align with ``period_df`` rows (stacked total for 80:20,
    bar height for mileage/elevation). Diamonds sit at ``bar_top + pad`` where
    ``pad = max(y_tops) * RACE_CHART_DIAMOND_Y_PAD_FRAC`` so they clear the bar
    without floating too high. Uses the same categorical x as the top race-week
    strip. Hover shows race name + type (or miles for Other); no legend entry.
    """
    if period_df.empty or "is_race_period" not in period_df.columns:
        return
    is_race = period_df["is_race_period"].fillna(False).astype(bool)
    if not bool(is_race.any()):
        return

    ys = pd.Series(y_tops, index=period_df.index, dtype=float)
    y_max = float(ys.fillna(0.0).max()) if len(ys) else 0.0
    pad = y_max * RACE_CHART_DIAMOND_Y_PAD_FRAC
    race = period_df.loc[is_race]
    labels = race["period_label"].astype(str).tolist()
    y_vals = (ys.loc[is_race].fillna(0.0).astype(float) + pad).tolist()
    hover = _race_period_hover_details(race)

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
    title = compliance_title(grain)
    fig = go.Figure()
    labels = [] if period_df.empty else period_df["period_label"].tolist()
    if period_df.empty:
        fig.update_layout(
            title=_title(title),
            xaxis=_training_xaxis(labels, grain),
            yaxis=_training_yaxis(),
            **{**CHART_LAYOUT, "margin": _training_margin(grain, 0)},
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
        title=_title(title),
        barmode="stack",
        legend=LEGEND_OUTSIDE_RIGHT,
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
        **{**CHART_LAYOUT, "margin": _training_margin(grain, len(labels))},
    )
    stack_tops = period_df["easy_frac"].fillna(0.0) + period_df["hard_frac"].fillna(0.0)
    _add_race_week_diamonds(fig, period_df, stack_tops)
    return fig


def mileage_chart(period_df: pd.DataFrame, grain: str) -> go.Figure:
    """Build a total mileage bar chart colored by magnitude.

    Bars use a sequential heatmap (pale tint → ``MILEAGE_BAR``) so
    low-mileage periods read light and high-mileage periods use the
    Training ochre series color. No colorbar: ``showscale=False``
    keeps the plot box aligned with the race-week strip, 80:20, and
    elevation charts.

    Parameters
    ----------
    period_df : pandas.DataFrame
        Aggregated period metrics from ``aggregate_period_metrics``.
    grain : str
        Period grain label used for goal scaling and axis formatting.

    Returns
    -------
    plotly.graph_objects.Figure
        Bar chart with a scaled mileage goal line and magnitude colors.
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
                color=mile_values,
                colorscale=MILEAGE_COLORSCALE,
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


def _race_strip_label_gutter() -> dict:
    """Transparent fill for the left label column (paper pixels, not plot)."""
    return dict(
        type="rect",
        xref="paper",
        yref="paper",
        xsizemode="pixel",
        xanchor=0,
        x0=0,
        x1=TRAINING_MARGIN_L,
        y0=0,
        y1=1,
        fillcolor=RACE_STRIP_BG,
        line=dict(width=0),
        layer="below",
    )


def _race_strip_compact_bg(n_labels: int) -> dict:
    """Transparent fill from the first through last category slot.

    Ends at the last marker's slot so the Training legend column (right
    margin) is not covered. Category range stays ``[-0.5, n-0.5]``.
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


def _race_strip_bg_shapes(n_labels: int) -> list[dict]:
    """Transparent strip shapes: label gutter + timeline; not full paper width."""
    shapes = [_race_strip_label_gutter()]
    if n_labels:
        shapes.append(_race_strip_compact_bg(n_labels))
    return shapes


def race_weeks_chart(period_df: pd.DataFrame, grain: str) -> go.Figure:
    """Build a compact race-period marker strip aligned to the Training x-axis.

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

    Returns
    -------
    plotly.graph_objects.Figure
        Marker strip with the same category x-axis as the charts below.
    """
    fig = go.Figure()
    labels = [] if period_df.empty else period_df["period_label"].tolist()
    strip_margin = _training_margin(
        grain,
        len(labels),
        top=RACE_STRIP_MARGIN_T,
        bottom=RACE_STRIP_MARGIN_B,
    )
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
        "barmode": "overlay",
        "bargap": TRAINING_BARGAP,
        "bargroupgap": 0,
        "shapes": _race_strip_bg_shapes(len(labels)),
    }
    yaxis = _training_yaxis(
        range=[0, 1],
        showticklabels=False,
        showgrid=False,
        ticks="",
        title=dict(text=""),
        zeroline=False,
    )
    if period_df.empty:
        fig.update_layout(
            xaxis=_training_xaxis(labels, grain, show_tick_labels=False),
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
        xaxis=_training_xaxis(labels, grain, show_tick_labels=False),
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


def pace_hr_title(grain: str, pace_label: str) -> str:
    """Return the pace-vs-HR line chart title for a pace bin label.

    Parameters
    ----------
    grain : str
        Period grain label.
    pace_label : str
        Human-readable pace-bin label.

    Returns
    -------
    str
        Chart title string for the selected pace range.
    """
    return f"Average HR for {pace_label} min/mile pace"


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


def pace_hr_line_chart(period_df: pd.DataFrame, grain: str, pace_label: str) -> go.Figure:
    """Build an average heart-rate line chart for a selected pace bin.

    Parameters
    ----------
    period_df : pandas.DataFrame
        Pace-HR period aggregates from ``aggregate_pace_hr_by_period``.
    grain : str
        Period grain label used for axis formatting.
    pace_label : str
        Human-readable pace-bin label for the chart title.

    Returns
    -------
    plotly.graph_objects.Figure
        Line chart of average heart rate by calendar period.
    """
    title = pace_hr_title(grain, pace_label)
    fig = go.Figure()
    if period_df.empty:
        fig.update_layout(title=_title(title), **CHART_LAYOUT)
        return fig

    labels = period_df["period_label"].tolist()
    tooltips = _period_tooltips(period_df)
    hr_values = period_df["avg_hr"].tolist()
    opacities = _bar_opacities(period_df)
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=hr_values,
            mode="lines+markers",
            name="Average HR",
            line=dict(color=EASY, width=2, dash="dash"),
            marker=dict(color=EASY, size=7, opacity=opacities),
            customdata=tooltips,
            hovertemplate="<b>%{customdata}</b><br>Avg HR: %{y:.0f} bpm<extra></extra>",
        )
    )
    finite = period_df["avg_hr"].dropna()
    y_min = float(finite.min()) - 5 if not finite.empty else 120.0
    y_max = float(finite.max()) + 5 if not finite.empty else 180.0
    y_min = max(y_min, 100.0)
    y_max = max(y_max, y_min + 10.0)
    fig.update_layout(
        title=_title(title),
        showlegend=False,
        yaxis=dict(
            title=dict(text="Average HR (bpm)", font=dict(size=12, color=MUTED)),
            range=[y_min, y_max],
            gridcolor="rgba(21, 32, 40, 0.08)",
            zeroline=False,
            automargin=True,
        ),
        xaxis={**_period_xaxis(labels, grain), "automargin": True},
        hoverlabel=_hoverlabel(),
        **{
            **CHART_LAYOUT,
            "height": PACE_HR_HEIGHT,
            "margin": _pace_hr_margin(grain, len(labels)),
        },
    )
    return fig


def _heatmap_colorscale(zmax: float, target: float) -> list[list[str | float]]:
    """Three-color scale: zero → goal (green) → high (orange)."""
    if zmax <= 0:
        zmax = max(target * 1.5, 1.0)
    target_frac = min(max(target / zmax, 0.08), 0.92)
    return [
        [0.0, SURFACE],
        [target_frac, TRAFFIC_GREEN],
        [1.0, TRAFFIC_ORANGE],
    ]


def mileage_heatmap_chart(
    matrix,
    y_labels: list[str],
    x_labels: list[str],
    *,
    title: str,
    grain: str,
    tooltip_matrix=None,
) -> go.Figure:
    """Build a mileage heatmap with a goal-centered three-color scale.

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
        Period grain used to scale the mileage goal for the color scale.
    tooltip_matrix : array-like, optional
        Per-cell tooltip text aligned with ``matrix``.

    Returns
    -------
    plotly.graph_objects.Figure
        Heatmap figure with goal-centered color scale.
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

    heatmap_kwargs: dict = dict(
        z=z,
        x=x_labels,
        y=y_labels,
        colorscale=_heatmap_colorscale(z_max, goal),
        zmin=0.0,
        zmax=z_max,
        hoverongaps=False,
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
        hoverlabel=_hoverlabel(),
        **{k: v for k, v in CHART_LAYOUT.items() if k not in ("margin", "height")},
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
    races: pd.DataFrame, *, metric: RaceChartMetric = "time"
) -> go.Figure:
    """Build a race finish-time or pace scatter chart over time.

    Parameters
    ----------
    races : pandas.DataFrame
        Filtered race dataframe with date, type, and metric columns.
    metric : {"time", "pace"}, optional
        Y-axis metric selection. Defaults to ``"time"``.

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
        fig.update_layout(title=_title(title), **CHART_LAYOUT)
        return fig

    if metric == "pace":
        races = ensure_race_pace_min(races)

    work = races.dropna(subset=[y_col]).copy()
    if work.empty:
        fig.update_layout(title=_title(title), **CHART_LAYOUT)
        return fig

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
                    opacity=0.92,
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
