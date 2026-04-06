using System.ComponentModel;
using System.Text.Json;
using System.Text.Json.Nodes;
using ModelContextProtocol;
using ModelContextProtocol.Protocol;
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

    [McpServerTool, Description(
        "POST /api/v3/flight — start a new flight. flight_json is the inner `data` object (Flight Initialization API). " +
        "Include `aircraft` { path, optional livery } and exactly one start-location object as a top-level key: " +
        "ramp_start, runway_start, lle_ground_start, lle_air_start, or boat_start (same nested field names as X-Plane). " +
        "You may add optional keys (weather, time, weight, engine_status, etc.) per the same API. " +
        "lle_air_start requires a speed field: speed_in_meters_per_second and/or speed_enum or speed_mode depending on X-Plane version.")]
    public Task<string> StartFlight(
        [Description("Inner `data` JSON (X-Plane Flight Initialization API)")] string flight_json,
        CancellationToken cancellationToken = default) =>
        RunToolAsync(async () =>
        {
            using var doc = JsonDocument.Parse(flight_json);
            var el = await svc.StartFlightAsync(doc.RootElement.Clone(), cancellationToken).ConfigureAwait(false);
            return Json(el);
        }, cancellationToken);

    [McpServerTool, Description(
        "PATCH /api/v3/flight — merge partial flight `data` into the current flight. " +
        "X-Plane rejects any start-location keys on PATCH (lle_ground_start, lle_air_start, runway_start, ramp_start, boat_start): " +
        "\"invalid to specify a start\". Relocate with start_flight (POST) using `aircraft` plus exactly one of lle_ground_start or lle_air_start (or runway/ramp/boat). " +
        "PATCH is for other init fields (e.g. weather, time, weight) where supported.")]
    public Task<string> PatchFlight(
        [Description("Partial inner `data` JSON — do not include start keys (lle_*, runway_start, ramp_start, boat_start); use start_flight to relocate")] string flight_json,
        CancellationToken cancellationToken = default) =>
        RunToolAsync(async () =>
        {
            using var doc = JsonDocument.Parse(flight_json);
            var el = await svc.PatchFlightAsync(doc.RootElement.Clone(), cancellationToken).ConfigureAwait(false);
            return Json(el);
        }, cancellationToken);

    [McpServerTool, Description(
        "List installed aircraft (.acf) under XPLANE_ROOT/Aircraft. Requires XPLANE_ROOT env var. " +
        "Structured result: { aircraft: [ { name, path } ] } (empty aircraft if XPLANE_ROOT unset).")]
    public Task<CallToolResult> ListAvailablePlanes() =>
        Task.FromResult(ListAvailablePlanesCore());

    private CallToolResult ListAvailablePlanesCore()
    {
        try
        {
            var aircraft = svc.ListAvailablePlanes().Select(p => new { name = p.Name, path = p.Path }).ToList();
            return new CallToolResult
            {
                StructuredContent = JsonSerializer.SerializeToElement(new { aircraft }),
            };
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

    [McpServerTool, Description(
        "Scan XPLANE_ROOT/Aircraft: for each .acf, list subfolders of acf_dir/liveries/ (X-Plane livery packs). " +
        "Optional aircraft_path limits to one sim-root-relative .acf path (forward slashes, same as list_available_planes path). " +
        "Use liveries[].name as aircraft.livery in flight init / change_plane_model. " +
        "Structured result: { aircraft: [ { name, path, liveries: [ { name, path } ] } ] }. Empty aircraft if XPLANE_ROOT unset.")]
    public Task<CallToolResult> ListAircraftLiveries(
        [Description("Optional sim-root-relative path to one .acf; omit to scan all aircraft")] string? aircraft_path = null) =>
        Task.FromResult(ListAircraftLiveriesCore(aircraft_path));

    private CallToolResult ListAircraftLiveriesCore(string? aircraft_path)
    {
        try
        {
            var aircraft = svc.ListAircraftLiveries(aircraft_path).Select(a => new
            {
                name = a.Name,
                path = a.Path,
                liveries = a.Liveries.Select(l => new { name = l.Name, path = l.Path }).ToList(),
            }).ToList();
            return new CallToolResult
            {
                StructuredContent = JsonSerializer.SerializeToElement(new { aircraft }),
            };
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
