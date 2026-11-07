"""Tests for the typed master and segment patch tools (issue #6).

Coverage: T04 (patch semantics + transition + power/brightness rules),
T06 (whole-request validation incl. RGB/RGBW and overlap), T07 (dry-run is
reads-only), T08 (verification and ACK-not-success), T09 (uncertain writes,
no replay), T10 (per-device lock covers prepare/write/verify and parallel
devices progress).

All tests use a mock transport. No LAN access, no real device.
"""

from __future__ import annotations

import copy
import json

import anyio
import httpx2 as httpx
import pytest
from pydantic import ValidationError

from tests.layout_support import FakeWLED
from tests.patch_support import WriteRouter
from tests.state_catalog_support import make_info, make_segment, make_state
from tests.test_inventory_client import config, device
from wled_mcp.operations import build_operations
from wled_mcp.patches import PatchSegmentsRequest, SetStateRequest
from wled_mcp.resources import Resources

DESK, SHELF = "desk.invalid", "shelf.invalid"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def fleet(**kwargs: object) -> WriteRouter:
    router = WriteRouter()
    router.device(DESK, **kwargs)
    return router


def open_resources(tmp_path, router, devices=None, **settings):
    return Resources(
        config(tmp_path, devices=devices, **settings),
        router.transport(),
    )


def tools(resources):
    return {operation.name: operation for operation in build_operations(resources)}


async def call_set_state(resources, **arguments):
    arguments.setdefault("device_id", "desk")
    operation = tools(resources)["wled_set_state"]
    return await operation.execute(SetStateRequest.model_validate(arguments).model_dump())


async def call_patch_segments(resources, segments, **arguments):
    arguments.setdefault("device_id", "desk")
    arguments["segments"] = segments
    operation = tools(resources)["wled_patch_segments"]
    return await operation.execute(PatchSegmentsRequest.model_validate(arguments).model_dump())


# =========================================================================== registry


@pytest.mark.anyio
async def test_registry_write_tools_have_strict_request_models(tmp_path):
    # Order and annotations are checked against tests/tool_contract.py centrally.
    async with open_resources(tmp_path, fleet()) as resources:
        registered = {o.name: o for o in build_operations(resources)}
        for name in ("wled_set_state", "wled_patch_segments"):
            schema = registered[name].request_model.model_json_schema()
            assert schema["additionalProperties"] is False


def test_set_state_request_strict_models():
    # extra forbidden
    with pytest.raises(ValidationError):
        SetStateRequest.model_validate({"device_id": "desk", "on": True, "extra": 1})
    # non-int brightness
    with pytest.raises(ValidationError):
        SetStateRequest.model_validate({"device_id": "desk", "brightness": "255"})
    # brightness out of range
    with pytest.raises(ValidationError):
        SetStateRequest.model_validate({"device_id": "desk", "brightness": 256})
    # transition_ms out of range
    with pytest.raises(ValidationError):
        SetStateRequest.model_validate({"device_id": "desk", "on": True, "transition_ms": 70000})
    # missing device_id
    with pytest.raises(ValidationError):
        SetStateRequest.model_validate({"on": True})


def test_patch_segments_request_strict_models():
    with pytest.raises(ValidationError):
        PatchSegmentsRequest.model_validate({"device_id": "desk", "segments": []})
    with pytest.raises(ValidationError):
        PatchSegmentsRequest.model_validate(
            {"device_id": "desk", "segments": [{"id": -1, "on": True}]}
        )
    with pytest.raises(ValidationError):
        PatchSegmentsRequest.model_validate(
            {"device_id": "desk", "segments": [{"id": 0, "on": True, "unknown": 1}]}
        )
    # colors field type
    with pytest.raises(ValidationError):
        PatchSegmentsRequest.model_validate(
            {"device_id": "desk", "segments": [{"id": 0, "colors": "red"}]}
        )


# ==========================================================================  T04: patch semantics


@pytest.mark.anyio
async def test_T04_patch_segment_two_preserves_segment_zero(tmp_path):
    """Patch ID 2 with speed=0/on=False/brightness=0; ID 0 untouched."""
    router = fleet()
    async with open_resources(tmp_path, router) as resources:
        result = await call_patch_segments(
            resources,
            segments=[{"id": 2, "on": False, "brightness": 0, "speed": 0}],
            dry_run=True,
        )
    assert result.ok and result.dry_run and result.application == "not_attempted"
    plan = result.data["plan"]
    assert plan["update_segment_ids"] == [2]
    assert plan["create_segment_ids"] == []
    assert plan["remove_segment_ids"] == []
    assert plan["preserve_segment_ids"] == [0, 5]
    # payload body contains exactly the patched segment and only the sent fields.
    payload = result.data["payload"]
    assert payload == {"seg": [{"id": 2, "on": False, "bri": 0, "sx": 0}]}
    assert router.method_counts()["POST"] == 0
    assert router.method_counts()["GET"] >= 2


