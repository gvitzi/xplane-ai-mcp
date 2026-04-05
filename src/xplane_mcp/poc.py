from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import httpx

from .mcp_server import XPlaneMCPServer
from .xplane_client import XPlaneConfig, XPlaneHttpClient, XPlaneWebSocketClient


DEFAULT_DATAREF = "sim/flightmodel/position/latitude"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Phase 0 PoC for X-Plane 12 local Web API connectivity."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8086)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument(
        "--dataref",
        default=DEFAULT_DATAREF,
        help="Preferred dataref name. If unavailable, the PoC falls back to the first listed dataref.",
    )
    parser.add_argument(
        "--flight-json",
        help="Path to a JSON file containing the POST /flight data object.",
    )
    parser.add_argument(
        "--skip-flight",
        action="store_true",
        help="Do not attempt POST /flight during the PoC run.",
    )
    return parser


async def run_poc(args: argparse.Namespace) -> int:
    config = XPlaneConfig(host=args.host, port=args.port, timeout=args.timeout)

    async with XPlaneHttpClient(config) as http_client:
        websocket_client = XPlaneWebSocketClient(config)
        server = XPlaneMCPServer(http_client, websocket_client)

        capabilities = await server.get_capabilities()
        print("Capabilities:")
        print(json.dumps(capabilities, indent=2, sort_keys=True))

        if not args.skip_flight and args.flight_json:
            flight_data = _load_json_file(args.flight_json)
            try:
                flight_result = await server.start_flight(flight_data)
                print("Flight started:")
                print(json.dumps(flight_result, indent=2, sort_keys=True))
                await asyncio.sleep(2)
            except httpx.TimeoutException:
                print(
                    "Flight request timed out while waiting for X-Plane to finish loading."
                )
                print("Continuing with state probing in case the simulator is still processing the new flight.")
                await asyncio.sleep(5)

        state = await server.get_state(args.dataref)
        print(f"Resolved dataref: {state.dataref['name']} (id={state.dataref['id']})")
        print("REST value:")
        print(json.dumps(state.rest_value, indent=2, sort_keys=True))
        if state.websocket_value is not None:
            print("WebSocket update:")
            print(json.dumps(state.websocket_value, indent=2, sort_keys=True))

        await websocket_client.close()
    return 0


def _load_json_file(path: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Flight payload must be a JSON object")
    return payload


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return asyncio.run(run_poc(args))


if __name__ == "__main__":
    raise SystemExit(main())
