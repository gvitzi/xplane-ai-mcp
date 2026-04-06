"""Smoke test: repo-root pytest config exposes the Python Web API client on PYTHONPATH."""

from __future__ import annotations


def test_xplane_mcp_client_importable() -> None:
    import xplane_mcp
    from xplane_mcp.xplane_client import XPlaneConfig

    assert hasattr(xplane_mcp, "XPlaneHttpClient")
    assert XPlaneConfig().rest_base_url.startswith("http://")