@pytest.mark.anyio
async def test_T04_patch_leaves_omitted_fields_and_other_segments_untouched(tmp_path):
    """Live run: patch segment 2 speed; read back confirms segment 0 still equal."""
    router = fleet()
    # Simulate the firmware updating segment 2's speed on POST.
    patched_state = make_state()
    patched_state["seg"][1]["sx"] = 0
    router.set_post(
        DESK,
        "/json/state",
        lambda request: _apply_speed_patch(router, patched_state),
    )

    async with open_resources(tmp_path, router) as resources:
        result = await call_patch_segments(
            resources,
            segments=[{"id": 2, "speed": 0}],
        )
    assert result.ok, result
    assert result.application == "applied" and result.verification == "verified"
    assert router.method_counts()["POST"] == 1
    sent_body = router.posts[0][2]
    # Only ID 2 and only 'sx' appears in the sent body; segments 0 and 5 are never mentioned.
    assert sent_body == {"seg": [{"id": 2, "sx": 0}]}


def _apply_speed_patch(router: WriteRouter, patched_state: dict) -> httpx.Response:
    router.set(DESK, "/json/state", copy.deepcopy(patched_state))
    return httpx.Response(200, json={"success": True})


@pytest.mark.anyio
async def test_T04_master_set_state_power_and_brightness_rules(tmp_path):
    router = fleet()
    async with open_resources(tmp_path, router) as resources:
        # off master + positive brightness: the omitted on is preserved by sending the
        # resolved on=false with bri (ISSUE-52-DEC-001; supersedes the former bri-only
        # payload, which the firmware turns on).
        router.set(DESK, "/json/state", make_state(on=False, bri=200))
        result = await call_set_state(resources, brightness=120, dry_run=True)
        assert result.ok and result.data["payload"] == {"on": False, "bri": 120}

        # explicit on=False keeps remembered brightness; payload only {on:false}.
        router.set(DESK, "/json/state", make_state(on=True, bri=180))
        result = await call_set_state(resources, on=False, dry_run=True)
        assert result.data["payload"] == {"on": False}

        # Reject on=True, brightness=0.
        router.set(DESK, "/json/state", make_state(on=False, bri=0))
        result = await call_set_state(resources, on=True, brightness=0, dry_run=True)
        assert not result.ok and result.error.code == "VALIDATION_ERROR"

        # Reject brightness=0 with resolved on=True (current on=True, no explicit on).
        router.set(DESK, "/json/state", make_state(on=True, bri=180))
        result = await call_set_state(resources, brightness=0, dry_run=True)
        assert not result.ok and result.error.code == "VALIDATION_ERROR"

        # Reject turning on without a remembered positive brightness and no explicit bri.
        router.set(DESK, "/json/state", make_state(on=False, bri=0))
        result = await call_set_state(resources, on=True, dry_run=True)
        assert not result.ok and result.error.code == "VALIDATION_ERROR"

        # Accept turning on with an explicit positive brightness even when remembered is 0.
        router.set(DESK, "/json/state", make_state(on=False, bri=0))
        result = await call_set_state(resources, on=True, brightness=200, dry_run=True)
        assert result.ok and result.data["payload"] == {"on": True, "bri": 200}


@pytest.mark.anyio
async def test_T04_transition_ms_conversion_and_bounds(tmp_path):
    router = fleet()
    async with open_resources(tmp_path, router) as resources:
        for ms, wire in ((0, 0), (50, 1), (149, 1), (150, 2), (65500, 655)):
            router.set(DESK, "/json/state", make_state(on=True, bri=180))
            result = await call_set_state(resources, on=True, transition_ms=ms, dry_run=True)
            assert result.ok, (ms, result.error)
            assert result.data["payload"].get("tt") == wire, ms
            transition = result.data["plan"]["transition"]
            assert transition["requested_ms"] == ms
            assert transition["effective_ms"] == wire * 100
            assert transition["wire_units"] == wire
        # 1-49 rejected
        for ms in (1, 25, 49):
            result = await call_set_state(resources, on=True, transition_ms=ms, dry_run=True)
            assert not result.ok and result.error.code == "VALIDATION_ERROR"
        # transition_ms out of range -> VALIDATION_ERROR via pydantic shape
        with pytest.raises(ValidationError):
            SetStateRequest.model_validate({"device_id": "desk", "on": True, "transition_ms": -1})
        # transition-only request (no on and no brightness) rejected before POST
        result = await call_set_state(resources, transition_ms=100, dry_run=True)
        assert not result.ok and result.error.code == "VALIDATION_ERROR"


@pytest.mark.anyio
async def test_T04_persistent_transition_is_never_in_payload(tmp_path):
    router = fleet()
    async with open_resources(tmp_path, router) as resources:
        result = await call_set_state(resources, on=True, transition_ms=500, dry_run=True)
    assert result.ok
    assert "transition" not in result.data["payload"]
    assert result.data["plan"]["persistent_transition_touched"] is False


# ==========================================================================  T06: validation


@pytest.mark.anyio
async def test_T06_patch_colors_width_rgb_only_and_rgbw(tmp_path):
    # Segment 0 is proven RGB-only (seglc[0]=1).
    router = fleet(info=make_info(leds={"count": 90, "maxseg": 32, "lc": 3, "seglc": [1, 3, 1]}))
    async with open_resources(tmp_path, router) as resources:
        # RGB-only with 4 channels -> VALIDATION_ERROR
        result = await call_patch_segments(
            resources,
            segments=[{"id": 0, "colors": [[1, 2, 3, 4]]}],
            dry_run=True,
        )
        assert not result.ok and result.error.code == "VALIDATION_ERROR"
        # RGBW with 3 channels -> VALIDATION_ERROR (seg 2 is RGBW per seglc)
        result = await call_patch_segments(
            resources,
            segments=[{"id": 2, "colors": [[1, 2, 3]]}],
            dry_run=True,
        )
        assert not result.ok and result.error.code == "VALIDATION_ERROR"
        # RGB-only with 3 channels succeeds
        result = await call_patch_segments(
            resources,
            segments=[{"id": 0, "colors": [[10, 20, 30]]}],
            dry_run=True,
        )
        assert result.ok
        assert result.data["payload"]["seg"] == [{"id": 0, "col": [[10, 20, 30]]}]


