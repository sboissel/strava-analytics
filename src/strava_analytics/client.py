"""Thin Strava OAuth and API client."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Collection, Dict, List, Optional, Sequence, Set, Union

import requests

from strava_analytics.csv_io import read_last_activity_id

REPO_ROOT = Path(__file__).resolve().parents[2]


class StravaClient:
    """Thin client for Strava OAuth and activity API calls."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        last_activity_id: str,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.last_activity_id = str(last_activity_id)
        self.access_token: Optional[str] = None

    @classmethod
    def from_env(cls, data_dir: Optional[Path] = None) -> "StravaClient":
        """Build a client from environment variables and the saved last activity ID.

        Parameters
        ----------
        data_dir : pathlib.Path, optional
            Directory containing ``highest_activity_id.txt``. Defaults to
            ``data`` under the repository root.

        Returns
        -------
        StravaClient
            A configured client instance whose ``last_activity_id`` is the value
            stored in that file.
        """
        data_dir = data_dir or (REPO_ROOT / "data")
        return cls(
            client_id=os.environ["CLIENT_ID"],
            client_secret=os.environ["CLIENT_SECRET"],
            refresh_token=os.environ["REFRESH_TOKEN"],
            last_activity_id=read_last_activity_id(data_dir),
        )

    def refresh_access_token(self) -> Dict[str, Any]:
        """Refresh the Strava access token and store it on the client.

        Returns
        -------
        dict
            The token payload returned by the Strava OAuth endpoint.

        Raises
        ------
        RuntimeError
            If Strava rejects the refresh request.
        """
        url = "https://www.strava.com/oauth/token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        }

        res = requests.post(url, data=payload, timeout=30)
        if res.status_code != 200:
            raise RuntimeError(f"Strava token refresh failed: {res.status_code} {res.text[:200]}")

        token_data = res.json()
        self.access_token = token_data["access_token"]
        if "refresh_token" in token_data:
            self.refresh_token = token_data["refresh_token"]
        return token_data

    def _require_access_token(self) -> str:
        if not self.access_token:
            self.refresh_access_token()
        if not self.access_token:
            raise RuntimeError("Failed to obtain an access token.")
        return self.access_token

    def get_activity_summaries(
        self,
        *,
        stop_at_activity_id: Optional[str] = None,
        stop_when_ids_seen: Optional[Collection[str]] = None,
        per_page: int = 100,
    ) -> List[Dict[str, Any]]:
        """Page athlete activity summaries from newest to oldest.

        Parameters
        ----------
        stop_at_activity_id : str, optional
            Stop after the page that contains this activity ID (incremental sync).
        stop_when_ids_seen : collection of str, optional
            Stop once every listed activity ID has appeared in a fetched page
            (location backfill). IDs never returned by Strava still cause a full
            history walk until an empty page.
        per_page : int, optional
            Page size for the list endpoint (max 200). Defaults to 100.

        Returns
        -------
        list[dict]
            Activity summary dictionaries from ``GET /athlete/activities``.

        Raises
        ------
        RuntimeError
            If the API request fails.
        """
        access_token = self._require_access_token()
        activities: List[Dict[str, Any]] = []
        page = 1
        headers = {"Authorization": f"Bearer {access_token}"}
        remaining: Optional[Set[str]] = (
            {str(activity_id) for activity_id in stop_when_ids_seen}
            if stop_when_ids_seen is not None
            else None
        )
        stop_id = str(stop_at_activity_id) if stop_at_activity_id is not None else None

        while True:
            url = "https://www.strava.com/api/v3/athlete/activities"
            params = {"per_page": per_page, "page": page}

            res = requests.get(url, headers=headers, params=params, timeout=30)
            if res.status_code != 200:
                raise RuntimeError(
                    f"Strava activities request failed: {res.status_code} {res.text[:200]}"
                )

            data = res.json()
            if not data:
                break

            activities.extend(data)
            print(f"Pulled page {page} ({len(activities)} activities)")

            page_ids = {str(act["id"]) for act in data}
            if remaining is not None:
                remaining -= page_ids
                if not remaining:
                    break

            if stop_id is not None and stop_id in page_ids:
                break

            page += 1
            time.sleep(1)

        return activities

    def get_activities(self) -> List[Dict[str, Any]]:
        """Fetch athlete activities until the last known activity ID is reached.

        Returns
        -------
        list[dict]
            Activity dictionaries returned by the Strava athlete activities endpoint.
        """
        return self.get_activity_summaries(stop_at_activity_id=self.last_activity_id)

    def get_streams(self, activity_id: Union[int, str], streams: Sequence[str]) -> Dict[str, Any]:
        """Retrieve one or more Strava activity streams for a given activity.

        Parameters
        ----------
        activity_id : int or str
            The Strava activity identifier.
        streams : sequence of str
            One or more stream names such as "distance" or "heartrate".

        Returns
        -------
        dict
            A dictionary payload from the Strava streams endpoint.

        Raises
        ------
        RuntimeError
            If the API request fails.
        """
        access_token = self._require_access_token()
        url = f"https://www.strava.com/api/v3/activities/{activity_id}/streams"
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {
            "keys": ",".join(streams),
            "key_by_type": "true",
        }

        res = requests.get(url, headers=headers, params=params, timeout=30)
        if res.status_code != 200:
            raise RuntimeError(f"Strava streams request failed: {res.status_code} {res.text[:200]}")

        return res.json()

    def get_activity_zones(self, activity_id: Union[int, str]) -> List[Dict[str, Any]]:
        """Retrieve Strava activity zone distributions for a given activity.

        Parameters
        ----------
        activity_id : int or str
            The Strava activity identifier.

        Returns
        -------
        list[dict]
            Zone objects from the Strava activity zones endpoint (heartrate,
            pace, and/or power). May be empty when no zone data is available.

        Raises
        ------
        RuntimeError
            If the API request fails.
        """
        access_token = self._require_access_token()
        url = f"https://www.strava.com/api/v3/activities/{activity_id}/zones"
        headers = {"Authorization": f"Bearer {access_token}"}

        res = requests.get(url, headers=headers, timeout=30)
        if res.status_code != 200:
            raise RuntimeError(
                f"Strava activity zones request failed: {res.status_code} {res.text[:200]}"
            )

        payload = res.json()
        if not isinstance(payload, list):
            raise RuntimeError("Strava activity zones response was not a list.")
        return payload
