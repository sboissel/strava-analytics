"""Training page."""

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
    compliance_chart,
    compliance_title,
    elevation_chart,
    hr_zones_stacked_area_chart,
    mileage_chart,
    mileage_heatmap_chart,
    race_weeks_chart,
)
from data import (
    PERIOD_CONFIG,
    PeriodGrain,
    aggregate_period_metrics,
    annotate_race_periods,
    attach_plan_targets_to_periods,
    latest_activity_label,
    load_runs,
    load_training_plans,
    period_showing_label,
    plan_targets_by_period,
    plan_targets_overlap_periods,
    training_plans_max_end,
)
from insights_data import (
    aggregate_hr_zones_by_period,
    mileage_heatmap_matrix,
    week_to_date_hr_zone_shares,
)
from race_data import load_race_results
from ui import (
    compliance_info_html,
    hr_zones_week_to_date_pie_html,
    race_weeks_legend_html,
    render_period_range_inputs,
    render_sidebar_section_nav,
    render_training_plan_zoom_select,
    render_training_plans,
)


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


def _with_plan_targets(period_metrics, plans, runs, *, grain: str, today: pd.Timestamp):
    """Attach plan miles/elevation when Show By periods overlap any loaded plan.

    Week uses plan week totals; Day / Month / Year sum dated plan sessions
    into each period (see ``plan_targets_by_period``).
    """
    if not plans:
        return period_metrics
    comparison = plan_targets_by_period(plans, grain, runs, as_of=today)
    if not plan_targets_overlap_periods(comparison, period_metrics):
        return period_metrics
    return attach_plan_targets_to_periods(period_metrics, comparison)


st.markdown(
    """
    <div class="panel-title">Training</div>
    <div class="panel-summary">80:20 compliance, mileage, elevation, and heart-rate zones.</div>
    """,
    unsafe_allow_html=True,
)

plans = load_training_plans()
runs = load_runs()
today = pd.Timestamp.now(tz="UTC")
as_of = runs["date"].max() if not runs.empty else today
# Allow End past latest activity so plan-vs-actual can show future plan weeks.
plan_max_end = training_plans_max_end(plans)

st.markdown('<div id="training-plans" class="page-anchor"></div>', unsafe_allow_html=True)
render_training_plans(plans, today=today)

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
    # Zoom writes Start/End session keys before the date widgets mount.
    render_training_plan_zoom_select(
        plans, grain, as_of=as_of, page_key="training", max_end=plan_max_end
    )
    window = render_period_range_inputs(
        grain, as_of=as_of, page_key="training", max_end=plan_max_end
    )
    st.markdown(
        f"""
        <div class="controls-meta">
          <div class="controls-meta-divider" aria-hidden="true"></div>
          <div class="meta-line">
            <span class="meta-key">Showing</span>
            <span class="meta-val">{period_showing_label(grain, start=window.start, end=window.end)}</span>
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

period_metrics = aggregate_period_metrics(
    runs, grain, as_of=as_of, start=window.start, end=window.end
)
period_metrics = annotate_race_periods(period_metrics, load_race_results(), grain)
period_metrics = _with_plan_targets(
    period_metrics, plans, runs, grain=grain, today=today
)
zone_periods = aggregate_hr_zones_by_period(
    runs, grain, as_of=as_of, start=window.start, end=window.end
)
week_to_date_zones = week_to_date_hr_zone_shares(runs, as_of=as_of)

st.markdown('<div id="chart-race-weeks" class="page-anchor"></div>', unsafe_allow_html=True)
_race_week_strip(period_metrics, grain)
st.markdown('<div id="chart-compliance" class="page-anchor"></div>', unsafe_allow_html=True)
# Title + inline ⓘ outside the zero-height page-anchor so Streamlit does not clip them.
st.markdown(
    compliance_info_html(compliance_title(grain)),
    unsafe_allow_html=True,
)
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
# Insights-style calendar heatmap under the weekly mileage bars.
with st.expander(
    "Mileage heatmap",
    expanded=False,
    type="compact",
    key="training_mileage_heatmap",
):
    matrix, y_labels, x_labels, heatmap_title_text, tooltip_matrix = (
        mileage_heatmap_matrix(
            runs, grain, as_of=as_of, start=window.start, end=window.end
        )
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
        key="training_mileage_heatmap_chart",
    )
st.markdown('<div id="chart-elevation" class="page-anchor"></div>', unsafe_allow_html=True)
st.plotly_chart(
    elevation_chart(period_metrics, grain),
    use_container_width=True,
    config=PLOTLY_CONFIG,
    key="training_elevation",
)
# HR zone stack last — week-to-date donut in the shared right gutter under Zone legend.
st.markdown('<div id="chart-hr-zones" class="page-anchor"></div>', unsafe_allow_html=True)
st.markdown(
    hr_zones_week_to_date_pie_html(week_to_date_zones),
    unsafe_allow_html=True,
)
st.plotly_chart(
    hr_zones_stacked_area_chart(zone_periods, grain),
    use_container_width=True,
    config=PLOTLY_CONFIG,
    key="training_hr_zones",
)
