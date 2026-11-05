"""Tests for ``wled_replace_layout`` (issue #7): T05-T10, SEG-02..05, MULTI-01, REL-03.

All tests use the stateful fake in ``tests/layout_support.py`` over a mock transport.
No LAN access and no real device.
"""

from __future__ import annotations

import json
from pathlib import Path

import anyio
import httpx2 as httpx
import pytest
from pydantic import ValidationError

from tests.layout_support import FakeWLED, inactive_slot
from tests.state_catalog_support import make_segment
from tests.test_inventory_client import config, device
from wled_mcp.layouts import ReplaceLayoutRequest
from wled_mcp.operations import build_operations
from wled_mcp.resources import Resources

DESK = "desk.invalid"
BLUE = [[0, 0, 255]]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def fixture_segments():
    """The synthetic case of examples/contracts/replace.json."""
    return [
        make_segment(0, 0, 10),
        make_segment(
            2,
            10,
            20,
            bri=180,
            col=[[255, 80, 0, 0], [1, 2, 3, 0], [4, 5, 6, 0]],
            fx=1,
            sx=90,
            ix=70,
            n="Edge",
        ),
        make_segment(5, 20, 30),
    ]


def fixture_fake(**kwargs):
    kwargs.setdefault("slot_count", 6)
    return FakeWLED(fixture_segments(), **kwargs)


def open_resources(tmp_path, fake, devices=None, clock=None, **settings):
    return Resources(config(tmp_path, devices=devices, **settings), fake.transport(), clock)


async def replace(resources, segments, **arguments):
    arguments.setdefault("device_id", "desk")
    arguments["segments"] = segments
    operation = {o.name: o for o in build_operations(resources)}["wled_replace_layout"]
    return await operation.execute(ReplaceLayoutRequest.model_validate(arguments).model_dump())


def seg_payloads(fake):
    """Segment payloads of every POST (main-only POSTs are shown as ``mainseg``)."""
    result = []
    for body in fake.posts:
        result.append(body["seg"] if "seg" in body else {"mainseg": body["mainseg"]})
    return result


def keep_all(**first):
    """Fixture layout unchanged, with optional field changes on ID 0."""
    return [
        {"id": 0, "start": 0, "stop": 10, **first},
        {"id": 2, "start": 10, "stop": 20},
        {"id": 5, "start": 20, "stop": 30},
    ]


def by_id(fake):
    return {s["id"]: s for s in fake.active()}


# ======================================================================= T05: exact replace


@pytest.mark.anyio
async def test_T05_fixture_case_exact_post_sequence_and_final_layout(tmp_path):
    fake = fixture_fake()
    desired = [
        {"id": 2, "start": 0, "stop": 30},
        {"id": 6, "start": 30, "stop": 60, "colors": BLUE},
    ]
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(resources, desired)
    assert result.ok, (result.application, result.verification, result.error, result.data)
    assert (result.application, result.verification) == ("applied", "verified")
    assert fake.posts == [
        {"mainseg": 2},
        {"seg": {"id": 0, "stop": 0}},
        {"seg": {"id": 5, "stop": 0}},
        {"seg": {"id": 2, "start": 0, "stop": 30, "n": "Edge"}},
        {
            "seg": {
                "id": 6,
                "start": 30,
                "stop": 60,
                "on": True,
                "bri": 255,
                "col": [[0, 0, 255], [0, 0, 0], [0, 0, 0]],
                "frz": False,
                "n": "",
                "fx": 0,
                "pal": 0,
                "sx": 128,
                "ix": 128,
                "grp": 1,
                "spc": 0,
                "of": 0,
                "rev": False,
                "mi": False,
                "sel": False,
            }
        },
    ]
    assert fake.layout() == {2: (0, 30), 6: (30, 60)}
    assert fake.mainseg == 2
    assert not fake.array_used
    kept = by_id(fake)[2]
    assert kept["col"][:3] == [[255, 80, 0, 0], [1, 2, 3, 0], [4, 5, 6, 0]]
    assert (kept["fx"], kept["sx"], kept["ix"], kept["bri"], kept["on"], kept["n"]) == (
        1,
        90,
        70,
        180,
        True,
        "Edge",
    )
    assert [s["status"] for s in result.data["steps_report"]] == ["verified"] * 5
    assert result.data["plan"]["main_segment"] == {
        "current": 0,
        "target": 2,
        "changed": True,
        "step": 0,
    }
    for body in fake.posts:  # master state is never part of a layout replacement
        assert not {"on", "bri", "tt", "transition", "ps", "pl", "live", "psave", "pdel"} & set(
            body
        )


@pytest.mark.anyio
async def test_T05_sparse_new_id_rejected_before_any_post_with_fixture_message(tmp_path):
    fake = fixture_fake()
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(
            resources,
            [{"id": 2, "start": 0, "stop": 30}, {"id": 8, "start": 30, "stop": 60, "colors": BLUE}],
        )
    assert result.error.code == "UNSUPPORTED_CAPABILITY"
    assert result.error.message == (
        "New ID 8 cannot be allocated as requested; the known next slot is 6."
    )
    assert (result.application, result.verification) == ("not_attempted", "not_requested")
    assert fake.posts == []


