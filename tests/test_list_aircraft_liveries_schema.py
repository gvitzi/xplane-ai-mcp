"""``list_aircraft_liveries``: fetch structuredContent from the running MCP server (integration only)."""

from __future__ import annotations

import pytest

from integration_constants import C172_STOCK_ACF_PATH
from mcp_integration import assert_xplane_reachable_via_mcp, mcp_tool_json
from mcp_stdio import McpStdioSession


@pytest.mark.integration
def test_list_aircraft_liveries_from_mcp_server(
    mcp_stdio_session: McpStdioSession,
) -> None:
    """Calls ``list_aircraft_liveries`` over stdio; asserts aircraft + nested liveries from XPLANE_ROOT."""
    assert_xplane_reachable_via_mcp(mcp_stdio_session)
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
