"""Unit tests for GoogleRoutesProvider."""

import json
import pytest
import responses
from plugins.commute.constants import (
    GMP_SOLUTION_ID,
    GOOGLE_ROUTES_API_URL,
    ROUTES_FIELD_MASK,
)
from plugins.commute.models import RouteRequest
from plugins.commute.providers.base import ProviderError
from plugins.commute.providers.google_routes import (
    GoogleRoutesProvider,
    parse_duration_string,
)


def test_parse_duration_string():
    assert parse_duration_string(None) == 0
    assert parse_duration_string("") == 0
    assert parse_duration_string("1800s") == 1800
    assert parse_duration_string("120.4s") == 120
    assert parse_duration_string("bad") == 0


def test_provider_init_requires_key():
    with pytest.raises(ProviderError, match="API Key is required"):
        GoogleRoutesProvider(api_key="")


def test_missing_origin_or_destination():
    provider = GoogleRoutesProvider(api_key="fake_key")
    with pytest.raises(ProviderError, match="no origin"):
        provider.get_route(RouteRequest(name="R1", origin="", destination="Dest"))
    with pytest.raises(ProviderError, match="no destination"):
        provider.get_route(RouteRequest(name="R1", origin="Orig", destination=""))


@responses.activate
def test_google_routes_with_waypoint_via():
    provider = GoogleRoutesProvider(api_key="test_api_key_123")

    mock_response = {
        "routes": [
            {
                "duration": "2040s",
                "staticDuration": "1320s",
                "distanceMeters": 32400,
                "description": "A1",
            }
        ]
    }

    responses.add(
        responses.POST,
        GOOGLE_ROUTES_API_URL,
        json=mock_response,
        status=200,
    )

    req = RouteRequest(
        name="A1 via Kreuz",
        origin="Home, Berlin",
        destination="Work, Berlin",
        via="Kreuz Schöneberg",
        avoid_highways=False,
        avoid_tolls=True,
    )

    result = provider.get_route(req)

    assert len(responses.calls) == 1
    call = responses.calls[0]

    # Verify HTTP Headers
    assert call.request.headers["X-Goog-Api-Key"] == "test_api_key_123"
    assert call.request.headers["X-Goog-FieldMask"] == ROUTES_FIELD_MASK
    assert call.request.headers["X-Goog-Maps-Solution-ID"] == GMP_SOLUTION_ID

    # Verify Payload
    body = json.loads(call.request.body)
    assert body["origin"]["address"] == "Home, Berlin"
    assert body["destination"]["address"] == "Work, Berlin"
    assert body["intermediates"] == [{"address": "Kreuz Schöneberg", "via": True}]
    assert body["routeModifiers"]["avoidTolls"] is True
    assert body["routeModifiers"]["avoidHighways"] is False

    # Verify result telemetry
    assert result.name == "A1 via Kreuz"
    assert result.duration_seconds == 2040
    assert result.duration_minutes == 34
    assert result.delay_minutes == 12
    assert result.distance_meters == 32400
    assert result.summary == "via A1"


@responses.activate
def test_google_routes_alternative_selection():
    provider = GoogleRoutesProvider(api_key="test_key")

    mock_response = {
        "routes": [
            {
                "duration": "1800s",
                "staticDuration": "1800s",
                "distanceMeters": 20000,
                "description": "A100",
            },
            {
                "duration": "1620s",
                "staticDuration": "1500s",
                "distanceMeters": 18500,
                "description": "B96",
            },
        ]
    }

    responses.add(
        responses.POST,
        GOOGLE_ROUTES_API_URL,
        json=mock_response,
        status=200,
    )

    # Request alternative index 1
    req = RouteRequest(
        name="Route 2",
        origin="Home",
        destination="Work",
        alternative_index=1,
    )

    result = provider.get_route(req)
    assert result.duration_seconds == 1620
    assert result.duration_minutes == 27
    assert result.summary == "via B96"


@responses.activate
def test_google_routes_api_error_response():
    provider = GoogleRoutesProvider(api_key="test_key")

    responses.add(
        responses.POST,
        GOOGLE_ROUTES_API_URL,
        json={"error": {"message": "API key not valid. Please pass a valid API key."}},
        status=400,
    )

    req = RouteRequest(name="R1", origin="Home", destination="Work")
    with pytest.raises(ProviderError, match="API key not valid"):
        provider.get_route(req)


@responses.activate
def test_google_routes_no_route_found():
    provider = GoogleRoutesProvider(api_key="test_key")

    responses.add(
        responses.POST,
        GOOGLE_ROUTES_API_URL,
        json={"routes": []},
        status=200,
    )

    req = RouteRequest(name="R1", origin="Home", destination="Work")
    with pytest.raises(ProviderError, match="No route found"):
        provider.get_route(req)


@responses.activate
def test_google_routes_with_google_maps_url():
    provider = GoogleRoutesProvider(api_key="test_key")

    shortlink = "https://maps.app.goo.gl/sampleShortlink"
    expanded = (
        "https://www.google.de/maps/dir/Start/Destination/@53.5,10.1,14z/am=t/data="
        "!3m2!1e3!4b1!4m19!4m18!1m10!2m2!1d13.4050!2d52.5200!3m4!1m2!1d13.3501!2d52.5145!1m5!2m2!1d13.3759!2d52.5096!3e0"
    )

    responses.add(
        responses.GET,
        shortlink,
        status=302,
        headers={"Location": expanded},
    )

    mock_response = {
        "routes": [
            {
                "duration": "1080s",
                "staticDuration": "960s",
                "distanceMeters": 14500,
                "description": "B5",
            }
        ]
    }

    responses.add(
        responses.POST,
        GOOGLE_ROUTES_API_URL,
        json=mock_response,
        status=200,
    )

    req = RouteRequest(name="Google Link Route", origin="", destination="", maps_url=shortlink)
    result = provider.get_route(req)

    assert result.name == "Google Link Route"
    assert result.duration_minutes == 18
    assert result.static_duration_minutes == 16
    assert result.delay_minutes == 2
    assert result.distance_meters == 14500
    assert result.summary == "via B5"

    # Verify posted payload has latLng locations
    post_call = [c for c in responses.calls if c.request.method == "POST"][0]
    payload = json.loads(post_call.request.body)
    assert "location" in payload["origin"]
    assert payload["origin"]["location"]["latLng"]["latitude"] == 52.52
    assert payload["destination"]["location"]["latLng"]["latitude"] == 52.5096
    assert len(payload["intermediates"]) == 1
    assert payload["intermediates"][0]["location"]["latLng"]["latitude"] == 52.5145

