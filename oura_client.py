"""Client for fetching data from all Oura Ring API v2 endpoints."""

from datetime import date, timedelta

import requests

BASE_URL = "https://api.ouraring.com/v2/usercollection"

ENDPOINTS = {
    "daily_activity": "/daily_activity",
    "daily_readiness": "/daily_readiness",
    "daily_sleep": "/daily_sleep",
    "daily_spo2": "/daily_spo2",
    "daily_stress": "/daily_stress",
    "daily_resilience": "/daily_resilience",
    "heartrate": "/heartrate",
    "sleep": "/sleep",
    "session": "/session",
    "tag": "/tag",
    "workout": "/workout",
    "personal_info": "/personal_info",
}


class OuraClient:
    def __init__(self, access_token: str):
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {access_token}"

    def _get(self, endpoint: str, params: dict | None = None) -> list[dict]:
        """Fetch data from an endpoint, handling pagination."""
        url = BASE_URL + endpoint
        all_data = []

        while url:
            resp = self.session.get(url, params=params)
            resp.raise_for_status()
            body = resp.json()

            # personal_info is a single object, not paginated
            if "data" not in body:
                return [body]

            all_data.extend(body["data"])
            url = body.get("next_token")
            if url:
                params = {"next_token": url}
                url = BASE_URL + endpoint

        return all_data

    def fetch_all(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, list[dict]]:
        """Fetch data from all endpoints for the given date range."""
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }

        results = {}
        for name, endpoint in ENDPOINTS.items():
            try:
                if name == "personal_info":
                    results[name] = self._get(endpoint)
                elif name == "heartrate":
                    # heartrate uses start_datetime / end_datetime
                    hr_params = {
                        "start_datetime": f"{start_date.isoformat()}T00:00:00",
                        "end_datetime": f"{end_date.isoformat()}T23:59:59",
                    }
                    results[name] = self._get(endpoint, hr_params)
                else:
                    results[name] = self._get(endpoint, params)
            except requests.HTTPError as e:
                # Some endpoints may not be available for all users
                print(f"Warning: could not fetch {name}: {e}")
                results[name] = []

        return results
