"""Issue #12 TD-12-4: the opt-in HTTP probe stays read-only, quiet about its credential
and honest about latency, timeouts and the request-body bound.

Everything runs on loopback: a stdlib stub server and the in-process service with a mocked
device fleet. The probe is never pointed at a device or target here.
"""

from __future__ import annotations

import importlib.util
import io
import json
import socket
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import ModuleType
from typing import Any

import anyio
import pytest

from tests.http_support import TOKEN, running_service
from tests.tool_contract import ToolClass, names_of

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "hw_http_probe.py"
STUB_TOKEN = "synthetic-probe-token-0123456789abcdef"


def load_probe() -> ModuleType:
    spec = importlib.util.spec_from_file_location("hw_http_probe", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Dataclasses resolve their module through sys.modules during class creation.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


probe = load_probe()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


# ------------------------------------------------------------------------ stub server


@dataclass
class StubLog:
    requests: list[dict[str, Any]] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)


def make_handler(
    log: StubLog, *, limit: int, slow_seconds: float, accepted_status: int | None = None
) -> type:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: Any) -> None:  # keep test output quiet
            return

        def do_POST(self) -> None:  # noqa: N802 - stdlib hook name
            length = int(self.headers.get("Content-Length", "0"))
            auth = self.headers.get("Authorization", "")
            with log.lock:
                log.requests.append(
                    {"bytes": length, "host": self.headers.get("Host"), "auth": auth}
                )
            if length > limit:
                self._reply(413, {"error": "too large"})
                return
            if accepted_status is not None:
                self._reply(accepted_status, {"error": "synthetic failure"})
                return
            body = json.loads(self.rfile.read(length))
            if auth != f"Bearer {STUB_TOKEN}":
                self._reply(401, {"error": "unauthorized"})
                return
            method = body.get("method")
            if method == "ping":
                self._reply(200, {"jsonrpc": "2.0", "id": body["id"], "result": {}})
            elif method == "tools/list":
                tools = [{"name": "wled_get_state"}]
                self._reply(200, {"jsonrpc": "2.0", "id": body["id"], "result": {"tools": tools}})
            elif method == "tools/call":
                arguments = body["params"]["arguments"]
                if arguments.get("device_id") == "slow":
                    time.sleep(slow_seconds)
                if arguments.get("device_id") == "echo":
                    # A hostile/buggy server echoing the credential must not leak it.
                    error = {"code": -32000, "message": f"seen {auth}"}
                    self._reply(200, {"jsonrpc": "2.0", "id": body["id"], "error": error})
                    return
                result = {
                    "content": [],
                    "structuredContent": {"ok": True, "device_id": arguments.get("device_id")},
                    "isError": False,
                }
                self._reply(200, {"jsonrpc": "2.0", "id": body["id"], "result": result})
            else:
                self._reply(200, {"jsonrpc": "2.0", "id": body.get("id"), "error": {"code": -1}})

        def _reply(self, status: int, payload: dict[str, Any]) -> None:
            data = json.dumps(payload).encode()
            try:
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except OSError:
                pass  # the probe already gave up (timeout case)

    return Handler


