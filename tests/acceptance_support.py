"""Synthetic loopback WLED for console-level acceptance tests (issue #10).

The fake binds ``127.0.0.1`` on an ephemeral port only. It keeps a resettable
state and a selectable POST behavior so the installed console can be driven to
verified, mismatching and uncertain write outcomes. Nothing contacts a LAN device.
"""

from __future__ import annotations

import copy
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Literal

from tests.state_catalog_support import EFFECTS, FXDATA, PALETTES, make_info, make_state

PostMode = Literal["apply", "ack_only", "reset"]
"""``apply``: update state and ACK; ``ack_only``: ACK without effect; ``reset``: read the
body, close the connection without a response and make later state reads unreadable."""


class LoopbackWLED:
    """Stateful synthetic controller that records every request it receives."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.mode: PostMode = "apply"
        self.state: dict[str, Any] = make_state()
        self.requests: list[tuple[str, str]] = []
        self.posts: list[Any] = []
        self.unreadable = False
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: Any) -> None:
                pass

            def _send(self, payload: Any, status: int = 200) -> None:
                body = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _drop(self) -> None:
                # No status line at all: the client sees a closed connection.
                self.close_connection = True

            def do_GET(self) -> None:  # noqa: N802
                with outer._lock:
                    outer.requests.append(("GET", self.path))
                    if self.path == "/json/state":
                        if outer.unreadable:
                            return self._drop()
                        payload: Any = copy.deepcopy(outer.state)
                    else:
                        routes = {
                            "/json/info": make_info(),
                            "/json/live": {"leds": ["FF0000"] * 45, "n": 2},
                            "/json/eff": list(EFFECTS),
                            "/json/pal": list(PALETTES),
                            "/json/fxdata": list(FXDATA),
                        }
                        if self.path not in routes:
                            return self._send({}, 404)
                        payload = routes[self.path]
                self._send(payload)

            def do_POST(self) -> None:  # noqa: N802
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                with outer._lock:
                    outer.requests.append(("POST", self.path))
                    outer.posts.append(body)
                    mode = outer.mode
                    if mode == "apply":
                        outer._apply(body)
                    elif mode == "reset":
                        outer.unreadable = True
                if mode == "reset":
                    return self._drop()
                self._send({"success": True})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = int(self.server.server_address[1])
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def _apply(self, body: dict[str, Any]) -> None:
        for key in ("on", "bri"):
            if key in body:
                self.state[key] = body[key]
        segments = body.get("seg")
        if isinstance(segments, dict):
            segments = [segments]
        for patch in segments or []:
            for segment in self.state["seg"]:
                if segment["id"] == patch.get("id"):
                    segment.update({k: v for k, v in patch.items() if k != "id"})

    def reset(self, mode: PostMode = "apply") -> None:
        """Restore the initial state, clear the request log and select a POST behavior."""
        with self._lock:
            self.mode = mode
            self.state = make_state()
            self.requests.clear()
            self.posts.clear()
            self.unreadable = False

    def count(self, method: str | None = None) -> int:
        with self._lock:
            return sum(1 for m, _path in self.requests if method is None or m == method)

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self._thread.join(timeout=10)
