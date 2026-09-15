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
    format_weekday_short,
    attach_plan_targets_to_periods,
    actual_shoe_mileage,
    actual_shoe_mileages,
    current_plan_week_index,
    default_expanded_plan_index,
    default_expanded_plan_week_index,
    default_period_bounds,
    estimated_shoe_mileage,
    estimated_shoe_mileages,
    future_planned_shoe_miles,
    is_plan_race_session,
    load_training_plans,
    lookup_shoe_miles,
    normalize_shoe_label,
    parse_plan_elevation,
    parse_plan_header_name,
    parse_plan_miles,
    parse_plan_notes,
    parse_plan_shoes,
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
    shoe_miles_for_wear_flag,
    shoes_labels_match,
    sync_training_plan_zoom_window,
    training_plans_max_end,
)
from dashboard.theme import (
    GLOBAL_CSS,
    MUTED,
    SHOE_MILEAGE_GOAL,
    SHOE_WEAR_PREPARE_MILES,
    TRAINING_PLAN_RACE_TEXT,
    shoe_wear_band,
)
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

    def test_parse_plan_shoes_direct_and_legacy_blank_column(self):
        self.assertEqual(
            parse_plan_shoes({"shoes": "Pegasus Trail 5", "": ""}),
            "Pegasus Trail 5",
        )
        self.assertEqual(
            parse_plan_shoes({"shoes": "", "": "Hoka Mach 7"}),
            "Hoka Mach 7",
        )
        self.assertIsNone(parse_plan_shoes({"shoes": "", "": ""}))
        self.assertIsNone(parse_plan_shoes({}))

    def test_parse_plan_notes(self):
        self.assertEqual(
            parse_plan_notes({"notes": "  Trail, easy  effort\n"}),
            "Trail, easy effort",
        )
        self.assertIsNone(parse_plan_notes({"notes": ""}))
        self.assertIsNone(parse_plan_notes({"notes": None}))
        self.assertIsNone(parse_plan_notes({}))


