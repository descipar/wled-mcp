"""Loopback-only harness for in-process Streamable HTTP tests.

The service binds a pre-opened ``127.0.0.1:0`` socket (no find-a-free-port race), the
device fleet is a ``WriteRouter`` mock transport, and nothing leaves the host.
"""

import dataclasses
import socket
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anyio
import httpx2 as httpx
from mcp.client import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.server.lowlevel import Server

from tests.patch_support import WriteRouter
from tests.state_catalog_support import FakeClock
from wled_mcp.config import Device, HTTPSettings, StartupConfig
from wled_mcp.http_config import TOKEN_ENV, HTTPServiceSettings, load_http_settings
from wled_mcp.http_service import HTTPService, build_http_app
from wled_mcp.operations import build_operations
from wled_mcp.resources import Resources
from wled_mcp.server import Operation, create_server

DESK, SHELF = "desk.invalid", "shelf.invalid"
TOKEN = "synthetic-http-token-0123456789abcdef"
WRONG_TOKEN = "synthetic-wrong-token-marker-0123456789"


def make_fleet() -> WriteRouter:
    router = WriteRouter()
    router.device(DESK)
    router.device(SHELF)
    return router


@dataclass
class Running:
    port: int
    url: str
    settings: HTTPServiceSettings
    service: HTTPService
    resources: Resources
    server: Server[None]
    router: WriteRouter
    executions: list[str] = field(default_factory=list)
    closes: list[int] = field(default_factory=list)
    ready_calls: int = 0

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {TOKEN}"}

    def raw(self, **kwargs: Any) -> httpx.AsyncClient:
        """Plain HTTP client against the service; no automatic credential."""
        return httpx.AsyncClient(base_url=f"http://127.0.0.1:{self.port}", **kwargs)


def initialize_body(version: str = "2025-11-25") -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": version,
            "capabilities": {},
            "clientInfo": {"name": "synthetic", "version": "1"},
        },
    }


MCP_HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


@asynccontextmanager
async def running_service(
    tmp_path: Path,
    router: WriteRouter | None = None,
    *,
    allowed_origins: tuple[str, ...] = (),
    extra_host_names: tuple[str, ...] = (),
    operation_timeout: float = 10,
    graceful_shutdown_seconds: int | None = None,
    wrap: Callable[[list[Operation]], list[Operation]] | None = None,
) -> AsyncIterator[Running]:
    fleet = router if router is not None else make_fleet()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    assert sock.getsockname()[0] == "127.0.0.1", "HTTP tests bind loopback only"
    port = sock.getsockname()[1]
    config = StartupConfig(
        tmp_path / "synthetic.toml",
        tmp_path,
        (
            Device(id="desk", name="Example desk", base_url=f"http://{DESK}"),
            Device(id="shelf", name="Example shelf", base_url=f"http://{SHELF}"),
        ),
        HTTPSettings(operation_timeout_seconds=operation_timeout),
    )
    settings = load_http_settings(
        host="127.0.0.1",
        port=port,
        allowed_hosts=[f"127.0.0.1:{port}", *(f"{name}:{port}" for name in extra_host_names)],
        allowed_origins=list(allowed_origins),
        token_file=None,
        operation_timeout_seconds=operation_timeout,
        environ={TOKEN_ENV: TOKEN},
    )
    if graceful_shutdown_seconds is not None:
        settings = dataclasses.replace(
            settings, graceful_shutdown_seconds=graceful_shutdown_seconds
        )
    started = anyio.Event()
    executions: list[str] = []
    closes: list[int] = []
    async with Resources(config, fleet.transport(), FakeClock().clock()) as resources:
        original_close = resources.client.aclose

        async def counting_close() -> None:
            closes.append(1)
            await original_close()

        resources.client.aclose = counting_close  # type: ignore[method-assign]

        def spy(operation: Operation) -> Operation:
            async def execute(arguments: dict[str, Any]) -> Any:
                executions.append(operation.name)
                return await operation.execute(arguments)

            return dataclasses.replace(operation, execute=execute)

        operations = [spy(op) for op in build_operations(resources)]
        if wrap is not None:
            operations = wrap(operations)
        server = create_server(operations)
        service = HTTPService(
            build_http_app(server, settings),
            settings,
            install_signal_handlers=False,
            on_started=started.set,
        )
        running = Running(
            port, f"http://127.0.0.1:{port}/mcp", settings, service, resources, server, fleet
        )
        running.executions = executions
        running.closes = closes
        async with anyio.create_task_group() as group:
            group.start_soon(service.serve, [sock])
            with anyio.fail_after(10):
                await started.wait()
            try:
                yield running
            finally:
                service.request_shutdown()


@asynccontextmanager
async def sdk_client(
    running: Running, mode: str = "legacy", token: str = TOKEN
) -> AsyncIterator[Client]:
    http = httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=15)
    async with http:
        transport = streamable_http_client(running.url, http_client=http, terminate_on_close=False)
        async with Client(transport, mode=mode, read_timeout_seconds=10) as client:
            yield client


def modern_call(
    name: str, arguments: dict[str, Any], request_id: int = 7
) -> tuple[dict[str, Any], dict[str, str]]:
    """Body and headers for the 2026-07-28 per-request protocol path."""
    body = tool_call(name, arguments, request_id)
    body["params"]["_meta"] = {
        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientCapabilities": {},
    }
    headers = {
        "MCP-Protocol-Version": "2026-07-28",
        "Mcp-Method": "tools/call",
        "Mcp-Name": name,
    }
    return body, headers


class DevicePosts:
    """POST handler that merges the body into the mocked state; optionally holds the first.

    The hold is event-synchronised: `dispatched` is set when the first POST has reached
    the device, and it completes only after `release` is set.
    """

    def __init__(self, router: WriteRouter, host: str, *, hold_first: bool = False) -> None:
        self.router = router
        self.host = host
        self.hold_first = hold_first
        self.bodies: list[Any] = []
        self.dispatched = anyio.Event()
        self.release = anyio.Event()
        router.set_post(host, "/json/state", self)

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        import copy
        import json

        index = len(self.bodies)
        self.bodies.append(json.loads(request.content))
        if self.hold_first and index == 0:
            self.dispatched.set()
            await self.release.wait()
        state = copy.deepcopy(self.router.get_routes[(self.host, "/json/state")])
        if callable(state):
            raise AssertionError("state route must be static for DevicePosts")
        state.update(self.bodies[-1])
        self.router.set(self.host, "/json/state", state)
        return httpx.Response(200, json={"success": True})


def tool_call(name: str, arguments: dict[str, Any], request_id: int = 7) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
