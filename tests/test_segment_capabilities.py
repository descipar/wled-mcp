"""Issue #19: capability model, read side (PR A, AC-19-01..03) and segment writes (PR B,
AC-19-04..17) under ISSUE-19-DEC-001..003.

Pure-function tests for ``wled_mcp.capabilities`` plus ``wled_get_state`` over the
stateful fake in ``tests/layout_support.py`` (mock transport only, no LAN). The WLED 16
shapes follow the v16.0.1 source pin 29b389d (docs/contract/segments.md).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from tests.layout_support import V16_DEFAULTS, FakeWLED
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
from wled_mcp.layouts import ReplaceLayoutRequest
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


def test_partial_per_segment_evidence_is_not_reported_as_complete():
    """One segment with ``lc`` and one without (no ``seglc``): evidence is incomplete."""
    state = make_state([v16_segment(0, 0, 30, RGB), make_segment(1, 30, 60)])
    device = derive_capabilities(state, leds(lc=1))
    assert [s.bits for s in device.segments] == [RGB, None]
    assert device.per_segment_reported is False
    result, _w = normalized(state, leds(lc=1))
    assert result["caps"]["segment_color_capability_reported"] is False
    assert "segment_color_capability" in result["unknown"]


@pytest.mark.parametrize("bad", [True, 256, -1])
def test_aligned_seglc_uses_the_state_lc_value_range(bad):
    """``info.leds.seglc`` entries are uint8_t bitfields like ``seg[].lc`` (0-255, no bool)."""
    state = make_state([make_segment(0, 0, 30), make_segment(1, 30, 60)])
    device = derive_capabilities(state, leds(lc=1, seglc=[1, bad]))
    assert [(s.bits, s.source) for s in device.segments] == [(None, None), (None, None)]


def test_uniform_bits_need_every_segment_equal_to_the_aggregate():
    state = make_state([v16_segment(0, 0, 30, RGBW), v16_segment(1, 30, 60, RGBW)])
    assert derive_capabilities(state, leds(lc=RGBW)).uniform_bits == RGBW
    mixed = make_state([v16_segment(0, 0, 30, RGBW), v16_segment(1, 30, 60, RGB)])
    assert derive_capabilities(mixed, leds(lc=RGBW)).uniform_bits is None
    unknown = make_state([v16_segment(0, 0, 30, RGBW), make_segment(1, 30, 60)])
    assert derive_capabilities(unknown, leds(lc=RGBW)).uniform_bits is None
    assert derive_capabilities(state, leds(lc=True)).uniform_bits is None
    # An empty segment list is no evidence for a new range (no vacuous ``all``).
    empty = derive_capabilities(make_state([]), leds(lc=RGBW, seglc=[]))
    assert empty.uniform_bits is None and empty.per_segment_reported is True


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


def test_color_trimming_keeps_the_stage_1_seglc_path_not_the_state_lc_chain():
    """A zero fourth channel is trimmed only on ``info.leds.seglc`` RGB-only evidence."""
    col = [[1, 2, 3, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
    # seg[].lc says RGBW, aligned seglc says RGB-only: trimmed (seglc path).
    state = make_state([v16_segment(0, 0, 30, RGBW, col=col)])
    trimmed, _w = normalized(state, leds(lc=3, seglc=[1]))
    seg = trimmed["view"]["segments"][0]
    assert seg["color_channels"] == 3 and seg["colors"][0] == [1, 2, 3]
    assert seg["reported_color_capability"]["white"] is True  # the chain reports RGBW
    # seg[].lc says RGB-only, no seglc: not trimmed (the chain is not used for trimming).
    kept, _w = normalized(make_state([v16_segment(0, 0, 30, RGB, col=col)]), leds(lc=1))
    seg = kept["view"]["segments"][0]
    assert seg["color_channels"] == 4 and seg["colors"][0] == [1, 2, 3, 0]


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


def open_resources(tmp_path, fake, **settings):
    return Resources(config(tmp_path, **settings), fake.transport(), None)


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


# --- AC-19-03 and the PR B switch of the write-side lookup ---------------------------


def test_stage_1_seglc_lookup_is_kept_for_reference():
    """``seglc_bits`` keeps ISSUE-6-DEC-003; since PR B the planners use the #19 chain."""
    segments = [v16_segment(0, 0, 30, RGBW)]
    assert seglc_bits(leds(lc=3), 0, segments) is None
    assert seglc_bits(leds(lc=3, seglc=[1]), 0, segments) == 1
    assert seglc_bits(leds(lc=3, seglc=[1, 1]), 0, segments) is None
    assert seglc_bits(leds(lc=3, seglc=[True]), 0, segments) is None  # bool rejected


@pytest.mark.anyio
@pytest.mark.parametrize("tool", ["wled_patch_segments", "wled_replace_layout"])
async def test_write_side_uses_the_seg_lc_chain_without_seglc(tmp_path, tool):
    """PR B switch (recorded in docs/contract/segments.md): ``seg[].lc`` alone is now
    per-segment evidence for both write tools. These cases were refused before the switch
    (the PR A pins ``test_*_colors_without_seglc_still_refused_despite_seg_lc``)."""
    fake = FakeWLED([make_segment(0, 0, 30)], led_count=30, v16=True, seglc=None)
    async with open_resources(tmp_path, fake) as resources:
        operation = {o.name: o for o in build_operations(resources)}[tool]
        model = PatchSegmentsRequest if tool == "wled_patch_segments" else ReplaceLayoutRequest
        request = model.model_validate(
            {
                "device_id": "desk",
                "segments": [{"id": 0, "start": 0, "stop": 20, "colors": [[1, 2, 3]]}],
            }
        ).model_dump()
        result = await operation.execute(request)
    assert result.ok, result.error
    assert (result.application, result.verification) == ("applied", "verified")
    assert fake.slots[0]["col"][0] == [1, 2, 3, 0] and fake.slots[0]["stop"] == 20


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


def test_fake_matrix_name_follows_the_requested_x_bounds_before_clamping():
    """json.cpp L144-151: the name is cleared when the requested start/stop differ from
    the current ones before ``setGeometry`` clamps them; a Y-only change keeps it."""
    fake = matrix_fake()
    seg = fake.slots[0]
    fake.apply({"seg": {"id": 0, "startY": 1, "stopY": 3}})
    assert (seg["startY"], seg["stopY"], seg["n"]) == (1, 3, "Segment 0")
    fake.apply({"seg": {"id": 0, "start": 0, "stop": 40}})  # clamps back to (0, 16)
    assert (seg["start"], seg["stop"], seg["n"]) == (0, 16, "")
    one_d = FakeWLED([make_segment(0, 0, 30)], led_count=30, v16=True)
    one_d.apply({"seg": {"id": 0, "start": 0, "stop": 30, "bri": 9}})
    assert one_d.slots[0]["n"] == "Segment 0"  # same bounds requested: name kept


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


