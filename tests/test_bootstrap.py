import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

import anyio
import pytest
from mcp import MCPError
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters
from pydantic import ValidationError

from wled_mcp.config import ConfigurationError, load_config
from wled_mcp.models import DomainError, Outcome

ROOT = Path(__file__).resolve().parents[1]
CONSOLE = Path(sys.executable).parent / ("wled-mcp.exe" if os.name == "nt" else "wled-mcp")


@pytest.fixture
def startup(tmp_path):
    config = tmp_path / "bootstrap.toml"
    config.write_text("schema_version = 1\ndevices = []\n", encoding="utf-8")
    return config, tmp_path


@pytest.mark.parametrize(
    "content",
    [
        "schema_version = true\ndevices = []",
        "schema_version = 2\ndevices = []",
        "schema_version = 1",
        "schema_version = 1\ndevices = {}",
        'schema_version = 1\ndevices = [{id = "synthetic-secret"}]',
        'schema_version = 1\ndevices = []\nsecret = "synthetic-secret"',
        'schema_version = "synthetic-secret',
        "#" * 65537,
    ],
)
def test_invalid_configuration_is_safe(startup, content):
    config, data = startup
    config.write_text(content, encoding="utf-8")
    with pytest.raises(ConfigurationError) as caught:
        load_config(str(config), str(data), {})
    assert "synthetic-secret" not in str(caught.value)
    assert set(data.iterdir()) == {config}


def test_paths_and_precedence(startup):
    config, data = startup
    env = {"WLED_MCP_CONFIG": str(config), "WLED_MCP_DATA_DIR": str(data)}
    assert load_config(None, None, env).config_path == config
    assert load_config(str(config), str(data), {key: "bad" for key in env}).data_dir == data
    for config_path, data_dir in [
        (None, None),
        ("relative", str(data)),
        (str(config), str(config)),
        (str(data / "absent"), str(data)),
    ]:
        with pytest.raises(ConfigurationError):
            load_config(config_path, data_dir, {})


