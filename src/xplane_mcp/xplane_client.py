from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

try:
    import websockets
except ModuleNotFoundError:  # pragma: no cover - exercised in environments without deps installed
    websockets = None

WebSocketClientProtocol = Any


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8086
DEFAULT_TIMEOUT = 5.0


class XPlaneApiError(RuntimeError):
    """Raised when the X-Plane Web API returns an error response."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.payload = payload or {}


@dataclass(frozen=True)
class XPlaneConfig:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    timeout: float = DEFAULT_TIMEOUT

    @property
    def capabilities_url(self) -> str:
        return f"http://{self.host}:{self.port}/api/capabilities"

    @property
    def rest_base_url(self) -> str:
        return f"http://{self.host}:{self.port}/api/v3"

    @property
    def websocket_url(self) -> str:
        return f"ws://{self.host}:{self.port}/api/v3"


@dataclass(frozen=True)
class XPlaneAircraft:
    path: str
    livery: str | None = None


class XPlaneHttpClient:
    """Minimal async HTTP client for the X-Plane local Web API."""

    def __init__(
        self,
        config: XPlaneConfig | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config or XPlaneConfig()
        self._client = client or httpx.AsyncClient(
            base_url=self.config.rest_base_url,
            timeout=self.config.timeout,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        self._owns_client = client is None

    async def __aenter__(self) -> "XPlaneHttpClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def get_capabilities(self) -> dict[str, Any]:
        response = await self._client.get(self.config.capabilities_url)
        return self._parse_response(response)

    async def start_flight(self, flight_data: dict[str, Any]) -> dict[str, Any]:
        response = await self._client.post("/flight", json={"data": flight_data})
        return self._parse_response(response, allow_empty=True)

    async def patch_flight(self, flight_data: dict[str, Any]) -> dict[str, Any]:
        response = await self._client.patch("/flight", json={"data": flight_data})
        return self._parse_response(response, allow_empty=True)

    async def move_plane_to_airport(
        self,
        airport_id: str,
        *,
        ramp: str = "A1",
        aircraft: XPlaneAircraft | None = None,
    ) -> dict[str, Any]:
        if not airport_id:
            raise ValueError("airport_id is required")

        selected_aircraft = aircraft or await self.get_current_aircraft()
        flight_data = {
            "ramp_start": {
                "airport_id": airport_id.upper(),
                "ramp": ramp,
            },
            "aircraft": {
                "path": selected_aircraft.path,
            },
        }
        if selected_aircraft.livery:
            flight_data["aircraft"]["livery"] = selected_aircraft.livery
        return await self.start_flight(flight_data)

    async def find_dataref(self, name: str) -> dict[str, Any]:
        response = await self._client.get(
            "/datarefs",
            params={
                "filter[name]": name,
                "fields": "id,name,value_type",
            },
        )
        payload = self._parse_response(response)
        items = payload.get("data", [])
        if not items:
            raise XPlaneApiError(f"Dataref not found: {name}", payload=payload)
        return items[0]

    async def list_datarefs(
        self,
        *,
        limit: int = 10,
        start: int = 0,
    ) -> list[dict[str, Any]]:
        response = await self._client.get(
            "/datarefs",
            params={
                "limit": limit,
                "start": start,
                "fields": "id,name,value_type",
            },
        )
        payload = self._parse_response(response)
        data = payload.get("data", [])
        if not isinstance(data, list):
            raise XPlaneApiError("Expected datarefs list response", payload=payload)
        return data

    async def get_dataref_value(self, dataref_id: int | str) -> dict[str, Any]:
        response = await self._client.get(f"/datarefs/{dataref_id}/value")
        return self._parse_response(response)

    async def get_current_aircraft(self) -> XPlaneAircraft:
        path_dataref = await self.find_dataref("sim/aircraft/view/acf_relative_path")
        livery_dataref = await self.find_dataref("sim/aircraft/view/acf_livery_path")

        path_value = await self.get_dataref_value(path_dataref["id"])
        livery_value = await self.get_dataref_value(livery_dataref["id"])

        aircraft_path = _decode_dataref_data(path_value.get("data"))
        if not aircraft_path:
            raise XPlaneApiError("Current aircraft path is unavailable", payload=path_value)

        livery = _decode_dataref_data(livery_value.get("data")) or None
        return XPlaneAircraft(path=aircraft_path, livery=livery)

    @staticmethod
    def _parse_response(
        response: httpx.Response,
        *,
        allow_empty: bool = False,
    ) -> dict[str, Any]:
        if allow_empty and not response.content:
            if response.is_error:
                raise XPlaneApiError(
                    f"X-Plane API request failed with HTTP {response.status_code}",
                    status_code=response.status_code,
                )
            return {"data": None}
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise XPlaneApiError(
                f"Expected JSON response, got HTTP {response.status_code}",
                status_code=response.status_code,
            ) from exc

        if response.is_error:
            error = payload if isinstance(payload, dict) else {}
            raise XPlaneApiError(
                error.get("error_message")
                or f"X-Plane API request failed with HTTP {response.status_code}",
                status_code=response.status_code,
                error_code=error.get("error_code"),
                payload=payload if isinstance(payload, dict) else {},
            )
        if not isinstance(payload, dict):
            raise XPlaneApiError(
                "Expected top-level JSON object from X-Plane API",
                status_code=response.status_code,
            )
        return payload


class XPlaneWebSocketClient:
    """Minimal WebSocket client for X-Plane streaming requests."""

    def __init__(
        self,
        config: XPlaneConfig | None = None,
        *,
        websocket_factory: Any | None = None,
    ) -> None:
        self.config = config or XPlaneConfig()
        self._websocket_factory = websocket_factory
        if self._websocket_factory is None and websockets is not None:
            self._websocket_factory = websockets.connect
        self._connection: WebSocketClientProtocol | None = None
        self._req_id = 0

    async def __aenter__(self) -> "XPlaneWebSocketClient":
        await self.connect()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def connect(self) -> None:
        if self._connection is None:
            if self._websocket_factory is None:
                raise RuntimeError(
                    "websockets is not installed; run `pip install -e .` before using the WebSocket client"
                )
            self._connection = await self._websocket_factory(self.config.websocket_url)

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    async def subscribe_dataref(
        self,
        *,
        dataref_id: int | str,
    ) -> int:
        req_id = self._next_req_id()
        await self._send_json(
            {
                "req_id": req_id,
                "type": "dataref_subscribe_values",
                "params": {"datarefs": [{"id": dataref_id}]},
            }
        )
        return req_id

    async def receive_json(self) -> dict[str, Any]:
        if self._connection is None:
            raise RuntimeError("WebSocket is not connected")
        message = await self._connection.recv()
        if not isinstance(message, str):
            raise XPlaneApiError("Expected text WebSocket message")
        payload = json.loads(message)
        if not isinstance(payload, dict):
            raise XPlaneApiError("Expected JSON object WebSocket message")
        return payload

    async def iter_messages(self) -> AsyncIterator[dict[str, Any]]:
        while True:
            try:
                yield await self.receive_json()
            except Exception as exc:
                if websockets is not None and isinstance(exc, websockets.ConnectionClosed):
                    return
                raise

    async def _send_json(self, payload: dict[str, Any]) -> None:
        if self._connection is None:
            raise RuntimeError("WebSocket is not connected")
        await self._connection.send(json.dumps(payload))

    def _next_req_id(self) -> int:
        self._req_id += 1
        return self._req_id


async def wait_for_dataref_update(
    websocket: XPlaneWebSocketClient,
    *,
    dataref_id: int | str,
    timeout: float = 5.0,
) -> dict[str, Any]:
    """Wait for the first update mentioning the requested dataref."""

    async def _wait() -> dict[str, Any]:
        async for message in websocket.iter_messages():
            if _message_mentions_dataref(message, dataref_id):
                return message
        raise XPlaneApiError("WebSocket closed before receiving a dataref update")

    return await asyncio.wait_for(_wait(), timeout=timeout)


def _message_mentions_dataref(message: dict[str, Any], dataref_id: int | str) -> bool:
    data = message.get("data", {})
    return str(dataref_id) in data


def _decode_dataref_data(value: Any) -> str:
    if value in (None, ""):
        return ""
    if not isinstance(value, str):
        raise XPlaneApiError("Expected base64 string for X-Plane dataref value")

    try:
        return base64.b64decode(value).decode("utf-8")
    except Exception as exc:  # pragma: no cover - defensive path
        raise XPlaneApiError("Failed to decode X-Plane dataref payload") from exc
