from __future__ import annotations

import asyncio
import os
from pathlib import Path

import httpx
import pytest

from xplane_mcp.xplane_client import XPlaneConfig, XPlaneHttpClient


def _integration_enabled() -> bool:
    return os.getenv("XPLANE_RUN_INTEGRATION") == "1"


def _require_integration() -> None:
    if not _integration_enabled():
        pytest.skip("Set XPLANE_RUN_INTEGRATION=1 to run live X-Plane integration tests")


def _xplane_root() -> Path:
    value = os.getenv("XPLANE_ROOT")
    if not value:
        pytest.skip("Set XPLANE_ROOT to the X-Plane installation path for integration tests")
    root = Path(value)
    if not root.exists():
        pytest.skip(f"XPLANE_ROOT does not exist: {root}")
    return root


def _config() -> XPlaneConfig:
    return XPlaneConfig(
        host=os.getenv("XPLANE_HOST", "127.0.0.1"),
        port=int(os.getenv("XPLANE_PORT", "8086")),
        timeout=float(os.getenv("XPLANE_TIMEOUT", "60")),
        xplane_root=_xplane_root(),
    )


async def _assert_live_server(client: XPlaneHttpClient) -> None:
    try:
        capabilities = await client.get_capabilities()
    except httpx.HTTPError as exc:  # pragma: no cover - exercised only in live mode
        pytest.skip(f"X-Plane is not reachable: {exc}")
    assert "v3" in capabilities["api"]["versions"]


async def _poll_current_aircraft(
    client: XPlaneHttpClient,
    *,
    expected_path: str,
    timeout: float = 90.0,
) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        current = await client.get_current_aircraft()
        if current.path == expected_path:
            return
        await asyncio.sleep(2)
    raise AssertionError(f"Aircraft did not switch to {expected_path!r} within {timeout} seconds")


async def _choose_alternate_aircraft(client: XPlaneHttpClient) -> str:
    current = await client.get_current_aircraft()
    preferred = [
        "Aircraft/Laminar Research/Cessna 172SP/Cessna_172SP.acf",
        "Aircraft/Laminar Research/Boeing 737-800/b738.acf",
        "Aircraft/Laminar Research/Baron B58/Baron_58.acf",
    ]
    available_paths = {plane.path for plane in client.list_available_planes()}

    for candidate in preferred:
        if candidate in available_paths and candidate != current.path:
            return candidate

    for candidate in sorted(available_paths):
        if candidate != current.path:
            return candidate

    pytest.skip("No alternate aircraft model is available for integration testing")


@pytest.mark.integration
def test_integration_list_available_planes_reads_real_installation():
    _require_integration()
    client = XPlaneHttpClient(_config())

    planes = client.list_available_planes()

    assert planes
    assert any(plane.path.endswith(".acf") for plane in planes)


@pytest.mark.integration
def test_integration_change_plane_model_updates_running_sim():
    _require_integration()

    async def run() -> None:
        async with XPlaneHttpClient(_config()) as client:
            await _assert_live_server(client)
            original = await client.get_current_aircraft()
            target = await _choose_alternate_aircraft(client)
            try:
                await client.change_plane_model(target)
                await _poll_current_aircraft(client, expected_path=target)
            finally:
                await client.change_plane_model(original.path, livery=original.livery)
                await _poll_current_aircraft(client, expected_path=original.path)

    asyncio.run(run())


@pytest.mark.integration
def test_integration_start_new_flight_with_airport_and_model_updates_running_sim():
    _require_integration()

    async def run() -> None:
        async with XPlaneHttpClient(_config()) as client:
            await _assert_live_server(client)
            original_aircraft = await client.get_current_aircraft()
            original_position = await client.get_current_position()
            target_aircraft = await _choose_alternate_aircraft(client)
            airport = os.getenv("XPLANE_TEST_AIRPORT", "KPDX")
            ramp = os.getenv("XPLANE_TEST_RAMP", "A1")

            try:
                await client.start_new_flight(
                    airport,
                    ramp=ramp,
                    aircraft_path=target_aircraft,
                )
                await _poll_current_aircraft(client, expected_path=target_aircraft)
                updated_position = await client.get_current_position()
                assert (
                    abs(updated_position.latitude - original_position.latitude) > 0.01
                    or abs(updated_position.longitude - original_position.longitude) > 0.01
                    or target_aircraft != original_aircraft.path
                )
            finally:
                await client.change_plane_model(original_aircraft.path, livery=original_aircraft.livery)
                await _poll_current_aircraft(client, expected_path=original_aircraft.path)

    asyncio.run(run())
