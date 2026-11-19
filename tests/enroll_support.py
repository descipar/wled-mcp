"""Fakes for the ``wled_add_device`` tests (issue #203): no real socket, ever.

``FakeFetch`` replaces ``enroll_tools.fetch_info`` with scripted ``InfoResult`` values and
records every ``(address, port)`` it was asked for. ``refusing_fetch`` is the autouse default
of tests/conftest.py, so no test can reach the network through the tool by accident.
"""

import threading

from wled_mcp.discovery_engine import InfoResult


def refusing_fetch(address: str, port: int) -> InfoResult:
    raise AssertionError("a test reached the real verification read (a real HTTP request)")


class FakeFetch:
    def __init__(self, *answers: InfoResult, default: InfoResult | None = None) -> None:
        self.answers = list(answers)
        self.default = default or InfoResult("timeout")
        self.calls: list[tuple[str, int]] = []
        self.lock = threading.Lock()

    def __call__(self, address: str, port: int) -> InfoResult:
        with self.lock:
            self.calls.append((address, port))
            return self.answers.pop(0) if self.answers else self.default
