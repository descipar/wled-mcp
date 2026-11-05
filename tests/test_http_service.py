"""Streamable HTTP service: protocol, parity, sharing, access, disconnect, shutdown.

Mock fleet and ``127.0.0.1`` ephemeral sockets only; every test is time-bounded.
"""

import copy
import logging
from dataclasses import replace
from typing import Any

import anyio
import httpx2 as httpx
import pytest
from mcp import MCPError
from mcp.client import Client
from mcp.types import ToolAnnotations

from tests.http_support import (
    DESK,
    MCP_HEADERS,
    SHELF,
    TOKEN,
    WRONG_TOKEN,
    DevicePosts,
    Running,
    initialize_body,
    make_fleet,
    modern_call,
    running_service,
    sdk_client,
    tool_call,
)
from wled_mcp import resources as resources_module
from wled_mcp.models import Outcome
from wled_mcp.server import Operation

TOOLS = [
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
SYNTHETIC_SECRET = "synthetic-secret-never-return"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def state_gets(router: Any, host: str = DESK) -> int:
    return router.count("GET", host, "/json/state")


# ===================================================================== C14-01 / T18


@pytest.mark.anyio
@pytest.mark.parametrize("mode", ["legacy", "auto", "2026-07-28"])
async def test_sdk_client_initialize_list_call_over_http(tmp_path, mode):
    router = make_fleet()
    posts = DevicePosts(router, DESK)
    with anyio.fail_after(30):
        async with running_service(tmp_path, router) as run, sdk_client(run, mode) as client:
            if mode != "2026-07-28":  # the modern path has no initialize handshake
                assert client.server_info is not None and client.server_info.name == "wled-mcp"
            assert client.protocol_version == ("2025-11-25" if mode == "legacy" else "2026-07-28")
            assert [t.name for t in (await client.list_tools()).tools] == TOOLS
            listed = await client.call_tool("wled_list_devices", {})
            assert [d["id"] for d in listed.structured_content["data"]["devices"]] == [
                "desk",
                "shelf",
            ]
            read = await client.call_tool("wled_get_state", {"device_id": "desk"})
            assert read.structured_content["ok"] is True
            assert router.count("POST") == 0, "reads never write"
            write = await client.call_tool(
                "wled_set_state", {"device_id": "desk", "on": True, "brightness": 200}
            )
            env = write.structured_content
            assert (env["ok"], env["application"], env["verification"]) == (
                True,
                "applied",
                "verified",
            )
            assert posts.bodies == [{"on": True, "bri": 200}]
            assert router.count("POST") == 1


@pytest.mark.anyio
async def test_stateless_json_transport_behavior(tmp_path):
    with anyio.fail_after(30):
        async with running_service(tmp_path) as run:
            async with run.raw(headers={**run.headers, **MCP_HEADERS}) as http:
                init = await http.post("/mcp", json=initialize_body())
                assert init.status_code == 200
                assert "mcp-session-id" not in init.headers
                assert init.headers["content-type"].startswith("application/json")
                assert init.json()["result"]["serverInfo"]["name"] == "wled-mcp"
                note = await http.post(
                    "/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"}
                )
                assert note.status_code == 202
                # No server-initiated stream even when an SSE stream is offered.
                for method in ("GET", "DELETE"):
                    response = await http.request(method, "/mcp")
                    assert response.status_code == 405
                    assert response.headers["allow"] == "POST"
                    assert "mcp-session-id" not in response.headers
                # A stale or foreign session ID is ignored; nothing was ever issued.
                listing = await http.post(
                    "/mcp",
                    json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                    headers={"Mcp-Session-Id": "stale-synthetic-id"},
                )
                assert listing.status_code == 200
                assert [t["name"] for t in listing.json()["result"]["tools"]] == TOOLS
                assert "mcp-session-id" not in listing.headers
                # Transport/protocol errors are SDK errors, never tool envelopes.
                assert (await http.post("/mcp", content=b"{nope")).status_code == 400
                bad_type = await http.post(
                    "/mcp", content=b"{}", headers={"Content-Type": "text/plain"}
                )
                assert bad_type.status_code == 400
                huge = await http.post("/mcp", content=b"x" * 300_000)
                assert huge.status_code == 413
                body, headers = modern_call("wled_list_devices", {})
                headers["Mcp-Name"] = "other"
                mismatch = await http.post("/mcp", json=body, headers=headers)
                assert mismatch.status_code == 400
                assert "structuredContent" not in mismatch.text
            assert run.executions == [], "transport errors execute no tool"
            assert run.router.calls == []


