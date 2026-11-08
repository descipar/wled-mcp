"""Preset bundle export and import of issue #18: A18-08 to A18-15.

Mock transport and ``tmp_path`` only; no LAN access. The synthetic devices of
``tests/bundle_support.py`` set firmware 16.0.1, LED count, segment maximum, matrix and
catalogs explicitly. Each import write uses the v16.0.1 single-entry routes modelled by
``tests/preset_support.py``.
"""

from __future__ import annotations

import copy
import json
import logging
import os
from typing import Any

import anyio
import httpx2 as httpx
import pytest
from mcp.client import Client

from tests.bundle_support import (
    EFFECTS,
    FIXTURE,
    PALETTES,
    BundleDevice,
    call,
    fleet_of,
    freeze_deadline_clock,
    load_fixture,
    open_resources,
    state_preset,
    stored_playlist,
)
from tests.test_presets import snapshot_files
from wled_mcp import bundle_tools
from wled_mcp.bundles import (
    MAX_BUNDLE_BYTES,
    BundleEntry,
    parse_bundle,
    referenced_catalog_ids,
)
from wled_mcp.client import ClientFailure
from wled_mcp.operations import build_operations
from wled_mcp.preset_writes import playlist_differences
from wled_mcp.presets import classify
from wled_mcp.server import create_server

SECRETS = ("desk.invalid", "192.0.2.10", "00005e005301", "00:00:5e:00:53:01", "Example desk")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def fixture_device() -> BundleDevice:
    """The device whose export is retained as examples/contracts/preset-bundle.json."""
    return BundleDevice(
        {
            "1": state_preset("Warm", fx=4),
            "2": state_preset("Sea", fx=2, pal=3),
            "3": stored_playlist([1, 2], name="Evening", repeat=2),
        }
    )


async def export(tmp_path, desk: BundleDevice, **arguments: Any):
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        return await call(resources, "wled_export_presets", **arguments)


async def import_(tmp_path, desk: BundleDevice, bundle: Any, **arguments: Any):
    fleet = fleet_of(desk)
    async with open_resources(tmp_path, fleet) as resources:
        outcome = await call(resources, "wled_import_presets", bundle=bundle, **arguments)
    return outcome, fleet


def bundle_with(*entries: dict[str, Any], **source: Any) -> dict[str, Any]:
    """A bundle as the source device (default catalogs) would export these entries."""
    bundle = load_fixture()
    bundle["presets"] = list(entries)
    bundle["source"]["capabilities"].update(source)
    fx_ids, pal_ids = referenced_catalog_ids(
        [BundleEntry(e["source_id"], e["name"], e["type"], e["preset"]) for e in entries]
    )
    bundle["catalog"] = {
        "effects": {str(i): EFFECTS[i] for i in sorted(fx_ids)},
        "palettes": {str(i): PALETTES[i] for i in sorted(pal_ids)},
    }
    return bundle


def item(source_id: int, preset: Any) -> dict[str, Any]:
    """A bundle entry with the type the classifier gives the object."""
    name = preset.get("n") if isinstance(preset, dict) else None
    return {"source_id": source_id, "name": name, "type": classify(preset)[0], "preset": preset}


# ================================================================== A18-08 export


@pytest.mark.anyio
async def test_export_carries_verbatim_typed_objects_and_no_device_data(tmp_path):
    warm = state_preset("Warm", fx=4, vendor_extension={"k": 1})  # unknown fields kept
    del warm["vendor_extension"]
    warm["seg"][0]["future_field"] = 7
    store = {
        "1": warm,
        "2": stored_playlist([1], name="Loop"),
        "3": {"win": "T=2", "n": "Command"},
        "4": {"on": True, "nl": {"on": True}, "n": "Night"},
        "6": [1, 2],
    }
    desk = BundleDevice(store)
    outcome = await export(tmp_path, desk)
    assert outcome.ok and outcome.application == "not_attempted"
    bundle = outcome.data["bundle"]
    assert [(p["source_id"], p["type"]) for p in bundle["presets"]] == [
        (1, "state"),
        (2, "playlist"),
    ]
    assert bundle["presets"][0]["preset"] == warm  # verbatim, unknown seg field included
    assert bundle["presets"][1]["preset"] == store["2"]
    assert outcome.data["excluded"] == [
        {"source_id": 3, "type": "api-command", "malformed": False},
        {"source_id": 4, "type": "unknown", "malformed": False},
        {"source_id": 6, "type": "unknown", "malformed": True},
    ]
    assert any("include_unwritable=true" in warning for warning in outcome.warnings)
    assert bundle["catalog"] == {"effects": {"4": "Fire 2012"}, "palettes": {"0": "Default"}}
    assert set(bundle) == {
        "format",
        "format_version",
        "created_at",
        "source",
        "catalog",
        "presets",
    }
    text = json.dumps(outcome.data).casefold()
    for secret in SECRETS:
        assert secret.casefold() not in text
    assert '"desk"' not in text and "bssid" not in text and '"info"' not in text
    assert desk.posts == []
    parse_bundle(bundle)  # an export is always readable by the parser


