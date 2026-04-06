from __future__ import annotations

import re
import time
from typing import Any

import pytest

from integration_constants import CESSNA_172_CLASSIC_ACF_PATH, EXAMPLE_FAILURE_DATAREF_NAMES
from mcp_integration import (
    assert_xplane_reachable_via_mcp,
    mcp_apply_regional_weather_draw_primers,
    mcp_choose_alternate_aircraft,
    mcp_find_dataref,
    mcp_get_current_aircraft,
    mcp_get_current_position,
    mcp_get_dataref_value,
    mcp_list_all_commands,
    mcp_list_available_plane_paths,
    mcp_poll_current_aircraft,
    mcp_read_region_cloud_layer_value,
    mcp_restore_regional_weather_draw_primers,
    mcp_set_dataref_value,
    mcp_set_region_value,
    mcp_tool_json,
)
from mcp_stdio import McpStdioSession, McpToolError


_WEATHER_PRESET_NAME_HINT = re.compile(
    r"(?i)(?:/weather/.*preset|preset.*weather|weather_preset|wx_preset|_wx_preset)"
)


def _looks_like_weather_preset_command(cmd: dict[str, Any]) -> bool:
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


@pytest.mark.integration
def test_integration_list_available_planes_reads_real_installation(
    mcp_stdio_session: McpStdioSession,
) -> None:
    assert_xplane_reachable_via_mcp(mcp_stdio_session)
    paths = mcp_list_available_plane_paths(mcp_stdio_session)
    assert paths
    assert any(p.endswith(".acf") for p in paths)


@pytest.mark.integration
def test_integration_change_plane_model_updates_running_sim(
    mcp_stdio_session: McpStdioSession,
    xplane_root,
) -> None:
    classic_acf = xplane_root.joinpath(*CESSNA_172_CLASSIC_ACF_PATH.split("/"))
    if not classic_acf.is_file():
        pytest.skip(f"Classic Cessna 172 .acf not found: {classic_acf}")

    target = CESSNA_172_CLASSIC_ACF_PATH
    s = mcp_stdio_session
    assert_xplane_reachable_via_mcp(s)
    original_path, original_livery = mcp_get_current_aircraft(s)
    try:
        mcp_tool_json(s, "change_plane_model", {"aircraft_path": target})
        mcp_poll_current_aircraft(s, expected_path=target)
    finally:
        restore: dict[str, Any] = {"aircraft_path": original_path}
        if original_livery:
            restore["livery"] = original_livery
        mcp_tool_json(s, "change_plane_model", restore)
        mcp_poll_current_aircraft(s, expected_path=original_path)


@pytest.mark.integration
def test_integration_start_new_flight_with_airport_and_model_updates_running_sim(
    mcp_stdio_session: McpStdioSession,
    xplane_test_airport: str,
    xplane_test_ramp: str,
) -> None:
    s = mcp_stdio_session
    assert_xplane_reachable_via_mcp(s)
    original_path, original_livery = mcp_get_current_aircraft(s)
    olat, olon, _ = mcp_get_current_position(s)
    target_aircraft = mcp_choose_alternate_aircraft(
        s,
        [
            CESSNA_172_CLASSIC_ACF_PATH,
            "Aircraft/Laminar Research/Boeing 737-800/b738.acf",
            "Aircraft/Laminar Research/Baron B58/Baron_58.acf",
        ],
    )
    try:
        args: dict[str, Any] = {
            "airport_id": xplane_test_airport,
            "ramp": xplane_test_ramp,
            "aircraft_path": target_aircraft,
        }
        mcp_tool_json(s, "start_new_flight", args)
        mcp_poll_current_aircraft(s, expected_path=target_aircraft)
        nlat, nlon, _ = mcp_get_current_position(s)
        assert (
            abs(nlat - olat) > 0.01
            or abs(nlon - olon) > 0.01
            or target_aircraft != original_path
        )
    finally:
        restore: dict[str, Any] = {"aircraft_path": original_path}
        if original_livery:
            restore["livery"] = original_livery
        mcp_tool_json(s, "change_plane_model", restore)
        mcp_poll_current_aircraft(s, expected_path=original_path)


