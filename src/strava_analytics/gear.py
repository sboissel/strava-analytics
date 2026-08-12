"""Shoe/gear mileage tracking from the Strava gear API."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

import pandas as pd

from strava_analytics.activities import MILE_METERS

GEAR_CSV_FILENAME = "strava_gear.csv"
GEAR_CSV_COLUMNS = ["gear_id", "name", "mileage", "status"]

# Baseline miles worn before tracking these shoes on Strava.
TRACKED_GEAR: List[Dict[str, Any]] = [
    {"gear_id": "g33031373", "name": "Hoka Mach 7", "baseline_miles": 12.0},
    {"gear_id": "g33031356", "name": "Nike Pegasus 42", "baseline_miles": 63.0},
    {"gear_id": "g33031350", "name": "Nike Pegasus Trail 5", "baseline_miles": 189.0},
    {"gear_id": "g33031360", "name": "Nike ZoomX", "baseline_miles": 50.0},
]


def _load_existing_gear(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}

    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    if df.empty or "gear_id" not in df.columns:
        return {}

    rows: Dict[str, Dict[str, Any]] = {}
    for _, row in df.iterrows():
        gear_id = str(row.get("gear_id", "")).strip()
        if not gear_id:
            continue
        rows[gear_id] = {
            "gear_id": gear_id,
            "name": str(row.get("name", "")).strip(),
            "mileage": float(row.get("mileage") or 0),
            "status": str(row.get("status", "active")).strip().lower(),
        }
    return rows


def _tracked_row(
    tracked: Mapping[str, Any],
    gear_payload: Mapping[str, Any],
) -> Dict[str, Any]:
    strava_miles = float(gear_payload.get("distance") or 0) / MILE_METERS
    baseline = float(tracked["baseline_miles"])
    return {
        "gear_id": tracked["gear_id"],
        "name": tracked["name"],
        "mileage": round(strava_miles + baseline, 2),
        "status": "retired" if gear_payload.get("retired") else "active",
    }


def update_gear_mileage_csv(
    get_gear: Callable[[str], Mapping[str, Any]],
    data_dir: Path,
    tracked_gear: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Path:
    """Fetch active gear distances from Strava and write ``strava_gear.csv``.

    Mileage is Strava ``distance`` (meters → miles) plus each shoe's baseline
    miles from before Strava tracking. Rows already marked ``retired`` in the
    CSV are kept as-is and not refreshed.

    Parameters
    ----------
    get_gear :
        Callable that returns a Strava gear payload for a gear ID.
    data_dir :
        Directory containing ``strava_gear.csv``.
    tracked_gear :
        Optional override of the tracked shoe list. Defaults to ``TRACKED_GEAR``.

    Returns
    -------
    pathlib.Path
        Path to the written CSV.
    """
    tracked = list(tracked_gear or TRACKED_GEAR)
    path = data_dir / GEAR_CSV_FILENAME
    existing = _load_existing_gear(path)

    updated: Dict[str, Dict[str, Any]] = {}
    for item in tracked:
        gear_id = str(item["gear_id"])
        prior = existing.get(gear_id)
        if prior is not None and prior["status"] == "retired":
            updated[gear_id] = prior
            continue

        payload = get_gear(gear_id)
        updated[gear_id] = _tracked_row(item, payload)

    # Preserve any retired (or other) rows no longer in the tracked list.
    for gear_id, row in existing.items():
        if gear_id not in updated:
            updated[gear_id] = row

    ordered_ids = [str(item["gear_id"]) for item in tracked]
    extra_ids = sorted(gear_id for gear_id in updated if gear_id not in ordered_ids)
    rows = [updated[gear_id] for gear_id in ordered_ids + extra_ids]

    out = pd.DataFrame(rows, columns=GEAR_CSV_COLUMNS)
    data_dir.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)
    return path
