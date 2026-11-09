"""Zone format 1 and the resolver of issue #27 (S3-ZONE-01, S3-ZONE-02).

Pure tests: no filesystem, no device. Synthetic IDs and layouts only.
"""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from wled_mcp.client import ClientFailure
from wled_mcp.zones import (
    Part,
    Span,
    ZoneLookupFailure,
    ZoneProblem,
    document_warnings,
    find_zone,
    overlapping_zones,
    parse_zone,
    resolve_part,
    zone_document,
)


def document(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "format": "wled-mcp.zone",
        "format_version": 1,
        "id": "shelf-left",
        "name": "Shelf, left side",
        "description": "Left half of the shelf",
        "parts": [
            {
                "device": "strip_a",
                "led_count": 150,
                "spans": [
                    {"start": 100, "stop": 150, "reversed": True},
                    {"start": 0, "stop": 20, "segment": 1},
                ],
            },
            {"device": "strip_b", "led_count": 60, "spans": [{"start": 0, "stop": 30}]},
        ],
    }
    base.update(overrides)
    return base


def rejected(raw: Any) -> str:
    with pytest.raises(ClientFailure) as caught:
        parse_zone(raw)
    assert caught.value.error.code == "VALIDATION_ERROR"
    return caught.value.error.message


def zone_with(**overrides: Any):
    return parse_zone(document(**overrides))


# ------------------------------------------------------------------------------ parser


def test_a_valid_zone_round_trips_through_its_document():
    zone = parse_zone(document())
    assert zone.parts[0].spans == (Span(100, 150, None, True), Span(0, 20, 1, False))
    assert zone_document(zone) == document()
    assert parse_zone(json.dumps(zone_document(zone))) == zone


@pytest.mark.parametrize("value", [0, 2, 10000, -1, 1.0, True, "1", None])
def test_other_versions_are_rejected_and_integers_are_named(value):
    message = rejected(document(format_version=value))
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 9999:
        assert f"format_version {value}" in message
    else:
        assert "integer 0-9999" in message


def mutated(path: list[Any], value: Any) -> dict[str, Any]:
    doc = copy.deepcopy(document())
    target: Any = doc
    for key in path[:-1]:
        target = target[key]
    if value is KeyError:
        del target[path[-1]]
    else:
        target[path[-1]] = value
    return doc


@pytest.mark.parametrize(
    ("doc", "fragment"),
    [
        (mutated(["extra"], 1), "Unknown zone key"),
        (mutated(["parts", 0, "extra"], 1), "unknown key"),
        (mutated(["parts", 0, "spans", 0, "start_y"], 0), "unknown key"),  # 1D only
        (mutated(["parts", 0, "host"], "x"), "unknown key"),  # no address field
        (mutated(["id"], KeyError), "Missing zone key"),
        (mutated(["id"], "../x"), "zone ID"),
        (mutated(["id"], "con"), "zone ID"),
        (mutated(["name"], " "), "zone name"),
        (mutated(["description"], ""), "description"),
        (mutated(["parts"], []), "'parts' must list"),
        (mutated(["parts", 0, "led_count"], KeyError), "missing 'led_count'"),
        (mutated(["parts", 0, "led_count"], 0), "led_count"),
        (mutated(["parts", 0, "led_count"], True), "led_count"),
        (mutated(["parts", 0, "spans"], []), "'spans' must list"),
        (mutated(["parts", 0, "spans", 0, "stop"], 151), "start < stop <= led_count"),
        (mutated(["parts", 0, "spans", 0, "stop"], 100), "start < stop <= led_count"),
        (mutated(["parts", 0, "spans", 0, "reversed"], "yes"), "'reversed'"),
        (mutated(["parts", 0, "spans", 1, "segment"], 255), "'segment'"),
        (mutated(["parts", 0, "device"], "Not An Id"), "device ID"),
    ],
)
def test_the_parser_rejects_bad_documents_without_quoting_content(doc, fragment):
    message = rejected(doc)
    assert fragment in message
    assert "Not An Id" not in message


def test_overlapping_spans_in_one_part_are_a_conflicting_mapping_but_adjacent_ones_are_fine():
    parts = document()["parts"]
    parts[0]["spans"] = [{"start": 0, "stop": 50}, {"start": 40, "stop": 60}]
    assert "overlap" in rejected(document(parts=parts))
    parts[0]["spans"] = [{"start": 0, "stop": 50}, {"start": 50, "stop": 60}]
    assert parse_zone(document(parts=parts))


