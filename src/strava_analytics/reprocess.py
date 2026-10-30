"""Re-fetch and rewrite specific Strava activities from a YAML ID list."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, List, Optional, Sequence

import yaml

# Allow `python src/strava_analytics/reprocess.py` without installing the package.
# Prefer: PYTHONPATH=src python -m strava_analytics.reprocess
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from strava_analytics.activities import process_activities
from strava_analytics.client import REPO_ROOT, StravaClient
from strava_analytics.csv_io import (
    save_activities_last_week,
    update_activity_analysis_csvs,
    update_run_pace_analysis_csv,
)

DEFAULT_YAML_PATH = REPO_ROOT / "data" / "reprocess_activities.yaml"


def load_activity_ids(yaml_path: Path) -> List[int]:
    """Load activity IDs from a reprocess YAML file.

    Expected shape::

        activity_ids:
          - 1234567890
          - 9876543210

    Entries may be ints, digit strings, or mappings with an ``id`` key
    (optional ``reason`` is ignored by the loader).

    Parameters
    ----------
    yaml_path : pathlib.Path
        Path to the YAML file.

    Returns
    -------
    list[int]
        Ordered unique activity IDs.

    Raises
    ------
    FileNotFoundError
        If ``yaml_path`` does not exist.
    ValueError
        If the file is empty, missing ``activity_ids``, has no IDs, or has
        invalid entries.
    """
    if not yaml_path.is_file():
        raise FileNotFoundError(f"Reprocess YAML not found: {yaml_path}")

    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    if raw is None:
        raise ValueError(f"Reprocess YAML is empty: {yaml_path}")
    if not isinstance(raw, dict):
        raise ValueError(f"Reprocess YAML must be a mapping: {yaml_path}")

    entries = raw.get("activity_ids")
    if entries is None:
        raise ValueError(f"Reprocess YAML missing 'activity_ids': {yaml_path}")
    if not isinstance(entries, list):
        raise ValueError(f"'activity_ids' must be a list: {yaml_path}")
    if not entries:
        raise ValueError(
            f"No activity IDs in {yaml_path}. Add IDs under activity_ids before running."
        )

    ids: List[int] = []
    seen: set[int] = set()
    for idx, entry in enumerate(entries):
        activity_id = _parse_activity_id_entry(entry, idx)
        if activity_id in seen:
            continue
        seen.add(activity_id)
        ids.append(activity_id)
    return ids


def _parse_activity_id_entry(entry: Any, index: int) -> int:
    """Normalize one YAML list entry to an int activity ID."""
    if isinstance(entry, bool) or entry is None:
        raise ValueError(f"Invalid activity_ids[{index}]: {entry!r}")
    if isinstance(entry, int):
        if entry <= 0:
            raise ValueError(f"Invalid activity_ids[{index}]: {entry!r}")
        return entry
    if isinstance(entry, str):
        text = entry.strip()
        if not text.isdigit():
            raise ValueError(f"Invalid activity_ids[{index}]: {entry!r}")
        return int(text)
    if isinstance(entry, dict):
        if "id" not in entry:
            raise ValueError(f"Invalid activity_ids[{index}]: mapping needs 'id': {entry!r}")
        return _parse_activity_id_entry(entry["id"], index)
    raise ValueError(f"Invalid activity_ids[{index}]: {entry!r}")


def fetch_activities_by_id(
    client: StravaClient,
    activity_ids: Sequence[int],
    *,
    pause_seconds: float = 1.0,
) -> List[dict]:
    """Fetch each activity from Strava, fail-fast on the first hard error.

    Parameters
    ----------
    client : StravaClient
        Authenticated client (token refresh should already have run).
    activity_ids : sequence of int
        Strava activity IDs to fetch.
    pause_seconds : float, optional
        Sleep between detail fetches to ease rate limits. Defaults to 1.0.

    Returns
    -------
    list[dict]
        Activity payloads in the same order as ``activity_ids``.
    """
    activities: List[dict] = []
    for index, activity_id in enumerate(activity_ids):
        print(f"Fetching activity {activity_id} ({index + 1}/{len(activity_ids)})...")
        activities.append(client.get_activity(activity_id))
        if index < len(activity_ids) - 1 and pause_seconds > 0:
            time.sleep(pause_seconds)
    return activities


def main(
    yaml_path: Optional[Path] = None,
    data_dir: Optional[Path] = None,
) -> None:
    """Reprocess listed activities and rewrite analysis CSVs.

    Does not update ``highest_activity_id.txt`` (watermark stays with incremental
    sync). Refreshes the weekly summary the same way as the daily pipeline.

    Parameters
    ----------
    yaml_path : pathlib.Path, optional
        YAML listing activity IDs. Defaults to ``data/reprocess_activities.yaml``.
    data_dir : pathlib.Path, optional
        Directory for activity CSVs. Defaults to ``data/activities``.
    """
    yaml_path = yaml_path or DEFAULT_YAML_PATH
    data_dir = data_dir or (REPO_ROOT / "data" / "activities")

    activity_ids = load_activity_ids(yaml_path)
    print(f"Reprocessing {len(activity_ids)} activit{'y' if len(activity_ids) == 1 else 'ies'} from {yaml_path}")

    client = StravaClient.from_env(data_dir=data_dir)
    client.refresh_access_token()
    print("Token refreshed")

    activities = fetch_activities_by_id(client, activity_ids)
    # Bypass the incremental watermark: only the fetched IDs are processed.
    df, pace_summaries = process_activities(
        activities,
        client.get_streams,
        "0",
        client.get_activity_zones,
    )

    if df.empty:
        raise RuntimeError("Reprocess produced no activity rows; refusing to write CSVs.")

    update_activity_analysis_csvs(df, data_dir)

    if pace_summaries:
        pace_output = data_dir / "strava_run_pace_analysis.csv"
        update_run_pace_analysis_csv(pace_summaries, pace_output)
        print(f"Saved run pace summary: {pace_output}")

    weekly_output = data_dir / "activities_last_week.csv"
    save_activities_last_week(data_dir, weekly_output)
    print(f"Saved weekly summary: {weekly_output}")
    print("Reprocess complete.")


if __name__ == "__main__":
    main()
