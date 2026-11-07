"""Build, install and exercise the wheel and uvx outside the source checkout.

Dependency installation uses exact runtime constraints, never LAN devices.
Run after `uv sync --frozen`; runtime export drift is checked separately.
"""

import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import zipfile
from pathlib import Path, PurePosixPath

import anyio
import httpx2
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters
from mcp.client.streamable_http import streamable_http_client
from packaging.requirements import Requirement


def run(command: list[str], cwd: Path, env: dict[str, str]) -> str:
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise SystemExit(result.stderr)
    return result.stdout.strip()


async def handshake(command: str, args: list[str], cwd: Path, env: dict[str, str]) -> None:
    for mode in ("legacy", "auto"):
        with anyio.fail_after(30):
            params = StdioServerParameters(command=command, args=args, cwd=cwd, env=env)
            async with Client(params, mode=mode, read_timeout_seconds=10) as client:
                assert client.server_info is not None
                assert client.server_info.name == "wled-mcp"
                assert client.server_info.version == "0.1.0"
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
                assert tools[0].input_schema["additionalProperties"] is False
                result = await client.call_tool("wled_list_devices", {})
                assert result.structured_content is not None
                assert result.structured_content["data"] == {"devices": []}
                assert not result.is_error


TOOL_COUNT = 12


async def http_exchange(port: int, token: str) -> None:
    for mode in ("legacy", "auto"):
        with anyio.fail_after(30):
            async with httpx2.AsyncClient(headers={"Authorization": f"Bearer {token}"}) as http:
                transport = streamable_http_client(
                    f"http://127.0.0.1:{port}/mcp", http_client=http, terminate_on_close=False
                )
                async with Client(transport, mode=mode, read_timeout_seconds=10) as client:
                    assert len((await client.list_tools()).tools) == TOOL_COUNT
                    result = await client.call_tool("wled_list_devices", {})
                    assert result.structured_content is not None
                    assert result.structured_content["data"] == {"devices": []}


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def http_smoke(console: Path, args: list[str], cwd: Path, env: dict[str, str], port: int) -> None:
    """Installed console serves authenticated loopback HTTP and exits 0 on a stop signal."""
    token = "synthetic-distribution-token-0123456789"
    flags = ["--transport", "streamable-http", "--port", str(port)]
    flags += ["--allowed-host", f"127.0.0.1:{port}"]
    creation = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    process = subprocess.Popen(
        [str(console), *args, *flags],
        cwd=cwd,
        env={**env, "WLED_MCP_HTTP_TOKEN": token},
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=creation,
    )
    assert process.stderr is not None and process.stdout is not None
    ready = threading.Event()
    stderr = process.stderr

    def watch() -> None:
        for line in stderr:
            if "listening on" in line:
                ready.set()

    threading.Thread(target=watch, daemon=True).start()
    try:
        if not ready.wait(30):
            raise SystemExit("Installed HTTP service did not report readiness.")
        anyio.run(http_exchange, port, token)
        stop = getattr(signal, "CTRL_BREAK_EVENT", signal.SIGTERM)  # CTRL_BREAK on Windows
        process.send_signal(stop)
        assert process.wait(timeout=30) == 0, "HTTP service must exit 0 after a stop signal"
        assert process.stdout.read() == "", "stdout stays unused in HTTP mode"
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        process.stdout.close()
        process.stderr.close()


def http_restart(console: Path, config: Path, data: Path, cwd: Path, env: dict[str, str]) -> None:
    """Two consecutive start/exchange/stop cycles on one config and data directory."""
    data.mkdir()
    args = ["--config", str(config), "--data-dir", str(data)]
    port = free_port()
    for _cycle in range(2):  # restart on the same port, config and data directory
        http_smoke(console, args, cwd, env, port)
        leftovers = sorted(path.name for path in data.iterdir())
        assert leftovers == [], f"HTTP start/stop left unexpected data files: {leftovers}"


