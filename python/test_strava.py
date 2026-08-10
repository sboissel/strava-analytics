import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

os.environ.setdefault("CLIENT_ID", "test_client")
os.environ.setdefault("CLIENT_SECRET", "test_secret")
os.environ.setdefault("AUTH_TOKEN", "test_auth")
os.environ.setdefault("REFRESH_TOKEN", "test_refresh")

import strava as strava_module
from strava import (
    _drop_header_like_rows,
    compute_hr_easy_stats,
    compute_run_pace_summary_from_streams,
    format_duration,
    is_fake_activity_id,
    pace_bin_for_seconds,
    pace_seconds_from_speed,
    pace_to_seconds,
    run_pace_columns,
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

class StravaApiTests(unittest.TestCase):
    """Test Strava API request helpers using mocked responses."""

    def test_refresh_access_token_returns_token_payload(self):
        """Ensure a successful OAuth response is returned as a dictionary."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "abc123"}

        with patch("strava.requests.post", return_value=mock_response) as post_mock:
            payload = strava_module.refresh_access_token("refresh-token")

        self.assertEqual(payload, {"access_token": "abc123"})
        post_mock.assert_called_once()

    def test_get_strava_activities_paginates_until_last_known_activity(self):
        """Ensure the activity fetch loops until it reaches the latest known activity ID."""
        first_page = Mock()
        first_page.status_code = 200
        first_page.json.return_value = [{"id": 1}]

        second_page = Mock()
        second_page.status_code = 200
        second_page.json.return_value = [{"id": 999}]

        with patch("strava.requests.get", side_effect=[first_page, second_page]) as get_mock, patch.object(
            strava_module, "last_id", "999"
        ), patch("strava.time.sleep", return_value=None):
            activities = strava_module.get_strava_activities("token")

        self.assertEqual(len(activities), 2)
        self.assertEqual(get_mock.call_count, 2)

    def test_get_streams_returns_empty_dict_for_failed_request(self):
        """Ensure failed stream requests return an empty payload instead of raising."""
        mock_response = Mock()
        mock_response.status_code = 404

        with patch("strava.requests.get", return_value=mock_response):
            payload = strava_module.get_streams(123, ["distance"], "token")

        self.assertEqual(payload, {})

    def test_get_streams_returns_stream_payload_on_success(self):
        """Ensure successful stream requests return the parsed JSON payload."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"distance": {"data": [1, 2]}}

        with patch("strava.requests.get", return_value=mock_response):
            payload = strava_module.get_streams(123, ["distance"], "token")

        self.assertEqual(payload, {"distance": {"data": [1, 2]}})

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
    """Test CSV-based processing and persistence helpers."""

    def test_update_run_pace_analysis_csv_writes_summaries(self):
        """Ensure the pace-analysis CSV file is populated from mocked stream data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "pace.csv"
            existing_df = pd.DataFrame({"activity_id": [999], "seconds_under_700": [10], "avg_hr_under_700": [100]})
            existing_df.to_csv(output_path, index=False)

            activity_df = pd.DataFrame(
                [{"activity_id": 123, "type": "Run"}, {"activity_id": 456, "type": "Ride"}]
            )

            mock_streams = {
                "distance": {"data": [0.0, 1609.34]},
                "time": {"data": [0.0, 420.0]},
                "heartrate": {"data": [150.0, 150.0]},
            }

            with patch.object(strava_module, "get_streams", return_value=mock_streams):
                strava_module.update_run_pace_analysis_csv(activity_df, "token", output_path)

            written = pd.read_csv(output_path)

        self.assertIn("activity_id", written.columns)
        self.assertIn("seconds_700_730", written.columns)
        self.assertTrue(written[written["activity_id"].astype(str) == "123"].shape[0] == 1)

    def test_process_activities_enriches_run_rows(self):
        """Ensure processed activities include the expected run-specific enrichment fields."""
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
            "altitude": {"data": [0.0, 0.0]},
            "time": {"data": [0.0, 600.0]},
        }

        with patch.object(strava_module, "get_streams", return_value=mock_streams), patch.object(
            strava_module.time, "sleep", return_value=None
        ):
            result = strava_module.process_activities(activities, "token")

        self.assertIn("%_easy", result.columns)
        self.assertEqual(result.loc[result["activity_id"] == 123, "avg_hr"].iloc[0], 140.0)
        self.assertEqual(result.loc[result["activity_id"] == 456, "type"].iloc[0], "Ride")

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
            result = strava_module.save_activities_last_week([first_file, second_file], output_path)

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
