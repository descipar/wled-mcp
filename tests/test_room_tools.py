"""Issue #183: rooms (R-183-1 to R-183-6; AC-183-03 to -16, -19, -24).

Mock fleet and ``tmp_path`` only (``tests/scene_support.py``); no LAN device, no hardware.
Three synthetic controllers (``strip_a``, ``strip_b``, ``strip_c``, segments 0, 2 and 5 each)
make a room; every refusal path asserts that no request reached any device.
"""

from __future__ import annotations

import copy
import json
import logging
from typing import Any

import anyio
import pytest
from pydantic import ValidationError

from tests.scene_support import (
    SceneFleet,
    call,
    device_target,
    group_arguments,
    group_target,
    open_fleet,
    scene_document,
    segments_of,
    stored_group_path,
    strip,
    write_group_file,
    write_raw,
    write_scene_file,
)
from tests.tool_contract import CONTROL, MANAGE, READ, expected_tool
from wled_mcp.access import AccessPolicy, ToolClass
from wled_mcp.client import ClientFailure
from wled_mcp.operations import build_operations
from wled_mcp.scene_store import DefinitionStore
from wled_mcp.scene_tools import MAX_GROUPS

NAMES = ("strip_a", "strip_b", "strip_c")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def fleet3() -> SceneFleet:
    return SceneFleet(**{name: strip() for name in NAMES})


def fake_of(fleet: SceneFleet, device_id: str) -> Any:
    return fleet.devices[f"{device_id}.invalid"]


def posts_of(fleet: SceneFleet, device_id: str) -> list[Any]:
    return fake_of(fleet, device_id).posts


def entry(outcome: Any, device_id: str) -> dict[str, Any]:
    (found,) = [d for d in outcome.data["devices"] if d["device_id"] == device_id]
    return found


def target_of(outcome: Any, device_id: str) -> dict[str, Any]:
    (found,) = [t for t in outcome.data["targets"] if t["device_id"] == device_id]
    return found


def triple(outcome: Any) -> tuple[str, str, bool]:
    return outcome.application, outcome.verification, outcome.ok


def write_room(tmp_path: Any, room_id: str, *members: dict[str, Any]) -> None:
    """A room file written directly (this also builds conflicts the tools would refuse)."""
    path = write_group_file(tmp_path, room_id, list(members))
    document = json.loads(path.read_text())
    document["kind"] = "room"
    write_raw(path, json.dumps(document, indent=2) + "\n")


def whole(*devices: str) -> list[dict[str, Any]]:
    return [{"device": device} for device in devices]


def living(tmp_path: Any, members: list[dict[str, Any]] | None = None) -> None:
    write_room(tmp_path, "living", *(members or whole(*NAMES)))


async def apply(resources: Any, room: str = "living", **kwargs: Any) -> Any:
    return await call(resources, "wled_apply_room", room=room, **kwargs)


def snapshot(fleet: SceneFleet) -> dict[str, Any]:
    return {host: copy.deepcopy(fake.state()) for host, fake in fleet.devices.items()}


# ======================================================== classification and registration


def test_the_room_action_is_a_control_tool_and_not_destructive():
    expected = expected_tool("wled_apply_room")
    assert (expected.tool_class, expected.destructive) == (CONTROL, False)
    assert expected_tool("wled_save_group").tool_class is MANAGE
    assert expected_tool("wled_list_groups").tool_class is READ


@pytest.mark.anyio
async def test_the_room_action_registers_with_the_write_annotations_and_the_guidance(tmp_path):
    async with open_fleet(tmp_path, fleet3()) as resources:
        operations = {op.name: op for op in build_operations(resources)}
    operation = operations["wled_apply_room"]
    assert operation.tool_class is ToolClass.CONTROL
    assert operation.annotations.read_only_hint is False
    assert operation.annotations.destructive_hint is False
    schema = operation.request_model.model_json_schema()
    assert "device_id" not in schema["properties"]
    for fact in ("kind=room", "not atomic", "never retried", "dry_run", "four", "strict"):
        assert fact in operation.description.casefold()
    # Every other room-aware description says where the room fits.
    assert "room" in operations["wled_list_devices"].description
    assert "room" in operations["wled_save_group"].description
    assert "room" in operations["wled_list_groups"].description
    for zone_tool in ("wled_plan_zone", "wled_apply_zone"):
        assert "room" in operations[zone_tool].description


