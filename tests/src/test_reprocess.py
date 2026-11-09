import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import yaml

from strava_analytics.client import StravaClient
from strava_analytics.csv_io import write_last_activity_id
from strava_analytics.reprocess import (
    DEFAULT_YAML_PATH,
    fetch_activities_by_id,
    load_activity_ids,
    main,
)


def make_client(last_activity_id: str = "0") -> StravaClient:
    """Create a StravaClient with test credentials and an optional last activity ID."""
    return StravaClient(
        client_id="test_client",
        client_secret="test_secret",
        refresh_token="test_refresh",
        last_activity_id=last_activity_id,
    )


def write_yaml(path: Path, payload) -> None:
    """Write a reprocess YAML document to ``path``."""
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")


class LoadActivityIdsTests(unittest.TestCase):
    """Test YAML parsing for reprocess activity IDs."""

    def test_loads_ints_and_digit_strings(self):
        """Ensure int and digit-string IDs are accepted in order."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "reprocess.yaml"
            write_yaml(path, {"activity_ids": [10, "20", 30]})
            self.assertEqual(load_activity_ids(path), [10, 20, 30])

    def test_loads_mapping_entries_with_id(self):
        """Ensure mapping entries with an id key are accepted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "reprocess.yaml"
            write_yaml(
                path,
                {
                    "activity_ids": [
                        {"id": 11, "reason": "wrong shoes"},
                        {"id": "22"},
                    ]
                },
            )
            self.assertEqual(load_activity_ids(path), [11, 22])

    def test_deduplicates_preserving_first_order(self):
        """Ensure duplicate IDs keep the first occurrence only."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "reprocess.yaml"
            write_yaml(path, {"activity_ids": [5, 5, 7, 5]})
            self.assertEqual(load_activity_ids(path), [5, 7])

    def test_raises_when_file_missing(self):
        """Ensure a missing YAML path raises FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            load_activity_ids(Path("/tmp/does-not-exist-reprocess.yaml"))

    def test_raises_when_activity_ids_empty(self):
        """Ensure an empty activity_ids list raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "reprocess.yaml"
            write_yaml(path, {"activity_ids": []})
            with self.assertRaisesRegex(ValueError, r"No activity IDs"):
                load_activity_ids(path)

    def test_raises_when_activity_ids_missing(self):
        """Ensure a YAML without activity_ids raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "reprocess.yaml"
            write_yaml(path, {"other": []})
            with self.assertRaisesRegex(ValueError, r"missing 'activity_ids'"):
                load_activity_ids(path)

    def test_raises_for_invalid_entry(self):
        """Ensure non-ID entries raise a clear ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "reprocess.yaml"
            write_yaml(path, {"activity_ids": ["not-an-id"]})
            with self.assertRaisesRegex(ValueError, r"Invalid activity_ids\[0\]"):
                load_activity_ids(path)


class FetchActivitiesByIdTests(unittest.TestCase):
    """Test ordered Strava detail fetches for reprocess."""

    def test_fetches_each_id_in_order(self):
        """Ensure get_activity is called once per ID and results keep order."""
        client = make_client()
        payloads = [{"id": 1}, {"id": 2}]

        with patch.object(client, "get_activity", side_effect=payloads) as get_mock, patch(
            "strava_analytics.reprocess.time.sleep", return_value=None
        ) as sleep_mock:
            activities = fetch_activities_by_id(client, [1, 2], pause_seconds=0.5)

        self.assertEqual(activities, payloads)
        self.assertEqual([call.args[0] for call in get_mock.call_args_list], [1, 2])
        sleep_mock.assert_called_once_with(0.5)

    def test_fail_fast_propagates_get_activity_error(self):
        """Ensure the first get_activity failure stops the loop."""
        client = make_client()

        with patch.object(
            client, "get_activity", side_effect=RuntimeError("Strava activity 9 not found")
        ), patch("strava_analytics.reprocess.time.sleep", return_value=None):
            with self.assertRaisesRegex(RuntimeError, r"activity 9 not found"):
                fetch_activities_by_id(client, [9, 10], pause_seconds=0)


class MainReprocessTests(unittest.TestCase):
    """Test reprocess main orchestration."""

    def test_main_reuses_pipeline_helpers_without_watermark_update(self):
        """Ensure main fetches IDs, processes with watermark 0, and writes CSVs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_dir = root / "data" / "activities"
            data_dir.mkdir(parents=True)
            write_last_activity_id(data_dir, 99)
            yaml_path = root / "reprocess.yaml"
            write_yaml(yaml_path, {"activity_ids": [50]})

            client = make_client(last_activity_id="99")
            client.access_token = "token"
            activity = {"id": 50, "type": "Run"}
            new_df = pd.DataFrame(
                [
                    {
                        "activity_id": 50,
                        "name": "Run",
                        "type": "Run",
                        "date": "2024-01-01T00:00:00Z",
                        "distance_miles": 1.0,
                    }
                ]
            )
            pace_summaries = [{"activity_id": 50, "seconds_under_700": 0}]

            with patch(
                "strava_analytics.reprocess.StravaClient.from_env", return_value=client
            ), patch.object(
                client, "refresh_access_token", return_value={"access_token": "token"}
            ), patch(
                "strava_analytics.reprocess.fetch_activities_by_id", return_value=[activity]
            ) as fetch_mock, patch(
                "strava_analytics.reprocess.process_activities",
                return_value=(new_df, pace_summaries),
            ) as process_mock, patch(
                "strava_analytics.reprocess.update_activity_analysis_csvs"
            ) as update_csvs_mock, patch(
                "strava_analytics.reprocess.update_run_pace_analysis_csv"
            ) as update_pace_mock, patch(
                "strava_analytics.reprocess.save_activities_last_week"
            ) as weekly_mock:
                main(yaml_path=yaml_path, data_dir=data_dir)

            fetch_mock.assert_called_once_with(client, [50])
            process_mock.assert_called_once()
            self.assertEqual(process_mock.call_args.args[0], [activity])
            self.assertEqual(process_mock.call_args.args[2], "0")
            update_csvs_mock.assert_called_once_with(new_df, data_dir)
            update_pace_mock.assert_called_once_with(
                pace_summaries, data_dir / "strava_run_pace_analysis.csv"
            )
            weekly_mock.assert_called_once()
            self.assertEqual((data_dir / "highest_activity_id.txt").read_text(), "99")

    def test_main_raises_when_process_returns_empty(self):
        """Ensure empty process output fails instead of writing partial state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_dir = root / "data" / "activities"
            data_dir.mkdir(parents=True)
            write_last_activity_id(data_dir, 1)
            yaml_path = root / "reprocess.yaml"
            write_yaml(yaml_path, {"activity_ids": [50]})

            client = make_client(last_activity_id="1")
            client.access_token = "token"

            with patch(
                "strava_analytics.reprocess.StravaClient.from_env", return_value=client
            ), patch.object(
                client, "refresh_access_token", return_value={"access_token": "token"}
            ), patch(
                "strava_analytics.reprocess.fetch_activities_by_id",
                return_value=[{"id": 50}],
            ), patch(
                "strava_analytics.reprocess.process_activities",
                return_value=(pd.DataFrame(), []),
            ):
                with self.assertRaisesRegex(RuntimeError, r"no activity rows"):
                    main(yaml_path=yaml_path, data_dir=data_dir)

    def test_default_yaml_path_points_at_repo_file(self):
        """Ensure the default YAML path is data/reprocess_activities.yaml."""
        self.assertEqual(DEFAULT_YAML_PATH.name, "reprocess_activities.yaml")
        self.assertEqual(DEFAULT_YAML_PATH.parent.name, "data")


if __name__ == "__main__":
    unittest.main()