@pytest.mark.anyio
@pytest.mark.parametrize("stale_count", [1, 3, 9, 20])
async def test_T05_removal_count_equals_exact_stale_set_without_fixed_tail(tmp_path, stale_count):
    # Noncontiguous IDs 0,3,6,... ; keep ID 0 only.
    ids = [i * 3 for i in range(stale_count + 1)]
    segments = [make_segment(i, n, n + 1) for n, i in enumerate(ids)]
    fake = FakeWLED(segments, led_count=200, maxseg=64)
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(resources, [{"id": 0, "start": 0, "stop": 1}])
    assert result.ok, result.error
    removed = [p["id"] for p in seg_payloads(fake) if p.get("stop") == 0]
    assert removed == ids[1:] and len(removed) == stale_count
    assert fake.layout() == {0: (0, 1)}
    assert not fake.array_used
    assert len(fake.posts) == stale_count  # nothing else: no filler, no purge, no reset


@pytest.mark.anyio
async def test_T05_gap_reuse_and_chained_creates_ascending(tmp_path):
    fake = FakeWLED(
        [make_segment(0, 0, 10), make_segment(2, 10, 20), make_segment(5, 20, 30)],
        slot_count=6,
        led_count=100,
    )
    desired = [
        {"id": 0, "start": 0, "stop": 10},
        {"id": 1, "start": 30, "stop": 40, "colors": BLUE},  # gap: reused inactive slot
        {"id": 2, "start": 10, "stop": 20},
        {"id": 4, "start": 40, "stop": 50, "colors": BLUE},  # gap
        {"id": 5, "start": 20, "stop": 30},
        {"id": 6, "start": 50, "stop": 60, "colors": BLUE},  # next slot
        {"id": 7, "start": 60, "stop": 70, "colors": BLUE},  # chained
    ]
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(resources, desired)
    assert result.ok, result.error
    created = [p["id"] for p in seg_payloads(fake)]
    assert created == [1, 4, 6, 7]
    assert fake.layout() == {s["id"]: (s["start"], s["stop"]) for s in desired}
    assert any("inherited_unexposed_state" in w for w in result.warnings)


@pytest.mark.anyio
async def test_T05_sparse_chain_is_rejected_without_post(tmp_path):
    fake = fixture_fake(led_count=100)
    desired = [
        {"id": 0, "start": 0, "stop": 10},
        {"id": 6, "start": 30, "stop": 40, "colors": BLUE},
        {"id": 8, "start": 40, "stop": 50, "colors": BLUE},
    ]
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(resources, desired)
    assert result.error.code == "UNSUPPORTED_CAPABILITY" and "ID 8" in result.error.message
    assert fake.posts == []


@pytest.mark.anyio
async def test_T05_blocked_move_waits_and_no_intermediate_overlap(tmp_path):
    # 1 [0,10) and 2 [10,20) shift right by 10: 2 must move before 1.
    fake = FakeWLED([make_segment(1, 0, 10), make_segment(2, 10, 20)], led_count=60)
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(
            resources,
            [{"id": 1, "start": 10, "stop": 20}, {"id": 2, "start": 20, "stop": 30}],
        )
    assert result.ok, result.error
    assert [p["id"] for p in seg_payloads(fake) if "id" in p] == [2, 1]
    for layout in fake.layouts:
        spans = sorted(layout.values())
        assert all(a[1] <= b[0] for a, b in zip(spans, spans[1:], strict=False))


@pytest.mark.anyio
async def test_T05_swap_cycle_is_rejected_without_temporary_segment(tmp_path):
    fake = FakeWLED([make_segment(1, 0, 20), make_segment(2, 20, 40)], led_count=60)
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(
            resources,
            [{"id": 1, "start": 20, "stop": 40}, {"id": 2, "start": 0, "stop": 20}],
        )
    assert result.error.code == "UNSUPPORTED_CAPABILITY"
    assert fake.posts == []


@pytest.mark.anyio
async def test_T05_main_id_handling(tmp_path):
    # main stays: main ID desired -> no mainseg key at all
    fake = fixture_fake()
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(resources, [{"id": 0, "start": 0, "stop": 10}])
    assert result.ok and all("mainseg" not in body for body in fake.posts)
    assert result.data["plan"]["main_segment"]["changed"] is False
    # all-new desired set + stale main: redirect is the LAST step, with a warning
    fake = fixture_fake()
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(resources, [{"id": 6, "start": 30, "stop": 60, "colors": BLUE}])
    assert result.ok, result.error
    assert fake.posts[-1] == {"mainseg": 6} and fake.mainseg == 6
    assert any("main_segment_transient" in w for w in result.warnings)
    # main inactive/out of range is redirected to the lowest desired ID
    fake = FakeWLED([make_segment(3, 0, 10)], mainseg=0, slot_count=4)
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(resources, [{"id": 3, "start": 0, "stop": 20}])
    assert result.ok and fake.posts[0] == {"mainseg": 3}


