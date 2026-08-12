"""Race Results page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import _bootstrap  # noqa: F401

from charts import PLOTLY_CONFIG, race_results_scatter
from race_data import (
    filter_race_results,
    load_race_results,
    race_date_bounds,
    race_summary_meta,
    race_table_rows,
    race_type_options,
)
from ui import render_race_section_nav


def _render_race_table(table_df: pd.DataFrame) -> None:
    if table_df.empty:
        st.markdown(
            '<div class="race-results-empty">No races match the current filters.</div>',
            unsafe_allow_html=True,
        )
        return

    st.dataframe(
        table_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Name": st.column_config.TextColumn("Name"),
            "Date": st.column_config.DateColumn("Date", format="MMMM D, YYYY"),
            "Race Type": st.column_config.TextColumn("Race Type"),
            "Miles": st.column_config.NumberColumn("Miles", format="%.2f"),
            "Time": st.column_config.TextColumn("Time"),
            "Pace": st.column_config.TextColumn("Pace"),
            "PR": st.column_config.TextColumn("PR", width="small"),
        },
    )


all_races = load_race_results()

st.markdown(
    """
    <div class="panel-title">Race Results</div>
    <div class="panel-summary">Finish times, personal records, and race history at a glance.</div>
    """,
    unsafe_allow_html=True,
)

panel_col, _ = st.columns([1.35, 1.65], gap="medium")
date_min, date_max = race_date_bounds(all_races)

with panel_col:
    st.markdown(
        """
        <div class="controls-panel race-controls-panel" aria-hidden="true"></div>
        <div class="controls-title">Controls</div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="controls-filter-label">Filter by race type</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="controls-select-narrow" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    type_options = race_type_options(all_races)
    race_type = st.selectbox(
        "Filter by race type",
        options=type_options,
        index=0,
        label_visibility="collapsed",
        key="race_type_filter",
    )
    st.markdown(
        '<div class="controls-date-filter">'
        '<div class="controls-filter-label">Date range</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="race-date-inputs" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    bounds_min = date_min.date()
    bounds_max = date_max.date()
    if "race_date_start" not in st.session_state:
        if "race_date_range" in st.session_state:
            legacy_start, legacy_end = st.session_state.race_date_range
            st.session_state.race_date_start = legacy_start
            st.session_state.race_date_end = legacy_end
        else:
            st.session_state.race_date_start = bounds_min
            st.session_state.race_date_end = bounds_max

    date_disabled = all_races.empty
    start_col, end_col = st.columns(2, gap="small")
    with start_col:
        range_start = st.date_input(
            "Start date",
            min_value=bounds_min,
            max_value=bounds_max,
            format="MM/DD/YYYY",
            label_visibility="collapsed",
            disabled=date_disabled,
            key="race_date_start",
        )
    with end_col:
        range_end = st.date_input(
            "End date",
            min_value=bounds_min,
            max_value=bounds_max,
            format="MM/DD/YYYY",
            label_visibility="collapsed",
            disabled=date_disabled,
            key="race_date_end",
        )

    filter_start = min(range_start, range_end)
    filter_end = max(range_start, range_end)

    filtered = filter_race_results(
        all_races,
        race_type=race_type,
        start=pd.Timestamp(filter_start, tz="UTC"),
        end=pd.Timestamp(filter_end, tz="UTC"),
    )

    st.markdown(
        f"""
        <div class="controls-meta">
          <div class="controls-meta-divider" aria-hidden="true"></div>
          <div class="meta-line">
            <span class="meta-key">Showing</span>
            <span class="meta-val">{race_summary_meta(filtered)}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

render_race_section_nav()

st.markdown(
    '<div id="chart-race-results" class="page-anchor"></div>',
    unsafe_allow_html=True,
)
st.plotly_chart(
    race_results_scatter(filtered),
    use_container_width=True,
    config=PLOTLY_CONFIG,
)

st.markdown(
    '<div id="race-results-table" class="page-anchor"></div>',
    unsafe_allow_html=True,
)
st.markdown('<div class="race-results-table-label">Race history</div>', unsafe_allow_html=True)
_render_race_table(race_table_rows(filtered))
