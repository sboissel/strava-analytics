"""Metrics page — key indicators, achievements, and shoe mileage."""

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

from data import (
    KPI_DETAIL_OPTIONS,
    build_kpi_detail,
    key_indicators,
    kpi_comparison_badges,
    lifetime_achievements,
    load_gear,
    load_runs,
)
from ui import (
    achievements_html,
    key_indicators_html,
    metrics_inspect_anchor_html,
    render_kpi_detail_panel,
    render_metrics_section_nav,
    shoe_kpi_cards_html,
)

_INSPECT_NONE = "Select a metric…"

st.markdown(
    """
    <div class="panel-title">Metrics</div>
    <div class="panel-summary">Achievements, key indicators, and shoe mileage at a glance.</div>
    """,
    unsafe_allow_html=True,
)

render_metrics_section_nav()

runs = load_runs()
indicators = key_indicators(runs)
comparisons = kpi_comparison_badges(runs)

st.markdown(
    achievements_html(lifetime_achievements(runs)),
    unsafe_allow_html=True,
)

# One painted column: Key Indicators gauges + Inspect (widgets can't live in HTML .panel).
ki_col, = st.columns(1, gap=None)
with ki_col:
    st.markdown(
        '<div class="ki-panel" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        key_indicators_html(
            indicators,
            comparisons=comparisons,
            wrap_panel=False,
        ),
        unsafe_allow_html=True,
    )
    st.markdown(metrics_inspect_anchor_html(), unsafe_allow_html=True)
    # Expander summary is the only visible Inspect label (styled as .panel-label).
    with st.expander(
        "Inspect a KI further",
        expanded=False,
        type="compact",
        key="metrics_inspect_ki",
    ):
        select_col, _ = st.columns([0.42, 0.58])
        with select_col:
            st.markdown(
                '<div class="metrics-inspect-select" aria-hidden="true"></div>',
                unsafe_allow_html=True,
            )
            selected_label = st.selectbox(
                "Inspect a KI further",
                options=[_INSPECT_NONE, *KPI_DETAIL_OPTIONS.values()],
                index=0,
                label_visibility="collapsed",
                key="metrics_kpi_detail",
            )
        if selected_label != _INSPECT_NONE:
            selected_key = next(
                key for key, label in KPI_DETAIL_OPTIONS.items() if label == selected_label
            )
            render_kpi_detail_panel(build_kpi_detail(runs, selected_key))

st.markdown(shoe_kpi_cards_html(load_gear()), unsafe_allow_html=True)
