using System.Text.Json;

namespace XPlaneMcp.Server;

/// <summary>High-level operations for MCP tools.</summary>
public sealed class XPlaneMcpService(XPlaneRestClient http, XPlaneConfig config)
{
    private readonly XPlaneRestClient _http = http;
    private readonly XPlaneConfig _config = config;

    /// <summary>Exposed for MCP tool handlers that map directly to REST helpers.</summary>
    public XPlaneRestClient Http => _http;

    public Task<JsonElement> GetCapabilitiesAsync(CancellationToken cancellationToken = default) =>
        _http.GetCapabilitiesAsync(cancellationToken);

    public Task<JsonElement> StartFlightAsync(JsonElement flightData, CancellationToken cancellationToken = default) =>
        _http.StartFlightAsync(flightData, cancellationToken);

    public Task<JsonElement> PatchFlightAsync(JsonElement flightData, CancellationToken cancellationToken = default) =>
        _http.PatchFlightAsync(flightData, cancellationToken);

    public IReadOnlyList<XPlaneAircraftModel> ListAvailablePlanes() => _http.ListAvailablePlanes();

    public IReadOnlyList<XPlaneAircraftWithLiveries> ListAircraftLiveries(string? aircraftPath = null) =>
        _http.ListAircraftLiveries(aircraftPath);

    public Task<JsonElement> ChangePlaneModelAsync(string aircraftPath, string? livery = null, CancellationToken cancellationToken = default) =>
        _http.ChangePlaneModelAsync(aircraftPath, livery, cancellationToken);

    public async Task<JsonElement> ResolveDatarefAsync(string? datarefName, CancellationToken cancellationToken = default)
    {
        if (!string.IsNullOrWhiteSpace(datarefName))
        {
            try
            {
                return await _http.FindDatarefAsync(datarefName, cancellationToken).ConfigureAwait(false);
            }
            catch (XPlaneApiException)
            {
                // Ignore lookup failure; fall back to listing datarefs below.
            }
        }

        var list = await _http.ListDatarefsAsync(limit: 1, start: 0, cancellationToken).ConfigureAwait(false);
        if (list.Count == 0)
            throw new InvalidOperationException("X-Plane returned no datarefs for the current session");
        return list[0];
    }

    public async Task<XPlaneStateResult> GetStateAsync(string datarefName, bool useWebSocket, CancellationToken cancellationToken = default)
    {
        var dataref = await ResolveDatarefAsync(datarefName, cancellationToken).ConfigureAwait(false);
        var id = dataref.GetProperty("id");
        var idStr = id.ValueKind == JsonValueKind.Number ? id.GetInt32().ToString(System.Globalization.CultureInfo.InvariantCulture) : id.GetString()!;
        var restValue = await _http.GetDatarefValueAsync(idStr, null, cancellationToken).ConfigureAwait(false);

        JsonElement? wsValue = null;
        if (useWebSocket)
        {
            await using var ws = new XPlaneWebSocketSession();
            await ws.ConnectAsync(_config, cancellationToken).ConfigureAwait(false);
            await ws.SubscribeDatarefAsync(id, cancellationToken).ConfigureAwait(false);
            var msg = await XPlaneWebSocketSession.WaitForDatarefUpdateAsync(
                ws,
                idStr,
                TimeSpan.FromSeconds(5),
                cancellationToken).ConfigureAwait(false);
            wsValue = msg;
        }

        return new XPlaneStateResult(dataref, restValue, wsValue);
    }

    public Task<JsonElement> SetDatarefByNameAsync(string name, JsonElement value, int? index = null, CancellationToken cancellationToken = default) =>
        _http.SetDatarefValueByNameAsync(name, value, index, cancellationToken);

    public Task<JsonElement> ActivateCommandByNameAsync(string name, double duration = 0, CancellationToken cancellationToken = default) =>
        _http.ActivateCommandByNameAsync(name, duration, cancellationToken);

    public Task<JsonElement> SetFailureDatarefAsync(string datarefName, JsonElement value, int? index = null, CancellationToken cancellationToken = default) =>
        _http.SetDatarefValueByNameAsync(datarefName, value, index, cancellationToken);
}

public readonly record struct XPlaneStateResult(JsonElement Dataref, JsonElement RestValue, JsonElement? WebSocketValue);
