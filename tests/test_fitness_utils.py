import tempfile
import unittest
from pathlib import Path

import pandas as pd

from strava_analytics.fitness_utils import (
    _drop_header_like_rows,
    compute_hr_easy_stats,
    compute_run_pace_summary_from_streams,
    format_duration,
    is_fake_activity_id,
    pace_bin_for_seconds,
    pace_seconds_from_speed,
    pace_to_seconds,
    run_pace_columns,
    save_activities_last_week,
    speed_to_pace,
)


class ActivityIdTests(unittest.TestCase):
    """Test helpers related to activity ID validation."""

    def test_fake_activity_ids_are_skipped(self):
        """Ensure fake activity IDs are detected while normal IDs are preserved."""
        self.assertTrue(is_fake_activity_id("FAKE123"))
        self.assertFalse(is_fake_activity_id(12345))


class PaceSummaryTests(unittest.TestCase):
    """Test pace summary aggregation and binning helpers."""

    def test_compute_run_pace_summary_from_streams(self):
        """Verify that pace-bin summaries are computed with the expected elapsed time and HR values."""
        summary = compute_run_pace_summary_from_streams(
            activity_id=123,
            distance_meters=[0.0, 1609.34, 3218.68],
            time_seconds=[0.0, 420.0, 900.0],
            hr_values=[150.0, 150.0, 150.0],
        )

        self.assertEqual(summary["activity_id"], 123)
        self.assertEqual(summary["seconds_700_730"], 420)
        self.assertAlmostEqual(summary["avg_hr_700_730"], 150.0)
        self.assertEqual(summary["seconds_800_830"], 480)
        self.assertAlmostEqual(summary["avg_hr_800_830"], 150.0)
        self.assertIn("seconds_under_700", summary)

    def test_ignores_runs_without_hr_data(self):
        """Ensure runs without heart-rate data return no summary instead of producing invalid output."""
        summary = compute_run_pace_summary_from_streams(
            activity_id=456,
            distance_meters=[0.0, 1609.34],
            time_seconds=[0.0, 300.0],
            hr_values=[],
        )

        self.assertIsNone(summary)


class PaceFormattingTests(unittest.TestCase):
    """Test pace parsing and formatting helper functions."""

    def test_pace_to_seconds_parses_common_formats(self):
        """Verify that pace values in numeric and MM:SS formats are parsed correctly."""
        self.assertEqual(pace_to_seconds(450), 450)
        self.assertEqual(pace_to_seconds("07:30"), 450)
        self.assertIsNone(pace_to_seconds("not-a-pace"))

    def test_pace_bin_for_seconds_uses_expected_labels(self):
        """Check that pace thresholds map to the expected pace-bin labels."""
        self.assertEqual(pace_bin_for_seconds(419), "under_700")
        self.assertEqual(pace_bin_for_seconds(420), "700_730")
        self.assertEqual(pace_bin_for_seconds(690), "over_1130")

    def test_speed_and_duration_helpers_format_values(self):
        """Ensure pace conversion and duration formatting return the expected strings."""
        self.assertEqual(pace_seconds_from_speed(3.0), 536)
        self.assertEqual(speed_to_pace(3.0), "08:56")
        self.assertEqual(format_duration(3661), "01:01:01")

    def test_run_pace_columns_returns_expected_order(self):
        """Ensure the canonical run-pace column list starts with the activity ID and includes pace bins."""
        columns = run_pace_columns()
        self.assertEqual(columns[0], "activity_id")
        self.assertIn("seconds_under_700", columns)
        self.assertIn("avg_hr_over_1130", columns)


class HeartRateAnalysisTests(unittest.TestCase):
    """Test heart-rate-based activity analysis helpers."""

    def test_compute_hr_easy_stats_returns_expected_durations(self):
        """Validate that easy and hard duration calculations are based on the HR threshold correctly."""
        pct_easy, mt_min_easy, mt_min_hard = compute_hr_easy_stats(
            hr_stream=[120, 160, 140],
            time_stream=[0, 600, 1200],
            threshold=142,
        )

        self.assertEqual(pct_easy, 50.0)
        self.assertEqual(mt_min_easy, 10.0)
        self.assertEqual(mt_min_hard, 10.0)


class CsvProcessingTests(unittest.TestCase):
    """Test CSV-based processing helpers that do not call the Strava API."""

    def test_save_activities_last_week_creates_summary(self):
        """Ensure the weekly summary combines recent activity exports and writes the output CSV."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            first_file = tmp_path / "first.csv"
            second_file = tmp_path / "second.csv"

            pd.DataFrame(
                [{"type": "Run", "date": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ"), "distance_miles": 3.1}]
            ).to_csv(first_file, index=False)
            pd.DataFrame(
                [{"type": "Ride", "date": (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ"), "distance_miles": 10.0}]
            ).to_csv(second_file, index=False)

            output_path = tmp_path / "weekly.csv"
            result = save_activities_last_week([first_file, second_file], output_path)

            self.assertTrue(output_path.exists())
            self.assertEqual(result.shape[0], 2)

    def test_drop_header_like_rows_removes_header_rows(self):
        """Ensure repeated header rows are removed from imported CSV-like dataframes."""
        df = pd.DataFrame(
            [
                ["activity_id", "name", "type"],
                ["123", "Run 1", "Run"],
            ],
            columns=["activity_id", "name", "type"],
        )
        cleaned = _drop_header_like_rows(df)

        self.assertEqual(cleaned.shape[0], 1)
        self.assertEqual(cleaned.iloc[0]["activity_id"], "123")


if __name__ == "__main__":
    unittest.main()
