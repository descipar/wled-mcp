"""Persistent preset tools (issue #9): T11 (list/read/activate/allocate/classify), T12
(snapshot before overwrite/delete, backup failure sends nothing) and T13 (bounded readback
verifies persistence, never the HTTP acknowledgment; uncertain outcomes are not replayed).

Mock transport and ``tmp_path`` only. No LAN access, no real device, no real sleep beyond
millisecond poll intervals.
"""

from __future__ import annotations

import copy
import json
import logging
import os
from pathlib import Path
from typing import Any

import anyio
import httpx2 as httpx
import pytest
from pydantic import ValidationError

from tests.preset_support import PresetDevice, PresetFleet, playlist_entry, state_entry
from tests.state_catalog_support import make_state
from tests.test_inventory_client import config, device
from tests.tool_contract import expected_names
from wled_mcp.models import Outcome
from wled_mcp.operations import build_operations
from wled_mcp.presets import (
    ActivatePresetRequest,
    DeletePresetRequest,
    GetPresetRequest,
    SavePresetRequest,
    classify,
    parse_store,
)
from wled_mcp.resources import Resources

DESK = "desk.invalid"
LAMP = "lamp.invalid"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def fleet_of(desk: PresetDevice | None = None, **others: PresetDevice) -> PresetFleet:
    fleet = PresetFleet()
    fleet.add(DESK, desk if desk is not None else PresetDevice())
    for host, dev in others.items():
        fleet.add(host.replace("__", "."), dev)
    return fleet


def open_resources(tmp_path, fleet, devices=None, **settings):
    settings.setdefault("operation_timeout_seconds", 1.0)
    resources = Resources(config(tmp_path, devices=devices, **settings), fleet.transport())
    resources.poll_interval_seconds = 0.005
    return resources


async def call(resources, tool: str, **arguments):
    arguments.setdefault("device_id", "desk")
    operation = {op.name: op for op in build_operations(resources)}[tool]
    return await operation.execute(operation.request_model.model_validate(arguments).model_dump())


def snapshot_files(tmp_path, device_id="desk") -> list[str]:
    directory = tmp_path / "backups" / device_id
    return sorted(p.name for p in directory.iterdir()) if directory.exists() else []


def desk_with(store: dict[str, Any], **kwargs: Any) -> PresetDevice:
    return PresetDevice(store={"0": {}, **store}, **kwargs)


# ============================================================ requests and registry


@pytest.mark.parametrize(
    "arguments",
    [
        {"preset_id": 0},
        {"preset_id": 251},
        {"preset_id": 255},
        {"preset_id": True},
        {"preset_id": "3"},
        {"preset_id": 3.0},
        {"preset_id": 3, "state": {"on": True}},
        {"preset_id": 3, "api": "T=1"},
    ],
)
def test_preset_id_requests_are_strict(arguments):
    for model in (GetPresetRequest, ActivatePresetRequest, DeletePresetRequest):
        with pytest.raises(ValidationError):
            model.model_validate({"device_id": "desk", **arguments})
    with pytest.raises(ValidationError):
        SavePresetRequest.model_validate({"device_id": "desk", "name": "x", **arguments})


@pytest.mark.parametrize(
    "name",
    ["", "   ", "a\x00b", "line\nbreak", "tab\there", "\x7f", "x" * 33, "é" * 17, "\ud800"],
)
def test_names_rejected_without_truncation(name):
    with pytest.raises(ValidationError):
        SavePresetRequest.model_validate({"device_id": "desk", "name": name})


@pytest.mark.parametrize("name", ["x", "x" * 32, "é" * 16, " padded ", "Zażółć"])
def test_names_accepted_unchanged(name):
    assert SavePresetRequest.model_validate({"device_id": "desk", "name": name}).name == name


def test_overwrite_requires_explicit_id_and_no_supplied_state_input():
    with pytest.raises(ValidationError):
        SavePresetRequest.model_validate({"device_id": "desk", "name": "x", "overwrite": True})
    with pytest.raises(ValidationError):
        SavePresetRequest.model_validate({"device_id": "desk", "name": "x", "state": {"on": True}})
    assert "state" not in SavePresetRequest.model_json_schema()["properties"]


@pytest.mark.anyio
async def test_registry_preset_tools_are_strict(tmp_path):
    # Order and annotations are checked against tests/tool_contract.py centrally; the
    # restore tool of #18 is one of the preset tools checked here.
    async with open_resources(tmp_path, fleet_of()) as resources:
        operations = build_operations(resources)
        registered = {o.name: o for o in operations}
        preset_tools = [name for name in expected_names() if "preset" in name]
        assert preset_tools  # the contract names the preset tools
        for name in preset_tools:
            schema = registered[name].request_model.model_json_schema()
            assert schema["additionalProperties"] is False


# ================================================================ T11 list and read


@pytest.mark.anyio
async def test_list_classifies_and_excludes_reserved_empty_and_malformed(tmp_path):
    desk = desk_with(
        {
            "1": state_entry("One"),
            "2": None,
            "3": {},
            "4": playlist_entry([1]),
            "5": {"win": "T=1", "n": "Command"},
            "6": {"vendor_extension": {"x": 1}},
            "7": "not an object",
            "251": state_entry("Reserved"),
            "254": state_entry("Reserved"),
            "255": state_entry("Temporary"),
            "abc": state_entry("Bad key"),
            "07": state_entry("Non canonical"),
        }
    )
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_list_presets")
    assert outcome.ok and (outcome.application, outcome.verification) == (
        "not_attempted",
        "not_requested",
    )
    presets = outcome.data["presets"]
    assert [(p["id"], p["type"]) for p in presets] == [
        (1, "state"),
        (4, "playlist"),
        (5, "api-command"),
        (6, "unknown"),
        (7, "unknown"),
    ]
    assert presets[0]["name"] == "One" and presets[3]["name"] is None
    assert presets[4].get("malformed") is True and "malformed" not in presets[0]
    assert outcome.data["count"] == 5
    assert outcome.data["freshness"]["source"] == "device"
    assert any("unrecognized" in w for w in outcome.warnings)
    assert "Bad key" not in str(outcome.model_dump())  # no raw bodies in the list
    assert desk.posts == []


