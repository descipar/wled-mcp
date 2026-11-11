"""Issue #29 (S3-T03): the pure SVG renderer, structurally and as one golden snapshot.

No device, no network and no clock are involved: ``render_svg`` takes plain synthetic models.
Every structural test parses the output with the standard library and checks the element
and attribute allowlist, so the properties do not depend on the exact layout of the picture.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any

import pytest

from wled_mcp.layout_preview import (
    MAX_COLOUR_RECTS,
    MAX_LANES,
    MAX_SVG_BYTES,
    NAMESPACE,
    LaneModel,
    LiveModel,
    LiveRun,
    PreviewModel,
    Rendered,
    ZoneModel,
    clean_text,
    render_svg,
)

ALLOWED_ELEMENTS = {"svg", "title", "desc", "g", "rect", "line", "text"}
ALLOWED_ATTRIBUTES = {
    "xmlns",
    "viewBox",
    "width",
    "height",
    "role",
    "x",
    "y",
    "x1",
    "y1",
    "x2",
    "y2",
    "fill",
    "fill-opacity",
    "stroke",
    "stroke-width",
    "stroke-dasharray",
    "font-family",
    "font-size",
    "text-anchor",
}
FORBIDDEN = (
    "http",
    "//",
    "href",
    "xlink",
    "url(",
    "<script",
    "<style",
    "<foreignobject",
    "<image",
    "<animate",
    "<set",
    "javascript:",
    "data:",
)


def lane(seg_id: int, start: int, stop: int, **kwargs: Any) -> LaneModel:
    kwargs.setdefault("name", f"Segment {seg_id}")
    kwargs.setdefault("on", True)
    kwargs.setdefault("brightness", 255)
    kwargs.setdefault("colors", ((255, 0, 0),))
    return LaneModel(seg_id, start, stop, **kwargs)


def model(*lanes: LaneModel, led_count: int | None = 60, **kwargs: Any) -> PreviewModel:
    kwargs.setdefault("source", "observed")
    kwargs.setdefault("device", "strip_a")
    return PreviewModel(led_count=led_count, lanes=lanes, **kwargs)


def check_safe(svg: str) -> ET.Element:
    """Parse and assert the allowlists; the only URL-shaped string is the namespace."""
    root = ET.fromstring(svg)  # raises on malformed or XML-illegal output
    assert root.tag == f"{{{NAMESPACE}}}svg"
    for element in root.iter():
        assert element.tag.removeprefix(f"{{{NAMESPACE}}}") in ALLOWED_ELEMENTS, element.tag
        assert set(element.attrib) <= ALLOWED_ATTRIBUTES, element.attrib
        for value in element.attrib.values():
            assert not any(token in value.lower() for token in FORBIDDEN), value
    assert svg.count(NAMESPACE) == 1
    # Markup and attributes only: element text legitimately holds escaped foreign strings.
    remainder = re.sub(r">[^<]*<", "><", svg.replace(NAMESPACE, ""))
    assert not any(token in remainder.lower() for token in FORBIDDEN)
    assert not re.search(r"\son\w+=", remainder)
    return root


def texts(svg: str) -> list[str]:
    root = check_safe(svg)
    return [e.text or "" for e in root.iter() if e.tag.endswith("}text")]


def render(*lanes: LaneModel, **kwargs: Any) -> Rendered:
    rendered = render_svg(model(*lanes, **kwargs))
    check_safe(rendered.svg)
    return rendered


def by_id(rendered: Rendered) -> dict[int, Any]:
    return {s["id"]: s for s in rendered.summary["segments"]}


GOLDEN = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 265" width="1000" height="265" role="img">
<title>Layout preview, observed, strip_a</title>
<desc>Static 1D layout preview. Ranges are [start,stop) with exclusive stop. Colours are approximate; effects are not simulated.</desc>
<rect x="0" y="0" width="1000" height="265" fill="#ffffff"/>
<g font-family="monospace" font-size="11" fill="#1a1a1a">
<text x="4" y="18" font-size="13">observed layout: strip_a · 60 LEDs</text>
<text x="4" y="33" font-size="10">ranges are [start,stop), stop exclusive · scale 1 LED = 13.5 px · master on bri 128 (shown, not applied)</text>
<rect x="170" y="56" width="810" height="18" fill="none" stroke="#bbbbbb"/>
<rect x="170" y="56" width="270" height="18" fill="#ffa000" fill-opacity="0.78"/>
<text x="4" y="68" font-size="10">0 Left</text>
<text x="4" y="82" font-size="9">[0,20) · bri 200 · white added</text>
<rect x="170" y="88" width="810" height="18" fill="none" stroke="#bbbbbb"/>
<rect x="507.5" y="88" width="270" height="18" fill="#0a141e"/>
<text x="4" y="100" font-size="10">3 Mid</text>
<text x="4" y="114" font-size="9">[25,45) · bri 255</text>
<rect x="170" y="120" width="810" height="18" fill="none" stroke="#bbbbbb"/>
<rect x="710" y="120" width="270" height="18" fill="none" stroke="#666666" stroke-dasharray="3 2"/>
<text x="4" y="132" font-size="10">7 Right</text>
<text x="4" y="146" font-size="9">[40,60) · bri 0 · off</text>
<rect x="170" y="152" width="810" height="12" fill="none" stroke="#bbbbbb"/>
<rect x="440" y="152" width="67.5" height="12" fill="#f0f0f0" stroke="#888888" stroke-dasharray="3 2"/>
<rect x="710" y="152" width="67.5" height="12" fill="#e74c3c" fill-opacity="0.45" stroke="#c0392b"/>
<text x="4" y="162" font-size="9">gaps / overlaps</text>
<g stroke="#444444">
<line x1="170" y1="174" x2="980" y2="174"/>
<line x1="170" y1="176" x2="980" y2="176" stroke-width="4" stroke-dasharray="1 12.5"/>
<line x1="170" y1="174" x2="170" y2="180"/>
<line x1="305" y1="174" x2="305" y2="180"/>
<line x1="440" y1="174" x2="440" y2="180"/>
<line x1="575" y1="174" x2="575" y2="180"/>
<line x1="710" y1="174" x2="710" y2="180"/>
<line x1="845" y1="174" x2="845" y2="180"/>
<line x1="980" y1="174" x2="980" y2="180"/>
</g>
<text x="170" y="192" font-size="9" text-anchor="middle">0</text>
<text x="305" y="192" font-size="9" text-anchor="middle">10</text>
<text x="440" y="192" font-size="9" text-anchor="middle">20</text>
<text x="575" y="192" font-size="9" text-anchor="middle">30</text>
<text x="710" y="192" font-size="9" text-anchor="middle">40</text>
<text x="845" y="192" font-size="9" text-anchor="middle">50</text>
<text x="980" y="192" font-size="9" text-anchor="middle">60</text>
<text x="4" y="220" font-size="10">gaps: [20,25); overlaps: [40,45) (scope: drawn segment ranges; not inferred wiring)</text>
<text x="4" y="233" font-size="10">approx.: white channel added to RGB for RGBW segments.</text>
<text x="4" y="246" font-size="10">Colours approximate the first colour slot (or live samples); not calibrated. Effects and animation are not simulated; 1D only.</text>
</g>
</svg>"""  # noqa: E501


