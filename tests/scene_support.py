"""Synthetic multi-device fleet for the group and scene tests of issue #17.

Routes every request by host to one stateful ``FakeWLED`` (``tests/layout_support.py``) and
adds what scenes need: per-device effect and palette catalogs (so one name can map to
different IDs, or be ambiguous), an unreachable switch, a POST counter, a request log and
an in-flight gauge. The firmware model, bus capability bits and matrix shapes are those of
``FakeWLED``; nothing here contacts a network.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import anyio
import httpx2 as httpx

from tests.layout_support import FakeWLED
from tests.state_catalog_support import FakeClock
from tests.test_inventory_client import config, device
from wled_mcp.operations import build_operations
from wled_mcp.resources import Resources

EFFECTS = ["Solid", "Blink", "Breathe", "Wipe", "Fire 2012"]
PALETTES = ["Default", "Random Cycle", "Party", "Ocean"]
GROUP_FORMAT = "wled-mcp.group"
SCENE_FORMAT = "wled-mcp.scene"


class SceneDevice(FakeWLED):
    """A fake with its own catalogs, a reachability switch and an optional response delay."""

    def __init__(
        self,
        *,
        effects: list[str] | None = None,
        palettes: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.effects = list(EFFECTS if effects is None else effects)
        self.palettes = list(PALETTES if palettes is None else palettes)
        self.unreachable = False
        self.delay = 0.0

    def info(self) -> dict[str, Any]:
        info = super().info()
        info["fxcount"] = len(self.effects)
        info["palcount"] = len(self.palettes)
        return info

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        if self.unreachable:
            raise httpx.ConnectError("synthetic")
        if self.delay:
            await anyio.sleep(self.delay)
        path = request.url.path
        if request.method == "GET" and path in ("/json/eff", "/json/pal", "/json/fxdata"):
            self.calls.append((request.method, path))
            value = {
                "/json/eff": self.effects,
                "/json/pal": self.palettes,
                "/json/fxdata": [""] * len(self.effects),
            }[path]
            return httpx.Response(200, json=list(value))
        return await super().__call__(request)


class SceneFleet:
    """Routes by host; counts requests and the most requests ever in flight at once."""

    def __init__(self, **devices: SceneDevice) -> None:
        # Keys are device IDs; the host is "<id>.invalid".
        self.devices = {f"{name}.invalid": fake for name, fake in devices.items()}
        self.calls: list[tuple[str, str, str]] = []
        self.in_flight = 0
        self.max_in_flight = 0

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append((request.method, request.url.host, request.url.path))
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await anyio.sleep(0)
            return await self.devices[request.url.host](request)
        finally:
            self.in_flight -= 1

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self)

    def post_count(self) -> int:
        return sum(1 for method, _host, _path in self.calls if method == "POST")

    def hosts_called(self) -> set[str]:
        return {host for _method, host, _path in self.calls}


def strip(**kwargs: Any) -> SceneDevice:
    """A default three-segment v16-style device (segments 0, 2, 5)."""
    kwargs.setdefault("v16", True)
    return SceneDevice(**kwargs)


def open_fleet(
    tmp_path: Path, fleet: SceneFleet, *, timeout: float = 2.0, **settings: Any
) -> Resources:
    """Resources over the fleet; one configured device per fake, data under ``tmp_path``."""
    settings.setdefault("operation_timeout_seconds", timeout)
    devices = [device(name.removesuffix(".invalid")) for name in fleet.devices]
    return Resources(
        config(tmp_path, devices=devices, **settings), fleet.transport(), clock=FakeClock().clock()
    )


async def call(resources: Resources, tool: str, **arguments: Any) -> Any:
    operation = {op.name: op for op in build_operations(resources)}[tool]
    return await operation.execute(operation.request_model.model_validate(arguments).model_dump())


def group_arguments(group_id: str = "shelf", *members: Any, **extra: Any) -> dict[str, Any]:
    """Arguments of ``wled_save_group``; a member is a device ID or ``(device, [segments])``."""
    listed = []
    for member in members or ("desk", "shelf_left"):
        device_id, segments = member if isinstance(member, tuple) else (member, None)
        entry: dict[str, Any] = {"device": device_id}
        if segments is not None:
            entry["segments"] = segments
        listed.append(entry)
    return {"group_id": group_id, "name": f"Group {group_id}", "members": listed, **extra}


def scene_document(*targets: dict[str, Any], **extra: Any) -> dict:
    """A format-1 scene document; the default has one device target. ``id`` may be overridden."""
    document: dict[str, Any] = {
        "format": SCENE_FORMAT,
        "format_version": 1,
        "id": "evening",
        "name": "Evening scene",
        "targets": list(targets) or [device_target("desk")],
    }
    document.update(extra)
    return document


def device_target(device_id: str, **extra: Any) -> dict[str, Any]:
    target: dict[str, Any] = {"device": device_id}
    if "master" not in extra and "segments" not in extra:
        extra["master"] = {"on": True, "brightness": 100}
    target.update(extra)
    return target


def group_target(group_id: str, **extra: Any) -> dict[str, Any]:
    target: dict[str, Any] = {"group": group_id}
    if "master" not in extra and "segments" not in extra:
        extra["master"] = {"on": True}
    target.update(extra)
    return target


def stored_scene_path(tmp_path: Path, scene_id: str) -> Path:
    return tmp_path / "scenes" / f"{scene_id}.json"


def stored_group_path(tmp_path: Path, group_id: str) -> Path:
    return tmp_path / "groups" / f"{group_id}.json"


def write_raw(path: Path, content: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))


def write_scene_file(tmp_path: Path, document: dict[str, Any]) -> Path:
    path = stored_scene_path(tmp_path, document["id"])
    write_raw(path, json.dumps(document, indent=2) + "\n")
    return path


def write_group_file(tmp_path: Path, group_id: str, members: list[dict[str, Any]]) -> Path:
    path = stored_group_path(tmp_path, group_id)
    document = {
        "format": GROUP_FORMAT,
        "format_version": 1,
        "id": group_id,
        "name": f"Group {group_id}",
        "members": members,
    }
    write_raw(path, json.dumps(document, indent=2) + "\n")
    return path


def segments_of(fake: FakeWLED) -> dict[int, dict[str, Any]]:
    return {seg["id"]: seg for seg in fake.state()["seg"]}


def canonical_scene() -> dict[str, Any]:
    """The scene retained (in shareable form) as examples/contracts/scene.json."""
    return {
        "format": SCENE_FORMAT,
        "format_version": 1,
        "id": "evening",
        "name": "Evening",
        "description": "Warm, dim lighting with a slow wipe on the strips",
        "targets": [
            {
                "device": "desk",
                "master": {"on": True, "brightness": 120, "transition_ms": 500},
                "segments": [
                    {
                        "ids": [0, 2],
                        "colors": [[255, 147, 41]],
                        "effect_name": "Solid",
                        "palette_name": "Default",
                    }
                ],
            },
            {
                "group": "shelf",
                "segments": [{"colors": [[255, 120, 20]], "effect_name": "Wipe", "speed": 60}],
            },
        ],
    }