def test_deep_toml_fails_safely_in_loader_and_console(startup):
    config, data = startup
    config.write_text(
        "schema_version=1\ndevices=[]\nx=" + "[" * 1500 + '"synthetic-secret"' + "]" * 1500,
        encoding="utf-8",
    )
    assert config.stat().st_size < 65536
    with pytest.raises(ConfigurationError) as caught:
        load_config(str(config), str(data), {})
    assert "synthetic-secret" not in str(caught.value)
    result = subprocess.run(
        [str(CONSOLE), "--config", str(config), "--data-dir", str(data)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2
    assert result.stdout == ""
    assert "Startup configuration error:" in result.stderr
    assert "synthetic-secret" not in result.stderr
    assert "Traceback" not in result.stderr
    assert "RecursionError" not in result.stderr
    assert set(data.iterdir()) == {config}


@pytest.mark.parametrize(
    "args", [[], ["--unknown", "synthetic-secret"], ["--transport", "synthetic-secret"]]
)
def test_cli_rejects_unsupported_arguments_without_stdout(args, tmp_path):
    env = {k: v for k, v in os.environ.items() if not k.startswith("WLED_MCP_")}
    result = subprocess.run(
        [str(CONSOLE), *args], capture_output=True, text=True, timeout=10, cwd=tmp_path, env=env
    )
    assert result.returncode == 2
    assert not result.stdout
    assert result.stderr
    assert "synthetic-secret" not in result.stderr


@pytest.mark.parametrize("transport", [[], ["--transport", "stdio"]])
@pytest.mark.parametrize("mode", ["legacy", "auto"])
def test_actual_console_sdk_handshake(startup, transport, mode):
    config, data = startup

    async def exercise():
        with anyio.fail_after(15):
            params = StdioServerParameters(
                command=str(CONSOLE),
                cwd=data,
                args=[
                    "--config",
                    str(config),
                    "--data-dir",
                    str(data),
                    *transport,
                ],
            )
            async with Client(params, mode=mode, read_timeout_seconds=5) as client:
                assert client.server_info.name == "wled-mcp"
                assert client.server_info.version == "0.1.0"
                assert client.protocol_version == (
                    "2025-11-25" if mode == "legacy" else "2026-07-28"
                )
                tools = (await client.list_tools()).tools
                assert [tool.name for tool in tools] == [
                    "wled_list_devices",
                    "wled_get_state",
                    "wled_get_effects",
                    "wled_get_palettes",
                    "wled_set_state",
                    "wled_patch_segments",
                    "wled_replace_layout",
                    "wled_list_presets",
                    "wled_get_preset",
                    "wled_activate_preset",
                    "wled_save_preset",
                    "wled_delete_preset",
                ]
                result = await client.call_tool("wled_list_devices", {})
                assert result.structured_content["data"] == {"devices": []}

    anyio.run(exercise)
    assert set(data.iterdir()) == {config}


def test_fixture_schema_results_and_errors():
    async def exercise():
        with anyio.fail_after(20):
            params = StdioServerParameters(
                command=sys.executable, cwd=ROOT, args=["-m", "tests.fixture_server"]
            )
            async with Client(params, mode="legacy", read_timeout_seconds=5) as client:
                tool = (await client.list_tools()).tools[0]
                assert tool.name == "fixture"
                assert tool.output_schema["additionalProperties"] is False
                assert set(tool.input_schema["required"]) == {"outcome", "value"}
                for state in ["success", "invalid", "uncertain"]:
                    result = await client.call_tool("fixture", {"outcome": state, "value": 0})
                    envelope = result.structured_content
                    assert json.loads(result.content[0].text) == envelope
                    Outcome.model_validate(envelope)
                    assert result.is_error == (not envelope["ok"])
                    if state == "success":
                        assert envelope["data"]["value"] == 0
                    if state == "uncertain":
                        assert envelope["application"] == "unknown"
                        assert envelope["error"]["write_retryable"] is False
                for arguments in [
                    {"outcome": "success", "value": True},
                    {"outcome": "success", "value": 1, "unknown": 2},
                ]:
                    rejected = await client.call_tool("fixture", arguments)
                    assert rejected.is_error
                    assert rejected.structured_content["error"]["code"] == "VALIDATION_ERROR"
                with pytest.raises(MCPError):
                    await client.call_tool("absent", {})
                with pytest.raises(MCPError) as caught:
                    await client.call_tool("fixture", {"outcome": "crash", "value": 1})
                assert "synthetic-secret" not in str(caught.value)

    anyio.run(exercise)


def test_stdout_is_only_protocol_and_clean_eof(startup):
    config, data = startup
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "synthetic", "version": "1"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "unknown-method"},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": 123}},
    ]
    process = subprocess.Popen(
        [str(CONSOLE), "--config", str(config), "--data-dir", str(data)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    output = queue.Queue()
    reader = threading.Thread(
        target=lambda: [output.put(line) for line in process.stdout], daemon=True
    )
    reader.start()
    responses = {}
    try:
        for message in messages:
            process.stdin.write(json.dumps(message) + "\n")
            process.stdin.flush()
            if "id" in message:
                response = json.loads(output.get(timeout=5))
                assert response["id"] == message["id"]
                responses[response["id"]] = response
        process.stdin.close()
        assert process.wait(timeout=5) == 0
        reader.join(timeout=2)
        assert output.empty()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        process.stdout.close()
        process.stderr.close()
    assert responses[1]["result"]["serverInfo"]["name"] == "wled-mcp"
    assert [tool["name"] for tool in responses[2]["result"]["tools"]] == [
        "wled_list_devices",
        "wled_get_state",
        "wled_get_effects",
        "wled_get_palettes",
        "wled_set_state",
        "wled_patch_segments",
        "wled_replace_layout",
        "wled_list_presets",
        "wled_get_preset",
        "wled_activate_preset",
        "wled_save_preset",
        "wled_delete_preset",
    ]
    assert responses[3]["error"]["code"] == -32601
    assert responses[4]["error"]["code"] == -32602


@pytest.mark.parametrize(
    "overrides",
    [
        {"ok": True, "application": "unknown", "verification": "unknown"},
        {"application": "applied", "verification": "verified"},
        {"dry_run": True, "application": "applied", "verification": "mismatch"},
        {"ok": True},
        {"application": "unknown", "verification": "verified"},
    ],
)
def test_inconsistent_domain_outcomes_rejected(overrides):
    fields = dict(
        ok=False,
        operation="synthetic",
        device_id=None,
        application="not_attempted",
        verification="not_requested",
        error=DomainError(
            code="VALIDATION_ERROR", message="Invalid.", reconciliation="Correct input."
        ),
    )
    fields.update(overrides)
    with pytest.raises(ValidationError):
        Outcome.model_validate(fields)
