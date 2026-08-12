"""Plotly chart builders for the Runner's Dashboard."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from theme import (
    EASY,
    EASY_TARGET_FRAC,
    FONT_BODY,
    HARD,
    INK,
    MUTED,
    TARGET,
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
    return dict(text=text, font=dict(size=18, color=INK, family=_plotly_font_family()), x=0, xanchor="left")


def _hoverlabel() -> dict:
    return dict(bgcolor="white", font_size=12, font_family=_plotly_font_family())


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


def _chart_margin(grain: str, label_count: int) -> dict:
    """Extra bottom margin when many angled day labels are shown."""
    if grain == "Day" and label_count > 14:
        return dict(l=48, r=168, t=52, b=96)
    return CHART_LAYOUT["margin"]


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
    opacities = _bar_opacities(period_df)
    fig.add_trace(
        go.Bar(
            name="Easy",
            x=labels,
            y=period_df["easy_frac"],
            # Leave cornerradius unset on Easy (square join). Explicit 0 would be the
            # first stack radius Plotly applies and would flatten the whole column.
            marker=dict(color=EASY, line=dict(width=0, color=EASY), opacity=opacities),
            hovertemplate="<b>%{x}</b><br>Easy: %{y:.0%}<extra></extra>",
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
            hovertemplate="<b>%{x}</b><br>Moderate/Hard: %{y:.0%}<extra></extra>",
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
            hovertemplate="<b>%{x}</b><br>%{y:.1f} miles<extra></extra>",
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
