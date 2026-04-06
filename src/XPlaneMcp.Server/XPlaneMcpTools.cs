using System.ComponentModel;
using System.Text.Json;
using System.Text.Json.Nodes;
using ModelContextProtocol.Server;

namespace XPlaneMcp.Server;

[McpServerToolType]
public sealed class XPlaneMcpTools(XPlaneMcpService svc)
{
    private static readonly JsonSerializerOptions JsonPretty = new() { WriteIndented = true };

    private static string Json(JsonElement e) => JsonSerializer.Serialize(e, JsonPretty);

    private static string Json(object o) => JsonSerializer.Serialize(o, JsonPretty);

    [McpServerTool, Description("GET /api/capabilities — API versions and server info from X-Plane.")]
    public async Task<string> GetCapabilities(CancellationToken cancellationToken = default)
    {
        var el = await svc.GetCapabilitiesAsync(cancellationToken).ConfigureAwait(false);
        return Json(el);
    }

    [McpServerTool, Description("POST /api/v3/flight — start a flight. flight_json must be the inner `data` object as JSON (e.g. ramp_start, aircraft).")]
    public async Task<string> StartFlight(
        [Description("JSON object matching X-Plane flight init `data`")] string flight_json,
        CancellationToken cancellationToken = default)
    {
        using var doc = JsonDocument.Parse(flight_json);
        var el = await svc.StartFlightAsync(doc.RootElement.Clone(), cancellationToken).ConfigureAwait(false);
        return Json(el);
    }

    [McpServerTool, Description("PATCH /api/v3/flight — update current flight. flight_json is the `data` object as JSON.")]
    public async Task<string> PatchFlight(
        [Description("JSON object matching X-Plane flight patch `data`")] string flight_json,
        CancellationToken cancellationToken = default)
    {
        using var doc = JsonDocument.Parse(flight_json);
        var el = await svc.PatchFlightAsync(doc.RootElement.Clone(), cancellationToken).ConfigureAwait(false);
        return Json(el);
    }

    [McpServerTool, Description("Start a new flight at an ICAO airport using the current aircraft (reads aircraft path from the sim).")]
    public async Task<string> MovePlaneToAirport(
        [Description("ICAO airport id, e.g. KPDX")] string airport_id,
        [Description("Ramp id (default A1)")] string ramp = "A1",
        CancellationToken cancellationToken = default)
    {
        var el = await svc.MovePlaneToAirportAsync(airport_id, ramp, cancellationToken).ConfigureAwait(false);
        return Json(el);
    }

    [McpServerTool, Description("Start a new flight at an airport. Optionally set aircraft_path (relative to X-Plane root) and livery.")]
    public async Task<string> StartNewFlight(
        string airport_id,
        string ramp = "A1",
        string? aircraft_path = null,
        string? livery = null,
        CancellationToken cancellationToken = default)
    {
        var el = await svc.StartNewFlightAsync(airport_id, ramp, aircraft_path, livery, cancellationToken).ConfigureAwait(false);
        return Json(el);
    }

    [McpServerTool, Description("List installed aircraft (.acf) under XPLANE_ROOT/Aircraft. Requires XPLANE_ROOT env var; returns [] if unset.")]
    public Task<string> ListAvailablePlanes()
    {
        var planes = svc.ListAvailablePlanes();
        return Task.FromResult(Json(planes.Select(p => new { p.Name, p.Path })));
    }

    [McpServerTool, Description("Change the loaded aircraft model while keeping current lat/lon/heading (in-place swap via POST /flight).")]
    public async Task<string> ChangePlaneModel(
        string aircraft_path,
        string? livery = null,
        CancellationToken cancellationToken = default)
    {
        var el = await svc.ChangePlaneModelAsync(aircraft_path, livery, cancellationToken).ConfigureAwait(false);
        return Json(el);
    }

    [McpServerTool, Description("Resolve a dataref by exact name. Returns first match metadata (id, name, value_type).")]
    public async Task<string> FindDataref(
        string name,
        CancellationToken cancellationToken = default)
    {
        var el = await svc.Http.FindDatarefAsync(name, cancellationToken).ConfigureAwait(false);
        return Json(el);
    }

