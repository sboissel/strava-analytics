"""Tests for shoe mileage loading and wear colors."""

import tempfile
import unittest
from pathlib import Path

from dashboard.data import load_gear
from dashboard.theme import (
    SHOE_MILEAGE_GOAL,
    TRAFFIC_GREEN,
    TRAFFIC_ORANGE,
    TRAFFIC_RED,
    shoe_wear_color,
)
from dashboard.ui import shoe_kpi_cards_html


class LoadGearTests(unittest.TestCase):
    """strava_gear.csv loading."""

    def test_loads_mileage_and_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            (data_dir / "strava_gear.csv").write_text(
                "gear_id,name,type,mileage,status\n"
                "g1,Hoka Mach 7,Speed,12.0,active\n"
                "g2,Old Shoe,Road,401.0,retired\n"
            )
            gear = load_gear(data_dir)

        self.assertEqual(len(gear), 2)
        self.assertEqual(gear.loc[0, "name"], "Hoka Mach 7")
        self.assertEqual(gear.loc[0, "type"], "Speed")
        self.assertEqual(gear.loc[0, "mileage"], 12.0)
        self.assertEqual(gear.loc[1, "status"], "retired")

    def test_missing_file_returns_empty_frame(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gear = load_gear(Path(tmpdir))
        self.assertTrue(gear.empty)
        self.assertEqual(
            list(gear.columns), ["gear_id", "name", "type", "mileage", "status"]
        )


class ShoeWearColorTests(unittest.TestCase):
    """Traffic-light bands for shoe wear."""

    def test_fresh_shoe_is_green(self):
        self.assertEqual(shoe_wear_color(12, SHOE_MILEAGE_GOAL), TRAFFIC_GREEN)

    def test_near_goal_is_orange(self):
        self.assertEqual(shoe_wear_color(360, SHOE_MILEAGE_GOAL), TRAFFIC_ORANGE)

    def test_at_or_over_goal_is_red(self):
        self.assertEqual(shoe_wear_color(400, SHOE_MILEAGE_GOAL), TRAFFIC_RED)
        self.assertEqual(shoe_wear_color(450, SHOE_MILEAGE_GOAL), TRAFFIC_RED)


class ShoeKpiCardsHtmlTests(unittest.TestCase):
    """Overview shoe gauge markup."""

    def test_renders_shoe_names_and_goal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            (data_dir / "strava_gear.csv").write_text(
                "gear_id,name,type,mileage,status\n"
                "g1,Nike ZoomX,Race,50.0,active\n"
                "g2,Nike Pegasus Trail 5,Trail,189.0,active\n"
            )
            html = shoe_kpi_cards_html(load_gear(data_dir))

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