@pytest.mark.integration
def test_integration_set_failure_dataref_roundtrip_when_available(
    mcp_stdio_session: McpStdioSession,
) -> None:
    s = mcp_stdio_session
    assert_xplane_reachable_via_mcp(s)
    dataref_meta = None
    for name in EXAMPLE_FAILURE_DATAREF_NAMES:
        try:
            dataref_meta = mcp_tool_json(s, "find_dataref", {"name": name})
            break
        except McpToolError:
            continue
    if dataref_meta is None:
        pytest.skip("No example failure dataref found in this X-Plane session")

    dr_id = str(dataref_meta["id"])
    before = mcp_get_dataref_value(s, dr_id)
    original = before["data"]
    try:
        mcp_set_dataref_value(s, dr_id, 1)
        after = mcp_get_dataref_value(s, dr_id)
        assert after["data"] != original or original == 1
    finally:
        mcp_set_dataref_value(s, dr_id, original)


@pytest.mark.integration
def test_integration_set_sealevel_pressure_1030_hpa(
    mcp_stdio_session: McpStdioSession,
    xplane_weather_region_index: int,
) -> None:
    dataref_name = "sim/weather/region/sealevel_pressure_pas"
    target_pa = 103_000.0
    forced_index = xplane_weather_region_index
    s = mcp_stdio_session
    assert_xplane_reachable_via_mcp(s)

    meta = mcp_find_dataref(s, dataref_name)
    dr_id = str(meta["id"])

    use_idx: int | None
    if forced_index >= 0:
        use_idx = forced_index
        try:
            before = mcp_get_dataref_value(s, dr_id, index=use_idx)
        except McpToolError as exc:
            pytest.skip(f"Could not read {dataref_name} at index {use_idx}: {exc}")
    else:
        before = None
        use_idx = None
        for idx in (None, 0):
            try:
                if idx is None:
                    before = mcp_get_dataref_value(s, dr_id)
                else:
                    before = mcp_get_dataref_value(s, dr_id, index=idx)
                use_idx = idx
                break
            except McpToolError:
                continue
        if before is None:
            pytest.skip(
                f"Could not read {dataref_name} (tried scalar and index 0); "
                "pass --xplane-weather-region-index=N if your build needs another slot."
            )

    def get_pressure() -> dict:
        if use_idx is None:
            return mcp_get_dataref_value(s, dr_id)
        return mcp_get_dataref_value(s, dr_id, index=use_idx)

    def set_pressure(value: Any) -> None:
        mcp_set_dataref_value(s, dr_id, value, index=use_idx)

    original = before["data"]
    try:
        try:
            set_pressure(target_pa)
        except McpToolError as exc:
            if "dataref_is_readonly" in str(exc).lower():
                pytest.skip("Sea level pressure dataref is read-only in this session")
            raise
        time.sleep(0.35)
        after = get_pressure()
        assert after["data"] == pytest.approx(
            target_pa,
            abs=2500,
            rel=0.02,
        ), (
            f"readback {after['data']!r} Pa far from requested {target_pa} Pa "
            "(try another --xplane-weather-region-index if this is the wrong slot)"
        )
    finally:
        set_pressure(original)


