"""Helpers for driving the C# MCP server in integration tests (stdio JSON-RPC)."""

from __future__ import annotations

import json
import time
from typing import Any

import pytest

from mcp_stdio import McpStdioSession, McpToolError, decode_xplane_dataref_string


def mcp_tool_json(session: McpStdioSession, name: str, arguments: dict[str, Any]) -> Any:
    text = session.call_tool(name, arguments)
    return json.loads(text)


def assert_xplane_reachable_via_mcp(session: McpStdioSession) -> None:
    try:
        cap = mcp_tool_json(session, "get_capabilities", {})
    except McpToolError as exc:
        pytest.skip(f"X-Plane Web API not reachable via MCP server: {exc}")
    assert "v3" in cap.get("api", {}).get("versions", []), cap


def mcp_find_dataref(session: McpStdioSession, name: str) -> dict[str, Any]:
    try:
        return mcp_tool_json(session, "find_dataref", {"name": name})
    except McpToolError as exc:
        if "not found" in str(exc).lower() or "404" in str(exc):
            pytest.skip(f"Dataref not available: {name}")
        raise


def mcp_get_dataref_value(
    session: McpStdioSession,
    dataref_id: str,
    *,
    index: int | None = None,
) -> dict[str, Any]:
    args: dict[str, Any] = {"dataref_id": str(dataref_id)}
    if index is not None:
        args["index"] = index
    return mcp_tool_json(session, "get_dataref_value", args)


def mcp_set_dataref_value(
    session: McpStdioSession,
    dataref_id: str,
    value: Any,
    *,
    index: int | None = None,
) -> None:
    args: dict[str, Any] = {
        "dataref_id": str(dataref_id),
        "value_json": json.dumps(value),
    }
    if index is not None:
        args["index"] = index
    mcp_tool_json(session, "set_dataref_value", args)


def mcp_resolve_region_array_element(
    session: McpStdioSession,
    dataref_name: str,
    element_index: int,
) -> tuple[str, int | None, Any]:
    meta = mcp_find_dataref(session, dataref_name)
    dr_id = str(meta["id"])
    for idx in (None, element_index):
        try:
            if idx is None:
                payload = mcp_get_dataref_value(session, dr_id)
            else:
                payload = mcp_get_dataref_value(session, dr_id, index=idx)
            return dr_id, idx, payload["data"]
        except McpToolError:
            continue
    pytest.skip(
        f"Could not read {dataref_name!r} at layer {element_index} "
        "(tried scalar and indexed access)."
    )


def mcp_read_scalar_dataref(session: McpStdioSession, name: str) -> tuple[str, Any]:
    meta = mcp_find_dataref(session, name)
    dr_id = str(meta["id"])
    payload = mcp_get_dataref_value(session, dr_id)
    return dr_id, payload["data"]


def mcp_read_region_cloud_layer_value(
    session: McpStdioSession,
    dr_id: str,
    layer: int,
    label: str,
) -> float:
    def _coerce_list(val: list[Any], idx: int) -> float:
        if len(val) > idx:
            return float(val[idx])
        if len(val) == 1:
            return float(val[0])
        pytest.skip(f"{label} array too short for layer {idx}")

    try:
        payload = mcp_get_dataref_value(session, dr_id, index=layer)
        raw = payload["data"]
        if isinstance(raw, list):
            return _coerce_list(raw, layer)
        return float(raw)
    except McpToolError:
        try:
            payload = mcp_get_dataref_value(session, dr_id)
            raw = payload["data"]
            if not isinstance(raw, list):
                return float(raw)
            return _coerce_list(raw, layer)
        except McpToolError as exc:
            pytest.skip(f"Could not read {label}: {exc}")


def mcp_set_region_value(
    session: McpStdioSession,
    dr_id: str,
    index_param: int | None,
    value: float,
) -> None:
    mcp_set_dataref_value(session, dr_id, value, index=index_param)


RegionalWeatherPrimers = tuple[str | None, Any, str | None, Any]