@pytest.mark.anyio
async def test_T05_preserved_and_requested_fields_on_existing_ids(tmp_path):
    fake = fixture_fake()
    desired = [
        {
            "id": 2,
            "start": 10,
            "stop": 20,
            "speed": 10,
            "grouping": 2,
            "spacing": 1,
            "offset": 3,
            "reverse": True,
            "mirror": True,
            "selected": False,
            "name": "Renamed",
            "colors": [[1, 1, 1]],
        },
        {"id": 0, "start": 0, "stop": 10},
        {"id": 5, "start": 20, "stop": 30},
    ]
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(resources, desired)
    assert result.ok, (result.error, result.data.get("observed"))
    assert seg_payloads(fake) == [
        {
            "id": 2,
            "col": [[1, 1, 1]],
            "sx": 10,
            "grp": 2,
            "spc": 1,
            "of": 3,
            "rev": True,
            "mi": True,
            "sel": False,
            "n": "Renamed",
        }
    ]
    seg = by_id(fake)[2]
    assert seg["col"] == [[1, 1, 1, 0], [1, 2, 3, 0], [4, 5, 6, 0]]
    assert (seg["fx"], seg["ix"], seg["bri"]) == (1, 70, 180)
    assert result.data["plan"]["unchanged_segment_ids"] == [0, 5]


@pytest.mark.anyio
async def test_T05_brightness_is_sent_alone_like_patch_and_firmware_power_flip_is_reported(
    tmp_path,
):
    """Aligned with #6: bri is sent without an extra resolved on. The firmware turns an off
    segment on for bri>0 (known limit shared with #6); the final readback reports it."""
    fake = FakeWLED([make_segment(0, 0, 10, on=False, bri=100)])
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(resources, [{"id": 0, "start": 0, "stop": 10, "brightness": 50}])
    assert fake.posts == [{"seg": {"id": 0, "bri": 50}}]
    assert by_id(fake)[0]["on"] is True  # firmware side effect, modeled by the fake
    assert not result.ok and result.error.code == "VERIFICATION_MISMATCH"
    assert result.data["plan"]["targeted_compensation"] == []


@pytest.mark.anyio
async def test_T05_explicit_on_false_with_brightness_is_sent_as_requested(tmp_path):
    fake = FakeWLED([make_segment(0, 0, 10, on=False, bri=100)])
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(
            resources, [{"id": 0, "start": 0, "stop": 10, "brightness": 50, "on": False}]
        )
    assert result.ok, result.error
    assert fake.posts == [{"seg": {"id": 0, "bri": 50, "on": False}}]
    assert by_id(fake)[0]["on"] is False


@pytest.mark.anyio
async def test_T05_reused_slot_inherited_state_is_forced_to_defaults(tmp_path):
    fake = FakeWLED([make_segment(0, 0, 10), make_segment(2, 10, 20)], slot_count=3)
    fake.slots[1] = inactive_slot(1, frz=True, rev=True, fx=3, sx=7, on=False, n="Old")
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(
            resources,
            [
                {"id": 0, "start": 0, "stop": 10},
                {"id": 1, "start": 20, "stop": 30, "colors": BLUE},
                {"id": 2, "start": 10, "stop": 20},
            ],
        )
    assert result.ok, result.error
    seg = by_id(fake)[1]
    assert (seg["frz"], seg["rev"], seg["fx"], seg["sx"], seg["on"], seg.get("n", "")) == (
        False,
        False,
        0,
        128,
        True,
        "",
    )


# ======================================================================= T06: validation


def _rgbw_fake():
    return FakeWLED(lc=3, seglc=[3, 3, 3], led_count=60, slot_count=6, maxseg=16)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("segments", "code"),
    [
        pytest.param(
            [{"id": 0, "start": 0, "stop": 10}, {"id": 0, "start": 10, "stop": 20}],
            "VALIDATION_ERROR",
            id="duplicate-id",
        ),
        pytest.param(
            [{"id": 16, "start": 0, "stop": 10, "colors": BLUE}],
            "VALIDATION_ERROR",
            id="id-at-maxseg",
        ),
        pytest.param([{"id": 0, "start": 0, "stop": 61}], "VALIDATION_ERROR", id="stop-over-led"),
        pytest.param([{"id": 0, "start": 10, "stop": 10}], "VALIDATION_ERROR", id="start-ge-stop"),
        pytest.param(
            [{"id": 0, "start": 0, "stop": 15}, {"id": 2, "start": 10, "stop": 20}],
            "VALIDATION_ERROR",
            id="desired-overlap",
        ),
        pytest.param([{"id": 6, "start": 30, "stop": 40}], "VALIDATION_ERROR", id="new-no-colors"),
        pytest.param(
            [{"id": 6, "start": 30, "stop": 40, "colors": [[1, 2, 3, 4]]}],
            "UNSUPPORTED_CAPABILITY",
            id="new-4-channels-on-rgb",
        ),
        pytest.param(
            [{"id": 0, "start": 0, "stop": 10, "colors": [[1, 2, 3, 4]]}],
            "VALIDATION_ERROR",
            id="existing-rgb-with-4-channels",
        ),
        pytest.param(
            [{"id": 0, "start": 0, "stop": 10, "colors": [[1, 2]]}],
            "VALIDATION_ERROR",
            id="two-channels",
        ),
        pytest.param(
            [{"id": 0, "start": 0, "stop": 10, "colors": [[1, 2, 3]] * 4}],
            "VALIDATION_ERROR",
            id="four-slots",
        ),
        pytest.param(
            [{"id": 0, "start": 0, "stop": 10, "effect_id": 4}],
            "VALIDATION_ERROR",
            id="effect-range",
        ),
        pytest.param(
            [{"id": 0, "start": 0, "stop": 10, "palette_id": 3}],
            "VALIDATION_ERROR",
            id="palette-range",
        ),
        pytest.param(
            [{"id": 0, "start": 0, "stop": 10, "offset": 10}],
            "VALIDATION_ERROR",
            id="offset-ge-length",
        ),
        pytest.param(
            [{"id": 0, "start": 0, "stop": 10, "on": True, "brightness": 0}],
            "VALIDATION_ERROR",
            id="on-true-bri-zero",
        ),
        pytest.param(
            [{"id": 0, "start": 0, "stop": 10, "brightness": 0}],
            "VALIDATION_ERROR",
            id="bri-zero-resolves-on",
        ),
        pytest.param(
            [{"id": 0, "start": 0, "stop": 10}]
            + [
                {"id": 2, "start": 10, "stop": 20},
                {"id": 5, "start": 20, "stop": 30, "colors": [[1, 2, 3]], "effect_id": 99},
            ],
            "VALIDATION_ERROR",
            id="late-invalid-entry-leaves-device-untouched",
        ),
    ],
)
async def test_T06_invalid_requests_send_no_post(tmp_path, segments, code):
    fake = fixture_fake()
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(resources, segments)
    assert result.error is not None and result.error.code == code, result.error
    assert (result.application, result.verification) == ("not_attempted", "not_requested")
    assert result.data == {}
    assert fake.posts == []


