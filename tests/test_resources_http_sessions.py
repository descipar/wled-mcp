"""Issue #258: two concurrent HTTP sessions read resources without leaking into each other.

In-process service on a loopback socket against the mocked fleet (tests/http_support.py); no LAN.
"""

from __future__ import annotations

import json
from typing import Any

import anyio
import pytest
from mcp import MCPError

from tests.http_support import DESK, SHELF, make_fleet, running_service, sdk_client

DESK_EFFECTS = ["Solid", "DeskGlow"]
SHELF_EFFECTS = ["Solid", "ShelfWave", "ShelfPulse"]
ROUNDS = 5


def fleet() -> Any:
    router = make_fleet()
    router.set(DESK, "/json/eff", DESK_EFFECTS)
    router.set(SHELF, "/json/eff", SHELF_EFFECTS)
    router.set(DESK, "/json/pal", ["Default", "DeskPalette"])
    router.set(SHELF, "/json/pal", ["Default", "ShelfPalette"])
    router.set(DESK, "/json/fxdata", ["", ""])
    router.set(SHELF, "/json/fxdata", ["", "", ""])
    return router


def names(result: Any, kind: str) -> list[str]:
    body = json.loads(result.contents[0].text)
    assert body["ok"] is True and "correlation_id" not in body
    return [item["name"] for item in body["data"][kind]]


async def session(run: Any, controllers: list[str], bad: str, seen: list[Any]) -> None:
    async with sdk_client(run) as client:
        for _ in range(ROUNDS):
            for controller in controllers:
                effects = await client.read_resource(f"wled://devices/{controller}/effects")
                palettes = await client.read_resource(f"wled://devices/{controller}/palettes")
                seen.append((controller, names(effects, "effects"), names(palettes, "palettes")))
            with pytest.raises(MCPError) as caught:
                await client.read_resource(f"wled://devices/{bad}/effects")
            seen.append((bad, caught.value.error.data))


async def check(seen: list[Any], controllers: list[str], bad: str) -> None:
    expected = {
        "desk": (DESK_EFFECTS, ["Default", "DeskPalette"]),
        "shelf": (SHELF_EFFECTS, ["Default", "ShelfPalette"]),
    }
    good = [item for item in seen if len(item) == 3]
    failed = [item for item in seen if len(item) == 2]
    assert len(good) == ROUNDS * len(controllers) and len(failed) == ROUNDS
    for controller, effects, palettes in good:
        assert (effects, palettes) == expected[controller]
    for name, data in failed:
        assert name == bad
        assert data["ok"] is False and data["error"]["code"] == "UNKNOWN_DEVICE"
        assert bad not in json.dumps(data)


@pytest.mark.anyio
async def test_concurrent_sessions_get_independent_correct_resources(tmp_path):
    a: list[Any] = []
    b: list[Any] = []
    with anyio.fail_after(60):
        async with running_service(tmp_path, fleet()) as run:
            async with anyio.create_task_group() as group:
                # Same controller (desk) in both, different second controllers and error targets.
                group.start_soon(session, run, ["desk", "shelf"], "nobody", a)
                group.start_soon(session, run, ["desk"], "ghost", b)
            # A fresh session afterwards still sees the same, uncontaminated data.
            async with sdk_client(run) as client:
                result = await client.read_resource("wled://devices/shelf/effects")
                assert names(result, "effects") == SHELF_EFFECTS
    await check(a, ["desk", "shelf"], "nobody")
    await check(b, ["desk"], "ghost")