# ===================================================================== C14-02 / parity


def crash_operation(operations: list[Operation]) -> list[Operation]:
    base = operations[0]

    async def boom(arguments: dict[str, Any]) -> Outcome:
        raise RuntimeError(SYNTHETIC_SECRET)

    return [
        *operations,
        replace(
            base,
            name="wled_test_crash",
            description="Test-only crashing operation.",
            execute=boom,
            annotations=ToolAnnotations(read_only_hint=True),
        ),
    ]


def _state_read_failure(router: Any) -> None:
    router.set(DESK, "/json/state", httpx.Response(503, text=SYNTHETIC_SECRET))


def _mismatch(router: Any) -> None:
    router.device(DESK)  # POST acknowledged, readback unchanged


def _uncertain(router: Any) -> None:
    router.device(DESK)

    def post_timeout(request: httpx.Request) -> httpx.Response:
        router.set(DESK, "/json/state", httpx.ReadError(SYNTHETIC_SECRET))
        raise httpx.WriteTimeout(SYNTHETIC_SECRET)

    router.set_post(DESK, "/json/state", post_timeout)


def _healthy(router: Any) -> None:
    router.device(DESK)
    router.device(SHELF)


PARITY_CASES: list[tuple[str, Any, str, dict[str, Any]]] = [
    ("list", _healthy, "wled_list_devices", {}),
    ("read", _healthy, "wled_get_state", {"device_id": "desk"}),
    ("dry-run", _healthy, "wled_set_state", {"device_id": "desk", "on": True, "dry_run": True}),
    ("schema", _healthy, "wled_set_state", {"device_id": "desk", "on": True, "bogus": 1}),
    ("range", _healthy, "wled_set_state", {"device_id": "desk", "brightness": 999}),
    ("domain", _healthy, "wled_set_state", {"device_id": "desk", "transition_ms": 100}),
    ("unknown-device", _healthy, "wled_get_state", {"device_id": "absent"}),
    ("read-failure", _state_read_failure, "wled_get_state", {"device_id": "desk"}),
    ("mismatch", _mismatch, "wled_set_state", {"device_id": "desk", "on": True, "brightness": 77}),
    ("uncertain", _uncertain, "wled_set_state", {"device_id": "desk", "on": True, "brightness": 9}),
    ("crash", _healthy, "wled_test_crash", {}),
]


async def _invoke(client: Client, name: str, arguments: dict[str, Any]) -> Any:
    try:
        result = await client.call_tool(name, arguments)
    except MCPError as error:
        return ("mcp-error", error.error.code, error.error.message)
    return ("result", result.structured_content, result.content[0].text, result.is_error)


@pytest.mark.anyio
@pytest.mark.parametrize("mode", ["legacy", "2026-07-28"])
async def test_http_results_match_in_process_server(tmp_path, mode):
    """Same server object over HTTP and in-process: identical results and device traffic."""
    with anyio.fail_after(60):
        async with running_service(tmp_path, wrap=crash_operation) as run:
            async with sdk_client(run, mode) as over_http, Client(run.server) as in_process:
                http_tools = (await over_http.list_tools()).tools
                local_tools = (await in_process.list_tools()).tools
                assert [t.model_dump() for t in http_tools] == [t.model_dump() for t in local_tools]
                for label, setup, name, arguments in [
                    *PARITY_CASES,
                    ("unknown-tool", _healthy, "absent_tool", {}),
                ]:
                    observed = []
                    for client in (over_http, in_process):
                        setup(run.router)
                        before = len(run.router.calls)
                        outcome = await _invoke(client, name, copy.deepcopy(arguments))
                        observed.append((outcome, run.router.calls[before:]))
                    assert observed[0] == observed[1], label
                    outcome = observed[0][0]
                    assert SYNTHETIC_SECRET not in repr(outcome), label
                    if label == "crash":
                        assert outcome == ("mcp-error", -32603, "Internal operation failure")
                    if label == "unknown-tool":
                        assert outcome[0] == "mcp-error"
                    if label == "uncertain":
                        assert outcome[1]["error"]["code"] == "WRITE_OUTCOME_UNKNOWN"
                        assert [m for m, *_ in observed[0][1]].count("POST") == 1
                    if label == "mismatch":
                        assert outcome[1]["error"]["code"] == "VERIFICATION_MISMATCH"
                    if label == "unknown-device":
                        assert observed[0][1] == []
                    if label in {"schema", "range", "domain"}:
                        assert outcome[1]["error"]["code"] == "VALIDATION_ERROR"


