"""Training page."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

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
    latest_activity_label,
    load_runs,
)
from insights_data import (
    aggregate_hr_zones_by_period,
    last_full_week_hr_zone_shares,
    mileage_heatmap_matrix,
)
from race_data import load_race_results
from ui import (
    compliance_info_html,
    hr_zones_last_week_pie_html,
    race_weeks_legend_html,
    render_sidebar_section_nav,
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


st.markdown(
    """
    <div class="panel-title">Training</div>
    <div class="panel-summary">80:20 compliance, mileage, elevation, and heart-rate zones.</div>
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
zone_periods = aggregate_hr_zones_by_period(runs, grain, as_of=as_of)
last_week_zones = last_full_week_hr_zone_shares(runs, as_of=as_of)

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
# Insights-style calendar heatmap under the solid mileage bars.
with st.expander(
    "Mileage heatmap",
    expanded=False,
    type="compact",
    key="training_mileage_heatmap",
):
    matrix, y_labels, x_labels, heatmap_title_text, tooltip_matrix = (
        mileage_heatmap_matrix(runs, grain, as_of=as_of)
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
# HR zone stack last — last-week donut in the shared right gutter under Zone legend.
st.markdown('<div id="chart-hr-zones" class="page-anchor"></div>', unsafe_allow_html=True)
st.markdown(
    hr_zones_last_week_pie_html(last_week_zones),
    unsafe_allow_html=True,
)
st.plotly_chart(
    hr_zones_stacked_area_chart(zone_periods, grain),
    use_container_width=True,
    config=PLOTLY_CONFIG,
    key="training_hr_zones",
)
