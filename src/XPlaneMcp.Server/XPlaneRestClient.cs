using System.Net.Http.Json;
using System.Text;
using System.Text.Json;

namespace XPlaneMcp.Server;

/// <summary>REST client for X-Plane local Web API v3.</summary>
public sealed class XPlaneRestClient : IDisposable
{
    private readonly HttpClient _http;
    private readonly XPlaneConfig _config;
    private readonly bool _ownsClient;

    public XPlaneRestClient(HttpClient http, XPlaneConfig config, bool ownsClient = false)
    {
        _http = http;
        _config = config;
        _ownsClient = ownsClient;
    }

    public XPlaneConfig Config => _config;

    public void Dispose()
    {
        if (_ownsClient)
            _http.Dispose();
    }

    public async Task<JsonElement> GetCapabilitiesAsync(CancellationToken cancellationToken = default)
    {
        using var request = new HttpRequestMessage(HttpMethod.Get, _config.CapabilitiesUrl);
        using var response = await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken).ConfigureAwait(false);
        return await ParseResponseAsync(response, allowEmpty: false, cancellationToken).ConfigureAwait(false);
    }

    public async Task<JsonElement> StartFlightAsync(JsonElement flightData, CancellationToken cancellationToken = default)
    {
        using var content = JsonContent.Create(new Dictionary<string, JsonElement> { ["data"] = flightData });
        using var response = await _http.PostAsync("flight", content, cancellationToken).ConfigureAwait(false);
        return await ParseResponseAsync(response, allowEmpty: true, cancellationToken).ConfigureAwait(false);
    }

    public async Task<JsonElement> PatchFlightAsync(JsonElement flightData, CancellationToken cancellationToken = default)
    {
        using var content = JsonContent.Create(new Dictionary<string, JsonElement> { ["data"] = flightData });
        using var response = await _http.PatchAsync("flight", content, cancellationToken).ConfigureAwait(false);
        return await ParseResponseAsync(response, allowEmpty: true, cancellationToken).ConfigureAwait(false);
    }

    public async Task<JsonElement> ChangePlaneModelAsync(string aircraftPath, string? livery = null, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(aircraftPath))
            throw new ArgumentException("aircraft_path is required", nameof(aircraftPath));
        var pos = await GetCurrentPositionAsync(cancellationToken).ConfigureAwait(false);
        var flight = new Dictionary<string, object?>
        {
            ["lle_ground_start"] = new Dictionary<string, object?>
            {
                ["latitude"] = pos.Latitude,
                ["longitude"] = pos.Longitude,
                ["heading_true"] = pos.HeadingTrue,
            },
            ["aircraft"] = new Dictionary<string, object?> { ["path"] = aircraftPath },
        };
        if (!string.IsNullOrEmpty(livery))
            ((Dictionary<string, object?>)flight["aircraft"]!)["livery"] = livery;
        var json = JsonSerializer.SerializeToElement(flight);
        return await StartFlightAsync(json, cancellationToken).ConfigureAwait(false);
    }

    public IReadOnlyList<XPlaneAircraftModel> ListAvailablePlanes()
    {
        if (string.IsNullOrEmpty(_config.XPlaneRoot))
            return [];

        var root = new DirectoryInfo(_config.XPlaneRoot);
        var aircraftRoot = new DirectoryInfo(Path.Combine(root.FullName, "Aircraft"));
        if (!aircraftRoot.Exists)
            throw new InvalidOperationException($"Aircraft directory not found: {aircraftRoot.FullName}");

        var list = new List<XPlaneAircraftModel>();
        foreach (var file in aircraftRoot.EnumerateFiles("*.acf", SearchOption.AllDirectories).OrderBy(f => f.FullName))
        {
            var rel = Path.GetRelativePath(root.FullName, file.FullName).Replace('\\', '/');
            var name = Path.GetFileNameWithoutExtension(file.Name).Replace('_', ' ');
            list.Add(new XPlaneAircraftModel(name, rel));
        }

        return list;
    }

    /// <summary>
    /// Lists livery subfolders under each aircraft's <c>liveries</c> directory (next to the <c>.acf</c>).
    /// Optional <paramref name="aircraftPathFilter"/> is a sim-root-relative path to one <c>.acf</c> (forward slashes).
    /// </summary>
    public IReadOnlyList<XPlaneAircraftWithLiveries> ListAircraftLiveries(string? aircraftPathFilter = null)
    {
        if (string.IsNullOrEmpty(_config.XPlaneRoot))
            return [];

        var root = new DirectoryInfo(_config.XPlaneRoot);
        var aircraftRoot = new DirectoryInfo(Path.Combine(root.FullName, "Aircraft"));
        if (!aircraftRoot.Exists)
            throw new InvalidOperationException($"Aircraft directory not found: {aircraftRoot.FullName}");

        var normalizedFilter = string.IsNullOrWhiteSpace(aircraftPathFilter)
            ? null
            : NormalizeSimRelativePath(aircraftPathFilter);

        var result = new List<XPlaneAircraftWithLiveries>();
        foreach (var file in aircraftRoot.EnumerateFiles("*.acf", SearchOption.AllDirectories).OrderBy(f => f.FullName, StringComparer.OrdinalIgnoreCase))
        {
            var rel = NormalizeSimRelativePath(Path.GetRelativePath(root.FullName, file.FullName));
            if (normalizedFilter is not null &&
                !rel.Equals(normalizedFilter, StringComparison.OrdinalIgnoreCase))
                continue;

            var dir = file.DirectoryName;
            if (string.IsNullOrEmpty(dir))
                continue;

            var displayName = Path.GetFileNameWithoutExtension(file.Name).Replace('_', ' ');
            var liveries = EnumerateLiveriesUnderAircraft(root.FullName, dir);
            result.Add(new XPlaneAircraftWithLiveries(displayName, rel, liveries));
        }

        return result;
    }

    private static IReadOnlyList<XPlaneLiveryInfo> EnumerateLiveriesUnderAircraft(string xplaneRootFull, string aircraftFolderFull)
    {
        var liveriesDir = Path.Combine(aircraftFolderFull, "liveries");
        if (!Directory.Exists(liveriesDir))
            return [];

        var list = new List<XPlaneLiveryInfo>();
        foreach (var sub in Directory.EnumerateDirectories(liveriesDir).OrderBy(d => d, StringComparer.OrdinalIgnoreCase))
        {
            var name = Path.GetFileName(sub);
            if (string.IsNullOrEmpty(name))
                continue;
            var rel = NormalizeSimRelativePath(Path.GetRelativePath(xplaneRootFull, sub));
            list.Add(new XPlaneLiveryInfo(name, rel));
        }

        return list;
    }

    private static string NormalizeSimRelativePath(string path) =>
        path.Trim().Replace('\\', '/').TrimStart('/');

    public async Task<JsonElement> FindDatarefAsync(string name, CancellationToken cancellationToken = default)
    {
        var filterKey = Uri.EscapeDataString("filter[name]");
        var url = $"datarefs?{filterKey}={Uri.EscapeDataString(name)}&fields=id,name,value_type";
        using var response = await _http.GetAsync(url, cancellationToken).ConfigureAwait(false);
        var payload = await ParseResponseAsync(response, allowEmpty: false, cancellationToken).ConfigureAwait(false);
        if (!payload.TryGetProperty("data", out var data) || data.ValueKind != JsonValueKind.Array || data.GetArrayLength() == 0)
            throw new XPlaneApiException($"Dataref not found: {name}", responseBody: payload.GetRawText());
        return data[0];
    }

    public async Task<IReadOnlyList<JsonElement>> ListDatarefsAsync(int limit = 10, int start = 0, CancellationToken cancellationToken = default)
    {
        var url = $"datarefs?limit={limit}&start={start}&fields=id,name,value_type";
        using var response = await _http.GetAsync(url, cancellationToken).ConfigureAwait(false);
        var payload = await ParseResponseAsync(response, allowEmpty: false, cancellationToken).ConfigureAwait(false);
        if (!payload.TryGetProperty("data", out var data) || data.ValueKind != JsonValueKind.Array)
            throw new XPlaneApiException("Expected datarefs list response", responseBody: payload.GetRawText());
        return data.EnumerateArray().ToList();
    }

    public async Task<JsonElement> GetDatarefValueAsync(string datarefId, int? index = null, CancellationToken cancellationToken = default)
    {
        var url = index is null
            ? $"datarefs/{datarefId}/value"
            : $"datarefs/{datarefId}/value?index={index.Value}";
        using var response = await _http.GetAsync(url, cancellationToken).ConfigureAwait(false);
        return await ParseResponseAsync(response, allowEmpty: false, cancellationToken).ConfigureAwait(false);
    }

    public async Task SetDatarefValueAsync(string datarefId, JsonElement value, int? index = null, CancellationToken cancellationToken = default)
    {
        var url = index is null
            ? $"datarefs/{datarefId}/value"
            : $"datarefs/{datarefId}/value?index={index.Value}";
        using var content = JsonContent.Create(new Dictionary<string, JsonElement> { ["data"] = value });
        using var response = await _http.PatchAsync(url, content, cancellationToken).ConfigureAwait(false);
        await ParseResponseAsync(response, allowEmpty: true, cancellationToken).ConfigureAwait(false);
    }

    public async Task<JsonElement> SetDatarefValueByNameAsync(string name, JsonElement value, int? index = null, CancellationToken cancellationToken = default)
    {
        var dataref = await FindDatarefAsync(name, cancellationToken).ConfigureAwait(false);
        var id = dataref.GetProperty("id").ToString();
        await SetDatarefValueAsync(id, value, index, cancellationToken).ConfigureAwait(false);
        return dataref;
    }

    public async Task<JsonElement> FindCommandAsync(string name, CancellationToken cancellationToken = default)
    {
        var filterKey = Uri.EscapeDataString("filter[name]");
        var url = $"commands?{filterKey}={Uri.EscapeDataString(name)}&fields=id,name,description";
        using var response = await _http.GetAsync(url, cancellationToken).ConfigureAwait(false);
        var payload = await ParseResponseAsync(response, allowEmpty: false, cancellationToken).ConfigureAwait(false);
        if (!payload.TryGetProperty("data", out var data) || data.ValueKind != JsonValueKind.Array || data.GetArrayLength() == 0)
            throw new XPlaneApiException($"Command not found: {name}", responseBody: payload.GetRawText());
        return data[0];
    }

    public async Task<IReadOnlyList<JsonElement>> ListCommandsAsync(int limit = 10, int start = 0, string? fields = "id,name,description", CancellationToken cancellationToken = default)
    {
        var url = fields is null
            ? $"commands?limit={limit}&start={start}"
            : $"commands?limit={limit}&start={start}&fields={Uri.EscapeDataString(fields)}";
        using var response = await _http.GetAsync(url, cancellationToken).ConfigureAwait(false);
        var payload = await ParseResponseAsync(response, allowEmpty: false, cancellationToken).ConfigureAwait(false);
        if (!payload.TryGetProperty("data", out var data) || data.ValueKind != JsonValueKind.Array)
            throw new XPlaneApiException("Expected commands list response", responseBody: payload.GetRawText());
        return data.EnumerateArray().ToList();
    }

    public async Task ActivateCommandAsync(string commandId, double duration = 0, CancellationToken cancellationToken = default)
    {
        using var content = JsonContent.Create(new Dictionary<string, double> { ["duration"] = duration });
        using var response = await _http.PostAsync($"command/{commandId}/activate", content, cancellationToken).ConfigureAwait(false);
        await ParseResponseAsync(response, allowEmpty: true, cancellationToken).ConfigureAwait(false);
    }

    public async Task<JsonElement> ActivateCommandByNameAsync(string name, double duration = 0, CancellationToken cancellationToken = default)
    {
        var cmd = await FindCommandAsync(name, cancellationToken).ConfigureAwait(false);
        var id = cmd.GetProperty("id").ToString();
        await ActivateCommandAsync(id, duration, cancellationToken).ConfigureAwait(false);
        return cmd;
    }

    public async Task<XPlanePosition> GetCurrentPositionAsync(CancellationToken cancellationToken = default)
    {
        var latDr = await FindDatarefAsync("sim/flightmodel/position/latitude", cancellationToken).ConfigureAwait(false);
        var lonDr = await FindDatarefAsync("sim/flightmodel/position/longitude", cancellationToken).ConfigureAwait(false);
        var hdgDr = await FindDatarefAsync("sim/flightmodel/position/true_psi", cancellationToken).ConfigureAwait(false);
        var lat = await GetDatarefValueAsync(latDr.GetProperty("id").ToString(), null, cancellationToken).ConfigureAwait(false);
        var lon = await GetDatarefValueAsync(lonDr.GetProperty("id").ToString(), null, cancellationToken).ConfigureAwait(false);
        var hdg = await GetDatarefValueAsync(hdgDr.GetProperty("id").ToString(), null, cancellationToken).ConfigureAwait(false);
        return new XPlanePosition(
            lat.GetProperty("data").GetDouble(),
            lon.GetProperty("data").GetDouble(),
            hdg.GetProperty("data").GetDouble());
    }

    internal static async Task<JsonElement> ParseResponseAsync(HttpResponseMessage response, bool allowEmpty, CancellationToken cancellationToken)
    {
        var bytes = await response.Content.ReadAsByteArrayAsync(cancellationToken).ConfigureAwait(false);
        var text = Encoding.UTF8.GetString(bytes).Trim();
        if (allowEmpty && text.Length == 0)
        {
            if (!response.IsSuccessStatusCode)
                throw new XPlaneApiException($"X-Plane API request failed with HTTP {(int)response.StatusCode}", (int)response.StatusCode);
            return ParseJson("{\"data\":null}");
        }

        JsonDocument? doc = null;
        try
        {
            if (text.Length == 0)
            {
                if (!response.IsSuccessStatusCode)
                    throw new XPlaneApiException($"Expected JSON response, got HTTP {(int)response.StatusCode}", (int)response.StatusCode);
                if (allowEmpty)
                    return ParseJson("{\"data\":null}");
                throw new XPlaneApiException($"Expected JSON response, got HTTP {(int)response.StatusCode}", (int)response.StatusCode);
            }

            doc = JsonDocument.Parse(text);
            var root = doc.RootElement;
            if (!response.IsSuccessStatusCode)
            {
                var msg = TryGetErrorMessage(root) ?? $"X-Plane API request failed with HTTP {(int)response.StatusCode}";
                var code = TryGetErrorCode(root);
                throw new XPlaneApiException(msg, (int)response.StatusCode, code, root.GetRawText());
            }

            if (root.ValueKind != JsonValueKind.Object)
            {
                if (allowEmpty)
                    return ParseJson("{\"data\":null}");
                throw new XPlaneApiException("Expected top-level JSON object from X-Plane API", (int)response.StatusCode);
            }

            ThrowIfJsonIndicatesXPlaneError(response, root);

            return root.Clone();
        }
        catch (JsonException ex)
        {
            if (allowEmpty && response.IsSuccessStatusCode)
                return ParseJson("{\"data\":null}");
            throw new XPlaneApiException($"Expected JSON response, got HTTP {(int)response.StatusCode}", (int)response.StatusCode, responseBody: Encoding.UTF8.GetString(bytes), inner: ex);
        }
        finally
        {
            doc?.Dispose();
        }
    }

    private static string? TryGetErrorMessage(JsonElement root) =>
        root.TryGetProperty("error_message", out var e) && e.ValueKind == JsonValueKind.String ? e.GetString() : null;

    private static string? TryGetErrorCode(JsonElement root)
    {
        if (!root.TryGetProperty("error_code", out var e))
            return null;
        return e.ValueKind switch
        {
            JsonValueKind.String => e.GetString(),
            JsonValueKind.Number => e.GetRawText(),
            _ => null,
        };
    }

    /// <summary>X-Plane may return HTTP 200 with <c>error_message</c> / <c>error_code</c> for failed flight init, etc.</summary>
    private static void ThrowIfJsonIndicatesXPlaneError(HttpResponseMessage response, JsonElement root)
    {
        var msg = TryGetErrorMessage(root);
        if (string.IsNullOrEmpty(msg) && root.TryGetProperty("data", out var data) && data.ValueKind == JsonValueKind.Object)
            msg = TryGetErrorMessage(data);

        if (string.IsNullOrEmpty(msg))
            return;

        var code = TryGetErrorCode(root);
        if (code is null && root.TryGetProperty("data", out var data2) && data2.ValueKind == JsonValueKind.Object)
            code = TryGetErrorCode(data2);

        throw new XPlaneApiException(msg, (int)response.StatusCode, code, root.GetRawText());
    }

    private static JsonElement ParseJson(string json)
    {
        using var d = JsonDocument.Parse(json);
        return d.RootElement.Clone();
    }

    internal static string DecodeDatarefData(JsonElement value)
    {
        if (value.ValueKind is JsonValueKind.Null or JsonValueKind.Undefined)
            return "";
        if (value.ValueKind != JsonValueKind.String)
            throw new XPlaneApiException("Expected base64 string for X-Plane dataref value");
        var s = value.GetString();
        if (string.IsNullOrEmpty(s))
            return "";
        try
        {
            return Encoding.UTF8.GetString(Convert.FromBase64String(s));
        }
        catch (FormatException ex)
        {
            throw new XPlaneApiException("Failed to decode X-Plane dataref payload", inner: ex);
        }
    }
}

public readonly record struct XPlanePosition(double Latitude, double Longitude, double HeadingTrue);

public readonly record struct XPlaneAircraftModel(string Name, string Path);

public readonly record struct XPlaneLiveryInfo(string Name, string Path);

public readonly record struct XPlaneAircraftWithLiveries(string Name, string Path, IReadOnlyList<XPlaneLiveryInfo> Liveries);
