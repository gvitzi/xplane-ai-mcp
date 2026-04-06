"""Unit tests for MCP stdio newline framing (no subprocess)."""

from __future__ import annotations

import io
import json

from mcp_stdio import encode_message, read_one_message


def test_mcp_ndjson_roundtrip() -> None:
    msg = {"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}
    raw = encode_message(msg)
    out = read_one_message(io.BytesIO(raw))
    assert out == msg


def test_mcp_ndjson_skips_blank_lines() -> None:
    line = json.dumps({"jsonrpc": "2.0", "id": 2}, separators=(",", ":"))
    raw = b"\n\n" + line.encode("utf-8") + b"\n"
    out = read_one_message(io.BytesIO(raw))
    assert out["id"] == 2