@pytest.mark.anyio
async def test_include_unwritable_exports_every_type_for_inspection(tmp_path):
    desk = BundleDevice({"3": {"win": "T=2", "n": "Command"}, "6": [1, 2]})
    outcome = await export(tmp_path, desk, include_unwritable=True)
    presets = outcome.data["bundle"]["presets"]
    assert any("only this device's host, IP, MAC and BSSID" in w for w in outcome.warnings)
    assert [(p["source_id"], p["type"], p["name"]) for p in presets] == [
        (3, "api-command", "Command"),
        (6, "unknown", None),
    ]
    assert presets[1]["preset"] == [1, 2] and outcome.data["importable"] is False
    parse_bundle(outcome.data["bundle"])


@pytest.mark.anyio
async def test_export_of_selected_ids_and_a_missing_id(tmp_path):
    desk = fixture_device()
    selected = await export(tmp_path, desk, preset_ids=[2])
    assert [p["source_id"] for p in selected.data["bundle"]["presets"]] == [2]
    assert selected.data["bundle"]["catalog"]["effects"] == {"2": "Breathe"}
    missing = await export(tmp_path, desk, preset_ids=[2, 9])
    assert missing.error.code == "PRESET_NOT_FOUND"


@pytest.mark.anyio
async def test_export_refuses_preset_text_that_contains_a_device_address(tmp_path):
    leaky = state_preset("Leak")
    leaky["seg"][0]["n"] = "see 192.0.2.10"
    desk = BundleDevice({"1": state_preset("Fine"), "2": leaky})
    outcome = await export(tmp_path, desk)
    assert outcome.error.code == "VALIDATION_ERROR" and "[2]" in outcome.error.message
    assert "192.0.2.10" not in json.dumps(outcome.model_dump())
    assert (await export(tmp_path, desk, preset_ids=[1])).ok


@pytest.mark.anyio
async def test_export_above_the_size_bound_fails_with_a_selection_hint(tmp_path, monkeypatch):
    monkeypatch.setattr(bundle_tools, "MAX_BUNDLE_BYTES", 500)
    outcome = await export(tmp_path, fixture_device())
    assert outcome.error.code == "VALIDATION_ERROR"
    assert "preset_ids" in outcome.error.reconciliation


@pytest.mark.anyio
async def test_retained_fixture_is_actual_export_output_and_parses(tmp_path):
    outcome = await export(tmp_path, fixture_device())
    assert outcome.data["bundle"] == load_fixture()
    parsed = parse_bundle(FIXTURE.read_text(encoding="utf-8"))
    assert [entry.type for entry in parsed.entries] == ["state", "state", "playlist"]
    assert parsed.effects == {2: "Breathe", 4: "Fire 2012"}


# ================================================================== A18-09 parser


def text_of(bundle: dict[str, Any]) -> str:
    return json.dumps(bundle)


@pytest.mark.parametrize(
    ("mutate", "fragment"),
    [
        (lambda b: b.update(format="other"), "'format' must be"),
        (lambda b: b.update(format_version=2), "format_version 2"),
        (lambda b: b.update(format_version=9999), "format_version 9999"),
        (lambda b: b.update(format_version=0), "format_version 0"),
        (lambda b: b.update(format_version="1"), "integer 0-9999"),
        (lambda b: b.update(format_version=True), "integer 0-9999"),
        (lambda b: b.update(format_version=10000), "integer 0-9999"),
        (lambda b: b.update(signature="x"), "Unknown bundle key 'signature'"),
        (lambda b: b.pop("catalog"), "Missing bundle key 'catalog'"),
        (lambda b: b.update(created_at="yesterday"), "created_at"),
        (lambda b: b["source"].update(device_id="desk"), "Unknown key 'device_id'"),
        (lambda b: b["source"]["capabilities"].update(matrix={"w": 0, "h": 2}), "matrix"),
        (lambda b: b["catalog"]["effects"].update({"01": "x"}), "catalog ID"),
        (lambda b: b["presets"][0].update(source_id=0), "1-250"),
        (lambda b: b["presets"][0].update(source_id=251), "1-250"),
        (lambda b: b["presets"][0].update(source_id="1"), "1-250"),
        (lambda b: b["presets"][1].update(source_id=1), "more than once"),
        (lambda b: b["presets"][2].update(type="state"), "never treated as a state preset"),
        (lambda b: b["presets"][0].update(type="playlist"), "does not match"),
        (lambda b: b["presets"][0].update(name="Other"), "name"),
        (lambda b: b["presets"][0].update(extra=1), "Unknown key 'extra'"),
        (lambda b: b.update(presets={}), "must be a list"),
    ],
)
def test_parser_rejects_invalid_bundles_naming_the_problem(mutate, fragment):
    bundle = load_fixture()
    mutate(bundle)
    for form in (bundle, text_of(bundle)):
        with pytest.raises(ClientFailure) as raised:
            parse_bundle(form)
        assert raised.value.error.code == "VALIDATION_ERROR"
        assert fragment in raised.value.error.message


