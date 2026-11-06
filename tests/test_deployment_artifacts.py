"""Issue #11: consistency of the deployment artifacts for both transport modes.

Cross-checks the Dockerfile, its allowlist build context, the Compose example, both hub
examples, the staging helper and the deployment documentation against each other and
against the installed console. Runs the Compose command and the hub HTTP header shape
against the installed console on ``127.0.0.1`` only. No Docker daemon, hub, LAN device
or network beyond loopback is needed; the optional ``docker compose config`` check is
opt-in (``WLED_MCP_DOCKER_CHECKS=1``).
"""

from __future__ import annotations

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


def wheel_name() -> str:
    return f"wled_mcp-{version()}-py3-none-any.whl"


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
    assert sources == [wheel_name(), CONSTRAINTS, "SHA256SUMS"]
    run = " ".join(rest for keyword, rest in instructions if keyword == "RUN")
    verify = " && ".join(image_checksum_commands())
    assert "--ignore-missing" not in verify, "unlisted inputs must not pass verification"
    for name in (wheel_name(), CONSTRAINTS):  # both pinned by name in the grep pattern
        assert name.replace(".", "\\.") in verify, name
    assert verify.endswith("sha256sum --strict -c required.sha256")
    install = re.search(r"pip install (?P<args>.*?) &&", run)
    assert install is not None
    tokens = install.group("args").split()
    assert tokens[tokens.index("--constraint") + 1] == CONSTRAINTS
    assert tokens[-1] == f"./{wheel_name()}", "only the staged wheel is installed"
    assert "-e" not in tokens and "--editable" not in tokens
    assert not any(t.startswith(("wled-mcp", "wled_mcp")) for t in tokens), "no index package"
    users = [rest for keyword, rest in instructions if keyword == "USER"]
    assert users == ["${APP_UID}:${APP_GID}"]
    assert ("ARG", "APP_UID=10001") in instructions
    assert ("ENTRYPOINT", '["wled-mcp"]') in instructions, "exec form, PID 1 gets SIGTERM"
    assert ("STOPSIGNAL", "SIGTERM") in instructions
    assert service()["image"] == f"wled-mcp:{version()}"
    assert service()["pull_policy"] == "never"


def test_build_context_is_an_allowlist_of_the_release_inputs():
    assert (
        dockerignore_violations(
            DOCKERIGNORE.read_text("utf-8"), {wheel_name(), CONSTRAINTS, "SHA256SUMS"}
        )
        == []
    )


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
    release = Path("/app/binaries/wled-mcp") / version()
    assert constraints == release / CONSTRAINTS and wheel == release / wheel_name()
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
                            assert len((await client.list_tools()).tools) == 12
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
# Committed live evidence must stay impersonal (AGENTS.md, DEC-005): no private addresses,
# home paths, router-local DNS names, MAC addresses or content-addressed image IDs.
PRIVATE_IDENTIFIER = re.compile(
    r"(?<![\d.])(?:10\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])|192\.168|169\.254)"
    r"\.\d{1,3}\.\d{1,3}(?![\d.]*\d)"
    r"|/home/|/Users/|\.fritz\.box\b|\.home\.arpa\b"
    r"|\b[0-9A-Fa-f]{2}(?:[:-][0-9A-Fa-f]{2}){5}\b"
    r"|sha256:[0-9a-f]{12,}",
)
LIVE_DOCUMENTS = [
    ROOT / "README.md",
    VALIDATION,
    DEPLOYMENT,
    ROOT / "docs/TRACEABILITY.md",
    ROOT / "docs/decisions/issue-11.md",
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
    return [match.group() for match in PRIVATE_IDENTIFIER.finditer(text)]


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
def test_private_identifier_detector_catches_installation_details(leak):
    section = markdown_section(VALIDATION.read_text("utf-8"), LIVE_HEADING)
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
    for name in ("README.md", "DEPLOYMENT.md"):
        flat = " ".join(texts[name].split())
        if "load measurements remain pending" in flat:
            problems.append(f"{name} still lists drain/load as pending")
        if "ISSUE-11-DEC-008" not in flat:
            problems.append(f"{name} does not reference ISSUE-11-DEC-008")
    return problems


def drain_load_texts() -> dict[str, str]:
    return {
        path.name: path.read_text("utf-8")
        for path in (TRACEABILITY, ROOT / "README.md", DEPLOYMENT)
    }


def test_drain_and_load_are_tracked_by_issue_12_not_pending_in_11():
    assert moved_drain_load_problems(drain_load_texts()) == []


@pytest.mark.parametrize(
    ("name", "old", "new", "expected"),
    [
        (
            "TRACEABILITY.md",
            "on the target, moved to [#12](https://github.com/descipar/wled-mcp/issues/12) "
            "per ISSUE-11-DEC-008; version",
            "on the target (#11); version",
            "MCP-04 does not track 'drain of an in-flight call' by #12",
        ),
        (
            "TRACEABILITY.md",
            "load measurements on the target, moved to",
            "load measurements on the target (#11), moved to",
            "OPS-01 does not track 'load measurements' by #12",
        ),
        (
            "TRACEABILITY.md",
            "pending: load measurements on the target,",
            "pending: resource figures on the target,",
            "OPS-01 no longer names 'load measurements'",
        ),
        (
            "README.md",
            "load measurements are tracked by #12 per ISSUE-11-DEC-008",
            "load measurements remain pending",
            "README.md still lists drain/load as pending",
        ),
        (
            "DEPLOYMENT.md",
            "load measurements are tracked by",
            "load measurements remain pending; see",
            "DEPLOYMENT.md still lists drain/load as pending",
        ),
    ],
)
def test_drain_load_tracking_check_rejects_regressions(name, old, new, expected):
    texts = drain_load_texts()
    assert old in texts[name]
    texts[name] = texts[name].replace(old, new)
    assert expected in moved_drain_load_problems(texts)


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