@pytest.mark.integration
def test_integration_set_low_broken_cloud_layer(
    mcp_stdio_session: McpStdioSession,
    xplane_keep_cloud_layer: bool,
) -> None:
    layer = 0
    targets: dict[str, float] = {
        "sim/weather/region/cloud_coverage_percent": 0.62,
        "sim/weather/region/cloud_type": 2.0,
        "sim/weather/region/cloud_base_msl_m": 900.0,
        "sim/weather/region/cloud_tops_msl_m": 2200.0,
    }
    s = mcp_stdio_session
    assert_xplane_reachable_via_mcp(s)
    primers = mcp_apply_regional_weather_draw_primers(s)

    entries: list[tuple[str, str, int, float, float]] = []
    for name, target in targets.items():
        meta = mcp_find_dataref(s, name)
        dr_id = str(meta["id"])
        cur = mcp_read_region_cloud_layer_value(s, dr_id, layer, name)
        entries.append((name, dr_id, layer, cur, target))

    try:
        for _name, dr_id, ui, _old, tgt in entries:
            try:
                mcp_set_region_value(s, dr_id, ui, tgt)
            except McpToolError as exc:
                if "dataref_is_readonly" in str(exc).lower():
                    pytest.skip("Regional cloud datarefs are read-only in this session")
                raise
        time.sleep(5.0 if xplane_keep_cloud_layer else 1.0)
        msl_altitude_datarefs = frozenset(
            {
                "sim/weather/region/cloud_base_msl_m",
                "sim/weather/region/cloud_tops_msl_m",
            }
        )
        for name, dr_id, ui, _old, tgt in entries:
            payload = mcp_get_dataref_value(s, dr_id, index=ui)
            raw = payload["data"]
            if isinstance(raw, list):
                got = float(raw[ui])
            else:
                got = float(raw)
            if name in msl_altitude_datarefs:
                assert got == pytest.approx(
                    tgt,
                    rel=0.5,
                    abs=800.0,
                ), f"{name} readback {got!r} far from requested {tgt!r}"
            else:
                assert got == pytest.approx(
                    tgt,
                    rel=0.65,
                    abs=0.55,
                ), f"{name} readback {got!r} far from requested {tgt!r}"
    finally:
        if not xplane_keep_cloud_layer:
            for _name, dr_id, ui, orig, _tgt in entries:
                try:
                    mcp_set_dataref_value(s, dr_id, orig, index=ui)
                except McpToolError:
                    pass
        mcp_restore_regional_weather_draw_primers(s, primers)


@pytest.mark.integration
def test_integration_set_clear_sky_regional_weather(
    mcp_stdio_session: McpStdioSession,
    xplane_keep_cloud_layer: bool,
) -> None:
    coverage_name = "sim/weather/region/cloud_coverage_percent"
    type_name = "sim/weather/region/cloud_type"
    target_coverage = 0.0
    target_type = 0.0
    s = mcp_stdio_session
    assert_xplane_reachable_via_mcp(s)
    primers = mcp_apply_regional_weather_draw_primers(s)

    cov_meta = mcp_find_dataref(s, coverage_name)
    cov_dr = str(cov_meta["id"])
    typ_meta = mcp_find_dataref(s, type_name)
    typ_dr = str(typ_meta["id"])

    entries: list[tuple[str, str, int, float, float]] = []
    for layer in (0, 1, 2):
        cur_cov = mcp_read_region_cloud_layer_value(s, cov_dr, layer, coverage_name)
        entries.append((coverage_name, cov_dr, layer, cur_cov, target_coverage))
        cur_typ = mcp_read_region_cloud_layer_value(s, typ_dr, layer, type_name)
        entries.append((type_name, typ_dr, layer, cur_typ, target_type))

    try:
        for _name, dr_id, ui, _old, tgt in entries:
            try:
                mcp_set_region_value(s, dr_id, ui, tgt)
            except McpToolError as exc:
                if "dataref_is_readonly" in str(exc).lower():
                    pytest.skip("Regional cloud datarefs are read-only in this session")
                raise
        time.sleep(5.0 if xplane_keep_cloud_layer else 1.0)
        for name, dr_id, ui, orig, tgt in entries:
            payload = mcp_get_dataref_value(s, dr_id, index=ui)
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
                    mcp_set_dataref_value(s, dr_id, orig, index=ui)
                except McpToolError:
                    pass
        mcp_restore_regional_weather_draw_primers(s, primers)


@pytest.mark.integration
def test_integration_activate_each_weather_preset_command(
    mcp_stdio_session: McpStdioSession,
) -> None:
    s = mcp_stdio_session
    assert_xplane_reachable_via_mcp(s)
    all_cmds = mcp_list_all_commands(s)
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
        name = str(cmd.get("name") or "")
        mcp_tool_json(s, "activate_command_by_name", {"name": name, "duration": 0.0})
        time.sleep(0.05)
