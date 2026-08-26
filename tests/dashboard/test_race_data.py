"""Tests for dashboard.race_data."""

import unittest

import pandas as pd

from dashboard.data import format_full_date
from dashboard.race_data import (
    ensure_race_pace_min,
    fastest_races_by_type,
    filter_race_results,
    mark_personal_records,
    parse_duration_minutes,
    race_table_rows,
    race_type_options,
)


class ParseDurationTests(unittest.TestCase):
    """Duration string parsing for race finish times."""

    def test_hms_with_leading_zero_hours(self):
        self.assertAlmostEqual(parse_duration_minutes("01:17:28"), 77 + 28 / 60, places=4)

    def test_hms_without_leading_zeros(self):
        self.assertAlmostEqual(parse_duration_minutes("1:58:35"), 118 + 35 / 60, places=4)

    def test_ms_format(self):
        self.assertAlmostEqual(parse_duration_minutes("0:39:06"), 39 + 6 / 60, places=4)

    def test_invalid_returns_none(self):
        self.assertIsNone(parse_duration_minutes(""))
        self.assertIsNone(parse_duration_minutes(None))


class PersonalRecordTests(unittest.TestCase):
    """PR flag per race type excluding Other."""

    def _races(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "race_type": ["5k", "5k", "Half", "Other", "Other"],
                "elapsed_min": [30.0, 28.5, 120.0, 40.0, 38.0],
            }
        )

    def test_marks_fastest_per_type_excluding_other(self):
        result = mark_personal_records(self._races())
        pr_rows = result.loc[result["is_pr"], ["race_type", "elapsed_min"]]
        self.assertEqual(len(pr_rows), 2)
        self.assertEqual(pr_rows.loc[pr_rows["race_type"] == "5k", "elapsed_min"].iloc[0], 28.5)
        self.assertEqual(pr_rows.loc[pr_rows["race_type"] == "Half", "elapsed_min"].iloc[0], 120.0)
        self.assertFalse(result.loc[result["race_type"] == "Other", "is_pr"].any())

    def test_ties_mark_all_fastest(self):
        races = pd.DataFrame(
            {
                "race_type": ["5k", "5k"],
                "elapsed_min": [30.0, 30.0],
            }
        )
        result = mark_personal_records(races)
        self.assertTrue(result["is_pr"].all())


class EnsureRacePaceMinTests(unittest.TestCase):
    """Backfill pace_min for dataframes loaded before the column existed."""

    def test_adds_pace_min_when_missing(self):
        races = pd.DataFrame(
            {
                "elapsed_min": [39.0, 47.0],
                "distance_miles": [3.1, 6.2],
            }
        )
        result = ensure_race_pace_min(races)
        self.assertIn("pace_min", result.columns)
        self.assertAlmostEqual(result.loc[0, "pace_min"], 39.0 / 3.1, places=4)

    def test_leaves_existing_pace_min_unchanged(self):
        races = pd.DataFrame({"pace_min": [8.0]})
        result = ensure_race_pace_min(races)
        pd.testing.assert_frame_equal(result, races)


class FilterRaceResultsTests(unittest.TestCase):
    """Race type and date filters."""

    def _races(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "date": pd.to_datetime(
                    ["2019-05-19T14:00:00Z", "2018-09-09T14:00:00Z", "2016-05-22T14:00:00Z"],
                    utc=True,
                ),
                "race_type": ["5M", "10k", "5M"],
                "elapsed_min": [39.0, 47.0, 36.0],
                "is_pr": [False, True, True],
            }
        )

    def test_filter_by_race_type(self):
        result = filter_race_results(self._races(), race_type="5M")
        self.assertEqual(len(result), 2)
        self.assertTrue((result["race_type"] == "5M").all())

    def test_filter_by_date_range(self):
        result = filter_race_results(
            self._races(),
            start=pd.Timestamp("2018-01-01", tz="UTC"),
            end=pd.Timestamp("2019-12-31", tz="UTC"),
        )
        self.assertEqual(len(result), 2)

    def test_filter_prs_only(self):
        result = filter_race_results(self._races(), race_type="PRs only")
        self.assertEqual(len(result), 2)
        self.assertTrue(result["is_pr"].all())
        self.assertNotIn("Other", result["race_type"].tolist())


class FormatFullDateTests(unittest.TestCase):
    """Full calendar date formatting."""

    def test_formats_full_month_name(self):
        ts = pd.Timestamp("2026-01-01", tz="UTC")
        self.assertEqual(format_full_date(ts), "January 1, 2026")

    def test_no_leading_zero_on_day(self):
        ts = pd.Timestamp("2019-05-19T14:00:00Z")
        self.assertEqual(format_full_date(ts), "May 19, 2019")