@pytest.mark.parametrize(
    "text",
    [
        '{"format": "wled-mcp.preset-bundle", "format": "wled-mcp.preset-bundle"}',
        text_of(load_fixture()).replace('"bri": 128', '"bri": NaN', 1),
        text_of(load_fixture()).replace('"bri": 128', '"bri": Infinity', 1),
        text_of(load_fixture())[:-1],
        "[" * 5000 + "]" * 5000,
    ],
)
def test_parser_rejects_duplicate_keys_non_finite_numbers_and_bad_json(text):
    with pytest.raises(ClientFailure) as raised:
        parse_bundle(text)
    assert raised.value.error.code == "VALIDATION_ERROR"


def test_parser_rejects_oversize_bundles_in_both_forms():
    bundle = load_fixture()
    bundle["presets"][0]["preset"]["seg"][0]["n"] = "x" * MAX_BUNDLE_BYTES
    bundle["presets"][0]["name"] = "Warm"
    for form in (bundle, text_of(bundle)):
        with pytest.raises(ClientFailure) as raised:
            parse_bundle(form)
        assert str(MAX_BUNDLE_BYTES) in raised.value.error.message


@pytest.mark.parametrize(
    "bundle",
    [
        {**load_fixture(), "format_version": 2},
        "{not json",
        bundle_with(*[item(i, state_preset(f"P{i}")) for i in range(1, 52)]),
    ],
)
@pytest.mark.anyio
async def test_rejected_bundles_cause_zero_device_io(tmp_path, bundle):
    outcome, fleet = await import_(tmp_path, BundleDevice(), bundle)
    assert outcome.error.code == "VALIDATION_ERROR" and fleet.calls == []


# ================================================================== A18-10 dry run


@pytest.mark.anyio
async def test_dry_run_names_every_mismatch_mapping_and_overwrite_without_writing(tmp_path):
    two_d = state_preset("Matrix")
    two_d["seg"][0].update(startY=0, stopY=4)
    bundle = bundle_with(
        item(1, state_preset("Long", stop=80)),  # beyond 60 target LEDs
        item(2, state_preset("Fiery", fx=4)),  # effect 4 is named differently on the target
        item(3, two_d),  # 2D geometry, matrix differs
        item(4, state_preset("Many", seg=[{"id": i, "start": i, "stop": i + 1} for i in range(4)])),
        item(5, state_preset("Kept", fx=2)),  # same name at the same ID
        item(6, stored_playlist([5, 9], name="Loop")),  # 9 is neither in the bundle nor mapped
        matrix={"w": 8, "h": 4},
    )
    desk = BundleDevice(
        {"5": state_preset("Occupied")},
        led_count=60,
        maxseg=3,
        matrix={"w": 4, "h": 4},
        effects=["Solid", "Blink", "Breathe", "Fire 2012", "Ripple"],
    )
    outcome, fleet = await import_(tmp_path, desk, bundle, id_map={"5": 5}, dry_run=True)
    assert outcome.dry_run and not outcome.ok and outcome.application == "not_attempted"
    assert fleet.post_count() == 0 and not (tmp_path / "backups").exists()
    plan = outcome.data["plan"]
    entries = {entry["source_id"]: entry for entry in plan["entries"]}
    assert plan["executable"] is False
    assert any("exceeds the target LED count 60" in m for m in entries[1]["blocking"])
    assert any("named differently" in m for m in entries[2]["blocking"])
    assert plan["required_mappings"] == [
        {
            "kind": "effect",
            "source_id": 4,
            "source_name": "Fire 2012",
            "proposed_target_id": 3,
            "proposed_target_name": "Fire 2012",
        }
    ]
    assert any("2D segment geometry" in m for m in entries[3]["blocking"])
    assert any("allows 3" in m for m in entries[4]["blocking"])
    assert entries[5]["destination_id"] == 5 and entries[5]["existing_type"] == "state"
    assert any("overwrite_ids" in m for m in entries[5]["blocking"])
    assert any("Member 9" in m for m in entries[6]["blocking"])
    assert entries[6]["member_map"] == {"5": 5, "9": None}
    assert plan["write_order"] == [1, 2, 3, 4, 5, 6]
    assert entries[6]["route"] == "playlist" and "Starts the playlist" in entries[6]["live_effect"]
    assert "applied to the lights" in plan["live_effect"]
    assert plan["backup_required"] is True


