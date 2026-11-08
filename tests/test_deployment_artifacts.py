"""Issue #11: consistency of the deployment artifacts for both transport modes.

Cross-checks the Dockerfile, its allowlist build context, the Compose example, both hub
examples, the staging helper and the deployment documentation against each other and
against the installed console. Runs the Compose command and the hub HTTP header shape
against the installed console on ``127.0.0.1`` only. No Docker daemon, hub, LAN device
or network beyond loopback is needed; the optional ``docker compose config`` check is
opt-in (``WLED_MCP_DOCKER_CHECKS=1``).
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import queue
import re
import secrets
import shutil
import signal
import subprocess
import threading
import tomllib
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import anyio
import httpx2 as httpx
import pytest
import yaml
from mcp.client import Client
from mcp.client.streamable_http import streamable_http_client

from deploy.stage_release import StageError, stage
from tests.test_http_cli import CONSOLE, POSIX_ONLY, clean_env, free_port, wait_ready
from tests.test_private_identifiers import scanner as identifier_scanner
from tests.tool_contract import expected_names

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "deploy/http/Dockerfile"
DOCKERIGNORE = ROOT / "deploy/http/Dockerfile.dockerignore"
COMPOSE = ROOT / "examples/compose.http.example.yaml"
HUB_HTTP = ROOT / "examples/mcphub.http.example.json"
HUB_STDIO = ROOT / "examples/mcphub.example.json"
DEPLOYMENT = ROOT / "docs/DEPLOYMENT.md"
TOKEN_PLACEHOLDER = "REPLACE_WITH_PRIVATE_SERVICE_TOKEN"
DRAIN_MAX_SECONDS = 122  # operation timeout bound (120 s) plus 2 s, see DEPLOYMENT.md
LOOPBACK_OR_WILDCARD = {"localhost", "127.0.0.1", "::1", "[::1]", "0.0.0.0", "::"}
CONSTRAINTS = "requirements-runtime.txt"
HTTP_ONLY_FLAGS = {"--host", "--port", "--allowed-host", "--allowed-origin", "--http-token-file"}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


# ------------------------------------------------------------------------------ helpers


def version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        return str(tomllib.load(stream)["project"]["version"])


def wheel_name(wheel_version: str | None = None) -> str:
    return f"wled_mcp-{wheel_version or version()}-py3-none-any.whl"


# The image files and examples carry no version literal (docs/contract/versioning.md):
# the Dockerfile copies the one staged wheel by pattern and pins it by checksum, and the
# examples name the staged release directory and image tag by placeholders.
WHEEL_PATTERN = "wled_mcp-*-py3-none-any.whl"
VERSION_PLACEHOLDER = "REPLACE_WITH_VERSION"
IMAGE_TAG_PLACEHOLDER = "REPLACE_WITH_IMAGE_TAG"


def compose() -> dict[str, Any]:
    loaded = yaml.safe_load(COMPOSE.read_text("utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def service() -> dict[str, Any]:
    services = compose()["services"]
    assert list(services) == ["wled-mcp"], "exactly one service, no hub service"
    return dict(services["wled-mcp"])


def option(args: list[str], flag: str) -> str:
    assert args.count(flag) == 1, f"{flag} must appear exactly once"
    return args[args.index(flag) + 1]


def options(args: list[str], flag: str) -> list[str]:
    return [args[i + 1] for i, token in enumerate(args) if token == flag]


def hub_http() -> dict[str, Any]:
    return dict(json.loads(HUB_HTTP.read_text("utf-8"))["mcpServers"]["wled"])


def hub_stdio() -> dict[str, Any]:
    return dict(json.loads(HUB_STDIO.read_text("utf-8"))["mcpServers"]["wled"])


def duration_seconds(text: str) -> float:
    units = {"ms": 0.001, "s": 1, "m": 60, "h": 3600}
    parts = re.findall(r"(\d+(?:\.\d+)?)(ms|s|m|h)", text)
    assert parts and "".join(n + u for n, u in parts) == text, f"unparsed duration {text!r}"
    return sum(float(n) * units[u] for n, u in parts)


AUTH_LITERAL = re.compile(
    r"(?:Bearer\s+|WLED_MCP_HTTP_TOKEN\s*[=:]\s*[\"']?|[\"']?token[\"']?\s*[=:]\s*[\"']?)"
    r"(?P<value>[!-~]{32,})",
    flags=re.IGNORECASE,
)


def token_literals(text: str) -> list[str]:
    """Credential-shaped values (32+ printable characters) in an authentication position."""
    found = []
    for match in AUTH_LITERAL.finditer(text):
        value = match.group("value").rstrip("\"',")
        if value != TOKEN_PLACEHOLDER and not value.startswith(("<", "$", "/")):
            found.append(value)
    return found


def dockerignore_violations(text: str, allowed: set[str]) -> list[str]:
    """An allowlist context excludes everything first and re-includes only ``allowed``."""
    rules = [line.strip() for line in text.splitlines()]
    rules = [rule for rule in rules if rule and not rule.startswith("#")]
    problems = []
    if not rules or rules[0] != "*":
        problems.append("first rule must exclude everything ('*')")
    for rule in rules[1:]:
        name = rule.removeprefix("!")
        if not rule.startswith("!") or name not in allowed:
            problems.append(f"unexpected rule {rule!r}")
    return problems


def dockerfile_instructions() -> list[tuple[str, str]]:
    joined = re.sub(r"\\\n", " ", DOCKERFILE.read_text("utf-8"))
    pairs = []
    for line in joined.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            keyword, _, rest = stripped.partition(" ")
            pairs.append((keyword.upper(), " ".join(rest.split())))
    return pairs


def deployment_files() -> list[Path]:
    files = [p for p in (ROOT / "deploy").rglob("*") if p.is_file()]
    files += [p for p in (ROOT / "examples").glob("*") if p.is_file()]
    return [p for p in files if "__pycache__" not in p.parts]


# ------------------------------------------------------------- HTTP: hub <-> service


def test_hub_http_url_names_the_compose_service_and_its_allowed_host():
    hub = hub_http()
    url = urlsplit(hub["url"])
    args = service()["command"]
    assert hub["type"] == "streamable-http"
    assert url.scheme == "http" and url.path == "/mcp" and not url.query
    assert url.hostname not in LOOPBACK_OR_WILDCARD, "localhost in MCPHub is the hub itself"
    assert url.hostname == "wled-mcp" and url.hostname in compose()["services"]
    assert url.port == int(option(args, "--port"))
    # Exact, case-insensitive Host allowlist entry for the authority MCPHub uses.
    assert url.netloc.casefold() in [h.casefold() for h in options(args, "--allowed-host")]
    assert all("*" not in h for h in options(args, "--allowed-host"))
    # No browser Origin is needed for a hub-to-service connection.
    assert options(args, "--allowed-origin") == []
    assert hub["headers"] == {"Authorization": f"Bearer {TOKEN_PLACEHOLDER}"}


def test_compose_is_a_separate_single_process_project_without_host_ports():
    project = compose()
    svc = service()
    args = svc["command"]
    assert isinstance(args, list) and all(isinstance(a, str) for a in args), "exec form"
    assert option(args, "--transport") == "streamable-http"
    # The container interface is bound explicitly; the allowlist above restricts Host.
    assert option(args, "--host") == "0.0.0.0"
    assert "ports" not in svc and "expose" not in svc, "no host publication"
    assert "depends_on" not in svc and "links" not in svc and "extends" not in svc
    assert "network_mode" not in svc
    replicas = svc.get("deploy", {}).get("replicas", 1)
    assert replicas == 1 and "scale" not in svc
    assert not any("worker" in a for a in args)
    networks = project["networks"]
    assert set(svc["networks"]) == set(networks)
    assert all(net.get("external") is True for net in networks.values()), "hub network joined"
    assert svc["restart"] == "unless-stopped"
    assert svc.get("stop_signal", "SIGTERM") == "SIGTERM"
    assert duration_seconds(svc["stop_grace_period"]) > DRAIN_MAX_SECONDS
    assert svc["read_only"] is True and svc["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in svc["security_opt"]


def test_healthcheck_is_a_credential_free_tcp_check_of_the_service_port():
    svc = service()
    test = svc["healthcheck"]["test"]
    assert test[0] == "CMD", "exec form, no shell"
    text = " ".join(test)
    port = option(svc["command"], "--port")
    assert re.search(rf"create_connection\(\(\"127\.0\.0\.1\", {port}\)", text)
    for forbidden in ("/run/secrets", "token", "Authorization", "http://", "/json"):
        assert forbidden.casefold() not in text.casefold()
    assert duration_seconds(svc["healthcheck"]["timeout"]) < duration_seconds(
        svc["healthcheck"]["interval"]
    )


def test_credential_only_from_a_git_ignored_runtime_secret_file():
    project = compose()
    svc = service()
    args = svc["command"]
    path = option(args, "--http-token-file")
    assert path.startswith("/run/secrets/")
    targets = {s["target"]: s["source"] for s in svc["secrets"]}
    source = targets[path.removeprefix("/run/secrets/")]
    secret_file = project["secrets"][source]["file"]
    # The secret source path is git-ignored relative to the deployed compose file.
    candidate = (COMPOSE.parent / secret_file).resolve().relative_to(ROOT)
    ignored = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", str(candidate)], cwd=ROOT, timeout=30
    )
    assert ignored.returncode == 0, f"{candidate} must be git-ignored"
    assert "environment" not in svc and "env_file" not in svc
    assert [a for a in args if "token" in a.casefold()] == ["--http-token-file", path]


def test_data_mount_matches_the_data_dir_and_holds_the_config():
    svc = service()
    args = svc["command"]
    data_dir = option(args, "--data-dir")
    config = option(args, "--config")
    assert data_dir.startswith("/") and config.startswith(f"{data_dir}/config/")
    mounts = [m.split(":") for m in svc["volumes"]]
    assert [m[1] for m in mounts] == [data_dir], "exactly one writable data mount"
    host = mounts[0][0]
    assert host.startswith("./"), "host data directory next to the deployed compose file"
    host_config = (COMPOSE.parent / host / "config" / "devices.toml").resolve().relative_to(ROOT)
    ignored = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", str(host_config)], cwd=ROOT, timeout=30
    )
    assert ignored.returncode == 0, "runtime inventory and backups stay out of Git"
    # The image pre-creates the data directory for the non-root user.
    instructions = dockerfile_instructions()
    run = " ".join(rest for keyword, rest in instructions if keyword == "RUN")
    assert f'-o "${{APP_UID}}" -g "${{APP_GID}}" -m 0700 {data_dir}' in run
    assert ("WORKDIR", data_dir) in instructions


# --------------------------------------------------------------- image and artifacts


def test_dockerfile_pins_base_image_wheel_and_constraints():
    instructions = dockerfile_instructions()
    froms = [rest for keyword, rest in instructions if keyword == "FROM"]
    assert len(froms) == 1
    assert re.fullmatch(r"python:3\.13\.\d+-slim(-[a-z]+)?(@sha256:[0-9a-f]{64})?", froms[0])
    copies = [rest.split() for keyword, rest in instructions if keyword == "COPY"]
    assert len(copies) == 1
    sources = copies[0][:-1]
    assert sources == [WHEEL_PATTERN, CONSTRAINTS, "SHA256SUMS"]
    run = " ".join(rest for keyword, rest in instructions if keyword == "RUN")
    steps = image_checksum_commands()
    verify = " && ".join(steps)
    assert "--ignore-missing" not in verify, "unlisted inputs must not pass verification"
    assert steps[:2] == [f"set -- {WHEEL_PATTERN}", 'test "$#" -eq 1'], "exactly one wheel"
    assert CONSTRAINTS.replace(".", "\\.") in verify, "constraints pinned in the grep pattern"
    assert 'requirements-runtime.txt "$1"' in verify, "the copied wheel is the required one"
    assert verify.endswith("sha256sum --strict -c required.sha256")
    install = re.search(r"pip install (?P<args>.*?) &&", run)
    assert install is not None
    tokens = install.group("args").split()
    assert tokens[tokens.index("--constraint") + 1] == CONSTRAINTS
    assert tokens[-1] == '"./$1"', "only the verified staged wheel is installed"
    assert "-e" not in tokens and "--editable" not in tokens
    assert not any(t.startswith(("wled-mcp", "wled_mcp")) for t in tokens), "no index package"
    users = [rest for keyword, rest in instructions if keyword == "USER"]
    assert users == ["${APP_UID}:${APP_GID}"]
    assert ("ARG", "APP_UID=10001") in instructions
    assert ("ENTRYPOINT", '["wled-mcp"]') in instructions, "exec form, PID 1 gets SIGTERM"
    assert ("STOPSIGNAL", "SIGTERM") in instructions
    assert service()["image"] == f"wled-mcp:{IMAGE_TAG_PLACEHOLDER}"
    assert service()["pull_policy"] == "never"


def test_build_context_is_an_allowlist_of_the_release_inputs():
    assert (
        dockerignore_violations(
            DOCKERIGNORE.read_text("utf-8"), {WHEEL_PATTERN, CONSTRAINTS, "SHA256SUMS"}
        )
        == []
    )
    # The wheel rule admits release and non-release wheels, nothing else.
    for name in (wheel_name(), wheel_name("1.2.3"), wheel_name("1.2.3+g0123456789ab.dirty")):
        assert fnmatch.fnmatchcase(name, WHEEL_PATTERN), name
    for name in ("devices.toml", "wled_mcp-1.2.3.tar.gz", "other-1.2.3-py3-none-any.whl"):
        assert not fnmatch.fnmatchcase(name, WHEEL_PATTERN), name


def test_dockerignore_check_rejects_leaky_contexts():
    allowed = {wheel_name(), CONSTRAINTS}
    assert dockerignore_violations(f"*\n!{wheel_name()}\n!devices.toml\n", allowed) == [
        "unexpected rule '!devices.toml'"
    ]
    assert dockerignore_violations("secrets/\n.env\n", allowed)[0].startswith("first rule")
    assert dockerignore_violations(f"*\n!{wheel_name()}\n!*\n", allowed) == ["unexpected rule '!*'"]


def test_no_unpinned_artifact_reference_in_deployment_files():
    for path in deployment_files():
        text = path.read_text("utf-8")
        assert not re.search(r"(?<![\w-])latest\b", text), path
        for ref in re.findall(r"git\+\S+", text):
            assert re.search(r"@[0-9a-f]{40}\b", ref), f"{path}: unpinned Git source {ref}"
        assert not re.search(r"(?:^|\s)(?:-e|--editable)\s", text), path


def test_no_credential_literal_in_deployment_files():
    for path in deployment_files():
        assert token_literals(path.read_text("utf-8")) == [], path


def test_credential_literal_detector_finds_planted_values():
    planted = "synthetic-planted-credential-0123456789abcdef"
    assert token_literals(f'"Authorization": "Bearer {planted}"') == [planted]
    assert token_literals(f"WLED_MCP_HTTP_TOKEN={planted}") == [planted]
    assert token_literals(f"token: {planted}") == [planted]
    assert token_literals(f"Bearer {TOKEN_PLACEHOLDER}") == []
    assert token_literals("--http-token-file /run/secrets/wled_mcp_http_token") == []


# ------------------------------------------------------------------ stdio hub entry


def test_stdio_hub_example_runs_the_staged_release_with_constraints():
    entry = hub_stdio()
    args: list[str] = entry["args"]
    assert entry["command"] == "uvx"
    for arg in args:  # every argument is its own element
        assert arg == arg.strip() and " " not in arg
        assert not (arg.startswith("--") and "=" in arg)
    console_at = args.index("wled-mcp")
    uvx_args, console_args = args[:console_at], args[console_at + 1 :]
    assert option(console_args, "--transport") == "stdio"
    assert console_args[console_args.index("--transport") + 1] == "stdio"
    assert not HTTP_ONLY_FLAGS & set(console_args)
    assert option(uvx_args, "--python") == "3.13"
    constraints = Path(option(uvx_args, "--constraints"))
    wheel = Path(option(uvx_args, "--from"))
    release = Path("/app/binaries/wled-mcp") / VERSION_PLACEHOLDER
    assert constraints == release / CONSTRAINTS
    assert wheel == release / wheel_name(VERSION_PLACEHOLDER)
    assert "--isolated" in uvx_args, "never fall back to a separately installed tool"
    data_dir = option(console_args, "--data-dir")
    assert option(console_args, "--config").startswith(f"{data_dir}/config/")
    env = entry["env"]
    assert set(env) == {"UV_CACHE_DIR", "UV_TOOL_DIR", "UV_PYTHON_INSTALL_DIR"}
    for value in env.values():
        assert value.startswith("/") and not value.startswith(f"{data_dir}/")
    assert "token" not in json.dumps(entry).casefold()


# ----------------------------------------------------- compose command, executed locally


def substituted_compose_command(
    config: Path, data: Path, token_file: Path, port: int
) -> tuple[list[str], str]:
    """The compose argv with only paths, bind and port replaced; returns the Host to send."""
    args = list(service()["command"])
    original_port = option(args, "--port")
    replacements = {
        "--config": str(config),
        "--data-dir": str(data),
        "--http-token-file": str(token_file),
        "--host": "127.0.0.1",  # tests bind loopback only, never 0.0.0.0
        "--port": str(port),
    }
    for index, token in enumerate(args[:-1]):
        if token in replacements:
            args[index + 1] = replacements[token]
    authority = urlsplit(hub_http()["url"]).netloc
    assert authority.endswith(f":{original_port}")
    host_header = f"{authority.removesuffix(f':{original_port}')}:{port}"
    args = [
        f"{a.removesuffix(f':{original_port}')}:{port}"
        if prev == "--allowed-host" and a.endswith(f":{original_port}")
        else a
        for prev, a in zip(["", *args[:-1]], args, strict=True)
    ]
    return args, host_header


@POSIX_ONLY
def test_compose_command_accepts_the_hub_example_connection(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "config").mkdir()
    config = data / "config" / "devices.toml"
    config.write_text("schema_version = 1\ndevices = []\n", encoding="utf-8")
    token = secrets.token_urlsafe(32)  # generated per run, never a committed literal
    token_file = tmp_path / "wled_mcp_http_token"
    token_file.write_text(token + "\n", encoding="utf-8")
    port = free_port()
    args, host_header = substituted_compose_command(config, data, token_file, port)
    headers = {
        name: value.replace(TOKEN_PLACEHOLDER, token)
        for name, value in hub_http()["headers"].items()
    }
    process = subprocess.Popen(
        [str(CONSOLE), *args],  # the image ENTRYPOINT plus the compose command
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=clean_env(),
        cwd=data,
    )
    assert process.stdout is not None and process.stderr is not None
    lines: queue.Queue[str] = queue.Queue()
    stderr = process.stderr
    threading.Thread(target=lambda: [lines.put(line) for line in stderr], daemon=True).start()
    try:
        wait_ready(lines, port)

        async def exercise() -> None:
            with anyio.fail_after(30):
                base = f"http://127.0.0.1:{port}/mcp"
                for mode in ("legacy", "auto"):
                    async with httpx.AsyncClient(headers={**headers, "Host": host_header}) as http:
                        transport = streamable_http_client(
                            base, http_client=http, terminate_on_close=False
                        )
                        async with Client(transport, mode=mode, read_timeout_seconds=10) as client:
                            tools = (await client.list_tools()).tools
                            assert [tool.name for tool in tools] == expected_names()
                            result = await client.call_tool("wled_list_devices", {})
                            assert result.structured_content["data"] == {"devices": []}
                body = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
                accept = {"Accept": "application/json, text/event-stream"}
                async with httpx.AsyncClient() as raw:
                    # Loopback authority is not in the compose allowlist: 403.
                    wrong_host = await raw.post(base, json=body, headers={**headers, **accept})
                    assert wrong_host.status_code == 403
                    # Hub authority without the credential: 401.
                    no_auth = await raw.post(
                        base, json=body, headers={"Host": host_header, **accept}
                    )
                    assert no_auth.status_code == 401

        anyio.run(exercise)
        process.send_signal(signal.SIGTERM)
        assert process.wait(timeout=30) == 0
        assert process.stdout.read() == ""
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
        process.stdout.close()
        process.stderr.close()
    assert sorted(p.name for p in data.iterdir()) == ["config"]
    assert token not in "".join(lines.queue), "the credential is never logged"


def test_compose_substitution_keeps_every_other_argument():
    original = service()["command"]
    args, host = substituted_compose_command(Path("/c"), Path("/d"), Path("/t"), 4321)
    assert len(args) == len(original)
    changed = {i for i, (a, b) in enumerate(zip(original, args, strict=True)) if a != b}
    flags = {original[i - 1] for i in changed}
    assert flags == {"--config", "--data-dir", "--http-token-file", "--host", "--port"} | {
        "--allowed-host"
    }
    assert host == "wled-mcp:4321" and option(args, "--allowed-host") == host


# ---------------------------------------------------------------- staging helper


def synthetic_wheel(directory: Path, wheel_version: str, name: str | None = None) -> Path:
    path = directory / (name or f"wled_mcp-{wheel_version}-py3-none-any.whl")
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            f"wled_mcp-{wheel_version}.dist-info/METADATA",
            f"Metadata-Version: 2.4\nName: wled-mcp\nVersion: {wheel_version}\n",
        )
    return path


def test_stage_release_writes_a_checksummed_immutable_directory(tmp_path):
    wheel = synthetic_wheel(tmp_path, version())
    output = tmp_path / "releases"
    target = stage(ROOT, wheel, output, "0" * 40, "clean")
    assert target == output / version()
    names = sorted(p.name for p in target.iterdir())
    assert names == sorted(
        [".dockerignore", "Dockerfile", "RELEASE", "SHA256SUMS", CONSTRAINTS, wheel.name]
    )
    sums = dict(
        reversed(line.split("  ", 1))
        for line in (target / "SHA256SUMS").read_text("utf-8").splitlines()
    )
    assert set(sums) == set(names) - {"SHA256SUMS", "RELEASE"}
    for name, digest in sums.items():
        assert hashlib.sha256((target / name).read_bytes()).hexdigest() == digest
    assert (target / CONSTRAINTS).read_bytes() == (ROOT / CONSTRAINTS).read_bytes()
    assert (target / ".dockerignore").read_bytes() == DOCKERIGNORE.read_bytes()
    assert (target / "RELEASE").read_text("utf-8").splitlines() == [
        f"version={version()}",
        f"source_commit={'0' * 40}",
        "source_tree=clean",
    ]
    # The staged directory is exactly the image build context the Dockerfile expects.
    context = {n for n in names if not dockerignore_violations(f"*\n!{n}\n", {n})}
    assert {wheel_name(), CONSTRAINTS, "SHA256SUMS"} <= context
    with pytest.raises(StageError, match="immutable"):
        stage(ROOT, wheel, output, "1" * 40, "clean")
    assert (target / "RELEASE").read_text("utf-8").count("0" * 40) == 1


@pytest.mark.parametrize(
    ("wheel_version", "name", "message"),
    [
        ("9.9.9", None, "Expected wheel"),
        ("9.9.9", f"wled_mcp-{version()}-py3-none-any.whl", "lacks wled-mcp metadata"),
    ],
)
def test_stage_release_rejects_a_wheel_of_another_version(tmp_path, wheel_version, name, message):
    wheel = synthetic_wheel(tmp_path, wheel_version, name)
    with pytest.raises(StageError, match=message):
        stage(ROOT, wheel, tmp_path / "releases", "0" * 40, "clean")
    assert not (tmp_path / "releases" / version()).exists()


def image_checksum_commands() -> list[str]:
    """Shell steps of the Dockerfile RUN that verify the copied release inputs."""
    joined = re.sub(r"\\\n", " ", DOCKERFILE.read_text("utf-8"))
    run = next(line for line in joined.splitlines() if line.startswith("RUN cd /tmp/wled-mcp-"))
    steps = [step.strip() for step in run.removeprefix("RUN ").split(" && ")]
    end = next(i for i, step in enumerate(steps) if step.startswith("python -m pip"))
    return steps[1:end]


def sums_without(sums: str, name: str) -> str:
    return "".join(line for line in sums.splitlines(True) if not line.endswith(f"  {name}\n"))


@pytest.mark.skipif(
    os.name == "nt" or shutil.which("sh") is None or shutil.which("sha256sum") is None,
    reason="runs the image's POSIX checksum step; needs sh and sha256sum",
)
@pytest.mark.parametrize(
    "tamper",
    [
        "none",
        "wheel line missing",
        "wheel line missing, wheel modified",
        "constraints line missing, constraints modified",
        "wheel line duplicated",
        "wheel modified",
        "only build-context lines",
    ],
)
def test_image_checksum_step_requires_both_staged_inputs(tmp_path, tamper):
    staged = stage(ROOT, synthetic_wheel(tmp_path, version()), tmp_path / "out", "0" * 40, "clean")
    # The image only receives the COPY sources, exactly as in /tmp/wled-mcp-release.
    work = tmp_path / "wled-mcp-release"
    work.mkdir()
    for name in (wheel_name(), CONSTRAINTS, "SHA256SUMS"):
        shutil.copyfile(staged / name, work / name)
    sums = (work / "SHA256SUMS").read_text("utf-8")
    wheel_line = next(
        line for line in sums.splitlines(True) if line.endswith(f"  {wheel_name()}\n")
    )
    if "wheel line missing" in tamper:
        sums = sums_without(sums, wheel_name())
    if "constraints line missing" in tamper:
        sums = sums_without(sums, CONSTRAINTS)
    if tamper == "wheel line duplicated":
        sums += wheel_line
    if tamper == "only build-context lines":
        sums = sums_without(sums_without(sums, wheel_name()), CONSTRAINTS)
    (work / "SHA256SUMS").write_text(sums, encoding="utf-8", newline="\n")
    if "wheel modified" in tamper:
        with (work / wheel_name()).open("ab") as stream:
            stream.write(b"tampered")
    if "constraints modified" in tamper:
        with (work / CONSTRAINTS).open("a", encoding="utf-8") as stream:
            stream.write("extra==1.0\n")
    result = subprocess.run(
        ["sh", "-c", " && ".join(image_checksum_commands())],
        cwd=work,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert (result.returncode == 0) is (tamper == "none"), result.stdout + result.stderr


# --------------------------------------------------------------- documented procedures


def code_lines(text: str) -> list[str]:
    blocks = re.findall(r"```[^\n]*\n(.*?)```", text, flags=re.S)
    return [line for block in blocks for line in re.sub(r"\\\n", " ", block).splitlines()]


def inline_code_spans(text: str) -> list[str]:
    prose = re.sub(r"```.*?```", "", text, flags=re.S)
    return [" ".join(span.split()) for span in re.findall(r"`([^`]+)`", prose)]


def container_command_problems(text: str, project: str) -> list[str]:
    """Scoping problems in fenced code lines and inline code spans of a document."""
    lines = code_lines(text) + inline_code_spans(text)
    problems = []
    for line in lines:
        if "docker compose" in line:
            if f"-p {project} " not in line:
                problems.append(f"unscoped compose command: {line}")
            if re.search(r"\s(-v|--volumes|--remove-orphans)\b", line):
                problems.append(f"volume/orphan removal: {line}")
        if "prune" in line:
            problems.append(f"prune: {line}")
        for image in re.findall(r"docker (?:rmi|image rm)\s+(\S+)", line):
            if not image.startswith("wled-mcp:"):
                problems.append(f"foreign image removal: {line}")
        if re.search(r"rm\s+-[a-z]*r[a-z]*\s+\S*backups", line):
            problems.append(f"backup removal: {line}")
    return problems


def test_documented_container_commands_touch_only_the_wled_mcp_project():
    project = compose()["name"]
    text = DEPLOYMENT.read_text("utf-8")
    fenced = [line for line in code_lines(text) if "docker compose" in line]
    inline = [span for span in inline_code_spans(text) if "docker compose" in span]
    assert len(fenced) >= 5, "start and inspection commands are documented in code blocks"
    assert len(inline) >= 2, "update and stop commands are documented inline"
    assert container_command_problems(text, project) == []


@pytest.mark.parametrize(
    ("scoped", "unscoped"),
    [
        (  # inline update command in prose
            "`docker compose -p wled-mcp-http -f compose.yaml up -d --no-deps wled-mcp`",
            "`docker compose up -d`",
        ),
        (  # inline stop command in prose
            "`docker compose -p wled-mcp-http -f compose.yaml stop wled-mcp`",
            "`docker compose -p mcphub stop`",
        ),
        (  # fenced recreation command
            "  docker compose -p wled-mcp-http -f compose.yaml up -d --no-deps --force-recreate",
            "  docker compose up -d --force-recreate",
        ),
    ],
)
def test_container_command_check_rejects_unscoped_commands(scoped, unscoped):
    text = DEPLOYMENT.read_text("utf-8")
    assert scoped in text
    problems = container_command_problems(text.replace(scoped, unscoped, 1), compose()["name"])
    assert any(p.startswith("unscoped compose command") for p in problems), problems


def test_documented_uvx_invocation_matches_the_stdio_hub_example():
    entry = hub_stdio()
    expected = " ".join([entry["command"], *entry["args"]])
    lines = [" ".join(line.split()) for line in code_lines(DEPLOYMENT.read_text("utf-8"))]
    assert expected in lines


# ------------------------------------------------------------- live-check documentation

VALIDATION = ROOT / "docs/VALIDATION.md"
LIVE_HEADING = "## Issue #11 live deployment check (2026-11-06)"
HARDWARE_HEADING = "## Issue #12 hardware acceptance (2026-11-06)"
RUN2_HEADING = "## Issue #12 hardware acceptance, run 2 (2026-11-06)"
# Committed live evidence must stay impersonal (AGENTS.md, DEC-005, DEC-009): the
# repository-wide rules of scripts/check_private_identifiers.py (private addresses, home
# paths, router-local DNS names, MAC addresses, ...) plus, for these live documents only,
# content-addressed image IDs (repository-wide they would hit uv.lock hashes).
IMAGE_ID = re.compile(r"sha256:[0-9a-f]{12,}")
PROJECT = ROOT / "docs/PROJECT.md"
LIVE_DOCUMENTS = [
    ROOT / "README.md",
    ROOT / "docs/QUICKSTARTS.md",
    PROJECT,
    VALIDATION,
    DEPLOYMENT,
    ROOT / "docs/TRACEABILITY.md",
    ROOT / "docs/decisions/issue-11.md",
    ROOT / "docs/decisions/issue-12.md",
    ROOT / "deploy/operations-record.template.md",
]


def markdown_section(text: str, heading: str) -> str:
    """The body of one second- or third-level section, up to the next heading of that level."""
    level = heading.split(" ", 1)[0]
    start = text.index(heading + "\n")
    following = re.search(rf"^{level} ", text[start + len(heading) :], flags=re.M)
    end = start + len(heading) + following.start() if following else len(text)
    return text[start:end]


def private_identifiers(text: str) -> list[str]:
    rule_hits = [finding.value for finding in identifier_scanner.scan_text("live.md", text)]
    return rule_hits + [match.group() for match in IMAGE_ID.finditer(text)]


@pytest.mark.parametrize("path", LIVE_DOCUMENTS, ids=lambda path: path.name)
def test_live_deployment_documents_carry_no_installation_identifiers(path):
    assert private_identifiers(path.read_text("utf-8")) == []


@pytest.mark.parametrize(
    "leak",
    [
        "base_url http://192.168.250.9",
        "blocked address 172.16.250.9",
        "address 10.0.0.7",
        "backup in /home/operator/backups",
        "host wled-desk.fritz.box",
        "MAC 02:00:5e:aa:bb:cc",
        "image sha256:0123456789abcdef0123456789abcdef",
    ],
)
@pytest.mark.parametrize(
    "heading",
    [
        LIVE_HEADING,
        HARDWARE_HEADING,
        RUN2_HEADING,
        "## Issue #12 hardware acceptance, run 3 (2026-11-06)",
    ],
)
def test_private_identifier_detector_catches_installation_details(leak, heading):
    section = markdown_section(VALIDATION.read_text("utf-8"), heading)
    assert private_identifiers(section) == []
    assert private_identifiers(section + "\n" + leak) != []


def test_private_identifier_detector_allows_loopback_wildcard_and_release_hashes():
    allowed = (
        "127.0.0.1:8000 0.0.0.0 wled-mcp:8000 Python 3.10.0.1 "
        "db0b2edde4d20a07f789d7192314d1e606acb50f319a"
    )
    assert private_identifiers(allowed) == []


STAGE_2_MOVE = "Moved to stage 2 per ISSUE-11-DEC-005:"
MOVED_TO_12 = "Moved to #12 per ISSUE-11-DEC-008:"
STILL_PENDING = "Not exercised and still pending:"
MOVED_LIVE_CHECKS = ("drain of an in-flight call", "load measurements")
FOLLOW_UP_HEADING = (
    "### Catalog/preset reads, stdio rebuild and hub container recreation (ISSUE-11-DEC-007)"
)


def live_scope_problems(section: str) -> list[str]:
    """What the #11 live section must state after ISSUE-11-DEC-005 to 008."""
    problems = []
    for heading in ("### Streamable HTTP service", "### stdio via uvx"):
        if heading + "\n" not in section:
            problems.append(f"missing mode: {heading}")
    if not re.search(r"from commit `([0-9a-f]{7,40})`", section):
        problems.append("the live record names no exercised source commit")
    removal_heading = "### HTTP service removal and redeploy (ISSUE-11-DEC-006)"
    if removal_heading + "\n" not in section:
        return [*problems, "HTTP service removal is not recorded as exercised"]
    removal = markdown_section(section, removal_heading)
    for step in ("rm --stop --force wled-mcp", "docker image rm", "Retained", "re-registration"):
        if step not in removal:
            problems.append(f"removal record lacks {step!r}")
    if STAGE_2_MOVE not in section or STILL_PENDING not in section:
        return [*problems, "stage-2 move or remaining-pending paragraph missing"]
    if MOVED_TO_12 not in section:
        return [*problems, "drain/load move to #12 is not recorded"]
    moved = section[section.index(STAGE_2_MOVE) : section.index(MOVED_TO_12)]
    moved_to_12 = " ".join(
        section[section.index(MOVED_TO_12) : section.index(STILL_PENDING)].split()
    )
    if "update and rollback between two releases" not in moved:
        problems.append("version update/rollback is not marked as moved to stage 2")
    for issue in ("issues/21", "issues/25"):
        if issue not in moved:
            problems.append(f"stage-2 move does not reference {issue}")
    pending = section[section.index(STILL_PENDING) :]
    for item in ("rollback", "removal of the HTTP service"):
        if item in pending:
            problems.append(f"{item!r} is still listed as pending in #11")
    if "hub container recreation" in pending.lower():
        problems.append("hub container recreation is still listed as pending in #11")
    for item in MOVED_LIVE_CHECKS:
        if item in pending:
            problems.append(f"{item!r} is still listed as pending in #11")
        if item not in moved_to_12:
            problems.append(f"{item!r} is not recorded as moved to #12")
    if "issues/12" not in moved_to_12:
        problems.append("drain/load move does not reference issues/12")
    if "(T21) remains the #11 evidence" not in moved_to_12:
        problems.append("automated drain coverage T21 is not kept as #11 evidence")
    if FOLLOW_UP_HEADING + "\n" not in section:
        return [*problems, "hub container recreation is not recorded as exercised"]
    follow_up = " ".join(markdown_section(section, FOLLOW_UP_HEADING).split())
    for fact in (
        "Hub container recreation",
        "same image before and after",
        "uv tree (49 MB) survived",
        "HTTP service | container not restarted",
        "`wled_list_presets`",
        "`wled_get_palettes`",
        "/json/eff",
        "No device writes were needed or performed",
        "identical to the baseline",
    ):
        if fact not in follow_up:
            problems.append(f"follow-up record lacks {fact!r}")
    if "Mode remaining active: Streamable HTTP" not in section:
        problems.append("the remaining active mode is not stated")
    return problems


