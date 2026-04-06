"""Minimal MCP client over stdio (newline-delimited JSON, MCP 2024-11-05 stdio transport)."""

from __future__ import annotations

import json
import os
import subprocess
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any


class McpJsonRpcError(RuntimeError):
    def __init__(self, error: Mapping[str, Any]) -> None:
        self.error = dict(error)
        code = error.get("code")
        msg = error.get("message", "")
        super().__init__(f"MCP JSON-RPC error {code}: {msg}")


class McpToolError(RuntimeError):
    """Tool finished with ``isError`` or no textual content."""


def encode_message(obj: dict[str, Any]) -> bytes:
    """One MCP message as a single line (no embedded newlines in JSON)."""
    line = json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n"
    return line.encode("utf-8")


def read_one_message(stream: Any) -> dict[str, Any]:
    """Read one newline-delimited JSON object from a binary stream."""
    raw = stream.readline()
    if not raw:
        raise EOFError("unexpected EOF while reading MCP message line")
    line = raw.decode("utf-8").strip()
    if not line:
        return read_one_message(stream)
    return json.loads(line)


def default_mcp_server_argv(repo_root: Path) -> list[str] | None:
    """Prefer ``bin/Release`` (latest ``dotnet build``), then Debug, published artifacts, then ``dotnet`` + DLL."""
    candidates: list[Path] = []
    if os.name == "nt":
        candidates.extend(
            [
                repo_root / "src/XPlaneMcp.Server/bin/Release/net9.0/xplaneMCP.exe",
                repo_root / "src/XPlaneMcp.Server/bin/Debug/net9.0/xplaneMCP.exe",
                repo_root / "artifacts/xplane-mcp/xplaneMCP.exe",
            ]
        )
    else:
        candidates.extend(
            [
                repo_root / "src/XPlaneMcp.Server/bin/Release/net9.0/xplaneMCP",
                repo_root / "src/XPlaneMcp.Server/bin/Debug/net9.0/xplaneMCP",
                repo_root / "artifacts/xplane-mcp/xplaneMCP",
            ]
        )
    for exe in candidates:
        if exe.is_file():
            return [str(exe)]
    dll = repo_root / "src/XPlaneMcp.Server/bin/Release/net9.0/xplaneMCP.dll"
    if not dll.is_file():
        dll = repo_root / "src/XPlaneMcp.Server/bin/Debug/net9.0/xplaneMCP.dll"
    if dll.is_file():
        return ["dotnet", str(dll)]
    return None


@dataclass(frozen=True)
class McpServerLaunch:
    argv: list[str]
    cwd: Path
    env: dict[str, str]


class McpStdioSession:
    """One JSON-RPC client session over a running MCP server process."""

    def __init__(self, proc: subprocess.Popen[bytes]) -> None:
        self._proc = proc
        self._stdin = proc.stdin
        self._stdout = proc.stdout
        if self._stdin is None or self._stdout is None:
            raise RuntimeError("Popen must use pipes for stdin/stdout")
        self._write_lock = threading.Lock()
        self._read_lock = threading.Lock()
        self._next_id = 1

    def _next_request_id(self) -> int:
        rid = self._next_id
        self._next_id += 1
        return rid

    def _write(self, obj: dict[str, Any]) -> None:
        data = encode_message(obj)
        with self._write_lock:
            self._stdin.write(data)
            self._stdin.flush()

    def _read_result_for_id(self, want_id: int) -> Any:
        with self._read_lock:
            while True:
                msg = read_one_message(self._stdout)
                if msg.get("id") != want_id:
                    # Notifications and unrelated responses (e.g. server logging as MCP — should not happen)
                    continue
                if "error" in msg:
                    raise McpJsonRpcError(msg["error"])
                return msg.get("result")

    def initialize(self) -> dict[str, Any]:
        req_id = self._next_request_id()
        self._write(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest-xplane-mcp", "version": "0"},
                },
            }
        )
        result = self._read_result_for_id(req_id)
        if not isinstance(result, dict):
            raise RuntimeError(f"initialize: expected object result, got {type(result)}")
        self._write({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return result

    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        req_id = self._next_request_id()
        self._write(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        result = self._read_result_for_id(req_id)
        if not isinstance(result, dict):
            raise McpToolError(f"tools/call: expected object result, got {result!r}")
        if result.get("isError"):
            parts = self._text_blocks(result)
            msg = "\n".join(parts) if parts else json.dumps(result)
            raise McpToolError(msg)
        parts = self._text_blocks(result)
        if parts:
            return "\n".join(parts)
        structured = result.get("structuredContent")
        if structured is not None:
            return json.dumps(structured, ensure_ascii=False)
        raise McpToolError(f"no text or structured content in tool result: {result!r}")

    @staticmethod
    def _text_blocks(result: dict[str, Any]) -> list[str]:
        out: list[str] = []
        for block in result.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "text":
                t = block.get("text")
                if t:
                    out.append(str(t))
        return out

    def close(self) -> None:
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc.stdout.close()  # type: ignore[union-attr]
        self._proc.stdin.close()  # type: ignore[union-attr]

    def __enter__(self) -> McpStdioSession:
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: TracebackType | None,
    ) -> None:
        self.close()


def start_mcp_session(launch: McpServerLaunch) -> McpStdioSession:
    proc = subprocess.Popen(
        launch.argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=launch.env,
        cwd=str(launch.cwd),
        bufsize=0,
    )
    session = McpStdioSession(proc)
    session.initialize()
    return session


def decode_xplane_dataref_string(value: Any) -> str:
    """Decode base64 UTF-8 payload from X-Plane Web API ``data`` field."""
    import base64

    if value in (None, ""):
        return ""
    if not isinstance(value, str):
        raise ValueError(f"expected base64 string from X-Plane, got {type(value)}")
    return base64.b64decode(value).decode("utf-8")
