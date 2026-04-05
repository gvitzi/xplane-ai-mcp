import asyncio
import json

import httpx
import pytest

from xplane_mcp.mcp_server import XPlaneMCPServer
from xplane_mcp.xplane_client import (
    XPlaneApiError,
    XPlaneConfig,
    XPlaneHttpClient,
    XPlaneWebSocketClient,
    _message_mentions_dataref,
)


def test_get_capabilities_uses_unversioned_endpoint():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://127.0.0.1:8086/api/capabilities"
        return httpx.Response(200, json={"data": {"api_versions": ["v2", "v3"]}})

    async def run() -> dict:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://unused") as client:
            api = XPlaneHttpClient(XPlaneConfig(), client=client)
            return await api.get_capabilities()

    payload = asyncio.run(run())
    assert payload["data"]["api_versions"] == ["v2", "v3"]


def test_find_dataref_returns_first_exact_match():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/datarefs"
        assert request.url.params["filter[name]"] == "sim/test/value"
        return httpx.Response(
            200,
            json={"data": [{"id": 42, "name": "sim/test/value", "value_type": "float"}]},
        )

    async def run() -> dict:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://example/api/v3") as client:
            api = XPlaneHttpClient(XPlaneConfig(), client=client)
            return await api.find_dataref("sim/test/value")

    dataref = asyncio.run(run())
    assert dataref["id"] == 42


def test_list_datarefs_returns_collection():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/datarefs"
        assert request.url.params["limit"] == "1"
        return httpx.Response(
            200,
            json={"data": [{"id": 1, "name": "sim/test/first", "value_type": "int"}]},
        )

    async def run() -> list[dict]:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://example/api/v3") as client:
            api = XPlaneHttpClient(XPlaneConfig(), client=client)
            return await api.list_datarefs(limit=1)

    datarefs = asyncio.run(run())
    assert datarefs[0]["name"] == "sim/test/first"


def test_start_flight_wraps_payload_in_data_envelope():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/flight"
        body = json.loads(request.content)
        assert body == {"data": {"airport": "EDDB", "ramp": "A12"}}
        return httpx.Response(200, content=b"")

    async def run() -> dict:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://example/api/v3") as client:
            api = XPlaneHttpClient(XPlaneConfig(), client=client)
            return await api.start_flight({"airport": "EDDB", "ramp": "A12"})

    payload = asyncio.run(run())
    assert payload == {"data": None}


def test_api_error_surfaces_xplane_error_details():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={"error_code": "FORBIDDEN", "error_message": "Disabled"},
        )

    async def run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://example/api/v3") as client:
            api = XPlaneHttpClient(XPlaneConfig(), client=client)
            await api.get_dataref_value(12)

    with pytest.raises(XPlaneApiError) as exc:
        asyncio.run(run())
    assert exc.value.status_code == 403
    assert exc.value.error_code == "FORBIDDEN"


def test_message_mentions_dataref_matches_nested_id():
    message = {"type": "dataref_update_values", "data": {"77": 12.3}}
    assert _message_mentions_dataref(message, 77) is True
    assert _message_mentions_dataref(message, 99) is False


class FakeWebSocket:
    def __init__(self, incoming_messages: list[str]) -> None:
        self.incoming_messages = incoming_messages
        self.sent_messages: list[dict] = []
        self.closed = False

    async def send(self, message: str) -> None:
        self.sent_messages.append(json.loads(message))

    async def recv(self) -> str:
        return self.incoming_messages.pop(0)

    async def close(self) -> None:
        self.closed = True


def test_websocket_client_sends_subscribe_request():
    websocket = FakeWebSocket([])

    async def factory(_: str) -> FakeWebSocket:
        return websocket

    async def run() -> int:
        client = XPlaneWebSocketClient(websocket_factory=factory)
        await client.connect()
        req_id = await client.subscribe_dataref(dataref_id=55)
        await client.close()
        return req_id

    req_id = asyncio.run(run())
    assert req_id == 1
    assert websocket.closed is True
    assert websocket.sent_messages == [
        {
            "req_id": 1,
            "type": "dataref_subscribe_values",
            "params": {"datarefs": [{"id": 55}]},
        }
    ]


def test_mcp_server_uses_http_and_websocket_clients():
    class FakeHttpClient:
        async def get_capabilities(self):
            return {"data": {"api_versions": ["v3"]}}

        async def start_flight(self, flight_data):
            return {"data": flight_data}

        async def find_dataref(self, name):
            return {"id": 10, "name": name}

        async def list_datarefs(self, limit=10, start=0):
            return [{"id": 10, "name": "sim/test/value"}]

        async def get_dataref_value(self, _):
            return {"data": {"value": 1.23}}

    class FakeStreamingClient:
        def __init__(self):
            self.connected = False
            self.subscribed = []
            self.messages = [
                {"type": "dataref_update_values", "data": {"10": 1.24}}
            ]

        async def connect(self):
            self.connected = True

        async def subscribe_dataref(self, *, dataref_id):
            self.subscribed.append(dataref_id)
            return 1

        async def iter_messages(self):
            for message in self.messages:
                yield message

    async def run():
        server = XPlaneMCPServer(FakeHttpClient(), FakeStreamingClient())
        return await server.get_state("sim/test/value")

    state = asyncio.run(run())
    assert state.dataref["id"] == 10
    assert state.rest_value["data"]["value"] == 1.23
    assert state.websocket_value["data"]["10"] == 1.24