@pytest.mark.anyio
async def test_get_returns_exact_object_and_not_found_for_empty_slots(tmp_path):
    original = state_entry("Scene", vendor_extension={"opaque": [1, 1.5, None]}, ql="A")
    desk = desk_with({"3": original, "4": None, "5": {}, "6": {"win": "&T=1"}})
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        got = await call(resources, "wled_get_preset", preset_id=3)
        assert got.ok and got.data["preset"] == original
        assert list(got.data["preset"]) == list(original)  # key order untouched
        assert (got.data["type"], got.data["name"], got.data["preset_id"]) == (
            "unknown",
            "Scene",
            3,
        )  # vendor key: not plain state
        command = await call(resources, "wled_get_preset", preset_id=6)
        assert command.data["type"] == "api-command"
        for empty in (4, 5, 9):
            missing = await call(resources, "wled_get_preset", preset_id=empty)
            assert not missing.ok and missing.error.code == "PRESET_NOT_FOUND"
            assert missing.application == "not_attempted"
    assert desk.posts == []


@pytest.mark.anyio
async def test_every_read_is_a_fresh_uncached_get(tmp_path):
    desk = desk_with({"1": state_entry()})
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        await call(resources, "wled_list_presets")
        await call(resources, "wled_list_presets")
        await call(resources, "wled_get_preset", preset_id=1)
    assert desk.get_counts["presets.json"] == 3
    assert all(h.get("cache-control") == "no-cache" for h in desk.presets_get_headers)


@pytest.mark.anyio
async def test_read_failure_mapping_without_leaks(tmp_path):
    desk = desk_with({})
    desk.presets_get_failure = lambda _n: httpx.ConnectError("http://secret.invalid/x")
    async with open_resources(tmp_path, fleet_of(desk), read_retries=0) as resources:
        outcome = await call(resources, "wled_list_presets")
        unknown = await call(resources, "wled_list_presets", device_id="nope")
    assert outcome.error.code == "UNREACHABLE" and "secret" not in outcome.model_dump_json()
    assert unknown.error.code == "UNKNOWN_DEVICE" and unknown.device_id is None


# ============================================================== T11 activation


@pytest.mark.anyio
async def test_activate_state_preset_posts_only_ps_and_never_touches_storage(tmp_path):
    desk = desk_with({"1": state_entry("A"), "3": state_entry("C")}, state=None)
    before = copy.deepcopy(desk.store)
    desk.apply_delay = 2
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_activate_preset", preset_id=3)
    assert outcome.ok and (outcome.application, outcome.verification) == ("applied", "verified")
    assert desk.posts == [{"ps": 3}]
    assert desk.store == before and desk.state["ps"] == 3
    assert outcome.data["type"] == "state" and snapshot_files(tmp_path) == []


@pytest.mark.anyio
async def test_activate_playlist_of_state_presets_verifies_playlist_marker(tmp_path):
    desk = desk_with({"1": state_entry("A"), "2": state_entry("B"), "4": playlist_entry([1, 2])})
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_activate_preset", preset_id=4)
    assert outcome.ok and outcome.data["type"] == "playlist"
    assert desk.posts == [{"ps": 4}] and desk.state["pl"] == 4


@pytest.mark.anyio
@pytest.mark.parametrize(
    "store",
    [
        {"3": {"win": "T=1&A=10"}},
        {"3": {"vendor_extension": 1}},
        {"3": {"on": True, "psave": 9}},
        {"3": {"on": True, "rb": True}},
        {"3": {"on": True, "pdel": 2}},
        {"3": "text"},
        {"3": playlist_entry([1, 9]), "1": state_entry()},  # member 9 missing
        {"3": playlist_entry([1, 2]), "1": state_entry(), "2": {"win": "T=1"}},
        {"3": playlist_entry([1, 2]), "1": state_entry(), "2": playlist_entry([1])},
        {"3": playlist_entry([1, 2]), "1": state_entry(), "2": {"vendor": 1}},
        {"3": {"playlist": {"ps": []}, "on": True}},
    ],
)
async def test_activation_of_unsafe_entries_is_refused_with_zero_posts(tmp_path, store):
    desk = desk_with(store)
    before = copy.deepcopy(desk.store)
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_activate_preset", preset_id=3)
    assert not outcome.ok and outcome.error.code == "UNSUPPORTED_CAPABILITY"
    assert outcome.application == "not_attempted" and desk.posts == []
    assert desk.store == before


@pytest.mark.anyio
async def test_activate_absent_and_dry_run_send_nothing(tmp_path):
    desk = desk_with({"1": state_entry()})
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        missing = await call(resources, "wled_activate_preset", preset_id=2)
        dry = await call(resources, "wled_activate_preset", preset_id=1, dry_run=True)
    assert missing.error.code == "PRESET_NOT_FOUND" and desk.posts == []
    assert dry.ok and dry.dry_run and dry.data["payload"] == {"ps": 1}


@pytest.mark.anyio
async def test_activate_unobservable_is_reported_not_replayed(tmp_path):
    desk = desk_with({"1": state_entry()})
    desk.apply_delay = 10**6
    async with open_resources(tmp_path, fleet_of(desk), operation_timeout_seconds=0.8) as resources:
        outcome = await call(resources, "wled_activate_preset", preset_id=1)
    assert outcome.error.code == "VERIFICATION_MISMATCH"
    assert (outcome.application, outcome.verification) == ("unknown", "mismatch")
    assert len(desk.posts) == 1 and outcome.data["no_replay"] is True


@pytest.mark.anyio
async def test_activate_already_active_warns_that_firmware_ignores_it(tmp_path):
    state = None
    desk = desk_with({"1": state_entry()}, state=state)
    desk.state["ps"] = 1
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_activate_preset", preset_id=1)
    assert outcome.ok and any("already active" in w for w in outcome.warnings)


