"""Tests for dashboard.insights_data."""

import unittest

import numpy as np
import pandas as pd

from dashboard.charts import mileage_heatmap_chart
from dashboard.data import PERIOD_CONFIG
from dashboard.insights_data import (
    HEATMAP_MONTH_YEARS,
    HR_ZONE_PCT_COLUMNS,
    aggregate_aerobic_efficiency_by_period,
    aggregate_hr_zones_by_period,
    aggregate_pace_hr_by_period,
    climb_density_ft_per_mile,
    efficiency_elevation_residuals,
    eligible_aerobic_efficiency_runs,
    heatmap_showing_label,
    last_completed_iso_week_monday,
    last_full_week_hr_zone_shares,
    mileage_heatmap_matrix,
    raw_aerobic_efficiency,
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
        self.assertEqual(
            week_row["period_tooltip"].iloc[0],
            "Mar 9, 2026 - Mar 15, 2026",
        )

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


class AggregateHrZonesTests(unittest.TestCase):
    """Seconds → period sums → 100% HR-zone stack."""

    def _runs(
        self,
        dates: list[str],
        zones: list[list[float | None]],
    ) -> pd.DataFrame:
        rows = {
            "date": pd.to_datetime(dates, utc=True),
            "hr_zone_1_sec": [row[0] for row in zones],
            "hr_zone_2_sec": [row[1] for row in zones],
            "hr_zone_3_sec": [row[2] for row in zones],
            "hr_zone_4_sec": [row[3] for row in zones],
            "hr_zone_5_sec": [row[4] for row in zones],
        }
        return pd.DataFrame(rows)

    def test_seconds_sum_to_100_percent_stack(self):
        """Two runs in one week: zone seconds are summed, then scaled to 100%."""
        runs = self._runs(
            ["2026-03-10T08:00:00Z", "2026-03-12T08:00:00Z"],
            [
                [100.0, 300.0, 0.0, 0.0, 0.0],
                [0.0, 100.0, 300.0, 100.0, 0.0],
            ],
        )
        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        result = aggregate_hr_zones_by_period(runs, "Week", as_of=as_of)
        week_row = result.loc[result["period_key"] == "2026-11"]
        self.assertEqual(len(week_row), 1)
        # Combined seconds: 100, 400, 300, 100, 0 = 900
        expected = [100 / 9, 400 / 9, 300 / 9, 100 / 9, 0.0]
        actual = [float(week_row[col].iloc[0]) for col in HR_ZONE_PCT_COLUMNS]
        for got, want in zip(actual, expected, strict=True):
            self.assertAlmostEqual(got, want, places=4)
        self.assertAlmostEqual(sum(actual), 100.0, places=4)
        self.assertEqual(
            week_row["period_tooltip"].iloc[0],
            "Mar 9, 2026 - Mar 15, 2026",
        )

    def test_all_null_period_is_nan(self):
        """A period whose runs have no zone columns filled is not a 0% stack."""
        runs = self._runs(
            ["2026-03-10T08:00:00Z", "2026-03-03T08:00:00Z"],
            [
                [None, None, None, None, None],
                [200.0, 800.0, 0.0, 0.0, 0.0],
            ],
        )
        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        result = aggregate_hr_zones_by_period(runs, "Week", as_of=as_of)
        empty_week = result.loc[result["period_key"] == "2026-11"]
        filled_week = result.loc[result["period_key"] == "2026-10"]
        for col in HR_ZONE_PCT_COLUMNS:
            self.assertTrue(np.isnan(float(empty_week[col].iloc[0])))
        self.assertAlmostEqual(float(filled_week["zone_1_pct"].iloc[0]), 20.0)
        self.assertAlmostEqual(float(filled_week["zone_2_pct"].iloc[0]), 80.0)
        self.assertAlmostEqual(float(filled_week["zone_3_pct"].iloc[0]), 0.0)

    def test_all_zero_period_is_nan(self):
        """A period whose zone seconds sum to 0 is skipped like missing HR."""
        runs = self._runs(
            ["2026-03-10T08:00:00Z"],
            [[0.0, 0.0, 0.0, 0.0, 0.0]],
        )
        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        result = aggregate_hr_zones_by_period(runs, "Week", as_of=as_of)
        week_row = result.loc[result["period_key"] == "2026-11"]
        for col in HR_ZONE_PCT_COLUMNS:
            self.assertTrue(np.isnan(float(week_row[col].iloc[0])))

    def test_null_run_in_same_period_is_ignored(self):
        """Runs without zone data do not dilute a period that has HR time."""
        runs = self._runs(
            ["2026-03-10T08:00:00Z", "2026-03-11T08:00:00Z"],
            [
                [50.0, 50.0, 0.0, 0.0, 0.0],
                [None, None, None, None, None],
            ],
        )
        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        result = aggregate_hr_zones_by_period(runs, "Week", as_of=as_of)
        week_row = result.loc[result["period_key"] == "2026-11"]
        self.assertAlmostEqual(float(week_row["zone_1_pct"].iloc[0]), 50.0)
        self.assertAlmostEqual(float(week_row["zone_2_pct"].iloc[0]), 50.0)
        self.assertAlmostEqual(float(week_row["zone_5_pct"].iloc[0]), 0.0)

    def test_missing_columns_yield_nan(self):
        """No hr_zone_* columns → empty shares on the full period index."""
        runs = pd.DataFrame(
            {"date": pd.to_datetime(["2026-03-10T08:00:00Z"], utc=True)}
        )
        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        result = aggregate_hr_zones_by_period(runs, "Week", as_of=as_of)
        self.assertEqual(len(result), int(PERIOD_CONFIG["Week"]["count"]))
        for col in HR_ZONE_PCT_COLUMNS:
            self.assertTrue(result[col].isna().all())

    def test_empty_frame_keeps_period_index(self):
        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        result = aggregate_hr_zones_by_period(pd.DataFrame(), "Week", as_of=as_of)
        self.assertEqual(len(result), int(PERIOD_CONFIG["Week"]["count"]))
        self.assertTrue(result["zone_1_pct"].isna().all())
        self.assertTrue(bool(result.loc[result["period_key"] == "2026-12", "in_progress"].iloc[0]))

    def test_last_completed_iso_week_skips_current_week(self):
        """Mid-week and Sunday both treat the current ISO week as in progress."""
        wednesday = pd.Timestamp("2026-03-11T12:00:00Z")  # Wed of ISO week 11
        sunday = pd.Timestamp("2026-03-15T12:00:00Z")  # Sun of ISO week 11
        monday = last_completed_iso_week_monday(wednesday)
        self.assertEqual(monday, pd.Timestamp("2026-03-02T00:00:00Z"))
        self.assertEqual(last_completed_iso_week_monday(sunday), monday)

    def test_last_full_week_hr_zone_shares(self):
        """Pie data uses the prior Mon–Sun week, not the in-progress week."""
        runs = self._runs(
            [
                "2026-03-03T08:00:00Z",  # week 10 (last full when as_of is week 11)
                "2026-03-05T08:00:00Z",
                "2026-03-10T08:00:00Z",  # week 11 (in progress — excluded)
            ],
            [
                [100.0, 300.0, 0.0, 0.0, 0.0],
                [100.0, 100.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 500.0, 500.0, 0.0],
            ],
        )
        as_of = pd.Timestamp("2026-03-12T12:00:00Z")  # Thu week 11
        result = last_full_week_hr_zone_shares(runs, as_of=as_of)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["week_key"], "2026-10")
        self.assertEqual(result["week_label"], "Mar 2, 2026 - Mar 8, 2026")
        # Combined week-10 seconds: 200, 400, 0, 0, 0 = 600
        self.assertAlmostEqual(float(result["zone_1_sec"]), 200.0, places=4)
        self.assertAlmostEqual(float(result["zone_2_sec"]), 400.0, places=4)
        self.assertAlmostEqual(float(result["zone_3_sec"]), 0.0, places=4)
        self.assertAlmostEqual(float(result["zone_1_pct"]), 200 / 6, places=4)
        self.assertAlmostEqual(float(result["zone_2_pct"]), 400 / 6, places=4)
        self.assertAlmostEqual(float(result["zone_3_pct"]), 0.0, places=4)

    def test_last_full_week_hr_zone_shares_empty_week(self):
        runs = self._runs(
            ["2026-03-10T08:00:00Z"],
            [[100.0, 0.0, 0.0, 0.0, 0.0]],
        )
        as_of = pd.Timestamp("2026-03-12T12:00:00Z")
        result = last_full_week_hr_zone_shares(runs, as_of=as_of)
        self.assertEqual(result["week_key"], "2026-10")
        self.assertEqual(result["week_label"], "Mar 2, 2026 - Mar 8, 2026")
        self.assertNotIn("zone_1_pct", result)