def test_live_section_records_removal_hub_recreation_and_stage_2_move():
    assert live_scope_problems(markdown_section(VALIDATION.read_text("utf-8"), LIVE_HEADING)) == []


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (
            lambda text: text.replace("### HTTP service removal and redeploy", "### Removal"),
            "HTTP service removal is not recorded as exercised",
        ),
        (
            lambda text: text.replace(
                STILL_PENDING, STILL_PENDING + " removal of the HTTP service,"
            ),
            "'removal of the HTTP service' is still listed as pending in #11",
        ),
        (
            lambda text: text.replace(STILL_PENDING, STILL_PENDING + " update and rollback,"),
            "'rollback' is still listed as pending in #11",
        ),
        (
            lambda text: text.replace("issues/25", "issues/99"),
            "stage-2 move does not reference issues/25",
        ),
        (
            lambda text: text.replace(STAGE_2_MOVE, "Deferred:"),
            "stage-2 move or remaining-pending paragraph missing",
        ),
        (
            lambda text: text.replace(STILL_PENDING, STILL_PENDING + " hub container recreation,"),
            "hub container recreation is still listed as pending in #11",
        ),
        (
            lambda text: text.replace(FOLLOW_UP_HEADING, "### Further checks"),
            "hub container recreation is not recorded as exercised",
        ),
        (
            lambda text: text.replace("uv tree (49 MB) survived", "uv tree was rebuilt"),
            "follow-up record lacks 'uv tree (49 MB) survived'",
        ),
        (
            lambda text: text.replace("graceful drain of an in-flight call", "graceful shutdown"),
            "'drain of an in-flight call' is not recorded as moved to #12",
        ),
        (
            lambda text: text.replace(
                STILL_PENDING, STILL_PENDING + " drain of an in-flight call on the target,"
            ),
            "'drain of an in-flight call' is still listed as pending in #11",
        ),
        (
            lambda text: text.replace(STILL_PENDING, STILL_PENDING + " load measurements,"),
            "'load measurements' is still listed as pending in #11",
        ),
        (
            lambda text: text.replace(MOVED_TO_12, "Deferred elsewhere:"),
            "drain/load move to #12 is not recorded",
        ),
        (
            lambda text: text.replace(
                "tracked by\n[#12](https://github.com/descipar/wled-mcp/issues/12)", "tracked later"
            ),
            "drain/load move does not reference issues/12",
        ),
        (
            lambda text: text.replace("(T21) remains the #11 evidence", "(T21) is dropped"),
            "automated drain coverage T21 is not kept as #11 evidence",
        ),
        (
            lambda text: text.replace("docker image rm", "image deletion"),
            "removal record lacks 'docker image rm'",
        ),
        (
            lambda text: text.replace("load measurements", "load notes"),
            "'load measurements' is not recorded as moved to #12",
        ),
        (
            lambda text: text.replace(
                "No device writes were needed or performed", "Device writes were performed"
            ),
            "follow-up record lacks 'No device writes were needed or performed'",
        ),
        (
            lambda text: text.replace("were identical to", "differed from"),
            "follow-up record lacks 'identical to the baseline'",
        ),
    ],
)
def test_live_scope_check_rejects_regressions(mutate, expected):
    section = markdown_section(VALIDATION.read_text("utf-8"), LIVE_HEADING)
    assert live_scope_problems(section) == []
    assert expected in live_scope_problems(mutate(section))


