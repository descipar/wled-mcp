"""Synthetic WLED payloads and a counting mock router shared by issue #5 tests.

All values are synthetic (reserved example hosts, documentation-range addresses).
"""

import copy
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx2 as httpx

from wled_mcp.catalogs import Clock

SECRET = "synthetic-secret"


def make_info(**overrides: Any) -> dict[str, Any]:
    info: dict[str, Any] = {
        "ver": "16.0.1",
        "vid": 2510010,
        "cn": "Synthetic",
        "brand": "WLED",
        "product": "FOSS",
        "arch": "esp32",
        "name": "Example",
        "mac": "00005e005301",
        "ip": "192.0.2.10",
        "wifi": {"bssid": "00:00:5E:00:53:01", "rssi": -50, "signal": 80},
        "leds": {"count": 90, "maxseg": 32, "lc": 1, "seglc": [1, 1, 1]},
        "fxcount": 4,
        "palcount": 3,
    }
    info.update(overrides)
    return info


def make_segment(seg_id: int, start: int, stop: int, **overrides: Any) -> dict[str, Any]:
    segment: dict[str, Any] = {
        "id": seg_id,
        "start": start,
        "stop": stop,
        "len": stop - start,
        "grp": 1,
        "spc": 0,
        "of": 0,
        "on": True,
        "frz": False,
        "bri": 255,
        "cct": 127,
        "col": [[255, 160, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]],
        "fx": 0,
        "sx": 128,
        "ix": 128,
        "pal": 0,
        "sel": True,
        "rev": False,
        "mi": False,
        "n": f"Segment {seg_id}",
    }
    segment.update(overrides)
    return segment


def make_state(segments: list[dict[str, Any]] | None = None, **overrides: Any) -> dict[str, Any]:
    state: dict[str, Any] = {
        "on": True,
        "bri": 128,
        "transition": 7,
        "ps": -1,
        "pl": -1,
        "mainseg": 0,
        "seg": segments
        if segments is not None
        else [make_segment(0, 0, 30), make_segment(2, 30, 60), make_segment(5, 60, 90)],
    }
    state.update(overrides)
    return state


EFFECTS = ["Solid", "Blink", "RSVD", "Wipe", "RSVD", "Numeric 12"]
FXDATA = ["", "!,Duty cycle;!,!;!;01", "", "!,!;!,!;!", "", "!;;"]
PALETTES = ["Default", "* Random Cycle", "Party"]


class FakeClock:
    """Manually advanced monotonic and wall clock."""

    def __init__(self) -> None:
        self.t = 1000.0
        self.base = datetime(2026, 1, 1, tzinfo=UTC)

    def clock(self) -> Clock:
        return Clock(monotonic=lambda: self.t, now=lambda: self.base + timedelta(seconds=self.t))

    def advance(self, seconds: float) -> None:
        self.t += seconds


class Router:
    """Mock WLED fleet: per (host, path) a value, an exception or a callable.

    Values become 200 JSON responses; exceptions are raised by the transport.
    Every request is recorded; `count(host, path)` supports exact request assertions.
    """

    def __init__(self) -> None:
        self.routes: dict[tuple[str, str], Any] = {}
        self.calls: list[tuple[str, str]] = []

    def set(self, host: str, path: str, value: Any) -> None:
        self.routes[(host, path)] = value

    def device(
        self,
        host: str,
        *,
        info: Any = None,
        state: Any = None,
        eff: Any = None,
        pal: Any = None,
        fxdata: Any = None,
    ) -> None:
        self.set(host, "/json/info", info if info is not None else make_info())
        self.set(host, "/json/state", state if state is not None else make_state())
        self.set(host, "/json/eff", eff if eff is not None else list(EFFECTS))
        self.set(host, "/json/pal", pal if pal is not None else list(PALETTES))
        self.set(host, "/json/fxdata", fxdata if fxdata is not None else list(FXDATA))

    def count(self, host: str | None = None, path: str | None = None) -> int:
        return sum(
            1 for h, p in self.calls if (host is None or h == host) and (path is None or p == path)
        )

    def counts(self) -> Counter[tuple[str, str]]:
        return Counter(self.calls)

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        key = (request.url.host, request.url.path)
        self.calls.append(key)
        assert request.method == "GET", "read operations must never write"
        value = self.routes[key]
        if callable(value):
            value = value()
            if hasattr(value, "__await__"):
                value = await value
        if isinstance(value, BaseException):
            raise value
        if isinstance(value, httpx.Response):
            return value
        return httpx.Response(200, json=copy.deepcopy(value))

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self)


def json_headers(**extra: str) -> dict[str, str]:
    return {"content-type": "application/json", **extra}


Failure = Callable[[], Any]
