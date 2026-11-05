"""Subprocess probe: run the default stdio start under a socket guard (issue #53).

Not collected by pytest (no ``test_`` prefix). Usage::

    python -m tests.stdio_socket_probe CONFIG DATA_DIR REPORT [MODE]

The guard records every ``socket.bind``, ``socket.connect`` (also ``connect_ex``),
``socket.sendto``, ``socket.sendmsg`` and ``socket.getaddrinfo`` audit event and every
``socket.socket.listen`` call (CPython emits no ``socket.listen`` audit event, so the
method is wrapped). Each operation is attributed to its direct caller, the first frame
outside the guard. Only the stdlib ``socket._fallback_socketpair`` (the asyncio self-pipe
on Windows) may bind a loopback address on port 0, call ``listen()`` and connect to a
loopback address. Everything else is a violation and is refused with ``PermissionError``
before it reaches the operating system, so negative controls never leave a listener
open or send a packet.

On Windows the Proactor event loop performs outbound connects (TCP ``ConnectEx``, UDP
``WSAConnect``) and datagram ``sendto`` (``WSASendTo``) through ``_overlapped``, which
emits no socket audit event. Where ``asyncio.windows_events.IocpProactor`` exists, its
``connect`` and ``sendto`` methods are therefore wrapped and routed through the same
check.

``MODE`` other than ``none`` replaces ``wled_mcp.cli.serve_stdio`` with a wrapper that
first attempts one injected forbidden operation inside the running event loop and then
starts the real stdio server. The report records whether the guard refused that
operation (its ``PermissionError`` reached the injected code) and, for plain-socket
modes, whether the socket ended up holding a local port. stdout stays empty; the report
is a JSON file.
"""

import ipaddress
import json
import socket
import sys
from collections.abc import Callable
from types import CodeType, FrameType
from typing import Any

AUDITED = frozenset(
    {"socket.bind", "socket.connect", "socket.sendto", "socket.sendmsg", "socket.getaddrinfo"}
)
_PAIR = getattr(socket, "_fallback_socketpair", None)
PAIR_CODE: CodeType | None = _PAIR.__code__ if _PAIR is not None else None
REFUSAL = "stdio socket guard refused"

allowed: list[dict[str, str]] = []
violations: list[dict[str, str]] = []
injection: dict[str, Any] = {}
_proactor_originals: dict[str, Callable[..., Any]] = {}


def _caller() -> FrameType | None:
    frame: FrameType | None = sys._getframe(1)
    while frame is not None and frame.f_code in GUARD_CODES:
        frame = frame.f_back
    return frame


def _is_loopback(host: object) -> bool:
    if not isinstance(host, str):
        return False
    try:
        return ipaddress.ip_address(host.split("%", 1)[0]).is_loopback
    except ValueError:
        return False


def _permitted(kind: str, address: object, caller: FrameType | None) -> bool:
    if PAIR_CODE is None or caller is None or caller.f_code is not PAIR_CODE:
        return False
    if kind == "listen":
        return True
    if not isinstance(address, tuple) or len(address) < 2:
        return False
    if kind == "bind":
        return _is_loopback(address[0]) and address[1] == 0
    return kind == "connect" and _is_loopback(address[0])


def _check(kind: str, address: object) -> None:
    caller = _caller()
    where = "?" if caller is None else f"{caller.f_code.co_filename}:{caller.f_code.co_name}"
    record = {"kind": kind, "address": repr(address), "caller": where}
    if _permitted(kind, address, caller):
        allowed.append(record)
        return
    violations.append(record)
    raise PermissionError(f"{REFUSAL} {kind} {address!r}")


def _hook(event: str, args: tuple[Any, ...]) -> None:
    if event not in AUDITED:
        return
    kind = event.removeprefix("socket.")
    if kind == "getaddrinfo":
        address: object = (args[0], args[1])
    elif kind == "sendmsg":
        address = args[1] if len(args) > 1 else None
    else:
        address = args[1] if len(args) > 1 else args
    _check(kind, address)


_original_listen = socket.socket.listen


def _listen(self: socket.socket, *args: int) -> None:
    _check("listen", _sockname(self))
    _original_listen(self, *args)


def _sockname(sock: socket.socket) -> object:
    try:
        return sock.getsockname()
    except OSError:
        return None


def _proactor_connect(self: object, conn: socket.socket, address: object) -> Any:
    _check("connect", address)
    return _proactor_originals["connect"](self, conn, address)


def _proactor_sendto(
    self: object, conn: socket.socket, buf: bytes, flags: int = 0, addr: object = None
) -> Any:
    _check("sendto", addr)
    return _proactor_originals["sendto"](self, conn, buf, flags, addr)