@pytest.mark.anyio
async def test_valid_dry_run_shows_destinations_routes_and_sends_nothing(tmp_path):
    desk = BundleDevice({"1": state_preset("Existing")})
    desk.state.update(ps=2)
    outcome, fleet = await import_(tmp_path, desk, load_fixture(), dry_run=True)
    assert "Entry 1: Destination 2 is the active preset marker (state.ps); it is replaced." in (
        outcome.warnings
    )
    assert outcome.ok and outcome.dry_run and fleet.post_count() == 0
    plan = outcome.data["plan"]
    rows = [(e["source_id"], e["destination_id"], e["route"]) for e in plan["entries"]]
    assert rows == [(1, 2, "state"), (2, 3, "state"), (3, 4, "playlist")]
    assert plan["entries"][2]["member_map"] == {"1": 2, "2": 3}
    assert plan["backup_required"] is False and plan["executable"] is True
    assert not (tmp_path / "backups").exists()


@pytest.mark.anyio
async def test_explicit_effect_map_accepts_the_proposal_and_rewrites_the_entry(tmp_path):
    desk = BundleDevice(effects=["Solid", "Blink", "Breathe", "Fire 2012"])
    bundle = bundle_with(item(1, state_preset("Fiery", fx=4)))
    outcome, _fleet = await import_(tmp_path, desk, bundle, effect_map={"4": 3})
    assert outcome.ok
    assert desk.store["1"]["seg"][0]["fx"] == 3
    expected = copy.deepcopy(state_preset("Fiery", fx=4))
    expected["seg"][0]["fx"] = 3
    assert desk.store["1"] == expected


@pytest.mark.anyio
async def test_unwritable_entries_multiple_playlists_and_stale_overwrite_intent_block(tmp_path):
    cases = [
        (bundle_with(item(1, {"win": "T=1", "n": "Cmd"})), {}, "never imported"),
        (
            bundle_with(
                item(1, state_preset("A")),
                item(2, stored_playlist([1])),
                item(3, stored_playlist([1], name="Two")),
            ),
            {},
            "one playlist per call",
        ),
        (bundle_with(item(1, state_preset("A"))), {"overwrite_ids": [9]}, "overwrite_ids [9]"),
        (bundle_with(item(1, state_preset("A"))), {"id_map": {"9": 3}}, "id_map keys [9]"),
        (
            bundle_with(item(1, state_preset("A")), item(2, state_preset("B"))),
            {"id_map": {"1": 7, "2": 7}},
            "twice",
        ),
    ]
    for bundle, arguments, fragment in cases:
        desk = BundleDevice()
        outcome, fleet = await import_(tmp_path, desk, bundle, **arguments)
        assert not outcome.ok and outcome.application == "not_attempted"
        assert fragment in json.dumps(outcome.model_dump())
        assert fleet.post_count() == 0


@pytest.mark.anyio
async def test_matching_2d_geometry_and_cct_without_capability(tmp_path):
    entry = state_preset("Grid")
    entry["seg"][0].update(startY=0, stopY=4, cct=127)
    bundle = bundle_with(item(1, entry), matrix={"w": 8, "h": 4})
    desk = BundleDevice(matrix={"w": 8, "h": 4}, lc=1)
    outcome, _fleet = await import_(tmp_path, desk, bundle)
    assert outcome.ok and desk.store["1"] == entry
    assert any(w.startswith("Entry 1:") and "'cct'" in w for w in outcome.warnings)


