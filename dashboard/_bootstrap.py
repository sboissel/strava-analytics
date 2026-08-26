"""Bootstrap import paths for the Streamlit dashboard."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

DASHBOARD_ROOT = Path(__file__).resolve().parent
REPO_ROOT = DASHBOARD_ROOT.parent
SRC_ROOT = REPO_ROOT / "src"

# Names Performance (and build-up UI) need. A stale ``race_data`` in
# ``sys.modules`` can point at the right file path but lack these attrs
# after a mixed Streamlit Cloud redeploy.
_REQUIRED_RACE_DATA_ATTRS = (
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


def _prepend_sys_path(path: Path) -> None:
    """Move ``path`` to the front of ``sys.path`` so dashboard modules win.

    Streamlit can leave the repository root ahead of ``dashboard/`` on
    ``sys.path``. A top-level ``data/`` CSV directory is then imported as the
    empty ``data`` namespace package instead of ``dashboard/data.py``.
    """
    path_str = str(path)
    if path_str in sys.path:
        sys.path.remove(path_str)
    sys.path.insert(0, path_str)


def ensure_sys_path() -> None:
    """Idempotently put ``dashboard/`` then ``src/`` at the front of ``sys.path``.

    Call this from page modules as well as the entrypoint. Streamlit may reset
    ``sys.path`` between ``streamlit_app.py`` and ``pages/*.py`` while leaving
    ``_bootstrap`` cached in ``sys.modules``, so import side effects alone are
    not enough.
    """
    # Dashboard first (``data``, ``race_data``, …), then ``src``.
    _prepend_sys_path(SRC_ROOT)
    _prepend_sys_path(DASHBOARD_ROOT)


def _reload_module_from_path(module_name: str, path: Path) -> None:
    """Replace ``sys.modules[module_name]`` with a fresh load from ``path``."""
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {module_name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)


def refresh_stale_modules() -> None:
    """Reload dashboard modules that are cached but missing expected attrs.

    Streamlit Cloud can keep an old ``race_data`` object in ``sys.modules``
    whose ``__file__`` still points at ``dashboard/race_data.py``, so
    ``from race_data import compare_race_type_options`` fails with ImportError
    even though the on-disk file defines the name.
    """
    ensure_sys_path()
    race_data = sys.modules.get("race_data")
    if race_data is None:
        return
    if all(hasattr(race_data, name) for name in _REQUIRED_RACE_DATA_ATTRS):
        return
    _reload_module_from_path("race_data", DASHBOARD_ROOT / "race_data.py")


def bootstrap() -> None:
    """Fix ``sys.path`` and replace stale dashboard modules when needed."""
    ensure_sys_path()
    refresh_stale_modules()


def load_bootstrap(dashboard_root: Path):
    """Load ``_bootstrap.py`` by absolute path, ignoring a stale ``_bootstrap``.

    Parameters
    ----------
    dashboard_root : pathlib.Path
        Directory that contains ``_bootstrap.py`` (the ``dashboard/`` folder).

    Returns
    -------
    module
        Freshly executed bootstrap module (also stored as ``_bootstrap``).
    """
    path = Path(dashboard_root).resolve() / "_bootstrap.py"
    spec = importlib.util.spec_from_file_location("_sa_dashboard_bootstrap", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load dashboard bootstrap from {path}")
    module = importlib.util.module_from_spec(spec)
    # Unique name avoids collisions; also replace bare ``_bootstrap``.
    sys.modules["_sa_dashboard_bootstrap"] = module
    sys.modules["_bootstrap"] = module
    spec.loader.exec_module(module)
    return module


bootstrap()