@pytest.mark.anyio
async def test_T06_name_of_32_characters_is_accepted_by_validation(tmp_path):
    """Validation counts characters (aligned with #6); the firmware byte buffer is a limit."""
    fake = fixture_fake()
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(
            resources,
            [{"id": 0, "start": 0, "stop": 10, "name": "ä" * 32}],
            dry_run=True,
        )
    assert result.ok, result.error
    assert fake.posts == []  # the dry run does not warn about the firmware byte buffer


@pytest.mark.anyio
async def test_T06_multibyte_name_over_firmware_buffer_is_reported_as_mismatch(tmp_path):
    """32 two-byte characters pass validation but exceed a 32-byte firmware buffer: the
    firmware truncates silently and the final readback reports VERIFICATION_MISMATCH."""
    fake = fixture_fake()
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(resources, [{"id": 0, "start": 0, "stop": 10, "name": "ä" * 32}])
    assert result.error is not None and result.error.code == "VERIFICATION_MISMATCH"
    assert by_id(fake)[0]["n"] == "ä" * 16  # truncated to the 32-byte buffer


@pytest.mark.anyio
async def test_T06_grouping_256_on_new_id_wraps_and_keeps_earlier_removals_applied(tmp_path):
    fake = fixture_fake()
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(
            resources,
            [
                {"id": 0, "start": 0, "stop": 10},
                {"id": 1, "start": 10, "stop": 20, "colors": BLUE, "grouping": 256},
            ],
        )
    assert result.error is not None and result.error.code == "VERIFICATION_MISMATCH"
    assert (result.application, result.verification) == ("applied", "mismatch")
    assert result.data["completed_steps"] >= 2  # earlier removals stay applied
    assert sorted(by_id(fake)) == [0, 1]
    assert by_id(fake)[1]["grp"] == 1  # 256 wrapped by the firmware uint8_t argument


@pytest.mark.anyio
async def test_T06_rgbw_rules(tmp_path):
    # RGBW 3 channels on an existing unchanged range -> validation error (never padded)
    fake = _rgbw_fake()
    async with open_resources(tmp_path, fake) as resources:
        three = await replace(resources, [{"id": 0, "start": 0, "stop": 10, "colors": [[1, 2, 3]]}])
        four = await replace(
            resources, [{"id": 0, "start": 0, "stop": 10, "colors": [[1, 2, 3, 4]]}], dry_run=True
        )
        moved = await replace(
            resources, [{"id": 0, "start": 0, "stop": 12, "colors": [[1, 2, 3, 4]]}], dry_run=True
        )
        new = await replace(
            resources,
            [{"id": 6, "start": 30, "stop": 40, "colors": [[1, 2, 3, 4]]}],
            dry_run=True,
        )
    assert three.error.code == "VALIDATION_ERROR"
    assert four.ok, four.error  # exact 4 channels on an unchanged RGBW range
    assert moved.error.code == "UNSUPPORTED_CAPABILITY"
    assert new.error.code == "UNSUPPORTED_CAPABILITY"
    assert fake.posts == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    "fake_kwargs",
    [
        {"lc": None},
        {"lc": 5},  # CCT bit
        {"lc": "x"},
        {"seglc": None, "lc": 1},  # absent seglc is allowed ...
        {"seglc": [1, 1]},  # misaligned
        {"seglc": [1, 1, 3]},  # mixed
    ],
)
async def test_T06_new_range_capability_evidence(tmp_path, fake_kwargs):
    fake = fixture_fake(**fake_kwargs)
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(
            resources,
            [{"id": 6, "start": 30, "stop": 40, "colors": BLUE}],
            dry_run=True,
        )
    if fake_kwargs == {"seglc": None, "lc": 1}:
        assert result.ok, result.error
    else:
        assert result.error.code == "UNSUPPORTED_CAPABILITY"
    assert fake.posts == []


