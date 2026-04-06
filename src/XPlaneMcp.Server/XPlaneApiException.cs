namespace XPlaneMcp.Server;

public sealed class XPlaneApiException : Exception
{
    public int? StatusCode { get; }
    public string? ErrorCode { get; }
    public string? ResponseBody { get; }

    public XPlaneApiException(string message, int? statusCode = null, string? errorCode = null, string? responseBody = null, Exception? inner = null)
        : base(message, inner)
    {
        StatusCode = statusCode;
        ErrorCode = errorCode;
        ResponseBody = responseBody;
    }
}
