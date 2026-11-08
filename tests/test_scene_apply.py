"""Issue #17, pull request B: ``wled_apply_scene`` (AC-17-06 to -09 and the apply parts of
-08, -11 and -12).

Mock fleet and ``tmp_path`` only; the only POSTs are those to the synthetic ``FakeWLED``
devices of ``tests/scene_support.py``. No LAN device, no hardware.
"""

from __future__ import annotations

import copy
import itertools
import logging
from collections import Counter
from typing import Any

import anyio
import pytest

from tests.scene_support import (
    SceneFleet,
    call,
    device_target,
    group_target,
    open_fleet,
    scene_document,
    segments_of,
    strip,
    write_group_file,
    write_scene_file,
)
from tests.tool_contract import CONTROL, expected_tool
from wled_mcp import scene_tools
from wled_mcp.access import AccessPolicy, ToolClass
from wled_mcp.models import DomainError
from wled_mcp.scene_tools import (
    MAX_CONCURRENCY,
    DeviceApply,
    DevicePlan,
    apply_outcome,
)
from wled_mcp.scenes import ExpandedTarget, Scene, SceneTarget

WIPE_LEFT = ["Solid", "Wipe", "Blink"]
AMBIGUOUS = ["Solid", "Wipe", "wipe"]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def three() -> SceneFleet:
    """desk (Wipe is ID 3), shelf_left (Wipe is ID 1) and shelf_right (``wipe`` ambiguous)."""
    return SceneFleet(
        desk=strip(),
        shelf_left=strip(effects=WIPE_LEFT),
        shelf_right=strip(effects=AMBIGUOUS),
    )


def look(**extra: Any) -> dict[str, Any]:
    """Master and segments on desk and shelf_left, segments only on shelf_right."""
    return scene_document(
        device_target(
            "desk",
            master={"on": True, "brightness": 90},
            segments=[{"ids": [0, 2], "effect_name": "Wipe", "speed": 77}],
        ),
        device_target(
            "shelf_left",
            master={"brightness": 40},
            segments=[{"ids": [0], "effect_name": "Wipe", "colors": [[255, 120, 20]]}],
        ),
        device_target("shelf_right", segments=[{"ids": [5], "speed": 12}]),
        **extra,
    )


async def stored(resources: Any, document: dict[str, Any]) -> None:
    outcome = await call(resources, "wled_save_scene", scene=document)
    assert outcome.ok, outcome.error


async def apply(resources: Any, scene_id: str = "evening", **kwargs: Any) -> Any:
    return await call(resources, "wled_apply_scene", scene_id=scene_id, **kwargs)


def fake_of(fleet: SceneFleet, device_id: str) -> Any:
    return fleet.devices[f"{device_id}.invalid"]


def posts_of(fleet: SceneFleet, device_id: str) -> list[Any]:
    return fake_of(fleet, device_id).posts


def entry(outcome: Any, device_id: str) -> dict[str, Any]:
    (found,) = [d for d in outcome.data["devices"] if d["device_id"] == device_id]
    return found


def triple(outcome: Any) -> tuple[str, str, bool]:
    return outcome.application, outcome.verification, outcome.ok


def snapshot(fleet: SceneFleet) -> dict[str, Any]:
    return {host: copy.deepcopy(fake.state()) for host, fake in fleet.devices.items()}


# ============================================================ classification (AC-17-11)


def test_apply_is_a_control_tool_and_not_destructive():
    expected = expected_tool("wled_apply_scene")
    assert (expected.tool_class, expected.destructive) == (CONTROL, False)


@pytest.mark.anyio
async def test_apply_registers_as_control_with_the_write_annotations(tmp_path):
    from wled_mcp.operations import build_operations

    async with open_fleet(tmp_path, three()) as resources:
        operations = {op.name: op for op in build_operations(resources)}
    operation = operations["wled_apply_scene"]
    assert operation.tool_class is ToolClass.CONTROL
    assert operation.annotations.read_only_hint is False
    assert operation.annotations.destructive_hint is False
    assert "device_id" not in operation.request_model.model_json_schema()["properties"]
    for fact in ("not atomic", "no rollback", "never retried", "four", "strict"):
        assert fact in operation.description


# ======================================================== success and per-device order


@pytest.mark.anyio
async def test_apply_writes_every_device_master_first_then_segments_and_verifies(tmp_path):
    fleet = three()
    async with open_fleet(tmp_path, fleet) as resources:
        await stored(resources, look())
        outcome = await apply(resources)
    assert outcome.ok, outcome.error
    assert triple(outcome) == ("applied", "verified", True)
    assert outcome.device_id is None and outcome.dry_run is False and outcome.error is None
    assert [d["device_id"] for d in outcome.data["devices"]] == [
        "desk",
        "shelf_left",
        "shelf_right",
    ]
    assert outcome.data["mode"] == "strict" and outcome.data["max_concurrency"] == 4
    assert outcome.data["summary"] == {
        "devices": 3,
        "verified": 3,
        "mismatch": 0,
        "unknown": 0,
        "not_attempted": 0,
    }
    assert any("not atomic" in warning for warning in outcome.warnings)
    # Master step first, then the segment step: one POST each, in that order.
    for device_id, steps in (
        ("desk", ["master", "segments"]),
        ("shelf_left", ["master", "segments"]),
        ("shelf_right", ["segments"]),
    ):
        reported = entry(outcome, device_id)
        assert [s["step"] for s in reported["steps"]] == steps
        assert all(s["ok"] and s["verification"] == "verified" for s in reported["steps"])
        posts = posts_of(fleet, device_id)
        assert len(posts) == len(steps)
        for body, step in zip(posts, steps, strict=True):
            assert ("seg" in body) is (step == "segments")
    assert posts_of(fleet, "desk")[0].keys() >= {"on", "bri"}
    # The names resolved per device and the live state follows the scene.
    assert segments_of(fake_of(fleet, "desk"))[0]["fx"] == 3
    assert segments_of(fake_of(fleet, "shelf_left"))[0]["fx"] == 1
    assert segments_of(fake_of(fleet, "desk"))[2]["sx"] == 77
    assert segments_of(fake_of(fleet, "shelf_right"))[5]["sx"] == 12
    assert (fake_of(fleet, "desk").on, fake_of(fleet, "desk").bri) == (True, 90)
    assert fake_of(fleet, "shelf_left").bri == 40
    resolved = entry(outcome, "shelf_left")["steps"][1]["resolved"]
    assert resolved == [{"segments": [0], "field": "effect", "name": "Wipe", "id": 1}]


