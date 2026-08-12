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

from data import format_full_date
from race_data import RACE_TYPE_ORDER
from theme import (
    CHART_TITLE_FONT_WEIGHT,
    CHART_TITLE_SIZE_PX,
    EASY,
    EASY_TARGET_FRAC,
    FONT_BODY,
    HARD,
    INK,
    MUTED,
    SURFACE,
    TARGET,
    TRAFFIC_GREEN,
    TRAFFIC_ORANGE,
    miles_color,
    miles_goal,
    miles_legend_labels,
)

IN_PROGRESS_OPACITY = 0.5
PLOTLY_CONFIG = {"displayModeBar": False}


def _plotly_font_family() -> str:
    return FONT_BODY.replace('"', "")


# Bottom margin: angled period labels. Right margin: vertical legend outside plot.
CHART_LAYOUT = dict(
    font=dict(family=_plotly_font_family(), color=INK, size=13),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=48, r=168, t=52, b=72),
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


def compliance_title(grain: str) -> str:
    return {
        "Day": "Daily 80:20 Compliance",
        "Week": "Weekly 80:20 Compliance",
        "Month": "Monthly 80:20 Compliance",
        "Year": "Yearly 80:20 Compliance",
    }.get(grain, "80:20 Compliance")


def mileage_title(grain: str) -> str:
    return {
        "Day": "Daily Mileage",
        "Week": "Weekly Mileage",
        "Month": "Monthly Mileage",
        "Year": "Yearly Mileage",
    }.get(grain, "Mileage")


def _period_xaxis(labels: list[str], grain: str) -> dict:
    """X-axis with an explicit tick for every period (no auto-thinning)."""
    tickfont_size = 9 if grain == "Day" and len(labels) > 14 else 11
    return dict(
        title="",
        tickmode="array",
        tickvals=labels,
        ticktext=labels,
        tickangle=-40,
        tickfont=dict(size=tickfont_size, color=MUTED),
        showticklabels=True,
        showgrid=False,
    )


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
        return dict(l=48, r=168, t=52, b=96)
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
    """Per-bar opacity: dim the in-progress calendar period."""
    if "in_progress" not in period_df.columns:
        return [base] * len(period_df)
    return [
        base * IN_PROGRESS_OPACITY if bool(in_prog) else base
        for in_prog in period_df["in_progress"]
    ]


def _format_miles_goal(goal: float) -> str:
    """Clean goal label: integer when whole, otherwise one decimal."""
    if abs(goal - round(goal)) < 1e-9:
        return str(int(round(goal)))
    return f"{goal:.1f}"


def compliance_chart(period_df: pd.DataFrame, grain: str) -> go.Figure:
    """100% stacked easy vs hard mileage share with an 80% target line."""
    title = compliance_title(grain)
    fig = go.Figure()
    if period_df.empty:
        fig.update_layout(title=_title(title), **CHART_LAYOUT)
        return fig

    labels = period_df["period_label"].tolist()
    tooltips = _period_tooltips(period_df)
    opacities = _bar_opacities(period_df)
    fig.add_trace(
        go.Bar(
            name="Easy",
            x=labels,
            y=period_df["easy_frac"],
            # Leave cornerradius unset on Easy (square join). Explicit 0 would be the
            # first stack radius Plotly applies and would flatten the whole column.
            marker=dict(color=EASY, line=dict(width=0, color=EASY), opacity=opacities),
            customdata=tooltips,
            hovertemplate="<b>%{customdata}</b><br>Easy: %{y:.0%}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            name="Moderate/Hard",
            x=labels,
            y=period_df["hard_frac"],
            # First set cornerradius in the stack → rounds outer column tops (~mileage).
            marker=dict(
                color=HARD,
                line=dict(width=0, color=HARD),
                cornerradius=5,
                opacity=opacities,
            ),
            customdata=tooltips,
            hovertemplate="<b>%{customdata}</b><br>Moderate/Hard: %{y:.0%}<extra></extra>",
        )
    )
    fig.add_hline(
        y=EASY_TARGET_FRAC,
        line_width=1,
        line_color=TARGET,
        annotation_text="Goal: 80% easy",
        annotation_font=dict(size=12, color=MUTED),
        annotation_position="top left",
        annotation_bgcolor="rgba(255,255,255,0.35)",
    )
    fig.update_layout(
        title=_title(title),
        barmode="stack",
        legend=LEGEND_OUTSIDE_RIGHT,
        yaxis=dict(
            title=dict(text="Fraction of mileage", font=dict(size=12, color=MUTED)),
            range=[0, 1.08],
            tickformat=".1f",
            gridcolor="rgba(21,32,40,0.08)",
            zeroline=False,
        ),
        xaxis=_period_xaxis(labels, grain),
        bargap=0.28,
        hoverlabel=_hoverlabel(),
        **{**CHART_LAYOUT, "margin": _chart_margin(grain, len(labels))},
    )
    return fig


