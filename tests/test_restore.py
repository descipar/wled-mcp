"""Restore of one snapshot entry (A18-03, A18-04) and snapshot listing (A18-06), issue #18.

Mock transport and ``tmp_path`` only. Snapshots are created through the real store with
an explicit firmware identity; the fake device models the WLED v16.0.1 routes of
docs/SOURCES.md "Issue-18 WLED 16 preset write evidence".
"""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from tests.preset_support import PresetDevice, playlist_entry, state_entry
from tests.state_catalog_support import FakeClock, make_info, make_state
from tests.test_inventory_client import config, device
from tests.test_presets import call, fleet_of, snapshot_files
from wled_mcp.backups import Firmware
from wled_mcp.resources import Resources

FIRMWARE = "16.0.1"
# A stored state entry with firmware-written segment fields the tools do not expose.
STORED = {
    "on": True,
    "bri": 140,
    "transition": 7,
    "bs": 0,
    "mainseg": 0,
    "seg": [
        {"id": 0, "start": 0, "stop": 45, "cct": 127, "c1": 128, "col": [[0, 80, 255]], "fx": 2},
        {"stop": 0},
    ],
    "n": "Saved scene",
}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def wled16(store: dict[str, Any] | None = None, version: str = FIRMWARE) -> PresetDevice:
    return PresetDevice(
        store={"0": {}, **(store or {})},
        state=make_state(bs=0),
        info=make_info(ver=version),
    )


def open_resources(tmp_path, fleet, devices=None) -> tuple[Resources, FakeClock]:
    clock = FakeClock()
    resources = Resources(
        config(tmp_path, devices=devices, operation_timeout_seconds=1.0),
        fleet.transport(),
        clock=clock.clock(),
    )
    resources.poll_interval_seconds = 0.005
    return resources, clock


def snapshot(
    resources: Resources,
    preset: dict[str, Any],
    preset_id: int = 5,
    version: str = FIRMWARE,
    device_id: str = "desk",
) -> str:
    record = resources.backups.backup_preset(
        device_id, preset_id, copy.deepcopy(preset), Firmware(version, None)
    )
    return record.backup_id


# ================================================================ A18-03 state restore


@pytest.mark.anyio
async def test_state_snapshot_restores_verbatim_to_its_own_free_id(tmp_path):
    desk = wled16()
    fleet = fleet_of(desk)
    resources, _clock = open_resources(tmp_path, fleet)
    async with resources:
        source = snapshot(resources, STORED)
        outcome = await call(resources, "wled_restore_preset", backup_id=source)
    assert outcome.ok and (outcome.application, outcome.verification) == ("applied", "verified")
    assert desk.posts == [{**STORED, "psave": 5, "o": True}]
    assert desk.store["5"] == STORED  # exact, firmware-written segment fields included
    data = outcome.data
    assert data["preset_id"] == 5 and data["source_backup_id"] == source
    assert data["route"] == "state" and data["snapshot_type"] == "state"
    assert "Applies the supplied state to the lights" in str(data["live_effect"])
    assert data["previous_lighting_restored"] is False and data["overwrote"] is False
    assert "backup_id" not in data  # a free destination needs no new snapshot
    assert snapshot_files(tmp_path) == [f"{source}.json"]
    assert desk.state["bri"] == 140  # applied live (ISSUE-18-DEC-001)


@pytest.mark.anyio
async def test_state_snapshot_restores_to_an_explicit_different_free_id(tmp_path):
    desk = wled16({"5": state_entry("Unrelated")})
    resources, _clock = open_resources(tmp_path, fleet_of(desk))
    async with resources:
        source = snapshot(resources, STORED)
        outcome = await call(resources, "wled_restore_preset", backup_id=source, preset_id=9)
    assert outcome.ok and outcome.data["preset_id"] == 9
    assert desk.store["9"] == STORED and desk.store["5"] == state_entry("Unrelated")
    assert outcome.data["source_preset_id"] == 5


@pytest.mark.anyio
async def test_occupied_destination_needs_overwrite_and_takes_a_new_snapshot_first(tmp_path):
    current = state_entry("Current")
    desk = wled16({"5": current})
    fleet = fleet_of(desk)
    resources, clock = open_resources(tmp_path, fleet)
    async with resources:
        source = snapshot(resources, STORED)
        clock.advance(5)
        refused = await call(resources, "wled_restore_preset", backup_id=source)
        assert refused.error.code == "PRESET_CONFLICT" and fleet.post_count() == 0
        seen: list[list[str]] = []
        desk.on_post = lambda body: seen.append(snapshot_files(tmp_path))
        outcome = await call(resources, "wled_restore_preset", backup_id=source, overwrite=True)
    assert outcome.ok and len(desk.posts) == 1 and desk.store["5"] == STORED
    prior = outcome.data["backup_id"]
    assert prior != source and outcome.data["source_backup_id"] == source
    assert seen == [sorted([f"{source}.json", f"{prior}.json"])]  # snapshot before the POST
    stored = json.loads((tmp_path / "backups/desk" / f"{prior}.json").read_text("utf-8"))
    assert stored["preset"] == current and stored["preset_id"] == 5
    assert outcome.data["overwrote"] is True