@pytest.mark.anyio
async def test_a_device_with_only_one_kind_of_target_gets_exactly_one_post(tmp_path):
    fleet = three()
    document = scene_document(
        device_target("desk", master={"brightness": 33}),
        device_target("shelf_left", segments=[{"ids": [2], "speed": 5}]),
    )
    async with open_fleet(tmp_path, fleet) as resources:
        await stored(resources, document)
        outcome = await apply(resources)
    assert triple(outcome) == ("applied", "verified", True)
    assert [len(posts_of(fleet, d)) for d in ("desk", "shelf_left", "shelf_right")] == [1, 1, 0]
    assert "seg" not in posts_of(fleet, "desk")[0]
    assert [s["step"] for s in entry(outcome, "desk")["steps"]] == ["master"]


@pytest.mark.anyio
async def test_a_step_reports_the_plan_of_the_single_device_planner(tmp_path):
    fleet = three()
    document = scene_document(
        device_target(
            "desk",
            master={"brightness": 40},
            segments=[{"ids": [2], "speed": 7, "colors": [[1, 2, 3]], "effect_id": 1}],
        )
    )
    async with open_fleet(tmp_path, fleet) as resources:
        await stored(resources, document)
        outcome = await apply(resources)
        master = await call(
            resources, "wled_set_state", device_id="desk", brightness=40, dry_run=True
        )
        patch = await call(
            resources,
            "wled_patch_segments",
            device_id="desk",
            segments=[{"id": 2, "speed": 7, "colors": [[1, 2, 3]], "effect_id": 1}],
            dry_run=True,
        )
    desk = entry(outcome, "desk")
    assert desk["steps"][0]["plan"] == master.data["plan"]
    assert desk["steps"][0]["postconditions"] == master.data["postconditions"]
    assert desk["steps"][1]["plan"] == patch.data["plan"]
    assert desk["steps"][1]["postconditions"] == patch.data["postconditions"]


# ================================================== dry_run equals the plan (AC-17-09)


@pytest.mark.anyio
@pytest.mark.parametrize("mode", ["strict", "best_effort"])
@pytest.mark.parametrize("broken", [False, True])
async def test_apply_dry_run_returns_exactly_the_plan_and_sends_no_post(tmp_path, mode, broken):
    fleet = three()
    if broken:  # one device fails preflight, so both modes differ and the error is present
        fake_of(fleet, "shelf_left").unreachable = True
    before = snapshot(fleet)
    async with open_fleet(tmp_path, fleet) as resources:
        await stored(resources, look())
        plan = await call(resources, "wled_plan_scene", scene_id="evening", mode=mode)
        dry = await apply(resources, mode=mode, dry_run=True)
    assert dry.dry_run is True and dry.operation == "wled_apply_scene"
    assert plan.operation == "wled_plan_scene"
    assert dry.model_dump() | {"operation": ""} == plan.model_dump() | {"operation": ""}
    assert fleet.post_count() == 0 and snapshot(fleet) == before
    assert dry.ok is (not broken or mode == "best_effort")
    assert (dry.application, dry.verification) == ("not_attempted", "not_requested")


@pytest.mark.anyio
async def test_apply_dry_run_of_a_refused_request_equals_the_plan_refusal(tmp_path):
    fleet = three()
    write_group_file(tmp_path, "pair", [{"device": "desk"}, {"device": "shelf_left"}])
    write_scene_file(tmp_path, scene_document(device_target("desk"), group_target("pair")))
    async with open_fleet(tmp_path, fleet) as resources:
        plan = await call(resources, "wled_plan_scene", scene_id="evening")
        dry = await apply(resources, dry_run=True)
        real = await apply(resources)
    assert dry.model_dump() | {"operation": ""} == plan.model_dump() | {"operation": ""}
    assert "targeted twice" in dry.error.message and dry.dry_run is True
    assert real.dry_run is False and real.error == dry.error
    assert fleet.calls == [], "a refused request performs no device I/O at all"


# ================================================================== strict (AC-17-07)

PREFLIGHT_FAILURES = {
    "unreachable": "UNREACHABLE",
    "ambiguous_name": "AMBIGUOUS_NAME",
    "missing_segment": "VALIDATION_ERROR",
    "no_cct": "UNSUPPORTED_CAPABILITY",
    "locked": "TIMEOUT",
}


def failing_scene(kind: str) -> dict[str, Any]:
    """desk and shelf_right are fine; shelf_left (the middle device) fails ``kind``."""
    middle: dict[str, Any] = {
        "unreachable": device_target("shelf_left", master={"brightness": 40}),
        "ambiguous_name": device_target(
            "shelf_left", segments=[{"ids": [0], "effect_name": "WIPE"}]
        ),
        "missing_segment": device_target("shelf_left", segments=[{"ids": [9], "speed": 1}]),
        "no_cct": device_target("shelf_left", segments=[{"ids": [0], "cct": 100}]),
        "locked": device_target("shelf_left", master={"brightness": 40}),
    }[kind]
    return scene_document(
        device_target("desk", master={"brightness": 90}),
        middle,
        device_target("shelf_right", segments=[{"ids": [5], "speed": 12}]),
    )


