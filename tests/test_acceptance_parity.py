"""Issue #10: outcome parity of the installed console over stdio and Streamable HTTP.

The same console binary serves the same synthetic inventory once over stdio and once
over loopback Streamable HTTP. Every case asserts the MCP result invariants
(``text == structuredContent``, ``isError == !ok``), stdio/HTTP equality and the exact
number of requests the synthetic loopback device received. Also covers the default
HTTP binding (MCP-03) without opening a socket.

Only ``127.0.0.1`` is contacted. No LAN device, no wall-clock sleep for synchronization.
"""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

import anyio
import httpx2 as httpx
import pytest
from mcp import MCPError
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters
from mcp.client.streamable_http import streamable_http_client

from tests.acceptance_support import LoopbackWLED, PostMode
from tests.envelopes import comparable_record
from tests.test_http_cli import CONSOLE, TOKEN, clean_env, console, free_port, wait_ready
from tests.tool_contract import expected_names

DESK = "desk"


def write_inventory(directory: Path, fake: LoopbackWLED) -> Path:
    config = directory / "service.toml"
    config.write_text(
        "schema_version = 1\n"
        "[http]\noperation_timeout_seconds = 3\nread_retries = 1\n"
        "[[devices]]\n"
        f'id = "{DESK}"\nname = "Example desk"\nbase_url = "{fake.base_url}"\n',
        encoding="utf-8",
    )
    return config


# name -> (tool, arguments, fake POST mode, expected POSTs, expect zero device requests)
CASES: dict[str, tuple[str, dict[str, Any], PostMode, int, bool]] = {
    "segment_names_preview": (
        "wled_patch_segments",
        {
            "device_id": DESK,
            "segments": [{"id": 2, "effect_name": "wipe", "palette_name": "Party"}],
            "dry_run": True,
        },
        "apply",
        0,
        False,
    ),
    "segment_name_unknown": (
        "wled_replace_layout",
        {"device_id": DESK, "segments": [{"id": 0, "start": 0, "stop": 10, "effect_name": "wi"}]},
        "apply",
        0,
        False,
    ),
    "read_success": ("wled_get_state", {"device_id": DESK}, "apply", 0, False),
    "write_verified": ("wled_set_state", {"device_id": DESK, "on": False}, "apply", 1, False),
    "schema_wrong_type": (
        "wled_set_state",
        {"device_id": DESK, "brightness": "255"},
        "apply",
        0,
        True,
    ),
    "schema_extra_field": (
        "wled_set_state",
        {"device_id": DESK, "on": True, "unknown_field": 1},
        "apply",
        0,
        True,
    ),
    "domain_transition_1_49": (
        "wled_set_state",
        {"device_id": DESK, "on": False, "transition_ms": 25},
        "apply",
        0,
        False,
    ),
    "domain_on_with_zero_brightness": (
        "wled_set_state",
        {"device_id": DESK, "on": True, "brightness": 0},
        "apply",
        0,
        False,
    ),
    "unknown_device": ("wled_get_state", {"device_id": "absent"}, "apply", 0, True),
    "verification_mismatch": (
        "wled_patch_segments",
        {"device_id": DESK, "segments": [{"id": 2, "speed": 0}]},
        "ack_only",
        1,
        False,
    ),
    "write_outcome_unknown": (
        "wled_set_state",
        {"device_id": DESK, "on": False},
        "reset",
        1,
        False,
    ),
}

EXPECTED_CODE = {
    "segment_names_preview": None,
    "segment_name_unknown": "VALIDATION_ERROR",
    "read_success": None,
    "write_verified": None,
    "schema_wrong_type": "VALIDATION_ERROR",
    "schema_extra_field": "VALIDATION_ERROR",
    "domain_transition_1_49": "VALIDATION_ERROR",
    "domain_on_with_zero_brightness": "VALIDATION_ERROR",
    "unknown_device": "UNKNOWN_DEVICE",
    "verification_mismatch": "VERIFICATION_MISMATCH",
    "write_outcome_unknown": "WRITE_OUTCOME_UNKNOWN",
}


async def run_cases(client: Client, fake: LoopbackWLED) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for name, (tool, arguments, mode, _posts, _zero) in CASES.items():
        fake.reset(mode)
        result = await client.call_tool(tool, arguments)
        assert len(result.content) == 1 and result.content[0].type == "text", name
        records[name] = {
            "text": json.loads(result.content[0].text),
            "structured": result.structured_content,
            "is_error": result.is_error,
            "posts": fake.count("POST"),
            "requests": fake.count(),
            "bodies": list(fake.posts),
        }
    fake.reset()
    with pytest.raises(MCPError) as caught:
        await client.call_tool("wled_absent_tool", {})
    records["unknown_tool"] = {"protocol_error": caught.value.code, "requests": fake.count()}
    return records


