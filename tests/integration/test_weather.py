"""Integration tests for weather-related datarefs and UI weather presets."""

from __future__ import annotations

import time
from typing import Any

import pytest

from mcp_integration import (
    assert_xplane_reachable_via_mcp,
    mcp_apply_regional_weather_draw_primers,
    mcp_find_dataref,
    mcp_get_dataref_value,
    mcp_read_region_cloud_layer_value,
    mcp_set_dataref_value,
    mcp_set_region_value,
)
from mcp_stdio import McpStdioSession, McpToolError

# X-Plane 12: sim/weather/region/weather_preset (writable enum, see Resources/plugins/DataRefs.txt)
_WEATHER_PRESET_DATAREF = "sim/weather/region/weather_preset"

# Regional wind layer 0 — sim/weather/region/* arrays are m/s and degrees true (wind *from* direction).
_WIND_LAYER = 0
_WIND_SPEED = "sim/weather/region/wind_speed_msc"
_WIND_DIRECTION = "sim/weather/region/wind_direction_degt"
_SHEAR_SPEED = "sim/weather/region/shear_speed_msc"
_SHEAR_DIRECTION = "sim/weather/region/shear_direction_degt"
_UPDATE_WEATHER_IMMEDIATELY = "sim/weather/region/update_immediately"
_KT_TO_MS = 1852.0 / 3600.0


def _kts_to_ms(kts: float) -> float:
    return kts * _KT_TO_MS


def _set_regional_ground_wind(
    s: McpStdioSession,
    *,
    speed_kts: float,
    direction_deg: float,
    gust_kts: float | None = None,
) -> None:
    """Apply surface (layer 0) regional wind; leaves sim state changed.

    Gust envelope uses ``shear_speed_msc`` (delta in m/s); ``shear_direction_degt`` is always
    the same heading as ``wind_direction_degt`` (wind *from* that bearing).
    """
    assert_xplane_reachable_via_mcp(s)
    try:
        imm_meta = mcp_find_dataref(s, _UPDATE_WEATHER_IMMEDIATELY)
        mcp_set_dataref_value(s, str(imm_meta["id"]), 1)
    except McpToolError:
        pass

    wind_from_deg = float(direction_deg) % 360.0
    gust_from_deg = wind_from_deg
    speed_ms = _kts_to_ms(max(0.0, speed_kts))
    if gust_kts is not None and gust_kts > speed_kts:
        shear_ms = _kts_to_ms(gust_kts - speed_kts)
    else:
        shear_ms = 0.0

    for name, idx, value in (
        (_WIND_SPEED, _WIND_LAYER, speed_ms),
        (_WIND_DIRECTION, _WIND_LAYER, wind_from_deg),
        (_SHEAR_SPEED, _WIND_LAYER, shear_ms),
        (_SHEAR_DIRECTION, _WIND_LAYER, gust_from_deg),
    ):
        meta = mcp_find_dataref(s, name)
        dr_id = str(meta["id"])
        try:
            mcp_set_region_value(s, dr_id, idx, float(value))
        except McpToolError as exc:
            if "dataref_is_readonly" in str(exc).lower():
                pytest.skip(f"Regional wind dataref read-only: {name}")
            raise

    time.sleep(0.75)


def _read_regional_wind_layer0(s: McpStdioSession, dataref_name: str) -> float:
    meta = mcp_find_dataref(s, dataref_name)
    dr_id = str(meta["id"])
    payload = mcp_get_dataref_value(s, dr_id, index=_WIND_LAYER)
    raw = payload["data"]
    if isinstance(raw, list):
        if len(raw) > _WIND_LAYER:
            return float(raw[_WIND_LAYER])
        return float(raw[0])
    return float(raw)


def _apply_weather_preset(
    mcp_stdio_session: McpStdioSession,
    preset_index: int,
) -> None:
    """Set UI weather preset by index; leaves the sim on that preset when the test ends."""
    s = mcp_stdio_session
    assert_xplane_reachable_via_mcp(s)
    meta = mcp_find_dataref(s, _WEATHER_PRESET_DATAREF)
    dr_id = str(meta["id"])
    try:
        mcp_set_dataref_value(s, dr_id, float(preset_index))
    except McpToolError as exc:
        if "dataref_is_readonly" in str(exc).lower():
            pytest.skip("Weather preset dataref is read-only in this session")
        raise
    time.sleep(0.2)