def test_one_device_in_two_parts_is_rejected_naming_the_merge():
    parts = document()["parts"]
    parts.append({"device": "strip_a", "led_count": 150, "spans": [{"start": 20, "stop": 30}]})
    assert "mapped twice" in rejected(document(parts=parts))


def test_strict_json_text_rejects_duplicate_keys_and_oversize():
    assert "strict JSON" in rejected('{"format": "wled-mcp.zone", "format": "wled-mcp.zone"}')
    assert "exceeds" in rejected(json.dumps(document(description="x" * 70_000)))


# ------------------------------------------------------------------------------ lookup


def named(zone_id: str, name: str, start: int = 0, stop: int = 10, device: str = "strip_a"):
    return parse_zone(
        document(
            id=zone_id,
            name=name,
            parts=[{"device": device, "led_count": 150, "spans": [{"start": start, "stop": stop}]}],
        )
    )


def test_lookup_prefers_the_id_then_a_unique_casefolded_name():
    zones = [named("left", "Shelf Left"), named("right", "Shelf Right", 10, 20)]
    assert find_zone(zones, "left")[0].id == "left"
    assert find_zone(zones, "shelf right")[0].id == "right"
    with pytest.raises(ZoneLookupFailure) as caught:
        find_zone(zones, "nothing")
    assert caught.value.error.code == "VALIDATION_ERROR"


def test_a_shared_name_is_ambiguous_with_bounded_candidates_while_the_id_still_works():
    zones = [named(f"z{number}", "Same Name", number * 10, number * 10 + 5) for number in range(12)]
    with pytest.raises(ZoneLookupFailure) as caught:
        find_zone(zones, "same name")
    assert caught.value.error.code == "AMBIGUOUS_NAME"
    assert caught.value.total == 12 and len(caught.value.candidates) == 10
    assert find_zone(zones, "z3")[0].id == "z3"


def test_an_id_wins_over_another_zones_name_with_a_warning():
    zones = [named("left", "Alpha"), named("other", "left", 10, 20)]
    zone, warnings = find_zone(zones, "left")
    assert zone.id == "left" and len(warnings) == 1 and "'other'" in warnings[0]


def test_document_warnings_name_name_collisions_and_duplicate_mappings():
    zones = [named("a", "Same"), named("b", "same"), named("c", "Other", 0, 10)]
    warnings = document_warnings(zones)
    assert any("share one name" in w for w in warnings)
    assert any("duplicate_mapping" in w and "'a'" in w and "'c'" in w for w in warnings)


def test_partial_overlap_across_zones_is_information_not_an_error():
    wide = named("wide", "Wide", 0, 50)
    inner = named("inner", "Inner", 10, 20)
    far = named("far", "Far", 60, 70)
    other_device = named("elsewhere", "Elsewhere", 0, 50, device="strip_b")
    found = overlapping_zones(wide, [wide, inner, far, other_device])
    assert found == [{"zone_id": "inner", "device_id": "strip_a"}]


# --------------------------------------------------------------------------- resolver


def live(segments: list[tuple[int, int, int]], led_count: int = 100, matrix: bool = False):
    """The four read views for a layout of ``(id, start, stop)`` segments."""
    view = {"segments": [{"id": i, "start": a, "stop": b} for i, a, b in segments]}
    raw_state = {"seg": [{"id": i, "start": a, "stop": b} for i, a, b in segments]}
    raw_info: dict[str, Any] = {"leds": {"count": led_count}}
    if matrix:
        raw_info["leds"]["matrix"] = {"w": 10, "h": 10}
    return view, {"led_count": led_count}, raw_info, raw_state


def resolve(part: Part, segments: list[tuple[int, int, int]], **kwargs: Any):
    view, caps, info, state = live(segments, **kwargs)
    return resolve_part(part, view, caps, info, state)


def problem_of(part: Part, segments: list[tuple[int, int, int]], **kwargs: Any) -> ZoneProblem:
    with pytest.raises(ZoneProblem) as caught:
        resolve(part, segments, **kwargs)
    return caught.value


def part(*spans: Span, led_count: int = 100) -> Part:
    return Part("strip_a", led_count, tuple(spans))


QUARTERS = [(0, 0, 25), (1, 25, 50), (2, 50, 75), (3, 75, 100)]


def test_a_span_equal_to_one_segment_resolves_to_exactly_that_segment():
    resolved = resolve(part(Span(25, 50)), QUARTERS)
    assert resolved.segment_ids == (1,)
    assert resolved.view()["spans"][0]["segments"] == [{"id": 1, "start": 25, "stop": 50}]
    assert resolved.view()["layout_changes"] is False


