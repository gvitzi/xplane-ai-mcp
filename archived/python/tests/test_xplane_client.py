import asyncio
import json
import logging
from pathlib import Path

import httpx
import pytest

from xplane_mcp.mcp_server import XPlaneMCPServer
from xplane_mcp.xplane_client import (
    XPlaneAircraft,
    XPlaneAircraftModel,
    XPlaneApiError,
    XPlaneConfig,
    XPlaneHttpClient,
    XPlanePosition,
    XPlaneWebSocketClient,
    _decode_dataref_data,
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


def test_get_current_aircraft_decodes_path_and_livery():
    responses = {
        "/api/v3/datarefs?filter%5Bname%5D=sim%2Faircraft%2Fview%2Facf_relative_path&fields=id%2Cname%2Cvalue_type":
            {"data": [{"id": 101, "name": "sim/aircraft/view/acf_relative_path", "value_type": "data"}]},
        "/api/v3/datarefs?filter%5Bname%5D=sim%2Faircraft%2Fview%2Facf_livery_path&fields=id%2Cname%2Cvalue_type":
            {"data": [{"id": 102, "name": "sim/aircraft/view/acf_livery_path", "value_type": "data"}]},
        "/api/v3/datarefs/101/value":
            {"data": "QWlyY3JhZnQvTGFtaW5hciBSZXNlYXJjaC9Cb2VpbmcgNzM3LTgwMC9iNzM4LmFjZg=="},
        "/api/v3/datarefs/102/value":
            {"data": "b2xkX3N0eWxl"},
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        key = str(request.url).replace("http://example", "")
        return httpx.Response(200, json=responses[key])

    async def run() -> XPlaneAircraft:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://example/api/v3") as client:
            api = XPlaneHttpClient(XPlaneConfig(), client=client)
            return await api.get_current_aircraft()

    aircraft = asyncio.run(run())
    assert aircraft.path == "Aircraft/Laminar Research/Boeing 737-800/b738.acf"
    assert aircraft.livery == "old_style"


def test_move_plane_to_airport_uses_current_aircraft():
    expected_body = {
        "data": {
            "ramp_start": {"airport_id": "EDDB", "ramp": "GATE 01"},
            "aircraft": {
                "path": "Aircraft/Laminar Research/Boeing 737-800/b738.acf",
                "livery": "old_style",
            },
        }
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v3/flight":
            assert json.loads(request.content) == expected_body
            return httpx.Response(200, content=b"")

        if request.url.params.get("filter[name]") == "sim/aircraft/view/acf_relative_path":
            return httpx.Response(
                200,
                json={"data": [{"id": 101, "name": "sim/aircraft/view/acf_relative_path", "value_type": "data"}]},
            )
        if request.url.params.get("filter[name]") == "sim/aircraft/view/acf_livery_path":
            return httpx.Response(
                200,
                json={"data": [{"id": 102, "name": "sim/aircraft/view/acf_livery_path", "value_type": "data"}]},
            )
        if request.url.path == "/api/v3/datarefs/101/value":
            return httpx.Response(
                200,
                json={"data": "QWlyY3JhZnQvTGFtaW5hciBSZXNlYXJjaC9Cb2VpbmcgNzM3LTgwMC9iNzM4LmFjZg=="},
            )
        if request.url.path == "/api/v3/datarefs/102/value":
            return httpx.Response(200, json={"data": "b2xkX3N0eWxl"})
        raise AssertionError(f"Unexpected request: {request.url}")

    async def run() -> dict:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://example/api/v3") as client:
            api = XPlaneHttpClient(XPlaneConfig(), client=client)
            return await api.move_plane_to_airport("eddb", ramp="GATE 01")

    payload = asyncio.run(run())
    assert payload == {"data": None}


def test_start_new_flight_uses_explicit_aircraft_when_provided():
    expected_body = {
        "data": {
            "ramp_start": {"airport_id": "EDDB", "ramp": "GATE 01"},
            "aircraft": {
                "path": "Aircraft/Laminar Research/Cessna 172 SP/Cessna_172SP.acf",
                "livery": "default",
            },
        }
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/flight"
        assert json.loads(request.content) == expected_body
        return httpx.Response(200, content=b"")

    async def run() -> dict:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://example/api/v3") as client:
            api = XPlaneHttpClient(XPlaneConfig(), client=client)
            return await api.start_new_flight(
                "EDDB",
                ramp="GATE 01",
                aircraft_path="Aircraft/Laminar Research/Cessna 172 SP/Cessna_172SP.acf",
                livery="default",
            )

    payload = asyncio.run(run())
    assert payload == {"data": None}


def test_change_plane_model_uses_current_position():
    expected_body = {
        "data": {
            "lle_ground_start": {
                "latitude": 52.3667,
                "longitude": 13.5033,
                "heading_true": 92.0,
            },
            "aircraft": {
                "path": "Aircraft/Laminar Research/Cessna 172 SP/Cessna_172SP.acf",
                "livery": "default",
            },
        }
    }

    dataref_ids = {
        "sim/flightmodel/position/latitude": 201,
        "sim/flightmodel/position/longitude": 202,
        "sim/flightmodel/position/true_psi": 203,
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v3/flight":
            assert json.loads(request.content) == expected_body
            return httpx.Response(200, content=b"")

        name = request.url.params.get("filter[name]")
        if name in dataref_ids:
            return httpx.Response(
                200,
                json={"data": [{"id": dataref_ids[name], "name": name, "value_type": "float"}]},
            )
        if request.url.path == "/api/v3/datarefs/201/value":
            return httpx.Response(200, json={"data": 52.3667})
        if request.url.path == "/api/v3/datarefs/202/value":
            return httpx.Response(200, json={"data": 13.5033})
        if request.url.path == "/api/v3/datarefs/203/value":
            return httpx.Response(200, json={"data": 92.0})
        raise AssertionError(f"Unexpected request: {request.url}")

    async def run() -> dict:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://example/api/v3") as client:
            api = XPlaneHttpClient(XPlaneConfig(), client=client)
            return await api.change_plane_model(
                "Aircraft/Laminar Research/Cessna 172 SP/Cessna_172SP.acf",
                livery="default",
            )

    payload = asyncio.run(run())
    assert payload == {"data": None}


def test_list_available_planes_reads_acf_files(tmp_path: Path):
    aircraft_dir = tmp_path / "Aircraft" / "Laminar Research" / "Boeing 737-800"
    aircraft_dir.mkdir(parents=True)
    (aircraft_dir / "b738.acf").write_text("acf", encoding="utf-8")
    second_dir = tmp_path / "Aircraft" / "Laminar Research" / "Cessna 172 SP"
    second_dir.mkdir(parents=True)
    (second_dir / "Cessna_172SP.acf").write_text("acf", encoding="utf-8")

    client = XPlaneHttpClient(XPlaneConfig(xplane_root=tmp_path))

    planes = client.list_available_planes()

    assert planes == [
        XPlaneAircraftModel(
            name="b738",
            path="Aircraft/Laminar Research/Boeing 737-800/b738.acf",
        ),
        XPlaneAircraftModel(
            name="Cessna 172SP",
            path="Aircraft/Laminar Research/Cessna 172 SP/Cessna_172SP.acf",
        ),
    ]


def test_list_available_planes_empty_without_xplane_root_logs_warning(caplog: pytest.LogCaptureFixture):
    caplog.set_level(logging.WARNING, logger="xplane_mcp.xplane_client")
    client = XPlaneHttpClient(XPlaneConfig())

    assert client.list_available_planes() == []
    assert any("xplane_root" in r.getMessage().lower() for r in caplog.records)


def test_set_dataref_value_sends_patch_with_json_body():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/datarefs/42/value"
        assert request.method == "PATCH"
        assert json.loads(request.content) == {"data": 3}
        return httpx.Response(200, content=b"")

    async def run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://example/api/v3") as client:
            api = XPlaneHttpClient(XPlaneConfig(), client=client)
            await api.set_dataref_value(42, 3)

    asyncio.run(run())


def test_set_dataref_value_with_array_index():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/datarefs/7/value"
        assert request.url.params["index"] == "2"
        assert json.loads(request.content) == {"data": 99}
        return httpx.Response(200, content=b"")

    async def run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://example/api/v3") as client:
            api = XPlaneHttpClient(XPlaneConfig(), client=client)
            await api.set_dataref_value(7, 99, index=2)

    asyncio.run(run())


def test_get_dataref_value_with_array_index():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/datarefs/7/value"
        assert request.url.params["index"] == "2"
        return httpx.Response(200, json={"data": 1.25})

    async def run() -> dict:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://example/api/v3") as client:
            api = XPlaneHttpClient(XPlaneConfig(), client=client)
            return await api.get_dataref_value(7, index=2)

    payload = asyncio.run(run())
    assert payload["data"] == 1.25


def test_set_dataref_value_by_name_resolves_then_patches():
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v3/datarefs" and request.url.params.get("filter[name]") == "sim/fail/x":
            return httpx.Response(
                200,
                json={"data": [{"id": 5, "name": "sim/fail/x", "value_type": "int"}]},
            )
        if request.url.path == "/api/v3/datarefs/5/value" and request.method == "PATCH":
            assert json.loads(request.content) == {"data": 1}
            return httpx.Response(200, content=b"")
        raise AssertionError(f"Unexpected request: {request.url}")

    async def run() -> dict:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://example/api/v3") as client:
            api = XPlaneHttpClient(XPlaneConfig(), client=client)
            return await api.set_dataref_value_by_name("sim/fail/x", 1)

    meta = asyncio.run(run())
    assert meta["id"] == 5


def test_find_command_returns_first_match():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/commands"
        assert request.url.params["filter[name]"] == "sim/operation/pause_toggle"
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": 9001,
                        "name": "sim/operation/pause_toggle",
                        "description": "Pause",
                    }
                ]
            },
        )

    async def run() -> dict:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://example/api/v3") as client:
            api = XPlaneHttpClient(XPlaneConfig(), client=client)
            return await api.find_command("sim/operation/pause_toggle")

    cmd = asyncio.run(run())
    assert cmd["id"] == 9001


def test_list_commands_returns_collection():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/commands"
        assert request.url.params["limit"] == "5"
        return httpx.Response(
            200,
            json={"data": [{"id": 1, "name": "sim/test/cmd", "description": "d"}]},
        )

    async def run() -> list[dict]:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://example/api/v3") as client:
            api = XPlaneHttpClient(XPlaneConfig(), client=client)
            return await api.list_commands(limit=5)

    cmds = asyncio.run(run())
    assert cmds[0]["name"] == "sim/test/cmd"


def test_activate_command_posts_duration():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/command/88/activate"
        assert json.loads(request.content) == {"duration": 0.0}
        return httpx.Response(200, content=b"")

    async def run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://example/api/v3") as client:
            api = XPlaneHttpClient(XPlaneConfig(), client=client)
            await api.activate_command(88, duration=0.0)

    asyncio.run(run())


def test_activate_command_by_name_resolves_then_posts():
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v3/commands":
            return httpx.Response(
                200,
                json={"data": [{"id": 3, "name": "sim/operation/pause_toggle", "description": ""}]},
            )
        if request.url.path == "/api/v3/command/3/activate":
            assert json.loads(request.content) == {"duration": 0.5}
            return httpx.Response(200, content=b"")
        raise AssertionError(f"Unexpected request: {request.url}")

    async def run() -> dict:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://example/api/v3") as client:
            api = XPlaneHttpClient(XPlaneConfig(), client=client)
            return await api.activate_command_by_name("sim/operation/pause_toggle", duration=0.5)

    meta = asyncio.run(run())
    assert meta["id"] == 3


def test_set_dataref_readonly_returns_api_error():
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={"error_code": "dataref_is_readonly", "error_message": "read only"},
        )

    async def run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://example/api/v3") as client:
            api = XPlaneHttpClient(XPlaneConfig(), client=client)
            await api.set_dataref_value(1, 0)

    with pytest.raises(XPlaneApiError) as exc:
        asyncio.run(run())
    assert exc.value.error_code == "dataref_is_readonly"


