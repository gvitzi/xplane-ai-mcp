"""Contract for ``list_aircraft_liveries`` structuredContent (runs in default pytest; no MCP/X-Plane)."""

from __future__ import annotations

from typing import Any


def _assert_liveries_payload(raw: dict[str, Any]) -> None:
    ac_list = raw["aircraft"]
    assert isinstance(ac_list, list)
    for ac in ac_list:
        assert isinstance(ac, dict)
        assert isinstance(ac.get("name"), str)
        assert isinstance(ac.get("path"), str)
        livs = ac["liveries"]
        assert isinstance(livs, list)
        for liv in livs:
            assert isinstance(liv, dict)
            assert isinstance(liv.get("name"), str)
            assert isinstance(liv.get("path"), str)


def test_list_aircraft_liveries_structured_shape_matches_server_contract() -> None:
    """Mirrors XPlaneMcpTools.ListAircraftLiveries / MCP structuredContent."""
    sample: dict[str, Any] = {
        "aircraft": [
            {
                "name": "Cessna 172 SP",
                "path": "Aircraft/Laminar Research/Cessna 172 SP/Cessna_172SP.acf",
                "liveries": [
                    {
                        "name": "Example Livery",
                        "path": "Aircraft/Laminar Research/Cessna 172 SP/liveries/Example Livery",
                    }
                ],
            }
        ]
    }
    _assert_liveries_payload(sample)


def test_list_aircraft_liveries_empty_install_is_valid() -> None:
    _assert_liveries_payload({"aircraft": []})