def hub_example_uvx(
    root: Path, wheel: Path, constraints: Path, data: Path, env: dict[str, str]
) -> tuple[str, list[str], dict[str, str]]:
    """The stdio hub example (#11) with only its paths replaced by local ones."""
    example = json.loads((root / "examples/mcphub.example.json").read_text("utf-8"))
    entry = example["mcpServers"]["wled"]
    args: list[str] = list(entry["args"])
    data.mkdir()
    (data / "config").mkdir()
    config = data / "config" / "devices.toml"
    config.write_text("schema_version = 1\ndevices = []\n", encoding="utf-8")
    replacements = {"--constraints": constraints, "--from": wheel, "--config": config}
    replacements["--data-dir"] = data
    for index, token in enumerate(args[:-1]):
        if token in replacements:
            documented = PurePosixPath(args[index + 1])
            local = replacements[token]
            assert documented.is_absolute(), f"{token} path in the hub example is absolute"
            if token in ("--constraints", "--from"):
                assert documented.name == local.name, f"{token} names the staged {local.name}"
            args[index + 1] = str(local)
    assert sum(token in replacements for token in args) == len(replacements)
    hub_env = dict(env)
    for name, value in entry["env"].items():
        assert PurePosixPath(value).is_absolute() and name in env, name
        hub_env[name] = env[name]  # persistent uv paths -> this check's local paths
    return str(entry["command"]), args, hub_env


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    artifacts = root / ".artifacts"
    artifacts.mkdir(exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith("WLED_MCP_")}
    env.update(
        UV_CACHE_DIR=env.get("UV_CACHE_DIR", str(root / ".uv-cache")),
        UV_TOOL_DIR=str(root / ".uv-tools"),
        UV_PYTHON_INSTALL_DIR=str(root / ".uv-python"),
        UV_PYTHON_DOWNLOADS="never",
    )
    constraints = root / "requirements-runtime.txt"
    expected = {}
    for line in constraints.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        requirement = Requirement(line)
        if requirement.marker is None or requirement.marker.evaluate():
            expected[requirement.name] = next(iter(requirement.specifier)).version
    expected["wled-mcp"] = "0.1.0"
    inspection = (
        "import importlib.metadata as m,json; "
        f"names={list(expected)!r}; "
        "print(json.dumps({n:m.version(n) for n in names})); "
        "import wled_mcp; print(wled_mcp.__file__)"
    )
    run(
        ["uv", "build", "--offline", "--wheel", "--no-build-isolation", "--python", sys.executable],
        root,
        env,
    )
    wheel = root / "dist" / "wled_mcp-0.1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel) as archive:
        assert "wled_mcp/cli.py" in archive.namelist()
        assert not any(name.startswith("tests/") for name in archive.namelist())
        metadata = archive.read("wled_mcp-0.1.0.dist-info/METADATA").decode()
        assert "Requires-Dist: mcp==2.3.0" in metadata
        assert "License-Expression: Apache-2.0" in metadata
        assert "Author: Kai Schulte" in metadata
        assert "Summary: Unofficial " in metadata
        assert "not affiliated with the WLED project" in metadata
        assert "wled_mcp-0.1.0.dist-info/licenses/LICENSE" in archive.namelist()
        assert "wled_mcp-0.1.0.dist-info/licenses/NOTICE" in archive.namelist()
    with tempfile.TemporaryDirectory(dir=artifacts) as temporary:
        outside = Path(temporary)
        environment = outside / "installed"
        run(["uv", "venv", "--python", sys.executable, str(environment)], outside, env)
        binaries = environment / ("Scripts" if os.name == "nt" else "bin")
        python = binaries / ("python.exe" if os.name == "nt" else "python")
        console = binaries / ("wled-mcp.exe" if os.name == "nt" else "wled-mcp")
        run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(python),
                "--constraint",
                constraints.as_uri(),
                wheel.as_uri(),
            ],
            outside,
            env,
        )
        installed = run([str(python), "-c", inspection], outside, env).splitlines()
        assert json.loads(installed[0]) == expected
        assert str(environment).casefold() in installed[1].casefold()
        assert run([str(console), "--version"], outside, env) == "wled-mcp 0.1.0"
        assert "--transport" in run([str(console), "--help"], outside, env)
        config = outside / "bootstrap.toml"
        config.write_text("schema_version = 1\ndevices = []\n", encoding="utf-8")
        args = ["--config", str(config), "--data-dir", str(outside)]
        anyio.run(handshake, str(console), args, outside, env)
        http_restart(console, config, outside / "service-data", outside, env)
        uvx = [
            "uvx",
            "--isolated",
            "--no-env-file",
            "--python",
            sys.executable,
            "--constraints",
            constraints.as_uri(),
            "--from",
            wheel.as_uri(),
        ]
        tool = run([*uvx, "python", "-c", inspection], outside, env).splitlines()
        assert json.loads(tool[0]) == expected
        assert str(root / "src").casefold() not in tool[1].casefold()
        assert run([*uvx, "wled-mcp", "--version"], outside, env) == "wled-mcp 0.1.0"
        anyio.run(handshake, uvx[0], [*uvx[1:], "wled-mcp", *args], outside, env)
        hub_data = outside / "hub-data"
        command, hub_args, hub_env = hub_example_uvx(root, wheel, constraints, hub_data, env)
        anyio.run(handshake, command, hub_args, outside, hub_env)
        leftovers = sorted(path.name for path in hub_data.iterdir())
        assert leftovers == ["config"], f"stdio hub example left data files: {leftovers}"
    print(
        "Wheel/clean install/stdio/HTTP restart/uvx/stdio hub example: PASS; "
        f"{len(expected)} exact runtime versions verified"
    )


if __name__ == "__main__":
    main()
