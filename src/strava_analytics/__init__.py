"""Strava analytics pipeline and dashboard support code."""

from __future__ import annotations

import re
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def _version_from_pyproject() -> str | None:
    """Read version from repo ``pyproject.toml`` when developing from source.

    Editable installs can leave a stale ``*.egg-info`` (gitignored); prefer the
    checked-in pyproject when present. Refresh metadata with ``pip install -e .``.
    """
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    if not pyproject.is_file():
        return None
    match = re.search(
        r'(?m)^version\s*=\s*"([^"]+)"',
        pyproject.read_text(encoding="utf-8"),
    )
    return match.group(1) if match else None


__version__ = _version_from_pyproject()
if __version__ is None:
    try:
        __version__ = version("strava-analytics")
    except PackageNotFoundError:
        __version__ = "1.8.1"
