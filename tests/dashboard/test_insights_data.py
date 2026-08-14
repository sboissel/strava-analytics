"""Tests for dashboard.insights_data."""

import unittest

import numpy as np
import pandas as pd

from dashboard.charts import mileage_heatmap_chart
from dashboard.data import PERIOD_CONFIG
from dashboard.insights_data import (
    HEATMAP_MONTH_YEARS,
    aggregate_pace_hr_by_period,
    heatmap_showing_label,
    mileage_heatmap_matrix,
)


class AggregatePaceHrTests(unittest.TestCase):
    """Time-weighted HR aggregation per calendar period."""

    def _pace_runs(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "date": pd.to_datetime(
                    ["2026-03-10T08:00:00Z", "2026-03-12T08:00:00Z"],
                    utc=True,
                ),
                "seconds_800_830": [600.0, 300.0],
                "avg_hr_800_830": [150.0, 160.0],
            }
        )

    def test_weighted_hr_single_period(self):
        """HR should be time-weighted within a week."""
        pace_runs = self._pace_runs()
        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        result = aggregate_pace_hr_by_period(
            pace_runs, "Week", "800_830", as_of=as_of
        )
        week_row = result.loc[result["period_key"] == "2026-11"]
        self.assertEqual(len(week_row), 1)
        expected = (150.0 * 600 + 160.0 * 300) / 900.0
        self.assertAlmostEqual(float(week_row["avg_hr"].iloc[0]), expected, places=4)

    def test_weighted_hr_ignores_zero_seconds(self):
        """Rows with zero seconds should not contribute."""
        pace_runs = pd.DataFrame(
            {
                "date": pd.to_datetime(["2026-03-10T08:00:00Z"], utc=True),
                "seconds_800_830": [0.0],
                "avg_hr_800_830": [150.0],
            }
        )
        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        result = aggregate_pace_hr_by_period(
            pace_runs, "Week", "800_830", as_of=as_of
        )
        week_row = result.loc[result["period_key"] == "2026-11", "avg_hr"]
        self.assertTrue(np.isnan(float(week_row.iloc[0])))


