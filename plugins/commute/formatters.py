"""Formatting utilities for the FiestaBoard Commute plugin."""

from __future__ import annotations

from typing import Any, Dict

from .constants import (
    COLOR_BLACK,
    COLOR_GREEN,
    COLOR_RED,
    COLOR_YELLOW,
    DEFAULT_DELAY_THRESHOLD_MINS,
    DEFAULT_HEAVY_DELAY_THRESHOLD_MINS,
    STATUS_CLEAR,
    STATUS_HEAVY,
    STATUS_MODERATE,
)
from .models import RouteTelemetry


def format_duration(seconds: int | float | None) -> str:
    """Format total seconds into human-readable duration (e.g., '34m' or '1h 12m')."""
    if seconds is None or seconds < 0:
        return "--"

    total_mins = max(0, round(seconds / 60))
    if total_mins < 60:
        return f"{total_mins}m"

    hours = total_mins // 60
    mins = total_mins % 60
    return f"{hours}h {mins}m"


def format_delay(delay_seconds: int | float | None) -> str:
    """Format delay in traffic into e.g. '+12m' or '0m'."""
    if delay_seconds is None or delay_seconds < 0:
        return "--"

    mins = max(0, round(delay_seconds / 60))
    if mins == 0:
        return "0m"
    return f"+{mins}m"


def format_distance(meters: int | float | None, unit_system: str = "metric") -> str:
    """Format distance in km or miles."""
    if meters is None or meters < 0:
        return "--"

    if (unit_system or "").lower() == "imperial":
        miles = meters * 0.000621371
        return f"{miles:.1f} mi"

    km = meters / 1000.0
    return f"{km:.1f} km"


def format_traffic_badge(
    delay_mins: int,
    delay_threshold: int = DEFAULT_DELAY_THRESHOLD_MINS,
    heavy_threshold: int = DEFAULT_HEAVY_DELAY_THRESHOLD_MINS,
) -> str:
    """Return Vestaboard color tile badge according to traffic delay."""
    if delay_mins < delay_threshold:
        return COLOR_GREEN
    if delay_mins < heavy_threshold:
        return COLOR_YELLOW
    return COLOR_RED


def format_traffic_status(
    delay_mins: int,
    delay_threshold: int = DEFAULT_DELAY_THRESHOLD_MINS,
    heavy_threshold: int = DEFAULT_HEAVY_DELAY_THRESHOLD_MINS,
) -> str:
    """Return text status according to traffic delay."""
    if delay_mins < delay_threshold:
        return STATUS_CLEAR
    if delay_mins < heavy_threshold:
        return STATUS_MODERATE
    return STATUS_HEAVY


def compare_routes(route1: RouteTelemetry, route2: RouteTelemetry) -> Dict[str, Any]:
    """Compare two route telemetry objects and compute delta & recommendations."""
    r1_mins = route1.duration_minutes
    r2_mins = route2.duration_minutes

    diff_mins = abs(r1_mins - r2_mins)
    time_diff_str = f"{diff_mins}m"

    if r1_mins < r2_mins:
        faster_route = "Route 1"
        faster_route_name = route1.name
        recommendation = f"TAKE {route1.name.upper()} (-{diff_mins}M)"[:22]
        recommendation_badge = COLOR_GREEN
    elif r2_mins < r1_mins:
        faster_route = "Route 2"
        faster_route_name = route2.name
        recommendation = f"TAKE {route2.name.upper()} (-{diff_mins}M)"[:22]
        recommendation_badge = COLOR_GREEN
    else:
        faster_route = "EQUAL"
        faster_route_name = "Both equal"
        recommendation = "EQUAL TRAVEL TIME"
        recommendation_badge = COLOR_BLACK

    return {
        "faster_route": faster_route,
        "faster_route_name": faster_route_name,
        "time_diff": time_diff_str,
        "time_diff_mins": diff_mins,
        "recommendation": recommendation,
        "recommendation_badge": recommendation_badge,
    }
