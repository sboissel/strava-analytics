"""Bootstrap import paths for the Streamlit dashboard."""

from __future__ import annotations

import sys
from pathlib import Path

DASHBOARD_ROOT = Path(__file__).resolve().parent
REPO_ROOT = DASHBOARD_ROOT.parent
SRC_ROOT = REPO_ROOT / "src"


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


ensure_sys_path()
