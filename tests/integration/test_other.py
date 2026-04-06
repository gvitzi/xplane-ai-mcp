"""Integration tests for installation discovery, datarefs, and tools outside flight/weather."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from integration_constants import BARON_B58_ACF_PATH, C172_STOCK_ACF_PATH
from mcp_integration import (
    assert_xplane_reachable_via_mcp,
    mcp_list_available_plane_paths,
    mcp_list_stock_aircraft_paths,
    mcp_tool_json,
)
from mcp_stdio import McpStdioSession, McpToolError

# Client-style envelope (e.g. Cursor ``mcp__*__tool``); aircraft from args, placement via ``lle_ground`` (no ramp assumed).
_RAW_START_NEW_FLIGHT_JSON = (
    '{"tool":"mcp__xplaneMCP__start_new_flight","arguments":'
    '{"airport_id":"EDAY","aircraft_path":"Aircraft/Laminar Research/Cessna 172 SP/Cessna_172SP.acf"}}'
)


@pytest.mark.integration
def test_raw_json_start_new_flight_envelope(
    mcp_stdio_session: McpStdioSession,
    xplane_root: Path,
) -> None:
    """Parse fixed raw JSON and call ``start_flight`` with ``lle_ground_start`` in ``flight_json``."""
    acf = xplane_root.joinpath(
        "Aircraft", "Laminar Research", "Cessna 172 SP", "Cessna_172SP.acf"
    )
    if not acf.is_file():
        pytest.skip(f"Cessna 172 SP stock .acf not found: {acf}")

    payload = json.loads(_RAW_START_NEW_FLIGHT_JSON)
    assert payload.get("tool") == "mcp__xplaneMCP__start_new_flight"
    args = payload["arguments"]
    aircraft_path = str(args["aircraft_path"])

    s = mcp_stdio_session
    assert_xplane_reachable_via_mcp(s)
    # EDDF (Frankfurt)-area coords; sample ``airport_id`` in JSON is not used for placement.
    flight_data = {
        "lle_ground_start": {
            "latitude": 50.0383,
            "longitude": 8.5619,
            "heading_true": 270.0,
        },
        "aircraft": {"path": aircraft_path},
    }
    try:
        mcp_tool_json(s, "start_flight", {"flight_json": json.dumps(flight_data)})
    except McpToolError as exc:
        pytest.skip(f"start_flight from raw JSON envelope not accepted: {exc}")


@pytest.mark.integration
def test_list_available_planes_reads_real_installation(
    mcp_stdio_session: McpStdioSession,
) -> None:
    assert_xplane_reachable_via_mcp(mcp_stdio_session)
    paths = mcp_list_available_plane_paths(mcp_stdio_session)
    assert paths
    assert any(p.endswith(".acf") for p in paths)


@pytest.mark.integration
def test_list_aircraft_liveries_structured_result(
    mcp_stdio_session: McpStdioSession,
) -> None:
    """``list_aircraft_liveries`` returns structuredContent: aircraft with nested liveries[]."""
    raw = mcp_tool_json(mcp_stdio_session, "list_aircraft_liveries", {})
    assert isinstance(raw, dict)
    assert "aircraft" in raw
    ac_list = raw["aircraft"]
    assert isinstance(ac_list, list)
    assert ac_list, "expected at least one .acf under XPLANE_ROOT/Aircraft"

    for ac in ac_list:
        assert isinstance(ac, dict)
        assert "name" in ac and "path" in ac and "liveries" in ac
        assert isinstance(ac["liveries"], list)
        for liv in ac["liveries"]:
            assert isinstance(liv, dict)
            assert "name" in liv and "path" in liv

    filtered = mcp_tool_json(
        mcp_stdio_session,
        "list_aircraft_liveries",
        {"aircraft_path": C172_STOCK_ACF_PATH},
    )
    one = filtered["aircraft"]
    assert isinstance(one, list) and len(one) == 1
    assert one[0]["path"].replace("\\", "/") == C172_STOCK_ACF_PATH
    assert isinstance(one[0]["liveries"], list)


@pytest.mark.integration
def test_list_stock_aircraft_hardcoded_paths(mcp_stdio_session: McpStdioSession) -> None:
    """Stock catalog is static JSON; should include paths used by other integration tests."""
    stock = mcp_list_stock_aircraft_paths(mcp_stdio_session)
    assert C172_STOCK_ACF_PATH in stock
    assert BARON_B58_ACF_PATH in stock
    assert any(p.startswith("Aircraft/Laminar Research/") and p.endswith(".acf") for p in stock)
