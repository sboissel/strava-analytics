"""Training Overview page."""

from __future__ import annotations

import streamlit as st

import _bootstrap  # noqa: F401

from charts import PLOTLY_CONFIG, compliance_chart, mileage_chart
from data import (
    PERIOD_CONFIG,
    PeriodGrain,
    aggregate_period_metrics,
    latest_activity_label,
    load_runs,
)
from ui import render_sidebar_section_nav

st.markdown(
    """
    <div class="panel-title">Training Overview</div>
    <div class="panel-summary">80:20 compliance and mileage trends.</div>
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

st.markdown('<div id="chart-compliance" class="page-anchor"></div>', unsafe_allow_html=True)
st.plotly_chart(
    compliance_chart(period_metrics, grain),
    use_container_width=True,
    config=PLOTLY_CONFIG,
)
st.markdown('<div id="chart-mileage" class="page-anchor"></div>', unsafe_allow_html=True)
st.plotly_chart(
    mileage_chart(period_metrics, grain),
    use_container_width=True,
    config=PLOTLY_CONFIG,
)