@pytest.mark.anyio
@pytest.mark.parametrize("kind", list(PREFLIGHT_FAILURES))
async def test_strict_writes_nothing_anywhere_when_one_target_fails_preflight(tmp_path, kind):
    fleet = three()
    if kind == "ambiguous_name":
        fake_of(fleet, "shelf_left").effects = list(AMBIGUOUS)
    if kind == "unreachable":
        fake_of(fleet, "shelf_left").unreachable = True
    before = snapshot(fleet)
    async with open_fleet(tmp_path, fleet, timeout=0.3) as resources:
        await stored(resources, failing_scene(kind))
        if kind == "locked":
            async with resources.locks["shelf_left"]:
                default = await apply(resources)
                explicit = await apply(resources, mode="strict")
        else:
            default = await apply(resources)
            explicit = await apply(resources, mode="strict")
    for outcome in (default, explicit):
        assert triple(outcome) == ("not_attempted", "not_requested", False)
        assert outcome.dry_run is False
        assert outcome.error.code == PREFLIGHT_FAILURES[kind]
        assert "'shelf_left'" in outcome.error.message
        assert outcome.data["mode"] == "strict"
        failed = entry(outcome, "shelf_left")
        assert failed["error"]["code"] == PREFLIGHT_FAILURES[kind] and failed["steps"] == []
        for passing in ("desk", "shelf_right"):
            held_back = entry(outcome, passing)
            assert held_back["error"] is None and held_back["ok"] is False
            assert "strict" in held_back["skipped"] and held_back["steps"] == []
        assert outcome.data["summary"]["not_attempted"] == 3
    assert fleet.post_count() == 0 and snapshot(fleet) == before
    assert all(fake.posts == [] for fake in fleet.devices.values())


@pytest.mark.anyio
async def test_strict_is_the_default_and_best_effort_must_be_requested(tmp_path):
    fleet = three()
    fake_of(fleet, "shelf_left").unreachable = True
    async with open_fleet(tmp_path, fleet) as resources:
        await stored(resources, failing_scene("unreachable"))
        default = await apply(resources)
        assert fleet.post_count() == 0
        best = await apply(resources, mode="best_effort")
    assert default.data["mode"] == "strict" and best.data["mode"] == "best_effort"
    assert default.application == "not_attempted" and best.application == "applied"


# ============================================================== best_effort (AC-17-07)


@pytest.mark.anyio
@pytest.mark.parametrize("kind", ["unreachable", "ambiguous_name", "missing_segment", "no_cct"])
async def test_best_effort_skips_only_the_failing_device_and_writes_the_rest(tmp_path, kind):
    fleet = three()
    if kind == "unreachable":
        fake_of(fleet, "shelf_left").unreachable = True
    if kind == "ambiguous_name":
        fake_of(fleet, "shelf_left").effects = list(AMBIGUOUS)
    async with open_fleet(tmp_path, fleet) as resources:
        await stored(resources, failing_scene(kind))
        outcome = await apply(resources, mode="best_effort")
    # Two of three devices were applied and verified: "proven partial", never ok.
    assert triple(outcome) == ("applied", "mismatch", False)
    assert outcome.error.code == "VERIFICATION_MISMATCH"
    assert outcome.data["summary"]["verified"] == 2
    skipped = entry(outcome, "shelf_left")
    assert skipped["error"]["code"] == PREFLIGHT_FAILURES[kind]
    assert skipped["application"] == "not_attempted" and "best_effort" in skipped["skipped"]
    assert skipped["steps"] == [] and posts_of(fleet, "shelf_left") == []
    for written in ("desk", "shelf_right"):
        assert entry(outcome, written)["ok"] is True
        assert posts_of(fleet, written), written
    if kind == "ambiguous_name":
        assert skipped["candidates"] and skipped["candidate_total"] == 2


@pytest.mark.anyio
async def test_best_effort_with_every_device_passing_is_a_full_success(tmp_path):
    fleet = three()
    async with open_fleet(tmp_path, fleet) as resources:
        await stored(resources, look())
        outcome = await apply(resources, mode="best_effort")
    assert triple(outcome) == ("applied", "verified", True)


@pytest.mark.anyio
async def test_best_effort_with_no_device_passing_writes_nothing_with_the_first_error(tmp_path):
    fleet = three()
    for fake in fleet.devices.values():
        fake.unreachable = True
    document = scene_document(
        device_target("desk"), device_target("shelf_left", segments=[{"ids": [9], "speed": 1}])
    )
    async with open_fleet(tmp_path, fleet) as resources:
        await stored(resources, document)
        outcome = await apply(resources, mode="best_effort")
    assert triple(outcome) == ("not_attempted", "not_requested", False)
    assert outcome.error.code == "UNREACHABLE" and "'desk'" in outcome.error.message
    assert fleet.post_count() == 0
    assert all(
        "Not written" in d["skipped"] or "Skipped" in d["skipped"] for d in outcome.data["devices"]
    )


