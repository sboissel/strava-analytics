import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from strava_analytics.strava import (
    StravaClient,
    main,
    read_last_activity_id,
    write_last_activity_id,
)


def make_client(last_activity_id: str = "0") -> StravaClient:
    """Create a StravaClient with test credentials and an optional last activity ID."""
    return StravaClient(
        client_id="test_client",
        client_secret="test_secret",
        refresh_token="test_refresh",
        last_activity_id=last_activity_id,
    )


class LastActivityIdHelperTests(unittest.TestCase):
    """Test read_last_activity_id and write_last_activity_id."""

    def test_read_and_write_last_activity_id(self):
        """Ensure last activity ID helpers round-trip through the data directory file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            write_last_activity_id(data_dir, 123)
            self.assertEqual(read_last_activity_id(data_dir), "123")

    def test_read_last_activity_id_returns_zero_when_missing(self):
        """Ensure a missing last-activity-id file defaults to zero."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            self.assertEqual(read_last_activity_id(data_dir), "0")


class StravaClientTests(unittest.TestCase):
    """Test StravaClient methods in source-file order."""

    def test_from_env_reads_credentials_and_last_activity_id(self):
        """Ensure from_env loads credentials from the environment and last activity ID from disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            (data_dir / "highest_activity_id.txt").write_text("42\n")

            env = {
                "CLIENT_ID": "env_client",
                "CLIENT_SECRET": "env_secret",
                "REFRESH_TOKEN": "env_refresh",
            }
            with patch.dict("os.environ", env, clear=False):
                client = StravaClient.from_env(data_dir=data_dir)

        self.assertEqual(client.client_id, "env_client")
        self.assertEqual(client.client_secret, "env_secret")
        self.assertEqual(client.refresh_token, "env_refresh")
        self.assertEqual(client.last_activity_id, "42")

    def test_from_env_defaults_data_dir_to_repo_data(self):
        """Ensure from_env uses the repo data directory when none is provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            data_dir = repo_root / "data"
            data_dir.mkdir()
            (data_dir / "highest_activity_id.txt").write_text("7\n")
            env = {
                "CLIENT_ID": "env_client",
                "CLIENT_SECRET": "env_secret",
                "REFRESH_TOKEN": "env_refresh",
            }
            with patch("strava_analytics.strava.REPO_ROOT", repo_root), patch.dict(
                "os.environ", env, clear=False
            ):
                client = StravaClient.from_env()

        self.assertEqual(client.last_activity_id, "7")

    def test_refresh_access_token_stores_token_on_client(self):
        """Ensure a successful OAuth response updates the client access token."""
        client = make_client()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "abc123",
            "refresh_token": "new-refresh",
        }

        with patch("strava_analytics.strava.requests.post", return_value=mock_response) as post_mock:
            payload = client.refresh_access_token()

        self.assertEqual(payload["access_token"], "abc123")
        self.assertEqual(client.access_token, "abc123")
        self.assertEqual(client.refresh_token, "new-refresh")
        post_mock.assert_called_once()

    def test_refresh_access_token_keeps_refresh_token_when_absent(self):
        """Ensure a token response without refresh_token leaves the existing value unchanged."""
        client = make_client()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "abc123"}

        with patch("strava_analytics.strava.requests.post", return_value=mock_response):
            client.refresh_access_token()

        self.assertEqual(client.access_token, "abc123")
        self.assertEqual(client.refresh_token, "test_refresh")

    def test_refresh_access_token_raises_for_failed_request(self):
        """Ensure a non-200 OAuth response raises a descriptive runtime error."""
        client = make_client()
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "unauthorized"

        with patch("strava_analytics.strava.requests.post", return_value=mock_response):
            with self.assertRaisesRegex(RuntimeError, r"401 unauthorized"):
                client.refresh_access_token()

    def test_require_access_token_raises_when_refresh_leaves_token_unset(self):
        """Ensure _require_access_token fails if refresh does not populate access_token."""
        client = make_client()

        with patch.object(client, "refresh_access_token", return_value={}):
            with self.assertRaisesRegex(RuntimeError, r"Failed to obtain an access token"):
                client.get_activities()

    def test_get_activities_paginates_until_last_known_activity(self):
        """Ensure activity fetch loops until it reaches the latest known activity ID."""
        client = make_client(last_activity_id="999")
        client.access_token = "token"

        first_page = Mock()
        first_page.status_code = 200
        first_page.json.return_value = [{"id": 1}]

        second_page = Mock()
        second_page.status_code = 200
        second_page.json.return_value = [{"id": 999}]

        with patch("strava_analytics.strava.requests.get", side_effect=[first_page, second_page]) as get_mock, patch(
            "strava_analytics.strava.time.sleep", return_value=None
        ):
            activities = client.get_activities()

        self.assertEqual(len(activities), 2)
        self.assertEqual(get_mock.call_count, 2)

    def test_get_activities_stops_on_empty_page(self):
        """Ensure activity fetch stops when a page returns no activities."""
        client = make_client(last_activity_id="999")
        client.access_token = "token"

        first_page = Mock()
        first_page.status_code = 200
        first_page.json.return_value = [{"id": 1}]

        empty_page = Mock()
        empty_page.status_code = 200
        empty_page.json.return_value = []

        with patch(
            "strava_analytics.strava.requests.get", side_effect=[first_page, empty_page]
        ) as get_mock, patch("strava_analytics.strava.time.sleep", return_value=None):
            activities = client.get_activities()

        self.assertEqual(activities, [{"id": 1}])
        self.assertEqual(get_mock.call_count, 2)

    def test_get_streams_refreshes_access_token_when_missing(self):
        """Ensure stream requests refresh the access token when none is set yet."""
        client = make_client()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"distance": {"data": [1, 2]}}

        def refresh_side_effect():
            client.access_token = "abc123"
            return {"access_token": "abc123"}

        with patch.object(client, "refresh_access_token", side_effect=refresh_side_effect) as refresh_mock, patch(
            "strava_analytics.strava.requests.get", return_value=mock_response
        ):
            payload = client.get_streams(123, ["distance"])

        refresh_mock.assert_called_once()
        self.assertEqual(payload, {"distance": {"data": [1, 2]}})

    def test_get_streams_raises_for_failed_request(self):
        """Ensure failed stream requests raise a descriptive runtime error."""
        client = make_client()
        client.access_token = "token"

        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "activity not found"

        with patch("strava_analytics.strava.requests.get", return_value=mock_response):
            with self.assertRaisesRegex(RuntimeError, r"404 activity not found"):
                client.get_streams(123, ["distance"])

    def test_get_streams_returns_stream_payload_on_success(self):
        """Ensure successful stream requests return the parsed JSON payload."""
        client = make_client()
        client.access_token = "token"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"distance": {"data": [1, 2]}}

        with patch("strava_analytics.strava.requests.get", return_value=mock_response):
            payload = client.get_streams(123, ["distance"])

        self.assertEqual(payload, {"distance": {"data": [1, 2]}})