def golden_model() -> PreviewModel:
    return model(
        lane(0, 0, 20, name="Left", brightness=200, colors=((255, 160, 0, 0),)),
        lane(3, 25, 45, name="Mid", colors=((10, 20, 30),)),
        lane(7, 40, 60, name="Right", on=False, brightness=0),
        master_on=True,
        master_brightness=128,
    )


# ================================================================== golden and structure


def test_one_golden_svg_catches_accidental_output_drift():
    # Update deliberately when the picture changes; every other test is structural.
    assert render_svg(golden_model()).svg.replace("><", ">\n<") == GOLDEN


def test_the_summary_describes_what_is_drawn_and_what_it_means():
    summary = render_svg(golden_model()).summary
    assert summary["source"] == "observed" and summary["led_count"] == 60
    assert summary["range_semantics"] == "[start,stop) exclusive stop"
    assert summary["scale"] == {"viewbox_width": 1000, "leds_per_pixel": round(60 / 810, 4)}
    assert summary["gaps"] == [{"start": 20, "stop": 25}]
    assert summary["overlaps"] == [{"start": 40, "stop": 45}]
    assert summary["colour_basis"] == "state_slot_0"
    assert summary["approximations"] == ["rgbw_white_added"]
    assert any("not calibrated" in item for item in summary["limits"])
    assert any("not simulated" in item for item in summary["limits"])


