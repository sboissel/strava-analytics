"""Strava analytics pipeline and dashboard support code."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("strava-analytics")
except PackageNotFoundError:
    __version__ = "1.5.1"