    [McpServerTool, Description("If name is non-empty, try find_dataref; on failure or empty name, return the first dataref from list_datarefs(limit=1).")]
    public async Task<string> ResolveDataref(
        string? dataref_name,
        CancellationToken cancellationToken = default)
    {
        var el = await svc.ResolveDatarefAsync(dataref_name, cancellationToken).ConfigureAwait(false);
        return Json(el);
    }

    [McpServerTool, Description("List datarefs (paged).")]
    public async Task<string> ListDatarefs(
        int limit = 10,
        int start = 0,
        CancellationToken cancellationToken = default)
    {
        var list = await svc.Http.ListDatarefsAsync(limit, start, cancellationToken).ConfigureAwait(false);
        return Json(list);
    }

    [McpServerTool, Description("GET dataref value by session-local id (from find_dataref). Optional array index.")]
    public async Task<string> GetDatarefValue(
        string dataref_id,
        int? index = null,
        CancellationToken cancellationToken = default)
    {
        var el = await svc.Http.GetDatarefValueAsync(dataref_id, index, cancellationToken).ConfigureAwait(false);
        return Json(el);
    }

    [McpServerTool, Description("PATCH dataref value by session-local id. value_json is any JSON value the API accepts.")]
    public async Task<string> SetDatarefValue(
        string dataref_id,
        string value_json,
        int? index = null,
        CancellationToken cancellationToken = default)
    {
        using var doc = JsonDocument.Parse(value_json);
        await svc.Http.SetDatarefValueAsync(dataref_id, doc.RootElement.Clone(), index, cancellationToken).ConfigureAwait(false);
        return """{"ok":true}""";
    }

    [McpServerTool, Description("Resolve dataref by exact name and PATCH its value. value_json is any JSON value.")]
    public async Task<string> SetDatarefByName(
        string name,
        string value_json,
        int? index = null,
        CancellationToken cancellationToken = default)
    {
        using var doc = JsonDocument.Parse(value_json);
        var meta = await svc.SetDatarefByNameAsync(name, doc.RootElement.Clone(), index, cancellationToken).ConfigureAwait(false);
        return Json(meta);
    }

    [McpServerTool, Description("List commands (paged).")]
    public async Task<string> ListCommands(
        int limit = 10,
        int start = 0,
        CancellationToken cancellationToken = default)
    {
        var list = await svc.Http.ListCommandsAsync(limit, start, cancellationToken: cancellationToken).ConfigureAwait(false);
        return Json(list);
    }

    [McpServerTool, Description("Activate a command by exact name. duration is seconds (max 10 per API).")]
    public async Task<string> ActivateCommandByName(
        string name,
        double duration = 0,
        CancellationToken cancellationToken = default)
    {
        var cmd = await svc.ActivateCommandByNameAsync(name, duration, cancellationToken).ConfigureAwait(false);
        return Json(cmd);
    }

    [McpServerTool, Description("Convenience: set a failure/malfunction dataref by exact name (same as set_dataref_by_name). value_json is dataref-specific.")]
    public async Task<string> SetFailureDataref(
        string dataref_name,
        string value_json,
        int? index = null,
        CancellationToken cancellationToken = default)
    {
        using var doc = JsonDocument.Parse(value_json);
        var meta = await svc.SetFailureDatarefAsync(dataref_name, doc.RootElement.Clone(), index, cancellationToken).ConfigureAwait(false);
        return Json(meta);
    }

    [McpServerTool, Description("Read one dataref via REST and optionally wait for one WebSocket update (10 Hz stream). use_websocket default true.")]
    public async Task<string> GetState(
        string dataref_name,
        bool use_websocket = true,
        CancellationToken cancellationToken = default)
    {
        var state = await svc.GetStateAsync(dataref_name, use_websocket, cancellationToken).ConfigureAwait(false);
        var root = new JsonObject
        {
            ["dataref"] = JsonNode.Parse(state.Dataref.GetRawText())!,
            ["rest_value"] = JsonNode.Parse(state.RestValue.GetRawText())!,
            ["websocket_value"] = state.WebSocketValue is { } w ? JsonNode.Parse(w.GetRawText()) : null,
        };
        return root.ToJsonString(JsonPretty);
    }
}
