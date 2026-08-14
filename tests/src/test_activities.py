import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd

from strava_analytics.activities import (
    _activity_base_row,
    _enrich_run_from_streams,
    compute_hr_zone_stats,
    compute_run_pace_summary_from_streams,
    extract_gear_id,
    format_time,
    hr_zone_pct_columns,
    last_full_week_bounds,
    pace_bin_for_seconds,
    process_activities,
    race_distance_label,
    run_pace_columns,
    speed_to_pace_seconds,
    week_summary_bounds,
)
from strava_analytics.csv_io import (
    _drop_header_like_rows,
    activity_analysis_columns,
    activity_analysis_paths,
    save_activities_last_week,
    update_activity_analysis_csvs,
    update_run_pace_analysis_csv,
)

SAMPLE_HR_ZONES = [
    {
        "score": 24.0,
        "distribution_buckets": [
            {"min": 0, "max": 115, "time": 167.0},
            {"min": 116, "max": 143, "time": 2400.0},
            {"min": 144, "max": 158, "time": 0.0},
            {"min": 159, "max": 172, "time": 0.0},
            {"min": 173, "max": -1, "time": 0.0},
        ],
        "type": "heartrate",
    },
    {
        "type": "pace",
        "distribution_buckets": [
            {"min": 0, "max": 300, "time": 100.0},
            {"min": 301, "max": -1, "time": 200.0},
        ],
    },
]


class HeartRateZoneAnalysisTests(unittest.TestCase):
    """Test compute_hr_zone_stats."""

    def test_compute_hr_zone_stats_returns_none_without_heartrate_zones(self):
        """Ensure missing heartrate zones leave easy/hard and zone %s empty."""
        empty = compute_hr_zone_stats([])
        self.assertIsNone(empty["%_easy"])
        self.assertIsNone(empty["mt_min_easy"])
        self.assertIsNone(empty["mt_min_hard"])
        for column in hr_zone_pct_columns():
            self.assertIsNone(empty[column])

        pace_only = compute_hr_zone_stats(
            [{"type": "pace", "distribution_buckets": [{"min": 0, "max": -1, "time": 60.0}]}]
        )
        self.assertIsNone(pace_only["%_easy"])

    def test_compute_hr_zone_stats_sample_payload(self):
        """Validate easy/hard and zone %s against the Strava sample heartrate zones."""
        stats = compute_hr_zone_stats(SAMPLE_HR_ZONES)
        total = 167.0 + 2400.0

        self.assertEqual(stats["%_easy"], round(total / total * 100, 1))
        self.assertEqual(stats["mt_min_easy"], round(total / 60, 1))
        self.assertEqual(stats["mt_min_hard"], 0.0)
        self.assertEqual(stats["hr_zone_1_pct"], round(167.0 / total * 100, 1))
        self.assertEqual(stats["hr_zone_2_pct"], round(2400.0 / total * 100, 1))
        self.assertEqual(stats["hr_zone_3_pct"], 0.0)
        self.assertEqual(stats["hr_zone_4_pct"], 0.0)
        self.assertEqual(stats["hr_zone_5_pct"], 0.0)

    def test_compute_hr_zone_stats_returns_none_when_all_bucket_times_zero(self):
        """Ensure all-zero heartrate bucket times are treated as missing HR."""
        stats = compute_hr_zone_stats(
            [
                {
                    "type": "heartrate",
                    "distribution_buckets": [
                        {"min": 0, "max": 115, "time": 0.0},
                        {"min": 116, "max": 143, "time": 0.0},
                    ],
                }
            ]
        )
        self.assertIsNone(stats["%_easy"])
        self.assertIsNone(stats["hr_zone_1_pct"])

    def test_compute_hr_zone_stats_handles_fewer_and_more_buckets(self):
        """Ensure first two buckets are easy, the rest hard, and zone columns pad to five."""
        three_buckets = compute_hr_zone_stats(
            [
                {
                    "type": "heartrate",
                    "distribution_buckets": [
                        {"min": 0, "max": 100, "time": 30.0},
                        {"min": 101, "max": 140, "time": 70.0},
                        {"min": 141, "max": -1, "time": 100.0},
                    ],
                }
            ]
        )
        self.assertEqual(three_buckets["%_easy"], 50.0)
        self.assertEqual(three_buckets["mt_min_easy"], round(100.0 / 60, 1))
        self.assertEqual(three_buckets["mt_min_hard"], round(100.0 / 60, 1))
        self.assertEqual(three_buckets["hr_zone_1_pct"], 15.0)
        self.assertEqual(three_buckets["hr_zone_2_pct"], 35.0)
        self.assertEqual(three_buckets["hr_zone_3_pct"], 50.0)
        self.assertIsNone(three_buckets["hr_zone_4_pct"])
        self.assertIsNone(three_buckets["hr_zone_5_pct"])

        six_buckets = compute_hr_zone_stats(
            [
                {
                    "type": "heartrate",
                    "distribution_buckets": [
                        {"min": 0, "max": 100, "time": 10.0},
                        {"min": 101, "max": 120, "time": 10.0},
                        {"min": 121, "max": 140, "time": 10.0},
                        {"min": 141, "max": 160, "time": 10.0},
                        {"min": 161, "max": 180, "time": 10.0},
                        {"min": 181, "max": -1, "time": 50.0},
                    ],
                }
            ]
        )
        self.assertEqual(six_buckets["%_easy"], 20.0)
        self.assertEqual(six_buckets["mt_min_hard"], round(80.0 / 60, 1))
        self.assertEqual(six_buckets["hr_zone_5_pct"], 10.0)
        self.assertNotIn("hr_zone_6_pct", six_buckets)


