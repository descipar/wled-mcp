"""Rooms (issue #183): a room is a stored group with ``kind`` ``room``. Pure, no I/O.

Belonging is derived, never stored twice: a controller is in the room whose room-kind group
lists it. At most one room per controller (ISSUE-183-DEC-002); a controller listed by two
rooms is a *conflict* that is reported and refuses the actions that need an unambiguous room,
never resolved silently. Plain groups never take part. This module holds the index, the
conflict report and the containment checks the room tools use before any device I/O.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final

from pydantic import JsonValue

from wled_mcp.groups import Group, Member
from wled_mcp.scenes import ExpandedTarget

MAX_PROBLEMS: Final = 10

CONFLICT_RECONCILE: Final = (
    "Remove the device from one of the rooms with wled_save_group overwrite=true and repeat "
    "the request. Nothing was written."
)
OUTSIDE_RECONCILE: Final = (
    "Name only controllers and segments that belong to the room, or change the room with "
    "wled_save_group overwrite=true. Nothing was written."
)
PARTIAL_RECONCILE: Final = (
    "A master power or brightness change would switch the whole controller. Use a scene or a "
    "zone for a room whose members designate segments. Nothing was written."
)


@dataclass(frozen=True)
class RoomProblem:
    """One reason a room request is refused as a whole; content-free apart from IDs."""

    device_id: str
    reason: str  # room_conflict | partial_member | device_outside_room | segment_outside_room
    message: str
    reconciliation: str

    def view(self) -> dict[str, JsonValue]:
        return {"device_id": self.device_id, "reason": self.reason, "message": self.message}


def rooms_of(groups: Iterable[Group]) -> list[Group]:
    return [group for group in groups if group.kind == "room"]


def room_index(groups: Iterable[Group]) -> dict[str, list[str]]:
    """Device ID -> the sorted IDs of the rooms that list it (plain groups are ignored)."""
    index: dict[str, set[str]] = {}
    for room in rooms_of(groups):
        for member in room.members:
            index.setdefault(member.device, set()).add(room.id)
    return {device: sorted(ids) for device, ids in index.items()}


def room_conflicts(groups: Iterable[Group]) -> list[dict[str, JsonValue]]:
    """Devices listed by more than one room, sorted by device ID."""
    return [
        {"device_id": device, "rooms": [*ids]}
        for device, ids in sorted(room_index(groups).items())
        if len(ids) > 1
    ]


def conflicts_of(room: Group, groups: Iterable[Group]) -> list[RoomProblem]:
    """The conflicts that involve ``room``: its members that another room lists as well."""
    index = room_index(groups)
    problems: list[RoomProblem] = []
    for member in room.members:
        others = [other for other in index.get(member.device, []) if other != room.id]
        if others:
            problems.append(
                RoomProblem(
                    member.device,
                    "room_conflict",
                    f"Device {member.device!r} is in room {room.id!r} and also in room "
                    f"{others[0]!r}; a controller may be in one room only.",
                    CONFLICT_RECONCILE,
                )
            )
    return problems


def save_conflict(room: Group, groups: Iterable[Group]) -> RoomProblem | None:
    """The first member of ``room`` that another stored room already lists (a save is
    refused); the room being replaced is excluded by ID."""
    others = rooms_of(group for group in groups if group.id != room.id)
    for member in room.members:
        for other in others:
            if any(item.device == member.device for item in other.members):
                return RoomProblem(
                    member.device,
                    "room_conflict",
                    f"Device {member.device!r} is already in room {other.id!r}; a controller "
                    "may be in one room only.",
                    CONFLICT_RECONCILE,
                )
    return None


def member_of(room: Group, device: str) -> Member | None:
    return next((member for member in room.members if member.device == device), None)


def partial_members(room: Group) -> list[RoomProblem]:
    """Members that designate segments: a master patch would reach the rest of the device."""
    return [
        RoomProblem(
            member.device,
            "partial_member",
            f"Device {member.device!r} is only partly assigned to room {room.id!r} (segments "
            f"{list(member.segments)}); a master state change would also switch its other "
            "segments.",
            PARTIAL_RECONCILE,
        )
        for member in room.members
        if member.segments is not None
    ]


def outside_devices(room: Group, devices: Iterable[str]) -> list[RoomProblem]:
    """Devices that are not members of ``room``, each once, in the order given."""
    problems: list[RoomProblem] = []
    seen: set[str] = set()
    for device in devices:
        if device in seen or member_of(room, device) is not None:
            continue
        seen.add(device)
        problems.append(
            RoomProblem(
                device,
                "device_outside_room",
                f"Device {device!r} is not a member of room {room.id!r}.",
                OUTSIDE_RECONCILE,
            )
        )
    return problems


def containment_problems(room: Group, targets: Sequence[ExpandedTarget]) -> list[RoomProblem]:
    """Everything an expanded scene touches must lie inside the room and its segments."""
    problems: list[RoomProblem] = []
    for target in targets:
        member = member_of(room, target.device_id)
        if member is None:
            problems.extend(outside_devices(room, [target.device_id]))
            continue
        if member.segments is None:
            continue  # a whole-device member: the controller belongs to the room
        if target.master is not None:
            problems.append(
                RoomProblem(
                    target.device_id,
                    "partial_member",
                    f"Device {target.device_id!r} is only partly assigned to room {room.id!r}; "
                    "the scene sets its master state, which would also switch its other segments.",
                    PARTIAL_RECONCILE,
                )
            )
        written = {segment_id for entry in target.segments for segment_id in entry.ids}
        extra = sorted(written - set(member.segments))
        if extra:
            problems.append(
                RoomProblem(
                    target.device_id,
                    "segment_outside_room",
                    f"The scene writes segment(s) {extra} of device {target.device_id!r}, "
                    f"which room {room.id!r} does not designate.",
                    OUTSIDE_RECONCILE,
                )
            )
    return problems


def problem_data(problems: Sequence[RoomProblem]) -> dict[str, JsonValue]:
    """At most ``MAX_PROBLEMS`` problems plus the total."""
    shown: list[JsonValue] = [problem.view() for problem in problems[:MAX_PROBLEMS]]
    return {"problems": shown, "problem_total": len(problems)}