@pytest.mark.anyio
@pytest.mark.parametrize("lc", [5, 7], ids=["rgb-cct", "rgbw-cct"])
async def test_cct_entry_on_a_cct_target_has_no_cct_warning(tmp_path, lc):
    """The aggregate ``info.leds.lc`` carries the CCT bit 0x04: no 'cct' warning."""
    entry = state_preset("Warm white")
    entry["seg"][0].update(cct=200)
    desk = BundleDevice(lc=lc)
    outcome, _fleet = await import_(tmp_path, desk, bundle_with(item(1, entry)))
    assert outcome.ok and desk.store["1"] == entry
    assert not any("'cct'" in w for w in outcome.warnings), outcome.warnings


@pytest.mark.anyio
async def test_running_playlist_blocks_a_playlist_import_but_names_state_interruption(tmp_path):
    desk = BundleDevice({"9": state_preset("M"), "8": stored_playlist([9])})
    desk.state.update(pl=8, ps=9)
    outcome, fleet = await import_(tmp_path, desk, load_fixture(), dry_run=True)
    assert outcome.error.code == "PRESET_CONFLICT" and "Playlist 8 is running" in str(
        outcome.data["plan"]["entries"][2]["blocking"]
    )
    states_only = bundle_with(item(1, state_preset("A")))
    outcome, fleet = await import_(tmp_path, desk, states_only, dry_run=True)
    assert outcome.ok and any("Playlist 8 is running" in w for w in outcome.warnings)
    assert fleet.post_count() == 0


# ================================================================== A18-11 execution


@pytest.mark.anyio
async def test_snapshots_precede_the_first_post_and_members_precede_playlists(
    tmp_path, monkeypatch
):
    freeze_deadline_clock(monkeypatch)  # snapshot I/O time must not race the 1 s window
    bundle = load_fixture()
    bundle["presets"] = [bundle["presets"][2], *bundle["presets"][:2]]  # playlist listed first
    desk = BundleDevice({"1": state_preset("Old one"), "2": state_preset("Old two")})
    at_post: list[list[str]] = []
    desk.on_post = lambda _body: at_post.append(snapshot_files(tmp_path))
    outcome, _fleet = await import_(
        tmp_path, desk, bundle, id_map={"1": 1, "2": 2}, overwrite_ids=[1, 2]
    )
    assert outcome.ok and (outcome.application, outcome.verification) == ("applied", "verified")
    assert [len(files) for files in at_post] == [2, 2, 2]  # both snapshots before POST 1
    assert [("playlist" in body, body["psave"]) for body in desk.posts] == [
        (False, 1),
        (False, 2),
        (True, 3),
    ]
    assert [e["status"] for e in outcome.data["entries"]] == ["verified"] * 3
    assert outcome.data["completed"] == 3 and len(outcome.data["backup_ids"]) == 2
    assert desk.store["3"]["playlist"]["ps"] == [1, 2]
    assert desk.state["pl"] == 3  # the playlist entry started


@pytest.mark.anyio
async def test_backup_failure_sends_nothing(tmp_path, monkeypatch):
    desk = BundleDevice({"1": state_preset("Old")})
    monkeypatch.setattr(os, "fsync", lambda fd: (_ for _ in ()).throw(OSError(5, "io")))
    outcome, fleet = await import_(
        tmp_path, desk, load_fixture(), id_map={"1": 1}, overwrite_ids=[1]
    )
    assert outcome.error.code == "BACKUP_FAILED" and outcome.application == "not_attempted"
    assert fleet.post_count() == 0


@pytest.mark.anyio
async def test_destination_taken_after_planning_is_a_conflict_before_any_post(tmp_path):
    desk = BundleDevice()
    reads = {"n": 0}

    def occupy(device: Any) -> None:
        reads["n"] += 1
        if reads["n"] == 2:  # the recheck after the snapshots
            device.store["2"] = state_preset("Other client")

    desk.before_presets_get = occupy
    outcome, fleet = await import_(tmp_path, desk, load_fixture())
    assert outcome.error.code == "PRESET_CONFLICT" and fleet.post_count() == 0


# ================================================================== A18-12 partial import


