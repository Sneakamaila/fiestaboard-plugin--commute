"""HERE Technologies Routing API v8 & Geocoding v7 provider for live commute telemetry.

HERE Technologies provides 30,000 free transactions per month and offers
premium automotive-grade traffic data in Germany (powered by BMW, Mercedes-Benz, and Audi).
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
import requests

from ..constants import (
    HERE_GEOCODE_API_BASE,
    HERE_ROUTING_API_BASE,
)
from ..google_maps_parser import is_google_maps_url, resolve_google_maps_route
from ..gpx_parser import is_gpx_path, parse_gpx_file
from ..models import RouteRequest, RouteTelemetry
from .base import BaseCommuteProvider, ProviderError

logger = logging.getLogger(__name__)

# Matches coordinate strings like "52.5200, 13.4050" or "52.5200,13.4050"
COORD_REGEX = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")

# Mapping of common 2-letter ISO codes to 3-letter ISO-3166-1 alpha-3 codes for HERE v7
ISO2_TO_ISO3: Dict[str, str] = {
    "DE": "DEU",
    "AT": "AUT",
    "CH": "CHE",
    "NL": "NLD",
    "BE": "BEL",
    "FR": "FRA",
    "IT": "ITA",
    "ES": "ESP",
    "PL": "POL",
    "CZ": "CZE",
    "DK": "DNK",
    "SE": "SWE",
    "NO": "NOR",
    "GB": "GBR",
    "UK": "GBR",
    "US": "USA",
}


class HereProvider(BaseCommuteProvider):
    """Fetches real-time traffic and route telemetry using the HERE Routing API v8.

    HERE Routing API v8 factors in live traffic conditions, incidents, and
    historical patterns to calculate accurate travel times.
    """

    def __init__(
        self,
        api_key: str,
        country_set: str = "DE",
        timeout_seconds: int = 15,
        session: Optional[requests.Session] = None,
    ) -> None:
        if not api_key or not api_key.strip():
            raise ProviderError("HERE API Key is required for HERE provider.")
        self.api_key = api_key.strip()
        self.country_set = (country_set or "DE").strip().upper()
        self.timeout_seconds = timeout_seconds
        self._session = session or requests.Session()
        self._geocode_cache: Dict[str, str] = {}

    def geocode(self, address_or_coords: str, bias_coords: Optional[tuple[float, float]] = None) -> str:
        """Geocode an address to 'lat,lon' string using HERE Geocoding API v7."""
        clean_addr = address_or_coords.strip()

        # Check if already a coordinate pair
        match = COORD_REGEX.match(clean_addr)
        if match:
            lat = float(match.group(1))
            lon = float(match.group(2))
            return f"{lat},{lon}"

        cache_key = f"{clean_addr}::{bias_coords}"
        if cache_key in self._geocode_cache:
            return self._geocode_cache[cache_key]

        params: Dict[str, Any] = {
            "apiKey": self.api_key,
            "q": clean_addr,
            "limit": 1,
        }

        # Country code restriction (alpha-3)
        if self.country_set:
            alpha3 = ISO2_TO_ISO3.get(self.country_set, self.country_set)
            params["in"] = f"countryCode:{alpha3}"

        if bias_coords:
            params["at"] = f"{bias_coords[0]},{bias_coords[1]}"

        try:
            resp = self._session.get(HERE_GEOCODE_API_BASE, params=params, timeout=self.timeout_seconds)
        except requests.RequestException as e:
            raise ProviderError(f"Network error querying HERE Geocoding API: {e}") from e

        if not resp.ok:
            raise ProviderError(f"HERE Geocoding API error (HTTP {resp.status_code}): {resp.text}")

        try:
            data = resp.json()
        except Exception as e:
            raise ProviderError(f"Invalid JSON from HERE Geocoding: {e}") from e

        items = data.get("items", [])
        if not items:
            raise ProviderError(f"HERE Geocoding: address not found '{clean_addr}'.")

        pos = items[0].get("position", {})
        lat = pos.get("lat")
        lon = pos.get("lng")
        if lat is None or lon is None:
            raise ProviderError(f"HERE Geocoding returned item with missing coordinates for '{clean_addr}'.")

        coord_str = f"{lat},{lon}"
        self._geocode_cache[cache_key] = coord_str
        return coord_str

    def get_route(self, request: RouteRequest) -> RouteTelemetry:
        """Fetch routing telemetry for a single route request using HERE Routing API v8."""
        # 1. Check if request specifies a GPX file
        gpx_path = (request.gpx_path or "").strip()
        if not gpx_path and is_gpx_path(request.origin):
            gpx_path = request.origin.strip()

        # 2. Check if request specifies a Google Maps URL
        maps_link = (request.maps_url or "").strip()
        if not maps_link and not gpx_path and is_google_maps_url(request.origin):
            maps_link = request.origin.strip()

        via_summary = ""
        via_coords: List[str] = []

        if gpx_path:
            try:
                resolved_gpx = parse_gpx_file(gpx_path)
            except Exception as e:
                raise ProviderError(f"Could not load or parse GPX file '{gpx_path}': {e}") from e

            orig_coords = resolved_gpx.origin_coords
            dest_coords = resolved_gpx.destination_coords
            via_coords = resolved_gpx.via_coords
            via_summary = f"via GPX ({resolved_gpx.name or 'Route'})"
        elif maps_link:
            try:
                resolved = resolve_google_maps_route(
                    maps_link,
                    timeout_seconds=self.timeout_seconds,
                    session=self._session,
                )
            except Exception as e:
                raise ProviderError(f"Could not resolve Google Maps URL: {e}") from e

            if resolved.origin_coords:
                orig_coords = resolved.origin_coords
            elif resolved.origin_address:
                orig_coords = self.geocode(resolved.origin_address)
            else:
                orig_coords = self.geocode(request.origin)

            orig_bias: Optional[tuple[float, float]] = None
            try:
                parts = orig_coords.split(",")
                orig_bias = (float(parts[0]), float(parts[1]))
            except Exception:
                pass

            if resolved.destination_coords:
                dest_coords = resolved.destination_coords
            elif resolved.destination_address:
                dest_coords = self.geocode(resolved.destination_address, bias_coords=orig_bias)
            else:
                dest_coords = self.geocode(request.destination, bias_coords=orig_bias)

            if resolved.via_coords:
                via_coords.extend(resolved.via_coords)
                via_summary = "via G-Maps Path"
            elif resolved.via_addresses:
                for va in resolved.via_addresses:
                    via_coords.append(self.geocode(va, bias_coords=orig_bias))
                via_summary = "via G-Maps Path"
        else:
            if not (request.origin and request.origin.strip()):
                raise ProviderError(f"Route '{request.name}' has no origin address configured.")
            if not (request.destination and request.destination.strip()):
                raise ProviderError(f"Route '{request.name}' has no destination address configured.")

            orig_coords = self.geocode(request.origin)
            orig_bias: Optional[tuple[float, float]] = None
            try:
                parts = orig_coords.split(",")
                orig_bias = (float(parts[0]), float(parts[1]))
            except Exception:
                pass

            dest_coords = self.geocode(request.destination, bias_coords=orig_bias)

            if request.via and request.via.strip():
                via_coord = self.geocode(request.via, bias_coords=orig_bias)
                via_coords.append(via_coord)
                via_summary = f"via {request.via.strip()}"

        # Construct HERE Routing API v8 request
        params: Dict[str, Any] = {
            "apiKey": self.api_key,
            "transportMode": "car",
            "origin": orig_coords,
            "destination": dest_coords,
            "return": "summary,travelSummary",
            "routingMode": "fast",
        }

        # Add via pass-through points
        if via_coords:
            # passThrough=true ensures the route bends without an intermediate arrival/stopover
            params["via"] = [f"{vc}!passThrough=true" for vc in via_coords]

        if request.alternative_index > 0:
            params["alternatives"] = max(1, min(request.alternative_index, 5))

        avoid_features: List[str] = []
        if request.avoid_highways:
            avoid_features.append("controlledAccessHighway")
        if request.avoid_tolls:
            avoid_features.append("tollRoad")
        if avoid_features:
            params["avoid[features]"] = ",".join(avoid_features)

        try:
            resp = self._session.get(HERE_ROUTING_API_BASE, params=params, timeout=self.timeout_seconds)
        except requests.RequestException as e:
            raise ProviderError(f"Network error querying HERE Routing API: {e}") from e

        if not resp.ok:
            error_msg = f"HTTP {resp.status_code}"
            try:
                err_data = resp.json()
                title = err_data.get("title")
                detail = err_data.get("detail")
                if title and detail:
                    error_msg = f"{title}: {detail}"
                else:
                    error_msg = detail or title or str(err_data)
            except Exception:
                error_msg = resp.text or error_msg
            raise ProviderError(f"HERE Routing API error: {error_msg}")

        try:
            data = resp.json()
        except Exception as e:
            raise ProviderError(f"Invalid JSON returned from HERE Routing API: {e}") from e

        routes = data.get("routes", [])
        if not routes:
            origin_desc = request.maps_url or request.origin
            dest_desc = request.destination or "(from link)"
            raise ProviderError(
                f"No route found by HERE between '{origin_desc}' and '{dest_desc}'."
            )

        target_idx = max(0, min(request.alternative_index, len(routes) - 1))
        chosen_route = routes[target_idx]
        sections = chosen_route.get("sections", [])
        if not sections:
            raise ProviderError(f"HERE Routing API returned route with empty sections for '{request.name}'.")

        # Sum duration, baseDuration and length across sections
        total_duration_sec = 0
        total_base_duration_sec = 0
        total_length_meters = 0

        for sec in sections:
            # Prefer travelSummary to exclude potential wait times, fallback to summary
            sec_sum = sec.get("travelSummary") or sec.get("summary", {})
            total_duration_sec += int(sec_sum.get("duration", 0))
            total_base_duration_sec += int(sec_sum.get("baseDuration", sec_sum.get("duration", 0)))
            total_length_meters += int(sec_sum.get("length", 0))

        route_summary = ""
        if via_summary:
            route_summary = via_summary
        elif maps_link:
            route_summary = "via G-Maps"
        elif request.avoid_highways:
            route_summary = "via Landstr./Lokal"
        elif target_idx > 0:
            route_summary = f"Alt {target_idx}"
        else:
            route_summary = "Fastest Route"

        return RouteTelemetry(
            name=request.name,
            duration_seconds=total_duration_sec,
            static_duration_seconds=total_base_duration_sec,
            distance_meters=total_length_meters,
            summary=route_summary,
            warnings=[],
        )