def test_fake_trailing_strip_rows_follow_start_y_and_stop_y():
    """``refreshLightCapabilities`` walks rows startY..stopY at ``x + width * y`` for a
    trailing strip too: row 1 of the strip indexes past every bus, so no capability."""
    fake = matrix_fake()
    assert fake.state()["seg"][2]["lc"] == RGB_CCT
    fake.apply({"seg": {"id": 2, "startY": 1, "stopY": 2}})
    assert (fake.slots[2]["startY"], fake.slots[2]["stopY"]) == (1, 2)
    assert fake.state()["seg"][2]["lc"] == 0


def test_fake_v16_applies_option_keys_with_firmware_clamps():
    fake = FakeWLED([make_segment(0, 0, 30)], led_count=30, v16=True)
    fake.apply({"seg": {"id": 0, "c3": 99, "m12": 9, "si": 2, "bm": 5, "cct": 10, "rY": True}})
    seg = fake.state()["seg"][0]
    assert (seg["c3"], seg["m12"], seg["si"], seg["bm"], seg["cct"]) == (31, 7, 2, 5, 10)
    assert "rY" not in seg  # orientation keys exist only on a matrix
    fake.apply({"seg": {"id": 0, "si": 9, "set": 7}})  # json.cpp L277-278
    seg = fake.state()["seg"][0]
    assert (seg["si"], seg["set"]) == (3, 3)


# ======================================================================================
# PR B: segment writes (AC-19-04 .. AC-19-17). Mock transport and tmp_path only.
# ======================================================================================

MIXED = [(0, 15, RGB), (15, 30, RGB_CCT)]  # seg 0 RGB-only, seg 1 RGB+CCT, lc 5
UNIFORM_CCT = [(0, 30, RGBW_CCT)]
UNIFORM_RGBW = [(0, 30, RGBW)]
OPTIONS = {
    "custom1": ("c1", 10),
    "custom2": ("c2", 20),
    "custom3": ("c3", 31),
    "check1": ("o1", True),
    "check2": ("o2", True),
    "check3": ("o3", True),
    "sound_simulation": ("si", 3),
    "segment_set": ("set", 2),
    "map_1d_2d": ("m12", 4),
    "freeze": ("frz", True),
    "blend_mode": ("bm", 16),
}
MODELS = {"wled_patch_segments": PatchSegmentsRequest, "wled_replace_layout": ReplaceLayoutRequest}


def v16_fake(buses=None, segments=None, **kwargs: Any) -> FakeWLED:
    """A 30-LED WLED 16 strip; by default segments 0 [0,15) and 1 [15,30)."""
    if segments is None:
        segments = [make_segment(0, 0, 15), make_segment(1, 15, 30)]
    return FakeWLED(segments, led_count=30, v16=True, buses=buses, **kwargs)


def stage1_fake(**kwargs: Any) -> FakeWLED:
    """The stage-1 shape (no ``seg[].lc`` and no WLED 16 option keys)."""
    return FakeWLED([make_segment(0, 0, 15), make_segment(1, 15, 30)], led_count=30, **kwargs)


async def call(resources, tool: str, **arguments: Any) -> Any:
    arguments.setdefault("device_id", "desk")
    operation = {o.name: o for o in build_operations(resources)}[tool]
    return await operation.execute(MODELS[tool].model_validate(arguments).model_dump())


async def patch(resources, segments, **arguments: Any) -> Any:
    return await call(resources, "wled_patch_segments", segments=segments, **arguments)


async def replace(resources, segments, **arguments: Any) -> Any:
    return await call(resources, "wled_replace_layout", segments=segments, **arguments)


def files(tmp_path) -> list[str]:
    return sorted(str(p.relative_to(tmp_path)) for p in Path(tmp_path).rglob("*"))


def refused(result: Any, code: str) -> None:
    assert result.error is not None and result.error.code == code, result.error
    assert (result.application, result.verification) == ("not_attempted", "not_requested")


# --- AC-19-04 / AC-19-05: CCT ---------------------------------------------------------


@pytest.mark.anyio
async def test_cct_patch_on_a_cct_segment_is_verified_and_the_dry_run_is_identical(tmp_path):
    fake = v16_fake(MIXED)
    before = files(tmp_path)
    async with open_resources(tmp_path, fake) as resources:
        dry = await patch(resources, [{"id": 1, "cct": 200}], dry_run=True)
        assert fake.method_count("POST") == 0 and files(tmp_path) == before
        live = await patch(resources, [{"id": 1, "cct": 200}])
    assert dry.ok and dry.data["payload"] == {"seg": [{"id": 1, "cct": 200}]}
    evidence = [{"id": 1, "field": "cct", "evidence": "state_lc"}]
    assert dry.data["plan"]["capability_evidence"] == evidence
    assert live.ok and (live.application, live.verification) == ("applied", "verified")
    assert fake.posts == [dry.data["payload"]]
    assert fake.slots[1]["cct"] == 200 and fake.slots[0]["cct"] == 127
    assert live.data["plan"] == dry.data["plan"]


def _aggregate_only(**kwargs: Any) -> FakeWLED:
    return stage1_fake(lc=RGB_CCT, seglc=None, **kwargs)


@pytest.mark.anyio
@pytest.mark.parametrize("dry_run", [True, False], ids=["dry", "live"])
@pytest.mark.parametrize(
    ("factory", "segments"),
    [
        pytest.param(lambda: v16_fake(MIXED), [{"id": 0, "cct": 10}], id="rgb-only-segment"),
        pytest.param(
            lambda: v16_fake(MIXED),
            [{"id": 1, "cct": 10}, {"id": 0, "cct": 10}],
            id="whole-request-refused",
        ),
        pytest.param(_aggregate_only, [{"id": 0, "cct": 10}], id="aggregate-cct-only"),
        pytest.param(
            lambda: stage1_fake(lc=RGB_CCT, seglc=[RGB_CCT]),
            [{"id": 0, "cct": 10}],
            id="misaligned-seglc",
        ),
        pytest.param(
            lambda: v16_fake(MIXED),
            [{"id": 1, "start": 15, "stop": 25, "cct": 10}],
            id="moved-range-without-uniform-evidence",
        ),
    ],
)
async def test_cct_without_evidence_is_unsupported_before_any_post(
    tmp_path, factory, segments, dry_run
):
    fake = factory()
    async with open_resources(tmp_path, fake) as resources:
        result = await patch(resources, segments, dry_run=dry_run)
    refused(result, "UNSUPPORTED_CAPABILITY")
    assert fake.method_count("POST") == 0