@pytest.mark.anyio
async def test_firmware_version_mismatch_is_refused(tmp_path):
    desk = wled16(version="16.0.1")
    fleet = fleet_of(desk)
    resources, _clock = open_resources(tmp_path, fleet)
    async with resources:
        source = snapshot(resources, STORED, version="16.0.0")
        for dry_run in (True, False):
            outcome = await call(
                resources, "wled_restore_preset", backup_id=source, dry_run=dry_run
            )
            assert outcome.error.code == "UNSUPPORTED_CAPABILITY"
            assert "exact version" in outcome.error.message
    assert fleet.post_count() == 0 and snapshot_files(tmp_path) == [f"{source}.json"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("preset", "kind"),
    [
        ({"win": "T=1", "n": "Command"}, "api-command"),
        ({"vendor_extension": {"x": 1}, "on": True}, "unknown"),
        ({"on": True, "nl": {"on": True}}, "unknown"),
    ],
)
async def test_api_command_and_unknown_snapshots_are_refused_without_device_io(
    tmp_path, preset, kind
):
    fleet = fleet_of(wled16())
    resources, _clock = open_resources(tmp_path, fleet)
    async with resources:
        source = snapshot(resources, preset)
        outcome = await call(resources, "wled_restore_preset", backup_id=source)
    assert outcome.error.code == "UNSUPPORTED_CAPABILITY"
    assert f"type '{kind}'" in outcome.error.message
    assert fleet.calls == []


@pytest.mark.anyio
async def test_destination_changed_after_planning_is_a_conflict(tmp_path):
    desk = wled16({"5": state_entry("Current")})

    def change_on_recheck(device: PresetDevice) -> None:
        if device.get_counts["presets.json"] == 2:
            device.store["5"] = state_entry("Changed by another client")

    desk.before_presets_get = change_on_recheck
    resources, clock = open_resources(tmp_path, fleet_of(desk))
    async with resources:
        source = snapshot(resources, STORED)
        clock.advance(5)
        outcome = await call(resources, "wled_restore_preset", backup_id=source, overwrite=True)
    assert outcome.error.code == "PRESET_CONFLICT" and desk.posts == []
    assert desk.store["5"] == state_entry("Changed by another client")
    assert len(snapshot_files(tmp_path)) == 2  # the snapshot of the earlier state is kept


@pytest.mark.anyio
async def test_dry_run_sends_nothing_and_creates_no_file(tmp_path):
    desk = wled16({"5": state_entry("Current")})
    fleet = fleet_of(desk)
    resources, _clock = open_resources(tmp_path, fleet)
    async with resources:
        source = snapshot(resources, STORED)
        outcome = await call(
            resources, "wled_restore_preset", backup_id=source, overwrite=True, dry_run=True
        )
    assert outcome.ok and outcome.dry_run and fleet.post_count() == 0
    assert snapshot_files(tmp_path) == [f"{source}.json"]
    plan = outcome.data["plan"]
    assert plan["will_overwrite"] is True and plan["backup_required"] is True
    assert plan["source_backup_id"] == source and plan["firmware_version"] == FIRMWARE
    assert outcome.data["payload"] == {**STORED, "psave": 5, "o": True}


@pytest.mark.anyio
async def test_missing_malformed_and_foreign_backup_ids(tmp_path):
    lamp = wled16()
    fleet = fleet_of(wled16(), lamp__invalid=lamp)
    resources, _clock = open_resources(tmp_path, fleet, devices=[device(), device("lamp")])
    async with resources:
        foreign = snapshot(resources, STORED, device_id="lamp")
        missing = await call(resources, "wled_restore_preset", backup_id=foreign)
        malformed = await call(resources, "wled_restore_preset", backup_id="../lamp/x")
        unknown = await call(
            resources, "wled_restore_preset", device_id="absent", backup_id=foreign
        )
    assert missing.error.code == "PRESET_NOT_FOUND"
    assert malformed.error.code == "VALIDATION_ERROR"
    assert unknown.error.code == "UNKNOWN_DEVICE" and unknown.device_id is None
    assert fleet.post_count() == 0


