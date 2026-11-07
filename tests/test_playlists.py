"""Playlist authoring of issue #18 (A18-07): ``wled_save_playlist``.

Mock transport and ``tmp_path`` only; the fake device models the WLED v16.0.1 playlist
route of docs/SOURCES.md "Issue-18 WLED 16 preset write evidence" (the save starts the
playlist and stores it re-serialized). The firmware is set explicitly (16.0.1).
"""

from __future__ import annotations

import copy
from typing import Any

import httpx2 as httpx
import pytest
from pydantic import ValidationError

from tests.bundle_support import (
    BundleDevice,
    call,
    fleet_of,
    open_resources,
    state_preset,
    stored_playlist,
)
from tests.test_presets import snapshot_files
from wled_mcp.backups import Firmware
from wled_mcp.playlists import SavePlaylistRequest

MEMBERS = {"1": state_preset("A"), "2": state_preset("B"), "3": state_preset("C")}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def steps(*ids: int, duration_s: float = 10, transition_s: float = 0.7) -> list[dict[str, Any]]:
    return [{"preset_id": i, "duration_s": duration_s, "transition_s": transition_s} for i in ids]


def request(**overrides: Any) -> dict[str, Any]:
    arguments: dict[str, Any] = {
        "device_id": "desk",
        "name": "Evening cycle",
        "entries": steps(1, 2),
        "repeat": 0,
        "shuffle": False,
    }
    arguments.update(overrides)
    return arguments


async def save(tmp_path, desk: BundleDevice, **overrides: Any):
    arguments = request(**overrides)
    arguments.pop("device_id")
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        return await call(resources, "wled_save_playlist", **arguments)


# ===================================================== valid playlist, semantic readback


@pytest.mark.anyio
async def test_valid_playlist_is_started_stored_and_verified_with_one_post(tmp_path):
    desk = BundleDevice(MEMBERS)
    outcome = await save(
        tmp_path,
        desk,
        entries=[
            {"preset_id": 2, "duration_s": 12.5, "transition_s": 0},
            {"preset_id": 1, "duration_s": 0, "transition_s": 65.5},
        ],
        repeat=3,
        shuffle=True,
        end_preset_id=3,
    )
    assert outcome.ok and (outcome.application, outcome.verification) == ("applied", "verified")
    assert desk.posts == [
        {
            "playlist": {
                "ps": [2, 1],
                "dur": [125, 0],
                "transition": [0, 655],
                "repeat": 3,
                "end": 3,
                "r": True,
            },
            "n": "Evening cycle",
            "psave": 4,
            "o": True,
        }
    ]
    # Stored re-serialized by the firmware (r as an integer, on: true) and accepted.
    assert desk.store["4"]["playlist"]["r"] == 1 and desk.store["4"]["on"] is True
    assert outcome.data["preset_id"] == 4 and outcome.data["route"] == "playlist"
    assert outcome.data["type"] == "playlist"
    assert "Starts the playlist" in str(outcome.data["live_effect"])
    assert outcome.data["previous_lighting_restored"] is False
    assert outcome.data["playback"]["starts_playlist"] is True
    assert desk.state["pl"] == 4  # the save started the playlist (ISSUE-18-DEC-001)
    assert snapshot_files(tmp_path) == []


@pytest.mark.anyio
async def test_dry_run_names_playback_effect_and_running_hazard_and_sends_nothing(tmp_path):
    desk = BundleDevice(MEMBERS)
    desk.state.update(ps=2)
    fleet = fleet_of(desk)
    async with open_resources(tmp_path, fleet) as resources:
        arguments = request(dry_run=True)
        arguments.pop("device_id")
        outcome = await call(resources, "wled_save_playlist", **arguments)
    assert outcome.ok and outcome.dry_run and fleet.post_count() == 0
    plan = outcome.data["plan"]
    assert plan["route"] == "playlist" and "Starts the playlist" in plan["live_effect"]
    playback = plan["playback"]
    assert playback["active_preset_id"] == 2 and playback["active_preset_is_member"] is True
    assert "refused while any playlist runs" in playback["running_playlist_hazard"]
    assert outcome.data["payload"]["playlist"]["dur"] == [100, 100]
    assert any("semantic" in str(p) for p in outcome.data["postconditions"])
    assert not (tmp_path / "backups").exists()


