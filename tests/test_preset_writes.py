"""Single-entry preset writes of issue #18: ``wled_store_preset`` and the shared state
route (A18-01, A18-02, A18-05), protocol envelope (A18-14) and log privacy (A18-15).

Mock transport and ``tmp_path`` only; the fake device models the WLED v16.0.1 routes of
docs/SOURCES.md "Issue-18 WLED 16 preset write evidence". The firmware is set explicitly.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import anyio
import httpx2 as httpx
import pytest
from mcp.client import Client
from pydantic import ValidationError

from tests.preset_support import PresetDevice, playlist_entry, state_entry
from tests.state_catalog_support import make_info, make_state
from tests.test_presets import call, desk_with, fleet_of, open_resources, snapshot_files
from wled_mcp.operations import build_operations
from wled_mcp.preset_tools import StorePresetRequest
from wled_mcp.preset_writes import expected_entry
from wled_mcp.server import create_server

FIRMWARE = "16.0.1"
STATE = {
    "on": True,
    "bri": 90,
    "transition": 4,
    "bs": 0,
    "mainseg": 0,
    "seg": [
        {"id": 0, "start": 0, "stop": 30, "col": [[255, 0, 0]], "fx": 1, "n": "Left"},
        {"id": 2, "start": 30, "stop": 60, "on": False, "bri": 0},
    ],
}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def wled16(store: dict[str, Any] | None = None) -> PresetDevice:
    return PresetDevice(
        store={"0": {}, **(store or {})},
        state=make_state(bs=0),
        info=make_info(ver=FIRMWARE),
    )


def sent_object(name: str, state: dict[str, Any] = STATE) -> dict[str, Any]:
    return {**json.loads(json.dumps(state)), "n": name}


# ===================================================== A18-01 state route, live effect


@pytest.mark.anyio
async def test_supplied_state_is_applied_then_stored_verbatim_with_one_post(tmp_path):
    desk = wled16()
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_store_preset", name="Evening", state=STATE)
    assert outcome.ok and (outcome.application, outcome.verification) == ("applied", "verified")
    assert desk.posts == [{**sent_object("Evening"), "psave": 1, "o": True}]
    # Stored exactly: the firmware removed psave and o; nothing else differs.
    assert desk.store["1"] == sent_object("Evening")
    assert outcome.data["preset"] == sent_object("Evening")
    assert outcome.data["type"] == "state" and outcome.data["route"] == "state"
    assert outcome.data["preset_id"] == 1 and outcome.data["allocated"] is True
    assert "Applies the supplied state to the lights" in str(outcome.data["live_effect"])
    assert outcome.data["previous_lighting_restored"] is False
    assert desk.state["bri"] == 90  # the live output changed (ISSUE-18-DEC-001)
    assert snapshot_files(tmp_path) == []  # a free destination needs no snapshot


@pytest.mark.anyio
async def test_dry_run_states_the_live_effect_and_sends_nothing(tmp_path):
    desk = wled16({"3": state_entry("Old")})
    fleet = fleet_of(desk)
    async with open_resources(tmp_path, fleet) as resources:
        outcome = await call(
            resources,
            "wled_store_preset",
            name="Evening",
            state=STATE,
            preset_id=3,
            overwrite=True,
            dry_run=True,
        )
    assert outcome.ok and outcome.dry_run and fleet.post_count() == 0
    assert not (tmp_path / "backups").exists()
    plan = outcome.data["plan"]
    assert plan["will_overwrite"] is True and plan["backup_required"] is True
    assert plan["route"] == "state" and "Applies the supplied state" in plan["live_effect"]
    assert plan["previous_lighting_restored"] is False
    assert outcome.data["payload"] == {**sent_object("Evening"), "psave": 3, "o": True}
    assert any("removed keys o, v, time" in str(p) for p in outcome.data["postconditions"])


@pytest.mark.anyio
async def test_any_stored_difference_including_unknown_fields_is_a_mismatch(tmp_path):
    desk = wled16()
    desk.entry_mutator = lambda entry: entry.update(vendor_extension=1)
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_store_preset", name="Evening", state=STATE)
    assert not outcome.ok and outcome.error.code == "VERIFICATION_MISMATCH"
    assert outcome.data["differences"] == ["vendor_extension"]
    assert outcome.data["no_replay"] is True and len(desk.posts) == 1


@pytest.mark.anyio
async def test_minimal_state_and_omitted_fields_are_absent_not_null(tmp_path):
    desk = wled16()
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_store_preset", name="Off", state={"on": False})
    assert outcome.ok
    assert desk.store["1"] == {"on": False, "n": "Off"}


# ======================================================= A18-02 validation, conflicts


@pytest.mark.parametrize(
    "state",
    [
        {"on": True, "ps": 3},
        {"on": True, "playlist": {"ps": [1]}},
        {"on": True, "win": "T=1"},
        {"on": True, "psave": 4},
        {"on": True, "nl": {"on": True}},
        {"on": True, "udpn": {"send": True}},
        {"on": True, "ledmap": 1},
        {"on": True, "n": "inline name"},
        # #19 TD-19-12: cct and the other WLED 16 keys are accepted within their bounds;
        # out-of-bound values and the excluded keys (ISSUE-19-DEC-002) are refused.
        {"seg": [{"id": 0, "start": 0, "stop": 10, "cct": 256}]},
        {"seg": [{"id": 0, "start": 0, "stop": 10, "c3": 32}]},
        {"seg": [{"id": 0, "start": 0, "stop": 10, "si": 4}]},
        {"seg": [{"id": 0, "start": 0, "stop": 10, "set": 4}]},
        {"seg": [{"id": 0, "start": 0, "stop": 10, "m12": 5}]},
        {"seg": [{"id": 0, "start": 0, "stop": 10, "bm": 17}]},
        {"seg": [{"id": 0, "start": 0, "stop": 10, "startY": -1}]},
        {"seg": [{"id": 0, "start": 0, "stop": 10, "rpt": True}]},
        {"seg": [{"id": 0, "start": 0, "stop": 10, "fxdef": True}]},
        {"seg": [{"id": 0, "start": 0, "stop": 10, "i": [0, [255, 0, 0]]}]},
        {"seg": [{"id": 0, "start": 0}]},
        {"bri": 256},
        {"bri": True},
        {"transition": -1},
        {"transition": 656},  # S2: tenths * 100 would wrap the firmware's uint16_t
        {"on": True, "bs": 32},  # N5: the firmware masks bs with 0x1F
        {},
        {"seg": []},
    ],
)
def test_control_unknown_and_malformed_state_is_refused_by_the_schema(state):
    with pytest.raises(ValidationError):
        StorePresetRequest.model_validate({"device_id": "desk", "name": "N", "state": state})


@pytest.mark.parametrize("name", ["", "   ", "x" * 33, "ä" * 17, "bad\x00", "tab\tname"])
def test_preset_name_rules_are_enforced(name):
    with pytest.raises(ValidationError):
        StorePresetRequest.model_validate({"device_id": "desk", "name": name, "state": STATE})


def test_overwrite_needs_an_explicit_preset_id():
    with pytest.raises(ValidationError):
        StorePresetRequest.model_validate(
            {"device_id": "desk", "name": "N", "state": STATE, "overwrite": True}
        )


def seg(**fields: Any) -> dict[str, Any]:
    return {"id": 0, "start": 0, "stop": 30, **fields}


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("state", "code"),
    [
        ({"seg": [seg(stop=91)]}, "VALIDATION_ERROR"),  # beyond led_count 90
        ({"seg": [seg(id=32)]}, "VALIDATION_ERROR"),  # maxseg 32
        ({"seg": [seg(), seg(id=1, start=20, stop=40)]}, "VALIDATION_ERROR"),  # overlap
        ({"seg": [seg(), seg()]}, "VALIDATION_ERROR"),  # duplicate ID
        ({"seg": [seg(start=30, stop=30)]}, "VALIDATION_ERROR"),
        ({"seg": [seg(of=30)]}, "VALIDATION_ERROR"),
        ({"seg": [seg(fx=6)]}, "VALIDATION_ERROR"),  # fxcount 4
        ({"seg": [seg(pal=3)]}, "VALIDATION_ERROR"),  # palcount 3
        ({"seg": [seg(col=[[1, 2, 3, 4]])]}, "VALIDATION_ERROR"),  # RGB-only device
        ({"seg": [seg(col=[[1, 2, 3]] * 4)]}, "VALIDATION_ERROR"),
        ({"seg": [seg(col=[[1, 2, 300]])]}, "VALIDATION_ERROR"),
        ({"seg": [seg(n="x" * 31 + "ä")]}, "VALIDATION_ERROR"),  # 33 UTF-8 bytes
        ({"seg": [seg(on=True, bri=0)]}, "VALIDATION_ERROR"),
        ({"seg": [seg(bri=0)]}, "VALIDATION_ERROR"),
        ({"on": True, "bri": 0}, "VALIDATION_ERROR"),
        ({"mainseg": 4, "seg": [seg()]}, "VALIDATION_ERROR"),
        ({"on": True, "mainseg": 0}, "VALIDATION_ERROR"),
    ],
)
async def test_out_of_range_state_is_refused_before_any_write(tmp_path, state, code):
    desk = wled16()
    fleet = fleet_of(desk)
    async with open_resources(tmp_path, fleet) as resources:
        for dry_run in (True, False):
            outcome = await call(
                resources, "wled_store_preset", name="N", state=state, dry_run=dry_run
            )
            assert not outcome.ok and outcome.error.code == code, outcome.error
            assert outcome.application == "not_attempted"
    assert fleet.post_count() == 0 and snapshot_files(tmp_path) == []


@pytest.mark.anyio
async def test_colors_need_capability_evidence(tmp_path):
    desk = wled16()
    desk.info["leds"].pop("lc")
    fleet = fleet_of(desk)
    async with open_resources(tmp_path, fleet) as resources:
        refused = await call(
            resources, "wled_store_preset", name="N", state={"seg": [seg(col=[[1, 2, 3]])]}
        )
        accepted = await call(resources, "wled_store_preset", name="N", state={"seg": [seg()]})
    assert refused.error.code == "UNSUPPORTED_CAPABILITY"
    assert accepted.ok and fleet.post_count() == 1


@pytest.mark.anyio
async def test_occupied_id_without_overwrite_is_a_conflict(tmp_path):
    desk = wled16({"4": state_entry("Keep")})
    fleet = fleet_of(desk)
    async with open_resources(tmp_path, fleet) as resources:
        outcome = await call(resources, "wled_store_preset", name="N", state=STATE, preset_id=4)
    assert outcome.error.code == "PRESET_CONFLICT" and fleet.post_count() == 0
    assert desk.store["4"] == state_entry("Keep") and snapshot_files(tmp_path) == []


@pytest.mark.anyio
async def test_overwrite_takes_a_snapshot_before_the_single_post(tmp_path):
    old = playlist_entry([1], name="Old playlist")
    desk = wled16({"1": state_entry("Member"), "4": old})
    seen: list[list[str]] = []
    desk.on_post = lambda body: seen.append(snapshot_files(tmp_path))
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(
            resources, "wled_store_preset", name="New", state=STATE, preset_id=4, overwrite=True
        )
    assert outcome.ok and len(desk.posts) == 1
    assert len(seen) == 1 and len(seen[0]) == 1  # the snapshot existed at POST time
    assert seen[0][0] == f"{outcome.data['backup_id']}.json"
    stored = json.loads((tmp_path / "backups/desk" / seen[0][0]).read_text("utf-8"))
    assert stored["preset"] == old and stored["firmware"]["version"] == FIRMWARE
    assert outcome.data["overwrote"] is True
    assert any("'playlist' entry is replaced by a state entry" in w for w in outcome.warnings)


@pytest.mark.anyio
async def test_backup_failure_sends_nothing(tmp_path, monkeypatch):
    desk = wled16({"4": state_entry("Keep")})
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        monkeypatch.setattr(os, "fsync", lambda fd: (_ for _ in ()).throw(OSError(5, "io")))
        outcome = await call(
            resources, "wled_store_preset", name="N", state=STATE, preset_id=4, overwrite=True
        )
    assert outcome.error.code == "BACKUP_FAILED" and outcome.application == "not_attempted"
    assert desk.posts == [] and desk.store["4"] == state_entry("Keep")


@pytest.mark.anyio
async def test_free_destination_taken_after_planning_is_a_conflict(tmp_path):
    desk = wled16()

    def occupy_on_recheck(device: PresetDevice) -> None:
        if device.get_counts["presets.json"] == 2:
            device.store["1"] = state_entry("Other client")

    desk.before_presets_get = occupy_on_recheck
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_store_preset", name="N", state=STATE)
    assert outcome.error.code == "PRESET_CONFLICT" and desk.posts == []
    assert desk.store["1"] == state_entry("Other client")


@pytest.mark.anyio
async def test_unknown_device_touches_nothing(tmp_path):
    fleet = fleet_of(wled16())
    async with open_resources(tmp_path, fleet) as resources:
        outcome = await call(
            resources, "wled_store_preset", device_id="absent", name="N", state=STATE
        )
    assert outcome.error.code == "UNKNOWN_DEVICE" and outcome.device_id is None
    assert fleet.calls == []


# ===================================================== A18-05 uncertain, never replayed


@pytest.mark.anyio
async def test_timeout_with_unreadable_readback_is_unknown_and_not_resent(tmp_path):
    desk = wled16()
    desk.post_mode = "timeout_no_apply"
    desk.presets_get_failure = lambda _count: (
        httpx.ConnectError("synthetic") if desk.posts else None
    )
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        first = await call(resources, "wled_store_preset", name="N", state=STATE)
        assert not first.ok and first.error.code == "WRITE_OUTCOME_UNKNOWN"
        assert (first.application, first.verification) == ("unknown", "unknown")
        assert first.data["no_replay"] is True and len(desk.posts) == 1
        # A later call is a new, explicit invocation that plans again from fresh reads.
        desk.post_mode = "ok"
        desk.presets_get_failure = None
        second = await call(resources, "wled_store_preset", name="N", state=STATE)
    assert second.ok and len(desk.posts) == 2


@pytest.mark.anyio
async def test_timeout_after_apply_reconciles_by_readback(tmp_path):
    desk = wled16()
    desk.post_mode = "timeout_after_apply"
    desk.persist_delay = 2
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_store_preset", name="N", state=STATE)
    assert outcome.ok and len(desk.posts) == 1
    assert "Transport error during write; outcome reconciled by readback." in outcome.warnings


@pytest.mark.anyio
async def test_running_playlist_is_named_as_interrupted(tmp_path):
    desk = wled16({"1": state_entry("Member"), "7": playlist_entry([1])})
    desk.state.update(pl=7, ps=1)
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        outcome = await call(resources, "wled_store_preset", name="N", state=STATE, dry_run=True)
    assert outcome.data["plan"]["live_before"] == {"active_preset_id": 1, "active_playlist_id": 7}
    assert any("Playlist 7 is running" in w for w in outcome.warnings)


# ===================================================== A18-14 protocol envelope


@pytest.mark.anyio
async def test_protocol_envelope_and_schema_errors_for_the_new_tools(tmp_path):
    desk = wled16()
    fleet = fleet_of(desk)
    async with open_resources(tmp_path, fleet) as resources:
        server = create_server(build_operations(resources))
        with anyio.fail_after(30):
            async with Client(server) as client:
                tools = {tool.name: tool for tool in (await client.list_tools()).tools}
                for name in ("wled_list_snapshots", "wled_restore_preset", "wled_store_preset"):
                    assert tools[name].input_schema["additionalProperties"] is False
                store_schema = tools["wled_store_preset"].input_schema
                assert "LIVE EFFECT" in (tools["wled_store_preset"].description or "")
                assert "LIVE EFFECT" in (tools["wled_restore_preset"].description or "")
                assert "state" in store_schema["required"]
                result = await client.call_tool(
                    "wled_store_preset",
                    {"device_id": "desk", "name": "N", "state": STATE, "dry_run": True},
                )
                assert json.loads(result.content[0].text) == result.structured_content
                assert result.is_error is False
                refused = await client.call_tool(
                    "wled_store_preset",
                    {"device_id": "desk", "name": "N", "state": {"on": True, "win": "T=1"}},
                )
                assert refused.structured_content["error"]["code"] == "VALIDATION_ERROR"
                assert refused.is_error is True
                listing = await client.call_tool("wled_list_snapshots", {"device_id": "desk"})
                assert json.loads(listing.content[0].text) == listing.structured_content
    assert fleet.post_count() == 0


@pytest.mark.anyio
async def test_list_snapshots_tool_warns_when_backups_root_is_a_symlink(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    (tmp_path / "backups").symlink_to(real, target_is_directory=True)
    resources = open_resources(tmp_path, fleet_of(desk_with({})))
    listing = await call(resources, "wled_list_snapshots")
    assert listing.data["snapshots"] == []
    assert any("symbolic link" in warning for warning in listing.warnings)


# ===================================================== A18-15 log privacy


@pytest.mark.anyio
async def test_logs_carry_no_preset_names_or_objects(tmp_path, caplog, monkeypatch):
    desk = wled16({"5": state_entry("PRIVATE-OLD")})
    private = {"seg": [seg(n="PRIVATE-SEG")]}
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        with caplog.at_level(logging.DEBUG):
            await call(
                resources,
                "wled_store_preset",
                name="PRIVATE-NEW",
                state=private,
                preset_id=5,
                overwrite=True,
            )
            listing = await call(resources, "wled_list_snapshots")
            backup_id = listing.data["snapshots"][0]["backup_id"]
            await call(
                resources, "wled_restore_preset", backup_id=backup_id, preset_id=6, dry_run=True
            )
            monkeypatch.setattr(os, "fsync", lambda fd: (_ for _ in ()).throw(OSError(5, "io")))
            await call(
                resources,
                "wled_store_preset",
                name="PRIVATE-AGAIN",
                state=private,
                preset_id=5,
                overwrite=True,
            )
    assert "PRIVATE" not in caplog.text


def test_state_transition_and_blending_style_upper_bounds_are_accepted():
    request = StorePresetRequest.model_validate(
        {"device_id": "desk", "name": "N", "state": {"on": True, "transition": 655, "bs": 31}}
    )
    assert (request.state.transition, request.state.bs) == (655, 31)


def test_firmware_removed_keys_are_excluded_from_the_expected_entry():
    # N1: only o and psave are ever sent; v, time, error and bootps cannot reach the
    # writer (schema and state classification), but the comparison follows the firmware.
    sent = {"on": True, "n": "N", "o": True, "v": True, "time": 1, "error": 0, "bootps": 3}
    assert expected_entry("state", {**sent, "psave": 4}, 4) == {"on": True, "n": "N"}
    assert expected_entry("state", {"on": True}, 4) == {"on": True, "n": "Preset 4"}
