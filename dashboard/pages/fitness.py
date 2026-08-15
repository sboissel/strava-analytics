"""Fitness page."""

from __future__ import annotations

import streamlit as st

import _bootstrap  # noqa: F401

from charts import (
    PLOTLY_CONFIG,
    aerobic_efficiency_line_chart,
    aerobic_efficiency_title,
    hr_zones_stacked_area_chart,
    pace_hr_line_chart,
)
from data import PERIOD_CONFIG, PeriodGrain, latest_activity_label, load_runs
from insights_data import (
    aggregate_aerobic_efficiency_by_period,
    aggregate_hr_zones_by_period,
    aggregate_pace_hr_by_period,
    last_full_week_hr_zone_shares,
    load_pace_runs,
)
from pace_bins import DEFAULT_PACE_BIN_KEY, PACE_BIN_OPTIONS
from ui import (
    aerobic_efficiency_info_html,
    hr_zones_last_week_pie_html,
    render_insights_section_nav,
)

runs = load_runs()
pace_runs = load_pace_runs()
pace_labels = [label for label, _ in PACE_BIN_OPTIONS]
pace_keys = [key for _, key in PACE_BIN_OPTIONS]
default_idx = pace_keys.index(DEFAULT_PACE_BIN_KEY)

st.markdown(
    """
    <div class="panel-title">Fitness</div>
    <div class="panel-summary">Pace-bin heart rate trends, time in HR zones, and elevation-adjusted aerobic efficiency.</div>
    """,
    unsafe_allow_html=True,
)

panel_col, _ = st.columns([1.5, 1.5], gap="medium")

with panel_col:
    st.markdown(
        """
        <div class="controls-panel controls-panel--compact insights-controls-panel" aria-hidden="true"></div>
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
            '<div class="controls-select-narrow fitness-pace-bins-anchor" aria-hidden="true"></div>',
            unsafe_allow_html=True,
        )
        default_label = pace_labels[default_idx]
        selected_labels = st.multiselect(
            "Pace Range",
            options=pace_labels,
            default=[default_label],
            label_visibility="collapsed",
            key="insights_pace_bins",
        )
        selected_set = set(selected_labels)
        ordered_bins = [
            (label, key)
            for label, key in PACE_BIN_OPTIONS
            if label in selected_set
        ]
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

render_insights_section_nav(grain, [label for label, _ in ordered_bins])

as_of = runs["date"].max() if not runs.empty else None
hr_series = [
    (label, aggregate_pace_hr_by_period(pace_runs, grain, key, as_of=as_of))
    for label, key in ordered_bins
]
zone_periods = aggregate_hr_zones_by_period(runs, grain, as_of=as_of)
efficiency_periods = aggregate_aerobic_efficiency_by_period(runs, grain, as_of=as_of)
last_week_zones = last_full_week_hr_zone_shares(runs, as_of=as_of)

st.markdown(
    '<div id="chart-pace-hr" class="page-anchor insights-chart"></div>',
    unsafe_allow_html=True,
)
st.plotly_chart(
    pace_hr_line_chart(hr_series, grain),
    use_container_width=True,
    config=PLOTLY_CONFIG,
)

st.markdown(
    '<div id="chart-aerobic-efficiency" class="page-anchor insights-chart"></div>',
    unsafe_allow_html=True,
)
# Title + right-gutter ⓘ tooltip outside the zero-height page-anchor so
# Streamlit does not clip them.
st.markdown(
    aerobic_efficiency_info_html(aerobic_efficiency_title(grain)),
    unsafe_allow_html=True,
)
st.plotly_chart(
    aerobic_efficiency_line_chart(efficiency_periods, grain),
    use_container_width=True,
    config=PLOTLY_CONFIG,
)

st.markdown(
    '<div id="chart-hr-zones" class="page-anchor insights-chart"></div>',
    unsafe_allow_html=True,
)
# Last-week donut in the shared right gutter under the Zone legend (not a
# full-width chart below the stack). Overlay sits beside the Plotly figure.
st.markdown(
    hr_zones_last_week_pie_html(last_week_zones),
    unsafe_allow_html=True,
)
st.plotly_chart(
    hr_zones_stacked_area_chart(zone_periods, grain),
    use_container_width=True,
    config=PLOTLY_CONFIG,
)
