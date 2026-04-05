"""MCP server and X-Plane Web API client (work in progress)."""

__version__ = "0.1.0"

from .mcp_server import XPlaneMCPServer
from .xplane_client import (
    XPlaneApiError,
    XPlaneHttpClient,
    XPlaneWebSocketClient,
)

__all__ = [
    "XPlaneApiError",
    "XPlaneHttpClient",
    "XPlaneMCPServer",
    "XPlaneWebSocketClient",
]
