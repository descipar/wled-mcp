"""Issue #29 (S3-T03): ``wled_preview_layout`` over mocks, observed and proposed.

The mock router answers GET only and fails any other method, so every test here also proves
that no write was sent. Devices and zones are synthetic (``desk.invalid``, ``tmp_path``);
nothing contacts a network. The pure renderer has its own tests in ``test_layout_preview.py``.
"""

from __future__ import annotations

import inspect
import json
import xml.etree.ElementTree as ET
from typing import Any

import httpx2 as httpx
import pytest
from mcp.client import Client
from pydantic import ValidationError

from tests.scene_support import write_raw
from tests.state_catalog_support import make_info, make_segment, make_state
from tests.test_state_catalogs import DESK, assert_read_envelope, call, fleet, open_resources
from tests.tool_contract import READ, expected_tool
from wled_mcp import preview_tools
from wled_mcp.access import AccessPolicy, ToolClass
from wled_mcp.layout_preview import MAX_SVG_BYTES, NAMESPACE
from wled_mcp.operations import build_operations
from wled_mcp.preview_tools import PreviewLayoutRequest
from wled_mcp.server import create_server

NAME = "wled_preview_layout"
STATE_INFO = [(DESK, "/json/state"), (DESK, "/json/info")]


@pytest.fixture
def anyio_backend():
    return "asyncio"


def three_segments(**kwargs: Any):
    return fleet(
        state=make_state(
            [
                make_segment(0, 0, 30, col=[[255, 0, 0, 0]] * 3),
                make_segment(2, 30, 60),
                make_segment(5, 60, 90),
            ]
        ),
        **kwargs,
    )


def text_lines(data: dict[str, Any]) -> list[str]:
    root = ET.fromstring(data["svg"])
    return [e.text or "" for e in root.iter() if e.tag.endswith("}text")]


def zone_file(tmp_path, zone_id: str, led_count: int = 90, name: str | None = None, **span):
    document = {
        "format": "wled-mcp.zone",
        "format_version": 1,
        "id": zone_id,
        "name": name or f"Zone {zone_id}",
        "parts": [
            {
                "device": "desk",
                "led_count": led_count,
                "spans": [{"start": 0, "stop": 45, **span}, {"start": 45, "stop": 90}],
            }
        ],
    }
    write_raw(tmp_path / "zones" / f"{zone_id}.json", json.dumps(document))


def failure_code(outcome) -> str:
    assert outcome.ok is False and outcome.error is not None
    assert "svg" not in outcome.data
    return outcome.error.code


# ============================================================================ classification


def test_the_tool_is_a_read_class_tool_in_the_expected_contract():
    assert expected_tool(NAME).tool_class is READ and expected_tool(NAME).destructive is False


def test_the_adapter_holds_no_write_path():
    source = inspect.getsource(preview_tools)
    for forbidden in ("write_verified", "write_sequence_verified", "require_write", "post("):
        assert forbidden not in source
    schema = PreviewLayoutRequest.model_json_schema()
    assert schema["additionalProperties"] is False and "dry_run" not in schema["properties"]
    with pytest.raises(ValidationError):
        PreviewLayoutRequest.model_validate({"device_id": "desk", "dry_run": True})


# ================================================================================== observed


@pytest.mark.anyio
async def test_the_observed_preview_reads_state_and_info_only_and_has_the_documented_shape(
    tmp_path,
):
    router = three_segments()
    async with open_resources(tmp_path, router) as resources:
        outcome = await call(resources, NAME)
    assert_read_envelope(outcome, NAME)
    assert outcome.device_id == "desk" and outcome.error is None
    assert router.calls == STATE_INFO  # in order, no live read, GET only (the router asserts)
    data = outcome.data
    assert data["source"] == "observed" and data["media_type"] == "image/svg+xml"
    assert data["svg"].startswith(f'<svg xmlns="{NAMESPACE}"')
    ET.fromstring(data["svg"])
    assert data["range_semantics"] == "[start,stop) exclusive stop"
    assert data["led_count"] == 90 and data["led_count_source"] == "info"
    assert [s["id"] for s in data["segments"]] == [0, 2, 5]
    assert [(s["start"], s["stop"]) for s in data["segments"]] == [(0, 30), (30, 60), (60, 90)]
    assert data["gaps"] == [] and data["overlaps"] == [] and data["omitted_segments"] == 0
    assert data["colour_basis"] == "state_slot_0" and data["captured_at"].endswith("+00:00")
    assert "zone" not in data and "live" not in data and "removed_segment_ids" not in data
    assert any("not simulated" in item for item in data["limits"])
    assert "Fresh non-atomic reads" in data["observation"]


