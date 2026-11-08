"""Stateful mock WLED fleet for the preset tools (issue #9). Never touches a network.

The fake models only facts recorded in docs/SOURCES.md ("Issue-9 preset evidence"):
``psave`` is processed asynchronously and stores a ``serializeState(forPreset)`` shaped
entry (inactive slots as ``{"stop": 0}`` markers), ``pdel`` removes the key, ``ps``
selects a preset in the main loop, and a POST of ``psave`` never changes live state.
Persistence is delayed by a configurable number of readbacks of the affected resource.
A WLED 16 profile is modelled by a live state carrying ``bs`` (docs/SOURCES.md "Issue-66
WLED 16 preset evidence"): only then does a saved entry carry ``bs`` too.

Issue #18 adds the two single-entry routes of docs/SOURCES.md "Issue-18 WLED 16 preset
write evidence": ``psave`` with a non-null ``o`` and no ``playlist`` applies the request
to the live state and stores it verbatim minus ``o``, ``v``, ``time``, ``error``,
``psave`` and ``bootps``; ``psave`` with ``o`` and ``playlist`` starts the playlist and
stores it re-serialized (full per-entry ``dur``/``transition`` arrays, ``repeat``,
``end``, ``r``, ``on: true``, the name; unknown fields dropped).
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from typing import Any

import anyio
import httpx2 as httpx

from tests.state_catalog_support import make_info, make_state

Hook = Callable[["PresetDevice"], None]


class PresetDevice:
    def __init__(
        self,
        store: dict[str, Any] | None = None,
        state: dict[str, Any] | None = None,
        info: dict[str, Any] | None = None,
    ) -> None:
        self.store: dict[str, Any] = {"0": {}} if store is None else store
        self.state: dict[str, Any] = state if state is not None else make_state()
        self.info: dict[str, Any] = info if info is not None else make_info()
        self.posts: list[dict[str, Any]] = []
        self.get_counts: dict[str, int] = {}
        self.presets_get_headers: list[dict[str, str]] = []
        # Behavior knobs.
        self.persist_delay = 0  # presets.json readbacks before psave/pdel become visible
        self.apply_delay = 0  # state readbacks before ps becomes visible
        self.persist = True  # False: ACK the POST but never store anything
        self.post_mode = "ok"  # ok | timeout_after_apply | timeout_no_apply | connect_error
        self.entry_mutator: Callable[[dict[str, Any]], None] | None = None
        self.before_presets_get: Hook | None = None
        self.on_post: Callable[[dict[str, Any]], None] | None = None
        # Hang every presets.json readback after this many post-POST polls (None: never).
        self.hang_after_post_polls: int | None = None
        self._post_polls = 0
        self.presets_get_failure: Callable[[int], BaseException | None] | None = None
        self._pending: list[tuple[str, int, dict[str, Any]]] = []

    # ------------------------------------------------------------------ helpers

    def entry_from_state(self, name: str) -> dict[str, Any]:
        active = {seg["id"]: seg for seg in self.state["seg"]}
        segments: list[dict[str, Any]] = []
        for slot in range(max(active) + 1):
            if slot not in active:
                segments.append({"stop": 0})
                continue
            seg = active[slot]
            segments.append(
                {
                    "id": slot,
                    "start": seg["start"],
                    "stop": seg["stop"],
                    "grp": seg["grp"],
                    "spc": seg["spc"],
                    "of": seg["of"],
                    "on": seg["on"],
                    "frz": seg["frz"],
                    "bri": seg["bri"],
                    "cct": seg["cct"],
                    "set": 0,
                    "n": seg.get("n", ""),
                    "col": copy.deepcopy(seg["col"]),
                    "fx": seg["fx"],
                    "sx": seg["sx"],
                    "ix": seg["ix"],
                    "pal": seg["pal"],
                    "c1": 128,
                    "c2": 128,
                    "c3": 16,
                    "sel": seg["sel"],
                    "rev": seg["rev"],
                    "mi": seg["mi"],
                    "o1": False,
                    "o2": False,
                    "o3": False,
                    "si": 0,
                    "m12": 0,
                }
            )
        entry: dict[str, Any] = {
            "on": self.state["on"],
            "bri": self.state["bri"],
            "transition": self.state["transition"],
        }
        if "bs" in self.state:  # v16.0.1 emits bs next to transition (includeBri block)
            entry["bs"] = self.state["bs"]
        entry.update({"mainseg": self.state["mainseg"], "seg": segments, "n": name})
        if self.entry_mutator is not None:
            self.entry_mutator(entry)
        return entry

    def store_verbatim(self, body: dict[str, Any]) -> None:
        """State route: apply the request live, then store it minus the removed keys."""
        for key in ("on", "bri", "transition", "bs", "mainseg"):
            if key in body:
                self.state[key] = body[key]
        live = {seg["id"]: seg for seg in self.state["seg"]}
        for patch in body.get("seg") or []:
            if isinstance(patch, dict) and patch.get("id") in live:
                live[patch["id"]].update({k: v for k, v in patch.items() if k != "id"})
        removed = {"o", "v", "time", "error", "psave", "bootps"}
        entry = {key: copy.deepcopy(value) for key, value in body.items() if key not in removed}
        if entry.get("n") is None:
            entry["n"] = f"Preset {body['psave']}"
        if self.entry_mutator is not None:
            self.entry_mutator(entry)
        self.store[str(body["psave"])] = entry

    def store_playlist(self, body: dict[str, Any]) -> None:
        """Playlist route: start the playlist, then store it from runtime data."""
        playlist = body["playlist"]
        ids = list(playlist["ps"])

        def expand(value: Any, default: int) -> list[int]:
            if value is None:
                return [default] * len(ids)
            values = [value] if isinstance(value, int) else list(value)
            values = values[: len(ids)]
            return values + [values[-1]] * (len(ids) - len(values))

        entry: dict[str, Any] = {
            "playlist": {
                "ps": ids,
                "dur": expand(playlist.get("dur"), 100),
                "transition": expand(playlist.get("transition"), self.state["transition"]),
                "repeat": playlist.get("repeat", 0),
                "end": playlist.get("end", 0),
                "r": int(bool(playlist.get("r", False))),  # playlistOptions & 1
            },
            "on": True,
            "n": body.get("n") or f"Preset {body['psave']}",
        }
        if body.get("ql"):
            entry["ql"] = body["ql"]
        if self.entry_mutator is not None:
            self.entry_mutator(entry)
        self.state["pl"] = body["psave"]
        self.state["ps"] = ids[0]
        self.store[str(body["psave"])] = entry

    def psave_count(self) -> int:
        return sum(1 for body in self.posts if "psave" in body)

    def _apply(self, kind: str, body: dict[str, Any]) -> None:
        if kind == "psave":
            if body.get("o") is not None:
                if self.persist:
                    if "playlist" in body:
                        self.store_playlist(body)
                    else:
                        self.store_verbatim(body)
            elif self.persist:
                self.store[str(body["psave"])] = self.entry_from_state(body["n"])
        elif kind == "pdel":
            if self.persist:
                self.store.pop(str(body["pdel"]), None)
        else:  # ps: applyPreset sets the active marker; a playlist sets pl
            identifier = body["ps"]
            entry = self.store.get(str(identifier)) or {}
            if "playlist" in entry:
                self.state["pl"] = identifier
                self.state["ps"] = identifier
            else:
                self.state["pl"] = -1
                self.state["ps"] = identifier

    def _tick(self, resource: str) -> None:
        due = []
        remaining = []
        for kind, delay, body in self._pending:
            belongs = (kind == "ps") == (resource == "state")
            if belongs and delay <= 0:
                due.append((kind, body))
            else:
                remaining.append((kind, delay - 1 if belongs else delay, body))
        self._pending = remaining
        for kind, body in due:
            self._apply(kind, body)

    # --------------------------------------------------------------------- HTTP

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "POST":
            assert path == "/json/state", path
            body = json.loads(request.content.decode("utf-8"))
            self.posts.append(body)
            if self.on_post is not None:
                self.on_post(body)
            if self.post_mode == "connect_error":
                raise httpx.ConnectError("synthetic")
            kind = "psave" if "psave" in body else "pdel" if "pdel" in body else "ps"
            if self.post_mode != "timeout_no_apply":
                delay = self.apply_delay if kind == "ps" else self.persist_delay
                if delay == 0:
                    self._apply(kind, body)
                else:
                    self._pending.append((kind, delay, body))
            if self.post_mode.startswith("timeout"):
                raise httpx.ReadTimeout("synthetic")
            return httpx.Response(200, json={"success": True})
        name = path.rsplit("/", 1)[-1]
        self.get_counts[name] = self.get_counts.get(name, 0) + 1
        if path == "/presets.json":
            self.presets_get_headers.append(dict(request.headers))
            if self.before_presets_get is not None:
                self.before_presets_get(self)
            if self.presets_get_failure is not None:
                failure = self.presets_get_failure(self.get_counts[name])
                if failure is not None:
                    raise failure
            self._tick("presets")
            return httpx.Response(200, json=copy.deepcopy(self.store))
        if path == "/json/state":
            self._tick("state")
            return httpx.Response(200, json=copy.deepcopy(self.state))
        if path == "/json/info":
            return httpx.Response(200, json=copy.deepcopy(self.info))
        raise AssertionError(f"unexpected path {path}")


class PresetFleet:
    """Routes by host to one stateful device each; counts every call."""

    def __init__(self, **devices: PresetDevice) -> None:
        # Keys are host names such as "desk.invalid".
        self.devices = {host.replace("__", "."): device for host, device in devices.items()}
        self.calls: list[tuple[str, str, str]] = []

    def add(self, host: str, device: PresetDevice) -> PresetDevice:
        self.devices[host] = device
        return device

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append((request.method, request.url.host, request.url.path))
        await anyio.sleep(0)
        device = self.devices[request.url.host]
        if device.hang_after_post_polls is not None and request.url.path == "/presets.json":
            if device.posts:
                device._post_polls += 1
                if device._post_polls > device.hang_after_post_polls:
                    await anyio.sleep(60)
        return self.devices[request.url.host].handle(request)

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self)

    def post_count(self) -> int:
        return sum(1 for method, _host, _path in self.calls if method == "POST")


def state_entry(name: str = "Warm", **extra: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "on": True,
        "bri": 128,
        "transition": 7,
        "seg": [{"id": 0, "start": 0, "stop": 30, "col": [[255, 160, 0]], "fx": 0}],
        "n": name,
    }
    entry.update(extra)
    return entry


def playlist_entry(ids: list[int], name: str = "Cycle", **extra: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "playlist": {"ps": ids, "dur": [100] * len(ids), "transition": [7], "repeat": 0, "end": 0},
        "on": True,
        "n": name,
    }
    entry.update(extra)
    return entry
