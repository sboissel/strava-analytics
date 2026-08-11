import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from strava_analytics.activity_utils import (
    _drop_header_like_rows,
    activity_analysis_columns,
    activity_analysis_paths,
    compute_hr_easy_stats,
    compute_run_pace_summary_from_streams,
    format_time,
    pace_bin_for_seconds,
    process_activities,
    run_pace_columns,
    save_activities_last_week,
    speed_to_pace_seconds,
    update_activity_analysis_csvs,
    update_run_pace_analysis_csv,
    week_summary_bounds,
)


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


class ActivityProcessingTests(unittest.TestCase):
    """Test activity enrichment helpers that consume a stream fetcher."""

    def test_process_activities_enriches_run_rows_and_reuses_streams(self):
        """Ensure runs are enriched and pace summaries reuse the same stream fetch."""
        activities = [
            {
                "id": 123,
                "name": "Morning Run",
                "type": "Run",
                "start_date": "2024-01-01T00:00:00Z",
                "distance": 1609.34,
                "moving_time": 600,
                "elapsed_time": 600,
                "total_elevation_gain": 0,
                "average_speed": 2.68,
                "max_speed": 3.0,
                "workout_type": 0,
            },
            {
                "id": 456,
                "name": "Ride",
                "type": "Ride",
                "start_date": "2024-01-01T00:00:00Z",
                "distance": 1000.0,
                "moving_time": 600,
                "elapsed_time": 600,
                "total_elevation_gain": 0,
                "average_speed": 3.0,
                "max_speed": 4.0,
                "workout_type": 0,
            },
        ]

        mock_streams = {
            "heartrate": {"data": [120.0, 160.0]},
            "distance": {"data": [0.0, 1609.34]},
            "time": {"data": [0.0, 600.0]},
        }
        get_streams = Mock(return_value=mock_streams)

        with patch("strava_analytics.activity_utils.time.sleep", return_value=None):
            result, pace_summaries = process_activities(activities, get_streams, last_activity_id="0")

        self.assertIn("%_easy", result.columns)
        self.assertEqual(result.loc[result["activity_id"] == 123, "avg_hr"].iloc[0], 140.0)
        self.assertEqual(result.loc[result["activity_id"] == 456, "type"].iloc[0], "Ride")
        self.assertEqual(len(pace_summaries), 1)
        self.assertEqual(pace_summaries[0]["activity_id"], 123)
        get_streams.assert_called_once_with(123, ["heartrate", "distance", "time"])