class PaceFormattingTests(unittest.TestCase):
    """Test speed_to_pace_seconds, format_time, pace_bin_for_seconds, and run_pace_columns."""

    def test_speed_and_duration_helpers_format_values(self):
        """Ensure speed conversion and time formatting return the expected values."""
        self.assertEqual(speed_to_pace_seconds(3.0), 536)
        self.assertEqual(speed_to_pace_seconds(0), None)
        self.assertEqual(format_time(536, include_hours=False), "08:56")
        self.assertEqual(format_time(3661, include_hours=True), "01:01:01")
        self.assertIsNone(format_time(None, include_hours=False))

    def test_pace_bin_for_seconds_uses_expected_labels(self):
        """Check that pace thresholds map to the expected pace-bin labels."""
        self.assertEqual(pace_bin_for_seconds(419), "under_700")
        self.assertEqual(pace_bin_for_seconds(420), "700_730")
        self.assertEqual(pace_bin_for_seconds(690), "over_1130")

    def test_run_pace_columns_returns_expected_order(self):
        """Ensure the canonical run-pace column list starts with the activity ID and includes pace bins."""
        columns = run_pace_columns()
        self.assertEqual(columns[0], "activity_id")
        self.assertIn("seconds_under_700", columns)
        self.assertIn("avg_hr_over_1130", columns)