# ============================================================================ storing a room


@pytest.mark.anyio
async def test_saving_a_room_stores_kind_and_a_plain_group_stays_byte_identical(tmp_path):
    async with open_fleet(tmp_path, fleet3()) as resources:
        plain = await call(resources, "wled_save_group", **group_arguments("floor", "strip_a"))
        room = await call(
            resources, "wled_save_group", **group_arguments("living", "strip_b", kind="room")
        )
    assert plain.ok and room.ok
    stored_plain = json.loads(stored_group_path(tmp_path, "floor").read_text())
    assert "kind" not in stored_plain
    assert plain.data["group"]["kind"] == "group" and room.data["group"]["kind"] == "room"
    assert json.loads(stored_group_path(tmp_path, "living").read_text())["kind"] == "room"


@pytest.mark.anyio
async def test_a_retained_plain_group_file_is_listed_and_never_rewritten(tmp_path):
    path = write_group_file(tmp_path, "floor", whole("strip_a"))
    before = path.read_bytes()
    async with open_fleet(tmp_path, fleet3()) as resources:
        listed = await call(resources, "wled_list_groups")
        single = await call(resources, "wled_list_groups", group_id="floor")
        refused = await call(resources, "wled_save_group", **group_arguments("floor", "strip_a"))
    assert listed.data["groups"][0]["kind"] == "group" and "room_conflicts" not in listed.data
    assert "kind" not in single.data["document"]
    assert refused.ok is False  # exists, needs overwrite=true
    assert path.read_bytes() == before


@pytest.mark.anyio
async def test_replacing_a_room_by_a_save_without_kind_demotes_it_and_warns(tmp_path):
    async with open_fleet(tmp_path, fleet3()) as resources:
        await call(
            resources, "wled_save_group", **group_arguments("living", "strip_a", kind="room")
        )
        outcome = await call(
            resources, "wled_save_group", **group_arguments("living", "strip_a", overwrite=True)
        )
    assert outcome.ok and outcome.data["replaced"]["kind"] == "room"
    assert outcome.data["group"]["kind"] == "group"
    assert any("kind changed" in warning for warning in outcome.warnings)
    assert "kind" not in json.loads(stored_group_path(tmp_path, "living").read_text())


@pytest.mark.anyio
async def test_a_dry_run_save_of_a_room_writes_nothing_and_reports_a_conflict(tmp_path):
    living(tmp_path, whole("strip_a"))
    async with open_fleet(tmp_path, fleet3()) as resources:
        fine = await call(
            resources,
            "wled_save_group",
            **group_arguments("kitchen", "strip_b", kind="room", dry_run=True),
        )
        clash = await call(
            resources,
            "wled_save_group",
            **group_arguments("kitchen", "strip_a", kind="room", dry_run=True),
        )
    assert fine.ok and fine.data["saved"] is False and fine.dry_run is True
    assert clash.ok is False and clash.error.code == "VALIDATION_ERROR"
    assert "'strip_a'" in clash.error.message and "'living'" in clash.error.message
    assert not stored_group_path(tmp_path, "kitchen").exists()