class AerobicEfficiencyTests(unittest.TestCase):
    """Raw efficiency, climb density, OLS residuals, and period medians."""

    def test_raw_efficiency_is_mph_per_bpm(self):
        """480 sec/mi at 150 bpm → 7.5 mph / 150 = 0.05 mph per bpm."""
        value = float(raw_aerobic_efficiency(480.0, 150.0))
        self.assertAlmostEqual(value, (3600.0 / 480.0) / 150.0, places=7)
        self.assertAlmostEqual(value, 0.05, places=7)

    def test_raw_efficiency_invalid_inputs_are_nan(self):
        out = raw_aerobic_efficiency([480.0, 0.0, np.nan, 480.0], [150.0, 150.0, 150.0, 0.0])
        self.assertAlmostEqual(float(out[0]), 0.05, places=7)
        self.assertTrue(np.isnan(out[1]))
        self.assertTrue(np.isnan(out[2]))
        self.assertTrue(np.isnan(out[3]))

    def test_climb_density_ft_per_mile(self):
        self.assertAlmostEqual(float(climb_density_ft_per_mile(500.0, 10.0)), 50.0)
        self.assertTrue(np.isnan(float(climb_density_ft_per_mile(100.0, 0.0))))
        self.assertTrue(np.isnan(float(climb_density_ft_per_mile(100.0, 1e-9))))
        # Missing elevation counts as flat (0 ft/mi) when distance is valid.
        self.assertAlmostEqual(float(climb_density_ft_per_mile(np.nan, 8.0)), 0.0)

    def test_two_point_fit_residuals_are_zero(self):
        residuals = efficiency_elevation_residuals([0.05, 0.04], [0.0, 100.0])
        self.assertEqual(len(residuals), 2)
        self.assertAlmostEqual(float(residuals[0]), 0.0, places=10)
        self.assertAlmostEqual(float(residuals[1]), 0.0, places=10)

    def test_point_above_the_line_has_positive_residual(self):
        """Higher residual means better than expected for that climb."""
        residuals = efficiency_elevation_residuals([0.0, 10.0, 0.0], [0.0, 1.0, 2.0])
        self.assertGreater(float(residuals[1]), 0.0)
        self.assertLess(float(residuals[0]), 0.0)
        self.assertLess(float(residuals[2]), 0.0)

    def test_single_point_cannot_fit(self):
        residuals = efficiency_elevation_residuals([0.05], [40.0])
        self.assertTrue(np.isnan(float(residuals[0])))

    def test_race_runs_are_excluded(self):
        runs = pd.DataFrame(
            {
                "date": pd.to_datetime(
                    ["2026-03-10T08:00:00Z", "2026-03-11T08:00:00Z", "2026-03-12T08:00:00Z"],
                    utc=True,
                ),
                "avg_pace_sec": [480.0, 480.0, 300.0],
                "avg_hr": [150.0, 150.0, 90.0],
                "distance_miles": [5.0, 5.0, 5.0],
                "elevation_gain_ft": [0.0, 100.0, 0.0],
                "race": [False, False, True],
            }
        )
        eligible = eligible_aerobic_efficiency_runs(runs)
        self.assertEqual(len(eligible), 2)
        self.assertTrue((eligible["race"] == False).all())  # noqa: E712

    def test_median_residual_by_period_and_nan_gaps(self):
        """Two runs in one week: median residual; empty weeks stay NaN."""
        runs = pd.DataFrame(
            {
                "date": pd.to_datetime(
                    [
                        "2026-03-10T08:00:00Z",
                        "2026-03-12T08:00:00Z",
                        "2026-03-03T08:00:00Z",
                    ],
                    utc=True,
                ),
                "avg_pace_sec": [480.0, 480.0, 480.0],
                "avg_hr": [150.0, 140.0, 150.0],
                "distance_miles": [6.0, 6.0, 6.0],
                "elevation_gain_ft": [0.0, 120.0, 0.0],
                "race": [False, False, False],
            }
        )
        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        result = aggregate_aerobic_efficiency_by_period(runs, "Week", as_of=as_of)
        week_11 = result.loc[result["period_key"] == "2026-11"]
        week_10 = result.loc[result["period_key"] == "2026-10"]
        empty_week = result.loc[result["period_key"] == "2026-09"]
        self.assertEqual(len(week_11), 1)
        self.assertFalse(np.isnan(float(week_11["residual"].iloc[0])))
        self.assertFalse(np.isnan(float(week_10["residual"].iloc[0])))
        self.assertTrue(np.isnan(float(empty_week["residual"].iloc[0])))
        self.assertEqual(
            week_11["period_tooltip"].iloc[0],
            "Mar 9, 2026 - Mar 15, 2026",
        )
        # Median of the two week-11 residuals matches a direct residual fit.
        eligible = eligible_aerobic_efficiency_runs(runs)
        eligible = eligible.copy()
        eligible["residual"] = efficiency_elevation_residuals(
            eligible["efficiency"].to_numpy(),
            eligible["elev_ft_per_mile"].to_numpy(),
        )
        week_11_runs = eligible.loc[eligible["date"] >= pd.Timestamp("2026-03-09", tz="UTC")]
        week_11_runs = week_11_runs.loc[
            week_11_runs["date"] < pd.Timestamp("2026-03-16", tz="UTC")
        ]
        expected = float(week_11_runs["residual"].median())
        self.assertAlmostEqual(float(week_11["residual"].iloc[0]), expected, places=10)

    def test_race_does_not_enter_period_median(self):
        """A race in the same week is dropped before the residual fit."""
        training = pd.DataFrame(
            {
                "date": pd.to_datetime(
                    ["2026-03-10T08:00:00Z", "2026-03-11T08:00:00Z"],
                    utc=True,
                ),
                "avg_pace_sec": [480.0, 480.0],
                "avg_hr": [150.0, 150.0],
                "distance_miles": [5.0, 5.0],
                "elevation_gain_ft": [0.0, 100.0],
                "race": [False, False],
            }
        )
        with_race = pd.concat(
            [
                training,
                pd.DataFrame(
                    {
                        "date": pd.to_datetime(["2026-03-12T08:00:00Z"], utc=True),
                        "avg_pace_sec": [300.0],
                        "avg_hr": [90.0],
                        "distance_miles": [13.1],
                        "elevation_gain_ft": [0.0],
                        "race": [True],
                    }
                ),
            ],
            ignore_index=True,
        )
        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        without = aggregate_aerobic_efficiency_by_period(training, "Week", as_of=as_of)
        with_ = aggregate_aerobic_efficiency_by_period(with_race, "Week", as_of=as_of)
        week_without = float(without.loc[without["period_key"] == "2026-11", "residual"].iloc[0])
        week_with = float(with_.loc[with_["period_key"] == "2026-11", "residual"].iloc[0])
        self.assertAlmostEqual(week_without, week_with, places=10)
        self.assertAlmostEqual(week_without, 0.0, places=8)

    def test_zero_distance_run_is_dropped(self):
        runs = pd.DataFrame(
            {
                "date": pd.to_datetime(["2026-03-10T08:00:00Z"], utc=True),
                "avg_pace_sec": [480.0],
                "avg_hr": [150.0],
                "distance_miles": [0.0],
                "elevation_gain_ft": [50.0],
                "race": [False],
            }
        )
        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        result = aggregate_aerobic_efficiency_by_period(runs, "Week", as_of=as_of)
        week_row = result.loc[result["period_key"] == "2026-11", "residual"]
        self.assertTrue(np.isnan(float(week_row.iloc[0])))

    def test_empty_frame_keeps_period_index(self):
        as_of = pd.Timestamp("2026-03-16T12:00:00Z")
        result = aggregate_aerobic_efficiency_by_period(pd.DataFrame(), "Week", as_of=as_of)
        self.assertEqual(len(result), int(PERIOD_CONFIG["Week"]["count"]))
        self.assertTrue(result["residual"].isna().all())
        self.assertTrue(
            bool(result.loc[result["period_key"] == "2026-12", "in_progress"].iloc[0])
        )


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