def test_get_current_position_reads_lat_lon_and_heading():
    dataref_ids = {
        "sim/flightmodel/position/latitude": 201,
        "sim/flightmodel/position/longitude": 202,
        "sim/flightmodel/position/true_psi": 203,
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        name = request.url.params.get("filter[name]")
        if name in dataref_ids:
            return httpx.Response(
                200,
                json={"data": [{"id": dataref_ids[name], "name": name, "value_type": "float"}]},
            )
        if request.url.path == "/api/v3/datarefs/201/value":
            return httpx.Response(200, json={"data": 52.3667})
        if request.url.path == "/api/v3/datarefs/202/value":
            return httpx.Response(200, json={"data": 13.5033})
        if request.url.path == "/api/v3/datarefs/203/value":
            return httpx.Response(200, json={"data": 92.0})
        raise AssertionError(f"Unexpected request: {request.url}")

    async def run() -> XPlanePosition:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="http://example/api/v3") as client:
            api = XPlaneHttpClient(XPlaneConfig(), client=client)
            return await api.get_current_position()

    position = asyncio.run(run())
    assert position == XPlanePosition(latitude=52.3667, longitude=13.5033, heading_true=92.0)


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


def test_decode_dataref_data_handles_empty_value():
    assert _decode_dataref_data("") == ""


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