@pytest.mark.anyio
async def test_an_unconfigured_device_is_a_per_device_unknown_device_refusal(tmp_path):
    fleet = three()
    write_group_file(tmp_path, "pair", [{"device": "shelf_left"}, {"device": "removed_strip"}])
    write_scene_file(
        tmp_path,
        scene_document(
            device_target("desk"),
            group_target("pair"),
            device_target("ghost"),  # a directly named device that is not configured
        ),
    )
    async with open_fleet(tmp_path, fleet) as resources:
        strict = await apply(resources)
        assert fleet.post_count() == 0
        best = await apply(resources, mode="best_effort")
    assert triple(strict) == ("not_attempted", "not_requested", False)
    assert strict.error.code == "UNKNOWN_DEVICE" and "'removed_strip'" in strict.error.message
    for name in ("removed_strip", "ghost"):
        gone = entry(strict, name)
        assert gone["error"]["code"] == "UNKNOWN_DEVICE" and gone["steps"] == []
        assert entry(best, name)["error"]["code"] == "UNKNOWN_DEVICE"
    hosts = fleet.hosts_called()
    assert "removed_strip.invalid" not in hosts and "ghost.invalid" not in hosts
    assert set(fleet.post_hosts()) == {"desk.invalid", "shelf_left.invalid"}
    assert triple(best) == ("applied", "mismatch", False)


@pytest.mark.anyio
async def test_a_request_refused_as_a_whole_does_no_device_io(tmp_path):
    fleet = three()
    write_scene_file(tmp_path, scene_document(group_target("nowhere")))
    async with open_fleet(tmp_path, fleet) as resources:
        missing_group = await apply(resources)
        missing_scene = await apply(resources, "absent")
        dry = await apply(resources, dry_run=True)
    for outcome in (missing_group, missing_scene):
        assert triple(outcome) == ("not_attempted", "not_requested", False)
        assert outcome.error.code == "VALIDATION_ERROR"
        assert outcome.data == {}
    assert dry.dry_run is True and dry.error == missing_group.error
    assert fleet.calls == []


# =============================================== write phase: failures never stop others

WRITE_FAILURES = {
    # failure -> (device application, verification, aggregate code, POST count of the device)
    "readback_lost": ("unknown", "unknown", "WRITE_OUTCOME_UNKNOWN", 1),
    "ack_only": ("unknown", "mismatch", "WRITE_OUTCOME_UNKNOWN", 1),
    "post_failed": ("unknown", "mismatch", "WRITE_OUTCOME_UNKNOWN", 1),
}


def inject(fake: Any, failure: str) -> None:
    if failure == "readback_lost":
        fake.fail_reads_from_post = 1
    elif failure == "ack_only":
        fake.post_actions = {0: "drop"}
    else:
        fake.post_actions = {0: "fail_before"}


@pytest.mark.anyio
@pytest.mark.parametrize("mode", ["strict", "best_effort"])
@pytest.mark.parametrize("failure", list(WRITE_FAILURES))
async def test_a_device_failing_in_the_write_phase_never_stops_or_undoes_another(
    tmp_path, mode, failure
):
    application, verification, code, expected_posts = WRITE_FAILURES[failure]
    fleet = three()
    inject(fake_of(fleet, "shelf_left"), failure)
    async with open_fleet(tmp_path, fleet) as resources:
        await stored(resources, look())
        outcome = await apply(resources, mode=mode)
    assert triple(outcome) == ("unknown", "unknown", False)
    assert outcome.error.code == code and outcome.dry_run is False
    bad = entry(outcome, "shelf_left")
    assert (bad["application"], bad["verification"]) == (application, verification)
    assert bad["ok"] is False and bad["step"] == "master"
    # The segment step of the failed device was never attempted, with the reason.
    assert [s["step"] for s in bad["steps"]] == ["master"] and "master step" in bad["skipped"]
    assert len(posts_of(fleet, "shelf_left")) == expected_posts
    # The devices before and after it in expansion order were fully written and verified.
    for good in ("desk", "shelf_right"):
        assert entry(outcome, good)["ok"] is True
    assert segments_of(fake_of(fleet, "desk"))[0]["fx"] == 3
    assert segments_of(fake_of(fleet, "shelf_right"))[5]["sx"] == 12
    assert outcome.data["summary"]["verified"] == 2


@pytest.mark.anyio
@pytest.mark.parametrize("failure", ["drop", "fail_before", "readback_lost"])
async def test_an_uncertain_segment_step_is_never_replayed(tmp_path, failure):
    # The segment step is POST index 1 on a device with a master step: inject there.
    fleet = three()
    desk = fake_of(fleet, "desk")
    if failure == "readback_lost":
        desk.fail_reads_from_post = 2
    else:
        desk.post_actions = {1: failure}
    async with open_fleet(tmp_path, fleet) as resources:
        await stored(resources, look())
        outcome = await apply(resources)
    reported = entry(outcome, "desk")
    assert [s["step"] for s in reported["steps"]] == ["master", "segments"]
    assert reported["steps"][0]["ok"] is True and reported["steps"][1]["ok"] is False
    assert reported["application"] == "unknown" and reported["step"] == "segments"
    expected = "unknown" if failure == "readback_lost" else "mismatch"
    assert reported["verification"] == expected
    assert len(posts_of(fleet, "desk")) == 2, "the uncertain segment write is not replayed"
    assert triple(outcome) == ("unknown", "unknown", False)
    assert outcome.error.code == "WRITE_OUTCOME_UNKNOWN"
    assert entry(outcome, "shelf_left")["ok"] and entry(outcome, "shelf_right")["ok"]


