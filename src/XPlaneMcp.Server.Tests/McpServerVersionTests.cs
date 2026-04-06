using System.Reflection;
using System.Text.Json;

namespace XPlaneMcp.Server.Tests;

public sealed class McpServerVersionTests
{
    [Fact]
    public void Server_assembly_exposes_non_empty_informational_version()
    {
        var asm = typeof(XPlaneMcpTools).Assembly;
        var informational = asm.GetCustomAttribute<AssemblyInformationalVersionAttribute>()?.InformationalVersion;
        Assert.False(string.IsNullOrWhiteSpace(informational));
    }

    [Fact]
    public void GetMcpServerVersion_returns_valid_json_matching_assembly()
    {
        var tools = new XPlaneMcpTools(null!);
        var json = tools.GetMcpServerVersion();
        using var doc = JsonDocument.Parse(json);
        var root = doc.RootElement;
        Assert.Equal("xplane-ai-mcp", root.GetProperty("name").GetString());
        Assert.False(string.IsNullOrWhiteSpace(root.GetProperty("version").GetString()));
        var asmName = typeof(XPlaneMcpTools).Assembly.GetName().Name;
        Assert.Equal(asmName, root.GetProperty("assembly").GetString());
    }
}
