"""Unit tests for the Commute DemoProvider."""

from plugins.commute.models import RouteRequest
from plugins.commute.providers.demo import DemoProvider


def test_demo_provider_single_route():
    provider = DemoProvider()

    # Route 1 request
    req1 = RouteRequest(
        name="A1 Autobahn",
        origin="Start",
        destination="End",
    )
    r1 = provider.get_route(req1)
    assert r1.name == "A1 Autobahn"
    assert r1.duration_minutes == 34
    assert r1.delay_minutes == 12
    assert r1.distance_meters == 32400
    assert r1.summary == "via A1"

    # Route 2 request
    req2 = RouteRequest(
        name="B3 Landstr.",
        origin="Start",
        destination="End",
        alternative_index=1,
    )
    r2 = provider.get_route(req2)
    assert r2.name == "B3 Landstr."
    assert r2.duration_minutes == 28
    assert r2.delay_minutes == 1
    assert r2.distance_meters == 26100
    assert r2.summary == "via B3"


def test_demo_provider_pair():
    provider = DemoProvider()
    req1 = RouteRequest(name="A1", origin="Home", destination="Work")
    req2 = RouteRequest(name="B3", origin="Home", destination="Work")

    pair = provider.get_commute_pair(req1, req2)
    assert pair.route1.duration_minutes == 34
    assert pair.route2.duration_minutes == 28