def test_every_output_is_script_free_namespaced_and_parseable():
    for item in (
        golden_model(),
        model(),
        model(lane(0, 0, 5), led_count=None),
        model(lane(0, 0, 80), led_count=60),
    ):
        check_safe(render_svg(item).svg)


# ====================================================================== ranges and axis


def test_sparse_ids_unsorted_input_and_exclusive_ends_are_labelled():
    rendered = render(lane(7, 40, 60), lane(0, 0, 20), lane(3, 20, 40))
    assert [s["id"] for s in rendered.summary["segments"]] == [0, 3, 7]
    shown = texts(rendered.svg)
    assert "[0,20)" in " ".join(shown) and "[20,40)" in " ".join(shown)
    assert any("stop exclusive" in line for line in shown)
    assert rendered.summary["gaps"] == [] and rendered.summary["overlaps"] == []  # adjacent


@pytest.mark.parametrize(
    "lanes,gaps",
    [
        ((lane(0, 5, 60),), [(0, 5)]),
        ((lane(0, 0, 20), lane(1, 30, 60)), [(20, 30)]),
        ((lane(0, 0, 40),), [(40, 60)]),
        ((), [(0, 60)]),
    ],
)
def test_gaps_at_the_start_middle_and_end_and_for_an_empty_layout(lanes, gaps):
    rendered = render(*lanes)
    assert [(g["start"], g["stop"]) for g in rendered.summary["gaps"]] == gaps
    assert any(f"[{a},{b})" in line for line in texts(rendered.svg) for a, b in gaps[:1])
    if not lanes:
        assert any("No active segments" in line for line in texts(rendered.svg))


def test_overlaps_are_reported_and_marked_in_text():
    rendered = render(lane(0, 0, 30), lane(1, 20, 50))
    assert rendered.summary["overlaps"] == [{"start": 20, "stop": 30}]
    assert any("overlaps: [20,30)" in line for line in texts(rendered.svg))


@pytest.mark.parametrize(
    "led_count,expected",
    [(60, "1 LED = 13.5 px"), (810, "1 LED = 1.0 px"), (8100, "1 px = 10.0 LEDs")],
)
def test_the_scale_is_stated_for_small_and_large_strips(led_count, expected):
    rendered = render(lane(0, 0, 10), led_count=led_count)
    assert any(expected in line for line in texts(rendered.svg))


def test_the_axis_has_a_bounded_number_of_labelled_round_ticks():
    for total in (7, 60, 61, 1000, 100000):
        rendered = render(lane(0, 0, 5), led_count=total)
        labels = [
            e.text
            for e in ET.fromstring(rendered.svg).iter()
            if e.tag.endswith("}text") and (e.text or "").isdigit() and e.get("text-anchor")
        ]
        assert 2 <= len(labels) <= 11
        assert labels[0] == "0" and labels[-1] == str(total)


# ======================================================================== large and bound


def test_a_large_strip_with_many_lanes_and_samples_stays_bounded():
    lanes = tuple(
        lane(
            i,
            i * 1500,
            i * 1500 + 1400,
            name="&" * 24,
            live_runs=tuple(
                LiveRun(i * 1500 + j * 10, 1, f"{(i * 7 + j) % 255:02X}00FF") for j in range(100)
            ),
            live_status="sampled",
        )
        for i in range(MAX_LANES)
    )
    big = model(*lanes, led_count=100_000, live=LiveModel("available", 10))
    rendered = render_svg(big)
    root = check_safe(rendered.svg)
    assert len(rendered.svg.encode("utf-8")) < MAX_SVG_BYTES
    assert len(list(root.iter())) < 1200  # no element per LED
    rects = [e for e in root.iter() if e.tag.endswith("}rect")]
    assert len(rects) < MAX_COLOUR_RECTS + 2 * MAX_LANES + 20
    assert any("1 px = " in line for line in texts(rendered.svg))
    assert rendered.summary["colour_basis"] == "live_samples"
    # The worst case measured about 46 kB against the 48 KiB cap; growth must stay deliberate.
    assert len(rendered.svg.encode("utf-8")) < 47_000


def test_the_worst_case_names_on_a_small_strip_still_fit_the_cap():
    lanes = tuple(lane(i, i, i + 1, name="&" * 40) for i in range(MAX_LANES))
    rendered = render_svg(model(*lanes, led_count=120))
    check_safe(rendered.svg)
    assert len(rendered.svg.encode("utf-8")) < MAX_SVG_BYTES