# ======================================================== T11 allocation and save


SAVE_CONTROLS = {"ib": True, "sb": True, "sc": False}


@pytest.mark.anyio
async def test_save_uses_lowest_free_id_and_sends_storage_controls_only(tmp_path):
    desk = desk_with({"1": state_entry(), "2": state_entry(), "4": state_entry()})
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_save_preset", name="Evening")
    assert outcome.ok and (outcome.application, outcome.verification) == ("applied", "verified")
    assert desk.posts == [{"psave": 3, "n": "Evening", **SAVE_CONTROLS}]
    assert desk.store["3"]["n"] == "Evening"
    assert outcome.data["preset_id"] == 3 and outcome.data["allocated"] is True
    assert outcome.data["overwrote"] is False and "backup_id" not in outcome.data
    assert any("asynchronous" in w for w in outcome.warnings)
    assert snapshot_files(tmp_path) == [] and not (tmp_path / "backups").exists()
    assert desk.state["ps"] == -1  # nothing was activated


@pytest.mark.anyio
async def test_save_explicit_free_id_and_overwrite_flag_on_free_id(tmp_path):
    desk = desk_with({"1": state_entry()})
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        first = await call(resources, "wled_save_preset", name="Seven", preset_id=7)
        second = await call(resources, "wled_save_preset", name="Nine", preset_id=9, overwrite=True)
    assert first.ok and first.data["preset_id"] == 7 and first.data["allocated"] is False
    assert second.ok and second.data["overwrote"] is False
    assert snapshot_files(tmp_path) == []


@pytest.mark.anyio
async def test_save_into_empty_markers_counts_as_free(tmp_path):
    desk = desk_with({"1": state_entry(), "2": None, "3": {}})
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_save_preset", name="Gap")
    assert outcome.ok and outcome.data["preset_id"] == 2


@pytest.mark.anyio
async def test_occupied_explicit_id_without_overwrite_conflicts_with_zero_posts(tmp_path):
    desk = desk_with({"5": state_entry("Mine")})
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_save_preset", name="New", preset_id=5)
    assert outcome.error.code == "PRESET_CONFLICT" and outcome.application == "not_attempted"
    assert desk.posts == [] and desk.store["5"]["n"] == "Mine" and snapshot_files(tmp_path) == []


@pytest.mark.anyio
async def test_exhausted_id_space_fails_without_writing(tmp_path):
    desk = desk_with({str(i): state_entry(f"P{i}") for i in range(1, 251)})
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_save_preset", name="No room")
    assert outcome.error.code == "PRESET_CONFLICT" and "free" in outcome.error.message
    assert desk.posts == [] and snapshot_files(tmp_path) == []


@pytest.mark.anyio
async def test_malformed_store_fails_closed_for_save_and_delete(tmp_path):
    desk = desk_with({"1": state_entry(), "x1": state_entry()})
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        saved = await call(resources, "wled_save_preset", name="n")
        deleted = await call(resources, "wled_delete_preset", preset_id=1)
    for outcome in (saved, deleted):
        assert outcome.error.code == "INVALID_RESPONSE" and outcome.application == "not_attempted"
    assert desk.posts == [] and snapshot_files(tmp_path) == []


@pytest.mark.anyio
async def test_collision_after_planning_is_a_conflict_not_a_reallocation(tmp_path):
    desk = desk_with({})

    def occupy(device: PresetDevice) -> None:
        if device.get_counts["presets.json"] == 2:  # the recheck right before dispatch
            device.store["1"] = state_entry("Foreign")

    desk.before_presets_get = occupy
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_save_preset", name="Mine")
    assert outcome.error.code == "PRESET_CONFLICT" and outcome.application == "not_attempted"
    assert desk.posts == [] and desk.store["1"]["n"] == "Foreign"


@pytest.mark.anyio
async def test_playlist_replacement_is_rejected_without_snapshot(tmp_path):
    desk = desk_with({"2": state_entry(), "5": playlist_entry([2])})
    before = copy.deepcopy(desk.store)
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(
            resources, "wled_save_preset", name="Replace", preset_id=5, overwrite=True
        )
    assert outcome.error.code == "UNSUPPORTED_CAPABILITY" and outcome.application == "not_attempted"
    assert desk.posts == [] and desk.store == before and snapshot_files(tmp_path) == []


@pytest.mark.anyio
async def test_save_dry_run_is_read_only(tmp_path):
    desk = desk_with({"1": state_entry("Old")})
    before = copy.deepcopy(desk.store)
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        free = await call(resources, "wled_save_preset", name="Plan", dry_run=True)
        over = await call(
            resources, "wled_save_preset", name="Plan", preset_id=1, overwrite=True, dry_run=True
        )
    assert free.ok and free.dry_run and free.application == "not_attempted"
    assert free.data["plan"]["preset_id"] == 2 and free.data["plan"]["will_overwrite"] is False
    assert free.data["payload"] == {"psave": 2, "n": "Plan", **SAVE_CONTROLS}
    assert over.data["plan"]["will_overwrite"] is True and over.data["plan"]["backup_required"]
    assert desk.posts == [] and desk.store == before and not (tmp_path / "backups").exists()


# ============================================================= T12 snapshots


@pytest.mark.anyio
async def test_overwrite_snapshots_exact_object_before_the_post(tmp_path):
    original = state_entry("Old", vendor_extension={"opaque": [1, 1.5, None]})
    desk = desk_with({"5": original})
    seen_at_post: list[list[str]] = []
    desk.on_post = lambda _body: seen_at_post.append(snapshot_files(tmp_path))
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_save_preset", name="New", preset_id=5, overwrite=True)
        assert outcome.ok and outcome.data["overwrote"] is True
        backup_id = outcome.data["backup_id"]
        snapshot = await resources.load_snapshot("desk", backup_id)
    assert seen_at_post == [[f"{backup_id}.json"]]
    assert snapshot.preset == original and snapshot.preset_id == 5
    assert snapshot.firmware.version == "16.0.1"
    assert desk.store["5"]["n"] == "New" and "vendor_extension" not in desk.store["5"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "entry",
    [
        {"win": "T=1", "n": "Cmd"},
        {"vendor_extension": {"x": 1}},
        state_entry("State"),
    ],
)
async def test_overwrite_of_other_entry_types_is_allowed_after_snapshot(tmp_path, entry):
    desk = desk_with({"5": entry})
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_save_preset", name="New", preset_id=5, overwrite=True)
        snapshot = await resources.load_snapshot("desk", outcome.data["backup_id"])
    assert outcome.ok and snapshot.preset == entry
    if classify(entry)[0] != "state":
        assert any("replaced by a state preset" in w for w in outcome.warnings)