@pytest.mark.anyio
async def test_T06_unknown_led_count_or_maxseg(tmp_path):
    fake = fixture_fake()
    original = fake.info

    def no_count():
        info = original()
        del info["leds"]["count"]
        return info

    fake.info = no_count
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(resources, [{"id": 0, "start": 0, "stop": 10}])
    assert result.error.code == "UNSUPPORTED_CAPABILITY"

    def no_max():
        info = original()
        del info["leds"]["maxseg"]
        return info

    fake.info = no_max
    async with open_resources(tmp_path, fake) as resources:
        new = await replace(resources, [{"id": 6, "start": 30, "stop": 40, "colors": BLUE}])
        existing = await replace(resources, [{"id": 0, "start": 0, "stop": 10}], dry_run=True)
    assert new.error.code == "UNSUPPORTED_CAPABILITY"
    assert existing.ok
    assert fake.posts == []


@pytest.mark.anyio
async def test_T06_shrinking_move_that_would_clamp_the_offset_is_rejected(tmp_path):
    fake = FakeWLED([make_segment(0, 0, 20, of=15)])
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(resources, [{"id": 0, "start": 0, "stop": 10}])
        ok = await replace(
            resources, [{"id": 0, "start": 0, "stop": 10, "offset": 2}], dry_run=True
        )
    assert result.error.code == "VALIDATION_ERROR" and "offset" in result.error.message
    assert ok.ok
    assert fake.posts == []


@pytest.mark.anyio
async def test_T06_unrepresentable_preservation_is_rejected(tmp_path):
    fake = FakeWLED([make_segment(0, 0, 20, n=5)])  # non-string name
    async with open_resources(tmp_path, fake) as resources:
        moved = await replace(resources, [{"id": 0, "start": 0, "stop": 10}])
    assert moved.error.code == "UNSUPPORTED_CAPABILITY"
    assert fake.posts == []


def test_T06_schema_rejections():
    base = {"device_id": "desk", "segments": [{"id": 0, "start": 0, "stop": 10}]}
    ReplaceLayoutRequest.model_validate(base)
    for bad in (
        {**base, "segments": []},
        {**base, "extra": 1},
        {**base, "segments": [{"id": 0, "start": 0, "stop": 10, "host": "x"}]},
        {**base, "segments": [{"id": True, "start": 0, "stop": 10}]},
        {**base, "segments": [{"id": 0, "start": 0, "stop": 10, "grouping": 0}]},
        {**base, "segments": [{"id": 0, "start": 0, "stop": 10, "spacing": -1}]},
        {**base, "segments": [{"id": 0, "start": 0, "stop": 10, "name": "a" * 33}]},
        {**base, "segments": [{"id": 0, "start": 0, "stop": 10, "brightness": 256}]},
        {**base, "segments": [{"id": 0, "start": 0, "stop": 10, "on": 1}]},
        {**base, "segments": [{"start": 0, "stop": 10}]},
        {**base, "segments": [{"id": 0, "stop": 10}]},
        {**base, "segments": [{"id": 0, "start": 0}]},
    ):
        with pytest.raises(ValidationError):
            ReplaceLayoutRequest.model_validate(bad)


def test_T06_limits_align_with_patch_segments():
    """#7 follows #6: 32-character name, no extra 255 cap on grouping/spacing."""
    seg = {"id": 0, "start": 0, "stop": 10, "grouping": 1000, "spacing": 1000, "name": "ä" * 32}
    ReplaceLayoutRequest.model_validate({"device_id": "desk", "segments": [seg]})


@pytest.mark.anyio
async def test_T06_unknown_device_has_zero_http(tmp_path):
    fake = fixture_fake()
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(resources, [{"id": 0, "start": 0, "stop": 10}], device_id="nowhere")
    assert result.error.code == "UNKNOWN_DEVICE" and fake.calls == []


# ======================================================================= T07: dry run


@pytest.mark.anyio
async def test_T07_dry_run_has_no_post_no_files_and_live_executes_the_same_payloads(tmp_path):
    desired = [
        {"id": 2, "start": 0, "stop": 30},
        {"id": 6, "start": 30, "stop": 60, "colors": BLUE},
    ]
    fake = fixture_fake()
    before = sorted(p.name for p in Path(tmp_path).iterdir())
    async with open_resources(tmp_path, fake) as resources:
        dry = await replace(resources, desired, dry_run=True)
        assert fake.posts == [] and fake.method_count("POST") == 0
        live = await replace(resources, desired)
    assert sorted(p.name for p in Path(tmp_path).iterdir()) == before
    assert (
        dry.ok
        and dry.dry_run
        and (dry.application, dry.verification)
        == (
            "not_attempted",
            "not_requested",
        )
    )
    plan = dry.data["plan"]
    assert plan["update_segment_ids"] == [2]
    assert plan["create_segment_ids"] == [6]
    assert plan["remove_segment_ids"] == [0, 5]
    assert plan["unchanged_segment_ids"] == []
    assert plan["step_actions"] == ["set_main", "remove", "remove", "update", "create"]
    assert plan["targeted_compensation"] == [{"id": 2, "name": "Edge"}]
    assert plan["step_payloads"] == fake.posts
    resolved = {s["id"]: s for s in plan["resolved_segments"]}
    assert resolved[6]["colors"] == [[0, 0, 255], [0, 0, 0], [0, 0, 0]]
    assert (resolved[6]["grouping"], resolved[6]["name"], resolved[6]["effective_brightness"]) == (
        1,
        "",
        255,
    )
    assert resolved[2]["name"] == "Edge" and resolved[2]["effect_id"] == 1
    assert live.data["plan"] == plan
    assert live.ok and dry.data["postconditions"] == live.data["postconditions"]