class PaceSummaryTests(unittest.TestCase):
    """Test compute_run_pace_summary_from_streams."""

    def test_compute_run_pace_summary_from_streams_returns_none_for_empty_streams(self):
        """Ensure missing distance, time, or HR streams return no pace summary."""
        distance = [0.0, 1609.34]
        time_vals = [0.0, 420.0]
        hr = [150.0, 150.0]

        self.assertIsNone(
            compute_run_pace_summary_from_streams(1, [], time_vals, hr)
        )
        self.assertIsNone(
            compute_run_pace_summary_from_streams(1, distance, [], hr)
        )
        self.assertIsNone(
            compute_run_pace_summary_from_streams(1, distance, time_vals, [])
        )

    def test_compute_run_pace_summary_from_streams_trims_to_shared_length(self):
        """Ensure streams are trimmed to the shared prefix before binning."""
        summary = compute_run_pace_summary_from_streams(
            activity_id=123,
            distance_meters=[0.0, 1609.34, 3218.68, 99999.0],
            time_seconds=[0.0, 420.0, 900.0],
            hr_values=[150.0, 150.0, 150.0],
        )

        self.assertEqual(summary["seconds_700_730"], 420)
        self.assertEqual(summary["seconds_800_830"], 480)
        self.assertIsNone(
            compute_run_pace_summary_from_streams(
                activity_id=1,
                distance_meters=[0.0],
                time_seconds=[0.0, 420.0],
                hr_values=[150.0, 150.0],
            )
        )

    def test_compute_run_pace_summary_from_streams_skips_non_finite_samples(self):
        """Ensure non-finite distance/time samples are skipped while finite segments are scored."""
        summary = compute_run_pace_summary_from_streams(
            activity_id=123,
            distance_meters=[0.0, 1609.34, np.nan, 3218.68],
            time_seconds=[0.0, 420.0, 500.0, 900.0],
            hr_values=[150.0, 150.0, 150.0, 160.0],
        )

        self.assertEqual(summary["seconds_700_730"], 420)
        self.assertAlmostEqual(summary["avg_hr_700_730"], 150.0)
        self.assertEqual(summary["seconds_800_830"], 0)

    def test_compute_run_pace_summary_from_streams_sets_avg_hr_nan_without_valid_hr(self):
        """Ensure bins with elapsed time but no finite HR get avg_hr as NaN."""
        summary = compute_run_pace_summary_from_streams(
            activity_id=123,
            distance_meters=[0.0, 1609.34],
            time_seconds=[0.0, 420.0],
            hr_values=[150.0, np.nan],
        )

        self.assertEqual(summary["seconds_700_730"], 420)
        self.assertTrue(np.isnan(summary["avg_hr_700_730"]))

    def test_compute_run_pace_summary_from_streams(self):
        """Verify that pace-bin summaries are computed with the expected elapsed time and HR values."""
        summary = compute_run_pace_summary_from_streams(
            activity_id=123,
            distance_meters=[0.0, 1609.34, 3218.68],
            time_seconds=[0.0, 420.0, 900.0],
            hr_values=[150.0, 150.0, 150.0],
        )

        self.assertEqual(summary["activity_id"], 123)
        self.assertEqual(summary["seconds_700_730"], 420)
        self.assertAlmostEqual(summary["avg_hr_700_730"], 150.0)
        self.assertEqual(summary["seconds_800_830"], 480)
        self.assertAlmostEqual(summary["avg_hr_800_830"], 150.0)
        self.assertIn("seconds_under_700", summary)