class EstimatedShoeMileageTests(unittest.TestCase):
    """Actual + future planned miles for training-plan shoe tooltips."""

    def _gear(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "gear_id": "g1",
                    "name": "Nike Pegasus Trail 5",
                    "type": "Trail",
                    "mileage": 200.0,
                    "status": "active",
                },
                {
                    "gear_id": "g2",
                    "name": "Hoka Mach 7",
                    "type": "Speed",
                    "mileage": 50.0,
                    "status": "active",
                },
            ]
        )

    def _plans(self) -> list[dict[str, object]]:
        return [
            {
                "name": "A",
                "weeks": [
                    {
                        "sessions": [
                            {
                                "date": pd.Timestamp("2026-09-10", tz="UTC"),
                                "shoes": "Pegasus Trail 5",
                                "miles": 8.0,
                            },
                            {
                                "date": pd.Timestamp("2026-09-20", tz="UTC"),
                                "shoes": "Pegasus Trail 5",
                                "miles": 10.0,
                            },
                            {
                                "date": pd.Timestamp("2026-09-22", tz="UTC"),
                                "shoes": "Hoka Mach 7",
                                "miles": 4.0,
                            },
                            {
                                "date": pd.Timestamp("2026-09-24", tz="UTC"),
                                "shoes": "Vaporfly",
                                "miles": 13.1,
                            },
                            {
                                "date": pd.Timestamp("2026-09-25", tz="UTC"),
                                "shoes": None,
                                "miles": 3.0,
                            },
                        ]
                    }
                ],
            },
            {
                "name": "B",
                "weeks": [
                    {
                        "sessions": [
                            {
                                "date": pd.Timestamp("2026-10-01", tz="UTC"),
                                "shoes": "Nike Pegasus Trail 5",
                                "miles": 6.0,
                            },
                        ]
                    }
                ],
            },
        ]

    def test_shoes_labels_match_case_and_nike_prefix(self):
        self.assertTrue(shoes_labels_match("Pegasus Trail 5", "Nike Pegasus Trail 5"))
        self.assertTrue(shoes_labels_match("hoka mach 7", "Hoka Mach 7"))
        self.assertFalse(shoes_labels_match("Vaporfly", "Nike ZoomX"))
        self.assertFalse(shoes_labels_match("", "Hoka Mach 7"))
        # Short / mid-token suffixes must not over-match.
        self.assertFalse(shoes_labels_match("5", "Pegasus Trail 5"))
        self.assertFalse(shoes_labels_match("Trail 5", "Pegasus Trail 5"))
        self.assertFalse(shoes_labels_match("Pegasus 42", "Pegasus Trail 5"))

    def test_normalize_treats_hyphen_placeholder_as_blank(self):
        self.assertIsNone(normalize_shoe_label("-"))
        self.assertIsNone(normalize_shoe_label("—"))
        self.assertEqual(normalize_shoe_label("Pegasus 42"), "Pegasus 42")

    def test_actual_matches_gear_via_suffix(self):
        self.assertEqual(
            actual_shoe_mileage("Pegasus Trail 5", self._gear()), 200.0
        )
        self.assertEqual(actual_shoe_mileage("Hoka Mach 7", self._gear()), 50.0)
        self.assertEqual(actual_shoe_mileage("Vaporfly", self._gear()), 0.0)

    def test_future_planned_sums_matching_shoes_after_as_of(self):
        as_of = pd.Timestamp("2026-09-15", tz="UTC")
        # Past 8 mi excluded; 10 (plan A shorthand) + 6 (plan B full name)
        # when both plans are passed to the helper.
        self.assertEqual(
            future_planned_shoe_miles("Pegasus Trail 5", self._plans(), as_of),
            16.0,
        )
        self.assertEqual(
            future_planned_shoe_miles("Hoka Mach 7", self._plans(), as_of),
            4.0,
        )

    def test_future_planned_sums_subset_when_one_plan_passed(self):
        """Helper filters to whatever plans are passed; UI passes all loaded."""
        as_of = pd.Timestamp("2026-09-15", tz="UTC")
        plan_a = [self._plans()[0]]
        self.assertEqual(
            future_planned_shoe_miles("Pegasus Trail 5", plan_a, as_of),
            10.0,
        )
        self.assertEqual(
            estimated_shoe_mileage(
                "Pegasus Trail 5", plan_a, self._gear(), as_of
            ),
            210.0,
        )

    def test_estimated_total_actual_plus_future(self):
        as_of = pd.Timestamp("2026-09-15", tz="UTC")
        self.assertEqual(
            estimated_shoe_mileage(
                "Pegasus Trail 5", self._plans(), self._gear(), as_of
            ),
            216.0,
        )
        self.assertEqual(
            estimated_shoe_mileage(
                "Vaporfly", self._plans(), self._gear(), as_of
            ),
            13.1,
        )
        self.assertIsNone(
            estimated_shoe_mileage(None, self._plans(), self._gear(), as_of)
        )

    def test_estimated_shoe_mileages_map(self):
        as_of = pd.Timestamp("2026-09-15", tz="UTC")
        estimates = estimated_shoe_mileages(self._plans(), self._gear(), as_of)
        self.assertEqual(estimates["Pegasus Trail 5"], 216.0)
        self.assertEqual(estimates["Hoka Mach 7"], 54.0)
        self.assertEqual(estimates["Vaporfly"], 13.1)
        # Full Nike name also present as a distinct session label.
        self.assertEqual(estimates["Nike Pegasus Trail 5"], 216.0)

    def test_cumulative_estimate_through_hovered_friday(self):
        """Hover estimate grows by each planned session, not end-of-plan total.

        actual 237 + this Friday 10 → 247; next Friday +10 → 257. Miles after
        the hovered date are excluded.
        """
        as_of = pd.Timestamp("2026-09-15", tz="UTC")
        friday_a = pd.Timestamp("2026-09-18", tz="UTC")
        friday_b = pd.Timestamp("2026-09-25", tz="UTC")
        later = pd.Timestamp("2026-10-02", tz="UTC")
        gear = pd.DataFrame(
            [
                {
                    "gear_id": "g33031350",
                    "name": "Nike Pegasus Trail 5",
                    "type": "Trail",
                    "mileage": 237.0,
                    "status": "active",
                }
            ]
        )
        plan = {
            "name": "November halves",
            "weeks": [
                {
                    "sessions": [
                        {
                            "date": friday_a,
                            "shoes": "Pegasus Trail 5",
                            "miles": 10.0,
                        },
                        {
                            "date": friday_b,
                            "shoes": "Pegasus Trail 5",
                            "miles": 10.0,
                        },
                        {
                            "date": later,
                            "shoes": "Pegasus Trail 5",
                            "miles": 11.0,
                        },
                    ]
                }
            ],
        }
        first = estimated_shoe_mileage(
            "Pegasus Trail 5", [plan], gear, as_of, through_date=friday_a
        )
        second = estimated_shoe_mileage(
            "Pegasus Trail 5", [plan], gear, as_of, through_date=friday_b
        )
        end_of_plan = estimated_shoe_mileage(
            "Pegasus Trail 5", [plan], gear, as_of
        )
        self.assertAlmostEqual(first, 247.0)
        self.assertAlmostEqual(second, 257.0)
        self.assertAlmostEqual(end_of_plan, 268.0)
        self.assertEqual(
            future_planned_shoe_miles(
                "Pegasus Trail 5", [plan], as_of, through_date=friday_a
            ),
            10.0,
        )
        self.assertEqual(
            future_planned_shoe_miles(
                "Pegasus Trail 5", [plan], as_of, through_date=friday_b
            ),
            20.0,
        )

    def test_estimates_accumulate_across_consecutive_plans(self):
        """November + Sierra are back-to-back: mileage continues across both.

        Hover on any plan uses all loaded plans with through_date=session:
        actual + Σ planned miles on that shoe where today < date ≤ D.
        Nov Friday stays 247 (Sierra dates are after Friday). A Sierra
        December session includes remaining Nov miles through D plus Sierra
        miles through D — not Nov-only scoping.
        """
        as_of = pd.Timestamp("2026-09-15", tz="UTC")
        nov_friday = pd.Timestamp("2026-09-18", tz="UTC")
        sierra_dec = pd.Timestamp("2026-12-01", tz="UTC")
        gear = pd.DataFrame(
            [
                {
                    "gear_id": "g33031350",
                    "name": "Nike Pegasus Trail 5",
                    "type": "Trail",
                    "mileage": 237.0,
                    "status": "active",
                }
            ]
        )
        november = {
            "name": "November halves",
            "weeks": [
                {
                    "sessions": [
                        {
                            "date": pd.Timestamp("2026-09-14", tz="UTC"),
                            "shoes": "Pegasus Trail 5",
                            "miles": 4.0,
                        },
                        {
                            "date": nov_friday,
                            "shoes": "Pegasus Trail 5",
                            "miles": 10.0,
                        },
                        {
                            "date": pd.Timestamp("2026-10-02", tz="UTC"),
                            "shoes": "Pegasus Trail 5",
                            "miles": 11.0,
                        },
                        {
                            "date": pd.Timestamp("2026-11-27", tz="UTC"),
                            "shoes": "Pegasus Trail 5",
                            "miles": 3.0,
                        },
                    ]
                }
            ],
        }
        sierra = {
            "name": "Sierra Nevada Half",
            "weeks": [
                {
                    "sessions": [
                        {
                            "date": pd.Timestamp("2026-11-30", tz="UTC"),
                            "shoes": "Pegasus Trail 5",
                            "miles": 2.0,
                        },
                        {
                            "date": sierra_dec,
                            "shoes": "Pegasus Trail 5",
                            "miles": 8.0,
                        },
                        {
                            "date": pd.Timestamp("2027-02-13", tz="UTC"),
                            "shoes": "Pegasus Trail 5",
                            "miles": 14.0,
                        },
                    ]
                }
            ],
        }
        both = [november, sierra]
        # Nov Friday with all plans: 237 + 10 = 247 (Sierra still in the future).
        this_friday = estimated_shoe_mileage(
            "Pegasus Trail 5", both, gear, as_of, through_date=nov_friday
        )
        self.assertAlmostEqual(this_friday, 247.0)
        # Same Friday result whether or not Sierra is in the list — through_date
        # already excludes later blocks.
        nov_only_friday = estimated_shoe_mileage(
            "Pegasus Trail 5",
            [november],
            gear,
            as_of,
            through_date=nov_friday,
        )
        self.assertAlmostEqual(nov_only_friday, 247.0)
        # Sierra Dec 1: 237 + Nov remaining after today through D (10+11+3)
        # + Sierra through D (2+8) = 271.
        sierra_day = estimated_shoe_mileage(
            "Pegasus Trail 5", both, gear, as_of, through_date=sierra_dec
        )
        self.assertAlmostEqual(sierra_day, 271.0)
        # Sierra-only scoping would miss Nov future miles (237 + 2 + 8 = 247).
        sierra_only = estimated_shoe_mileage(
            "Pegasus Trail 5",
            [sierra],
            gear,
            as_of,
            through_date=sierra_dec,
        )
        self.assertAlmostEqual(sierra_only, 247.0)
        self.assertGreater(sierra_day, sierra_only)
        # End-of-all-plans (no through_date) still sums everything remaining.
        end_both = estimated_shoe_mileage(
            "Pegasus Trail 5", both, gear, as_of
        )
        self.assertAlmostEqual(end_both, 237.0 + 10 + 11 + 3 + 2 + 8 + 14)
        self.assertAlmostEqual(
            future_planned_shoe_miles(
                "Pegasus Trail 5", both, as_of, through_date=sierra_dec
            ),
            34.0,
        )

    def test_estimated_shoe_mileages_respects_through_date(self):
        as_of = pd.Timestamp("2026-09-15", tz="UTC")
        friday = pd.Timestamp("2026-09-18", tz="UTC")
        gear = pd.DataFrame(
            [
                {
                    "gear_id": "g1",
                    "name": "Nike Pegasus Trail 5",
                    "type": "Trail",
                    "mileage": 237.0,
                    "status": "active",
                }
            ]
        )
        plan = {
            "name": "A",
            "weeks": [
                {
                    "sessions": [
                        {
                            "date": friday,
                            "shoes": "Pegasus Trail 5",
                            "miles": 10.0,
                        },
                        {
                            "date": pd.Timestamp("2026-09-25", tz="UTC"),
                            "shoes": "Pegasus Trail 5",
                            "miles": 10.0,
                        },
                    ]
                }
            ],
        }
        capped = estimated_shoe_mileages(
            [plan], gear, as_of, through_date=friday
        )
        uncapped = estimated_shoe_mileages([plan], gear, as_of)
        self.assertAlmostEqual(capped["Pegasus Trail 5"], 247.0)
        self.assertAlmostEqual(uncapped["Pegasus Trail 5"], 257.0)

    def test_actual_shoe_mileages_and_lookup_soft_match(self):
        gear = self._gear()
        actuals = actual_shoe_mileages(self._plans(), gear)
        self.assertEqual(actuals["Pegasus Trail 5"], 200.0)
        self.assertEqual(actuals["Hoka Mach 7"], 50.0)
        self.assertEqual(actuals["Vaporfly"], 0.0)
        self.assertEqual(
            lookup_shoe_miles("Nike Pegasus Trail 5", actuals), 200.0
        )
        self.assertIsNone(lookup_shoe_miles("Unknown", actuals))
        self.assertIsNone(lookup_shoe_miles("-", actuals))


