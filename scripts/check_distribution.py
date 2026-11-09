"""Build, install and exercise the wheel and uvx outside the source checkout.

Dependency installation uses exact runtime constraints, never LAN devices. The wheel's
``Requires-Dist`` must equal the declared ranges of ``pyproject.toml`` (no exact pins).
Run after `uv sync --frozen`; runtime export drift is checked separately.

Without options the wheel is built into ``dist/`` and checked (CI). The publish workflow
(docs/PUBLISHING.md) uses ``--release-ref`` as its guard before building and then
``--wheel``/``--sdist`` to check the files it built, without building again.
"""

import argparse
import importlib.util
import json
import os
import re
import signal
import socket
import subprocess
import sys
import tarfile
import tempfile
import threading
import tomllib
import zipfile
from pathlib import Path, PurePosixPath

import anyio
import httpx2
from mcp import MCPError
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters
from mcp.client.streamable_http import streamable_http_client
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "tests" / "tool_contract.py"
VERSION_PLACEHOLDER = "REPLACE_WITH_VERSION"  # release directory name in the hub example
# A published release version: no local label, no development release (as
# deploy/stage_release.py; docs/contract/versioning.md).
RELEASE_VERSION = re.compile(r"\d+\.\d+\.\d+(?:rc\d+)?")
EFFECT_DATA = "src/wled_mcp/catalog_data/effect_properties.json"  # packaged effect catalog (#31)
MAIN_REF = "refs/remotes/origin/main"  # releases come from `main` commits (DEC-023 item 1)


def project_version(root: Path = ROOT) -> str:
    """The canonical version: ``project.version`` (docs/contract/versioning.md)."""
    with (root / "pyproject.toml").open("rb") as stream:
        return str(tomllib.load(stream)["project"]["version"])


VERSION = project_version()