@pytest.mark.anyio
async def test_a_room_with_a_device_of_another_room_is_refused_but_the_same_room_may_change(
    tmp_path,
):
    async with open_fleet(tmp_path, fleet3()) as resources:
        first = await call(
            resources, "wled_save_group", **group_arguments("living", "strip_a", kind="room")
        )
        clash = await call(
            resources, "wled_save_group", **group_arguments("kitchen", "strip_a", kind="room")
        )
        again = await call(
            resources,
            "wled_save_group",
            **group_arguments("living", "strip_a", "strip_b", kind="room", overwrite=True),
        )
        # A plain group may overlap any room freely.
        plain = await call(resources, "wled_save_group", **group_arguments("floor", "strip_a"))
    assert first.ok and again.ok and plain.ok
    assert clash.ok is False and "'living'" in clash.error.message
    assert not stored_group_path(tmp_path, "kitchen").exists()


@pytest.mark.anyio
async def test_rooms_and_groups_share_the_group_bound(tmp_path):
    for number in range(MAX_GROUPS):
        write_group_file(tmp_path, f"g{number}", whole("strip_a"))
    async with open_fleet(tmp_path, fleet3()) as resources:
        outcome = await call(
            resources, "wled_save_group", **group_arguments("living", "strip_b", kind="room")
        )
    assert outcome.ok is False and "maximum" in outcome.error.message


# ============================================================================ listings


@pytest.mark.anyio
async def test_list_groups_reports_a_conflicting_pair_and_ignores_overlapping_plain_groups(
    tmp_path,
):
    write_room(tmp_path, "living", *whole("strip_a", "strip_b"))
    write_room(tmp_path, "hall", *whole("strip_b", "strip_c"))
    write_group_file(tmp_path, "floor", whole("strip_a", "strip_b", "strip_c"))
    write_group_file(tmp_path, "evening", whole("strip_a"))
    fleet = fleet3()
    async with open_fleet(tmp_path, fleet) as resources:
        outcome = await call(resources, "wled_list_groups")
    assert outcome.data["room_conflicts"] == [{"device_id": "strip_b", "rooms": ["hall", "living"]}]
    assert {g["id"]: g["kind"] for g in outcome.data["groups"]} == {
        "evening": "group",
        "floor": "group",
        "hall": "room",
        "living": "room",
    }
    assert any("more than one room" in warning for warning in outcome.warnings)
    assert fleet.calls == []


@pytest.mark.anyio
async def test_list_devices_shows_the_room_without_any_device_io(tmp_path):
    write_room(tmp_path, "living", *whole("strip_a"))
    write_room(tmp_path, "kitchen", *whole("strip_b"))
    write_group_file(tmp_path, "floor", whole("strip_a", "strip_b", "strip_c"))
    fleet = fleet3()
    async with open_fleet(tmp_path, fleet) as resources:
        outcome = await call(resources, "wled_list_devices")
    rooms = {d["id"]: d["room"] for d in outcome.data["devices"]}
    assert rooms == {"strip_a": "living", "strip_b": "kitchen", "strip_c": None}
    assert "room_conflicts" not in outcome.data and outcome.warnings == []
    assert fleet.calls == []


@pytest.mark.anyio
async def test_list_devices_reports_a_device_in_two_rooms_without_choosing_one(tmp_path):
    write_room(tmp_path, "living", *whole("strip_a", "strip_b"))
    write_room(tmp_path, "hall", *whole("strip_b"))
    async with open_fleet(tmp_path, fleet3()) as resources:
        outcome = await call(resources, "wled_list_devices")
    by_id = {d["id"]: d for d in outcome.data["devices"]}
    assert by_id["strip_b"]["room"] is None
    assert by_id["strip_b"]["room_conflict"] == ["hall", "living"]
    assert by_id["strip_a"]["room"] == "living" and "room_conflict" not in by_id["strip_a"]
    assert outcome.data["room_conflicts"] == 1
    assert any("more than one room" in warning for warning in outcome.warnings)