def mcp_apply_regional_weather_draw_primers(session: McpStdioSession) -> RegionalWeatherPrimers:
    override_clouds_id: str | None = None
    override_clouds_orig: Any = None
    change_mode_id: str | None = None
    change_mode_orig: Any = None
    try:
        override_clouds_id, override_clouds_orig = mcp_read_scalar_dataref(
            session,
            "sim/operation/override/override_clouds",
        )
        mcp_set_dataref_value(session, override_clouds_id, 1)
    except McpToolError:
        override_clouds_id = None
    try:
        change_mode_id, change_mode_orig = mcp_read_scalar_dataref(
            session,
            "sim/weather/region/change_mode",
        )
        mcp_set_dataref_value(session, change_mode_id, 3)
    except McpToolError:
        change_mode_id = None
    return override_clouds_id, override_clouds_orig, change_mode_id, change_mode_orig


def mcp_restore_regional_weather_draw_primers(
    session: McpStdioSession,
    pack: RegionalWeatherPrimers,
) -> None:
    override_clouds_id, override_clouds_orig, change_mode_id, change_mode_orig = pack
    if change_mode_id is not None:
        try:
            mcp_set_dataref_value(session, change_mode_id, change_mode_orig)
        except McpToolError:
            pass
    if override_clouds_id is not None:
        try:
            mcp_set_dataref_value(session, override_clouds_id, override_clouds_orig)
        except McpToolError:
            pass


def mcp_list_all_commands(session: McpStdioSession) -> list[dict[str, Any]]:
    page_size = 250
    start = 0
    out: list[dict[str, Any]] = []
    while True:
        batch = mcp_tool_json(
            session,
            "list_commands",
            {"limit": page_size, "start": start},
        )
        if not batch:
            break
        out.extend(batch)
        if len(batch) < page_size:
            break
        start += page_size
    return out


def mcp_get_current_aircraft(session: McpStdioSession) -> tuple[str, str | None]:
    path_dr = mcp_find_dataref(session, "sim/aircraft/view/acf_relative_path")
    liv_dr = mcp_find_dataref(session, "sim/aircraft/view/acf_livery_path")
    path_raw = mcp_get_dataref_value(session, str(path_dr["id"]))["data"]
    liv_raw = mcp_get_dataref_value(session, str(liv_dr["id"]))["data"]
    path = decode_xplane_dataref_string(path_raw)
    if not path:
        pytest.fail("Current aircraft path is empty from simulator")
    livery = decode_xplane_dataref_string(liv_raw) or None
    return path, livery


def mcp_get_current_position(session: McpStdioSession) -> tuple[float, float, float]:
    lat = float(mcp_get_dataref_value(session, str(mcp_find_dataref(session, "sim/flightmodel/position/latitude")["id"]))["data"])
    lon = float(mcp_get_dataref_value(session, str(mcp_find_dataref(session, "sim/flightmodel/position/longitude")["id"]))["data"])
    hdg = float(mcp_get_dataref_value(session, str(mcp_find_dataref(session, "sim/flightmodel/position/true_psi")["id"]))["data"])
    return lat, lon, hdg


def mcp_poll_current_aircraft(
    session: McpStdioSession,
    *,
    expected_path: str,
    timeout: float = 90.0,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        path, _ = mcp_get_current_aircraft(session)
        if path == expected_path:
            return
        time.sleep(2)
    raise AssertionError(f"Aircraft did not switch to {expected_path!r} within {timeout} seconds")


def mcp_list_available_plane_paths(session: McpStdioSession) -> set[str]:
    raw = mcp_tool_json(session, "list_available_planes", {})
    if not raw:
        return set()
    paths: set[str] = set()
    for item in raw:
        if isinstance(item, dict) and (p := item.get("Path")):
            paths.add(str(p))
    return paths


def mcp_choose_alternate_aircraft(session: McpStdioSession, preferred: list[str]) -> str:
    current_path, _ = mcp_get_current_aircraft(session)
    available = mcp_list_available_plane_paths(session)
    for candidate in preferred:
        if candidate in available and candidate != current_path:
            return candidate
    for candidate in sorted(available):
        if candidate != current_path:
            return candidate
    pytest.skip("No alternate aircraft model is available for integration testing")
