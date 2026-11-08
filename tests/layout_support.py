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

WLED 16 segment evidence (ISSUE-19-DEC-003, v16.0.1 29b389d), all opt-in so the stage-1
behavior above stays the default: ``v16=True`` serializes ``seg[].lc`` and the option keys
``c1``-``c3``, ``o1``-``o3``, ``si``, ``set``, ``m12``, ``bm`` (``serializeSegment``
L574-643) and applies them; ``matrix=(w, h)`` adds ``info.leds.matrix``, per-segment
``startY``/``stopY``/``rY``/``mY``/``tp`` and the X/Y clamping of ``setGeometry``
(FX_fcn.cpp L460-538, including the trailing 1D strip after the matrix); ``buses`` lists
``(first, end, lc)`` pixel ranges so each segment's capability is recomputed from the
pixels it covers after every geometry change (``refreshLightCapabilities`` L1027ff).
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from typing import Any

import httpx2 as httpx

from tests.state_catalog_support import EFFECTS, FXDATA, PALETTES, make_info, make_segment

DEFAULT_COLORS = [[255, 160, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
# FX.h defaults of the option keys a WLED 16 segment serializes (L42-48, L564-586).
V16_DEFAULTS: dict[str, Any] = {
    "c1": 128,
    "c2": 128,
    "c3": 16,
    "o1": False,
    "o2": False,
    "o3": False,
    "si": 0,
    "set": 0,
    "m12": 0,
    "bm": 0,
}
V16_SETTERS = ("cct", "c1", "c2", "o1", "o2", "o3", "si", "set", "bm")
ORIENTATION_KEYS = ("rY", "mY", "tp")


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
        v16: bool = False,
        matrix: tuple[int, int] | None = None,
        buses: list[tuple[int, int, int]] | None = None,
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
        self.v16 = v16
        self.matrix = matrix
        self.buses = buses
        for slot in self.slots:
            self._fill_v16(slot)
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

    def _fill_v16(self, slot: dict[str, Any]) -> None:
        if self.v16:
            for key, value in V16_DEFAULTS.items():
                slot.setdefault(key, value)
        if self.matrix is not None:
            slot.setdefault("startY", 0)
            slot.setdefault("stopY", self.matrix[1] if slot["stop"] > slot["start"] else 1)
            for key in ORIENTATION_KEYS:
                slot.setdefault(key, False)

    def segment_lc(self, slot: dict[str, Any]) -> int:
        """Capability bits of the pixels a segment covers (1 without a bus model)."""
        if self.buses is None:
            return 1
        width = self.matrix[0] if self.matrix is not None else self.led_count
        rows = range(slot.get("startY", 0), slot.get("stopY", 1))
        if self.matrix is not None and slot["start"] >= width * self.matrix[1]:
            rows = range(0, 1)  # trailing 1D strip: plain indices after the matrix
            width = 0
        bits = 0
        for y in rows:
            for x in range(slot["start"], slot["stop"]):
                index = x + width * y
                for first, end, lc in self.buses:
                    if first <= index < end:
                        bits |= lc
                        break
        return bits

    def info(self) -> dict[str, Any]:
        active = self.active()
        seglc: Any = [self.segment_lc(s) for s in active] if self.seglc == "auto" else self.seglc
        lc = self.lc
        if self.buses is not None:
            lc = 0
            for slot in active:
                lc |= self.segment_lc(slot)
        leds: dict[str, Any] = {
            "count": self.led_count,
            "maxseg": self.maxseg,
            "lc": lc,
        }
        if seglc is not None:
            leds["seglc"] = seglc
        if self.matrix is not None:
            leds["matrix"] = {"w": self.matrix[0], "h": self.matrix[1]}
        return make_info(leds=leds)

    def state(self) -> dict[str, Any]:
        out: list[dict[str, Any]] = []
        for slot in self.active():
            seg = copy.deepcopy(slot)
            seg["len"] = seg["stop"] - seg["start"]
            if not seg.get("n"):
                seg.pop("n", None)
            if self.v16:
                seg["lc"] = self.segment_lc(slot)
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
            self._fill_v16(self.slots[seg_id])
        slot = self.slots[seg_id]
        if self.matrix is not None and any(k in obj for k in ("start", "stop", "startY", "stopY")):
            if not self._set_geometry_2d(slot, obj, seg_id):
                return
        elif "start" in obj or "stop" in obj:
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
        if self.v16:
            for key in V16_SETTERS:
                if key in obj:
                    slot[key] = obj[key]
            if "c3" in obj:
                slot["c3"] = max(0, min(31, obj["c3"]))
            if "m12" in obj:
                slot["m12"] = max(0, min(7, obj["m12"]))
        if self.matrix is not None:
            for key in ORIENTATION_KEYS:
                if key in obj:
                    slot[key] = obj[key]

    def _set_geometry_2d(self, slot: dict[str, Any], obj: dict[str, Any], seg_id: int) -> bool:
        """``setGeometry`` on a matrix: X against width, Y against height, trailing strip.

        Omitted bounds keep the current value (``elem[key] | seg.key``). Returns False when
        the segment ends up removed.
        """
        assert self.matrix is not None
        width, height = self.matrix
        cells = width * height
        old = (slot["start"], slot["stop"], slot["startY"], slot["stopY"])
        i1 = obj.get("start", slot["start"])
        i2 = obj.get("stop", slot["stop"])
        i1y = obj.get("startY", slot["startY"])
        i2y = obj.get("stopY", slot["stopY"])
        if i2 <= i1:
            slot["stop"] = 0
            if seg_id == self.mainseg:
                self.mainseg = 0
            return False
        if i1 < width or cells <= i1 < self.led_count:
            slot["start"] = i1
        if i2 > cells and i1 >= cells:
            slot["stop"] = min(i2, self.led_count)
        else:
            slot["stop"] = max(1, min(i2, width))
        slot["startY"] = i1y if i1y < height else 0
        slot["stopY"] = max(1, min(i2y, height))
        if slot["start"] >= slot["stop"] or slot["startY"] >= slot["stopY"]:
            slot["stop"] = 0
            return False
        changed = old != (slot["start"], slot["stop"], slot["startY"], slot["stopY"])
        if changed and "n" not in obj:
            slot["n"] = ""
        return True

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
