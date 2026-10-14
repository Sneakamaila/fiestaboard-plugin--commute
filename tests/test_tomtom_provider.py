"""Unit tests for TomTomProvider."""

import pytest
import responses
from plugins.commute.constants import (
    TOMTOM_GEOCODE_API_BASE,
    TOMTOM_ROUTING_API_BASE,
)
from plugins.commute.models import RouteRequest
from plugins.commute.providers.base import ProviderError
from plugins.commute.providers.tomtom import TomTomProvider


def test_tomtom_init_requires_key():
    with pytest.raises(ProviderError, match="TomTom API Key is required"):
        TomTomProvider(api_key="")


def test_tomtom_geocode_raw_coordinates():
    provider = TomTomProvider(api_key="test_key")
    coords = provider.geocode("52.5200, 13.4050")
    assert coords == "52.5200,13.4050"


@responses.activate
def test_tomtom_geocode_address_and_caching():
    provider = TomTomProvider(api_key="test_key")

    mock_geo_resp = {
        "results": [
            {
                "position": {"lat": 52.5200, "lon": 13.4050},
            }
        ]
    }

    responses.add(
        responses.GET,
        f"{TOMTOM_GEOCODE_API_BASE}/Alexanderplatz%2C%20Berlin.json",
        json=mock_geo_resp,
        status=200,
    )

    # First call triggers HTTP request
    coords = provider.geocode("Alexanderplatz, Berlin")
    assert coords == "52.52,13.405"
    assert len(responses.calls) == 1
    assert responses.calls[0].request.params["countrySet"] == "DE"

    # Second call uses in-memory cache, no new HTTP request
    coords2 = provider.geocode("Alexanderplatz, Berlin")
    assert coords2 == "52.52,13.405"
    assert len(responses.calls) == 1


@responses.activate
def test_tomtom_geocode_no_results():
    provider = TomTomProvider(api_key="test_key")

    responses.add(
        responses.GET,
        f"{TOMTOM_GEOCODE_API_BASE}/Nowhere.json",
        json={"results": []},
        status=200,
    )

    with pytest.raises(ProviderError, match="Could not find coordinates"):
        provider.geocode("Nowhere")


@responses.activate
def test_tomtom_get_route_with_traffic_and_waypoint():
    provider = TomTomProvider(api_key="test_key")

    mock_route_resp = {
        "routes": [
            {
                "summary": {
                    "lengthInMeters": 32400,
                    "travelTimeInSeconds": 2040,
                    "trafficDelayInSeconds": 720,
                    "noTrafficTravelTimeInSeconds": 1320,
                }
            }
        ]
    }

    # Pass raw coordinates to bypass geocoding
    responses.add(
        responses.GET,
        f"{TOMTOM_ROUTING_API_BASE}/52.50,13.30:52.52,13.35:52.55,13.40/json",
        json=mock_route_resp,
        status=200,
    )

    req = RouteRequest(
        name="A1 via Kreuz",
        origin="52.50,13.30",
        destination="52.55,13.40",
        via="52.52,13.35",
        avoid_highways=True,
        avoid_tolls=True,
    )

    result = provider.get_route(req)

    assert len(responses.calls) == 1
    call = responses.calls[0]
    assert call.request.params["traffic"] == "true"
    assert call.request.params["travelMode"] == "car"
    assert "motorways" in call.request.params["avoid"]
    assert "tollRoads" in call.request.params["avoid"]

    assert result.name == "A1 via Kreuz"
    assert result.duration_seconds == 2040
    assert result.duration_minutes == 34
    assert result.delay_minutes == 12
    assert result.distance_meters == 32400


@responses.activate
def test_tomtom_get_route_alternative_selection():
    provider = TomTomProvider(api_key="test_key")

    mock_route_resp = {
        "routes": [
            {
                "summary": {
                    "lengthInMeters": 25000,
                    "travelTimeInSeconds": 1800,
                    "trafficDelayInSeconds": 0,
                    "noTrafficTravelTimeInSeconds": 1800,
                }
            },
            {
                "summary": {
                    "lengthInMeters": 27000,
                    "travelTimeInSeconds": 1620,
                    "trafficDelayInSeconds": 60,
                    "noTrafficTravelTimeInSeconds": 1560,
                }
            },
        ]
    }

    responses.add(
        responses.GET,
        f"{TOMTOM_ROUTING_API_BASE}/52.50,13.30:52.55,13.40/json",
        json=mock_route_resp,
        status=200,
    )

    req = RouteRequest(
        name="Alt Route",
        origin="52.50,13.30",
        destination="52.55,13.40",
        alternative_index=1,
    )

    result = provider.get_route(req)
    call = responses.calls[0]
    assert call.request.params["alternativeType"] == "anyRoute"
    assert call.request.params["maxAlternatives"] == "1"
    assert call.request.params["departAt"] == "now"

    assert result.duration_seconds == 1620
    assert result.duration_minutes == 27
    assert result.distance_meters == 27000
    assert "Alt Route 1" in result.summary