class MainPipelineTests(unittest.TestCase):
    """Test main pipeline orchestration."""

    def test_main_skips_writes_when_no_new_activities(self):
        """Ensure main still writes the weekly summary when processing returns no rows."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            write_last_activity_id(data_dir, 1)
            for activity_type in ["run", "ride", "swim", "hike"]:
                (data_dir / f"strava_{activity_type}_analysis.csv").write_text(
                    "type,date,distance_miles\n"
                )

            client = make_client(last_activity_id="1")
            client.access_token = "token"

            with patch("strava_analytics.strava.StravaClient.from_env", return_value=client), patch.object(
                client, "refresh_access_token", return_value={"access_token": "token"}
            ), patch.object(client, "get_activities", return_value=[]), patch(
                "strava_analytics.strava.process_activities", return_value=(pd.DataFrame(), [])
            ) as process_mock, patch(
                "strava_analytics.strava.update_activity_analysis_csvs"
            ) as update_csvs_mock, patch(
                "strava_analytics.strava.update_run_pace_analysis_csv"
            ) as update_pace_mock:
                main(data_dir=data_dir)

            process_mock.assert_called_once()
            update_csvs_mock.assert_not_called()
            update_pace_mock.assert_not_called()
            self.assertTrue((data_dir / "activities_last_week.csv").exists())
            self.assertEqual(read_last_activity_id(data_dir), "1")

    def test_main_writes_analysis_when_new_activities_exist(self):
        """Ensure main updates analysis CSVs, last activity ID, and pace summary for new rows."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            write_last_activity_id(data_dir, 1)
            for activity_type in ["run", "ride", "swim", "hike"]:
                (data_dir / f"strava_{activity_type}_analysis.csv").write_text(
                    "type,date,distance_miles\n"
                )

            client = make_client(last_activity_id="1")
            client.access_token = "token"
            new_df = pd.DataFrame(
                [
                    {
                        "activity_id": 50,
                        "name": "Run",
                        "type": "Run",
                        "date": "2024-01-01T00:00:00Z",
                        "distance_miles": 1.0,
                    },
                    {
                        "activity_id": 99,
                        "name": "Ride",
                        "type": "Ride",
                        "date": "2024-01-02T00:00:00Z",
                        "distance_miles": 10.0,
                    },
                ]
            )
            pace_summaries = [{"activity_id": 50, "seconds_under_700": 0}]

            with patch("strava_analytics.strava.StravaClient.from_env", return_value=client), patch.object(
                client, "refresh_access_token", return_value={"access_token": "token"}
            ), patch.object(client, "get_activities", return_value=[{"id": 99}]), patch(
                "strava_analytics.strava.process_activities",
                return_value=(new_df, pace_summaries),
            ), patch(
                "strava_analytics.strava.update_activity_analysis_csvs"
            ) as update_csvs_mock, patch(
                "strava_analytics.strava.update_run_pace_analysis_csv"
            ) as update_pace_mock:
                main(data_dir=data_dir)

            update_csvs_mock.assert_called_once()
            update_pace_mock.assert_called_once_with(
                pace_summaries, data_dir / "strava_run_pace_analysis.csv"
            )
            self.assertEqual(read_last_activity_id(data_dir), "99")
            self.assertTrue((data_dir / "activities_last_week.csv").exists())

    def test_main_defaults_data_dir_to_repo_data(self):
        """Ensure main uses the repo data directory when none is provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            data_dir = repo_root / "data"
            data_dir.mkdir()
            write_last_activity_id(data_dir, 1)
            for activity_type in ["run", "ride", "swim", "hike"]:
                (data_dir / f"strava_{activity_type}_analysis.csv").write_text(
                    "type,date,distance_miles\n"
                )

            client = make_client(last_activity_id="1")
            client.access_token = "token"

            with patch("strava_analytics.strava.REPO_ROOT", repo_root), patch(
                "strava_analytics.strava.StravaClient.from_env", return_value=client
            ) as from_env_mock, patch.object(
                client, "refresh_access_token", return_value={"access_token": "token"}
            ), patch.object(client, "get_activities", return_value=[]), patch(
                "strava_analytics.strava.process_activities", return_value=(pd.DataFrame(), [])
            ):
                main()

            from_env_mock.assert_called_once_with(data_dir=data_dir)
            self.assertTrue((data_dir / "activities_last_week.csv").exists())


if __name__ == "__main__":
    unittest.main()