@pytest.mark.anyio
async def test_T07_live_call_replans_when_state_changed_after_dry_run(tmp_path):
    desired = [{"id": 0, "start": 0, "stop": 10}, {"id": 2, "start": 10, "stop": 20}]
    fake = fixture_fake()
    async with open_resources(tmp_path, fake) as resources:
        dry = await replace(resources, desired, dry_run=True)
        assert dry.data["plan"]["remove_segment_ids"] == [5]
        fake.slots[5]["stop"] = 0  # ID 5 disappeared in the meantime
        live = await replace(resources, desired)
    assert live.ok and live.application == "not_attempted"  # nothing left to do
    assert live.data["plan"]["noop"] is True and fake.posts == []


@pytest.mark.anyio
async def test_T07_noop_request_sends_zero_posts(tmp_path):
    fake = fixture_fake()
    desired = [
        {"id": 0, "start": 0, "stop": 10},
        {"id": 2, "start": 10, "stop": 20, "name": "Edge", "speed": 90},
        {"id": 5, "start": 20, "stop": 30},
    ]
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(resources, desired)
    assert result.ok and (result.application, result.verification) == (
        "not_attempted",
        "not_requested",
    )
    assert result.data["plan"]["noop"] and result.data["plan"]["unchanged_segment_ids"] == [0, 2, 5]
    assert len(result.warnings) == 1
    assert fake.posts == []


# ======================================================================= T08: verification


@pytest.mark.anyio
async def test_T08_ack_without_effect_is_a_mismatch_not_success(tmp_path):
    fake = fixture_fake()
    fake.post_actions = {i: "drop" for i in range(10)}
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(resources, [{"id": 0, "start": 0, "stop": 10}])
    assert not result.ok and result.error.code == "VERIFICATION_MISMATCH"
    assert (result.application, result.verification) == ("unknown", "mismatch")
    assert len(fake.posts) == 1  # stops at the first unproven step
    assert result.data["steps_report"][0]["status"] == "failed"
    assert result.data["observed"]["active"][0] == {"id": 0, "start": 0, "stop": 10}


@pytest.mark.anyio
async def test_T08_ignored_field_is_mismatch_with_observation(tmp_path):
    fake = fixture_fake()
    fake.ignore_keys = {"rev"}
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(
            resources,
            [
                {"id": 0, "start": 0, "stop": 10},
                {"id": 2, "start": 10, "stop": 20, "reverse": True},
                {"id": 5, "start": 20, "stop": 30},
            ],
        )
    assert result.error.code == "VERIFICATION_MISMATCH"
    assert result.data["no_replay"] is True
    assert result.data["steps_report"][0] == {
        "index": 0,
        "action": "update",
        "id": 2,
        "status": "failed",
    }


@pytest.mark.anyio
async def test_T08_zero_brightness_with_off_is_accepted_and_envelope_roundtrips(tmp_path):
    fake = FakeWLED([make_segment(0, 0, 10, bri=200)])
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(
            resources, [{"id": 0, "start": 0, "stop": 10, "on": False, "brightness": 0}]
        )
    assert result.ok, result.error
    assert fake.posts == [{"seg": {"id": 0, "bri": 0, "on": False}}]
    envelope = json.loads(result.model_dump_json())
    assert envelope["operation"] == "wled_replace_layout"
    assert envelope["data"]["steps_report"][0]["status"] == "verified"


@pytest.mark.anyio
async def test_T08_tool_registration_annotations_and_schema(tmp_path):
    fake = fixture_fake()
    async with open_resources(tmp_path, fake) as resources:
        tool = {o.name: o for o in build_operations(resources)}["wled_replace_layout"]
    hints = tool.annotations
    assert (hints.read_only_hint, hints.destructive_hint) == (False, True)
    assert (hints.idempotent_hint, hints.open_world_hint) == (False, False)
    schema = tool.request_model.model_json_schema()
    assert schema["additionalProperties"] is False
    assert schema["$defs"]["LayoutSegment"]["additionalProperties"] is False


# ======================================================================= T09: uncertain writes


@pytest.mark.anyio
@pytest.mark.parametrize("k", [0, 1, 2, 3, 4])
async def test_T09_post_failure_at_step_k_with_unreadable_state_stops_there(tmp_path, k):
    fake = fixture_fake()
    fake.post_actions = {k: "fail_after"}
    fake.fail_reads_from_post = k + 1
    desired = [
        {"id": 2, "start": 0, "stop": 30},
        {"id": 6, "start": 30, "stop": 60, "colors": BLUE},
    ]
    async with open_resources(tmp_path, fake, operation_timeout_seconds=1, read_retries=0) as r:
        result = await replace(r, desired)
    assert result.error.code == "WRITE_OUTCOME_UNKNOWN"
    assert (result.application, result.verification) == ("unknown", "unknown")
    assert len(fake.posts) == k + 1  # nothing after the uncertain step, nothing replayed
    statuses = [s["status"] for s in result.data["steps_report"]]
    assert statuses == ["verified"] * k + ["uncertain"] + ["not_dispatched"] * (4 - k)
    assert result.data["completed_steps"] == k
    assert [s["index"] for s in result.data["remaining_steps"]] == list(range(k, 5))
    assert "synthetic" not in result.model_dump_json()
    if k < 3:  # no removal happened after the failure point
        removed = [b for b in fake.posts if "seg" in b and b["seg"].get("stop") == 0]
        assert len(removed) <= max(0, k)


