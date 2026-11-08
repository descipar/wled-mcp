"""Synthetic WLED 16 devices for the bundle and playlist tests of issue #18.

Extends the stateful preset fake with the effect and palette catalogs (``/json/eff``,
``/json/pal``, ``/json/fxdata``) that import planning reads. The firmware version, LED
count, segment maximum, matrix and capability bits are set explicitly here and never
taken from shared fixture defaults. No network access.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import anyio
import httpx2 as httpx
import pytest

from tests.preset_support import PresetDevice, PresetFleet
from tests.state_catalog_support import FakeClock, make_info, make_state
from tests.test_inventory_client import config
from wled_mcp.operations import build_operations
from wled_mcp.resources import Resources

FIRMWARE = "16.0.1"
EFFECTS = ["Solid", "Blink", "Breathe", "Wipe", "Fire 2012"]
PALETTES = ["Default", "Random Cycle", "Party", "Ocean"]
FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "contracts" / "preset-bundle.json"


class BundleDevice(PresetDevice):
    def __init__(
        self,
        store: dict[str, Any] | None = None,
        *,
        led_count: int = 90,
        maxseg: int = 32,
        matrix: dict[str, int] | None = None,
        lc: int = 1,
        effects: list[str] | None = None,
        palettes: list[str] | None = None,
        version: str = FIRMWARE,
    ) -> None:
        leds: dict[str, Any] = {"count": led_count, "maxseg": maxseg, "lc": lc, "seglc": [lc]}
        if matrix is not None:
            leds["matrix"] = matrix
        effect_names = list(EFFECTS if effects is None else effects)
        palette_names = list(PALETTES if palettes is None else palettes)
        super().__init__(
            store={"0": {}, **(store or {})},
            state=make_state(bs=0),
            info=make_info(
                ver=version, leds=leds, fxcount=len(effect_names), palcount=len(palette_names)
            ),
        )
        self.effects = effect_names
        self.palettes = palette_names

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and path in ("/json/eff", "/json/pal", "/json/fxdata"):
            name = path.rsplit("/", 1)[-1]
            self.get_counts[name] = self.get_counts.get(name, 0) + 1
            value = {
                "/json/eff": self.effects,
                "/json/pal": self.palettes,
                "/json/fxdata": [""] * len(self.effects),
            }[path]
            return httpx.Response(200, json=copy.deepcopy(value))
        return super().handle(request)


class DeadlineClock:
    """Controlled deadline time: ``Deadline`` reads ``anyio.current_time``."""

    def __init__(self, base: float) -> None:
        self.base = base
        self.offset = 0.0

    def now(self) -> float:
        return self.base + self.offset


def freeze_deadline_clock(monkeypatch: pytest.MonkeyPatch) -> DeadlineClock:
    """Freeze the time the import deadlines run on; only ``clock.offset`` advances it.

    The import's per-write window also covers planning and the snapshot files, whose real
    I/O time depends on the host (issue #111: a slow arm64 runner exhausted the 1 s window
    before the first POST). With a frozen clock no deadline expires from slowness, and a
    test that needs an expiry advances ``offset`` explicitly. Poll sleeps stay real and
    short, so no test waits for a deadline.
    """
    clock = DeadlineClock(anyio.current_time())
    monkeypatch.setattr(anyio, "current_time", clock.now)
    return clock


def fleet_of(desk: BundleDevice) -> PresetFleet:
    fleet = PresetFleet()
    fleet.add("desk.invalid", desk)
    return fleet


def open_resources(tmp_path, fleet: PresetFleet, **settings: Any) -> Resources:
    settings.setdefault("operation_timeout_seconds", 1.0)
    resources = Resources(
        config(tmp_path, **settings), fleet.transport(), clock=FakeClock().clock()
    )
    resources.poll_interval_seconds = 0.005
    return resources


async def call(resources: Resources, tool: str, **arguments: Any) -> Any:
    arguments.setdefault("device_id", "desk")
    operation = {op.name: op for op in build_operations(resources)}[tool]
    return await operation.execute(operation.request_model.model_validate(arguments).model_dump())


def state_preset(name: str, fx: int = 0, pal: int = 0, stop: int = 30, **extra: Any) -> dict:
    """A firmware-shaped saved state entry (inactive slot marker and unknown seg field)."""
    entry: dict[str, Any] = {
        "on": True,
        "bri": 128,
        "transition": 7,
        "bs": 0,
        "mainseg": 0,
        "seg": [
            {
                "id": 0,
                "start": 0,
                "stop": stop,
                "col": [[255, 160, 0], [0, 0, 0], [0, 0, 0]],
                "fx": fx,
                "pal": pal,
                "sx": 128,
                "ix": 128,
                "c1": 128,
                "o1": False,
                "si": 0,
            },
            {"stop": 0},
        ],
        "n": name,
    }
    entry.update(extra)
    return entry


def stored_playlist(ids: list[int], name: str = "Cycle", **playlist: Any) -> dict:
    """A playlist entry as the firmware re-serializes it."""
    body: dict[str, Any] = {
        "ps": ids,
        "dur": [100] * len(ids),
        "transition": [7] * len(ids),
        "repeat": 0,
        "end": 0,
        "r": 0,
    }
    body.update(playlist)
    return {"playlist": body, "on": True, "n": name}


def load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))
