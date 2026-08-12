"""Shared KPI and sidebar UI helpers for the Runner's Dashboard."""

from __future__ import annotations

import html

from charts import compliance_title, heatmap_title, mileage_title, pace_hr_title
from theme import (
    TRAFFIC_GREEN,
    TRAFFIC_LIME,
    TRAFFIC_ORANGE,
    TRAFFIC_RED,
    TRAFFIC_YELLOW,
    WEEKLY_MILES_GOAL,
    eh_color,
    miles_legend_labels,
)


def band_dot(color_hex: str) -> str:
    """Small colored circle for KPI tooltip band rows."""
    return f'<span class="band-dot" style="background:{color_hex}"></span>'


def eh_kpi_tooltip(period: str) -> str:
    """Tooltip body for easy:hard KPI cards."""
    period_desc = {
        "week": "the last full Mon–Sun week",
        "month": "the last 30 days",
    }[period]
    return (
        "<strong>Definition</strong>"
        f"Easy:hard time ratio from heart-rate zones for {period_desc}."
        "<br><br>"
        "<strong>Target</strong>"
        "~80% easy (80:20)"
        "<br><br>"
        "<strong>Target Bands</strong>"
        f"{band_dot(TRAFFIC_GREEN)}≥85% easy"
        f"<br>{band_dot(TRAFFIC_LIME)}≥75%"
        f"<br>{band_dot(TRAFFIC_YELLOW)}≥65%"
        f"<br>{band_dot(TRAFFIC_ORANGE)}≥55%"
        f"<br>{band_dot(TRAFFIC_RED)}below 55%"
    )


def miles_kpi_tooltip() -> str:
    """Tooltip body for weekly mileage KPI card."""
    band_lines = "<br>".join(
        f"{band_dot(color)}{html.escape(label)}"
        for color, label in reversed(miles_legend_labels("Week"))
    )
    return (
        "<strong>Definition</strong>"
        "Total run mileage for the last full Mon–Sun week."
        "<br><br>"
        "<strong>Target</strong>"
        f"~{WEEKLY_MILES_GOAL:.0f} mi/week."
        "<br><br>"
        "<strong>Target Bands</strong>"
        f"{band_lines}"
    )


def kpi_label_html(label: str, tooltip: str) -> str:
    """Render a KPI label with a muted info icon and hover tooltip."""
    safe_label = html.escape(label)
    return (
        f'<div class="kpi-label">'
        f"<span>{safe_label}</span>"
        f'<span class="kpi-info" tabindex="0" role="button" '
        f'aria-label="About {safe_label}">'
        f'<span aria-hidden="true">ⓘ</span>'
        f'<span class="kpi-tooltip" role="tooltip">{tooltip}</span>'
        f"</span></div>"
    )


def render_section_nav(sections: list[tuple[str, str]], *, aria_label: str) -> None:
    """Render in-page section links in the sidebar."""
    import streamlit as st

    links = "".join(
        f'<a href="#{anchor}">{html.escape(label)}</a>'
        for anchor, label in sections
    )
    nav_html = f"""
<div class="sidebar-section-nav">
  <div class="sidebar-section-nav-label">On this page</div>
  <nav class="sidebar-section-nav-links" aria-label="{html.escape(aria_label)}">
    {links}
  </nav>
</div>
"""
    with st.sidebar:
        st.markdown(nav_html, unsafe_allow_html=True)


def render_insights_section_nav(
    hr_grain: str, heatmap_grain: str, pace_label: str
) -> None:
    """In-page section links for Training Insights."""
    render_section_nav(
        [
            ("chart-pace-hr", pace_hr_title(hr_grain, pace_label)),
            ("chart-mileage-heatmap", heatmap_title(heatmap_grain)),
        ],
        aria_label="Training Insights sections",
    )


def render_sidebar_section_nav(grain: str) -> None:
    """In-page section links for Training Overview."""
    render_section_nav(
        [
            ("key-indicators", "Key Indicators"),
            ("chart-compliance", compliance_title(grain)),
            ("chart-mileage", mileage_title(grain)),
        ],
        aria_label="Training Overview sections",
    )


def render_race_section_nav() -> None:
    """In-page section links for Race Results."""
    render_section_nav(
        [
            ("chart-race-results", "Finish Times"),
            ("race-results-table", "Race History"),
        ],
        aria_label="Race Results sections",
    )
