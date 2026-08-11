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

import strava_analytics.strava as strava_module


class StravaApiTests(unittest.TestCase):
    """Test Strava API request helpers using mocked responses."""

    def test_refresh_access_token_returns_token_payload(self):
        """Ensure a successful OAuth response is returned as a dictionary."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "abc123"}

        with patch("strava_analytics.strava.requests.post", return_value=mock_response) as post_mock:
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

        with patch("strava_analytics.strava.requests.get", side_effect=[first_page, second_page]) as get_mock, patch.object(
            strava_module, "last_id", "999"
        ), patch("strava_analytics.strava.time.sleep", return_value=None):
            activities = strava_module.get_strava_activities("token")

        self.assertEqual(len(activities), 2)
        self.assertEqual(get_mock.call_count, 2)

    def test_get_streams_raises_for_failed_request(self):
        """Ensure failed stream requests raise a descriptive runtime error."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "activity not found"

        with patch("strava_analytics.strava.requests.get", return_value=mock_response):
            with self.assertRaisesRegex(RuntimeError, r"404 activity not found"):
                strava_module.get_streams(123, ["distance"], "token")

    def test_get_streams_returns_stream_payload_on_success(self):
        """Ensure successful stream requests return the parsed JSON payload."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"distance": {"data": [1, 2]}}

        with patch("strava_analytics.strava.requests.get", return_value=mock_response):
            payload = strava_module.get_streams(123, ["distance"], "token")

        self.assertEqual(payload, {"distance": {"data": [1, 2]}})


class ActivityProcessingTests(unittest.TestCase):
    """Test activity processing helpers that call the Strava API."""

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

    def test_update_run_pace_analysis_csv_skips_empty_dataframe(self):
        """Ensure an empty activity dataframe returns early without writing or calling streams."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "pace.csv"

            with patch.object(strava_module, "get_streams") as get_streams_mock:
                strava_module.update_run_pace_analysis_csv(pd.DataFrame(), "token", output_path)

            get_streams_mock.assert_not_called()
            self.assertFalse(output_path.exists())

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


if __name__ == "__main__":
    unittest.main()
