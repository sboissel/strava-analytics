"""Tests for dashboard import bootstrap."""

from __future__ import annotations

import importlib
import importlib.util
import sys
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_ROOT = REPO_ROOT / "dashboard"
PAGES_ROOT = DASHBOARD_ROOT / "pages"
DATA_MODULE = DASHBOARD_ROOT / "data.py"
RACE_DATA_MODULE = DASHBOARD_ROOT / "race_data.py"

# Names Performance imports from race_data (keep in sync with that page).
_PERFORMANCE_RACE_DATA_IMPORTS = (
    "RACE_TABLE_DISPLAY_COLUMNS",
    "compare_race_type_options",
    "filter_race_results",
    "load_race_results",
    "race_buildup_compare_rows",
    "race_buildup_hr_coverage_sufficient",
    "race_buildup_hr_mileage_coverage",
    "race_buildup_mileage_hr_zone_shares",
    "race_buildup_side_stats",
    "race_buildup_training_periods",
    "race_buildup_weeks",
    "race_compare_choices",
    "race_date_bounds",
    "race_row_by_activity_id",
    "race_summary_meta",
    "race_table_rows",
    "race_type_options",
)


def _load_bootstrap():
    """Load ``dashboard/_bootstrap.py`` by path (same as Streamlit entrypoints)."""
    bootstrap_spec = importlib.util.spec_from_file_location(
        "_sa_dashboard_bootstrap",
        DASHBOARD_ROOT / "_bootstrap.py",
    )
    assert bootstrap_spec and bootstrap_spec.loader
    bootstrap = importlib.util.module_from_spec(bootstrap_spec)
    sys.modules["_sa_dashboard_bootstrap"] = bootstrap
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
        saved_sa = sys.modules.pop("_sa_dashboard_bootstrap", None)
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
            sys.modules.pop("_sa_dashboard_bootstrap", None)
            if saved_data is not None:
                sys.modules["data"] = saved_data
            if saved_bootstrap is not None:
                sys.modules["_bootstrap"] = saved_bootstrap
            if saved_sa is not None:
                sys.modules["_sa_dashboard_bootstrap"] = saved_sa
            sys.path[:] = saved_path

    def test_ensure_sys_path_after_path_reset(self):
        """Cached ``_bootstrap`` must still restore ``dashboard/`` on ``sys.path``."""
        saved_path = list(sys.path)
        saved_mods = {
            name: sys.modules.pop(name, None)
            for name in (
                "_bootstrap",
                "_sa_dashboard_bootstrap",
                "data",
                "race_data",
            )
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
            for name in (
                "_bootstrap",
                "_sa_dashboard_bootstrap",
                "data",
                "race_data",
            ):
                sys.modules.pop(name, None)
                if saved_mods[name] is not None:
                    sys.modules[name] = saved_mods[name]
            sys.path[:] = saved_path

    def test_page_cold_start_can_import_race_data(self):
        """Pages under ``pages/`` must reach ``race_data`` without the entrypoint."""
        saved_path = list(sys.path)
        saved_mods = {
            name: sys.modules.pop(name, None)
            for name in (
                "_bootstrap",
                "_sa_dashboard_bootstrap",
                "data",
                "race_data",
            )
        }
        try:
            sys.path[:] = [str(PAGES_ROOT), str(REPO_ROOT)]
            bootstrap = _load_bootstrap()
            bootstrap.bootstrap()

            race_spec = importlib.util.find_spec("race_data")
            self.assertIsNotNone(race_spec)
            assert race_spec is not None
            self.assertEqual(race_spec.origin, str(RACE_DATA_MODULE))
            self.assertEqual(sys.path[0], str(DASHBOARD_ROOT))
        finally:
            for name in (
                "_bootstrap",
                "_sa_dashboard_bootstrap",
                "data",
                "race_data",
            ):
                sys.modules.pop(name, None)
                if saved_mods[name] is not None:
                    sys.modules[name] = saved_mods[name]
            sys.path[:] = saved_path

    def test_path_load_wins_over_stale_bootstrap_without_ensure_sys_path(self):
        """File-path load must work even if ``sys.modules['_bootstrap']`` is stale."""
        saved_path = list(sys.path)
        saved_mods = {
            name: sys.modules.pop(name, None)
            for name in ("_bootstrap", "_sa_dashboard_bootstrap", "data", "race_data")
        }
        try:
            stale = types.ModuleType("_bootstrap")
            # Old Cloud module: import succeeds, attribute missing.
            sys.modules["_bootstrap"] = stale
            sys.path[:] = [str(PAGES_ROOT), str(REPO_ROOT)]

            bootstrap = _load_bootstrap()
            self.assertTrue(hasattr(bootstrap, "ensure_sys_path"))
            self.assertTrue(hasattr(bootstrap, "bootstrap"))
            self.assertIs(sys.modules["_bootstrap"], bootstrap)

            bootstrap.bootstrap()
            self.assertEqual(sys.path[0], str(DASHBOARD_ROOT))
        finally:
            for name in ("_bootstrap", "_sa_dashboard_bootstrap", "data", "race_data"):
                sys.modules.pop(name, None)
                if saved_mods[name] is not None:
                    sys.modules[name] = saved_mods[name]
            sys.path[:] = saved_path

    def test_refresh_replaces_stale_race_data_missing_compare_options(self):
        """Stale ``race_data`` with correct ``__file__`` but missing attrs is reloaded."""
        saved_path = list(sys.path)
        saved_mods = {
            name: sys.modules.pop(name, None)
            for name in ("_bootstrap", "_sa_dashboard_bootstrap", "data", "race_data")
        }
        try:
            sys.path[:] = [str(DASHBOARD_ROOT), str(REPO_ROOT / "src"), str(REPO_ROOT)]
            stale = types.ModuleType("race_data")
            stale.__file__ = str(RACE_DATA_MODULE)
            stale.RACE_TYPE_ORDER = ["5k"]
            stale.ensure_race_pace_min = lambda df: df
            # Intentionally omit compare_race_type_options (Cloud ImportError case).
            sys.modules["race_data"] = stale

            with self.assertRaises(ImportError):
                from race_data import compare_race_type_options  # noqa: F401

            bootstrap = _load_bootstrap()
            bootstrap.bootstrap()

            race_data = sys.modules["race_data"]
            self.assertTrue(hasattr(race_data, "compare_race_type_options"))
            for name in _PERFORMANCE_RACE_DATA_IMPORTS:
                self.assertTrue(
                    hasattr(race_data, name),
                    msg=f"race_data missing required export {name!r}",
                )
            # Re-import must succeed after refresh.
            from race_data import compare_race_type_options as compare_fn

            self.assertTrue(callable(compare_fn))
        finally:
            for name in ("_bootstrap", "_sa_dashboard_bootstrap", "data", "race_data"):
                sys.modules.pop(name, None)
                if saved_mods[name] is not None:
                    sys.modules[name] = saved_mods[name]
            sys.path[:] = saved_path

    def test_performance_race_data_exports_exist_on_disk(self):
        """Every name Performance imports from race_data must exist on the module."""
        saved_path = list(sys.path)
        saved_mods = {
            name: sys.modules.pop(name, None)
            for name in ("_bootstrap", "_sa_dashboard_bootstrap", "data", "race_data")
        }
        try:
            sys.path[:] = [str(DASHBOARD_ROOT), str(REPO_ROOT / "src"), str(REPO_ROOT)]
            bootstrap = _load_bootstrap()
            bootstrap.bootstrap()
            race_data = importlib.import_module("race_data")
            missing = [
                name
                for name in _PERFORMANCE_RACE_DATA_IMPORTS
                if not hasattr(race_data, name)
            ]
            self.assertEqual(missing, [])
        finally:
            for name in ("_bootstrap", "_sa_dashboard_bootstrap", "data", "race_data"):
                sys.modules.pop(name, None)
                if saved_mods[name] is not None:
                    sys.modules[name] = saved_mods[name]
            sys.path[:] = saved_path


if __name__ == "__main__":
    unittest.main()