@pytest.mark.anyio
async def test_T09_failed_post_with_readable_differing_state_is_unknown_mismatch(tmp_path):
    fake = fixture_fake()
    fake.post_actions = {0: "fail_before"}
    async with open_resources(tmp_path, fake, read_retries=0) as resources:
        result = await replace(resources, [{"id": 0, "start": 0, "stop": 10}])
    assert (result.application, result.verification) == ("unknown", "mismatch")
    assert result.error.code == "VERIFICATION_MISMATCH"
    assert len(fake.posts) == 1


@pytest.mark.anyio
async def test_T09_failed_last_step_post_with_matching_final_state_is_success(tmp_path):
    fake = fixture_fake()
    fake.post_actions = {0: "fail_after"}  # applied, but the ACK is lost
    async with open_resources(tmp_path, fake, read_retries=0) as resources:
        result = await replace(resources, keep_all(speed=5))
    assert result.ok and result.application == "applied"
    assert len(fake.posts) == 1


@pytest.mark.anyio
async def test_T09_failed_post_with_matching_state_on_earlier_step_still_stops(tmp_path):
    fake = fixture_fake()
    fake.post_actions = {0: "fail_after"}  # the redirect was applied; ACK lost
    async with open_resources(tmp_path, fake, read_retries=0) as resources:
        result = await replace(
            resources,
            [{"id": 2, "start": 0, "stop": 30}],
        )
    assert result.error.code == "WRITE_OUTCOME_UNKNOWN"
    assert len(fake.posts) == 1 and fake.mainseg == 2
    assert result.data["steps_report"][1]["status"] == "not_dispatched"


@pytest.mark.anyio
async def test_T09_external_interference_is_reported_never_corrected(tmp_path):
    fake = fixture_fake()

    def interfere(device: FakeWLED) -> None:
        device.slots[4] = make_segment(4, 40, 50)  # an extra active ID appears
        device.slots.extend([])

    fake.interference = {1: interfere}
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(
            resources,
            [{"id": 2, "start": 0, "stop": 30}, {"id": 6, "start": 30, "stop": 60, "colors": BLUE}],
        )
    assert result.error.code == "VERIFICATION_MISMATCH"
    assert (result.application, result.verification) == ("applied", "mismatch")
    assert len(fake.posts) == 2  # stopped right after the disturbed step: no corrective POST
    assert result.data["completed_steps"] == 1
    assert {"id": 4, "start": 40, "stop": 50} in result.data["observed"]["active"]


@pytest.mark.anyio
async def test_T09_interference_during_the_only_step_is_unknown_mismatch(tmp_path):
    fake = fixture_fake()

    def interfere(device: FakeWLED) -> None:
        device.slots[4] = make_segment(4, 40, 50)

    fake.interference = {0: interfere}  # single-step plan: last step verified, extra ID found
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(
            resources,
            [
                {"id": 0, "start": 0, "stop": 10, "speed": 5},
                {"id": 2, "start": 10, "stop": 20},
                {"id": 5, "start": 20, "stop": 30},
            ],
        )
    assert (result.application, result.verification) == ("unknown", "mismatch")
    assert len(fake.posts) == 1


@pytest.mark.anyio
async def test_T09_budget_exhaustion_stops_before_dispatch(tmp_path, monkeypatch):
    """Deterministic: the clock jumps once step 2 (index 1) was dispatched, so the pre-dispatch
    budget check of the next step fails without any wall-clock sleep."""
    fake = fixture_fake()
    offset = {"value": 0.0}
    real_time = anyio.current_time
    monkeypatch.setattr(anyio, "current_time", lambda: real_time() + offset["value"])

    def jump_after_second_post():
        if len(fake.posts) == 2:
            offset["value"] = 9.99  # operation timeout is 10 s: about 0.01 s remain

    fake.read_hook = jump_after_second_post
    async with open_resources(
        tmp_path, fake, operation_timeout_seconds=10, read_retries=0
    ) as resources:
        result = await replace(
            resources,
            [{"id": 2, "start": 0, "stop": 30}, {"id": 6, "start": 30, "stop": 60, "colors": BLUE}],
        )
    assert len(fake.posts) == 2  # exactly the dispatched steps; nothing after the budget ended
    assert result.error.code == "TIMEOUT"
    assert (result.application, result.verification) == ("applied", "mismatch")
    assert result.error.write_retryable is False
    statuses = [s["status"] for s in result.data["steps_report"]]
    assert statuses == [
        "verified",
        "verified",
        "not_dispatched",
        "not_dispatched",
        "not_dispatched",
    ]
    assert result.data["completed_steps"] == 2
    assert len({json.dumps(p, sort_keys=True) for p in fake.posts}) == 2  # no replay


@pytest.mark.anyio
async def test_T09_final_check_mismatch_after_all_steps_verified(tmp_path):
    """Interference on a preserved field of an untouched ID during the last step: every step
    verifies, only the final check against the full desired layout fails."""
    fake = fixture_fake()

    def interfere(device: FakeWLED) -> None:
        device.slots[2]["fx"] = 0  # ID 2 is preserved, not among the last step's fields

    fake.interference = {4: interfere}
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(
            resources,
            [{"id": 2, "start": 0, "stop": 30}, {"id": 6, "start": 30, "stop": 60, "colors": BLUE}],
        )
    assert [s["status"] for s in result.data["steps_report"]] == ["verified"] * 5
    assert (result.application, result.verification) == ("applied", "mismatch")
    assert result.error.code == "VERIFICATION_MISMATCH"
    assert len(fake.posts) == 5