@contextmanager
def stub_server(
    *, limit: int = 4096, slow_seconds: float = 1.0, accepted_status: int | None = None
) -> Iterator[tuple[str, StubLog]]:
    log = StubLog()
    handler = make_handler(
        log, limit=limit, slow_seconds=slow_seconds, accepted_status=accepted_status
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server.daemon_threads = True
    assert server.server_address[0] == "127.0.0.1"
    thread = threading.Thread(target=server.serve_forever, args=(0.05,), daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/mcp", log
    finally:
        server.shutdown()
        server.server_close()


def run_probe(
    argv: list[str], environ: dict[str, str] | None = None, stdin: str = ""
) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = probe.main(
        argv,
        environ=environ if environ is not None else {},
        stdin=io.StringIO(stdin),
        stdout=out,
        stderr=err,
    )
    return code, out.getvalue(), err.getvalue()


# ---------------------------------------------------------------------- allowlist


NON_READ_TOOLS = sorted(names_of(ToolClass.CONTROL, ToolClass.MANAGE))


@pytest.mark.parametrize("tool", [*NON_READ_TOOLS, "unknown_tool", "WLED_GET_STATE"])
def test_non_read_only_tools_are_refused_before_any_request(tool):
    with stub_server() as (url, log):
        code, out, err = run_probe(
            ["--url", url, "--token-env", "T", "call", "--tool", tool],
            environ={"T": STUB_TOKEN},
        )
    assert code == probe.USAGE_ERROR
    assert out == ""
    assert "refusing tool" in err
    assert log.requests == [], "a refused tool must not open any connection"


def test_every_allowlisted_tool_is_a_read_only_contract_tool():
    # The allowlist must not drift into the server's mutating tools.
    assert NON_READ_TOOLS, "the contract lists mutating tools"
    assert probe.READ_ONLY_TOOLS <= names_of(ToolClass.READ)
    assert probe.READ_ONLY_TOOLS.isdisjoint(NON_READ_TOOLS)
    assert all(name.startswith(("wled_get_", "wled_list_")) for name in probe.READ_ONLY_TOOLS)


@pytest.mark.parametrize(
    "argv, message",
    [
        (["call", "--tool", "wled_get_state", "--concurrency", "9"], "--concurrency"),
        (["call", "--tool", "wled_get_state", "--requests", "101"], "--requests"),
        (["ping", "--concurrency", "0"], "--concurrency"),
        (["call", "--tool", "wled_get_state", "--arguments", "[1]"], "JSON object"),
    ],
)
def test_out_of_bounds_load_and_bad_arguments_send_nothing(argv, message):
    with stub_server() as (url, log):
        code, _, err = run_probe(["--url", url, "--token-env", "T", *argv], {"T": STUB_TOKEN})
    assert code == probe.USAGE_ERROR
    assert message in err
    assert log.requests == []


@pytest.mark.parametrize(
    "url", ["ftp://127.0.0.1/mcp", "http://user:pw@127.0.0.1/mcp", "http://127.0.0.1/mcp?x=1"]
)
def test_unsupported_urls_are_refused(url):
    code, _, err = run_probe(["--url", url, "--token-env", "T", "ping"], {"T": STUB_TOKEN})
    assert code == probe.USAGE_ERROR
    assert "--url" in err


# --------------------------------------------------------------------- credential


def test_credential_from_file_is_sent_but_never_output(tmp_path):
    token_file = tmp_path / "token"
    token_file.write_text(STUB_TOKEN + "\n", encoding="ascii")
    with stub_server() as (url, log):
        code, out, err = run_probe(
            [
                "--url",
                url,
                "--token-file",
                str(token_file),
                "call",
                "--tool",
                "wled_get_state",
                "--arguments",
                '{"device_id": "echo"}',
                "--include-results",
                "--include-samples",
            ]
        )
    assert code == 0
    assert [r["auth"] for r in log.requests] == [f"Bearer {STUB_TOKEN}"]
    assert STUB_TOKEN not in out and STUB_TOKEN not in err
    report = json.loads(out)
    assert report["outcome_counts"] == {"jsonrpc_error": 1}
    assert probe.REDACTED in report["errors"][0]["detail"]
    assert probe.REDACTED in json.dumps(report["results"])


def test_credential_from_environment_and_stdin_and_output_file(tmp_path):
    with stub_server() as (url, log):
        code, out, _ = run_probe(["--url", url, "--token-env", "T", "ping"], {"T": STUB_TOKEN})
        assert code == 0 and json.loads(out)["outcome_counts"] == {"ok": 1}
        report_path = tmp_path / "report.json"
        code, out, err = run_probe(
            ["--url", url, "--token-stdin", "--output", str(report_path), "tools-list"],
            stdin=STUB_TOKEN + "\n",
        )
    assert code == 0 and out == ""
    assert STUB_TOKEN not in err
    text = report_path.read_text(encoding="utf-8")
    assert STUB_TOKEN not in text
    assert json.loads(text)["status_counts"] == {"200": 1}
    assert report_path.stat().st_mode & 0o077 == 0
    assert len(log.requests) == 2


@pytest.mark.parametrize("bad", ["", "with space", "tab\there", "nön-ascii"])
def test_invalid_credentials_are_refused_without_echo(bad):
    with stub_server() as (url, log):
        code, out, err = run_probe(["--url", url, "--token-env", "T", "ping"], {"T": bad})
    assert code == probe.USAGE_ERROR and out == ""
    if bad:
        assert bad not in err
    assert log.requests == []


def test_missing_environment_variable_names_no_value():
    code, _, err = run_probe(["--url", "http://127.0.0.1:1/mcp", "--token-env", "T", "ping"])
    assert code == probe.USAGE_ERROR
    assert "not set" in err


def test_wrong_credential_is_counted_as_401():
    with stub_server() as (url, _):
        code, out, _ = run_probe(
            ["--url", url, "--token-env", "T", "ping", "--requests", "3"],
            {"T": "synthetic-wrong-token-0123456789"},
        )
    report = json.loads(out)
    assert code == 0
    assert report["status_counts"] == {"401": 3}
    assert report["outcome_counts"] == {"http_401": 3}


# -------------------------------------------------------------------- percentiles


def test_nearest_rank_percentiles():
    values = [float(v) for v in range(100, 0, -1)]  # unsorted input
    assert probe.percentile(values, 50) == 50
    assert probe.percentile(values, 95) == 95
    assert probe.percentile(values, 99) == 99
    assert probe.percentile(values, 100) == 100
    assert probe.percentile(values, 0) == 1
    assert probe.percentile([3.0, 1.0, 2.0, 4.0], 50) == 2
    assert probe.percentile([3.0, 1.0, 2.0, 4.0], 51) == 3
    assert probe.percentile([7.5], 99) == 7.5
    assert probe.percentile([], 50) is None
    with pytest.raises(ValueError):
        probe.percentile([1.0], 101)


def test_latency_summary_of_known_samples():
    summary = probe.latency_summary([10.0, 20.0, 30.0, 40.0, 1000.0])
    assert summary == {
        "count": 5,
        "min": 10.0,
        "p50": 30.0,
        "p90": 1000.0,
        "p95": 1000.0,
        "p99": 1000.0,
        "max": 1000.0,
        "mean": 220.0,
    }
    assert probe.latency_summary([])["p95"] is None


def test_concurrent_burst_counts_every_request():
    with stub_server() as (url, log):
        code, out, _ = run_probe(
            [
                "--url",
                url,
                "--token-env",
                "T",
                "tools-list",
                "--concurrency",
                "4",
                "--requests",
                "40",
                "--include-samples",
            ],
            {"T": STUB_TOKEN},
        )
    report = json.loads(out)
    assert code == 0 and len(log.requests) == 40
    assert report["completed"] == 40 and report["status_counts"] == {"200": 40}
    assert report["latency_ms"]["count"] == 40
    assert report["latency_ms"]["min"] <= report["latency_ms"]["p50"] <= report["latency_ms"]["max"]
    samples = report["samples"]
    assert sorted(s["index"] for s in samples) == list(range(40))
    assert all(s["t_send"] <= s["t_response"] for s in samples)


# --------------------------------------------------------------------- body bound


def test_padded_ping_is_valid_json_of_the_exact_size():
    body = probe.padded_ping(1000)
    assert len(body) == 1000
    assert json.loads(body) == {"jsonrpc": "2.0", "id": 1, "method": "ping"}


@pytest.mark.parametrize(
    "server_limit, under_met, over_met",
    [
        (4096, True, True),  # the bound holds exactly at --limit
        (4100, True, False),  # server accepts one byte over: regression is reported
        (4000, False, True),  # server rejects below the bound: also reported
    ],
)
def test_body_bound_probe_classifies_413(server_limit, under_met, over_met):
    with stub_server(limit=server_limit) as (url, log):
        code, out, _ = run_probe(
            ["--url", url, "--token-env", "T", "body-bound", "--limit", "4096"],
            {"T": STUB_TOKEN},
        )
    probes = {p["label"]: p for p in json.loads(out)["body_bound"]["probes"]}
    assert code == 0
    assert [r["bytes"] for r in log.requests] == [4095, 4097]
    assert probes["under"]["met"] is under_met
    assert probes["over"]["met"] is over_met
    assert json.loads(out)["body_bound"]["met"] is (under_met and over_met)


@pytest.mark.parametrize("status", [500, 400])
def test_body_bound_under_probe_needs_a_successful_ping(status):
    # The server answers 413 above the bound but fails below it for another reason:
    # that is not evidence that a body just under the bound is accepted.
    with stub_server(accepted_status=status) as (url, _):
        code, out, _ = run_probe(
            ["--url", url, "--token-env", "T", "body-bound", "--limit", "4096"],
            {"T": STUB_TOKEN},
        )
    bound = json.loads(out)["body_bound"]
    probes = {p["label"]: p for p in bound["probes"]}
    assert code == 0
    assert probes["under"]["status"] == status
    assert probes["under"]["met"] is False
    assert probes["over"]["met"] is True
    assert bound["met"] is False


# ------------------------------------------------------------------------ timeout


def test_timeout_is_reported_not_retried():
    with stub_server(slow_seconds=1.5) as (url, log):
        started = time.perf_counter()
        code, out, _ = run_probe(
            [
                "--url",
                url,
                "--token-env",
                "T",
                "--timeout",
                "0.3",
                "call",
                "--tool",
                "wled_get_state",
                "--arguments",
                '{"device_id": "slow"}',
                "--requests",
                "2",
                "--concurrency",
                "2",
            ],
            {"T": STUB_TOKEN},
        )
        elapsed = time.perf_counter() - started
    report = json.loads(out)
    assert code == 0
    assert report["outcome_counts"] == {"timeout": 2}
    assert report["status_counts"] == {"timeout": 2}
    assert report["latency_ms"]["count"] == 0
    assert len(log.requests) == 2, "a timed-out request is not retried"
    assert elapsed < 1.4


def test_refused_connection_is_a_connection_error():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    code, out, _ = run_probe(
        ["--url", f"http://127.0.0.1:{port}/mcp", "--token-env", "T", "ping"], {"T": STUB_TOKEN}
    )
    assert code == 0
    assert json.loads(out)["outcome_counts"] == {"connection_error": 1}


# ------------------------------------------------- against the in-process service


@pytest.mark.anyio
async def test_probe_against_the_real_service_on_loopback(tmp_path):
    host_name = "wled-mcp.example"
    with anyio.fail_after(60):
        async with running_service(tmp_path, extra_host_names=(host_name,)) as run:
            base = [
                "--url",
                run.url,
                "--host-header",
                f"{host_name}:{run.port}",
                "--token-env",
                "T",
            ]
            env = {"T": TOKEN}

            async def call(*argv: str) -> dict[str, Any]:
                code, out, err = await anyio.to_thread.run_sync(
                    lambda: run_probe([*base, *argv], env)
                )
                assert code == 0, err
                assert TOKEN not in out and TOKEN not in err
                return dict(json.loads(out))

            ping = await call("ping", "--concurrency", "4", "--requests", "8")
            assert ping["status_counts"] == {"200": 8}
            assert ping["outcome_counts"] == {"ok": 8}
            listing = await call("tools-list", "--include-samples")
            assert listing["outcome_counts"] == {"ok": 1}
            devices = await call("call", "--tool", "wled_list_devices", "--include-results")
            assert devices["outcome_counts"] == {"ok": 1}
            listed = devices["results"][0]["structuredContent"]["data"]["devices"]
            assert {d["id"] for d in listed} == {"desk", "shelf"}
            bound = await call("body-bound")
            probes = {p["label"]: p for p in bound["body_bound"]["probes"]}
            assert probes["under"]["status"] == 200
            assert probes["over"]["status"] == 413
            assert bound["body_bound"]["met"] is True
            assert run.executions == ["wled_list_devices"]
            assert run.router.count("POST") == 0, "the probe never writes to a device"
            wrong_host = await anyio.to_thread.run_sync(
                lambda: run_probe(
                    [
                        "--url",
                        run.url,
                        "--host-header",
                        "other.example",
                        "--token-env",
                        "T",
                        "ping",
                    ],
                    env,
                )
            )
            assert json.loads(wrong_host[1])["status_counts"] == {"403": 1}
