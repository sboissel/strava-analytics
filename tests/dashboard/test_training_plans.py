"""Tests for training plan CSV parsing and week helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from dashboard.data import (
    PLAN_ZOOM_NONE,
    PeriodWindow,
    align_to_period_start,
    attach_plan_targets_to_periods,
    current_plan_week_index,
    default_expanded_plan_index,
    default_expanded_plan_week_index,
    default_period_bounds,
    is_plan_race_session,
    load_training_plans,
    parse_plan_elevation,
    parse_plan_header_name,
    parse_plan_miles,
    parse_training_plan_file,
    period_window_for_plan,
    period_window_widget_values,
    plan_focus_session_date,
    plan_targets_overlap_periods,
    plan_vs_actual_all_plans,
    plan_vs_actual_by_week,
    plan_vs_actual_has_overlap,
    plan_week_expander_label,
    plan_week_index_for_date,
    plan_week_totals,
    select_plan_for_charts,
    sync_training_plan_zoom_window,
    training_plans_max_end,
)
from dashboard.theme import GLOBAL_CSS, TRAINING_PLAN_RACE_TEXT
from dashboard.ui import training_plan_table_html, training_plan_week_table_html


class PlanHeaderTests(unittest.TestCase):
    def test_parse_hash_header(self):
        self.assertEqual(
            parse_plan_header_name("#November halves"), "November halves"
        )
        self.assertEqual(
            parse_plan_header_name("#Sierra Nevada Half"), "Sierra Nevada Half"
        )

    def test_parse_header_fallback(self):
        self.assertEqual(parse_plan_header_name("#"), "Training plan")
        self.assertEqual(
            parse_plan_header_name(None, fallback="sierra half"), "sierra half"
        )
        self.assertEqual(parse_plan_header_name("  "), "Training plan")


class PlanRaceAndMilesTests(unittest.TestCase):
    def test_race_session_detection(self):
        self.assertTrue(is_plan_race_session("Race day"))
        self.assertTrue(is_plan_race_session("RACE DAY"))
        self.assertTrue(is_plan_race_session("12.5K trail race"))
        self.assertTrue(is_plan_race_session("Malaga Half"))
        self.assertTrue(is_plan_race_session("Cordoba Half"))
        self.assertTrue(is_plan_race_session("Sierra Nevada Half"))
        self.assertTrue(is_plan_race_session("City Marathon"))
        self.assertFalse(is_plan_race_session("Easy trail run"))
        self.assertFalse(is_plan_race_session("Long run"))
        self.assertFalse(is_plan_race_session(""))
        self.assertFalse(is_plan_race_session(None))

    def test_parse_plan_miles_number_and_range(self):
        miles, label = parse_plan_miles("10")
        self.assertEqual(miles, 10.0)
        self.assertEqual(label, "10")

        miles, label = parse_plan_miles("3-4")
        self.assertEqual(miles, 3.5)
        self.assertEqual(label, "3-4")

        miles, label = parse_plan_miles("")
        self.assertIsNone(miles)
        self.assertEqual(label, "—")

    def test_parse_plan_elevation(self):
        self.assertEqual(parse_plan_elevation(1200), 1200.0)
        self.assertEqual(parse_plan_elevation("850.5"), 850.5)
        self.assertIsNone(parse_plan_elevation(""))
        self.assertIsNone(parse_plan_elevation(None))
        self.assertIsNone(parse_plan_elevation("flat"))
        self.assertIsNone(parse_plan_elevation(float("nan")))


class PlanWeekHelperTests(unittest.TestCase):
    def test_week_totals_with_and_without_elevation(self):
        miles, elev = plan_week_totals(
            [
                {"miles": 3.0, "elevation_ft": None},
                {"miles": 7.0, "elevation_ft": None},
            ]
        )
        self.assertEqual(miles, 10.0)
        self.assertIsNone(elev)

        miles, elev = plan_week_totals(
            [
                {"miles": 2.0, "elevation_ft": 100},
                {"miles": 6.0, "elevation_ft": 400},
            ]
        )
        self.assertEqual(miles, 8.0)
        self.assertEqual(elev, 500.0)

    def test_default_expanded_current_week(self):
        weeks = [
            {"week_start": pd.Timestamp("2026-09-07", tz="UTC")},
            {"week_start": pd.Timestamp("2026-09-14", tz="UTC")},
            {"week_start": pd.Timestamp("2026-09-21", tz="UTC")},
        ]
        today = pd.Timestamp("2026-09-16", tz="UTC")
        self.assertEqual(default_expanded_plan_week_index(weeks, today), 1)
        self.assertEqual(current_plan_week_index(weeks, today), 1)

    def test_default_expanded_nearest_upcoming(self):
        weeks = [
            {"week_start": pd.Timestamp("2026-08-31", tz="UTC")},
            {"week_start": pd.Timestamp("2026-09-21", tz="UTC")},
        ]
        today = pd.Timestamp("2026-09-14", tz="UTC")
        self.assertEqual(default_expanded_plan_week_index(weeks, today), 1)
        # Week-row open state only expands "this week", not nearest upcoming.
        self.assertIsNone(current_plan_week_index(weeks, today))

    def test_default_expanded_all_past_collapses(self):
        weeks = [
            {"week_start": pd.Timestamp("2026-08-03", tz="UTC")},
            {"week_start": pd.Timestamp("2026-08-10", tz="UTC")},
        ]
        today = pd.Timestamp("2026-09-14", tz="UTC")
        self.assertIsNone(default_expanded_plan_week_index(weeks, today))
        self.assertIsNone(current_plan_week_index(weeks, today))

    def test_default_expanded_plan_prefers_current_week_plan(self):
        plans = [
            {
                "name": "Past Plan",
                "weeks": [{"week_start": pd.Timestamp("2026-08-03", tz="UTC")}],
            },
            {
                "name": "Active Plan",
                "weeks": [
                    {"week_start": pd.Timestamp("2026-09-07", tz="UTC")},
                    {"week_start": pd.Timestamp("2026-09-14", tz="UTC")},
                ],
            },
            {
                "name": "Future Plan",
                "weeks": [{"week_start": pd.Timestamp("2026-11-02", tz="UTC")}],
            },
        ]
        today = pd.Timestamp("2026-09-16", tz="UTC")
        self.assertEqual(default_expanded_plan_index(plans, today), 1)

    def test_default_expanded_plan_nearest_upcoming(self):
        plans = [
            {
                "name": "Past Plan",
                "weeks": [{"week_start": pd.Timestamp("2026-08-03", tz="UTC")}],
            },
            {
                "name": "Soon Plan",
                "weeks": [{"week_start": pd.Timestamp("2026-09-21", tz="UTC")}],
            },
            {
                "name": "Later Plan",
                "weeks": [{"week_start": pd.Timestamp("2026-11-02", tz="UTC")}],
            },
        ]
        today = pd.Timestamp("2026-09-14", tz="UTC")
        self.assertEqual(default_expanded_plan_index(plans, today), 1)

    def test_default_expanded_plan_all_past_collapses(self):
        plans = [
            {
                "name": "Past A",
                "weeks": [{"week_start": pd.Timestamp("2026-07-06", tz="UTC")}],
            },
            {
                "name": "Past B",
                "weeks": [{"week_start": pd.Timestamp("2026-08-03", tz="UTC")}],
            },
        ]
        today = pd.Timestamp("2026-09-14", tz="UTC")
        self.assertIsNone(default_expanded_plan_index(plans, today))

    def test_expander_label_includes_elev_when_present(self):
        week = {
            "week_label": "Sep 14, 2026 - Sep 20, 2026",
            "total_miles": 20.8,
            "total_elevation_ft": None,
        }
        self.assertEqual(
            plan_week_expander_label(week),
            "Sep 14, 2026 - Sep 20, 2026 · 20.8 mi",
        )
        week["total_elevation_ft"] = 1234.0
        self.assertEqual(
            plan_week_expander_label(week),
            "Sep 14, 2026 - Sep 20, 2026 · 20.8 mi · 1,234 ft",
        )


class PlanFileParseTests(unittest.TestCase):
    def _write_plan(self, directory: Path, name: str, body: str) -> Path:
        path = directory / name
        path.write_text(body, encoding="utf-8")
        return path

    def test_parse_header_name_and_weeks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_plan(
                Path(tmp),
                "sample.csv",
                "\n".join(
                    [
                        "#Sample Plan",
                        "Date,Target Miles,Session,Target Elevation",
                        "2026-09-14,4,Easy trail run,",
                        "2026-09-16,3.8,Hill repeats,",
                        "2026-09-18,10,Long run,",
                        "2026-09-21,4,Easy run,",
                        "2026-11-08,13.1,Race day,",
                    ]
                )
                + "\n",
            )
            plan = parse_training_plan_file(path)

        self.assertEqual(plan["name"], "Sample Plan")
        self.assertEqual(len(plan["weeks"]), 3)
        self.assertEqual(
            plan["end_date"], pd.Timestamp("2026-11-08", tz="UTC")
        )
        week0 = plan["weeks"][0]
        self.assertEqual(
            week0["week_start"], pd.Timestamp("2026-09-14", tz="UTC")
        )
        self.assertAlmostEqual(float(week0["total_miles"]), 17.8)
        self.assertIsNone(week0["total_elevation_ft"])
        self.assertEqual(len(week0["sessions"]), 3)

        race_week = plan["weeks"][2]
        self.assertTrue(bool(race_week["sessions"][0]["is_race"]))

    def test_column_case_and_elevation_totals(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_plan(
                Path(tmp),
                "elev.csv",
                "\n".join(
                    [
                        "#Elev Plan",
                        "Date,Target miles,Session,Target elevation",
                        "2026-12-01,2.0,Easy trail,72",
                        "2026-12-03,6,Long run,492",
                    ]
                )
                + "\n",
            )
            plan = parse_training_plan_file(path)

        week = plan["weeks"][0]
        self.assertAlmostEqual(float(week["total_miles"]), 8.0)
        self.assertAlmostEqual(float(week["total_elevation_ft"]), 564.0)

    def test_unquoted_comma_in_session_merged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_plan(
                Path(tmp),
                "comma.csv",
                "\n".join(
                    [
                        "#Comma Plan",
                        "Date,Target Miles,Session,Target Elevation",
                        "2026-10-23,13,Long run, flat terrain,",
                    ]
                )
                + "\n",
            )
            plan = parse_training_plan_file(path)

        session = plan["weeks"][0]["sessions"][0]
        self.assertEqual(session["session"], "Long run, flat terrain")
        self.assertEqual(session["miles"], 13.0)
        self.assertIsNone(session["elevation_ft"])

    def test_load_plans_chronological_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_plan(
                root,
                "later.csv",
                "\n".join(
                    [
                        "#Later Plan",
                        "Date,Target Miles,Session,Target Elevation",
                        "2026-12-01,5,Easy,",
                    ]
                )
                + "\n",
            )
            self._write_plan(
                root,
                "earlier.csv",
                "\n".join(
                    [
                        "#Earlier Plan",
                        "Date,Target Miles,Session,Target Elevation",
                        "2026-07-27,3,Easy,",
                    ]
                )
                + "\n",
            )
            plans = load_training_plans(root)

        self.assertEqual([p["name"] for p in plans], ["Earlier Plan", "Later Plan"])

    def test_training_plans_max_end_uses_latest_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_plan(
                root,
                "a.csv",
                "\n".join(
                    [
                        "#A",
                        "Date,Target Miles,Session,Target Elevation",
                        "2026-09-14,4,Easy,",
                        "2026-11-08,13.1,Race,",
                    ]
                )
                + "\n",
            )
            self._write_plan(
                root,
                "b.csv",
                "\n".join(
                    [
                        "#B",
                        "Date,Target Miles,Session,Target Elevation",
                        "2026-12-01,5,Easy,",
                        "2027-04-04,15.5,Race,",
                    ]
                )
                + "\n",
            )
            plans = load_training_plans(root)

        self.assertEqual(
            training_plans_max_end(plans),
            pd.Timestamp("2027-04-04", tz="UTC"),
        )

    def test_training_plans_max_end_empty(self):
        self.assertIsNone(training_plans_max_end([]))
        self.assertIsNone(
            training_plans_max_end(
                [{"name": "x", "start_date": None, "end_date": None, "weeks": []}]
            )
        )

    def test_training_plans_max_end_falls_back_to_week_sunday(self):
        plans = [
            {
                "name": "No end_date",
                "end_date": None,
                "weeks": [
                    {"week_start": pd.Timestamp("2026-09-14", tz="UTC")},
                    {"week_start": pd.Timestamp("2026-09-21", tz="UTC")},
                ],
            }
        ]
        self.assertEqual(
            training_plans_max_end(plans),
            pd.Timestamp("2026-09-27", tz="UTC"),
        )

    def test_repo_plan_csvs_parse(self):
        repo_plans = Path(__file__).resolve().parents[2] / "data" / "plans"
        if not repo_plans.is_dir():
            self.skipTest("data/plans not present")
        plans = load_training_plans(repo_plans)
        self.assertGreaterEqual(len(plans), 2)
        names = [p["name"] for p in plans]
        self.assertIn("November halves", names)
        self.assertIn("Sierra Nevada Half", names)
        # Chronological: November halves starts before Sierra.
        self.assertEqual(names[0], "November halves")
        nov = next(p for p in plans if p["name"] == "November halves")
        race_sessions = [
            s
            for week in nov["weeks"]
            for s in week["sessions"]
            if s["is_race"]
        ]
        self.assertGreaterEqual(len(race_sessions), 2)


class PlanFocusDateTests(unittest.TestCase):
    def _weeks(self) -> list[dict[str, object]]:
        return [
            {
                "week_start": pd.Timestamp("2026-09-07", tz="UTC"),
                "sessions": [
                    {"date": pd.Timestamp("2026-09-08", tz="UTC")},
                    {"date": pd.Timestamp("2026-09-10", tz="UTC")},
                ],
            },
            {
                "week_start": pd.Timestamp("2026-09-14", tz="UTC"),
                "sessions": [
                    {"date": pd.Timestamp("2026-09-16", tz="UTC")},
                    {"date": pd.Timestamp("2026-09-18", tz="UTC")},
                ],
            },
        ]

    def test_focus_prefers_today(self):
        today = pd.Timestamp("2026-09-16", tz="UTC")
        self.assertEqual(
            plan_focus_session_date(self._weeks(), today),
            pd.Timestamp("2026-09-16", tz="UTC"),
        )
        self.assertEqual(plan_week_index_for_date(self._weeks(), today), 1)

    def test_focus_next_in_current_week(self):
        today = pd.Timestamp("2026-09-15", tz="UTC")
        self.assertEqual(
            plan_focus_session_date(self._weeks(), today),
            pd.Timestamp("2026-09-16", tz="UTC"),
        )

    def test_focus_next_across_plan_when_current_week_exhausted(self):
        # Sep 12 is in week 0; no remaining sessions that week → Sep 16.
        today = pd.Timestamp("2026-09-12", tz="UTC")
        self.assertEqual(
            plan_focus_session_date(self._weeks(), today),
            pd.Timestamp("2026-09-16", tz="UTC"),
        )

    def test_focus_none_when_all_past(self):
        today = pd.Timestamp("2026-10-01", tz="UTC")
        self.assertIsNone(plan_focus_session_date(self._weeks(), today))

    def test_focus_skips_to_next_week_when_current_exhausted(self):
        weeks = self._weeks() + [
            {
                "week_start": pd.Timestamp("2026-09-21", tz="UTC"),
                "sessions": [
                    {"date": pd.Timestamp("2026-09-22", tz="UTC")},
                ],
            },
        ]
        # Sun Sep 20 is still in week 1, but no remaining sessions → Sep 22.
        today = pd.Timestamp("2026-09-20", tz="UTC")
        self.assertEqual(
            plan_focus_session_date(weeks, today),
            pd.Timestamp("2026-09-22", tz="UTC"),
        )
        self.assertEqual(plan_week_index_for_date(weeks, today), None)
        self.assertEqual(
            plan_week_index_for_date(
                weeks, pd.Timestamp("2026-09-22", tz="UTC")
            ),
            2,
        )


class PlanTableHtmlTests(unittest.TestCase):
    def _sample_weeks(self) -> list[dict[str, object]]:
        return [
            {
                "week_label": "Sep 7, 2026 - Sep 13, 2026",
                "week_start": pd.Timestamp("2026-09-07", tz="UTC"),
                "total_miles": 10.0,
                "total_elevation_ft": None,
                "sessions": [
                    {
                        "date": pd.Timestamp("2026-09-08", tz="UTC"),
                        "session": "Easy run",
                        "miles_label": "4",
                        "elevation_ft": None,
                        "is_race": False,
                    }
                ],
            },
            {
                "week_label": "Sep 14, 2026 - Sep 20, 2026",
                "week_start": pd.Timestamp("2026-09-14", tz="UTC"),
                "total_miles": 20.8,
                "total_elevation_ft": 1234.0,
                "sessions": [
                    {
                        "date": pd.Timestamp("2026-09-16", tz="UTC"),
                        "session": "Hill repeats",
                        "miles_label": "3.8",
                        "elevation_ft": 400,
                        "is_race": False,
                    },
                    {
                        "date": pd.Timestamp("2026-11-08", tz="UTC"),
                        "session": "Race day",
                        "miles_label": "13.1",
                        "elevation_ft": None,
                        "is_race": True,
                    },
                ],
            },
        ]

    def test_race_rows_marked_without_requiring_background_class(self):
        html = training_plan_week_table_html(
            [
                {
                    "date": pd.Timestamp("2026-11-08", tz="UTC"),
                    "session": "Race day",
                    "miles_label": "13.1",
                    "elevation_ft": None,
                    "is_race": True,
                },
                {
                    "date": pd.Timestamp("2026-11-09", tz="UTC"),
                    "session": "Easy run",
                    "miles_label": "3.6",
                    "elevation_ft": None,
                    "is_race": False,
                },
            ],
            today=pd.Timestamp("2026-11-01", tz="UTC"),
        )
        self.assertIn("training-plan-session-row is-race", html)
        self.assertIn("training-plan-race-badge", html)
        self.assertIn("Race day", html)
        self.assertIn("Easy run", html)
        # Race day is the next upcoming session from Nov 1.
        self.assertIn("training-plan-session-row is-race is-next", html)

    def test_race_row_text_color_applies_to_whole_row(self):
        """Race cue is muted-gold text on the row, not only the session name."""
        self.assertEqual(TRAINING_PLAN_RACE_TEXT, "#A67C2D")
        self.assertIn(
            f".training-plan-session-row.is-race {{\n    color: {TRAINING_PLAN_RACE_TEXT};",
            GLOBAL_CSS,
        )
        # Session name stays bold; color comes from the row (not a session-only rule).
        self.assertIn(
            ".training-plan-session-row.is-race .training-plan-session {\n"
            "    font-weight: 700;",
            GLOBAL_CSS,
        )
        self.assertNotIn(
            ".training-plan-session-row.is-race .training-plan-session {\n"
            "    font-weight: 700;\n"
            f"    color: {TRAINING_PLAN_RACE_TEXT};",
            GLOBAL_CSS,
        )
        # No gold background wash on race rows.
        self.assertNotIn(
            ".training-plan-session-row.is-race {\n    background:",
            GLOBAL_CSS,
        )
        self.assertNotIn(
            f"background: {TRAINING_PLAN_RACE_TEXT}",
            GLOBAL_CSS,
        )

    def test_today_session_highlighted(self):
        html = training_plan_table_html(
            self._sample_weeks(),
            expanded_week_index=1,
            today=pd.Timestamp("2026-09-16", tz="UTC"),
        )
        self.assertIn("training-plan-session-row is-today", html)
        self.assertIn("Hill repeats", html)
        self.assertNotIn("is-next", html)

    def test_next_session_highlighted_when_no_today(self):
        html = training_plan_table_html(
            self._sample_weeks(),
            expanded_week_index=1,
            today=pd.Timestamp("2026-09-15", tz="UTC"),
        )
        self.assertIn("training-plan-session-row is-next", html)
        self.assertIn("Hill repeats", html)
        self.assertNotIn("is-today", html)

    def test_plan_table_uses_details_week_rows(self):
        html = training_plan_table_html(
            self._sample_weeks(),
            expanded_week_index=1,
            today=pd.Timestamp("2026-09-01", tz="UTC"),
        )
        self.assertIn('class="training-plan-week"', html)
        self.assertIn("Week 1 total", html)
        self.assertIn("Week 2 total", html)
        self.assertIn("Sep 14, 2026 - Sep 20, 2026", html)
        self.assertIn(">20.8<", html)
        self.assertIn(">1,234<", html)
        self.assertIn("Hill repeats", html)
        self.assertIn("training-plan-session-row is-race", html)

        # Session rows nest under week summaries (indent via CSS padding).
        self.assertIn('class="training-plan-sessions"', html)

        # Only the selected week summary has the open attribute.
        open_weeks = html.count('<details class="training-plan-week" open>')
        closed_weeks = html.count('<details class="training-plan-week">')
        self.assertEqual(open_weeks, 1)
        self.assertEqual(closed_weeks, 1)

    def test_no_focus_marker_when_all_sessions_past(self):
        html = training_plan_table_html(
            self._sample_weeks(),
            expanded_week_index=None,
            today=pd.Timestamp("2026-12-01", tz="UTC"),
        )
        self.assertNotIn("is-today", html)
        self.assertNotIn("is-next", html)

    def test_plan_table_all_weeks_collapsed_without_index(self):
        html = training_plan_table_html(
            self._sample_weeks(),
            expanded_week_index=None,
            today=pd.Timestamp("2026-09-01", tz="UTC"),
        )
        self.assertEqual(
            html.count('<details class="training-plan-week" open>'), 0
        )
        self.assertEqual(html.count('<details class="training-plan-week">'), 2)


class PlanVsActualAggregatorTests(unittest.TestCase):
    def _plan(self) -> dict[str, object]:
        return {
            "name": "Sample",
            "weeks": [
                {
                    "week_start": pd.Timestamp("2026-09-14", tz="UTC"),
                    "week_label": "Sep 14, 2026 - Sep 20, 2026",
                    "total_miles": 17.8,
                    "total_elevation_ft": None,
                    "sessions": [
                        {
                            "date": pd.Timestamp("2026-09-14", tz="UTC"),
                            "miles": 4.0,
                            "elevation_ft": None,
                        },
                        {
                            "date": pd.Timestamp("2026-09-16", tz="UTC"),
                            "miles": 3.8,
                            "elevation_ft": None,
                        },
                        {
                            "date": pd.Timestamp("2026-09-18", tz="UTC"),
                            "miles": 10.0,
                            "elevation_ft": None,
                        },
                    ],
                },
                {
                    "week_start": pd.Timestamp("2026-09-21", tz="UTC"),
                    "week_label": "Sep 21, 2026 - Sep 27, 2026",
                    "total_miles": 12.0,
                    "total_elevation_ft": 800.0,
                    "sessions": [],
                },
            ],
        }

    def _runs(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "date": [
                    pd.Timestamp("2026-09-14", tz="UTC"),
                    pd.Timestamp("2026-09-18", tz="UTC"),
                    pd.Timestamp("2026-09-20", tz="UTC"),  # Sunday of week 0
                    pd.Timestamp("2026-09-21", tz="UTC"),  # Monday of week 1
                    pd.Timestamp("2026-09-28", tz="UTC"),  # outside plan weeks
                ],
                "distance_miles": [4.0, 9.5, 3.0, 5.0, 99.0],
                "elevation_gain_ft": [100.0, 200.0, 50.0, 400.0, 999.0],
            }
        )

    def test_aligns_iso_weeks_and_sums_actuals(self):
        out = plan_vs_actual_by_week(
            self._plan(),
            self._runs(),
            as_of=pd.Timestamp("2026-09-16", tz="UTC"),
        )
        self.assertEqual(len(out), 2)
        self.assertEqual(out.iloc[0]["period_key"], "2026-38")
        self.assertEqual(out.iloc[0]["plan_name"], "Sample")
        self.assertEqual(int(out.iloc[0]["plan_week"]), 1)
        self.assertEqual(int(out.iloc[1]["plan_week"]), 2)
        self.assertAlmostEqual(float(out.iloc[0]["plan_miles"]), 17.8)
        self.assertTrue(pd.isna(out.iloc[0]["plan_elevation_ft"]))
        # Sep 14 + 18 + 20 (Sun still in Mon–Sun week)
        self.assertAlmostEqual(float(out.iloc[0]["actual_miles"]), 16.5)
        self.assertAlmostEqual(float(out.iloc[0]["actual_elevation_ft"]), 350.0)
        self.assertEqual(int(out.iloc[0]["run_count"]), 3)
        self.assertTrue(bool(out.iloc[0]["in_progress"]))

        self.assertAlmostEqual(float(out.iloc[1]["plan_miles"]), 12.0)
        self.assertAlmostEqual(float(out.iloc[1]["plan_elevation_ft"]), 800.0)
        self.assertAlmostEqual(float(out.iloc[1]["actual_miles"]), 5.0)
        self.assertAlmostEqual(float(out.iloc[1]["actual_elevation_ft"]), 400.0)
        self.assertFalse(bool(out.iloc[1]["in_progress"]))
        # Sep 28 is outside both plan weeks.
        self.assertNotIn(99.0, out["actual_miles"].tolist())

    def test_empty_plan_and_no_overlap(self):
        empty = plan_vs_actual_by_week({"name": "x", "weeks": []}, self._runs())
        self.assertTrue(empty.empty)
        self.assertFalse(plan_vs_actual_has_overlap(empty))

        no_overlap_runs = pd.DataFrame(
            {
                "date": [pd.Timestamp("2026-01-01", tz="UTC")],
                "distance_miles": [10.0],
                "elevation_gain_ft": [100.0],
            }
        )
        out = plan_vs_actual_by_week(self._plan(), no_overlap_runs)
        self.assertEqual(len(out), 2)
        self.assertFalse(plan_vs_actual_has_overlap(out))
        self.assertEqual(int(out["run_count"].sum()), 0)

    def test_range_midpoint_flows_into_week_totals_for_actual_chart(self):
        # parse_plan_miles midpoint already used when building week totals;
        # ensure aggregator consumes those totals as plan_miles.
        plan = {
            "name": "Ranges",
            "weeks": [
                {
                    "week_start": pd.Timestamp("2026-09-14", tz="UTC"),
                    "total_miles": 3.5,  # midpoint of 3-4
                    "total_elevation_ft": None,
                    "sessions": [],
                }
            ],
        }
        out = plan_vs_actual_by_week(plan, pd.DataFrame())
        self.assertAlmostEqual(float(out.iloc[0]["plan_miles"]), 3.5)
        self.assertAlmostEqual(float(out.iloc[0]["actual_miles"]), 0.0)

    def test_select_plan_for_charts_fallback_to_latest_past(self):
        plans = [
            {
                "name": "Past A",
                "weeks": [{"week_start": pd.Timestamp("2026-07-06", tz="UTC")}],
            },
            {
                "name": "Past B",
                "weeks": [{"week_start": pd.Timestamp("2026-08-03", tz="UTC")}],
            },
        ]
        today = pd.Timestamp("2026-09-14", tz="UTC")
        self.assertIsNone(default_expanded_plan_index(plans, today))
        idx, plan = select_plan_for_charts(plans, today)
        self.assertEqual(idx, 1)
        self.assertEqual(plan["name"], "Past B")

    def test_attach_plan_targets_joins_by_period_key(self):
        comparison = plan_vs_actual_by_week(self._plan(), self._runs())
        period_df = pd.DataFrame(
            {
                "period_key": ["2026-37", "2026-38", "2026-39"],
                "period_label": ["a", "b", "c"],
                "total_miles": [1.0, 16.5, 5.0],
                "total_elevation_ft": [10.0, 350.0, 400.0],
            }
        )
        self.assertTrue(plan_targets_overlap_periods(comparison, period_df))
        out = attach_plan_targets_to_periods(period_df, comparison)
        self.assertTrue(pd.isna(out.iloc[0]["plan_miles"]))
        self.assertTrue(pd.isna(out.iloc[0]["plan_name"]))
        self.assertTrue(pd.isna(out.iloc[0]["plan_week"]))
        self.assertAlmostEqual(float(out.iloc[1]["plan_miles"]), 17.8)
        self.assertEqual(out.iloc[1]["plan_name"], "Sample")
        self.assertEqual(int(out.iloc[1]["plan_week"]), 1)
        self.assertAlmostEqual(float(out.iloc[2]["plan_miles"]), 12.0)
        self.assertEqual(out.iloc[2]["plan_name"], "Sample")
        self.assertEqual(int(out.iloc[2]["plan_week"]), 2)
        self.assertTrue(pd.isna(out.iloc[1]["plan_elevation_ft"]))
        self.assertAlmostEqual(float(out.iloc[2]["plan_elevation_ft"]), 800.0)

    def test_plan_targets_no_overlap_with_unrelated_window(self):
        comparison = plan_vs_actual_by_week(self._plan(), self._runs())
        period_df = pd.DataFrame(
            {
                "period_key": ["2026-01", "2026-02"],
                "total_miles": [1.0, 2.0],
            }
        )
        self.assertFalse(plan_targets_overlap_periods(comparison, period_df))

    def test_all_plans_attach_disjoint_weeks(self):
        plans = [
            {
                "name": "Early",
                "weeks": [
                    {
                        "week_start": pd.Timestamp("2026-09-14", tz="UTC"),
                        "total_miles": 10.0,
                        "total_elevation_ft": 100.0,
                        "sessions": [],
                    }
                ],
            },
            {
                "name": "Late",
                "weeks": [
                    {
                        "week_start": pd.Timestamp("2026-11-30", tz="UTC"),
                        "total_miles": 20.0,
                        "total_elevation_ft": 200.0,
                        "sessions": [],
                    }
                ],
            },
        ]
        comparison = plan_vs_actual_all_plans(plans, pd.DataFrame())
        self.assertEqual(len(comparison), 2)
        self.assertEqual(set(comparison["period_key"]), {"2026-38", "2026-49"})
        period_df = pd.DataFrame(
            {
                "period_key": ["2026-38", "2026-40", "2026-49"],
                "total_miles": [1.0, 2.0, 3.0],
            }
        )
        self.assertTrue(plan_targets_overlap_periods(comparison, period_df))
        out = attach_plan_targets_to_periods(period_df, comparison)
        self.assertAlmostEqual(float(out.iloc[0]["plan_miles"]), 10.0)
        self.assertEqual(out.iloc[0]["plan_name"], "Early")
        self.assertEqual(int(out.iloc[0]["plan_week"]), 1)
        self.assertTrue(pd.isna(out.iloc[1]["plan_miles"]))
        self.assertAlmostEqual(float(out.iloc[2]["plan_miles"]), 20.0)
        self.assertEqual(out.iloc[2]["plan_name"], "Late")
        self.assertEqual(int(out.iloc[2]["plan_week"]), 1)

    def test_all_plans_attach_overlapping_week_sums_and_joins_names(self):
        plans = [
            {
                "name": "Plan A",
                "weeks": [
                    {
                        "week_start": pd.Timestamp("2026-09-14", tz="UTC"),
                        "total_miles": 10.0,
                        "total_elevation_ft": 100.0,
                        "sessions": [],
                    }
                ],
            },
            {
                "name": "Plan B",
                "weeks": [
                    {
                        "week_start": pd.Timestamp("2026-09-14", tz="UTC"),
                        "total_miles": 5.0,
                        "total_elevation_ft": None,
                        "sessions": [],
                    }
                ],
            },
        ]
        comparison = plan_vs_actual_all_plans(plans, pd.DataFrame())
        self.assertEqual(len(comparison), 2)
        self.assertEqual(comparison["period_key"].tolist(), ["2026-38", "2026-38"])
        period_df = pd.DataFrame(
            {
                "period_key": ["2026-38"],
                "total_miles": [1.0],
            }
        )
        out = attach_plan_targets_to_periods(period_df, comparison)
        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(float(out.iloc[0]["plan_miles"]), 15.0)
        self.assertAlmostEqual(float(out.iloc[0]["plan_elevation_ft"]), 100.0)
        self.assertEqual(
            out.iloc[0]["plan_name"], "Plan A · Week 1 / Plan B · Week 1"
        )
        self.assertTrue(pd.isna(out.iloc[0]["plan_week"]))

    def test_attach_empty_comparison_adds_nan_plan_columns(self):
        period_df = pd.DataFrame(
            {
                "period_key": ["2026-38"],
                "total_miles": [10.0],
            }
        )
        out = attach_plan_targets_to_periods(period_df, pd.DataFrame())
        self.assertTrue(pd.isna(out.iloc[0]["plan_miles"]))
        self.assertTrue(pd.isna(out.iloc[0]["plan_elevation_ft"]))
        self.assertTrue(pd.isna(out.iloc[0]["plan_name"]))
        self.assertTrue(pd.isna(out.iloc[0]["plan_week"]))


class PlanZoomWindowTests(unittest.TestCase):
    """Zoom-to-plan window helper and session-state sync."""

    def _plan(self) -> dict[str, object]:
        # Wednesday start → Week grain aligns to prior Monday (2026-09-14).
        return {
            "name": "Sample",
            "start_date": pd.Timestamp("2026-09-16", tz="UTC"),
            "end_date": pd.Timestamp("2027-04-04", tz="UTC"),
            "weeks": [],
        }

    def test_period_window_for_plan_aligns_week(self):
        as_of = pd.Timestamp("2026-09-14T12:00:00Z")
        plan_end = pd.Timestamp("2027-04-04", tz="UTC")
        window = period_window_for_plan(
            "Week",
            self._plan(),
            as_of=as_of,
            max_end=plan_end,
        )
        self.assertIsNotNone(window)
        assert window is not None
        self.assertEqual(
            window.start, align_to_period_start("Week", self._plan()["start_date"])
        )
        self.assertEqual(
            window.end, align_to_period_start("Week", self._plan()["end_date"])
        )

    def test_period_window_for_plan_missing_dates(self):
        as_of = pd.Timestamp("2026-09-14T12:00:00Z")
        self.assertIsNone(
            period_window_for_plan(
                "Week",
                {"name": "Empty", "start_date": None, "end_date": None},
                as_of=as_of,
            )
        )

    def test_period_window_widget_values_week_and_year(self):
        week = PeriodWindow(
            start=pd.Timestamp("2026-09-14", tz="UTC"),
            end=pd.Timestamp("2026-11-30", tz="UTC"),
        )
        start, end = period_window_widget_values("Week", week)
        self.assertEqual(start, week.start.date())
        self.assertEqual(end, week.end.date())

        year = PeriodWindow(
            start=pd.Timestamp("2024-01-01", tz="UTC"),
            end=pd.Timestamp("2026-01-01", tz="UTC"),
        )
        y_start, y_end = period_window_widget_values("Year", year)
        self.assertEqual((y_start, y_end), (2024, 2026))

    def test_sync_applies_plan_then_restores_defaults_on_none(self):
        as_of = pd.Timestamp("2026-09-14T12:00:00Z")
        plan = self._plan()
        plan_end = plan["end_date"]
        assert isinstance(plan_end, pd.Timestamp)
        state: dict[str, object] = {}

        # Initial None: do not write Start/End (page defaults apply on load).
        sync_training_plan_zoom_window(
            state,
            selected=PLAN_ZOOM_NONE,
            grain="Week",
            plans=[plan],
            as_of=as_of,
            max_end=plan_end,
        )
        self.assertNotIn("training_period_start_Week", state)
        self.assertEqual(state["training_plan_zoom_prev"], PLAN_ZOOM_NONE)

        # Select plan → write aligned plan window.
        sync_training_plan_zoom_window(
            state,
            selected="Sample",
            grain="Week",
            plans=[plan],
            as_of=as_of,
            max_end=plan_end,
        )
        expected = period_window_for_plan(
            "Week", plan, as_of=as_of, max_end=plan_end
        )
        assert expected is not None
        self.assertEqual(
            state["training_period_start_Week"], expected.start.date()
        )
        self.assertEqual(state["training_period_end_Week"], expected.end.date())
        self.assertEqual(state["training_plan_zoom_prev"], "Sample")

        # Back to None → restore original default window (not prior plan).
        sync_training_plan_zoom_window(
            state,
            selected=PLAN_ZOOM_NONE,
            grain="Week",
            plans=[plan],
            as_of=as_of,
            max_end=plan_end,
        )
        defaults = default_period_bounds("Week", as_of)
        self.assertEqual(
            state["training_period_start_Week"], defaults.start.date()
        )
        self.assertEqual(state["training_period_end_Week"], defaults.end.date())
        self.assertEqual(state["training_plan_zoom_prev"], PLAN_ZOOM_NONE)

    def test_sync_reapplies_plan_when_grain_changes(self):
        as_of = pd.Timestamp("2026-09-14T12:00:00Z")
        plan = self._plan()
        plan_end = plan["end_date"]
        assert isinstance(plan_end, pd.Timestamp)
        state: dict[str, object] = {
            "training_plan_zoom_prev": "Sample",
            "training_plan_zoom_grain": "Week",
        }
        sync_training_plan_zoom_window(
            state,
            selected="Sample",
            grain="Month",
            plans=[plan],
            as_of=as_of,
            max_end=plan_end,
        )
        expected = period_window_for_plan(
            "Month", plan, as_of=as_of, max_end=plan_end
        )
        assert expected is not None
        self.assertEqual(
            state["training_period_start_Month"], expected.start.date()
        )
        self.assertEqual(state["training_period_end_Month"], expected.end.date())
        self.assertEqual(state["training_plan_zoom_grain"], "Month")


if __name__ == "__main__":
    unittest.main()