@pytest.mark.anyio
async def test_timeout_with_unreadable_readback_is_unknown_and_not_resent(tmp_path):
    import httpx2 as httpx

    desk = wled16()
    desk.post_mode = "timeout_no_apply"
    desk.presets_get_failure = lambda _count: (
        httpx.ConnectError("synthetic") if desk.posts else None
    )
    resources, _clock = open_resources(tmp_path, fleet_of(desk))
    async with resources:
        source = snapshot(resources, STORED)
        outcome = await call(resources, "wled_restore_preset", backup_id=source)
    assert outcome.error.code == "WRITE_OUTCOME_UNKNOWN" and outcome.data["no_replay"] is True
    assert len(desk.posts) == 1


# ============================================================= A18-04 playlist restore

PLAYLIST = playlist_entry([1, 2], name="Cycle")  # dur [100, 100], transition [7]


@pytest.mark.anyio
async def test_playlist_snapshot_restores_through_the_playlist_route(tmp_path):
    desk = wled16({"1": state_entry("A"), "2": state_entry("B")})
    desk.state.update(pl=4, ps=1)
    resources, _clock = open_resources(tmp_path, fleet_of(desk))
    async with resources:
        source = snapshot(resources, PLAYLIST, preset_id=7)
        outcome = await call(resources, "wled_restore_preset", backup_id=source)
    assert outcome.ok and outcome.data["route"] == "playlist"
    assert desk.posts == [{"playlist": PLAYLIST["playlist"], "n": "Cycle", "psave": 7, "o": True}]
    # Stored re-serialized: full per-entry arrays; verified semantically.
    assert desk.store["7"]["playlist"]["transition"] == [7, 7]
    assert outcome.data["type"] == "playlist"
    assert "Starts the playlist" in str(outcome.data["live_effect"])
    assert desk.state["pl"] == 7  # the playlist started
    assert any("Playlist 4 is running" in w for w in outcome.warnings)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("preset", "fragment"),
    [
        (playlist_entry([1], bri=40), "drop these fields"),
        ({**PLAYLIST, "playlist": {**PLAYLIST["playlist"], "vendor": 1}}, "playlist.vendor"),
        (playlist_entry([1], on=False), "on=true"),
        ({**PLAYLIST, "playlist": {**PLAYLIST["playlist"], "end": 255}}, "255"),
        ({**PLAYLIST, "playlist": {**PLAYLIST["playlist"], "repeat": -1}}, "repeat"),
        ({**PLAYLIST, "playlist": {**PLAYLIST["playlist"], "dur": []}}, "dur"),
        ({**PLAYLIST, "playlist": {**PLAYLIST["playlist"], "dur": [1.5, 2]}}, "dur"),
        (playlist_entry([3]), "IDs [3]"),  # missing member
        (playlist_entry([1, 9]), "IDs [9]"),  # member 9 is an API command
        (playlist_entry([1, 7]), "IDs [7]"),  # the destination itself
        (playlist_entry(list(range(1, 102))), "1-100"),
        # The firmware saves after starting: repeat and shuffle are not reproducible.
        ({**PLAYLIST, "playlist": {**PLAYLIST["playlist"], "repeat": 2}}, "repeat count"),
        ({**PLAYLIST, "playlist": {**PLAYLIST["playlist"], "r": True}}, "shuffle"),
        (playlist_entry([1], name="x" * 33), "32 UTF-8 bytes"),
        (playlist_entry([1], ql=""), "quick-load"),
    ],
)
async def test_unreproducible_or_unsafe_playlist_blocks_in_preview_and_write(
    tmp_path, preset, fragment
):
    desk = wled16({"1": state_entry("A"), "2": state_entry("B"), "9": {"win": "T=1"}})
    fleet = fleet_of(desk)
    resources, _clock = open_resources(tmp_path, fleet)
    async with resources:
        source = snapshot(resources, preset, preset_id=7)
        for dry_run in (True, False):
            outcome = await call(
                resources, "wled_restore_preset", backup_id=source, dry_run=dry_run
            )
            assert outcome.error.code == "UNSUPPORTED_CAPABILITY", outcome.error
            assert fragment in outcome.error.message
    assert fleet.post_count() == 0 and "7" not in desk.store


@pytest.mark.anyio
async def test_playlist_semantic_difference_is_a_mismatch(tmp_path):
    desk = wled16({"1": state_entry("A"), "2": state_entry("B")})
    desk.entry_mutator = lambda entry: entry["playlist"].update(repeat=3)
    resources, _clock = open_resources(tmp_path, fleet_of(desk))
    async with resources:
        source = snapshot(resources, PLAYLIST, preset_id=7)
        outcome = await call(resources, "wled_restore_preset", backup_id=source)
    assert outcome.error.code == "VERIFICATION_MISMATCH"
    assert outcome.data["differences"] == ["playlist.repeat"] and len(desk.posts) == 1


