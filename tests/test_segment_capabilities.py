"""Issue #19 PR A: capability model and read side (ISSUE-19-DEC-003, AC-19-01..03).

Pure-function tests for ``wled_mcp.capabilities`` plus ``wled_get_state`` over the
stateful fake in ``tests/layout_support.py`` (mock transport only, no LAN). The WLED 16
shapes follow the v16.0.1 source pin 29b389d (docs/contract/segments.md).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.layout_support import FakeWLED
from tests.state_catalog_support import make_info, make_segment, make_state
from tests.test_inventory_client import config
from wled_mcp import readmodels
from wled_mcp.capabilities import (
    CAP_CCT,
    CAP_RGB,
    CAP_WHITE,
    aggregate_cct,
    derive_capabilities,
    matrix_of,
    parse_matrix,
    required_color_channels,
    seglc_bits,
)
from wled_mcp.operations import GetStateRequest, build_operations
from wled_mcp.patches import PatchSegmentsRequest
from wled_mcp.readmodels import Collector, normalize_state
from wled_mcp.resources import Resources

RGB, RGBW, WHITE_ONLY = CAP_RGB, CAP_RGB | CAP_WHITE, CAP_WHITE
RGB_CCT, RGBW_CCT = CAP_RGB | CAP_CCT, CAP_RGB | CAP_WHITE | CAP_CCT


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def v16_segment(seg_id: int, start: int, stop: int, lc: Any, **overrides: Any) -> dict[str, Any]:
    return make_segment(seg_id, start, stop, lc=lc, **overrides)


def leds(**values: Any) -> dict[str, Any]:
    return make_info(leds={"count": 90, "maxseg": 32, **values})


def normalized(state: dict[str, Any], info: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    warnings = Collector()
    view, caps, _firmware, unknown = normalize_state(state, info, warnings)
    return {"view": view, "caps": caps, "unknown": unknown}, warnings.result()


# --- AC-19-01: per-segment evidence chain ---------------------------------------------


@pytest.mark.parametrize(
    ("lc", "channels", "flags"),
    [
        (RGB, 3, {"rgb": True, "white": False, "cct": False}),
        (RGBW, 4, {"rgb": True, "white": True, "cct": False}),
        (WHITE_ONLY, None, {"rgb": False, "white": True, "cct": False}),
        (CAP_CCT, None, {"rgb": False, "white": False, "cct": True}),
        (RGB_CCT, None, {"rgb": True, "white": False, "cct": True}),
        (CAP_WHITE | CAP_CCT, None, {"rgb": False, "white": True, "cct": True}),
        (RGBW_CCT, 4, {"rgb": True, "white": True, "cct": True}),
    ],
)
def test_state_lc_is_the_first_evidence_source(lc, channels, flags):
    # info.leds.seglc deliberately disagrees: the WLED 16 per-segment key wins.
    state = make_state([v16_segment(0, 0, 30, lc)])
    info = leds(lc=lc, seglc=[RGB if lc != RGB else RGBW])
    device = derive_capabilities(state, info)
    seg = device.segment(0)
    assert seg is not None and (seg.bits, seg.source) == (lc, "state_lc")
    assert required_color_channels(lc) == channels
    result, _warnings = normalized(state, info)
    view = result["view"]["segments"][0]
    assert view["reported_color_capability"] == flags
    assert view["color_capability_source"] == "state_lc"
    assert result["caps"]["segment_color_capability_reported"] is True


def test_0_15_shape_without_seg_lc_falls_back_to_aligned_seglc():
    """TD-21-7 explicit 0.15.1 case: no ``seg[].lc``, position-aligned ``seglc``."""
    state = make_state()  # three segments, no "lc" key
    info = make_info(ver="0.15.1", leds={"count": 90, "maxseg": 32, "lc": 3, "seglc": [1, 3, 1]})
    device = derive_capabilities(state, info)
    assert [(s.id, s.bits, s.source) for s in device.segments] == [
        (0, 1, "info_seglc"),
        (2, 3, "info_seglc"),
        (5, 1, "info_seglc"),
    ]
    result, warnings = normalized(state, info)
    sources = [s["color_capability_source"] for s in result["view"]["segments"]]
    assert sources == ["info_seglc"] * 3 and warnings == []


def test_mixed_sources_are_reported_per_segment():
    state = make_state([v16_segment(0, 0, 30, RGBW), make_segment(1, 30, 60)])
    device = derive_capabilities(state, leds(lc=3, seglc=[3, 1]))
    assert [(s.bits, s.source) for s in device.segments] == [(RGBW, "state_lc"), (1, "info_seglc")]


@pytest.mark.parametrize("bad", [True, "1", -1, 256, 1.0, [1]])
def test_malformed_seg_lc_is_ignored_with_a_warning(bad):
    state = make_state([v16_segment(0, 0, 30, bad)])
    with_seglc = derive_capabilities(state, leds(lc=1, seglc=[RGBW])).segment(0)
    assert with_seglc is not None and (with_seglc.bits, with_seglc.source) == (RGBW, "info_seglc")
    without = derive_capabilities(state, leds(lc=1)).segment(0)
    assert without is not None and (without.bits, without.source) == (None, None)
    result, warnings = normalized(state, leds(lc=1))
    view = result["view"]["segments"][0]
    assert view["reported_color_capability"] is None  # unknown never becomes false
    assert view["color_capability_source"] is None
    assert any("field 'lc'" in w for w in warnings)
    assert "segment_color_capability" in result["unknown"]


def test_no_per_segment_evidence_is_unknown_not_false():
    state = make_state()
    for info in (leds(lc=1), leds(lc=1, seglc=[1]), leds(lc=1, seglc=[1, "x", 1])):
        device = derive_capabilities(state, info)
        assert all(s.bits is None and s.source is None for s in device.segments)
        assert device.per_segment_reported is False
        result, _w = normalized(state, info)
        assert result["caps"]["segment_color_capability_reported"] is False
        assert "segment_color_capability" in result["unknown"]


def test_uniform_bits_need_every_segment_equal_to_the_aggregate():
    state = make_state([v16_segment(0, 0, 30, RGBW), v16_segment(1, 30, 60, RGBW)])
    assert derive_capabilities(state, leds(lc=RGBW)).uniform_bits == RGBW
    mixed = make_state([v16_segment(0, 0, 30, RGBW), v16_segment(1, 30, 60, RGB)])
    assert derive_capabilities(mixed, leds(lc=RGBW)).uniform_bits is None
    unknown = make_state([v16_segment(0, 0, 30, RGBW), make_segment(1, 30, 60)])
    assert derive_capabilities(unknown, leds(lc=RGBW)).uniform_bits is None
    assert derive_capabilities(state, leds(lc=True)).uniform_bits is None


def test_aggregate_cct_is_none_when_unreported():
    assert aggregate_cct(leds(lc=RGB_CCT)) is True
    assert aggregate_cct(leds(lc=RGB)) is False
    assert aggregate_cct(leds()) is None
    assert aggregate_cct(leds(lc=True)) is None


# --- AC-19-01: matrix -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ({"w": 16, "h": 8}, (16, 8)),
        ({"w": 0, "h": 8}, None),
        ({"w": 16}, None),
        ({"w": "16", "h": 8}, None),
        ({"w": True, "h": 8}, None),
        ({"w": 16, "h": 8, "x": 1}, None),
        ([16, 8], None),
    ],
)
def test_matrix_is_parsed_strictly(raw, expected):
    assert parse_matrix(raw) == expected
    info = leds(lc=1, matrix=raw)
    assert matrix_of(info) == expected
    result, warnings = normalized(make_state(), info)
    view = None if expected is None else {"width": expected[0], "height": expected[1]}
    assert result["caps"]["matrix"] == view
    assert any("leds.matrix" in w for w in warnings) is (expected is None)


def test_one_d_device_reports_no_matrix_without_a_warning():
    result, warnings = normalized(make_state(), leds(lc=1, seglc=[1, 1, 1]))
    assert result["caps"]["matrix"] is None and warnings == []
    assert "matrix" not in result["unknown"]  # absence on a 1D build is not an unknown


def test_bundle_module_uses_the_moved_parse_matrix():
    from wled_mcp import bundles

    assert bundles.parse_matrix is parse_matrix


# --- AC-19-02: new segment fields -----------------------------------------------------

V16_KEYS = {
    "cct": ("cct", 200),
    "custom1": ("c1", 10),
    "custom2": ("c2", 255),
    "custom3": ("c3", 31),
    "check1": ("o1", True),
    "check2": ("o2", False),
    "check3": ("o3", True),
    "sound_simulation": ("si", 2),
    "segment_set": ("set", 3),
    "map_1d_2d": ("m12", 4),
    "freeze": ("frz", True),
    "blend_mode": ("bm", 16),
    "start_y": ("startY", 2),
    "stop_y": ("stopY", 6),
    "reverse_y": ("rY", True),
    "mirror_y": ("mY", False),
    "transpose": ("tp", True),
}


def test_new_segment_fields_come_from_their_wire_keys():
    wire = {key: value for key, value in V16_KEYS.values()}
    result, warnings = normalized(make_state([v16_segment(0, 0, 8, RGB, **wire)]), leds(lc=1))
    view = result["view"]["segments"][0]
    assert {name: view[name] for name in V16_KEYS} == {
        name: value for name, (_key, value) in V16_KEYS.items()
    }
    assert warnings == []


def test_absent_new_fields_are_null():
    segment = make_segment(0, 0, 30)
    for key in ("cct", "frz"):
        segment.pop(key)
    result, warnings = normalized(make_state([segment]), leds(lc=1, seglc=[1]))
    view = result["view"]["segments"][0]
    assert all(view[name] is None for name in V16_KEYS) and warnings == []


@pytest.mark.parametrize(
    ("name", "bad"),
    [
        ("cct", 256),
        ("cct", True),
        ("custom1", -1),
        ("custom3", 32),
        ("check1", 1),
        ("freeze", "yes"),
        ("sound_simulation", 1.5),
        ("blend_mode", 256),
        ("start_y", -1),
        ("transpose", 0),
    ],
)
def test_malformed_new_field_is_null_with_a_warning(name, bad):
    key = V16_KEYS[name][0]
    result, warnings = normalized(make_state([v16_segment(0, 0, 8, RGB, **{key: bad})]), leds(lc=1))
    assert result["view"]["segments"][0][name] is None
    assert len(warnings) == 1 and warnings[0].startswith(
        f"Segment 0: field '{key}' has an unexpected"
    )
    assert warnings[0].endswith("reported as null.")


def test_new_fields_are_additive_to_the_stage_1_segment_view():
    result, _w = normalized(make_state(), leds(lc=3, seglc=[1, 3, 1]))
    keys = list(result["view"]["segments"][0])
    stage1 = keys[: keys.index("name") + 1]
    assert stage1[-1] == "name" and keys[len(stage1) :] == [
        "color_capability_source",
        *V16_KEYS,
    ]


def test_state_example_matches_the_read_model():
    """examples/contracts/state.json is the read model's output for its raw payloads."""
    path = Path(__file__).resolve().parents[1] / "examples/contracts/state.json"
    data = json.loads(path.read_text(encoding="utf-8"))["cases"]["state"]["expected"]["data"]
    result, warnings = normalized(data["raw"]["state"], data["raw"]["info"])
    assert result["view"] == data["state"] and result["caps"] == data["capabilities"]
    assert warnings == [] and result["unknown"] == data["diagnostics"]["unknown_capabilities"]


