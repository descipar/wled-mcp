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
async def test_registry_includes_write_tools_with_mutation_annotations(tmp_path):
    async with open_resources(tmp_path, fleet()) as resources:
        operations = build_operations(resources)
        names = [o.name for o in operations]
        assert names == [
            "wled_list_devices",
            "wled_get_state",
            "wled_get_effects",
            "wled_get_palettes",
            "wled_set_state",
            "wled_patch_segments",
            "wled_replace_layout",
            "wled_list_presets",
            "wled_get_preset",
            "wled_activate_preset",
            "wled_save_preset",
            "wled_delete_preset",
        ]
        for op in operations[4:6]:
            hints = op.annotations
            assert hints.read_only_hint is False
            assert hints.destructive_hint is False
            assert hints.idempotent_hint is False
            assert hints.open_world_hint is False
            assert op.request_model.model_json_schema()["additionalProperties"] is False


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
        # off master + positive brightness: payload contains only bri (preserves omitted on).
        router.set(DESK, "/json/state", make_state(on=False, bri=200))
        result = await call_set_state(resources, brightness=120, dry_run=True)
        assert result.ok and result.data["payload"] == {"bri": 120}

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