class ActivityRowHelperTests(unittest.TestCase):
    """Test _activity_base_row and _enrich_run_from_streams."""

    def test_activity_base_row_maps_strava_fields(self):
        """Ensure a raw Strava activity is mapped into the shared analysis row shape."""
        row = _activity_base_row(
            {
                "id": 123,
                "name": "Morning Run",
                "type": "Run",
                "start_date": "2024-01-01T00:00:00Z",
                "distance": 1609.34,
                "moving_time": 600,
                "elapsed_time": 660,
                "total_elevation_gain": 30.48,
                "average_speed": 2.68,
                "max_speed": 3.0,
            }
        )

        self.assertEqual(
            row,
            {
                "activity_id": 123,
                "name": "Morning Run",
                "type": "Run",
                "gear_id": "",
                "date": "2024-01-01T00:00:00Z",
                "distance_miles": 1.0,
                "moving_time_min": "00:10:00",
                "elapsed_time_min": "00:11:00",
                "elevation_gain_ft": 100.0,
                "avg_pace": "10:00",
                "avg_pace_sec": 600,
                "max_pace": "08:56",
                "max_pace_sec": 536,
                "race": None,
            },
        )

    def test_activity_base_row_prefers_summary_gear_id(self):
        """Ensure summary ``gear_id`` is stored without needing nested gear."""
        row = _activity_base_row(
            {
                "id": 123,
                "name": "Morning Run",
                "type": "Run",
                "gear_id": "g33031373",
                "start_date": "2024-01-01T00:00:00Z",
                "distance": 1609.34,
                "moving_time": 600,
                "elapsed_time": 660,
                "total_elevation_gain": 30.48,
                "average_speed": 2.68,
                "max_speed": 3.0,
            }
        )
        self.assertEqual(row["gear_id"], "g33031373")

    def test_extract_gear_id_falls_back_to_nested_gear(self):
        """Ensure detail payloads with nested ``gear.id`` still resolve."""
        self.assertEqual(extract_gear_id({"gear": {"id": "g99"}}), "g99")
        self.assertEqual(extract_gear_id({"gear_id": "g1", "gear": {"id": "g2"}}), "g1")
        self.assertEqual(extract_gear_id({}), "")

    def test_enrich_run_from_streams_adds_hr_stats_and_pace_summary(self):
        """Ensure run rows gain HR fields/zones and return a pace summary from streams."""
        row = {"activity_id": 123}
        get_streams = Mock(
            return_value={
                "heartrate": {"data": [120.0, 160.0]},
                "distance": {"data": [0.0, 1609.34]},
                "time": {"data": [0.0, 600.0]},
            }
        )
        get_activity_zones = Mock(return_value=SAMPLE_HR_ZONES)

        pace_summary = _enrich_run_from_streams(row, 123, get_streams, get_activity_zones)

        self.assertEqual(row["avg_hr"], 140.0)
        self.assertEqual(row["max_hr"], 160)
        self.assertEqual(row["%_easy"], 100.0)
        self.assertEqual(row["mt_min_easy"], round(2567.0 / 60, 1))
        self.assertEqual(row["mt_min_hard"], 0.0)
        self.assertIn("hr_zone_1_pct", row)
        self.assertEqual(pace_summary["activity_id"], 123)
        self.assertEqual(pace_summary["seconds_1000_1030"], 600)
        get_streams.assert_called_once_with(123, ["heartrate", "distance", "time"])
        get_activity_zones.assert_called_once_with(123)

    def test_enrich_run_from_streams_skips_easy_hard_without_hr_zones(self):
        """Ensure missing heartrate zones leave easy/hard empty while stream HR still loads."""
        row = {"activity_id": 123}
        get_streams = Mock(
            return_value={
                "heartrate": {"data": [120.0, 160.0]},
                "distance": {"data": [0.0, 1609.34]},
                "time": {"data": [0.0, 600.0]},
            }
        )
        get_activity_zones = Mock(return_value=[])

        _enrich_run_from_streams(row, 123, get_streams, get_activity_zones)

        self.assertEqual(row["avg_hr"], 140.0)
        self.assertNotIn("%_easy", row)
        self.assertNotIn("hr_zone_1_pct", row)