def expected_tool_names(path: Path = CONTRACT_PATH, profile: str = "full") -> list[str]:
    """Ordered tool names of a profile (default ``full``), from the source checkout's contract.

    Loaded by path: the expectation is not part of the wheel, so the installed wheel's
    served list is compared with the source tree (ISSUE-98-DEC-001).
    """
    spec = importlib.util.spec_from_file_location("wled_mcp_tool_contract", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load the expected tool contract {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve annotations through sys.modules
    spec.loader.exec_module(module)
    names = module.expected_names() if profile == "full" else module.expected_names(profile)
    if not isinstance(names, list) or not names or not all(isinstance(n, str) for n in names):
        raise SystemExit(f"{path.name} did not provide an ordered list of tool names")
    return names


EXPECTED_TOOL_NAMES = expected_tool_names()
READ_ONLY_TOOL_NAMES = expected_tool_names(profile="read-only")


def release_names(version: str) -> tuple[str, str]:
    """File names of the source distribution and the wheel of ``version``."""
    return f"wled_mcp-{version}.tar.gz", f"wled_mcp-{version}-py3-none-any.whl"


def release_ref_problems(ref_type: str, ref_name: str, version: str) -> list[str]:
    """Why the workflow ref must not be built and published as ``version``."""
    problems = []
    if not RELEASE_VERSION.fullmatch(version):
        problems.append(f"project.version {version!r} is not a release version")
    if ref_type != "tag":
        problems.append(f"the workflow ref type is {ref_type!r}, not 'tag'")
    if ref_name != f"v{version}":
        problems.append(f"ref {ref_name!r} is not the tag 'v{version}' of project.version")
    return problems


def git_commit(root: Path, revision: str) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"{revision}^{{commit}}"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def tag_commit_problems(root: Path, tag: str, expected: str | None) -> list[str]:
    """The checked-out commit is the tag's commit and reachable from ``main``."""
    head = git_commit(root, "HEAD")
    tagged = git_commit(root, f"refs/tags/{tag}")
    if head is None:
        return ["no checked-out commit"]
    problems = []
    if tagged != head:
        problems.append(f"tag {tag!r} does not point at the checked-out commit")
    if expected is not None and expected != head:
        problems.append("the checked-out commit is not the workflow commit")
    if git_commit(root, MAIN_REF) is None:
        return [*problems, f"{MAIN_REF} is missing; fetch the full history of main"]
    reachable = subprocess.run(
        ["git", "merge-base", "--is-ancestor", head, MAIN_REF],
        cwd=root,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if reachable.returncode == 1:
        problems.append("the tagged commit is not reachable from main")
    elif reachable.returncode:
        problems.append("git could not decide whether the tagged commit is on main")
    return problems


def release_directory_problems(names: list[str], version: str) -> list[str]:
    """The upload directory holds exactly the sdist and the wheel of ``version``."""
    expected = set(release_names(version))
    present = set(names)
    problems = [f"missing {name}" for name in sorted(expected - present)]
    problems += [f"unexpected file {name}" for name in sorted(present - expected)]
    return problems


def metadata_version(text: str) -> str | None:
    """The ``Version`` field of core metadata (header part only)."""
    for line in text.split("\n\n", 1)[0].splitlines():
        if line.startswith("Version: "):
            return line.removeprefix("Version: ").strip()
    return None


def project_dependencies(root: Path = ROOT) -> list[str]:
    """``project.dependencies`` of ``pyproject.toml``: the declared runtime ranges."""
    with (root / "pyproject.toml").open("rb") as stream:
        return [str(item) for item in tomllib.load(stream)["project"]["dependencies"]]


def registry_name(root: Path = ROOT) -> str:
    """The MCP registry name of ``server.json`` (#24): the ownership marker names exactly it."""
    document = json.loads((root / "server.json").read_text("utf-8"))
    return str(document["name"])


def registry_marker_problems(metadata: str, name: str) -> list[str]:
    """The package description carries ``mcp-name: <name>``, which the registry verifies."""
    marker = f"mcp-name: {name}"
    # `\S+` takes the whole token on purpose: a longer name that merely starts with the
    # expected one is reported, not accepted as a prefix match (the registry's own rule for
    # the marker boundary was not checked).
    found = re.findall(r"mcp-name:\s*(\S+)", metadata)
    problems = []
    if marker not in metadata:
        problems.append(f"METADATA lacks the registry ownership marker {marker!r}")
    problems += [
        f"METADATA names another registry entry {other!r}" for other in found if other != name
    ]
    return problems


def requirement_key(text: str) -> tuple[str, frozenset[str], frozenset[str], str]:
    """A requirement independent of specifier order and name spelling (``mcp<3,>=2.3.0``)."""
    requirement = Requirement(text)
    return (
        canonicalize_name(requirement.name),
        frozenset(requirement.extras),
        frozenset(str(item) for item in requirement.specifier),
        str(requirement.marker or ""),
    )


def requires_dist_problems(metadata: str, declared: list[str]) -> list[str]:
    """The wheel's ``Requires-Dist`` equals ``declared`` and holds no exact pin (#22 item 4)."""
    found = [
        line.removeprefix("Requires-Dist: ").strip()
        for line in metadata.split("\n\n", 1)[0].splitlines()
        if line.startswith("Requires-Dist: ")
    ]
    problems = []
    for text in found:
        if any(item.operator in ("==", "===") for item in Requirement(text).specifier):
            problems.append(f"Requires-Dist {text!r} is an exact pin")
    shipped = {requirement_key(text): text for text in found}
    wanted = {requirement_key(text): text for text in declared}
    problems += sorted(f"Requires-Dist lacks {wanted[k]!r}" for k in wanted.keys() - shipped)
    problems += sorted(
        f"Requires-Dist has undeclared {shipped[k]!r}" for k in shipped.keys() - wanted
    )
    return problems


def sdist_member_problems(members: list[str], version: str) -> list[str]:
    """Paths that must not be in the published source distribution."""
    top = f"wled_mcp-{version}"
    problems = []
    for member in members:
        parts = PurePosixPath(member).parts
        if not parts or parts[0] != top:
            problems.append(f"{member}: outside {top}/")
            continue
        if ".git" in parts:
            problems.append(f"{member}: Git data")
        elif len(parts) > 1 and parts[1] in (".agent-runs", ".artifacts"):
            problems.append(f"{member}: local run or build output")
        elif any(part.startswith(".env") for part in parts):
            problems.append(f"{member}: environment file")
        elif parts[-1] == "devices.toml":
            problems.append(f"{member}: device inventory")
    return problems


def check_sdist(sdist: Path, version: str) -> None:
    if sdist.name != release_names(version)[0]:
        raise SystemExit(f"{sdist.name} is not the source distribution of {version}")
    with tarfile.open(sdist, "r:gz") as archive:
        members = archive.getnames()
        stream = archive.extractfile(f"wled_mcp-{version}/PKG-INFO")
        if stream is None:
            raise SystemExit(f"{sdist.name} has no PKG-INFO")
        pkg_info = stream.read().decode("utf-8")
    problems = sdist_member_problems(members, version)
    if f"wled_mcp-{version}/{EFFECT_DATA}" not in members:
        problems.append(f"{EFFECT_DATA} (effect catalog data) is missing")
    if metadata_version(pkg_info) != version:
        problems.append(f"PKG-INFO Version is not {version}")
    if problems:
        raise SystemExit(f"{sdist.name}: " + "; ".join(problems))


def check_release_ref(root: Path, environ: dict[str, str]) -> None:
    """Publish-workflow guard, run before anything is built (docs/PUBLISHING.md)."""
    ref_name = environ.get("GITHUB_REF_NAME", "")
    problems = release_ref_problems(environ.get("GITHUB_REF_TYPE", ""), ref_name, VERSION)
    if not problems:
        problems = tag_commit_problems(root, ref_name, environ.get("GITHUB_SHA") or None)
    if problems:
        raise SystemExit("Release guard: " + "; ".join(problems))
    print(f"Release guard: PASS; tag {ref_name} is project.version on main")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build or check and exercise the wheel.")
    parser.add_argument(
        "--release-ref",
        action="store_true",
        help="only check that the workflow tag is v<project.version> on main; build nothing",
    )
    parser.add_argument("--wheel", type=Path, help="check this built wheel instead of building")
    parser.add_argument("--sdist", type=Path, help="also check this built source distribution")
    args = parser.parse_args(argv)
    if args.release_ref and (args.wheel or args.sdist):
        parser.error("--release-ref checks the ref only")
    if args.sdist and not args.wheel:
        parser.error("--sdist needs --wheel")
    return args


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
                assert client.server_info.version == VERSION
                tools = (await client.list_tools()).tools
                assert [tool.name for tool in tools] == EXPECTED_TOOL_NAMES
                assert tools[0].input_schema["additionalProperties"] is False
                result = await client.call_tool("wled_list_devices", {})
                assert result.structured_content is not None
                assert result.structured_content["data"] == {"devices": []}
                assert not result.is_error


async def restricted_handshake(
    command: str, args: list[str], cwd: Path, env: dict[str, str]
) -> None:
    """The installed console under ``--profile read-only`` (issue #20, T20-13)."""
    with anyio.fail_after(30):
        params = StdioServerParameters(command=command, args=args, cwd=cwd, env=env)
        async with Client(params, mode="legacy", read_timeout_seconds=10) as client:
            tools = (await client.list_tools()).tools
            assert [tool.name for tool in tools] == READ_ONLY_TOOL_NAMES
            assert len(READ_ONLY_TOOL_NAMES) < len(EXPECTED_TOOL_NAMES)
            result = await client.call_tool("wled_list_devices", {})
            assert result.structured_content is not None
            assert result.structured_content["data"] == {"devices": []}
            try:
                await client.call_tool("wled_set_state", {"device_id": "x", "on": True})
            except MCPError as error:
                assert error.message == "Unknown tool", error.message
            else:
                raise AssertionError("an excluded tool must be an unknown tool")


async def http_exchange(port: int, token: str) -> None:
    for mode in ("legacy", "auto"):
        with anyio.fail_after(30):
            async with httpx2.AsyncClient(headers={"Authorization": f"Bearer {token}"}) as http:
                transport = streamable_http_client(
                    f"http://127.0.0.1:{port}/mcp", http_client=http, terminate_on_close=False
                )
                async with Client(transport, mode=mode, read_timeout_seconds=10) as client:
                    tools = (await client.list_tools()).tools
                    assert [tool.name for tool in tools] == EXPECTED_TOOL_NAMES
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


def setup_smoke(console: Path, directory: Path, env: dict[str, str]) -> None:
    """Installed `config init`/`config validate`/`doctor --offline` (#16), stdin closed."""
    directory.mkdir()
    data = directory / "data"
    data.mkdir()
    config = directory / "devices.toml"

    def json_run(*argv: str) -> dict[str, object]:
        result = subprocess.run(
            [str(console), *argv, "--format", "json"],
            cwd=directory,
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode:
            raise SystemExit(f"{argv[0]} failed: {result.stdout}{result.stderr}")
        document: dict[str, object] = json.loads(result.stdout)
        assert document["schema_version"] == 1 and document["ok"] is True, document
        return document

    paths = ["--config", str(config)]
    device = ["--device-id", "desk", "--device-name", "Example desk"]
    json_run("config", "init", *paths, *device, "--base-url", "http://192.0.2.10")
    assert json_run("config", "validate", *paths, "--data-dir", str(data))["device_count"] == 1
    report = json_run("doctor", *paths, "--data-dir", str(data), "--offline")
    assert report["command"] == "doctor", report
    leftovers = sorted(path.name for path in directory.rglob("*"))
    assert leftovers == ["data", "devices.toml"], f"setup commands left files: {leftovers}"


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
                assert documented.parent.name == VERSION_PLACEHOLDER, f"{token} release dir"
                staged = documented.name.replace(VERSION_PLACEHOLDER, VERSION)
                assert staged == local.name, f"{token} names the staged {local.name}"
            args[index + 1] = str(local)
    assert sum(token in replacements for token in args) == len(replacements)
    hub_env = dict(env)
    for name, value in entry["env"].items():
        assert PurePosixPath(value).is_absolute() and name in env, name
        hub_env[name] = env[name]  # persistent uv paths -> this check's local paths
    return str(entry["command"]), args, hub_env


def main(argv: list[str] | None = None) -> None:
    options = parse_args(argv)
    root = ROOT
    if options.release_ref:
        check_release_ref(root, dict(os.environ))
        return
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
    expected["wled-mcp"] = VERSION
    inspection = (
        "import importlib.metadata as m,json; "
        f"names={list(expected)!r}; "
        "print(json.dumps({n:m.version(n) for n in names})); "
        "import wled_mcp; print(wled_mcp.__file__)"
    )
    if options.wheel is None:
        run(
            [
                "uv",
                "build",
                "--offline",
                "--wheel",
                "--no-build-isolation",
                "--python",
                sys.executable,
            ],
            root,
            env,
        )
        wheel = root / "dist" / release_names(VERSION)[1]
    else:  # an already built release file: checked as it is, never rebuilt
        wheel = options.wheel.resolve()
        if wheel.name != release_names(VERSION)[1]:
            raise SystemExit(f"{wheel.name} is not the wheel of {VERSION}")
    if options.sdist is not None:
        sdist = options.sdist.resolve()
        check_sdist(sdist, VERSION)
        if sdist.parent != wheel.parent:
            raise SystemExit("--sdist and --wheel must be in the upload directory")
        names = sorted(path.name for path in wheel.parent.iterdir())
        if problems := release_directory_problems(names, VERSION):
            raise SystemExit(f"{wheel.parent.name}/: " + "; ".join(problems))
    dist_info = f"wled_mcp-{VERSION}.dist-info"
    with zipfile.ZipFile(wheel) as archive:
        assert "wled_mcp/cli.py" in archive.namelist()
        assert "wled_mcp/catalog_data/effect_properties.json" in archive.namelist()
        assert not any(name.startswith("tests/") for name in archive.namelist())
        metadata = archive.read(f"{dist_info}/METADATA").decode()
        if problems := requires_dist_problems(metadata, project_dependencies(root)):
            raise SystemExit(f"{wheel.name}: " + "; ".join(problems))
        if problems := registry_marker_problems(metadata, registry_name(root)):
            raise SystemExit(f"{wheel.name}: " + "; ".join(problems))
        assert "License-Expression: Apache-2.0" in metadata
        assert "Author: Kai Schulte" in metadata
        assert f"Version: {VERSION}\n" in metadata
        assert metadata_version(metadata) == VERSION
        assert "Summary: Unofficial " in metadata
        assert "not affiliated with the WLED project" in metadata
        assert f"{dist_info}/licenses/LICENSE" in archive.namelist()
        assert f"{dist_info}/licenses/NOTICE" in archive.namelist()
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
        assert run([str(console), "--version"], outside, env) == f"wled-mcp {VERSION}"
        assert "--transport" in run([str(console), "--help"], outside, env)
        setup_smoke(console, outside / "setup", env)
        config = outside / "bootstrap.toml"
        config.write_text("schema_version = 1\ndevices = []\n", encoding="utf-8")
        args = ["--config", str(config), "--data-dir", str(outside)]
        anyio.run(handshake, str(console), args, outside, env)
        anyio.run(
            restricted_handshake, str(console), [*args, "--profile", "read-only"], outside, env
        )
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
        assert run([*uvx, "wled-mcp", "--version"], outside, env) == f"wled-mcp {VERSION}"
        anyio.run(handshake, uvx[0], [*uvx[1:], "wled-mcp", *args], outside, env)
        hub_data = outside / "hub-data"
        command, hub_args, hub_env = hub_example_uvx(root, wheel, constraints, hub_data, env)
        anyio.run(handshake, command, hub_args, outside, hub_env)
        leftovers = sorted(path.name for path in hub_data.iterdir())
        assert leftovers == ["config"], f"stdio hub example left data files: {leftovers}"
    checked = "Source distribution/wheel" if options.sdist is not None else "Wheel"
    print(
        f"{checked}/clean install/setup commands/stdio/read-only profile/HTTP restart/uvx/"
        "stdio hub example: PASS; "
        f"{len(expected)} exact runtime versions verified"
    )


if __name__ == "__main__":
    main()
