from __future__ import annotations

import os
from pathlib import Path

import pytest

from mcp_stdio import McpServerLaunch, default_mcp_server_argv, start_mcp_session


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--xplane-root",
        action="store",
        default=None,
        help="Path to X-Plane installation (required for integration tests).",
    )
    parser.addoption(
        "--mcp-server",
        action="store",
        default=None,
        help=(
            "Path to XPlaneMcp.Server executable (or `dotnet` + DLL as one argv string is not supported; "
            "pass a single .exe or native binary path). Default: auto-detect Release/Debug build under src/."
        ),
    )
    parser.addoption(
        "--xplane-host",
        action="store",
        default="127.0.0.1",
        help="X-Plane Web API host (default: 127.0.0.1).",
    )
    parser.addoption(
        "--xplane-port",
        action="store",
        default=8086,
        type=int,
        help="X-Plane Web API port (default: 8086).",
    )
    parser.addoption(
        "--xplane-timeout",
        action="store",
        default=60.0,
        type=float,
        help="HTTP timeout in seconds for the MCP server → X-Plane client (default: 60).",
    )
    parser.addoption(
        "--xplane-test-airport",
        action="store",
        default="KPDX",
        help="ICAO for integration tests that use --xplane-test-airport (default: KPDX).",
    )
    parser.addoption(
        "--xplane-test-ramp",
        action="store",
        default="A1",
        help="Ramp id for integration tests that use --xplane-test-ramp (default: A1).",
    )
    parser.addoption(
        "--xplane-weather-region-index",
        action="store",
        default=-1,
        type=int,
        help=(
            "Sea-level pressure test: array index, or -1 (default) to auto-detect "
            "(try scalar read first, then index 0)."
        ),
    )
    parser.addoption(
        "--xplane-keep-cloud-layer",
        action="store_true",
        default=False,
        help=(
            "Regional cloud integration tests (broken layer, clear sky): skip restoring "
            "written cloud datarefs so you can verify visuals in X-Plane."
        ),
    )


@pytest.fixture
def xplane_root(request: pytest.FixtureRequest) -> Path:
    raw_root = request.config.getoption("--xplane-root")
    if not raw_root:
        pytest.skip("Pass --xplane-root=PATH to your X-Plane installation.")
    root = Path(raw_root)
    if not root.exists():
        pytest.skip(f"--xplane-root does not exist: {root}")
    return root


@pytest.fixture
def mcp_stdio_session(request: pytest.FixtureRequest, xplane_root: Path):
    """Spawn the C# MCP server (stdio) with XPLANE_* env; yield session; terminate process."""
    repo_root = Path(request.config.rootpath)
    custom = request.config.getoption("--mcp-server")
    if custom:
        argv = [custom.strip()]
    else:
        argv = default_mcp_server_argv(repo_root)
    if not argv:
        pytest.skip(
            "MCP server not found. Build with `dotnet build -c Release` or pass "
            "`--mcp-server=PATH` to XPlaneMcp.Server.exe."
        )

    env = os.environ.copy()
    env["XPLANE_HOST"] = str(request.config.getoption("--xplane-host"))
    env["XPLANE_PORT"] = str(request.config.getoption("--xplane-port"))
    env["XPLANE_TIMEOUT"] = str(request.config.getoption("--xplane-timeout"))
    env["XPLANE_ROOT"] = str(xplane_root)

    session = start_mcp_session(McpServerLaunch(argv=argv, cwd=repo_root, env=env))
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def xplane_test_airport(request: pytest.FixtureRequest) -> str:
    return request.config.getoption("--xplane-test-airport")


@pytest.fixture
def xplane_test_ramp(request: pytest.FixtureRequest) -> str:
    return request.config.getoption("--xplane-test-ramp")


@pytest.fixture
def xplane_weather_region_index(request: pytest.FixtureRequest) -> int:
    """-1 means auto; >= 0 forces that array index for the weather dataref test."""
    return request.config.getoption("--xplane-weather-region-index")


@pytest.fixture
def xplane_keep_cloud_layer(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--xplane-keep-cloud-layer"))
