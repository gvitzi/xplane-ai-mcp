# MCP API overview

This document summarizes tools exposed by the **XPlaneMcp** stdio MCP server ([`src/XPlaneMcp.Server/XPlaneMcpTools.cs`](src/XPlaneMcp.Server/XPlaneMcpTools.cs)). Tool names are **snake_case** as seen by MCP clients. Full parameter schemas come from the server’s tool definitions at runtime.

## General MCP

API discovery, listing, and simulator commands.

| Tool | Description |
|------|-------------|
| `get_capabilities` | Reads X-Plane Web API capabilities (versions and server info). |
| `list_commands` | Pages through available simulator commands (`limit`, `start`). |
| `list_datarefs` | Pages through datarefs (`limit`, `start`). |
| `activate_command_by_name` | Activates an X-Plane command by exact name; optional `duration` in seconds (API max 10). |

## Flight operations

Starting or updating flights, airports, and aircraft.

| Tool | Description |
|------|-------------|
| `start_flight` | `POST /api/v3/flight` — `flight_json` is the inner API `data` object ([Flight Initialization API](https://developer.x-plane.com/article/flight-initialization-api/)). Put **`aircraft`** and **exactly one** of **`ramp_start`**, **`runway_start`**, **`lle_ground_start`**, **`lle_air_start`**, or **`boat_start`** as top-level keys in that JSON (same nested shapes as X-Plane). Optional keys: weather, time, weight, etc. |
| `patch_flight` | `PATCH /api/v3/flight` — partial `data` merge. **X-Plane does not allow start-location keys on PATCH** (`lle_ground_start`, `lle_air_start`, `runway_start`, `ramp_start`, `boat_start` → HTTP 400 *invalid to specify a start*). Use `start_flight` (POST) to set lat/lon/altitude via `lle_*`. |
| `list_available_planes` | Lists installed `.acf` aircraft under `XPLANE_ROOT/Aircraft` (needs `XPLANE_ROOT` env). Returns MCP **structured** `{ "aircraft": [ { "name", "path" } ] }` (empty `aircraft` if unset). |
| `list_aircraft_liveries` | Scans each aircraft’s `liveries/` folder under `XPLANE_ROOT/Aircraft`. Optional `aircraft_path` filters to one `.acf`. Structured `{ "aircraft": [ { "name", "path", "liveries": [ { "name", "path" } ] } ] }`; use `liveries[].name` for `aircraft.livery`. |
| `change_plane_model` | Swaps the loaded aircraft via flight init while keeping position/heading (`aircraft_path`, optional `livery`). |

## Datarefs operations

Resolve, read, write, and stream dataref values.

| Tool | Description |
|------|-------------|
| `find_dataref` | Resolves a dataref by exact name; returns session metadata (`id`, `name`, `value_type`). |
| `resolve_dataref` | Tries `find_dataref` when `dataref_name` is set; otherwise returns the first dataref from a paged list. |
| `get_dataref_value` | Gets the current value for a session-local dataref `id`; optional array `index`. |
| `set_dataref_value` | Patches a value by session-local dataref `id` (`value_json`, optional `index`). |
| `set_dataref_by_name` | Resolves a dataref by name and patches its value (`value_json`, optional `index`). |
| `set_failure_dataref` | Convenience alias for setting failure/malfunction datarefs by name (same as `set_dataref_by_name`). |
| `get_state` | Reads a dataref by name over REST and optionally waits for one WebSocket update (~10 Hz). |

The server talks to the X-Plane **local Web API** (REST + optional WebSocket). Dataref and command **IDs are session-local**; resolve names after each simulator restart. See the [X-Plane Web API article](https://developer.x-plane.com/article/x-plane-web-api/) and [`README.md`](README.md) for configuration (`XPLANE_HOST`, `XPLANE_PORT`, `XPLANE_ROOT`, etc.).
