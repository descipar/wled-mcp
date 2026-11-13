"""Authenticated stateless Streamable HTTP adapter around the shared tool server.

The access guard is the outermost ASGI layer: Host, Origin, bearer credential, path
and method checks look at headers only, so no body is read and no tool or device
operation runs for a rejected request. The SDK app is used with stateless JSON
responses: no session IDs, event store or server-initiated streams.
"""

import contextlib
import hmac
import json
import logging
import re
import signal
import sys
import threading
from collections.abc import Callable, Iterator
from types import FrameType
from typing import Any

import uvicorn
from mcp.server.lowlevel import Server
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from wled_mcp.http_config import ENDPOINT_PATH, HTTPServiceSettings, token_digest

logger = logging.getLogger(__name__)

MAX_REQUEST_BODY_BYTES = 262144
MAX_CONCURRENCY = 128
_HANDLED_SIGNALS = tuple(
    sig
    for sig in (
        signal.SIGINT,
        signal.SIGTERM,
        getattr(signal, "SIGBREAK", None),
    )
    if sig is not None
)


def _headers(scope: Scope, name: bytes) -> list[str]:
    return [value.decode("latin-1") for key, value in scope["headers"] if key == name]


def _bearer_ok(values: list[str], expected_digest: bytes) -> bool:
    if len(values) != 1:
        return False
    scheme, space, credential = values[0].partition(" ")
    if scheme.lower() != "bearer" or not space or not credential:
        return False
    # Compare fixed-length digests so neither content nor length is leaked by timing.
    return hmac.compare_digest(token_digest(credential), expected_digest)


class AccessGuard:
    """Pure-ASGI access checks in the contract order, before the SDK sees a request."""

    def __init__(self, app: ASGIApp, settings: HTTPServiceSettings) -> None:
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self.app(scope, receive, send)
            return
        if scope["type"] != "http":
            return
        rejection = self._check(scope)
        if rejection is not None:
            status, reason, extra = rejection
            # Fixed class only: never the header values the peer supplied.
            logger.warning("HTTP request rejected: %s", reason)
            await self._respond(scope, send, status, reason, extra)
            return
        # SDK validation errors can include raw peer input. Only HTTP errors are
        # buffered, with a hard cap; successful MCP responses pass through unchanged.
        error_status: int | None = None
        error_body = bytearray()
        overflow = False

        async def safe_send(message: Message) -> None:
            nonlocal error_status, overflow
            if message["type"] == "http.response.start" and message["status"] >= 400:
                error_status = message["status"]
            elif error_status is not None and message["type"] == "http.response.body":
                chunk = message.get("body", b"")
                if len(error_body) + len(chunk) <= 8192 and not overflow:
                    error_body.extend(chunk)
                else:
                    overflow = True
                if not message.get("more_body", False):
                    response = JSONResponse(
                        self._safe_error(b"" if overflow else bytes(error_body)),
                        status_code=error_status,
                        headers={"Cache-Control": "no-store"},
                    )
                    await response(scope, receive, send)
            else:
                await send(message)

        await self.app(self._normalized(scope), receive, safe_send)

    @staticmethod
    def _safe_error(raw: bytes) -> dict[str, Any]:
        # Preserve protocol codes and request IDs for MCP clients. Messages supplied
        # by this server are fixed or contain only a generated correlation ID.
        safe: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32600, "message": "HTTP request rejected."},
        }
        try:
            document = json.loads(raw)
            error = document["error"]
            code, message = error["code"], error["message"]
            identifier = document.get("id")
            if type(identifier) in {str, int}:
                safe["id"] = identifier
            if type(code) is int:
                safe["error"]["code"] = code
            if isinstance(message, str) and (
                message in {"Unknown tool", "Unknown prompt or unexpected arguments"}
                or re.fullmatch(
                    r"Internal operation failure \(correlation_id=[0-9a-f]{16}\)", message
                )
            ):
                safe["error"]["message"] = message
        except (ValueError, TypeError, KeyError, RecursionError):
            return safe
        return safe

    def _check(self, scope: Scope) -> tuple[int, str, list[tuple[bytes, bytes]]] | None:
        hosts = _headers(scope, b"host")
        if len(hosts) != 1 or hosts[0].lower() not in self.settings.allowed_hosts:
            return 403, "forbidden", []
        origins = _headers(scope, b"origin")
        if len(origins) > 1 or (
            origins and origins[0].lower() not in self.settings.allowed_origins
        ):
            return 403, "forbidden", []
        if not _bearer_ok(_headers(scope, b"authorization"), self.settings.token_digest):
            return 401, "unauthorized", [(b"www-authenticate", b"Bearer")]
        if scope["path"] != ENDPOINT_PATH:
            return 404, "not_found", []
        if scope["method"] != "POST":
            return 405, "method_not_allowed", [(b"allow", b"POST")]
        return None

    @staticmethod
    def _normalized(scope: Scope) -> Scope:
        """Lower-case the already validated Host/Origin so SDK defense in depth agrees."""
        headers = [
            (key, value.lower() if key in (b"host", b"origin") else value)
            for key, value in scope["headers"]
        ]
        return {**scope, "headers": headers}

    @staticmethod
    async def _respond(
        scope: Scope, send: Send, status: int, reason: str, extra: list[tuple[bytes, bytes]]
    ) -> None:
        body = b"" if scope["method"] == "HEAD" else json.dumps({"error": reason}).encode()
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
            (b"cache-control", b"no-store"),
            *extra,
        ]
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})


