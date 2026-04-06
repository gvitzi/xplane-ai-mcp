using System.Net;
using System.Text;
using System.Text.Json;

namespace XPlaneMcp.Server.Tests;

public sealed class XPlaneRestClientTests
{
    private static string? GetQueryParam(Uri uri, string key)
    {
        var query = uri.Query.TrimStart('?');
        foreach (var part in query.Split('&', StringSplitOptions.RemoveEmptyEntries))
        {
            var eq = part.IndexOf('=');
            if (eq <= 0)
                continue;
            var k = Uri.UnescapeDataString(part[..eq]);
            if (k == key)
                return Uri.UnescapeDataString(part[(eq + 1)..]);
        }

        return null;
    }

    private sealed class StubHandler(Func<HttpRequestMessage, HttpResponseMessage> onSend) : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken) =>
            Task.FromResult(onSend(request));
    }

    private static XPlaneRestClient CreateClient(HttpMessageHandler handler, XPlaneConfig? config = null)
    {
        var cfg = config ?? new XPlaneConfig();
        var http = new HttpClient(handler) { BaseAddress = cfg.RestBaseUri };
        return new XPlaneRestClient(http, cfg, ownsClient: true);
    }

    [Fact]
    public async Task GetCapabilities_uses_unversioned_endpoint()
    {
        using var client = CreateClient(new StubHandler(req =>
        {
            Assert.Equal("http://127.0.0.1:8086/api/capabilities", req.RequestUri!.ToString());
            return new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent("""{"data":{"api_versions":["v2","v3"]}}""", Encoding.UTF8, "application/json"),
            };
        }));

        var payload = await client.GetCapabilitiesAsync();
        Assert.Equal(JsonValueKind.Array, payload.GetProperty("data").GetProperty("api_versions").ValueKind);
    }

    [Fact]
    public async Task FindDataref_queries_v3_datarefs_with_filter()
    {
        using var client = CreateClient(new StubHandler(req =>
        {
            Assert.Equal("/api/v3/datarefs", req.RequestUri!.AbsolutePath);
            Assert.Equal("sim/test/value", GetQueryParam(req.RequestUri!, "filter[name]"));
            Assert.Equal("id,name,value_type", GetQueryParam(req.RequestUri!, "fields"));
            return new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent(
                    """{"data":[{"id":42,"name":"sim/test/value","value_type":"float"}]}""",
                    Encoding.UTF8,
                    "application/json"),
            };
        }));

        var dr = await client.FindDatarefAsync("sim/test/value");
        Assert.Equal(42, dr.GetProperty("id").GetInt32());
    }

    [Fact]
    public async Task ListDatarefs_uses_limit_param()
    {
        using var client = CreateClient(new StubHandler(req =>
        {
            Assert.Equal("/api/v3/datarefs", req.RequestUri!.AbsolutePath);
            Assert.Equal("1", GetQueryParam(req.RequestUri!, "limit"));
            return new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent(
                    """{"data":[{"id":1,"name":"sim/test/first","value_type":"int"}]}""",
                    Encoding.UTF8,
                    "application/json"),
            };
        }));

        var list = await client.ListDatarefsAsync(limit: 1);
        Assert.Single(list);
        Assert.Equal("sim/test/first", list[0].GetProperty("name").GetString());
    }

    [Fact]
    public async Task StartFlight_posts_data_envelope()
    {
        using var client = CreateClient(new StubHandler(req =>
        {
            Assert.Equal(HttpMethod.Post, req.Method);
            Assert.Equal("/api/v3/flight", req.RequestUri!.AbsolutePath);
            var body = req.Content!.ReadAsStringAsync().Result;
            Assert.Equal("""{"data":{"airport":"EDDB","ramp":"A12"}}""", body);
            return new HttpResponseMessage(HttpStatusCode.OK) { Content = new StringContent("", Encoding.UTF8, "application/json") };
        }));

        using var flight = JsonDocument.Parse("""{"airport":"EDDB","ramp":"A12"}""");
        var payload = await client.StartFlightAsync(flight.RootElement);
        Assert.True(payload.TryGetProperty("data", out var d) && d.ValueKind == JsonValueKind.Null);
    }

    [Fact]
    public async Task ParseResponse_maps_error_json_to_exception()
    {
        using var resp = new HttpResponseMessage(HttpStatusCode.BadRequest)
        {
            Content = new StringContent("""{"error_message":"nope","error_code":"E1"}""", Encoding.UTF8, "application/json"),
        };
        var ex = await Assert.ThrowsAsync<XPlaneApiException>(() =>
            XPlaneRestClient.ParseResponseAsync(resp, allowEmpty: false, CancellationToken.None));
        Assert.Equal(400, ex.StatusCode);
        Assert.Equal("E1", ex.ErrorCode);
        Assert.Contains("nope", ex.Message, StringComparison.Ordinal);
    }

    [Fact]
    public async Task ParseResponse_throws_on_success_http_when_error_message_present()
    {
        using var resp = new HttpResponseMessage(HttpStatusCode.OK)
        {
            Content = new StringContent(
                """{"error_message":"invalid flight init","error_code":2}""",
                Encoding.UTF8,
                "application/json"),
        };
        var ex = await Assert.ThrowsAsync<XPlaneApiException>(() =>
            XPlaneRestClient.ParseResponseAsync(resp, allowEmpty: true, CancellationToken.None));
        Assert.Equal(200, ex.StatusCode);
        Assert.Equal("2", ex.ErrorCode);
        Assert.Contains("invalid flight init", ex.Message, StringComparison.Ordinal);
    }

    [Fact]
    public void DecodeDatarefData_decodes_base64_utf8()
    {
        var b64 = Convert.ToBase64String(Encoding.UTF8.GetBytes("Aircraft/Test.acf"));
        using var doc = JsonDocument.Parse($$"""{"data":"{{b64}}"}""");
        var s = XPlaneRestClient.DecodeDatarefData(doc.RootElement.GetProperty("data"));
        Assert.Equal("Aircraft/Test.acf", s);
    }

    [Fact]
    public void ListAircraftLiveries_returns_empty_when_xplane_root_unset()
    {
        var cfg = new XPlaneConfig();
        using var http = new HttpClient(new StubHandler(_ => throw new InvalidOperationException())) { BaseAddress = cfg.RestBaseUri };
        using var client = new XPlaneRestClient(http, cfg, ownsClient: true);
        Assert.Empty(client.ListAircraftLiveries());
    }

    [Fact]
    public void ListAircraftLiveries_finds_livery_folders_and_filters_by_acf_path()
    {
        var tmp = Directory.CreateTempSubdirectory("xplane_liv_");
        try
        {
            var acfDir = Path.Combine(tmp.FullName, "Aircraft", "Mfr", "My Plane");
            Directory.CreateDirectory(Path.Combine(acfDir, "liveries", "N100"));
            Directory.CreateDirectory(Path.Combine(acfDir, "liveries", "N200"));
            File.WriteAllText(Path.Combine(acfDir, "My_Plane.acf"), "");
            var bare = Path.Combine(tmp.FullName, "Aircraft", "Solo");
            Directory.CreateDirectory(bare);
            File.WriteAllText(Path.Combine(bare, "Solo.acf"), "");

            var cfg = new XPlaneConfig(XPlaneRoot: tmp.FullName);
            using var http = new HttpClient(new StubHandler(_ => throw new InvalidOperationException())) { BaseAddress = cfg.RestBaseUri };
            using var client = new XPlaneRestClient(http, cfg, ownsClient: true);

            var all = client.ListAircraftLiveries(null);
            Assert.Equal(2, all.Count);
            var my = Assert.Single(all, a => a.Path.EndsWith("My_Plane.acf", StringComparison.OrdinalIgnoreCase));
            Assert.Equal("My Plane", my.Name);
            Assert.Equal(2, my.Liveries.Count);
            Assert.Contains(my.Liveries, l => l.Name == "N100");
            Assert.Contains(my.Liveries, l => l.Name == "N200");
            Assert.All(my.Liveries, l => Assert.StartsWith("Aircraft/", l.Path, StringComparison.Ordinal));

            var solo = Assert.Single(all, a => a.Path.EndsWith("Solo.acf", StringComparison.OrdinalIgnoreCase));
            Assert.Empty(solo.Liveries);

            var filtered = client.ListAircraftLiveries(@"Aircraft\Mfr\My Plane\My_Plane.acf");
            var one = Assert.Single(filtered);
            Assert.Equal(2, one.Liveries.Count);

            Assert.Empty(client.ListAircraftLiveries("Aircraft/Missing.acf"));
        }
        finally
        {
            tmp.Delete(true);
        }
    }
}
