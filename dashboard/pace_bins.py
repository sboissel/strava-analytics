"""Pace bin labels for the Training Insights page."""

from __future__ import annotations

# Display label → internal bin key (matches activity_utils.PACE_BIN_LABELS).
PACE_BIN_OPTIONS: list[tuple[str, str]] = [
    ("Under 7:00", "under_700"),
    ("7:00-7:30", "700_730"),
    ("7:30-8:00", "730_800"),
    ("8:00-8:30", "800_830"),
    ("8:30-9:00", "830_900"),
    ("9:00-9:30", "900_930"),
    ("9:30-10:00", "930_1000"),
    ("10:00-10:30", "1000_1030"),
    ("10:30-11:00", "1030_1100"),
    ("11:00-11:30", "1100_1130"),
    ("Over 11:30", "over_1130"),
]

PACE_BIN_LABEL_BY_KEY = {key: label for label, key in PACE_BIN_OPTIONS}
DEFAULT_PACE_BIN_KEY = "800_830"
