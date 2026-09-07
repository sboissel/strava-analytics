"""Tests for summaries-only location backfill CLI."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from strava_analytics.backfill_locations import main
from strava_analytics.client import StravaClient
from strava_analytics.csv_io import activity_analysis_columns, write_last_activity_id


def make_client(last_activity_id: str = "0") -> StravaClient:
    """Create a StravaClient with test credentials."""
    return StravaClient(
        client_id="test_client",
        client_secret="test_secret",
        refresh_token="test_refresh",
        last_activity_id=last_activity_id,
    )


class BackfillLocationsMainTests(unittest.TestCase):
    """Test historical location backfill orchestration."""

    def test_main_pages_summaries_and_patches_empty_coords(self):
        """Ensure CLI migrates schema, fetches summaries, and fills GPS."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            write_last_activity_id(data_dir, 999)
            hike_path = data_dir / "strava_hike_analysis.csv"
            pd.DataFrame(
                [
                    {
                        "activity_id": "100",
                        "name": "Old Hike",
                        "type": "Hike",
                        "date": "2024-01-01T00:00:00Z",
                        "distance_miles": "5.0",
                        "moving_time_min": "02:00:00",
                        "elapsed_time_min": "02:10:00",
                        "elevation_gain_ft": "1000",
                        "avg_pace": "24:00",
                        "avg_pace_sec": "1440",
                        "max_pace": "12:00",
                        "max_pace_sec": "720",
                    }
                ]
            ).to_csv(hike_path, index=False)

            client = make_client(last_activity_id="999")
            client.access_token = "token"
            summaries = [
                {"id": 200, "type": "Run", "start_latlng": [1.0, 2.0]},
                {"id": 100, "type": "Hike", "start_latlng": [37.1, -3.6]},
            ]

            with patch(
                "strava_analytics.backfill_locations.StravaClient.from_env", return_value=client
            ), patch.object(
                client, "refresh_access_token", return_value={"access_token": "token"}
            ), patch.object(
                client, "get_activity_summaries", return_value=summaries
            ) as summaries_mock:
                filled = main(data_dir=data_dir)

            summaries_mock.assert_called_once()
            kwargs = summaries_mock.call_args.kwargs
            self.assertEqual(kwargs["stop_when_ids_seen"], {"100"})
            self.assertEqual(filled, 1)

            hike_df = pd.read_csv(hike_path)
            for col in activity_analysis_columns("Hike"):
                self.assertIn(col, hike_df.columns)
            self.assertEqual(float(hike_df.iloc[0]["start_lat"]), 37.1)
            self.assertEqual(float(hike_df.iloc[0]["start_lng"]), -3.6)

    def test_main_skips_fetch_when_nothing_missing(self):
        """Ensure CLI exits early when every row already has GPS."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            write_last_activity_id(data_dir, 1)
            columns = activity_analysis_columns("Hike")
            row = {col: "" for col in columns}
            row.update(
                {
                    "activity_id": "100",
                    "name": "Located Hike",
                    "type": "Hike",
                    "date": "2024-01-01T00:00:00Z",
                    "distance_miles": "5.0",
                    "moving_time_min": "02:00:00",
                    "elapsed_time_min": "02:10:00",
                    "elevation_gain_ft": "1000",
                    "avg_pace": "24:00",
                    "avg_pace_sec": "1440",
                    "max_pace": "12:00",
                    "max_pace_sec": "720",
                    "start_lat": "37.1",
                    "start_lng": "-3.6",
                }
            )
            pd.DataFrame([row], columns=columns).to_csv(
                data_dir / "strava_hike_analysis.csv", index=False
            )

            with patch(
                "strava_analytics.backfill_locations.StravaClient.from_env"
            ) as from_env_mock:
                filled = main(data_dir=data_dir)

            self.assertEqual(filled, 0)
            from_env_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
