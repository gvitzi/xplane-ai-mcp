"""Integration tests for installation discovery, datarefs, and tools outside flight/weather."""

from __future__ import annotations

import pytest

from integration_constants import EXAMPLE_FAILURE_DATAREF_NAMES
from mcp_integration import (
    assert_xplane_reachable_via_mcp,
    mcp_get_dataref_value,
    mcp_list_available_plane_paths,
    mcp_set_dataref_value,
    mcp_tool_json,
)
from mcp_stdio import McpStdioSession, McpToolError


@pytest.mark.integration
def test_list_available_planes_reads_real_installation(
    mcp_stdio_session: McpStdioSession,
) -> None:
    assert_xplane_reachable_via_mcp(mcp_stdio_session)
    paths = mcp_list_available_plane_paths(mcp_stdio_session)
    assert paths
    assert any(p.endswith(".acf") for p in paths)