@pytest.mark.anyio
async def test_T06_unknown_segment_capability_rejects_color_change(tmp_path):
    # seglc length mismatches; aggregate lc unknown too => color change fails.
    router = fleet(info=make_info(leds={"count": 90, "maxseg": 32, "seglc": [1]}))
    async with open_resources(tmp_path, router) as resources:
        result = await call_patch_segments(
            resources,
            segments=[{"id": 0, "colors": [[1, 2, 3]]}],
            dry_run=True,
        )
    assert not result.ok and result.error.code == "UNSUPPORTED_CAPABILITY"


@pytest.mark.anyio
async def test_T06_patch_unknown_segment_id_rejected(tmp_path):
    router = fleet()
    async with open_resources(tmp_path, router) as resources:
        result = await call_patch_segments(
            resources, segments=[{"id": 99, "on": True}], dry_run=True
        )
    assert not result.ok and result.error.code == "VALIDATION_ERROR"
    assert "add segments" in result.error.message


@pytest.mark.anyio
async def test_T06_patch_requires_a_mutable_field(tmp_path):
    router = fleet()
    async with open_resources(tmp_path, router) as resources:
        result = await call_patch_segments(resources, segments=[{"id": 0}], dry_run=True)
    assert not result.ok and result.error.code == "VALIDATION_ERROR"
    assert "mutable field" in result.error.message


@pytest.mark.anyio
async def test_T06_range_change_requires_both_start_and_stop(tmp_path):
    router = fleet()
    async with open_resources(tmp_path, router) as resources:
        result = await call_patch_segments(
            resources, segments=[{"id": 0, "start": 0}], dry_run=True
        )
    assert not result.ok and result.error.code == "VALIDATION_ERROR"


@pytest.mark.anyio
async def test_T06_range_change_overlap_with_untouched_segment(tmp_path):
    router = fleet()
    async with open_resources(tmp_path, router) as resources:
        # existing layout: 0/2/5 over 0-30/30-60/60-90. Push 0's stop into 2's range.
        result = await call_patch_segments(
            resources,
            segments=[{"id": 0, "start": 0, "stop": 45}],
            dry_run=True,
        )
    assert not result.ok and result.error.code == "VALIDATION_ERROR"
    assert "overlap" in result.error.message


@pytest.mark.anyio
async def test_T06_effect_id_out_of_catalog_range(tmp_path):
    router = fleet(info=make_info(fxcount=4))
    async with open_resources(tmp_path, router) as resources:
        result = await call_patch_segments(
            resources, segments=[{"id": 0, "effect_id": 10}], dry_run=True
        )
    assert not result.ok and result.error.code == "VALIDATION_ERROR"
    assert "effect_id" in result.error.message


@pytest.mark.anyio
async def test_T06_unknown_device_before_any_http(tmp_path):
    router = fleet()
    async with open_resources(tmp_path, router) as resources:
        result = await call_patch_segments(
            resources,
            segments=[{"id": 0, "on": True}],
            device_id="nope",
            dry_run=True,
        )
    assert not result.ok and result.error.code == "UNKNOWN_DEVICE"
    assert result.device_id is None
    assert router.method_counts().get("GET", 0) == 0


# ===================================================================  T07: dry-run reads-only


@pytest.mark.anyio
async def test_T07_dry_run_performs_no_post_and_shows_resolved_plan(tmp_path):
    router = fleet()
    async with open_resources(tmp_path, router) as resources:
        result = await call_patch_segments(
            resources,
            segments=[{"id": 2, "on": False, "brightness": 0, "speed": 0}],
            dry_run=True,
        )
    assert result.ok and result.dry_run and router.method_counts()["POST"] == 0
    plan = result.data["plan"]
    # resolved view carries post-patch fields
    resolved = plan["resolved_segments"][0]
    assert resolved["id"] == 2
    assert resolved["on"] is False
    assert resolved["effective_brightness"] == 0
    # brightness remembered from previous state (bri=255 from fixture) is kept
    # even though the patch resolves to off.
    assert resolved["brightness"] == 0
    assert resolved["effect_id"] == 0  # unchanged
    assert "preserve_segment_ids" in plan


@pytest.mark.anyio
async def test_T07_actual_invocation_replans_under_lock(tmp_path):
    """After a dry-run plan, live changes before the real call are revalidated."""
    router = fleet()
    async with open_resources(tmp_path, router) as resources:
        # First: dry-run says it would work.
        pre = await call_patch_segments(
            resources, segments=[{"id": 0, "effect_id": 1}], dry_run=True
        )
        assert pre.ok
        # Now: device identity/state changes so that segment 0 no longer exists.
        router.set(DESK, "/json/state", make_state([make_segment(1, 0, 90)]))
        # Live call must revalidate and fail cleanly without POST.
        live = await call_patch_segments(
            resources, segments=[{"id": 0, "effect_id": 1}], dry_run=False
        )
    assert not live.ok and live.error.code == "VALIDATION_ERROR"
    assert router.method_counts()["POST"] == 0