@pytest.mark.anyio
async def test_unreadable_kth_write_stops_the_import_without_any_resend(tmp_path, monkeypatch):
    bundle = bundle_with(*[item(i, state_preset(f"P{i}")) for i in (1, 2, 3)])
    desk = BundleDevice({str(i): state_preset(f"Old {i}") for i in (1, 2, 3)})
    clock = freeze_deadline_clock(monkeypatch)

    def unreadable_after_second_post(_count: int) -> Exception | None:
        if len(desk.posts) < 2:
            return None
        # The readback stays unreadable until the entry's deadline: advance the controlled
        # clock past the 1 s per-write window (but not the 5 s overall one), without waiting.
        clock.offset = 2.0
        return httpx.ConnectError("synthetic")

    desk.presets_get_failure = unreadable_after_second_post
    desk.post_mode = "ok"

    def timeout_second(body: dict[str, Any]) -> None:
        if len(desk.posts) == 2:
            desk.post_mode = "timeout_no_apply"

    desk.on_post = timeout_second
    outcome, fleet = await import_(
        tmp_path,
        desk,
        bundle,
        id_map={"1": 1, "2": 2, "3": 3},
        overwrite_ids=[1, 2, 3],
    )
    assert fleet.post_count() == 2  # entry 2 was sent once, entry 3 never
    assert outcome.error.code == "WRITE_OUTCOME_UNKNOWN"
    # Proven partial steps, final postcondition not reached.
    assert (outcome.application, outcome.verification) == ("applied", "mismatch")
    assert [e["status"] for e in outcome.data["entries"]] == [
        "verified",
        "unknown",
        "not_attempted",
    ]
    assert outcome.data["no_replay"] is True and outcome.data["completed"] == 1
    assert len(outcome.data["backup_ids"]) == 3
    assert sorted(f[:-5] for f in snapshot_files(tmp_path)) == sorted(outcome.data["backup_ids"])


@pytest.mark.anyio
async def test_first_entry_mismatch_and_later_conflict_outcomes(tmp_path):
    bundle = bundle_with(item(1, state_preset("A")), item(2, state_preset("B")))
    desk = BundleDevice()
    desk.entry_mutator = lambda entry: entry.update(vendor=1)
    outcome, fleet = await import_(tmp_path, desk, bundle)
    assert outcome.error.code == "VERIFICATION_MISMATCH" and fleet.post_count() == 1
    assert (outcome.application, outcome.verification) == ("unknown", "mismatch")
    assert outcome.data["entries"][0]["differences"] == ["vendor"]

    desk = BundleDevice()
    desk.on_post = lambda body: desk.store.update({"2": state_preset("Racer")})
    outcome, fleet = await import_(tmp_path / "second", desk, bundle)
    assert outcome.error.code == "PRESET_CONFLICT" and fleet.post_count() == 1
    assert (outcome.application, outcome.verification) == ("applied", "mismatch")
    assert [e["status"] for e in outcome.data["entries"]] == ["verified", "not_attempted"]


@pytest.mark.anyio
async def test_member_mapped_to_an_existing_target_state_preset(tmp_path):
    bundle = bundle_with(item(2, stored_playlist([7, 8], name="Mixed")))
    desk = BundleDevice({"20": state_preset("Seven"), "21": stored_playlist([20])})
    blocked, _fleet = await import_(tmp_path, desk, bundle, id_map={"7": 20, "8": 21})
    assert blocked.error.code == "UNSUPPORTED_CAPABILITY" and "Member 8" in json.dumps(blocked.data)
    desk = BundleDevice({"20": state_preset("Seven"), "22": state_preset("Eight")})
    outcome, _fleet = await import_(tmp_path, desk, bundle, id_map={"7": 20, "8": 22})
    assert outcome.ok and desk.store["1"]["playlist"]["ps"] == [20, 22]


# ================================================================== A18-13 roundtrip


@pytest.mark.anyio
async def test_roundtrip_export_import_reproduces_the_objects(tmp_path):
    source = fixture_device()
    exported = await export(tmp_path / "a", source)
    target = BundleDevice()
    text = json.dumps(exported.data["bundle"])  # the JSON text form is accepted too
    outcome, _fleet = await import_(tmp_path / "b", target, text)
    assert outcome.ok
    assert target.store["1"] == source.store["1"]  # state entries exact
    assert target.store["2"] == source.store["2"]
    playlist = source.store["3"]
    assert playlist_differences(target.store["3"], playlist) == []  # playlist semantic


# ================================================================== A18-14 parity