@pytest.mark.anyio
async def test_cct_on_a_moved_range_uses_the_uniform_rule(tmp_path):
    fake = v16_fake(UNIFORM_CCT)
    async with open_resources(tmp_path, fake) as resources:
        result = await patch(resources, [{"id": 1, "start": 15, "stop": 25, "cct": 0}])
    assert result.ok, result.error
    assert result.data["plan"]["capability_evidence"] == [
        {"id": 1, "field": "cct", "evidence": "uniform"}
    ]
    assert (fake.slots[1]["stop"], fake.slots[1]["cct"]) == (25, 0)


@pytest.mark.anyio
async def test_cct_on_0_15_shaped_info_uses_aligned_seglc_without_a_version_gate(tmp_path):
    """AC-19-17: firmware below 16.0.0 is not refused by version; evidence decides."""
    fake = FakeWLED(
        [make_segment(0, 0, 15), make_segment(1, 15, 30)], led_count=30, buses=UNIFORM_CCT
    )
    original = fake.info
    fake.info = lambda: {**original(), "ver": "0.15.1"}  # type: ignore[method-assign]
    async with open_resources(tmp_path, fake) as resources:
        result = await patch(resources, [{"id": 0, "cct": 33}])
    assert result.ok, result.error
    assert result.data["plan"]["capability_evidence"][0]["evidence"] == "info_seglc"
    assert fake.slots[0]["cct"] == 33


def test_no_issue_19_rule_reads_the_firmware_tier():
    """AC-19-17 / TD-21-6: the #19 rules never consult ``compat.py``."""
    from wled_mcp import capabilities, layouts, patches, preset_writes, segment_rules

    for module in (capabilities, segment_rules, patches, layouts, preset_writes):
        source = Path(module.__file__ or "").read_text(encoding="utf-8")
        assert "wled_mcp.compat" not in source, module.__name__
        assert "import compat" not in source, module.__name__
        assert "firmware_support" not in source, module.__name__


# --- AC-19-06: white handling ----------------------------------------------------------


@pytest.mark.anyio
async def test_white_only_range_takes_four_channels_with_rgb_zero(tmp_path):
    fake = v16_fake([(0, 30, WHITE_ONLY)])
    async with open_resources(tmp_path, fake) as resources:
        ok = await patch(resources, [{"id": 0, "colors": [[0, 0, 0, 200]]}])
        rgb = await patch(resources, [{"id": 0, "colors": [[1, 0, 0, 200]]}], dry_run=True)
        three = await patch(resources, [{"id": 0, "colors": [[0, 0, 200]]}], dry_run=True)
    assert ok.ok and ok.verification == "verified", ok.error
    assert fake.slots[0]["col"][0] == [0, 0, 0, 200]
    refused(rgb, "VALIDATION_ERROR")
    assert "white-only" in rgb.error.message
    refused(three, "VALIDATION_ERROR")
    assert len(fake.posts) == 1  # never padded or trimmed


@pytest.mark.anyio
async def test_rgb_cct_range_takes_three_channels(tmp_path):
    fake = v16_fake(MIXED)
    async with open_resources(tmp_path, fake) as resources:
        three = await patch(resources, [{"id": 1, "colors": [[9, 8, 7]]}])
        four = await patch(resources, [{"id": 1, "colors": [[9, 8, 7, 6]]}], dry_run=True)
    assert three.ok and fake.slots[1]["col"][0][:3] == [9, 8, 7]
    refused(four, "VALIDATION_ERROR")


@pytest.mark.anyio
async def test_moved_range_takes_four_channels_only_under_the_uniform_rule(tmp_path):
    fake = v16_fake(UNIFORM_RGBW)
    async with open_resources(tmp_path, fake) as resources:
        four = await patch(resources, [{"id": 0, "start": 0, "stop": 10, "colors": [[1, 2, 3, 4]]}])
        three = await patch(
            resources, [{"id": 0, "start": 0, "stop": 12, "colors": [[1, 2, 3]]}], dry_run=True
        )
    assert four.ok and four.verification == "verified", four.error
    assert fake.slots[0]["col"][0] == [1, 2, 3, 4]
    refused(three, "VALIDATION_ERROR")
    mixed = v16_fake([(0, 15, RGB), (15, 30, RGBW)])
    async with open_resources(tmp_path, mixed) as resources:
        result = await patch(
            resources, [{"id": 1, "start": 15, "stop": 25, "colors": [[1, 2, 3, 4]]}]
        )
    refused(result, "UNSUPPORTED_CAPABILITY")
    assert mixed.method_count("POST") == 0


@pytest.mark.anyio
async def test_new_range_with_four_channels_on_a_uniform_rgbw_device_is_verified(tmp_path):
    fake = v16_fake(UNIFORM_RGBW, segments=[make_segment(0, 0, 15)])
    desired = [
        {"id": 0, "start": 0, "stop": 15},
        {"id": 1, "start": 15, "stop": 30, "colors": [[1, 2, 3, 4]]},
    ]
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(resources, desired)
    assert result.ok and result.verification == "verified", result.error
    assert fake.slots[1]["col"][0] == [1, 2, 3, 4]


# --- AC-19-07 / AC-19-08 / AC-19-09: 2D bounds, matrix gap, orientation --------------


@pytest.mark.anyio
async def test_matrix_x_patch_keeps_rows_and_resends_the_name(tmp_path):
    fake = matrix_fake()
    async with open_resources(tmp_path, fake) as resources:
        result = await patch(resources, [{"id": 0, "start": 2, "stop": 10}])
    assert result.ok and result.verification == "verified", result.error
    assert fake.posts == [{"seg": [{"id": 0, "start": 2, "stop": 10, "n": "Segment 0"}]}]
    seg = fake.slots[0]
    assert (seg["start"], seg["stop"], seg["startY"], seg["stopY"]) == (2, 10, 0, 4)
    assert seg["n"] == "Segment 0"


@pytest.mark.anyio
async def test_matrix_rows_only_patch_sends_no_name(tmp_path):
    fake = matrix_fake()
    async with open_resources(tmp_path, fake) as resources:
        result = await patch(resources, [{"id": 0, "start_y": 0, "stop_y": 2}])
    assert result.ok and result.verification == "verified", result.error
    assert fake.posts == [{"seg": [{"id": 0, "startY": 0, "stopY": 2}]}]
    assert (fake.slots[0]["startY"], fake.slots[0]["stopY"], fake.slots[0]["n"]) == (
        0,
        2,
        "Segment 0",
    )
    assert result.data["plan"]["capability_evidence"] == [
        {"id": 0, "field": "start_y", "evidence": "matrix"},
        {"id": 0, "field": "stop_y", "evidence": "matrix"},
    ]


