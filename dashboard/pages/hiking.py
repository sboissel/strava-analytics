"""Hiking page — controls + location map, highlights, period miles/elevation, and GAP."""

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
    elevation_chart,
    hike_gap_chart,
    hike_location_folium_map,
    mileage_chart,
)
from data import (
    HIKING_MAP_CHART_REV_KEY,
    HIKING_MAP_CLUSTERS_KEY,
    HIKING_MAP_DRILL_KEY,
    HIKING_MAP_FILTER_KEY,
    HIKING_MAP_VIEW_KEY,
    HIKING_SHOW_BY_KEY,
    PERIOD_CONFIG,
    PeriodGrain,
    aggregate_period_metrics,
    apply_hiking_map_filter,
    cluster_hike_starts,
    consume_hiking_map_click,
    hike_gap_points,
    hike_map_view,
    hikes_with_start_coords,
    hiking_kpis,
    hiking_map_chart_key,
    latest_activity_label,
    load_hikes,
    period_showing_label,
    period_window_from_activities,
    sync_hiking_show_by_for_map_filter,
)
from ui import (
    clear_hiking_map_filter,
    hiking_badges_html,
    render_hiking_section_nav,
    render_period_range_inputs,
)

st.markdown(
    """
    <div class="panel-title">Hiking</div>
    <div class="panel-summary">Highlights, hike locations, mileage and elevation by period, and grade-adjusted pace.</div>
    """,
    unsafe_allow_html=True,
)

hikes = load_hikes()
as_of = hikes["date"].max() if not hikes.empty else pd.Timestamp.now(tz="UTC")

# Apply Folium marker clicks from the previous ``st_folium`` interaction
# before badges/charts so the filter is current on this rerun.
_map_rev = int(st.session_state.get(HIKING_MAP_CHART_REV_KEY, 0) or 0)
_chart_key = hiking_map_chart_key(_map_rev)
_pending_map = st.session_state.get(_chart_key)
_pending_clusters = st.session_state.get(HIKING_MAP_CLUSTERS_KEY)
_cluster_df = None
if isinstance(_pending_clusters, dict):
    rows = _pending_clusters.get("rows")
    if isinstance(rows, list) and rows:
        _cluster_df = pd.DataFrame(rows)

_prior_filter = st.session_state.get(HIKING_MAP_FILTER_KEY)
if isinstance(_pending_map, dict) and consume_hiking_map_click(
    _pending_map,
    hikes,
    current_filter_ids=_prior_filter,
    clusters=_cluster_df if isinstance(_cluster_df, pd.DataFrame) else None,
):
    # Remount key / filter / drill updated; continue with fresh session values.
    pass

_map_rev = int(st.session_state.get(HIKING_MAP_CHART_REV_KEY, 0) or 0)
_chart_key = hiking_map_chart_key(_map_rev)
_drill_level = int(st.session_state.get(HIKING_MAP_DRILL_KEY, 0) or 0)

# Top row: Controls (left) | Map (right), matching Training's column ratio.
controls_col, map_col = st.columns([1.05, 2.35], gap="medium")

# Resolve map filter before chart windows so period axes can auto-fit.
map_filter_ids = st.session_state.get(HIKING_MAP_FILTER_KEY)
page_hikes = apply_hiking_map_filter(hikes, map_filter_ids)