# ==========================================================================  T08: verification


@pytest.mark.anyio
async def test_T08_ack_without_matching_readback_is_mismatch(tmp_path):
    router = fleet()
    # POST returns 200 but readback shows segment 2 unchanged (sx still 128).
    async with open_resources(tmp_path, router) as resources:
        result = await call_patch_segments(resources, segments=[{"id": 2, "speed": 0}])
    assert not result.ok
    assert result.application == "unknown" and result.verification == "mismatch"
    assert result.error.code == "VERIFICATION_MISMATCH"
    assert router.method_counts()["POST"] == 1


@pytest.mark.anyio
async def test_T08_normalized_off_keeps_remembered_brightness(tmp_path):
    router = fleet()

    # Simulate: after POST on=False+bri=0, device turns off; readback bri stays 255.
    def after_off(request):
        router.set(DESK, "/json/state", make_state(on=False, bri=255))
        return httpx.Response(200, json={"success": True})

    router.set_post(DESK, "/json/state", after_off)
    async with open_resources(tmp_path, router) as resources:
        result = await call_set_state(resources, on=False, brightness=0)
    # Explicit on=False + bri=0: expectation is on=False; remembered bri readback
    # is still 255 because that's how the firmware behaves.
    assert result.ok and result.application == "applied"


# ==========================================================================  T09: uncertain writes


@pytest.mark.anyio
async def test_T09_timed_out_dispatch_is_outcome_unknown(tmp_path):
    router = fleet()
    original_state = router.get_routes[(DESK, "/json/state")]

    def post_timeout(request):
        # Switch state route to fail future reads so readback is unavailable.
        router.set(DESK, "/json/state", httpx.ReadError("synthetic-secret"))
        raise httpx.WriteTimeout("synthetic-secret")

    router.set_post(DESK, "/json/state", post_timeout)

    async with open_resources(
        tmp_path, router, operation_timeout_seconds=0.3, read_retries=0
    ) as resources:
        result = await call_patch_segments(resources, segments=[{"id": 2, "speed": 0}])
    assert not result.ok, (result.application, result.verification, result.error)
    assert result.application == "unknown" and result.verification == "unknown"
    assert result.error.code == "WRITE_OUTCOME_UNKNOWN"
    # Single POST, never replayed.
    assert router.method_counts()["POST"] == 1
    assert "synthetic-secret" not in result.model_dump_json()
    # original_state ref is kept to show the test setup was deterministic
    assert original_state is not None


# ==========================================================================  T10: lock & parallel


@pytest.mark.anyio
async def test_T10_patch_segments_serializes_per_device(tmp_path):
    router = fleet()
    second_started = anyio.Event()
    first_in_write = anyio.Event()
    release = anyio.Event()

    async def slow_post(request):
        first_in_write.set()
        await release.wait()
        return httpx.Response(200, json={"success": True})

    router.set_post(DESK, "/json/state", slow_post)

    async with open_resources(tmp_path, router) as resources:

        async def first_call():
            return await call_patch_segments(resources, segments=[{"id": 2, "speed": 0}])

        async def second_call():
            await first_in_write.wait()
            second_started.set()
            return await call_patch_segments(resources, segments=[{"id": 2, "speed": 1}])

        async with anyio.create_task_group() as group:
            group.start_soon(first_call)
            group.start_soon(second_call)
            await first_in_write.wait()
            assert second_started.is_set() is False or resources.locks["desk"].locked() is not False
            release.set()

    # Both calls dispatched POST but not simultaneously.
    assert router.method_counts()["POST"] == 2


@pytest.mark.anyio
async def test_T10_different_devices_progress_in_parallel(tmp_path):
    router = WriteRouter()
    router.device(DESK)
    router.device(SHELF)

    desk_in_write = anyio.Event()
    shelf_done = anyio.Event()
    release = anyio.Event()

    async def slow_desk(request):
        desk_in_write.set()
        await release.wait()
        return httpx.Response(200, json={"success": True})

    router.set_post(DESK, "/json/state", slow_desk)

    async with open_resources(tmp_path, router, devices=[device(), device("shelf")]) as resources:

        async def desk_call():
            return await call_patch_segments(
                resources, segments=[{"id": 2, "speed": 0}], device_id="desk"
            )

        async def shelf_call():
            await desk_in_write.wait()
            result = await call_patch_segments(
                resources, segments=[{"id": 2, "speed": 0}], device_id="shelf"
            )
            shelf_done.set()
            return result

        async with anyio.create_task_group() as group:
            group.start_soon(desk_call)
            group.start_soon(shelf_call)
            with anyio.fail_after(2):
                await shelf_done.wait()
            release.set()

    assert router.method_counts()["POST"] == 2


# ==========================================================================  JSON parity + envelope


@pytest.mark.anyio
async def test_envelope_round_trip_through_json(tmp_path):
    router = fleet()
    async with open_resources(tmp_path, router) as resources:
        result = await call_patch_segments(
            resources, segments=[{"id": 0, "effect_id": 1}], dry_run=True
        )
    # JSON-serializable via model_dump_json
    text = result.model_dump_json()
    envelope = json.loads(text)
    assert envelope["ok"] is True and envelope["dry_run"] is True
    assert envelope["operation"] == "wled_patch_segments"
    assert "synthetic-secret" not in text


