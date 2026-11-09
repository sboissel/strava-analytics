import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from strava_analytics.activities import run_pace_columns
from strava_analytics.csv_io import (
    read_last_activity_id,
    update_activity_analysis_csvs,
    update_run_pace_analysis_csv,
    write_last_activity_id,
)


def _run_row(activity_id, date, gear_id):
    return {
        "activity_id": activity_id,
        "name": f"Run {activity_id}",
        "type": "Run",
        "gear_id": gear_id,
        "date": date,
    }


def _pace_row(activity_id, seconds):
    row = {col: 0 for col in run_pace_columns()}
    row["activity_id"] = activity_id
    row[run_pace_columns()[1]] = seconds
    return row


class ReprocessUpsertTests(unittest.TestCase):
    """Re-writing activities that already exist must replace, not append or reorder."""

    def test_reprocessed_run_rows_replace_in_place_and_stay_newest_first(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            update_activity_analysis_csvs(
                pd.DataFrame([
                    _run_row(3, "2026-11-08T07:00:00Z", "g_old"),
                    _run_row(2, "2026-11-05T07:00:00Z", "g_old"),
                    _run_row(1, "2026-11-01T07:00:00Z", "g_old"),
                ]),
                data_dir,
            )

            # Reprocess two older activities with corrected gear.
            update_activity_analysis_csvs(
                pd.DataFrame([
                    _run_row(2, "2026-11-05T07:00:00Z", "g_new"),
                    _run_row(1, "2026-11-01T07:00:00Z", "g_new"),
                ]),
                data_dir,
            )

            df = pd.read_csv(data_dir / "strava_run_analysis.csv")
            self.assertEqual(df["activity_id"].tolist(), [3, 2, 1])
            self.assertEqual(df["gear_id"].tolist(), ["g_old", "g_new", "g_new"])

    def test_reprocessed_pace_rows_replace_existing_rows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "strava_run_pace_analysis.csv"
            update_run_pace_analysis_csv([_pace_row(1, 10), _pace_row(2, 20), _pace_row(3, 30)], output)

            update_run_pace_analysis_csv([_pace_row(2, 99), _pace_row(1, 88)], output)

            df = pd.read_csv(output)
            first_bin = run_pace_columns()[1]
            self.assertEqual(df["activity_id"].tolist(), [1, 2, 3])
            self.assertEqual(df[first_bin].tolist(), [88, 99, 30])

    def test_new_pace_rows_are_appended(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "strava_run_pace_analysis.csv"
            update_run_pace_analysis_csv([_pace_row(1, 10)], output)
            update_run_pace_analysis_csv([_pace_row(2, 20)], output)

            df = pd.read_csv(output)
            self.assertEqual(df["activity_id"].tolist(), [1, 2])


class LastActivityIdHelperTests(unittest.TestCase):
    """Test read_last_activity_id and write_last_activity_id."""

    def test_read_and_write_last_activity_id(self):
        """Ensure last activity ID helpers round-trip through the data directory file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            write_last_activity_id(data_dir, 123)
            self.assertEqual(read_last_activity_id(data_dir), "123")

    def test_read_last_activity_id_returns_zero_when_missing(self):
        """Ensure a missing last-activity-id file defaults to zero."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            self.assertEqual(read_last_activity_id(data_dir), "0")




if __name__ == "__main__":
    unittest.main()