def test_mcp_server_moves_plane_to_airport():
    class FakeHttpClient:
        async def move_plane_to_airport(self, airport_id, ramp="A1"):
            return {"data": {"airport_id": airport_id, "ramp": ramp}}

    async def run():
        server = XPlaneMCPServer(FakeHttpClient())
        return await server.move_plane_to_airport("EDDB", ramp="A2")

    result = asyncio.run(run())
    assert result["data"]["airport_id"] == "EDDB"
    assert result["data"]["ramp"] == "A2"


def test_mcp_server_starts_new_flight_with_airport_and_model():
    class FakeHttpClient:
        async def start_new_flight(self, airport_id, ramp="A1", aircraft_path=None, livery=None):
            return {
                "data": {
                    "airport_id": airport_id,
                    "ramp": ramp,
                    "aircraft_path": aircraft_path,
                    "livery": livery,
                }
            }

    async def run():
        server = XPlaneMCPServer(FakeHttpClient())
        return await server.start_new_flight(
            "EDDB",
            ramp="GATE 01",
            aircraft_path="Aircraft/Laminar Research/Cessna 172 SP/Cessna_172SP.acf",
            livery="default",
        )

    result = asyncio.run(run())
    assert result["data"]["airport_id"] == "EDDB"
    assert result["data"]["aircraft_path"].endswith("Cessna_172SP.acf")
    assert result["data"]["livery"] == "default"