def mileage_chart(period_df: pd.DataFrame, grain: str) -> go.Figure:
    """Total miles by period, colored by goal bands, with a scaled goal line."""
    title = mileage_title(grain)
    fig = go.Figure()
    if period_df.empty:
        fig.update_layout(title=_title(title), **CHART_LAYOUT)
        return fig

    labels = period_df["period_label"].tolist()
    tooltips = _period_tooltips(period_df)
    totals = period_df["total_miles"].tolist()
    bar_colors = [miles_color(float(m), grain) for m in totals]
    goal = miles_goal(grain)
    fig.add_trace(
        go.Bar(
            x=labels,
            y=totals,
            marker=dict(
                color=bar_colors,
                line=dict(width=0),
                cornerradius=5,
                opacity=_bar_opacities(period_df, base=0.92),
            ),
            customdata=tooltips,
            hovertemplate="<b>%{customdata}</b><br>%{y:.1f} miles<extra></extra>",
            showlegend=False,
        )
    )
    for color, name in miles_legend_labels(grain):
        fig.add_trace(
            go.Bar(
                x=[None],
                y=[None],
                name=name,
                marker=dict(color=color, line=dict(width=0)),
                showlegend=True,
                hoverinfo="skip",
            )
        )
    fig.add_hline(
        y=goal,
        line_width=1,
        line_color=TARGET,
        annotation_text=f"Goal: {_format_miles_goal(goal)} miles",
        annotation_font=dict(size=12, color=MUTED),
        annotation_position="top left",
        annotation_bgcolor="rgba(255,255,255,0.35)",
    )
    y_max = max(float(period_df["total_miles"].max()), goal) * 1.18
    y_max = max(y_max, 5)
    fig.update_layout(
        title=_title(title),
        yaxis=dict(
            title=dict(text="Total Miles", font=dict(size=12, color=MUTED)),
            range=[0, y_max],
            gridcolor="rgba(21,32,40,0.08)",
            zeroline=False,
        ),
        xaxis=_period_xaxis(labels, grain),
        bargap=0.28,
        legend=LEGEND_OUTSIDE_RIGHT,
        hoverlabel=_hoverlabel(),
        **{**CHART_LAYOUT, "margin": _chart_margin(grain, len(labels))},
    )
    return fig


def pace_hr_title(grain: str, pace_label: str) -> str:
    return f"Average HR for {pace_label} min/mile pace"


def heatmap_title(grain: str) -> str:
    return {
        "Day": "Daily Mileage by Month",
        "Week": "Weekly Mileage by Month",
        "Month": "Monthly Mileage by Year",
        "Year": "Yearly Mileage",
    }.get(grain, "Mileage")


def pace_hr_line_chart(period_df: pd.DataFrame, grain: str, pace_label: str) -> go.Figure:
    """Average heart rate by period for a selected pace bin."""
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
    """Mileage heatmap with goal-centered three-color scale."""
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
    "Half": "#D99A3D",
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
    """Race finish times or pace over time, colored by race type with PR star markers."""
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
