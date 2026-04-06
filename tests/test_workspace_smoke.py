"""Non-integration smoke tests so default ``pytest`` (``-m \"not integration\"``) has tests to run in CI."""

from pathlib import Path

from mcp_stdio import default_mcp_server_argv


def test_default_mcp_server_argv_returns_none_or_list_without_crashing() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    argv = default_mcp_server_argv(repo_root)
    assert argv is None or (isinstance(argv, list) and len(argv) >= 1)