def build_http_app(server: Server[Any], settings: HTTPServiceSettings) -> ASGIApp:
    """Wrap the SDK stateless-JSON app; the same `server` object serves stdio."""
    sdk_app = server.streamable_http_app(
        streamable_http_path=ENDPOINT_PATH,
        json_response=True,
        stateless_http=True,
        max_request_body_size=MAX_REQUEST_BODY_BYTES,
        # Defense in depth only; the guard owns the contract status codes (403, not 421).
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=sorted(settings.allowed_hosts),
            allowed_origins=sorted(settings.allowed_origins),
        ),
        host=settings.host,
    )
    return AccessGuard(sdk_app, settings)


class _Server(uvicorn.Server):
    """uvicorn server that owns SIGINT/SIGTERM and never re-raises them afterwards."""

    def __init__(
        self,
        config: uvicorn.Config,
        *,
        install_signal_handlers: bool,
        on_started: Callable[[], None] | None,
    ) -> None:
        super().__init__(config)
        self._install_signal_handlers = install_signal_handlers
        self._on_started = on_started

    @contextlib.contextmanager
    def capture_signals(self) -> Iterator[None]:
        if not self._install_signal_handlers or threading.current_thread() is not (
            threading.main_thread()
        ):
            yield
            return
        previous = {sig: signal.signal(sig, self.handle_exit) for sig in _HANDLED_SIGNALS}
        try:
            yield
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)

    def handle_exit(self, sig: int, frame: FrameType | None) -> None:
        # First signal drains gracefully; a second SIGINT forces exit (writes stay uncertain).
        if self.should_exit and sig == signal.SIGINT:
            self.force_exit = True
        self.should_exit = True

    async def startup(self, sockets: list[Any] | None = None) -> None:
        await super().startup(sockets=sockets)
        if self.started and self._on_started is not None:
            self._on_started()


class HTTPService:
    """Single-worker listener. `serve` returns after the drain; exit status stays 0."""

    def __init__(
        self,
        app: ASGIApp,
        settings: HTTPServiceSettings,
        *,
        install_signal_handlers: bool = True,
        on_started: Callable[[], None] | None = None,
    ) -> None:
        config = uvicorn.Config(
            app,
            host=settings.host,
            port=settings.port,
            http="h11",
            ws="none",
            lifespan="on",
            log_config=None,
            access_log=False,
            server_header=False,
            proxy_headers=False,  # X-Forwarded-* is never trusted
            limit_concurrency=MAX_CONCURRENCY,
            timeout_keep_alive=5,
            timeout_graceful_shutdown=settings.graceful_shutdown_seconds,
            workers=None,
        )
        self._server = _Server(
            config, install_signal_handlers=install_signal_handlers, on_started=on_started
        )

    @property
    def started(self) -> bool:
        return self._server.started

    def request_shutdown(self) -> None:
        self._server.should_exit = True

    async def serve(self, sockets: list[Any] | None = None) -> None:
        await self._server.serve(sockets=sockets)


def announce(settings: HTTPServiceSettings) -> Callable[[], None]:
    def write() -> None:
        print(
            f"listening on configured address path {ENDPOINT_PATH}",
            file=sys.stderr,
            flush=True,
        )

    return write