@pytest.mark.anyio
@pytest.mark.parametrize("dry_run", [True, False], ids=["dry", "live"])
@pytest.mark.parametrize(
    ("segments", "code", "fragment"),
    [
        # AC-19-08: stop > width but <= led_count was a late mismatch in stage 1.
        ([{"id": 0, "start": 0, "stop": 20}], "VALIDATION_ERROR", "width (16)"),
        ([{"id": 0, "start_y": 0, "stop_y": 9}], "VALIDATION_ERROR", "height (8)"),
        ([{"id": 0, "start_y": 1}], "VALIDATION_ERROR", "both start_y and stop_y"),
        ([{"id": 0, "start_y": 3, "stop_y": 3}], "VALIDATION_ERROR", "start_y"),
        ([{"id": 1, "start_y": 3, "stop_y": 8}], "VALIDATION_ERROR", "allow_overlap"),
        ([{"id": 2, "start": 129, "stop": 136}], "UNSUPPORTED_CAPABILITY", "trailing"),
        ([{"id": 2, "start_y": 0, "stop_y": 2}], "UNSUPPORTED_CAPABILITY", "trailing"),
        ([{"id": 0, "start": 128, "stop": 130}], "UNSUPPORTED_CAPABILITY", "trailing"),
    ],
)
async def test_matrix_patch_bounds_are_refused_before_any_post(
    tmp_path, segments, code, fragment, dry_run
):
    fake = matrix_fake()
    async with open_resources(tmp_path, fake) as resources:
        result = await patch(resources, segments, dry_run=dry_run)
    refused(result, code)
    assert fragment in result.error.message
    assert fake.method_count("POST") == 0


@pytest.mark.anyio
@pytest.mark.parametrize("tool", list(MODELS))
@pytest.mark.parametrize(
    "fields",
    [{"start_y": 0, "stop_y": 1}, {"reverse_y": True}, {"mirror_y": False}, {"transpose": True}],
)
async def test_2d_fields_on_a_1d_device_are_unsupported(tmp_path, tool, fields):
    fake = v16_fake()
    segment = {"id": 0, **fields}
    if tool == "wled_replace_layout":
        segment.update(start=0, stop=15)
    async with open_resources(tmp_path, fake) as resources:
        result = await call(resources, tool, segments=[segment])
    refused(result, "UNSUPPORTED_CAPABILITY")
    assert "matrix" in result.error.message and fake.method_count("POST") == 0


@pytest.mark.anyio
async def test_matrix_orientation_patch_is_verified(tmp_path):
    fake = matrix_fake()
    async with open_resources(tmp_path, fake) as resources:
        result = await patch(resources, [{"id": 0, "reverse_y": True, "transpose": True}])
    assert result.ok and result.verification == "verified", result.error
    assert fake.posts == [{"seg": [{"id": 0, "rY": True, "tp": True}]}]
    assert (fake.slots[0]["rY"], fake.slots[0]["mY"], fake.slots[0]["tp"]) == (True, False, True)


@pytest.mark.anyio
async def test_matrix_replace_uses_rectangles_and_preserves_the_trailing_strip(tmp_path):
    fake = matrix_fake()
    desired = [
        {"id": 0, "start": 0, "stop": 8, "start_y": 0, "stop_y": 4},
        {"id": 1, "start": 8, "stop": 16, "start_y": 0, "stop_y": 8},
        {"id": 2, "start": 128, "stop": 136},
    ]
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(resources, desired)
    assert result.ok and result.verification == "verified", (result.error, result.data)
    rows = {s["id"]: (s["start"], s["stop"], s["startY"], s["stopY"]) for s in fake.active()}
    assert rows == {0: (0, 8, 0, 4), 1: (8, 16, 0, 8), 2: (128, 136, 0, 1)}
    assert fake.posts == [
        {"seg": {"id": 0, "start": 0, "stop": 8, "n": "Segment 0"}},
        {"seg": {"id": 1, "start": 8, "stop": 16, "startY": 0, "stopY": 8, "n": "Segment 1"}},
    ]
    assert "Move ID 1 to [8,16) rows [0,8)" in result.data["plan"]["steps"][1]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("segments", "code", "fragment"),
    [
        (
            [{"id": 0, "start": 0, "stop": 16, "start_y": 0, "stop_y": 5}],
            "VALIDATION_ERROR",
            "allow_overlap",
        ),
        (
            [{"id": 3, "start": 0, "stop": 4, "colors": [[1, 2, 3, 4]]}],
            "VALIDATION_ERROR",
            "start_y and stop_y",
        ),
        (
            [{"id": 3, "start": 130, "stop": 136, "colors": [[1, 2, 3, 4]]}],
            "UNSUPPORTED_CAPABILITY",
            "trailing",
        ),
        ([{"id": 2, "start": 129, "stop": 136}], "UNSUPPORTED_CAPABILITY", "trailing"),
        ([{"id": 0, "start": 0, "stop": 17, "start_y": 0, "stop_y": 4}], "VALIDATION_ERROR", "16"),
    ],
)
async def test_matrix_replace_refusals_send_nothing(tmp_path, segments, code, fragment):
    fake = matrix_fake()
    base = [
        {"id": 0, "start": 0, "stop": 16},
        {"id": 1, "start": 0, "stop": 16},
        {"id": 2, "start": 128, "stop": 136},
    ]
    by_id = {s["id"]: s for s in base} | {s["id"]: s for s in segments}
    async with open_resources(tmp_path, fake) as resources:
        dry = await replace(resources, list(by_id.values()), dry_run=True)
        live = await replace(resources, list(by_id.values()))
    for result in (dry, live):
        refused(result, code)
        assert fragment in result.error.message
    assert fake.method_count("POST") == 0


# --- AC-19-10: options with field-presence evidence ------------------------------------


@pytest.mark.anyio
async def test_every_option_is_sent_and_verified_where_the_readback_carries_it(tmp_path):
    fake = v16_fake()
    fields = {name: value for name, (_wire, value) in OPTIONS.items()}
    async with open_resources(tmp_path, fake) as resources:
        result = await patch(resources, [{"id": 0, **fields}])
    assert result.ok and result.verification == "verified", result.error
    sent = fake.posts[0]["seg"][0]
    assert sent == {"id": 0, **{wire: value for wire, value in OPTIONS.values()}}
    assert {e["field"]: e["evidence"] for e in result.data["plan"]["capability_evidence"]} == {
        name: "field_present" for name in OPTIONS
    }
    assert any(w.startswith("freeze:") for w in result.warnings)  # TD-19-8
    assert all(fake.slots[0][wire] == value for wire, value in OPTIONS.values())