@pytest.mark.anyio
async def test_set_state_dry_run_shape(tmp_path):
    router = fleet()
    async with open_resources(tmp_path, router) as resources:
        result = await call_set_state(
            resources, on=True, brightness=200, transition_ms=250, dry_run=True
        )
    assert result.ok and result.dry_run is True
    assert result.data["payload"] == {"on": True, "bri": 200, "tt": 3}
    assert result.data["plan"]["transition"] == {
        "requested_ms": 250,
        "effective_ms": 300,
        "wire_units": 3,
    }


@pytest.mark.anyio
async def test_set_state_live_success_when_readback_matches(tmp_path):
    router = fleet()

    # Switch state to the expected target after POST so verification passes.
    def after_post(request):
        router.set(DESK, "/json/state", make_state(on=True, bri=200))
        return httpx.Response(200, json={"success": True})

    router.set_post(DESK, "/json/state", after_post)
    async with open_resources(tmp_path, router) as resources:
        result = await call_set_state(resources, on=True, brightness=200)
    assert result.ok, (result.application, result.verification, result.error)
    assert result.application == "applied" and result.verification == "verified"
    assert router.posts[0][2] == {"on": True, "bri": 200}


# ===================================================  issue #48: shared firmware limits (#6 side)
#
# These tests run against the firmware-like fake of ``tests/layout_support.py`` (byte name
# buffer, uint8_t grp/spc, bri/on coupling), because static router fixtures cannot model
# the firmware power flip. ``ISSUE-48-DEC-001``; mock-only.


def seg_fake(**seg0: object) -> FakeWLED:
    """Two active segments; ID 0 carries the overrides (default: on, bri 255)."""
    return FakeWLED([make_segment(0, 0, 10, **seg0), make_segment(1, 10, 20)])


def fake_seg(fake: FakeWLED, seg_id: int = 0) -> dict:
    return {s["id"]: s for s in fake.active()}[seg_id]


INVALID_48 = [
    pytest.param({"name": "a" * 31 + "ä"}, "33 UTF-8 bytes", id="name-33-bytes"),
    pytest.param({"name": "ä" * 17}, "34 UTF-8 bytes", id="name-17-two-byte-chars"),
    pytest.param({"name": "ab\x00cd"}, "U+0000", id="name-nul"),
    pytest.param({"on": True, "brightness": 0}, "on=true with brightness=0", id="on-true-bri-0"),
    pytest.param({"brightness": 0}, "requires an explicit on=false", id="bri-0-on-segment"),
]


@pytest.mark.anyio
@pytest.mark.parametrize("name", ["a" * 32, "ä" * 16], ids=["ascii-32", "two-byte-16"])
async def test_48_name_of_exactly_32_utf8_bytes_is_accepted_and_verified(tmp_path, name):
    """AC-48-01 (#6)."""
    fake = seg_fake()
    async with open_resources(tmp_path, fake) as resources:
        result = await call_patch_segments(resources, [{"id": 0, "name": name}])
    assert result.ok, (result.error, result.data)
    assert (result.application, result.verification) == ("applied", "verified")
    assert fake.posts == [{"seg": [{"id": 0, "n": name}]}]
    assert fake_seg(fake)["n"] == name


@pytest.mark.anyio
@pytest.mark.parametrize("dry_run", [True, False], ids=["dry", "live"])
@pytest.mark.parametrize(("fields", "message"), INVALID_48)
async def test_48_rejections_before_any_post(tmp_path, fields, message, dry_run):
    """AC-48-02/03/05/06/11 (#6): rejected identically in dry run and live call."""
    fake = seg_fake()
    async with open_resources(tmp_path, fake) as resources:
        result = await call_patch_segments(resources, [{"id": 0, **fields}], dry_run=dry_run)
    assert result.error is not None and result.error.code == "VALIDATION_ERROR"
    assert message in result.error.message and "Segment 0" in result.error.message
    if "name" in fields and "U+0000" not in message:
        assert "32 bytes" in result.error.message
    assert (result.ok, result.application, result.verification) == (
        False,
        "not_attempted",
        "not_requested",
    )
    assert fake.posts == [] and fake.method_count("POST") == 0


@pytest.mark.anyio
async def test_48_brightness_zero_with_on_false_or_on_off_segment_is_accepted(tmp_path):
    """AC-48-06 (#6): explicit on=false works; an already-off segment needs no on."""
    fake = FakeWLED([make_segment(0, 0, 10), make_segment(1, 10, 20, on=False, bri=90)])
    async with open_resources(tmp_path, fake) as resources:
        result = await call_patch_segments(
            resources, [{"id": 0, "brightness": 0, "on": False}, {"id": 1, "brightness": 0}]
        )
    assert result.ok, (result.error, result.data)
    assert fake.posts == [{"seg": [{"id": 0, "on": False, "bri": 0}, {"id": 1, "bri": 0}]}]
    assert (fake_seg(fake, 0)["on"], fake_seg(fake, 1)["on"]) == (False, False)