class PaceFormattingTests(unittest.TestCase):
    """Test pace parsing and formatting helper functions."""

    def test_pace_bin_for_seconds_uses_expected_labels(self):
        """Check that pace thresholds map to the expected pace-bin labels."""
        self.assertEqual(pace_bin_for_seconds(419), "under_700")
        self.assertEqual(pace_bin_for_seconds(420), "700_730")
        self.assertEqual(pace_bin_for_seconds(690), "over_1130")

    def test_speed_and_duration_helpers_format_values(self):
        """Ensure speed conversion and clock formatting return the expected values."""
        self.assertEqual(speed_to_pace_seconds(3.0), 536)
        self.assertEqual(format_time(536, include_hours=False), "08:56")
        self.assertEqual(format_time(3661, include_hours=True), "01:01:01")
        self.assertIsNone(format_time(None, include_hours=False))

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

    def test_update_run_pace_analysis_csv_writes_summaries(self):
        """Ensure the pace-analysis CSV file is populated from precomputed summaries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "pace.csv"
            existing_df = pd.DataFrame({"activity_id": [999], "seconds_under_700": [10], "avg_hr_under_700": [100]})
            existing_df.to_csv(output_path, index=False)

            pace_summaries = [
                {
                    "activity_id": 123,
                    "seconds_under_700": 0,
                    "avg_hr_under_700": float("nan"),
                    "seconds_700_730": 420,
                    "avg_hr_700_730": 150.0,
                }
            ]

            update_run_pace_analysis_csv(pace_summaries, output_path)
            written = pd.read_csv(output_path)

        self.assertIn("activity_id", written.columns)
        self.assertIn("seconds_700_730", written.columns)
        self.assertTrue(written[written["activity_id"].astype(str) == "123"].shape[0] == 1)

    def test_update_run_pace_analysis_csv_skips_empty_summaries(self):
        """Ensure empty pace summaries return early without writing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "pace.csv"

            update_run_pace_analysis_csv([], output_path)

            self.assertFalse(output_path.exists())

    def test_update_activity_analysis_csvs_merges_by_type(self):
        """Ensure per-type analysis CSVs are updated and existing rows are preserved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            existing_run = pd.DataFrame(
                [
                    {
                        "activity_id": "999",
                        "name": "Old Run",
                        "type": "Run",
                        "date": "2024-01-01T00:00:00Z",
                        "distance_miles": "3.0",
                        "moving_time_min": "00:30:00",
                        "elapsed_time_min": "00:30:00",
                        "elevation_gain_ft": "0",
                        "avg_pace": "10:00",
                        "avg_pace_sec": "600",
                        "max_pace": "09:00",
                        "max_pace_sec": "540",
                    }
                ]
            )
            for activity_type in ["Run", "Ride", "Swim", "Hike"]:
                path = output_dir / f"strava_{activity_type.lower()}_analysis.csv"
                if activity_type == "Run":
                    existing_run.to_csv(path, index=False)
                else:
                    pd.DataFrame(columns=activity_analysis_columns(activity_type)).to_csv(path, index=False)

            new_df = pd.DataFrame(
                [
                    {
                        "activity_id": 123,
                        "name": "New Run",
                        "type": "Run",
                        "date": "2024-02-01T00:00:00Z",
                        "distance_miles": 1.0,
                        "moving_time_min": "00:10:00",
                        "elapsed_time_min": "00:10:00",
                        "elevation_gain_ft": 0.0,
                        "avg_pace": "10:00",
                        "avg_pace_sec": 600,
                        "max_pace": "09:00",
                        "max_pace_sec": 540,
                        "avg_hr": 140.0,
                        "max_hr": 160,
                        "%_easy": 50.0,
                        "mt_min_easy": 5.0,
                        "mt_min_hard": 5.0,
                        "race": False,
                    },
                    {
                        "activity_id": 456,
                        "name": "New Ride",
                        "type": "Ride",
                        "date": "2024-02-01T00:00:00Z",
                        "distance_miles": 10.0,
                        "moving_time_min": "00:40:00",
                        "elapsed_time_min": "00:40:00",
                        "elevation_gain_ft": 100.0,
                        "avg_pace": "04:00",
                        "avg_pace_sec": 240,
                        "max_pace": "03:00",
                        "max_pace_sec": 180,
                    },
                ]
            )

            update_activity_analysis_csvs(new_df, output_dir)

            run_df = pd.read_csv(output_dir / "strava_run_analysis.csv")
            ride_df = pd.read_csv(output_dir / "strava_ride_analysis.csv")

        self.assertEqual(sorted(run_df["activity_id"].astype(str).tolist()), ["123", "999"])
        self.assertEqual(ride_df["activity_id"].astype(str).tolist(), ["456"])
        self.assertIn("avg_hr", run_df.columns)
        self.assertNotIn("avg_hr", ride_df.columns)

    def test_update_activity_analysis_csvs_skips_writes_for_empty_dataframe(self):
        """Ensure an empty activity dataframe does not rewrite analysis files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            for activity_type in ["Run", "Ride", "Swim", "Hike"]:
                path = output_dir / f"strava_{activity_type.lower()}_analysis.csv"
                pd.DataFrame(columns=activity_analysis_columns(activity_type)).to_csv(path, index=False)
                path.write_text(path.read_text() + "# sentinel\n")

            update_activity_analysis_csvs(pd.DataFrame(), output_dir)

            for path in activity_analysis_paths(output_dir):
                self.assertIn("# sentinel", path.read_text())

    def test_week_summary_bounds_uses_previous_week_on_weekdays(self):
        """Ensure Monday-Saturday select the previous Mon-Sun calendar week."""
        wednesday = pd.Timestamp("2026-08-12T15:00:00Z")
        start, end = week_summary_bounds(wednesday)

        self.assertEqual(start, pd.Timestamp("2026-08-03T00:00:00Z"))
        self.assertEqual(end, pd.Timestamp("2026-08-10T00:00:00Z"))

    def test_week_summary_bounds_uses_current_week_on_sunday(self):
        """Ensure Sunday selects the current Mon-Sun calendar week."""
        sunday = pd.Timestamp("2026-08-16T15:00:00Z")
        start, end = week_summary_bounds(sunday)

        self.assertEqual(start, pd.Timestamp("2026-08-10T00:00:00Z"))
        self.assertEqual(end, pd.Timestamp("2026-08-17T00:00:00Z"))

    def test_save_activities_last_week_creates_summary(self):
        """Ensure the weekly summary keeps only activities inside the week window."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            as_of = pd.Timestamp("2026-08-12T12:00:00Z")  # Wednesday -> previous week Aug 3-9
            pd.DataFrame(
                [{"type": "Run", "date": "2026-08-05T10:00:00Z", "distance_miles": 3.1}]
            ).to_csv(data_dir / "strava_run_analysis.csv", index=False)
            pd.DataFrame(
                [{"type": "Ride", "date": "2026-08-08T10:00:00Z", "distance_miles": 10.0}]
            ).to_csv(data_dir / "strava_ride_analysis.csv", index=False)
            pd.DataFrame(
                [{"type": "Hike", "date": "2026-08-11T10:00:00Z", "distance_miles": 2.0}]
            ).to_csv(data_dir / "strava_hike_analysis.csv", index=False)

            output_path = data_dir / "weekly.csv"
            result = save_activities_last_week(data_dir, output_path, as_of=as_of)

            self.assertTrue(output_path.exists())
            self.assertEqual(result.shape[0], 2)
            self.assertEqual(sorted(result["type"].tolist()), ["Ride", "Run"])

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