@pytest.mark.anyio
async def test_playlist_dry_run_names_the_playback_effect(tmp_path):
    desk = wled16({"1": state_entry("A"), "2": state_entry("B")})
    fleet = fleet_of(desk)
    resources, _clock = open_resources(tmp_path, fleet)
    async with resources:
        source = snapshot(resources, PLAYLIST, preset_id=7)
        outcome = await call(resources, "wled_restore_preset", backup_id=source, dry_run=True)
    assert outcome.ok and fleet.post_count() == 0
    assert outcome.data["plan"]["route"] == "playlist"
    assert "Starts the playlist" in outcome.data["plan"]["live_effect"]
    assert any("semantic" in str(p) for p in outcome.data["postconditions"])


# ============================================================== A18-06 list snapshots


@pytest.mark.anyio
async def test_list_snapshots_newest_first_counts_invalid_and_reads_no_device(tmp_path):
    fleet = fleet_of(wled16())
    resources, clock = open_resources(tmp_path, fleet)
    async with resources:
        first = snapshot(resources, STORED, preset_id=5)
        clock.advance(10)
        second = snapshot(resources, PLAYLIST, preset_id=7)
        clock.advance(10)
        third = snapshot(resources, {"win": "T=1", "n": "Command"}, preset_id=5)
        bad = tmp_path / "backups/desk/b-20260101T000000Z-000000000000.json"
        bad.write_text("{not json", encoding="utf-8")
        listing = await call(resources, "wled_list_snapshots")
        only_five = await call(resources, "wled_list_snapshots", preset_id=5)
    assert fleet.calls == []
    assert listing.ok and (listing.application, listing.verification) == (
        "not_attempted",
        "not_requested",
    )
    items = listing.data["snapshots"]
    assert [item["backup_id"] for item in items] == [third, second, first]
    assert items[0] == {
        "backup_id": third,
        "preset_id": 5,
        "created_at": items[0]["created_at"],
        "firmware_version": FIRMWARE,
        "type": "api-command",
        "name": "Command",
        "restorable": False,
    }
    assert items[1]["type"] == "playlist" and items[1]["restorable"] is True
    assert listing.data["invalid_count"] == 1 and listing.data["count"] == 3
    assert any("1 invalid snapshot file" in w for w in listing.warnings)
    assert "b-20260101T000000Z" not in json.dumps(listing.model_dump(mode="json"))
    assert [item["backup_id"] for item in only_five.data["snapshots"]] == [third, first]


@pytest.mark.anyio
async def test_list_snapshots_empty_and_unknown_device(tmp_path):
    fleet = fleet_of(wled16())
    resources, _clock = open_resources(tmp_path, fleet)
    async with resources:
        empty = await call(resources, "wled_list_snapshots")
        unknown = await call(resources, "wled_list_snapshots", device_id="absent")
    assert empty.ok and empty.data["snapshots"] == [] and empty.data["invalid_count"] == 0
    assert unknown.error.code == "UNKNOWN_DEVICE" and unknown.device_id is None
    assert not (tmp_path / "backups").exists() and fleet.calls == []


@pytest.mark.anyio
async def test_nameless_state_snapshot_expects_the_firmware_default_name(tmp_path):
    nameless = {key: value for key, value in STORED.items() if key != "n"}
    desk = wled16()
    resources, _clock = open_resources(tmp_path, fleet_of(desk))
    async with resources:
        source = snapshot(resources, nameless)
        outcome = await call(resources, "wled_restore_preset", backup_id=source)
    assert desk.posts == [{**nameless, "psave": 5, "o": True}]
    assert outcome.ok and desk.store["5"] == {**nameless, "n": "Preset 5"}


@pytest.mark.anyio
async def test_playlist_quick_load_label_is_sent_and_verified(tmp_path):
    labelled = playlist_entry([1, 2], name="Cycle", ql="C1")
    desk = wled16({"1": state_entry("A"), "2": state_entry("B")})
    resources, _clock = open_resources(tmp_path, fleet_of(desk))
    async with resources:
        source = snapshot(resources, labelled, preset_id=7)
        outcome = await call(resources, "wled_restore_preset", backup_id=source)
    assert outcome.ok and desk.posts[0]["ql"] == "C1" and desk.store["7"]["ql"] == "C1"


@pytest.mark.anyio
@pytest.mark.parametrize("stored_dur", [["x", "y"], [], "100", None])
async def test_unusable_stored_playlist_values_are_a_mismatch_not_a_crash(tmp_path, stored_dur):
    desk = wled16({"1": state_entry("A"), "2": state_entry("B")})
    desk.entry_mutator = lambda entry: entry["playlist"].update(dur=stored_dur)
    resources, _clock = open_resources(tmp_path, fleet_of(desk))
    async with resources:
        source = snapshot(resources, PLAYLIST, preset_id=7)
        outcome = await call(resources, "wled_restore_preset", backup_id=source)
    assert outcome.error.code == "VERIFICATION_MISMATCH"
    assert outcome.data["differences"] == ["playlist.dur"] and len(desk.posts) == 1