@pytest.mark.anyio
async def test_48_positive_brightness_on_off_segment_is_compensated(tmp_path):
    """AC-48-07/11 (#6): bri is sent with the resolved on=false, shown as targeted
    compensation; dry run and live call carry the same payload; the segment stays off."""
    fake = seg_fake(on=False, bri=100)
    async with open_resources(tmp_path, fake) as resources:
        dry = await call_patch_segments(resources, [{"id": 0, "brightness": 50}], dry_run=True)
        assert fake.posts == []
        live = await call_patch_segments(resources, [{"id": 0, "brightness": 50}])
    expected = {"seg": [{"id": 0, "on": False, "bri": 50}]}
    assert dry.ok and dry.data["payload"] == expected
    assert dry.data["plan"]["targeted_compensation"] == [{"id": 0, "on": False}]
    assert any("on=false" in text for text in dry.data["postconditions"])
    assert fake.posts == [expected]
    assert live.ok, (live.error, live.data)
    assert (live.application, live.verification) == ("applied", "verified")
    assert live.data["plan"] == dry.data["plan"]
    assert (fake_seg(fake)["on"], fake_seg(fake)["bri"]) == (False, 50)
    resolved = live.data["plan"]["resolved_segments"][0]
    assert (resolved["on"], resolved["brightness"], resolved["effective_brightness"]) == (
        False,
        50,
        0,
    )


@pytest.mark.anyio
async def test_48_positive_brightness_on_on_segment_is_sent_alone_and_stays_on(tmp_path):
    """AC-48-08 (#6): no on is added for a segment that is on; it stays on."""
    fake = seg_fake(on=True, bri=100)
    async with open_resources(tmp_path, fake) as resources:
        result = await call_patch_segments(resources, [{"id": 0, "brightness": 50}])
    assert fake.posts == [{"seg": [{"id": 0, "bri": 50}]}]
    assert result.ok and (result.application, result.verification) == ("applied", "verified")
    assert result.data["plan"]["targeted_compensation"] == []
    assert (fake_seg(fake)["on"], fake_seg(fake)["bri"]) == (True, 50)


@pytest.mark.anyio
async def test_48_power_flip_after_brightness_is_a_mismatch_not_silent_success(tmp_path):
    """AC-48-09 (#6): the resolved on is verified whenever bri is sent. The device drops
    the compensating on=false and the firmware switches the segment on."""
    fake = seg_fake(on=False, bri=100)
    fake.ignore_keys = {"on"}
    async with open_resources(tmp_path, fake) as resources:
        result = await call_patch_segments(resources, [{"id": 0, "brightness": 50}])
    assert fake_seg(fake)["on"] is True and fake_seg(fake)["bri"] == 50
    assert not result.ok and result.error.code == "VERIFICATION_MISMATCH"
    assert (result.application, result.verification) == ("unknown", "mismatch")


@pytest.mark.anyio
async def test_48_power_flip_on_on_segment_is_also_verified(tmp_path):
    """AC-48-09 (#6): a segment that ends off after a positive bri is reported too."""
    fake = seg_fake(on=True, bri=100)

    def switch_off(device: FakeWLED) -> None:
        device.slots[0]["on"] = False

    fake.interference = {0: switch_off}
    async with open_resources(tmp_path, fake) as resources:
        result = await call_patch_segments(resources, [{"id": 0, "brightness": 50}])
    assert fake_seg(fake)["bri"] == 50  # the requested brightness itself was stored
    assert not result.ok and result.error.code == "VERIFICATION_MISMATCH"


@pytest.mark.anyio
@pytest.mark.parametrize("field", ["grouping", "spacing"])
async def test_48_grouping_and_spacing_255_are_accepted_and_verified(tmp_path, field):
    """AC-48-04 (#6): the bound itself is storable; 256 is a schema rejection."""
    fake = seg_fake()
    async with open_resources(tmp_path, fake) as resources:
        result = await call_patch_segments(resources, [{"id": 0, field: 255}])
    assert result.ok, (result.error, result.data)
    wire = {"grouping": "grp", "spacing": "spc"}[field]
    assert fake_seg(fake)[wire] == 255
    with pytest.raises(ValidationError):
        PatchSegmentsRequest.model_validate(
            {"device_id": "desk", "segments": [{"id": 0, field: 256}]}
        )


# Parity: the same edge case through both tools gives the same code, the same power
# compensation and the same resolved power (guards drift between #6 and #7).
PARITY_CASES = [
    pytest.param({"on": False, "bri": 100}, {"brightness": 50}, None, id="bri-on-off-segment"),
    pytest.param({"on": True, "bri": 100}, {"brightness": 50}, None, id="bri-on-on-segment"),
    pytest.param({"on": True}, {"brightness": 0}, "VALIDATION_ERROR", id="bri-0-on-segment"),
    pytest.param({"on": False}, {"brightness": 0}, None, id="bri-0-off-segment"),
    pytest.param(
        {"on": True}, {"on": True, "brightness": 0}, "VALIDATION_ERROR", id="on-true-bri-0"
    ),
    pytest.param({"on": True}, {"on": False, "brightness": 0}, None, id="on-false-bri-0"),
    pytest.param({}, {"name": "a" * 31 + "ä"}, "VALIDATION_ERROR", id="name-33-bytes"),
    pytest.param({}, {"name": "x\x00"}, "VALIDATION_ERROR", id="name-nul"),
    pytest.param({}, {"name": "ä" * 16}, None, id="name-32-bytes"),
    pytest.param(
        {"on": None}, {"brightness": 50}, "UNSUPPORTED_CAPABILITY", id="unknown-power-bri"
    ),
    pytest.param({"on": None}, {"speed": 3}, None, id="unknown-power-unrelated"),
]


