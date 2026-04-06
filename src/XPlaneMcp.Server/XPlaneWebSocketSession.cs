using System.Net.WebSockets;
using System.Runtime.CompilerServices;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace XPlaneMcp.Server;

/// <summary>Minimal WebSocket session for X-Plane streaming dataref updates.</summary>
public sealed class XPlaneWebSocketSession : IAsyncDisposable
{
    private readonly ClientWebSocket _ws = new();
    private int _reqId;

    public async Task ConnectAsync(XPlaneConfig config, CancellationToken cancellationToken = default)
    {
        if (_ws.State == WebSocketState.Open)
            return;
        var uri = new Uri(config.WebSocketUrl);
        await _ws.ConnectAsync(uri, cancellationToken).ConfigureAwait(false);
    }

    public async Task<int> SubscribeDatarefAsync(JsonElement datarefId, CancellationToken cancellationToken = default)
    {
        var id = Interlocked.Increment(ref _reqId);
        var root = new JsonObject
        {
            ["req_id"] = id,
            ["type"] = "dataref_subscribe_values",
            ["params"] = new JsonObject
            {
                ["datarefs"] = new JsonArray(new JsonObject { ["id"] = JsonNode.Parse(datarefId.GetRawText())! }),
            },
        };
        var json = root.ToJsonString();
        var bytes = Encoding.UTF8.GetBytes(json);
        await _ws.SendAsync(bytes, WebSocketMessageType.Text, endOfMessage: true, cancellationToken).ConfigureAwait(false);
        return id;
    }

    public async Task<JsonElement> ReceiveJsonAsync(CancellationToken cancellationToken = default)
    {
        var buffer = new ArraySegment<byte>(new byte[64 * 1024]);
        using var ms = new MemoryStream();
        WebSocketReceiveResult result;
        do
        {
            result = await _ws.ReceiveAsync(buffer, cancellationToken).ConfigureAwait(false);
            if (result.MessageType == WebSocketMessageType.Close)
                throw new XPlaneApiException("WebSocket closed before receiving a dataref update");
            ms.Write(buffer.Array!, buffer.Offset, result.Count);
        } while (!result.EndOfMessage);

        var text = Encoding.UTF8.GetString(ms.ToArray());
        using var doc = JsonDocument.Parse(text);
        return doc.RootElement.Clone();
    }

    public async IAsyncEnumerable<JsonElement> IterMessagesAsync([EnumeratorCancellation] CancellationToken cancellationToken = default)
    {
        while (true)
        {
            JsonElement msg;
            try
            {
                msg = await ReceiveJsonAsync(cancellationToken).ConfigureAwait(false);
            }
            catch (WebSocketException)
            {
                yield break;
            }
            yield return msg;
        }
    }

    public static async Task<JsonElement> WaitForDatarefUpdateAsync(
        XPlaneWebSocketSession ws,
        string datarefId,
        TimeSpan timeout,
        CancellationToken cancellationToken = default)
    {
        using var linked = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        linked.CancelAfter(timeout);
        try
        {
            await foreach (var message in ws.IterMessagesAsync(linked.Token).ConfigureAwait(false))
            {
                if (MessageMentionsDataref(message, datarefId))
                    return message;
            }
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        {
            throw new XPlaneApiException("Timed out waiting for WebSocket dataref update");
        }

        throw new XPlaneApiException("WebSocket closed before receiving a dataref update");
    }

    public static bool MessageMentionsDataref(JsonElement message, string datarefId)
    {
        if (!message.TryGetProperty("data", out var data) || data.ValueKind != JsonValueKind.Object)
            return false;
        foreach (var prop in data.EnumerateObject())
        {
            if (prop.Name == datarefId || prop.Name == datarefId.ToString())
                return true;
        }
        return data.TryGetProperty(datarefId, out _);
    }

    public async ValueTask DisposeAsync()
    {
        if (_ws.State is WebSocketState.Open or WebSocketState.CloseReceived or WebSocketState.CloseSent)
        {
            try
            {
                await _ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "done", CancellationToken.None).ConfigureAwait(false);
            }
            catch
            {
                // ignore
            }
        }

        _ws.Dispose();
    }
}