@pytest.mark.anyio
async def test_running_playlist_refuses_the_save_before_any_snapshot_or_post(tmp_path):
    desk = BundleDevice({**MEMBERS, "9": stored_playlist([1, 2]), "4": stored_playlist([3])})
    desk.state.update(pl=9, ps=1)
    for dry_run in (True, False):
        outcome = await save(tmp_path, desk, preset_id=4, overwrite=True, dry_run=dry_run)
        assert outcome.error.code == "PRESET_CONFLICT"
        assert "Playlist 9 is running" in outcome.error.message
    assert desk.posts == [] and snapshot_files(tmp_path) == []


@pytest.mark.anyio
async def test_playlist_started_after_the_snapshot_is_a_conflict(tmp_path):
    desk = BundleDevice({**MEMBERS, "4": stored_playlist([3])})
    calls = {"n": 0}

    def start_playlist_on_second_read(device: Any) -> None:
        calls["n"] += 1
        if calls["n"] == 2:  # the recheck after the snapshot
            device.state["pl"] = 7

    desk.before_presets_get = start_playlist_on_second_read
    outcome = await save(tmp_path, desk, preset_id=4, overwrite=True)
    assert outcome.error.code == "PRESET_CONFLICT" and desk.posts == []
    assert len(snapshot_files(tmp_path)) == 1  # the snapshot taken first is kept


@pytest.mark.anyio
async def test_overwrite_snapshots_the_existing_playlist_before_the_post(tmp_path):
    old = stored_playlist([3], name="Old")
    desk = BundleDevice({**MEMBERS, "4": old})
    seen: list[list[str]] = []
    desk.on_post = lambda _body: seen.append(snapshot_files(tmp_path))
    outcome = await save(tmp_path, desk, preset_id=4, overwrite=True)
    assert outcome.ok and len(seen) == 1 and len(seen[0]) == 1
    assert outcome.data["backup_id"] + ".json" == seen[0][0]
    assert outcome.data["overwrote"] is True and outcome.data["existing_type"] == "playlist"


@pytest.mark.anyio
async def test_occupied_destination_without_overwrite_is_a_conflict(tmp_path):
    desk = BundleDevice({**MEMBERS, "4": stored_playlist([3])})
    outcome = await save(tmp_path, desk, preset_id=4)
    assert outcome.error.code == "PRESET_CONFLICT" and desk.posts == []


# ===================================================== invalid input, zero writes


@pytest.mark.parametrize(
    "overrides",
    [
        {"entries": steps(*range(1, 102))},  # more than 100 members
        {"entries": []},
        {"entries": steps(0)},
        {"entries": steps(251)},
        {"end_preset_id": 255},  # restore previous preset: refused as for activation
        {"end_preset_id": 0},
        {"repeat": -1},  # the firmware reads it as endless + shuffle
        {"repeat": 255},  # repeat + 1 would wrap in the firmware's byte
        {"repeat": True},
        {"shuffle": 1},
        {"entries": steps(1, duration_s=-1)},
        {"entries": steps(1, duration_s=0.05)},  # not a multiple of 0.1 s
        {"entries": steps(1, duration_s=4294967.1)},  # above 42949670 tenths
        {"entries": steps(1, duration_s=float("nan"))},
        {"entries": steps(1, transition_s=65.6)},  # x 100 would wrap the live transition
        {"entries": steps(1, transition_s=0.15)},
        {"entries": [{"preset_id": 1, "duration_s": 1}]},  # transition_s missing
        {"entries": [{"preset_id": 1, "duration_s": 1, "transition_s": 0, "dur": 1}]},
        {"overwrite": True},  # needs an explicit preset_id
        {"name": " "},
        {"name": "x" * 33},
        {"r": True},
        {"playlist": {"ps": [1]}},
    ],
)
def test_out_of_range_and_unknown_input_is_rejected_by_the_schema(overrides):
    arguments = request(**overrides)
    with pytest.raises(ValidationError):
        SavePlaylistRequest.model_validate(arguments)


def test_shuffle_and_repeat_are_explicit_fields():
    for missing in ("shuffle", "repeat"):
        arguments = request()
        del arguments[missing]
        with pytest.raises(ValidationError):
            SavePlaylistRequest.model_validate(arguments)


