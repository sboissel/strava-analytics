import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from strava_analytics.client import StravaClient
from strava_analytics.csv_io import read_last_activity_id, write_last_activity_id
from strava_analytics.pipeline import main


def make_client(last_activity_id: str = "0") -> StravaClient:
    """Create a StravaClient with test credentials and an optional last activity ID."""
    return StravaClient(
        client_id="test_client",
        client_secret="test_secret",
        refresh_token="test_refresh",
        last_activity_id=last_activity_id,
    )


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

            with patch("strava_analytics.pipeline.StravaClient.from_env", return_value=client), patch.object(
                client, "refresh_access_token", return_value={"access_token": "token"}
            ), patch.object(client, "get_activities", return_value=[]), patch(
                "strava_analytics.pipeline.process_activities", return_value=(pd.DataFrame(), [])
            ) as process_mock, patch(
                "strava_analytics.pipeline.update_activity_analysis_csvs"
            ) as update_csvs_mock, patch(
                "strava_analytics.pipeline.update_run_pace_analysis_csv"
            ) as update_pace_mock, patch(
                "strava_analytics.pipeline.update_gear_mileage_csv"
            ) as update_gear_mock:
                main(data_dir=data_dir)

            process_mock.assert_called_once()
            update_csvs_mock.assert_not_called()
            update_pace_mock.assert_not_called()
            update_gear_mock.assert_called_once_with(client.get_gear, data_dir)
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

            with patch("strava_analytics.pipeline.StravaClient.from_env", return_value=client), patch.object(
                client, "refresh_access_token", return_value={"access_token": "token"}
            ), patch.object(client, "get_activities", return_value=[{"id": 99}]), patch(
                "strava_analytics.pipeline.process_activities",
                return_value=(new_df, pace_summaries),
            ), patch(
                "strava_analytics.pipeline.update_activity_analysis_csvs"
            ) as update_csvs_mock, patch(
                "strava_analytics.pipeline.update_run_pace_analysis_csv"
            ) as update_pace_mock, patch(
                "strava_analytics.pipeline.update_gear_mileage_csv"
            ) as update_gear_mock:
                main(data_dir=data_dir)

            update_csvs_mock.assert_called_once()
            update_pace_mock.assert_called_once_with(
                pace_summaries, data_dir / "strava_run_pace_analysis.csv"
            )
            update_gear_mock.assert_called_once_with(client.get_gear, data_dir)
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

            with patch("strava_analytics.pipeline.REPO_ROOT", repo_root), patch(
                "strava_analytics.pipeline.StravaClient.from_env", return_value=client
            ) as from_env_mock, patch.object(
                client, "refresh_access_token", return_value={"access_token": "token"}
            ), patch.object(client, "get_activities", return_value=[]), patch(
                "strava_analytics.pipeline.process_activities", return_value=(pd.DataFrame(), [])
            ), patch(
                "strava_analytics.pipeline.update_gear_mileage_csv"
            ):
                main()

            from_env_mock.assert_called_once_with(data_dir=data_dir)
            self.assertTrue((data_dir / "activities_last_week.csv").exists())


if __name__ == "__main__":
    unittest.main()


if __name__ == "__main__":
    unittest.main()
