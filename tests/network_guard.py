"""Offline guard for tests that must never resolve a name or open a connection.

``install_no_network`` replaces ``socket.getaddrinfo``, ``socket.create_connection`` and
``socket.socket.connect`` / ``connect_ex`` with functions that record the attempt and raise
``AssertionError``. The one exception is the Windows event loop: the default Proactor loop
builds its self-pipe with the stdlib ``socket._fallback_socketpair`` (also ``socket.socketpair``
there), which connects a client socket to a listener on a loopback port. That connect is
delegated to the real method only when its direct caller is that function's code object and
the address is loopback (the caller attribution of ``tests/stdio_socket_probe.py``, issue #53).
Native ``socketpair()`` on POSIX never connects, so nothing changes there. Every other
caller, including loopback connects from test code, httpx or anyio, is refused and recorded.

Known limit (pre-existing, not widened here): the Windows Proactor loop connects outbound
through ``ConnectEx`` in ``_overlapped``, which bypasses ``socket.socket.connect``. The tests
that use this guard run against ``httpx.MockTransport`` or an in-process client, so the code
under test never attempts a connection.
"""

from __future__ import annotations

import ipaddress
import socket
import sys
from types import CodeType
from typing import Any

import pytest

_PAIR = getattr(socket, "_fallback_socketpair", None)
PAIR_CODE: CodeType | None = _PAIR.__code__ if _PAIR is not None else None


def _is_loopback(host: object) -> bool:
    if not isinstance(host, str):
        return False
    try:
        return ipaddress.ip_address(host.split("%", 1)[0]).is_loopback
    except ValueError:
        return False


def connect_allowed(caller_code: CodeType | None, address: object) -> bool:
    """True only for the stdlib socketpair helper connecting to a loopback host."""
    if PAIR_CODE is None or caller_code is not PAIR_CODE:
        return False
    return isinstance(address, tuple) and len(address) >= 2 and _is_loopback(address[0])


def install_no_network(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Install the guard and return the list of refused attempts (empty when clean)."""
    attempts: list[Any] = []
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def refuse(*args: Any, **kwargs: Any) -> Any:
        attempts.append(args[:1])
        raise AssertionError("tests must not resolve names or open connections")

    def guarded(original: Any) -> Any:
        def method(self: socket.socket, address: Any) -> Any:
            if connect_allowed(sys._getframe(1).f_code, address):
                return original(self, address)
            return refuse(address)

        return method

    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", guarded(original_connect))
    monkeypatch.setattr(socket.socket, "connect_ex", guarded(original_connect_ex))
    return attempts
