"""Pace bin labels for the Training Insights page."""

from __future__ import annotations

from strava_analytics.activity_utils import PACE_BIN_LABELS

PACE_BIN_DISPLAY_LABELS: dict[str, str] = {
    "under_700": "Under 7:00",
    "700_730": "7:00-7:30",
    "730_800": "7:30-8:00",
    "800_830": "8:00-8:30",
    "830_900": "8:30-9:00",
    "900_930": "9:00-9:30",
    "930_1000": "9:30-10:00",
    "1000_1030": "10:00-10:30",
    "1030_1100": "10:30-11:00",
    "1100_1130": "11:00-11:30",
    "over_1130": "Over 11:30",
}

PACE_BIN_OPTIONS: list[tuple[str, str]] = [
    (PACE_BIN_DISPLAY_LABELS[key], key) for key in PACE_BIN_LABELS
]
DEFAULT_PACE_BIN_KEY = "800_830"
