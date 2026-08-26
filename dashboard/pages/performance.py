"""Performance page."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Streamlit may put ``pages/`` first and/or reset ``sys.path`` after the
# entrypoint; ensure ``dashboard/`` is importable before bare module imports.
_DASHBOARD_ROOT = Path(__file__).resolve().parents[1]
if str(_DASHBOARD_ROOT) not in sys.path:
    sys.path.insert(0, str(_DASHBOARD_ROOT))

import _bootstrap  # noqa: F401

_bootstrap.ensure_sys_path()

from charts import PLOTLY_CONFIG, mileage_chart, race_results_scatter
from data import load_runs
from race_data import (
    RACE_TABLE_DISPLAY_COLUMNS,
    compare_race_type_options,
    filter_race_results,
    load_race_results,
    race_buildup_compare_rows,
    race_buildup_hr_coverage_sufficient,
    race_buildup_hr_mileage_coverage,
    race_buildup_mileage_hr_zone_shares,
    race_buildup_side_stats,
    race_buildup_training_periods,
    race_buildup_weeks,
    race_compare_choices,
    race_date_bounds,
    race_row_by_activity_id,
    race_summary_meta,
    race_table_rows,
    race_type_options,
)
from theme import INK, RACE_TABLE_FILL
from ui import (
    fastest_race_cards_html,
    race_buildup_delta_table_html,
    race_buildup_eh_values_html,
    race_buildup_hr_pies_html,
    race_buildup_row_heading_html,
    race_buildup_section_heading_html,
    race_buildup_summary_html,
    render_race_section_nav,
)

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


def _buildup_mileage_frame(
    runs: pd.DataFrame,
    race_row: pd.Series,
    *,
    weeks: int,
) -> pd.DataFrame:
    """Pre-race training weeks only (same window as build-up stats)."""
    return race_buildup_training_periods(runs, race_row, weeks)


def _shared_mileage_y_max(*frames: pd.DataFrame) -> float:
    """Shared mileage axis so side-by-side build-up charts compare fairly.

    Based on data peaks only (plus pad); the weekly goal line is hidden on
    build-up charts, so it is not forced into the axis range.
    """
    peak = 0.0
    for frame in frames:
        if frame.empty or "total_miles" not in frame.columns:
            continue
        peak = max(peak, float(frame["total_miles"].fillna(0.0).max()))
    return max(peak * 1.18, 5.0)


def _render_race_buildup(all_races: pd.DataFrame, runs: pd.DataFrame) -> None:
    """Controls + side-by-side weekly mileage compare for two races."""
    st.markdown(
        '<div id="chart-race-buildup" class="page-anchor"></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="chart-section-title">Race Build-Up Comparison</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="panel-summary performance-buildup-summary">'
        "Compare training leading into two races."
        "</div>",
        unsafe_allow_html=True,
    )

    type_options = compare_race_type_options(all_races)
    if not type_options:
        st.markdown(
            '<div class="race-results-empty">'
            "Need at least two races of the same type to compare build-up."
            "</div>",
            unsafe_allow_html=True,
        )
        return

    panel_col, _ = st.columns([2.2, 0.8], gap="medium")
    with panel_col:
        st.markdown(
            """
            <div class="controls-panel controls-panel--compact race-controls-panel race-buildup-controls" aria-hidden="true"></div>
            <div class="controls-title">Build-up Controls</div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="controls-filter-label">Race type</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="controls-select-narrow" aria-hidden="true"></div>',
            unsafe_allow_html=True,
        )
        compare_type = st.selectbox(
            "Race type",
            options=type_options,
            index=0,
            label_visibility="collapsed",
            key="race_buildup_type",
        )
        buildup_weeks = race_buildup_weeks(compare_type)
        choices = race_compare_choices(all_races, compare_type)
        activity_ids = [activity_id for _, activity_id in choices]
        label_by_id = {activity_id: label for label, activity_id in choices}

        def _format_race(activity_id: str) -> str:
            return label_by_id.get(activity_id, activity_id)

        if st.session_state.get("race_buildup_a") not in activity_ids:
            st.session_state.race_buildup_a = activity_ids[0]
        default_b = activity_ids[1] if len(activity_ids) > 1 else activity_ids[0]
        if st.session_state.get("race_buildup_b") not in activity_ids:
            st.session_state.race_buildup_b = default_b

        race_a_col, race_b_col = st.columns(2, gap="medium")
        with race_a_col:
            st.markdown(
                '<div class="controls-filter-label">Race A</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<div class="controls-select-narrow" aria-hidden="true"></div>',
                unsafe_allow_html=True,
            )
            id_a = st.selectbox(
                "Race A",
                options=activity_ids,
                format_func=_format_race,
                label_visibility="collapsed",
                key="race_buildup_a",
            )
        with race_b_col:
            st.markdown(
                '<div class="controls-filter-label">Race B</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<div class="controls-select-narrow" aria-hidden="true"></div>',
                unsafe_allow_html=True,
            )
            id_b = st.selectbox(
                "Race B",
                options=activity_ids,
                format_func=_format_race,
                label_visibility="collapsed",
                key="race_buildup_b",
            )

    if id_a == id_b:
        st.markdown(
            '<div class="race-results-empty">Pick two different races to compare.</div>',
            unsafe_allow_html=True,
        )
        return

    race_a = race_row_by_activity_id(all_races, id_a)
    race_b = race_row_by_activity_id(all_races, id_b)
    if race_a is None or race_b is None:
        st.markdown(
            '<div class="race-results-empty">Could not load the selected races.</div>',
            unsafe_allow_html=True,
        )
        return

    left = _buildup_mileage_frame(runs, race_a, weeks=buildup_weeks)
    right = _buildup_mileage_frame(runs, race_b, weeks=buildup_weeks)
    y_max = _shared_mileage_y_max(left, right)

    cov_a = race_buildup_hr_mileage_coverage(runs, race_a, buildup_weeks)
    cov_b = race_buildup_hr_mileage_coverage(runs, race_b, buildup_weeks)
    hr_ok_a = race_buildup_hr_coverage_sufficient(cov_a)
    hr_ok_b = race_buildup_hr_coverage_sufficient(cov_b)
    insufficient_a = not hr_ok_a
    insufficient_b = not hr_ok_b
    shares_a = (
        race_buildup_mileage_hr_zone_shares(runs, race_a, buildup_weeks)
        if hr_ok_a
        else None
    )
    shares_b = (
        race_buildup_mileage_hr_zone_shares(runs, race_b, buildup_weeks)
        if hr_ok_b
        else None
    )
    # Column labels are Race A / Race B (not event names) outside the stats block.
    pies_html = race_buildup_hr_pies_html(
        shares_a,
        shares_b,
        insufficient_a=insufficient_a,
        insufficient_b=insufficient_b,
    )
    stats_a = race_buildup_side_stats(runs, race_a, buildup_weeks)
    stats_b = race_buildup_side_stats(runs, race_b, buildup_weeks)

    # Stacked: stats → training heading → mileage → HR zones → % easy:hard → metrics.
    st.markdown(
        race_buildup_summary_html(
            compare_type,
            race_a,
            race_b,
            avg_pace_min_a=stats_a["avg_pace_min"],
            avg_pace_min_b=stats_b["avg_pace_min"],
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        race_buildup_section_heading_html(
            f"{buildup_weeks} week training comparison",
            subtitle="Excludes race week",
        ),
        unsafe_allow_html=True,
    )
    # Weekly mileage: title in left gutter, charts in A | mid | B columns.
    # Ratios are overridden in CSS to the shared label|A|mid|B grid tracks.
    label_col, left_col, mid_col, right_col = st.columns(
        [1.15, 2.4, 0.35, 2.4], gap=None
    )
    with label_col:
        st.markdown(
            race_buildup_row_heading_html("Weekly mileage"),
            unsafe_allow_html=True,
        )
    with left_col:
        st.plotly_chart(
            mileage_chart(
                left,
                "Week",
                title="",
                y_max=y_max,
                show_goal=False,
                relative_weeks_from_race=True,
            ),
            use_container_width=True,
            config=PLOTLY_CONFIG,
            key="race_buildup_left_mileage",
        )
    with mid_col:
        st.markdown(
            '<div class="race-buildup-mid-gutter" aria-hidden="true"></div>',
            unsafe_allow_html=True,
        )
    with right_col:
        st.plotly_chart(
            mileage_chart(
                right,
                "Week",
                title="",
                y_max=y_max,
                show_goal=False,
                relative_weeks_from_race=True,
            ),
            use_container_width=True,
            config=PLOTLY_CONFIG,
            key="race_buildup_right_mileage",
        )
    if pies_html:
        st.markdown(pies_html, unsafe_allow_html=True)
    st.markdown(
        race_buildup_eh_values_html(
            weeks=buildup_weeks,
            easy_pct_a=stats_a["easy_pct"] if hr_ok_a else None,
            easy_pct_b=stats_b["easy_pct"] if hr_ok_b else None,
            insufficient_a=insufficient_a,
            insufficient_b=insufficient_b,
        ),
        unsafe_allow_html=True,
    )
    st.markdown(
        race_buildup_delta_table_html(
            race_buildup_compare_rows(runs, race_a, race_b, buildup_weeks),
            weeks=buildup_weeks,
        ),
        unsafe_allow_html=True,
    )


all_races = load_race_results()
runs = load_runs()

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

_render_race_buildup(all_races, runs)
