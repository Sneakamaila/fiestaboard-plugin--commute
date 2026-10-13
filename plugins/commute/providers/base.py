"""Base interface for commute telemetry providers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import CommuteTelemetry, RouteRequest, RouteTelemetry


class ProviderError(Exception):
    """Raised when telemetry provider encounters an API, network, or data error."""

    pass


class BaseCommuteProvider(ABC):
    """Abstract base class for routing telemetry providers."""

    @abstractmethod
    def get_route(self, request: RouteRequest) -> RouteTelemetry:
        """Fetch routing telemetry for a single route request."""
        raise NotImplementedError

    def get_commute_pair(self, req1: RouteRequest, req2: RouteRequest) -> CommuteTelemetry:
        """Fetch telemetry for two routes to compare."""
        r1 = self.get_route(req1)
        r2 = self.get_route(req2)
        return CommuteTelemetry(route1=r1, route2=r2)