@pytest.mark.integration
def test_set_sealevel_pressure_1030_hpa(
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


@pytest.mark.integration
def test_ground_wind_calm(mcp_stdio_session: McpStdioSession) -> None:
    _set_regional_ground_wind(mcp_stdio_session, speed_kts=0.0, direction_deg=0.0)
    s = mcp_stdio_session
    spd = _read_regional_wind_layer0(s, _WIND_SPEED)
    sh = _read_regional_wind_layer0(s, _SHEAR_SPEED)
    assert spd == pytest.approx(0.0, abs=2.5), f"calm wind readback {spd!r} m/s"
    assert sh == pytest.approx(0.0, abs=2.5), f"calm shear readback {sh!r} m/s"


@pytest.mark.integration
def test_ground_wind_15_gusting_25_from_300(mcp_stdio_session: McpStdioSession) -> None:
    _set_regional_ground_wind(
        mcp_stdio_session,
        speed_kts=15.0,
        direction_deg=300.0,
        gust_kts=25.0,
    )
    s = mcp_stdio_session
    spd = _read_regional_wind_layer0(s, _WIND_SPEED)
    sh = _read_regional_wind_layer0(s, _SHEAR_SPEED)
    direc = _read_regional_wind_layer0(s, _WIND_DIRECTION)
    shear_dir = _read_regional_wind_layer0(s, _SHEAR_DIRECTION)
    assert spd == pytest.approx(_kts_to_ms(15.0), abs=4.0, rel=0.35)
    assert sh == pytest.approx(_kts_to_ms(10.0), abs=4.0, rel=0.35)
    assert direc == pytest.approx(300.0, abs=12.0)
    assert shear_dir == pytest.approx(
        direc,
        abs=12.0,
    ), "gust (shear) direction must match steady wind direction"


@pytest.mark.integration
def test_ground_wind_40kt_from_150(mcp_stdio_session: McpStdioSession) -> None:
    _set_regional_ground_wind(
        mcp_stdio_session,
        speed_kts=40.0,
        direction_deg=150.0,
        gust_kts=None,
    )
    s = mcp_stdio_session
    spd = _read_regional_wind_layer0(s, _WIND_SPEED)
    sh = _read_regional_wind_layer0(s, _SHEAR_SPEED)
    direc = _read_regional_wind_layer0(s, _WIND_DIRECTION)
    assert spd == pytest.approx(_kts_to_ms(40.0), abs=5.0, rel=0.35)
    assert sh == pytest.approx(0.0, abs=3.5)
    assert direc == pytest.approx(150.0, abs=12.0)


@pytest.mark.integration
def test_set_low_broken_cloud_layer(
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
    mcp_apply_regional_weather_draw_primers(s)

    entries: list[tuple[str, str, int, float]] = []
    for name, target in targets.items():
        meta = mcp_find_dataref(s, name)
        dr_id = str(meta["id"])
        mcp_read_region_cloud_layer_value(s, dr_id, layer, name)
        entries.append((name, dr_id, layer, target))

    for _name, dr_id, ui, tgt in entries:
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
    for name, dr_id, ui, tgt in entries:
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


@pytest.mark.integration
def test_weather_preset_clear(mcp_stdio_session: McpStdioSession) -> None:
    _apply_weather_preset(mcp_stdio_session, 0)


@pytest.mark.integration
def test_weather_preset_vfr_few(mcp_stdio_session: McpStdioSession) -> None:
    _apply_weather_preset(mcp_stdio_session, 1)


@pytest.mark.integration
def test_weather_preset_vfr_scattered(mcp_stdio_session: McpStdioSession) -> None:
    _apply_weather_preset(mcp_stdio_session, 2)


@pytest.mark.integration
def test_weather_preset_vfr_broken(mcp_stdio_session: McpStdioSession) -> None:
    _apply_weather_preset(mcp_stdio_session, 3)


@pytest.mark.integration
def test_weather_preset_vfr_marginal(mcp_stdio_session: McpStdioSession) -> None:
    _apply_weather_preset(mcp_stdio_session, 4)


@pytest.mark.integration
def test_weather_preset_ifr_non_precision(mcp_stdio_session: McpStdioSession) -> None:
    _apply_weather_preset(mcp_stdio_session, 5)


@pytest.mark.integration
def test_weather_preset_ifr_precision(mcp_stdio_session: McpStdioSession) -> None:
    _apply_weather_preset(mcp_stdio_session, 6)


@pytest.mark.integration
def test_weather_preset_convective(mcp_stdio_session: McpStdioSession) -> None:
    _apply_weather_preset(mcp_stdio_session, 7)


@pytest.mark.integration
def test_weather_preset_large_cell_storms(mcp_stdio_session: McpStdioSession) -> None:
    _apply_weather_preset(mcp_stdio_session, 8)
