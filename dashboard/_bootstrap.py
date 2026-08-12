"""Bootstrap import paths for the Streamlit dashboard."""

from __future__ import annotations

import sys
from pathlib import Path

DASHBOARD_ROOT = Path(__file__).resolve().parent
REPO_ROOT = DASHBOARD_ROOT.parent
SRC_ROOT = REPO_ROOT / "src"

for path in (DASHBOARD_ROOT, SRC_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