# ===================================================================== C14-03 / T19


@pytest.mark.anyio
async def test_two_http_clients_share_device_lock_while_other_device_progresses(tmp_path):
    router = make_fleet()
    desk = DevicePosts(router, DESK, hold_first=True)
    DevicePosts(router, SHELF)
    created: list[int] = []
    original_init = resources_module.Resources.__init__

    def counting_init(self: Any, *args: Any, **kwargs: Any) -> None:
        created.append(1)
        original_init(self, *args, **kwargs)

    results: dict[str, Any] = {}
    with anyio.fail_after(60), pytest.MonkeyPatch.context() as patch:
        patch.setattr(resources_module.Resources, "__init__", counting_init)
        async with running_service(tmp_path, router) as run:
            lock = run.resources.locks["desk"]

            async def call(label: str, device: str, brightness: int) -> None:
                async with sdk_client(run) as client:
                    results[label] = await client.call_tool(
                        "wled_set_state",
                        {"device_id": device, "on": True, "brightness": brightness},
                    )

            async with anyio.create_task_group() as group:
                group.start_soon(call, "first", "desk", 200)
                await desk.dispatched.wait()
                group.start_soon(call, "second", "desk", 100)
                while lock.statistics().tasks_waiting < 1:
                    await anyio.sleep(0.01)
                # Another device is independent of the held desk lock.
                async with sdk_client(run) as other:
                    shelf = await other.call_tool(
                        "wled_set_state", {"device_id": "shelf", "on": True, "brightness": 50}
                    )
                    assert shelf.structured_content["verification"] == "verified"
                    read_other = await other.call_tool("wled_get_state", {"device_id": "shelf"})
                    assert read_other.structured_content["ok"] is True
                # Reads on the held device queue behind the same lock (no stale snapshot).
                group.start_soon(_reader(run, results))
                while lock.statistics().tasks_waiting < 2:
                    await anyio.sleep(0.01)
                assert lock.locked()
                assert router.count("POST", DESK) == 1, "second writer waits for the lock"
                assert len(desk.bodies) == 1
                desk.release.set()
            assert results["first"].structured_content["verification"] == "verified"
            assert results["second"].structured_content["verification"] == "verified"
            assert desk.bodies == [{"on": True, "bri": 200}, {"on": True, "bri": 100}]
            # Strict per-device ordering: plan, POST, readback, then the next writer.
            desk_calls = [(m, p) for m, h, p in router.calls if h == DESK and p == "/json/state"]
            assert [m for m, _ in desk_calls] == ["GET", "POST", "GET", "GET", "POST", "GET", "GET"]
            assert results["queued_read"].structured_content["ok"] is True
            assert created == [1], "one resource graph per process"
        assert run.closes == [1], "shared client closed exactly once"


def _reader(run: Running, results: dict[str, Any]) -> Any:
    async def read() -> None:
        async with sdk_client(run) as client:
            results["queued_read"] = await client.call_tool("wled_get_state", {"device_id": "desk"})

    return read


@pytest.mark.anyio
async def test_clients_share_one_catalog_cache(tmp_path):
    router = make_fleet()
    with anyio.fail_after(30):
        async with running_service(tmp_path, router) as run:
            async with sdk_client(run) as first, sdk_client(run, "2026-07-28") as second:
                a = await first.call_tool("wled_get_effects", {"device_id": "desk"})
                b = await second.call_tool("wled_get_effects", {"device_id": "desk"})
                assert a.structured_content["ok"] and b.structured_content["ok"]
            assert router.count("GET", DESK, "/json/eff") == 1


