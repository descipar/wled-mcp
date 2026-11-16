"""Room tool of issue #183: ``wled_apply_room``.

A room is a stored group with ``kind`` ``room`` (``rooms.py``). The room action applies one
master state patch or one stored scene to the members of a room, through the code path of
``wled_apply_scene`` without change: one ``ExpandedTarget`` per member (or the scene's own
expansion), ``plan_device`` for the fresh read, the access ceiling and the real planners,
``apply_device`` and ``Resources.write_verified`` for the verified write, ``plan_outcome`` and
``apply_outcome`` for the aggregate (so a partial failure is never overall success), strict by
default, at most four devices in flight. Nothing new is written: no write primitive, no
application or verification value, no error code, no room-level lock. Everything that decides
whether the request is allowed (room kind, conflicts, containment) is checked before any device
I/O and refuses the request as a whole. A timed-out or unreadable write is uncertain and is
never retried, replayed or rolled back. Room, scene, group and device names are never logged.
"""

from __future__ import annotations

from collections.abc import Sequence
from functools import partial
from typing import Any, Literal

import anyio
from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from wled_mcp.access import ToolClass
from wled_mcp.client import ClientFailure
from wled_mcp.formats import invalid
from wled_mcp.groups import Group
from wled_mcp.models import DomainError, Outcome
from wled_mcp.resources import Resources
from wled_mcp.rooms import (
    RoomProblem,
    conflicts_of,
    containment_problems,
    partial_members,
    problem_data,
)
from wled_mcp.scene_store import DefinitionStore
from wled_mcp.scene_tools import (
    APPLY_ANNOTATIONS,
    DeviceApply,
    Identifier,
    _local_failed,
    apply_device,
    apply_outcome,
    open_group_store,
    open_scene_store,
    plan_device,
    plan_outcome,
    run_bounded,
)
from wled_mcp.scenes import ExpandedTarget, expand_scene, group_references, parse_master
from wled_mcp.server import Operation


class RoomState(BaseModel):
    """A master patch: power and brightness for the whole controller, never segments."""

    model_config = ConfigDict(extra="forbid", strict=True)
    on: bool | None = Field(default=None, description="Master power.")
    brightness: int | None = Field(default=None, ge=0, le=255, description="Master brightness.")
    transition_ms: int | None = Field(default=None, ge=0, le=65500, description="Transition, ms.")


class ApplyRoomRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    room: Identifier = Field(description="Stored room ID (a group saved with kind=room).")
    state: RoomState | None = Field(
        default=None,
        description="Master patch (on or brightness); exactly one of state or scene_id.",
    )
    scene_id: Identifier | None = Field(
        default=None, description="Stored scene ID; it must lie inside the room."
    )
    mode: Literal["strict", "best_effort"] = Field(
        default="strict",
        description=(
            "strict blocks all targets if any preflight fails; best_effort skips failing targets."
        ),
    )
    dry_run: bool = Field(
        default=False,
        description="Validate and return the plan without changing devices or stored definitions.",
    )

    @model_validator(mode="after")
    def exactly_one(self) -> ApplyRoomRequest:
        if (self.state is None) == (self.scene_id is None):
            raise ValueError("name exactly one of state or scene_id")
        return self


def load_room(store: DefinitionStore[Group], room_id: str) -> tuple[Group, tuple[Group, ...]]:
    """The stored room and every stored group (for conflicts); blocking, run in a thread.

    A plain group or an unusable file is a VALIDATION_ERROR before any device I/O.
    """
    room = store.load(room_id)
    if room.kind != "room":
        raise invalid(
            f"Group {room_id!r} is a group, not a room. Use wled_apply_scene for a stored "
            "scene, or save it with kind=room to make it a room."
        )
    return room, store.list_items().items


def room_refusal(
    name: str,
    room: Group,
    problems: Sequence[RoomProblem],
    *,
    dry_run: bool,
    extra: dict[str, JsonValue] | None = None,
    lead: str = "",
) -> Outcome:
    """A whole-request refusal before any device I/O; the first problem is the error."""
    first = problems[0]
    return Outcome(
        ok=False,
        operation=name,
        device_id=None,
        dry_run=dry_run,
        application="not_attempted",
        verification="not_requested",
        data={
            "room": {"id": room.id, "name": room.name},
            **problem_data(problems),
            **(extra or {}),
        },
        error=DomainError(
            code="VALIDATION_ERROR",
            message=lead + first.message,
            reconciliation=first.reconciliation,
        ),
    )