class RaceTableRowsTests(unittest.TestCase):
    """Race history table columns and default sort."""

    def _races(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "activity_id": ["111", "222"],
                "date": pd.to_datetime(
                    ["2019-05-19T14:00:00Z", "2018-09-09T14:00:00Z"],
                    utc=True,
                ),
                "name": ["Brooklyn Half", "Charleston Bridge Run"],
                "race_type": ["Half", "10k"],
                "distance_miles": [13.1, 6.2],
                "elapsed_time_min": ["1:58:35", "0:47:00"],
                "elapsed_pace": ["9:03", "7:35"],
                "is_pr": [True, False],
            }
        )

    def test_columns_exclude_avg_pace(self):
        result = race_table_rows(self._races())
        self.assertEqual(
            list(result.columns),
            [
                "activity_id",
                "Name",
                "Date",
                "Race Type",
                "Miles",
                "Time",
                "Pace",
                "PR",
            ],
        )
        self.assertNotIn("Avg Pace", result.columns)
        self.assertNotIn("Day of Date", result.columns)
        self.assertEqual(list(result["activity_id"]), ["222", "111"])

    def test_default_sort_is_date_ascending(self):
        result = race_table_rows(self._races())
        self.assertLess(result["Date"].iloc[0], result["Date"].iloc[1])
        self.assertEqual(result.iloc[0]["Name"], "Charleston Bridge Run")
        self.assertEqual(result.iloc[1]["Name"], "Brooklyn Half")

    def test_date_column_is_datetime(self):
        result = race_table_rows(self._races())
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(result["Date"]))

    def test_pr_trophy_only_on_fastest_per_type(self):
        result = race_table_rows(self._races())
        self.assertEqual(result.loc[result["Name"] == "Brooklyn Half", "PR"].iloc[0], "🏆")
        self.assertEqual(result.loc[result["Name"] == "Charleston Bridge Run", "PR"].iloc[0], "")


class RaceTypeOptionsTests(unittest.TestCase):
    """Filter dropdown options."""

    def test_all_first_then_ordered_types(self):
        races = pd.DataFrame({"race_type": ["Half", "5k", "Other"]})
        options = race_type_options(races)
        self.assertEqual(options[0], "All")
        self.assertEqual(options[1], "PRs only")
        self.assertEqual(options.index("5k"), 2)
        self.assertEqual(options.index("Half"), 3)
        self.assertEqual(options.index("Other"), 4)


class FastestRacesByTypeTests(unittest.TestCase):
    """Fastest (personal-record) row per race type for Performance cards."""

    def _races(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "activity_id": ["1", "2", "3", "4", "5", "6"],
                "date": pd.to_datetime(
                    [
                        "2019-05-19T14:00:00Z",
                        "2020-05-19T14:00:00Z",
                        "2018-09-09T14:00:00Z",
                        "2021-03-01T14:00:00Z",
                        "2017-01-01T14:00:00Z",
                        "2022-06-01T14:00:00Z",
                    ],
                    utc=True,
                ),
                "name": [
                    "Brooklyn Half",
                    "Faster Half",
                    "Bridge 10k",
                    "Park 5k",
                    "Odd Race",
                    "Trail Other",
                ],
                "race_type": ["Half", "Half", "10k", "5k", "8k", "Other"],
                "elapsed_min": [120.0, 110.0, 47.0, 22.0, 55.0, 90.0],
                "elapsed_time_min": [
                    "2:00:00",
                    "1:50:00",
                    "0:47:00",
                    "0:22:00",
                    "0:55:00",
                    "1:30:00",
                ],
                "elapsed_pace": ["9:09", "8:24", "7:35", "7:06", "11:00", "9:00"],
            }
        )

    def test_excludes_other_and_orders_known_types(self):
        result = fastest_races_by_type(self._races())
        self.assertEqual(list(result["race_type"]), ["5k", "10k", "Half", "8k"])
        self.assertNotIn("Other", result["race_type"].tolist())

    def test_picks_fastest_finish_per_type(self):
        result = fastest_races_by_type(self._races())
        by_type = result.set_index("race_type")
        self.assertEqual(by_type.loc["Half", "elapsed_min"], 110.0)
        self.assertEqual(by_type.loc["Half", "name"], "Faster Half")
        self.assertEqual(by_type.loc["5k", "elapsed_min"], 22.0)

    def test_tie_prefers_most_recent(self):
        races = pd.DataFrame(
            {
                "race_type": ["5k", "5k"],
                "elapsed_min": [22.0, 22.0],
                "date": pd.to_datetime(
                    ["2018-01-01T12:00:00Z", "2020-01-01T12:00:00Z"],
                    utc=True,
                ),
                "name": ["Older", "Newer"],
                "elapsed_time_min": ["0:22:00", "0:22:00"],
            }
        )
        result = fastest_races_by_type(races)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["name"], "Newer")

    def test_empty_input(self):
        result = fastest_races_by_type(pd.DataFrame())
        self.assertTrue(result.empty)


