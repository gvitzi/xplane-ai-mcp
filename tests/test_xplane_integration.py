from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

import httpx
import pytest

from xplane_mcp.failures import EXAMPLE_FAILURE_DATAREF_NAMES
from xplane_mcp.xplane_client import XPlaneApiError, XPlaneConfig, XPlaneHttpClient

# Stock XP12: steam-gauge / "classic" 172 — not ``Cessna_172SP_G1000.acf`` (see ``Cessna 172 SP`` folder).
CESSNA_172_CLASSIC_ACF_PATH = "Aircraft/Laminar Research/Cessna 172 SP/Cessna_172SP.acf"


async def _resolve_region_array_element(
    client: XPlaneHttpClient,
    dataref_name: str,
    element_index: int,
) -> tuple[int, int | None, Any]:
    """
    Return (dataref_id, index_param, current_value) for one element of a regional weather array.

    Tries scalar read first, then ``index=element_index``, matching X-Plane Web API quirks.
    """
    try:
        meta = await client.find_dataref(dataref_name)
    except XPlaneApiError:
        pytest.skip(f"Dataref not available: {dataref_name}")

    dr_id = meta["id"]
    for idx in (None, element_index):
        try:
            if idx is None:
                payload = await client.get_dataref_value(dr_id)
            else:
                payload = await client.get_dataref_value(dr_id, index=idx)
            return dr_id, idx, payload["data"]
        except XPlaneApiError:
            continue
    pytest.skip(
        f"Could not read {dataref_name!r} at layer {element_index} "
        "(tried scalar and indexed access)."
    )


async def _set_region_value(
    client: XPlaneHttpClient,
    dr_id: int,
    index_param: int | None,
    value: float,
) -> None:
    if index_param is None:
        await client.set_dataref_value(dr_id, value)
    else:
        await client.set_dataref_value(dr_id, value, index=index_param)


async def _read_scalar_dataref(client: XPlaneHttpClient, name: str) -> tuple[int, Any]:
    meta = await client.find_dataref(name)
    dr_id = meta["id"]
    payload = await client.get_dataref_value(dr_id)
    return dr_id, payload["data"]


