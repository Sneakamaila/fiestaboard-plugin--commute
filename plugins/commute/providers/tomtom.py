"""TomTom Routing API provider for 100% free live commute telemetry (2,500 daily requests, no credit card required)."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List
import urllib.parse
import requests

from ..constants import (
    TOMTOM_GEOCODE_API_BASE,
    TOMTOM_ROUTING_API_BASE,
)
from ..models import RouteRequest, RouteTelemetry
from .base import BaseCommuteProvider, ProviderError

logger = logging.getLogger(__name__)

# Matches coordinate strings like "52.5200, 13.4050" or "52.5200,13.4050"
COORD_REGEX = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")


class TomTomProvider(BaseCommuteProvider):
    """Fetches real-time traffic and route telemetry using the TomTom Routing API.

    TomTom provides 2,500 free requests per day without requiring a credit card.
    """

    def __init__(
        self,
        api_key: str,
        timeout_seconds: int = 15,
        session: requests.Session | None = None,
    ) -> None:
        if not api_key or not api_key.strip():
            raise ProviderError("TomTom API Key is required for TomTom provider.")
        self.api_key = api_key.strip()
        self.timeout_seconds = timeout_seconds
        self._session = session or requests.Session()
        # In-memory cache so addresses are only geocoded once across plugin poll cycles
        self._geocode_cache: Dict[str, str] = {}

    def geocode(self, location: str) -> str:
        """Resolve an address or coordinate string into 'latitude,longitude' format."""
        clean = (location or "").strip()
        if not clean:
            raise ProviderError("Empty location provided for geocoding.")

        # Check if already in 'lat,lon' format
        coord_match = COORD_REGEX.match(clean)
        if coord_match:
            lat, lon = coord_match.group(1), coord_match.group(2)
            return f"{lat},{lon}"

        # Check in-memory cache
        if clean in self._geocode_cache:
            return self._geocode_cache[clean]

        # Call TomTom Search/Geocode API
        encoded_query = urllib.parse.quote(clean)
        url = f"{TOMTOM_GEOCODE_API_BASE}/{encoded_query}.json"
        params = {
            "key": self.api_key,
            "limit": 1,
        }

        try:
            resp = self._session.get(url, params=params, timeout=self.timeout_seconds)
        except requests.RequestException as e:
            raise ProviderError(f"Network error geocoding location '{clean}' with TomTom: {e}") from e

        if not resp.ok:
            raise ProviderError(f"TomTom Geocoding failed for '{clean}' (HTTP {resp.status_code}): {resp.text}")

        try:
            data = resp.json()
        except Exception as e:
            raise ProviderError(f"Invalid JSON returned from TomTom Geocoding: {e}") from e

        results = data.get("results", [])
        if not results:
            raise ProviderError(f"Could not find coordinates for address '{clean}' with TomTom.")

        pos = results[0].get("position", {})
        lat = pos.get("lat")
        lon = pos.get("lon")
        if lat is None or lon is None:
            raise ProviderError(f"Invalid position returned for address '{clean}' from TomTom.")

        coord_str = f"{lat},{lon}"
        self._geocode_cache[clean] = coord_str
        return coord_str

    def get_route(self, request: RouteRequest) -> RouteTelemetry:
        """Fetch routing telemetry for a single route request using TomTom calculateRoute."""
        if not (request.origin and request.origin.strip()):
            raise ProviderError(f"Route '{request.name}' has no origin address configured.")
        if not (request.destination and request.destination.strip()):
            raise ProviderError(f"Route '{request.name}' has no destination address configured.")

        orig_coords = self.geocode(request.origin)
        dest_coords = self.geocode(request.destination)

        # Assemble location path, including non-stop via point if specified
        if request.via and request.via.strip():
            via_coords = self.geocode(request.via)
            locations_path = f"{orig_coords}:{via_coords}:{dest_coords}"
        else:
            locations_path = f"{orig_coords}:{dest_coords}"

        url = f"{TOMTOM_ROUTING_API_BASE}/{locations_path}/json"

        params: Dict[str, Any] = {
            "key": self.api_key,
            "traffic": "true",
            "travelMode": "car",
            "computeBestAlternativeBy": "anyRoute",
            "maxAlternatives": 2,
        }

        avoid_list: List[str] = []
        if request.avoid_highways:
            avoid_list.append("motorways")
        if request.avoid_tolls:
            avoid_list.append("tollRoads")
        if avoid_list:
            params["avoid"] = ",".join(avoid_list)

        try:
            resp = self._session.get(url, params=params, timeout=self.timeout_seconds)
        except requests.RequestException as e:
            raise ProviderError(f"Network error querying TomTom Routing API: {e}") from e

        if not resp.ok:
            error_msg = f"HTTP {resp.status_code}"
            try:
                err_data = resp.json()
                if "error" in err_data:
                    error_msg = err_data["error"].get("description") or str(err_data["error"])
                elif "detailedError" in err_data:
                    error_msg = err_data["detailedError"].get("message") or str(err_data["detailedError"])
            except Exception:
                error_msg = resp.text or error_msg
            raise ProviderError(f"TomTom Routing API error: {error_msg}")

        try:
            data = resp.json()
        except Exception as e:
            raise ProviderError(f"Invalid JSON returned from TomTom Routing: {e}") from e

        routes = data.get("routes", [])
        if not routes:
            raise ProviderError(
                f"No route found for '{request.name}' between '{request.origin}' and '{request.destination}'."
            )

        # Select alternative index
        target_idx = max(0, min(request.alternative_index, len(routes) - 1))
        chosen_route = routes[target_idx]
        summary = chosen_route.get("summary", {})

        duration_sec = int(summary.get("travelTimeInSeconds", 0))
        traffic_delay_sec = int(summary.get("trafficDelayInSeconds", 0))

        # Base duration without traffic delay
        if "noTrafficTravelTimeInSeconds" in summary:
            static_duration_sec = int(summary["noTrafficTravelTimeInSeconds"])
        else:
            static_duration_sec = max(0, duration_sec - traffic_delay_sec)

        distance_meters = int(summary.get("lengthInMeters", 0))

        # Check legs or summary description for road names
        route_summary = ""
        legs = chosen_route.get("legs", [])
        for leg in legs:
            points = leg.get("points", [])
            if points:
                pass
        if not route_summary:
            if target_idx > 0:
                route_summary = f"Alt Route {target_idx}"
            else:
                route_summary = "Main Route"

        return RouteTelemetry(
            name=request.name,
            duration_seconds=duration_sec,
            static_duration_seconds=static_duration_sec,
            distance_meters=distance_meters,
            summary=route_summary,
        )
