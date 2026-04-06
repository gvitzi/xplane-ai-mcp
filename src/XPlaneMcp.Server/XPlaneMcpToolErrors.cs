using System.Net.Http;
using System.Text.Json;

namespace XPlaneMcp.Server;

/// <summary>Formats exceptions for <c>McpException</c> so MCP clients receive detailed tool errors (the C# MCP SDK hides other exception types).</summary>
internal static class XPlaneMcpToolErrors
{
    public static string Format(Exception ex)
    {
        ex = Unwrap(ex);

        return ex switch
        {
            XPlaneApiException x => FormatXPlane(x),
            HttpRequestException h => $"X-Plane HTTP request failed: {h.Message}",
            TaskCanceledException => "X-Plane request timed out or was canceled. Check that X-Plane is running, the Web API is enabled, XPLANE_HOST/XPLANE_PORT, and firewall settings.",
            JsonException j => $"Invalid JSON in tool arguments: {j.Message}",
            InvalidOperationException or ArgumentException => ex.Message,
            _ => $"{ex.GetType().Name}: {ex.Message}",
        };
    }

    private static Exception Unwrap(Exception ex)
    {
        if (ex is AggregateException agg)
        {
            agg = agg.Flatten();
            if (agg.InnerExceptions.Count == 1)
                return Unwrap(agg.InnerExceptions[0]);
        }

        return ex;
    }

    private static string FormatXPlane(XPlaneApiException x)
    {
        // Message already includes HTTP status, error_code, and a truncated response from XPlaneApiException.
        if (x.InnerException is not { } inner || inner is XPlaneApiException)
            return x.Message;
        return x.Message + Environment.NewLine + "Caused by: " + inner.GetType().Name + ": " + inner.Message;
    }
}
