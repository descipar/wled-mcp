"""Issue #10, T08: readback tolerates unrelated transient fields, not requested mismatches.

SEG-04: "animation progression and normal unrelated transient fields are not equality
requirements". The fake changes fields nobody requested between the POST and the
readback (master timebase, preset/playlist indicators, an untouched segment's colors and
effect, unrequested fields of the patched segment); verification still succeeds. A
change of a requested field still fails. Mock transport only, no network.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.layout_support import FakeWLED
from tests.test_inventory_client import config
from wled_mcp.operations import build_operations
from wled_mcp.patches import PatchSegmentsRequest, SetStateRequest
from wled_mcp.resources import Resources


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class TransientWLED(FakeWLED):
    """Adds master fields that advance on every read, like a running controller."""

    def __init__(self) -> None:
        super().__init__()
        self.reads = 0
        self.master_extra: dict[str, Any] = {"ps": -1, "pl": -1}

    def state(self) -> dict[str, Any]:
        self.reads += 1
        state = super().state()
        state.update(self.master_extra)
        state["tb"] = 1000 * self.reads  # timebase advances with animation time
        return state


def segment(fake: FakeWLED, seg_id: int) -> dict[str, Any]:
    return fake.slots[seg_id]


def churn(fake: Any, patched: int, untouched: int, keep: set[str]) -> None:
    """Change everything that was not requested, as animation/other activity would."""
    fake.master_extra = {"ps": 3, "pl": 1}
    other = segment(fake, untouched)
    other["col"] = [[1, 2, 3, 0], [4, 5, 6, 0], [7, 8, 9, 0]]
    other["fx"], other["sx"], other["pal"] = 1, 17, 2
    target = segment(fake, patched)
    for key, value in {
        "col": [[9, 9, 9, 0], [0, 0, 0, 0], [0, 0, 0, 0]],
        "ix": 3,
        "pal": 2,
    }.items():
        if key not in keep:
            target[key] = value


async def run(fake: FakeWLED, tmp_path: Any, tool: str, arguments: dict[str, Any]) -> Any:
    model = SetStateRequest if tool == "wled_set_state" else PatchSegmentsRequest
    async with Resources(config(tmp_path), fake.transport()) as resources:
        operation = {o.name: o for o in build_operations(resources)}[tool]
        payload = model.model_validate({"device_id": "desk", **arguments}).model_dump()
        return await operation.execute(payload)


@pytest.mark.anyio
async def test_patch_verifies_despite_unrelated_transient_changes(tmp_path):
    fake = TransientWLED()
    fake.interference = {0: lambda device: churn(device, patched=2, untouched=0, keep={"sx"})}
    result = await run(fake, tmp_path, "wled_patch_segments", {"segments": [{"id": 2, "speed": 0}]})
    assert result.ok, result.error
    assert (result.application, result.verification) == ("applied", "verified")
    assert fake.posts == [{"seg": [{"id": 2, "sx": 0}]}]
    assert segment(fake, 0)["fx"] == 1 and segment(fake, 2)["ix"] == 3  # churn really happened


@pytest.mark.anyio
async def test_set_state_verifies_despite_unrelated_transient_changes(tmp_path):
    fake = TransientWLED()
    fake.interference = {0: lambda device: churn(device, patched=2, untouched=0, keep=set())}
    result = await run(fake, tmp_path, "wled_set_state", {"on": True, "brightness": 90})
    assert result.ok, result.error
    assert (result.application, result.verification) == ("applied", "verified")
    assert len(fake.posts) == 1
    assert fake.reads >= 2  # the readback saw an advanced timebase


@pytest.mark.anyio
async def test_requested_field_changed_before_readback_is_still_a_mismatch(tmp_path):
    fake = TransientWLED()

    def undo_speed(device: FakeWLED) -> None:
        churn(device, patched=2, untouched=0, keep=set())
        segment(device, 2)["sx"] = 128  # the requested field does not hold

    fake.interference = {0: undo_speed}
    result = await run(fake, tmp_path, "wled_patch_segments", {"segments": [{"id": 2, "speed": 0}]})
    assert not result.ok and result.error.code == "VERIFICATION_MISMATCH"
    assert result.verification == "mismatch"
    assert len(fake.posts) == 1  # reported, never corrected or replayed


@pytest.mark.anyio
async def test_requested_master_brightness_changed_before_readback_is_still_a_mismatch(tmp_path):
    fake = TransientWLED()

    def undo_brightness(device: FakeWLED) -> None:
        churn(device, patched=2, untouched=0, keep=set())
        device.bri = 40

    fake.interference = {0: undo_brightness}
    result = await run(fake, tmp_path, "wled_set_state", {"on": True, "brightness": 90})
    assert not result.ok and result.error.code == "VERIFICATION_MISMATCH"
    assert len(fake.posts) == 1