TRACEABILITY = ROOT / "docs/TRACEABILITY.md"
HARDWARE_ANCHOR = "VALIDATION.md#issue-12-hardware-acceptance-2026-11-06"
RUN2_ANCHOR = "VALIDATION.md#issue-12-hardware-acceptance-run-2-2026-11-06"


def moved_drain_load_problems(texts: dict[str, str]) -> list[str]:
    """Drain/load live checks are tracked by #12 (ISSUE-11-DEC-008), not pending in #11."""
    problems = []
    rows = {
        line.split("|")[1].strip(): line
        for line in texts["TRACEABILITY.md"].splitlines()
        if line.startswith("| ")
    }
    for requirement, item in (
        ("MCP-04", "drain of an in-flight call"),
        ("OPS-01", "load measurements"),
    ):
        cells = [cell.strip() for cell in rows[requirement].split("|")]
        status = next((cell for cell in cells if cell.startswith("pending:")), "")
        clause = next((part for part in status.split(";") if item in part), "")
        if not clause:
            problems.append(f"{requirement} no longer names {item!r}")
        elif "(#11)" in clause or "issues/12" not in clause or "ISSUE-11-DEC-008" not in clause:
            problems.append(f"{requirement} does not track {item!r} by #12")
        elif HARDWARE_ANCHOR not in clause:
            problems.append(f"{requirement} does not link the #12 record for {item!r}")
    for name in ("PROJECT.md", "DEPLOYMENT.md"):
        flat = " ".join(texts[name].split())
        if "load measurements remain pending" in flat:
            problems.append(f"{name} still lists drain/load as pending")
        if "ISSUE-11-DEC-008" not in flat:
            problems.append(f"{name} does not reference ISSUE-11-DEC-008")
        if HARDWARE_ANCHOR not in flat:
            problems.append(f"{name} does not link the #12 hardware record")
        if RUN2_ANCHOR not in flat:
            problems.append(f"{name} does not link the #12 run-2 record")
        for issue in ("issues/66", "issues/67", "issues/70"):
            if issue not in flat:
                problems.append(f"{name} does not reference {issue}")
    return problems