def test_a_span_tiled_by_several_segments_lists_all_of_them_in_ascending_order():
    resolved = resolve(part(Span(0, 50)), QUARTERS)
    assert [s.id for s in resolved.spans[0].segments] == [0, 1]


def test_reversed_ordering_lists_the_high_range_first_in_descending_segment_order():
    # "left" is the physically high range of the strip and runs from high to low.
    resolved = resolve(part(Span(50, 100, reversed=True), Span(0, 25)), QUARTERS)
    assert [item.index for item in resolved.spans] == [1, 2]  # file order is logical order
    assert [s.id for s in resolved.spans[0].segments] == [3, 2]  # descending LED order
    assert [s.id for s in resolved.spans[1].segments] == [0]
    assert resolved.segment_ids == (0, 2, 3)  # the patch addresses the sorted union
    flows = [item["flow_reversed"] for item in resolved.view()["spans"]]
    assert flows == [True, False]


def test_a_stale_led_count_is_refused_with_both_counts():
    problem = problem_of(part(Span(0, 25)), QUARTERS, led_count=120)
    assert problem.reason == "topology_stale" and problem.problem["layout_change_required"] is False
    assert problem.problem["expected_led_count"] == 100 and problem.problem["live_led_count"] == 120


def test_an_unknown_led_count_is_an_unsupported_capability():
    view, _caps, info, state = live(QUARTERS)
    with pytest.raises(ZoneProblem) as caught:
        resolve_part(part(Span(0, 25)), view, {"led_count": None}, info, state)
    assert caught.value.error.code == "UNSUPPORTED_CAPABILITY"


def test_a_matrix_device_is_refused_because_zones_are_one_dimensional():
    problem = problem_of(part(Span(0, 25)), QUARTERS, matrix=True)
    assert problem.reason == "matrix_unsupported" and problem.error.code == "UNSUPPORTED_CAPABILITY"


@pytest.mark.parametrize(
    ("span", "layout", "reason", "offender"),
    [
        # A segment straddles the zone edge.
        (Span(0, 40), QUARTERS, "boundary_crossing", 1),
        # A segment larger than the whole zone.
        (Span(10, 20), [(0, 0, 100)], "boundary_crossing", 0),
        # An overlapping foreign segment that starts inside the zone.
        (Span(0, 25), [(0, 0, 25), (1, 20, 60)], "boundary_crossing", 1),
        # No active segment at all in the range.
        (Span(60, 70), [(0, 0, 25)], "span_unsegmented", None),
        # Part of the range is covered by no segment.
        (Span(0, 50), [(0, 0, 20), (1, 30, 50)], "span_gap", None),
        (Span(0, 50), [(0, 0, 40)], "span_gap", None),
    ],
)
def test_a_zone_that_does_not_tile_onto_inner_segments_needs_a_layout_change(
    span, layout, reason, offender
):
    problem = problem_of(part(span), layout)
    assert problem.reason == reason and problem.error.code == "VALIDATION_ERROR"
    assert problem.problem["layout_change_required"] is True and problem.problem["span"] == 1
    assert "wled_replace_layout" in (problem.error.reconciliation or "")
    hint = problem.problem["layout_hint"]
    assert hint["span"] == {"start": span.start, "stop": span.stop}
    if offender is not None:
        assert [s["id"] for s in hint["segments"]][0] == offender


def test_the_segment_hint_must_match_but_does_not_replace_the_range():
    assert resolve(part(Span(25, 50, segment=1)), QUARTERS).segment_ids == (1,)
    problem = problem_of(part(Span(25, 50, segment=2)), QUARTERS)
    assert problem.reason == "segment_mismatch"
    assert problem.problem["layout_change_required"] is False
    # Naming a segment that is wider than the range is still a boundary problem.
    assert problem_of(part(Span(0, 10, segment=0)), QUARTERS).reason == "boundary_crossing"


def test_inactive_segments_do_not_count_and_live_overlaps_inside_are_only_warned_about():
    layout = [(0, 0, 25), (1, 25, 25), (2, 20, 50)]  # segment 1 is inactive (stop == start)
    resolved = resolve(part(Span(0, 50)), layout)
    assert resolved.segment_ids == (0, 2)
    assert any("overlap" in warning for warning in resolved.warnings)


def test_the_signature_changes_with_ids_or_ranges_and_not_with_unrelated_segments():
    base = resolve(part(Span(25, 50)), QUARTERS).signature()
    assert resolve(part(Span(25, 50)), QUARTERS + [(4, 100, 100)]).signature() == base
    renumbered = [(7, 25, 50) if s[0] == 1 else s for s in QUARTERS]
    assert resolve(part(Span(25, 50)), renumbered).signature() != base