# ===================================================================== C14-04/05 / T20


def _access_cases(port: int, valid: str) -> list[tuple[str, str, list[tuple[str, str]], int]]:
    host = ("Host", f"127.0.0.1:{port}")
    good = ("Authorization", valid)
    cases: list[tuple[str, str, list[tuple[str, str]], int]] = []

    def add(label: str, method: str, headers: list[tuple[str, str]], status: int) -> None:
        cases.append((label, method, headers, status))

    # Authorization failures (Host valid, no Origin).
    for label, value in [
        ("wrong-token", f"Bearer {WRONG_TOKEN}"),
        ("short-token", "Bearer abc"),
        ("scheme-only", "Bearer"),
        ("basic-scheme", f"Basic {TOKEN}"),
        ("no-scheme", TOKEN),
        ("two-spaces", f"Bearer  {TOKEN}"),
        ("prefix-of-token", f"Bearer {TOKEN[:-1]}"),
        ("token-plus-suffix", f"Bearer {TOKEN}x"),
    ]:
        add(label, "POST", [host, ("Authorization", value)], 401)
    add("missing-auth", "POST", [host], 401)
    add("duplicate-auth", "POST", [host, good, good], 401)
    add("lowercase-scheme", "POST", [host, ("Authorization", f"bearer {TOKEN}")], 200)
    # Host failures win over every credential state.
    for label, value in [
        ("wrong-port", f"127.0.0.1:{port + 1}"),
        ("wrong-name", f"evil-marker.example:{port}"),
        ("userinfo", f"user@127.0.0.1:{port}"),
        ("wildcard", f"*:{port}"),
        ("no-port", "127.0.0.1"),
        ("empty", ""),
    ]:
        add(f"host-{label}", "POST", [("Host", value), good], 403)
        add(f"host-{label}-no-auth", "POST", [("Host", value)], 403)
    add(
        "forwarded-host-does-not-satisfy",
        "POST",
        [("Host", "evil-marker.example"), good, ("X-Forwarded-Host", f"127.0.0.1:{port}")],
        403,
    )
    add(
        "forwarded-header-does-not-satisfy",
        "POST",
        [("Host", "evil-marker.example"), good, ("Forwarded", f"host=127.0.0.1:{port}")],
        403,
    )
    add("case-insensitive-host", "POST", [("Host", f"WLED-MCP.EXAMPLE:{port}"), good], 200)
    # Origin: checked before the credential, exact match, absent is allowed.
    add(
        "origin-denied-with-auth",
        "POST",
        [host, good, ("Origin", "http://evil-marker.example")],
        403,
    )
    add("origin-denied-no-auth", "POST", [host, ("Origin", "http://evil-marker.example")], 403)
    add("origin-null", "POST", [host, good, ("Origin", "null")], 403)
    add("origin-wrong-port", "POST", [host, good, ("Origin", "http://ui.example:81")], 403)
    add("origin-allowed", "POST", [host, good, ("Origin", "http://ui.example")], 200)
    add("origin-allowed-case", "POST", [host, good, ("Origin", "HTTP://UI.EXAMPLE")], 200)
    add("origin-allowed-no-auth", "POST", [host, ("Origin", "http://ui.example")], 401)
    add(
        "origin-duplicate",
        "POST",
        [host, good, ("Origin", "http://ui.example"), ("Origin", "http://ui.example")],
        403,
    )
    # Every method is checked; only POST ever reaches the SDK.
    for method in ("GET", "DELETE", "PUT", "PATCH", "OPTIONS", "HEAD"):
        add(f"{method}-no-auth", method, [host], 401)
        add(f"{method}-bad-host", method, [("Host", "evil-marker.example"), good], 403)
        add(
            f"{method}-bad-origin",
            method,
            [host, good, ("Origin", "http://evil-marker.example")],
            403,
        )
        add(f"{method}-authenticated", method, [host, good], 405)
    # Paths: learn nothing before the credential.
    add("unknown-path-no-auth", "POST", [host], 401)
    add("unknown-path-authenticated", "POST", [host, good], 404)
    return cases


