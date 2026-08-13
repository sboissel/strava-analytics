"""Tests for strava_analytics.gear."""

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from strava_analytics.activities import MILE_METERS
from strava_analytics.gear import TRACKED_GEAR, update_gear_mileage_csv


class UpdateGearMileageCsvTests(unittest.TestCase):
    """CSV sync behavior for active vs retired gear."""

    def _tracked(self):
        return [
            {"gear_id": "g1", "name": "Shoe A", "type": "Road", "baseline_miles": 10.0},
            {"gear_id": "g2", "name": "Shoe B", "type": "Trail", "baseline_miles": 20.0},
        ]

    def test_writes_strava_distance_plus_baseline(self):
        payloads = {
            "g1": {"distance": MILE_METERS * 2, "retired": False},
            "g2": {"distance": MILE_METERS * 5, "retired": False},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            path = update_gear_mileage_csv(
                payloads.__getitem__, data_dir, tracked_gear=self._tracked()
            )
            df = pd.read_csv(path)

        self.assertEqual(list(df.columns), ["gear_id", "name", "type", "mileage", "status"])
        self.assertEqual(df.loc[df["gear_id"] == "g1", "mileage"].iloc[0], 12.0)
        self.assertEqual(df.loc[df["gear_id"] == "g2", "mileage"].iloc[0], 25.0)
        self.assertEqual(df.loc[df["gear_id"] == "g1", "type"].iloc[0], "Road")
        self.assertTrue((df["status"] == "active").all())

    def test_skips_api_for_already_retired_rows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            (data_dir / "strava_gear.csv").write_text(
                "gear_id,name,type,mileage,status\n"
                "g1,Shoe A,Road,99.0,retired\n"
                "g2,Shoe B,Trail,20.0,active\n"
            )
            calls = []

            def get_gear(gear_id: str):
                calls.append(gear_id)
                return {"distance": MILE_METERS * 3, "retired": False}

            path = update_gear_mileage_csv(
                get_gear, data_dir, tracked_gear=self._tracked()
            )
            df = pd.read_csv(path)

        self.assertEqual(calls, ["g2"])
        self.assertEqual(df.loc[df["gear_id"] == "g1", "mileage"].iloc[0], 99.0)
        self.assertEqual(df.loc[df["gear_id"] == "g1", "status"].iloc[0], "retired")
        self.assertEqual(df.loc[df["gear_id"] == "g2", "mileage"].iloc[0], 23.0)

    def test_marks_newly_retired_and_preserves_untracked_rows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            (data_dir / "strava_gear.csv").write_text(
                "gear_id,name,type,mileage,status\n"
                "g_old,Old Shoe,Road,300.0,retired\n"
            )

            def get_gear(gear_id: str):
                return {"distance": MILE_METERS, "retired": gear_id == "g1"}

            path = update_gear_mileage_csv(
                get_gear, data_dir, tracked_gear=self._tracked()
            )
            df = pd.read_csv(path)

        self.assertEqual(df.loc[df["gear_id"] == "g1", "status"].iloc[0], "retired")
        self.assertEqual(df.loc[df["gear_id"] == "g1", "mileage"].iloc[0], 11.0)
        self.assertIn("g_old", df["gear_id"].tolist())

    def test_default_tracked_gear_ids(self):
        gear_ids = [item["gear_id"] for item in TRACKED_GEAR]
        self.assertEqual(
            gear_ids,
            ["g33031373", "g33031356", "g33031350", "g33031360"],
        )
        types = {item["gear_id"]: item["type"] for item in TRACKED_GEAR}
        self.assertEqual(types["g33031373"], "Speed")
        self.assertEqual(types["g33031356"], "Road")
        self.assertEqual(types["g33031350"], "Trail")
        self.assertEqual(types["g33031360"], "Race")


if __name__ == "__main__":
    unittest.main()
