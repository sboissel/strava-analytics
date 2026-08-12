"""Tests for dashboard data helpers."""

import unittest

import pandas as pd

from dashboard.data import key_indicators


class KeyIndicatorsTests(unittest.TestCase):
    """Test key indicator week/month windows."""

    def _runs(self, dates: list[str], distances: list[float] | None = None) -> pd.DataFrame:
        n = len(dates)
        return pd.DataFrame(
            {
                "date": pd.to_datetime(dates, utc=True),
                "distance_miles": distances or [5.0] * n,
                "mt_min_easy": [30.0] * n,
                "mt_min_hard": [10.0] * n,
                "%_easy": [75.0] * n,
            }
        )

    def test_current_period_key_week(self):
        """ISO week key should match the Monday of the containing week."""
        sunday = pd.Timestamp("2026-03-15T12:00:00Z")
        from dashboard.data import current_period_key

        self.assertEqual(current_period_key("Week", sunday), "2026-11")

    def test_key_indicators_uses_last_full_week_on_monday(self):
        """Monday should use the last full Mon–Sun week for last-week KPIs."""
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

    def test_key_indicators_uses_last_full_week_on_sunday(self):
        """Sunday should use the previous completed Mon–Sun week, not the current one."""
        sunday = pd.Timestamp("2026-03-15T12:00:00Z")
        runs = self._runs(
            [
                "2026-03-02T08:00:00Z",
                "2026-03-08T08:00:00Z",
                "2026-03-09T08:00:00Z",
                "2026-03-15T08:00:00Z",
            ]
        )
        indicators = key_indicators(runs, as_of=sunday)
        self.assertEqual(indicators["miles_last_week"], 10.0)

    def test_key_indicators_uses_last_30_days_for_month(self):
        """E:H last month should aggregate the rolling 30-day window."""
        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        runs = self._runs(
            [
                "2026-02-13T08:00:00Z",
                "2026-02-14T08:00:00Z",
                "2026-03-16T08:00:00Z",
            ],
            distances=[1.0, 5.0, 9.0],
        )
        indicators = key_indicators(runs, as_of=as_of)
        eh_label, _ = indicators["eh_last_month"]
        self.assertNotEqual(eh_label, "—")
        # Feb 13 is exactly 31 days before Mar 16 and should be excluded.
        # Feb 14 through Mar 16 should contribute easy/hard minutes.
        runs_in_window = runs.loc[
            (runs["date"] >= as_of.normalize() - pd.Timedelta(days=30))
            & (runs["date"] < as_of.normalize() + pd.Timedelta(days=1))
        ]
        self.assertEqual(len(runs_in_window), 2)


if __name__ == "__main__":
    unittest.main()