@pytest.mark.anyio
async def test_access_matrix_rejects_before_any_tool_or_device_work(tmp_path, caplog):
    caplog.set_level(logging.DEBUG)
    with anyio.fail_after(60):
        async with running_service(
            tmp_path,
            allowed_origins=("http://ui.example",),
            extra_host_names=("wled-mcp.example",),
        ) as run:
            valid = f"Bearer {TOKEN}"
            seen_bodies: list[str] = []
            async with run.raw(timeout=10) as http:
                for label, method, headers, status in _access_cases(run.port, valid):
                    path = "/other" if label.startswith("unknown-path") else "/mcp"
                    body = tool_call("wled_list_devices", {})
                    before_exec, before_calls = len(run.executions), len(run.router.calls)
                    request = http.build_request(
                        method,
                        path,
                        headers=[*headers, *[(k, v) for k, v in MCP_HEADERS.items()]],
                        json=body if method in {"POST", "PUT", "PATCH"} else None,
                    )
                    response = await http.send(request)
                    assert response.status_code == status, (label, response.status_code)
                    seen_bodies.append(response.text + str(dict(response.headers)))
                    if status == 401:
                        assert response.headers["www-authenticate"] == "Bearer", label
                    if status == 405:
                        assert response.headers["allow"] == "POST", label
                    if status != 200:
                        assert len(run.executions) == before_exec, label
                        assert len(run.router.calls) == before_calls, label
                    if status == 200:
                        assert response.json()["result"], label
                # An unauthenticated oversized body is refused on headers, never read as 413.
                big = await http.post(
                    "/mcp",
                    content=b"x" * 300_000,
                    headers={"Content-Type": "application/json"},
                )
                assert big.status_code == 401
            assert run.router.calls == [], "list_devices performs no device request"
            for text in seen_bodies:
                assert TOKEN not in text and WRONG_TOKEN not in text
                assert "evil-marker" not in text
            logs = caplog.text
            assert TOKEN not in logs and WRONG_TOKEN not in logs
            assert "evil-marker" not in logs and "ui.example" not in logs


@pytest.mark.anyio
async def test_duplicate_and_missing_host_are_rejected_on_the_wire(tmp_path):
    with anyio.fail_after(30):
        async with running_service(tmp_path) as run:
            for request_head in (
                f"POST /mcp HTTP/1.1\r\nHost: 127.0.0.1:{run.port}\r\nHost: evil.example\r\n",
                "POST /mcp HTTP/1.0\r\n",
            ):
                raw = (
                    request_head
                    + f"Authorization: Bearer {TOKEN}\r\nContent-Type: application/json\r\n"
                    + "Content-Length: 2\r\nConnection: close\r\n\r\n{}"
                )
                async with await anyio.connect_tcp("127.0.0.1", run.port) as stream:
                    await stream.send(raw.encode())
                    reply = b""
                    with anyio.move_on_after(5):
                        try:
                            while chunk := await stream.receive():
                                reply += chunk
                        except anyio.EndOfStream:
                            pass
                status = int(reply.split(b" ", 2)[1])
                assert status in {400, 403}, reply[:80]
            assert run.executions == [] and run.router.calls == []


# ===================================================================== C14-06/07 / T21


async def _post_held_write(run: Running, modern: bool, started: anyio.Event) -> None:
    arguments = {"device_id": "desk", "on": True, "brightness": 200}
    if modern:
        body, extra = modern_call("wled_set_state", arguments)
    else:
        body, extra = tool_call("wled_set_state", arguments), {}
    async with run.raw(headers={**run.headers, **MCP_HEADERS, **extra}, timeout=30) as http:
        started.set()
        await http.post("/mcp", json=body)


