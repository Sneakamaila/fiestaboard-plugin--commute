"""Unit tests for google_maps_parser."""

import pytest
import responses
from plugins.commute.google_maps_parser import (
    is_google_maps_url,
    resolve_google_maps_route,
)


def test_is_google_maps_url():
    assert is_google_maps_url("https://maps.app.goo.gl/sampleShortlink123") is True
    assert is_google_maps_url("http://goo.gl/maps/xyz") is True
    assert is_google_maps_url("https://www.google.de/maps/dir/A/B") is True
    assert is_google_maps_url("https://google.com/maps") is True
    assert is_google_maps_url("https://maps.google.com/?q=52,13") is True
    assert is_google_maps_url("https://example.com") is False
    assert is_google_maps_url("") is False
    assert is_google_maps_url(None) is False


@responses.activate
def test_resolve_google_maps_route_shortlink():
    shortlink = "https://maps.app.goo.gl/sample123"
    expanded = (
        "https://www.google.de/maps/dir/Alexanderplatz,+10178+Berlin,+Deutschland/"
        "Potsdamer+Platz,+10785+Berlin,+Deutschland/@53.5122874,10.1215512,14z/am=t/data="
        "!3m2!1e3!4b1!4m19!4m18!1m10!1m1!1s0x47b18976b9762cf1:0xfbe757657ea4d026"
        "!2m2!1d13.4050!2d52.5200!3m4!1m2!1d13.3501!2d52.5145!3s0x47b189e4726615b3:0xbcfce8145ae78550"
        "!1m5!1m1!1s0x47b18be59b0ae9f1:0xab953257850284ab!2m2!1d13.3759!2d52.5096!3e0"
    )

    responses.add(
        responses.GET,
        shortlink,
        status=302,
        headers={"Location": expanded},
    )

    resolved = resolve_google_maps_route(shortlink)

    assert resolved.origin_coords == "52.52,13.405"
    assert resolved.destination_coords == "52.5096,13.3759"
    assert resolved.via_coords == ["52.5145,13.3501"]
    assert "StartCity" in resolved.origin_address
    assert "EndCity" in resolved.destination_address


def test_resolve_google_maps_route_expanded_url_without_network():
    expanded = (
        "https://www.google.de/maps/dir/Start+Location/End+Location/@52.5,13.4,12z/data="
        "!4m18!1m10!2m2!1d13.4050!2d52.5200!3m4!1m2!1d13.3500!2d52.5100!1m5!2m2!1d13.3000!2d52.5000"
    )

    resolved = resolve_google_maps_route(expanded)

    assert resolved.origin_coords == "52.52,13.405"
    assert resolved.destination_coords == "52.5,13.3"
    assert resolved.via_coords == ["52.51,13.35"]
    assert resolved.origin_address == "Start Location"
    assert resolved.destination_address == "End Location"


def test_resolve_google_maps_route_path_addresses_only():
    url = "https://www.google.com/maps/dir/Alexanderplatz,+Berlin/Potsdamer+Platz,+Berlin"

    resolved = resolve_google_maps_route(url)

    assert resolved.origin_coords == ""
    assert resolved.destination_coords == ""
    assert resolved.origin_address == "Alexanderplatz, Berlin"
    assert resolved.destination_address == "Potsdamer Platz, Berlin"


def test_resolve_google_maps_route_query_params():
    url = "https://www.google.com/maps/dir/?api=1&origin=52.52,13.40&destination=52.50,13.30&waypoints=52.51,13.35|52.515,13.36"

    resolved = resolve_google_maps_route(url)

    assert resolved.origin_coords == "52.52,13.40"
    assert resolved.destination_coords == "52.50,13.30"
    assert resolved.via_coords == ["52.51,13.35", "52.515,13.36"]


def test_resolve_google_maps_route_invalid_empty():
    with pytest.raises(ValueError, match="Empty Google Maps URL"):
        resolve_google_maps_route("")


def test_resolve_google_maps_route_no_stops():
    with pytest.raises(ValueError, match="Could not extract origin and destination"):
        resolve_google_maps_route("https://www.google.com/maps/@52.52,13.40,15z")
