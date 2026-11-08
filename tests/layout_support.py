"""Stateful fake WLED for layout-replacement tests (issue #7). Never touches the network.

Models the baseline profile-0 behavior (v0.15.1 source, observed on 16.0.1) that matters
for a layout replacement (source-derived, ``docs/SOURCES.md#issue-7-layout-evidence``):
single-object ``seg`` edits, removal by
``stop <= start`` that keeps the slot, append-at-end allocation that ignores the requested
ID, ``id >= maxseg`` ignored, geometry change clearing the name unless ``n`` is sent,
offset clamping, main reset to 0 when the main slot is removed, ``mainseg < slots``,
bri/on interplay and the array-path purge (so accidental array or bulk use is caught).

Issue #52 adds the master power/brightness coupling of ``json.cpp`` L314-318 and
``led.cpp`` ``toggleOnOff``: ``on = root["on"] | (bri > 0)``, a toggle when power and the
actual brightness disagree, and a readback of ``on = bri > 0`` with the remembered
``briLast`` as ``bri`` (``json.cpp`` L572-575). Segment behavior is unchanged.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from typing import Any

import httpx2 as httpx

from tests.state_catalog_support import EFFECTS, FXDATA, PALETTES, make_info, make_segment

DEFAULT_COLORS = [[255, 160, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]


def inactive_slot(seg_id: int, **overrides: Any) -> dict[str, Any]:
    slot = make_segment(seg_id, 0, 0, **{"n": "", **overrides})
    slot["stop"] = 0
    slot["len"] = 0
    return slot


class FakeWLED:
    """One fake device. ``slots`` is the full segment vector (active and inactive)."""

    def __init__(
        self,
        segments: list[dict[str, Any]] | None = None,
        *,
        slot_count: int | None = None,
        led_count: int = 60,
        maxseg: int = 16,
        mainseg: int = 0,
        lc: int | Any = 1,
        seglc: list[int] | None | str = "auto",
        name_buffer: int = 32,
    ) -> None:
        active = (
            segments
            if segments is not None
            else [make_segment(0, 0, 10), make_segment(2, 10, 20), make_segment(5, 20, 30)]
        )
        size = max([s["id"] for s in active] + [(slot_count or 0) - 1]) + 1
        self.slots: list[dict[str, Any]] = [inactive_slot(i) for i in range(size)]
        for seg in active:
            self.slots[seg["id"]] = copy.deepcopy(seg)
        self.name_buffer = name_buffer  # firmware name buffer in bytes (ESP8266 32, ESP32 64)
        self.led_count = led_count
        self.maxseg = maxseg
        self.mainseg = mainseg
        self.lc = lc
        self.seglc = seglc
        # Master readback: ``on`` is actual power, ``bri`` the remembered ``briLast``.
        self.on = True
        self.bri = 128
        self.posts: list[Any] = []
        self.calls: list[tuple[str, str]] = []
        self.layouts: list[dict[int, tuple[int, int]]] = []
        self.array_used = False
        # hooks ------------------------------------------------------------------
        # POST index -> "drop" (ACK, ignore) | "fail_before" | "fail_after" | callable
        self.post_actions: dict[int, Any] = {}
        # POST index -> mutation applied right after that POST (external interference)
        self.interference: dict[int, Callable[[FakeWLED], None]] = {}
        self.ignore_keys: set[str] = set()
        self.fail_reads_from_post: int | None = None
        self.read_hook: Callable[[], Any] | None = None

    # ------------------------------------------------------------------ views
    def active(self) -> list[dict[str, Any]]:
        return [s for s in self.slots if s["stop"] > s["start"]]

    def layout(self) -> dict[int, tuple[int, int]]:
        return {s["id"]: (s["start"], s["stop"]) for s in self.active()}

    def info(self) -> dict[str, Any]:
        active = self.active()
        seglc: Any = [1] * len(active) if self.seglc == "auto" else self.seglc
        leds: dict[str, Any] = {
            "count": self.led_count,
            "maxseg": self.maxseg,
            "lc": self.lc,
        }
        if seglc is not None:
            leds["seglc"] = seglc
        return make_info(leds=leds)

    def state(self) -> dict[str, Any]:
        out: list[dict[str, Any]] = []
        for slot in self.active():
            seg = copy.deepcopy(slot)
            seg["len"] = seg["stop"] - seg["start"]
            if not seg.get("n"):
                seg.pop("n", None)
            out.append(seg)
        return {
            "on": self.on,
            "bri": self.bri,
            "transition": 7,
            "ps": -1,
            "pl": -1,
            "mainseg": self.mainseg,
            "seg": out,
        }

    # ------------------------------------------------------------------ firmware model
    def apply(self, body: dict[str, Any]) -> None:
        self._apply_master(body)
        if "mainseg" in body:
            value = body["mainseg"]
            self.mainseg = value if 0 <= value < len(self.slots) else 0
        seg = body.get("seg")
        if isinstance(seg, dict):
            self._apply_segment(seg)
        elif isinstance(seg, list):
            self.array_used = True
            deleted = 0
            for item in seg:
                if isinstance(item, dict):
                    self._apply_segment(item)
                    if item.get("stop") == 0:
                        deleted += 1
            if len(self.slots) > 3 and deleted >= len(self.slots) // 2:
                self._purge()

    def _apply_master(self, body: dict[str, Any]) -> None:
        """Top-level ``on``/``bri`` per pinned ``json.cpp`` L314-318 and ``toggleOnOff``."""
        obj = {k: v for k, v in body.items() if k in ("on", "bri") and k not in self.ignore_keys}
        if not obj:
            return
        bri = self.bri if self.on else 0  # firmware ``bri`` (actual output brightness)
        bri_last = self.bri
        if "bri" in obj:
            bri = obj["bri"]
        on = obj["on"] if "on" in obj else bri > 0
        if (not on) != (not bri):  # toggleOnOff()
            if bri == 0:
                bri = bri_last
            else:
                bri_last, bri = bri, 0
        if bri > 0:
            bri_last = bri
        self.on = bri > 0
        self.bri = bri_last

    def _purge(self) -> None:
        kept = [s for s in self.slots if s["stop"] > s["start"]]
        for index, slot in enumerate(kept):
            slot["id"] = index
        self.slots = kept
        self.mainseg = 0

    def _apply_segment(self, obj: dict[str, Any]) -> None:
        obj = {k: v for k, v in obj.items() if k not in self.ignore_keys}
        seg_id = obj.get("id", self.mainseg)
        if seg_id >= len(self.slots):
            if len(self.slots) >= self.maxseg or obj.get("stop", -1) <= 0:
                return
            seg_id = len(self.slots)
            self.slots.append(inactive_slot(seg_id))
        slot = self.slots[seg_id]
        if "start" in obj or "stop" in obj:
            start = obj.get("start", slot["start"])
            stop = obj.get("stop", slot["stop"])
            changed = (start, stop) != (slot["start"], slot["stop"])
            if stop <= start:
                slot["stop"] = 0
                if seg_id == self.mainseg:
                    self.mainseg = 0
                return
            slot["start"], slot["stop"] = start, stop
            if changed and "n" not in obj:
                slot["n"] = ""
        length = slot["stop"] - slot["start"]
        if "grp" in obj:
            slot["grp"] = (obj["grp"] & 255) or 1
        if "spc" in obj:
            slot["spc"] = obj["spc"] & 255
        if "of" in obj:
            slot["of"] = obj["of"] % length if length else 0
        if length and slot["of"] > length - 1:
            slot["of"] = length - 1
        if "bri" in obj:
            if obj["bri"] > 0:
                slot["bri"] = obj["bri"]
            slot["on"] = obj["bri"] > 0
        if "on" in obj:
            slot["on"] = obj["on"]
        if "col" in obj:
            for index, color in enumerate(obj["col"][:3]):
                slot["col"][index] = list(color) + [0] * (4 - len(color))
        if "n" in obj:
            slot["n"] = obj["n"].encode()[: self.name_buffer].decode(errors="ignore")
        for key in ("fx", "sx", "ix", "pal", "frz", "sel", "rev", "mi"):
            if key in obj:
                slot[key] = obj[key]

    # ------------------------------------------------------------------ transport
    async def __call__(self, request: httpx.Request) -> httpx.Response:
        path, method = request.url.path, request.method
        self.calls.append((method, path))
        if method == "POST":
            body = json.loads(request.content.decode("utf-8"))
            index = len(self.posts)
            self.posts.append(body)
            action = self.post_actions.get(index)
            if callable(action):
                result = action(self, request)
                if hasattr(result, "__await__"):
                    result = await result
                action = result
            if action == "fail_before":
                raise httpx.ReadTimeout("synthetic")
            if action != "drop":
                self.apply(body)
            self.layouts.append(self.layout())
            hook = self.interference.get(index)
            if hook is not None:
                hook(self)
            if action == "fail_after":
                raise httpx.ReadTimeout("synthetic")
            return httpx.Response(200, json={"success": True})
        if self.read_hook is not None:
            result = self.read_hook()
            if hasattr(result, "__await__"):
                await result
        if (
            path == "/json/state"
            and self.fail_reads_from_post is not None
            and len(self.posts) >= self.fail_reads_from_post
        ):
            raise httpx.ReadError("synthetic")
        if path == "/json/state":
            return httpx.Response(200, json=self.state())
        if path == "/json/info":
            return httpx.Response(200, json=self.info())
        if path == "/json/eff":
            return httpx.Response(200, json=list(EFFECTS))
        if path == "/json/pal":
            return httpx.Response(200, json=list(PALETTES))
        if path == "/json/fxdata":
            return httpx.Response(200, json=list(FXDATA))
        return httpx.Response(404, json={})

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self)

    def method_count(self, method: str) -> int:
        return sum(1 for m, _p in self.calls if m == method)