@pytest.mark.anyio
async def test_protocol_envelope_and_schema_errors_for_the_new_tools(tmp_path):
    desk = BundleDevice({"1": state_preset("A"), "2": state_preset("B")})
    fleet = fleet_of(desk)
    async with open_resources(tmp_path, fleet) as resources:
        server = create_server(build_operations(resources))
        with anyio.fail_after(30):
            async with Client(server) as client:
                tools = {tool.name: tool for tool in (await client.list_tools()).tools}
                for name in ("wled_save_playlist", "wled_export_presets", "wled_import_presets"):
                    assert tools[name].input_schema["additionalProperties"] is False
                for name in ("wled_save_playlist", "wled_import_presets"):
                    assert "LIVE EFFECT" in (tools[name].description or "")
                exported = await client.call_tool("wled_export_presets", {"device_id": "desk"})
                assert json.loads(exported.content[0].text) == exported.structured_content
                bundle = exported.structured_content["data"]["bundle"]
                preview = await client.call_tool(
                    "wled_import_presets",
                    {"device_id": "desk", "bundle": bundle, "dry_run": True},
                )
                assert json.loads(preview.content[0].text) == preview.structured_content
                assert preview.is_error is False
                playlist = await client.call_tool(
                    "wled_save_playlist",
                    {
                        "device_id": "desk",
                        "name": "L",
                        "entries": [{"preset_id": 1, "duration_s": 1, "transition_s": 0}],
                        "repeat": 0,
                        "shuffle": False,
                        "dry_run": True,
                    },
                )
                assert playlist.is_error is False
                for name, arguments in (
                    ("wled_save_playlist", {"device_id": "desk", "name": "L", "entries": []}),
                    ("wled_import_presets", {"device_id": "desk", "bundle": 3}),
                    (
                        "wled_import_presets",
                        {"device_id": "desk", "bundle": {}, "id_map": {"x": 1}},
                    ),
                    ("wled_export_presets", {"device_id": "desk", "preset_ids": [1, 1]}),
                ):
                    refused = await client.call_tool(name, arguments)
                    assert refused.is_error is True
                    assert refused.structured_content["error"]["code"] == "VALIDATION_ERROR"
    assert fleet.post_count() == 0


# ================================================================== A18-15 log privacy


@pytest.mark.anyio
async def test_logs_carry_no_bundle_content_names_or_addresses(tmp_path, caplog, monkeypatch):
    desk = BundleDevice({"1": state_preset("PRIVATE-ONE"), "2": state_preset("PRIVATE-TWO")})
    private = bundle_with(
        item(1, state_preset("PRIVATE-NEW")), item(2, stored_playlist([1], name="PRIVATE-PL"))
    )
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        with caplog.at_level(logging.DEBUG):
            await call(resources, "wled_export_presets", include_unwritable=True)
            await call(resources, "wled_import_presets", bundle=private, dry_run=True)
            await call(
                resources,
                "wled_import_presets",
                bundle=private,
                id_map={"1": 1, "2": 3},
                overwrite_ids=[1],
            )
            await call(
                resources,
                "wled_save_playlist",
                name="PRIVATE-LIST",
                entries=[{"preset_id": 2, "duration_s": 1, "transition_s": 0}],
                repeat=0,
                shuffle=False,
                dry_run=True,
            )
            monkeypatch.setattr(os, "fsync", lambda fd: (_ for _ in ()).throw(OSError(5, "io")))
            await call(
                resources,
                "wled_import_presets",
                bundle=json.dumps(private),
                id_map={"1": 2},
                overwrite_ids=[2],
            )
    assert "PRIVATE" not in caplog.text
    # The server logs at WARNING (cli.py); library request lines below it are not emitted.
    emitted = " ".join(r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING)
    for secret in SECRETS:
        assert secret not in emitted


# ================================================================== review round 1


def test_parser_rejects_a_duplicate_key_in_an_otherwise_valid_bundle():
    # Without the duplicate the text is a valid bundle, so only duplicate detection fails it.
    valid = text_of(load_fixture())
    parse_bundle(valid)
    text = valid.replace('"bri": 128', '"bri": 128, "bri": 5', 1)
    with pytest.raises(ClientFailure) as raised:
        parse_bundle(text)
    assert raised.value.error.code == "VALIDATION_ERROR"
    assert "duplicate" in raised.value.error.message


@pytest.mark.anyio
async def test_import_snapshots_survive_each_others_retention_pruning(tmp_path, monkeypatch):
    freeze_deadline_clock(monkeypatch)  # three snapshot files must not race the 1 s window
    bundle = bundle_with(*[item(i, state_preset(f"P{i}")) for i in (1, 2, 3)])
    desk = BundleDevice({str(i): state_preset(f"Old {i}") for i in (1, 2, 3)})
    async with open_resources(tmp_path, fleet_of(desk)) as resources:
        resources.backups.retain_per_device = 1
        outcome = await call(
            resources,
            "wled_import_presets",
            bundle=bundle,
            id_map={"1": 1, "2": 2, "3": 3},
            overwrite_ids=[1, 2, 3],
        )
    assert outcome.ok and len(outcome.data["backup_ids"]) == 3
    files = snapshot_files(tmp_path)
    assert all(f"{backup_id}.json" in files for backup_id in outcome.data["backup_ids"])


