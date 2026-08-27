"""Fitness page."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Load bootstrap by absolute path so a stale/wrong ``_bootstrap`` in
# ``sys.modules`` cannot win; then refresh stale ``race_data`` if needed.
_DASHBOARD_ROOT = Path(__file__).resolve().parents[1]
_bs_spec = importlib.util.spec_from_file_location(
    "_sa_dashboard_bootstrap",
    _DASHBOARD_ROOT / "_bootstrap.py",
)
assert _bs_spec is not None and _bs_spec.loader is not None
_bootstrap = importlib.util.module_from_spec(_bs_spec)
sys.modules["_sa_dashboard_bootstrap"] = _bootstrap
sys.modules["_bootstrap"] = _bootstrap
_bs_spec.loader.exec_module(_bootstrap)
_bootstrap.bootstrap()

from charts import (
    PLOTLY_CONFIG,
    aerobic_efficiency_line_chart,
    aerobic_efficiency_title,
    fitness_form_fatigue_line_chart,
    fitness_freshness_title,
    pace_hr_line_chart,
    pace_hr_title,
    pace_hr_trend_subtitle,
    race_weeks_chart,
)
from data import (
    PERIOD_CONFIG,
    PeriodGrain,
    aggregate_period_metrics,
    annotate_race_periods,
    latest_activity_label,
    load_runs,
    merge_race_period_annotations,
    period_showing_label,
)
from insights_data import (
    aggregate_aerobic_efficiency_by_period,
    aggregate_fitness_form_fatigue_by_period,
    aggregate_pace_hr_by_period,
    load_pace_runs,
)
from pace_bins import DEFAULT_PACE_BIN_KEY, PACE_BIN_OPTIONS
from race_data import load_race_results
from ui import (
    aerobic_efficiency_info_html,
    fitness_freshness_info_html,
    pace_hr_title_html,
    race_weeks_legend_html,
    render_insights_section_nav,
    render_period_range_inputs,
)


def _race_week_strip(period_metrics, grain: str) -> None:
    """Render the top in-flow race-week strip (legend + markers)."""
    with st.container(key="race_week_strip", gap=None):
        st.markdown(race_weeks_legend_html(), unsafe_allow_html=True)
        st.plotly_chart(
            race_weeks_chart(period_metrics, grain, plot="fitness"),
            use_container_width=True,
            config=PLOTLY_CONFIG,
            key="fitness_race_weeks",
        )


runs = load_runs()
pace_runs = load_pace_runs()
pace_labels = [label for label, _ in PACE_BIN_OPTIONS]
pace_keys = [key for _, key in PACE_BIN_OPTIONS]
default_idx = pace_keys.index(DEFAULT_PACE_BIN_KEY)
as_of = runs["date"].max() if not runs.empty else pd.Timestamp.now(tz="UTC")

st.markdown(
    """
    <div class="panel-title">Fitness</div>
    <div class="panel-summary">Pace-bin heart rate trends, elevation-adjusted aerobic efficiency, and Fitness &amp; Freshness.</div>
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
        window = render_period_range_inputs(grain, as_of=as_of, page_key="fitness")
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
                <span class="meta-val">{period_showing_label(grain, start=window.start, end=window.end)}</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

render_insights_section_nav(grain, [label for label, _ in ordered_bins])

period_metrics = aggregate_period_metrics(
    runs, grain, as_of=as_of, start=window.start, end=window.end
)
period_metrics = annotate_race_periods(period_metrics, load_race_results(), grain)
hr_series = [
    (
        label,
        merge_race_period_annotations(
            aggregate_pace_hr_by_period(
                pace_runs,
                grain,
                key,
                as_of=as_of,
                start=window.start,
                end=window.end,
            ),
            period_metrics,
        ),
    )
    for label, key in ordered_bins
]
freshness_periods = merge_race_period_annotations(
    aggregate_fitness_form_fatigue_by_period(
        runs, grain, as_of=as_of, start=window.start, end=window.end
    ),
    period_metrics,
)
efficiency_periods = merge_race_period_annotations(
    aggregate_aerobic_efficiency_by_period(
        runs, grain, as_of=as_of, start=window.start, end=window.end
    ),
    period_metrics,
)

st.markdown('<div id="chart-race-weeks" class="page-anchor"></div>', unsafe_allow_html=True)
_race_week_strip(period_metrics, grain)

st.markdown(
    '<div id="chart-pace-hr" class="page-anchor insights-chart"></div>',
    unsafe_allow_html=True,
)
# Title + rolling-window subtitle outside the zero-height page-anchor and
# outside Plotly so SVG margin clipping cannot cut the heading/caps.
st.markdown(
    pace_hr_title_html(
        pace_hr_title(grain, [label for label, _ in ordered_bins]),
        pace_hr_trend_subtitle(grain),
    ),
    unsafe_allow_html=True,
)
st.plotly_chart(
    pace_hr_line_chart(hr_series, grain, period_df=period_metrics),
    use_container_width=True,
    config=PLOTLY_CONFIG,
)

st.markdown(
    '<div id="chart-aerobic-efficiency" class="page-anchor insights-chart"></div>',
    unsafe_allow_html=True,
)
# Title + inline ⓘ tooltip outside the zero-height page-anchor so
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
    '<div id="chart-fitness-freshness" class="page-anchor insights-chart"></div>',
    unsafe_allow_html=True,
)
st.markdown(
    fitness_freshness_info_html(fitness_freshness_title(grain)),
    unsafe_allow_html=True,
)
st.plotly_chart(
    fitness_form_fatigue_line_chart(freshness_periods, grain),
    use_container_width=True,
    config=PLOTLY_CONFIG,
)