@pytest.mark.anyio
@pytest.mark.parametrize("tool", ["wled_save_preset", "wled_delete_preset"])
async def test_backup_failure_sends_nothing(tmp_path, monkeypatch, tool):
    desk = desk_with({"5": state_entry("Keep")})
    before = copy.deepcopy(desk.store)
    arguments = {"name": "New", "overwrite": True} if tool == "wled_save_preset" else {}
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        monkeypatch.setattr(os, "fsync", lambda fd: (_ for _ in ()).throw(OSError(5, "io")))
        outcome = await call(resources, tool, preset_id=5, **arguments)
        monkeypatch.undo()
    assert not outcome.ok and outcome.error.code == "BACKUP_FAILED"
    assert (outcome.application, outcome.verification) == ("not_attempted", "not_requested")
    assert desk.posts == [] and desk.store == before and snapshot_files(tmp_path) == []


@pytest.mark.anyio
@pytest.mark.parametrize("tool", ["wled_save_preset", "wled_delete_preset"])
async def test_prior_object_changed_after_snapshot_conflicts_and_keeps_snapshot(tmp_path, tool):
    desk = desk_with({"5": state_entry("Old")})

    def change(device: PresetDevice) -> None:
        if device.get_counts["presets.json"] == 2:
            device.store["5"] = state_entry("Changed by another client")

    desk.before_presets_get = change
    arguments = {"name": "New", "overwrite": True} if tool == "wled_save_preset" else {}
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, tool, preset_id=5, **arguments)
        kept = await resources.load_snapshot("desk", outcome.data["backup_id"])
    assert outcome.error.code == "PRESET_CONFLICT" and outcome.application == "not_attempted"
    assert desk.posts == [] and kept.preset["n"] == "Old"


@pytest.mark.anyio
async def test_delete_snapshots_then_removes_exactly_one_entry(tmp_path):
    desk = desk_with(
        {"1": state_entry("Keep"), "5": state_entry("Gone"), "6": state_entry("Keep2")}
    )
    desk.persist_delay = 2
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_delete_preset", preset_id=5)
        snapshot = await resources.load_snapshot("desk", outcome.data["backup_id"])
    assert outcome.ok and (outcome.application, outcome.verification) == ("applied", "verified")
    assert desk.posts == [{"pdel": 5}]
    assert sorted(desk.store) == ["0", "1", "6"] and snapshot.preset["n"] == "Gone"
    assert outcome.data["deleted_type"] == "state" and "interference" not in outcome.data


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("entry", "kind"),
    [
        (playlist_entry([2]), "playlist"),
        ({"win": "T=1"}, "api-command"),
        ({"vendor_extension": 1}, "unknown"),
    ],
)
async def test_delete_works_for_every_object_entry_type_with_snapshot(tmp_path, entry, kind):
    desk = desk_with({"2": state_entry(), "5": entry})
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_delete_preset", preset_id=5)
        snapshot = await resources.load_snapshot("desk", outcome.data["backup_id"])
    assert outcome.ok and outcome.data["deleted_type"] == kind and snapshot.preset == entry
    assert "5" not in desk.store


@pytest.mark.anyio
async def test_delete_absence_by_null_or_empty_marker_verifies(tmp_path):
    desk = desk_with({"5": state_entry()})

    def leave_marker(body: dict[str, Any]) -> None:
        desk.persist = False
        desk.store["5"] = None  # a device that keeps a null marker instead of removing the key

    desk.on_post = leave_marker
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_delete_preset", preset_id=5)
    assert outcome.ok and outcome.verification == "verified"


@pytest.mark.anyio
async def test_delete_validation_and_not_found_send_nothing(tmp_path):
    desk = desk_with({"5": "text", "6": 7})
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        missing = await call(resources, "wled_delete_preset", preset_id=4)
        scalar = await call(resources, "wled_delete_preset", preset_id=5)
    assert missing.error.code == "PRESET_NOT_FOUND"
    assert scalar.error.code == "VALIDATION_ERROR" and scalar.application == "not_attempted"
    assert desk.posts == [] and snapshot_files(tmp_path) == []


@pytest.mark.anyio
async def test_delete_warns_about_referencing_playlists_and_active_marker(tmp_path):
    desk = desk_with({"1": state_entry(), "4": playlist_entry([1])})
    desk.state["ps"] = 1
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_delete_preset", preset_id=1)
    assert outcome.ok
    assert any("[4]" in w and "reference" in w for w in outcome.warnings)
    assert any("active" in w for w in outcome.warnings)
    assert "4" in desk.store  # the playlist is not edited


@pytest.mark.anyio
async def test_delete_dry_run_creates_no_files_and_sends_nothing(tmp_path):
    desk = desk_with({"5": state_entry()})
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_delete_preset", preset_id=5, dry_run=True)
    assert outcome.ok and outcome.dry_run and outcome.data["payload"] == {"pdel": 5}
    assert outcome.data["plan"]["backup_required"] is True
    assert desk.posts == [] and not (tmp_path / "backups").exists() and "5" in desk.store


# ======================================================== T13 bounded verification