class ActivityProcessingTests(unittest.TestCase):
    """Test process_activities."""

    def test_process_activities_enriches_run_rows_and_reuses_streams(self):
        """Ensure runs are enriched, old IDs skipped, and streams fetched once per new run."""
        activities = [
            {
                "id": 50,
                "name": "Already Processed Run",
                "type": "Run",
                "start_date": "2023-12-01T00:00:00Z",
                "distance": 1609.34,
                "moving_time": 600,
                "elapsed_time": 600,
                "total_elevation_gain": 0,
                "average_speed": 2.68,
                "max_speed": 3.0,
                "workout_type": 0,
            },
            {
                "id": 123,
                "name": "Morning Run",
                "type": "Run",
                "start_date": "2024-01-01T00:00:00Z",
                "distance": 1609.34,
                "moving_time": 600,
                "elapsed_time": 600,
                "total_elevation_gain": 0,
                "average_speed": 2.68,
                "max_speed": 3.0,
                "workout_type": 0,
            },
            {
                "id": 200,
                "name": "No HR Run",
                "type": "Run",
                "start_date": "2024-01-02T00:00:00Z",
                "distance": 1609.34,
                "moving_time": 600,
                "elapsed_time": 600,
                "total_elevation_gain": 0,
                "average_speed": 2.68,
                "max_speed": 3.0,
                "workout_type": 0,
            },
            {
                "id": 456,
                "name": "Ride",
                "type": "Ride",
                "start_date": "2024-01-01T00:00:00Z",
                "distance": 1000.0,
                "moving_time": 600,
                "elapsed_time": 600,
                "total_elevation_gain": 0,
                "average_speed": 3.0,
                "max_speed": 4.0,
                "workout_type": 0,
            },
        ]

        streams_with_hr = {
            "heartrate": {"data": [120.0, 160.0]},
            "distance": {"data": [0.0, 1609.34]},
            "time": {"data": [0.0, 600.0]},
        }
        streams_without_hr = {
            "heartrate": {"data": []},
            "distance": {"data": [0.0, 1609.34]},
            "time": {"data": [0.0, 600.0]},
        }

        def get_streams_side_effect(activity_id, keys):
            if activity_id == 123:
                return streams_with_hr
            return streams_without_hr

        get_streams = Mock(side_effect=get_streams_side_effect)
        get_activity_zones = Mock(
            side_effect=lambda activity_id: SAMPLE_HR_ZONES if activity_id == 123 else []
        )

        with patch("strava_analytics.activities.time.sleep", return_value=None):
            result, pace_summaries = process_activities(
                activities,
                get_streams,
                last_activity_id="100",
                get_activity_zones=get_activity_zones,
            )

        self.assertNotIn(50, result["activity_id"].tolist())
        self.assertIn("%_easy", result.columns)
        self.assertEqual(result.loc[result["activity_id"] == 123, "avg_hr"].iloc[0], 140.0)
        self.assertEqual(result.loc[result["activity_id"] == 123, "%_easy"].iloc[0], 100.0)
        self.assertTrue(pd.isna(result.loc[result["activity_id"] == 200, "avg_hr"].iloc[0]))
        self.assertTrue(pd.isna(result.loc[result["activity_id"] == 200, "%_easy"].iloc[0]))
        self.assertEqual(result.loc[result["activity_id"] == 456, "type"].iloc[0], "Ride")
        self.assertEqual(len(pace_summaries), 1)
        self.assertEqual(pace_summaries[0]["activity_id"], 123)
        self.assertEqual(
            get_streams.call_args_list,
            [
                ((123, ["heartrate", "distance", "time"]),),
                ((200, ["heartrate", "distance", "time"]),),
            ],
        )
        self.assertEqual(get_activity_zones.call_args_list, [((123,),), ((200,),)])

    def test_process_activities_sets_race_distance_for_races(self):
        """Ensure race runs get a race_distance bucket based on distance."""
        activities = [
            {
                "id": 301,
                "name": "5k Race",
                "type": "Run",
                "start_date": "2024-01-01T00:00:00Z",
                "distance": 5000.0,
                "moving_time": 1200,
                "elapsed_time": 1200,
                "total_elevation_gain": 0,
                "average_speed": 4.17,
                "max_speed": 5.0,
                "workout_type": 1,
            },
            {
                "id": 302,
                "name": "Trail race",
                "type": "Run",
                "start_date": "2024-01-02T00:00:00Z",
                "distance": 12000.0,
                "moving_time": 3600,
                "elapsed_time": 3600,
                "total_elevation_gain": 100,
                "average_speed": 3.33,
                "max_speed": 4.0,
                "workout_type": 1,
            },
        ]
        get_streams = Mock(return_value={"heartrate": {"data": []}, "distance": {"data": []}, "time": {"data": []}})
        get_activity_zones = Mock(return_value=[])

        with patch("strava_analytics.activities.time.sleep", return_value=None):
            result, _ = process_activities(
                activities,
                get_streams,
                last_activity_id="0",
                get_activity_zones=get_activity_zones,
            )

        self.assertEqual(result.loc[result["activity_id"] == 301, "race_distance"].iloc[0], "5k")
        self.assertEqual(result.loc[result["activity_id"] == 302, "race_distance"].iloc[0], "Other")


class RaceDistanceLabelTests(unittest.TestCase):
    """Test race_distance_label buckets."""

    def test_race_distance_label_returns_none_for_non_race(self):
        self.assertIsNone(race_distance_label(13.1, False))

    def test_race_distance_label_maps_standard_distances(self):
        self.assertEqual(race_distance_label(3.1, True), "5k")
        self.assertEqual(race_distance_label(13.1, True), "Half")
        self.assertEqual(race_distance_label(26.2, True), "Marathon")
        self.assertEqual(race_distance_label(7.5, True), "Other")


