"""Build, install and exercise the wheel and uvx outside the source checkout.

Dependency installation uses exact runtime constraints, never LAN devices.
Run after `uv sync --frozen`; runtime export drift is checked separately.
"""

import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import anyio
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters
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
                ]
                assert tools[0].input_schema["additionalProperties"] is False
                result = await client.call_tool("wled_list_devices", {})
                assert result.structured_content is not None
                assert result.structured_content["data"] == {"devices": []}
                assert not result.is_error


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
        assert "License-Expression:" not in metadata
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
    print(f"Wheel/clean install/uvx: PASS; {len(expected)} exact runtime versions verified")


if __name__ == "__main__":
    main()