@pytest.mark.anyio
async def test_no_device_is_ever_written_twice_and_nothing_is_compensated(tmp_path):
    fleet = three()
    inject(fake_of(fleet, "shelf_left"), "ack_only")
    fake_of(fleet, "shelf_right").post_actions = {0: "fail_after"}  # applied, response lost
    async with open_fleet(tmp_path, fleet) as resources:
        await stored(resources, look())
        before = snapshot(fleet)
        outcome = await apply(resources)
        after_apply = snapshot(fleet)
        # An explicit second call is a new request; the first never replays by itself.
        counts = {d: len(posts_of(fleet, d)) for d in ("desk", "shelf_left", "shelf_right")}
    assert outcome.application == "unknown"
    assert counts == {"desk": 2, "shelf_left": 1, "shelf_right": 1}
    # The device that succeeded keeps the scene state: no restoring write followed the
    # failure of another device, and the device that did not apply received nothing more.
    assert after_apply["desk.invalid"] != before["desk.invalid"]
    assert after_apply["shelf_left.invalid"] == before["shelf_left.invalid"]
    for device_id in ("desk", "shelf_left", "shelf_right"):
        for body in posts_of(fleet, device_id):
            assert body.keys() <= {"on", "bri", "tt", "seg"}
    assert segments_of(fake_of(fleet, "desk"))[0]["fx"] == 3


@pytest.mark.anyio
async def test_a_timed_out_write_is_uncertain_and_never_retried(tmp_path):
    fleet = three()

    async def stall(_fake: Any, _request: Any) -> None:
        await anyio.sleep(30)

    fake_of(fleet, "desk").post_actions = {0: stall}
    async with open_fleet(tmp_path, fleet, timeout=0.6) as resources:
        await stored(resources, look())
        with anyio.fail_after(20):
            outcome = await apply(resources)
    desk = entry(outcome, "desk")
    assert desk["application"] == "unknown" and desk["ok"] is False
    assert desk["verification"] in {"unknown", "mismatch"} and desk["step"] == "master"
    assert len(posts_of(fleet, "desk")) == 1, "the timed-out write is not replayed"
    assert [len(posts_of(fleet, d)) for d in ("shelf_left", "shelf_right")] == [2, 1]
    assert outcome.application == "unknown" and outcome.error.code == "WRITE_OUTCOME_UNKNOWN"


@pytest.mark.anyio
async def test_a_proven_master_step_with_a_refused_segment_step_is_a_partial_device(tmp_path):
    fleet = three()
    desk = fake_of(fleet, "desk")

    def remove_segment_after_master() -> None:
        # Preflight passed; after the master write the device no longer has segment 2.
        if len(desk.posts) == 1:
            desk.slots[2]["stop"] = desk.slots[2]["start"]

    desk.read_hook = remove_segment_after_master
    document = scene_document(
        device_target("desk", master={"brightness": 90}, segments=[{"ids": [0, 2], "speed": 77}]),
        device_target("shelf_left", master={"brightness": 40}),
    )
    async with open_fleet(tmp_path, fleet) as resources:
        await stored(resources, document)
        outcome = await apply(resources)
    reported = entry(outcome, "desk")
    # The device was replanned under the lock, so the vanished segment is a refusal that
    # was never sent; the proven master step stays reported as applied.
    assert (reported["application"], reported["verification"]) == ("applied", "mismatch")
    assert reported["error"]["code"] == "VALIDATION_ERROR" and reported["ok"] is False
    assert [s["step"] for s in reported["steps"]] == ["master", "segments"]
    assert reported["steps"][0]["ok"] is True and reported["steps"][1]["ok"] is False
    assert reported["steps"][1]["application"] == "not_attempted"
    assert "refused before it was sent" in reported["skipped"]
    assert len(posts_of(fleet, "desk")) == 1
    assert triple(outcome) == ("applied", "mismatch", False)
    assert outcome.error.code == "VERIFICATION_MISMATCH"
    assert entry(outcome, "shelf_left")["ok"] is True


# ============================================================ ordering and concurrency


def crowd(count: int) -> SceneFleet:
    return SceneFleet(**{f"strip{n}": strip() for n in range(count)})


@pytest.mark.anyio
async def test_at_most_four_devices_are_written_at_once_and_results_keep_expansion_order(tmp_path):
    fleet = crowd(8)
    for number, fake in enumerate(fleet.devices.values()):
        fake.delay = 0.03 - number * 0.003  # later devices finish sooner
    document = scene_document(
        *[device_target(f"strip{n}", master={"brightness": 10 + n}) for n in range(8)]
    )
    async with open_fleet(tmp_path, fleet) as resources:
        await stored(resources, document)
        outcome = await apply(resources)
    assert triple(outcome) == ("applied", "verified", True)
    assert [d["device_id"] for d in outcome.data["devices"]] == [f"strip{n}" for n in range(8)]
    assert fleet.max_in_flight == MAX_CONCURRENCY == 4
    # Completion order differs from expansion order: the first POSTs are not strip0..3 in order
    # of finishing, yet the report is in document order.
    assert set(fleet.post_hosts()) == {f"strip{n}.invalid" for n in range(8)}
    assert all(len(posts_of(fleet, f"strip{n}")) == 1 for n in range(8))
    assert all(fake_of(fleet, f"strip{n}").bri == 10 + n for n in range(8))


@pytest.mark.anyio
async def test_the_write_phase_itself_is_bounded_not_only_the_preflight(tmp_path):
    fleet = crowd(8)
    document = scene_document(*[device_target(f"strip{n}") for n in range(8)])
    gauge = {"now": 0, "max": 0}

    async def slow_post(_fake: Any, _request: Any) -> None:
        gauge["now"] += 1
        gauge["max"] = max(gauge["max"], gauge["now"])
        try:
            await anyio.sleep(0.05)
        finally:
            gauge["now"] -= 1

    for fake in fleet.devices.values():
        fake.post_actions = {0: slow_post}
    async with open_fleet(tmp_path, fleet) as resources:
        await stored(resources, document)
        outcome = await apply(resources)
    assert outcome.ok and gauge["max"] == 4