@responses.activate
def test_tomtom_api_error_response():
    provider = TomTomProvider(api_key="test_key")

    responses.add(
        responses.GET,
        f"{TOMTOM_ROUTING_API_BASE}/52.50,13.30:52.55,13.40/json",
        json={"error": {"description": "Developer Over Qps"}},
        status=403,
    )

    req = RouteRequest(name="R1", origin="52.50,13.30", destination="52.55,13.40")
    with pytest.raises(ProviderError, match="Developer Over Qps"):
        provider.get_route(req)


@responses.activate
def test_tomtom_get_route_with_google_maps_url():
    provider = TomTomProvider(api_key="test_key")

    shortlink = "https://maps.app.goo.gl/userRoute"
    expanded = (
        "https://www.google.de/maps/dir/Start/Destination/@53.5,10.1,14z/am=t/data="
        "!3m2!1e3!4b1!4m19!4m18!1m10!2m2!1d13.4050!2d52.5200!3m4!1m2!1d13.3501!2d52.5145!1m5!2m2!1d13.3759!2d52.5096!3e0"
    )

    # 1. Mock shortlink 302 redirect
    responses.add(
        responses.GET,
        shortlink,
        status=302,
        headers={"Location": expanded},
    )

    # 2. Mock TomTom Routing API with exact coordinate chain
    mock_route_resp = {
        "routes": [
            {
                "summary": {
                    "lengthInMeters": 14200,
                    "travelTimeInSeconds": 1020,  # 17 mins
                    "trafficDelayInSeconds": 60,
                    "noTrafficTravelTimeInSeconds": 960,  # 16 mins
                }
            }
        ]
    }

    expected_tomtom_url = f"{TOMTOM_ROUTING_API_BASE}/52.52,13.405:52.5096,13.3759/json"
    responses.add(
        responses.GET,
        expected_tomtom_url,
        json=mock_route_resp,
        status=200,
    )

    req = RouteRequest(
        name="B5 via Google Link",
        origin="",
        destination="",
        maps_url=shortlink,
    )

    result = provider.get_route(req)

    assert result.name == "B5 via Google Link"
    assert result.duration_minutes == 17
    assert result.static_duration_minutes == 16
    assert result.delay_minutes == 1
    assert result.distance_meters == 14200
    assert result.summary == "via G-Maps"


@responses.activate
def test_tomtom_get_route_with_real_intermediate_stops():
    provider = TomTomProvider(api_key="test_key")

    expanded_3stops = (
        "https://www.google.de/maps/dir/Start/Middle/End/@53.5,10.1,14z/am=t/data="
        "!3m2!1e3!4b1!4m24!1m5!2m2!1d13.4050!2d52.5200!1m5!2m2!1d13.3501!2d52.5145!1m5!2m2!1d13.3759!2d52.5096!3e0"
    )

    mock_route_resp = {
        "routes": [
            {
                "summary": {
                    "lengthInMeters": 16000,
                    "travelTimeInSeconds": 1200,
                    "trafficDelayInSeconds": 0,
                    "noTrafficTravelTimeInSeconds": 1200,
                }
            }
        ]
    }

    expected_tomtom_url = f"{TOMTOM_ROUTING_API_BASE}/52.52,13.405:52.5145,13.3501:52.5096,13.3759/json"
    responses.add(
        responses.GET,
        expected_tomtom_url,
        json=mock_route_resp,
        status=200,
    )

    req = RouteRequest(
        name="3 Stops Route",
        origin="",
        destination="",
        maps_url=expanded_3stops,
    )

    result = provider.get_route(req)
    assert result.name == "3 Stops Route"
    assert result.duration_minutes == 20
    assert result.summary == "via G-Maps Path"


