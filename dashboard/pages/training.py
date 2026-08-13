"""Training page."""

from __future__ import annotations

import streamlit as st

import _bootstrap  # noqa: F401

from charts import (
    PLOTLY_CONFIG,
    compliance_chart,
    elevation_chart,
    mileage_chart,
    race_weeks_chart,
)
from data import (
    PERIOD_CONFIG,
    PeriodGrain,
    aggregate_period_metrics,
    annotate_race_periods,
    latest_activity_label,
    load_runs,
)
from race_data import load_race_results
from ui import race_weeks_legend_html, render_sidebar_section_nav


def _race_week_strip(period_metrics, grain: str) -> None:
    """Render the top in-flow race-week strip (legend + markers)."""
    with st.container(key="race_week_strip", gap=None):
        st.markdown(race_weeks_legend_html(), unsafe_allow_html=True)
        st.plotly_chart(
            race_weeks_chart(period_metrics, grain),
            use_container_width=True,
            config=PLOTLY_CONFIG,
            key="training_race_weeks",
        )


st.markdown(
    """
    <div class="panel-title">Training</div>
    <div class="panel-summary">80:20 compliance, mileage, and elevation trends.</div>
    """,
    unsafe_allow_html=True,
)

runs = load_runs()
controls_col, _ = st.columns([1.05, 2.35], gap="medium")

with controls_col:
    st.markdown(
        '<div class="controls-panel controls-title">Controls</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="controls-filter-label">Show By</div>',
        unsafe_allow_html=True,
    )
    grain: PeriodGrain = st.selectbox(
        "Show By",
        options=list(PERIOD_CONFIG.keys()),
        index=1,
        label_visibility="collapsed",
    )
    st.markdown(
        f"""
        <div class="controls-meta">
          <div class="controls-meta-divider" aria-hidden="true"></div>
          <div class="meta-line">
            <span class="meta-key">Showing</span>
            <span class="meta-val">{PERIOD_CONFIG[grain]["showing"]}</span>
          </div>
          <div class="meta-line">
            <span class="meta-key">Latest activity</span>
            <span class="meta-val">{latest_activity_label(runs)}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

render_sidebar_section_nav(grain)

as_of = runs["date"].max() if not runs.empty else None
period_metrics = aggregate_period_metrics(runs, grain, as_of=as_of)
period_metrics = annotate_race_periods(period_metrics, load_race_results(), grain)

st.markdown('<div id="chart-race-weeks" class="page-anchor"></div>', unsafe_allow_html=True)
_race_week_strip(period_metrics, grain)
st.markdown('<div id="chart-compliance" class="page-anchor"></div>', unsafe_allow_html=True)
st.plotly_chart(
    compliance_chart(period_metrics, grain),
    use_container_width=True,
    config=PLOTLY_CONFIG,
    key="training_compliance",
)
st.markdown('<div id="chart-mileage" class="page-anchor"></div>', unsafe_allow_html=True)
st.plotly_chart(
    mileage_chart(period_metrics, grain),
    use_container_width=True,
    config=PLOTLY_CONFIG,
    key="training_mileage",
)
st.markdown('<div id="chart-elevation" class="page-anchor"></div>', unsafe_allow_html=True)
st.plotly_chart(
    elevation_chart(period_metrics, grain),
    use_container_width=True,
    config=PLOTLY_CONFIG,
    key="training_elevation",
)