async def over_stdio(config: Path, data: Path, fake: LoopbackWLED) -> dict[str, dict[str, Any]]:
    params = StdioServerParameters(
        command=str(CONSOLE), cwd=data, args=["--config", str(config), "--data-dir", str(data)]
    )
    with anyio.fail_after(120):
        async with Client(params, mode="legacy", read_timeout_seconds=30) as client:
            return await run_cases(client, fake)


async def over_http(port: int, fake: LoopbackWLED) -> dict[str, dict[str, Any]]:
    with anyio.fail_after(120):
        async with httpx.AsyncClient(headers={"Authorization": f"Bearer {TOKEN}"}) as http:
            transport = streamable_http_client(
                f"http://127.0.0.1:{port}/mcp", http_client=http, terminate_on_close=False
            )
            async with Client(transport, mode="legacy", read_timeout_seconds=30) as client:
                return await run_cases(client, fake)


def http_args(port: int) -> list[str]:
    return ["--transport", "streamable-http", "--port", str(port)] + [
        "--allowed-host",
        f"127.0.0.1:{port}",
    ]


@pytest.fixture(scope="module")
def fake() -> Iterator[LoopbackWLED]:
    device = LoopbackWLED()
    try:
        yield device
    finally:
        device.close()


@pytest.fixture(scope="module")
def outcomes(
    tmp_path_factory: pytest.TempPathFactory, fake: LoopbackWLED
) -> dict[str, dict[str, dict[str, Any]]]:
    stdio_dir = tmp_path_factory.mktemp("parity-stdio")
    stdio = anyio.run(over_stdio, write_inventory(stdio_dir, fake), stdio_dir, fake)
    http_dir = tmp_path_factory.mktemp("parity-http")
    config = write_inventory(http_dir, fake)
    port = free_port()
    env = clean_env(WLED_MCP_HTTP_TOKEN=TOKEN)
    with console(config, http_dir, *http_args(port), env=env) as (process, lines):
        wait_ready(lines, port)
        http = anyio.run(over_http, port, fake)
        assert process.poll() is None
        # Signal semantics are not under test here; the context manager kills the process.
    return {"stdio": stdio, "http": http}


@pytest.mark.parametrize("name", list(CASES))
@pytest.mark.parametrize("transport", ["stdio", "http"])
def test_text_fallback_equals_structured_and_is_error_equals_not_ok(outcomes, transport, name):
    record = outcomes[transport][name]
    envelope = record["structured"]
    assert envelope is not None
    assert record["text"] == envelope
    assert record["is_error"] is (not envelope["ok"])
    code = EXPECTED_CODE[name]
    if code is None:
        assert envelope["ok"] is True and envelope["error"] is None
    else:
        assert envelope["ok"] is False and envelope["error"]["code"] == code


@pytest.mark.parametrize("name", list(CASES))
@pytest.mark.parametrize("transport", ["stdio", "http"])
def test_device_requests_match_the_outcome_and_writes_are_never_replayed(outcomes, transport, name):
    record = outcomes[transport][name]
    _tool, _arguments, _mode, posts, zero = CASES[name]
    assert record["posts"] == posts
    if zero:
        assert record["requests"] == 0
    if name in {"write_verified", "write_outcome_unknown"}:
        assert record["bodies"] == [{"on": False}]


def mask_volatile(record: dict[str, Any]) -> dict[str, Any]:
    """Replace the volatile fields (a state read's ``read_at``, the per-call correlation ID)."""
    masked = comparable_record(record)
    for key in ("text", "structured"):
        envelope = masked.get(key)
        freshness = (envelope or {}).get("data", {}).get("freshness") or {}
        if "read_at" in freshness:
            assert datetime.fromisoformat(freshness["read_at"]).tzinfo is not None
            freshness["read_at"] = "<read_at>"
    return masked


@pytest.mark.parametrize("name", list(CASES))
def test_stdio_and_http_return_identical_results(outcomes, name):
    assert mask_volatile(outcomes["stdio"][name]) == mask_volatile(outcomes["http"][name])


def test_outcome_axes_for_mismatch_and_uncertain_writes(outcomes):
    for transport in ("stdio", "http"):
        mismatch = outcomes[transport]["verification_mismatch"]["structured"]
        assert (mismatch["application"], mismatch["verification"]) == ("unknown", "mismatch")
        unknown = outcomes[transport]["write_outcome_unknown"]["structured"]
        assert (unknown["application"], unknown["verification"]) == ("unknown", "unknown")
        assert unknown["error"]["write_retryable"] is False
        verified = outcomes[transport]["write_verified"]["structured"]
        assert (verified["application"], verified["verification"]) == ("applied", "verified")


