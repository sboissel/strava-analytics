"""Strava analytics pipeline and dashboard support code."""

from __future__ import annotations

import re
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

_FALLBACK_VERSION = "1.10.0"
_PROJECT_NAME_RE = re.compile(r'(?m)^name\s*=\s*"strava-analytics"')
_PROJECT_VERSION_RE = re.compile(r'(?m)^version\s*=\s*"([^"]+)"')


def _find_checkout_pyproject(anchor: Path) -> Path | None:
    """Walk parents of ``anchor`` for this repo's ``pyproject.toml``.

    Parameters
    ----------
    anchor : pathlib.Path
        File or directory inside the checkout (e.g. this package's ``__init__``).

    Returns
    -------
    pathlib.Path or None
        Path to ``pyproject.toml`` when found and named ``strava-analytics``.
    """
    start = anchor.resolve()
    roots = [start] if start.is_dir() else [start.parent]
    roots.extend(start.parents)
    for parent in roots:
        candidate = parent / "pyproject.toml"
        if not candidate.is_file():
            continue
        try:
            text = candidate.read_text(encoding="utf-8")
        except OSError:
            continue
        if _PROJECT_NAME_RE.search(text):
            return candidate
    return None


def _version_from_pyproject(anchor: Path | None = None) -> str | None:
    """Read version from checkout ``pyproject.toml`` when present.

    Prefer the checked-in file over ``importlib`` metadata: editable installs and
    Streamlit Cloud can leave stale ``*.egg-info`` / wheel metadata (e.g. 1.6.0)
    while the deployed tree already has a newer ``pyproject.toml``.
    """
    pyproject = _find_checkout_pyproject(anchor or Path(__file__))
    if pyproject is None:
        return None
    match = _PROJECT_VERSION_RE.search(pyproject.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def _resolve_version(anchor: Path | None = None) -> str:
    """Resolve version: checkout pyproject → package metadata → fallback."""
    from_pyproject = _version_from_pyproject(anchor)
    if from_pyproject:
        return from_pyproject
    try:
        return version("strava-analytics")
    except PackageNotFoundError:
        return _FALLBACK_VERSION


__version__ = _resolve_version()