class FastestRaceCardsHtmlTests(unittest.TestCase):
    """Personal Records card strip markup."""

    def test_renders_cards_for_non_other_types(self):
        from dashboard.ui import fastest_race_cards_html

        races = pd.DataFrame(
            {
                "date": pd.to_datetime(["2019-05-19T14:00:00Z"], utc=True),
                "name": ["Brooklyn Half"],
                "race_type": ["Half"],
                "elapsed_min": [118.0],
                "elapsed_time_min": ["1:58:35"],
                "elapsed_pace": ["9:03"],
            }
        )
        html = fastest_race_cards_html(races)
        self.assertIn('id="fastest-races"', html)
        self.assertIn("Personal Records", html)
        self.assertNotIn("Personal Bests", html)
        self.assertIn("Half", html)
        self.assertIn("1:58:35", html)
        self.assertIn("Brooklyn Half", html)
        self.assertIn("May 19, 2019", html)
        self.assertIn("9:03 /mi", html)
        self.assertNotIn("Other", html)

    def test_empty_returns_blank(self):
        from dashboard.ui import fastest_race_cards_html

        self.assertEqual(fastest_race_cards_html(pd.DataFrame()), "")


class RaceBuildupCompareHelpersTests(unittest.TestCase):
    """Race type / dropdown helpers for Performance build-up compare."""

    def _races(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "activity_id": ["a1", "a2", "a3", "a4"],
                "name": ["Boston", "Chicago", "Local 5k", "PR 5k"],
                "race_type": ["Marathon", "Marathon", "5k", "5k"],
                "is_pr": [False, True, False, True],
                "date": pd.to_datetime(
                    [
                        "2024-04-15T12:00:00Z",
                        "2023-10-08T12:00:00Z",
                        "2022-06-01T12:00:00Z",
                        "2021-05-01T12:00:00Z",
                    ],
                    utc=True,
                ),
            }
        )

    def test_compare_types_require_two_races(self):
        from dashboard.race_data import compare_race_type_options

        races = self._races()
        races.loc[races["race_type"] == "5k", "race_type"] = ["5k", "Half"]
        options = compare_race_type_options(races)
        self.assertEqual(options, ["Marathon"])

    def test_option_label_marks_pr(self):
        from dashboard.race_data import race_option_label

        row = self._races().iloc[1]
        label = race_option_label(row)
        self.assertTrue(label.startswith("🏆 PR · "))
        self.assertIn("Chicago", label)
        self.assertIn("2023", label)

    def test_compare_choices_sorted_newest_first(self):
        from dashboard.race_data import race_compare_choices

        choices = race_compare_choices(self._races(), "Marathon")
        self.assertEqual([aid for _, aid in choices], ["a1", "a2"])
        self.assertIn("🏆 PR · ", choices[1][0])
        self.assertNotIn("🏆 PR · ", choices[0][0])
        self.assertNotIn("🏆", choices[0][0])

    def test_buildup_weeks_by_distance(self):
        from dashboard.race_data import race_buildup_weeks

        self.assertEqual(race_buildup_weeks("5k"), 8)
        self.assertEqual(race_buildup_weeks("5M"), 8)
        self.assertEqual(race_buildup_weeks("10k"), 10)
        self.assertEqual(race_buildup_weeks("Half"), 12)
        self.assertEqual(race_buildup_weeks("Marathon"), 16)
        self.assertEqual(race_buildup_weeks("Other"), 12)

    def test_compare_short_name_and_summary(self):
        from dashboard.race_data import (
            race_buildup_comparison_title,
            race_compare_short_name,
        )
        from dashboard.ui import (
            race_buildup_delta_table_html,
            race_buildup_eh_values_html,
            race_buildup_row_heading_html,
            race_buildup_section_heading_html,
            race_buildup_summary_html,
        )

        self.assertEqual(
            race_buildup_comparison_title("Half"),
            "HALF MARATHON RACE COMPARISON",
        )
        row = pd.Series(
            {
                "name": "Nice half",
                "date": pd.Timestamp("2026-04-26T12:00:00Z"),
                "elapsed_time_min": "1:53:48",
                "elapsed_pace": "8:41",
                "elapsed_min": 113.8,
                "distance_miles": 13.1,
                "pace_min": 8.0 + 41 / 60.0,
                "is_pr": True,
            }
        )
        self.assertEqual(race_compare_short_name(row), "Nice 2026")
        # Header pace is training-period avg pace (not race elapsed_pace).
        html = race_buildup_summary_html(
            "Half",
            row,
            row,
            avg_pace_min_a=8.0 + 46 / 60.0,
            avg_pace_min_b=8.0 + 46 / 60.0,
        )
        self.assertIn("HALF MARATHON RACE COMPARISON", html)
        self.assertIn("race-buildup-col-headers", html)
        self.assertIn("race-buildup-col-header", html)
        self.assertIn("race-buildup-compare-row", html)
        self.assertIn("race-buildup-label-gutter", html)
        self.assertIn("race-buildup-mid-gutter", html)
        self.assertIn(">Race A</", html)
        self.assertIn(">Race B</", html)
        # Column labels sit above the comparison title.
        self.assertLess(
            html.index("race-buildup-col-headers"),
            html.index("race-buildup-summary-title"),
        )
        self.assertLess(
            html.index("race-buildup-summary-title"),
            html.index("race-buildup-summary-grid"),
        )
        self.assertIn("Nice 2026", html)
        self.assertIn("April 26, 2026", html)
        self.assertIn("1:53:48", html)
        self.assertIn("8:46/mi", html)
        self.assertNotIn("8:41/mi", html)
        self.assertIn("race-buildup-pr", html)
        # Missing training pace shows an em dash, not race result pace.
        empty_pace = race_buildup_summary_html("Half", row, row)
        self.assertIn("—", empty_pace)
        self.assertNotIn("8:41/mi", empty_pace)

        heading = race_buildup_section_heading_html(
            "12 week training comparison",
            subtitle="Excludes race week",
        )
        self.assertIn("12 week training comparison", heading)
        self.assertIn("race-buildup-section-title", heading)
        self.assertIn("race-buildup-section-heading-main", heading)
        self.assertIn("race-buildup-compare-row", heading)
        self.assertIn("Excludes race week", heading)
        self.assertIn("race-buildup-section-sub", heading)

        mileage = race_buildup_row_heading_html("Weekly mileage")
        self.assertIn("Weekly mileage", mileage)
        self.assertIn("race-buildup-mileage-label", mileage)
        self.assertIn("race-buildup-row-title", mileage)

        eh = race_buildup_eh_values_html(
            weeks=12,
            easy_pct_a=72.4,
            easy_pct_b=None,
        )
        self.assertIn("race-buildup-eh-values", eh)
        self.assertIn("race-buildup-compare-row", eh)
        self.assertIn("race-buildup-eh-title", eh)
        self.assertIn("race-buildup-eh-value", eh)
        self.assertIn("race-buildup-mid-gutter", eh)
        self.assertIn("% easy : % hard", eh)
        self.assertIn("72% : 28%", eh)
        # Title is inline with values (no separate stacked eh-grid).
        self.assertNotIn("race-buildup-eh-grid", eh)
        # Event names stay in the stats summary only — not on EH cells.
        self.assertNotIn("Nice 2026", eh)
        self.assertNotIn("Boston 2025", eh)
        self.assertNotIn("race-buildup-eh-label", eh)
        self.assertNotIn("kpi-card", eh)
        self.assertNotIn("kpi-gauge", eh)
        self.assertNotIn("gauge-target-tick", eh)
        self.assertNotIn("target 80:20", eh)
        self.assertNotIn("<strong>Target</strong>", eh)
        self.assertNotIn("<strong>Target Bands</strong>", eh)
        self.assertNotIn("80:20", eh)
        # Missing HR data renders an em dash, not a crash / empty value.
        self.assertIn("—", eh)
        self.assertIn("pre-race weeks (race week excluded)", eh)
        self.assertIn("<strong>Definition</strong>", eh)

        metrics = race_buildup_delta_table_html(
            [
                {
                    "metric": "Avg weekly mileage",
                    "race_a": "18.4",
                    "race_b": "22.7",
                    "delta": "+4.3",
                }
            ],
            weeks=12,
        )
        # Exclude note lives on the training-comparison heading, not metrics.
        self.assertNotIn("Excludes race week", metrics)
        self.assertNotIn("race-buildup-delta-sub", metrics)
        self.assertIn("Avg weekly mileage", metrics)
        self.assertIn("race-buildup-metric-title", metrics)
        self.assertIn("race-buildup-compare-row", metrics)
        self.assertIn("race-buildup-metric-value", metrics)
        self.assertIn("+4.3", metrics)
        self.assertIn("race-buildup-metric-mid", metrics)
        self.assertIn("race-buildup-delta-delta", metrics)
        # Inline title | A | Δ | B — no nested metric-grid wrapper.
        self.assertNotIn("race-buildup-metric-grid", metrics)
        # Plain value rows — not a dense HTML table.
        self.assertNotIn("<table", metrics)
        self.assertNotIn("<th", metrics)
        # Title then A then Δ then B on one row.
        title_pos = metrics.index("race-buildup-metric-title")
        a_pos = metrics.index(">18.4</")
        mid_pos = metrics.index("race-buildup-metric-mid")
        b_pos = metrics.index(">22.7</")
        self.assertLess(title_pos, a_pos)
        self.assertLess(a_pos, mid_pos)
        self.assertLess(mid_pos, b_pos)
        # No nested EH/pies inside the metrics helper.
        self.assertNotIn("race-buildup-eh-values", metrics)
        self.assertNotIn("% easy : % hard", metrics)
        self.assertNotIn("race-buildup-hr-pies", metrics)

    def test_easy_hard_ratio_from_pct(self):
        from dashboard.race_data import easy_hard_ratio_from_pct

        label, pct = easy_hard_ratio_from_pct(72.4)
        self.assertEqual(label, "72% : 28%")
        self.assertAlmostEqual(pct, 72.4)
        empty, none_pct = easy_hard_ratio_from_pct(None)
        self.assertEqual(empty, "—")
        self.assertIsNone(none_pct)

    def test_training_window_excludes_race_week(self):
        from dashboard.data import current_period_key, normalize_utc
        from dashboard.race_data import (
            race_buildup_side_stats,
            race_buildup_training_periods,
        )

        # Race on Wed of ISO week 2026-17 (Mon Apr 20 – Sun Apr 26, 2026).
        race_date = pd.Timestamp("2026-04-22T12:00:00Z")
        race_key = current_period_key("Week", normalize_utc(race_date))
        runs = pd.DataFrame(
            {
                "date": pd.to_datetime(
                    [
                        "2026-04-06T08:00:00Z",  # week before race week
                        "2026-04-13T08:00:00Z",  # week before race week
                        "2026-04-21T08:00:00Z",  # race week — must be excluded
                        "2026-04-22T12:00:00Z",  # race day
                    ],
                    utc=True,
                ),
                "distance_miles": [10.0, 20.0, 99.0, 13.1],
                "%_easy": [80.0, 70.0, 50.0, 40.0],
                "elevation_gain_ft": [0.0, 0.0, 0.0, 0.0],
            }
        )
        race_row = pd.Series(
            {
                "date": race_date,
                "name": "Test Half",
                "elapsed_min": 120.0,
                "distance_miles": 13.1,
                "pace_min": 120.0 / 13.1,
                "elapsed_time_min": "2:00:00",
                "elapsed_pace": "9:09",
            }
        )
        training = race_buildup_training_periods(runs, race_row, weeks=2)
        self.assertEqual(len(training), 2)
        self.assertNotIn(race_key, set(training["period_key"].astype(str)))
        # Peak must ignore the 99-mile race-week run.
        stats = race_buildup_side_stats(runs, race_row, weeks=2)
        self.assertAlmostEqual(stats["peak_week_miles"], 20.0, places=3)
        self.assertAlmostEqual(stats["longest_run_miles"], 20.0, places=3)
        self.assertNotAlmostEqual(stats["peak_week_miles"], 99.0)

        # Optional include_race_week still available; charts use the default
        # (exclude) window so race diamonds are not race-week-only markers.
        chart = race_buildup_training_periods(
            runs, race_row, weeks=2, include_race_week=True
        )
        self.assertEqual(len(chart), 3)
        self.assertIn(race_key, set(chart["period_key"].astype(str)))
        race_week = chart.loc[chart["period_key"] == race_key].iloc[0]
        self.assertTrue(bool(race_week["is_race_period"]))
        # Default frame used by mileage charts has no race-week diamond row.
        self.assertFalse(
            bool(training["is_race_period"].fillna(False).astype(bool).any())
            if "is_race_period" in training.columns
            else False
        )

    def test_avg_runs_per_week_excludes_race_week_and_empty_weeks(self):
        from dashboard.race_data import (
            race_buildup_compare_rows,
            race_buildup_side_stats,
        )

        # Race A on Wed of ISO week 2026-17. Window weeks=3 → ISO weeks 14, 15, 16.
        # Week 14: 2 runs, week 15: 0 runs, week 16: 3 runs → 5/3 ≈ 1.666…
        # Race-week runs must not count. Race B is a year earlier so windows
        # do not overlap in the shared runs frame.
        race_a_date = pd.Timestamp("2026-04-22T12:00:00Z")
        race_b_date = pd.Timestamp("2025-04-16T12:00:00Z")
        runs = pd.DataFrame(
            {
                "date": pd.to_datetime(
                    [
                        # Race A window
                        "2026-03-30T08:00:00Z",  # week 14
                        "2026-04-01T08:00:00Z",  # week 14
                        "2026-04-13T08:00:00Z",  # week 16
                        "2026-04-14T08:00:00Z",  # week 16
                        "2026-04-15T08:00:00Z",  # week 16
                        "2026-04-21T08:00:00Z",  # race A week — excluded
                        "2026-04-22T12:00:00Z",  # race A day — excluded
                        # Race B window: 6 runs across 3 pre-race weeks
                        "2025-03-24T08:00:00Z",
                        "2025-03-25T08:00:00Z",
                        "2025-03-31T08:00:00Z",
                        "2025-04-01T08:00:00Z",
                        "2025-04-07T08:00:00Z",
                        "2025-04-08T08:00:00Z",
                        "2025-04-15T08:00:00Z",  # race B week — excluded
                    ],
                    utc=True,
                ),
                "distance_miles": [
                    5.0,
                    6.0,
                    7.0,
                    8.0,
                    9.0,
                    99.0,
                    13.1,
                    5.0,
                    5.0,
                    5.0,
                    5.0,
                    5.0,
                    5.0,
                    13.1,
                ],
                "%_easy": [80.0] * 14,
                "elevation_gain_ft": [0.0] * 14,
            }
        )
        race_a = pd.Series(
            {
                "date": race_a_date,
                "name": "Test Half A",
                "elapsed_min": 120.0,
                "distance_miles": 13.1,
                "pace_min": 120.0 / 13.1,
            }
        )
        race_b = pd.Series(
            {
                "date": race_b_date,
                "name": "Test Half B",
                "elapsed_min": 110.0,
                "distance_miles": 13.1,
                "pace_min": 110.0 / 13.1,
            }
        )

        stats_a = race_buildup_side_stats(runs, race_a, weeks=3)
        self.assertAlmostEqual(stats_a["avg_runs_per_week"], 5.0 / 3.0, places=3)

        stats_b = race_buildup_side_stats(runs, race_b, weeks=3)
        self.assertAlmostEqual(stats_b["avg_runs_per_week"], 6.0 / 3.0, places=3)

        rows = race_buildup_compare_rows(runs, race_a, race_b, weeks=3)
        metrics = [row["metric"] for row in rows]
        self.assertEqual(metrics[0], "Avg weekly mileage")
        self.assertEqual(metrics[1], "Avg runs/week")
        avg_row = rows[1]
        self.assertEqual(avg_row["race_a"], "1.7")
        self.assertEqual(avg_row["race_b"], "2.0")
        self.assertEqual(avg_row["delta"], "+0.3")

        # Peak / longest append `` mi``; avg weekly and runs/week stay unitless.
        avg_miles_row = next(
            row for row in rows if row["metric"] == "Avg weekly mileage"
        )
        self.assertFalse(avg_miles_row["race_a"].endswith(" mi"))
        self.assertFalse(avg_miles_row["race_b"].endswith(" mi"))
        self.assertFalse(avg_miles_row["delta"].endswith(" mi"))
        self.assertFalse(avg_row["race_a"].endswith(" mi"))
        self.assertFalse(avg_row["delta"].endswith(" mi"))

        peak_row = next(row for row in rows if row["metric"] == "Peak week")
        longest_row = next(row for row in rows if row["metric"] == "Longest run")
        self.assertTrue(peak_row["race_a"].endswith(" mi"))
        self.assertTrue(peak_row["race_b"].endswith(" mi"))
        self.assertTrue(peak_row["delta"].endswith(" mi") or peak_row["delta"] == "—")
        self.assertTrue(longest_row["race_a"].endswith(" mi"))
        self.assertTrue(longest_row["race_b"].endswith(" mi"))
        self.assertTrue(
            longest_row["delta"].endswith(" mi") or longest_row["delta"] == "—"
        )
        # Peak week A: weeks 14=11, 15=0, 16=24 → 24.0 mi
        self.assertEqual(peak_row["race_a"], "24.0 mi")
        # Longest single run in A window (excluding race week): 9.0
        self.assertEqual(longest_row["race_a"], "9.0 mi")
        # Race B: six 5-mile runs across 3 weeks → peak 10.0, longest 5.0
        self.assertEqual(peak_row["race_b"], "10.0 mi")
        self.assertEqual(longest_row["race_b"], "5.0 mi")
        self.assertEqual(peak_row["delta"], "−14.0 mi")
        self.assertEqual(longest_row["delta"], "−4.0 mi")

    def test_avg_pace_excludes_race_week_and_replaces_race_pace(self):
        from dashboard.race_data import (
            format_pace_min_per_mile,
            race_buildup_compare_rows,
            race_buildup_side_stats,
        )

        # Race A: two pre-race runs (10 mi @ 9:00, 20 mi @ 8:00) →
        # distance-weighted avg = (10*540 + 20*480) / 30 = 500 sec/mi = 8:20/mi.
        # Race-week 5:00/mi run must not count. Race pace on the race row is
        # unrelated (9:09) and must not appear as the build-up pace metric.
        race_a_date = pd.Timestamp("2026-04-22T12:00:00Z")
        race_b_date = pd.Timestamp("2025-04-16T12:00:00Z")
        runs = pd.DataFrame(
            {
                "date": pd.to_datetime(
                    [
                        "2026-04-06T08:00:00Z",
                        "2026-04-13T08:00:00Z",
                        "2026-04-21T08:00:00Z",  # race A week — excluded
                        "2025-03-31T08:00:00Z",
                        "2025-04-07T08:00:00Z",
                        "2025-04-15T08:00:00Z",  # race B week — excluded
                    ],
                    utc=True,
                ),
                "distance_miles": [10.0, 20.0, 5.0, 12.0, 12.0, 5.0],
                "avg_pace_sec": [540.0, 480.0, 300.0, 600.0, 540.0, 300.0],
                "%_easy": [80.0] * 6,
                "elevation_gain_ft": [0.0] * 6,
            }
        )
        race_a = pd.Series(
            {
                "date": race_a_date,
                "name": "Test Half A",
                "elapsed_min": 120.0,
                "distance_miles": 13.1,
                "pace_min": 120.0 / 13.1,
                "elapsed_pace": "9:09",
            }
        )
        race_b = pd.Series(
            {
                "date": race_b_date,
                "name": "Test Half B",
                "elapsed_min": 110.0,
                "distance_miles": 13.1,
                "pace_min": 110.0 / 13.1,
                "elapsed_pace": "8:24",
            }
        )

        stats_a = race_buildup_side_stats(runs, race_a, weeks=2)
        self.assertAlmostEqual(stats_a["avg_pace_min"], 500.0 / 60.0, places=4)
        self.assertNotIn("race_pace_min", stats_a)

        stats_b = race_buildup_side_stats(runs, race_b, weeks=2)
        # (12*600 + 12*540) / 24 = 570 sec/mi = 9:30/mi
        self.assertAlmostEqual(stats_b["avg_pace_min"], 570.0 / 60.0, places=4)

        rows = race_buildup_compare_rows(runs, race_a, race_b, weeks=2)
        metrics = [row["metric"] for row in rows]
        self.assertIn("Avg pace", metrics)
        self.assertNotIn("Race pace", metrics)
        self.assertNotIn("Easy running", metrics)
        pace_row = next(row for row in rows if row["metric"] == "Avg pace")
        self.assertEqual(pace_row["race_a"], format_pace_min_per_mile(500.0 / 60.0))
        self.assertEqual(pace_row["race_b"], format_pace_min_per_mile(570.0 / 60.0))
        self.assertEqual(pace_row["race_a"], "8:20/mi")
        self.assertEqual(pace_row["race_b"], "9:30/mi")
        # B is slower by 70 sec/mi → positive delta with /mi suffix.
        self.assertEqual(pace_row["delta"], "+1:10/mi")

    def test_mileage_weighted_hr_zones_exclude_race_week(self):
        from dashboard.race_data import race_buildup_mileage_hr_zone_shares
        from dashboard.ui import race_buildup_hr_pies_html

        race_date = pd.Timestamp("2026-04-22T12:00:00Z")
        runs = pd.DataFrame(
            {
                "date": pd.to_datetime(
                    [
                        "2026-04-13T08:00:00Z",  # pre-race week
                        "2026-04-21T08:00:00Z",  # race week — excluded
                    ],
                    utc=True,
                ),
                "distance_miles": [10.0, 50.0],
                "hr_zone_1_sec": [3000.0, 100.0],
                "hr_zone_2_sec": [1000.0, 100.0],
                "hr_zone_3_sec": [0.0, 3800.0],
                "hr_zone_4_sec": [0.0, 0.0],
                "hr_zone_5_sec": [0.0, 0.0],
                "%_easy": [80.0, 20.0],
                "elevation_gain_ft": [0.0, 0.0],
            }
        )
        race_row = pd.Series(
            {
                "date": race_date,
                "name": "Test Half",
                "elapsed_min": 120.0,
                "distance_miles": 13.1,
                "pace_min": 120.0 / 13.1,
            }
        )
        shares = race_buildup_mileage_hr_zone_shares(runs, race_row, weeks=2)
        self.assertIsNotNone(shares)
        assert shares is not None
        # Only the 10-mile pre-race run: 75% Z1, 25% Z2.
        self.assertAlmostEqual(shares["zone_1_pct"], 75.0, places=3)
        self.assertAlmostEqual(shares["zone_2_pct"], 25.0, places=3)
        self.assertAlmostEqual(shares["zone_1_miles"], 7.5, places=3)
        html = race_buildup_hr_pies_html(
            shares, shares, label_a="A", label_b="B"
        )
        self.assertIn("HR zones", html)
        self.assertNotIn("HR zones by mileage", html)
        self.assertIn("race-buildup-compare-row", html)
        self.assertIn("race-buildup-hr-pies-title", html)
        self.assertIn("race-buildup-mid-gutter", html)
        self.assertIn("race-buildup-hr-pie-donut", html)
        self.assertNotIn("race-buildup-hr-pies-grid", html)
        self.assertNotIn("Pre-race weeks only", html)
        self.assertNotIn("race-buildup-hr-pies-sub", html)
        self.assertNotIn("race-buildup-hr-pie-caption", html)
        self.assertEqual(
            race_buildup_hr_pies_html(None, None, label_a="A", label_b="B"),
            "",
        )

    def test_hr_mileage_coverage_threshold_boundary(self):
        from dashboard.race_data import (
            RACE_BUILDUP_HR_COVERAGE_MIN,
            race_buildup_hr_coverage_sufficient,
            race_buildup_hr_mileage_coverage,
        )
        from dashboard.ui import (
            race_buildup_eh_values_html,
            race_buildup_hr_pies_html,
        )

        self.assertEqual(RACE_BUILDUP_HR_COVERAGE_MIN, 0.10)

        race_date = pd.Timestamp("2026-04-22T12:00:00Z")
        race_row = pd.Series(
            {
                "date": race_date,
                "name": "Coverage Boundary Half",
                "elapsed_min": 120.0,
                "distance_miles": 13.1,
                "pace_min": 120.0 / 13.1,
            }
        )

        def _runs(hr_miles: float, no_hr_miles: float) -> pd.DataFrame:
            return pd.DataFrame(
                {
                    "date": pd.to_datetime(
                        ["2026-04-13T08:00:00Z", "2026-04-14T08:00:00Z"],
                        utc=True,
                    ),
                    "distance_miles": [hr_miles, no_hr_miles],
                    "hr_zone_1_sec": [3000.0, None],
                    "hr_zone_2_sec": [1000.0, None],
                    "hr_zone_3_sec": [0.0, None],
                    "hr_zone_4_sec": [0.0, None],
                    "hr_zone_5_sec": [0.0, None],
                    "%_easy": [75.0, None],
                    "elevation_gain_ft": [0.0, 0.0],
                }
            )

        # Exactly 10% coverage → insufficient (need > 10%).
        at_boundary = race_buildup_hr_mileage_coverage(
            _runs(1.0, 9.0), race_row, weeks=2
        )
        self.assertAlmostEqual(at_boundary["coverage"], 0.10, places=6)
        self.assertAlmostEqual(at_boundary["hr_miles"], 1.0, places=6)
        self.assertAlmostEqual(at_boundary["total_miles"], 10.0, places=6)
        self.assertFalse(race_buildup_hr_coverage_sufficient(at_boundary))

        # Just above 10% → sufficient.
        above = race_buildup_hr_mileage_coverage(
            _runs(1.1, 8.9), race_row, weeks=2
        )
        self.assertGreater(above["coverage"], 0.10)
        self.assertTrue(race_buildup_hr_coverage_sufficient(above))

        # Thin coverage like Harvest Half (~1.7%).
        thin = race_buildup_hr_mileage_coverage(
            _runs(1.78, 105.85), race_row, weeks=2
        )
        self.assertAlmostEqual(thin["coverage"], 1.78 / 107.63, places=5)
        self.assertFalse(race_buildup_hr_coverage_sufficient(thin))

        # total_miles == 0 → coverage 0, insufficient.
        empty_cov = {"total_miles": 0.0, "hr_miles": 0.0, "coverage": 0.0}
        self.assertFalse(race_buildup_hr_coverage_sufficient(empty_cov))
        self.assertFalse(race_buildup_hr_coverage_sufficient(None))

        tiny_shares = {
            "zone_1_pct": 50.0,
            "zone_2_pct": 50.0,
            "zone_3_pct": 0.0,
            "zone_4_pct": 0.0,
            "zone_5_pct": 0.0,
            "zone_1_miles": 0.5,
            "zone_2_miles": 0.5,
            "zone_3_miles": 0.0,
            "zone_4_miles": 0.0,
            "zone_5_miles": 0.0,
        }
        # Insufficient column suppresses the pie (no tiny mile tooltips).
        pies = race_buildup_hr_pies_html(
            tiny_shares,
            tiny_shares,
            insufficient_a=True,
            insufficient_b=False,
        )
        self.assertEqual(pies.count("Insufficient HR data"), 1)
        self.assertEqual(pies.count("race-buildup-hr-insufficient"), 1)
        self.assertEqual(pies.count("race-buildup-hr-pie-empty"), 1)
        self.assertNotIn('aria-label="Insufficient HR data"', pies)
        self.assertIn("race-buildup-hr-pie-donut", pies)
        self.assertIn("Zone 1: 50%", pies)
        self.assertIn("0.5 mi", pies)

        eh = race_buildup_eh_values_html(
            weeks=12,
            easy_pct_a=80.0,
            easy_pct_b=70.0,
            insufficient_a=True,
            insufficient_b=False,
        )
        self.assertIn("Insufficient HR data", eh)
        self.assertIn("race-buildup-eh-insufficient", eh)
        # Insufficient A must not show the 80:20 ratio.
        self.assertNotIn("80% : 20%", eh)
        self.assertIn("70% : 30%", eh)

        # Both insufficient still renders the HR zones row — one indicator
        # per column (bold text inside the dashed circle).
        both = race_buildup_hr_pies_html(
            None, None, insufficient_a=True, insufficient_b=True
        )
        self.assertIn("HR zones", both)
        self.assertEqual(both.count("Insufficient HR data"), 2)
        self.assertEqual(both.count("race-buildup-hr-insufficient"), 2)
        self.assertEqual(both.count("race-buildup-hr-pie-empty"), 2)


if __name__ == "__main__":
    unittest.main()
