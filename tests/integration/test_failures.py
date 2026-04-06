"""Integration tests that arm X-Plane failure datarefs (changes persist in the sim)."""

from __future__ import annotations

import time

import pytest

from mcp_integration import (
    assert_xplane_reachable_via_mcp,
    mcp_find_dataref,
    mcp_get_dataref_value,
    mcp_set_dataref_value,
    mcp_tool_json,
)
from mcp_stdio import McpStdioSession, McpToolError

# sim/operation/failures/* use failure_enum; 6 is the usual “failed / inoperative now” state in X-Plane.
_FAILURE_ACTIVE = 6

_ELECTRICAL_BUS_1 = "sim/operation/failures/rel_esys"
_ENGINE_1_LOSS_OF_POWER = "sim/operation/failures/rel_engfai0"
_PITOT_1_BLOCKAGE = "sim/operation/failures/rel_pitot"
_FIX_ALL_SYSTEMS_CMD = "sim/operation/fix_all_systems"


def _apply_failure_dataref(
    s: McpStdioSession,
    dataref_name: str,
    *,
    value: int = _FAILURE_ACTIVE,
) -> None:
    assert_xplane_reachable_via_mcp(s)
    meta = mcp_find_dataref(s, dataref_name)
    dr_id = str(meta["id"])
    before = mcp_get_dataref_value(s, dr_id)
    original = before["data"]
    try:
        mcp_set_dataref_value(s, dr_id, value)
    except McpToolError as exc:
        if "dataref_is_readonly" in str(exc).lower():
            pytest.skip(f"Failure dataref read-only: {dataref_name}")
        raise
    after = mcp_get_dataref_value(s, dr_id)
    assert after["data"] != original or original == value, (
        f"{dataref_name} did not change after write (before={original!r} after={after['data']!r})"
    )


@pytest.mark.integration
def test_electrical_system_bus_1_failure(mcp_stdio_session: McpStdioSession) -> None:
    """Electrical System (Bus 1) — DataRefs.txt ``rel_esys``."""
    _apply_failure_dataref(mcp_stdio_session, _ELECTRICAL_BUS_1)


@pytest.mark.integration
def test_engine_one_loss_of_power_failure(mcp_stdio_session: McpStdioSession) -> None:
    """Engine 1 loss of power (no smoke) — ``rel_engfai0``."""
    _apply_failure_dataref(mcp_stdio_session, _ENGINE_1_LOSS_OF_POWER)


@pytest.mark.integration
def test_pitot_blocked_pilot(mcp_stdio_session: McpStdioSession) -> None:
    """Pilot pitot blockage (blocked / no dynamic pressure) — ``rel_pitot``."""
    _apply_failure_dataref(mcp_stdio_session, _PITOT_1_BLOCKAGE)


@pytest.mark.integration
def test_reset_all_failures(mcp_stdio_session: McpStdioSession) -> None:
    """``sim/operation/fix_all_systems`` clears failures (verified via pitot blockage dataref)."""
    s = mcp_stdio_session
    assert_xplane_reachable_via_mcp(s)
    _apply_failure_dataref(s, _PITOT_1_BLOCKAGE)
    try:
        mcp_tool_json(
            s,
            "activate_command_by_name",
            {"name": _FIX_ALL_SYSTEMS_CMD, "duration": 0.0},
        )
    except McpToolError as exc:
        pytest.skip(f"Could not run {_FIX_ALL_SYSTEMS_CMD!r}: {exc}")
    time.sleep(0.5)
    meta = mcp_find_dataref(s, _PITOT_1_BLOCKAGE)
    dr_id = str(meta["id"])
    cleared = mcp_get_dataref_value(s, dr_id)["data"]
    assert float(cleared) == pytest.approx(0.0, abs=0.01), (
        f"expected {_PITOT_1_BLOCKAGE} cleared after fix_all, got {cleared!r}"
    )
