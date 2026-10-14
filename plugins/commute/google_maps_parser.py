"""Parser and resolver for Google Maps route URLs."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import re
from typing import Dict, List, Tuple
import urllib.parse
import requests

logger = logging.getLogger(__name__)

# Matches Google Maps shortlinks and full URLs
GMAPS_URL_REGEX = re.compile(
    r"^https?://(?:maps\.app\.goo\.gl/|goo\.gl/maps/|(?:www\.)?google\.[a-z.]+/maps)",
    re.IGNORECASE,
)

# Matches coordinate pairs in Google Maps URL data parameters: !1d<lon>!2d<lat>
COORD_PROTOBUF_REGEX = re.compile(r"!1d(-?\d+(?:\.\d+)?)\!2d(-?\d+(?:\.\d+)?)")

# Matches coordinate string like "52.5200,13.4050" or "52.5200, 13.4050"
COORD_REGEX = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")

# Matches /maps/dir/stop1/stop2/...
DIR_PATH_REGEX = re.compile(r"/maps/dir/(.*?)(?:/@|\?|/data=|$)", re.IGNORECASE)


@dataclass
class ResolvedGoogleRoute:
    """Parsed route locations from a Google Maps link."""

    origin_coords: str = ""
    destination_coords: str = ""
    via_coords: List[str] = field(default_factory=list)
    origin_address: str = ""
    destination_address: str = ""
    via_addresses: List[str] = field(default_factory=list)
    expanded_url: str = ""


_URL_CACHE: Dict[str, ResolvedGoogleRoute] = {}


def is_google_maps_url(url: str | None) -> bool:
    """Check if a string looks like a Google Maps route URL."""
    if not url:
        return False
    clean = url.strip()
    return bool(GMAPS_URL_REGEX.match(clean)) or ("google." in clean and "/maps" in clean)


def resolve_google_maps_route(
    url: str,
    timeout_seconds: int = 10,
    session: requests.Session | None = None,
) -> ResolvedGoogleRoute:
    """Resolve a Google Maps URL (shortlink or full) and extract coordinates and waypoints."""
    clean_url = (url or "").strip()
    if not clean_url:
        raise ValueError("Empty Google Maps URL provided.")

    if clean_url in _URL_CACHE:
        return _URL_CACHE[clean_url]

    target_url = clean_url

    # Only fetch over network if it is a shortlink or not already an expanded URL containing route data
    is_shortlink = "maps.app.goo.gl" in clean_url or "goo.gl/maps" in clean_url
    has_route_data = "!1d" in clean_url or "/maps/dir/" in clean_url

    if is_shortlink or not has_route_data:
        s = session or requests.Session()
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

        try:
            resp = s.get(clean_url, allow_redirects=False, headers=headers, timeout=timeout_seconds)
            target_url = resp.headers.get("Location") or resp.url
            if resp.status_code in (301, 302, 303, 307, 308) and "Location" in resp.headers:
                target_url = resp.headers["Location"]
                if target_url.startswith("/"):
                    target_url = urllib.parse.urljoin(clean_url, target_url)
        except requests.RequestException as e:
            raise ValueError(f"Failed to fetch Google Maps link: {e}") from e

    # If redirected through consent screen, extract continue URL if present
    if "consent.google" in target_url:
        parsed = urllib.parse.urlparse(target_url)
        qs = urllib.parse.parse_qs(parsed.query)
        if "continue" in qs and qs["continue"]:
            target_url = qs["continue"][0]

    unquoted_url = urllib.parse.unquote(target_url)

    # 1. Try extracting protobuf coordinate pairs: !1d<lon>!2d<lat>
    matches = COORD_PROTOBUF_REGEX.findall(unquoted_url)
    points: List[Tuple[float, float]] = []
    for lon_str, lat_str in matches:
        try:
            pt = (float(lat_str), float(lon_str))
            if not points or points[-1] != pt:
                points.append(pt)
        except ValueError:
            continue

    # 2. Extract human-readable addresses or path stops from /maps/dir/...
    origin_addr = ""
    dest_addr = ""
    via_addrs: List[str] = []
    dir_match = DIR_PATH_REGEX.search(unquoted_url)
    if dir_match:
        dir_content = dir_match.group(1)
        raw_stops = [urllib.parse.unquote_plus(x).strip() for x in dir_content.split("/") if x.strip()]
        if len(raw_stops) >= 1:
            origin_addr = raw_stops[0]
        if len(raw_stops) >= 2:
            dest_addr = raw_stops[-1]
            via_addrs = raw_stops[1:-1]

    # 3. Check query parameters (e.g. ?api=1&origin=...&destination=...&waypoints=...)
    parsed_q = urllib.parse.urlparse(unquoted_url)
    qs = urllib.parse.parse_qs(parsed_q.query)
    if "origin" in qs and qs["origin"] and not origin_addr:
        origin_addr = qs["origin"][0]
    if "destination" in qs and qs["destination"] and not dest_addr:
        dest_addr = qs["destination"][0]
    if "waypoints" in qs and qs["waypoints"] and not via_addrs:
        via_addrs = [w.strip() for w in qs["waypoints"][0].split("|") if w.strip()]

    # If protobuf coordinates were found (standard Google Maps share link)
    if len(points) >= 2:
        origin_coords = f"{points[0][0]},{points[0][1]}"
        destination_coords = f"{points[-1][0]},{points[-1][1]}"
        via_coords = [f"{p[0]},{p[1]}" for p in points[1:-1]]
    else:
        # Check if stops in path or query are raw coordinates
        origin_coords = ""
        destination_coords = ""
        via_coords = []

        if origin_addr and COORD_REGEX.match(origin_addr):
            origin_coords = COORD_REGEX.sub(r"\1,\2", origin_addr)
            origin_addr = ""
        if dest_addr and COORD_REGEX.match(dest_addr):
            destination_coords = COORD_REGEX.sub(r"\1,\2", dest_addr)
            dest_addr = ""
        for va in via_addrs:
            if COORD_REGEX.match(va):
                via_coords.append(COORD_REGEX.sub(r"\1,\2", va))

    if not (origin_coords or origin_addr) or not (destination_coords or dest_addr):
        raise ValueError(
            f"Could not extract origin and destination from Google Maps URL: {target_url}"
        )

    resolved = ResolvedGoogleRoute(
        origin_coords=origin_coords,
        destination_coords=destination_coords,
        via_coords=via_coords,
        origin_address=origin_addr,
        destination_address=dest_addr,
        via_addresses=[va for va in via_addrs if not COORD_REGEX.match(va)],
        expanded_url=target_url,
    )

    _URL_CACHE[clean_url] = resolved
    return resolved