@pytest.mark.anyio
@pytest.mark.parametrize("tool", list(MODELS))
@pytest.mark.parametrize("name", [n for n in OPTIONS if n != "freeze"])
async def test_option_without_its_wire_key_is_unsupported(tmp_path, tool, name):
    fake = stage1_fake()
    segment: dict[str, Any] = {"id": 0, name: OPTIONS[name][1]}
    desired = [segment]
    if tool == "wled_replace_layout":
        segment.update(start=0, stop=15)
        desired.append({"id": 1, "start": 15, "stop": 30})
    async with open_resources(tmp_path, fake) as resources:
        dry = await call(resources, tool, segments=desired, dry_run=True)
        live = await call(resources, tool, segments=desired)
    for result in (dry, live):
        refused(result, "UNSUPPORTED_CAPABILITY")
        assert f"'{OPTIONS[name][0]}'" in result.error.message
    assert fake.method_count("POST") == 0


@pytest.mark.anyio
async def test_freeze_needs_the_frz_key_too(tmp_path):
    fake = stage1_fake()
    del fake.slots[0]["frz"]
    async with open_resources(tmp_path, fake) as resources:
        result = await patch(resources, [{"id": 0, "freeze": True}])
        other = await patch(resources, [{"id": 1, "freeze": False}])
    refused(result, "UNSUPPORTED_CAPABILITY")
    assert other.ok and fake.posts == [{"seg": [{"id": 1, "frz": False}]}]


@pytest.mark.parametrize("model", [PatchSegmentsRequest, ReplaceLayoutRequest])
@pytest.mark.parametrize(
    ("name", "bad"),
    [
        ("cct", 256),
        ("custom1", 256),
        ("custom2", -1),
        ("custom3", 32),
        ("sound_simulation", 4),
        ("segment_set", 4),
        ("map_1d_2d", 5),
        ("blend_mode", 17),
        ("check1", 1),
        ("freeze", "yes"),
        ("start_y", -1),
        ("stop_y", 0),
        ("transpose", 0),
    ],
)
def test_option_bounds_are_schema_errors(model, name, bad):
    segment = {"id": 0, "start": 0, "stop": 10, name: bad}
    with pytest.raises(ValidationError):
        model.model_validate({"device_id": "desk", "segments": [segment]})


@pytest.mark.anyio
async def test_new_id_option_needs_the_key_on_every_active_segment(tmp_path):
    fake = v16_fake()
    del fake.slots[1]["c1"]
    keep = [{"id": 0, "start": 0, "stop": 10}, {"id": 1, "start": 15, "stop": 30}]
    new = {"id": 2, "start": 10, "stop": 15, "colors": [[1, 2, 3]]}
    async with open_resources(tmp_path, fake) as resources:
        with_c1 = await replace(resources, [*keep, {**new, "custom1": 9}], dry_run=True)
        default = await replace(resources, [*keep, new], dry_run=True)
    refused(with_c1, "UNSUPPORTED_CAPABILITY")
    create = default.data["plan"]["step_payloads"][-1]["seg"]
    assert "c1" not in create and create["c2"] == 128  # no default without evidence


# --- AC-19-11: overlap opt-in and blend mode -------------------------------------------


def three_strip() -> FakeWLED:
    return v16_fake(
        segments=[make_segment(0, 0, 10), make_segment(1, 10, 20), make_segment(2, 20, 30)]
    )


@pytest.mark.anyio
async def test_patch_overlap_needs_allow_overlap_and_the_plan_lists_pairs(tmp_path):
    fake = three_strip()
    move = [{"id": 0, "start": 0, "stop": 15}]
    async with open_resources(tmp_path, fake) as resources:
        default = await patch(resources, move)
        dry = await patch(resources, move, allow_overlap=True, dry_run=True)
        assert fake.method_count("POST") == 0
        live = await patch(resources, move, allow_overlap=True)
    refused(default, "VALIDATION_ERROR")
    assert "allow_overlap" in default.error.message
    assert "overlaps" not in default.data.get("plan", {})
    assert dry.ok and dry.data["plan"]["overlaps"] == [[0, 1]]
    assert dry.data["plan"]["render_order"] == [0, 1, 2]
    assert live.ok and live.verification == "verified", live.error
    assert fake.posts == [dry.data["payload"]]
    assert fake.layout() == {0: (0, 15), 1: (10, 20), 2: (20, 30)}


@pytest.mark.anyio
async def test_replace_overlap_with_blend_mode_and_render_order(tmp_path):
    fake = three_strip()
    desired = [
        {"id": 0, "start": 0, "stop": 20},
        {"id": 1, "start": 10, "stop": 30, "blend_mode": 5},
    ]
    async with open_resources(tmp_path, fake) as resources:
        default = await replace(resources, desired, dry_run=True)
        dry = await replace(resources, desired, allow_overlap=True, dry_run=True)
        live = await replace(resources, desired, allow_overlap=True)
    refused(default, "VALIDATION_ERROR")
    assert "allow_overlap" in default.error.message
    plan = dry.data["plan"]
    assert (plan["overlaps"], plan["render_order"]) == ([[0, 1]], [0, 1])
    assert {"id": 1, "field": "blend_mode", "evidence": "field_present"} in plan[
        "capability_evidence"
    ]
    assert live.ok and live.verification == "verified", (live.error, live.data)
    assert [p for p in fake.posts if "seg" in p] == plan["step_payloads"]
    assert fake.layout() == {0: (0, 20), 1: (10, 30)} and fake.slots[1]["bm"] == 5


@pytest.mark.anyio
async def test_allow_overlap_without_an_overlap_lists_no_pairs(tmp_path):
    fake = three_strip()
    async with open_resources(tmp_path, fake) as resources:
        result = await patch(resources, [{"id": 2, "speed": 9}], allow_overlap=True, dry_run=True)
    assert result.data["plan"]["overlaps"] == [] and result.data["plan"]["render_order"] == [
        0,
        1,
        2,
    ]


# --- AC-19-12: replace create defaults and the inherited-state warning ----------------


@pytest.mark.anyio
async def test_replace_create_sends_the_wled_16_defaults(tmp_path):
    fake = v16_fake(segments=[make_segment(0, 0, 15)])
    desired = [
        {"id": 0, "start": 0, "stop": 15},
        {"id": 1, "start": 15, "stop": 30, "colors": [[1, 2, 3]]},
    ]
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(resources, desired)
    assert result.ok and result.verification == "verified", result.error
    create = fake.posts[-1]["seg"]
    expected = {"cct": 127, "frz": False, **{k: v for k, v in V16_DEFAULTS.items()}}
    assert {k: create[k] for k in expected} == expected
    assert not any("inherited_unexposed_state" in w for w in result.warnings)


@pytest.mark.anyio
async def test_reused_slot_legacy_state_is_reset_where_the_fields_are_reported(tmp_path):
    fake = v16_fake(segments=[make_segment(0, 0, 10), make_segment(3, 20, 30)], slot_count=4)
    fake.slots[1].update(c1=7, cct=50, bm=9, o2=True, si=2)
    desired = [
        {"id": 0, "start": 0, "stop": 10},
        {"id": 1, "start": 10, "stop": 20, "colors": [[1, 2, 3]]},
        {"id": 3, "start": 20, "stop": 30},
    ]
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(resources, desired)
    assert result.ok and result.verification == "verified", result.error
    slot = fake.slots[1]
    assert (slot["c1"], slot["cct"], slot["bm"], slot["o2"], slot["si"]) == (128, 127, 0, False, 0)
    assert not any("inherited_unexposed_state" in w for w in result.warnings)


