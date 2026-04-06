"""Aircraft failure / malfunction datarefs (X-Plane Web API).

Writable failure state is usually exposed under ``sim/operation/failures/...``.
Values are aircraft- and dataref-specific (often integer enums: off / fail / stuck).

Use :meth:`xplane_mcp.xplane_client.XPlaneHttpClient.set_dataref_value_by_name` or
:class:`xplane_mcp.mcp_server.XPlaneMCPServer.set_failure_dataref` after resolving
exact names in the Dataref browser or X-Plane documentation for your aircraft.
"""

from __future__ import annotations

# Prefix for many built-in failure datarefs (not guaranteed for all add-on aircraft).
FAILURE_DATAREF_PREFIX: str = "sim/operation/failures/"

# Example exact names useful for integration tests or documentation (may vary by XP version).
EXAMPLE_FAILURE_DATAREF_NAMES: tuple[str, ...] = (
    "sim/operation/failures/rel_generators_gen_1",
    "sim/operation/failures/rel_battery_starter",
    "sim/operation/failures/rel_engfai0",
)
