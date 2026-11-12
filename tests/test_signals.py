"""Pure planning and comparison of temporary signals (issue #28, T28-01, T28-05 pure part).

No I/O, no clock: a fresh state/info pair in, a plan or a list of differences out.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from tests.signal_support import BASE_COLOR, SOLID, WIPE, FakeController
from tests.state_catalog_support import make_segment
from wled_mcp.client import ClientFailure
from wled_mcp.patches import matches_segments, matches_set_state
from wled_mcp.readmodels import Collector, normalize_state
from wled_mcp.signals import (
    MAX_DIFFERENCES,
    SignalPlan,
    SignalRefusal,
    SignalSpec,
    build_restore_plan,
    build_signal_plan,
    compare,
)


def spec(*segments: int, color: tuple[int, int, int] = (255, 0, 0)) -> SignalSpec:
    return SignalSpec("desk", segments or (0,), color, 10)


def views(controller: FakeController) -> tuple[Any, Any, Any, Any]:
    state, info = copy.deepcopy(controller.state), copy.deepcopy(controller.info)
    view, capabilities, _firmware, _unknown = normalize_state(state, info, Collector())
    return view, capabilities, info, state


def plan_for(controller: FakeController, signal: SignalSpec | None = None) -> SignalPlan:
    view, capabilities, info, state = views(controller)
    return build_signal_plan(signal or spec(), view, capabilities, info, state, SOLID)


def owned(plan: SignalPlan) -> list[tuple[Any, ...]]:
    return [(f.scope, f.segment_id, f.name, f.captured, f.applied) for f in plan.owned]


def refusal(controller: FakeController, signal: SignalSpec | None = None) -> SignalRefusal:
    with pytest.raises(SignalRefusal) as caught:
        plan_for(controller, signal)
    return caught.value


# ------------------------------------------------------------------- T28-01 owned fields


def test_the_owned_fields_are_exactly_the_written_ones():
    # Master off, segment on, a non-Solid effect: master power, colour slot 0 and the effect.
    plan = plan_for(FakeController(master_on=False))
    assert owned(plan) == [
        ("master", None, "on", False, True),
        ("segment", 0, "col0", BASE_COLOR, [255, 0, 0]),
        ("segment", 0, "fx", WIPE, SOLID),
    ]
    assert plan.payload == {
        "on": True,
        "seg": [{"id": 0, "col": [[255, 0, 0]], "fx": SOLID}],
    }  # no bri, tt, sx, ix, pal: the unowned fields are never sent
    assert plan.unowned == {"master_brightness": 47, "segments": [{"id": 0, "brightness": 255}]}

    # Master on and the segment off: the segment power is owned instead, the master is not.
    plan = plan_for(FakeController(master_on=True, segments=[make_segment(0, 0, 30, on=False)]))
    assert [(f.scope, f.name) for f in plan.owned] == [
        ("segment", "col0"),
        ("segment", "fx"),
        ("segment", "on"),
    ]
    assert plan.payload == {"seg": [{"id": 0, "on": True, "col": [[255, 0, 0]], "fx": SOLID}]}

    # Everything already on: no power field is owned and none is written or restored.
    plan = plan_for(FakeController(master_on=True))
    assert [f.name for f in plan.owned] == ["col0", "fx"] and "on" not in plan.payload


def test_the_colour_follows_the_channel_width_of_the_segment():
    rgbw = FakeController(master_on=True, lc=3)  # RGB plus white
    assert owned(plan_for(rgbw))[0][4] == [255, 0, 0, 0]
    assert refusal(FakeController(master_on=True, lc=2)).reason == "color_capability"  # white only
    assert refusal(FakeController(master_on=True, lc=0)).reason == "color_capability"


# ------------------------------------------------------------------ T28-01 rejections

CASES: dict[str, tuple[Any, str]] = {
    "unknown_segment": (lambda c: None, "segment_unknown"),
    "playlist": (lambda c: c.edit(pl=1), "playlist_active"),
    "realtime": (lambda c: c.info.update(live=True), "realtime_active"),
    "nightlight": (lambda c: c.edit(nl={"on": True}), "nightlight_active"),
    "frozen_target": (lambda c: c.edit_segment(0, frz=True), "segment_frozen"),
    "frozen_other_while_off": (lambda c: c.edit_segment(1, frz=True), "segment_frozen"),
    "master_brightness_zero": (lambda c: c.edit(bri=0, on=True), "brightness_zero"),
    "segment_off_with_zero": (lambda c: c.edit_segment(0, on=False, bri=0), "brightness_zero"),
    "incomplete_capture": (lambda c: c.segment(0).pop("fx"), "capture_incomplete"),
    "incomplete_colour": (lambda c: c.segment(0).update(col=[]), "capture_incomplete"),
}


@pytest.mark.parametrize("case", CASES)
def test_unsupported_states_are_refused_before_any_write_with_a_stable_reason(case):
    change, reason = CASES[case]
    controller = FakeController(
        master_on=True, segments=[make_segment(0, 0, 30), make_segment(1, 30, 60)]
    )
    change(controller)
    target = spec(7) if case == "unknown_segment" else spec(0)
    if case == "frozen_other_while_off":
        controller.edit(on=False)
        controller.edit_segment(1, on=False)
    assert refusal(controller, target).reason == reason


def test_a_master_that_is_off_cannot_isolate_a_target_next_to_a_visible_segment():
    controller = FakeController(
        master_on=False, segments=[make_segment(0, 0, 30), make_segment(1, 30, 60)]
    )
    assert refusal(controller).reason == "master_off_other_segments"
    controller.edit_segment(1, on=False)  # the neighbour is off: turning the master on is safe
    assert plan_for(controller).payload["on"] is True


def test_a_running_preset_is_allowed_with_a_warning():
    controller = FakeController(master_on=True)
    controller.edit(ps=4)
    plan = plan_for(controller)
    assert any("preset marker" in warning for warning in plan.warnings)


# ---------------------------------------------------------------------- comparison


def applied_state(controller: FakeController, plan: SignalPlan) -> dict[str, Any]:
    """What the device reports after the signal was applied (the planner's own postconditions)."""
    state = copy.deepcopy(controller.state)
    if plan.master is not None:
        state["on"] = True
    for identifier, fields in plan.segments.expectations.items():
        segment = next(s for s in state["seg"] if s["id"] == identifier)
        segment["col"][0][:3] = fields["col"][0][:3]
        segment["fx"] = fields["fx"]
        segment["on"] = fields.get("on", segment["on"])
    return state


def test_compare_agrees_with_the_verification_functions_and_names_each_difference():
    controller = FakeController(master_on=False)
    plan = plan_for(controller)
    state, info = applied_state(controller, plan), controller.info
    assert compare(plan.owned, plan.geometry, state, info) == []
    assert plan.matches(state)

    # Unowned fields and animation progress never count.
    state["bri"], state["transition"] = 1, 9
    state["seg"][0].update(sx=1, ix=2, pal=2, bri=3, n="x", col=[[255, 0, 0, 0], [5, 5, 5, 0]])
    assert compare(plan.owned, plan.geometry, state, info) == []

    changed = copy.deepcopy(state)
    changed["on"] = False
    changed["seg"][0]["fx"] = 1
    changed["seg"][0]["col"][0] = [0, 0, 1, 0]
    changed["pl"] = 2
    found = compare(plan.owned, plan.geometry, changed, {**info, "live": True})
    assert {(d["scope"], d["field"]) for d in found} == {
        ("device", "playlist"),
        ("device", "realtime"),
        ("master", "on"),
        ("segment", "fx"),
        ("segment", "col0"),
    }
    assert not matches_set_state(plan.master, changed)  # type: ignore[arg-type]
    assert not matches_segments(plan.segments.expectations, changed)


def test_the_number_of_reported_differences_is_bounded():
    controller = FakeController(
        master_on=True, segments=[make_segment(i, i, i + 1) for i in range(16)]
    )
    plan = plan_for(controller, spec(*range(16)))
    state = applied_state(controller, plan)
    for segment in state["seg"]:
        segment.update(fx=2, col=[[1, 1, 1, 0], [0] * 4, [0] * 4])
    assert len(compare(plan.owned, plan.geometry, state, controller.info)) == MAX_DIFFERENCES


# ------------------------------------------------------------------------- restore plan


def test_the_restore_plan_writes_only_the_owned_fields_with_their_captured_values():
    controller = FakeController(master_on=False)
    plan = plan_for(controller)
    state = applied_state(controller, plan)
    view, capabilities, _firmware, _unknown = normalize_state(state, controller.info, Collector())
    restore = build_restore_plan(plan.owned, "desk", view, capabilities, controller.info, state)
    assert restore.payload == {
        "on": False,
        "seg": [{"id": 0, "col": [BASE_COLOR[:3]], "fx": WIPE}],
    }
    restored = copy.deepcopy(state)
    restored["on"] = False
    restored["seg"][0].update(fx=WIPE)
    restored["seg"][0]["col"][0] = BASE_COLOR
    assert restore.matches(restored) and not restore.matches(state)


def test_the_planner_failures_stay_client_failures():
    controller = FakeController(master_on=True)
    controller.info["fxcount"] = 0  # no effect catalog range: the existing planner refuses
    with pytest.raises(ClientFailure):
        plan_for(controller)