class LastFullWeekBoundsTests(unittest.TestCase):
    """Test last_full_week_bounds always uses the previous complete week."""

    def test_last_full_week_bounds_uses_previous_week_on_sunday(self):
        """Sunday should still use the previous completed Mon–Sun week."""
        sunday = pd.Timestamp("2026-08-16T15:00:00Z")
        start, end = last_full_week_bounds(sunday)

        self.assertEqual(start, pd.Timestamp("2026-08-03T00:00:00Z"))
        self.assertEqual(end, pd.Timestamp("2026-08-10T00:00:00Z"))


class CsvProcessingTests(unittest.TestCase):
    """Test CSV persistence helpers in source-file order."""

    def test_update_activity_analysis_csvs_merges_by_type(self):
        """Ensure per-type analysis CSVs are updated and existing rows are preserved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            existing_run = pd.DataFrame(
                [
                    {
                        "activity_id": "999",
                        "name": "Old Run",
                        "type": "Run",
                        "date": "2024-01-01T00:00:00Z",
                        "distance_miles": "3.0",
                        "moving_time_min": "00:30:00",
                        "elapsed_time_min": "00:30:00",
                        "elevation_gain_ft": "0",
                        "avg_pace": "10:00",
                        "avg_pace_sec": "600",
                        "max_pace": "09:00",
                        "max_pace_sec": "540",
                    }
                ]
            )
            for activity_type in ["Run", "Ride", "Swim", "Hike"]:
                path = output_dir / f"strava_{activity_type.lower()}_analysis.csv"
                if activity_type == "Run":
                    existing_run.to_csv(path, index=False)
                else:
                    pd.DataFrame(columns=activity_analysis_columns(activity_type)).to_csv(path, index=False)

            new_df = pd.DataFrame(
                [
                    {
                        "activity_id": 123,
                        "name": "New Run",
                        "type": "Run",
                        "date": "2024-02-01T00:00:00Z",
                        "distance_miles": 1.0,
                        "moving_time_min": "00:10:00",
                        "elapsed_time_min": "00:10:00",
                        "elevation_gain_ft": 0.0,
                        "avg_pace": "10:00",
                        "avg_pace_sec": 600,
                        "max_pace": "09:00",
                        "max_pace_sec": 540,
                        "avg_hr": 140.0,
                        "max_hr": 160,
                        "%_easy": 50.0,
                        "mt_min_easy": 5.0,
                        "mt_min_hard": 5.0,
                        "race": False,
                    },
                    {
                        "activity_id": 456,
                        "name": "New Ride",
                        "type": "Ride",
                        "date": "2024-02-01T00:00:00Z",
                        "distance_miles": 10.0,
                        "moving_time_min": "00:40:00",
                        "elapsed_time_min": "00:40:00",
                        "elevation_gain_ft": 100.0,
                        "avg_pace": "04:00",
                        "avg_pace_sec": 240,
                        "max_pace": "03:00",
                        "max_pace_sec": 180,
                    },
                ]
            )

            update_activity_analysis_csvs(new_df, output_dir)

            run_df = pd.read_csv(output_dir / "strava_run_analysis.csv")
            ride_df = pd.read_csv(output_dir / "strava_ride_analysis.csv")

        self.assertEqual(sorted(run_df["activity_id"].astype(str).tolist()), ["123", "999"])
        self.assertEqual(ride_df["activity_id"].astype(str).tolist(), ["456"])
        self.assertIn("avg_hr", run_df.columns)
        self.assertIn("hr_zone_1_pct", run_df.columns)
        self.assertIn("hr_zone_5_pct", run_df.columns)
        self.assertNotIn("avg_hr", ride_df.columns)

    def test_update_activity_analysis_csvs_keeps_new_row_for_duplicate_activity_id(self):
        """Ensure an activity present in both the CSV and new dataframe keeps the new values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            existing_run = pd.DataFrame(
                [
                    {
                        "activity_id": "123",
                        "name": "Old Name",
                        "type": "Run",
                        "date": "2024-01-01T00:00:00Z",
                        "distance_miles": "3.0",
                        "moving_time_min": "00:30:00",
                        "elapsed_time_min": "00:30:00",
                        "elevation_gain_ft": "0",
                        "avg_pace": "10:00",
                        "avg_pace_sec": "600",
                        "max_pace": "09:00",
                        "max_pace_sec": "540",
                    }
                ]
            )
            for activity_type in ["Run", "Ride", "Swim", "Hike"]:
                path = output_dir / f"strava_{activity_type.lower()}_analysis.csv"
                if activity_type == "Run":
                    existing_run.to_csv(path, index=False)
                else:
                    pd.DataFrame(columns=activity_analysis_columns(activity_type)).to_csv(path, index=False)

            new_df = pd.DataFrame(
                [
                    {
                        "activity_id": 123,
                        "name": "Updated Run",
                        "type": "Run",
                        "date": "2024-02-01T00:00:00Z",
                        "distance_miles": 1.0,
                        "moving_time_min": "00:10:00",
                        "elapsed_time_min": "00:10:00",
                        "elevation_gain_ft": 0.0,
                        "avg_pace": "10:00",
                        "avg_pace_sec": 600,
                        "max_pace": "09:00",
                        "max_pace_sec": 540,
                        "avg_hr": 145.0,
                        "max_hr": 165,
                        "%_easy": 40.0,
                        "mt_min_easy": 4.0,
                        "mt_min_hard": 6.0,
                        "race": False,
                    }
                ]
            )

            update_activity_analysis_csvs(new_df, output_dir)
            run_df = pd.read_csv(output_dir / "strava_run_analysis.csv")

        self.assertEqual(len(run_df), 1)
        self.assertEqual(str(run_df.iloc[0]["activity_id"]), "123")
        self.assertEqual(run_df.iloc[0]["name"], "Updated Run")
        self.assertEqual(float(run_df.iloc[0]["avg_hr"]), 145.0)

    def test_update_activity_analysis_csvs_skips_writes_for_empty_dataframe(self):
        """Ensure an empty activity dataframe does not rewrite analysis files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            for activity_type in ["Run", "Ride", "Swim", "Hike"]:
                path = output_dir / f"strava_{activity_type.lower()}_analysis.csv"
                pd.DataFrame(columns=activity_analysis_columns(activity_type)).to_csv(path, index=False)
                path.write_text(path.read_text() + "# sentinel\n")

            update_activity_analysis_csvs(pd.DataFrame(), output_dir)

            for path in activity_analysis_paths(output_dir):
                self.assertIn("# sentinel", path.read_text())

    def test_update_activity_analysis_csvs_creates_missing_file(self):
        """Ensure missing analysis CSVs are created on first update."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            new_df = pd.DataFrame(
                [
                    {
                        "activity_id": 123,
                        "name": "New Run",
                        "type": "Run",
                        "date": "2024-02-01T00:00:00Z",
                        "distance_miles": 1.0,
                        "moving_time_min": "00:10:00",
                        "elapsed_time_min": "00:10:00",
                        "elevation_gain_ft": 0.0,
                        "avg_pace": "10:00",
                        "avg_pace_sec": 600,
                        "max_pace": "09:00",
                        "max_pace_sec": 540,
                        "avg_hr": 140.0,
                        "max_hr": 160,
                        "%_easy": 50.0,
                        "mt_min_easy": 5.0,
                        "mt_min_hard": 5.0,
                        "race": False,
                    }
                ]
            )

            update_activity_analysis_csvs(new_df, output_dir)

            run_path = output_dir / "strava_run_analysis.csv"
            self.assertTrue(run_path.exists())
            run_df = pd.read_csv(run_path)
            self.assertEqual(len(run_df), 1)
            self.assertEqual(str(run_df.iloc[0]["activity_id"]), "123")

    def test_update_run_pace_analysis_csv_writes_summaries(self):
        """Ensure the pace-analysis CSV file is populated from precomputed summaries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "pace.csv"
            existing_df = pd.DataFrame({"activity_id": [999], "seconds_under_700": [10], "avg_hr_under_700": [100]})
            existing_df.to_csv(output_path, index=False)

            pace_summaries = [
                {
                    "activity_id": 123,
                    "seconds_under_700": 0,
                    "avg_hr_under_700": float("nan"),
                    "seconds_700_730": 420,
                    "avg_hr_700_730": 150.0,
                }
            ]

            update_run_pace_analysis_csv(pace_summaries, output_path)
            written = pd.read_csv(output_path)

        self.assertIn("activity_id", written.columns)
        self.assertIn("seconds_700_730", written.columns)
        self.assertTrue(written[written["activity_id"].astype(str) == "123"].shape[0] == 1)

    def test_update_run_pace_analysis_csv_skips_empty_summaries(self):
        """Ensure empty pace summaries return early without writing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "pace.csv"

            update_run_pace_analysis_csv([], output_path)

            self.assertFalse(output_path.exists())

    def test_drop_header_like_rows_removes_header_rows(self):
        """Ensure repeated header rows are removed from imported CSV-like dataframes."""
        df = pd.DataFrame(
            [
                ["activity_id", "name", "type"],
                ["123", "Run 1", "Run"],
            ],
            columns=["activity_id", "name", "type"],
        )
        cleaned = _drop_header_like_rows(df)

        self.assertEqual(cleaned.shape[0], 1)
        self.assertEqual(cleaned.iloc[0]["activity_id"], "123")

    def test_week_summary_bounds_uses_previous_week_on_monday(self):
        """Ensure Monday selects the previous Mon-Sun calendar week."""
        monday = pd.Timestamp("2026-08-10T15:00:00Z")
        start, end = week_summary_bounds(monday)

        self.assertEqual(start, pd.Timestamp("2026-08-03T00:00:00Z"))
        self.assertEqual(end, pd.Timestamp("2026-08-10T00:00:00Z"))

    def test_week_summary_bounds_uses_previous_week_on_saturday(self):
        """Ensure Saturday selects the previous Mon-Sun calendar week."""
        saturday = pd.Timestamp("2026-08-15T15:00:00Z")
        start, end = week_summary_bounds(saturday)

        self.assertEqual(start, pd.Timestamp("2026-08-03T00:00:00Z"))
        self.assertEqual(end, pd.Timestamp("2026-08-10T00:00:00Z"))

    def test_week_summary_bounds_uses_current_week_on_sunday(self):
        """Ensure Sunday selects the current Mon-Sun calendar week."""
        sunday = pd.Timestamp("2026-08-16T15:00:00Z")
        start, end = week_summary_bounds(sunday)

        self.assertEqual(start, pd.Timestamp("2026-08-10T00:00:00Z"))
        self.assertEqual(end, pd.Timestamp("2026-08-17T00:00:00Z"))

    def test_save_activities_last_week_creates_summary(self):
        """Ensure the weekly summary keeps only activities inside the week window."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            as_of = pd.Timestamp("2026-08-12T12:00:00Z")  # Wednesday -> previous week Aug 3-9
            pd.DataFrame(
                [
                    {"type": "Run", "date": "2026-08-05T10:00:00Z", "distance_miles": 3.1},
                    {"type": "Run", "date": "2026-08-01T09:00:00Z", "distance_miles": 2.0},
                ]
            ).to_csv(data_dir / "strava_run_analysis.csv", index=False)
            pd.DataFrame(
                [{"type": "Ride", "date": "2026-08-08T10:00:00Z", "distance_miles": 10.0}]
            ).to_csv(data_dir / "strava_ride_analysis.csv", index=False)
            pd.DataFrame(
                [{"type": "Swim", "date": "2026-08-01T10:00:00Z", "distance_miles": 1.0}]
            ).to_csv(data_dir / "strava_swim_analysis.csv", index=False)
            pd.DataFrame(
                [{"type": "Hike", "date": "2026-08-11T10:00:00Z", "distance_miles": 2.0}]
            ).to_csv(data_dir / "strava_hike_analysis.csv", index=False)

            output_path = data_dir / "weekly.csv"
            result = save_activities_last_week(data_dir, output_path, as_of=as_of)

            self.assertTrue(output_path.exists())
            self.assertEqual(result.shape[0], 2)
            self.assertEqual(sorted(result["type"].tolist()), ["Ride", "Run"])


if __name__ == "__main__":
    unittest.main()