def test_unknown_tool_is_a_protocol_error_on_both_transports(outcomes):
    stdio, http = outcomes["stdio"]["unknown_tool"], outcomes["http"]["unknown_tool"]
    assert stdio == http
    assert isinstance(stdio["protocol_error"], int) and stdio["protocol_error"] < 0
    assert stdio["requests"] == 0


# ============================================================ real console access control


def test_real_console_rejects_missing_credential_and_disallowed_host_before_device_work(
    tmp_path,
):
    fake = LoopbackWLED()
    try:
        config = write_inventory(tmp_path, fake)
        port = free_port()
        env = clean_env(WLED_MCP_HTTP_TOKEN=TOKEN)
        call = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "wled_set_state", "arguments": {"device_id": DESK, "on": False}},
        }
        headers = {"Accept": "application/json, text/event-stream"}
        url = f"http://127.0.0.1:{port}/mcp"
        with console(config, tmp_path, *http_args(port), env=env) as (process, lines):
            wait_ready(lines, port)
            with httpx.Client(timeout=10) as http:
                missing = http.post(url, json=call, headers=headers)
                wrong = http.post(
                    url, json=call, headers={**headers, "Authorization": "Bearer " + "x" * 40}
                )
                bad_host = http.post(
                    url,
                    json=call,
                    headers={
                        **headers,
                        "Authorization": f"Bearer {TOKEN}",
                        "Host": "attacker.example:8000",
                    },
                )
            assert process.poll() is None
        assert (missing.status_code, wrong.status_code, bad_host.status_code) == (401, 401, 403)
        for response in (missing, wrong, bad_host):
            assert TOKEN not in response.text
        assert fake.count() == 0, "no device request before access control passes"
    finally:
        fake.close()


# ============================================================ default HTTP binding (MCP-03)


def test_default_http_binding_is_loopback_8000_with_exact_default_hosts():
    from wled_mcp.http_config import load_http_settings

    settings = load_http_settings(
        host=None,
        port=None,
        allowed_hosts=[],
        allowed_origins=[],
        token_file=None,
        operation_timeout_seconds=10,
        environ={"WLED_MCP_HTTP_TOKEN": TOKEN},
    )
    assert (settings.host, settings.port) == ("127.0.0.1", 8000)
    assert settings.allowed_hosts == frozenset({"127.0.0.1:8000", "localhost:8000"})
    assert settings.allowed_origins == frozenset()
    assert TOKEN not in repr(settings)


def test_console_without_bind_options_selects_the_default_binding_and_binds_nothing(
    tmp_path, monkeypatch
):
    from wled_mcp import cli

    captured: list[Any] = []

    def capture(function: Any, *args: Any) -> None:
        captured.append(args)

    def refuse_bind(self: socket.socket, address: Any) -> None:
        raise AssertionError(f"no socket may be bound: {address!r}")

    for key in [k for k in os.environ if k.startswith("WLED_MCP_")]:
        monkeypatch.delenv(key)
    monkeypatch.setenv("WLED_MCP_HTTP_TOKEN", TOKEN)
    monkeypatch.setattr(cli.anyio, "run", capture)
    monkeypatch.setattr(socket.socket, "bind", refuse_bind)
    config = tmp_path / "bootstrap.toml"
    config.write_text("schema_version = 1\ndevices = []\n", encoding="utf-8")
    code = cli.main(
        ["--config", str(config), "--data-dir", str(tmp_path), "--transport", "streamable-http"]
    )
    assert code == 0
    ((_config, settings, _writable),) = captured
    assert (settings.host, settings.port) == ("127.0.0.1", 8000)
    assert settings.allowed_hosts == frozenset({"127.0.0.1:8000", "localhost:8000"})


def test_parity_cases_never_use_a_non_loopback_device(tmp_path):
    """Guard for the fixture itself: the synthetic device URL is loopback only."""
    fake = LoopbackWLED()
    try:
        assert fake.base_url.startswith("http://127.0.0.1:")
        assert "127.0.0.1" in write_inventory(tmp_path, fake).read_text(encoding="utf-8")
    finally:
        fake.close()


# ============================================================ documented commands (T16)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


ROOT = Path(__file__).resolve().parents[1]
FLAG = re.compile(r"--[a-z][a-z-]*")


# Subcommand words of the console (#16). A documented flag is checked against the help
# of the command it is written after, so a subcommand flag cannot hide a serve flag.
SUBCOMMAND_WORDS = frozenset({"config", "init", "add-device", "validate", "doctor"})


