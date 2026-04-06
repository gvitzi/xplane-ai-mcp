namespace XPlaneMcp.Server;

public sealed class XPlaneApiException : Exception
{
    public int? StatusCode { get; }
    public string? ErrorCode { get; }
    public string? ResponseBody { get; }

    public XPlaneApiException(string message, int? statusCode = null, string? errorCode = null, string? responseBody = null, Exception? inner = null)
        : base(ComposeMessage(message, statusCode, errorCode, responseBody), inner)
    {
        StatusCode = statusCode;
        ErrorCode = errorCode;
        ResponseBody = responseBody;
    }

    private static string ComposeMessage(string message, int? statusCode, string? errorCode, string? responseBody)
    {
        var parts = new List<string> { message };
        if (statusCode is int sc)
            parts.Add($"HTTP {sc}");
        if (!string.IsNullOrEmpty(errorCode))
            parts.Add($"error_code={errorCode}");
        if (!string.IsNullOrEmpty(responseBody))
        {
            const int max = 8000;
            var body = responseBody.Length > max ? responseBody[..max] + "…[truncated]" : responseBody;
            parts.Add($"response={body}");
        }

        return string.Join(" | ", parts);
    }
}