@pytest.mark.anyio
async def test_save_visible_only_after_several_polls_succeeds_within_deadline(tmp_path):
    desk = desk_with({})
    desk.persist_delay = 3
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_save_preset", name="Slow")
    assert outcome.ok and outcome.data["preset"]["n"] == "Slow"
    # plan read + recheck read + at least four polls, every one a fresh GET
    assert desk.get_counts["presets.json"] >= 6
    assert len(desk.posts) == 1


@pytest.mark.anyio
async def test_acknowledged_but_never_persisted_save_is_a_mismatch_at_the_deadline(tmp_path):
    desk = desk_with({"3": state_entry("Old")})
    desk.persist = False
    async with open_resources(tmp_path, fleet_of(desk), operation_timeout_seconds=0.8) as resources:
        outcome = await call(
            resources, "wled_save_preset", name="Ghost", preset_id=3, overwrite=True
        )
    assert not outcome.ok and outcome.error.code == "VERIFICATION_MISMATCH"
    assert (outcome.application, outcome.verification) == ("unknown", "mismatch")
    assert outcome.data["observed"]["n"] == "Old" and outcome.data["differences"]
    assert outcome.data["preset_id"] == 3 and outcome.data["name"] == "Ghost"
    assert outcome.data["backup_id"] and len(desk.posts) == 1
    assert outcome.error.write_retryable is False


@pytest.mark.anyio
async def test_matching_name_but_differing_captured_field_is_a_mismatch(tmp_path):
    desk = desk_with({})
    desk.entry_mutator = lambda entry: entry["seg"][0].update({"fx": 99})
    async with open_resources(tmp_path, fleet_of(desk), operation_timeout_seconds=0.8) as resources:
        outcome = await call(resources, "wled_save_preset", name="Drift")
    assert outcome.error.code == "VERIFICATION_MISMATCH"
    assert outcome.data["differences"] == ["seg[0].fx"]
    assert outcome.data["observed"]["n"] == "Drift"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "mutate",
    [
        lambda e: e.update({"bri": 1}),
        lambda e: e["seg"].pop(),  # an active segment missing
        lambda e: e["seg"].append({"id": 9, "start": 0, "stop": 1}),
        lambda e: e.update({"n": "Other"}),
        lambda e: e["seg"][2].update({"stop": 0}),
        lambda e: e["seg"][0].update({"on": 1}),  # 1 is not true
    ],
)
async def test_every_kind_of_capture_difference_is_reported(tmp_path, mutate):
    desk = desk_with({})
    desk.entry_mutator = mutate
    async with open_resources(tmp_path, fleet_of(desk), operation_timeout_seconds=0.8) as resources:
        outcome = await call(resources, "wled_save_preset", name="Drift")
    assert outcome.error.code == "VERIFICATION_MISMATCH"


@pytest.mark.anyio
async def test_saved_entry_with_inactive_slot_markers_matches(tmp_path):
    desk = desk_with({})  # default state has segments 0, 2, 5: slots 1, 3, 4 are markers
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_save_preset", name="Markers")
    assert outcome.ok
    assert {"stop": 0} in desk.store["1"]["seg"]


@pytest.mark.anyio
async def test_unrelated_change_is_reported_as_interference_not_failure(tmp_path):
    desk = desk_with({"1": state_entry(), "9": state_entry("Other")})

    def touch(device: PresetDevice) -> None:
        if device.posts:
            device.store["9"] = state_entry("Edited elsewhere")
            device.store["200"] = state_entry("New elsewhere")

    desk.before_presets_get = touch
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_save_preset", name="Mine")
    assert outcome.ok and outcome.verification == "verified"
    assert outcome.data["interference"] == [9, 200]
    assert any("Unrelated preset entries" in w for w in outcome.warnings)


@pytest.mark.anyio
async def test_delete_never_persisted_is_a_mismatch_with_observed_entry(tmp_path):
    desk = desk_with({"5": state_entry("Stays")})
    desk.persist = False
    async with open_resources(tmp_path, fleet_of(desk), operation_timeout_seconds=0.8) as resources:
        outcome = await call(resources, "wled_delete_preset", preset_id=5)
    assert outcome.error.code == "VERIFICATION_MISMATCH"
    assert outcome.data["observed"]["n"] == "Stays" and len(desk.posts) == 1
    assert outcome.data["backup_id"]


@pytest.mark.anyio
async def test_post_timeout_after_apply_reconciles_by_readback_with_warning(tmp_path):
    desk = desk_with({})
    desk.post_mode = "timeout_after_apply"
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_save_preset", name="Late")
    assert outcome.ok and outcome.verification == "verified"
    assert any("Transport error" in w for w in outcome.warnings)
    assert desk.psave_count() == 1


@pytest.mark.anyio
@pytest.mark.parametrize("post_mode", ["timeout_no_apply", "connect_error"])
async def test_failed_post_with_unchanged_store_is_unknown_and_not_replayed(tmp_path, post_mode):
    desk = desk_with({})
    desk.post_mode = post_mode
    async with open_resources(tmp_path, fleet_of(desk), operation_timeout_seconds=0.8) as resources:
        outcome = await call(resources, "wled_save_preset", name="Lost")
    assert outcome.error.code == "WRITE_OUTCOME_UNKNOWN"
    assert (outcome.application, outcome.verification) == ("unknown", "unknown")
    assert outcome.data["preset_id"] == 1 and outcome.data["name"] == "Lost"
    assert desk.psave_count() == 1
    assert "wled_list_presets" in outcome.error.reconciliation


@pytest.mark.anyio
async def test_unreadable_readback_is_unknown_and_second_call_is_a_new_invocation(tmp_path):
    desk = desk_with({})
    desk.persist = False

    def fail_after_post(_n: int):
        return httpx.ConnectError("down") if desk.posts else None

    desk.presets_get_failure = fail_after_post
    async with open_resources(
        tmp_path, fleet_of(desk), operation_timeout_seconds=0.8, read_retries=0
    ) as resources:
        first = await call(resources, "wled_save_preset", name="Maybe")
        desk.presets_get_failure = None
        second = await call(resources, "wled_save_preset", name="Maybe")
    assert first.error.code == "WRITE_OUTCOME_UNKNOWN" and first.application == "unknown"
    assert first.data["preset_id"] == 1
    # The caller chose to ask again: a fresh invocation, planned from fresh reads, and the
    # unpersisted slot is still free. The tool never retries or re-allocates by itself.
    assert desk.psave_count() == 2 and second.data["preset_id"] == 1
    assert first.model_dump()["error"]["write_retryable"] is False


