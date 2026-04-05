from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .xplane_client import (
    XPlaneHttpClient,
    XPlaneWebSocketClient,
    wait_for_dataref_update,
)


@dataclass
class XPlaneStateResult:
    dataref: dict[str, Any]
    rest_value: dict[str, Any]
    websocket_value: dict[str, Any] | None


class XPlaneMCPServer:
    """
    Thin MCP-facing service layer.

    This keeps the transport-specific HTTP/WebSocket logic in the X-Plane client
    and exposes higher-level operations for a future MCP server entrypoint.
    """

    def __init__(
        self,
        http_client: XPlaneHttpClient,
        websocket_client: XPlaneWebSocketClient | None = None,
    ) -> None:
        self._http = http_client
        self._websocket = websocket_client

    async def get_capabilities(self) -> dict[str, Any]:
        return await self._http.get_capabilities()

    async def start_flight(self, flight_data: dict[str, Any]) -> dict[str, Any]:
        return await self._http.start_flight(flight_data)

    async def move_plane_to_airport(
        self,
        airport_id: str,
        *,
        ramp: str = "A1",
    ) -> dict[str, Any]:
        return await self._http.move_plane_to_airport(airport_id, ramp=ramp)

    async def resolve_dataref(self, dataref_name: str | None) -> dict[str, Any]:
        if dataref_name:
            try:
                return await self._http.find_dataref(dataref_name)
            except Exception:
                pass

        datarefs = await self._http.list_datarefs(limit=1)
        if not datarefs:
            raise RuntimeError("X-Plane returned no datarefs for the current session")
        return datarefs[0]

    async def get_state(self, dataref_name: str) -> XPlaneStateResult:
        dataref = await self.resolve_dataref(dataref_name)
        rest_value = await self._http.get_dataref_value(dataref["id"])

        websocket_value: dict[str, Any] | None = None
        if self._websocket is not None:
            await self._websocket.connect()
            await self._websocket.subscribe_dataref(dataref_id=dataref["id"])
            websocket_value = await wait_for_dataref_update(
                self._websocket,
                dataref_id=dataref["id"],
            )

        return XPlaneStateResult(
            dataref=dataref,
            rest_value=rest_value,
            websocket_value=websocket_value,
        )
