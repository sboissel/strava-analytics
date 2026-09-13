"""Tests for Hiking dashboard page logic and wiring."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from dashboard.charts import hike_gap_chart, hike_gap_title, hike_location_folium_map, hike_map_title
from dashboard.data import (
    activity_ids_from_hiking_map_click,
    activity_ids_from_hiking_map_popup,
    aggregate_period_metrics,
    align_to_period_start,
    apply_hiking_map_filter,
    cluster_hike_starts,
    consecutive_hike_trips,
    consume_hiking_map_click,
    grade_adjusted_pace,
    hike_cluster_cell_deg,
    hike_cluster_precision,
    hike_gap_points,
    hike_map_view,
    hikes_with_start_coords,
    hiking_kpis,
    hiking_map_chart_key,
    hiking_map_click_fingerprint,
    hiking_map_cluster_popup,
    hiking_map_view_revision,
    load_hikes,
    period_grain_for_date_span,
    period_window_from_activities,
    select_hiking_map_cluster,
    sync_hiking_show_by_for_map_filter,
)
from dashboard.ui import NAV_PAGES, clear_hiking_map_filter, hiking_badges_html, sidebar_nav_entries


def _hikes(
    dates: list[str],
    *,
    distances: list[float] | None = None,
    elev: list[float] | None = None,
    elapsed: list[float] | None = None,
    names: list[str] | None = None,
    activity_ids: list[int] | None = None,
    lats: list[float | None] | None = None,
    lngs: list[float | None] | None = None,
) -> pd.DataFrame:
    n = len(dates)
    data: dict[str, object] = {
        "date": pd.to_datetime(dates, utc=True),
        "distance_miles": distances or [5.0] * n,
        "elevation_gain_ft": elev or [1000.0] * n,
        "elapsed_min": elapsed or [120.0] * n,
        "name": names or [f"Hike {i}" for i in range(n)],
        "activity_id": activity_ids or list(range(1, n + 1)),
    }
    if lats is not None:
        data["start_lat"] = lats
    if lngs is not None:
        data["start_lng"] = lngs
    return pd.DataFrame(data)


class GradeAdjustedPaceTests(unittest.TestCase):
    """GAP = elapsed_min / (elev_ft/1000 + miles)."""

    def test_gap_formula_minutes_per_grade_mile(self):
        # 180 min, 2000 ft, 8 mi → denom = 2 + 8 = 10 → 18.0 min/grade-mi
        self.assertAlmostEqual(grade_adjusted_pace(180.0, 2000.0, 8.0), 18.0)

    def test_gap_rejects_non_positive_denominator(self):
        self.assertIsNone(grade_adjusted_pace(60.0, 0.0, 0.0))
        self.assertIsNone(grade_adjusted_pace(60.0, -500.0, 0.0))

    def test_gap_rejects_missing_inputs(self):
        self.assertIsNone(grade_adjusted_pace(None, 1000.0, 5.0))
        self.assertIsNone(grade_adjusted_pace(60.0, None, 5.0))
        self.assertIsNone(grade_adjusted_pace(60.0, 1000.0, None))


class ConsecutiveHikeTripTests(unittest.TestCase):
    """Trips are consecutive calendar days with any hike activity."""

    def test_sums_miles_across_consecutive_days(self):
        hikes = _hikes(
            [
                "2026-05-25T08:00:00Z",
                "2026-05-26T09:00:00Z",
                "2026-05-27T10:00:00Z",
                "2026-05-30T08:00:00Z",
            ],
            distances=[9.0, 3.0, 4.0, 15.0],
        )
        trips = consecutive_hike_trips(hikes)
        self.assertEqual(len(trips), 2)
        # May 25–27 trip: 16 mi; May 30 alone: 15 mi
        self.assertAlmostEqual(float(trips.loc[0, "total_miles"]), 16.0)
        self.assertEqual(int(trips.loc[0, "days"]), 3)
        self.assertAlmostEqual(float(trips.loc[1, "total_miles"]), 15.0)
        self.assertEqual(int(trips.loc[1, "days"]), 1)

    def test_same_day_hikes_merge_into_one_trip_day(self):
        hikes = _hikes(
            [
                "2026-04-19T10:00:00Z",
                "2026-04-19T12:00:00Z",
            ],
            distances=[1.4, 1.3],
        )
        trips = consecutive_hike_trips(hikes)
        self.assertEqual(len(trips), 1)
        self.assertAlmostEqual(float(trips.loc[0, "total_miles"]), 2.7)
        self.assertEqual(int(trips.loc[0, "days"]), 1)

    def test_gap_of_one_day_starts_new_trip(self):
        hikes = _hikes(
            ["2026-06-01T08:00:00Z", "2026-06-03T08:00:00Z"],
            distances=[5.0, 7.0],
        )
        trips = consecutive_hike_trips(hikes)
        self.assertEqual(len(trips), 2)


class HikingKpiTests(unittest.TestCase):
    """Badge values and longest consecutive-day trip."""

    def test_ytd_and_longest_trip(self):
        hikes = _hikes(
            [
                "2025-12-31T08:00:00Z",
                "2026-05-25T08:00:00Z",
                "2026-05-26T08:00:00Z",
                "2026-05-27T08:00:00Z",
                "2026-07-01T08:00:00Z",
            ],
            distances=[8.0, 9.0, 3.0, 4.0, 12.0],
            elev=[1000.0, 2000.0, 500.0, 300.0, 4000.0],
            names=["Old", "A", "B", "C", "Peak"],
        )
        as_of = pd.Timestamp("2026-07-01T12:00:00Z")
        kpis = hiking_kpis(hikes, as_of=as_of)
        self.assertAlmostEqual(float(kpis["total_miles"]), 36.0)
        self.assertAlmostEqual(float(kpis["ytd_miles"]), 28.0)
        self.assertEqual(kpis["this_year"], 2026)
        self.assertAlmostEqual(float(kpis["longest_hike_miles"]), 12.0)
        self.assertEqual(kpis["longest_hike_name"], "Peak")
        self.assertAlmostEqual(float(kpis["greatest_elevation_miles"]), 4000.0 / 5280.0)
        # Trip May 25–27 = 16 mi beats single 12 mi hike
        self.assertAlmostEqual(float(kpis["longest_trip_miles"]), 16.0)
        self.assertEqual(int(kpis["longest_trip_days"]), 3)
        trip_names = [h["name"] for h in kpis["longest_trip_hikes"]]
        self.assertEqual(trip_names, ["A", "B", "C"])
        # Elevation KPIs are feet → miles (5280).
        self.assertAlmostEqual(float(kpis["total_elevation_miles"]), 7800.0 / 5280.0)
        self.assertAlmostEqual(float(kpis["ytd_elevation_miles"]), 6800.0 / 5280.0)


class HikeGapPointsTests(unittest.TestCase):
    """GAP point filtering respects the Show By window."""

    def test_filters_to_selected_window(self):
        hikes = _hikes(
            [
                "2026-01-05T08:00:00Z",
                "2026-06-10T08:00:00Z",
                "2026-06-17T08:00:00Z",
            ],
            distances=[5.0, 6.0, 7.0],
            elev=[1000.0, 1000.0, 1000.0],
            elapsed=[90.0, 100.0, 110.0],
        )
        points = hike_gap_points(
            hikes,
            grain="Week",
            as_of=pd.Timestamp("2026-06-20T00:00:00Z"),
            start=pd.Timestamp("2026-06-08T00:00:00Z"),
            end=pd.Timestamp("2026-06-20T00:00:00Z"),
        )
        self.assertEqual(len(points), 2)
        self.assertTrue(
            (points["gap_min_per_grade_mi"] > 0).all()
        )


class HikeGapChartTests(unittest.TestCase):
    """GAP chart carries markers and a trend when enough points exist."""

    def test_title_and_trend_trace(self):
        self.assertEqual(hike_gap_title(), "Grade-Adjusted Pace")
        points = pd.DataFrame(
            {
                "date": pd.to_datetime(
                    ["2026-06-01T08:00:00Z", "2026-06-08T08:00:00Z", "2026-06-15T08:00:00Z"],
                    utc=True,
                ),
                "name": ["A", "B", "C"],
                "distance_miles": [5.0, 6.0, 7.0],
                "elevation_gain_ft": [1000.0, 1200.0, 800.0],
                "elapsed_min": [100.0, 110.0, 120.0],
                "gap_min_per_grade_mi": [16.7, 15.3, 15.4],
            }
        )
        fig = hike_gap_chart(points)
        names = [t.name for t in fig.data]
        self.assertIn("Hikes", names)
        self.assertIn("Trend", names)
        self.assertIn("min / grade-mi", fig.layout.yaxis.title.text)


class HikingBadgesHtmlTests(unittest.TestCase):
    """Badge markup includes YTD and trip-rule tooltips."""

    def test_renders_five_badges_with_ytd_and_trip_rule(self):
        html = hiking_badges_html(
            {
                "total_miles": 100.0,
                "total_elevation_miles": 50000.0 / 5280.0,
                "this_year": 2026,
                "ytd_miles": 40.0,
                "ytd_elevation_miles": 20000.0 / 5280.0,
                "longest_hike_miles": 15.0,
                "longest_hike_date": pd.Timestamp("2026-05-28T00:00:00Z"),
                "longest_hike_name": "Cares",
                "greatest_elevation_miles": 3275.0 / 5280.0,
                "greatest_elevation_date": pd.Timestamp("2026-07-14T00:00:00Z"),
                "greatest_elevation_name": "Veleta",
                "longest_trip_miles": 30.0,
                "longest_trip_start": pd.Timestamp("2026-05-25T00:00:00Z"),
                "longest_trip_end": pd.Timestamp("2026-05-28T00:00:00Z"),
                "longest_trip_days": 4,
                "longest_trip_hikes": [
                    {
                        "name": "Pico Gilbo",
                        "date": pd.Timestamp("2026-05-25T00:00:00Z"),
                        "miles": 9.68,
                    },
                    {
                        "name": "Lagos",
                        "date": pd.Timestamp("2026-05-26T00:00:00Z"),
                        "miles": 2.76,
                    },
                ],
            }
        )
        self.assertIn('id="hiking-kpis"', html)
        self.assertEqual(html.count("achievement-medal"), 5)
        self.assertIn("Year-to-date", html)
        self.assertIn("consecutive calendar days that each include", html)
        self.assertNotIn("Miles are summed across all hikes", html)
        self.assertIn("Most Miles in a Trip", html)
        self.assertIn("Pico Gilbo", html)
        self.assertIn("Lagos", html)
        self.assertNotIn(" ft", html)
        # Elevation miles use the same mi formatting as distance badges.
        self.assertIn(" mi", html)


class HikingNavWiringTests(unittest.TestCase):
    """Hiking is registered in navigation and page list."""

    def test_nav_pages_include_hiking(self):
        from dashboard.ui import NAV_SECTIONS

        titles = [title for _, title, _ in NAV_PAGES]
        self.assertEqual(
            titles,
            ["Metrics", "Training", "Fitness", "Performance", "Hiking"],
        )
        paths = {path for _, _, path in NAV_PAGES}
        self.assertIn("pages/hiking.py", paths)
        other = dict(NAV_SECTIONS)["Other sports"]
        self.assertEqual([title for _, title, _ in other], ["Hiking"])

    def test_theme_hiking_section_gaps_match_metrics_training(self):
        """Controls→badges use --layout-gap; miles gets the larger top gap."""
        from dashboard.theme import (
            CHART_ELEVATION_MARGIN_TOP,
            CHART_HIKING_FIRST_MARGIN_TOP,
            CHART_MILEAGE_MARGIN_TOP,
            GLOBAL_CSS,
            LAYOUT_GAP,
        )

        self.assertEqual(LAYOUT_GAP, "1.8rem")
        self.assertEqual(CHART_MILEAGE_MARGIN_TOP, "1.85rem")
        self.assertEqual(CHART_ELEVATION_MARGIN_TOP, "1.85rem")
        self.assertEqual(CHART_HIKING_FIRST_MARGIN_TOP, "2.5rem")
        self.assertIn('#hiking-kpis', GLOBAL_CSS)
        self.assertIn(
            '[data-testid="stElementContainer"]:has(#hiking-kpis)',
            GLOBAL_CSS,
        )
        self.assertIn('[class*="st-key-hiking_map"]', GLOBAL_CSS)
        self.assertIn(".hiking-map-panel", GLOBAL_CSS)
        self.assertIn(".st-key-hiking_miles", GLOBAL_CSS)
        self.assertIn(".st-key-hiking_elevation", GLOBAL_CSS)
        self.assertIn(".st-key-hiking_gap", GLOBAL_CSS)
        # Map is top-row (beside Controls): no mid-page first-chart gap.
        map_css_idx = GLOBAL_CSS.index('[class*="st-key-hiking_map"]')
        map_rule = GLOBAL_CSS[map_css_idx : map_css_idx + 180]
        self.assertIn("margin-top: 0 !important", map_rule)
        self.assertNotIn(
            "margin-top: var(--chart-hiking-first-margin-top)",
            map_rule,
        )
        # First full-width chart after highlights uses the larger gap.
        miles_css_idx = GLOBAL_CSS.index(".st-key-hiking_miles")
        miles_rule = GLOBAL_CSS[miles_css_idx : miles_css_idx + 160]
        self.assertIn(
            "margin-top: var(--chart-hiking-first-margin-top) !important",
            miles_rule,
        )
        self.assertIn("#chart-hiking-map", GLOBAL_CSS)
        self.assertIn("#chart-hiking-miles", GLOBAL_CSS)
        self.assertIn("#chart-hiking-gap", GLOBAL_CSS)

    def test_streamlit_app_registers_hiking_page(self):
        app = Path(__file__).resolve().parents[2] / "dashboard" / "streamlit_app.py"
        text = app.read_text(encoding="utf-8")
        self.assertIn('st.Page("pages/hiking.py", title="Hiking")', text)
        self.assertIn("hiking", text)
        self.assertIn('"Other sports"', text)
        self.assertIn('"Running"', text)
        page = Path(__file__).resolve().parents[2] / "dashboard" / "pages" / "hiking.py"
        self.assertTrue(page.is_file())
        page_text = page.read_text(encoding="utf-8")
        self.assertIn("hike_location_folium_map", page_text)
        self.assertIn("st_folium", page_text)
        self.assertIn("consume_hiking_map_click", page_text)
        self.assertIn("HIKING_MAP_FILTER_KEY", page_text)
        self.assertIn("HIKING_MAP_CHART_REV_KEY", page_text)
        self.assertIn("HIKING_MAP_DRILL_KEY", page_text)
        self.assertIn("hiking_map_chart_key", page_text)
        self.assertIn("period_window_from_activities", page_text)
        self.assertIn("sync_hiking_show_by_for_map_filter", page_text)
        self.assertIn("HIKING_SHOW_BY_KEY", page_text)
        self.assertIn("chart_window", page_text)
        self.assertIn("Reset map filter", page_text)
        self.assertNotIn("Show all hikes", page_text)
        self.assertIn("hiking-map-panel", page_text)
        # Top row: Controls left, map right — then badges, then charts.
        self.assertIn("controls_col, map_col = st.columns([1.05, 2.35]", page_text)
        cols_idx = page_text.find("controls_col, map_col = st.columns")
        body = page_text[cols_idx:]
        self.assertLess(body.find("with map_col:"), body.find("hiking_badges_html("))
        self.assertLess(body.find("hiking_badges_html("), body.find("chart-hiking-miles"))
        self.assertLess(body.find("chart-hiking-map"), body.find("hiking_badges_html("))
        # Reset + map-filter count always live in the controls panel (filtered or not).
        controls_block = body[body.find("with controls_col:") : body.find("with map_col:")]
        map_block = body[body.find("with map_col:") :]
        self.assertIn("Reset map filter", controls_block)
        self.assertIn("Map filter", controls_block)
        self.assertIn("No area selected", controls_block)
        self.assertIn("in selected area", controls_block)
        self.assertNotIn("if map_filter_ids is not None:\n        n_", controls_block)
        self.assertNotIn("Reset map filter", map_block)
        self.assertNotIn("hike_cluster_", page_text)
        self.assertNotIn("hike_location_map_chart", page_text)
        self.assertNotIn("on_select=", page_text)
        self.assertNotIn("area buttons", page_text)

    def test_sidebar_entries_include_hiking_sections(self):
        entries = sidebar_nav_entries(
            "hiking",
            [
                ("chart-hiking-map", "Hike locations"),
                ("hiking-kpis", "Highlights"),
                ("chart-hiking-miles", "Weekly Mileage"),
                ("chart-hiking-elevation", "Weekly Elevation"),
                ("chart-hiking-gap", "Grade-Adjusted Pace"),
            ],
        )
        labels = [label for _, _, label in entries]
        self.assertIn("Other sports", labels)
        self.assertIn("Hiking", labels)
        self.assertIn("Highlights", labels)
        self.assertIn("Hike locations", labels)
        self.assertIn("Grade-Adjusted Pace", labels)
        # Hiking stays last among page links (after Other sports header).
        page_labels = [label for kind, _, label in entries if kind == "page"]
        self.assertEqual(page_labels[-1], "Hiking")
        # Section order matches top-of-page map, then highlights, then charts.
        section_labels = [label for kind, _, label in entries if kind == "section"]
        self.assertLess(
            section_labels.index("Hike locations"),
            section_labels.index("Highlights"),
        )
        self.assertLess(
            section_labels.index("Highlights"),
            section_labels.index("Weekly Mileage"),
        )
        ui = (
            Path(__file__).resolve().parents[2] / "dashboard" / "ui.py"
        ).read_text(encoding="utf-8")
        hiking_nav = ui[
            ui.index("def render_hiking_section_nav") : ui.index(
                "def clear_hiking_map_filter"
            )
        ]
        self.assertLess(
            hiking_nav.find("chart-hiking-map"),
            hiking_nav.find("hiking-kpis"),
        )
        self.assertLess(
            hiking_nav.find("hiking-kpis"),
            hiking_nav.find("chart-hiking-miles"),
        )


class LoadHikesTests(unittest.TestCase):
    """Hike CSV loader parses elapsed minutes."""

    def test_load_hikes_parses_elapsed(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            csv_path = data_dir / "strava_hike_analysis.csv"
            csv_path.write_text(
                "activity_id,name,type,gear_id,date,distance_miles,"
                "moving_time_min,elapsed_time_min,elevation_gain_ft,"
                "avg_pace,avg_pace_sec,max_pace,max_pace_sec,start_lat,start_lng\n"
                "1,Test,Hike,,2026-06-01T08:00:00Z,5.0,"
                "01:30:00,02:00:00,1000.0,18:00,1080,10:00,600,42.3,-71.1\n",
                encoding="utf-8",
            )
            df = load_hikes(data_dir)
            self.assertEqual(len(df), 1)
            self.assertAlmostEqual(float(df.iloc[0]["elapsed_min"]), 120.0)
            self.assertAlmostEqual(float(df.iloc[0]["distance_miles"]), 5.0)
            self.assertAlmostEqual(float(df.iloc[0]["start_lat"]), 42.3)
            self.assertAlmostEqual(float(df.iloc[0]["start_lng"]), -71.1)


class PeriodWindowFromActivitiesTests(unittest.TestCase):
    """Map-filter chart windows fit filtered hike date ranges."""

    def test_aligns_min_max_to_grain(self):
        hikes = _hikes(
            [
                "2024-05-15T08:00:00Z",
                "2024-07-20T08:00:00Z",
            ]
        )
        week = period_window_from_activities(hikes, "Week")
        assert week is not None
        self.assertEqual(
            week.start,
            align_to_period_start("Week", pd.Timestamp("2024-05-15T08:00:00Z")),
        )
        self.assertEqual(
            week.end,
            align_to_period_start("Week", pd.Timestamp("2024-07-20T08:00:00Z")),
        )
        month = period_window_from_activities(hikes, "Month")
        assert month is not None
        self.assertEqual(month.start, pd.Timestamp("2024-05-01T00:00:00Z"))
        self.assertEqual(month.end, pd.Timestamp("2024-07-01T00:00:00Z"))
        year = period_window_from_activities(hikes, "Year")
        assert year is not None
        self.assertEqual(year.start, pd.Timestamp("2024-01-01T00:00:00Z"))
        self.assertEqual(year.end, pd.Timestamp("2024-01-01T00:00:00Z"))

    def test_empty_or_invalid_returns_none(self):
        self.assertIsNone(period_window_from_activities(pd.DataFrame(), "Week"))
        self.assertIsNone(
            period_window_from_activities(pd.DataFrame({"name": ["a"]}), "Week")
        )

    def test_filtered_metrics_drop_leading_trailing_empty_periods(self):
        """Map subset replaces a wide Start/End with activity-bounded periods."""
        all_hikes = _hikes(
            [
                "2022-01-10T08:00:00Z",
                "2024-06-03T08:00:00Z",
                "2024-06-10T08:00:00Z",
                "2026-08-01T08:00:00Z",
            ],
            activity_ids=[1, 2, 3, 4],
            distances=[5.0, 6.0, 7.0, 8.0],
            elev=[500.0, 600.0, 700.0, 800.0],
        )
        filtered = apply_hiking_map_filter(all_hikes, ["2", "3"])
        as_of = pd.Timestamp("2026-09-01T00:00:00Z")
        # Simulated global control window (last many weeks) would pad empties.
        wide_start = align_to_period_start("Week", pd.Timestamp("2026-04-01T00:00:00Z"))
        wide_end = align_to_period_start("Week", as_of)
        wide = aggregate_period_metrics(
            filtered, "Week", as_of=as_of, start=wide_start, end=wide_end
        )
        # Filtered hikes are in June 2024 — outside the wide 2026 window → zeros.
        self.assertTrue((wide["total_miles"] == 0).all())

        fitted = period_window_from_activities(filtered, "Week")
        assert fitted is not None
        metrics = aggregate_period_metrics(
            filtered,
            "Week",
            as_of=as_of,
            start=fitted.start,
            end=fitted.end,
        )
        self.assertEqual(len(metrics), 2)
        self.assertAlmostEqual(float(metrics["total_miles"].sum()), 13.0)
        self.assertAlmostEqual(float(metrics["total_elevation_ft"].sum()), 1300.0)
        # No leading/trailing empty periods outside the two hike weeks.
        self.assertTrue((metrics["total_miles"] > 0).all())

        filtered_gap = filtered.copy()
        filtered_gap["elapsed_min"] = [100.0, 110.0]
        gap = hike_gap_points(
            filtered_gap,
            grain="Week",
            as_of=as_of,
            start=fitted.start,
            end=fitted.end,
        )
        self.assertEqual(len(gap), 2)


class PeriodGrainForDateSpanTests(unittest.TestCase):
    """Map-filter auto Show By grain from filtered hike date span."""

    def test_thresholds(self):
        # Single day / ~week → Day (≤ 14 days span).
        self.assertEqual(
            period_grain_for_date_span(_hikes(["2026-06-01T08:00:00Z"])),
            "Day",
        )
        self.assertEqual(
            period_grain_for_date_span(
                _hikes(["2026-06-01T08:00:00Z", "2026-06-08T08:00:00Z"])
            ),
            "Day",
        )
        self.assertEqual(
            period_grain_for_date_span(
                _hikes(["2026-06-01T08:00:00Z", "2026-06-15T08:00:00Z"])
            ),
            "Day",
        )
        # 15 days → Week; ~2 months → Week; 90 days → Week.
        self.assertEqual(
            period_grain_for_date_span(
                _hikes(["2026-06-01T08:00:00Z", "2026-06-16T08:00:00Z"])
            ),
            "Week",
        )
        self.assertEqual(
            period_grain_for_date_span(
                _hikes(["2026-01-01T08:00:00Z", "2026-04-01T08:00:00Z"])
            ),
            "Week",
        )
        # Just over 90 days → Month; ~2 years → Month.
        self.assertEqual(
            period_grain_for_date_span(
                _hikes(["2026-01-01T08:00:00Z", "2026-04-02T08:00:00Z"])
            ),
            "Month",
        )
        self.assertEqual(
            period_grain_for_date_span(
                _hikes(["2024-01-01T08:00:00Z", "2025-12-31T08:00:00Z"])
            ),
            "Month",
        )
        # > 730 days → Year.
        self.assertEqual(
            period_grain_for_date_span(
                _hikes(["2022-01-01T08:00:00Z", "2026-01-02T08:00:00Z"])
            ),
            "Year",
        )

    def test_empty_defaults_to_week(self):
        self.assertEqual(period_grain_for_date_span(pd.DataFrame()), "Week")
        self.assertEqual(
            period_grain_for_date_span(pd.DataFrame({"name": ["a"]})),
            "Week",
        )


class SyncHikingShowByForMapFilterTests(unittest.TestCase):
    """Session-state auto grain + restore around map filter changes."""

    def test_auto_on_filter_manual_override_restore_on_clear(self):
        import streamlit as st

        st.session_state.clear()
        st.session_state["hiking_show_by"] = "Month"

        week_span = _hikes(
            ["2026-06-01T08:00:00Z", "2026-06-08T08:00:00Z"],
            activity_ids=[1, 2],
        )
        # Filter activates → save Month, auto Day for ~week span.
        sync_hiking_show_by_for_map_filter(week_span, ["1", "2"])
        self.assertEqual(st.session_state["hiking_show_by"], "Day")
        self.assertEqual(st.session_state["hiking_map_prior_show_by"], "Month")
        self.assertEqual(st.session_state["hiking_map_auto_grain_ids"], ["1", "2"])

        # Same id set again → keep user's manual override.
        st.session_state["hiking_show_by"] = "Year"
        sync_hiking_show_by_for_map_filter(week_span, ["1", "2"])
        self.assertEqual(st.session_state["hiking_show_by"], "Year")
        self.assertEqual(st.session_state["hiking_map_prior_show_by"], "Month")

        # Id set changes → re-auto from new span; prior grain stays Month.
        month_span = _hikes(
            ["2024-05-01T08:00:00Z", "2024-08-01T08:00:00Z"],
            activity_ids=[3, 4],
        )
        sync_hiking_show_by_for_map_filter(month_span, ["4", "3"])
        self.assertEqual(st.session_state["hiking_show_by"], "Month")
        self.assertEqual(st.session_state["hiking_map_prior_show_by"], "Month")
        self.assertEqual(st.session_state["hiking_map_auto_grain_ids"], ["3", "4"])

        # Filter cleared → restore prior Show By.
        sync_hiking_show_by_for_map_filter(week_span, None)
        self.assertEqual(st.session_state["hiking_show_by"], "Month")
        self.assertNotIn("hiking_map_prior_show_by", st.session_state)
        self.assertNotIn("hiking_map_auto_grain_ids", st.session_state)

    def test_clear_hiking_map_filter_preserves_prior_grain_for_restore(self):
        """clear_hiking_map_filter leaves prior/auto keys for the next sync."""
        import streamlit as st

        st.session_state.clear()
        st.session_state["hiking_show_by"] = "Week"
        hikes = _hikes(
            ["2026-06-01T08:00:00Z", "2026-06-08T08:00:00Z"],
            activity_ids=[1, 2],
        )
        sync_hiking_show_by_for_map_filter(hikes, ["1", "2"])
        st.session_state["hiking_map_activity_ids"] = ["1", "2"]
        clear_hiking_map_filter()
        self.assertNotIn("hiking_map_activity_ids", st.session_state)
        self.assertEqual(st.session_state["hiking_map_prior_show_by"], "Week")
        self.assertEqual(st.session_state["hiking_map_auto_grain_ids"], ["1", "2"])
        # Page re-run with filter gone restores Week.
        sync_hiking_show_by_for_map_filter(hikes, None)
        self.assertEqual(st.session_state["hiking_show_by"], "Week")
        self.assertNotIn("hiking_map_prior_show_by", st.session_state)


class HikeMapHelperTests(unittest.TestCase):
    """GPS clustering, filter, drill-down, and map figure."""

    def test_drops_missing_coords(self):
        hikes = _hikes(
            ["2026-06-01T08:00:00Z", "2026-06-02T08:00:00Z"],
            lats=[42.0, None],
            lngs=[-71.0, -71.0],
        )
        geo = hikes_with_start_coords(hikes)
        self.assertEqual(len(geo), 1)
        self.assertEqual(int(geo.iloc[0]["activity_id"]), 1)

    def test_clusters_nearby_points_and_keeps_ids(self):
        hikes = _hikes(
            [
                "2026-06-01T08:00:00Z",
                "2026-06-02T08:00:00Z",
                "2026-06-03T08:00:00Z",
            ],
            activity_ids=[10, 11, 12],
            lats=[42.36, 42.37, 37.17],
            lngs=[-71.05, -71.04, -3.59],
        )
        # Force coarse bins so Boston pair merges.
        clusters = cluster_hike_starts(hikes, precision=1)
        self.assertEqual(len(clusters), 2)
        boston = clusters.loc[clusters["count"] == 2].iloc[0]
        self.assertEqual(set(boston["activity_ids"]), {"10", "11"})
        self.assertIn("label", clusters.columns)

    def test_hierarchical_parent_splits_into_children(self):
        """Parent cluster → filter + finer cell → child bubbles."""
        hikes = _hikes(
            [
                "2026-06-01T08:00:00Z",
                "2026-06-02T08:00:00Z",
                "2026-06-03T08:00:00Z",
                "2026-06-04T08:00:00Z",
            ],
            activity_ids=[1, 2, 3, 4],
            # Two tight Boston starts + two tight Granada starts, far apart.
            lats=[42.360, 42.361, 37.170, 37.171],
            lngs=[-71.050, -71.051, -3.590, -3.591],
            names=["B1", "B2", "G1", "G2"],
        )
        parents = cluster_hike_starts(hikes, cell_deg=5.0, max_clusters=12)
        self.assertEqual(len(parents), 2)
        boston = parents.loc[parents["lat"] > 40].iloc[0]
        self.assertEqual(int(boston["count"]), 2)
        boston_ids = list(boston["activity_ids"])
        self.assertEqual(set(boston_ids), {"1", "2"})

        child_hikes = apply_hiking_map_filter(hikes, boston_ids)
        children = cluster_hike_starts(child_hikes, drill_level=3, max_clusters=12)
        child_id_sets = [set(ids) for ids in children["activity_ids"]]
        self.assertTrue(all(s.issubset({"1", "2"}) for s in child_id_sets))
        self.assertEqual(len(children), 2)
        self.assertEqual(sorted(int(c) for c in children["count"]), [1, 1])
        # Mid-scale span still shrinks cell when drill increases.
        mid = _hikes(
            ["2026-06-01T08:00:00Z", "2026-06-02T08:00:00Z"],
            lats=[42.0, 43.0],
            lngs=[-71.0, -70.0],
        )
        self.assertLess(
            hike_cluster_cell_deg(mid, drill_level=2),
            hike_cluster_cell_deg(mid, drill_level=0),
        )

    def test_max_clusters_merges_nearby_bins(self):
        hikes = _hikes(
            [f"2026-06-{i:02d}T08:00:00Z" for i in range(1, 9)],
            activity_ids=list(range(1, 9)),
            lats=[42.0 + 0.01 * i for i in range(8)],
            lngs=[-71.0 - 0.01 * i for i in range(8)],
        )
        capped = cluster_hike_starts(hikes, precision=3, max_clusters=3)
        self.assertLessEqual(len(capped), 3)
        self.assertEqual(int(capped["count"].sum()), 8)

    def test_precision_coarsens_for_wide_span(self):
        wide = _hikes(
            ["2026-01-01T08:00:00Z", "2026-01-02T08:00:00Z"],
            lats=[40.0, -40.0],
            lngs=[-70.0, 10.0],
        )
        tight = _hikes(
            ["2026-01-01T08:00:00Z", "2026-01-02T08:00:00Z"],
            lats=[42.360, 42.361],
            lngs=[-71.050, -71.051],
        )
        self.assertLessEqual(hike_cluster_precision(wide), 1)
        self.assertGreaterEqual(hike_cluster_precision(tight), 3)
        self.assertGreater(
            hike_cluster_cell_deg(wide),
            hike_cluster_cell_deg(tight),
        )
        # Drill refines cell size on a mid-scale span (not already at the floor).
        mid = _hikes(
            ["2026-01-01T08:00:00Z", "2026-01-02T08:00:00Z"],
            lats=[42.0, 43.0],
            lngs=[-71.0, -70.0],
        )
        self.assertGreater(
            hike_cluster_cell_deg(mid, drill_level=0),
            hike_cluster_cell_deg(mid, drill_level=2),
        )

    def test_apply_filter_and_select_cluster(self):
        import streamlit as st

        hikes = _hikes(
            ["2026-06-01T08:00:00Z", "2026-06-02T08:00:00Z"],
            activity_ids=[100, 200],
            lats=[42.0, 43.0],
            lngs=[-71.0, -72.0],
        )
        filtered = apply_hiking_map_filter(hikes, ["100"])
        self.assertEqual(len(filtered), 1)
        self.assertEqual(int(filtered.iloc[0]["activity_id"]), 100)
        self.assertEqual(len(apply_hiking_map_filter(hikes, None)), 2)

        st.session_state.clear()
        select_hiking_map_cluster(["100"], hikes, current_filter_ids=None)
        self.assertEqual(st.session_state["hiking_map_activity_ids"], ["100"])
        self.assertIn("hiking_map_view", st.session_state)
        self.assertEqual(st.session_state["hiking_map_drill_level"], 0)
        self.assertEqual(st.session_state["hiking_map_chart_rev"], 1)

        # Clicking the same id set again forces a drill refine.
        select_hiking_map_cluster(["100"], hikes, current_filter_ids=["100"])
        self.assertEqual(st.session_state["hiking_map_drill_level"], 1)
        self.assertEqual(st.session_state["hiking_map_chart_rev"], 2)

    def test_map_chart_key_and_view_revision(self):
        self.assertEqual(hiking_map_chart_key(0), "hiking_map_0")
        self.assertEqual(hiking_map_chart_key(3), "hiking_map_3")
        view = {"center_lat": 42.1, "center_lon": -71.2, "zoom": 8.5}
        rev = hiking_map_view_revision(view)
        self.assertIn("42.1", rev)
        self.assertEqual(hiking_map_view_revision(view), rev)
        self.assertNotEqual(
            hiking_map_view_revision(view),
            hiking_map_view_revision({**view, "zoom": 11.0}),
        )

    def test_clear_hiking_map_filter_removes_rev_keys(self):
        import streamlit as st

        st.session_state.clear()
        st.session_state["hiking_map_activity_ids"] = ["1"]
        st.session_state["hiking_map_view"] = {"center_lat": 1.0, "center_lon": 2.0, "zoom": 3.0}
        st.session_state["hiking_map_chart_rev"] = 2
        st.session_state["hiking_map_drill_level"] = 3
        st.session_state["hiking_map_last_click"] = "fp"
        st.session_state["hiking_map_2"] = {"last_object_clicked": {"lat": 1.0, "lng": 2.0}}
        st.session_state["hiking_map_clusters"] = {"rows": [{"lat": 1.0}]}
        clear_hiking_map_filter()
        self.assertNotIn("hiking_map_activity_ids", st.session_state)
        self.assertNotIn("hiking_map_view", st.session_state)
        self.assertNotIn("hiking_map_chart_rev", st.session_state)
        self.assertNotIn("hiking_map_drill_level", st.session_state)
        self.assertNotIn("hiking_map_last_click", st.session_state)
        self.assertNotIn("hiking_map_2", st.session_state)
        self.assertNotIn("hiking_map_clusters", st.session_state)

    def test_click_fingerprint_stable_and_sensitive(self):
        event = {
            "last_object_clicked": {"lat": 42.36012, "lng": -71.05034},
            "last_object_clicked_popup": "CLUSTER:10",
            "last_object_clicked_tooltip": "1 hike",
        }
        fp = hiking_map_click_fingerprint(event)
        self.assertEqual(fp, "42.36012:-71.05034:CLUSTER:10:1 hike")
        self.assertEqual(hiking_map_click_fingerprint(event), fp)
        self.assertNotEqual(
            hiking_map_click_fingerprint({**event, "last_object_clicked_popup": "CLUSTER:11"}),
            fp,
        )
        self.assertIsNone(hiking_map_click_fingerprint(None))
        self.assertIsNone(hiking_map_click_fingerprint({"last_object_clicked": None}))

    def test_popup_encoding_and_click_consume(self):
        import streamlit as st

        self.assertEqual(hiking_map_cluster_popup(["10", "11"]), "CLUSTER:10,11")
        self.assertEqual(
            activity_ids_from_hiking_map_popup("CLUSTER:10,11"),
            ["10", "11"],
        )
        self.assertEqual(
            activity_ids_from_hiking_map_popup("<div>CLUSTER:10,11</div>"),
            ["10", "11"],
        )
        hikes = _hikes(
            ["2026-06-01T08:00:00Z", "2026-06-02T08:00:00Z"],
            activity_ids=[10, 11],
            lats=[42.0, 43.0],
            lngs=[-71.0, -72.0],
        )
        clusters = cluster_hike_starts(hikes, precision=1)
        event = {
            "last_object_clicked": {"lat": 42.0, "lng": -71.0},
            "last_object_clicked_popup": "CLUSTER:10",
            "last_object_clicked_tooltip": "1 hike",
        }
        self.assertEqual(activity_ids_from_hiking_map_click(event, clusters), ["10"])
        # Lat/lng fallback when popup is missing.
        event_no_popup = {
            "last_object_clicked": {
                "lat": float(clusters.iloc[0]["lat"]),
                "lng": float(clusters.iloc[0]["lng"]),
            },
            "last_object_clicked_popup": None,
        }
        fallback_ids = activity_ids_from_hiking_map_click(event_no_popup, clusters)
        self.assertTrue(fallback_ids)
        self.assertTrue(set(fallback_ids).issubset({"10", "11"}))

        st.session_state.clear()
        self.assertTrue(
            consume_hiking_map_click(event, hikes, current_filter_ids=None, clusters=clusters)
        )
        self.assertEqual(st.session_state["hiking_map_activity_ids"], ["10"])
        # Same click fingerprint must not re-apply (loop guard).
        self.assertFalse(
            consume_hiking_map_click(event, hikes, current_filter_ids=["10"], clusters=clusters)
        )

    def test_map_view_and_folium_markers(self):
        hikes = _hikes(
            ["2026-06-01T08:00:00Z", "2026-06-02T08:00:00Z"],
            activity_ids=[1, 2],
            lats=[42.0, 42.1],
            lngs=[-71.0, -71.1],
        )
        view = hike_map_view(hikes)
        self.assertIn("center_lat", view)
        self.assertIn("zoom", view)
        self.assertGreater(view["zoom"], 0)
        # Default pad/zoom_out is more zoomed out than the prior tight fit.
        tight_legacy = hike_map_view(hikes, pad_frac=0.18, zoom_out=0.0)
        self.assertLessEqual(view["zoom"], tight_legacy["zoom"])
        self.assertEqual(hike_map_title(), "Hike locations")
        clusters = cluster_hike_starts(hikes, precision=2)
        fmap = hike_location_folium_map(
            clusters,
            center_lat=view["center_lat"],
            center_lon=view["center_lon"],
            zoom=view["zoom"],
        )
        # Folium children include the tile layer plus one Marker per cluster.
        marker_count = sum(
            1
            for child in fmap._children.values()
            if child.__class__.__name__ == "Marker"
        )
        self.assertEqual(marker_count, len(clusters))
        # Half-step zoom floors to the more zoomed-out integer (1.5 → 1).
        wide_fmap = hike_location_folium_map(
            clusters,
            center_lat=0.0,
            center_lon=0.0,
            zoom=1.5,
        )
        self.assertEqual(wide_fmap.options["zoom"], 1)
        html = fmap.get_root().render()
        self.assertIn("CLUSTER:", html)
        # DivIcon HTML is JS-escaped in the Folium render (e.g. ``\\u003e1\\u003c/div``).
        self.assertIn("\\u003e1\\u003c/div", html)
        self.assertIn("#509B8F", html)
        self.assertIn("click to filter", html)

    def test_filter_refines_precision_and_view_zooms(self):
        """Drill-down: subset span → finer bins and higher zoom."""
        hikes = _hikes(
            [
                "2026-06-01T08:00:00Z",
                "2026-06-02T08:00:00Z",
                "2026-06-03T08:00:00Z",
                "2026-06-04T08:00:00Z",
            ],
            activity_ids=[1, 2, 3, 4],
            lats=[42.36, 42.37, 37.17, 48.85],
            lngs=[-71.05, -71.04, -3.59, 2.35],
        )
        wide_view = hike_map_view(hikes)
        boston = apply_hiking_map_filter(hikes, ["1", "2"])
        tight_view = hike_map_view(boston)
        self.assertGreater(tight_view["zoom"], wide_view["zoom"])
        self.assertGreater(
            hike_cluster_precision(boston),
            hike_cluster_precision(hikes),
        )
        self.assertLess(
            hike_cluster_cell_deg(boston),
            hike_cluster_cell_deg(hikes),
        )


if __name__ == "__main__":
    unittest.main()