class MileageHeatmapTests(unittest.TestCase):
    """Adaptive heatmap matrix layouts."""

    def _runs(self, dates: list[str], miles: list[float]) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "date": pd.to_datetime(dates, utc=True),
                "distance_miles": miles,
            }
        )

    def test_year_grain_horizontal_layout(self):
        """Year grain uses a single Miles row with year columns."""
        runs = self._runs(
            ["2024-06-15T08:00:00Z", "2025-08-20T08:00:00Z", "2026-02-10T08:00:00Z"],
            [10.0, 20.0, 5.0],
        )
        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        matrix, y_labels, x_labels, title, _tooltips = mileage_heatmap_matrix(
            runs, "Year", as_of=as_of
        )
        self.assertEqual(y_labels, ["Miles"])
        self.assertEqual(len(x_labels), int(PERIOD_CONFIG["Year"]["count"]))
        self.assertIn("2024", x_labels)
        self.assertIn("2026", x_labels)
        self.assertEqual(matrix.shape[0], 1)
        idx_2025 = x_labels.index("2025")
        self.assertAlmostEqual(float(matrix[0, idx_2025]), 20.0)
        self.assertIn("Yearly", title)

    def test_year_grain_chart_labels_every_year_on_xaxis(self):
        """Year heatmap chart exposes every year on the x-axis (no auto-thinning)."""
        runs = self._runs(
            ["2024-06-15T08:00:00Z", "2025-08-20T08:00:00Z", "2026-02-10T08:00:00Z"],
            [10.0, 20.0, 5.0],
        )
        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        matrix, y_labels, x_labels, title, _tooltips = mileage_heatmap_matrix(
            runs, "Year", as_of=as_of
        )
        fig = mileage_heatmap_chart(
            matrix, y_labels, x_labels, title=title, grain="Year"
        )
        self.assertEqual(fig.layout.xaxis.tickmode, "array")
        self.assertEqual(list(fig.layout.xaxis.tickvals), x_labels)
        self.assertEqual(list(fig.layout.xaxis.ticktext), x_labels)
        self.assertFalse(fig.layout.yaxis.showticklabels)

    def test_month_grain_year_by_month_grid(self):
        """Month grain uses 10 year rows and Jan–Dec columns."""
        runs = self._runs(
            ["2025-01-15T08:00:00Z", "2025-03-20T08:00:00Z", "2026-02-10T08:00:00Z"],
            [5.0, 7.0, 3.0],
        )
        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        matrix, y_labels, x_labels, title, _tooltips = mileage_heatmap_matrix(
            runs, "Month", as_of=as_of
        )
        self.assertEqual(x_labels[0], "Jan")
        self.assertEqual(x_labels[-1], "Dec")
        self.assertEqual(len(y_labels), HEATMAP_MONTH_YEARS)
        self.assertIn("2025", y_labels)
        self.assertIn("2026", y_labels)
        jan_2025_idx = y_labels.index("2025")
        mar_2025_idx = y_labels.index("2025")
        self.assertAlmostEqual(float(matrix[jan_2025_idx, 0]), 5.0)
        self.assertAlmostEqual(float(matrix[mar_2025_idx, 2]), 7.0)
        self.assertIn("10 Years", title)

    def test_month_grain_chart_labels_every_year_on_yaxis(self):
        """Month heatmap chart exposes every year on the y-axis (no auto-thinning)."""
        runs = self._runs(
            ["2025-01-15T08:00:00Z", "2025-03-20T08:00:00Z", "2026-02-10T08:00:00Z"],
            [5.0, 7.0, 3.0],
        )
        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        matrix, y_labels, x_labels, title, _tooltips = mileage_heatmap_matrix(
            runs, "Month", as_of=as_of
        )
        fig = mileage_heatmap_chart(
            matrix, y_labels, x_labels, title=title, grain="Month"
        )
        self.assertEqual(fig.layout.yaxis.tickmode, "array")
        self.assertEqual(list(fig.layout.yaxis.tickvals), y_labels)
        self.assertEqual(list(fig.layout.yaxis.ticktext), y_labels)
        self.assertEqual(len(y_labels), HEATMAP_MONTH_YEARS)

    def test_week_grain_week_by_month_grid(self):
        """Week grain uses Week 1–5 rows and month columns for the last 24 months."""
        runs = self._runs(
            ["2026-03-02T08:00:00Z", "2026-03-09T08:00:00Z"],
            [4.0, 6.0],
        )
        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        matrix, y_labels, x_labels, title, tooltips = mileage_heatmap_matrix(
            runs, "Week", as_of=as_of
        )
        self.assertEqual(y_labels, ["Week 1", "Week 2", "Week 3", "Week 4", "Week 5"])
        self.assertEqual(len(x_labels), 24)
        self.assertIn("Mar '26", x_labels)
        mar_idx = x_labels.index("Mar '26")
        self.assertAlmostEqual(float(matrix[0, mar_idx]), 4.0)
        self.assertAlmostEqual(float(matrix[1, mar_idx]), 6.0)
        # March 2026 has Mondays on the 2nd, 9th, 16th, 23rd, and 30th — Weeks
        # 3–5 exist but have no runs, so they are 0.0 (not NaN gaps).
        self.assertAlmostEqual(float(matrix[2, mar_idx]), 0.0)
        self.assertAlmostEqual(float(matrix[3, mar_idx]), 0.0)
        self.assertAlmostEqual(float(matrix[4, mar_idx]), 0.0)
        self.assertIn("2 Years", title)
        self.assertEqual(tooltips[0, mar_idx], "March 2, 2026 - March 8, 2026")
        self.assertEqual(tooltips[1, mar_idx], "March 9, 2026 - March 15, 2026")

    def test_week_grain_absent_week_slot_is_nan_zero_miles_is_zero(self):
        """No Week 5 Monday → NaN; existing week with no runs → 0.0."""
        # Feb 2026 Mondays: 2, 9, 16, 23 (no Week 5). One run in Week 1 only.
        runs = self._runs(["2026-02-03T08:00:00Z"], [5.0])
        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        matrix, _y, x_labels, _title, tooltips = mileage_heatmap_matrix(
            runs, "Week", as_of=as_of
        )
        feb_idx = x_labels.index("Feb '26")
        self.assertAlmostEqual(float(matrix[0, feb_idx]), 5.0)
        self.assertAlmostEqual(float(matrix[1, feb_idx]), 0.0)
        self.assertAlmostEqual(float(matrix[2, feb_idx]), 0.0)
        self.assertAlmostEqual(float(matrix[3, feb_idx]), 0.0)
        self.assertTrue(np.isnan(matrix[4, feb_idx]))
        self.assertEqual(tooltips[4, feb_idx], "")
        self.assertEqual(tooltips[1, feb_idx], "February 9, 2026 - February 15, 2026")

    def test_week_grain_tooltips_are_iso_week_ranges(self):
        """Week hover labels are Mon–Sun full-date ranges for the cell's slot."""
        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        matrix, _y, x_labels, _title, tooltips = mileage_heatmap_matrix(
            self._runs([], []), "Week", as_of=as_of
        )
        jan_idx = x_labels.index("Jan '26")
        # First Monday in January 2026 is the 5th (ISO week Mon–Sun).
        self.assertEqual(tooltips[0, jan_idx], "January 5, 2026 - January 11, 2026")
        self.assertAlmostEqual(float(matrix[0, jan_idx]), 0.0)
        # Week 5 of Dec 2025 starts Mon Dec 29 (spans into early January).
        dec_idx = x_labels.index("Dec '25")
        self.assertEqual(tooltips[4, dec_idx], "December 29, 2025 - January 4, 2026")
        self.assertAlmostEqual(float(matrix[4, dec_idx]), 0.0)

    def test_day_grain_month_by_day_grid(self):
        """Day grain uses month rows and day-of-month columns for the last 12 months."""
        runs = self._runs(
            ["2026-03-14T08:00:00Z", "2026-03-15T08:00:00Z"],
            [3.0, 5.0],
        )
        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        matrix, y_labels, x_labels, title, _tooltips = mileage_heatmap_matrix(
            runs, "Day", as_of=as_of
        )
        self.assertEqual(x_labels[0], "1")
        self.assertEqual(x_labels[-1], "31")
        self.assertEqual(len(y_labels), 12)
        self.assertIn("Mar, 26", y_labels)
        mar_idx = y_labels.index("Mar, 26")
        self.assertAlmostEqual(float(matrix[mar_idx, 13]), 3.0)
        self.assertAlmostEqual(float(matrix[mar_idx, 14]), 5.0)
        self.assertIn("12 Months", title)


class HeatmapShowingLabelTests(unittest.TestCase):
    """Heatmap window labels for dashboard controls."""

    def test_labels_match_heatmap_windows(self):
        self.assertEqual(heatmap_showing_label("Year"), "Last 10 years")
        self.assertEqual(heatmap_showing_label("Month"), "Last 10 years × months")
        self.assertEqual(heatmap_showing_label("Week"), "Last 2 years")
        self.assertEqual(heatmap_showing_label("Day"), "Last 1 year")


if __name__ == "__main__":
    unittest.main()
