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
    "races_have_start_coords",
    "reverse_geocode_error_message",
)

# ``data`` must expose activities-path helpers after the data/ → data/activities
# move; stale Cloud modules may still default loaders to ``data/``.
_REQUIRED_DATA_ATTRS = (
    "ACTIVITIES_DIR",
    "load_gear",
    "load_hikes",
    "load_runs",
    "resolve_activities_dir",
)

# Names pages / entrypoint import from ``ui``. A stale ``ui`` in ``sys.modules``
# can point at the right file but lack newer helpers (e.g. training-plan
# zoom/render, or ``hero_html`` after a mixed Cloud redeploy).
_REQUIRED_UI_ATTRS = (
    "achievements_html",
    "aerobic_efficiency_info_html",
    "clear_hiking_map_filter",
    "compliance_info_html",
    "fastest_race_cards_html",
    "fitness_freshness_info_html",
    "hero_html",
    "hike_gap_info_html",
    "hiking_badges_html",
    "hr_zones_week_to_date_pie_html",
    "key_indicators_html",
    "metrics_inspect_anchor_html",
    "pace_hr_title_html",
    "race_buildup_delta_table_html",
    "race_buildup_eh_values_html",
    "race_buildup_hr_pies_html",
    "race_buildup_row_heading_html",
    "race_buildup_section_heading_html",
    "race_buildup_summary_html",
    "race_weeks_legend_html",
    "render_hiking_section_nav",
    "render_insights_section_nav",
    "render_kpi_detail_panel",
    "render_metrics_section_nav",
    "render_period_range_inputs",
    "render_race_section_nav",
    "render_sidebar_section_nav",
    "render_training_plan_zoom_select",
    "render_training_plans",
    "shoe_kpi_cards_html",
    "sidebar_version_html",
)


def _loader_default_is_activities(module: object, fn_name: str) -> bool:
    """Return True when ``fn``'s first default path ends with ``activities``."""
    fn = getattr(module, fn_name, None)
    if fn is None or not callable(fn):
        return False
    defaults = getattr(fn, "__defaults__", None) or ()
    if not defaults:
        return False
    try:
        return Path(defaults[0]).name == "activities"
    except TypeError:
        return False


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

    Streamlit Cloud can keep an old ``race_data`` / ``ui`` object in
    ``sys.modules`` whose ``__file__`` still points at the dashboard file, so
    ``from race_data import compare_race_type_options`` or
    ``from ui import render_training_plans`` fails with ImportError even
    though the on-disk file defines the name.

    Also reloads ``data`` / ``race_data`` when loader defaults still point at
    legacy ``data/`` instead of ``data/activities``, and reloads ``ui`` when
    its ``data`` / ``race_data`` dependencies were refreshed.
    """
    ensure_sys_path()
    data_reloaded = False
    data = sys.modules.get("data")
    if data is not None:
        data_stale = not all(
            hasattr(data, name) for name in _REQUIRED_DATA_ATTRS
        ) or not _loader_default_is_activities(data, "load_runs")
        if data_stale:
            _reload_module_from_path("data", DASHBOARD_ROOT / "data.py")
            data_reloaded = True

    race_data_reloaded = False
    race_data = sys.modules.get("race_data")
    if race_data is not None:
        race_stale = (
            data_reloaded
            or not all(
                hasattr(race_data, name) for name in _REQUIRED_RACE_DATA_ATTRS
            )
            or not _loader_default_is_activities(race_data, "load_race_results")
        )
        if race_stale:
            _reload_module_from_path("race_data", DASHBOARD_ROOT / "race_data.py")
            race_data_reloaded = True

    ui = sys.modules.get("ui")
    if ui is not None:
        ui_stale = (
            data_reloaded
            or race_data_reloaded
            or not all(hasattr(ui, name) for name in _REQUIRED_UI_ATTRS)
        )
        if ui_stale:
            _reload_module_from_path("ui", DASHBOARD_ROOT / "ui.py")


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
