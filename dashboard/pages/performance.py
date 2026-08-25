"""Performance page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import _bootstrap  # noqa: F401

from charts import PLOTLY_CONFIG, race_results_scatter
from race_data import (
    RACE_TABLE_DISPLAY_COLUMNS,
    filter_race_results,
    load_race_results,
    race_date_bounds,
    race_summary_meta,
    race_table_rows,
    race_type_options,
)
from theme import INK, RACE_TABLE_FILL
from ui import fastest_race_cards_html, render_race_section_nav

RACE_HISTORY_TABLE_KEY = "race_history_table"


def _selection_rows(state: object) -> list[int]:
    """Return selected row indices from a Streamlit dataframe selection state."""
    if state is None:
        return []
    if isinstance(state, dict):
        selection = state.get("selection") or {}
        rows = selection.get("rows") if isinstance(selection, dict) else None
    else:
        selection = getattr(state, "selection", None)
        if isinstance(selection, dict):
            rows = selection.get("rows")
        else:
            rows = getattr(selection, "rows", None) if selection is not None else None
    if not rows:
        return []
    return [int(idx) for idx in rows]


def _selected_activity_id(table_df: pd.DataFrame) -> str | None:
    """Map the Race History row selection to a stable ``activity_id``."""
    if table_df.empty or "activity_id" not in table_df.columns:
        return None
    rows = _selection_rows(st.session_state.get(RACE_HISTORY_TABLE_KEY))
    if not rows:
        return None
    idx = rows[0]
    if idx < 0 or idx >= len(table_df):
        return None
    value = table_df.iloc[idx]["activity_id"]
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


def _style_race_table(table_df: pd.DataFrame):
    """Keep body cells transparent so the page wash shows through."""
    return table_df.style.set_properties(
        **{
            "background-color": RACE_TABLE_FILL,
            "color": INK,
        }
    )


def _render_race_table(table_df: pd.DataFrame) -> None:
    if table_df.empty:
        st.markdown(
            '<div class="race-results-empty">No races match the current filters.</div>',
            unsafe_allow_html=True,
        )
        return

    st.dataframe(
        _style_race_table(table_df),
        use_container_width=True,
        hide_index=True,
        column_order=RACE_TABLE_DISPLAY_COLUMNS,
        column_config={
            "activity_id": None,
            "Name": st.column_config.TextColumn("Name"),
            "Date": st.column_config.DateColumn("Date", format="MMMM D, YYYY"),
            "Race Type": st.column_config.TextColumn("Race Type"),
            "Miles": st.column_config.NumberColumn("Miles", format="%.2f"),
            "Time": st.column_config.TextColumn("Time"),
            "Pace": st.column_config.TextColumn("Pace"),
            "PR": st.column_config.TextColumn("PR", width="small"),
        },
        key=RACE_HISTORY_TABLE_KEY,
        on_select="rerun",
        selection_mode="single-row",
    )


all_races = load_race_results()

st.markdown(
    """
    <div class="panel-title">Performance</div>
    <div class="panel-summary">Finish times, personal records, and race history at a glance.</div>
    """,
    unsafe_allow_html=True,
)

cards_html = fastest_race_cards_html(all_races)
if cards_html:
    st.markdown(cards_html, unsafe_allow_html=True)
    st.markdown(
        '<div class="performance-pr-gap" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )

panel_col, _ = st.columns([1.35, 1.65], gap="medium")
date_min, date_max = race_date_bounds(all_races)

with panel_col:
    st.markdown(
        """
        <div class="controls-panel controls-panel--compact race-controls-panel" aria-hidden="true"></div>
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
        '<div class="controls-filter-label">Chart</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="controls-select-narrow" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    chart_label = st.selectbox(
        "Chart",
        options=["Finish Times", "Pace"],
        index=0,
        label_visibility="collapsed",
        key="race_chart_metric",
    )
    chart_metric = "pace" if chart_label == "Pace" else "time"
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

render_race_section_nav(chart_label=chart_label)

table_df = race_table_rows(filtered)
selected_activity_id = _selected_activity_id(table_df)

st.markdown(
    '<div id="chart-race-results" class="page-anchor"></div>',
    unsafe_allow_html=True,
)
st.plotly_chart(
    race_results_scatter(
        filtered,
        metric=chart_metric,
        highlight_activity_id=selected_activity_id,
    ),
    use_container_width=True,
    config=PLOTLY_CONFIG,
)

st.markdown(
    '<div id="race-results-table" class="page-anchor"></div>',
    unsafe_allow_html=True,
)
st.markdown('<div class="chart-section-title">Race History</div>', unsafe_allow_html=True)
_render_race_table(table_df)