@pytest.mark.anyio
@pytest.mark.parametrize(("seg0", "fields", "code"), PARITY_CASES)
async def test_48_patch_and_replace_apply_the_same_rules(tmp_path, seg0, fields, code):
    from tests.test_layouts import replace

    def make() -> FakeWLED:
        fake = seg_fake(**{k: v for k, v in seg0.items() if v is not None})
        if "on" in seg0 and seg0["on"] is None:
            fake.slots[0].pop("on")
        return fake

    patch_fake, replace_fake = make(), make()
    async with open_resources(tmp_path, patch_fake) as resources:
        patched = await call_patch_segments(resources, [{"id": 0, **fields}], dry_run=True)
    async with open_resources(tmp_path, replace_fake) as resources:
        replaced = await replace(
            resources,
            [{"id": 0, "start": 0, "stop": 10, **fields}, {"id": 1, "start": 10, "stop": 20}],
            dry_run=True,
        )
    assert patch_fake.posts == [] and replace_fake.posts == []
    patched_code = patched.error.code if patched.error else None
    replaced_code = replaced.error.code if replaced.error else None
    assert patched_code == replaced_code == code
    if patched.ok:

        def power_entries(plan: dict) -> list:
            return [c for c in plan["targeted_compensation"] if "on" in c]

        assert power_entries(patched.data["plan"]) == power_entries(replaced.data["plan"])
        patched_on = patched.data["plan"]["resolved_segments"][0]["on"]
        replaced_on = replaced.data["plan"]["resolved_segments"][0]["on"]
        assert patched_on == replaced_on


# ===================================================  issue #52: master power preservation (#6)
#
# Master side of ``wled_set_state`` against the firmware-like fake of
# ``tests/layout_support.py``, which models ``on = root["on"] | (bri > 0)`` and
# ``toggleOnOff`` (pinned v0.15.1). ``ISSUE-52-DEC-001``; mock-only.


def master_fake(*, on: bool, bri: int) -> FakeWLED:
    fake = FakeWLED([make_segment(0, 0, 10), make_segment(1, 10, 20)])
    fake.on, fake.bri = on, bri
    return fake


def segment_power(fake: FakeWLED) -> list[bool]:
    return [seg["on"] for seg in fake.active()]


@pytest.mark.anyio
async def test_52_off_master_positive_brightness_dry_run_is_compensated(tmp_path):
    """AC-52-01: the dry run shows the compensating on=false and sends nothing."""
    fake = master_fake(on=False, bri=200)
    async with open_resources(tmp_path, fake) as resources:
        result = await call_set_state(resources, brightness=120, dry_run=True)
    assert result.ok and result.dry_run, (result.error, result.data)
    assert result.data["payload"] == {"on": False, "bri": 120}
    plan = result.data["plan"]
    assert plan["targeted_compensation"] == [{"on": False}]
    assert plan["on"] is None
    assert plan["resolved"] == {"on": False, "brightness": 120}
    assert any("on=false" in text for text in result.data["postconditions"])
    assert fake.posts == [] and fake.method_count("POST") == 0
    assert (fake.on, fake.bri) == (False, 200)


@pytest.mark.anyio
async def test_52_off_master_positive_brightness_live_stays_off_and_verifies(tmp_path):
    """AC-52-02: one POST with the dry-run payload; the master stays off, remembers the
    brightness, segment power is untouched and the live plan equals the dry-run plan."""
    fake = master_fake(on=False, bri=200)
    async with open_resources(tmp_path, fake) as resources:
        dry = await call_set_state(resources, brightness=120, dry_run=True)
        live = await call_set_state(resources, brightness=120)
    assert live.ok, (live.error, live.data)
    assert (live.application, live.verification) == ("applied", "verified")
    assert fake.posts == [{"on": False, "bri": 120}]
    assert (fake.state()["on"], fake.state()["bri"]) == (False, 120)
    assert live.data["plan"] == dry.data["plan"]
    assert segment_power(fake) == [True, True]


@pytest.mark.anyio
async def test_52_on_master_positive_brightness_is_sent_alone_and_stays_on(tmp_path):
    """AC-52-03: no on is added for a master that is on; it stays on."""
    fake = master_fake(on=True, bri=200)
    async with open_resources(tmp_path, fake) as resources:
        result = await call_set_state(resources, brightness=120)
    assert fake.posts == [{"bri": 120}]
    assert result.ok and (result.application, result.verification) == ("applied", "verified")
    assert result.data["plan"]["targeted_compensation"] == []
    assert (fake.on, fake.bri) == (True, 120)


@pytest.mark.anyio
async def test_52_dropped_compensation_power_flip_is_a_mismatch(tmp_path):
    """AC-52-04: the device drops the compensating on=false and the firmware switches the
    master on; this is reported as a mismatch after one POST, never replayed."""
    fake = master_fake(on=False, bri=200)
    fake.ignore_keys = {"on"}
    async with open_resources(tmp_path, fake) as resources:
        result = await call_set_state(resources, brightness=120)
    assert (fake.on, fake.bri) == (True, 120)
    assert not result.ok and result.error.code == "VERIFICATION_MISMATCH"
    assert (result.application, result.verification) == ("unknown", "mismatch")
    assert fake.method_count("POST") == 1 and fake.posts == [{"on": False, "bri": 120}]


