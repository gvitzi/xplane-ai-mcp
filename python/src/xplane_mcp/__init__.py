"""X-Plane Web API client helpers used by repo-root integration tests."""

__version__ = "0.1.0"

from .failures import EXAMPLE_FAILURE_DATAREF_NAMES, FAILURE_DATAREF_PREFIX
from .xplane_client import (
    XPlaneAircraft,
    XPlaneAircraftModel,
    XPlaneApiError,
    XPlaneHttpClient,
    XPlanePosition,
    XPlaneWebSocketClient,
)

__all__ = [
    "EXAMPLE_FAILURE_DATAREF_NAMES",
    "FAILURE_DATAREF_PREFIX",
    "XPlaneAircraft",
    "XPlaneAircraftModel",
    "XPlaneApiError",
    "XPlaneHttpClient",
    "XPlanePosition",
    "XPlaneWebSocketClient",
]