def test_cap_constants_stay_importable_from_readmodels():
    assert (readmodels.CAP_RGB, readmodels.CAP_WHITE, readmodels.CAP_CCT) == (1, 2, 4)


# --- wled_get_state over the WLED 16 fake ---------------------------------------------


def open_resources(tmp_path, fake):
    return Resources(config(tmp_path), fake.transport(), None)


async def get_state(resources) -> Any:
    operation = {o.name: o for o in build_operations(resources)}["wled_get_state"]
    request = GetStateRequest.model_validate({"device_id": "desk"}).model_dump()
    return await operation.execute(request)


def matrix_fake(**kwargs: Any) -> FakeWLED:
    """16x8 matrix plus an 8-LED trailing strip; RGBW panel, RGB+CCT strip."""
    kwargs.setdefault("buses", [(0, 128, RGBW), (128, 136, RGB_CCT)])
    return FakeWLED(
        [
            make_segment(0, 0, 16, startY=0, stopY=4),
            make_segment(1, 0, 16, startY=4, stopY=8, c1=40, bm=3),
            make_segment(2, 128, 136, startY=0, stopY=1),
        ],
        led_count=136,
        v16=True,
        matrix=(16, 8),
        **kwargs,
    )


@pytest.mark.anyio
async def test_get_state_reports_v16_matrix_fields(tmp_path):
    fake = matrix_fake()
    async with open_resources(tmp_path, fake) as resources:
        result = await get_state(resources)
    assert result.ok and result.warnings == []
    data = result.data
    assert data["capabilities"]["matrix"] == {"width": 16, "height": 8}
    assert data["capabilities"]["device_wide_color"]["cct"] is True
    by_id = {s["id"]: s for s in data["state"]["segments"]}
    assert by_id[0]["reported_color_capability"] == {"rgb": True, "white": True, "cct": False}
    assert by_id[2]["reported_color_capability"] == {"rgb": True, "white": False, "cct": True}
    assert {s["color_capability_source"] for s in by_id.values()} == {"state_lc"}
    assert (by_id[1]["start_y"], by_id[1]["stop_y"]) == (4, 8)
    assert (by_id[1]["custom1"], by_id[1]["custom2"], by_id[1]["custom3"]) == (40, 128, 16)
    assert by_id[1]["blend_mode"] == 3 and by_id[0]["transpose"] is False
    assert fake.method_count("POST") == 0