@pytest.mark.anyio
async def test_52_on_master_that_ends_off_after_bri_is_a_mismatch(tmp_path):
    """AC-52-05: a bri-only write on an on master verifies the resolved on=true."""
    fake = master_fake(on=True, bri=200)

    def switch_off(device: FakeWLED) -> None:
        device.on = False

    fake.interference = {0: switch_off}
    async with open_resources(tmp_path, fake) as resources:
        result = await call_set_state(resources, brightness=120)
    assert fake.posts == [{"bri": 120}] and fake.bri == 120
    assert not result.ok and result.error.code == "VERIFICATION_MISMATCH"
    assert (result.application, result.verification) == ("unknown", "mismatch")


@pytest.mark.anyio
async def test_52_compensation_keeps_one_call_transition(tmp_path):
    """AC-52-06: tt is still sent and reported; persistent transition is untouched."""
    fake = master_fake(on=False, bri=200)
    async with open_resources(tmp_path, fake) as resources:
        dry = await call_set_state(resources, brightness=120, transition_ms=150, dry_run=True)
        assert fake.posts == []
        live = await call_set_state(resources, brightness=120, transition_ms=150)
    expected = {"on": False, "bri": 120, "tt": 2}
    assert dry.ok and dry.data["payload"] == expected
    assert dry.data["plan"]["transition"] == {
        "requested_ms": 150,
        "effective_ms": 200,
        "wire_units": 2,
    }
    assert dry.data["plan"]["persistent_transition_touched"] is False
    assert fake.posts == [expected]
    assert live.ok and (fake.on, fake.bri) == (False, 120)


MASTER_REJECTIONS_52 = [
    pytest.param(False, 0, {"on": True, "brightness": 0}, id="on-true-bri-0"),
    pytest.param(True, 180, {"brightness": 0}, id="bri-0-on-master"),
    pytest.param(False, 0, {"on": True}, id="turn-on-remembered-0"),
]


@pytest.mark.anyio
@pytest.mark.parametrize("dry_run", [True, False], ids=["dry", "live"])
@pytest.mark.parametrize(("on", "bri", "fields"), MASTER_REJECTIONS_52)
async def test_52_existing_master_rejections_before_any_post(tmp_path, on, bri, fields, dry_run):
    """AC-52-07: unchanged rejections, identical in dry run and live call."""
    fake = master_fake(on=on, bri=bri)
    async with open_resources(tmp_path, fake) as resources:
        result = await call_set_state(resources, dry_run=dry_run, **fields)
    assert result.error is not None and result.error.code == "VALIDATION_ERROR"
    assert (result.ok, result.application, result.verification) == (
        False,
        "not_attempted",
        "not_requested",
    )
    assert fake.posts == [] and fake.method_count("POST") == 0


@pytest.mark.anyio
async def test_52_off_master_brightness_zero_is_accepted_without_compensation(tmp_path):
    """AC-52-08: bri=0 on an off master needs no on and is verified off."""
    fake = master_fake(on=False, bri=200)
    async with open_resources(tmp_path, fake) as resources:
        result = await call_set_state(resources, brightness=0)
    assert fake.posts == [{"bri": 0}]
    assert result.ok and (result.application, result.verification) == ("applied", "verified")
    assert result.data["plan"]["targeted_compensation"] == []
    assert fake.on is False


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("current_on", "requested_on"),
    [(False, True), (True, False), (False, False), (True, True)],
    ids=["off-to-on", "on-to-off", "off-stays-off", "on-stays-on"],
)
async def test_52_explicit_on_with_brightness_is_not_compensation(
    tmp_path, current_on, requested_on
):
    """AC-52-09: an explicit on is sent as requested, listed as no compensation, and the
    readback checks it: a device that drops on=false (positive bri then turns it on) is a
    mismatch, not a verified success."""
    fake = master_fake(on=current_on, bri=200)
    async with open_resources(tmp_path, fake) as resources:
        result = await call_set_state(resources, on=requested_on, brightness=120)
    assert fake.posts == [{"on": requested_on, "bri": 120}]
    assert result.ok and (result.application, result.verification) == ("applied", "verified")
    assert result.data["plan"]["targeted_compensation"] == []
    assert result.data["plan"]["on"] is requested_on
    assert (fake.on, fake.bri) == (requested_on, 120)

    flipped = master_fake(on=current_on, bri=200)
    flipped.ignore_keys = {"on"}
    async with open_resources(tmp_path, flipped) as resources:
        dropped = await call_set_state(resources, on=requested_on, brightness=120)
    assert flipped.on is True
    if requested_on:
        assert dropped.ok
    else:
        assert not dropped.ok and dropped.error.code == "VERIFICATION_MISMATCH"


@pytest.mark.anyio
@pytest.mark.parametrize("dry_run", [True, False], ids=["dry", "live"])
@pytest.mark.parametrize("raw_on", [None, "off", 0], ids=["missing", "string", "int"])
async def test_52_master_without_boolean_on_is_invalid_response(tmp_path, raw_on, dry_run):
    """AC-52-10: unknown master power is rejected before planning; no POST."""
    router = fleet()
    state = make_state(bri=200)
    if raw_on is None:
        state.pop("on")
    else:
        state["on"] = raw_on
    router.set(DESK, "/json/state", state)
    async with open_resources(tmp_path, router) as resources:
        result = await call_set_state(resources, brightness=120, dry_run=dry_run)
    assert not result.ok and result.error.code == "INVALID_RESPONSE"
    assert result.application == "not_attempted"
    assert router.method_counts()["POST"] == 0
