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
    """Return HTML for a small colored circle in KPI tooltips.

    Parameters
    ----------
    color_hex : str
        CSS hex color for the dot.

    Returns
    -------
    str
        HTML ``span`` element markup for the colored dot.
    """
    return f'<span class="band-dot" style="background:{color_hex}"></span>'


def eh_kpi_tooltip(period: str) -> str:
    """Return tooltip HTML for easy:hard KPI cards.

    Parameters
    ----------
    period : str
        Window identifier, either ``"week"`` or ``"month"``.

    Returns
    -------
    str
        HTML tooltip body describing the ratio definition and target bands.

    Raises
    ------
    KeyError
        If ``period`` is not ``"week"`` or ``"month"``.
    """
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
    """Return tooltip HTML for the weekly mileage KPI card.

    Returns
    -------
    str
        HTML tooltip body describing mileage definition and target bands.
    """
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
    """Render a KPI label with a muted info icon and hover tooltip.

    Parameters
    ----------
    label : str
        Visible KPI label text.
    tooltip : str
        HTML tooltip body shown on hover.

    Returns
    -------
    str
        HTML markup for the KPI label row.
    """
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
    """Render in-page section links in the Streamlit sidebar.

    Parameters
    ----------
    sections : list[tuple[str, str]]
        Pairs of anchor id and link label.
    aria_label : str
        Accessible name for the navigation landmark.

    Returns
    -------
    None
        Renders sidebar HTML via Streamlit.
    """
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
    """Render in-page section links for Training Insights.

    Parameters
    ----------
    hr_grain : str
        Period grain label for the pace-vs-HR chart title.
    heatmap_grain : str
        Period grain label for the mileage heatmap title.
    pace_label : str
        Selected pace-bin display label.

    Returns
    -------
    None
        Renders sidebar navigation links via Streamlit.
    """
    render_section_nav(
        [
            ("chart-pace-hr", pace_hr_title(hr_grain, pace_label)),
            ("chart-mileage-heatmap", heatmap_title(heatmap_grain)),
        ],
        aria_label="Training Insights sections",
    )


def render_sidebar_section_nav(grain: str) -> None:
    """Render in-page section links for Training Overview.

    Parameters
    ----------
    grain : str
        Period grain used for chart section titles.

    Returns
    -------
    None
        Renders sidebar navigation links via Streamlit.
    """
    render_section_nav(
        [
            ("key-indicators", "Key Indicators"),
            ("chart-compliance", compliance_title(grain)),
            ("chart-mileage", mileage_title(grain)),
        ],
        aria_label="Training Overview sections",
    )


def render_race_section_nav(*, chart_label: str = "Finish Times") -> None:
    """Render in-page section links for Race Results.

    Parameters
    ----------
    chart_label : str, optional
        Label for the scatter chart link. Defaults to ``"Finish Times"``.

    Returns
    -------
    None
        Renders sidebar navigation links via Streamlit.
    """
    render_section_nav(
        [
            ("chart-race-results", chart_label),
            ("race-results-table", "Race History"),
        ],
        aria_label="Race Results sections",
    )