@pytest.mark.anyio
async def test_get_state_on_a_1d_v16_device_has_no_2d_fields(tmp_path):
    fake = FakeWLED([make_segment(0, 0, 30)], led_count=30, v16=True, buses=[(0, 30, RGBW)])
    async with open_resources(tmp_path, fake) as resources:
        result = await get_state(resources)
    seg = result.data["state"]["segments"][0]
    assert result.data["capabilities"]["matrix"] is None
    assert (seg["start_y"], seg["reverse_y"], seg["transpose"]) == (None, None, None)
    assert (seg["sound_simulation"], seg["map_1d_2d"], seg["check1"]) == (0, 0, False)
    assert seg["color_capability_source"] == "state_lc"
    assert seg["reported_color_capability"]["white"] is True


# --- AC-19-03: PR A boundary, write side unchanged ------------------------------------


def test_write_side_lookup_still_uses_info_seglc_only():
    """``seglc_bits`` keeps ISSUE-6-DEC-003; the #19 chain reaches writes in PR B."""
    segments = [v16_segment(0, 0, 30, RGBW)]
    assert seglc_bits(leds(lc=3), 0, segments) is None
    assert seglc_bits(leds(lc=3, seglc=[1]), 0, segments) == 1
    assert seglc_bits(leds(lc=3, seglc=[1, 1]), 0, segments) is None


