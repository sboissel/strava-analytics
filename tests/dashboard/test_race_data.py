"""Tests for dashboard.race_data."""

import unittest

import pandas as pd

from dashboard.data import format_full_date
from dashboard.race_data import (
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
            ["Name", "Date", "Race Type", "Miles", "Time", "Pace", "PR"],
        )
        self.assertNotIn("Avg Pace", result.columns)
        self.assertNotIn("Day of Date", result.columns)

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


if __name__ == "__main__":
    unittest.main()