def test_more_than_the_lane_limit_reports_omitted_segments():
    lanes = tuple(lane(i, i, i + 1) for i in range(70))
    rendered = render(*lanes, led_count=100)
    assert rendered.summary["omitted_segments"] == 6
    assert len(rendered.summary["segments"]) == MAX_LANES
    assert max(s["id"] for s in rendered.summary["segments"]) == 63
    assert any("6 more omitted" in line for line in texts(rendered.svg))


def test_colour_rectangles_are_budgeted_across_all_lanes():
    many = tuple(LiveRun(j, 1, f"{j % 256:02X}{(j * 3) % 256:02X}00") for j in range(0, 600, 2))
    lanes = (lane(0, 0, 1000, live_runs=many, live_status="sampled"), lane(1, 1000, 1100))
    rendered = render_svg(model(*lanes, led_count=2000, live=LiveModel("available", 1)))
    root = check_safe(rendered.svg)
    fills = [
        e for e in root.iter() if e.tag.endswith("}rect") and e.get("fill", "").startswith("#")
    ]
    drawn = [e for e in fills if e.get("height") == "18" and e.get("fill") != "none"]
    assert len(drawn) <= MAX_COLOUR_RECTS
    assert any("more runs not drawn" in n for n in by_id(rendered)[0]["notes"])


# ====================================================================== hostile labels

HOSTILE = [
    "</text><script>alert(1)</script>",
    '"onload="x"',
    "&amp; &lt;b&gt;",
    "a]]>b",
    "tab\there\x00nul\x1bescape\x85",
    "bidi ‮evil⁦x⁩ ‎",
    "pair \ud800 lone \udfff and ﷐ ￿ end",
    "x" * 10_000,
]


@pytest.mark.parametrize("name", HOSTILE)
def test_hostile_names_never_become_markup_and_are_truncated(name):
    rendered = render(lane(0, 0, 10, name=name), zone=ZoneModel("z", name, ((0, 5, False),)))
    root = check_safe(rendered.svg)
    assert not [e for e in root.iter() if e.tag.endswith("}script")]
    assert "<script" not in rendered.svg.lower().replace("&lt;script", "")
    label = by_id(rendered)[0]["label"]
    assert len(label) <= 24
    assert not any(ch in label for ch in "\x00\x1b\x85‮⁦⁩‎\ud800﷐￿")
    assert all(len(line) <= 150 for line in texts(rendered.svg))


def test_the_text_sanitiser_collapses_drops_and_truncates():
    assert clean_text("  a \t b\n c ", 20) == "a b c"
    assert clean_text("ab‮cd", 20) == "abcd"
    assert clean_text("x" * 50, 10) == "x" * 9 + "…"
    assert clean_text(12, 5) == "12"


def test_a_hostile_device_name_is_sanitised_in_the_title_and_header():
    rendered = render_svg(model(lane(0, 0, 5), device="</title><svg onload=x>"))
    root = check_safe(rendered.svg)
    assert [e for e in root.iter() if e.tag.endswith("}svg")] == [root]


def test_a_hostile_live_colour_cannot_reach_an_attribute():
    runs = (LiveRun(0, 1, '"/><script>'), LiveRun(1, 1, "12345G"), LiveRun(2, 1, "00ff00"))
    rendered = render_svg(
        model(lane(0, 0, 5, live_runs=runs), live=LiveModel("available", 1), led_count=5)
    )
    root = check_safe(rendered.svg)
    fills = {e.get("fill") for e in root.iter() if e.tag.endswith("}rect")}
    assert "#00ff00" in fills and not any("script" in (f or "") for f in fills)


# ======================================================================= colours


def mode_of(item: LaneModel) -> dict[str, Any]:
    return by_id(render(item))[item.id]


def test_rgb_is_used_as_is_and_rgbw_adds_white_with_a_clamp_and_a_label():
    assert mode_of(lane(0, 0, 10, colors=((10, 20, 30),)))["colour"] == "#0a141e"
    rgbw = render(lane(0, 0, 10, colors=((200, 100, 10, 100),)))
    assert by_id(rendered := rgbw)[0]["colour"] == "#ffc86e"  # 200+100 clamps to 255
    assert by_id(rendered)[0]["colour_mode"] == "rgbw_white_added"
    assert "rgbw_white_added" in rendered.summary["approximations"]
    assert any("white channel added" in line for line in texts(rendered.svg))


