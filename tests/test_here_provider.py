"""Unit tests for the HERE Technologies Routing API v8 provider."""

import responses
import pytest

from plugins.commute.constants import (
    HERE_GEOCODE_API_BASE,
    HERE_ROUTING_API_BASE,
)
from plugins.commute.models import RouteRequest
from plugins.commute.providers.base import ProviderError
from plugins.commute.providers.here import HereProvider


def test_here_init_requires_key():
    with pytest.raises(ProviderError, match="HERE API Key is required"):
        HereProvider(api_key="")


def test_here_geocode_raw_coordinates():
    provider = HereProvider(api_key="test_key")
    coords = provider.geocode("52.5200, 13.4050")
    assert coords == "52.52,13.405"


@responses.activate
def test_here_geocode_address_and_caching():
    provider = HereProvider(api_key="test_key", country_set="DE")

    mock_resp = {
        "items": [
            {
                "title": "Musterstr. 1, Berlin",
                "position": {"lat": 52.5123, "lng": 13.3845},
            }
        ]
    }

    responses.add(
        responses.GET,
        HERE_GEOCODE_API_BASE,
        json=mock_resp,
        status=200,
    )

    result = provider.geocode("Musterstr. 1, Berlin")
    assert result == "52.5123,13.3845"

    # Second call should use cache (no second HTTP call)
    cached = provider.geocode("Musterstr. 1, Berlin")
    assert cached == "52.5123,13.3845"
    assert len(responses.calls) == 1


@responses.activate
def test_here_geocode_no_results():
    provider = HereProvider(api_key="test_key")

    responses.add(
        responses.GET,
        HERE_GEOCODE_API_BASE,
        json={"items": []},
        status=200,
    )

    with pytest.raises(ProviderError, match="address not found"):
        provider.geocode("Unknown Street 99999")


@responses.activate
def test_here_get_route_with_traffic_and_waypoint():
    provider = HereProvider(api_key="test_key")

    mock_route_resp = {
        "routes": [
            {
                "id": "route_1",
                "sections": [
                    {
                        "id": "sec_1",
                        "summary": {
                            "duration": 600,
                            "baseDuration": 540,
                            "length": 8000,
                        },
                    },
                    {
                        "id": "sec_2",
                        "summary": {
                            "duration": 480,
                            "baseDuration": 420,
                            "length": 6000,
                        },
                    },
                ],
            }
        ]
    }

    responses.add(
        responses.GET,
        HERE_ROUTING_API_BASE,
        json=mock_route_resp,
        status=200,
    )

    req = RouteRequest(
        name="Work Route",
        origin="52.5200,13.4050",
        destination="52.4800,13.3200",
        via="52.5000,13.3600",
    )

    result = provider.get_route(req)

    assert result.name == "Work Route"
    # total duration = 600 + 480 = 1080s = 18 mins
    assert result.duration_minutes == 18
    # static duration = 540 + 420 = 960s = 16 mins
    assert result.static_duration_minutes == 16
    assert result.delay_minutes == 2
    assert result.distance_meters == 14000
    assert "52.5000,13.3600" in result.summary

    # Verify query params passed to HERE
    call = responses.calls[0]
    assert call.request.params["origin"] == "52.52,13.405"
    assert call.request.params["destination"] == "52.48,13.32"
    assert "52.5,13.36!passThrough=true" in call.request.params["via"]


@responses.activate
def test_here_get_route_avoid_highways_and_tolls():
    provider = HereProvider(api_key="test_key")

    mock_route_resp = {
        "routes": [
            {
                "sections": [
                    {
                        "summary": {
                            "duration": 900,
                            "baseDuration": 900,
                            "length": 12000,
                        }
                    }
                ]
            }
        ]
    }

    responses.add(
        responses.GET,
        HERE_ROUTING_API_BASE,
        json=mock_route_resp,
        status=200,
    )

    req = RouteRequest(
        name="Local Route",
        origin="52.5200,13.4050",
        destination="52.4800,13.3200",
        avoid_highways=True,
        avoid_tolls=True,
    )

    result = provider.get_route(req)
    assert result.name == "Local Route"
    assert result.duration_minutes == 15
    assert result.summary == "via Landstr./Lokal"

    call = responses.calls[0]
    assert "controlledAccessHighway" in call.request.params["avoid[features]"]
    assert "tollRoad" in call.request.params["avoid[features]"]


@responses.activate
def test_here_get_route_alternative_selection():
    provider = HereProvider(api_key="test_key")

    mock_route_resp = {
        "routes": [
            {
                "sections": [{"summary": {"duration": 1200, "baseDuration": 1000, "length": 15000}}]
            },
            {
                "sections": [{"summary": {"duration": 1320, "baseDuration": 1100, "length": 14000}}]
            },
        ]
    }

    responses.add(
        responses.GET,
        HERE_ROUTING_API_BASE,
        json=mock_route_resp,
        status=200,
    )

    req = RouteRequest(
        name="Alt Route",
        origin="52.5200,13.4050",
        destination="52.4800,13.3200",
        alternative_index=1,
    )

    result = provider.get_route(req)
    assert result.duration_minutes == 22  # 1320s / 60
    assert result.distance_meters == 14000
    assert result.summary == "Alt 1"


@responses.activate
def test_here_get_route_with_gpx():
    provider = HereProvider(api_key="test_key")

    mock_route_resp = {
        "routes": [
            {
                "sections": [
                    {
                        "summary": {
                            "duration": 600,
                            "baseDuration": 540,
                            "length": 5200,
                        }
                    }
                ]
            }
        ]
    }

    responses.add(
        responses.GET,
        HERE_ROUTING_API_BASE,
        json=mock_route_resp,
        status=200,
    )

    req = RouteRequest(
        name="GPX Route",
        origin="",
        destination="",
        gpx_path="tests/fixtures/sample_route.gpx",
    )

    result = provider.get_route(req)
    assert result.name == "GPX Route"
    assert result.duration_minutes == 10
    assert result.distance_meters == 5200
    assert "GPX" in result.summary


@responses.activate
def test_here_api_error_response():
    provider = HereProvider(api_key="test_key")

    responses.add(
        responses.GET,
        HERE_ROUTING_API_BASE,
        json={"title": "Invalid Request", "detail": "No route could be calculated"},
        status=400,
    )

    req = RouteRequest(
        name="Error Route",
        origin="52.52,13.40",
        destination="52.48,13.32",
    )

    with pytest.raises(ProviderError, match="HERE Routing API error: Invalid Request: No route could be calculated"):
        provider.get_route(req)