def drain_load_texts() -> dict[str, str]:
    return {path.name: path.read_text("utf-8") for path in (TRACEABILITY, PROJECT, DEPLOYMENT)}


def test_drain_and_load_are_tracked_by_issue_12_not_pending_in_11():
    assert moved_drain_load_problems(drain_load_texts()) == []


@pytest.mark.parametrize(
    ("name", "old", "new", "expected"),
    [
        (
            "TRACEABILITY.md",
            "tracked by [#12](https://github.com/descipar/wled-mcp/issues/12) "
            "per ISSUE-11-DEC-008 (the stdio host",
            "(#11) (the stdio host",
            "MCP-04 does not track 'drain of an in-flight call' by #12",
        ),
        (
            "TRACEABILITY.md",
            "certainly in flight at the signal) recorded in "
            "[VALIDATION.md](VALIDATION.md#issue-12-hardware-acceptance-2026-11-06) and",
            "certainly in flight at the signal) and",
            "MCP-04 does not link the #12 record for 'drain of an in-flight call'",
        ),
        (
            "TRACEABILITY.md",
            "without the hub hop (not exercised, and",
            "without the hub hop (#11) (not exercised, and",
            "OPS-01 does not track 'load measurements' by #12",
        ),
        (
            "TRACEABILITY.md",
            "pending: load measurements on the target in stdio mode beyond the MCPHub rate "
            "limit and without the hub hop (not exercised, and not required for #12 per "
            "ISSUE-12-DEC-007, so no issue tracks them), after the load measurements moved",
            "pending: resource figures on the target in stdio mode beyond the MCPHub rate "
            "limit and without the hub hop (not exercised), after the figures moved",
            "OPS-01 no longer names 'load measurements'",
        ),
        (
            "PROJECT.md",
            "load measurements moved to #12 per ISSUE-11-DEC-008",
            "load measurements remain pending",
            "PROJECT.md still lists drain/load as pending",
        ),
        (
            "PROJECT.md",
            "(VALIDATION.md#issue-12-hardware-acceptance-2026-11-06)",
            "(VALIDATION.md)",
            "PROJECT.md does not link the #12 hardware record",
        ),
        (
            "PROJECT.md",
            "issues/66",
            "issues",
            "PROJECT.md does not reference issues/66",
        ),
        (
            "DEPLOYMENT.md",
            "load measurements moved to",
            "load measurements remain pending; see",
            "DEPLOYMENT.md still lists drain/load as pending",
        ),
        (
            "DEPLOYMENT.md",
            "issues/67",
            "issues",
            "DEPLOYMENT.md does not reference issues/67",
        ),
        (
            "DEPLOYMENT.md",
            "issues/70",
            "issues",
            "DEPLOYMENT.md does not reference issues/70",
        ),
        (
            "PROJECT.md",
            "(VALIDATION.md#issue-12-hardware-acceptance-run-2-2026-11-06)",
            "(VALIDATION.md)",
            "PROJECT.md does not link the #12 run-2 record",
        ),
    ],
)
def test_drain_load_tracking_check_rejects_regressions(name, old, new, expected):
    texts = drain_load_texts()
    assert old in texts[name]
    texts[name] = texts[name].replace(old, new)
    assert expected in moved_drain_load_problems(texts)