@pytest.mark.anyio
async def test_list_devices_with_probe_keeps_the_room_and_an_unusable_store_never_fails_it(
    tmp_path, monkeypatch
):
    living(tmp_path)
    fleet = fleet3()
    async with open_fleet(tmp_path, fleet) as resources:
        probed = await call(resources, "wled_list_devices", probe=True)
        assert {d["room"] for d in probed.data["devices"]} == {"living"}
        assert {d["probe_status"] for d in probed.data["devices"]} == {"reachable"}

        def broken(self: Any) -> Any:
            raise ClientFailure("STORAGE_FAILED", "synthetic")

        monkeypatch.setattr(DefinitionStore, "list_items", broken)
        outcome = await call(resources, "wled_list_devices")
    assert outcome.ok is True and len(outcome.data["devices"]) == 3
    assert all("room" not in device for device in outcome.data["devices"])
    assert any("room assignment was unavailable" in warning for warning in outcome.warnings)


# ============================================================================ the state path


@pytest.mark.anyio
async def test_a_state_reaches_every_member_with_one_master_post_each_and_verifies(tmp_path):
    living(tmp_path)
    fleet = fleet3()
    async with open_fleet(tmp_path, fleet) as resources:
        outcome = await apply(resources, state={"on": True, "brightness": 61})
    assert triple(outcome) == ("applied", "verified", True)
    assert outcome.data["room"] == {"id": "living", "name": "Group living"}
    assert [d["device_id"] for d in outcome.data["devices"]] == list(NAMES)
    assert [d["origin"] for d in outcome.data["devices"]] == [
        f"room:living/member:{n}" for n in (1, 2, 3)
    ]
    for device_id in NAMES:
        (body,) = posts_of(fleet, device_id)
        assert set(body) <= {"on", "bri", "tt"} and body["bri"] == 61  # master only
    assert fleet.max_in_flight <= 4
    assert any("not atomic" in warning and "room" in warning for warning in outcome.warnings)


@pytest.mark.anyio
async def test_the_request_needs_exactly_one_of_state_and_scene_id_and_a_bounded_master(tmp_path):
    living(tmp_path)
    fleet = fleet3()
    async with open_fleet(tmp_path, fleet) as resources:
        for bad in (
            {},
            {"state": {"on": True}, "scene_id": "evening"},
            {"state": {"brightness": 256}},
            {"state": {"transition_ms": -1}},
            {"state": {"on": True, "colors": [[1, 2, 3]]}},  # a segment field
            {"state": {"on": True, "seg": []}},  # a raw patch
            {"state": {"on": "yes"}},
        ):
            with pytest.raises(ValidationError):
                await apply(resources, **bad)
        # A syntactically fine state that sets neither power nor brightness.
        empty = await apply(resources, state={"transition_ms": 100})
        none = await apply(resources, state={})
    for outcome in (empty, none):
        assert outcome.ok is False and outcome.error.code == "VALIDATION_ERROR"
        assert triple(outcome) == ("not_attempted", "not_requested", False)
    assert fleet.calls == []


@pytest.mark.anyio
async def test_a_state_is_refused_for_a_partly_assigned_member_before_any_io(tmp_path):
    living(tmp_path, [{"device": "strip_a"}, {"device": "strip_b", "segments": [0, 2]}])
    fleet = fleet3()
    async with open_fleet(tmp_path, fleet) as resources:
        outcome = await apply(resources, state={"on": False})
        dry = await apply(resources, state={"on": False}, dry_run=True)
    for refused in (outcome, dry):
        assert triple(refused) == ("not_attempted", "not_requested", False)
        assert refused.error.code == "VALIDATION_ERROR" and "'strip_b'" in refused.error.message
        assert refused.data["problems"][0]["reason"] == "partial_member"
        assert refused.data["problem_total"] == 1
    assert dry.dry_run is True and fleet.calls == []


# ============================================================================ the scene path


