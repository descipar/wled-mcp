"""Group and scene tools of issue #17, pull request A: AC-17-01, -03, -04, -05, -10, -11.

Mock fleet and ``tmp_path`` only; no LAN device. Every test of a read, manage or plan path
asserts that no device POST was sent.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import anyio
import pytest
from pydantic import ValidationError

from tests.scene_support import (
    SceneDevice,
    SceneFleet,
    call,
    canonical_scene,
    device_target,
    group_arguments,
    group_target,
    open_fleet,
    scene_document,
    segments_of,
    stored_group_path,
    stored_scene_path,
    strip,
    write_group_file,
    write_raw,
    write_scene_file,
)
from tests.tool_contract import MANAGE, READ, expected_tool
from wled_mcp.scene_tools import MAX_CONCURRENCY
from wled_mcp.scenes import MAX_EXPANDED_DEVICES

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "contracts" / "scene.json"
WIPE_LEFT = ["Solid", "Wipe", "Blink"]
AMBIGUOUS = ["Solid", "Wipe", "wipe"]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def three() -> SceneFleet:
    """desk (default catalogs), shelf_left (Wipe is ID 1) and shelf_right (ambiguous)."""
    return SceneFleet(
        desk=strip(),
        shelf_left=strip(effects=WIPE_LEFT),
        shelf_right=strip(effects=AMBIGUOUS),
    )


def error_of(outcome: Any) -> dict[str, Any]:
    assert outcome.ok is False and outcome.error is not None
    return outcome.error.model_dump()


def target_of(outcome: Any, device_id: str) -> dict[str, Any]:
    (found,) = [t for t in outcome.data["targets"] if t["device_id"] == device_id]
    return found


async def save_scene(resources: Any, document: dict[str, Any], **kwargs: Any) -> Any:
    outcome = await call(resources, "wled_save_scene", scene=document, **kwargs)
    return outcome


async def stored_scene(resources: Any, document: dict[str, Any]) -> None:
    outcome = await save_scene(resources, document)
    assert outcome.ok, outcome.error


async def stored_group(resources: Any, group_id: str, *members: Any) -> None:
    outcome = await call(resources, "wled_save_group", **group_arguments(group_id, *members))
    assert outcome.ok, outcome.error


# ================================================================ classification (AC-17-11)


def test_new_tools_are_classified_in_the_expected_contract():
    classes = {
        "wled_list_groups": (READ, False),
        "wled_save_group": (MANAGE, True),
        "wled_delete_group": (MANAGE, True),
        "wled_list_scenes": (READ, False),
        "wled_save_scene": (MANAGE, True),
        "wled_delete_scene": (MANAGE, True),
        "wled_plan_scene": (READ, False),
    }
    for name, (tool_class, destructive) in classes.items():
        expected = expected_tool(name)
        assert (expected.tool_class, expected.destructive) == (tool_class, destructive)


@pytest.mark.anyio
async def test_annotations_match_the_classes(tmp_path):
    from wled_mcp.operations import build_operations

    async with open_fleet(tmp_path, three()) as resources:
        operations = {op.name: op for op in build_operations(resources)}
    for name in ("wled_list_groups", "wled_list_scenes", "wled_plan_scene"):
        assert operations[name].annotations.read_only_hint is True
    for name in ("wled_save_group", "wled_delete_group", "wled_save_scene", "wled_delete_scene"):
        annotations = operations[name].annotations
        assert annotations.read_only_hint is False and annotations.destructive_hint is True
    # Every description states that no device is written.
    for name in ("wled_save_group", "wled_save_scene", "wled_plan_scene", "wled_list_scenes"):
        assert "device" in operations[name].description


# ===================================================================== groups (AC-17-01)


@pytest.mark.anyio
async def test_save_group_stores_the_document_and_contacts_no_device(tmp_path):
    fleet = three()
    async with open_fleet(tmp_path, fleet) as resources:
        outcome = await call(
            resources,
            "wled_save_group",
            **group_arguments("shelf", ("shelf_left", [0, 2]), "shelf_right"),
        )
    assert outcome.ok and outcome.application == "not_attempted" and outcome.device_id is None
    assert outcome.data["saved"] is True and outcome.data["replaced"] is None
    assert fleet.calls == [], "saving a group performs zero device I/O"
    stored = json.loads(stored_group_path(tmp_path, "shelf").read_text("utf-8"))
    assert stored == {
        "format": "wled-mcp.group",
        "format_version": 1,
        "id": "shelf",
        "name": "Group shelf",
        "members": [{"device": "shelf_left", "segments": [0, 2]}, {"device": "shelf_right"}],
    }


@pytest.mark.anyio
async def test_save_group_refuses_an_unknown_device_before_writing(tmp_path):
    async with open_fleet(tmp_path, three()) as resources:
        outcome = await call(
            resources, "wled_save_group", **group_arguments("g", "desk", "not_configured")
        )
    assert error_of(outcome)["code"] == "VALIDATION_ERROR"
    assert "Member 2" in outcome.error.message and "not configured" in outcome.error.message
    assert not stored_group_path(tmp_path, "g").exists()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "members, fragment",
    [
        (["desk", "desk"], "listed twice"),
        ([("desk", [1]), ("desk", [2])], "conflicting segment lists"),
    ],
)
async def test_save_group_rejects_a_duplicate_device_even_with_different_segments(
    tmp_path, members, fragment
):
    async with open_fleet(tmp_path, three()) as resources:
        outcome = await call(resources, "wled_save_group", **group_arguments("g", *members))
    assert error_of(outcome)["code"] == "VALIDATION_ERROR" and fragment in outcome.error.message
    assert not stored_group_path(tmp_path, "g").exists()


@pytest.mark.anyio
async def test_group_schema_bounds_are_enforced_before_the_domain(tmp_path):
    async with open_fleet(tmp_path, three()) as resources:
        for bad in (
            group_arguments("../x"),
            group_arguments("g", ("desk", [255])),
            group_arguments("g", ("desk", [])),
            group_arguments("g", ("desk", [1.5])),
            {**group_arguments("g"), "members": []},
            {**group_arguments("g"), "name": ""},
            {**group_arguments("g"), "unknown": 1},
        ):
            with pytest.raises(ValidationError):
                await call(resources, "wled_save_group", **bad)


@pytest.mark.anyio
async def test_save_group_overwrite_dry_run_and_previous_document(tmp_path):
    async with open_fleet(tmp_path, three()) as resources:
        await stored_group(resources, "shelf", "desk")
        before = stored_group_path(tmp_path, "shelf").read_bytes()
        refused = await call(resources, "wled_save_group", **group_arguments("shelf", "shelf_left"))
        assert error_of(refused)["code"] == "VALIDATION_ERROR"
        assert "overwrite=true" in refused.error.message
        dry = await call(
            resources,
            "wled_save_group",
            **group_arguments("shelf", "shelf_left", overwrite=True, dry_run=True),
        )
        assert dry.ok and dry.dry_run is True and dry.data["saved"] is False
        assert dry.data["replaced"]["members"] == [{"device": "desk"}]
        assert stored_group_path(tmp_path, "shelf").read_bytes() == before
        done = await call(
            resources, "wled_save_group", **group_arguments("shelf", "shelf_left", overwrite=True)
        )
        assert done.ok and done.data["saved"] is True
        assert done.data["replaced"]["members"] == [{"device": "desk"}]
        assert json.loads(stored_group_path(tmp_path, "shelf").read_text("utf-8"))["members"] == [
            {"device": "shelf_left"}
        ]


@pytest.mark.anyio
async def test_list_groups_shows_the_exact_expansion_and_flags_a_missing_member(tmp_path):
    fleet = three()
    write_group_file(
        tmp_path,
        "shelf",
        [{"device": "shelf_left", "segments": [0]}, {"device": "removed_strip"}],
    )
    write_group_file(tmp_path, "single", [{"device": "desk"}])
    async with open_fleet(tmp_path, fleet) as resources:
        outcome = await call(resources, "wled_list_groups")
        single = await call(resources, "wled_list_groups", group_id="shelf")
    assert outcome.ok and fleet.calls == []
    by_id = {g["id"]: g for g in outcome.data["groups"]}
    assert list(by_id) == ["shelf", "single"] and outcome.data["invalid_count"] == 0
    assert by_id["shelf"]["members"] == [
        {"member": 1, "device_id": "shelf_left", "segments": [0], "in_inventory": True},
        {"member": 2, "device_id": "removed_strip", "segments": None, "in_inventory": False},
    ]
    assert by_id["shelf"]["unresolved_members"] == 1 and by_id["single"]["unresolved_members"] == 0
    assert any("'shelf'" in warning and "UNKNOWN_DEVICE" in warning for warning in outcome.warnings)
    assert single.data["document"]["id"] == "shelf" and single.data["group"]["member_count"] == 2


@pytest.mark.anyio
async def test_list_groups_counts_unusable_files_and_reports_not_found(tmp_path):
    write_group_file(tmp_path, "good", [{"device": "desk"}])
    write_raw(stored_group_path(tmp_path, "future"), json.dumps({"format_version": 7}))
    write_raw(stored_group_path(tmp_path, "broken"), "{")
    before = stored_group_path(tmp_path, "future").read_bytes()
    async with open_fleet(tmp_path, three()) as resources:
        outcome = await call(resources, "wled_list_groups")
        missing = await call(resources, "wled_list_groups", group_id="absent")
        newer = await call(resources, "wled_list_groups", group_id="future")
    assert [g["id"] for g in outcome.data["groups"]] == ["good"]
    assert outcome.data["invalid_count"] == 2
    assert error_of(missing)["code"] == "VALIDATION_ERROR" and "No group" in missing.error.message
    assert error_of(newer)["code"] == "VALIDATION_ERROR"
    assert stored_group_path(tmp_path, "future").read_bytes() == before


@pytest.mark.anyio
async def test_delete_group_dry_run_delete_and_missing(tmp_path):
    async with open_fleet(tmp_path, three()) as resources:
        await stored_group(resources, "shelf", "desk")
        dry = await call(resources, "wled_delete_group", group_id="shelf", dry_run=True)
        assert dry.ok and dry.dry_run and dry.data["removed"] is False
        assert stored_group_path(tmp_path, "shelf").exists()
        done = await call(resources, "wled_delete_group", group_id="shelf")
        assert done.ok and done.data["removed"] is True
        assert done.data["deleted"]["members"] == [{"device": "desk"}]
        assert not stored_group_path(tmp_path, "shelf").exists()
        again = await call(resources, "wled_delete_group", group_id="shelf")
        assert error_of(again)["code"] == "VALIDATION_ERROR"


@pytest.mark.anyio
async def test_a_group_file_of_a_newer_version_is_not_replaced_or_deleted(tmp_path):
    path = stored_group_path(tmp_path, "future")
    write_raw(path, json.dumps({"format": "wled-mcp.group", "format_version": 2, "id": "future"}))
    before = path.read_bytes()
    async with open_fleet(tmp_path, three()) as resources:
        for overwrite in (False, True):
            outcome = await call(
                resources,
                "wled_save_group",
                **group_arguments("future", "desk", overwrite=overwrite),
            )
            assert error_of(outcome)["code"] == "VALIDATION_ERROR"
            assert "group format_version 2" in outcome.error.message
        assert error_of(await call(resources, "wled_delete_group", group_id="future"))["code"]
    assert path.read_bytes() == before


@pytest.mark.anyio
async def test_an_unwritable_data_directory_is_a_not_attempted_storage_failure(tmp_path):
    fleet = three()
    async with open_fleet(tmp_path, fleet) as resources:
        (tmp_path / "groups").write_text("a file where the directory should be", encoding="utf-8")
        outcome = await call(resources, "wled_save_group", **group_arguments("g", "desk"))
    error = error_of(outcome)
    assert error["code"] == "STORAGE_FAILED" and error["write_retryable"] is False
    assert (outcome.application, outcome.verification) == ("not_attempted", "not_requested")
    assert fleet.calls == []


# ===================================================================== scenes (AC-17-02, -10)


@pytest.mark.anyio
async def test_save_scene_from_object_and_text_stores_one_canonical_file(tmp_path):
    fleet = three()
    async with open_fleet(tmp_path, fleet) as resources:
        await stored_group(resources, "shelf", ("shelf_left", [0]), ("shelf_right", [0]))
        as_object = await save_scene(resources, canonical_scene())
        path = stored_scene_path(tmp_path, "evening")
        first = path.read_bytes()
        as_text = await call(
            resources, "wled_save_scene", scene=json.dumps(canonical_scene()), overwrite=True
        )
    assert as_object.ok and as_text.ok and fleet.calls == []
    assert (as_object.application, as_object.verification) == ("not_attempted", "not_requested")
    assert as_object.data["scene"] == {
        "id": "evening",
        "name": "Evening",
        "description": canonical_scene()["description"],
        "target_count": 2,
    }
    assert path.read_bytes() == first
    assert as_text.data["replaced"] == canonical_scene()


@pytest.mark.anyio
async def test_save_scene_validates_references_and_expansion_before_writing(tmp_path):
    fleet = three()
    async with open_fleet(tmp_path, fleet) as resources:
        await stored_group(resources, "shelf", "shelf_left", "shelf_right")
        cases = {
            "unknown device": scene_document(device_target("not_configured")),
            "unknown group": scene_document(group_target("absent")),
            "same device twice": scene_document(device_target("desk"), device_target("desk")),
            "device overlaps group": scene_document(
                device_target("shelf_left"), group_target("shelf")
            ),
            "ids-less entry": scene_document({"group": "shelf", "segments": [{"on": True}]}),
        }
        for label, document in cases.items():
            outcome = await save_scene(resources, document)
            assert error_of(outcome)["code"] == "VALIDATION_ERROR", label
            assert not stored_scene_path(tmp_path, "evening").exists(), label
    assert fleet.calls == []


@pytest.mark.anyio
@pytest.mark.parametrize("version", [0, 2, 9999])
async def test_save_scene_rejects_other_versions_naming_integers(tmp_path, version):
    async with open_fleet(tmp_path, three()) as resources:
        outcome = await save_scene(resources, scene_document(format_version=version))
    assert error_of(outcome)["code"] == "VALIDATION_ERROR"
    assert f"scene format_version {version}" in outcome.error.message
    assert not stored_scene_path(tmp_path, "evening").exists()


@pytest.mark.anyio
async def test_save_scene_text_with_duplicate_keys_is_refused(tmp_path):
    text = json.dumps(scene_document()).replace('"id": "evening"', '"id": "x", "id": "evening"')
    async with open_fleet(tmp_path, three()) as resources:
        outcome = await call(resources, "wled_save_scene", scene=text)
    assert "strict JSON" in outcome.error.message
    assert not (tmp_path / "scenes").exists()


@pytest.mark.anyio
async def test_save_scene_overwrite_dry_run_and_stored_newer_version(tmp_path):
    async with open_fleet(tmp_path, three()) as resources:
        await stored_scene(resources, scene_document())
        path = stored_scene_path(tmp_path, "evening")
        before = path.read_bytes()
        changed = scene_document(name="Changed")
        refused = await save_scene(resources, changed)
        assert "overwrite=true" in refused.error.message and path.read_bytes() == before
        dry = await save_scene(resources, changed, overwrite=True, dry_run=True)
        assert dry.ok and dry.dry_run and dry.data["saved"] is False
        assert dry.data["replaced"]["name"] == "Evening scene" and path.read_bytes() == before
        done = await save_scene(resources, changed, overwrite=True)
        assert (
            done.data["saved"] is True and json.loads(path.read_text("utf-8"))["name"] == "Changed"
        )
        future = stored_scene_path(tmp_path, "future")
        write_raw(future, json.dumps(scene_document(id="future", format_version=2)))
        raw = future.read_bytes()
        outcome = await save_scene(resources, scene_document(id="future"), overwrite=True)
        assert "format_version 2" in outcome.error.message and future.read_bytes() == raw
        deleted = await call(resources, "wled_delete_scene", scene_id="future")
        assert error_of(deleted)["code"] == "VALIDATION_ERROR" and future.read_bytes() == raw


@pytest.mark.anyio
async def test_list_scenes_summaries_document_and_not_found(tmp_path):
    async with open_fleet(tmp_path, three()) as resources:
        await stored_group(resources, "shelf", ("shelf_left", [0]), ("shelf_right", [0]))
        await stored_scene(resources, canonical_scene())
        write_raw(stored_scene_path(tmp_path, "future"), json.dumps({"format_version": 3}))
        listing = await call(resources, "wled_list_scenes")
        one = await call(resources, "wled_list_scenes", scene_id="evening")
        missing = await call(resources, "wled_list_scenes", scene_id="absent")
    (summary,) = listing.data["scenes"]
    assert summary["id"] == "evening" and summary["target_count"] == 2
    assert summary["references"] == [{"device": "desk"}, {"group": "shelf"}]
    assert listing.data["invalid_count"] == 1 and listing.data["count"] == 1
    assert one.data["document"] == canonical_scene()
    assert error_of(missing)["code"] == "VALIDATION_ERROR" and "No scene" in missing.error.message


@pytest.mark.anyio
async def test_shareable_export_carries_no_inventory_identity(tmp_path):
    async with open_fleet(tmp_path, three()) as resources:
        await stored_group(resources, "shelf", ("shelf_left", [0]), ("shelf_right", [0]))
        await stored_scene(resources, canonical_scene())
        shared = await call(resources, "wled_list_scenes", scene_id="evening", shareable=True)
        kept = await call(
            resources, "wled_list_scenes", scene_id="evening", shareable=True, include_targets=True
        )
    document = shared.data["document"]
    assert document["placeholders"] == ["t1", "t2"]
    text = json.dumps(document).casefold()
    for secret in ("desk", "shelf", "invalid", "example", "http", "127.0", "192."):
        assert secret not in text, secret
    assert kept.data["document"] == canonical_scene()
    assert "placeholder" in shared.warnings[0]
    # The retained example is exactly this tool output.
    assert document == json.loads(EXAMPLE.read_text("utf-8"))


@pytest.mark.anyio
async def test_export_refuses_a_name_that_contains_a_configured_host(tmp_path):
    async with open_fleet(tmp_path, three()) as resources:
        await stored_scene(resources, scene_document(name="Shelf at desk.invalid"))
        for kwargs in ({"shareable": True}, {"shareable": True, "include_targets": True}):
            outcome = await call(resources, "wled_list_scenes", scene_id="evening", **kwargs)
            assert error_of(outcome)["code"] == "VALIDATION_ERROR"
            assert "'name'" in outcome.error.message and "desk.invalid" not in outcome.error.message
        plain = await call(resources, "wled_list_scenes", scene_id="evening")
        assert plain.ok, "the local document stays readable"


@pytest.mark.anyio
async def test_sharing_options_need_a_scene_and_a_shareable_export(tmp_path):
    async with open_fleet(tmp_path, three()) as resources:
        for kwargs in ({"shareable": True}, {"include_targets": True}):
            outcome = await call(resources, "wled_list_scenes", **kwargs)
            assert error_of(outcome)["code"] == "VALIDATION_ERROR"
        outcome = await call(resources, "wled_list_scenes", scene_id="x", include_targets=True)
        assert "shareable export only" in outcome.error.message


@pytest.mark.anyio
async def test_shared_scene_maps_back_through_target_map_and_round_trips(tmp_path):
    fleet = three()
    async with open_fleet(tmp_path, fleet) as resources:
        await stored_group(resources, "shelf", ("shelf_left", [0]), ("shelf_right", [0]))
        await stored_scene(resources, canonical_scene())
        shared = (
            await call(resources, "wled_list_scenes", scene_id="evening", shareable=True)
        ).data["document"]
        await call(resources, "wled_delete_scene", scene_id="evening")
        mapping = {"t1": {"device": "desk"}, "t2": {"group": "shelf"}}
        outcome = await save_scene(resources, shared, target_map=mapping)
        again = await call(resources, "wled_list_scenes", scene_id="evening")
    assert outcome.ok, outcome.error
    assert again.data["document"] == canonical_scene()
    assert fleet.calls == []


@pytest.mark.anyio
async def test_target_map_failures_write_nothing_all_or_nothing(tmp_path):
    async with open_fleet(tmp_path, three()) as resources:
        await stored_group(resources, "shelf", ("shelf_left", [0]), ("shelf_right", [0]))
        await stored_scene(resources, canonical_scene())
        shared = (
            await call(resources, "wled_list_scenes", scene_id="evening", shareable=True)
        ).data["document"]
        await call(resources, "wled_delete_scene", scene_id="evening")
        good = {"t1": {"device": "desk"}, "t2": {"group": "shelf"}}
        attempts = {
            "no map": None,
            "unmapped": {"t1": good["t1"]},
            "extra": {**good, "t9": good["t1"]},
            "wrong kind": {"t1": {"group": "shelf"}, "t2": good["t2"]},
            "unknown device": {"t1": {"device": "nowhere"}, "t2": good["t2"]},
            "unknown group": {"t1": good["t1"], "t2": {"group": "nowhere"}},
        }
        for label, mapping in attempts.items():
            outcome = await save_scene(resources, shared, target_map=mapping)
            assert error_of(outcome)["code"] == "VALIDATION_ERROR", label
            assert not stored_scene_path(tmp_path, "evening").exists(), label
        # A stored-form document refuses a target_map; a bad mapping value is a schema error.
        plain = await save_scene(resources, canonical_scene(), target_map=good)
        assert "placeholders only" in plain.error.message
        with pytest.raises(ValidationError):
            await save_scene(resources, shared, target_map={"t1": {"device": "a", "group": "b"}})
        with pytest.raises(ValidationError):
            await save_scene(resources, shared, target_map={"t1": {}})


# ===================================================================== plan (AC-17-04, -05)


def snapshot(fleet: SceneFleet) -> dict[str, Any]:
    return {host: copy.deepcopy(fake.state()) for host, fake in fleet.devices.items()}


async def planned(resources: Any, scene_id: str = "evening", **kwargs: Any) -> Any:
    return await call(resources, "wled_plan_scene", scene_id=scene_id, **kwargs)


@pytest.mark.anyio
async def test_plan_resolves_targets_names_and_plans_without_any_write(tmp_path):
    fleet = three()
    before = snapshot(fleet)
    document = scene_document(
        device_target(
            "desk",
            master={"on": True, "brightness": 90, "transition_ms": 500},
            segments=[{"ids": [0, 2], "effect_name": "wipe", "palette_name": "Party", "speed": 10}],
        ),
        {
            "group": "shelf",
            "segments": [{"effect_name": "Wipe", "colors": [[255, 120, 20]]}],
        },
    )
    async with open_fleet(tmp_path, fleet) as resources:
        await stored_group(resources, "shelf", ("shelf_left", [0, 5]))
        await stored_scene(resources, document)
        outcome = await planned(resources)
    assert outcome.ok, outcome.error
    assert (outcome.application, outcome.verification, outcome.dry_run) == (
        "not_attempted",
        "not_requested",
        True,
    )
    assert fleet.post_count() == 0 and snapshot(fleet) == before
    assert all(fake.posts == [] for fake in fleet.devices.values())
    data = outcome.data
    assert (data["mode"], data["max_concurrency"], data["device_count"]) == ("strict", 4, 2)
    assert data["would_write"] == ["desk", "shelf_left"] and data["skipped"] == []
    assert data["summary"] == {"devices": 2, "preflight_ok": 2, "preflight_failed": 0}
    desk, left = data["targets"]
    assert (desk["device_id"], desk["origin"], desk["target_index"]) == ("desk", "device", 1)
    assert (left["device_id"], left["origin"]) == ("shelf_left", "group:shelf/member:1")
    assert desk["preflight"] == left["preflight"] == "ok" and desk["reachable"] is True
    # Names resolve per device; the same name is a different ID on the second device.
    assert desk["resolved"] == [
        {"segments": [0, 2], "field": "effect", "name": "wipe", "id": 3},
        {"segments": [0, 2], "field": "palette", "name": "Party", "id": 2},
    ]
    assert left["resolved"] == [{"segments": [0, 5], "field": "effect", "name": "Wipe", "id": 1}]
    # The plan is the output of the real planners.
    assert desk["master"]["payload"] == {"on": True, "bri": 90, "tt": 5}
    assert [p["id"] for p in desk["segments"]["payload"]["seg"]] == [0, 2]
    assert desk["segments"]["payload"]["seg"][0]["fx"] == 3
    assert left["segments"]["payload"]["seg"][0]["fx"] == 1
    assert any("not a reservation" in warning for warning in outcome.warnings)
    assert any("not atomic" in note for note in data["notes"])


@pytest.mark.anyio
async def test_plan_equals_the_single_device_planners_for_the_same_request(tmp_path):
    fleet = three()
    document = scene_document(
        device_target(
            "desk",
            master={"brightness": 40},
            segments=[{"ids": [2], "speed": 7, "colors": [[1, 2, 3]], "effect_id": 1}],
        )
    )
    async with open_fleet(tmp_path, fleet) as resources:
        await stored_scene(resources, document)
        outcome = await planned(resources)
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
    (desk,) = outcome.data["targets"]
    assert desk["master"]["plan"] == master.data["plan"]
    assert desk["master"]["payload"] == master.data["payload"]
    assert desk["segments"]["plan"] == patch.data["plan"]
    assert desk["segments"]["payload"] == patch.data["payload"]
    assert desk["segments"]["postconditions"] == patch.data["postconditions"]


@pytest.mark.anyio
async def test_numeric_ids_are_used_as_given_with_a_portability_warning(tmp_path):
    fleet = three()
    document = scene_document(
        device_target("desk", segments=[{"ids": [0], "effect_id": 3, "palette_id": 1}])
    )
    async with open_fleet(tmp_path, fleet) as resources:
        await stored_scene(resources, document)
        outcome = await planned(resources)
    (desk,) = outcome.data["targets"]
    assert desk["resolved"] == [] and desk["segments"]["payload"]["seg"][0]["fx"] == 3
    joined = " ".join(desk["warnings"])
    assert "numeric effect_id" in joined and "numeric palette_id" in joined
    assert "specific to a device and firmware" in joined


@pytest.mark.anyio
async def test_an_ambiguous_name_is_refused_per_device_with_bounded_candidates(tmp_path):
    fleet = three()
    document = scene_document(
        device_target("desk", segments=[{"ids": [0], "effect_name": "WIPE"}]),
        device_target("shelf_right", segments=[{"ids": [0], "effect_name": "WIPE"}]),
    )
    async with open_fleet(tmp_path, fleet) as resources:
        await stored_scene(resources, document)
        strict = await planned(resources)
        best = await planned(resources, mode="best_effort")
    assert error_of(strict)["code"] == "AMBIGUOUS_NAME"
    assert "'shelf_right'" in strict.error.message
    right = target_of(strict, "shelf_right")
    assert right["preflight"] == "failed" and right["error"]["code"] == "AMBIGUOUS_NAME"
    assert right["candidates"] == [{"id": 1, "name": "Wipe"}, {"id": 2, "name": "wipe"}]
    assert right["candidate_total"] == 2 and right["segments"] is None
    assert target_of(strict, "desk")["preflight"] == "ok"
    assert strict.data["would_write"] == [] and strict.data["skipped"] == []
    assert (
        best.ok and best.data["would_write"] == ["desk"] and best.data["skipped"] == ["shelf_right"]
    )
    assert fleet.post_count() == 0


@pytest.mark.anyio
async def test_an_unknown_name_is_a_per_device_validation_error(tmp_path):
    fleet = three()
    document = scene_document(
        device_target("desk", segments=[{"ids": [0], "palette_name": "No such palette"}])
    )
    async with open_fleet(tmp_path, fleet) as resources:
        await stored_scene(resources, document)
        outcome = await planned(resources)
    assert error_of(outcome)["code"] == "VALIDATION_ERROR"
    assert "No palette matches" in target_of(outcome, "desk")["error"]["message"]
    assert fleet.post_count() == 0


REFUSALS: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {
    # label: (scene segment entry, the equivalent wled_patch_segments segment)
    "missing segment": ({"ids": [9], "speed": 5}, {"id": 9, "speed": 5}),
    "effect out of range": ({"ids": [0], "effect_id": 99}, {"id": 0, "effect_id": 99}),
    "palette out of range": ({"ids": [0], "palette_id": 99}, {"id": 0, "palette_id": 99}),
    "rgbw on rgb": ({"ids": [0], "colors": [[1, 2, 3, 4]]}, {"id": 0, "colors": [[1, 2, 3, 4]]}),
    "cct without evidence": ({"ids": [0], "cct": 10}, {"id": 0, "cct": 10}),
    "custom without field": ({"ids": [0], "custom1": 5}, {"id": 0, "custom1": 5}),
}


@pytest.mark.anyio
@pytest.mark.parametrize("label", list(REFUSALS))
async def test_planner_refusals_equal_the_single_device_tool_refusals(tmp_path, label):
    entry, equivalent = REFUSALS[label]
    # The custom parameters are refused where the readback lacks their keys (no WLED 16 keys).
    desk = strip(v16=False) if label == "custom without field" else strip()
    fleet = SceneFleet(desk=desk, other=strip())
    document = scene_document(
        device_target("desk", segments=[entry]), device_target("other", master={"on": False})
    )
    async with open_fleet(tmp_path, fleet) as resources:
        await stored_scene(resources, document)
        outcome = await planned(resources)
        direct = await call(
            resources, "wled_patch_segments", device_id="desk", segments=[equivalent], dry_run=True
        )
    assert not direct.ok
    desk = target_of(outcome, "desk")
    assert desk["preflight"] == "failed"
    assert desk["error"]["code"] == direct.error.code
    assert desk["error"]["message"] == direct.error.message
    assert target_of(outcome, "other")["preflight"] == "ok"
    assert error_of(outcome)["code"] == direct.error.code
    assert fleet.post_count() == 0


@pytest.mark.anyio
async def test_cct_is_planned_where_the_range_reports_the_capability(tmp_path):
    fleet = SceneFleet(desk=strip(buses=[(0, 60, 5)]), plain=strip())
    document = scene_document(
        device_target("desk", segments=[{"ids": [0], "cct": 10}]),
        device_target("plain", segments=[{"ids": [0], "cct": 10}]),
    )
    async with open_fleet(tmp_path, fleet) as resources:
        await stored_scene(resources, document)
        outcome = await planned(resources, mode="best_effort")
    assert target_of(outcome, "desk")["preflight"] == "ok"
    evidence = target_of(outcome, "desk")["segments"]["plan"]["capability_evidence"]
    assert evidence, "the plan shows the capability evidence of the field"
    assert target_of(outcome, "plain")["error"]["code"] == "UNSUPPORTED_CAPABILITY"
    assert outcome.data["would_write"] == ["desk"]


@pytest.mark.anyio
async def test_an_offline_device_is_reported_and_the_others_are_still_planned(tmp_path):
    fleet = three()
    fleet.devices["shelf_left.invalid"].unreachable = True
    document = scene_document(
        device_target("desk"), device_target("shelf_left"), device_target("shelf_right")
    )
    async with open_fleet(tmp_path, fleet) as resources:
        await stored_scene(resources, document)
        strict = await planned(resources)
        best = await planned(resources, mode="best_effort")
    assert error_of(strict)["code"] == "UNREACHABLE"
    left = target_of(strict, "shelf_left")
    assert left["preflight"] == "failed" and left["reachable"] is False
    assert left["master"] is None
    assert [t["preflight"] for t in strict.data["targets"]] == ["ok", "failed", "ok"]
    assert (strict.application, strict.verification, strict.dry_run) == (
        "not_attempted",
        "not_requested",
        True,
    )
    assert strict.data["would_write"] == []
    assert best.ok and best.data["would_write"] == ["desk", "shelf_right"]
    assert best.data["skipped"] == ["shelf_left"]
    assert fleet.post_count() == 0


@pytest.mark.anyio
async def test_a_timeout_is_a_per_device_entry_not_a_failed_plan(tmp_path):
    fleet = three()
    fleet.devices["desk.invalid"].delay = 1.0
    async with open_fleet(tmp_path, fleet, timeout=0.2) as resources:
        await stored_scene(
            resources, scene_document(device_target("desk"), device_target("shelf_left"))
        )
        outcome = await planned(resources, mode="best_effort")
    assert target_of(outcome, "desk")["error"]["code"] == "TIMEOUT"
    assert target_of(outcome, "desk")["reachable"] is False
    assert outcome.ok and outcome.data["would_write"] == ["shelf_left"]


@pytest.mark.anyio
async def test_a_device_that_left_the_inventory_fails_preflight_without_device_io(tmp_path):
    fleet = three()
    write_group_file(tmp_path, "shelf", [{"device": "shelf_left"}, {"device": "removed_strip"}])
    write_scene_file(tmp_path, scene_document(group_target("shelf")))
    async with open_fleet(tmp_path, fleet) as resources:
        outcome = await planned(resources, mode="best_effort")
    gone = target_of(outcome, "removed_strip")
    assert gone["error"]["code"] == "UNKNOWN_DEVICE" and gone["reachable"] is None
    assert "removed_strip.invalid" not in fleet.hosts_called()
    assert outcome.ok and outcome.data["would_write"] == ["shelf_left"]


@pytest.mark.anyio
async def test_a_duplicate_device_refuses_the_whole_plan_before_any_device_io(tmp_path):
    fleet = three()
    write_group_file(tmp_path, "shelf", [{"device": "desk"}, {"device": "shelf_left"}])
    write_scene_file(tmp_path, scene_document(device_target("desk"), group_target("shelf")))
    async with open_fleet(tmp_path, fleet) as resources:
        outcome = await planned(resources)
    message = error_of(outcome)["message"]
    assert outcome.error.code == "VALIDATION_ERROR" and "'desk'" in message
    assert "target 1 (device)" in message and "target 2 (group:shelf/member:1)" in message
    assert fleet.calls == [] and outcome.dry_run is True
    assert (outcome.application, outcome.verification) == ("not_attempted", "not_requested")


@pytest.mark.anyio
async def test_a_group_changed_after_saving_is_rechecked_at_plan_time(tmp_path):
    fleet = three()
    async with open_fleet(tmp_path, fleet) as resources:
        await stored_group(resources, "shelf", "shelf_left")
        await stored_scene(resources, scene_document(device_target("desk"), group_target("shelf")))
        await call(
            resources,
            "wled_save_group",
            **group_arguments("shelf", "desk", "shelf_left", overwrite=True),
        )
        outcome = await planned(resources)
        await call(resources, "wled_delete_group", group_id="shelf")
        gone = await planned(resources)
    assert "targeted twice" in error_of(outcome)["message"]
    assert (
        "'shelf'" in error_of(gone)["message"]
        and "not stored" in gone.error.message
        or ("No group" in gone.error.message)
    )
    assert fleet.calls == []


@pytest.mark.anyio
async def test_plan_of_a_missing_or_newer_version_scene_fails_before_device_io(tmp_path):
    fleet = three()
    write_raw(
        stored_scene_path(tmp_path, "future"),
        json.dumps(scene_document(id="future", format_version=4)),
    )
    async with open_fleet(tmp_path, fleet) as resources:
        missing = await planned(resources, "absent")
        newer = await planned(resources, "future")
    assert "No scene" in error_of(missing)["message"]
    assert "scene format_version 4" in error_of(newer)["message"]
    assert fleet.calls == [] and missing.dry_run and newer.dry_run


@pytest.mark.anyio
async def test_mode_defaults_to_strict_and_blocks_every_device_on_one_failure(tmp_path):
    fleet = three()
    document = scene_document(
        device_target("desk"), device_target("shelf_left", segments=[{"ids": [9], "speed": 1}])
    )
    async with open_fleet(tmp_path, fleet) as resources:
        await stored_scene(resources, document)
        default = await planned(resources)
        strict = await planned(resources, mode="strict")
        best = await planned(resources, mode="best_effort")
        with pytest.raises(ValidationError):
            await planned(resources, mode="eager")
    assert default.data["mode"] == "strict" and default.model_dump() == strict.model_dump()
    assert not default.ok and default.data["would_write"] == []
    assert best.ok and best.data["would_write"] == ["desk"]
    # Nothing was written in any mode, and a refusal names the first failing device.
    assert "'shelf_left'" in default.error.message and fleet.post_count() == 0


@pytest.mark.anyio
async def test_best_effort_with_no_device_passing_is_refused_with_the_first_device_code(tmp_path):
    fleet = three()
    fleet.devices["desk.invalid"].unreachable = True
    document = scene_document(
        device_target("desk"), device_target("shelf_left", segments=[{"ids": [9], "speed": 1}])
    )
    async with open_fleet(tmp_path, fleet) as resources:
        await stored_scene(resources, document)
        outcome = await planned(resources, mode="best_effort")
    assert error_of(outcome)["code"] == "UNREACHABLE" and outcome.data["would_write"] == []
    assert outcome.data["summary"]["preflight_failed"] == 2


# ============================================================ ordering and concurrency


def crowd(count: int) -> SceneFleet:
    return SceneFleet(**{f"strip{n}": strip() for n in range(count)})


@pytest.mark.anyio
async def test_at_most_four_devices_are_in_flight_and_results_keep_expansion_order(tmp_path):
    fleet = crowd(8)
    for number, fake in enumerate(fleet.devices.values()):
        fake.delay = 0.03 - number * 0.003  # later devices finish sooner
    document = scene_document(*[device_target(f"strip{n}") for n in range(8)])
    async with open_fleet(tmp_path, fleet) as resources:
        await stored_scene(resources, document)
        outcome = await planned(resources)
    assert outcome.ok and fleet.post_count() == 0
    assert [t["device_id"] for t in outcome.data["targets"]] == [f"strip{n}" for n in range(8)]
    assert fleet.max_in_flight == MAX_CONCURRENCY == 4
    assert outcome.data["max_concurrency"] == 4


@pytest.mark.anyio
async def test_fewer_devices_than_the_limit_run_all_at_once(tmp_path):
    fleet = crowd(3)
    for fake in fleet.devices.values():
        fake.delay = 0.02
    async with open_fleet(tmp_path, fleet) as resources:
        await stored_scene(
            resources, scene_document(*[device_target(f"strip{n}") for n in range(3)])
        )
        outcome = await planned(resources)
    assert outcome.ok and fleet.max_in_flight == 3


@pytest.mark.anyio
async def test_sixteen_devices_plan_and_seventeen_are_refused_before_io(tmp_path):
    fleet = crowd(MAX_EXPANDED_DEVICES)
    write_group_file(
        tmp_path, "all", [{"device": f"strip{n}"} for n in range(MAX_EXPANDED_DEVICES)]
    )
    write_scene_file(tmp_path, scene_document(group_target("all")))
    async with open_fleet(tmp_path, fleet) as resources:
        outcome = await planned(resources)
        assert outcome.ok and len(outcome.data["targets"]) == 16 and fleet.post_count() == 0
        write_scene_file(
            tmp_path, scene_document(group_target("all"), device_target("extra"), id="over")
        )
        calls_before = len(fleet.calls)
        over = await planned(resources, "over")
    assert "more than 16 devices" in error_of(over)["message"]
    assert len(fleet.calls) == calls_before


@pytest.mark.anyio
async def test_the_plan_reads_under_the_existing_per_device_lock(tmp_path):
    fleet = three()
    document = scene_document(device_target("desk"), device_target("shelf_left"))
    async with open_fleet(tmp_path, fleet, timeout=0.3) as resources:
        await stored_scene(resources, document)
        async with resources.locks["desk"]:
            outcome = await planned(resources, mode="best_effort")
    assert target_of(outcome, "desk")["error"]["code"] == "TIMEOUT"
    assert target_of(outcome, "shelf_left")["preflight"] == "ok"
    assert "desk.invalid" not in fleet.hosts_called(), "no request was made while the lock was held"


@pytest.mark.anyio
async def test_plan_requests_are_reads_only_and_never_a_post(tmp_path):
    fleet = three()
    write_group_file(tmp_path, "shelf", [{"device": "shelf_left"}, {"device": "shelf_right"}])
    document = canonical_scene()
    document["targets"][1]["segments"][0]["ids"] = [0]
    document["targets"][1]["segments"][0]["effect_name"] = "Solid"
    write_scene_file(tmp_path, document)
    async with open_fleet(tmp_path, fleet) as resources:
        for mode in ("strict", "best_effort"):
            await planned(resources, mode=mode)
        await call(resources, "wled_list_scenes")
        await call(resources, "wled_list_scenes", scene_id="evening", shareable=True)
        await call(resources, "wled_list_groups")
    assert fleet.calls and {method for method, _h, _p in fleet.calls} == {"GET"}
    assert fleet.post_count() == 0


@pytest.mark.anyio
async def test_the_plan_does_not_change_live_state_or_cancel_on_a_cancelled_scope(tmp_path):
    fleet = three()
    before = snapshot(fleet)
    async with open_fleet(tmp_path, fleet) as resources:
        await stored_scene(resources, scene_document(device_target("desk")))
        with anyio.move_on_after(0.0):
            await planned(resources)
        again = await planned(resources)
    assert again.ok and snapshot(fleet) == before and fleet.post_count() == 0


@pytest.mark.anyio
async def test_a_segment_of_the_fake_device_is_untouched_after_a_plan(tmp_path):
    fleet = three()
    document = scene_document(device_target("desk", segments=[{"ids": [0], "speed": 5}]))
    async with open_fleet(tmp_path, fleet) as resources:
        await stored_scene(resources, document)
        await planned(resources)
    assert segments_of(fleet.devices["desk.invalid"])[0]["sx"] == 128


def test_support_fleet_rejects_nothing_silently():
    fleet = SceneFleet(desk=SceneDevice())
    assert fleet.devices.keys() == {"desk.invalid"} and fleet.post_count() == 0