@pytest.mark.anyio
async def test_sparse_ids_gaps_and_overlaps_of_the_observed_layout_are_reported(tmp_path):
    router = fleet(
        state=make_state([make_segment(0, 5, 20), make_segment(3, 15, 30), make_segment(7, 40, 50)])
    )
    async with open_resources(tmp_path, router) as resources:
        data = (await call(resources, NAME)).data
    assert [s["id"] for s in data["segments"]] == [0, 3, 7]
    assert data["gaps"] == [
        {"start": 0, "stop": 5},
        {"start": 30, "stop": 40},
        {"start": 50, "stop": 90},
    ]
    assert data["overlaps"] == [{"start": 15, "stop": 20}]


# ====================================================================== matrix, unknown count


@pytest.mark.anyio
@pytest.mark.parametrize(
    "info,segments",
    [
        (
            make_info(
                leds={"count": 64, "maxseg": 32, "lc": 1, "seglc": [1], "matrix": {"w": 8, "h": 8}}
            ),
            [make_segment(0, 0, 8, startY=0, stopY=8)],
        ),
        (make_info(), [make_segment(0, 0, 8, startY=2, stopY=4)]),
    ],
)
async def test_a_matrix_device_is_refused_and_nothing_is_drawn(tmp_path, info, segments):
    router = fleet(info=info, state=make_state(segments))
    async with open_resources(tmp_path, router) as resources:
        observed = await call(resources, NAME)
        proposed = await call(
            resources, NAME, segments=[{"id": 0, "start": 0, "stop": 8, "colors": [[1, 2, 3]]}]
        )
    for outcome in (observed, proposed):
        assert failure_code(outcome) == "UNSUPPORTED_CAPABILITY"
        assert "2D/matrix" in outcome.error.message
        assert outcome.application == "not_attempted"


@pytest.mark.anyio
async def test_an_unknown_led_count_is_drawn_with_a_label_and_a_limit(tmp_path):
    router = fleet(
        info=make_info(leds={"maxseg": 32, "lc": 1, "seglc": [1, 1, 1]}),
        state=make_state([make_segment(0, 0, 20), make_segment(1, 30, 45)]),
    )
    async with open_resources(tmp_path, router) as resources:
        outcome = await call(resources, NAME)
    data = outcome.data
    assert outcome.ok and data["led_count"] is None and data["led_count_source"] == "unknown"
    assert any("LED count unknown" in line for line in text_lines(data))
    assert any("LED count unknown" in item for item in data["limits"])
    assert data["gaps"] == [{"start": 20, "stop": 30}]


# ===================================================================================== proposed


@pytest.mark.anyio
async def test_a_valid_proposal_is_validated_by_the_planner_and_never_written(tmp_path):
    router = three_segments()
    layout = [
        {"id": 0, "start": 0, "stop": 45},
        {"id": 2, "start": 45, "stop": 90},
        {"id": 6, "start": 0, "stop": 10, "colors": [[1, 2, 3]], "name": "New"},
    ]
    async with open_resources(tmp_path, router) as resources:
        refused = await call(resources, NAME, segments=layout)
        allowed = await call(resources, NAME, segments=layout, allow_overlap=True)
    assert failure_code(refused) == "VALIDATION_ERROR" and "overlap" in refused.error.message
    assert allowed.ok and router.calls == STATE_INFO * 2
    data = allowed.data
    assert data["source"] == "proposed" and data["colour_basis"] == "plan"
    assert data["removed_segment_ids"] == [5] and "captured_at" not in data
    assert {s["id"]: s["change"] for s in data["segments"]} == {
        0: "changed",
        2: "changed",
        6: "new",
    }
    assert data["overlaps"] == [{"start": 0, "stop": 10}]
    assert any("proposed layout (not applied)" in line for line in text_lines(data))
    assert any("removed by this layout" in line for line in text_lines(data))
    assert allowed.dry_run is False and allowed.application == "not_attempted"