@pytest.mark.anyio
@pytest.mark.parametrize("modern", [False, True], ids=["legacy-path", "modern-path"])
async def test_disconnect_after_dispatch_does_not_cancel_or_replay(tmp_path, modern):
    router = make_fleet()
    desk = DevicePosts(router, DESK, hold_first=True)
    with anyio.fail_after(60):
        async with running_service(tmp_path, router) as run:
            started = anyio.Event()
            async with anyio.create_task_group() as group:
                group.start_soon(_post_held_write, run, modern, started)
                await desk.dispatched.wait()
                group.cancel_scope.cancel()  # client drops the connection mid-call
            gets_before_release = state_gets(router)
            desk.release.set()
            async with sdk_client(run) as client:
                # Queues behind the same lock: returns only after the abandoned call finished.
                follow_up = await client.call_tool("wled_get_state", {"device_id": "desk"})
            assert follow_up.structured_content["data"]["state"]["brightness"] == 200, (
                "write applied"
            )
            # plan read + readback happened for the abandoned call (plus the follow-up read)
            assert state_gets(router) - gets_before_release == 2
            assert router.count("POST") == 1
            assert not run.resources.locks["desk"].locked()
            await anyio.sleep(0.3)  # bounded negative check: nothing replays on its own
            assert router.count("POST") == 1


@pytest.mark.anyio
async def test_reconnect_is_a_new_invocation(tmp_path):
    router = make_fleet()
    desk = DevicePosts(router, DESK)
    with anyio.fail_after(60):
        async with running_service(tmp_path, router) as run:
            for expected in (1, 2):
                async with sdk_client(run) as client:
                    result = await client.call_tool(
                        "wled_set_state", {"device_id": "desk", "on": True, "brightness": 40}
                    )
                    assert result.structured_content["application"] == "applied"
                assert router.count("POST") == expected, "one POST per explicit invocation"
            assert len(desk.bodies) == 2


@pytest.mark.anyio
async def test_graceful_shutdown_drains_in_flight_write(tmp_path):
    router = make_fleet()
    desk = DevicePosts(router, DESK, hold_first=True)
    outcome: dict[str, Any] = {}
    with anyio.fail_after(60):
        async with running_service(tmp_path, router) as run:

            async def write() -> None:
                async with sdk_client(run) as client:
                    await client.list_tools()  # the client caches schemas; no request after drain
                    outcome["result"] = await client.call_tool(
                        "wled_set_state", {"device_id": "desk", "on": True, "brightness": 200}
                    )

            async with anyio.create_task_group() as group:
                group.start_soon(write)
                await desk.dispatched.wait()
                run.service.request_shutdown()
                # Admission stops: the listener closes while the write is still held.
                while True:
                    try:
                        probe = await anyio.connect_tcp("127.0.0.1", run.port)
                    except OSError:
                        break
                    await probe.aclose()
                    await anyio.sleep(0.05)
                assert run.closes == [], "resources stay open until the drain completes"
                desk.release.set()
            envelope = outcome["result"].structured_content
            assert (envelope["application"], envelope["verification"]) == ("applied", "verified")
        assert router.count("POST") == 1
        assert run.closes == [1]


@pytest.mark.anyio
async def test_forced_shutdown_leaves_write_uncertain_without_replay(tmp_path):
    router = make_fleet()
    desk = DevicePosts(router, DESK, hold_first=True)
    failure: dict[str, Any] = {}
    with anyio.fail_after(60):
        async with running_service(tmp_path, router, graceful_shutdown_seconds=1) as run:

            async def write() -> None:
                body, extra = modern_call(
                    "wled_set_state", {"device_id": "desk", "on": True, "brightness": 200}
                )
                async with run.raw(headers={**run.headers, **MCP_HEADERS, **extra}) as http:
                    try:
                        failure["response"] = await http.post("/mcp", json=body, timeout=30)
                    except httpx.HTTPError as error:
                        failure["error"] = error

            async with anyio.create_task_group() as group:
                group.start_soon(write)
                await desk.dispatched.wait()
                run.service.request_shutdown()  # the held write outlives the drain window
            # The held handler was cancelled: no success envelope was delivered.
            response = failure.get("response")
            assert response is None or response.status_code >= 500
            if response is not None:
                assert "structuredContent" not in response.text
        assert router.count("POST") == 1, "never replayed during or after shutdown"
        assert run.closes == [1]
        # A restarted service never resumes the write and contacts no device at startup.
        fresh = make_fleet()
        async with running_service(tmp_path, fresh) as again:
            await anyio.sleep(0.2)
            assert fresh.calls == [] and again.executions == []
        assert router.count("POST") == 1