@pytest.mark.anyio
async def test_playlist_member_turned_into_a_playlist_before_its_write_is_a_conflict(tmp_path):
    bundle = bundle_with(item(1, state_preset("A")), item(2, stored_playlist([1, 7], name="L")))
    desk = BundleDevice({"20": state_preset("Seven")})

    def change(_body: dict[str, Any]) -> None:
        if len(desk.posts) == 1:
            desk.store["20"] = stored_playlist([1])

    desk.on_post = change
    outcome, fleet = await import_(tmp_path, desk, bundle, id_map={"7": 20})
    assert fleet.post_count() == 1 and outcome.error.code == "PRESET_CONFLICT"
    assert [e["status"] for e in outcome.data["entries"]] == ["verified", "not_attempted"]


@pytest.mark.anyio
async def test_playlist_started_before_the_playlist_write_is_a_conflict(tmp_path):
    bundle = bundle_with(item(1, state_preset("A")), item(2, stored_playlist([1], name="L")))
    desk = BundleDevice({"9": state_preset("M"), "8": stored_playlist([9])})

    def start(_body: dict[str, Any]) -> None:
        if len(desk.posts) == 1:
            desk.state.update(pl=8)

    desk.on_post = start
    outcome, fleet = await import_(tmp_path, desk, bundle)
    assert fleet.post_count() == 1 and outcome.error.code == "PRESET_CONFLICT"
    assert "Playlist 8 is running" in outcome.data["entries"][1]["reason"]


@pytest.mark.anyio
async def test_lowest_free_allocation_skips_id_map_destinations(tmp_path):
    bundle = bundle_with(item(5, state_preset("Unmapped")), item(6, state_preset("Mapped")))
    outcome, fleet = await import_(tmp_path, BundleDevice(), bundle, id_map={"6": 1}, dry_run=True)
    assert outcome.ok and fleet.post_count() == 0
    rows = [
        (e["source_id"], e["destination_id"], e["allocated"])
        for e in outcome.data["plan"]["entries"]
    ]
    assert rows == [(5, 2, True), (6, 1, False)]


@pytest.mark.anyio
async def test_playlist_rewritten_onto_its_own_destination_is_blocked(tmp_path):
    bundle = bundle_with(item(5, stored_playlist([7], name="Self")))
    desk = BundleDevice({"20": state_preset("Target")})
    outcome, fleet = await import_(
        tmp_path, desk, bundle, id_map={"5": 20, "7": 20}, overwrite_ids=[20]
    )
    assert outcome.error.code == "UNSUPPORTED_CAPABILITY" and fleet.post_count() == 0
    assert "its own destination" in json.dumps(outcome.data["plan"]["entries"][0]["blocking"])


@pytest.mark.anyio
async def test_malformed_target_store_blocks_the_import(tmp_path):
    desk = BundleDevice({"abc": state_preset("Odd")})
    outcome, fleet = await import_(tmp_path, desk, bundle_with(item(1, state_preset("A"))))
    assert outcome.error.code == "INVALID_RESPONSE" and fleet.post_count() == 0


@pytest.mark.anyio
async def test_explicit_catalog_map_outside_the_target_catalog_is_blocked(tmp_path):
    bundle = bundle_with(item(1, state_preset("Fiery", fx=4, pal=3)))
    for arguments, fragment in (
        ({"effect_map": {"4": 99}}, "maps effect 4 to 99, outside the target catalog (0-4)"),
        ({"palette_map": {"3": 4}}, "maps palette 3 to 4, outside the target catalog (0-3)"),
    ):
        outcome, fleet = await import_(tmp_path, BundleDevice(), bundle, **arguments)
        assert outcome.error.code == "VALIDATION_ERROR" and fleet.post_count() == 0
        assert fragment in json.dumps(outcome.data["plan"]["entries"][0]["blocking"])


@pytest.mark.parametrize(("stop", "blocked"), [(30, False), (31, True)])
@pytest.mark.anyio
async def test_segment_stop_boundary_at_the_target_led_count(tmp_path, stop, blocked):
    bundle = bundle_with(item(1, state_preset("Edge", stop=stop)))
    outcome, fleet = await import_(tmp_path, BundleDevice(led_count=30), bundle, dry_run=True)
    assert fleet.post_count() == 0
    assert outcome.ok is not blocked
    if blocked:
        assert "stop 31 exceeds the target LED count 30" in json.dumps(outcome.data["plan"])
