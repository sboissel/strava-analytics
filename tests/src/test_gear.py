"""Tests for strava_analytics.gear."""

import unittest

import pandas as pd

from strava_analytics.gear import TRACKED_GEAR, gear_mileage_from_activities


class GearMileageFromActivitiesTests(unittest.TestCase):
    """Baseline + activity distance sums by gear_id."""

    def _tracked(self):
        return [
            {"gear_id": "g1", "name": "Shoe A", "type": "Road", "baseline_miles": 10.0},
            {"gear_id": "g2", "name": "Shoe B", "type": "Trail", "baseline_miles": 20.0},
        ]

    def test_sums_distance_plus_baseline(self):
        activities = pd.DataFrame(
            [
                {"gear_id": "g1", "distance_miles": 2.0},
                {"gear_id": "g1", "distance_miles": 3.5},
                {"gear_id": "g2", "distance_miles": 1.0},
                {"gear_id": "", "distance_miles": 99.0},
            ]
        )
        df = gear_mileage_from_activities(activities, tracked_gear=self._tracked())

        self.assertEqual(list(df.columns), ["gear_id", "name", "type", "mileage", "status"])
        self.assertEqual(df.loc[df["gear_id"] == "g1", "mileage"].iloc[0], 15.5)
        self.assertEqual(df.loc[df["gear_id"] == "g2", "mileage"].iloc[0], 21.0)
        self.assertEqual(df.loc[df["gear_id"] == "g1", "type"].iloc[0], "Road")
        self.assertTrue((df["status"] == "active").all())

    def test_missing_baseline_defaults_to_zero(self):
        tracked = [
            {"gear_id": "g1", "name": "Shoe A", "type": "Road"},
            {"gear_id": "g2", "name": "Shoe B", "type": "Trail", "baseline_miles": None},
        ]
        activities = pd.DataFrame(
            [
                {"gear_id": "g1", "distance_miles": 4.0},
                {"gear_id": "g2", "distance_miles": 1.5},
            ]
        )
        df = gear_mileage_from_activities(activities, tracked_gear=tracked)

        self.assertEqual(df.loc[df["gear_id"] == "g1", "mileage"].iloc[0], 4.0)
        self.assertEqual(df.loc[df["gear_id"] == "g2", "mileage"].iloc[0], 1.5)

    def test_tracked_shoes_with_no_activities_use_baseline(self):
        df = gear_mileage_from_activities(
            pd.DataFrame(columns=["gear_id", "distance_miles"]),
            tracked_gear=self._tracked(),
        )

        self.assertEqual(len(df), 2)
        self.assertEqual(df.loc[df["gear_id"] == "g1", "mileage"].iloc[0], 10.0)
        self.assertEqual(df.loc[df["gear_id"] == "g2", "mileage"].iloc[0], 20.0)

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