def test_cct_only_segments_are_neutral_grey_with_the_value_and_a_flag():
    item = lane(0, 0, 10, color_capability={"rgb": False, "white": False, "cct": True}, cct=127)
    rendered = render(item)
    entry = by_id(rendered)[0]
    assert entry["colour_mode"] == "cct_not_rendered" and entry["colour"] == "#9e9e9e"
    assert any("cct 127 not rendered" in note for note in entry["notes"])
    assert "cct_not_rendered" in rendered.summary["approximations"]
    both = lane(1, 0, 10, color_capability={"rgb": True, "white": False, "cct": True})
    assert mode_of(both)["colour_mode"] == "rgb"


def test_an_off_segment_is_outline_only_and_brightness_is_only_an_opacity_with_a_floor():
    off = render(lane(0, 0, 10, on=False, brightness=0))
    assert by_id(off)[0]["colour"] is None and by_id(off)[0]["colour_mode"] == "off"
    dim = render(lane(1, 0, 10, brightness=5))
    root = ET.fromstring(dim.svg)
    opacities = {e.get("fill-opacity") for e in root.iter() if e.get("fill-opacity")}
    assert opacities == {"0.25"}  # visible floor, not 5/255


def test_missing_colours_are_neutral_with_a_note_and_never_claim_a_simulation():
    rendered = render(lane(0, 0, 10, colors=None), lane(1, 10, 20, effect_id=42))
    entry = by_id(rendered)[0]
    assert entry["colour_mode"] == "unknown" and entry["colour"] == "#bdbdbd"
    assert "colour unknown" in entry["notes"]
    shown = " ".join(texts(rendered.svg))
    assert "not simulated" in shown and "effect not simulated" in shown
    assert "effects_not_simulated" in rendered.summary["approximations"]
    tags = {e.tag.removeprefix(f"{{{NAMESPACE}}}") for e in ET.fromstring(rendered.svg).iter()}
    assert not tags & {"animate", "animateTransform", "set", "script", "style", "image"}


def test_a_proposed_layout_marks_changes_removals_and_its_basis():
    rendered = render(
        lane(0, 0, 30, change="unchanged"),
        lane(1, 30, 60, change="new"),
        source="proposed",
        removed_segment_ids=(4, 5),
    )
    assert rendered.summary["source"] == "proposed" and rendered.summary["colour_basis"] == "plan"
    assert rendered.summary["removed_segment_ids"] == [4, 5]
    assert by_id(rendered)[1]["change"] == "new"
    shown = " ".join(texts(rendered.svg))
    assert "proposed layout (not applied)" in shown and "removed by this layout" in shown


# ====================================================================== missing geometry


def test_an_unknown_led_count_is_labelled_and_scaled_to_the_highest_end():
    rendered = render(lane(0, 0, 20), lane(1, 30, 45), led_count=None)
    assert rendered.summary["led_count"] is None
    assert rendered.summary["led_count_source"] == "unknown"
    assert any("LED count unknown" in line for line in texts(rendered.svg))
    assert [(g["start"], g["stop"]) for g in rendered.summary["gaps"]] == [(20, 30)]  # no tail


def test_segments_beyond_the_led_count_are_clipped_and_marked_never_invented():
    rendered = render(lane(0, 0, 40), lane(1, 50, 80), lane(2, 70, 90), led_count=60)
    notes = {i: s["notes"] for i, s in by_id(rendered).items()}
    assert "range outside LED count" not in notes[0]
    assert "range outside LED count" in notes[1] and "range outside LED count" in notes[2]
    assert [(g["start"], g["stop"]) for g in rendered.summary["gaps"]] == [(40, 50)]
    assert rendered.summary["overlaps"] == []  # the fully outside lane draws nothing


def test_zero_length_segments_are_omitted_and_an_empty_layout_has_a_scale():
    rendered = render(lane(0, 10, 10), lane(1, 0, 30))
    assert [s["id"] for s in rendered.summary["segments"]] == [1]
    empty = render()
    assert empty.summary["segments"] == [] and empty.summary["omitted_segments"] == 0
    assert any("No active segments" in line for line in texts(empty.svg))


