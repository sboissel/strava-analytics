"""Summaries-only historical backfill for ``start_lat`` / ``start_lng``.

Pages Strava list/summary activities and patches empty GPS columns on local
analysis CSVs. Does not fetch streams, zones, or re-run ``process_activities``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import pandas as pd

# Allow `python src/strava_analytics/backfill_locations.py` without installing.
# Prefer: PYTHONPATH=src python -m strava_analytics.backfill_locations
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from strava_analytics.client import REPO_ROOT, StravaClient
from strava_analytics.csv_io import (
    activity_ids_missing_location,
    backfill_location_from_summaries,
    update_activity_analysis_csvs,
)


def main(data_dir: Optional[Path] = None) -> int:
    """Backfill empty start GPS columns from Strava activity summaries.

    Parameters
    ----------
    data_dir : pathlib.Path, optional
        Directory for analysis CSVs. Defaults to ``data`` under the repo root.

    Returns
    -------
    int
        Number of analysis rows whose coordinates were filled.
    """
    data_dir = data_dir or (REPO_ROOT / "data")

    # Ensure start_lat / start_lng columns exist before scanning/patching.
    update_activity_analysis_csvs(pd.DataFrame(), data_dir)

    missing = activity_ids_missing_location(data_dir)
    if not missing:
        print("No rows missing start_lat/start_lng.")
        return 0

    print(
        f"{len(missing)} analysis row(s) missing GPS; "
        "paging Strava activity summaries (no streams)..."
    )

    client = StravaClient.from_env(data_dir=data_dir)
    client.refresh_access_token()
    print("Token refreshed")

    summaries = client.get_activity_summaries(stop_when_ids_seen=missing)
    print(f"Fetched {len(summaries)} summaries")

    filled = backfill_location_from_summaries(summaries, data_dir)
    still_missing = activity_ids_missing_location(data_dir)

    print(f"Backfilled start_lat/start_lng on {filled} row(s).")
    if still_missing:
        print(
            f"{len(still_missing)} row(s) still missing GPS "
            "(no start_latlng on list summary — indoor/manual, privacy, or deleted)."
        )
    else:
        print("All analysis rows now have start_lat/start_lng where Strava provided GPS.")

    return filled


if __name__ == "__main__":
    main()