@pytest.mark.anyio
async def test_operation_deadline_keeps_last_readable_observation(tmp_path):
    desk = desk_with({"3": state_entry("Old")})
    desk.persist = False
    desk.hang_after_post_polls = 1  # one readable poll, then every readback hangs
    async with open_resources(tmp_path, fleet_of(desk), operation_timeout_seconds=0.8) as resources:
        outcome = await call(
            resources, "wled_save_preset", name="Tight", preset_id=3, overwrite=True
        )
    assert len(desk.posts) == 1
    assert outcome.error.code == "VERIFICATION_MISMATCH"
    assert (outcome.application, outcome.verification) == ("unknown", "mismatch")
    assert outcome.data["observed"]["n"] == "Old" and outcome.data["backup_id"]


@pytest.mark.anyio
async def test_non_object_poll_is_an_unreadable_observation(tmp_path):
    desk = desk_with({})
    desk.persist = False
    original = desk.handle

    def handle(request):
        if request.url.path == "/presets.json" and desk.posts:
            return httpx.Response(200, json=[1])  # not an object: also rejected by the client
        return original(request)

    desk.handle = handle
    async with open_resources(tmp_path, fleet_of(desk), operation_timeout_seconds=0.8) as resources:
        outcome = await call(resources, "wled_save_preset", name="X")
    assert outcome.error.code == "WRITE_OUTCOME_UNKNOWN" and len(desk.posts) == 1


@pytest.mark.anyio
async def test_playlist_end_preset_must_be_a_safe_member(tmp_path):
    def playlist(end: int) -> dict[str, Any]:
        entry = playlist_entry([1])
        entry["playlist"]["end"] = end
        return entry

    desk = desk_with(
        {
            "1": state_entry(),
            "6": state_entry("End"),
            "7": {"win": "&RB", "n": "Cmd"},
            "4": playlist(7),
            "5": playlist(255),
            "8": playlist(6),
            "9": playlist(251),  # 251-254: the firmware sets no end preset
        }
    )
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        unsafe_end = await call(resources, "wled_activate_preset", preset_id=4)
        restore_end = await call(resources, "wled_activate_preset", preset_id=5)
        good_end = await call(resources, "wled_activate_preset", preset_id=8)
        ignored_end = await call(resources, "wled_activate_preset", preset_id=9)
    wrapped = {}
    async with open_resources(tmp_path / "w", fleet_of(desk)) as resources:
        for value in (262, 263, -1, 511, 256):
            desk.store["20"] = playlist(value)
            wrapped[value] = await call(resources, "wled_activate_preset", preset_id=20)
    for refused in (unsafe_end, restore_end, *wrapped.values()):
        assert refused.error.code == "UNSUPPORTED_CAPABILITY"
        assert refused.application == "not_attempted"
    assert good_end.ok and ignored_end.ok
    assert desk.posts == [{"ps": 8}, {"ps": 9}]


@pytest.mark.anyio
async def test_delete_warns_when_a_playlist_references_the_preset_as_end(tmp_path):
    entry = playlist_entry([1])
    entry["playlist"]["end"] = 6
    desk = desk_with({"1": state_entry(), "6": state_entry("End"), "4": entry})
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_delete_preset", preset_id=6)
    assert outcome.ok and any("[4]" in w for w in outcome.warnings)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "extra",
    [{"rmcpal": True}, {"wifi": {"ap": True}}, {"np": True}, {"nl": {"on": True}}, {"lor": 1}],
)
async def test_state_shaped_entry_with_side_effect_keys_is_unknown_and_not_activated(
    tmp_path, extra
):
    desk = desk_with({"6": state_entry(**extra)})
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        listing = await call(resources, "wled_list_presets")
        outcome = await call(resources, "wled_activate_preset", preset_id=6)
    assert listing.data["presets"][0]["type"] == "unknown"
    assert outcome.error.code == "UNSUPPORTED_CAPABILITY" and desk.posts == []


def test_state_requires_an_observable_field_and_allows_storage_keys():
    assert classify({"transition": 5, "n": "t"}) == ("unknown", False)
    assert classify({"mainseg": 0}) == ("unknown", False)
    assert classify({"on": True, "ql": "A", "ledmap": 1, "n": "x"}) == ("state", False)
    assert classify({"seg": [], "bri": 3}) == ("state", False)


@pytest.mark.anyio
async def test_already_running_playlist_warning_does_not_claim_firmware_ignores_it(tmp_path):
    desk = desk_with({"1": state_entry(), "4": playlist_entry([1])})
    desk.state["pl"] = 4
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_activate_preset", preset_id=4)
    assert outcome.ok and desk.posts == [{"ps": 4}]
    assert any("already running" in w for w in outcome.warnings)
    assert not any("ignores" in w for w in outcome.warnings)


@pytest.mark.anyio
async def test_same_device_saves_serialize_to_distinct_ids_and_other_device_progresses(tmp_path):
    desk, lamp = desk_with({}), desk_with({})
    results: dict[str, Any] = {}
    fleet = fleet_of(desk, **{"lamp__invalid": lamp})
    async with open_resources(
        tmp_path, fleet, devices=[device("desk"), device("lamp")]
    ) as resources:

        async def run(key: str, device_id: str, name: str) -> None:
            results[key] = await call(resources, "wled_save_preset", device_id=device_id, name=name)

        async with anyio.create_task_group() as group:
            group.start_soon(run, "a", "desk", "A")
            group.start_soon(run, "b", "desk", "B")
            group.start_soon(run, "c", "lamp", "C")
    assert all(r.ok for r in results.values())
    assert {results["a"].data["preset_id"], results["b"].data["preset_id"]} == {1, 2}
    assert results["c"].data["preset_id"] == 1
    assert desk.store["1"]["n"] != desk.store["2"]["n"]