HARDWARE_FACTS = (
    "WLED 16.0.1",
    "no compatibility with other firmware, controllers or LED types",
    "Streamable HTTP only",
    "another WLED controller visible via the node list",
    "nothing was disabled",
    "issues/66",
    "issues/67",
    "`UNSUPPORTED_CAPABILITY`",
    "pre-existing state preset",
    "three snapshot files",
    "files mode 0600",
    "Attempt 1 | invalid as a drain sample",
    "not the moment the process received SIGTERM",
    "262,145 bytes: HTTP 413",
)
RESTORATION = {
    "R1 preset file": ("JSON-equal to the baseline", "blanks deleted entries with spaces"),
    "R2 state": ("byte-identical to the baseline",),
    "R3 configuration": ("byte-identical to the baseline",),
}
NOT_RUN_ITEMS = (
    "Visual check",
    "D3 drain of an in-flight write",
    "L4 peak concurrent connections",
    "stdio mode",
    "H07 offline device",
    "Controller reboot",
    "Activation of a preset saved by WLED 16",
    "issues/66",
)


def hardware_section_problems(section: str) -> list[str]:
    """What the #12 hardware record must state (ISSUE-12-DEC-001 to 003, TD-12-7)."""
    problems = []
    flat = " ".join(section.split())
    if "```text" not in section or "Restoration performed and verified:" not in section:
        problems.append("the evidence template is not used")
    for fact in HARDWARE_FACTS:
        if fact not in flat:
            problems.append(f"hardware record lacks {fact!r}")
    rows = {
        cells[0]: " ".join(cells[1:])
        for line in section.splitlines()
        if line.startswith("| ")
        for cells in [[cell.strip() for cell in line.strip().strip("|").split("|")]]
    }
    for check, facts in RESTORATION.items():
        if check not in rows:
            problems.append(f"restoration result {check!r} is missing")
            continue
        for fact in facts:
            if fact not in rows[check]:
                problems.append(f"{check} lacks {fact!r}")
    if "### Not run\n" not in section:
        return [*problems, "the not-run list is missing"]
    not_run = " ".join(markdown_section(section, "### Not run").split())
    for item in NOT_RUN_ITEMS:
        if item not in not_run:
            problems.append(f"not-run list lacks {item!r}")
    if re.search(r"\b(?:all|every) (?:firmware|controllers?)\b[^.]*\bsupported\b", flat, re.I):
        problems.append("the record makes a blanket compatibility claim")
    return problems


