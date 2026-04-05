"""MCP server and X-Plane Web API client (work in progress)."""

__version__ = "0.1.0"

from .mcp_server import XPlaneMCPServer
from .xplane_client import (
    XPlaneAircraft,
    XPlaneAircraftModel,
    XPlaneApiError,
    XPlaneHttpClient,
    XPlanePosition,
    XPlaneWebSocketClient,
)

__all__ = [
    "XPlaneAircraft",
    "XPlaneAircraftModel",
    "XPlaneApiError",
    "XPlaneHttpClient",
    "XPlaneMCPServer",
    "XPlanePosition",
    "XPlaneWebSocketClient",
]