def test_mcp_server_lists_available_planes():
    class FakeHttpClient:
        def list_available_planes(self):
            return [XPlaneAircraftModel(name="b738", path="Aircraft/Laminar Research/Boeing 737-800/b738.acf")]

    server = XPlaneMCPServer(FakeHttpClient())
    planes = server.list_available_planes()

    assert planes[0].path.endswith("b738.acf")


def test_mcp_server_changes_plane_model():
    class FakeHttpClient:
        async def change_plane_model(self, aircraft_path, livery=None):
            return {"data": {"path": aircraft_path, "livery": livery}}

    async def run():
        server = XPlaneMCPServer(FakeHttpClient())
        return await server.change_plane_model("Aircraft/Laminar Research/Cessna 172 SP/Cessna_172SP.acf", livery="default")

    result = asyncio.run(run())
    assert result["data"]["path"].endswith("Cessna_172SP.acf")
    assert result["data"]["livery"] == "default"


def test_mcp_server_set_failure_dataref_delegates_to_http():
    class FakeHttpClient:
        async def set_dataref_value_by_name(self, name, value, index=None):
            assert name == "sim/operation/failures/rel_test"
            assert value == 2
            assert index is None
            return {"id": 9, "name": name, "value_type": "int"}

    async def run():
        server = XPlaneMCPServer(FakeHttpClient())
        return await server.set_failure_dataref("sim/operation/failures/rel_test", 2)

    meta = asyncio.run(run())
    assert meta["id"] == 9


def test_mcp_server_set_dataref_by_name():
    class FakeHttpClient:
        async def set_dataref_value_by_name(self, name, value, index=None):
            return {"id": 1, "name": name, "value_type": "float"}

    async def run():
        server = XPlaneMCPServer(FakeHttpClient())
        return await server.set_dataref_by_name("sim/custom/x", 1.5)

    meta = asyncio.run(run())
    assert meta["name"] == "sim/custom/x"


def test_mcp_server_activate_command_by_name():
    class FakeHttpClient:
        async def activate_command_by_name(self, name, duration=0.0):
            return {"id": 2, "name": name}

    async def run():
        server = XPlaneMCPServer(FakeHttpClient())
        return await server.activate_command_by_name("sim/operation/pause_toggle", duration=0.0)

    meta = asyncio.run(run())
    assert meta["id"] == 2
