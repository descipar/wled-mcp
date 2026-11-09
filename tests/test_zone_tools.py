"""Zone tools of issue #27: list, plan and apply (S3-ZONE-01, S3-ZONE-02).

Mock fleet and ``tmp_path`` only (``tests/scene_support.py``); no LAN device, no hardware.
Every preview asserts that no POST was sent. Layouts are synthetic: strip ``a`` has four
quarter segments of a 100-LED strip, strip ``b`` two halves of 60 LEDs.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from mcp.client import Client
from pydantic import ValidationError

from tests.layout_support import inactive_slot
from tests.scene_support import (
    SceneDevice,
    SceneFleet,
    call,
    group_arguments,
    open_fleet,
    segments_of,
    strip,
    write_raw,
)
from tests.state_catalog_support import make_segment
from tests.tool_contract import CONTROL, READ, expected_tool
from wled_mcp import zone_tools
from wled_mcp.access import AccessPolicy, ToolClass
from wled_mcp.operations import build_operations
from wled_mcp.server import create_server

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def quarters() -> SceneDevice:
    return strip(
        led_count=100,
        segments=[
            make_segment(0, 0, 25),
            make_segment(1, 25, 50),
            make_segment(2, 50, 75),
            make_segment(3, 75, 100),
        ],
    )


def halves() -> SceneDevice:
    return strip(led_count=60, segments=[make_segment(0, 0, 30), make_segment(1, 30, 60)])


def fleet_ab() -> SceneFleet:
    return SceneFleet(a=quarters(), b=halves())


def fake_of(fleet: SceneFleet, device_id: str) -> Any:
    return fleet.devices[f"{device_id}.invalid"]


def zone_doc(zone_id: str, parts: list[dict[str, Any]], name: str | None = None) -> dict[str, Any]:
    return {
        "format": "wled-mcp.zone",
        "format_version": 1,
        "id": zone_id,
        "name": name or f"Zone {zone_id}",
        "parts": parts,
    }


def part(device: str, led_count: int, *spans: dict[str, Any]) -> dict[str, Any]:
    return {"device": device, "led_count": led_count, "spans": list(spans)}


def span(start: int, stop: int, **extra: Any) -> dict[str, Any]:
    return {"start": start, "stop": stop, **extra}


def put_zone(tmp_path: Path, document: dict[str, Any]) -> None:
    write_raw(tmp_path / "zones" / f"{document['id']}.json", json.dumps(document, indent=2) + "\n")


def shelf_left(tmp_path: Path) -> None:
    """Strip a: the high half runs reversed, plus the first two quarters; strip b: first half."""
    put_zone(
        tmp_path,
        zone_doc(
            "shelf-left",
            [
                part("a", 100, span(50, 100, reversed=True), span(0, 50)),
                part("b", 60, span(0, 30)),
            ],
            name="Shelf, left side",
        ),
    )


def error_of(outcome: Any) -> dict[str, Any]:
    assert outcome.ok is False and outcome.error is not None
    return outcome.error.model_dump()


def target_of(outcome: Any, device_id: str) -> dict[str, Any]:
    (found,) = [t for t in outcome.data["targets"] if t["device_id"] == device_id]
    return found


def device_entry(outcome: Any, device_id: str) -> dict[str, Any]:
    (found,) = [d for d in outcome.data["devices"] if d["device_id"] == device_id]
    return found


def bodies(fleet: SceneFleet, device_id: str) -> list[Any]:
    return fake_of(fleet, device_id).posts


def lit(fake: Any) -> dict[int, int]:
    """Segment ID -> brightness, to see which segments a write touched."""
    return {seg_id: seg["bri"] for seg_id, seg in segments_of(fake).items()}


# ================================================================ classification


def test_the_zone_tools_are_classified_in_the_expected_contract():
    assert expected_tool("wled_list_zones").tool_class is READ
    assert expected_tool("wled_plan_zone").tool_class is READ
    assert expected_tool("wled_apply_zone").tool_class is CONTROL
    assert expected_tool("wled_apply_zone").destructive is False


# ======================================================================= listing


async def test_list_reads_local_files_only_and_summarizes_each_zone(tmp_path):
    fleet = fleet_ab()
    shelf_left(tmp_path)
    put_zone(tmp_path, zone_doc("gone", [part("missing", 10, span(0, 5))]))
    write_raw(tmp_path / "zones" / "broken.json", "{not json")
    async with open_fleet(tmp_path, fleet) as resources:
        outcome = await call(resources, "wled_list_zones")
    assert outcome.ok and fleet.calls == []
    assert outcome.data["count"] == 2 and outcome.data["invalid_count"] == 1
    by_id = {z["id"]: z for z in outcome.data["zones"]}
    assert by_id["shelf-left"]["span_count"] == 3 and by_id["shelf-left"]["part_count"] == 2
    assert by_id["gone"]["devices"] == [{"device_id": "missing", "in_inventory": False}]
    assert any("not in the inventory" in w for w in outcome.warnings)
    assert any("cannot be used" in w for w in outcome.warnings)


async def test_list_reports_ambiguous_names_and_duplicate_mappings(tmp_path):
    put_zone(tmp_path, zone_doc("one", [part("a", 100, span(0, 25))], name="Same"))
    put_zone(tmp_path, zone_doc("two", [part("a", 100, span(0, 25))], name="same"))
    async with open_fleet(tmp_path, fleet_ab()) as resources:
        outcome = await call(resources, "wled_list_zones")
    assert any("share one name" in w for w in outcome.warnings)
    assert any("duplicate_mapping" in w for w in outcome.warnings)


async def test_a_zone_is_returned_by_id_or_name_with_its_document(tmp_path):
    shelf_left(tmp_path)
    async with open_fleet(tmp_path, fleet_ab()) as resources:
        by_id = await call(resources, "wled_list_zones", zone="shelf-left")
        by_name = await call(resources, "wled_list_zones", zone="SHELF, LEFT SIDE")
        missing = await call(resources, "wled_list_zones", zone="nope")
    assert by_id.ok and by_id.data["document"]["parts"][0]["spans"][0]["reversed"] is True
    assert by_name.data["zone"]["id"] == "shelf-left"
    assert error_of(missing)["code"] == "VALIDATION_ERROR"


async def test_an_ambiguous_name_is_refused_with_candidates_and_the_id_still_works(tmp_path):
    fleet = fleet_ab()
    put_zone(tmp_path, zone_doc("one", [part("a", 100, span(0, 25))], name="Same"))
    put_zone(tmp_path, zone_doc("two", [part("a", 100, span(25, 50))], name="same"))
    async with open_fleet(tmp_path, fleet) as resources:
        ambiguous = await call(resources, "wled_plan_zone", zone="SAME")
        by_id = await call(resources, "wled_plan_zone", zone="two")
    assert error_of(ambiguous)["code"] == "AMBIGUOUS_NAME"
    assert [c["id"] for c in ambiguous.data["candidates"]] == ["one", "two"]
    assert by_id.ok and by_id.data["zone"]["id"] == "two"
    assert fleet.post_count() == 0


# ========================================================================= plan


async def test_the_plan_of_a_span_equal_to_a_segment_sends_no_write(tmp_path):
    fleet = fleet_ab()
    put_zone(tmp_path, zone_doc("one", [part("a", 100, span(25, 50))]))
    async with open_fleet(tmp_path, fleet) as resources:
        outcome = await call(resources, "wled_plan_zone", zone="one")
    assert outcome.ok and outcome.dry_run is True
    entry = target_of(outcome, "a")
    resolved = entry["zone_target"]
    assert resolved["segment_ids"] == [1] and resolved["layout_changes"] is False
    assert resolved["spans"][0]["segments"] == [{"id": 1, "start": 25, "stop": 50}]
    assert entry["segments"] is None  # no fields requested: resolution only
    assert fleet.post_count() == 0


async def test_several_spans_and_devices_give_one_target_per_device_in_logical_order(tmp_path):
    fleet = fleet_ab()
    shelf_left(tmp_path)
    async with open_fleet(tmp_path, fleet) as resources:
        outcome = await call(
            resources, "wled_plan_zone", zone="shelf-left", segments=[{"brightness": 40}]
        )
    assert outcome.ok, outcome.error
    assert [t["device_id"] for t in outcome.data["targets"]] == ["a", "b"]
    on_a = target_of(outcome, "a")["zone_target"]
    assert [s["span"] for s in on_a["spans"]] == [1, 2]
    # The reversed high span lists its segments from the high LED end first.
    assert [seg["id"] for seg in on_a["spans"][0]["segments"]] == [3, 2]
    assert on_a["spans"][0]["flow_reversed"] is True and on_a["spans"][1]["flow_reversed"] is False
    assert on_a["segment_ids"] == [0, 1, 2, 3]
    # The real segment planner ran for each device; nothing was sent.
    planned = target_of(outcome, "a")["segments"]["payload"]["seg"]
    assert sorted(item["id"] for item in planned) == [0, 1, 2, 3]
    assert target_of(outcome, "b")["zone_target"]["segment_ids"] == [0]
    assert outcome.data["layout_changes"] is False and fleet.post_count() == 0


async def test_the_plan_reports_overlapping_zones_and_groups_as_information(tmp_path):
    fleet = fleet_ab()
    put_zone(tmp_path, zone_doc("wide", [part("a", 100, span(0, 50))]))
    put_zone(tmp_path, zone_doc("inner", [part("a", 100, span(25, 50))]))
    async with open_fleet(tmp_path, fleet) as resources:
        saved = await call(resources, "wled_save_group", **group_arguments("g", ("a", [1, 3])))
        assert saved.ok
        outcome = await call(resources, "wled_plan_zone", zone="inner")
    assert outcome.ok
    assert outcome.data["overlaps_zones"] == [{"zone_id": "wide", "device_id": "a"}]
    assert outcome.data["overlaps_groups"] == [
        {"group_id": "g", "device_id": "a", "segments": [1, 3]}
    ]
    assert fleet.post_count() == 0


# ================================================ refusals before any write (AC-27-08/09)


async def test_a_stale_led_count_is_refused_per_device_with_nothing_sent(tmp_path):
    fleet = SceneFleet(a=strip(led_count=120, segments=[make_segment(0, 0, 120)]))
    put_zone(tmp_path, zone_doc("one", [part("a", 100, span(0, 50))]))
    async with open_fleet(tmp_path, fleet) as resources:
        plan = await call(resources, "wled_plan_zone", zone="one")
        apply = await call(resources, "wled_apply_zone", zone="one", segments=[{"brightness": 10}])
    for outcome in (plan, apply):
        assert error_of(outcome)["code"] == "VALIDATION_ERROR"
        assert "120" in outcome.error.message and "100" in outcome.error.message
    problem = target_of(plan, "a")["problem"]
    assert problem["reason"] == "topology_stale" and problem["layout_change_required"] is False
    assert fleet.post_count() == 0


@pytest.mark.parametrize(
    ("span_args", "reason"),
    [
        (span(0, 40), "boundary_crossing"),  # quarter 1 straddles the edge
        (span(10, 20), "boundary_crossing"),  # the zone is smaller than a segment
        (span(25, 50, segment=2), "segment_mismatch"),  # the hint names another segment
    ],
)
async def test_a_zone_that_does_not_fit_the_live_segments_changes_no_led(
    tmp_path, span_args, reason
):
    fleet = fleet_ab()
    put_zone(tmp_path, zone_doc("one", [part("a", 100, span_args)]))
    async with open_fleet(tmp_path, fleet) as resources:
        before = copy.deepcopy(fake_of(fleet, "a").state())
        outcome = await call(
            resources, "wled_apply_zone", zone="one", segments=[{"brightness": 10}]
        )
        dry = await call(
            resources, "wled_apply_zone", zone="one", segments=[{"brightness": 10}], dry_run=True
        )
    assert error_of(outcome)["code"] == "VALIDATION_ERROR"
    assert outcome.application == "not_attempted"
    problem = target_of(dry, "a")["problem"]
    assert problem["reason"] == reason
    assert problem["layout_change_required"] is (reason != "segment_mismatch")
    assert fleet.post_count() == 0 and fake_of(fleet, "a").state() == before


@pytest.mark.parametrize(
    ("layout", "span_args", "reason"),
    [
        ([make_segment(0, 0, 20), make_segment(1, 30, 50)], span(0, 50), "span_gap"),
        ([make_segment(0, 0, 25)], span(60, 70), "span_unsegmented"),
    ],
)
async def test_uncovered_leds_are_refused_not_lit(tmp_path, layout, span_args, reason):
    fleet = SceneFleet(a=strip(led_count=100, segments=layout))
    put_zone(tmp_path, zone_doc("one", [part("a", 100, span_args)]))
    async with open_fleet(tmp_path, fleet) as resources:
        outcome = await call(
            resources, "wled_apply_zone", zone="one", segments=[{"brightness": 10}]
        )
    assert not outcome.ok and fleet.post_count() == 0
    assert target_problem(outcome)["reason"] == reason


def target_problem(outcome: Any) -> dict[str, Any]:
    (entry,) = [d for d in outcome.data["devices"] if d.get("error")]
    return entry["steps"][0]["problem"] if entry["steps"] else entry["problem"]


async def test_a_matrix_device_is_an_unsupported_capability(tmp_path):
    fleet = SceneFleet(a=strip(led_count=100, matrix=(10, 10)))
    put_zone(tmp_path, zone_doc("one", [part("a", 100, span(0, 10))]))
    async with open_fleet(tmp_path, fleet) as resources:
        outcome = await call(resources, "wled_plan_zone", zone="one")
    assert error_of(outcome)["code"] == "UNSUPPORTED_CAPABILITY" and fleet.post_count() == 0


# =================================================================== missing device


async def test_a_missing_device_blocks_strict_and_is_skipped_in_best_effort(tmp_path):
    fleet = fleet_ab()
    put_zone(
        tmp_path,
        zone_doc("mixed", [part("a", 100, span(0, 25)), part("missing", 10, span(0, 5))]),
    )
    fields = [{"brightness": 10}]
    async with open_fleet(tmp_path, fleet) as resources:
        strict = await call(resources, "wled_apply_zone", zone="mixed", segments=fields)
        assert fleet.post_count() == 0 and fleet.hosts_called() == {"a.invalid"}  # read only
        best = await call(
            resources, "wled_apply_zone", zone="mixed", segments=fields, mode="best_effort"
        )
    assert error_of(strict)["code"] == "UNKNOWN_DEVICE" and "'missing'" in strict.error.message
    assert device_entry(strict, "a")["application"] == "not_attempted"
    assert fleet.post_hosts() == ["a.invalid"]
    assert device_entry(best, "a")["ok"] is True
    assert device_entry(best, "missing")["error"]["code"] == "UNKNOWN_DEVICE"
    assert "missing.invalid" not in fleet.hosts_called()  # no I/O for the unknown device
    assert best.error.code == "VERIFICATION_MISMATCH"  # partial: one device not written


# ========================================================================== apply


async def test_apply_changes_only_the_segments_inside_the_zone(tmp_path):
    fleet = fleet_ab()
    # "left" is the high half of strip a, physically reversed relative to the zone's flow.
    put_zone(tmp_path, zone_doc("left", [part("a", 100, span(50, 100, reversed=True))]))
    async with open_fleet(tmp_path, fleet) as resources:
        before = lit(fake_of(fleet, "a"))
        outcome = await call(
            resources, "wled_apply_zone", zone="left", segments=[{"brightness": 33}]
        )
    assert outcome.ok, outcome.error
    assert (outcome.application, outcome.verification) == ("applied", "verified")
    after = lit(fake_of(fleet, "a"))
    assert after[2] == after[3] == 33 and after[0] == before[0] and after[1] == before[1]
    (body,) = bodies(fleet, "a")
    assert sorted(seg["id"] for seg in body["seg"]) == [2, 3]
    # A zone apply never writes geometry or master state.
    assert all(not {"start", "stop", "len", "grp", "spc", "of"} & seg.keys() for seg in body["seg"])
    assert not {"on", "bri", "transition"} & body.keys()
    assert fleet.post_hosts() == ["a.invalid"]  # strip b is not part of the zone
    assert any("not atomic" in w and "zone" in w for w in outcome.warnings)


async def test_a_zone_over_two_devices_writes_each_device_once_and_verifies(tmp_path):
    fleet = fleet_ab()
    shelf_left(tmp_path)
    async with open_fleet(tmp_path, fleet) as resources:
        outcome = await call(
            resources,
            "wled_apply_zone",
            zone="Shelf, Left Side",
            segments=[{"on": True, "colors": [[255, 120, 20]], "effect_name": "Wipe"}],
        )
    assert outcome.ok, outcome.error
    assert sorted(fleet.post_hosts()) == ["a.invalid", "b.invalid"]
    assert sorted(seg["id"] for seg in bodies(fleet, "a")[0]["seg"]) == [0, 1, 2, 3]
    assert [seg["id"] for seg in bodies(fleet, "b")[0]["seg"]] == [0]
    # b's second half is untouched while its first half changed
    assert segments_of(fake_of(fleet, "b"))[1]["fx"] != segments_of(fake_of(fleet, "b"))[0]["fx"]
    assert [segments_of(fake_of(fleet, "b"))[i]["col"][0] for i in (0, 1)][1] != [255, 120, 20, 0]
    assert outcome.data["zone"] == {"id": "shelf-left", "name": "Shelf, left side"}


async def test_dry_run_returns_exactly_the_plan_and_sends_no_write(tmp_path):
    fleet = fleet_ab()
    shelf_left(tmp_path)
    fields = [{"brightness": 40}]
    async with open_fleet(tmp_path, fleet) as resources:
        plan = await call(resources, "wled_plan_zone", zone="shelf-left", segments=fields)
        dry = await call(
            resources, "wled_apply_zone", zone="shelf-left", segments=fields, dry_run=True
        )
    assert dry.ok and dry.dry_run is True and dry.application == "not_attempted"
    assert dry.data == plan.data and fleet.post_count() == 0


@pytest.mark.parametrize(
    "arguments",
    [
        {"segments": [{"start": 0, "stop": 10}]},  # geometry
        {"segments": [{"reverse": True}]},
        {"segments": [{"grouping": 2}]},
        {"segments": [{"ids": [0], "brightness": 10}]},  # the zone decides the segments
        {"segments": [{"unknown_field": 1}]},
        {"segments": [{}]},
    ],
)
async def test_geometry_and_unknown_fields_are_refused_before_any_io(tmp_path, arguments):
    fleet = fleet_ab()
    shelf_left(tmp_path)
    async with open_fleet(tmp_path, fleet) as resources:
        outcome = await call(resources, "wled_apply_zone", zone="shelf-left", **arguments)
    assert error_of(outcome)["code"] == "VALIDATION_ERROR" and fleet.calls == []


@pytest.mark.parametrize(
    "arguments",
    [
        {"segments": [{"brightness": 10}], "brightness": 10},  # master state
        {"segments": [{"brightness": 10}], "on": True},
        {"segments": [{"brightness": 10}], "transition_ms": 100},
        {"segments": [{"brightness": 10}, {"speed": 1}]},  # one field object only
        {"segments": []},
        {},
    ],
)
async def test_the_request_schema_has_no_master_state_and_needs_one_field_object(
    tmp_path, arguments
):
    shelf_left(tmp_path)
    async with open_fleet(tmp_path, fleet_ab()) as resources:
        with pytest.raises(ValidationError):
            await call(resources, "wled_apply_zone", zone="shelf-left", **arguments)


# ========================================================= layout changes (AC-27-10/11)


async def test_an_explicit_layout_change_makes_the_zone_resolve_and_the_zone_never_writes_it(
    tmp_path,
):
    fleet = SceneFleet(a=strip(led_count=100, segments=[make_segment(0, 0, 100)]))
    put_zone(tmp_path, zone_doc("high", [part("a", 100, span(50, 100))]))
    fields = [{"brightness": 20}]
    async with open_fleet(tmp_path, fleet) as resources:
        blocked = await call(resources, "wled_apply_zone", zone="high", segments=fields)
        assert not blocked.ok and fleet.post_count() == 0
        layout = await call(
            resources,
            "wled_replace_layout",
            device_id="a",
            segments=[
                {"id": 0, "start": 0, "stop": 50},
                {"id": 1, "start": 50, "stop": 100, "colors": [[0, 0, 255]]},
            ],
        )
        assert layout.ok, layout.error
        layout_posts = len(bodies(fleet, "a"))
        applied = await call(resources, "wled_apply_zone", zone="high", segments=fields)
    assert applied.ok, applied.error
    zone_bodies = bodies(fleet, "a")[layout_posts:]
    assert len(zone_bodies) == 1
    assert [seg["id"] for seg in zone_bodies[0]["seg"]] == [1]
    assert all("start" not in seg and "stop" not in seg for seg in zone_bodies[0]["seg"])
    assert lit(fake_of(fleet, "a"))[0] != 20


async def test_a_layout_change_between_preview_and_write_sends_nothing(tmp_path, monkeypatch):
    fleet = fleet_ab()
    put_zone(
        tmp_path, zone_doc("mixed", [part("a", 100, span(50, 100)), part("b", 60, span(0, 30))])
    )
    real = zone_tools.apply_device

    async def changed_then_write(resources, plan, name):
        if plan.target.device_id == "a":
            # Another actor repartitions strip a after the preflight passed.
            fake_of(fleet, "a").slots[2]["stop"] = 60
            fake_of(fleet, "a").slots[3]["start"] = 60
        return await real(resources, plan, name)

    monkeypatch.setattr(zone_tools, "apply_device", changed_then_write)
    async with open_fleet(tmp_path, fleet) as resources:
        outcome = await call(
            resources,
            "wled_apply_zone",
            zone="mixed",
            segments=[{"brightness": 20}],
            mode="best_effort",
        )
    stale = device_entry(outcome, "a")
    assert (stale["application"], stale["verification"]) == ("not_attempted", "not_requested")
    assert stale["error"]["code"] == "VALIDATION_ERROR"
    assert stale["steps"][0]["problem"]["reason"] == "topology_changed"
    assert bodies(fleet, "a") == []  # nothing was sent, nothing retried
    # The other device is unaffected under best_effort.
    assert device_entry(outcome, "b")["ok"] is True and len(bodies(fleet, "b")) == 1
    assert outcome.error.code == "VERIFICATION_MISMATCH"


async def test_a_resolution_that_still_works_but_differs_also_fails_the_write(
    tmp_path, monkeypatch
):
    fleet = SceneFleet(a=quarters())
    put_zone(tmp_path, zone_doc("one", [part("a", 100, span(50, 100))]))
    real = zone_tools.apply_device
    fake_of(fleet, "a").slots.extend([inactive_slot(4), inactive_slot(5)])

    async def renumber(resources, plan, name):
        # The same range, now under another segment ID: IDs are not stable, so it is refused.
        fake = fake_of(fleet, "a")
        fake.slots[4] = {**fake.slots[2], "id": 4}
        fake.slots[2] = inactive_slot(2)
        return await real(resources, plan, name)

    monkeypatch.setattr(zone_tools, "apply_device", renumber)
    async with open_fleet(tmp_path, fleet) as resources:
        outcome = await call(resources, "wled_apply_zone", zone="one", segments=[{"speed": 9}])
    assert not outcome.ok and fleet.post_count() == 0
    assert target_problem(outcome)["reason"] == "topology_changed"


# =============================================================== access (AC-27-12)


def policy(profile: str = "control", **caps: str) -> AccessPolicy:
    return AccessPolicy(profile, {d: ToolClass(v) for d, v in caps.items()})  # type: ignore[arg-type]


async def test_a_read_capped_device_of_a_zone_is_refused_before_any_read_but_still_previews(
    tmp_path,
):
    fleet = fleet_ab()
    shelf_left(tmp_path)
    fields = [{"brightness": 40}]
    async with open_fleet(tmp_path, fleet, access=policy(b="read")) as resources:
        strict = await call(resources, "wled_apply_zone", zone="shelf-left", segments=fields)
        dry = await call(
            resources, "wled_apply_zone", zone="shelf-left", segments=fields, dry_run=True
        )
        assert fleet.post_count() == 0 and "b.invalid" not in fleet.hosts_called()
        preview = await call(resources, "wled_plan_zone", zone="shelf-left", segments=fields)
        best = await call(
            resources, "wled_apply_zone", zone="shelf-left", segments=fields, mode="best_effort"
        )
    assert error_of(strict)["code"] == "ACCESS_DENIED" and "'b'" in strict.error.message
    assert error_of(dry)["code"] == "ACCESS_DENIED"  # dry_run does not lower the class
    assert preview.ok and "b.invalid" in fleet.hosts_called()  # the read tool may read it
    assert target_of(best, "b")["preflight"] == "ok" if "targets" in best.data else True
    assert device_entry(best, "b")["error"]["code"] == "ACCESS_DENIED"
    assert fleet.post_hosts() == ["a.invalid"]  # best_effort wrote only the permitted device


async def test_a_read_only_profile_serves_the_plan_but_not_the_apply(tmp_path):
    shelf_left(tmp_path)
    fleet = fleet_ab()
    async with open_fleet(tmp_path, fleet, access=policy("read-only")) as resources:
        server = create_server(build_operations(resources), resources.config.access)
        async with Client(server) as client:
            names = [tool.name for tool in (await client.list_tools()).tools]
            result = await client.call_tool("wled_plan_zone", {"zone": "shelf-left"})
    assert "wled_plan_zone" in names and "wled_list_zones" in names
    assert "wled_apply_zone" not in names
    assert result.structured_content is not None and result.structured_content["ok"] is True


# ============================================================ aggregate outcomes


async def test_an_unverified_write_is_unknown_and_never_retried(tmp_path):
    fleet = fleet_ab()
    shelf_left(tmp_path)
    fake_of(fleet, "b").fail_reads_from_post = 1  # the readback is lost: outcome unknown
    async with open_fleet(tmp_path, fleet) as resources:
        outcome = await call(
            resources, "wled_apply_zone", zone="shelf-left", segments=[{"brightness": 40}]
        )
    assert not outcome.ok
    assert (outcome.application, outcome.verification) == ("unknown", "unknown")
    assert outcome.error.code == "WRITE_OUTCOME_UNKNOWN"
    assert len(bodies(fleet, "b")) == 1  # exactly one POST: no replay
    assert device_entry(outcome, "a")["ok"] is True  # the other device is not undone