def _install_proactor_guard() -> bool:
    """Wrap the Windows Proactor connect/sendto, which bypass the socket audit events."""
    if sys.platform != "win32":
        return False
    from asyncio import windows_events

    proactor = windows_events.IocpProactor
    _proactor_originals.update(connect=proactor.connect, sendto=proactor.sendto)
    proactor.connect = _proactor_connect  # type: ignore[method-assign,assignment]
    proactor.sendto = _proactor_sendto  # type: ignore[method-assign,assignment]
    return True


GUARD_CODES = frozenset(
    {
        _caller.__code__,
        _check.__code__,
        _hook.__code__,
        _listen.__code__,
        _proactor_connect.__code__,
        _proactor_sendto.__code__,
    }
)


def _refused(exc: BaseException | None) -> bool:
    """True if the guard's own ``PermissionError`` is in the exception chain."""
    seen: set[int] = set()
    while exc is not None and id(exc) not in seen:
        if isinstance(exc, PermissionError) and REFUSAL in str(exc):
            return True
        seen.add(id(exc))
        exc = exc.__cause__ or exc.__context__
    return False


def _record_bound(sock: socket.socket) -> None:
    """Record whether the socket holds a local port; a refused bind/listen/send leaves none."""
    name = _sockname(sock)
    injection["bound"] = isinstance(name, tuple) and len(name) >= 2 and name[1] != 0


def _inject(mode: str) -> None:
    import asyncio

    import wled_mcp.cli as cli

    original = cli.serve_stdio

    class RecordingDatagram(asyncio.DatagramProtocol):
        def __init__(self) -> None:
            self.errors: list[Exception] = []

        def error_received(self, exc: Exception) -> None:
            self.errors.append(exc)

    async def attempt() -> None:
        loop = asyncio.get_running_loop()
        if mode == "listen_loopback":
            with socket.socket() as sock:
                try:
                    sock.bind(("127.0.0.1", 0))
                    sock.listen()
                finally:
                    _record_bound(sock)
        elif mode == "listen_unbound":
            with socket.socket() as sock:
                try:
                    sock.listen()
                finally:
                    _record_bound(sock)
        elif mode == "bind_any":
            with socket.socket() as sock:
                try:
                    sock.bind(("0.0.0.0", 0))
                finally:
                    _record_bound(sock)
        elif mode == "create_server":
            server = await loop.create_server(asyncio.Protocol, "127.0.0.1", 0)
            server.close()
            await server.wait_closed()
        elif mode == "connect_loopback":
            with socket.socket() as sock:
                sock.connect(("127.0.0.1", 9))
        elif mode == "udp_sendto":
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                try:
                    sock.sendto(b"x", ("127.0.0.1", 9))
                finally:
                    _record_bound(sock)
        elif mode == "asyncio_connect":
            _, writer = await asyncio.open_connection("127.0.0.1", 9)
            writer.close()
        elif mode == "asyncio_udp_connect":
            transport, _ = await loop.create_datagram_endpoint(
                asyncio.DatagramProtocol, remote_addr=("127.0.0.1", 9)
            )
            transport.close()
        elif mode == "asyncio_udp_sendto":
            transport, protocol = await loop.create_datagram_endpoint(
                RecordingDatagram, family=socket.AF_INET
            )
            try:
                transport.sendto(b"x", ("127.0.0.1", 9))
                await asyncio.sleep(0)
            finally:
                transport.close()
            # The datagram transport reports send errors to its protocol, not the caller.
            errors = sorted(protocol.errors, key=lambda exc: not _refused(exc))
            if errors:
                raise errors[0]
        else:
            raise ValueError(f"unknown probe mode {mode!r}")

    async def guarded(server: Any) -> None:
        try:
            await attempt()
        except OSError as exc:  # refused by the guard (or by the OS)
            injection.update(refused=_refused(exc), error=repr(exc))
        else:
            injection.update(refused=False, error=None)
        await original(server)

    cli.serve_stdio = guarded  # type: ignore[assignment]


def main(argv: list[str]) -> None:
    config, data_dir, report = argv[:3]
    mode = argv[3] if len(argv) > 3 else "none"
    sys.addaudithook(_hook)
    socket.socket.listen = _listen  # type: ignore[method-assign]
    result: dict[str, Any] = {"code": None, "error": None}
    result["proactor_guard"] = _install_proactor_guard()
    try:
        if mode != "none":
            _inject(mode)
        from wled_mcp.cli import main as cli_main

        result["code"] = cli_main(["--config", config, "--data-dir", data_dir])
    except BaseException as exc:  # report every failure; never print it
        result["error"] = repr(exc)
    finally:
        result.update(
            allowed=allowed,
            violations=violations,
            injection=injection,
            service="wled_mcp.http_service" in sys.modules,
            pair_fallback=PAIR_CODE is not None and socket.socketpair is _PAIR,
        )
        with open(report, "w", encoding="utf-8") as handle:
            json.dump(result, handle)


if __name__ == "__main__":
    main(sys.argv[1:])