@pytest.mark.anyio
async def test_an_unchanged_segment_is_marked_unchanged(tmp_path):
    router = three_segments()
    same = [{"id": 0, "start": 0, "stop": 30}, {"id": 2, "start": 30, "stop": 60}]
    async with open_resources(tmp_path, router) as resources:
        outcome = await call(resources, NAME, segments=same)
    assert outcome.ok
    assert {s["id"]: s["change"] for s in outcome.data["segments"]} == {
        0: "unchanged",
        2: "unchanged",
    }
    assert outcome.data["removed_segment_ids"] == [5]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "segments,code",
    [
        ([{"id": 0, "start": 0, "stop": 91}], "VALIDATION_ERROR"),  # stop beyond led_count
        (
            [{"id": 0, "start": 0, "stop": 10}, {"id": 0, "start": 10, "stop": 20}],
            "VALIDATION_ERROR",
        ),
        (
            [{"id": 0, "start": 0, "stop": 20}, {"id": 2, "start": 10, "stop": 30}],
            "VALIDATION_ERROR",
        ),
        ([{"id": 9, "start": 0, "stop": 10}], "VALIDATION_ERROR"),  # new ID without colours
        (
            [{"id": 40, "start": 0, "stop": 10, "colors": [[1, 2, 3]]}],
            "VALIDATION_ERROR",
        ),  # >= maxseg
    ],
)
async def test_an_invalid_proposal_is_the_planner_error_envelope_with_no_svg(
    tmp_path, segments, code
):
    router = three_segments()
    async with open_resources(tmp_path, router) as resources:
        outcome = await call(resources, NAME, segments=segments)
    assert failure_code(outcome) == code
    assert outcome.application == "not_attempted" and outcome.verification == "not_requested"
    assert router.calls == STATE_INFO


@pytest.mark.anyio
async def test_the_planner_limits_unknown_counts_and_maximum_segments(tmp_path):
    unknown = fleet(info=make_info(leds={"maxseg": 32, "lc": 1, "seglc": [1, 1, 1]}))
    few = fleet(info=make_info(leds={"count": 90, "maxseg": 3, "lc": 1, "seglc": [1, 1, 1]}))
    four = [
        {"id": i, "start": i * 10, "stop": i * 10 + 10, "colors": [[1, 2, 3]]} for i in range(4)
    ]
    async with open_resources(tmp_path, unknown) as resources:
        no_count = await call(resources, NAME, segments=[{"id": 0, "start": 0, "stop": 10}])
    async with open_resources(tmp_path, few) as resources:
        too_many = await call(resources, NAME, segments=four)
    assert failure_code(no_count) == "UNSUPPORTED_CAPABILITY"
    assert failure_code(too_many) == "VALIDATION_ERROR" and "maximum" in too_many.error.message


@pytest.mark.anyio
async def test_effect_and_palette_names_are_accepted_but_dropped_with_a_warning(tmp_path):
    router = three_segments()
    layout = [{"id": 0, "start": 0, "stop": 30, "effect_name": "NoSuchEffect", "palette_name": "x"}]
    async with open_resources(tmp_path, router) as resources:
        outcome = await call(resources, NAME, segments=layout)
    assert outcome.ok and router.calls == STATE_INFO  # no catalog read
    assert any("not resolved by the preview" in w for w in outcome.warnings)


@pytest.mark.anyio
async def test_option_combinations_that_do_not_apply_are_rejected_before_any_read(tmp_path):
    router = three_segments()
    layout = [{"id": 0, "start": 0, "stop": 30}]
    async with open_resources(tmp_path, router) as resources:
        live_and_layout = await call(resources, NAME, segments=layout, live_samples=True)
        overlap_only = await call(resources, NAME, allow_overlap=True)
        unknown = await call(resources, NAME, device_id="absent")
    assert failure_code(live_and_layout) == "VALIDATION_ERROR"
    assert failure_code(overlap_only) == "VALIDATION_ERROR"
    assert failure_code(unknown) == "UNKNOWN_DEVICE" and unknown.device_id is None
    assert router.calls == []