@pytest.mark.anyio
async def test_reused_slot_on_a_stage_1_device_lists_only_unreported_keys(tmp_path):
    fake = FakeWLED([make_segment(0, 0, 10), make_segment(3, 20, 30)], led_count=30, slot_count=4)
    desired = [
        {"id": 0, "start": 0, "stop": 10},
        {"id": 1, "start": 10, "stop": 20, "colors": [[1, 2, 3]]},
        {"id": 3, "start": 20, "stop": 30},
    ]
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(resources, desired, dry_run=True)
    warning = next(w for w in result.warnings if "inherited_unexposed_state" in w)
    assert "c1, c2, c3, o1, o2, o3, si, set, m12, bm" in warning
    assert "cct" not in warning  # every active segment reports cct: it is reset


@pytest.mark.anyio
async def test_matrix_create_needs_rows_and_resets_orientation(tmp_path):
    fake = matrix_fake(buses=[(0, 136, RGBW)])  # uniform RGBW: 4 channels on a new range
    desired = [
        {"id": 0, "start": 0, "stop": 16, "start_y": 0, "stop_y": 4},
        {"id": 1, "start": 0, "stop": 8, "start_y": 4, "stop_y": 8},
        {"id": 2, "start": 128, "stop": 136},
        {"id": 3, "start": 8, "stop": 16, "start_y": 4, "stop_y": 8, "colors": [[1, 2, 3, 4]]},
    ]
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(resources, desired)
    assert result.ok and result.verification == "verified", (result.error, result.data)
    create = fake.posts[-1]["seg"]
    assert (create["startY"], create["stopY"]) == (4, 8)
    assert (create["rY"], create["mY"], create["tp"]) == (False, False, False)
    slot = fake.slots[3]
    assert (slot["start"], slot["stop"], slot["startY"], slot["stopY"]) == (8, 16, 4, 8)


# --- AC-19-13 / AC-19-14: preservation and uncertain writes ----------------------------


@pytest.mark.anyio
async def test_omitted_new_fields_are_never_sent(tmp_path):
    fake = matrix_fake()
    async with open_resources(tmp_path, fake) as resources:
        patched = await patch(resources, [{"id": 1, "speed": 5}])
        replaced = await replace(
            resources,
            [
                {"id": 0, "start": 0, "stop": 16, "intensity": 6},
                {"id": 1, "start": 0, "stop": 16},
                {"id": 2, "start": 128, "stop": 136},
            ],
        )
    assert patched.ok and replaced.ok, (patched.error, replaced.error)
    assert fake.posts == [{"seg": [{"id": 1, "sx": 5}]}, {"seg": {"id": 0, "ix": 6}}]
    assert (fake.slots[1]["c1"], fake.slots[1]["bm"]) == (40, 3)  # untouched


@pytest.mark.anyio
async def test_uncertain_cct_write_is_unknown_and_not_replayed(tmp_path):
    fake = v16_fake(MIXED)
    fake.post_actions = {0: "fail_after"}
    fake.fail_reads_from_post = 1
    async with open_resources(tmp_path, fake, operation_timeout_seconds=1, read_retries=0) as r:
        result = await patch(r, [{"id": 1, "cct": 9}])
    assert result.error.code == "WRITE_OUTCOME_UNKNOWN"
    assert (result.application, result.verification) == ("unknown", "unknown")
    assert len(fake.posts) == 1


@pytest.mark.anyio
async def test_ignored_option_is_a_mismatch_with_the_stage_1_mapping_and_no_replay(tmp_path):
    """An ACKed write the firmware did not apply keeps the stage-1 outcome mappings."""
    fake = three_strip()
    fake.ignore_keys = {"bm"}
    async with open_resources(tmp_path, fake, read_retries=0) as resources:
        patched = await patch(resources, [{"id": 0, "blend_mode": 4}])
        replaced = await replace(
            resources,
            [
                {"id": 0, "start": 0, "stop": 10, "speed": 3},
                {"id": 1, "start": 10, "stop": 20, "blend_mode": 4},
                {"id": 2, "start": 20, "stop": 30},
            ],
        )
    assert patched.error.code == "VERIFICATION_MISMATCH"
    assert (patched.application, patched.verification) == ("unknown", "mismatch")
    assert replaced.error.code == "VERIFICATION_MISMATCH" and replaced.data["no_replay"] is True
    assert (replaced.application, replaced.verification) == ("applied", "mismatch")
    assert [s["status"] for s in replaced.data["steps_report"]] == ["verified", "failed"]
    assert len(fake.posts) == 3  # one patch POST, two replace steps, nothing replayed


@pytest.mark.anyio
async def test_uncertain_matrix_replace_step_stops_the_sequence(tmp_path):
    fake = matrix_fake()
    fake.post_actions = {0: "fail_after"}
    fake.fail_reads_from_post = 1
    desired = [
        {"id": 0, "start": 0, "stop": 8, "start_y": 0, "stop_y": 4},
        {"id": 1, "start": 8, "stop": 16, "start_y": 0, "stop_y": 8},
        {"id": 2, "start": 128, "stop": 136},
    ]
    async with open_resources(tmp_path, fake, operation_timeout_seconds=1, read_retries=0) as r:
        result = await replace(r, desired)
    assert result.error.code == "WRITE_OUTCOME_UNKNOWN"
    assert len(fake.posts) == 1
    assert [s["status"] for s in result.data["steps_report"]] == ["uncertain", "not_dispatched"]


# --- AC-19-15: transport parity of the input schemas -----------------------------------


def test_new_input_fields_are_additive_and_identical_in_both_tools():
    from wled_mcp.segment_rules import SEGMENT_FIELDS

    layout = ReplaceLayoutRequest.model_json_schema()
    patch_schema = PatchSegmentsRequest.model_json_schema()
    names = [name for name, _wire in SEGMENT_FIELDS]
    layout_props = layout["$defs"]["LayoutSegment"]["properties"]
    patch_props = patch_schema["$defs"]["SegmentPatch"]["properties"]
    for name in names:
        assert layout_props[name] == patch_props[name], name
    for schema in (layout, patch_schema):
        assert schema["properties"]["allow_overlap"] == {
            "default": False,
            "title": "Allow Overlap",
            "type": "boolean",
        }
        assert "allow_overlap" not in schema.get("required", [])
    assert not set(names) & set(layout["$defs"]["LayoutSegment"].get("required", []))
    assert not set(names) & set(patch_schema["$defs"]["SegmentPatch"].get("required", []))


