using System.ComponentModel;
using System.Text.Json;
using System.Text.Json.Nodes;
using ModelContextProtocol;
using ModelContextProtocol.Server;

namespace XPlaneMcp.Server;

[McpServerToolType]
public sealed class XPlaneMcpTools(XPlaneMcpService svc)
{
    private static readonly JsonSerializerOptions JsonPretty = new() { WriteIndented = true };

    private static string Json(JsonElement e) => JsonSerializer.Serialize(e, JsonPretty);

    private static string Json(object o) => JsonSerializer.Serialize(o, JsonPretty);

    /// <summary>MCP C# SDK only forwards <see cref="McpException"/> messages to clients; other exceptions become a generic tool error.</summary>
    private static async Task<string> RunToolAsync(Func<Task<string>> action, CancellationToken cancellationToken)
    {
        try
        {
            return await action().ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            throw;
        }
        catch (McpProtocolException)
        {
            throw;
        }
        catch (McpException)
        {
            throw;
        }
        catch (Exception ex)
        {
            throw new McpException(XPlaneMcpToolErrors.Format(ex), ex);
        }
    }

    private static string RunToolSync(Func<string> action)
    {
        try
        {
            return action();
        }
        catch (McpProtocolException)
        {
            throw;
        }
        catch (McpException)
        {
            throw;
        }
        catch (Exception ex)
        {
            throw new McpException(XPlaneMcpToolErrors.Format(ex), ex);
        }
    }

    [McpServerTool, Description("GET /api/capabilities — API versions and server info from X-Plane.")]
    public Task<string> GetCapabilities(CancellationToken cancellationToken = default) =>
        RunToolAsync(async () =>
        {
            var el = await svc.GetCapabilitiesAsync(cancellationToken).ConfigureAwait(false);
            return Json(el);
        }, cancellationToken);

    [McpServerTool, Description("POST /api/v3/flight — start a flight. flight_json must be the inner `data` object as JSON (e.g. ramp_start, aircraft).")]
    public Task<string> StartFlight(
        [Description("JSON object matching X-Plane flight init `data`")] string flight_json,
        CancellationToken cancellationToken = default) =>
        RunToolAsync(async () =>
        {
            using var doc = JsonDocument.Parse(flight_json);
            var el = await svc.StartFlightAsync(doc.RootElement.Clone(), cancellationToken).ConfigureAwait(false);
            return Json(el);
        }, cancellationToken);

    [McpServerTool, Description("PATCH /api/v3/flight — update current flight. flight_json is the `data` object as JSON.")]
    public Task<string> PatchFlight(
        [Description("JSON object matching X-Plane flight patch `data`")] string flight_json,
        CancellationToken cancellationToken = default) =>
        RunToolAsync(async () =>
        {
            using var doc = JsonDocument.Parse(flight_json);
            var el = await svc.PatchFlightAsync(doc.RootElement.Clone(), cancellationToken).ConfigureAwait(false);
            return Json(el);
        }, cancellationToken);

    [McpServerTool, Description("Start a new flight at an ICAO airport using the current aircraft (reads aircraft path from the sim).")]
    public Task<string> MovePlaneToAirport(
        string airport_id,
        string ramp = "A1",
        CancellationToken cancellationToken = default) =>
        RunToolAsync(async () =>
        {
            var el = await svc.MovePlaneToAirportAsync(airport_id, ramp, cancellationToken).ConfigureAwait(false);
            return Json(el);
        }, cancellationToken);

    [McpServerTool, Description("List installed aircraft (.acf) under XPLANE_ROOT/Aircraft. Requires XPLANE_ROOT env var; returns [] if unset.")]
    public Task<string> ListAvailablePlanes() =>
        Task.FromResult(RunToolSync(() =>
            Json(svc.ListAvailablePlanes().Select(p => new { p.Name, p.Path }))));

    [McpServerTool, Description(
        "Return a hardcoded list of X-Plane 12 Laminar stock aircraft paths (relative to the sim root) for flight API aircraft.path. " +
        "No filesystem access and no XPLANE_ROOT required; verify against list_available_planes when an install path is configured.")]
    public Task<string> ListStockAircraft() =>
        Task.FromResult(RunToolSync(() =>
            Json(StockAircraftCatalog.All.Select(p => new { p.Name, p.Path }))));

    [McpServerTool, Description("Change the loaded aircraft model while keeping current lat/lon/heading (in-place swap via POST /flight).")]
    public Task<string> ChangePlaneModel(
        string aircraft_path,
        string? livery = null,
        CancellationToken cancellationToken = default) =>
        RunToolAsync(async () =>
        {
            var el = await svc.ChangePlaneModelAsync(aircraft_path, livery, cancellationToken).ConfigureAwait(false);
            return Json(el);
        }, cancellationToken);

