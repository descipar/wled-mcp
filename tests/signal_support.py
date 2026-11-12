"""Harness for the temporary-signal tests of issue #28 (S3-T02). Never touches the network.

``FakeController`` is a stateful mock WLED behind ``httpx.MockTransport``: it *applies* POST
bodies (master ``on``/``bri``, per-segment ``col``/``fx``/``on``/``bri``/``sx``/...), so a
restore is observable, and it can be edited externally between calls, taken offline, made to
drop or ignore a POST or to answer no readback. ``ManualTimer`` replaces the manager's wait with
the existing ``FakeClock`` so no test waits in real time. Every host is ``*.invalid``.
"""

from __future__ import annotations

import copy
import json
from collections import Counter
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anyio
import httpx2 as httpx

from tests.state_catalog_support import (
    EFFECTS,
    FXDATA,
    PALETTES,
    FakeClock,
    make_info,
    make_segment,
    make_state,
)
from wled_mcp.access import CURRENT_TOOL_CLASS, AccessPolicy, ToolClass
from wled_mcp.config import Device, HTTPSettings, StartupConfig
from wled_mcp.models import Outcome
from wled_mcp.operations import build_operations
from wled_mcp.resources import Resources

SOLID = EFFECTS.index("Solid")
WIPE = EFFECTS.index("Wipe")
BASE_COLOR = [255, 160, 0, 0]


def host_of(device_id: str) -> str:
    return f"{device_id}.invalid"


class FakeController:
    """One mock device. ``seg`` ids and geometry are fixed unless a test edits them."""

    def __init__(
        self,
        *,
        master_on: bool = False,
        master_bri: int = 47,
        segments: list[dict[str, Any]] | None = None,
        lc: int = 1,
    ) -> None:
        listed = (
            segments
            if segments is not None
            else [make_segment(0, 0, 30, fx=WIPE, col=[BASE_COLOR, [0, 0, 0, 0], [0, 0, 0, 0]])]
        )
        self.state: dict[str, Any] = make_state(listed, on=master_on, bri=master_bri)
        self.info: dict[str, Any] = make_info(
            leds={"count": 60, "maxseg": 16, "lc": lc, "seglc": [lc] * len(listed)},
            fxcount=len(EFFECTS),
            palcount=len(PALETTES),
        )
        self.posts: list[dict[str, Any]] = []  # bodies the device received
        self.post_attempts = 0  # including POSTs that failed before reaching the device
        self.gets: Counter[str] = Counter()
        self.classes: list[ToolClass | None] = []  # CURRENT_TOOL_CLASS seen at each POST
        self.offline = False
        self.hang = False
        self.unreadable_state = False
        self._post_modes: list[str] = []

    # -- test controls --------------------------------------------------------------

    def next_posts(self, *modes: str) -> None:
        """Behaviour of the next POSTs: apply, ack_only, drop, timeout or apply_unreadable."""
        self._post_modes = list(modes)

    def edit(self, **fields: Any) -> None:
        """An external client changes top-level state fields."""
        self.state.update(fields)

    def edit_segment(self, identifier: int, **fields: Any) -> None:
        self.segment(identifier).update(fields)

    def segment(self, identifier: int) -> dict[str, Any]:
        return next(s for s in self.state["seg"] if s["id"] == identifier)

    def snapshot(self) -> dict[str, Any]:
        return copy.deepcopy(self.state)

    # -- transport -----------------------------------------------------------------

    def _apply(self, body: dict[str, Any]) -> None:
        for key in ("on", "bri"):
            if key in body:
                self.state[key] = body[key]
        for patch in body.get("seg", []):
            segment = self.segment(patch["id"])
            for key, value in patch.items():
                if key == "id":
                    continue
                if key == "col":
                    # WLED keeps the stored channel width of a slot.
                    for index, slot in enumerate(value):
                        old = segment["col"][index]
                        segment["col"][index] = list(slot) + old[len(slot) :]
                else:
                    segment[key] = value

    async def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "POST":
            self.post_attempts += 1
            self.classes.append(CURRENT_TOOL_CLASS.get())
            if self.offline:
                raise httpx.ConnectError("offline")
            body = json.loads(request.content)
            self.posts.append(body)
            mode = self._post_modes.pop(0) if self._post_modes else "apply"
            if mode == "drop":
                raise httpx.ReadError("connection reset")
            if mode == "timeout":
                raise httpx.ReadTimeout("no answer")
            if mode != "ack_only":
                self._apply(body)
            if mode == "apply_unreadable":
                self.unreadable_state = True
            return httpx.Response(200, json={"success": True})
        self.gets[path] += 1
        if self.offline:
            raise httpx.ConnectError("offline")
        if self.hang:
            await anyio.sleep_forever()
        payloads: dict[str, Any] = {
            "/json/state": self.state,
            "/json/info": self.info,
            "/json/eff": list(EFFECTS),
            "/json/pal": list(PALETTES),
            "/json/fxdata": list(FXDATA),
        }
        if path == "/json/state" and self.unreadable_state:
            raise httpx.ReadError("unreadable")
        return httpx.Response(200, json=copy.deepcopy(payloads[path]))


class Fleet:
    """Routes by host to one ``FakeController`` per configured device."""

    def __init__(self, controllers: dict[str, FakeController]) -> None:
        self.controllers = controllers

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        return await self.controllers[request.url.host].handle(request)

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self)


