import unittest
from unittest.mock import patch

import pandas as pd

from backfill_run_pace_analysis import (
    build_run_pace_output,
    should_skip_missing_activity_error,
)
from strava import (
    compute_hr_easy_stats,
    compute_run_pace_summary_from_streams,
    is_fake_activity_id,
    pace_bin_for_seconds,
    pace_to_seconds,
    _drop_header_like_rows,
)


class RunPaceAnalysisTests(unittest.TestCase):
    def test_fake_activity_ids_are_skipped(self):
        self.assertTrue(is_fake_activity_id("FAKE123"))
        self.assertFalse(is_fake_activity_id(12345))

    def test_compute_run_pace_summary_from_streams(self):
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

    def test_ignores_runs_without_hr_data(self):
        summary = compute_run_pace_summary_from_streams(
            activity_id=456,
            distance_meters=[0.0, 1609.34],
            time_seconds=[0.0, 300.0],
            hr_values=[],
        )

        self.assertIsNone(summary)

    def test_missing_activity_404_is_skipped(self):
        self.assertTrue(
            should_skip_missing_activity_error(
                "Strava stream fetch failed for activity 19538454642: 404 {'message': 'Resource Not Found'}"
            )
        )
        self.assertFalse(
            should_skip_missing_activity_error(
                "Strava stream fetch failed for activity 19538454642: 401 {'message': 'Unauthorized'}"
            )
        )

    def test_empty_stream_payload_is_skipped(self):
        df = pd.DataFrame({"activity_id": [3132080636]})

        with patch("backfill_run_pace_analysis.get_streams", return_value={}):
            result = build_run_pace_output(df, "token")

        self.assertIsNone(result)

    def test_pace_to_seconds_parses_common_formats(self):
        self.assertEqual(pace_to_seconds(450), 450)
        self.assertEqual(pace_to_seconds("07:30"), 450)
        self.assertIsNone(pace_to_seconds("not-a-pace"))

    def test_pace_bin_for_seconds_uses_expected_labels(self):
        self.assertEqual(pace_bin_for_seconds(419), "under_700")
        self.assertEqual(pace_bin_for_seconds(420), "700_730")
        self.assertEqual(pace_bin_for_seconds(690), "over_1130")

    def test_compute_hr_easy_stats_returns_expected_durations(self):
        pct_easy, mt_min_easy, mt_min_hard = compute_hr_easy_stats(
            hr_stream=[120, 160, 140],
            time_stream=[0, 600, 1200],
            threshold=142,
        )

        self.assertEqual(pct_easy, 50.0)
        self.assertEqual(mt_min_easy, 10.0)
        self.assertEqual(mt_min_hard, 10.0)

    def test_drop_header_like_rows_removes_header_rows(self):
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


if __name__ == "__main__":
    unittest.main()
