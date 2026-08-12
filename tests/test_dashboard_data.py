"""Tests for dashboard data helpers."""

import unittest

import pandas as pd

from dashboard.data import key_indicators


class KeyIndicatorsTests(unittest.TestCase):
    """Test key indicator week/month windows."""

    def _runs(self, dates: list[str]) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "date": pd.to_datetime(dates, utc=True),
                "distance_miles": [5.0] * len(dates),
                "mt_min_easy": [30.0] * len(dates),
                "mt_min_hard": [10.0] * len(dates),
                "%_easy": [75.0] * len(dates),
            }
        )

    def test_current_period_key_week(self):
        """ISO week key should match the Monday of the containing week."""
        sunday = pd.Timestamp("2026-03-15T12:00:00Z")
        from dashboard.data import current_period_key

        self.assertEqual(current_period_key("Week", sunday), "2026-11")

    def test_key_indicators_uses_previous_week_on_monday(self):
        """Monday should use the previous Mon–Sun week for last-week KPIs."""
        monday = pd.Timestamp("2026-03-16T12:00:00Z")
        runs = self._runs(
            [
                "2026-03-09T08:00:00Z",
                "2026-03-15T08:00:00Z",
                "2026-03-16T08:00:00Z",
            ]
        )
        indicators = key_indicators(runs, as_of=monday)
        self.assertEqual(indicators["miles_last_week"], 10.0)

    def test_key_indicators_uses_current_week_on_sunday(self):
        """Sunday should use the current Mon–Sun week, matching week_summary_bounds."""
        sunday = pd.Timestamp("2026-03-15T12:00:00Z")
        runs = self._runs(
            [
                "2026-03-09T08:00:00Z",
                "2026-03-15T08:00:00Z",
            ]
        )
        indicators = key_indicators(runs, as_of=sunday)
        self.assertEqual(indicators["miles_last_week"], 10.0)


if __name__ == "__main__":
    unittest.main()
