// Immediate custom action: fill CODEX_CONFIG_SNIPPET with real paths (no WiX escape sequences).
function SetSnippet() {
    var folder = Session.Property("INSTALLFOLDER");
    if (!folder || folder.length === 0) {
        return 1;
    }
    var exePath = folder;
    if (exePath.charAt(exePath.length - 1) !== "\\") {
        exePath += "\\";
    }
    exePath += "xplaneMCP.exe";
    var lit = exePath.replace(/'/g, "''");
    var text = "[mcp_servers.xplaneMCP]\r\n";
    text += "command = '" + lit + "'\r\n";
    text += "args = []\r\n";
    text += "enabled = true\r\n\r\n";
    text += "# Optional:\r\n";
    text += "# env = { XPLANE_HOST = \"127.0.0.1\", XPLANE_PORT = \"8086\" }";
    Session.Property("CODEX_CONFIG_SNIPPET") = text;
    return 1;
}
