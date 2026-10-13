"""Pytest fixtures for Commute plugin test suite."""

import json
from pathlib import Path
import pytest


@pytest.fixture
def manifest_dict():
    """Load and parse manifest.json."""
    manifest_path = Path(__file__).parent.parent / "manifest.json"
    with open(manifest_path, encoding="utf-8") as f:
        return json.load(f)