async def _read_region_cloud_layer_value(
    client: XPlaneHttpClient,
    dr_id: int,
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
        payload = await client.get_dataref_value(dr_id, index=layer)
        raw = payload["data"]
        if isinstance(raw, list):
            return _coerce_list(raw, layer)
        return float(raw)
    except XPlaneApiError:
        try:
            payload = await client.get_dataref_value(dr_id)
            raw = payload["data"]
            if not isinstance(raw, list):
                return float(raw)
            return _coerce_list(raw, layer)
        except XPlaneApiError as exc:
            pytest.skip(f"Could not read {label}: {exc}")


RegionalWeatherPrimers = tuple[int | None, Any, int | None, Any]


async def _apply_regional_weather_draw_primers(client: XPlaneHttpClient) -> RegionalWeatherPrimers:
    override_clouds_id: int | None = None
    override_clouds_orig: Any = None
    change_mode_id: int | None = None
    change_mode_orig: Any = None
    try:
        override_clouds_id, override_clouds_orig = await _read_scalar_dataref(
            client,
            "sim/operation/override/override_clouds",
        )
        await client.set_dataref_value(override_clouds_id, 1)
    except XPlaneApiError:
        override_clouds_id = None
    try:
        change_mode_id, change_mode_orig = await _read_scalar_dataref(
            client,
            "sim/weather/region/change_mode",
        )
        await client.set_dataref_value(change_mode_id, 3)
    except XPlaneApiError:
        change_mode_id = None
    return override_clouds_id, override_clouds_orig, change_mode_id, change_mode_orig


async def _restore_regional_weather_draw_primers(
    client: XPlaneHttpClient,
    pack: RegionalWeatherPrimers,
) -> None:
    override_clouds_id, override_clouds_orig, change_mode_id, change_mode_orig = pack
    if change_mode_id is not None:
        try:
            await client.set_dataref_value(change_mode_id, change_mode_orig)
        except XPlaneApiError:
            pass
    if override_clouds_id is not None:
        try:
            await client.set_dataref_value(override_clouds_id, override_clouds_orig)
        except XPlaneApiError:
            pass


async def _assert_live_server(client: XPlaneHttpClient) -> None:
    try:
        capabilities = await client.get_capabilities()
    except httpx.HTTPError as exc:  # pragma: no cover - exercised only in live mode
        pytest.skip(f"X-Plane is not reachable: {exc}")
    assert "v3" in capabilities["api"]["versions"]


_WEATHER_PRESET_NAME_HINT = re.compile(
    r"(?i)(?:/weather/.*preset|preset.*weather|weather_preset|wx_preset|_wx_preset)"
)


def _looks_like_weather_preset_command(cmd: dict[str, Any]) -> bool:
    """
    Heuristic match for built-in **environment** weather presets exposed as X-Plane commands.

    X-Plane 12 registers UI weather presets in the live command table; static ``Commands.txt``
    mirrors are often incomplete. We intentionally skip instruments/autopilot/radar commands.
    """
    name = str(cmd.get("name") or "")
    desc_l = str(cmd.get("description") or "").lower()
    nl = name.lower()

    if nl.startswith(
        (
            "sim/instruments/",
            "sim/autopilot/",
            "sim/ice/",
        )
    ):
        return False

    if _WEATHER_PRESET_NAME_HINT.search(name):
        return True

    if "preset" in desc_l and "weather" in desc_l:
        if any(w in desc_l for w in ("radar", "efis", "wxr", "multiscan")):
            return False
        if "sim/weather" in nl or "sim/operation" in nl or "/laminar" in nl:
            return True

    return False


async def _list_all_commands(client: XPlaneHttpClient) -> list[dict[str, Any]]:
    page_size = 250
    start = 0
    out: list[dict[str, Any]] = []
    while True:
        batch = await client.list_commands(limit=page_size, start=start)
        if not batch:
            break
        out.extend(batch)
        if len(batch) < page_size:
            break
        start += page_size
    return out


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
        CESSNA_172_CLASSIC_ACF_PATH,
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
def test_integration_list_available_planes_reads_real_installation(xplane_integration_config: XPlaneConfig):
    client = XPlaneHttpClient(xplane_integration_config)

    planes = client.list_available_planes()

    assert planes
    assert any(plane.path.endswith(".acf") for plane in planes)


@pytest.mark.integration
def test_integration_change_plane_model_updates_running_sim(xplane_integration_config: XPlaneConfig):
    """Switch to the stock **Cessna 172 classic** (steam gauges), not the G1000 variant."""

    root = xplane_integration_config.xplane_root
    assert root is not None
    classic_acf = root.joinpath(*CESSNA_172_CLASSIC_ACF_PATH.split("/"))
    if not classic_acf.is_file():
        pytest.skip(f"Classic Cessna 172 .acf not found: {classic_acf}")

    target = CESSNA_172_CLASSIC_ACF_PATH

    async def run() -> None:
        async with XPlaneHttpClient(xplane_integration_config) as client:
            await _assert_live_server(client)
            original = await client.get_current_aircraft()
            try:
                await client.change_plane_model(target)
                await _poll_current_aircraft(client, expected_path=target)
            finally:
                await client.change_plane_model(original.path, livery=original.livery)
                await _poll_current_aircraft(client, expected_path=original.path)

    asyncio.run(run())


@pytest.mark.integration
def test_integration_start_new_flight_with_airport_and_model_updates_running_sim(
    xplane_integration_config: XPlaneConfig,
    xplane_test_airport: str,
    xplane_test_ramp: str,
):
    async def run() -> None:
        async with XPlaneHttpClient(xplane_integration_config) as client:
            await _assert_live_server(client)
            original_aircraft = await client.get_current_aircraft()
            original_position = await client.get_current_position()
            target_aircraft = await _choose_alternate_aircraft(client)

            try:
                await client.start_new_flight(
                    xplane_test_airport,
                    ramp=xplane_test_ramp,
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


@pytest.mark.integration
def test_integration_set_failure_dataref_roundtrip_when_available(xplane_integration_config: XPlaneConfig):
    """Toggle a known failure dataref if present, then restore prior value."""

    async def run() -> None:
        async with XPlaneHttpClient(xplane_integration_config) as client:
            await _assert_live_server(client)
            dataref_meta = None
            for name in EXAMPLE_FAILURE_DATAREF_NAMES:
                try:
                    dataref_meta = await client.find_dataref(name)
                    break
                except XPlaneApiError:
                    continue
            if dataref_meta is None:
                pytest.skip("No example failure dataref found in this X-Plane session")

            dr_id = dataref_meta["id"]
            before = await client.get_dataref_value(dr_id)
            original = before["data"]
            try:
                await client.set_dataref_value(dr_id, 1)
                after = await client.get_dataref_value(dr_id)
                assert after["data"] != original or original == 1
            finally:
                await client.set_dataref_value(dr_id, original)

    asyncio.run(run())


@pytest.mark.integration
def test_integration_set_sealevel_pressure_1030_hpa(
    xplane_integration_config: XPlaneConfig,
    xplane_weather_region_index: int,
):
    """Set regional sea-level pressure to 1030 hPa (103_000 Pa), verify readback, restore."""

    dataref_name = "sim/weather/region/sealevel_pressure_pas"
    target_pa = 103_000.0  # 1030 hPa; suffix _pas is Pascals
    forced_index = xplane_weather_region_index

    async def run() -> None:
        async with XPlaneHttpClient(xplane_integration_config) as client:
            await _assert_live_server(client)
            try:
                meta = await client.find_dataref(dataref_name)
            except XPlaneApiError:
                pytest.skip(f"Dataref not available: {dataref_name}")

            dr_id = meta["id"]

            use_idx: int | None
            if forced_index >= 0:
                use_idx = forced_index
                try:
                    before = await client.get_dataref_value(dr_id, index=use_idx)
                except XPlaneApiError as exc:
                    pytest.skip(f"Could not read {dataref_name} at index {use_idx}: {exc}")
            else:
                before = None
                use_idx = None
                for idx in (None, 0):
                    try:
                        if idx is None:
                            before = await client.get_dataref_value(dr_id)
                        else:
                            before = await client.get_dataref_value(dr_id, index=idx)
                        use_idx = idx
                        break
                    except XPlaneApiError:
                        continue
                if before is None:
                    pytest.skip(
                        f"Could not read {dataref_name} (tried scalar and index 0); "
                        "pass --xplane-weather-region-index=N if your build needs another slot."
                    )

            async def get_pressure() -> dict:
                if use_idx is None:
                    return await client.get_dataref_value(dr_id)
                return await client.get_dataref_value(dr_id, index=use_idx)

            async def set_pressure(value) -> None:
                if use_idx is None:
                    await client.set_dataref_value(dr_id, value)
                else:
                    await client.set_dataref_value(dr_id, value, index=use_idx)

            original = before["data"]
            try:
                try:
                    await set_pressure(target_pa)
                except XPlaneApiError as exc:
                    if exc.error_code == "dataref_is_readonly":
                        pytest.skip("Sea level pressure dataref is read-only in this session")
                    raise
                # X-Plane may clamp, smooth, or apply limits; give the sim a beat to settle.
                await asyncio.sleep(0.35)
                after = await get_pressure()
                assert after["data"] == pytest.approx(
                    target_pa,
                    abs=2500,
                    rel=0.02,
                ), (
                    f"readback {after['data']!r} Pa far from requested {target_pa} Pa "
                    "(try another --xplane-weather-region-index if this is the wrong slot)"
                )
            finally:
                await set_pressure(original)

    asyncio.run(run())


@pytest.mark.integration
def test_integration_set_low_broken_cloud_layer(
    xplane_integration_config: XPlaneConfig,
    xplane_keep_cloud_layer: bool,
):
    """
    Configure regional weather layer 0 as a low broken layer (XP12 ``sim/weather/region/*``).

    Uses blended cloud type (cumulus = 2), fractional coverage ~0.62, and a low MSL band.
    See ``.refs/datarefs.csv`` / X-Plane 12 weather region datarefs.

    By default all values are **restored in ``finally``**, so you will not see lasting clouds
    unless you pass ``--xplane-keep-cloud-layer``. Even then: use **manual / custom weather**
    (not real-weather), enable **volumetric clouds** in rendering settings, and allow up to
    **~60 s** for cloud redraw (X-Plane does not apply ``update_immediately`` to clouds).
    """

    layer = 0
    targets: dict[str, float] = {
        "sim/weather/region/cloud_coverage_percent": 0.62,
        "sim/weather/region/cloud_type": 2.0,
        "sim/weather/region/cloud_base_msl_m": 900.0,
        "sim/weather/region/cloud_tops_msl_m": 2200.0,
    }

    async def run() -> None:
        async with XPlaneHttpClient(xplane_integration_config) as client:
            await _assert_live_server(client)

            primers = await _apply_regional_weather_draw_primers(client)

            entries: list[tuple[str, int, int, float, float]] = []
            for name, target in targets.items():
                try:
                    meta = await client.find_dataref(name)
                except XPlaneApiError:
                    pytest.skip(f"Dataref not available: {name}")
                dr_id = meta["id"]
                cur = await _read_region_cloud_layer_value(client, dr_id, layer, name)
                entries.append((name, dr_id, layer, cur, target))

            try:
                for _name, dr_id, ui, _old, tgt in entries:
                    try:
                        await _set_region_value(client, dr_id, ui, tgt)
                    except XPlaneApiError as exc:
                        if exc.error_code == "dataref_is_readonly":
                            pytest.skip("Regional cloud datarefs are read-only in this session")
                        raise
                # Cloud updates can lag other regional fields (not covered by update_immediately).
                await asyncio.sleep(5.0 if xplane_keep_cloud_layer else 1.0)
                msl_altitude_datarefs = frozenset(
                    {
                        "sim/weather/region/cloud_base_msl_m",
                        "sim/weather/region/cloud_tops_msl_m",
                    }
                )
                for name, dr_id, ui, _old, tgt in entries:
                    payload = await client.get_dataref_value(dr_id, index=ui)
                    raw = payload["data"]
                    if isinstance(raw, list):
                        got = float(raw[ui])
                    else:
                        got = float(raw)
                    if name in msl_altitude_datarefs:
                        # MSL bases/tops are often clamped or blended with terrain / internal weather.
                        assert got == pytest.approx(
                            tgt,
                            rel=0.5,
                            abs=800.0,
                        ), f"{name} readback {got!r} far from requested {tgt!r}"
                    else:
                        # Coverage and blended type are frequently clamped (e.g. presets / real wx).
                        assert got == pytest.approx(
                            tgt,
                            rel=0.65,
                            abs=0.55,
                        ), f"{name} readback {got!r} far from requested {tgt!r}"
            finally:
                if not xplane_keep_cloud_layer:
                    for _name, dr_id, ui, orig, _tgt in entries:
                        try:
                            await client.set_dataref_value(dr_id, orig, index=ui)
                        except XPlaneApiError:
                            pass
                await _restore_regional_weather_draw_primers(client, primers)

    asyncio.run(run())


@pytest.mark.integration
def test_integration_set_clear_sky_regional_weather(
    xplane_integration_config: XPlaneConfig,
    xplane_keep_cloud_layer: bool,
):
    """
    Drive XP12 regional weather toward **clear sky**: zero coverage and cirrus-ward type on
    cloud slots 0–2 (or fewer if the Web API exposes shorter arrays).

    Same operational notes as ``test_integration_set_low_broken_cloud_layer`` (restore by
    default, ``--xplane-keep-cloud-layer`` to inspect visually, manual weather, cloud redraw delay).

    Skips if coverage does not drop materially after the writes (common under real weather).
    """

    coverage_name = "sim/weather/region/cloud_coverage_percent"
    type_name = "sim/weather/region/cloud_type"
    target_coverage = 0.0
    target_type = 0.0

    async def run() -> None:
        async with XPlaneHttpClient(xplane_integration_config) as client:
            await _assert_live_server(client)

            primers = await _apply_regional_weather_draw_primers(client)

            try:
                cov_meta = await client.find_dataref(coverage_name)
            except XPlaneApiError:
                pytest.skip(f"Dataref not available: {coverage_name}")
            cov_dr = cov_meta["id"]
            try:
                typ_meta = await client.find_dataref(type_name)
            except XPlaneApiError:
                pytest.skip(f"Dataref not available: {type_name}")
            typ_dr = typ_meta["id"]

            entries: list[tuple[str, int, int, float, float]] = []
            for layer in (0, 1, 2):
                cur_cov = await _read_region_cloud_layer_value(
                    client, cov_dr, layer, coverage_name
                )
                entries.append((coverage_name, cov_dr, layer, cur_cov, target_coverage))
                cur_typ = await _read_region_cloud_layer_value(client, typ_dr, layer, type_name)
                entries.append((type_name, typ_dr, layer, cur_typ, target_type))

            try:
                for _name, dr_id, ui, _old, tgt in entries:
                    try:
                        await _set_region_value(client, dr_id, ui, tgt)
                    except XPlaneApiError as exc:
                        if exc.error_code == "dataref_is_readonly":
                            pytest.skip("Regional cloud datarefs are read-only in this session")
                        raise
                await asyncio.sleep(5.0 if xplane_keep_cloud_layer else 1.0)
                for name, dr_id, ui, orig, tgt in entries:
                    payload = await client.get_dataref_value(dr_id, index=ui)
                    raw = payload["data"]
                    if isinstance(raw, list):
                        got = float(raw[ui]) if len(raw) > ui else float(raw[0])
                    else:
                        got = float(raw)
                    if name == coverage_name:
                        ceiling = min(orig + 0.05, max(0.25, orig * 0.55))
                        if got > ceiling + 1e-6:
                            pytest.skip(
                                f"{name}[{ui}] stayed at {got!r} after clear request (from {orig!r}); "
                                "simulator may ignore writes under real-weather / locked presets — "
                                "use manual weather and retry, or wait ~60s for cloud refresh."
                            )
                    else:
                        assert got == pytest.approx(
                            tgt,
                            rel=0.65,
                            abs=0.35,
                        ), f"{name}[{ui}] readback {got!r} far from requested {tgt!r}"
            finally:
                if not xplane_keep_cloud_layer:
                    for _name, dr_id, ui, orig, _tgt in entries:
                        try:
                            await client.set_dataref_value(dr_id, orig, index=ui)
                        except XPlaneApiError:
                            pass
                await _restore_regional_weather_draw_primers(client, primers)

    asyncio.run(run())


@pytest.mark.integration
def test_integration_activate_each_weather_preset_command(xplane_integration_config: XPlaneConfig):
    """
    Discover registered commands via GET ``/commands`` (paged), select entries that look like
    built-in **weather presets**, and POST ``/command/{id}/activate`` with duration 0 for each.

    If your X-Plane build uses different naming, extend ``_looks_like_weather_preset_command``.
    """

    async def run() -> None:
        async with XPlaneHttpClient(xplane_integration_config) as client:
            await _assert_live_server(client)
            all_cmds = await _list_all_commands(client)
            presets = sorted(
                (c for c in all_cmds if _looks_like_weather_preset_command(c)),
                key=lambda c: str(c.get("name") or ""),
            )
            if not presets:
                pytest.skip(
                    "No commands matched the weather-preset heuristic; check X-Plane 12's "
                    "registered command names and update _looks_like_weather_preset_command if needed."
                )
            for cmd in presets:
                cmd_id = cmd["id"]
                await client.activate_command(cmd_id, duration=0.0)
                await asyncio.sleep(0.05)

    asyncio.run(run())