# ======================================================================================= zones


@pytest.mark.anyio
async def test_a_zone_is_overlaid_by_id_or_name_with_reversed_as_text_only(tmp_path):
    zone_file(tmp_path, "shelf", name="Shelf side", reversed=True)
    router = three_segments()
    async with open_resources(tmp_path, router) as resources:
        by_id = await call(resources, NAME, zone="shelf")
        by_name = await call(resources, NAME, zone="shelf SIDE")
    assert by_id.ok and by_name.ok and by_id.data["zone"] == by_name.data["zone"]
    zone = by_id.data["zone"]
    assert zone["id"] == "shelf" and zone["status"] == "drawn"
    assert zone["spans"][0] == {"start": 0, "stop": 45, "reversed": True}
    assert any("[0,45) reversed" in line for line in text_lines(by_id.data))
    assert any("alignment not checked" in line for line in text_lines(by_id.data))


@pytest.mark.anyio
async def test_an_ambiguous_zone_name_lists_candidates_and_a_missing_zone_is_refused(tmp_path):
    zone_file(tmp_path, "one", name="Same")
    zone_file(tmp_path, "two", name="same")
    router = three_segments()
    async with open_resources(tmp_path, router) as resources:
        ambiguous = await call(resources, NAME, zone="SAME")
        missing = await call(resources, NAME, zone="nope")
    assert failure_code(ambiguous) == "AMBIGUOUS_NAME"
    assert [c["id"] for c in ambiguous.data["candidates"]] == ["one", "two"]
    assert failure_code(missing) == "VALIDATION_ERROR"
    assert router.calls == []


@pytest.mark.anyio
async def test_a_zone_without_a_part_for_the_device_is_refused_before_any_device_read(tmp_path):
    document = {
        "format": "wled-mcp.zone",
        "format_version": 1,
        "id": "other",
        "name": "Other",
        "parts": [{"device": "elsewhere", "led_count": 90, "spans": [{"start": 0, "stop": 10}]}],
    }
    write_raw(tmp_path / "zones" / "other.json", json.dumps(document))
    router = three_segments()
    async with open_resources(tmp_path, router) as resources:
        outcome = await call(resources, NAME, zone="other")
    assert failure_code(outcome) == "VALIDATION_ERROR" and "no part" in outcome.error.message
    assert router.calls == []


@pytest.mark.anyio
async def test_a_zone_with_a_stale_led_count_is_not_drawn(tmp_path):
    zone_file(tmp_path, "old", led_count=120)
    router = three_segments()
    async with open_resources(tmp_path, router) as resources:
        outcome = await call(resources, NAME, zone="old")
    assert outcome.ok and outcome.data["zone"]["status"] == "topology_stale"
    assert outcome.data["zone"]["spans"] == []
    assert any("topology_stale" in line for line in text_lines(outcome.data))


# ======================================================================================== live


def live_router(live: Any):
    router = three_segments()
    router.set(DESK, "/json/live", live)
    return router


@pytest.mark.anyio
async def test_live_samples_are_read_last_and_colour_the_lanes(tmp_path):
    leds = ["FF0000"] * 45 + ["0000FF"] * 45
    router = live_router({"leds": leds, "n": 1})
    async with open_resources(tmp_path, router) as resources:
        outcome = await call(resources, NAME, live_samples=True)
    assert outcome.ok and router.calls == [*STATE_INFO, (DESK, "/json/live")]
    data = outcome.data
    assert data["colour_basis"] == "live_samples"
    assert data["live"] == {"requested": True, "status": "available", "sampling_step": 1}
    assert {s["id"]: s["colour_mode"] for s in data["segments"]} == {
        0: "live_samples",
        2: "live_samples",
        5: "live_samples",
    }
    assert "live_rgb_brightness_scaled" in data["approximations"]
    assert "unsampled_leds_unknown" not in data["approximations"]