def test_hardware_section_records_restoration_not_run_list_and_findings():
    section = markdown_section(VALIDATION.read_text("utf-8"), HARDWARE_HEADING)
    assert hardware_section_problems(section) == []


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        (
            "| R1 preset file | JSON-equal",
            "| R1 preset file | restored",
            "R1 preset file lacks 'JSON-equal to the baseline'",
        ),
        (
            "| R2 state | byte-identical",
            "| R2 state | similar",
            "R2 state lacks 'byte-identical to the baseline'",
        ),
        (
            "| R3 configuration |",
            "| R3 config |",
            "restoration result 'R3 configuration' is missing",
        ),
        ("### Not run\n", "### Remaining\n", "the not-run list is missing"),
        (
            "- Visual check of the LEDs",
            "- Inspection of the LEDs",
            "not-run list lacks 'Visual check'",
        ),
        (
            "- Activation of a preset saved by WLED 16 (blocked by\n"
            "  [#66](https://github.com/descipar/wled-mcp/issues/66)).\n",
            "",
            "not-run list lacks 'Activation of a preset saved by WLED 16'",
        ),
        (
            "- L4 peak concurrent connections (not sampled).\n",
            "",
            "not-run list lacks 'L4 peak concurrent connections'",
        ),
        (
            "- H07 offline device on hardware",
            "- Offline device on hardware",
            "not-run list lacks 'H07 offline device'",
        ),
        (
            "Restoration performed and verified:",
            "Restoration:",
            "the evidence template is not used",
        ),
        (
            "not the moment the process received SIGTERM",
            "the moment of SIGTERM",
            "hardware record lacks 'not the moment the process received SIGTERM'",
        ),
        (
            "is claimed.",
            "is claimed. All firmware versions are supported.",
            "the record makes a blanket compatibility claim",
        ),
    ],
)
def test_hardware_section_check_rejects_regressions(old, new, expected):
    section = markdown_section(VALIDATION.read_text("utf-8"), HARDWARE_HEADING)
    assert hardware_section_problems(section) == []
    assert old in section
    assert expected in hardware_section_problems(section.replace(old, new))


RUN2_FACTS = (
    "ISSUE-12-DEC-005",
    "ISSUE-12-DEC-004",
    "WLED 16.0.1",
    "no compatibility with other firmware, controllers or LED types",
    "issues/70",
    "peak 64 established",
    "no write reported `uncertain`",
    "not the moment the process received SIGTERM",
    "HTTP 429",
    "answered by the hub itself",
    "the first load attempts were invalid",
)
RUN2_RESULTS = {
    "#66 re-check": ("issues/66", "hardware re-check: save then activate"),
    "stale-ID removal": ("H05 stale-ID removal on hardware passed",),
    "stdio drain finding": (
        "closed the connection without draining in-flight calls",
        "Connection closed",
        "read the state before retrying",
        "ISSUE-12-DEC-006 accepts this host behavior as a documented limitation of stdio mode",
    ),
}
RUN2_RESTORATION = {
    "R1 preset file": ("JSON-equal to the run-2 baseline", "blanks deleted entries with spaces"),
    "R2 state": ("byte-identical to the run-2 baseline",),
    "R3 configuration": ("byte-identical to the run-2 baseline",),
}
RUN2_VISUAL = {"A": "left blue, right red", "B": "all green", "C": "left blue, right red"}
RUN2_NOT_RUN = ("H07 offline device", "Controller reboot", "beyond the hub's rate limit")


def table_rows(section: str) -> dict[str, str]:
    return {
        cells[0]: " ".join(cells[1:])
        for line in section.splitlines()
        if line.startswith("| ")
        for cells in [[cell.strip() for cell in line.strip().strip("|").split("|")]]
    }


def run2_section_problems(section: str) -> list[str]:
    """What the #12 run-2 record must state (ISSUE-12-DEC-004/005, TD-12-7)."""
    problems = []
    flat = " ".join(section.split())
    if "```text" not in section or "Restoration performed and verified:" not in section:
        problems.append("the evidence template is not used")
    for fact in RUN2_FACTS:
        if fact not in flat:
            problems.append(f"run-2 record lacks {fact!r}")
    for result, facts in RUN2_RESULTS.items():
        for fact in facts:
            if fact not in flat:
                problems.append(f"run-2 {result} lacks {fact!r}")
    rows = table_rows(section)
    for check, reply in RUN2_VISUAL.items():
        if check not in rows:
            problems.append(f"visual check {check} is missing")
        elif reply not in rows[check]:
            problems.append(f"visual check {check} lacks the owner's observation")
    for check, facts in RUN2_RESTORATION.items():
        if check not in rows:
            problems.append(f"restoration result {check!r} is missing")
            continue
        for fact in facts:
            if fact not in rows[check]:
                problems.append(f"{check} lacks {fact!r}")
    if "### Not run\n" not in section:
        return [*problems, "the not-run list is missing"]
    not_run = " ".join(markdown_section(section, "### Not run").split())
    for item in RUN2_NOT_RUN:
        if item not in not_run:
            problems.append(f"not-run list lacks {item!r}")
    if re.search(r"\b(?:all|every) (?:firmware|controllers?)\b[^.]*\bsupported\b", flat, re.I):
        problems.append("the record makes a blanket compatibility claim")
    return problems


def test_run2_section_records_rechecks_visual_checks_stdio_drain_and_restoration():
    section = markdown_section(VALIDATION.read_text("utf-8"), RUN2_HEADING)
    assert run2_section_problems(section) == []


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        (
            "hardware re-check: save then\n  activate",
            "hardware re-check: deferred,\n  activate",
            "run-2 #66 re-check lacks 'hardware re-check: save then activate'",
        ),
        (
            "- H05 stale-ID removal on hardware passed",
            "- H05 stale-ID removal on hardware pending",
            "run-2 stale-ID removal lacks 'H05 stale-ID removal on hardware passed'",
        ),
        (
            "| C | `wled_activate_preset`",
            "| D | `wled_activate_preset`",
            "visual check C is missing",
        ),
        ('"all green"', '"no reply"', "visual check B lacks the owner's observation"),
        (
            "it closed the connection without draining in-flight calls",
            "it drained in-flight calls",
            "run-2 stdio drain finding lacks "
            "'closed the connection without draining in-flight calls'",
        ),
        (
            "so a client has to read the state\nbefore retrying it",
            "so a client may retry it",
            "run-2 stdio drain finding lacks 'read the state before retrying'",
        ),
        (
            "ISSUE-12-DEC-006 accepts this host behavior",
            "The host behavior is open",
            "run-2 stdio drain finding lacks 'ISSUE-12-DEC-006 accepts this host behavior "
            "as a documented limitation of stdio mode'",
        ),
        (
            "JSON-equal to the run-2 baseline",
            "equal to the run-2 baseline",
            "R1 preset file lacks 'JSON-equal to the run-2 baseline'",
        ),
        (
            "| R2 state | byte-identical to the run-2 baseline",
            "| R2 state | byte-identical to the run-1 baseline",
            "R2 state lacks 'byte-identical to the run-2 baseline'",
        ),
        (
            "| R3 configuration |",
            "| R3 config |",
            "restoration result 'R3 configuration' is missing",
        ),
        (
            "- Controller reboot and power-cycle",
            "- Power-cycle",
            "not-run list lacks 'Controller reboot'",
        ),
        (
            "Disclosure: the first load attempts were invalid",
            "Disclosure: all load attempts were valid",
            "run-2 record lacks 'the first load attempts were invalid'",
        ),
        (
            "tracked by\n[#70](https://github.com/descipar/wled-mcp/issues/70)",
            "tracked later",
            "run-2 record lacks 'issues/70'",
        ),
        (
            "is claimed.\n",
            "is claimed. Every controller is supported.\n",
            "the record makes a blanket compatibility claim",
        ),
    ],
)
def test_run2_section_check_rejects_regressions(old, new, expected):
    section = markdown_section(VALIDATION.read_text("utf-8"), RUN2_HEADING)
    assert run2_section_problems(section) == []
    assert old in section
    assert expected in run2_section_problems(section.replace(old, new))


RUN2_FORWARD_REFERENCE = "[run 2](#issue-12-hardware-acceptance-run-2-2026-11-06)"


def test_run1_not_run_list_points_forward_to_run2():
    run1 = markdown_section(VALIDATION.read_text("utf-8"), HARDWARE_HEADING)
    assert RUN2_FORWARD_REFERENCE in markdown_section(run1, "### Not run")
    assert RUN2_HEADING not in run1
    # Run-1 history stays: its not-run items are not removed by the forward reference.
    assert hardware_section_problems(run1) == []