@pytest.mark.anyio
async def test_T09_repeated_call_is_a_new_explicit_invocation(tmp_path):
    fake = fixture_fake()
    fake.post_actions = {0: "drop"}
    desired = keep_all(speed=7)
    async with open_resources(tmp_path, fake) as resources:
        first = await replace(resources, desired)
        assert not first.ok and len(fake.posts) == 1
        second = await replace(resources, desired)
    assert second.ok and len(fake.posts) == 2


# ======================================================================= T10: serialization


@pytest.mark.anyio
async def test_T10_concurrent_replacements_on_one_device_are_fully_serialized(tmp_path):
    fake = fixture_fake()
    order: list[str] = []
    first_in_write = anyio.Event()
    release = anyio.Event()

    async def hold(_device, _request):
        order.append("a-post")
        first_in_write.set()
        await release.wait()
        return None

    fake.post_actions = {0: hold}
    original_call = fake.__call__

    async def tracing(request):
        if request.method == "GET" and request.url.path == "/json/state":
            order.append("get")
        return await original_call(request)

    fake.__class__ = type("Traced", (FakeWLED,), {"__call__": lambda self, r: tracing(r)})
    a = keep_all(speed=1)
    b = keep_all(speed=2)
    async with open_resources(tmp_path, fake) as resources:
        results = {}

        async def run(label, segments):
            if label == "b":
                await first_in_write.wait()
            results[label] = await replace(resources, segments)

        async with anyio.create_task_group() as group:
            group.start_soon(run, "a", a)
            group.start_soon(run, "b", b)
            await first_in_write.wait()
            await anyio.sleep(0.05)
            assert resources.locks["desk"].locked()
            assert len(fake.posts) == 1  # B has not dispatched anything
            release.set()
    assert results["a"].ok and results["b"].ok
    # A: GET, POST, readback GET; only then B's first GET (A holds the lock throughout).
    assert order[:4] == ["get", "a-post", "get", "get"]
    assert [p["seg"]["sx"] for p in fake.posts] == [1, 2]
    assert by_id(fake)[0]["sx"] == 2


@pytest.mark.anyio
async def test_T10_other_device_progresses_while_one_is_writing(tmp_path):
    desk, shelf = fixture_fake(), fixture_fake()
    desk_in_write = anyio.Event()
    shelf_done = anyio.Event()
    release = anyio.Event()

    async def hold(_device, _request):
        desk_in_write.set()
        await release.wait()

    desk.post_actions = {0: hold}

    async def route(request: httpx.Request) -> httpx.Response:
        return await (desk if request.url.host == DESK else shelf)(request)

    class Both:
        def transport(self):
            return httpx.MockTransport(route)

    async with Resources(
        config(tmp_path, devices=[device(), device("shelf")]), Both().transport()
    ) as resources:

        async def desk_call():
            return await replace(resources, keep_all(speed=1))

        async def shelf_call():
            await desk_in_write.wait()
            result = await replace(resources, keep_all(speed=1), device_id="shelf")
            shelf_done.set()
            return result

        async with anyio.create_task_group() as group:
            group.start_soon(desk_call)
            group.start_soon(shelf_call)
            with anyio.fail_after(3):
                await shelf_done.wait()
            release.set()
    assert len(shelf.posts) == 1 and len(desk.posts) == 1


# ======================================================================= contract examples

EXAMPLES = Path(__file__).resolve().parents[1] / "examples/contracts"
FIXTURE_DESIRED = [
    {"id": 2, "start": 0, "stop": 30},
    {"id": 6, "start": 30, "stop": 60, "colors": BLUE},
]


def _envelope(result):
    return json.loads(result.model_dump_json())


async def _example_outputs(tmp_path):
    outputs = {}
    async with open_resources(tmp_path, fixture_fake()) as resources:
        outputs["dry_run"] = _envelope(await replace(resources, FIXTURE_DESIRED, dry_run=True))
    rejected = [{"id": 2, "start": 0, "stop": 30}, {**FIXTURE_DESIRED[1], "id": 8}]
    async with open_resources(tmp_path, fixture_fake()) as resources:
        outputs["rejected"] = _envelope(await replace(resources, rejected))
    fake = fixture_fake()

    def interfere(device: FakeWLED) -> None:
        device.slots[4] = make_segment(4, 40, 50)

    fake.interference = {2: interfere}
    async with open_resources(tmp_path, fake) as resources:
        outputs["partial"] = _envelope(await replace(resources, FIXTURE_DESIRED))
    return outputs


@pytest.mark.anyio
async def test_contract_examples_equal_actual_mock_output(tmp_path):
    outputs = await _example_outputs(tmp_path)
    replace_case = json.loads((EXAMPLES / "replace.json").read_text(encoding="utf-8"))
    assert replace_case["expected"] == outputs["dry_run"]
    assert replace_case["rejected_outcome"] == outputs["rejected"]
    errors = json.loads((EXAMPLES / "errors.json").read_text(encoding="utf-8"))["cases"]
    partial = next(c for c in errors if c["name"] == "replace_layout_partial_application")
    assert partial["expected"] == outputs["partial"]
    assert partial["expected"]["application"] == "applied"
    assert partial["mcp_isError"] is True