with controls_col:
    st.markdown(
        '<div class="controls-panel controls-title">Controls</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="controls-filter-label">Show By</div>',
        unsafe_allow_html=True,
    )
    # Auto Show By from filtered date span when the map filter id set
    # changes; restore the pre-filter grain when the filter is cleared.
    # Manual grain changes while filtered stick until the next id-set change.
    sync_hiking_show_by_for_map_filter(page_hikes, map_filter_ids)
    grain: PeriodGrain = st.selectbox(
        "Show By",
        options=list(PERIOD_CONFIG.keys()),
        index=1,
        key=HIKING_SHOW_BY_KEY,
        label_visibility="collapsed",
    )
    window = render_period_range_inputs(grain, as_of=as_of, page_key="hiking")
    # While map-filtered, override Start/End for charts with the filtered
    # hike min..max (grain-aligned). Clearing the filter restores ``window``.
    if map_filter_ids is not None:
        fitted = period_window_from_activities(page_hikes, grain)
        chart_window = fitted if fitted is not None else window
    else:
        chart_window = window
    n_page = len(page_hikes)
    hike_word = "hike" if n_page == 1 else "hikes"
    if map_filter_ids is not None:
        map_filter_label = f"{n_page} {hike_word} in selected area"
    else:
        map_filter_label = f"No area selected · {n_page} {hike_word}"
    if st.button("Reset map filter", key="hiking_map_clear", use_container_width=True):
        clear_hiking_map_filter()
        st.rerun()
    st.markdown(
        f'<div class="controls-meta" style="padding-top:0.35rem">'
        f'<div class="meta-line">'
        f'<span class="meta-key">Map filter</span>'
        f'<span class="meta-val">{map_filter_label}</span>'
        f"</div></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="controls-meta">
          <div class="controls-meta-divider" aria-hidden="true"></div>
          <div class="meta-line">
            <span class="meta-key">Showing</span>
            <span class="meta-val">{period_showing_label(grain, start=chart_window.start, end=chart_window.end)}</span>
          </div>
          <div class="meta-line">
            <span class="meta-key">Latest activity</span>
            <span class="meta-val">{latest_activity_label(hikes)}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# --- Location map (fitted beside Controls) ---
geo_source = page_hikes if map_filter_ids is not None else hikes
geo_hikes = hikes_with_start_coords(geo_source)

with map_col:
    st.markdown(
        '<div class="hiking-map-panel" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div id="chart-hiking-map" class="page-anchor"></div>',
        unsafe_allow_html=True,
    )

    if geo_hikes.empty and hikes_with_start_coords(hikes).empty:
        st.info("No GPS start locations in the hike data yet — map unavailable.")
    elif geo_hikes.empty:
        st.info("No GPS start locations in the current map filter.")
    else:
        from streamlit_folium import st_folium

        clusters = cluster_hike_starts(geo_hikes, drill_level=_drill_level)
        st.session_state[HIKING_MAP_CLUSTERS_KEY] = {
            "rows": clusters.to_dict(orient="records"),
        }
        stored_view = st.session_state.get(HIKING_MAP_VIEW_KEY)
        if isinstance(stored_view, dict) and {
            "center_lat",
            "center_lon",
            "zoom",
        }.issubset(stored_view):
            view = stored_view
        else:
            view = hike_map_view(geo_hikes)
            st.session_state[HIKING_MAP_VIEW_KEY] = view

        fmap = hike_location_folium_map(
            clusters,
            center_lat=float(view["center_lat"]),
            center_lon=float(view["center_lon"]),
            zoom=float(view["zoom"]),
        )
        st.caption("Click a count bubble to zoom in and filter highlights and charts.")
        map_event = st_folium(
            fmap,
            height=420,
            use_container_width=True,
            key=_chart_key,
            returned_objects=[
                "last_object_clicked",
                "last_object_clicked_popup",
                "last_object_clicked_tooltip",
            ],
        )
        # Same-run click (widget returned before early session read existed).
        if consume_hiking_map_click(
            map_event if isinstance(map_event, dict) else None,
            hikes,
            current_filter_ids=map_filter_ids,
            clusters=clusters,
        ):
            st.rerun()

render_hiking_section_nav(grain)

st.markdown(
    hiking_badges_html(hiking_kpis(page_hikes, as_of=as_of)),
    unsafe_allow_html=True,
)

period_metrics = aggregate_period_metrics(
    page_hikes,
    grain,
    as_of=as_of,
    start=chart_window.start,
    end=chart_window.end,
)
gap_points = hike_gap_points(
    page_hikes,
    grain=grain,
    as_of=as_of,
    start=chart_window.start,
    end=chart_window.end,
)

st.markdown('<div id="chart-hiking-miles" class="page-anchor"></div>', unsafe_allow_html=True)
st.plotly_chart(
    mileage_chart(period_metrics, grain, show_goal=False),
    use_container_width=True,
    config=PLOTLY_CONFIG,
    key="hiking_miles",
)
st.markdown(
    '<div id="chart-hiking-elevation" class="page-anchor"></div>',
    unsafe_allow_html=True,
)
st.plotly_chart(
    elevation_chart(period_metrics, grain, unit="mi"),
    use_container_width=True,
    config=PLOTLY_CONFIG,
    key="hiking_elevation",
)
st.markdown('<div id="chart-hiking-gap" class="page-anchor"></div>', unsafe_allow_html=True)
st.plotly_chart(
    hike_gap_chart(gap_points),
    use_container_width=True,
    config=PLOTLY_CONFIG,
    key="hiking_gap",
)
