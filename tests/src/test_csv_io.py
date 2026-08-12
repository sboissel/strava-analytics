import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from strava_analytics.csv_io import read_last_activity_id, write_last_activity_id


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
