"""Tests for GPX route parser."""

import os
from pathlib import Path
import pytest

from plugins.commute.gpx_parser import (
    is_gpx_path,
    parse_gpx_content,
    parse_gpx_file,
    resolve_gpx_path,
)


def test_is_gpx_path():
    assert is_gpx_path("route.gpx") is True
    assert is_gpx_path("routes/my_commute_route.gpx") is True
    assert is_gpx_path("/tmp/test.GPX") is True
    assert is_gpx_path("<?xml version='1.0'?><gpx>...</gpx>") is True
    assert is_gpx_path("https://maps.app.goo.gl/123") is False
    assert is_gpx_path("Musterstrasse 1, Berlin") is False
    assert is_gpx_path("") is False


def test_parse_sample_gpx_file():
    resolved = parse_gpx_file("tests/fixtures/sample_route.gpx")
    assert resolved.origin_coords == "52.5200,13.4050"
    assert resolved.destination_coords == "52.5000,13.3000"
    assert resolved.via_coords == ["52.5100,13.3500"]
    assert len(resolved.supporting_points) == 5
    assert resolved.name == "Sample Test Route"


def test_parse_minimal_gpx_xml():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <gpx version="1.1" creator="test">
        <wpt lat="52.52" lon="13.405"/>
        <wpt lat="52.51" lon="13.35"/>
        <wpt lat="52.50" lon="13.30"/>
    </gpx>
    """
    resolved = parse_gpx_content(xml)
    assert resolved.origin_coords == "52.52,13.405"
    assert resolved.destination_coords == "52.50,13.30"
    assert resolved.via_coords == ["52.51,13.35"]
    assert resolved.supporting_points == []


def test_parse_track_only_gpx():
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <gpx version="1.1" creator="test">
        <trk>
            <name>Track Only Route</name>
            <trkseg>
                <trkpt lat="52.52" lon="13.405"/>
                <trkpt lat="52.51" lon="13.35"/>
                <trkpt lat="52.50" lon="13.30"/>
            </trkseg>
        </trk>
    </gpx>
    """
    resolved = parse_gpx_content(xml)
    assert resolved.origin_coords == "52.52,13.405"
    assert resolved.destination_coords == "52.5,13.3"
    assert len(resolved.supporting_points) == 3
    assert resolved.name == "Track Only Route"


def test_parse_empty_gpx_raises():
    with pytest.raises(ValueError, match="empty"):
        parse_gpx_content("")


def test_resolve_nonexistent_gpx_raises():
    with pytest.raises(FileNotFoundError):
        resolve_gpx_path("nonexistent_file_xyz_1234.gpx")