@pytest.mark.anyio
async def test_two_scenes_on_one_device_serialize_under_the_existing_lock(tmp_path):
    fleet = three()
    one = scene_document(
        device_target("desk", master={"brightness": 11}, segments=[{"ids": [0], "speed": 1}]),
        id="one",
    )
    two = scene_document(
        device_target("desk", master={"brightness": 22}, segments=[{"ids": [0], "speed": 2}]),
        id="two",
    )
    results: dict[str, Any] = {}
    async with open_fleet(tmp_path, fleet) as resources:
        await stored(resources, one)
        await stored(resources, two)

        async def run(scene_id: str) -> None:
            results[scene_id] = await apply(resources, scene_id)

        async with anyio.create_task_group() as group:
            group.start_soon(run, "one")
            group.start_soon(run, "two")
    assert all(outcome.ok for outcome in results.values())
    assert fleet.host_max_in_flight["desk.invalid"] == 1
    assert len(posts_of(fleet, "desk")) == 4


# ============================================================= stop semantics (contract)


@pytest.mark.anyio
async def test_a_stopped_scene_leaves_unstarted_devices_untouched_and_never_replays(tmp_path):
    fleet = crowd(8)
    document = scene_document(*[device_target(f"strip{n}") for n in range(8)])
    scope = anyio.CancelScope()

    async def stop_here(_fake: Any, _request: Any) -> None:
        scope.cancel()
        await anyio.sleep(30)

    for fake in fleet.devices.values():
        fake.post_actions = {0: stop_here}
    async with open_fleet(tmp_path, fleet) as resources:
        await stored(resources, document)
        before = snapshot(fleet)
        with scope:
            await apply(resources)
        assert scope.cancelled_caught
        sent = {n: len(posts_of(fleet, f"strip{n}")) for n in range(8)}
        # Devices that never started were not contacted for a write, and nothing was
        # written twice; the devices that did start were interrupted mid-write.
        assert all(count <= 1 for count in sent.values())
        assert all(sent[n] == 0 for n in range(4, 8)), sent
        assert 1 <= sum(sent.values()) <= 4
        untouched = [n for n in range(8) if sent[n] == 0]
        for n in untouched:
            assert snapshot(fleet)[f"strip{n}.invalid"] == before[f"strip{n}.invalid"]
        # The locks were released: the same process can read every device again.
        assert not any(lock.locked() for lock in resources.locks.values())
        again = await call(resources, "wled_get_state", device_id="strip7")
        assert again.ok


# ======================================================== access: profiles and ceilings


def policy(profile: str = "control", **caps: str) -> AccessPolicy:
    return AccessPolicy(profile, {d: ToolClass(v) for d, v in caps.items()})  # type: ignore[arg-type]


@pytest.mark.anyio
async def test_a_device_below_control_fails_preflight_before_any_read_of_it(tmp_path):
    fleet = three()
    async with open_fleet(tmp_path, fleet, access=policy(shelf_left="read")) as resources:
        await stored(resources, look())
        strict = await apply(resources)
        assert fleet.post_count() == 0
        best = await apply(resources, mode="best_effort")
    assert triple(strict) == ("not_attempted", "not_requested", False)
    assert strict.error.code == "ACCESS_DENIED" and "'shelf_left'" in strict.error.message
    assert entry(strict, "shelf_left")["error"]["code"] == "ACCESS_DENIED"
    assert entry(strict, "shelf_left")["steps"] == []
    # Best effort skips only the capped device; it is never read and never written.
    assert triple(best) == ("applied", "mismatch", False)
    assert entry(best, "shelf_left")["error"]["code"] == "ACCESS_DENIED"
    assert "shelf_left.invalid" not in fleet.hosts_called()
    assert {d for d in fleet.post_hosts()} == {"desk.invalid", "shelf_right.invalid"}
    assert entry(best, "desk")["ok"] and entry(best, "shelf_right")["ok"]


@pytest.mark.anyio
async def test_apply_dry_run_applies_the_same_ceiling_as_an_apply(tmp_path):
    # dry_run does not lower the class (TD-20-2): the capped device is refused in the
    # preview exactly as in the apply, while the read-class plan tool still previews.
    fleet = three()
    async with open_fleet(tmp_path, fleet, access=policy(shelf_left="read")) as resources:
        await stored(resources, look())
        dry = await apply(resources, mode="best_effort", dry_run=True)
        plan = await call(resources, "wled_plan_scene", scene_id="evening", mode="best_effort")
    assert entry_of_plan(dry, "shelf_left")["error"]["code"] == "ACCESS_DENIED"
    assert entry_of_plan(plan, "shelf_left")["preflight"] == "ok"
    assert fleet.post_count() == 0


def entry_of_plan(outcome: Any, device_id: str) -> dict[str, Any]:
    (found,) = [t for t in outcome.data["targets"] if t["device_id"] == device_id]
    return found


@pytest.mark.anyio
async def test_the_preflight_calls_require_access_once_per_expanded_device(tmp_path):
    fleet = three()
    # A strict refusal on shelf_left keeps the write engines out of the count: only the
    # preflight calls the public check.
    fake_of(fleet, "shelf_left").unreachable = True
    seen: list[tuple[str, ToolClass, bool]] = []
    async with open_fleet(tmp_path, fleet) as resources:
        real = resources.require_access

        def spy(device_id: str, tool_class: ToolClass) -> None:
            seen.append((device_id, tool_class, f"{device_id}.invalid" in fleet.hosts_called()))
            real(device_id, tool_class)

        resources.require_access = spy  # type: ignore[method-assign]
        await stored(resources, look())
        outcome = await apply(resources)
    assert outcome.application == "not_attempted" and fleet.post_count() == 0
    assert Counter(device for device, _c, _r in seen) == {
        "desk": 1,
        "shelf_left": 1,
        "shelf_right": 1,
    }
    assert {tool_class for _d, tool_class, _r in seen} == {ToolClass.CONTROL}
    assert not any(read_before for _d, _c, read_before in seen), "checked before any read"


