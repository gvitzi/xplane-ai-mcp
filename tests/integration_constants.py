"""Constants shared by X-Plane MCP integration tests."""

from __future__ import annotations

# Laminar stock .acf paths (relative to X-Plane root) used by flight tests and stock-aircraft catalog checks.
C172_STOCK_ACF_PATH = "Aircraft/Laminar Research/Cessna 172 SP/Cessna_172SP.acf"
BARON_B58_ACF_PATH = "Aircraft/Laminar Research/Beechcraft Baron 58/Baron_58.acf"

EXAMPLE_FAILURE_DATAREF_NAMES: tuple[str, ...] = (
    "sim/operation/failures/rel_generators_gen_1",
    "sim/operation/failures/rel_battery_starter",
    "sim/operation/failures/rel_engfai0",
)