# --- AC-19-16: wled_store_preset ---------------------------------------------------------


def store_device(fake: FakeWLED) -> Any:
    from tests.preset_support import PresetDevice

    return PresetDevice(store={"0": {}}, state=fake.state(), info=fake.info())


async def store(tmp_path, desk: Any, state: dict[str, Any], **arguments: Any) -> Any:
    from tests.test_presets import call as preset_call
    from tests.test_presets import fleet_of
    from tests.test_presets import open_resources as preset_resources

    fleet = fleet_of(desk)
    async with preset_resources(tmp_path, fleet) as resources:
        outcome = await preset_call(
            resources, "wled_store_preset", name="N", state=state, **arguments
        )
    return outcome, fleet


@pytest.mark.anyio
async def test_store_accepts_wled_16_keys_with_evidence_and_stores_them_verbatim(tmp_path):
    desk = store_device(v16_fake(UNIFORM_CCT))
    segment = {"id": 0, "start": 0, "stop": 15, "cct": 200, "c1": 7, "bm": 3, "frz": False}
    outcome, fleet = await store(tmp_path, desk, {"seg": [segment]})
    assert outcome.ok and outcome.verification == "verified", outcome.error
    assert desk.store["1"] == {"seg": [segment], "n": "N"}
    assert fleet.post_count() == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("factory", "segments", "code", "fragment"),
    [
        (
            lambda: v16_fake(MIXED),
            [{"id": 0, "start": 0, "stop": 15, "cct": 9}],
            "UNSUPPORTED_CAPABILITY",
            "CCT",
        ),
        (
            lambda: v16_fake(MIXED),
            [{"id": 3, "start": 0, "stop": 5, "cct": 9}],
            "UNSUPPORTED_CAPABILITY",
            "uniform",
        ),
        (
            stage1_fake,
            [{"id": 0, "start": 0, "stop": 15, "c1": 9}],
            "UNSUPPORTED_CAPABILITY",
            "'c1'",
        ),
        (
            v16_fake,
            [{"id": 0, "start": 0, "stop": 15, "startY": 0, "stopY": 1}],
            "UNSUPPORTED_CAPABILITY",
            "matrix",
        ),
        (
            matrix_fake,
            [{"id": 0, "start": 0, "stop": 20, "startY": 0, "stopY": 4}],
            "VALIDATION_ERROR",
            "16",
        ),
        (matrix_fake, [{"id": 5, "start": 0, "stop": 4}], "VALIDATION_ERROR", "startY"),
        (matrix_fake, [{"id": 5, "start": 130, "stop": 136}], "UNSUPPORTED_CAPABILITY", "trailing"),
        (
            matrix_fake,
            [
                {"id": 0, "start": 0, "stop": 16, "startY": 0, "stopY": 5},
                {"id": 1, "start": 0, "stop": 16, "startY": 4, "stopY": 8},
            ],
            "VALIDATION_ERROR",
            "overlap",
        ),
    ],
)
async def test_store_refuses_wled_16_keys_without_evidence(
    tmp_path, factory, segments, code, fragment
):
    desk = store_device(factory())
    for dry_run in (True, False):
        outcome, fleet = await store(tmp_path, desk, {"seg": segments}, dry_run=dry_run)
        refused(outcome, code)
        assert fragment in outcome.error.message, outcome.error.message
        assert fleet.post_count() == 0


@pytest.mark.anyio
async def test_store_matrix_rectangles_side_by_side_and_the_unchanged_trailing_strip(tmp_path):
    desk = store_device(matrix_fake())
    segments = [
        {"id": 0, "start": 0, "stop": 8, "startY": 0, "stopY": 8, "tp": True},
        {"id": 1, "start": 8, "stop": 16, "startY": 0, "stopY": 8},
        {"id": 2, "start": 128, "stop": 136},
    ]
    outcome, _fleet = await store(tmp_path, desk, {"seg": segments})
    assert outcome.ok, outcome.error
    assert desk.store["1"]["seg"] == segments


def test_store_has_no_allow_overlap():
    from wled_mcp.preset_tools import StorePresetRequest

    state = {"seg": [{"id": 0, "start": 0, "stop": 10}], "allow_overlap": True}
    with pytest.raises(ValidationError):
        StorePresetRequest.model_validate({"device_id": "desk", "name": "N", "state": state})
    with pytest.raises(ValidationError):
        StorePresetRequest.model_validate(
            {"device_id": "desk", "name": "N", "state": {"seg": state["seg"]}, "allow_overlap": 1}
        )


# ======================================================================================
# Review round 1 of b219017 (probe P1, test gaps G1-G6, nits N-1/N-2).
# ======================================================================================


@pytest.mark.anyio
async def test_no_tool_moves_an_existing_trailing_strip_into_the_matrix(tmp_path):
    """M-1 / P1: the store refuses it like patch and replace (TD-19-7)."""
    desk = store_device(matrix_fake())
    segments = [
        {"id": 0, "start": 0, "stop": 16, "startY": 1, "stopY": 4},
        {"id": 1, "start": 0, "stop": 16, "startY": 4, "stopY": 8},
        {"id": 2, "start": 0, "stop": 4},  # existing trailing ID 2 moved into matrix X 0-4
    ]
    for dry_run in (True, False):
        outcome, fleet = await store(tmp_path, desk, {"seg": segments}, dry_run=dry_run)
        refused(outcome, "UNSUPPORTED_CAPABILITY")
        assert "trailing" in outcome.error.message and fleet.post_count() == 0
    fake = matrix_fake()
    async with open_resources(tmp_path, fake) as resources:
        patched = await patch(resources, [{"id": 2, "start": 0, "stop": 4}], allow_overlap=True)
        replaced = await replace(
            resources,
            [
                {"id": 0, "start": 0, "stop": 16},
                {"id": 1, "start": 0, "stop": 16},
                {"id": 2, "start": 0, "stop": 4},
            ],
            allow_overlap=True,
        )
    refused(patched, "UNSUPPORTED_CAPABILITY")  # G6: kills the patch trailing-move mutant
    refused(replaced, "UNSUPPORTED_CAPABILITY")
    assert fake.posts == []


@pytest.mark.anyio
async def test_patch_accepts_unchanged_bounds_on_a_trailing_strip(tmp_path):
    """N-1: unchanged start/stop (and rows) on the trailing strip are not a move."""
    fake = matrix_fake()
    rows = (fake.slots[2]["startY"], fake.slots[2]["stopY"])
    async with open_resources(tmp_path, fake) as resources:
        result = await patch(
            resources,
            [
                {
                    "id": 2,
                    "start": 128,
                    "stop": 136,
                    "start_y": rows[0],
                    "stop_y": rows[1],
                    "custom1": 5,
                }
            ],
        )
    assert result.ok and result.verification == "verified", result.error
    assert (fake.slots[2]["start"], fake.slots[2]["stop"], fake.slots[2]["c1"]) == (128, 136, 5)


