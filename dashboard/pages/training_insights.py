"""Training Insights page."""

from __future__ import annotations

import streamlit as st

import _bootstrap  # noqa: F401

from charts import PLOTLY_CONFIG, mileage_heatmap_chart, pace_hr_line_chart
from data import PERIOD_CONFIG, PeriodGrain, latest_activity_label, load_runs
from insights_data import (
    aggregate_pace_hr_by_period,
    load_pace_analysis,
    mileage_heatmap_matrix,
)
from pace_bins import DEFAULT_PACE_BIN_KEY, PACE_BIN_OPTIONS
from ui import render_insights_section_nav

runs = load_runs()
pace_runs = load_pace_analysis()
pace_labels = [label for label, _ in PACE_BIN_OPTIONS]
pace_keys = [key for _, key in PACE_BIN_OPTIONS]
default_idx = pace_keys.index(DEFAULT_PACE_BIN_KEY)

st.markdown(
    """
    <div class="panel-title">Training Insights</div>
    <div class="panel-summary">Pace-bin heart rate trends and mileage heatmaps.</div>
    """,
    unsafe_allow_html=True,
)

panel_col, _ = st.columns([1.5, 1.5], gap="medium")

with panel_col:
    st.markdown(
        """
        <div class="controls-panel insights-controls-panel" aria-hidden="true"></div>
        <div class="controls-title">Controls</div>
        """,
        unsafe_allow_html=True,
    )
    col_dash, col_hr = st.columns(2, gap="medium")

    with col_dash:
        st.markdown(
            '<div class="controls-section-label">Entire Dashboard</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="controls-filter-label">Show By</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="controls-select-narrow" aria-hidden="true"></div>',
            unsafe_allow_html=True,
        )
        grain: PeriodGrain = st.selectbox(
            "Show By",
            options=list(PERIOD_CONFIG.keys()),
            index=1,
            label_visibility="collapsed",
            key="insights_grain",
        )
        st.markdown(
            f"""
            <div class="controls-meta">
              <div class="controls-meta-divider" aria-hidden="true"></div>
              <div class="meta-line">
                <span class="meta-key">Latest activity</span>
                <span class="meta-val">{latest_activity_label(runs)}</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_hr:
        st.markdown(
            '<div class="controls-section-label">Average HR Chart</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="controls-filter-label">Pace Range</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="controls-select-narrow" aria-hidden="true"></div>',
            unsafe_allow_html=True,
        )
        pace_label = st.selectbox(
            "Pace Range",
            options=pace_labels,
            index=default_idx,
            label_visibility="collapsed",
            key="insights_pace_bin",
        )
        bin_key = pace_keys[pace_labels.index(pace_label)]
        st.markdown(
            f"""
            <div class="controls-meta">
              <div class="controls-meta-divider" aria-hidden="true"></div>
              <div class="meta-line">
                <span class="meta-key">Showing</span>
                <span class="meta-val">{PERIOD_CONFIG[grain]["showing"]}</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

render_insights_section_nav(grain, grain, pace_label)

as_of = runs["date"].max() if not runs.empty else None
hr_periods = aggregate_pace_hr_by_period(pace_runs, grain, bin_key, as_of=as_of)

st.markdown(
    '<div id="chart-pace-hr" class="page-anchor insights-chart"></div>',
    unsafe_allow_html=True,
)
st.plotly_chart(
    pace_hr_line_chart(hr_periods, grain, pace_label),
    use_container_width=True,
    config=PLOTLY_CONFIG,
)

matrix, y_labels, x_labels, heatmap_title_text, tooltip_matrix = mileage_heatmap_matrix(
    runs, grain, as_of=as_of
)
st.markdown(
    '<div id="chart-mileage-heatmap" class="page-anchor insights-chart"></div>',
    unsafe_allow_html=True,
)
st.plotly_chart(
    mileage_heatmap_chart(
        matrix,
        y_labels,
        x_labels,
        title=heatmap_title_text,
        grain=grain,
        tooltip_matrix=tooltip_matrix,
    ),
    use_container_width=True,
    config=PLOTLY_CONFIG,
)