@pytest.mark.anyio
async def test_the_write_engine_refuses_a_class_the_preflight_no_longer_matches(tmp_path):
    # Preflight passes; before the write the deployment's ceiling for the device drops.
    # The write goes through the engine (G3), which refuses it with nothing sent.
    fleet = three()
    desk = fake_of(fleet, "desk")
    async with open_fleet(tmp_path, fleet) as resources:
        flipped: list[bool] = []

        def tighten() -> None:
            if not flipped:
                flipped.append(True)
                resources.access = policy("full", desk="read")

        desk.read_hook = tighten
        await stored(resources, scene_document(device_target("desk", master={"brightness": 90})))
        outcome = await apply(resources)
    assert triple(outcome) == ("not_attempted", "not_requested", False)
    reported = entry(outcome, "desk")
    assert reported["error"]["code"] == "ACCESS_DENIED" and reported["steps"][0]["step"] == "master"
    assert outcome.error.code == "ACCESS_DENIED" and fleet.post_count() == 0


@pytest.mark.anyio
async def test_an_unrestricted_deployment_is_not_affected_by_the_checks(tmp_path):
    fleet = three()
    async with open_fleet(tmp_path, fleet, access=policy("full")) as resources:
        await stored(resources, look())
        outcome = await apply(resources)
    assert triple(outcome) == ("applied", "verified", True)


# ============================================================== the aggregate mapping


def expanded(number: int) -> ExpandedTarget:
    return ExpandedTarget(f"d{number}", "device", number, {"on": True}, ())


def error(code: str, text: str) -> DomainError:
    return DomainError(code=code, message=text, reconciliation="x")  # type: ignore[arg-type]


SCENE = Scene("evening", "Evening", None, (SceneTarget("device", "d1", {"on": True}, ()),))

# One device's situation: V verified, U unknown/unknown, M unknown/mismatch, P partial
# (master proven, segments refused), N refused in the write phase, S failed preflight.
SITUATIONS = ("V", "U", "M", "P", "N", "S")


def build(situations: tuple[str, ...]) -> tuple[list[DevicePlan], list[DeviceApply]]:
    plans: list[DevicePlan] = []
    results: list[DeviceApply] = []
    for number, situation in enumerate(situations, start=1):
        plan = DevicePlan(expanded(number))
        if situation == "S":
            plan.error = error("VALIDATION_ERROR", f"preflight {number}")
        plans.append(plan)
        result = DeviceApply(expanded(number))
        if situation == "V":
            result.application, result.verification = "applied", "verified"
        elif situation == "U":
            result.application, result.verification = "unknown", "unknown"
            result.error = error("WRITE_OUTCOME_UNKNOWN", f"unknown {number}")
        elif situation == "M":
            result.application, result.verification = "unknown", "mismatch"
            result.error = error("VERIFICATION_MISMATCH", f"mismatch {number}")
        elif situation == "P":
            result.application, result.verification = "applied", "mismatch"
            result.error = error("VALIDATION_ERROR", f"partial {number}")
        elif situation == "N":
            result.error = error("UNREACHABLE", f"refused {number}")
        if situation != "S":
            results.append(result)
    return plans, results


def expected_mapping(situations: tuple[str, ...]) -> tuple[str, str, bool, str | None]:
    """The aggregate by the documented rule, written independently of the implementation."""
    if all(s == "V" for s in situations):
        return "applied", "verified", True, None
    if "U" in situations or "M" in situations:
        return "unknown", "unknown", False, "WRITE_OUTCOME_UNKNOWN"
    if "V" in situations or "P" in situations:
        return "applied", "mismatch", False, "VERIFICATION_MISMATCH"
    first = next(s for s in situations if s in "NS")
    return (
        "not_attempted",
        "not_requested",
        False,
        "UNREACHABLE" if first == "N" else ("VALIDATION_ERROR"),
    )


@pytest.mark.parametrize(
    "situations",
    [combo for size in (1, 2, 3) for combo in itertools.product(SITUATIONS, repeat=size)],
    ids=lambda combo: "".join(combo),
)
def test_the_aggregate_follows_the_documented_mapping_for_every_combination(situations):
    plans, results = build(situations)
    outcome = apply_outcome("wled_apply_scene", SCENE, "best_effort", plans, results)
    application, verification, ok, code = expected_mapping(situations)
    assert (outcome.application, outcome.verification, outcome.ok) == (
        application,
        verification,
        ok,
    )
    assert (outcome.error.code if outcome.error else None) == code
    assert outcome.dry_run is False and outcome.device_id is None
    devices = outcome.data["devices"]
    assert [d["device_id"] for d in devices] == [f"d{n}" for n in range(1, len(situations) + 1)]
    summary = outcome.data["summary"]
    assert summary["devices"] == len(situations)
    assert summary["verified"] + summary["mismatch"] + summary["unknown"] + summary[
        "not_attempted"
    ] == len(situations)
    assert summary["verified"] == situations.count("V")
    if code is not None and application == "not_attempted":
        # The first refusal in expansion order, with the device named.
        first = next(n for n, s in enumerate(situations, start=1) if s in "NS")
        assert f"Device 'd{first}'" in outcome.error.message