# ================================================================ misc evidence


@pytest.mark.anyio
async def test_logs_carry_no_preset_names_or_objects(tmp_path, caplog, monkeypatch):
    desk = desk_with({"5": state_entry("PRIVATE-NAME")})
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        with caplog.at_level(logging.DEBUG):
            await call(
                resources, "wled_save_preset", name="PRIVATE-NEW", preset_id=5, overwrite=True
            )
            monkeypatch.setattr(os, "fsync", lambda fd: (_ for _ in ()).throw(OSError(5, "io")))
            await call(resources, "wled_delete_preset", preset_id=5)
    assert "PRIVATE" not in caplog.text


def test_classification_is_positive_evidence_only():
    assert classify(state_entry()) == ("state", False)
    assert classify({"n": "only a name"}) == ("unknown", False)
    assert classify({"on": True, "playlist": {"ps": "1"}}) == ("unknown", False)
    assert classify({"win": 5, "on": True}) == (
        "unknown",
        False,
    )  # a control key is never plain state
    assert classify([1]) == ("unknown", True)
    assert classify(playlist_entry([1, 251])) == ("unknown", False)
    assert classify(playlist_entry([True])) == ("unknown", False)


def test_store_parsing_rules():
    store = parse_store(
        {"0": {"x": 1}, "1": {}, "2": None, "3": {"on": True}, "250": {"on": True}, "256": {}}
    )
    assert list(store.entries) == [3, 250] and store.malformed_keys == 1


# ================================================================ contract examples

EXAMPLES = Path(__file__).resolve().parents[1] / "examples/contracts"


def example_store() -> dict[str, Any]:
    return {
        "0": {},
        "1": {"n": "Existing", "on": True, "bri": 80},
        "2": {"vendor_extension": {"opaque": True}},
        "3": None,
        "4": {"playlist": {"ps": [1], "dur": [100], "repeat": 0}, "on": True, "n": "Cycle"},
    }


async def build_example_cases(tmp_path) -> dict[str, Any]:
    """Actual tool output against the stateful mock; reproduced by the test below."""
    from tests.state_catalog_support import FakeClock

    desk = PresetDevice(store=example_store())
    fleet = fleet_of(desk)
    resources = Resources(config(tmp_path), fleet.transport(), clock=FakeClock().clock())
    resources.poll_interval_seconds = 0.005
    cases: dict[str, Any] = {}
    async with resources:
        for name, tool, arguments in (
            ("list", "wled_list_presets", {}),
            ("get_unknown_entry", "wled_get_preset", {"preset_id": 2}),
            ("get_empty_slot", "wled_get_preset", {"preset_id": 3}),
            (
                "save_occupied_without_overwrite",
                "wled_save_preset",
                {"name": "Evening", "preset_id": 1},
            ),
            (
                "activate_playlist_dry_run",
                "wled_activate_preset",
                {"preset_id": 4, "dry_run": True},
            ),
            ("delete_dry_run", "wled_delete_preset", {"preset_id": 2, "dry_run": True}),
        ):
            outcome = await call(resources, tool, **arguments)
            cases[name] = {
                "request": {"device_id": "desk", **arguments},
                "expected": outcome.model_dump(mode="json"),
            }
    assert desk.posts == []
    return cases


@pytest.mark.anyio
async def test_preset_contract_examples_are_actual_output(tmp_path):
    stored = json.loads((EXAMPLES / "presets.json").read_text(encoding="utf-8"))
    assert await build_example_cases(tmp_path) == stored["cases"]
    for case in stored["cases"].values():
        Outcome.model_validate(case["expected"])


@pytest.mark.anyio
async def test_backup_failure_example_is_actual_delete_output(tmp_path, monkeypatch):
    errors = json.loads((EXAMPLES / "errors.json").read_text(encoding="utf-8"))["cases"]
    case = next(c for c in errors if c["name"] == "backup_failure")
    desk = desk_with({"5": state_entry()})
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        monkeypatch.setattr(os, "fsync", lambda fd: (_ for _ in ()).throw(OSError(5, "io")))
        outcome = await call(resources, "wled_delete_preset", preset_id=5)
        monkeypatch.undo()
    assert outcome.model_dump(mode="json") == case["expected"]


@pytest.mark.anyio
@pytest.mark.parametrize("end", [1.5, True, "7", None])
async def test_non_integer_playlist_end_is_ignored_like_zero(tmp_path, end):
    entry = playlist_entry([1])
    entry["playlist"]["end"] = end
    desk = desk_with({"1": state_entry(), "4": entry})
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_activate_preset", preset_id=4)
    assert outcome.ok and desk.posts == [{"ps": 4}]


# ================================================ issue #66: WLED 16 state presets (bs)


def wled16_entry(name: str = "Synthetic", **extra: Any) -> dict[str, Any]:
    """Top-level shape of a v16.0.1 state-preset save (synthetic values)."""
    entry: dict[str, Any] = {
        "on": True,
        "bri": 120,
        "transition": 7,
        "bs": 0,
        "mainseg": 0,
        "seg": [{"id": 0, "start": 0, "stop": 30, "col": [[255, 160, 0]], "fx": 0, "bm": 0}],
        "n": name,
    }
    entry.update(extra)
    return entry


def wled16_desk(store: dict[str, Any] | None = None, bs: int = 3) -> PresetDevice:
    return desk_with(store or {}, state=make_state(bs=bs))


def test_wled16_state_preset_with_bs_classifies_as_state():
    # S66-1: the WLED 16 shape is a plain state preset; the 0.15 shape still is.
    assert classify(wled16_entry()) == ("state", False)
    without_bs = wled16_entry()
    del without_bs["bs"]
    assert classify(without_bs) == ("state", False)