@pytest.mark.anyio
async def test_allow_overlap_swap_has_no_intermediate_overlap(tmp_path):
    """G1: the opt-in permits only overlaps the final layout contains; a swap of two
    adjacent ranges has none, so no step may create one."""
    fake = v16_fake()
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(
            resources,
            [{"id": 0, "start": 15, "stop": 30}, {"id": 1, "start": 0, "stop": 15}],
            allow_overlap=True,
        )
    for layout in fake.layouts:
        ranges = sorted(layout.values())
        assert all(a[1] <= b[0] for a, b in zip(ranges, ranges[1:], strict=False)), layout
    # A swap needs a temporary segment: refused before any POST, as without the opt-in.
    refused(result, "UNSUPPORTED_CAPABILITY")
    assert fake.posts == []


def non_uniform_cct_matrix() -> FakeWLED:
    """Segment 0 (rows 0-4) has CCT per segment; the device is not uniform."""
    return matrix_fake(buses=[(0, 64, RGB_CCT), (64, 128, RGB), (128, 136, RGB)])


@pytest.mark.anyio
@pytest.mark.parametrize("rows", [(0, 4), (0, 3)], ids=["same-rows", "fewer-rows"])
async def test_rows_change_counts_as_moved_for_cct_in_patch(tmp_path, rows):
    """G2: supplying rows is a moved range for cct, so the uniform rule applies."""
    fake = non_uniform_cct_matrix()
    async with open_resources(tmp_path, fake) as resources:
        plain = await patch(resources, [{"id": 0, "cct": 9}], dry_run=True)
        moved = await patch(
            resources, [{"id": 0, "start_y": rows[0], "stop_y": rows[1], "cct": 9}], dry_run=True
        )
    assert plain.ok, plain.error  # per-segment CCT evidence for the unchanged range
    refused(moved, "UNSUPPORTED_CAPABILITY")
    assert "uniform" in moved.error.message


@pytest.mark.anyio
async def test_rows_change_counts_as_moved_for_cct_in_replace(tmp_path):
    """G3: the same rule in wled_replace_layout."""
    fake = non_uniform_cct_matrix()
    base = [{"id": 1, "start": 0, "stop": 16}, {"id": 2, "start": 128, "stop": 136}]
    async with open_resources(tmp_path, fake) as resources:
        plain = await replace(
            resources, [{"id": 0, "start": 0, "stop": 16, "cct": 9}, *base], dry_run=True
        )
        moved = await replace(
            resources,
            [{"id": 0, "start": 0, "stop": 16, "start_y": 0, "stop_y": 3, "cct": 9}, *base],
            dry_run=True,
        )
    assert plain.ok, plain.error
    refused(moved, "UNSUPPORTED_CAPABILITY")
    assert "uniform" in moved.error.message


@pytest.mark.anyio
async def test_unknown_rows_of_another_segment_block_a_geometry_change(tmp_path):
    """G4: without the rows of an active matrix segment no overlap check is possible."""
    fake = matrix_fake()
    del fake.slots[1]["startY"]
    del fake.slots[1]["stopY"]
    async with open_resources(tmp_path, fake) as resources:
        moved = await patch(resources, [{"id": 0, "start": 0, "stop": 8}], dry_run=True)
        listed = await patch(resources, [{"id": 0, "speed": 3}], allow_overlap=True, dry_run=True)
        scalar = await patch(resources, [{"id": 0, "speed": 3}], dry_run=True)
    refused(moved, "UNSUPPORTED_CAPABILITY")
    refused(listed, "UNSUPPORTED_CAPABILITY")
    assert "2D bounds unknown" in moved.error.message
    assert scalar.ok, scalar.error  # a scalar patch needs no overlap check


@pytest.mark.anyio
async def test_every_overlapping_pair_is_listed(tmp_path):
    """G5 (AC-19-11): three mutually overlapping ranges give all three pairs."""
    fake = v16_fake()
    desired = [
        {"id": 0, "start": 0, "stop": 20},
        {"id": 1, "start": 10, "stop": 30},
        {"id": 2, "start": 5, "stop": 25, "colors": [[1, 2, 3]]},
    ]
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(resources, desired, allow_overlap=True)
    assert result.ok and result.verification == "verified", result.error
    assert result.data["plan"]["overlaps"] == [[0, 1], [0, 2], [1, 2]]
    assert result.data["plan"]["render_order"] == [0, 1, 2]
    assert fake.layout() == {0: (0, 20), 1: (10, 30), 2: (5, 25)}


@pytest.mark.anyio
async def test_store_option_on_a_new_id_uses_every_active_segment(tmp_path):
    """N-2 (M22): a new ID's option is evidenced by the keys every active segment has."""
    segment = {"id": 5, "start": 0, "stop": 10, "c1": 9, "si": 1}
    outcome, _fleet = await store(tmp_path, store_device(v16_fake()), {"seg": [segment]})
    assert outcome.ok, outcome.error
    fake = v16_fake()
    del fake.slots[1]["c1"]
    outcome, fleet = await store(tmp_path, store_device(fake), {"seg": [segment]})
    refused(outcome, "UNSUPPORTED_CAPABILITY")
    assert fleet.post_count() == 0


@pytest.mark.anyio
async def test_replace_rows_only_change_does_not_resend_the_name(tmp_path):
    """N-2 (M27): the firmware keeps the name on a rows-only change (json.cpp L144-151)."""
    fake = matrix_fake()
    desired = [
        {"id": 0, "start": 0, "stop": 16, "start_y": 0, "stop_y": 3},
        {"id": 1, "start": 0, "stop": 16},
        {"id": 2, "start": 128, "stop": 136},
    ]
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(resources, desired)
    assert result.ok and result.verification == "verified", result.error
    assert fake.posts == [{"seg": {"id": 0, "startY": 0, "stopY": 3}}]
    assert result.data["plan"]["targeted_compensation"] == []
    assert fake.slots[0]["n"] == "Segment 0"


@pytest.mark.anyio
async def test_replace_create_sends_no_cct_default_without_the_key(tmp_path):
    """N-2 (M28): ``cct`` 127 is sent only where every active segment reports ``cct``."""
    segment = make_segment(0, 0, 15)
    del segment["cct"]
    fake = FakeWLED([segment], led_count=30)
    desired = [
        {"id": 0, "start": 0, "stop": 15},
        {"id": 1, "start": 15, "stop": 30, "colors": [[1, 2, 3]]},
    ]
    async with open_resources(tmp_path, fake) as resources:
        result = await replace(resources, desired, dry_run=True)
    create = result.data["plan"]["step_payloads"][-1]["seg"]
    assert "cct" not in create and create["frz"] is False
