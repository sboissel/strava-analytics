"""Strava API client and pipeline entrypoint for refreshing tokens and syncing activities."""

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import requests

from strava_analytics.activity_utils import (
    process_activities,
    save_activities_last_week,
    update_activity_analysis_csvs,
    update_run_pace_analysis_csv,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LAST_ACTIVITY_ID_FILENAME = "highest_activity_id.txt"


def last_activity_id_path(data_dir: Path) -> Path:
    """Return the path to the saved last-activity-id file."""
    return data_dir / LAST_ACTIVITY_ID_FILENAME


def read_last_activity_id(data_dir: Path) -> str:
    """Read the last known activity ID from disk."""
    path = last_activity_id_path(data_dir)
    if not path.exists():
        return "0"
    return path.read_text().strip()


def write_last_activity_id(data_dir: Path, activity_id: Union[int, str]) -> None:
    """Persist the last known activity ID to disk."""
    last_activity_id_path(data_dir).write_text(str(activity_id))


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

    def get_activities(self) -> List[Dict[str, Any]]:
        """Fetch athlete activities until the last known activity ID is reached.

        Returns
        -------
        list[dict]
            Activity dictionaries returned by the Strava athlete activities endpoint.
        """
        access_token = self._require_access_token()
        activities = []
        page = 1
        headers = {"Authorization": f"Bearer {access_token}"}

        while True:
            # Fetch one page of activities at a time until we hit the last known activity.
            url = "https://www.strava.com/api/v3/athlete/activities"
            params = {"per_page": 100, "page": page}

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

            # Stop early once the latest known activity appears in the current page.
            if self.last_activity_id in [str(act["id"]) for act in data]:
                break

            page += 1
            time.sleep(1)

        return activities

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


def main(data_dir: Optional[Path] = None) -> None:
    """Run the Strava analytics pipeline.

    Parameters
    ----------
    data_dir : pathlib.Path, optional
        Directory for activity CSVs and the last-activity-id file. Defaults to
        ``data`` under the repository root.
    """
    data_dir = data_dir or (REPO_ROOT / "data")

    client = StravaClient.from_env(data_dir=data_dir)
    client.refresh_access_token()
    print("Token refreshed")

    print("Getting activities...")
    activities = client.get_activities()

    print(f"Processing {len(activities)} activities...")
    df, pace_summaries = process_activities(
        activities, client.get_streams, client.last_activity_id
    )

    if df.empty:
        print("No new activities to process.")
    else:
        update_activity_analysis_csvs(df, data_dir)
        write_last_activity_id(data_dir, df["activity_id"].max())

        pace_output = data_dir / "strava_run_pace_analysis.csv"
        update_run_pace_analysis_csv(pace_summaries, pace_output)
        print(f"Saved run pace summary: {pace_output}")

    weekly_output = data_dir / "activities_last_week.csv"
    save_activities_last_week(data_dir, weekly_output)
    print(f"Saved weekly summary: {weekly_output}")


if __name__ == "__main__":
    main()
