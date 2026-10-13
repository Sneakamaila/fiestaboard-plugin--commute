"""Demo provider for simulating commute routes without credentials."""

from __future__ import annotations

from ..models import CommuteTelemetry, RouteRequest, RouteTelemetry
from .base import BaseCommuteProvider


class DemoProvider(BaseCommuteProvider):
    """Simulates realistic commute telemetry for visual testing and demo mode."""

    def get_route(self, request: RouteRequest) -> RouteTelemetry:
        """Return simulated route telemetry."""
        name_lower = request.name.lower()

        # If it looks like Route 2 or an alternative route
        if (
            "2" in name_lower
            or "b3" in name_lower
            or "land" in name_lower
            or request.alternative_index > 0
        ):
            return RouteTelemetry(
                name=request.name or "B3 Landstr.",
                duration_seconds=1680,  # 28 mins
                static_duration_seconds=1620,  # 27 mins
                distance_meters=26100,  # 26.1 km
                summary="via B3",
            )

        # Default: Route 1 (Autobahn with traffic delay)
        return RouteTelemetry(
            name=request.name or "A1 Autobahn",
            duration_seconds=2040,  # 34 mins
            static_duration_seconds=1320,  # 22 mins
            distance_meters=32400,  # 32.4 km
            summary="via A1",
        )

    def get_commute_pair(self, req1: RouteRequest, req2: RouteRequest) -> CommuteTelemetry:
        """Return simulated pair with Route 1 experiencing traffic and Route 2 clear."""
        r1 = RouteTelemetry(
            name=req1.name or "A1 Autobahn",
            duration_seconds=2040,  # 34 mins
            static_duration_seconds=1320,  # 22 mins
            distance_meters=32400,  # 32.4 km
            summary="via A1",
        )
        r2 = RouteTelemetry(
            name=req2.name or "B3 Landstr.",
            duration_seconds=1680,  # 28 mins
            static_duration_seconds=1620,  # 27 mins
            distance_meters=26100,  # 26.1 km
            summary="via B3",
        )
        return CommuteTelemetry(route1=r1, route2=r2)
