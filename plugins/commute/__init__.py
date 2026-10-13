"""Smart Commute & Traffic plugin for FiestaBoard."""

from __future__ import annotations

import datetime
import logging
from typing import Any, Dict, List

try:
    from src.plugins.base import PluginBase, PluginResult, TriggerResult
except ImportError:
    # Standalone compatibility fallback
    from dataclasses import dataclass

    @dataclass
    class PluginResult:
        available: bool
        data: dict[str, Any] | None = None
        error: str | None = None
        formatted_lines: list[str] | None = None

    @dataclass
    class TriggerResult:
        triggered: bool
        trigger_id: str = ""
        message: str | None = None
        formatted_lines: list[str] | None = None
        priority: int = 0
        duration_seconds: int = 30
        data: dict[str, Any] | None = None

    class PluginBase:  # type: ignore[no-redef]
        def __init__(self, manifest: dict[str, Any]):
            self._manifest = manifest
            self._config: dict[str, Any] = {}
            self._enabled = False

        @property
        def config(self) -> dict[str, Any]:
            return self._config

        @config.setter
        def config(self, value: dict[str, Any]) -> None:
            self._config = value

        @property
        def enabled(self) -> bool:
            return self._enabled

        @enabled.setter
        def enabled(self, value: bool) -> None:
            self._enabled = value

        def cleanup(self) -> None:
            pass


from .constants import (
    DEFAULT_DELAY_THRESHOLD_MINS,
    DEFAULT_HEAVY_DELAY_THRESHOLD_MINS,
)
from .formatters import (
    compare_routes,
    format_delay,
    format_distance,
    format_duration,
    format_traffic_badge,
    format_traffic_status,
)
from .models import RouteRequest
from .providers import (
    BaseCommuteProvider,
    DemoProvider,
    GoogleRoutesProvider,
    ProviderError,
)

logger = logging.getLogger(__name__)