def test_upper_bounds_are_accepted():
    accepted = SavePlaylistRequest.model_validate(
        request(
            entries=steps(*([1] * 100), duration_s=4294967, transition_s=65.5),
            repeat=254,
            end_preset_id=250,
        )
    )
    assert len(accepted.entries) == 100 and accepted.repeat == 254


@pytest.mark.parametrize(
    ("store", "overrides", "code"),
    [
        ({"1": state_preset("A")}, {"entries": steps(1, 7)}, "UNSUPPORTED_CAPABILITY"),
        (
            {"1": state_preset("A"), "2": stored_playlist([1])},
            {"entries": steps(1, 2)},
            "UNSUPPORTED_CAPABILITY",
        ),
        (
            {"1": state_preset("A"), "2": {"win": "T=1", "n": "Cmd"}},
            {"entries": steps(1, 2)},
            "UNSUPPORTED_CAPABILITY",
        ),
        (MEMBERS, {"end_preset_id": 9}, "UNSUPPORTED_CAPABILITY"),
        # The destination itself as a member: saving would start a self-reference.
        (MEMBERS, {"preset_id": 2, "overwrite": True}, "UNSUPPORTED_CAPABILITY"),
    ],
)
@pytest.mark.anyio
async def test_non_state_missing_or_self_members_are_refused_before_any_write(
    tmp_path, store, overrides, code
):
    desk = BundleDevice(store)
    outcome = await save(tmp_path, desk, **overrides)
    assert not outcome.ok and outcome.error.code == code
    assert outcome.application == "not_attempted" and desk.posts == []
    assert snapshot_files(tmp_path) == []


@pytest.mark.anyio
async def test_member_changed_after_the_snapshot_is_a_conflict(tmp_path):
    desk = BundleDevice({**MEMBERS, "4": stored_playlist([3])})
    calls = {"n": 0}

    def drop_member(device: Any) -> None:
        calls["n"] += 1
        if calls["n"] == 2:
            device.store.pop("2")

    desk.before_presets_get = drop_member
    outcome = await save(tmp_path, desk, preset_id=4, overwrite=True)
    assert outcome.error.code == "PRESET_CONFLICT" and desk.posts == []


# ===================================================== uncertain and mismatching writes


@pytest.mark.anyio
async def test_timeout_with_unreadable_readback_is_unknown_and_not_resent(tmp_path):
    desk = BundleDevice(MEMBERS)
    desk.post_mode = "timeout_no_apply"
    desk.presets_get_failure = lambda _count: (
        httpx.ConnectError("synthetic") if desk.posts else None
    )
    outcome = await save(tmp_path, desk)
    assert outcome.error.code == "WRITE_OUTCOME_UNKNOWN"
    assert (outcome.application, outcome.verification) == ("unknown", "unknown")
    assert outcome.data["no_replay"] is True and len(desk.posts) == 1


@pytest.mark.parametrize(
    "mutate",
    [
        lambda entry: entry["playlist"].update(repeat=2),
        lambda entry: entry["playlist"].update(r=0),
        lambda entry: entry["playlist"].update(ps=[2, 1]),
        lambda entry: entry["playlist"].update(transition=[7, 6]),
    ],
)
@pytest.mark.anyio
async def test_semantic_difference_in_the_stored_playlist_is_a_mismatch(tmp_path, mutate):
    desk = BundleDevice(MEMBERS)
    desk.entry_mutator = mutate
    outcome = await save(tmp_path, desk, repeat=3, shuffle=True)
    assert outcome.error.code == "VERIFICATION_MISMATCH"
    assert outcome.data["no_replay"] is True and len(desk.posts) == 1


# ===================================================== shared check used by restore and import


@pytest.mark.anyio
async def test_restore_refuses_a_repeat_the_firmware_byte_would_wrap(tmp_path):
    desk = BundleDevice(MEMBERS)
    fleet = fleet_of(desk)
    async with open_resources(tmp_path, fleet) as resources:
        record = resources.backups.backup_preset(
            "desk",
            8,
            copy.deepcopy(stored_playlist([1, 2], repeat=255)),
            Firmware("16.0.1", None),
        )
        outcome = await call(
            resources, "wled_restore_preset", backup_id=record.backup_id, dry_run=True
        )
    assert outcome.error.code == "UNSUPPORTED_CAPABILITY"
    assert "0-254" in outcome.error.message and fleet.post_count() == 0