class ShoeWearBandTests(unittest.TestCase):
    """Prepare / limit bands for gauge wash and shoe wear tooltips."""

    def test_bands_prepare_half_open_limit_inclusive(self):
        self.assertIsNone(shoe_wear_band(349.9))
        self.assertEqual(shoe_wear_band(350.0), "prepare")
        self.assertEqual(shoe_wear_band(399.9), "prepare")
        self.assertEqual(shoe_wear_band(400.0), "limit")
        self.assertEqual(shoe_wear_band(500.0), "limit")
        self.assertIsNone(shoe_wear_band(None))
        self.assertEqual(SHOE_WEAR_PREPARE_MILES, 350.0)
        self.assertEqual(SHOE_MILEAGE_GOAL, 400.0)

    def test_wear_flag_miles_prefer_estimate_for_future(self):
        as_of = pd.Timestamp("2026-09-15", tz="UTC")
        future = pd.Timestamp("2026-09-18", tz="UTC")
        past = pd.Timestamp("2026-09-14", tz="UTC")
        estimates = {"Pegasus Trail 5": 360.0}
        actuals = {"Pegasus Trail 5": 237.0}
        self.assertEqual(
            shoe_miles_for_wear_flag(
                "Pegasus Trail 5",
                session_day=future,
                today=as_of,
                shoe_estimates=estimates,
                shoe_actuals=actuals,
            ),
            360.0,
        )
        self.assertEqual(
            shoe_miles_for_wear_flag(
                "Pegasus Trail 5",
                session_day=past,
                today=as_of,
                shoe_estimates=estimates,
                shoe_actuals=actuals,
            ),
            237.0,
        )
        self.assertEqual(
            shoe_miles_for_wear_flag(
                "Pegasus Trail 5",
                session_day=as_of,
                today=as_of,
                shoe_estimates=estimates,
                shoe_actuals=actuals,
            ),
            237.0,
        )

    def test_wear_flag_prefers_estimated_miles_over_map(self):
        as_of = pd.Timestamp("2026-09-15", tz="UTC")
        future = pd.Timestamp("2026-09-18", tz="UTC")
        self.assertEqual(
            shoe_miles_for_wear_flag(
                "Pegasus Trail 5",
                session_day=future,
                today=as_of,
                estimated_miles=247.0,
                shoe_estimates={"Pegasus Trail 5": 999.0},
                shoe_actuals={"Pegasus Trail 5": 237.0},
            ),
            247.0,
        )


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
        nov_races = [
            s
            for week in nov["weeks"]
            for s in week["sessions"]
            if s["is_race"]
        ]
        self.assertGreaterEqual(len(nov_races), 1)
        self.assertTrue(
            any(
                "12.5K race" in str(s["session"]) for s in nov_races
            ),
            msg="November halves should include the 12.5K race session",
        )
        sierra = next(p for p in plans if p["name"] == "Sierra Nevada Half")
        sierra_races = [
            s
            for week in sierra["weeks"]
            for s in week["sessions"]
            if s["is_race"]
        ]
        self.assertEqual(len(sierra_races), 1)
        self.assertEqual(sierra_races[0]["session"], "Sierra Nevada Half")

    def test_november_halves_parses_shoes_from_csv(self):
        repo_plans = Path(__file__).resolve().parents[2] / "data" / "plans"
        nov = parse_training_plan_file(repo_plans / "november_halves.csv")
        first = nov["weeks"][0]["sessions"][0]
        self.assertEqual(first["session"], "Easy run")
        self.assertEqual(first["shoes"], "Pegasus Trail 5")
        # Shoe column alias ``Shoe`` → shoes; mid-plan Hoka session.
        by_date = {
            s["date"]: s
            for week in nov["weeks"]
            for s in week["sessions"]
        }
        hoka = by_date[pd.Timestamp("2026-09-16", tz="UTC")]
        self.assertEqual(hoka["session"], "6x60sec hill reps")
        self.assertEqual(hoka["shoes"], "Hoka Mach 7")
        vapor = by_date[pd.Timestamp("2026-09-21", tz="UTC")]
        self.assertEqual(vapor["shoes"], "Vaporfly")

    def test_november_halves_parses_session_notes(self):
        repo_plans = Path(__file__).resolve().parents[2] / "data" / "plans"
        nov = parse_training_plan_file(repo_plans / "november_halves.csv")
        by_date = {
            s["date"]: s
            for week in nov["weeks"]
            for s in week["sessions"]
        }
        easy = by_date[pd.Timestamp("2026-07-27", tz="UTC")]
        self.assertIsNone(easy.get("notes"))
        hills = by_date[pd.Timestamp("2026-07-29", tz="UTC")]
        self.assertEqual(
            hills["notes"],
            "10 min warm-up, jog/walk recovery between reps, 10 min cooldown",
        )
        long_run = by_date[pd.Timestamp("2026-07-31", tz="UTC")]
        self.assertEqual(long_run["notes"], "Trail, easy/comfortable effort")


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

    def test_focus_none_before_plan_starts(self):
        # Before week 1: do not treat the first session as focus/current.
        today = pd.Timestamp("2026-09-01", tz="UTC")
        self.assertIsNone(plan_focus_session_date(self._weeks(), today))
        self.assertIsNone(current_plan_week_index(self._weeks(), today))

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
            today=pd.Timestamp("2026-11-05", tz="UTC"),
        )
        self.assertIn("training-plan-session-row is-race", html)
        self.assertIn("training-plan-race-badge", html)
        self.assertIn("Race day", html)
        self.assertIn("Easy run", html)
        # Race day is the next upcoming session from Nov 5 (same plan week).
        self.assertIn("training-plan-session-row is-race is-next", html)

    def test_race_row_text_color_applies_to_whole_row(self):
        """Race cue is muted-gold text on every cell, not only the session name."""
        self.assertEqual(TRAINING_PLAN_RACE_TEXT, "#A67C2D")
        # Row + direct cell spans (Day/Date/Session/Shoes/Miles/Elev) share race gold.
        # Cell-level rules (.training-plan-dow MUTED, .training-plan-shoes INK) must not win.
        self.assertIn(
            ".training-plan-session-row.is-race,\n"
            "  .training-plan-session-row.is-race > span {\n"
            f"    color: {TRAINING_PLAN_RACE_TEXT};",
            GLOBAL_CSS,
        )
        # Session name stays bold; color comes from the row/span rule above.
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
        # Week summary rows must not pick up race gold (different class, no is-race).
        self.assertNotIn(".training-plan-week-sum.is-race", GLOBAL_CSS)
        self.assertNotIn(
            f".training-plan-week-sum {{\n    color: {TRAINING_PLAN_RACE_TEXT}",
            GLOBAL_CSS,
        )

    def test_training_plans_section_title_matches_panel_label(self):
        """Outer Training plans expander uses the same chrome as .panel-label (RACES)."""
        section_css = GLOBAL_CSS.split(
            "/* Training plans section title: match .panel-label", 1
        )[1].split("/* Plan name expanders:", 1)[0]
        self.assertIn('.st-key-training_plans [data-testid="stExpander"] summary p', section_css)
        self.assertIn("font-size: 0.72rem !important;", section_css)
        self.assertIn("font-weight: 600 !important;", section_css)
        self.assertIn("letter-spacing: 0.08em !important;", section_css)
        self.assertIn("text-transform: uppercase !important;", section_css)
        self.assertIn(f"color: {MUTED} !important;", section_css)

    def test_training_plans_section_expander_open_by_default(self):
        """Outer Training plans expander starts expanded so this week's plan is visible."""
        import inspect

        from dashboard import ui as ui_mod

        source = inspect.getsource(ui_mod.render_training_plans)
        self.assertIn('st.expander(\n        "Training plans",\n        expanded=True,', source)
        self.assertNotIn('st.expander(\n        "Training plans",\n        expanded=False,', source)
        # Focus-week-only remains the default session state.
        self.assertIn(
            "st.session_state.training_plan_show_all_weeks = False",
            source,
        )
        # Week-only mode skips plans with no calendar week for today.
        self.assertIn("if current_plan_week_index(weeks, as_of) is None:", source)
        self.assertIn("No training plan covers this week.", source)
        # Consecutive plans share shoe estimates (do not scope to [plan]).
        self.assertIn("shoe_plans=plans if gear is not None else None", source)
        self.assertNotIn("scoped_plans", source)

    def test_render_hides_plans_without_current_week_in_focus_mode(self):
        """Focus-week mode omits future plans; full-plan mode shows them."""
        import contextlib
        from unittest import mock

        from dashboard import ui as ui_mod

        plans = [
            {
                "name": "November halves",
                "weeks": [
                    {
                        "week_start": pd.Timestamp("2026-09-14", tz="UTC"),
                        "week_label": "Sep 14, 2026 - Sep 20, 2026",
                        "total_miles": 10.0,
                        "total_elevation_ft": None,
                        "sessions": [
                            {
                                "date": pd.Timestamp("2026-09-15", tz="UTC"),
                                "session": "Easy",
                                "miles": 5.0,
                                "miles_label": "5",
                                "elevation_ft": None,
                                "shoes": "",
                                "notes": "",
                            }
                        ],
                    }
                ],
            },
            {
                "name": "Sierra Nevada Half",
                "weeks": [
                    {
                        "week_start": pd.Timestamp("2026-11-30", tz="UTC"),
                        "week_label": "Nov 30, 2026 - Dec 6, 2026",
                        "total_miles": 8.0,
                        "total_elevation_ft": None,
                        "sessions": [
                            {
                                "date": pd.Timestamp("2026-11-30", tz="UTC"),
                                "session": "Easy trail",
                                "miles": 4.0,
                                "miles_label": "4",
                                "elevation_ft": None,
                                "shoes": "",
                                "notes": "",
                            }
                        ],
                    }
                ],
            },
        ]
        today = pd.Timestamp("2026-09-15", tz="UTC")

        class _Session(dict):
            def __getattr__(self, name: str):
                try:
                    return self[name]
                except KeyError as exc:
                    raise AttributeError(name) from exc

            def __setattr__(self, name: str, value: object) -> None:
                self[name] = value

        def _run(*, show_all: bool) -> list[str]:
            titles: list[str] = []
            fake_st = mock.MagicMock()
            fake_st.session_state = _Session()
            fake_st.session_state.training_plan_show_all_weeks = show_all
            fake_st.button.return_value = False

            @contextlib.contextmanager
            def _expander(title, *args, **kwargs):
                titles.append(title)
                yield

            fake_st.expander.side_effect = _expander
            with (
                mock.patch.dict("sys.modules", {"streamlit": fake_st}),
                mock.patch.object(ui_mod, "load_gear", return_value=None),
            ):
                ui_mod.render_training_plans(plans, today=today)
            # Drop the outer section expander title.
            return [t for t in titles if t != "Training plans"]

        self.assertEqual(
            _run(show_all=False),
            ["November halves"],
        )
        self.assertEqual(
            _run(show_all=True),
            ["November halves", "Sierra Nevada Half"],
        )

    def test_render_focus_week_empty_state_when_no_plan_covers_today(self):
        """When no plan has today's week, show empty copy instead of expanders."""
        import contextlib
        from unittest import mock

        from dashboard import ui as ui_mod

        plans = [
            {
                "name": "Sierra Nevada Half",
                "weeks": [
                    {
                        "week_start": pd.Timestamp("2026-11-30", tz="UTC"),
                        "week_label": "Nov 30, 2026 - Dec 6, 2026",
                        "total_miles": 8.0,
                        "total_elevation_ft": None,
                        "sessions": [
                            {
                                "date": pd.Timestamp("2026-11-30", tz="UTC"),
                                "session": "Easy trail",
                                "miles": 4.0,
                                "miles_label": "4",
                                "elevation_ft": None,
                                "shoes": "",
                                "notes": "",
                            }
                        ],
                    }
                ],
            },
        ]
        today = pd.Timestamp("2026-09-15", tz="UTC")
        titles: list[str] = []
        markdowns: list[str] = []

        class _Session(dict):
            def __getattr__(self, name: str):
                try:
                    return self[name]
                except KeyError as exc:
                    raise AttributeError(name) from exc

            def __setattr__(self, name: str, value: object) -> None:
                self[name] = value

        fake_st = mock.MagicMock()
        fake_st.session_state = _Session()
        fake_st.session_state.training_plan_show_all_weeks = False
        fake_st.button.return_value = False

        @contextlib.contextmanager
        def _expander(title, *args, **kwargs):
            titles.append(title)
            yield

        def _markdown(html, **kwargs):
            markdowns.append(html)

        fake_st.expander.side_effect = _expander
        fake_st.markdown.side_effect = _markdown
        with (
            mock.patch.dict("sys.modules", {"streamlit": fake_st}),
            mock.patch.object(ui_mod, "load_gear", return_value=None),
        ):
            ui_mod.render_training_plans(plans, today=today)

        self.assertEqual(titles, ["Training plans"])
        self.assertTrue(
            any("No training plan covers this week." in m for m in markdowns)
        )

    def test_plan_expander_titles_use_race_session_block_weight(self):
        """Plan name expanders share the race-session bold (700) block weight."""
        self.assertIn("/* Plan name expanders:", GLOBAL_CSS)
        # Keep plan titles ink-colored — race gold stays on race session rows only.
        plan_title_css = GLOBAL_CSS.split("/* Plan name expanders:", 1)[1].split(
            ".training-plan-table-wrap", 1
        )[0]
        self.assertNotIn('.st-key-training_plans [data-testid="stExpander"] summary p', plan_title_css)
        self.assertIn(
            '[class*="st-key-training_plan_"] [data-testid="stExpander"] summary p',
            plan_title_css,
        )
        self.assertIn("font-weight: 700 !important;", plan_title_css)
        self.assertIn("text-transform: none !important;", plan_title_css)
        self.assertNotIn(TRAINING_PLAN_RACE_TEXT, plan_title_css)

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

    def test_plan_table_shoes_column(self):
        html = training_plan_table_html(
            [
                {
                    "week_label": "Sep 14, 2026 - Sep 20, 2026",
                    "week_start": pd.Timestamp("2026-09-14", tz="UTC"),
                    "total_miles": 7.8,
                    "total_elevation_ft": 400.0,
                    "sessions": [
                        {
                            "date": pd.Timestamp("2026-09-16", tz="UTC"),
                            "session": "Hill repeats",
                            "miles_label": "3.8",
                            "elevation_ft": 400,
                            "shoes": "Hoka Mach 7",
                            "is_race": False,
                        },
                    ],
                },
            ],
            expanded_week_index=0,
            today=pd.Timestamp("2026-09-01", tz="UTC"),
        )
        self.assertIn(">Shoes<", html)
        self.assertIn('class="training-plan-shoes">Hoka Mach 7<', html)
        self.assertIn("training-plan-week-shoes", html)
        self.assertIn(
            "minmax(5.5rem, 1.15fr) 4.5rem 5rem",
            GLOBAL_CSS,
        )

    def test_plan_table_shoes_tooltip_future_only(self):
        weeks = [
            {
                "week_label": "Sep 14, 2026 - Sep 20, 2026",
                "week_start": pd.Timestamp("2026-09-14", tz="UTC"),
                "total_miles": 17.8,
                "total_elevation_ft": None,
                "sessions": [
                    {
                        "date": pd.Timestamp("2026-09-14", tz="UTC"),
                        "session": "Past run",
                        "miles": 5.0,
                        "miles_label": "5",
                        "shoes": "Hoka Mach 7",
                        "is_race": False,
                    },
                    {
                        "date": pd.Timestamp("2026-09-15", tz="UTC"),
                        "session": "Today run",
                        "miles": 4.0,
                        "miles_label": "4",
                        "shoes": "Hoka Mach 7",
                        "is_race": False,
                    },
                    {
                        "date": pd.Timestamp("2026-09-16", tz="UTC"),
                        "session": "Future run",
                        "miles": 3.8,
                        "miles_label": "3.8",
                        "shoes": "Hoka Mach 7",
                        "is_race": False,
                    },
                    {
                        "date": pd.Timestamp("2026-09-17", tz="UTC"),
                        "session": "No shoes",
                        "miles": 5.0,
                        "miles_label": "5",
                        "shoes": None,
                        "is_race": False,
                    },
                ],
            },
        ]
        estimates = {"Hoka Mach 7": 54.0}
        html = training_plan_table_html(
            weeks,
            expanded_week_index=0,
            today=pd.Timestamp("2026-09-15", tz="UTC"),
            shoe_estimates=estimates,
        )
        self.assertIn("training-plan-cell--tip", html)
        self.assertIn(
            '<span class="kpi-tooltip" role="tooltip">Est. ~54 mi</span>',
            html,
        )
        # Past / today / empty shoes: no estimate tooltip on those cells.
        # Only one Est. tip for the future Hoka row (not in aria-label alone).
        self.assertEqual(
            html.count('<span class="kpi-tooltip" role="tooltip">Est. ~54 mi</span>'),
            1,
        )
        self.assertIn('class="training-plan-shoes">—<', html)
        self.assertIn("training-plan-cell--tip", GLOBAL_CSS)
        self.assertIn(
            ".training-plan-cell--tip:hover .kpi-tooltip",
            GLOBAL_CSS,
        )

    def test_plan_table_cumulative_estimates_increase_across_fridays(self):
        """Two future Fridays on the same shoe: Est. ~247 then Est. ~257.

        Passing the consecutive Sierra plan as well must not inflate Nov
        Friday hovers — through_date excludes later Sierra sessions.
        """
        as_of = pd.Timestamp("2026-09-15", tz="UTC")
        friday_a = pd.Timestamp("2026-09-18", tz="UTC")
        friday_b = pd.Timestamp("2026-09-25", tz="UTC")
        gear = pd.DataFrame(
            [
                {
                    "gear_id": "g33031350",
                    "name": "Nike Pegasus Trail 5",
                    "type": "Trail",
                    "mileage": 237.0,
                    "status": "active",
                }
            ]
        )
        november = {
            "name": "November halves",
            "weeks": [
                {
                    "week_label": "Sep 14, 2026 - Sep 27, 2026",
                    "week_start": pd.Timestamp("2026-09-14", tz="UTC"),
                    "total_miles": 20.0,
                    "total_elevation_ft": None,
                    "sessions": [
                        {
                            "date": friday_a,
                            "session": "This Friday",
                            "miles": 10.0,
                            "miles_label": "10",
                            "shoes": "Pegasus Trail 5",
                            "is_race": False,
                        },
                        {
                            "date": friday_b,
                            "session": "Next Friday",
                            "miles": 10.0,
                            "miles_label": "10",
                            "shoes": "Pegasus Trail 5",
                            "is_race": False,
                        },
                    ],
                }
            ],
        }
        sierra = {
            "name": "Sierra Nevada Half",
            "weeks": [
                {
                    "sessions": [
                        {
                            "date": pd.Timestamp("2026-12-01", tz="UTC"),
                            "shoes": "Pegasus Trail 5",
                            "miles": 8.0,
                        }
                    ]
                }
            ],
        }
        html = training_plan_table_html(
            november["weeks"],
            expanded_week_index=0,
            today=as_of,
            shoe_plans=[november, sierra],
            shoe_gear=gear,
        )
        self.assertIn(
            '<span class="kpi-tooltip" role="tooltip">Est. ~247 mi</span>',
            html,
        )
        self.assertIn(
            '<span class="kpi-tooltip" role="tooltip">Est. ~257 mi</span>',
            html,
        )
        # Must not show the same end-of-plan total on every future row.
        self.assertEqual(
            html.count(
                '<span class="kpi-tooltip" role="tooltip">Est. ~247 mi</span>'
            ),
            1,
        )
        self.assertEqual(
            html.count(
                '<span class="kpi-tooltip" role="tooltip">Est. ~257 mi</span>'
            ),
            1,
        )
        self.assertNotIn(
            '<span class="kpi-tooltip" role="tooltip">Est. ~268 mi</span>',
            html,
        )
        # Sierra miles must not appear on November Friday tooltips.
        self.assertNotIn("Est. ~265 mi", html)

    def test_plan_table_sierra_estimate_includes_november_future_miles(self):
        """Sierra hover includes Nov remaining miles on the same shoe through D."""
        as_of = pd.Timestamp("2026-09-15", tz="UTC")
        sierra_dec = pd.Timestamp("2026-12-01", tz="UTC")
        gear = pd.DataFrame(
            [
                {
                    "gear_id": "g33031350",
                    "name": "Nike Pegasus Trail 5",
                    "type": "Trail",
                    "mileage": 237.0,
                    "status": "active",
                }
            ]
        )
        november = {
            "name": "November halves",
            "weeks": [
                {
                    "sessions": [
                        {
                            "date": pd.Timestamp("2026-09-18", tz="UTC"),
                            "shoes": "Pegasus Trail 5",
                            "miles": 10.0,
                        },
                        {
                            "date": pd.Timestamp("2026-10-02", tz="UTC"),
                            "shoes": "Pegasus Trail 5",
                            "miles": 11.0,
                        },
                        {
                            "date": pd.Timestamp("2026-11-27", tz="UTC"),
                            "shoes": "Pegasus Trail 5",
                            "miles": 3.0,
                        },
                    ]
                }
            ],
        }
        sierra = {
            "name": "Sierra Nevada Half",
            "weeks": [
                {
                    "week_label": "Nov 30, 2026 - Dec 6, 2026",
                    "week_start": pd.Timestamp("2026-11-30", tz="UTC"),
                    "total_miles": 10.0,
                    "total_elevation_ft": None,
                    "sessions": [
                        {
                            "date": pd.Timestamp("2026-11-30", tz="UTC"),
                            "session": "Shakeout",
                            "miles": 2.0,
                            "miles_label": "2",
                            "shoes": "Pegasus Trail 5",
                            "is_race": False,
                        },
                        {
                            "date": sierra_dec,
                            "session": "Long run",
                            "miles": 8.0,
                            "miles_label": "8",
                            "shoes": "Pegasus Trail 5",
                            "is_race": False,
                        },
                    ],
                }
            ],
        }
        html = training_plan_table_html(
            sierra["weeks"],
            expanded_week_index=0,
            today=as_of,
            shoe_plans=[november, sierra],
            shoe_gear=gear,
        )
        # Nov 30: 237 + 10+11+3 + 2 = 263
        self.assertIn(
            '<span class="kpi-tooltip" role="tooltip">Est. ~263 mi</span>',
            html,
        )
        # Dec 1: 237 + 10+11+3 + 2+8 = 271
        self.assertIn(
            '<span class="kpi-tooltip" role="tooltip">Est. ~271 mi</span>',
            html,
        )
        # Sierra-only scoping would wrongly show 239 / 247.
        self.assertNotIn(
            '<span class="kpi-tooltip" role="tooltip">Est. ~239 mi</span>',
            html,
        )
        self.assertNotIn(
            '<span class="kpi-tooltip" role="tooltip">Est. ~247 mi</span>',
            html,
        )

    def test_plan_table_shoe_wear_colored_text_without_dots(self):
        weeks = [
            {
                "week_label": "Sep 14, 2026 - Sep 20, 2026",
                "week_start": pd.Timestamp("2026-09-14", tz="UTC"),
                "total_miles": 20.0,
                "total_elevation_ft": None,
                "sessions": [
                    {
                        "date": pd.Timestamp("2026-09-14", tz="UTC"),
                        "session": "Past prepare",
                        "miles": 5.0,
                        "miles_label": "5",
                        "shoes": "Pegasus Trail 5",
                        "is_race": False,
                    },
                    {
                        "date": pd.Timestamp("2026-09-16", tz="UTC"),
                        "session": "Future limit",
                        "miles": 10.0,
                        "miles_label": "10",
                        "shoes": "Pegasus Trail 5",
                        "is_race": False,
                    },
                    {
                        "date": pd.Timestamp("2026-09-17", tz="UTC"),
                        "session": "Fresh shoe",
                        "miles": 4.0,
                        "miles_label": "4",
                        "shoes": "Hoka Mach 7",
                        "is_race": False,
                    },
                ],
            },
        ]
        html = training_plan_table_html(
            weeks,
            expanded_week_index=0,
            today=pd.Timestamp("2026-09-15", tz="UTC"),
            shoe_estimates={"Pegasus Trail 5": 410.0, "Hoka Mach 7": 54.0},
            shoe_actuals={"Pegasus Trail 5": 360.0, "Hoka Mach 7": 50.0},
        )
        # Orange/red text classes stay; colored wear dots do not.
        self.assertIn("training-plan-shoes--prepare", html)
        self.assertIn("training-plan-shoes--limit", html)
        self.assertIn("training-plan-shoes--prepare", GLOBAL_CSS)
        self.assertIn("training-plan-shoes--limit", GLOBAL_CSS)
        self.assertNotIn("training-plan-shoe-wear", html)
        self.assertNotIn("training-plan-shoe-wear", GLOBAL_CSS)
        self.assertNotIn("band-dot", html)
        self.assertIn("Nearing retirement", html)
        self.assertIn("At retirement mileage", html)
        # Future limit row combines estimate + wear in one CSS tooltip.
        self.assertIn(
            '<span class="kpi-tooltip" role="tooltip">'
            "Est. ~410 mi · At retirement mileage</span>",
            html,
        )
        # Past prepare: wear tip only (no Est. on past rows).
        self.assertIn(
            '<span class="kpi-tooltip" role="tooltip">'
            "Nearing retirement — prepare to switch</span>",
            html,
        )
        # No threshold numbers as visible table copy (tooltips may omit them too).
        self.assertNotIn(">350<", html)
        self.assertNotIn(">400<", html)
        self.assertNotIn("hit their limit", html.lower())
        # Fresh shoe: estimate tip only; no prepare/limit class on Hoka.
        self.assertIn("Est. ~54 mi", html)
        self.assertIn("Est. ~410 mi", html)
        self.assertIn("Nearing retirement — prepare to switch", html)
        self.assertEqual(html.count("training-plan-shoes--prepare"), 1)
        self.assertEqual(html.count("training-plan-shoes--limit"), 1)
        self.assertNotIn(
            'training-plan-shoes training-plan-shoes--prepare">Hoka',
            html,
        )
        self.assertNotIn(
            'training-plan-shoes training-plan-shoes--limit">Hoka',
            html,
        )
    def test_plan_table_session_notes_tooltip(self):
        weeks = [
            {
                "week_label": "Sep 14, 2026 - Sep 20, 2026",
                "week_start": pd.Timestamp("2026-09-14", tz="UTC"),
                "total_miles": 9.0,
                "total_elevation_ft": None,
                "sessions": [
                    {
                        "date": pd.Timestamp("2026-09-14", tz="UTC"),
                        "session": "Past with notes",
                        "miles": 5.0,
                        "miles_label": "5",
                        "shoes": "Hoka Mach 7",
                        "notes": "Trail, easy effort",
                        "is_race": False,
                    },
                    {
                        "date": pd.Timestamp("2026-09-16", tz="UTC"),
                        "session": "Future no notes",
                        "miles": 4.0,
                        "miles_label": "4",
                        "shoes": "Hoka Mach 7",
                        "notes": None,
                        "is_race": False,
                    },
                    {
                        "date": pd.Timestamp("2026-09-17", tz="UTC"),
                        "session": "Notes need <escape>",
                        "miles": 3.0,
                        "miles_label": "3",
                        "shoes": None,
                        "notes": "Warm-up & 4x2min; cool-down",
                        "is_race": False,
                    },
                ],
            },
        ]
        html = training_plan_table_html(
            weeks,
            expanded_week_index=0,
            today=pd.Timestamp("2026-09-15", tz="UTC"),
        )
        # Notes hover on any dated session with notes (including past).
        self.assertIn(
            '<span class="kpi-tooltip" role="tooltip">Trail, easy effort</span>',
            html,
        )
        self.assertIn(
            '<span class="kpi-tooltip" role="tooltip">'
            "Warm-up &amp; 4x2min; cool-down</span>",
            html,
        )
        self.assertIn("Notes need &lt;escape&gt;", html)
        # Session without notes: name cell has no tip modifier.
        self.assertIn(
            'class="training-plan-session-name">Future no notes<',
            html,
        )
        self.assertEqual(html.count("training-plan-session-name training-plan-cell--tip"), 2)

    def test_plan_table_weekday_column(self):
        self.assertEqual(
            format_weekday_short(pd.Timestamp("2026-09-16", tz="UTC")), "Wed"
        )
        html = training_plan_table_html(
            self._sample_weeks(),
            expanded_week_index=1,
            today=pd.Timestamp("2026-09-01", tz="UTC"),
        )
        self.assertIn(">Day<", html)
        self.assertIn(">Date<", html)
        self.assertNotIn("Week / Date", html)
        self.assertIn('class="training-plan-dow">Tue<', html)
        self.assertIn('class="training-plan-dow">Wed<', html)
        # Week summary rows merge Day + Date (no Day cell / em dash).
        self.assertNotIn('class="training-plan-dow" aria-hidden="true">—<', html)
        self.assertNotIn('aria-hidden="true">—<', html)
        self.assertIn('class="training-plan-week-range"', html)
        self.assertIn(
            ".training-plan-week-range {\n"
            "    /* Merge Day + Date columns on week-total rows "
            "(Day cell omitted in HTML). */\n"
            "    grid-column: 1 / span 2;\n"
            "    min-width: 0;\n"
            "  }",
            GLOBAL_CSS,
        )

    def test_plan_table_focus_week_only_omits_other_weeks(self):
        html = training_plan_table_html(
            self._sample_weeks(),
            expanded_week_index=1,
            show_all_weeks=False,
            today=pd.Timestamp("2026-09-16", tz="UTC"),
        )
        self.assertIn("Sep 14, 2026 - Sep 20, 2026", html)
        self.assertIn("Hill repeats", html)
        self.assertNotIn("Sep 7, 2026 - Sep 13, 2026", html)
        self.assertNotIn("Easy run", html)
        self.assertEqual(html.count('<details class="training-plan-week'), 1)
        self.assertIn('class="training-plan-week" open>', html)
        self.assertNotIn("is-current-week", html)

    def test_plan_table_uses_details_week_rows(self):
        html = training_plan_table_html(
            self._sample_weeks(),
            expanded_week_index=None,
            show_all_weeks=True,
            today=pd.Timestamp("2026-09-01", tz="UTC"),
        )
        self.assertIn('class="training-plan-week"', html)
        self.assertIn("Week 1 total", html)
        self.assertIn("Week 2 total", html)
        self.assertIn("Sep 7, 2026 - Sep 13, 2026", html)
        self.assertIn("Sep 14, 2026 - Sep 20, 2026", html)
        self.assertIn(">20.8<", html)
        self.assertIn(">1,234<", html)
        self.assertIn("Hill repeats", html)
        self.assertIn("training-plan-session-row is-race", html)

        # Session rows nest under week summaries (indent via CSS padding).
        self.assertIn('class="training-plan-sessions"', html)

        # Full-plan mode: every week present, all collapsed by default.
        self.assertEqual(html.count('<details class="training-plan-week" open>'), 0)
        self.assertEqual(html.count('<details class="training-plan-week">'), 2)

    def test_no_focus_marker_when_all_sessions_past(self):
        html = training_plan_table_html(
            self._sample_weeks(),
            expanded_week_index=None,
            today=pd.Timestamp("2026-12-01", tz="UTC"),
        )
        self.assertNotIn("is-today", html)
        self.assertNotIn("is-next", html)

    def test_plan_table_focus_only_empty_when_all_past(self):
        html = training_plan_table_html(
            self._sample_weeks(),
            expanded_week_index=None,
            show_all_weeks=False,
            today=pd.Timestamp("2026-12-01", tz="UTC"),
        )
        self.assertIn("No current week in this plan.", html)
        self.assertNotIn('<details class="training-plan-week"', html)

    def test_sierra_focus_week_empty_before_plan_starts(self):
        """Sep 15 2026 is before Sierra (starts Nov 30): no week-1 fallback."""
        from pathlib import Path

        from data import parse_training_plan_file

        sierra = parse_training_plan_file(
            Path(__file__).resolve().parents[2] / "data" / "plans" / "sierra_half.csv"
        )
        weeks = list(sierra["weeks"])
        today = pd.Timestamp("2026-09-15", tz="UTC")
        self.assertIsNone(current_plan_week_index(weeks, today))
        self.assertIsNone(plan_focus_session_date(weeks, today))

        html = training_plan_table_html(
            weeks,
            expanded_week_index=None,
            show_all_weeks=False,
            today=today,
        )
        self.assertIn("No current week in this plan.", html)
        self.assertNotIn('<details class="training-plan-week"', html)
        self.assertNotIn("is-today", html)
        self.assertNotIn("is-next", html)
        self.assertNotIn("is-current-week", html)
        self.assertNotIn("Week 1 total", html)

    def test_sierra_full_plan_no_week1_highlight_before_start(self):
        """Full plan before start: week 1 visible but not cool-highlighted."""
        from pathlib import Path

        from data import parse_training_plan_file

        sierra = parse_training_plan_file(
            Path(__file__).resolve().parents[2] / "data" / "plans" / "sierra_half.csv"
        )
        weeks = list(sierra["weeks"])
        today = pd.Timestamp("2026-09-15", tz="UTC")
        html = training_plan_table_html(
            weeks,
            expanded_week_index=None,
            show_all_weeks=True,
            today=today,
        )
        self.assertIn("Week 1 total", html)
        self.assertIn("Easy trail", html)
        self.assertNotIn("is-today", html)
        self.assertNotIn("is-next", html)
        self.assertNotIn("is-current-week", html)
        self.assertEqual(html.count('<details class="training-plan-week" open>'), 0)

    def test_current_week_summary_highlighted(self):
        """Week containing today gets is-current-week; other weeks do not."""
        html = training_plan_table_html(
            self._sample_weeks(),
            expanded_week_index=None,
            show_all_weeks=True,
            today=pd.Timestamp("2026-09-16", tz="UTC"),
        )
        # Class on both <details> and the painted <summary> row.
        self.assertEqual(html.count("is-current-week"), 2)
        self.assertIn('class="training-plan-week is-current-week"', html)
        self.assertIn('class="training-plan-week-sum is-current-week"', html)
        self.assertIn("Week 2 total", html)
        # Week 1 (past) is present but not highlighted.
        self.assertIn("Week 1 total", html)
        self.assertIn(
            ".training-plan-week.is-current-week:not([open]) > "
            ".training-plan-week-sum {\n"
            "    background: rgba(91, 155, 213, 0.18);",
            GLOBAL_CSS,
        )
        # Expander chrome must not force transparent on week summary rows.
        self.assertIn(
            "summary:not(.training-plan-week-sum)",
            GLOBAL_CSS,
        )

    def test_current_week_not_highlighted_in_focus_week_mode(self):
        """Focus-week-only omits is-current-week even when today is in that week."""
        html = training_plan_table_html(
            self._sample_weeks(),
            expanded_week_index=1,
            show_all_weeks=False,
            today=pd.Timestamp("2026-09-16", tz="UTC"),
        )
        self.assertIn('class="training-plan-week" open>', html)
        self.assertIn("Week 2 total", html)
        self.assertNotIn("is-current-week", html)
        # Session-day focus highlights still apply.
        self.assertIn("training-plan-session-row is-today", html)

    def test_past_weeks_not_highlighted_as_current(self):
        html = training_plan_table_html(
            self._sample_weeks(),
            expanded_week_index=None,
            show_all_weeks=True,
            today=pd.Timestamp("2026-12-01", tz="UTC"),
        )
        self.assertIn("Week 1 total", html)
        self.assertIn("Week 2 total", html)
        self.assertNotIn("is-current-week", html)

    def test_future_plan_first_week_not_highlighted(self):
        """Before plan start, week 1 must not get the current-week wash."""
        from pathlib import Path

        from data import parse_training_plan_file

        sierra = parse_training_plan_file(
            Path(__file__).resolve().parents[2] / "data" / "plans" / "sierra_half.csv"
        )
        weeks = list(sierra["weeks"])
        today = pd.Timestamp("2026-09-15", tz="UTC")
        self.assertIsNone(current_plan_week_index(weeks, today))
        html = training_plan_table_html(
            weeks,
            expanded_week_index=None,
            show_all_weeks=True,
            today=today,
        )
        self.assertIn("Week 1 total", html)
        self.assertNotIn("is-current-week", html)

    def test_plan_table_all_weeks_collapsed_without_index(self):
        html = training_plan_table_html(
            self._sample_weeks(),
            expanded_week_index=None,
            show_all_weeks=True,
            today=pd.Timestamp("2026-09-01", tz="UTC"),
        )
        self.assertEqual(
            html.count('<details class="training-plan-week" open>'), 0
        )
        self.assertEqual(html.count('<details class="training-plan-week">'), 2)
        self.assertNotIn("is-current-week", html)


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
