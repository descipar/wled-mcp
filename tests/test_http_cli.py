"""Console-level Streamable HTTP tests: fail-closed startup, real process, signals.

Real subprocesses bind only ``127.0.0.1`` ports; devices are empty or a synthetic
loopback fake. Nothing contacts a LAN device.
"""

import json
import os
import queue
import signal
import socket
import subprocess
import sys
import textwrap
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import anyio
import httpx2 as httpx
import pytest
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters
from mcp.client.streamable_http import streamable_http_client

from tests.state_catalog_support import EFFECTS, FXDATA, PALETTES, make_info, make_state

ROOT = Path(__file__).resolve().parents[1]
CONSOLE = Path(sys.executable).parent / ("wled-mcp.exe" if os.name == "nt" else "wled-mcp")
TOKEN = "synthetic-console-token-0123456789abcdef"
MARKER = "synthetic-marker-never-echo"
POSIX_ONLY = pytest.mark.skipif(
    os.name == "nt", reason="POSIX signal delivery; Windows relies on the in-process shutdown tests"
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def clean_env(**extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("WLED_MCP_")}
    env.update(extra)
    return env


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def write_config(tmp_path: Path, devices: str = "") -> Path:
    config = tmp_path / "service.toml"
    config.write_text(f"schema_version = 1\ndevices = [{devices}]\n", encoding="utf-8")
    return config


@contextmanager
def console(
    config: Path, tmp_path: Path, *args: str, env: dict[str, str] | None = None
) -> Iterator[tuple[subprocess.Popen[str], queue.Queue[str]]]:
    process = subprocess.Popen(
        [str(CONSOLE), "--config", str(config), "--data-dir", str(tmp_path), *args],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env if env is not None else clean_env(),
        cwd=tmp_path,
    )
    lines: queue.Queue[str] = queue.Queue()
    threading.Thread(
        target=lambda: [lines.put(line) for line in process.stderr], daemon=True
    ).start()
    try:
        yield process, lines
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
        process.stdout.close()
        process.stderr.close()


def wait_ready(lines: queue.Queue[str], port: int) -> list[str]:
    seen: list[str] = []
    while True:
        line = lines.get(timeout=20)
        seen.append(line)
        if f"listening on 127.0.0.1:{port} path /mcp" in line:
            return seen


# ===================================================================== fail-closed startup


def run_failing(
    tmp_path: Path, args: list[str], env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    config = write_config(tmp_path)
    return subprocess.run(
        [str(CONSOLE), "--config", str(config), "--data-dir", str(tmp_path), *args],
        capture_output=True,
        text=True,
        timeout=20,
        cwd=tmp_path,
        env=env,
        stdin=subprocess.DEVNULL,
    )


def token_file(tmp_path: Path, content: bytes, name: str = "token") -> str:
    path = tmp_path / name
    path.write_bytes(content)
    return str(path)


def _failure_cases(tmp_path: Path) -> list[tuple[str, list[str], dict[str, str]]]:
    http = ["--transport", "streamable-http"]
    good_env = {"WLED_MCP_HTTP_TOKEN": TOKEN}
    good_file = token_file(tmp_path, TOKEN.encode(), "good-token")
    (tmp_path / "adir").mkdir()
    return [
        ("no-credential", http, {}),
        ("both-sources", [*http, "--http-token-file", good_file], good_env),
        ("empty-env", http, {"WLED_MCP_HTTP_TOKEN": ""}),
        ("short-env", http, {"WLED_MCP_HTTP_TOKEN": "x" * 31}),
        ("long-env", http, {"WLED_MCP_HTTP_TOKEN": "x" * 513}),
        ("whitespace-env", http, {"WLED_MCP_HTTP_TOKEN": TOKEN + " " + TOKEN}),
        ("control-char-env", http, {"WLED_MCP_HTTP_TOKEN": TOKEN + "\x01"}),
        ("non-ascii-env", http, {"WLED_MCP_HTTP_TOKEN": TOKEN + "é"}),
        ("file-missing", [*http, "--http-token-file", str(tmp_path / "absent")], {}),
        ("file-relative", [*http, "--http-token-file", "token"], {}),
        ("file-directory", [*http, "--http-token-file", str(tmp_path / "adir")], {}),
        ("file-empty", [*http, "--http-token-file", token_file(tmp_path, b"", "e")], {}),
        ("file-oversize", [*http, "--http-token-file", token_file(tmp_path, b"x" * 2000, "o")], {}),
        (
            "file-inner-space",
            [*http, "--http-token-file", token_file(tmp_path, TOKEN.encode() + b" y", "s")],
            {},
        ),
        (
            "file-two-lines",
            [
                *http,
                "--http-token-file",
                token_file(tmp_path, TOKEN.encode() + b"\n" + TOKEN.encode(), "l"),
            ],
            {},
        ),
        ("token-cli-value", [*http, "--http-token", MARKER], good_env),
        ("abbreviated-option", [*http, "--http-token-f", good_file], {}),
        ("port-without-allowed-host", [*http, "--port", "9100"], good_env),
        ("non-loopback-without-allowed-host", [*http, "--host", "0.0.0.0"], good_env),
        ("port-zero", [*http, "--port", "0", "--allowed-host", "127.0.0.1:1"], good_env),
        ("port-too-big", [*http, "--port", "70000", "--allowed-host", "127.0.0.1:1"], good_env),
        ("port-not-number", [*http, "--port", MARKER], good_env),
        ("bad-host", [*http, "--host", "not a host", "--allowed-host", "x:1"], good_env),
        *[
            (f"allowed-host-{index}", [*http, "--allowed-host", value], good_env)
            for index, value in enumerate(
                ["*", "a/b", "host:*", "http://host", "", "u@h:1", "h:99999", "h:0", " h", "::1"]
            )
        ],
        *[
            (f"allowed-origin-{index}", [*http, "--allowed-origin", value], good_env)
            for index, value in enumerate(
                [
                    "null",
                    "http://x/path",
                    "http://x/",
                    "*",
                    "x.example",
                    "ftp://x",
                    "http://*.x",
                    "http://x:*",
                ]
            )
        ],
        (
            "too-many-hosts",
            [*http, *[a for i in range(17) for a in ("--allowed-host", f"h{i}:1")]],
            good_env,
        ),
        ("workers-option", [*http, "--workers", "2"], good_env),
        ("http-flag-with-stdio-port", ["--port", "9"], {}),
        ("http-flag-with-stdio-host", ["--transport", "stdio", "--host", "127.0.0.1"], {}),
        ("http-flag-with-stdio-allowed-host", ["--allowed-host", "h:1"], {}),
        ("http-flag-with-stdio-allowed-origin", ["--allowed-origin", "http://h"], {}),
        ("http-flag-with-stdio-token-file", ["--http-token-file", good_file], {}),
    ]


def _complete(label: str, args: list[str], port: int) -> list[str]:
    full = [*args]
    if "streamable-http" in args and not any(
        f in args for f in ("--port", "--host", "--allowed-host")
    ):
        full += ["--port", str(port), "--allowed-host", f"127.0.0.1:{port}"]
    return full


def test_http_startup_fails_closed_in_process(tmp_path, monkeypatch, capsys):
    from wled_mcp import cli

    def must_not_start(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("nothing may be served after a startup failure")

    monkeypatch.setattr(cli.anyio, "run", must_not_start)
    config = write_config(tmp_path)
    cases = _failure_cases(tmp_path)  # creates its own credential files up front
    before = {p.name for p in tmp_path.iterdir()}
    port = free_port()
    for label, args, env in cases:
        for key in [k for k in os.environ if k.startswith("WLED_MCP_")]:
            monkeypatch.delenv(key)
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        argv = ["--config", str(config), "--data-dir", str(tmp_path), *_complete(label, args, port)]
        try:
            code = cli.main(argv)
        except SystemExit as exit_:  # argparse usage errors
            code = exit_.code
        captured = capsys.readouterr()
        assert code == 2, (label, captured.err)
        assert captured.out == "", label
        assert captured.err.strip(), label
        for secret in (TOKEN, MARKER, str(tmp_path), "Traceback"):
            assert secret not in captured.err, (label, secret)
    assert {p.name for p in tmp_path.iterdir()} == before, "startup failures write nothing"


@pytest.mark.parametrize(
    "label",
    ["no-credential", "token-cli-value", "port-without-allowed-host", "http-flag-with-stdio-port"],
)
def test_real_console_refuses_to_start_and_never_listens(tmp_path, label):
    port = free_port()
    case = {name: (args, env) for name, args, env in _failure_cases(tmp_path)}[label]
    write_config(tmp_path)
    before = {p.name for p in tmp_path.iterdir()}
    result = run_failing(tmp_path, _complete(label, case[0], port), clean_env(**case[1]))
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr.strip()
    for secret in (TOKEN, MARKER, str(tmp_path), "Traceback"):
        assert secret not in result.stderr
    assert not listening(port)
    assert {p.name for p in tmp_path.iterdir()} == before


@POSIX_ONLY
@pytest.mark.parametrize("source", ["env", "file", "file-crlf"])
def test_console_serves_http_and_shuts_down_cleanly(tmp_path, source):
    port = free_port()
    config = write_config(tmp_path)
    args = [
        "--transport",
        "streamable-http",
        "--port",
        str(port),
        "--allowed-host",
        f"127.0.0.1:{port}",
    ]
    env = clean_env()
    if source == "env":
        env["WLED_MCP_HTTP_TOKEN"] = TOKEN
    else:
        path = token_file(tmp_path, TOKEN.encode() + (b"\r\n" if source == "file-crlf" else b"\n"))
        args += ["--http-token-file", path]
    with console(config, tmp_path, *args, env=env) as (process, lines):
        wait_ready(lines, port)

        async def exercise() -> None:
            with anyio.fail_after(30):
                for mode in ("legacy", "auto"):
                    async with httpx.AsyncClient(
                        headers={"Authorization": f"Bearer {TOKEN}"}
                    ) as http:
                        transport = streamable_http_client(
                            f"http://127.0.0.1:{port}/mcp",
                            http_client=http,
                            terminate_on_close=False,
                        )
                        async with Client(transport, mode=mode, read_timeout_seconds=10) as client:
                            tools = (await client.list_tools()).tools
                            assert len(tools) == 7
                            result = await client.call_tool("wled_list_devices", {})
                            assert result.structured_content["data"] == {"devices": []}

        anyio.run(exercise)
        process.send_signal(signal.SIGTERM)
        assert process.wait(timeout=20) == 0
        assert process.stdout.read() == ""
    assert not listening(port)


def test_stdio_ignores_ambient_http_token_and_binds_nothing(tmp_path):
    """Default stdio: no listener, no HTTP credential needed, HTTP service module unloaded."""
    config = write_config(tmp_path)
    report = tmp_path / "audit.json"
    script = textwrap.dedent(
        f"""
        import json, sys
        events = []
        def hook(event, args):
            if event in ("socket.bind", "socket.listen", "socket.connect"):
                events.append(event)
        sys.addaudithook(hook)
        from wled_mcp.cli import main
        code = main(["--config", {str(config)!r}, "--data-dir", {str(tmp_path)!r}])
        open({str(report)!r}, "w").write(json.dumps({{
            "code": code, "events": events,
            "service": "wled_mcp.http_service" in sys.modules,
        }}))
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=30,
        env=clean_env(WLED_MCP_HTTP_TOKEN=TOKEN),
    )
    assert result.stdout == "" and result.returncode == 0, result.stderr
    assert json.loads(report.read_text()) == {
        "code": 0,
        "events": [],
        "service": False,
    }


@pytest.mark.anyio
async def test_http_and_stdio_expose_identical_tool_descriptors(tmp_path):
    port = free_port()
    config = write_config(tmp_path)
    args = [
        "--transport",
        "streamable-http",
        "--port",
        str(port),
        "--allowed-host",
        f"127.0.0.1:{port}",
    ]
    with console(config, tmp_path, *args, env=clean_env(WLED_MCP_HTTP_TOKEN=TOKEN)) as (_, lines):
        await anyio.to_thread.run_sync(wait_ready, lines, port)
        with anyio.fail_after(60):
            params = StdioServerParameters(
                command=str(CONSOLE),
                cwd=tmp_path,
                args=["--config", str(config), "--data-dir", str(tmp_path)],
            )
            async with Client(params, mode="legacy", read_timeout_seconds=10) as over_stdio:
                stdio_tools = (await over_stdio.list_tools()).tools
            async with httpx.AsyncClient(headers={"Authorization": f"Bearer {TOKEN}"}) as http:
                transport = streamable_http_client(
                    f"http://127.0.0.1:{port}/mcp", http_client=http, terminate_on_close=False
                )
                async with Client(transport, mode="legacy", read_timeout_seconds=10) as over_http:
                    http_tools = (await over_http.list_tools()).tools
    assert len(stdio_tools) == 7

    def dump(tools: list[Any]) -> str:
        return json.dumps([t.model_dump(mode="json") for t in tools], sort_keys=True)

    assert dump(http_tools) == dump(stdio_tools)


# ===================================================================== signals with a fake device


class FakeWLED:
    """Synthetic loopback WLED controller: counts POSTs, can hold the first one."""

    def __init__(self) -> None:
        self.state = make_state(on=False, bri=10)
        self.posts: list[Any] = []
        self.first_post = threading.Event()
        self.release = threading.Event()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: Any) -> None:
                pass

            def _send(self, payload: Any) -> None:
                body = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:  # noqa: N802
                routes = {
                    "/json/info": make_info(),
                    "/json/state": outer.state,
                    "/json/eff": EFFECTS,
                    "/json/pal": PALETTES,
                    "/json/fxdata": FXDATA,
                }
                self._send(routes[self.path])

            def do_POST(self) -> None:  # noqa: N802
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.posts.append(body)
                if len(outer.posts) == 1:
                    outer.first_post.set()
                    outer.release.wait(timeout=30)
                outer.state.update(body)
                self._send({"success": True})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.release.set()
        self.server.shutdown()
        self.server.server_close()


@POSIX_ONLY
@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT], ids=["SIGTERM", "SIGINT"])
def test_signal_drains_in_flight_write_and_exits_zero(tmp_path, sig):
    fake = FakeWLED()
    try:
        port = free_port()
        config = write_config(
            tmp_path,
            f'{{id = "desk", name = "Example desk", base_url = "http://127.0.0.1:{fake.port}"}}',
        )
        args = [
            "--transport",
            "streamable-http",
            "--port",
            str(port),
            "--allowed-host",
            f"127.0.0.1:{port}",
        ]
        with console(config, tmp_path, *args, env=clean_env(WLED_MCP_HTTP_TOKEN=TOKEN)) as (
            process,
            lines,
        ):
            wait_ready(lines, port)
            outcome: dict[str, Any] = {}

            async def call() -> None:
                with anyio.fail_after(60):
                    async with httpx.AsyncClient(
                        headers={"Authorization": f"Bearer {TOKEN}"}
                    ) as http:
                        transport = streamable_http_client(
                            f"http://127.0.0.1:{port}/mcp",
                            http_client=http,
                            terminate_on_close=False,
                        )
                        async with Client(
                            transport, mode="legacy", read_timeout_seconds=40
                        ) as client:
                            await client.list_tools()
                            async with anyio.create_task_group() as group:

                                async def write() -> None:
                                    outcome["result"] = await client.call_tool(
                                        "wled_set_state",
                                        {"device_id": "desk", "on": True, "brightness": 200},
                                    )

                                group.start_soon(write)
                                await anyio.to_thread.run_sync(fake.first_post.wait, 20)
                                process.send_signal(sig)
                                while listening(port):  # admission stops before the drain ends
                                    await anyio.sleep(0.05)
                                assert process.poll() is None, "still draining the held write"
                                fake.release.set()

            anyio.run(call)
            envelope = outcome["result"].structured_content
            assert (envelope["application"], envelope["verification"]) == ("applied", "verified")
            assert process.wait(timeout=30) == 0
            assert process.stdout.read() == ""
        assert fake.posts == [{"on": True, "bri": 200}], "exactly one device POST"
    finally:
        fake.close()