    [McpServerTool, Description("Resolve a dataref by exact name. Returns first match metadata (id, name, value_type).")]
    public Task<string> FindDataref(
        string name,
        CancellationToken cancellationToken = default) =>
        RunToolAsync(async () =>
        {
            var el = await svc.Http.FindDatarefAsync(name, cancellationToken).ConfigureAwait(false);
            return Json(el);
        }, cancellationToken);

    [McpServerTool, Description("If name is non-empty, try find_dataref; on failure or empty name, return the first dataref from list_datarefs(limit=1).")]
    public Task<string> ResolveDataref(
        string? dataref_name,
        CancellationToken cancellationToken = default) =>
        RunToolAsync(async () =>
        {
            var el = await svc.ResolveDatarefAsync(dataref_name, cancellationToken).ConfigureAwait(false);
            return Json(el);
        }, cancellationToken);

    [McpServerTool, Description("List datarefs (paged).")]
    public Task<string> ListDatarefs(
        int limit = 10,
        int start = 0,
        CancellationToken cancellationToken = default) =>
        RunToolAsync(async () =>
        {
            var list = await svc.Http.ListDatarefsAsync(limit, start, cancellationToken).ConfigureAwait(false);
            return Json(list);
        }, cancellationToken);

    [McpServerTool, Description("GET dataref value by session-local id (from find_dataref). Optional array index.")]
    public Task<string> GetDatarefValue(
        string dataref_id,
        int? index = null,
        CancellationToken cancellationToken = default) =>
        RunToolAsync(async () =>
        {
            var el = await svc.Http.GetDatarefValueAsync(dataref_id, index, cancellationToken).ConfigureAwait(false);
            return Json(el);
        }, cancellationToken);

    [McpServerTool, Description("PATCH dataref value by session-local id. value_json is any JSON value the API accepts.")]
    public Task<string> SetDatarefValue(
        string dataref_id,
        string value_json,
        int? index = null,
        CancellationToken cancellationToken = default) =>
        RunToolAsync(async () =>
        {
            using var doc = JsonDocument.Parse(value_json);
            await svc.Http.SetDatarefValueAsync(dataref_id, doc.RootElement.Clone(), index, cancellationToken).ConfigureAwait(false);
            return """{"ok":true}""";
        }, cancellationToken);

    [McpServerTool, Description("Resolve dataref by exact name and PATCH its value. value_json is any JSON value.")]
    public Task<string> SetDatarefByName(
        string name,
        string value_json,
        int? index = null,
        CancellationToken cancellationToken = default) =>
        RunToolAsync(async () =>
        {
            using var doc = JsonDocument.Parse(value_json);
            var meta = await svc.SetDatarefByNameAsync(name, doc.RootElement.Clone(), index, cancellationToken).ConfigureAwait(false);
            return Json(meta);
        }, cancellationToken);

    [McpServerTool, Description("List commands (paged).")]
    public Task<string> ListCommands(
        int limit = 10,
        int start = 0,
        CancellationToken cancellationToken = default) =>
        RunToolAsync(async () =>
        {
            var list = await svc.Http.ListCommandsAsync(limit, start, cancellationToken: cancellationToken).ConfigureAwait(false);
            return Json(list);
        }, cancellationToken);

    [McpServerTool, Description("Activate a command by exact name. duration is seconds (max 10 per API).")]
    public Task<string> ActivateCommandByName(
        string name,
        double duration = 0,
        CancellationToken cancellationToken = default) =>
        RunToolAsync(async () =>
        {
            var cmd = await svc.ActivateCommandByNameAsync(name, duration, cancellationToken).ConfigureAwait(false);
            return Json(cmd);
        }, cancellationToken);

    [McpServerTool, Description("Convenience: set a failure/malfunction dataref by exact name (same as set_dataref_by_name). value_json is dataref-specific.")]
    public Task<string> SetFailureDataref(
        string dataref_name,
        string value_json,
        int? index = null,
        CancellationToken cancellationToken = default) =>
        RunToolAsync(async () =>
        {
            using var doc = JsonDocument.Parse(value_json);
            var meta = await svc.SetFailureDatarefAsync(dataref_name, doc.RootElement.Clone(), index, cancellationToken).ConfigureAwait(false);
            return Json(meta);
        }, cancellationToken);

    [McpServerTool, Description("Read one dataref via REST and optionally wait for one WebSocket update (10 Hz stream). use_websocket default true.")]
    public Task<string> GetState(
        string dataref_name,
        bool use_websocket = true,
        CancellationToken cancellationToken = default) =>
        RunToolAsync(async () =>
        {
            var state = await svc.GetStateAsync(dataref_name, use_websocket, cancellationToken).ConfigureAwait(false);
            var root = new JsonObject
            {
                ["dataref"] = JsonNode.Parse(state.Dataref.GetRawText())!,
                ["rest_value"] = JsonNode.Parse(state.RestValue.GetRawText())!,
                ["websocket_value"] = state.WebSocketValue is { } w ? JsonNode.Parse(w.GetRawText()) : null,
            };
            return root.ToJsonString(JsonPretty);
        }, cancellationToken);
}