@pytest.mark.anyio
async def test_a_downsampled_live_read_says_that_the_unsampled_leds_are_unknown(tmp_path):
    router = live_router({"leds": ["FF0000"] * 45, "n": 2})
    async with open_resources(tmp_path, router) as resources:
        outcome = await call(resources, NAME, live_samples=True)
    assert "unsampled_leds_unknown" in outcome.data["approximations"]
    assert any("sampled every 2 LEDs" in line for line in text_lines(outcome.data))


@pytest.mark.anyio
@pytest.mark.parametrize("status", [404, 501])
async def test_a_missing_live_endpoint_keeps_the_preview_with_state_colours(tmp_path, status):
    router = live_router(httpx.Response(status))
    async with open_resources(tmp_path, router) as resources:
        outcome = await call(resources, NAME, live_samples=True)
    assert outcome.ok and "live samples unavailable (cause unknown)" in outcome.warnings
    assert outcome.data["colour_basis"] == "state_slot_0"
    assert outcome.data["live"]["status"] == "unavailable"


@pytest.mark.anyio
async def test_other_live_failures_keep_the_existing_safe_error_envelope(tmp_path):
    malformed = live_router({"leds": ["invalid"], "n": 1})
    broken = live_router(httpx.Response(500))
    async with open_resources(tmp_path, malformed) as resources:
        bad = await call(resources, NAME, live_samples=True)
    async with open_resources(tmp_path, broken) as resources:
        error = await call(resources, NAME, live_samples=True)
    assert failure_code(bad) == "INVALID_RESPONSE" and failure_code(error) == "INVALID_RESPONSE"


@pytest.mark.anyio
async def test_an_offline_device_gives_the_unreachable_envelope_without_a_drawing(tmp_path):
    router = three_segments()
    router.set(DESK, "/json/state", httpx.ConnectError("synthetic-secret"))
    async with open_resources(tmp_path, router, read_retries=0) as resources:
        outcome = await call(resources, NAME)
    assert failure_code(outcome) == "UNREACHABLE" and outcome.device_id == "desk"
    assert "synthetic-secret" not in outcome.model_dump_json()


# ================================================================== access, privacy, bounds


@pytest.mark.anyio
async def test_the_output_contains_none_of_the_devices_private_identifiers(tmp_path):
    router = three_segments()
    async with open_resources(tmp_path, router) as resources:
        observed = await call(resources, NAME)
        proposed = await call(resources, NAME, segments=[{"id": 0, "start": 0, "stop": 30}])
    for outcome in (observed, proposed):
        dumped = outcome.model_dump_json()
        for private in ("desk.invalid", "00005e005301", "192.0.2.10", "Synthetic", "16.0.1"):
            assert private not in dumped


@pytest.mark.anyio
@pytest.mark.parametrize("profile,caps", [("read-only", {}), ("full", {"desk": ToolClass.READ})])
async def test_the_tool_is_served_in_a_read_only_profile_and_for_a_read_capped_device(
    tmp_path, profile, caps
):
    router = three_segments()
    async with open_resources(tmp_path, router) as resources:
        server = create_server(build_operations(resources), AccessPolicy(profile, caps))
        async with Client(server) as client:
            names = [tool.name for tool in (await client.list_tools()).tools]
            result = await client.call_tool(NAME, {"device_id": "desk"})
    assert NAME in names
    envelope = result.structured_content
    assert envelope is not None and envelope["ok"] is True and envelope["data"]["svg"]
    assert json.loads(result.content[0].text) == envelope  # the SVG travels as plain data
    assert router.calls == STATE_INFO


@pytest.mark.anyio
async def test_an_output_over_the_size_cap_fails_safely_instead_of_truncating(
    tmp_path, monkeypatch
):
    router = three_segments()
    monkeypatch.setattr(preview_tools, "MAX_SVG_BYTES", 100)
    async with open_resources(tmp_path, router) as resources:
        outcome = await call(resources, NAME)
    assert failure_code(outcome) == "INVALID_RESPONSE"
    assert len(outcome.model_dump_json()) < 1024
    assert MAX_SVG_BYTES == 48 * 1024  # the real cap is unchanged by the monkeypatch
