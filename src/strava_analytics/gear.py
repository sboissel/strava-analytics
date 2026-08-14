"""Shoe mileage from activity ``gear_id`` values plus tracked baselines."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

import pandas as pd

GEAR_COLUMNS = ["gear_id", "name", "type", "mileage", "status"]

# Baseline miles worn before tracking these shoes on Strava.
TRACKED_GEAR: List[Dict[str, Any]] = [
    {
        "gear_id": "g33031373",
        "name": "Hoka Mach 7",
        "type": "Speed",
        "baseline_miles": 12.0,
    },
    {
        "gear_id": "g33031356",
        "name": "Nike Pegasus 42",
        "type": "Road",
        "baseline_miles": 63.0,
    },
    {
        "gear_id": "g33031350",
        "name": "Nike Pegasus Trail 5",
        "type": "Trail",
        "baseline_miles": 189.0,
    },
    {
        "gear_id": "g33031360",
        "name": "Nike ZoomX",
        "type": "Race",
        "baseline_miles": 50.0,
    },
]


def gear_mileage_from_activities(
    activities: pd.DataFrame,
    tracked_gear: Optional[Sequence[Mapping[str, Any]]] = None,
) -> pd.DataFrame:
    """Compute shoe mileage as baseline plus summed activity distances.

    For each entry in ``tracked_gear`` (defaults to ``TRACKED_GEAR``), mileage is
    ``baseline_miles`` (or ``0`` when missing) plus the sum of
    ``distance_miles`` for activities whose ``gear_id`` matches. Shoes with no
    matching activities still appear with their baseline. Status is always
    ``active`` (retired state is no longer read from the Strava gear API).

    Parameters
    ----------
    activities :
        Activity rows with at least ``gear_id`` and ``distance_miles``.
    tracked_gear :
        Optional override of the tracked shoe list.

    Returns
    -------
    pandas.DataFrame
        Columns ``gear_id``, ``name``, ``type``, ``mileage``, and ``status``.
    """
    tracked = list(tracked_gear or TRACKED_GEAR)
    miles_by_gear: Dict[str, float] = {}

    if (
        not activities.empty
        and "gear_id" in activities.columns
        and "distance_miles" in activities.columns
    ):
        tmp = activities[["gear_id", "distance_miles"]].copy()
        tmp["gear_id"] = tmp["gear_id"].astype(str).str.strip()
        tmp["distance_miles"] = pd.to_numeric(tmp["distance_miles"], errors="coerce").fillna(
            0.0
        )
        tmp = tmp.loc[tmp["gear_id"] != ""]
        if not tmp.empty:
            miles_by_gear = (
                tmp.groupby("gear_id", sort=False)["distance_miles"].sum().astype(float).to_dict()
            )

    rows: List[Dict[str, Any]] = []
    for item in tracked:
        gear_id = str(item["gear_id"])
        baseline = float(item.get("baseline_miles") or 0.0)
        activity_miles = float(miles_by_gear.get(gear_id, 0.0))
        rows.append(
            {
                "gear_id": gear_id,
                "name": item["name"],
                "type": str(item.get("type") or "").strip(),
                "mileage": round(baseline + activity_miles, 2),
                "status": "active",
            }
        )

    return pd.DataFrame(rows, columns=GEAR_COLUMNS)