def scene_for(*targets: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return scene_document(*targets, **extra)


@pytest.mark.anyio
async def test_a_scene_inside_the_room_applies_and_untouched_members_are_listed(tmp_path):
    living(tmp_path)
    write_scene_file(
        tmp_path,
        scene_for(
            device_target("strip_a", master={"on": True}),
            device_target("strip_b", segments=[{"ids": [0], "effect_name": "Blink"}]),
        ),
    )
    fleet = fleet3()
    async with open_fleet(tmp_path, fleet) as resources:
        outcome = await apply(resources, scene_id="evening")
    assert triple(outcome) == ("applied", "verified", True)
    assert outcome.data["room"]["id"] == "living" and outcome.data["scene"]["id"] == "evening"
    assert outcome.data["members_not_targeted"] == ["strip_c"]
    assert any("not named by the scene" in warning for warning in outcome.warnings)
    assert posts_of(fleet, "strip_c") == []
    assert segments_of(fake_of(fleet, "strip_b"))[0]["fx"] == 1  # Blink


@pytest.mark.anyio
async def test_a_scene_may_reach_the_room_through_a_group_and_a_room_group_is_just_a_group(
    tmp_path,
):
    living(tmp_path)
    write_group_file(tmp_path, "pair", whole("strip_a", "strip_b"))
    write_scene_file(tmp_path, scene_for(group_target("pair"), group_target("living")))
    write_scene_file(tmp_path, scene_for(group_target("living"), id="whole", name="Whole"))
    fleet = fleet3()
    async with open_fleet(tmp_path, fleet) as resources:
        duplicate = await apply(resources, scene_id="evening")
        assert fleet.calls == [] and duplicate.error.code == "VALIDATION_ERROR"
        assert "targeted twice" in duplicate.error.message
        whole_room = await apply(resources, scene_id="whole")
    assert whole_room.ok
    assert [d["origin"] for d in whole_room.data["devices"]] == [
        f"group:living/member:{n}" for n in (1, 2, 3)
    ]
    assert whole_room.data["members_not_targeted"] == []


@pytest.mark.anyio
async def test_a_scene_touching_anything_outside_the_room_is_refused_as_a_whole(tmp_path):
    living(
        tmp_path,
        [{"device": "strip_a"}, {"device": "strip_b", "segments": [0, 2]}],
    )
    fleet = fleet3()
    cases = {
        "device": (
            [device_target("strip_a", master={"on": True}), device_target("strip_c")],
            "device_outside_room",
            "'strip_c'",
        ),
        "segment": (
            [device_target("strip_b", segments=[{"ids": [0, 5], "speed": 10}])],
            "segment_outside_room",
            "'strip_b'",
        ),
        "master": (
            [device_target("strip_b", master={"on": False})],
            "partial_member",
            "'strip_b'",
        ),
    }
    async with open_fleet(tmp_path, fleet) as resources:
        for name, (targets, reason, device) in cases.items():
            write_scene_file(tmp_path, scene_for(*targets, id=name, name=name))
            for dry_run in (False, True):
                outcome = await apply(resources, scene_id=name, dry_run=dry_run)
                assert triple(outcome) == ("not_attempted", "not_requested", False)
                assert outcome.error.code == "VALIDATION_ERROR" and device in outcome.error.message
                assert outcome.data["problems"][0]["reason"] == reason
                assert outcome.dry_run is dry_run
    assert fleet.calls == []


@pytest.mark.anyio
async def test_a_member_with_designated_segments_accepts_a_scene_inside_them(tmp_path):
    living(tmp_path, [{"device": "strip_b", "segments": [0, 2]}])
    write_scene_file(
        tmp_path, scene_for(device_target("strip_b", segments=[{"ids": [2], "speed": 33}]))
    )
    fleet = fleet3()
    async with open_fleet(tmp_path, fleet) as resources:
        outcome = await apply(resources, scene_id="evening")
    assert triple(outcome) == ("applied", "verified", True)
    (body,) = posts_of(fleet, "strip_b")
    assert [seg["id"] for seg in body["seg"]] == [2] and "on" not in body


@pytest.mark.anyio
async def test_the_refusal_lists_at_most_ten_problems_and_the_total(tmp_path):
    living(tmp_path, whole("strip_a"))
    write_scene_file(
        tmp_path,
        scene_for(*(device_target(f"other{n}", master={"on": True}) for n in range(12))),
    )
    fleet = fleet3()
    async with open_fleet(tmp_path, fleet) as resources:
        outcome = await apply(resources, scene_id="evening")
    assert outcome.data["problem_total"] == 12 and len(outcome.data["problems"]) == 10
    assert fleet.calls == []


# ============================================================ partial failure, unreachable, empty


@pytest.mark.anyio
async def test_a_partial_failure_is_never_overall_success_and_nothing_is_replayed(tmp_path):
    living(tmp_path)
    fleet = fleet3()
    fake_of(fleet, "strip_b").post_actions = {0: "drop"}  # acknowledged, not applied
    fake_of(fleet, "strip_c").fail_reads_from_post = 1  # applied, readback lost
    async with open_fleet(tmp_path, fleet) as resources:
        before = snapshot(fleet)
        outcome = await apply(resources, state={"on": True, "brightness": 77})
    assert triple(outcome) == ("unknown", "unknown", False)
    assert outcome.error.code == "WRITE_OUTCOME_UNKNOWN"
    assert entry(outcome, "strip_a")["ok"] is True
    assert (entry(outcome, "strip_b")["application"], entry(outcome, "strip_b")["ok"]) == (
        "unknown",
        False,
    )
    assert entry(outcome, "strip_c")["application"] == "unknown"
    assert [len(posts_of(fleet, d)) for d in NAMES] == [1, 1, 1]  # pinned: no retry
    assert snapshot(fleet)["strip_a.invalid"] != before["strip_a.invalid"]  # no rollback
    assert snapshot(fleet)["strip_b.invalid"] == before["strip_b.invalid"]


@pytest.mark.anyio
async def test_a_write_that_times_out_is_uncertain_and_never_retried(tmp_path):
    living(tmp_path)
    fleet = fleet3()

    async def stall(_fake: Any, _request: Any) -> None:
        await anyio.sleep(30)

    fake_of(fleet, "strip_a").post_actions = {0: stall}
    async with open_fleet(tmp_path, fleet, timeout=0.6) as resources:
        with anyio.fail_after(20):
            outcome = await apply(resources, state={"brightness": 50})
    assert entry(outcome, "strip_a")["application"] == "unknown"
    assert len(posts_of(fleet, "strip_a")) == 1
    assert outcome.application == "unknown" and outcome.ok is False


@pytest.mark.anyio
async def test_an_unreachable_member_blocks_strict_and_is_skipped_by_best_effort(tmp_path):
    living(tmp_path)
    fleet = fleet3()
    fake_of(fleet, "strip_b").unreachable = True
    async with open_fleet(tmp_path, fleet) as resources:
        strict = await apply(resources, state={"on": True})
        assert fleet.post_count() == 0
        best = await apply(resources, state={"on": True}, mode="best_effort")
    assert triple(strict) == ("not_attempted", "not_requested", False)
    assert strict.error.code == "UNREACHABLE" and "'strip_b'" in strict.error.message
    assert triple(best) == ("applied", "mismatch", False)
    assert best.error.code == "VERIFICATION_MISMATCH"
    assert entry(best, "strip_b")["error"]["code"] == "UNREACHABLE"
    assert sorted(fleet.post_hosts()) == ["strip_a.invalid", "strip_c.invalid"]


@pytest.mark.anyio
async def test_a_dry_run_is_the_plan_sends_no_write_and_shows_an_unreachable_member(tmp_path):
    living(tmp_path)
    fleet = fleet3()
    fake_of(fleet, "strip_c").unreachable = True
    async with open_fleet(tmp_path, fleet) as resources:
        dry = await apply(resources, state={"on": True}, dry_run=True, mode="best_effort")
        strict = await apply(resources, state={"on": True}, dry_run=True)
    assert dry.dry_run is True and dry.ok is True and fleet.post_count() == 0
    assert dry.data["would_write"] == ["strip_a", "strip_b"]
    assert dry.data["skipped"] == ["strip_c"]
    assert target_of(dry, "strip_c")["error"]["code"] == "UNREACHABLE"
    assert target_of(dry, "strip_a")["master"]["payload"]["on"] is True
    assert strict.ok is False and strict.data["would_write"] == []


@pytest.mark.anyio
async def test_a_capability_a_member_lacks_fails_only_that_member_and_strict_blocks_all(tmp_path):
    living(tmp_path)
    fleet = SceneFleet(
        strip_a=strip(),
        strip_b=strip(effects=["Solid", "Blink"]),  # no "Wipe"
        strip_c=strip(),
    )
    write_scene_file(
        tmp_path,
        scene_for(
            group_target("living", segments=[{"ids": [0], "effect_name": "Wipe"}]),
        ),
    )
    async with open_fleet(tmp_path, fleet) as resources:
        strict = await apply(resources, scene_id="evening")
        assert fleet.post_count() == 0
        best = await apply(resources, scene_id="evening", mode="best_effort")
    assert strict.ok is False and "'strip_b'" in strict.error.message
    assert entry(strict, "strip_b")["error"]["code"] in {"VALIDATION_ERROR", "UNKNOWN_NAME"}
    assert entry(strict, "strip_a")["skipped"].startswith("Not written")
    assert sorted(fleet.post_hosts()) == ["strip_a.invalid", "strip_c.invalid"]
    assert triple(best) == ("applied", "mismatch", False)


@pytest.mark.anyio
@pytest.mark.parametrize("mode", ["strict", "best_effort"])
async def test_a_room_whose_members_all_left_the_inventory_writes_and_reads_nothing(tmp_path, mode):
    write_room(tmp_path, "living", *whole("gone_a", "gone_b"))
    fleet = fleet3()
    async with open_fleet(tmp_path, fleet) as resources:
        outcome = await apply(resources, state={"on": True}, mode=mode)
    assert triple(outcome) == ("not_attempted", "not_requested", False)
    assert outcome.error.code == "UNKNOWN_DEVICE" and "'gone_a'" in outcome.error.message
    assert [d["error"]["code"] for d in outcome.data["devices"]] == ["UNKNOWN_DEVICE"] * 2
    assert fleet.calls == []


@pytest.mark.anyio
async def test_a_plain_group_an_unknown_id_and_an_unusable_file_are_refused_before_any_io(
    tmp_path,
):
    write_group_file(tmp_path, "floor", whole("strip_a"))
    write_raw(stored_group_path(tmp_path, "broken"), b"{not json")
    fleet = fleet3()
    async with open_fleet(tmp_path, fleet) as resources:
        plain = await apply(resources, "floor", state={"on": True})
        unknown = await apply(resources, "nowhere", state={"on": True})
        broken = await apply(resources, "broken", state={"on": True})
    assert "is a group, not a room" in plain.error.message
    for outcome in (plain, unknown, broken):
        assert triple(outcome) == ("not_attempted", "not_requested", False)
        assert outcome.error.code == "VALIDATION_ERROR"
    assert fleet.calls == []


# ============================================================================ overlap, conflicts


@pytest.mark.anyio
async def test_a_device_in_two_rooms_refuses_both_rooms_and_leaves_another_room_usable(tmp_path):
    write_room(tmp_path, "living", *whole("strip_a", "strip_b"))
    write_room(tmp_path, "hall", *whole("strip_b"))
    write_room(tmp_path, "garage", *whole("strip_c"))
    write_group_file(tmp_path, "floor", whole("strip_a", "strip_c"))  # a plain overlap
    fleet = fleet3()
    async with open_fleet(tmp_path, fleet) as resources:
        living_refused = await apply(resources, "living", state={"on": True})
        hall_refused = await apply(resources, "hall", state={"on": True}, dry_run=True)
        assert fleet.calls == []
        garage = await apply(resources, "garage", state={"on": True})
    for refused in (living_refused, hall_refused):
        assert refused.error.code == "VALIDATION_ERROR"
        assert refused.data["problems"][0]["reason"] == "room_conflict"
        assert "'strip_b'" in refused.error.message
        assert "wled_save_group" in refused.error.reconciliation
    assert garage.ok and fleet.post_hosts() == ["strip_c.invalid"]


# ============================================================================ access, reuse, logs


def policy(profile: str = "control", **caps: str) -> AccessPolicy:
    return AccessPolicy(profile, {d: ToolClass(v) for d, v in caps.items()})  # type: ignore[arg-type]


@pytest.mark.anyio
async def test_a_member_capped_below_control_fails_preflight_and_the_mode_decides(tmp_path):
    living(tmp_path)
    fleet = fleet3()
    async with open_fleet(tmp_path, fleet, access=policy(strip_b="read")) as resources:
        strict = await apply(resources, state={"on": True})
        dry = await apply(resources, state={"on": True}, dry_run=True, mode="best_effort")
        assert fleet.post_count() == 0
        best = await apply(resources, state={"on": True}, mode="best_effort")
    assert strict.error.code == "ACCESS_DENIED" and "'strip_b'" in strict.error.message
    assert target_of(dry, "strip_b")["error"]["code"] == "ACCESS_DENIED"
    assert triple(best) == ("applied", "mismatch", False)
    assert "strip_b.invalid" not in fleet.hosts_called()


@pytest.mark.anyio
async def test_the_write_engine_refuses_a_ceiling_that_dropped_after_the_preflight(tmp_path):
    living(tmp_path, whole("strip_a"))
    fleet = fleet3()
    async with open_fleet(tmp_path, fleet) as resources:
        flipped: list[bool] = []

        def tighten() -> None:
            if not flipped:
                flipped.append(True)
                resources.access = policy("full", strip_a="read")

        fake_of(fleet, "strip_a").read_hook = tighten
        outcome = await apply(resources, state={"brightness": 90})
    assert triple(outcome) == ("not_attempted", "not_requested", False)
    assert outcome.error.code == "ACCESS_DENIED" and fleet.post_count() == 0


@pytest.mark.anyio
async def test_a_room_state_equals_the_scene_apply_it_reuses_apart_from_the_room_and_origin(
    tmp_path,
):
    living(tmp_path)
    master = {"on": True, "brightness": 90}
    write_scene_file(tmp_path, scene_for(*(device_target(n, master=master) for n in NAMES)))
    results = []
    for tool, arguments in (
        ("wled_apply_room", {"room": "living", "state": master}),
        ("wled_apply_scene", {"scene_id": "evening"}),
    ):
        async with open_fleet(tmp_path, fleet3()) as resources:
            results.append(await call(resources, tool, **arguments))
    room, scene = (outcome.model_dump(mode="json") for outcome in results)
    for dumped in (room, scene):
        dumped.pop("operation")
        dumped["data"].pop("room", None)
        dumped["data"].pop("scene", None)
        dumped.pop("warnings")
        for device in dumped["data"]["devices"]:
            device.pop("origin")
            device.pop("target_index")
        dumped["data"].pop("notes")
    assert room == scene


@pytest.mark.anyio
async def test_the_room_action_never_logs_room_scene_group_or_device_names(tmp_path, caplog):
    write_room(tmp_path, "secretroom", *whole("strip_a", "strip_b"))
    write_scene_file(
        tmp_path,
        scene_for(group_target("secretroom"), id="hushscene", name="Hush glow"),
    )
    fleet = fleet3()
    fake_of(fleet, "strip_b").unreachable = True
    caplog.set_level(logging.DEBUG)
    async with open_fleet(tmp_path, fleet) as resources:
        await apply(resources, "secretroom", state={"on": True}, mode="best_effort")
        await apply(resources, "secretroom", scene_id="hushscene", dry_run=True)
    for record in caplog.records:
        text = record.getMessage().casefold()
        for secret in ("secretroom", "hushscene", "glow"):
            assert secret not in text, record.name
