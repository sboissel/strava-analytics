"""Tests for training plan CSV parsing and week helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from dashboard.data import (
    current_plan_week_index,
    default_expanded_plan_index,
    default_expanded_plan_week_index,
    is_plan_race_session,
    load_training_plans,
    parse_plan_header_name,
    parse_plan_miles,
    parse_training_plan_file,
    plan_focus_session_date,
    plan_week_expander_label,
    plan_week_index_for_date,
    plan_week_totals,
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


if __name__ == "__main__":
    unittest.main()