class CommutePlugin(PluginBase):
    """Smart Commute & Traffic comparison plugin for FiestaBoard."""

    @property
    def plugin_id(self) -> str:
        return "commute"

    def _get_provider(self, cfg: Dict[str, Any]) -> BaseCommuteProvider:
        """Instantiate the appropriate routing telemetry provider."""
        provider_name = (cfg.get("provider") or "").lower().strip()
        demo_mode = bool(cfg.get("demo_mode", False))

        if demo_mode or provider_name == "demo":
            return DemoProvider()

        api_key = str(cfg.get("api_key") or "").strip()
        traffic_model = str(cfg.get("traffic_model") or "best_guess").strip()
        return GoogleRoutesProvider(api_key=api_key, traffic_model=traffic_model)

    def _build_route_requests(self, cfg: Dict[str, Any]) -> tuple[RouteRequest, RouteRequest]:
        """Resolve route requests incorporating fallbacks and route-specific parameters."""
        default_origin = str(cfg.get("origin") or "").strip()
        default_destination = str(cfg.get("destination") or "").strip()

        # Route 1
        r1_name = str(cfg.get("route1_name") or "Route 1").strip()
        r1_orig = str(cfg.get("route1_origin") or "").strip() or default_origin
        r1_dest = str(cfg.get("route1_destination") or "").strip() or default_destination
        r1_via = str(cfg.get("route1_via") or "").strip()
        r1_avoid_hw = bool(cfg.get("route1_avoid_highways", False))
        r1_avoid_tolls = bool(cfg.get("route1_avoid_tolls", False))
        r1_alt_idx = int(cfg.get("route1_alternative_index", 0))

        req1 = RouteRequest(
            name=r1_name,
            origin=r1_orig,
            destination=r1_dest,
            via=r1_via,
            avoid_highways=r1_avoid_hw,
            avoid_tolls=r1_avoid_tolls,
            alternative_index=r1_alt_idx,
        )

        # Route 2
        r2_name = str(cfg.get("route2_name") or "Route 2").strip()
        r2_orig = str(cfg.get("route2_origin") or "").strip() or default_origin
        r2_dest = str(cfg.get("route2_destination") or "").strip() or default_destination
        r2_via = str(cfg.get("route2_via") or "").strip()
        r2_avoid_hw = bool(cfg.get("route2_avoid_highways", False))
        r2_avoid_tolls = bool(cfg.get("route2_avoid_tolls", False))
        r2_alt_idx = int(cfg.get("route2_alternative_index", 1))

        req2 = RouteRequest(
            name=r2_name,
            origin=r2_orig,
            destination=r2_dest,
            via=r2_via,
            avoid_highways=r2_avoid_hw,
            avoid_tolls=r2_avoid_tolls,
            alternative_index=r2_alt_idx,
        )

        return req1, req2

    def fetch_data(self) -> PluginResult:
        """Fetch commute telemetry and return formatted variables."""
        cfg = self.config or {}
        unit_system = str(cfg.get("unit_system") or "metric").lower()
        delay_thresh = int(cfg.get("delay_threshold_mins") or DEFAULT_DELAY_THRESHOLD_MINS)
        heavy_thresh = int(cfg.get("heavy_delay_threshold_mins") or DEFAULT_HEAVY_DELAY_THRESHOLD_MINS)

        try:
            provider = self._get_provider(cfg)
            req1, req2 = self._build_route_requests(cfg)
            pair = provider.get_commute_pair(req1, req2)
            r1, r2 = pair.route1, pair.route2

            # Route 1 formatted metrics
            r1_duration = format_duration(r1.duration_seconds)
            r1_duration_mins = r1.duration_minutes
            r1_static = format_duration(r1.static_duration_seconds)
            r1_delay = format_delay(r1.delay_seconds)
            r1_delay_mins = r1.delay_minutes
            r1_dist = format_distance(r1.distance_meters, unit_system=unit_system)
            r1_badge = format_traffic_badge(r1_delay_mins, delay_thresh, heavy_thresh)
            r1_status = format_traffic_status(r1_delay_mins, delay_thresh, heavy_thresh)

            # Route 2 formatted metrics
            r2_duration = format_duration(r2.duration_seconds)
            r2_duration_mins = r2.duration_minutes
            r2_static = format_duration(r2.static_duration_seconds)
            r2_delay = format_delay(r2.delay_seconds)
            r2_delay_mins = r2.delay_minutes
            r2_dist = format_distance(r2.distance_meters, unit_system=unit_system)
            r2_badge = format_traffic_badge(r2_delay_mins, delay_thresh, heavy_thresh)
            r2_status = format_traffic_status(r2_delay_mins, delay_thresh, heavy_thresh)

            # Route Comparison
            comparison = compare_routes(r1, r2)
            last_updated = datetime.datetime.now().strftime("%H:%M")

            variables = {
                # Route 1
                "route1_name": r1.name,
                "route1_duration": r1_duration,
                "route1_duration_mins": r1_duration_mins,
                "route1_static_duration": r1_static,
                "route1_delay": r1_delay,
                "route1_delay_mins": r1_delay_mins,
                "route1_distance": r1_dist,
                "route1_summary": r1.summary,
                "route1_badge": r1_badge,
                "route1_status": r1_status,
                # Route 2
                "route2_name": r2.name,
                "route2_duration": r2_duration,
                "route2_duration_mins": r2_duration_mins,
                "route2_static_duration": r2_static,
                "route2_delay": r2_delay,
                "route2_delay_mins": r2_delay_mins,
                "route2_distance": r2_dist,
                "route2_summary": r2.summary,
                "route2_badge": r2_badge,
                "route2_status": r2_status,
                # Comparison & Recommendation
                "faster_route": comparison["faster_route"],
                "faster_route_name": comparison["faster_route_name"],
                "time_diff": comparison["time_diff"],
                "time_diff_mins": comparison["time_diff_mins"],
                "recommendation": comparison["recommendation"],
                "recommendation_badge": comparison["recommendation_badge"],
                # System
                "last_updated": last_updated,
            }

            return PluginResult(available=True, data=variables)

        except ProviderError as e:
            logger.warning("Provider error for Commute plugin: %s", e)
            return PluginResult(available=False, error=str(e))
        except Exception as e:
            logger.exception("Unexpected error fetching Commute data")
            return PluginResult(available=False, error=f"Unexpected error: {e}")

    def check_triggers(self) -> List[TriggerResult]:
        """Check for high-priority notification events (heavy delays or better alternative)."""
        triggers: List[TriggerResult] = []
        result = self.fetch_data()
        if not result.available or not result.data:
            return triggers

        data = result.data
        cfg = self.config or {}
        heavy_thresh = int(cfg.get("heavy_delay_threshold_mins") or DEFAULT_HEAVY_DELAY_THRESHOLD_MINS)

        r1_delay_mins = data.get("route1_delay_mins", 0)
        r2_delay_mins = data.get("route2_delay_mins", 0)
        r1_name = data.get("route1_name", "Route 1")
        r2_name = data.get("route2_name", "Route 2")

        # 1. Heavy Delay Trigger on Route 1
        if r1_delay_mins >= heavy_thresh:
            triggers.append(
                TriggerResult(
                    triggered=True,
                    trigger_id=f"commute_delay_r1_{r1_delay_mins}",
                    message=f"Heavy traffic on {r1_name}: +{r1_delay_mins}m delay",
                    priority=2,
                    duration_seconds=60,
                    data=data,
                )
            )

        # 2. Faster Alternative Route Trigger (Route 2 is >= 5 mins faster than Route 1)
        r1_dur_mins = data.get("route1_duration_mins", 0)
        r2_dur_mins = data.get("route2_duration_mins", 0)
        if r1_dur_mins > 0 and r2_dur_mins > 0 and (r1_dur_mins - r2_dur_mins) >= 5:
            savings = r1_dur_mins - r2_dur_mins
            triggers.append(
                TriggerResult(
                    triggered=True,
                    trigger_id=f"commute_alt_faster_{savings}",
                    message=f"{r2_name} is {savings}m faster than {r1_name}",
                    priority=1,
                    duration_seconds=45,
                    data=data,
                )
            )

        return triggers

    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        """Validate configuration settings."""
        errors: List[str] = []
        if not config:
            return errors

        demo_mode = config.get("demo_mode", False)
        provider = (config.get("provider") or "").lower().strip()

        if not demo_mode and provider != "demo":
            # API Key check
            api_key = (config.get("api_key") or "").strip()
            if not api_key:
                errors.append("Google Cloud API Key is required unless Demo Mode is enabled.")

            # Address checks
            default_orig = (config.get("origin") or "").strip()
            default_dest = (config.get("destination") or "").strip()

            r1_orig = (config.get("route1_origin") or "").strip() or default_orig
            r1_dest = (config.get("route1_destination") or "").strip() or default_dest
            r2_orig = (config.get("route2_origin") or "").strip() or default_orig
            r2_dest = (config.get("route2_destination") or "").strip() or default_dest

            if not r1_orig:
                errors.append("Route 1 requires an origin address (or Default Start).")
            if not r1_dest:
                errors.append("Route 1 requires a destination address (or Default Destination).")
            if not r2_orig:
                errors.append("Route 2 requires an origin address (or Default Start).")
            if not r2_dest:
                errors.append("Route 2 requires a destination address (or Default Destination).")

        refresh_seconds = config.get("refresh_seconds")
        if refresh_seconds is not None:
            try:
                val = int(refresh_seconds)
                if val < 60:
                    errors.append("Refresh interval must be at least 60 seconds.")
            except (ValueError, TypeError):
                errors.append("Refresh interval must be a valid integer.")

        unit_system = config.get("unit_system")
        if unit_system and str(unit_system).lower() not in ("metric", "imperial"):
            errors.append("Unit system must be either 'metric' or 'imperial'.")

        return errors
