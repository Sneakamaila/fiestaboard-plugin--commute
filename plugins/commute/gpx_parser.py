"""GPX route parser for FiestaBoard Commute plugin.

Supports standard GPX 1.0/1.1 files as well as TomTom MyDrive GPX exports,
extracting origin, destination, intermediate waypoints (via points),
and full supporting trackpoints for route reconstruction with real-time traffic.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as ET


@dataclass
class ResolvedGpxRoute:
    """Parsed routing details extracted from a GPX file."""

    origin_coords: str = ""
    destination_coords: str = ""
    via_coords: List[str] = field(default_factory=list)
    supporting_points: List[Dict[str, float]] = field(default_factory=list)
    name: str = ""


def is_gpx_path(value: str) -> bool:
    """Return True if the string looks like a GPX filename, path, or XML header."""
    if not value or not isinstance(value, str):
        return False
    val = value.strip()
    if val.lower().endswith(".gpx"):
        return True
    if "<gpx" in val.lower():
        return True
    return False


def resolve_gpx_path(file_path_or_name: str, base_dir: Optional[Path] = None) -> Path:
    """Locate a GPX file across possible directories (routes/, current dir, plugin dir)."""
    p = Path(file_path_or_name)
    if p.is_file():
        return p

    search_dirs: List[Path] = []
    if base_dir:
        search_dirs.extend([
            base_dir,
            base_dir / "routes",
            base_dir.parent / "routes" if base_dir.parent else None,
        ])

    cwd = Path.cwd()
    search_dirs.extend([
        cwd,
        cwd / "routes",
        Path(__file__).resolve().parent.parent.parent / "routes",
    ])

    for d in search_dirs:
        if not d or not d.is_dir():
            continue
        cand = d / p
        if cand.is_file():
            return cand
        cand_name = d / p.name
        if cand_name.is_file():
            return cand_name

    raise FileNotFoundError(f"GPX file not found: {file_path_or_name}")


def _clean_tag(tag: str) -> str:
    """Strip XML namespace from tag."""
    return tag.split("}")[-1] if "}" in tag else tag


def parse_gpx_content(xml_text: str) -> ResolvedGpxRoute:
    """Parse GPX XML string into ResolvedGpxRoute."""
    if not xml_text or not xml_text.strip():
        raise ValueError("GPX content is empty")

    root = ET.fromstring(xml_text)

    # 1. Extract route name
    name = ""
    for elem in root.iter():
        if _clean_tag(elem.tag) == "name" and elem.text and elem.text.strip():
            name = elem.text.strip()
            break

    # 2. Extract waypoints (<wpt> or <rtept>)
    wpts: List[str] = []
    for elem in root:
        if _clean_tag(elem.tag) in ("wpt", "rtept"):
            lat = elem.attrib.get("lat")
            lon = elem.attrib.get("lon")
            if lat and lon:
                wpts.append(f"{lat},{lon}")

    # Fallback to route points inside <rte>
    if not wpts:
        for rte in root.iter():
            if _clean_tag(rte.tag) == "rte":
                for child in rte:
                    if _clean_tag(child.tag) == "rtept":
                        lat = child.attrib.get("lat")
                        lon = child.attrib.get("lon")
                        if lat and lon:
                            wpts.append(f"{lat},{lon}")

    # 3. Extract trackpoints (<trkpt>)
    supporting_points: List[Dict[str, float]] = []
    for elem in root.iter():
        if _clean_tag(elem.tag) == "trkpt":
            lat = elem.attrib.get("lat")
            lon = elem.attrib.get("lon")
            if lat and lon:
                try:
                    supporting_points.append({
                        "latitude": round(float(lat), 6),
                        "longitude": round(float(lon), 6),
                    })
                except (ValueError, TypeError):
                    pass

    origin_coords = ""
    destination_coords = ""
    via_coords: List[str] = []

    if len(wpts) >= 2:
        origin_coords = wpts[0]
        destination_coords = wpts[-1]
        via_coords = wpts[1:-1]
    elif supporting_points:
        # Fall back to first and last trackpoint
        first_p = supporting_points[0]
        last_p = supporting_points[-1]
        origin_coords = f"{first_p['latitude']},{first_p['longitude']}"
        destination_coords = f"{last_p['latitude']},{last_p['longitude']}"
    elif len(wpts) == 1:
        origin_coords = wpts[0]

    if not origin_coords or not destination_coords:
        raise ValueError("Could not determine origin and destination coordinates from GPX file.")

    return ResolvedGpxRoute(
        origin_coords=origin_coords,
        destination_coords=destination_coords,
        via_coords=via_coords,
        supporting_points=supporting_points,
        name=name,
    )


def parse_gpx_file(file_path_or_name: str, base_dir: Optional[Path] = None) -> ResolvedGpxRoute:
    """Locate and parse a GPX file."""
    path = resolve_gpx_path(file_path_or_name, base_dir=base_dir)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return parse_gpx_content(content)
