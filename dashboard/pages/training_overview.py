"""Training Overview page."""

from __future__ import annotations

import streamlit as st

import _bootstrap  # noqa: F401

from charts import PLOTLY_CONFIG, compliance_chart, mileage_chart
from data import (
    PERIOD_CONFIG,
    PeriodGrain,
    aggregate_period_metrics,
    filter_to_recent_periods,
    key_indicators,
    latest_activity_label,
    load_runs,
)
from theme import miles_color
from ui import (
    eh_color,
    eh_kpi_tooltip,
    kpi_label_html,
    miles_kpi_tooltip,
    render_sidebar_section_nav,
)

st.markdown(
    """
    <div class="panel-title">Training Overview</div>
    <div class="panel-summary">Key indicators, 80:20 compliance, and mileage trends.</div>
    """,
    unsafe_allow_html=True,
)

runs = load_runs()
left, right = st.columns([1.05, 2.35], gap="medium")

with left:
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

indicators = key_indicators(runs)
eh_week, eh_week_pct = indicators["eh_last_week"]
eh_month, eh_month_pct = indicators["eh_last_month"]
miles_week = indicators["miles_last_week"]
week_color = eh_color(eh_week_pct)
month_color = eh_color(eh_month_pct)
miles_accent = miles_color(miles_week, grain="Week")

with right:
    st.markdown(
        f"""
        <div class="panel" id="key-indicators">
          <div class="panel-label">Key Indicators</div>
          <div class="kpi-grid">
            <div class="kpi-card" style="--accent:{week_color}">
              {kpi_label_html("E:H Last Week", eh_kpi_tooltip("week"))}
              <div class="kpi-value">{eh_week}</div>
            </div>
            <div class="kpi-card" style="--accent:{month_color}">
              {kpi_label_html("E:H Last 30 Days", eh_kpi_tooltip("month"))}
              <div class="kpi-value">{eh_month}</div>
            </div>
            <div class="kpi-card" style="--accent:{miles_accent}">
              {kpi_label_html("Miles Last Week", miles_kpi_tooltip())}
              <div class="kpi-value">{miles_week:.2f}</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

period_runs = filter_to_recent_periods(runs, grain)
as_of = runs["date"].max() if not runs.empty else None
period_metrics = aggregate_period_metrics(period_runs, grain, as_of=as_of)

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
