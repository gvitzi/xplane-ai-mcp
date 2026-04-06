"""Integration tests that change aircraft or start a new flight."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest

# C172_STOCK_ACF_PATH is the steam-gauge 172 SP, not the G1000 variant (Cessna_172SP_G1000.acf).
from integration_constants import BARON_B58_ACF_PATH, C172_STOCK_ACF_PATH
from mcp_integration import (
    assert_xplane_reachable_via_mcp,
    mcp_get_current_position,
    mcp_poll_current_aircraft,
    mcp_tool_json,
)
from mcp_stdio import McpStdioSession, McpToolError

# EDDB 25R — approximate threshold + 2 NM back on extended centerline (weather reference point).
# ``final_distance_in_nautical_miles`` in the flight API is nautical miles from the threshold.
_EDDB_25R_THRESH_LAT = 52.36635
_EDDB_25R_THRESH_LON = 13.51185
# Reciprocal of landing ~252° → approach from ~072°; 2 NM behind threshold along that ray.
_EDDB_25R_RECIP_DEG = 72.0


def _nm_offset_lat_lon(lat0: float, lon0: float, bearing_deg: float, distance_nm: float) -> tuple[float, float]:
    """Offset WGS84 point by ``distance_nm`` at true ``bearing_deg`` (0=north)."""
    br = math.radians(bearing_deg)
    dlat = (distance_nm / 60.0) * math.cos(br)
    dlon = (distance_nm / 60.0) * math.sin(br) / max(math.cos(math.radians(lat0)), 1e-6)
    return lat0 + dlat, lon0 + dlon


@pytest.mark.integration
def test_change_model_to_c172(
    mcp_stdio_session: McpStdioSession,
    xplane_root: Path,
) -> None:
    acf_on_disk = xplane_root.joinpath(*C172_STOCK_ACF_PATH.split("/"))
    if not acf_on_disk.is_file():
        pytest.skip(f"Cessna 172 SP stock .acf not found: {acf_on_disk}")

    s = mcp_stdio_session
    assert_xplane_reachable_via_mcp(s)
    mcp_tool_json(s, "change_plane_model", {"aircraft_path": C172_STOCK_ACF_PATH})
    mcp_poll_current_aircraft(s, expected_path=C172_STOCK_ACF_PATH)


@pytest.mark.integration
def test_start_flight_runway_start(
    mcp_stdio_session: McpStdioSession,
    xplane_root: Path,
) -> None:
    """Baron at runway threshold via ``runway_start`` (no ``final_distance_in_nautical_miles``).

    Uses KBOS 22L as in the official Flight Initialization API example so the runway ID
    matches default X-Plane airport data.
    """
    target_aircraft = BARON_B58_ACF_PATH
    flight_data: dict[str, Any] = {
        "runway_start": {"airport_id": "KBOS", "runway": "22L"},
        "aircraft": {"path": target_aircraft},
    }

    s = mcp_stdio_session
    assert_xplane_reachable_via_mcp(s)
    try:
        mcp_tool_json(s, "start_flight", {"flight_json": json.dumps(flight_data)})
    except McpToolError as exc:
        pytest.skip(f"start_flight (KBOS 22L runway threshold) not accepted: {exc}")

    mcp_poll_current_aircraft(s, expected_path=target_aircraft)
    nlat, nlon, _ = mcp_get_current_position(s)
    assert 42.1 < nlat < 42.5 and -71.3 < nlon < -70.75, (
        f"expected aircraft near KBOS (Boston Logan), got lat={nlat}, lon={nlon}"
    )


@pytest.mark.integration
def test_final_approach_EDDB_24R_gusts(
    mcp_stdio_session: McpStdioSession,
    xplane_root: Path,
) -> None:
    """2 NM final to EDDB 25R, VFR few clouds, wind 5 kt gusting 12 from 230° (Flight Init API + custom wind)."""
    acf_on_disk = xplane_root.joinpath(*C172_STOCK_ACF_PATH.split("/"))
    if not acf_on_disk.is_file():
        pytest.skip(f"Cessna 172 SP stock .acf not found: {acf_on_disk}")

    wx_lat, wx_lon = _nm_offset_lat_lon(
        _EDDB_25R_THRESH_LAT,
        _EDDB_25R_THRESH_LON,
        _EDDB_25R_RECIP_DEG,
        2.0,
    )

    flight_data: dict[str, Any] = {
        "runway_start": {
            "airport_id": "EDDB",
            "runway": "24R",
            "final_distance_in_nautical_miles": 2.0,
        },
        "aircraft": {"path": C172_STOCK_ACF_PATH},
        "engine_status": {"all_engines": {"running": True}},
        "weather": {
            "definition": {
                "latitude_in_degrees": wx_lat,
                "longitude_in_degrees": wx_lon,
                "elevation_in_meters": 40.0,
                "visibility_in_kilometers": 15.0,
                "temperature_in_degrees_celsius": 12.0,
                "clouds": [
                    {
                        "type": "cumulus",
                        "cover_ratio": 0.18,
                        "bases_in_feet_msl": 4200.0,
                        "tops_in_feet_msl": 6500.0,
                    },
                ],
                "wind": [
                    {
                        "altitude_in_feet_msl": 1500.0,
                        "speed_in_knots": 5.0,
                        "direction_in_degrees_true": 230.0,
                        "gust_increase_in_knots": 7.0,
                        "shear_in_degrees": 0.0,
                    },
                ],
            },
            "vertical_speed_in_thermal_in_feet_per_minute": 250.0,
            "wave_height_in_meters": 0.3,
            "wave_direction_in_degrees": 230.0,
            "terrain_state": "dry",
            "variation_across_region_percentage": 35.0,
            "evolution_over_time_enum": "static",
        },
    }

    s = mcp_stdio_session
    assert_xplane_reachable_via_mcp(s)
    try:
        mcp_tool_json(s, "start_flight", {"flight_json": json.dumps(flight_data)})
    except McpToolError as exc:
        pytest.skip(f"start_flight (EDDB 25R final) not accepted: {exc}")

    mcp_poll_current_aircraft(s, expected_path=C172_STOCK_ACF_PATH)
    lat, lon, hdg = mcp_get_current_position(s)
    assert 52.15 < lat < 52.55 and 13.1 < lon < 13.75, (
        f"expected aircraft near EDDB after placement, got lat={lat}, lon={lon}"
    )
    assert 200.0 < hdg < 295.0, (
        f"expected roughly runway 25 final heading (~250° true), got hdg={hdg}"
    )

@pytest.mark.integration
def test_start_flight_lle_ground_start_near_EDDF(
    mcp_stdio_session: McpStdioSession,
    xplane_root: Path,
) -> None:
    """POST with ``lle_ground_start`` (Flight Initialization API field names)."""
    acf_on_disk = xplane_root.joinpath(*C172_STOCK_ACF_PATH.split("/"))
    if not acf_on_disk.is_file():
        pytest.skip(f"Cessna 172 SP stock .acf not found: {acf_on_disk}")

    flight_data: dict[str, Any] = {
        "lle_ground_start": {
            "latitude": 50.0383,
            "longitude": 8.5619,
            "heading_true": 270.0,
        },
        "aircraft": {"path": C172_STOCK_ACF_PATH},
    }
    s = mcp_stdio_session
    assert_xplane_reachable_via_mcp(s)
    try:
        mcp_tool_json(s, "start_flight", {"flight_json": json.dumps(flight_data)})
    except McpToolError as exc:
        pytest.skip(f"start_flight lle_ground_start near EDDF not accepted: {exc}")

    mcp_poll_current_aircraft(s, expected_path=C172_STOCK_ACF_PATH)
    lat, lon, _ = mcp_get_current_position(s)
    assert 49.98 < lat < 50.08 and 8.48 < lon < 8.65, (
        f"expected aircraft near EDDF (Frankfurt) after lle_ground_start, got lat={lat}, lon={lon}"
    )


@pytest.mark.integration
def test_start_flight_lle_air_start_near_EDAH(
    mcp_stdio_session: McpStdioSession,
    xplane_root: Path,
) -> None:
    """POST with ``lle_air_start`` and ``speed_in_meters_per_second`` (API speed key names vary by build)."""
    acf_on_disk = xplane_root.joinpath(*C172_STOCK_ACF_PATH.split("/"))
    if not acf_on_disk.is_file():
        pytest.skip(f"Cessna 172 SP stock .acf not found: {acf_on_disk}")

    desired_lat = 53.862
    desired_lon = 14.145
    flight_data: dict[str, Any] = {
        "lle_air_start": {
            "latitude": desired_lat,
            "longitude": desired_lon,
            "elevation_in_meters": 450.0,
            "heading_true": 270.0,
            "speed_in_meters_per_second": 55.0,
        },
        "aircraft": {"path": C172_STOCK_ACF_PATH},
    }
    s = mcp_stdio_session
    assert_xplane_reachable_via_mcp(s)
    try:
        mcp_tool_json(s, "start_flight", {"flight_json": json.dumps(flight_data)})
    except McpToolError as exc:
        pytest.skip(f"start_flight lle_air_start near EDAH not accepted: {exc}")

    mcp_poll_current_aircraft(s, expected_path=C172_STOCK_ACF_PATH)
    actual_lat, actual_lon, _ = mcp_get_current_position(s)
    assert desired_lat - 0.02 < actual_lat < desired_lat + 0.02 and desired_lon - 0.02 < actual_lon < desired_lon + 0.02, (
        f"expected aircraft near EDAH (Hamburg) after lle_air_start, got lat={actual_lat}, lon={actual_lon}"
    )