def documented_console_commands(text: str) -> dict[tuple[str, ...], set[str]]:
    """Flags after a ``wled-mcp`` command word, grouped by the subcommand path written."""
    snippets = re.findall(r"```[^\n]*\n(.*?)```", text, flags=re.S)
    snippets += re.findall(r"`([^`\n]*\bwled-mcp [^`\n]*)`", text)
    found: dict[tuple[str, ...], set[str]] = {}
    for snippet in snippets:
        for line in re.sub(r"\\[ \t]*\n", " ", snippet).splitlines():  # join continuations
            tokens = line.split()
            if "wled-mcp" in tokens:
                after = tokens[tokens.index("wled-mcp") + 1 :]
                path: list[str] = []
                while after and after[0] in SUBCOMMAND_WORDS:
                    path.append(after.pop(0))
                flags = found.setdefault(tuple(path), set())
                flags.update(m.group() for t in after if (m := FLAG.fullmatch(t)))
    return found


def documented_console_flags(text: str) -> set[str]:
    """Flags written after a ``wled-mcp`` command word in code blocks and inline code."""
    return set().union(*documented_console_commands(text).values())


def console_help_flags(*command: str) -> set[str]:
    result = subprocess.run(
        [str(CONSOLE), *command, "--help"],
        capture_output=True,
        text=True,
        timeout=30,
        env=clean_env(),
        stdin=subprocess.DEVNULL,
    )
    assert result.returncode == 0, result.stderr
    return set(FLAG.findall(result.stdout))


def test_documented_console_flags_exist_in_the_installed_console():
    accepted = console_help_flags()
    deployment = documented_console_flags((ROOT / "docs/DEPLOYMENT.md").read_text("utf-8"))
    development = documented_console_flags((ROOT / "docs/DEVELOPMENT.md").read_text("utf-8"))
    # The HTTP service command and the local commands really were found.
    assert {"--transport", "--host", "--port", "--allowed-host", "--http-token-file"} <= deployment
    assert {"--config", "--data-dir", "--transport"} <= development
    for name in ("DEPLOYMENT.md", "DEVELOPMENT.md"):
        commands = documented_console_commands((ROOT / "docs" / name).read_text("utf-8"))
        for command, flags in commands.items():
            known = accepted if not command else console_help_flags(*command)
            assert flags - known == set(), (name, command)


def test_subcommand_flags_are_checked_against_their_own_command():
    """Negative control: a serve-only flag written after a subcommand is reported."""
    sample = "`wled-mcp config validate --config x --transport stdio`"
    assert documented_console_commands(sample) == {
        ("config", "validate"): {"--config", "--transport"}
    }
    assert "--transport" not in console_help_flags("config", "validate")


def test_documented_command_word_extraction_rejects_an_invented_flag():
    """Negative control for the extractor: an undocumented flag would be reported."""
    sample = "```text\nuv run --frozen wled-mcp --config x \\\n  --invented-flag y\n```\n"
    assert documented_console_flags(sample) == {"--config", "--invented-flag"}
    assert "--invented-flag" not in console_help_flags()


@pytest.mark.anyio
async def test_stdio_hub_example_arguments_complete_a_handshake(tmp_path):
    example = json.loads((ROOT / "examples/mcphub.example.json").read_text("utf-8"))
    args: list[str] = example["mcpServers"]["wled"]["args"]
    console_args = args[args.index("wled-mcp") + 1 :]
    config = tmp_path / "devices.toml"
    config.write_text("schema_version = 1\ndevices = []\n", encoding="utf-8")
    synthetic = {"--config": str(config), "--data-dir": str(tmp_path)}
    substituted: list[str] = []
    for index, token in enumerate(console_args):
        previous = console_args[index - 1] if index else ""
        if previous in synthetic:
            assert token.startswith("/"), "documented paths are absolute"
            substituted.append(synthetic[previous])
        else:
            substituted.append(token)
    assert substituted[:2] == ["--transport", "stdio"]
    assert set(synthetic) <= set(substituted)
    params = StdioServerParameters(command=str(CONSOLE), cwd=tmp_path, args=substituted)
    with anyio.fail_after(60):
        async with Client(params, mode="legacy", read_timeout_seconds=10) as client:
            tools = (await client.list_tools()).tools
            assert [tool.name for tool in tools] == expected_names()
            result = await client.call_tool("wled_list_devices", {})
    assert not result.is_error and result.structured_content["data"] == {"devices": []}
    assert sorted(path.name for path in tmp_path.iterdir()) == ["devices.toml"]


def test_segment_name_results_show_resolved_ids_and_diagnostic_suggestions(outcomes):
    for transport in ("stdio", "http"):
        preview = outcomes[transport]["segment_names_preview"]["structured"]
        planned = preview["data"]["plan"]["resolved_segments"][0]
        assert planned["effect_id"] == 3 and planned["palette_id"] == 2
        unknown = outcomes[transport]["segment_name_unknown"]["structured"]
        assert unknown["data"]["candidates"] == [{"id": 3, "name": "Wipe"}]
