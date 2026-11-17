"""Issue #183: the pure room rules (index, conflicts, containment). No I/O, no device."""

from __future__ import annotations

from wled_mcp.groups import Group, Member
from wled_mcp.rooms import (
    MAX_PROBLEMS,
    conflicts_of,
    containment_problems,
    outside_devices,
    partial_members,
    problem_data,
    room_conflicts,
    room_index,
    save_conflict,
)
from wled_mcp.scenes import ExpandedTarget, ResolvedSegments


def group(group_id: str, *members: Member, kind: str = "room") -> Group:
    return Group(group_id, group_id.title(), members, kind)  # type: ignore[arg-type]


def whole(device: str) -> Member:
    return Member(device)


def target(device: str, *ids: int, master: bool = False) -> ExpandedTarget:
    segments = (ResolvedSegments(ids, {"brightness": 10}),) if ids else ()
    return ExpandedTarget(device, "device", 1, {"on": True} if master else None, segments)


LIVING = group("living", whole("strip_a"), Member("strip_b", (0, 2)))
KITCHEN = group("kitchen", whole("strip_c"))


def test_plain_groups_never_take_part_in_the_index_or_in_conflicts():
    floor = group("floor", whole("strip_a"), whole("strip_c"), kind="group")
    assert room_index([LIVING, KITCHEN, floor]) == {
        "strip_a": ["living"],
        "strip_b": ["living"],
        "strip_c": ["kitchen"],
    }
    assert room_conflicts([LIVING, KITCHEN, floor]) == []


def test_a_device_in_two_rooms_is_a_conflict_with_or_without_segments():
    other = group("hall", Member("strip_b", (5,)), whole("strip_d"))
    assert room_conflicts([LIVING, KITCHEN, other]) == [
        {"device_id": "strip_b", "rooms": ["hall", "living"]}
    ]
    problems = conflicts_of(LIVING, [LIVING, KITCHEN, other])
    assert [(p.device_id, p.reason) for p in problems] == [("strip_b", "room_conflict")]
    assert "'hall'" in problems[0].message
    assert conflicts_of(KITCHEN, [LIVING, KITCHEN, other]) == []


def test_saving_a_room_is_refused_for_a_device_in_another_room_but_not_for_itself():
    assert save_conflict(group("hall", whole("strip_a")), [LIVING, KITCHEN]) is not None
    assert save_conflict(group("living", whole("strip_a")), [LIVING, KITCHEN]) is None
    assert save_conflict(group("hall", whole("strip_z")), [LIVING, KITCHEN]) is None


def test_partial_members_name_every_member_that_designates_segments():
    assert [p.device_id for p in partial_members(LIVING)] == ["strip_b"]
    assert partial_members(KITCHEN) == []


def test_containment_reports_every_reason_and_lets_a_whole_member_take_anything():
    problems = containment_problems(
        LIVING,
        [
            target("strip_a", 0, 1, master=True),  # whole-device member: fine
            target("strip_b", 0, 1),  # segment 1 is not designated
            target("strip_b", 0, master=True),  # master on a partial member
            target("strip_c", 0),  # not a member
        ],
    )
    assert [(p.device_id, p.reason) for p in problems] == [
        ("strip_b", "segment_outside_room"),
        ("strip_b", "partial_member"),
        ("strip_c", "device_outside_room"),
    ]
    assert containment_problems(LIVING, [target("strip_b", 2, 0), target("strip_a", 7)]) == []


def test_outside_devices_names_each_device_once():
    assert [p.device_id for p in outside_devices(LIVING, ["x", "strip_a", "x", "y"])] == ["x", "y"]


def test_problem_data_is_bounded_and_carries_the_total():
    problems = outside_devices(LIVING, [f"d{n}" for n in range(MAX_PROBLEMS + 5)])
    data = problem_data(problems)
    assert data["problem_total"] == MAX_PROBLEMS + 5
    assert len(data["problems"]) == MAX_PROBLEMS  # type: ignore[arg-type]
