"""Data models for the FiestaBoard Commute plugin."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class RouteRequest:
    """Request definition for a commute route."""

    name: str
    origin: str
    destination: str
    via: str = ""
    avoid_highways: bool = False
    avoid_tolls: bool = False
    alternative_index: int = 0
    maps_url: str = ""


@dataclass
class RouteTelemetry:
    """Calculated route metrics returned by a data provider."""

    name: str
    duration_seconds: int
    static_duration_seconds: int
    distance_meters: int
    summary: str = ""
    warnings: List[str] = field(default_factory=list)

    @property
    def duration_minutes(self) -> int:
        """Total duration in traffic rounded to nearest minute."""
        return max(0, round(self.duration_seconds / 60))

    @property
    def static_duration_minutes(self) -> int:
        """Base duration without traffic delay rounded to nearest minute."""
        return max(0, round(self.static_duration_seconds / 60))

    @property
    def delay_seconds(self) -> int:
        """Delay caused by traffic (non-negative)."""
        return max(0, self.duration_seconds - self.static_duration_seconds)

    @property
    def delay_minutes(self) -> int:
        """Delay caused by traffic in rounded minutes."""
        return max(0, round(self.delay_seconds / 60))


@dataclass
class CommuteTelemetry:
    """Combined telemetry comparing two routes."""

    route1: RouteTelemetry
    route2: RouteTelemetry
