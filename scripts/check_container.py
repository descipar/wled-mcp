"""Build the HTTP image from a staged release directory and smoke-test it on loopback.

Used by the CI ``container`` job on each native architecture (issue #21, TD-21-8):
builds ``deploy/http/Dockerfile`` from the staged directory with the tag recorded in
``RELEASE``, starts it with the hardening of the Compose example and an empty synthetic
inventory, publishes the service port on ``127.0.0.1`` only, then checks the console
version, one authenticated MCP ``tools/list`` against ``tests/tool_contract.py``,
``wled_list_devices`` and a clean exit on SIGTERM. Nothing is pushed or pulled except
the pinned base image; no LAN device is contacted. Removes its container and image.

    python scripts/check_container.py .artifacts/release/<version>
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import platform
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import anyio
import httpx2
from mcp.client import Client
from mcp.client.streamable_http import streamable_http_client

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "tests" / "tool_contract.py"
SERVICE_PORT = 8000
DATA = "/app/data/wled-mcp"
TOKEN = "/run/secrets/wled_mcp_http_token"


def expected_tool_names(path: Path = CONTRACT_PATH) -> list[str]:
    """Ordered default tool names from the source checkout (ISSUE-98-DEC-001)."""
    spec = importlib.util.spec_from_file_location("wled_mcp_tool_contract", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load the expected tool contract {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve annotations through sys.modules
    spec.loader.exec_module(module)
    names = module.expected_names()
    if not isinstance(names, list) or not names or not all(isinstance(n, str) for n in names):
        raise SystemExit(f"{path.name} did not provide an ordered list of tool names")
    return names


def release_record(directory: Path) -> dict[str, str]:
    lines = (directory / "RELEASE").read_text("utf-8").splitlines()
    record = dict(line.split("=", 1) for line in lines if "=" in line)
    if record.get("version") != directory.name:
        raise SystemExit(f"RELEASE version {record.get('version')} != {directory.name}")
    return record


def docker(*args: str, timeout: float = 120, check: bool = True) -> str:
    result = subprocess.run(
        ["docker", *args], capture_output=True, text=True, timeout=timeout, check=False
    )
    if check and result.returncode:
        raise SystemExit(f"docker {args[0]} failed:\n{result.stderr.strip()[-4000:]}")
    return result.stdout.strip()


def require(condition: bool, message: str) -> None:
    """Fail the smoke check explicitly; unlike ``assert`` this is never optimized away."""
    if not condition:
        raise SystemExit(f"container check failed: {message}")


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


async def exchange(port: int, token: str, version: str, expected: list[str]) -> None:
    with anyio.fail_after(60):
        async with httpx2.AsyncClient(headers={"Authorization": f"Bearer {token}"}) as http:
            transport = streamable_http_client(
                f"http://127.0.0.1:{port}/mcp", http_client=http, terminate_on_close=False
            )
            async with Client(transport, read_timeout_seconds=20) as client:
                info = client.server_info
                if info is None:
                    raise SystemExit("container check failed: the server sent no serverInfo")
                require(info.name == "wled-mcp", f"serverInfo.name is {info.name!r}")
                require(info.version == version, f"serverInfo.version is {info.version!r}")
                names = [tool.name for tool in (await client.list_tools()).tools]
                require(names == expected, f"tools/list names {names} != {expected}")
                result = await client.call_tool("wled_list_devices", {})
                require(not result.is_error, "wled_list_devices returned an error result")
                content = result.structured_content
                if content is None:
                    raise SystemExit("container check failed: wled_list_devices has no content")
                require(
                    content.get("data") == {"devices": []},
                    f"wled_list_devices data is {content.get('data')!r}",
                )


def container_logs(name: str) -> str:
    """The container's stdout and stderr (the service logs to stderr only)."""
    logs = subprocess.run(
        ["docker", "logs", name], capture_output=True, text=True, timeout=30, check=False
    )
    return logs.stdout + logs.stderr


def wait_listening(name: str, deadline: float) -> None:
    while time.monotonic() < deadline:
        state = docker("inspect", "--format", "{{.State.Status}}", name)
        if state != "running":
            raise SystemExit(f"container {state}:\n{container_logs(name)}")
        if "listening on" in container_logs(name):
            return
        time.sleep(1)
    raise SystemExit(f"container did not report readiness:\n{container_logs(name)}")


def smoke(directory: Path) -> None:
    record = release_record(directory)
    version = record["version"]
    tag = record.get("image_tag", f"wled-mcp:{version}")
    if tag != f"wled-mcp:{version.replace('+', '-')}":
        raise SystemExit(f"image tag {tag} does not derive from version {version}")
    expected = expected_tool_names()
    docker("build", "--pull", "-t", tag, str(directory), timeout=900)
    name = f"wled-mcp-smoke-{secrets.token_hex(4)}"
    try:
        architecture = docker("image", "inspect", "--format", "{{.Architecture}}", tag)
        console = docker("run", "--rm", "--network", "none", tag, "--version")
        require(console == f"wled-mcp {version}", f"--version printed {console!r}")
        with tempfile.TemporaryDirectory() as temporary:
            data = Path(temporary) / "data"
            (data / "config").mkdir(parents=True)
            (data / "config" / "devices.toml").write_text(
                "schema_version = 1\ndevices = []\n", encoding="utf-8"
            )
            token = secrets.token_urlsafe(32)
            token_file = Path(temporary) / "token"
            token_file.write_text(token, encoding="ascii")
            for path in (Path(temporary), data, data / "config"):
                path.chmod(0o755)  # the image's non-root UID reads the synthetic inputs
            for path in (data / "config" / "devices.toml", token_file):
                path.chmod(0o644)
            port = free_port()
            docker(
                "run",
                "--detach",
                "--name",
                name,
                "--read-only",
                "--tmpfs",
                "/tmp",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges:true",
                "--publish",
                f"127.0.0.1:{port}:{SERVICE_PORT}",
                "--volume",
                f"{data}:{DATA}:ro",
                "--volume",
                f"{token_file}:{TOKEN}:ro",
                tag,
                "--config",
                f"{DATA}/config/devices.toml",
                "--data-dir",
                DATA,
                "--transport",
                "streamable-http",
                "--host",
                "0.0.0.0",
                "--port",
                str(SERVICE_PORT),
                "--allowed-host",
                f"127.0.0.1:{port}",
                "--http-token-file",
                TOKEN,
            )
            wait_listening(name, time.monotonic() + 60)
            anyio.run(exchange, port, token, version, expected)
            docker("stop", "--time", "130", name, timeout=180)
            code = docker("inspect", "--format", "{{.State.ExitCode}}", name)
            require(code == "0", f"service exit code {code} after SIGTERM")
            stdout = subprocess.run(
                ["docker", "logs", name], capture_output=True, text=True, timeout=30
            ).stdout
            require(stdout == "", "stdout must stay unused in HTTP mode")
    finally:
        docker("rm", "--force", name, check=False)
        docker("image", "rm", tag, check=False)
    print(
        f"Container {tag} ({architecture}, host {platform.machine()}): build, --version, "
        f"loopback HTTP tools/list ({len(expected)} tools), wled_list_devices, SIGTERM exit 0: "
        "PASS"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("release_dir", type=Path, help="Staged release directory.")
    args = parser.parse_args(argv)
    if os.name == "nt":
        raise SystemExit("Linux container check; run it on a Linux Docker host.")
    smoke(args.release_dir.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
