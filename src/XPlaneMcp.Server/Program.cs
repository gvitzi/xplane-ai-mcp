using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using ModelContextProtocol.Server;
using XPlaneMcp.Server;

var builder = Host.CreateApplicationBuilder(args);
builder.Logging.AddConsole(o => o.LogToStandardErrorThreshold = LogLevel.Trace);

builder.Services.AddSingleton(XPlaneConfig.FromEnvironment());
builder.Services.AddSingleton(sp =>
{
    var cfg = sp.GetRequiredService<XPlaneConfig>();
    var handler = new HttpClientHandler();
    var client = new HttpClient(handler, disposeHandler: true)
    {
        BaseAddress = cfg.RestBaseUri,
        Timeout = TimeSpan.FromSeconds(Math.Max(1, cfg.TimeoutSeconds)),
    };
    client.DefaultRequestHeaders.Accept.ParseAdd("application/json");
    return new XPlaneRestClient(client, cfg, ownsClient: true);
});
builder.Services.AddSingleton<XPlaneMcpService>();

builder.Services
    .AddMcpServer()
    .WithStdioServerTransport()
    .WithTools<XPlaneMcpTools>();

await builder.Build().RunAsync().ConfigureAwait(false);