def test_a_zone_overlay_draws_bands_and_a_stale_zone_is_not_drawn():
    zone = ZoneModel("shelf", "Shelf", ((0, 20, False), (20, 60, True)))
    drawn = render(lane(0, 0, 60), zone=zone)
    assert drawn.summary["zone"]["status"] == "drawn"
    assert drawn.summary["zone"]["spans"][1] == {"start": 20, "stop": 60, "reversed": True}
    assert any("[20,60) reversed" in line for line in texts(drawn.svg))
    assert any("alignment not checked" in line for line in texts(drawn.svg))
    stale = render(lane(0, 0, 60), zone=ZoneModel("shelf", "Shelf", (), "topology_stale"))
    assert stale.summary["zone"]["status"] == "topology_stale"
    assert stale.summary["zone"]["spans"] == []
    assert any("topology_stale" in line for line in texts(stale.svg))


# ======================================================================== live samples


def live_model(step: int, runs: tuple[LiveRun, ...], status: str = "sampled", **kwargs: Any):
    item = lane(0, 0, 20, live_runs=runs, live_status=status, **kwargs)
    return model(item, led_count=20, live=LiveModel("available", step))


def test_every_led_sampled_draws_the_runs_without_an_unknown_led_legend():
    runs = (LiveRun(0, 5, "FF0000"), LiveRun(5, 5, "00FF00"))
    rendered = render_svg(live_model(1, runs))
    check_safe(rendered.svg)
    assert rendered.summary["colour_basis"] == "live_samples"
    assert "unsampled_leds_unknown" not in rendered.summary["approximations"]
    assert "live_rgb_brightness_scaled" in rendered.summary["approximations"]
    assert rendered.summary["live"] == {
        "requested": True,
        "status": "available",
        "sampling_step": 1,
    }
    assert by_id(rendered)[0]["colour_mode"] == "live_samples"


def test_downsampled_runs_state_that_the_intervening_leds_are_unknown():
    runs = (LiveRun(0, 2, "FF0000"), LiveRun(6, 1, "0000FF"))
    rendered = render_svg(live_model(3, runs))
    shown = " ".join(texts(rendered.svg))
    assert "sampled every 3 LEDs; unsampled LEDs are unknown" in shown
    assert "unsampled_leds_unknown" in rendered.summary["approximations"]


def test_identical_adjacent_runs_are_merged_and_other_statuses_become_lane_notes():
    runs = (LiveRun(0, 5, "FF0000"), LiveRun(5, 5, "ff0000"), LiveRun(10, 5, "00FF00"))
    rendered = render_svg(live_model(1, runs))
    root = ET.fromstring(rendered.svg)
    widths = [e.get("width") for e in root.iter() if e.get("fill") in {"#ff0000", "#00ff00"}]
    assert len(widths) == 2
    truncated = render_svg(live_model(1, (), status="missing_samples"))
    assert "live missing_samples" in by_id(truncated)[0]["notes"]
    assert by_id(truncated)[0]["colour"] is None  # nothing sampled, nothing invented


def test_the_colour_basis_is_mixed_when_only_some_lanes_have_live_samples():
    sampled = lane(0, 0, 10, live_runs=(LiveRun(0, 10, "FF0000"),), live_status="sampled")
    state_only = lane(1, 10, 20)  # e.g. returned beyond the live cap: no live runs
    rendered = render_svg(model(sampled, state_only, led_count=20, live=LiveModel("available", 1)))
    assert rendered.summary["colour_basis"] == "mixed"
    assert by_id(rendered)[0]["colour"] == "#ff0000"
    assert by_id(rendered)[1]["colour_mode"] == "rgb"  # the lane itself stays truthful


def test_an_unavailable_live_read_falls_back_to_the_state_colours():
    item = lane(0, 0, 20)
    rendered = render_svg(model(item, led_count=20, live=LiveModel("unavailable", 1)))
    assert rendered.summary["colour_basis"] == "state_slot_0"
    assert rendered.summary["live"]["status"] == "unavailable"
    assert by_id(rendered)[0]["colour_mode"] == "rgb"


# ===================================================================== determinism


def test_two_renders_of_one_model_are_byte_identical():
    first, second = render_svg(golden_model()), render_svg(golden_model())
    assert first.svg == second.svg and first.summary == second.summary