def build_room_operations(resources: Resources) -> tuple[Operation, ...]:
    data_dir = resources.config.data_dir
    groups = open_group_store(data_dir)
    scenes = open_scene_store(data_dir)

    def read_scene_inputs(scene_id: str) -> tuple[Any, dict[str, Group]]:
        scene = scenes.load(scene_id)
        return scene, {ref: groups.load(ref) for ref in group_references(scene)}

    async def apply_room(arguments: dict[str, Any]) -> Outcome:
        name = "wled_apply_room"
        mode: str = arguments["mode"]
        dry_run: bool = arguments["dry_run"]
        extra: dict[str, JsonValue] = {}
        try:
            master: dict[str, JsonValue] | None = None
            if arguments["state"] is not None:
                given = {k: v for k, v in arguments["state"].items() if v is not None}
                master = parse_master(given, "State")
            room, stored = await anyio.to_thread.run_sync(load_room, groups, arguments["room"])
            conflicts = conflicts_of(room, stored)
            if conflicts:
                return room_refusal(name, room, conflicts, dry_run=dry_run)
            warnings: list[str] = []
            if master is not None:
                problems = partial_members(room)
                targets: tuple[ExpandedTarget, ...] = tuple(
                    ExpandedTarget(
                        member.device, f"room:{room.id}/member:{number}", number, master, ()
                    )
                    for number, member in enumerate(room.members, start=1)
                )
            else:
                scene, referenced = await anyio.to_thread.run_sync(
                    read_scene_inputs, arguments["scene_id"]
                )
                targets = expand_scene(scene, referenced)
                problems = containment_problems(room, targets)
                touched = {target.device_id for target in targets}
                untouched: list[JsonValue] = [
                    member.device for member in room.members if member.device not in touched
                ]
                extra["scene"] = {"id": scene.id, "name": scene.name}
                extra["members_not_targeted"] = untouched
                if untouched:
                    warnings.append(
                        f"{len(untouched)} member(s) of the room are not named by the scene and "
                        "were left unchanged (see data.members_not_targeted)."
                    )
            if problems:
                return room_refusal(name, room, problems, dry_run=dry_run, extra=extra)
        except ClientFailure as failure:
            return _local_failed(name, failure, dry_run=dry_run)
        # Preflight of every device first (fresh reads, name resolution, capability checks and
        # the per-device access ceiling of the class this tool has); nothing is written yet.
        plans = await run_bounded(
            targets, partial(plan_device, resources, tool_class=ToolClass.CONTROL)
        )
        if dry_run:
            return _with_warnings(
                plan_outcome(name, room, mode, plans, label="room", extra=extra), warnings
            )
        passing = [plan for plan in plans if plan.ok]
        blocked = len(passing) < len(plans) if mode == "strict" else not passing
        written: list[DeviceApply] = []
        if not blocked:
            written = await run_bounded(passing, partial(apply_device, resources, name=name))
        return _with_warnings(
            apply_outcome(name, room, mode, plans, written, label="room", extra=extra), warnings
        )

    return (
        Operation(
            name="wled_apply_room",
            tool_class=ToolClass.CONTROL,
            description=(
                "Apply one master state (on, brightness, transition_ms) or one stored scene to "
                "the controllers of a room (a group saved with kind=room: where controllers "
                "are, one room per controller). Changes the live output. Refused as a whole "
                "before any write when the room is a plain group, a controller is in two rooms, "
                "a state meets a member that designates segments, or a scene touches a "
                "controller or segment outside the room. Preflights every member (fresh reads, "
                "access ceiling), then writes each through the verified write path, master "
                "first, then segments. At most four at once. mode strict (default) writes "
                "nothing when any member fails preflight; best_effort skips failing members. "
                "One outcome per device in data.devices; partial failure is never overall "
                "success. Not atomic or synchronized: no rollback or replay, an unverified "
                "write is never retried. dry_run returns the plan and sends no write."
            ),
            request_model=ApplyRoomRequest,
            execute=apply_room,
            annotations=APPLY_ANNOTATIONS,
        ),
    )


def _with_warnings(outcome: Outcome, warnings: Sequence[str]) -> Outcome:
    if not warnings:
        return outcome
    return outcome.model_copy(update={"warnings": [*outcome.warnings, *warnings]})
