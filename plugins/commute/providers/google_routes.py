"""Google Routes API v2 provider for live commute telemetry."""

from __future__ import annotations

import logging
from typing import Any, Dict, List
import requests

from ..constants import (
    GMP_SOLUTION_ID,
    GOOGLE_ROUTES_API_URL,
    ROUTES_FIELD_MASK,
)
from ..models import RouteRequest, RouteTelemetry
from .base import BaseCommuteProvider, ProviderError

logger = logging.getLogger(__name__)


def parse_duration_string(duration_str: str | None) -> int:
    """Parse Google Routes API duration string (e.g. '2040s' or '120.5s') into seconds."""
    if not duration_str:
        return 0
    try:
        clean = str(duration_str).strip()
        if clean.endswith("s"):
            clean = clean[:-1]
        return max(0, round(float(clean)))
    except (ValueError, TypeError):
        return 0


class GoogleRoutesProvider(BaseCommuteProvider):
    """Fetches real-time traffic route telemetry using the Google Routes API v2."""

    def __init__(
        self,
        api_key: str,
        traffic_model: str = "best_guess",
        timeout_seconds: int = 15,
        session: requests.Session | None = None,
    ) -> None:
        if not api_key:
            raise ProviderError("Google Cloud API Key is required for Google Routes provider.")
        self.api_key = api_key.strip()
        self.traffic_model = traffic_model
        self.timeout_seconds = timeout_seconds
        self._session = session or requests.Session()

    def _build_payload(self, request: RouteRequest) -> Dict[str, Any]:
        """Construct the REST request payload for computeRoutes."""
        payload: Dict[str, Any] = {
            "origin": {"address": request.origin.strip()},
            "destination": {"address": request.destination.strip()},
            "travelMode": "DRIVE",
            "routingPreference": "TRAFFIC_AWARE",
            "computeAlternativeRoutes": True,
            "routeModifiers": {
                "avoidTolls": bool(request.avoid_tolls),
                "avoidHighways": bool(request.avoid_highways),
                "avoidFerries": False,
            },
        }

        # If a waypoint / via location is specified, add it as a non-stop via point
        if request.via and request.via.strip():
            payload["intermediates"] = [
                {
                    "address": request.via.strip(),
                    "via": True,
                }
            ]

        return payload

    def get_route(self, request: RouteRequest) -> RouteTelemetry:
        """Fetch routing telemetry for a single route request."""
        if not (request.origin and request.origin.strip()):
            raise ProviderError(f"Route '{request.name}' has no origin address configured.")
        if not (request.destination and request.destination.strip()):
            raise ProviderError(f"Route '{request.name}' has no destination address configured.")

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": ROUTES_FIELD_MASK,
            "X-Goog-Maps-Solution-ID": GMP_SOLUTION_ID,
        }

        payload = self._build_payload(request)

        try:
            response = self._session.post(
                GOOGLE_ROUTES_API_URL,
                json=payload,
                headers=headers,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as e:
            raise ProviderError(f"Network error querying Google Routes API: {e}") from e

        if not response.ok:
            error_msg = f"HTTP {response.status_code}"
            try:
                data = response.json()
                if "error" in data:
                    err = data["error"]
                    error_msg = err.get("message") or str(err)
            except Exception:
                error_msg = response.text or error_msg
            raise ProviderError(f"Google Routes API error: {error_msg}")

        try:
            data = response.json()
        except Exception as e:
            raise ProviderError(f"Invalid JSON returned from Google Routes API: {e}") from e

        routes: List[Dict[str, Any]] = data.get("routes", [])
        if not routes:
            raise ProviderError(
                f"No route found for '{request.name}' between '{request.origin}' and '{request.destination}'."
            )

        # Select requested alternative route index (clamped to available routes)
        target_idx = max(0, min(request.alternative_index, len(routes) - 1))
        chosen_route = routes[target_idx]

        duration_sec = parse_duration_string(chosen_route.get("duration"))
        static_duration_sec = parse_duration_string(chosen_route.get("staticDuration"))
        if static_duration_sec == 0:
            static_duration_sec = duration_sec

        distance_meters = int(chosen_route.get("distanceMeters") or 0)
        description = str(chosen_route.get("description") or "").strip()
        summary = f"via {description}" if description and not description.lower().startswith("via ") else description

        raw_warnings = chosen_route.get("warnings") or []
        warnings = [str(w) for w in raw_warnings if w]

        return RouteTelemetry(
            name=request.name,
            duration_seconds=duration_sec,
            static_duration_seconds=static_duration_sec,
            distance_meters=distance_meters,
            summary=summary,
            warnings=warnings,
        )
