"""Tests for package version resolution."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock


class PackageVersionTests(unittest.TestCase):
    """Checkout pyproject beats stale importlib metadata."""

    def test_find_checkout_pyproject_from_src_layout(self):
        from strava_analytics import _find_checkout_pyproject

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "strava-analytics"
            pkg = root / "src" / "strava_analytics"
            pkg.mkdir(parents=True)
            (root / "pyproject.toml").write_text(
                '[project]\nname = "strava-analytics"\nversion = "9.8.7"\n',
                encoding="utf-8",
            )
            init_path = pkg / "__init__.py"
            init_path.write_text("# fake\n", encoding="utf-8")
            found = _find_checkout_pyproject(init_path)
            self.assertIsNotNone(found)
            assert found is not None
            self.assertEqual(found.resolve(), (root / "pyproject.toml").resolve())

    def test_resolve_version_prefers_pyproject_over_metadata(self):
        from strava_analytics import _resolve_version

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "strava-analytics"
            pkg = root / "src" / "strava_analytics"
            pkg.mkdir(parents=True)
            (root / "pyproject.toml").write_text(
                '[project]\nname = "strava-analytics"\nversion = "9.8.7"\n',
                encoding="utf-8",
            )
            init_path = pkg / "__init__.py"
            init_path.write_text("# fake\n", encoding="utf-8")
            with mock.patch(
                "strava_analytics.version", return_value="1.6.0"
            ) as meta:
                resolved = _resolve_version(init_path)
            self.assertEqual(resolved, "9.8.7")
            meta.assert_not_called()

    def test_resolve_version_falls_back_to_metadata(self):
        from importlib.metadata import PackageNotFoundError

        from strava_analytics import _FALLBACK_VERSION, _resolve_version

        with tempfile.TemporaryDirectory() as tmp:
            orphan = Path(tmp) / "orphan" / "pkg"
            orphan.mkdir(parents=True)
            init_path = orphan / "__init__.py"
            init_path.write_text("# fake\n", encoding="utf-8")
            with mock.patch(
                "strava_analytics.version", return_value="1.6.0"
            ):
                self.assertEqual(_resolve_version(init_path), "1.6.0")
            with mock.patch(
                "strava_analytics.version",
                side_effect=PackageNotFoundError("strava-analytics"),
            ):
                self.assertEqual(_resolve_version(init_path), _FALLBACK_VERSION)


if __name__ == "__main__":
    unittest.main()