RUN3_HEADING = "## Issue #12 hardware acceptance, run 3 (2026-11-06)"
RUN3_ANCHOR = "VALIDATION.md#issue-12-hardware-acceptance-run-3-2026-11-06"
RUN3_FORWARD_REFERENCE = "[run 3](#issue-12-hardware-acceptance-run-3-2026-11-06)"
RUN3_FACTS = (
    "ISSUE-12-DEC-007 item 2",
    "ISSUE-12-DEC-001",
    "WLED 16.0.1",
    "no compatibility with other firmware, controllers or LED types",
    "no deployment, service, hub or inventory change",
    "Authorization basis for E3",
    "explicitly asked for the repeats of E3",
    "The only exception is the first dimming call of attempt 2",
)
RUN3_VISUAL = {
    "E1": ("effect ID 9", "slowly moving rainbow"),
    "E2": ("speed 240", "faster, clearly"),
    "E3 attempt 1": ("no dimming visible",),
    "E3 attempt 2": ("no dimming visible",),
    "E3 attempt 3": ("below the cap", "gently became darker"),
}
RUN3_RESULTS = {
    "current-limiter explanation": (
        "analysis, not a measurement",
        "most likely cause is the controller's current limiter (ABL)",
        "850 mA (the configured limit) for solid red at brightness 80",
        "645 mA, below the cap, for solid red at brightness 40",
        "No power reading was taken for the rainbow in run 3",
        "have to start below the cap",
    ),
    "TIMEOUT note": (
        "returned `TIMEOUT` with application `not_attempted`",
        "the brightness unchanged",
        "not a blind replay",
        "the cause of the expired deadline is unknown",
    ),
}
RUN3_RESTORATION = {
    "R1 preset file": "byte-identical to the run-3 baseline",
    "R2 state": "byte-identical to the run-3 baseline",
    "R3 configuration": "byte-identical to the run-3 baseline",
}
# Each remaining run-2 item and the ISSUE-12-DEC-007 item that resolves it.
RUN3_RESOLUTIONS = {
    "H02 comparison with the WLED UI": "ISSUE-12-DEC-007 item 1",
    "H04 visible effect animation, speed and brightness transition": "ISSUE-12-DEC-007 item 2",
    "H04 in stdio mode": "ISSUE-12-DEC-007 item 3",
    "stdio drain on SIGTERM": "ISSUE-12-DEC-007 item 4",
    "stdio load beyond the hub's rate limit and without the hub hop": "ISSUE-12-DEC-007 item 5",
    "H07 offline device on hardware": "ISSUE-12-DEC-007 item 6",
}


def run3_section_problems(section: str) -> list[str]:
    """What the #12 run-3 record must state (ISSUE-12-DEC-007, TD-12-7)."""
    problems = []
    flat = " ".join(section.split())
    if "```text" not in section or "Restoration performed and verified:" not in section:
        problems.append("the evidence template is not used")
    for fact in RUN3_FACTS:
        if fact not in flat:
            problems.append(f"run-3 record lacks {fact!r}")
    for result, facts in RUN3_RESULTS.items():
        for fact in facts:
            if fact not in flat:
                problems.append(f"run-3 {result} lacks {fact!r}")
    rows = table_rows(section)
    for check, facts in RUN3_VISUAL.items():
        if check not in rows:
            problems.append(f"check {check} is missing")
            continue
        for fact in facts:
            if fact not in rows[check]:
                problems.append(f"check {check} lacks {fact!r}")
    for check, fact in RUN3_RESTORATION.items():
        if check not in rows:
            problems.append(f"restoration result {check!r} is missing")
        elif fact not in rows[check]:
            problems.append(f"{check} lacks {fact!r}")
    for item, decision in RUN3_RESOLUTIONS.items():
        if item not in rows:
            problems.append(f"remaining item {item!r} has no resolution")
        elif decision not in rows[item]:
            problems.append(f"remaining item {item!r} does not cite {decision}")
    if "issues/25" not in rows.get("H07 offline device on hardware", ""):
        problems.append("the H07 move does not reference issues/25")
    if "### Not run\n" not in section:
        return [*problems, "the not-run list is missing"]
    not_run = " ".join(markdown_section(section, "### Not run").split())
    for item in ("intensity", "H07 offline device", "Controller reboot", "cause of the `TIMEOUT`"):
        if item not in not_run:
            problems.append(f"not-run list lacks {item!r}")
    if "not needed for #12 per ISSUE-12-DEC-008" not in not_run:
        problems.append("the intensity item does not cite ISSUE-12-DEC-008")
    if re.search(r"\b(?:all|every) (?:firmware|controllers?)\b[^.]*\bsupported\b", flat, re.I):
        problems.append("the record makes a blanket compatibility claim")
    return problems


def test_run3_section_records_visible_checks_limiter_timeout_and_resolutions():
    section = markdown_section(VALIDATION.read_text("utf-8"), RUN3_HEADING)
    assert run3_section_problems(section) == []


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ('"yes": a slowly moving rainbow', '"no reply"', "check E1 lacks 'slowly moving rainbow'"),
        ('"faster, clearly"', '"no change"', "check E2 lacks 'faster, clearly'"),
        (
            "Authorization basis for E3: the owner's agreement",
            "Note: the owner's agreement",
            "run-3 record lacks 'Authorization basis for E3'",
        ),
        ("| E3 attempt 3 |", "| E3 attempt 4 |", "check E3 attempt 3 is missing"),
        (
            '"yes, gently became darker"',
            "not visible",
            "check E3 attempt 3 lacks 'gently became darker'",
        ),
        (
            "(analysis, not a measurement)",
            "(measured)",
            "run-3 current-limiter explanation lacks 'analysis, not a measurement'",
        ),
        (
            "No power reading was taken for the rainbow in\n  run 3",
            "The power estimate was at the cap for the rainbow in\n  run 3",
            "run-3 current-limiter explanation lacks "
            "'No power reading was taken for the rainbow in run 3'",
        ),
        (
            "and 645 mA, below the\n  cap, for solid red",
            "and 700 mA, below the\n  cap, for solid red",
            "run-3 current-limiter explanation lacks "
            "'645 mA, below the cap, for solid red at brightness 40'",
        ),
        (
            "The only exception is the first dimming\ncall of attempt 2",
            "All writes were\ncalls of attempt 2",
            "run-3 record lacks 'The only exception is the first dimming call of attempt 2'",
        ),
        (
            "(not a blind replay\nof a possibly applied write)",
            "(a retry)",
            "run-3 TIMEOUT note lacks 'not a blind replay'",
        ),
        (
            "the cause of the expired deadline is unknown",
            "the cause was a slow device",
            "run-3 TIMEOUT note lacks 'the cause of the expired deadline is unknown'",
        ),
        (
            "| R2 state | byte-identical to the run-3 baseline",
            "| R2 state | similar to the run-3 baseline",
            "R2 state lacks 'byte-identical to the run-3 baseline'",
        ),
        (
            "| R1 preset file |",
            "| R1 presets |",
            "restoration result 'R1 preset file' is missing",
        ),
        (
            "per ISSUE-12-DEC-007 item 1 |",
            "per the coordinator |",
            "remaining item 'H02 comparison with the WLED UI' does not cite "
            "ISSUE-12-DEC-007 item 1",
        ),
        (
            "| stdio drain on SIGTERM |",
            "| stdio drain |",
            "remaining item 'stdio drain on SIGTERM' has no resolution",
        ),
        (
            "moved to stage 2 ([#25](https://github.com/descipar/wled-mcp/issues/25)) per "
            "ISSUE-12-DEC-007 item 6",
            "moved to stage 2 per ISSUE-12-DEC-007 item 6",
            "the H07 move does not reference issues/25",
        ),
        (
            "- A visual intensity change (not part of this run; not needed for #12 per\n"
            "  ISSUE-12-DEC-008, which accepts the verified intensity readback of run 1 H04 "
            "plus the\n"
            "  visible speed change E2).\n",
            "",
            "not-run list lacks 'intensity'",
        ),
        (
            "(not part of this run; not needed for #12 per\n  ISSUE-12-DEC-008,",
            "(not part of this run; pending,",
            "the intensity item does not cite ISSUE-12-DEC-008",
        ),
        (
            "- The cause of the `TIMEOUT` before dispatch",
            "- The timeout",
            "not-run list lacks 'cause of the `TIMEOUT`'",
        ),
        (
            "is claimed.\n",
            "is claimed. All firmware is supported.\n",
            "the record makes a blanket compatibility claim",
        ),
    ],
)
def test_run3_section_check_rejects_regressions(old, new, expected):
    section = markdown_section(VALIDATION.read_text("utf-8"), RUN3_HEADING)
    assert run3_section_problems(section) == []
    assert old in section
    assert expected in run3_section_problems(section.replace(old, new))


def test_run2_not_run_list_points_forward_to_run3_and_keeps_its_history():
    text = VALIDATION.read_text("utf-8")
    run2 = markdown_section(text, RUN2_HEADING)
    assert RUN3_FORWARD_REFERENCE in markdown_section(run2, "### Not run")
    assert RUN3_HEADING not in run2
    assert run2_section_problems(run2) == []