@pytest.mark.anyio
async def test_patch_colors_without_seglc_still_refused_despite_seg_lc(tmp_path):
    fake = FakeWLED([make_segment(0, 0, 30)], led_count=30, v16=True, seglc=None)
    async with open_resources(tmp_path, fake) as resources:
        operation = {o.name: o for o in build_operations(resources)}["wled_patch_segments"]
        request = PatchSegmentsRequest.model_validate(
            {
                "device_id": "desk",
                "segments": [{"id": 0, "start": 0, "stop": 20, "colors": [[1, 2, 3]]}],
            }
        ).model_dump()
        result = await operation.execute(request)
    assert result.error is not None and result.error.code == "UNSUPPORTED_CAPABILITY"
    assert fake.method_count("POST") == 0


# --- FakeWLED v16 model (used by PR B) -------------------------------------------------


def test_fake_default_keeps_the_stage_1_shape():
    fake = FakeWLED([make_segment(0, 0, 30)], led_count=30)
    seg = fake.state()["seg"][0]
    assert not {"lc", "c1", "startY", "rY", "bm"} & set(seg)
    assert "matrix" not in fake.info()["leds"]


def test_fake_matrix_keeps_omitted_y_and_clamps_to_the_matrix():
    fake = matrix_fake()
    fake.apply({"seg": {"id": 0, "start": 2, "stop": 40}})  # Y omitted, X beyond width
    seg = fake.slots[0]
    assert (seg["start"], seg["stop"], seg["startY"], seg["stopY"]) == (2, 16, 0, 4)
    assert seg["n"] == ""  # geometry change clears the name unless n is sent
    fake.apply({"seg": {"id": 0, "startY": 9, "stopY": 99, "n": "Kept"}})
    assert (seg["startY"], seg["stopY"], seg["n"]) == (0, 8, "Kept")


def test_fake_matrix_trailing_strip_and_capability_recompute():
    fake = matrix_fake()
    lc = {s["id"]: s["lc"] for s in fake.state()["seg"]}
    assert lc == {0: RGBW, 1: RGBW, 2: RGB_CCT}
    assert fake.info()["leds"]["seglc"] == [RGBW, RGBW, RGB_CCT]
    fake.apply({"seg": {"id": 2, "start": 130, "stop": 999}})
    assert (fake.slots[2]["start"], fake.slots[2]["stop"]) == (130, 136)
    # start beyond the strip is ignored; the old start stays
    fake.apply({"seg": {"id": 2, "start": 200, "stop": 210}})
    assert fake.slots[2]["start"] == 130
    # A moved panel segment that now covers no CCT pixels drops the CCT bit device-wide.
    fake.apply({"seg": {"id": 2, "start": 0, "stop": 4, "startY": 0, "stopY": 1}})
    assert fake.state()["seg"][2]["lc"] == RGBW
    assert fake.info()["leds"]["lc"] == RGBW


def test_fake_v16_applies_option_keys_with_firmware_clamps():
    fake = FakeWLED([make_segment(0, 0, 30)], led_count=30, v16=True)
    fake.apply({"seg": {"id": 0, "c3": 99, "m12": 9, "si": 2, "bm": 5, "cct": 10, "rY": True}})
    seg = fake.state()["seg"][0]
    assert (seg["c3"], seg["m12"], seg["si"], seg["bm"], seg["cct"]) == (31, 7, 2, 5, 10)
    assert "rY" not in seg  # orientation keys exist only on a matrix
