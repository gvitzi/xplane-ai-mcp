# Example MCP stdio JSON lines

The XPlane MCP server speaks **newline-delimited JSON** (one JSON object per line, no embedded newlines in the payload) on **stdin** / **stdout**, matching MCP stdio transport (`protocolVersion` **2024-11-05**).

Paste or pipe **single-line** JSON into the running process (for example after starting `XPlaneMcp.Server.exe` from [`README.md`](../README.md)). Read each response line from stdout before sending the next request; responses are JSON-RPC **result** or **error** objects with matching `id`.

## Build (from repository root, PowerShell)

**Publish the MCP server** (framework-dependent output to `artifacts/xplane-mcp/`, including `XPlaneMcp.Server.exe`):

```powershell
.\make.ps1 publish
```

Equivalent direct script:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\publish-server.ps1
```

Optional: `-Configuration Debug` or `-Output <folder>` — see [`scripts/publish-server.ps1`](../scripts/publish-server.ps1).

**Build the Windows installer (MSI)** — WiX project, self-contained `win-x64` publish staged under `artifacts/msi-staging/`, MSI at `artifacts/installer/xplaneMCP.msi`. Requires **.NET SDK 9+** (WiX restored via NuGet); the build runs [`scripts/prepare_installer_assets.py`](../scripts/prepare_installer_assets.py) (needs **Python** on `PATH`).

```powershell
.\make.ps1 msi
```

Equivalent direct script:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-msi.ps1
```

Optional: `-Configuration Debug` — see [`scripts/build-msi.ps1`](../scripts/build-msi.ps1).

## Running the server with `XPLANE_ROOT` (Steam library on `E:\`)

From the **repository root**, PowerShell (adjust the folder if your install is X-Plane 11 or a different Steam library path):

```powershell
$env:XPLANE_ROOT = "E:\SteamLibrary\steamapps\common\X-Plane 12"; .\artifacts\xplane-mcp\XPlaneMcp.Server.exe
```

`XPLANE_ROOT` must be the simulator **install root** (the directory that contains `Aircraft`, `Resources`, etc.), not the `steamapps` folder alone.

## 1. `initialize`

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"manual-terminal","version":"0"}}}
```

After you receive a successful result for `id` **1**, send the initialized notification (no `id`):

```json
{"jsonrpc":"2.0","method":"notifications/initialized"}
```

## 2. `tools/call` — `list_available_planes`

Lists installed `.acf` aircraft under `XPLANE_ROOT/Aircraft`. Set the **`XPLANE_ROOT`** environment variable to your X-Plane install before starting the server; if unset, the tool returns an empty list.

Use a new request id (e.g. **2**):

```json
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"list_available_planes","arguments":{}}}
```

The result uses **`structuredContent`**: `{ "aircraft": [ { "name": "…", "path": "…" } ] }` (no text `content` block). Other tools may still return JSON in a text block.

## 3. `tools/call` — `list_aircraft_liveries`

Scans `XPLANE_ROOT/Aircraft`: for each `.acf`, lists subfolders of `acf_dir/liveries/` (livery pack folder names match `aircraft.livery` in flight init). Requires **`XPLANE_ROOT`** (see **Running the server with `XPLANE_ROOT`** above).

**All aircraft** (use a fresh request id, e.g. **3**):

```json
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"list_aircraft_liveries","arguments":{}}}
```

**One aircraft** — `aircraft_path` is sim-root-relative, forward slashes, same as `list_available_planes` `path` values:

```json
{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"list_aircraft_liveries","arguments":{"aircraft_path":"Aircraft/Laminar Research/Cessna 172 SP/Cessna_172SP.acf"}}}
```

Structured result: `{ "aircraft": [ { "name", "path", "liveries": [ { "name", "path" } ] } ] }`. If `XPLANE_ROOT` is unset, `aircraft` is `[]`.