def test_a_strict_block_marks_every_passing_device_as_not_written():
    plans, _ = build(("V", "S", "V"))
    outcome = apply_outcome("wled_apply_scene", SCENE, "strict", plans, [])
    assert (outcome.application, outcome.verification, outcome.ok) == (
        "not_attempted",
        "not_requested",
        False,
    )
    assert outcome.error.message.startswith("Device 'd2'")
    first, second, third = outcome.data["devices"]
    assert "strict" in first["skipped"] and first["error"] is None
    assert second["error"]["code"] == "VALIDATION_ERROR" and "strict" in second["skipped"]
    assert "strict" in third["skipped"]
    assert outcome.data["summary"]["not_attempted"] == 3


# ============================================================= never raises, never logs


@pytest.mark.anyio
async def test_a_bug_in_one_device_does_not_hide_the_others_and_is_logged_without_content(
    tmp_path, monkeypatch, caplog
):
    fleet = three()
    real = scene_tools._write_master

    async def broken(resources: Any, target: ExpandedTarget, name: str) -> Any:
        if target.device_id == "shelf_left":
            raise RuntimeError("Secret evening glow")
        return await real(resources, target, name)

    monkeypatch.setattr(scene_tools, "_write_master", broken)
    caplog.set_level(logging.DEBUG)
    async with open_fleet(tmp_path, fleet) as resources:
        await stored(resources, look(name="Secret evening glow"))
        outcome = await apply(resources, mode="best_effort")
    bad = entry(outcome, "shelf_left")
    assert bad["application"] == "not_attempted" and bad["error"]["code"] == "VALIDATION_ERROR"
    assert entry(outcome, "desk")["ok"] and entry(outcome, "shelf_right")["ok"]
    assert posts_of(fleet, "shelf_left") == []
    assert [r for r in caplog.records if "scene apply failure" in r.getMessage()]
    # The project's own loggers (the HTTP client library logs request lines with hosts).
    ours = [r for r in caplog.records if r.name.startswith("wled_mcp")]
    assert ours
    for record in ours:
        text = record.getMessage().casefold() + " " + str(record.args).casefold()
        for secret in ("secret", "glow", "evening", "wipe", "desk", "shelf"):
            assert secret not in text, (secret, record.getMessage())


@pytest.mark.anyio
async def test_a_bug_after_the_master_write_keeps_the_engine_verdict(tmp_path, monkeypatch):
    # Raised inside `_write_master` after `write_verified` returned: the POST was sent, so the
    # device must never be reported as not attempted. The engine's verdict is kept.
    fleet = three()
    real = scene_tools._step_data
    hit: list[int] = []

    def broken(plan: Any, extra: Any) -> Any:
        if not hit:
            hit.append(1)
            raise RuntimeError("synthetic")
        return real(plan, extra)

    monkeypatch.setattr(scene_tools, "_step_data", broken)
    async with open_fleet(tmp_path, fleet) as resources:
        await stored(resources, look())
        outcome = await apply(resources, mode="best_effort")
    assert hit
    assert not [d for d in outcome.data["devices"] if d["application"] == "not_attempted"]
    assert triple(outcome) == ("applied", "verified", True)
    first = outcome.data["devices"][0]
    assert first["steps"][0]["ok"] is True and "plan" not in first["steps"][0]


@pytest.mark.anyio
async def test_a_bug_after_an_uncertain_master_write_stays_unknown(tmp_path, monkeypatch):
    fleet = three()
    inject(fake_of(fleet, "desk"), "readback_lost")
    monkeypatch.setattr(
        scene_tools, "_step_data", lambda plan, extra: (_ for _ in ()).throw(RuntimeError("x"))
    )
    async with open_fleet(tmp_path, fleet) as resources:
        await stored(resources, look())
        outcome = await apply(resources, mode="best_effort")
    desk = entry(outcome, "desk")
    assert (desk["application"], desk["verification"]) == ("unknown", "unknown")
    assert len(posts_of(fleet, "desk")) == 1
    assert triple(outcome) == ("unknown", "unknown", False)


@pytest.mark.anyio
async def test_a_bug_after_a_step_may_have_been_sent_is_reported_as_unknown(tmp_path, monkeypatch):
    fleet = three()
    real = scene_tools._write_segments

    async def broken(resources: Any, target: ExpandedTarget, name: str) -> Any:
        if target.device_id == "desk":
            raise RuntimeError("synthetic")
        return await real(resources, target, name)

    monkeypatch.setattr(scene_tools, "_write_segments", broken)
    async with open_fleet(tmp_path, fleet) as resources:
        await stored(resources, look())
        outcome = await apply(resources)
    desk = entry(outcome, "desk")
    assert (desk["application"], desk["verification"]) == ("unknown", "unknown")
    assert desk["error"]["code"] == "WRITE_OUTCOME_UNKNOWN" and desk["ok"] is False
    assert triple(outcome) == ("unknown", "unknown", False)
    assert entry(outcome, "shelf_left")["ok"] and entry(outcome, "shelf_right")["ok"]


@pytest.mark.anyio
async def test_apply_never_logs_scene_names_ids_or_device_content(tmp_path, caplog):
    fleet = three()
    fake_of(fleet, "shelf_left").unreachable = True
    caplog.set_level(logging.DEBUG)
    async with open_fleet(tmp_path, fleet) as resources:
        await stored(resources, look(name="Secret evening glow"))
        await apply(resources, mode="best_effort")
        await apply(resources, dry_run=True)
    for record in caplog.records:
        text = record.getMessage().casefold()
        for secret in ("secret", "glow", "evening"):
            assert secret not in text, record.name
