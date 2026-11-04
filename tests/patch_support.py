"""Mock router for write tests: captures POST bodies and allows per-path overrides.

Reuses the state fixtures from ``tests/state_catalog_support`` and extends them
with POST capture so issue #6 write/verify flows can be asserted against a
mocked WLED controller. Never contacts the network.
"""

from __future__ import annotations

import copy
import json
from collections import Counter
from collections.abc import Callable
from typing import Any

import httpx2 as httpx


class WriteRouter:
    """A mock fleet that captures every POST body per host.

    ``set(host, path, value)`` routes GET requests; ``set_post(host, path,
    response)`` routes POST requests. Captured POST calls land in ``posts``.
    """

    def __init__(self) -> None:
        self.get_routes: dict[tuple[str, str], Any] = {}
        self.post_routes: dict[tuple[str, str], Any] = {}
        self.calls: list[tuple[str, str, str]] = []  # (method, host, path)
        self.posts: list[tuple[str, str, Any]] = []  # (host, path, parsed body)

    def set(self, host: str, path: str, value: Any) -> None:
        self.get_routes[(host, path)] = value

    def set_post(self, host: str, path: str, value: Any) -> None:
        self.post_routes[(host, path)] = value

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
        from tests.state_catalog_support import EFFECTS, FXDATA, PALETTES, make_info, make_state

        self.set(host, "/json/info", info if info is not None else make_info())
        self.set(host, "/json/state", state if state is not None else make_state())
        self.set(host, "/json/eff", eff if eff is not None else list(EFFECTS))
        self.set(host, "/json/pal", pal if pal is not None else list(PALETTES))
        self.set(host, "/json/fxdata", fxdata if fxdata is not None else list(FXDATA))
        # Default POST handler for /json/state echoes success. Tests may override.
        self.set_post(host, "/json/state", httpx.Response(200, json={"success": True}))

    def count(self, method: str, host: str | None = None, path: str | None = None) -> int:
        return sum(
            1
            for call_method, call_host, call_path in self.calls
            if call_method == method
            and (host is None or call_host == host)
            and (path is None or call_path == path)
        )

    def method_counts(self) -> Counter[str]:
        return Counter(method for method, _host, _path in self.calls)

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        host = request.url.host
        path = request.url.path
        method = request.method
        self.calls.append((method, host, path))
        if method == "POST":
            body: Any
            try:
                body = json.loads(request.content.decode("utf-8"))
            except Exception:
                body = None
            self.posts.append((host, path, body))
            response = self.post_routes.get((host, path))
            if response is None:
                return httpx.Response(200, json={"success": True})
            if callable(response):
                response = response(request)
                if hasattr(response, "__await__"):
                    response = await response
            if isinstance(response, BaseException):
                raise response
            if isinstance(response, httpx.Response):
                return response
            return httpx.Response(200, json=copy.deepcopy(response))
        # GET path.
        value = self.get_routes[(host, path)]
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


# Convenience typed alias so tests can keep the shared router pattern.
PostHandler = Callable[[httpx.Request], Any]