class ManualTimer:
    """The manager's wait driven by ``FakeClock``: nothing sleeps, ``advance`` releases waiters."""

    def __init__(self, clock: FakeClock) -> None:
        self.clock = clock
        self.waiters: list[tuple[float, anyio.Event]] = []

    async def sleep_until(self, due: float, wake: anyio.Event) -> None:
        if wake.is_set() or self.clock.t >= due:
            return
        release = anyio.Event()
        entry = (due, release)
        self.waiters.append(entry)
        try:
            async with anyio.create_task_group() as group:

                async def watch() -> None:
                    await wake.wait()
                    release.set()

                group.start_soon(watch)
                await release.wait()
                group.cancel_scope.cancel()
        finally:
            self.waiters.remove(entry)

    def advance(self, seconds: float) -> None:
        self.clock.advance(seconds)
        for due, release in list(self.waiters):
            if self.clock.t >= due:
                release.set()


@dataclass
class Env:
    resources: Resources
    fleet: Fleet
    clock: FakeClock
    timer: ManualTimer
    path: Path
    operations: dict[str, Any] = field(default_factory=dict)

    @property
    def ctl(self) -> FakeController:
        return self.fleet.controllers[host_of("desk")]

    @property
    def signals(self) -> Any:
        return self.resources.signals

    def controller(self, device_id: str) -> FakeController:
        return self.fleet.controllers[host_of(device_id)]

    async def call(self, name: str, **arguments: Any) -> Outcome:
        """Run one tool as the dispatcher does (validation and ambient class), without G2."""
        operation = self.operations[name]
        validated = operation.request_model.model_validate(arguments).model_dump()
        token = CURRENT_TOOL_CLASS.set(operation.tool_class)
        try:
            return await operation.execute(validated)  # type: ignore[no-any-return]
        finally:
            CURRENT_TOOL_CLASS.reset(token)

    async def start(self, **overrides: Any) -> Outcome:
        arguments: dict[str, Any] = {
            "device_id": "desk",
            "segment_ids": [0],
            "color": [255, 0, 0],
            "duration_seconds": 10,
        }
        arguments.update(overrides)
        return await self.call("wled_start_signal", **arguments)

    async def status(self, operation_id: str) -> dict[str, Any]:
        outcome = await self.call("wled_get_signal_status", operation_id=operation_id)
        assert outcome.ok, outcome.error
        signal: dict[str, Any] = outcome.data["signal"]  # type: ignore[assignment]
        return signal

    async def until(self, predicate: Callable[[], bool], timeout: float = 5) -> None:
        with anyio.fail_after(timeout):
            while not predicate():
                await anyio.sleep(0.001)

    async def advance(self, seconds: float, until: Callable[[], bool] | None = None) -> None:
        """Move the controlled clock and let the released tasks run; optionally wait for a state."""
        self.timer.advance(seconds)
        if until is None:
            for _ in range(50):
                await anyio.sleep(0)
        else:
            await self.until(until)

    async def advance_until_ended(self, seconds: float, operation_id: str) -> dict[str, Any]:
        self.timer.advance(seconds)
        await self.until(lambda: self.signals.get(operation_id).done.is_set())
        return await self.status(operation_id)


def make_signal_config(
    path: Path,
    device_ids: Sequence[str] = ("desk",),
    *,
    profile: str = "full",
    caps: dict[str, str] | None = None,
    timeout: float = 2.0,
) -> StartupConfig:
    caps = caps or {}
    devices = tuple(
        Device(
            id=identifier,
            name=f"Example {identifier}",
            base_url=f"http://{host_of(identifier)}",
            max_class=caps.get(identifier),  # type: ignore[arg-type]
        )
        for identifier in device_ids
    )
    return StartupConfig(
        path / "config.toml",
        path,
        devices,
        HTTPSettings(operation_timeout_seconds=timeout),
        access=AccessPolicy(
            profile,  # type: ignore[arg-type]
            {identifier: ToolClass(value) for identifier, value in caps.items()},
        ),
    )


def make_env(
    path: Path,
    controllers: dict[str, FakeController] | None = None,
    *,
    device_ids: Sequence[str] = ("desk",),
    profile: str = "full",
    caps: dict[str, str] | None = None,
    timeout: float = 2.0,
) -> Env:
    """A resource graph over fake controllers; the caller enters it with ``async with env``."""
    fleet = Fleet(
        controllers
        if controllers is not None
        else {host_of(identifier): FakeController() for identifier in device_ids}
    )
    clock = FakeClock()
    resources = Resources(
        make_signal_config(path, device_ids, profile=profile, caps=caps, timeout=timeout),
        fleet.transport(),
        clock.clock(),
    )
    timer = ManualTimer(clock)
    resources.signals.sleep_until = timer.sleep_until
    env = Env(resources, fleet, clock, timer, path)
    env.operations = {op.name: op for op in build_operations(resources)}
    return env


@asynccontextmanager
async def signal_env(
    path: Path,
    controllers: dict[str, FakeController] | None = None,
    **options: Any,
) -> AsyncIterator[Env]:
    env = make_env(path, controllers, **options)
    with anyio.fail_after(60):
        async with env.resources:
            yield env


def tree(directory: Path) -> list[str]:
    return sorted(str(p.relative_to(directory)) for p in directory.rglob("*"))
