namespace XPlaneMcp.Server;

public sealed record XPlaneConfig(
    string Host = "127.0.0.1",
    int Port = 8086,
    double TimeoutSeconds = 5.0,
    string? XPlaneRoot = null)
{
    public string CapabilitiesUrl => $"http://{Host}:{Port}/api/capabilities";

    /// <summary>Base URL for API v3 REST calls, without trailing slash.</summary>
    public string RestBaseUrl => $"http://{Host}:{Port}/api/v3";

    public string WebSocketUrl => $"ws://{Host}:{Port}/api/v3";

    /// <summary>HttpClient BaseAddress must use a trailing slash so relative "datarefs" resolves to /api/v3/datarefs.</summary>
    public Uri RestBaseUri => new(RestBaseUrl.TrimEnd('/') + "/", UriKind.Absolute);

    public static XPlaneConfig FromEnvironment()
    {
        var host = Environment.GetEnvironmentVariable("XPLANE_HOST") ?? "127.0.0.1";
        var port = int.TryParse(Environment.GetEnvironmentVariable("XPLANE_PORT"), out var p) ? p : 8086;
        var timeout = double.TryParse(Environment.GetEnvironmentVariable("XPLANE_TIMEOUT"), System.Globalization.NumberStyles.Float,
            System.Globalization.CultureInfo.InvariantCulture, out var t) ? t : 5.0;
        var root = Environment.GetEnvironmentVariable("XPLANE_ROOT");
        return new XPlaneConfig(host, port, timeout, string.IsNullOrWhiteSpace(root) ? null : root.Trim());
    }
}
