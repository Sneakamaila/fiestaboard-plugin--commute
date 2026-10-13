"""Unit tests for commute formatters."""

import pytest
from plugins.commute.constants import (
    COLOR_BLACK,
    COLOR_GREEN,
    COLOR_RED,
    COLOR_YELLOW,
    STATUS_CLEAR,
    STATUS_HEAVY,
    STATUS_MODERATE,
)
from plugins.commute.formatters import (
    compare_routes,
    format_delay,
    format_distance,
    format_duration,
    format_traffic_badge,
    format_traffic_status,
)
from plugins.commute.models import RouteTelemetry


def test_format_duration():
    assert format_duration(None) == "--"
    assert format_duration(-10) == "--"
    assert format_duration(0) == "0m"
    assert format_duration(50) == "1m"
    assert format_duration(1800) == "30m"
    assert format_duration(3600) == "1h 0m"
    assert format_duration(4500) == "1h 15m"


def test_format_delay():
    assert format_delay(None) == "--"
    assert format_delay(-5) == "--"
    assert format_delay(0) == "0m"
    assert format_delay(25) == "0m"
    assert format_delay(60) == "+1m"
    assert format_delay(720) == "+12m"


def test_format_distance():
    assert format_distance(None) == "--"
    assert format_distance(-100) == "--"
    assert format_distance(0, unit_system="metric") == "0.0 km"
    assert format_distance(25400, unit_system="metric") == "25.4 km"
    assert format_distance(16093.4, unit_system="imperial") == "10.0 mi"


def test_format_traffic_badge_and_status():
    # Delay < 5 min -> green / clear
    assert format_traffic_badge(2, delay_threshold=5, heavy_threshold=15) == COLOR_GREEN
    assert format_traffic_status(2, delay_threshold=5, heavy_threshold=15) == STATUS_CLEAR

    # 5 <= Delay < 15 -> yellow / moderate
    assert format_traffic_badge(8, delay_threshold=5, heavy_threshold=15) == COLOR_YELLOW
    assert format_traffic_status(8, delay_threshold=5, heavy_threshold=15) == STATUS_MODERATE

    # Delay >= 15 -> red / heavy
    assert format_traffic_badge(18, delay_threshold=5, heavy_threshold=15) == COLOR_RED
    assert format_traffic_status(18, delay_threshold=5, heavy_threshold=15) == STATUS_HEAVY


def test_compare_routes():
    # Route 1 faster
    r1 = RouteTelemetry(
        name="A1",
        duration_seconds=1200,  # 20m
        static_duration_seconds=1200,
        distance_meters=20000,
    )
    r2 = RouteTelemetry(
        name="B3",
        duration_seconds=1800,  # 30m
        static_duration_seconds=1500,
        distance_meters=22000,
    )
    comp = compare_routes(r1, r2)
    assert comp["faster_route"] == "Route 1"
    assert comp["faster_route_name"] == "A1"
    assert comp["time_diff"] == "10m"
    assert comp["time_diff_mins"] == 10
    assert "TAKE A1 (-10M)" in comp["recommendation"]
    assert comp["recommendation_badge"] == COLOR_GREEN

    # Route 2 faster
    r1.duration_seconds = 2400  # 40m
    r2.duration_seconds = 1800  # 30m
    comp2 = compare_routes(r1, r2)
    assert comp2["faster_route"] == "Route 2"
    assert comp2["faster_route_name"] == "B3"
    assert comp2["time_diff"] == "10m"
    assert "TAKE B3 (-10M)" in comp2["recommendation"]
    assert comp2["recommendation_badge"] == COLOR_GREEN

    # Equal duration
    r1.duration_seconds = 1800
    r2.duration_seconds = 1800
    comp_equal = compare_routes(r1, r2)
    assert comp_equal["faster_route"] == "EQUAL"
    assert comp_equal["time_diff"] == "0m"
    assert comp_equal["time_diff_mins"] == 0
    assert comp_equal["recommendation"] == "EQUAL TRAVEL TIME"
    assert comp_equal["recommendation_badge"] == COLOR_BLACK
