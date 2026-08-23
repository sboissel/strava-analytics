"""Tests for dashboard import bootstrap."""

from __future__ import annotations

import importlib
import importlib.util
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_ROOT = REPO_ROOT / "dashboard"
DATA_MODULE = DASHBOARD_ROOT / "data.py"


class BootstrapImportTests(unittest.TestCase):
    """Ensure ``dashboard/`` wins over the repo ``data/`` directory."""

    def test_bootstrap_resolves_dashboard_data_module(self):
        """Repo root on ``sys.path`` must not shadow ``dashboard/data.py``."""
        saved_path = list(sys.path)
        saved_data = sys.modules.pop("data", None)
        try:
            sys.path[:] = [str(REPO_ROOT), str(DASHBOARD_ROOT)]
            if "data" in sys.modules:
                del sys.modules["data"]

            bootstrap_spec = importlib.util.spec_from_file_location(
                "_bootstrap",
                DASHBOARD_ROOT / "_bootstrap.py",
            )
            assert bootstrap_spec and bootstrap_spec.loader
            bootstrap = importlib.util.module_from_spec(bootstrap_spec)
            bootstrap_spec.loader.exec_module(bootstrap)

            spec = importlib.util.find_spec("data")
            self.assertIsNotNone(spec)
            assert spec is not None
            self.assertEqual(spec.origin, str(DATA_MODULE))
            self.assertIsNone(spec.submodule_search_locations)
            self.assertEqual(sys.path[0], str(DASHBOARD_ROOT))
        finally:
            sys.modules.pop("data", None)
            if saved_data is not None:
                sys.modules["data"] = saved_data
            sys.path[:] = saved_path


if __name__ == "__main__":
    unittest.main()
