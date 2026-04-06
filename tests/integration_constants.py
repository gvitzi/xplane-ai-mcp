"""Constants shared by X-Plane MCP integration tests."""

from __future__ import annotations

# Stock XP12: steam-gauge / "classic" 172 — not ``Cessna_172SP_G1000.acf``.
CESSNA_172_CLASSIC_ACF_PATH = "Aircraft/Laminar Research/Cessna 172 SP/Cessna_172SP.acf"

EXAMPLE_FAILURE_DATAREF_NAMES: tuple[str, ...] = (
    "sim/operation/failures/rel_generators_gen_1",
    "sim/operation/failures/rel_battery_starter",
    "sim/operation/failures/rel_engfai0",
)
