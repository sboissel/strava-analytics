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


if __name__ == "__main__":
    unittest.main()
