"""Tests for dashboard import bootstrap."""

from __future__ import annotations

import importlib
import importlib.util
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_ROOT = REPO_ROOT / "dashboard"
PAGES_ROOT = DASHBOARD_ROOT / "pages"
DATA_MODULE = DASHBOARD_ROOT / "data.py"
RACE_DATA_MODULE = DASHBOARD_ROOT / "race_data.py"


def _load_bootstrap():
    """Load ``dashboard/_bootstrap.py`` as ``_bootstrap`` (fresh module body)."""
    bootstrap_spec = importlib.util.spec_from_file_location(
        "_bootstrap",
        DASHBOARD_ROOT / "_bootstrap.py",
    )
    assert bootstrap_spec and bootstrap_spec.loader
    bootstrap = importlib.util.module_from_spec(bootstrap_spec)
    sys.modules["_bootstrap"] = bootstrap
    bootstrap_spec.loader.exec_module(bootstrap)
    return bootstrap


class BootstrapImportTests(unittest.TestCase):
    """Ensure ``dashboard/`` wins over the repo ``data/`` directory."""

    def test_bootstrap_resolves_dashboard_data_module(self):
        """Repo root on ``sys.path`` must not shadow ``dashboard/data.py``."""
        saved_path = list(sys.path)
        saved_data = sys.modules.pop("data", None)
        saved_bootstrap = sys.modules.pop("_bootstrap", None)
        try:
            sys.path[:] = [str(REPO_ROOT), str(DASHBOARD_ROOT)]
            if "data" in sys.modules:
                del sys.modules["data"]

            _load_bootstrap()

            spec = importlib.util.find_spec("data")
            self.assertIsNotNone(spec)
            assert spec is not None
            self.assertEqual(spec.origin, str(DATA_MODULE))
            self.assertIsNone(spec.submodule_search_locations)
            self.assertEqual(sys.path[0], str(DASHBOARD_ROOT))
        finally:
            sys.modules.pop("data", None)
            sys.modules.pop("_bootstrap", None)
            if saved_data is not None:
                sys.modules["data"] = saved_data
            if saved_bootstrap is not None:
                sys.modules["_bootstrap"] = saved_bootstrap
            sys.path[:] = saved_path

    def test_ensure_sys_path_after_path_reset(self):
        """Cached ``_bootstrap`` must still restore ``dashboard/`` on ``sys.path``."""
        saved_path = list(sys.path)
        saved_mods = {
            name: sys.modules.pop(name, None)
            for name in ("_bootstrap", "data", "race_data")
        }
        try:
            sys.path[:] = [str(DASHBOARD_ROOT), str(REPO_ROOT)]
            bootstrap = _load_bootstrap()

            # Simulate Streamlit resetting path while keeping the module cached.
            sys.path[:] = [str(PAGES_ROOT), str(REPO_ROOT)]
            sys.modules.pop("data", None)
            sys.modules.pop("race_data", None)

            bootstrap.ensure_sys_path()

            self.assertEqual(sys.path[0], str(DASHBOARD_ROOT))
            data_spec = importlib.util.find_spec("data")
            race_spec = importlib.util.find_spec("race_data")
            self.assertIsNotNone(data_spec)
            self.assertIsNotNone(race_spec)
            assert data_spec is not None and race_spec is not None
            self.assertEqual(data_spec.origin, str(DATA_MODULE))
            self.assertEqual(race_spec.origin, str(RACE_DATA_MODULE))
        finally:
            for name in ("_bootstrap", "data", "race_data"):
                sys.modules.pop(name, None)
                if saved_mods[name] is not None:
                    sys.modules[name] = saved_mods[name]
            sys.path[:] = saved_path

    def test_page_cold_start_can_import_race_data(self):
        """Pages under ``pages/`` must reach ``race_data`` without the entrypoint."""
        saved_path = list(sys.path)
        saved_mods = {
            name: sys.modules.pop(name, None)
            for name in ("_bootstrap", "data", "race_data")
        }
        try:
            sys.path[:] = [str(PAGES_ROOT), str(REPO_ROOT)]
            # Mirror page preamble: put dashboard on path, then re-ensure.
            sys.path.insert(0, str(DASHBOARD_ROOT))
            bootstrap = _load_bootstrap()
            bootstrap.ensure_sys_path()

            race_spec = importlib.util.find_spec("race_data")
            self.assertIsNotNone(race_spec)
            assert race_spec is not None
            self.assertEqual(race_spec.origin, str(RACE_DATA_MODULE))
            self.assertEqual(sys.path[0], str(DASHBOARD_ROOT))
        finally:
            for name in ("_bootstrap", "data", "race_data"):
                sys.modules.pop(name, None)
                if saved_mods[name] is not None:
                    sys.modules[name] = saved_mods[name]
            sys.path[:] = saved_path


if __name__ == "__main__":
    unittest.main()
