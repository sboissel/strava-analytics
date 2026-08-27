"""Tests for shoe mileage loading and wear colors."""

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from dashboard.data import load_gear
from dashboard.theme import (
    SHOE_MILEAGE_GOAL,
    TRAFFIC_GREEN,
    TRAFFIC_ORANGE,
    TRAFFIC_RED,
    shoe_wear_color,
)
from dashboard.ui import shoe_kpi_cards_html, shoe_kpi_tooltip
from strava_analytics.gear import TRACKED_GEAR


class LoadGearTests(unittest.TestCase):
    """Shoe mileage from activity gear_id sums plus TRACKED_GEAR baselines."""

    def test_sums_activity_miles_with_baseline(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            gear_id = TRACKED_GEAR[0]["gear_id"]
            pd.DataFrame(
                [
                    {
                        "activity_id": "1",
                        "name": "Run",
                        "type": "Run",
                        "gear_id": gear_id,
                        "date": "2024-01-01T00:00:00Z",
                        "distance_miles": "5.0",
                    },
                    {
                        "activity_id": "2",
                        "name": "Run 2",
                        "type": "Run",
                        "gear_id": gear_id,
                        "date": "2024-01-02T00:00:00Z",
                        "distance_miles": "3.0",
                    },
                ]
            ).to_csv(data_dir / "strava_run_analysis.csv", index=False)

            gear = load_gear(data_dir)

        row = gear.loc[gear["gear_id"] == gear_id].iloc[0]
        self.assertEqual(row["name"], TRACKED_GEAR[0]["name"])
        self.assertEqual(row["type"], TRACKED_GEAR[0]["type"])
        self.assertEqual(row["mileage"], TRACKED_GEAR[0]["baseline_miles"] + 8.0)
        self.assertEqual(row["status"], "active")
        self.assertEqual(len(gear), len(TRACKED_GEAR))

    def test_missing_activity_csvs_returns_baselines(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gear = load_gear(Path(tmpdir))
        self.assertEqual(len(gear), len(TRACKED_GEAR))
        self.assertEqual(
            list(gear.columns), ["gear_id", "name", "type", "mileage", "status"]
        )
        for item in TRACKED_GEAR:
            mileage = gear.loc[gear["gear_id"] == item["gear_id"], "mileage"].iloc[0]
            self.assertEqual(mileage, item["baseline_miles"])


class ShoeWearColorTests(unittest.TestCase):
    """Traffic-light bands for shoe wear."""

    def test_fresh_shoe_is_green(self):
        self.assertEqual(shoe_wear_color(12, SHOE_MILEAGE_GOAL), TRAFFIC_GREEN)

    def test_near_goal_is_orange(self):
        self.assertEqual(shoe_wear_color(360, SHOE_MILEAGE_GOAL), TRAFFIC_ORANGE)

    def test_at_or_over_goal_is_red(self):
        self.assertEqual(shoe_wear_color(400, SHOE_MILEAGE_GOAL), TRAFFIC_RED)
        self.assertEqual(shoe_wear_color(450, SHOE_MILEAGE_GOAL), TRAFFIC_RED)


class ShoeKpiTooltipTests(unittest.TestCase):
    """Shoes ⓘ copy explains baseline + activity miles."""

    def test_definition_mentions_baseline_and_activity_gear(self):
        tip = shoe_kpi_tooltip()
        self.assertIn("Baseline miles", tip)
        self.assertIn("gear ID", tip)
        self.assertIn("400", tip)


class ShoeKpiCardsHtmlTests(unittest.TestCase):
    """Overview shoe gauge markup."""

    def test_renders_shoe_names_and_goal(self):
        gear = pd.DataFrame(
            [
                {
                    "gear_id": "g1",
                    "name": "Nike ZoomX",
                    "type": "Race",
                    "mileage": 50.0,
                    "status": "active",
                },
                {
                    "gear_id": "g2",
                    "name": "Nike Pegasus Trail 5",
                    "type": "Trail",
                    "mileage": 189.0,
                    "status": "active",
                },
            ]
        )
        html = shoe_kpi_cards_html(gear)

        self.assertIn("Nike ZoomX", html)
        self.assertIn("Race", html)
        self.assertIn("Trail", html)
        self.assertNotIn(">active<", html)
        self.assertIn("of 400 mi", html)
        self.assertIn('id="shoe-mileage"', html)
        self.assertIn("shoe-gauge", html)
        # End-of-arc tick marks the 400 mi goal (target_progress=1.0).
        self.assertEqual(html.count("gauge-target-tick"), 2)
        # One section-level info control, not per shoe.
        self.assertEqual(html.count("kpi-info"), 1)
        # Highest mileage first.
        self.assertLess(html.index("Nike Pegasus Trail 5"), html.index("Nike ZoomX"))


if __name__ == "__main__":
    unittest.main()