def dec007_problems(texts: dict[str, str]) -> list[str]:
    """Items resolved by run 3 or ISSUE-12-DEC-007 are no longer pending for #12."""
    problems = []
    rows = {
        line.split("|")[1].strip(): line.split("|")[-2].strip()
        for line in texts["TRACEABILITY.md"].splitlines()
        if line.startswith("| ")
    }
    for requirement, stale in (
        ("READ-02", "visual comparison with the WLED UI"),
        ("CTRL-01", "pending: visible effect animation"),
        ("SEG-04", "pending: visible effect animation"),
        ("TEST-01", "the visual comparison with the WLED UI"),
    ):
        if stale in rows[requirement]:
            problems.append(f"{requirement} still lists {stale!r} as pending")
    for requirement in ("DEV-02", "REL-01", "TEST-01"):
        cell = rows[requirement]
        if "H07 (#12)" in cell or "observation (#12)" in cell:
            problems.append(f"{requirement} still tracks H07 by #12")
        if "issues/25" not in cell or "ISSUE-12-DEC-007" not in cell:
            problems.append(f"{requirement} does not move H07 to #25 per ISSUE-12-DEC-007")
    intensity = next(
        (part for part in rows["CTRL-01"].split(";") if "visual intensity change" in part), ""
    )
    if "ISSUE-12-DEC-008" not in intensity:
        problems.append("CTRL-01 does not resolve the visual intensity change per ISSUE-12-DEC-008")
    if "visual intensity change" in rows["CTRL-01"].split(";")[0]:
        problems.append("CTRL-01 still lists the visual intensity change as pending")
    for requirement in ("READ-02", "CTRL-01", "MCP-04", "OPS-01"):
        if "ISSUE-12-DEC-007" not in rows[requirement]:
            problems.append(f"{requirement} does not cite ISSUE-12-DEC-007")
    for requirement in ("CTRL-01", "SEG-04", "REL-01"):
        if RUN3_ANCHOR not in rows[requirement]:
            problems.append(f"{requirement} does not link the #12 run-3 record")
    if "tracked by [#12](https://github.com/descipar/wled-mcp/issues/12)" in rows["OPS-01"]:
        problems.append("OPS-01 still tracks stdio load beyond the rate limit by #12")
    for name in ("PROJECT.md", "DEPLOYMENT.md"):
        flat = " ".join(texts[name].split())
        if RUN3_ANCHOR not in flat:
            problems.append(f"{name} does not link the #12 run-3 record")
        if "issues/25" not in flat or "ISSUE-12-DEC-007" not in flat:
            problems.append(f"{name} does not state the DEC-007 scope with #25")
    if "H07, the visual comparison with the WLED UI" in texts["PROJECT.md"]:
        problems.append("PROJECT.md still lists the UI comparison as pending")
    if not re.search(r"current-limiter \(ABL\) cap", " ".join(texts["DEPLOYMENT.md"].split())):
        problems.append("DEPLOYMENT.md lacks the current-limiter guidance")
    h04 = " ".join(
        markdown_section(texts["VALIDATION.md"], "## Opt-in physical write checks").split()
    )
    if "stay below the controller's current-limiter (ABL) cap" not in h04 or "leds.pwr" not in h04:
        problems.append("VALIDATION.md H04 guidance lacks the current-limiter note")
    heading = re.search(r"^## ISSUE-12-DEC-007 .*$", texts["issue-12.md"], flags=re.M)
    entry = markdown_section(texts["issue-12.md"], heading.group()) if heading else ""
    if "Authority: human decision." not in entry or "issues/25" not in entry:
        problems.append("issue-12.md lacks the human ISSUE-12-DEC-007 entry")
    if "[ISSUE-12-DEC-007](decisions/issue-12.md)" not in texts["DECISIONS.md"]:
        problems.append("DECISIONS.md lacks the ISSUE-12-DEC-007 pointer")
    if "[ISSUE-12-DEC-008](decisions/issue-12.md)" not in texts["DECISIONS.md"]:
        problems.append("DECISIONS.md lacks the ISSUE-12-DEC-008 pointer")
    heading8 = re.search(r"^## ISSUE-12-DEC-008 .*$", texts["issue-12.md"], flags=re.M)
    entry8 = markdown_section(texts["issue-12.md"], heading8.group()) if heading8 else ""
    if "Authority: human decision." not in entry8:
        problems.append("issue-12.md lacks the human ISSUE-12-DEC-008 entry")
    return problems


def dec007_texts() -> dict[str, str]:
    return {
        path.name: path.read_text("utf-8")
        for path in (
            TRACEABILITY,
            PROJECT,
            DEPLOYMENT,
            VALIDATION,
            ROOT / "docs/decisions/issue-12.md",
            ROOT / "docs/DECISIONS.md",
        )
    }


def test_dec007_resolutions_are_reflected_in_traceability_project_and_guidance():
    assert dec007_problems(dec007_texts()) == []


@pytest.mark.parametrize(
    ("name", "old", "new", "expected"),
    [
        (
            "TRACEABILITY.md",
            "| pending: live H07 offline observation, moved to stage 2",
            "| pending: H07 offline observation (#12), moved to stage 2",
            "DEV-02 still tracks H07 by #12",
        ),
        (
            "TRACEABILITY.md",
            "| pending: live H07, moved to stage 2 "
            "([#25](https://github.com/descipar/wled-mcp/issues/25)) per ISSUE-12-DEC-007;",
            "| pending: live H07 (#12);",
            "REL-01 does not move H07 to #25 per ISSUE-12-DEC-007",
        ),
        (
            "TRACEABILITY.md",
            "| pending: controllers and firmware other than WLED 16.0.1 (no compatibility "
            "claim); the H02 comparison",
            "| pending: visual comparison with the WLED UI; the H02 comparison",
            "READ-02 still lists 'visual comparison with the WLED UI' as pending",
        ),
        (
            "TRACEABILITY.md",
            "| pending: RGBW/CCT colors and controllers",
            "| pending: visible effect animation, RGBW/CCT colors and controllers",
            "CTRL-01 still lists 'pending: visible effect animation' as pending",
        ),
        (
            "TRACEABILITY.md",
            "(not exercised, and not required for #12 per ISSUE-12-DEC-007, so no issue tracks "
            "them), after the load measurements moved to",
            "(not exercised), tracked by",
            "OPS-01 still tracks stdio load beyond the rate limit by #12",
        ),
        (
            "TRACEABILITY.md",
            "a visual intensity change is not required for #12 per ISSUE-12-DEC-008",
            "a visual intensity change is not required for #12",
            "CTRL-01 does not resolve the visual intensity change per ISSUE-12-DEC-008",
        ),
        (
            "TRACEABILITY.md",
            "(one RGB-only controller only); a visual intensity change",
            "(one RGB-only controller only), a visual intensity change",
            "CTRL-01 still lists the visual intensity change as pending",
        ),
        (
            "DECISIONS.md",
            "[ISSUE-12-DEC-008](decisions/issue-12.md)",
            "ISSUE-12-DEC-008",
            "DECISIONS.md lacks the ISSUE-12-DEC-008 pointer",
        ),
        (
            "PROJECT.md",
            "(VALIDATION.md#issue-12-hardware-acceptance-run-3-2026-11-06)",
            "(VALIDATION.md)",
            "PROJECT.md does not link the #12 run-3 record",
        ),
        (
            "DEPLOYMENT.md",
            "stay below its current-limiter (ABL) cap",
            "check the output",
            "DEPLOYMENT.md lacks the current-limiter guidance",
        ),
        (
            "VALIDATION.md",
            "must stay below the controller's current-limiter\n(ABL) cap",
            "should be watched",
            "VALIDATION.md H04 guidance lacks the current-limiter note",
        ),
        (
            "issue-12.md",
            "## ISSUE-12-DEC-007 — Remaining #12 scope",
            "## ISSUE-12-DEC-008 — Remaining #12 scope",
            "issue-12.md lacks the human ISSUE-12-DEC-007 entry",
        ),
        (
            "DECISIONS.md",
            "[ISSUE-12-DEC-007](decisions/issue-12.md)",
            "ISSUE-12-DEC-007",
            "DECISIONS.md lacks the ISSUE-12-DEC-007 pointer",
        ),
    ],
)
def test_dec007_check_rejects_regressions(name, old, new, expected):
    texts = dec007_texts()
    assert old in texts[name]
    texts[name] = texts[name].replace(old, new, 1)
    assert expected in dec007_problems(texts)


def test_hub_http_registration_points_to_owner_and_reload_requirements():
    text = DEPLOYMENT.read_text("utf-8")
    registration = markdown_section(text, "## HTTP service: build, start, verify")
    assert "(#mcphub-notes)" in registration
    notes = markdown_section(text, "### MCPHub notes")
    assert re.search(r"owner[^.]*admin user", notes), "SSRF guard needs an admin-owned entry"
    assert re.search(r"reload[^.]*entry", notes), "an edited entry needs a reload"
    assert "Do not disable the hub's guard" in notes
    assert "owner" not in json.dumps(hub_http()), "ownership is hub-side, not in the example"


@pytest.mark.skipif(
    os.environ.get("WLED_MCP_DOCKER_CHECKS") != "1" or shutil.which("docker") is None,
    reason="opt-in local Docker check (WLED_MCP_DOCKER_CHECKS=1); never required in CI",
)
def test_docker_compose_accepts_the_example(tmp_path):
    deployed = tmp_path / "compose.yaml"
    shutil.copyfile(COMPOSE, deployed)
    (tmp_path / "secrets").mkdir()
    (tmp_path / "secrets" / "wled_mcp_http_token").write_text("unused", encoding="utf-8")
    result = subprocess.run(
        ["docker", "compose", "-f", str(deployed), "config", "--format", "json"],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    rendered = json.loads(result.stdout)
    assert rendered["name"] == compose()["name"]
    assert rendered["services"]["wled-mcp"]["command"] == service()["command"]