@pytest.mark.parametrize(
    "extra",
    [
        {"rmcpal": True},
        {"nl": {"on": True}},
        {"lor": 1},
        {"udpn": {"send": True}},
        {"np": True},
        {"xq": 1},
    ],
)
def test_wled16_entry_with_any_other_key_stays_unknown(extra):
    # S66-2: bs extends the allowlist by exactly one key, nothing else.
    assert classify(wled16_entry(**extra)) == ("unknown", False)


def test_bs_alone_is_not_an_observable_state_preset():
    # S66-2: bs (like transition) cannot be observed after activation.
    assert classify({"bs": 0, "n": "x"}) == ("unknown", False)
    assert classify({"bs": 0, "transition": 5}) == ("unknown", False)


@pytest.mark.anyio
@pytest.mark.parametrize("extra", [{"rmcpal": True}, {"nl": {"on": True}}, {"xq": 1}])
async def test_wled16_entry_with_side_effect_key_is_refused_with_zero_posts(tmp_path, extra):
    desk = wled16_desk({"6": wled16_entry(**extra)})
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_activate_preset", preset_id=6)
    assert outcome.error.code == "UNSUPPORTED_CAPABILITY"
    assert outcome.application == "not_attempted" and desk.posts == []


@pytest.mark.anyio
async def test_wled16_entry_is_listed_and_read_as_state_with_exact_object(tmp_path):
    # S66-3
    original = wled16_entry("Synthetic")
    desk = wled16_desk({"2": original})
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        listing = await call(resources, "wled_list_presets")
        got = await call(resources, "wled_get_preset", preset_id=2)
    assert [(p["id"], p["type"]) for p in listing.data["presets"]] == [(2, "state")]
    assert got.data["type"] == "state" and got.data["preset"] == original
    assert got.data["preset"]["bs"] == 0 and desk.posts == []


@pytest.mark.anyio
async def test_wled16_state_preset_activates_with_one_ps_post(tmp_path):
    # S66-4
    desk = wled16_desk({"2": wled16_entry()})
    before = copy.deepcopy(desk.store)
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_activate_preset", preset_id=2)
    assert outcome.ok and (outcome.application, outcome.verification) == ("applied", "verified")
    assert outcome.data["type"] == "state"
    assert desk.posts == [{"ps": 2}] and desk.store == before


@pytest.mark.anyio
async def test_playlist_of_wled16_state_presets_is_activatable(tmp_path):
    # S66-5: members and the end preset are WLED 16 state presets.
    playlist = playlist_entry([1, 2])
    playlist["playlist"]["end"] = 3
    desk = wled16_desk(
        {"1": wled16_entry("A"), "2": wled16_entry("B"), "3": wled16_entry("C"), "4": playlist}
    )
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_activate_preset", preset_id=4)
    assert outcome.ok and outcome.verification == "verified"
    assert outcome.data["type"] == "playlist"
    assert desk.posts == [{"ps": 4}] and desk.state["pl"] == 4


def _type_warnings(outcome: Outcome) -> list[str]:
    return [w for w in outcome.warnings if "not a plain state preset" in w]


@pytest.mark.anyio
async def test_wled16_save_verifies_bs_and_saved_preset_activates(tmp_path):
    # S66-6: end-to-end mock of the failure seen in the #12 hardware run (H06).
    desk = wled16_desk(bs=3)
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        saved = await call(resources, "wled_save_preset", name="Synthetic")
        assert saved.ok and (saved.application, saved.verification) == ("applied", "verified")
        assert saved.data["type"] == "state" and saved.data["preset"]["bs"] == 3
        assert _type_warnings(saved) == []
        preset_id = saved.data["preset_id"]
        activated = await call(resources, "wled_activate_preset", preset_id=preset_id)
    assert activated.ok and activated.verification == "verified"
    assert desk.posts[-1] == {"ps": preset_id}


@pytest.mark.anyio
@pytest.mark.parametrize(
    "mutate",
    [lambda e: e.update({"bs": 4}), lambda e: e.pop("bs")],
    ids=["differs", "missing"],
)
async def test_wled16_save_with_stored_bs_differing_from_live_is_a_mismatch(tmp_path, mutate):
    # S66-7
    desk = wled16_desk(bs=3)
    desk.entry_mutator = mutate
    async with open_resources(tmp_path, fleet_of(desk), operation_timeout_seconds=0.8) as resources:
        outcome = await call(resources, "wled_save_preset", name="Drift")
    assert outcome.error.code == "VERIFICATION_MISMATCH"
    assert outcome.data["differences"] == ["bs"]
    assert outcome.data["no_replay"] is True and desk.psave_count() == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    "mutate", [None, lambda e: e.update({"bs": 5})], ids=["no-bs", "stored-bs-only"]
)
async def test_wled015_save_without_live_bs_does_not_compare_bs(tmp_path, mutate):
    # S66-8: the 0.15 control; a stored bs without a live bs is tolerated.
    desk = desk_with({})
    assert "bs" not in desk.state
    desk.entry_mutator = mutate
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_save_preset", name="Control")
    assert outcome.ok and outcome.verification == "verified"
    assert outcome.data["type"] == "state" and _type_warnings(outcome) == []
    assert ("bs" in desk.store["1"]) is (mutate is not None)


@pytest.mark.anyio
async def test_saved_entry_with_unknown_key_is_verified_but_warned(tmp_path):
    # S66-9: a future firmware key yields a warning, not a silent unactivatable preset.
    desk = wled16_desk(bs=1)
    desk.entry_mutator = lambda e: e.update({"xq": {"secret-value": 77}})
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_save_preset", name="PRIVATE-NAME")
    assert outcome.ok and (outcome.application, outcome.verification) == ("applied", "verified")
    assert outcome.data["type"] == "unknown" and desk.psave_count() == 1
    (warning,) = _type_warnings(outcome)
    assert "'unknown'" in warning and "xq" in warning
    assert "PRIVATE" not in warning and "secret" not in warning and "77" not in warning
    assert warning.endswith("(unexpected top-level keys: xq).")  # allowlisted keys unnamed
