"""Unit tests for the FiestaBoard CommutePlugin."""

import pytest
from plugins.commute import CommutePlugin


def test_plugin_properties(manifest_dict):
    plugin = CommutePlugin(manifest=manifest_dict)
    assert plugin.plugin_id == "commute"


def test_validate_config(manifest_dict):
    plugin = CommutePlugin(manifest=manifest_dict)

    # Valid config with api_key and default origin/destination
    valid_cfg = {
        "api_key": "token_123",
        "origin": "Home, Berlin",
        "destination": "Work, Berlin",
        "refresh_seconds": 300,
    }
    assert plugin.validate_config(valid_cfg) == []

    # Valid config with demo_mode (no api key or addresses needed)
    assert plugin.validate_config({"demo_mode": True}) == []

    # Invalid: missing api_key when demo_mode is False (TomTom default)
    errors = plugin.validate_config({
        "demo_mode": False,
        "origin": "Home",
        "destination": "Work",
    })
    assert any("TomTom API Key is required" in err for err in errors)

    # Invalid: missing api_key when provider is google_routes
    errors_google = plugin.validate_config({
        "provider": "google_routes",
        "demo_mode": False,
        "origin": "Home",
        "destination": "Work",
    })
    assert any("Google Cloud API Key is required" in err for err in errors_google)

    # Invalid: missing origin and destination (and no GPX / Google Maps link)
    errors = plugin.validate_config({"api_key": "token_123"})
    assert any("requires either a GPX file, Google Maps Link" in err for err in errors)

    # Valid: using Google Maps links instead of manual addresses
    maps_cfg = {
        "api_key": "token_123",
        "route1_maps_url": "https://maps.app.goo.gl/route1",
        "route2_maps_url": "https://maps.app.goo.gl/route2",
    }
    assert plugin.validate_config(maps_cfg) == []

    # Valid: using GPX files
    gpx_cfg = {
        "api_key": "token_123",
        "route1_gpx_path": "tests/fixtures/sample_route.gpx",
        "route2_gpx_path": "tests/fixtures/sample_route.gpx",
    }
    assert plugin.validate_config(gpx_cfg) == []


    # Invalid: refresh_seconds too low
    errors = plugin.validate_config({"demo_mode": True, "refresh_seconds": 30})
    assert any("at least 60 seconds" in err for err in errors)

    # Invalid: unit_system
    errors = plugin.validate_config({"demo_mode": True, "unit_system": "yards"})
    assert any("Unit system must be" in err for err in errors)


def test_fetch_data_demo_mode(manifest_dict):
    plugin = CommutePlugin(manifest=manifest_dict)
    plugin.config = {
        "demo_mode": True,
        "unit_system": "metric",
        "route1_name": "A1 Autobahn",
        "route2_name": "B3 Landstr.",
    }

    result = plugin.fetch_data()
    assert result.available is True
    assert result.error is None
    assert result.data is not None

    data = result.data

    # Verify all manifest variables exist in the payload
    manifest_vars = manifest_dict.get("variables", {}).get("simple", {})
    for var_name in manifest_vars:
        assert var_name in data, f"Manifest variable '{var_name}' missing from fetch_data() result"

    # Route 1 checks
    assert data["route1_name"] == "A1 Autobahn"
    assert data["route1_duration"] == "34m"
    assert data["route1_duration_mins"] == 34
    assert data["route1_delay"] == "+12m"
    assert data["route1_delay_mins"] == 12
    assert "km" in data["route1_distance"]
    assert data["route1_badge"] == "{65}"  # 12 min delay is moderate (< 15)
    assert data["route1_status"] == "MODERATE"

    # Route 2 checks
    assert data["route2_name"] == "B3 Landstr."
    assert data["route2_duration"] == "28m"
    assert data["route2_duration_mins"] == 28
    assert data["route2_delay"] == "+1m"
    assert data["route2_delay_mins"] == 1
    assert "km" in data["route2_distance"]
    assert data["route2_badge"] == "{66}"  # 1 min delay is clear (< 5)
    assert data["route2_status"] == "CLEAR"

    # Comparison checks
    assert data["faster_route"] == "Route 2"
    assert data["faster_route_name"] == "B3 Landstr."
    assert data["time_diff"] == "6m"
    assert data["time_diff_mins"] == 6
    assert "TAKE B3 LANDSTR. (-6M)" in data["recommendation"]
    assert data["recommendation_badge"] == "{66}"
    assert ":" in data["last_updated"]


def test_check_triggers_demo_mode(manifest_dict):
    plugin = CommutePlugin(manifest=manifest_dict)
    plugin.config = {
        "demo_mode": True,
        "heavy_delay_threshold_mins": 10,  # 12 min delay will exceed this!
    }

    triggers = plugin.check_triggers()
    assert len(triggers) >= 1

    trigger_ids = [t.trigger_id for t in triggers]
    # Heavy delay trigger on Route 1 (12 mins >= 10 mins)
    assert any("commute_delay_r1" in tid for tid in trigger_ids)
    # Alternative faster trigger (28m vs 34m = 6m savings >= 5m)
    assert any("commute_alt_faster" in tid for tid in trigger_ids)


def test_manifest_previews_and_teaser_compliance(manifest_dict):
    """Ensure manifest teaser and previews strictly comply with FiestaBoard dimensional constraints."""
    import re

    color_marker_re = re.compile(r"\{([0-9]{1,2}|[a-zA-Z_]+)\}")
    valid_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890 !@#$()+-&=;: '\"%,./?")

    def count_tiles(text: str) -> int:
        tiles = 0
        pos = 0
        while pos < len(text):
            m = color_marker_re.match(text, pos)
            if m:
                tiles += 1
                pos = m.end()
                continue
            tiles += 1
            pos += 1
        return tiles

    # 1. Teaser check: max 15 tiles (Note width)
    teaser = manifest_dict.get("teaser", "")
    assert teaser, "Teaser is required"
    assert count_tiles(teaser) <= 15, f"Teaser exceeds 15 tiles: {count_tiles(teaser)}"

    # 2. Previews check: Flagship (22 cols, 6 rows), Note (15 cols, 3 rows)
    previews = manifest_dict.get("previews", [])
    assert previews, "Previews are required"

    dims = {"flagship": (6, 22), "note": (3, 15)}
    for p_idx, preview in enumerate(previews):
        device = preview.get("device_type")
        assert device in dims, f"Unknown device_type: {device}"
        max_rows, max_cols = dims[device]
        rows = preview.get("rows", [])
        assert len(rows) <= max_rows, f"Preview {p_idx} has too many rows ({len(rows)} > {max_rows})"
        for r_idx, row in enumerate(rows):
            width = count_tiles(row)
            assert width <= max_cols, f"Preview {p_idx} row {r_idx} exceeds {max_cols} tiles: {width} -> '{row}'"
            pos = 0
            while pos < len(row):
                m = color_marker_re.match(row, pos)
                if m:
                    pos = m.end()
                    continue
                c = row[pos].upper()
                assert c in valid_chars, f"Unmappable character '{c}' in preview {p_idx} row {r_idx}"
                pos += 1
