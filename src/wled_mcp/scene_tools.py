"""Group and scene tools of issue #17, pull request A: definitions and plan, no device write.

``wled_list_groups``/``wled_list_scenes`` (read), ``wled_save_group``/``wled_delete_group``/
``wled_save_scene``/``wled_delete_scene`` (manage; local files only) and ``wled_plan_scene``
(read). Nothing in this module sends a device write: the plan uses bounded read-only
requests under the existing per-device lock, with at most four devices in flight, and builds
its master and segment plans with the planners of ``wled_set_state`` and
``wled_patch_segments``. A local definition change reports ``application=not_attempted``
because no device write is attempted; ``data.saved``/``data.removed`` state what happened to
the file. Scene contents and names are never logged.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from functools import partial
from typing import Annotated, Any, Final, Literal

import anyio
from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from wled_mcp.access import ToolClass
from wled_mcp.catalogs import AmbiguousName, CatalogView, Kind, load_catalog, resolve_name
from wled_mcp.client import ClientFailure, Endpoint
from wled_mcp.formats import invalid
from wled_mcp.groups import MAX_DOCUMENT_BYTES as MAX_GROUP_BYTES
from wled_mcp.groups import (
    MAX_MEMBER_SEGMENTS,
    MAX_MEMBERS,
    MAX_NAME,
    MAX_SEGMENT_ID,
    Group,
    group_document,
    member_views,
    parse_group,
)
from wled_mcp.models import DomainError, Outcome
from wled_mcp.patches import (
    PatchSegmentsRequest,
    SetStateRequest,
    build_segment_patch_plan,
    build_set_state_plan,
)
from wled_mcp.preset_tools import DESTRUCTIVE, READ_ONLY
from wled_mcp.readmodels import Collector, as_dict, normalize_state
from wled_mcp.resources import OperationContext, Resources
from wled_mcp.scene_store import DefinitionStore, serialize_document
from wled_mcp.scenes import (
    MAX_DOCUMENT_BYTES as MAX_SCENE_BYTES,
)
from wled_mcp.scenes import (
    ExpandedTarget,
    Scene,
    TargetMapping,
    apply_target_map,
    check_references,
    expand_scene,
    export_scene,
    group_references,
    inventory_tokens,
    parse_scene,
    scene_document,
    scene_summary,
)
from wled_mcp.server import Operation

LOGGER = logging.getLogger("wled_mcp.scene_tools")

# Fixed limits of the request, not configuration (TD-17-9).
MAX_CONCURRENCY: Final = 4
MAX_GROUPS: Final = 100
MAX_SCENES: Final = 500

PLAN_RECONCILE: Final = (
    "Correct the scene, its groups or the device as listed in data.targets; nothing was written."
)
PLAN_NOTES: Final = (
    "The plan is read-only and not a reservation: state, catalogs and reachability can change "
    "before an apply, which plans again under each device lock.",
    "A scene is not atomic and not synchronized: each device is planned and written "
    "independently and nothing is rolled back across devices.",
)

Identifier = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")]
SegmentId = Annotated[int, Field(strict=True, ge=0, le=MAX_SEGMENT_ID)]


# ----------------------------------------------------------------------------- requests


class ListGroupsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    group_id: Identifier | None = None


class GroupMember(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    device: Identifier
    segments: list[SegmentId] | None = Field(
        default=None, min_length=1, max_length=MAX_MEMBER_SEGMENTS
    )


class SaveGroupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    group_id: Identifier
    name: str = Field(min_length=1, max_length=MAX_NAME)
    members: list[GroupMember] = Field(min_length=1, max_length=MAX_MEMBERS)
    overwrite: bool = False
    dry_run: bool = False


class DeleteGroupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    group_id: Identifier
    dry_run: bool = False


class ListScenesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    scene_id: Identifier | None = None
    shareable: bool = False
    include_targets: bool = False


class TargetRef(BaseModel):
    """What a placeholder stands for: exactly one of a configured device or a stored group."""

    model_config = ConfigDict(extra="forbid", strict=True)
    device: Identifier | None = None
    group: Identifier | None = None

    @model_validator(mode="after")
    def exactly_one(self) -> TargetRef:
        if (self.device is None) == (self.group is None):
            raise ValueError("name exactly one of device or group")
        return self


class SaveSceneRequest(BaseModel):
    """A scene document as JSON text (exact duplicate-key detection) or as an object."""

    model_config = ConfigDict(extra="forbid", strict=True)
    scene: str | dict[str, JsonValue]
    target_map: dict[Identifier, TargetRef] | None = Field(default=None, max_length=16)
    overwrite: bool = False
    dry_run: bool = False


class DeleteSceneRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    scene_id: Identifier
    dry_run: bool = False


class PlanSceneRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    scene_id: Identifier
    mode: Literal["strict", "best_effort"] = "strict"


# ------------------------------------------------------------------------------ outcomes


def _local_ok(
    name: str, data: dict[str, JsonValue], *, dry_run: bool = False, warnings: Sequence[str] = ()
) -> Outcome:
    """A definition read or change: no device was contacted for a write."""
    return Outcome(
        ok=True,
        operation=name,
        device_id=None,
        dry_run=dry_run,
        application="not_attempted",
        verification="not_requested",
        data=data,
        warnings=list(warnings),
    )


def _local_failed(name: str, failure: ClientFailure, *, dry_run: bool = False) -> Outcome:
    return Outcome(
        ok=False,
        operation=name,
        device_id=None,
        dry_run=dry_run,
        application="not_attempted",
        verification="not_requested",
        error=failure.error,
    )


# ------------------------------------------------------------------------------ planning


async def run_bounded[A, R](
    items: Sequence[A], worker: Callable[[A], Awaitable[R]], limit: int = MAX_CONCURRENCY
) -> list[R]:
    """Run ``worker`` over ``items`` with at most ``limit`` in flight; results keep input order.

    The worker must handle its own failures: an exception would cancel the other devices.
    """
    results: list[R | None] = [None] * len(items)
    limiter = anyio.Semaphore(limit)

    async def run(index: int, item: A) -> None:
        async with limiter:
            results[index] = await worker(item)

    async with anyio.create_task_group() as group:
        for index, item in enumerate(items):
            group.start_soon(run, index, item)
    return [result for result in results if result is not None]  # every slot is filled


@dataclass
class DevicePlan:
    """The preflight result of one expanded device."""

    target: ExpandedTarget
    error: DomainError | None = None
    candidates: list[JsonValue] | None = None
    candidate_total: int | None = None
    reachable: bool | None = None
    master: dict[str, JsonValue] | None = None
    segments: dict[str, JsonValue] | None = None
    resolved: list[JsonValue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.error is None

    def entry(self) -> dict[str, JsonValue]:
        item: dict[str, JsonValue] = {
            "device_id": self.target.device_id,
            "origin": self.target.origin,
            "target_index": self.target.target_index,
            "preflight": "ok" if self.ok else "failed",
            "reachable": self.reachable,
            "error": self.error.model_dump(mode="json") if self.error is not None else None,
            "master": self.master,
            "segments": self.segments,
            "resolved": self.resolved,
            "warnings": list(self.warnings),
        }
        if self.candidates is not None:
            item["candidates"] = self.candidates
            item["candidate_total"] = self.candidate_total
        return item


async def _read_state_and_info(
    context: OperationContext,
) -> tuple[
    dict[str, JsonValue],
    dict[str, JsonValue],
    dict[str, JsonValue],
    dict[str, JsonValue],
    list[str],
]:
    """Fresh ``/json/state`` + ``/json/info`` read under the active lock and deadline."""
    state = await context.read(Endpoint.STATE)
    info = await context.read(Endpoint.INFO)
    collector = Collector()
    view, capabilities, _firmware, _unknown = normalize_state(state, info, collector)
    return view, capabilities, as_dict(info), as_dict(state), collector.result()


_CATALOGS: Final[tuple[tuple[str, Kind], ...]] = (("effect", "effects"), ("palette", "palettes"))


async def _resolve_segment_patches(
    resources: Resources, context: OperationContext, target: ExpandedTarget, plan: DevicePlan
) -> list[dict[str, JsonValue]]:
    """Resolve names per device inside the device operation; build the patch list."""
    views: dict[Kind, CatalogView] = {}
    numeric: set[str] = set()
    patches: list[dict[str, JsonValue]] = []
    for entry in target.segments:
        fields: dict[str, JsonValue] = dict(entry.fields)
        for key, kind in _CATALOGS:
            name_key, id_key = f"{key}_name", f"{key}_id"
            if id_key in fields:
                numeric.add(key)
            if name_key in fields:
                query = fields.pop(name_key)
                assert isinstance(query, str)
                if kind not in views:
                    views[kind] = await load_catalog(context, resources.metadata_cache, kind)
                index = resolve_name(views[kind].entry, kind, query)
                fields[id_key] = index
                affected: list[JsonValue] = [*entry.ids]
                plan.resolved.append(
                    {"segments": affected, "field": key, "name": query, "id": index}
                )
        patches.extend({"id": segment_id, **fields} for segment_id in entry.ids)
    for key in sorted(numeric):
        plan.warnings.append(
            f"A numeric {key}_id is used as given; numeric IDs are specific to a device and "
            f"firmware. Use {key}_name to resolve it per device."
        )
    return patches


async def plan_device(resources: Resources, target: ExpandedTarget) -> DevicePlan:
    """Read-only preflight of one device: reads, name resolution and the real planners.

    Never raises for a device problem and never sends a write; a failure is the device's
    own refusal, reported in the result.
    """
    plan = DevicePlan(target)
    try:
        # An unknown device is UNKNOWN_DEVICE from `operation`, before any device I/O.
        async with resources.operation(target.device_id) as context:
            (
                state_view,
                capabilities,
                raw_info,
                raw_state,
                read_warnings,
            ) = await _read_state_and_info(context)
            plan.reachable = True
            plan.warnings.extend(read_warnings)
            patches = await _resolve_segment_patches(resources, context, target, plan)
        if target.master is not None:
            master_request = SetStateRequest.model_validate(
                {"device_id": target.device_id, **target.master}
            )
            master = build_set_state_plan(master_request, state_view)
            plan.master = {
                "plan": master.public,
                "payload": master.payload,
                "postconditions": master.postconditions,
            }
        if patches:
            segment_request = PatchSegmentsRequest.model_validate(
                {"device_id": target.device_id, "segments": patches}
            )
            segments = build_segment_patch_plan(
                segment_request, state_view, capabilities, raw_info, raw_state
            )
            plan.segments = {
                "plan": segments.public,
                "payload": segments.payload,
                "postconditions": segments.postconditions,
            }
            plan.warnings.extend(segments.warnings)
    except AmbiguousName as failure:
        plan.error = failure.error
        plan.candidates = failure.candidates
        plan.candidate_total = failure.total
    except ClientFailure as failure:
        plan.error = failure.error
        if failure.error.code in {"UNREACHABLE", "TIMEOUT"}:
            plan.reachable = False
    except Exception as error:  # a planner bug must not hide the other devices
        LOGGER.warning("scene plan failure class=%s", type(error).__name__)
        plan.error = DomainError(
            code="VALIDATION_ERROR",
            message="Planning failed for this device.",
            reconciliation=PLAN_RECONCILE,
        )
    return plan


def _prefixed(plan: DevicePlan) -> DomainError:
    """The refusal of the first failing device, with the device named."""
    assert plan.error is not None
    return DomainError(
        code=plan.error.code,
        message=f"Device {plan.target.device_id!r}: {plan.error.message}",
        read_retryable=plan.error.read_retryable,
        reconciliation=PLAN_RECONCILE,
    )


def plan_outcome(
    name: str, scene: Scene, mode: str, plans: Sequence[DevicePlan], *, dry_run: bool = True
) -> Outcome:
    """Aggregate a plan. ``ok`` means the scene would write something under ``mode``.

    strict (default): any failing target blocks every device. best_effort: failing targets
    are skipped and the rest would be written. Nothing here sends a write.
    """
    failing = [plan for plan in plans if not plan.ok]
    passing = [plan for plan in plans if plan.ok]
    blocked = bool(failing) if mode == "strict" else not passing
    would_write = [] if blocked else [plan.target.device_id for plan in passing]
    data: dict[str, JsonValue] = {
        "scene": {"id": scene.id, "name": scene.name},
        "mode": mode,
        "max_concurrency": MAX_CONCURRENCY,
        "device_count": len(plans),
        "summary": {
            "devices": len(plans),
            "preflight_ok": len(passing),
            "preflight_failed": len(failing),
        },
        "would_write": list(would_write),
        "skipped": [plan.target.device_id for plan in failing] if not blocked else [],
        "targets": [plan.entry() for plan in plans],
        "notes": list(PLAN_NOTES),
    }
    warnings = [PLAN_NOTES[0]]
    if blocked:
        return Outcome(
            ok=False,
            operation=name,
            device_id=None,
            dry_run=dry_run,
            application="not_attempted",
            verification="not_requested",
            data=data,
            warnings=warnings,
            error=_prefixed(failing[0]),
        )
    return Outcome(
        ok=True,
        operation=name,
        device_id=None,
        dry_run=dry_run,
        application="not_attempted",
        verification="not_requested",
        data=data,
        warnings=warnings,
    )


# -------------------------------------------------------------------------------- tools


def build_scene_operations(resources: Resources) -> tuple[Operation, ...]:
    data_dir = resources.config.data_dir
    configured = frozenset(device.id for device in resources.inventory)

    def parse_group_bytes(raw: bytes) -> Group:
        return parse_group(raw)

    def parse_scene_bytes(raw: bytes) -> Scene:
        return parse_scene(raw, allow_placeholders=False)

    groups: DefinitionStore[Group] = DefinitionStore(
        data_dir / "groups",
        "group",
        parse_group_bytes,
        lambda item: item.id,
        max_items=MAX_GROUPS,
        max_bytes=MAX_GROUP_BYTES,
    )
    scenes: DefinitionStore[Scene] = DefinitionStore(
        data_dir / "scenes",
        "scene",
        parse_scene_bytes,
        lambda item: item.id,
        max_items=MAX_SCENES,
        max_bytes=MAX_SCENE_BYTES,
    )

    async def read_store(call: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return await anyio.to_thread.run_sync(partial(call, *args, **kwargs))

    async def write_store(call: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        # Shielded: a cancelled call must not leave a store write half-finished.
        with anyio.CancelScope(shield=True):
            return await anyio.to_thread.run_sync(partial(call, *args, **kwargs))

    def group_entry(group: Group) -> dict[str, JsonValue]:
        members = member_views(group, configured)
        unresolved = sum(
            1 for item in members if isinstance(item, dict) and not item["in_inventory"]
        )
        return {
            "id": group.id,
            "name": group.name,
            "member_count": len(group.members),
            "unresolved_members": unresolved,
            "members": members,
        }

    def unresolved_warnings(entries: Sequence[dict[str, JsonValue]]) -> list[str]:
        return [
            f"Group {entry['id']!r} lists {entry['unresolved_members']} device(s) that are not "
            "in the inventory; a plan using them fails preflight with UNKNOWN_DEVICE."
            for entry in entries
            if entry["unresolved_members"]
        ]

    # ------------------------------------------------------------------ groups

    async def list_groups(arguments: dict[str, Any]) -> Outcome:
        name = "wled_list_groups"
        try:
            if arguments["group_id"] is not None:
                group = await read_store(groups.load, arguments["group_id"])
                entry = group_entry(group)
                return _local_ok(
                    name,
                    {"group": entry, "document": group_document(group)},
                    warnings=unresolved_warnings([entry]),
                )
            listing = await read_store(groups.list_items)
        except ClientFailure as failure:
            return _local_failed(name, failure)
        entries = [group_entry(group) for group in listing.items]
        shown: list[JsonValue] = [*entries]
        return _local_ok(
            name,
            {
                "groups": shown,
                "count": len(entries),
                "invalid_count": listing.invalid_count,
            },
            warnings=[*listing.warnings, *unresolved_warnings(entries)],
        )

    async def save_group(arguments: dict[str, Any]) -> Outcome:
        name = "wled_save_group"
        dry_run: bool = arguments["dry_run"]
        try:
            members: list[JsonValue] = []
            for member in arguments["members"]:
                item: dict[str, JsonValue] = {"device": member["device"]}
                if member["segments"] is not None:
                    item["segments"] = list(member["segments"])
                members.append(item)
            document: dict[str, JsonValue] = {
                "format": "wled-mcp.group",
                "format_version": 1,
                "id": arguments["group_id"],
                "name": arguments["name"],
                "members": members,
            }
            group = parse_group(document)
            for position, member_ in enumerate(group.members, start=1):
                if member_.device not in configured:
                    raise invalid(
                        f"Member {position} names device {member_.device!r}, which is not "
                        "configured."
                    )
            body = serialize_document(group_document(group), "group document", MAX_GROUP_BYTES)
            result = await write_store(
                groups.save, group, body, overwrite=arguments["overwrite"], dry_run=dry_run
            )
        except ClientFailure as failure:
            return _local_failed(name, failure, dry_run=dry_run)
        previous = group_document(result.replaced) if result.replaced is not None else None
        return _local_ok(
            name,
            {"group": group_entry(group), "saved": result.stored, "replaced": previous},
            dry_run=dry_run,
        )

    async def delete_group(arguments: dict[str, Any]) -> Outcome:
        name = "wled_delete_group"
        dry_run: bool = arguments["dry_run"]
        try:
            group = await write_store(groups.delete, arguments["group_id"], dry_run=dry_run)
        except ClientFailure as failure:
            return _local_failed(name, failure, dry_run=dry_run)
        return _local_ok(
            name,
            {"removed": not dry_run, "deleted": group_document(group)},
            dry_run=dry_run,
            warnings=["Scenes that name this group fail their plan until it is stored again."],
        )

    # ------------------------------------------------------------------ scenes

    async def list_scenes(arguments: dict[str, Any]) -> Outcome:
        name = "wled_list_scenes"
        scene_id, shareable, include_targets = (
            arguments["scene_id"],
            arguments["shareable"],
            arguments["include_targets"],
        )
        try:
            if (shareable or include_targets) and scene_id is None:
                raise invalid("shareable and include_targets need a scene_id.")
            if include_targets and not shareable:
                raise invalid("include_targets applies to a shareable export only.")
            if scene_id is not None:
                scene = await read_store(scenes.load, scene_id)
                if not shareable:
                    return _local_ok(
                        name, {"scene": scene_summary(scene), "document": scene_document(scene)}
                    )
                shared = export_scene(
                    scene,
                    include_targets=include_targets,
                    tokens=inventory_tokens(resources.inventory),
                )
                warning = (
                    "The document keeps device and group references of this installation."
                    if include_targets
                    else "Device and group references are placeholders; map them with target_map."
                )
                return _local_ok(
                    name,
                    {"scene": scene_summary(scene), "document": scene_document(shared)},
                    warnings=[warning],
                )
            listing = await read_store(scenes.list_items)
        except ClientFailure as failure:
            return _local_failed(name, failure)
        entries: list[JsonValue] = []
        for scene in listing.items:
            summary = scene_summary(scene)
            summary["references"] = [{target.kind: target.ref} for target in scene.targets]
            entries.append(summary)
        return _local_ok(
            name,
            {"scenes": entries, "count": len(entries), "invalid_count": listing.invalid_count},
            warnings=list(listing.warnings),
        )

    async def stored_group_ids() -> frozenset[str]:
        listing = await read_store(groups.list_items)
        return frozenset(group.id for group in listing.items)

    async def load_groups(scene: Scene) -> dict[str, Group]:
        return {
            group_id: await read_store(groups.load, group_id)
            for group_id in group_references(scene)
        }

    async def save_scene(arguments: dict[str, Any]) -> Outcome:
        name = "wled_save_scene"
        dry_run: bool = arguments["dry_run"]
        target_map = arguments["target_map"]
        try:
            scene = parse_scene(arguments["scene"], allow_placeholders=True)
            known_groups = (
                await stored_group_ids()
                if any(target.kind == "group" for target in scene.targets)
                else frozenset()
            )
            if scene.placeholders is not None:
                if target_map is None:
                    raise invalid(
                        "The scene carries placeholders; supply target_map with an entry for each."
                    )
                mapping = {
                    key: TargetMapping(
                        "device" if value["device"] is not None else "group",
                        value["device"] if value["device"] is not None else value["group"],
                    )
                    for key, value in target_map.items()
                }
                scene = apply_target_map(scene, mapping, devices=configured, groups=known_groups)
            else:
                if target_map is not None:
                    raise invalid("target_map applies to a scene with placeholders only.")
                check_references(scene, devices=configured, groups=known_groups)
            # The same expansion a plan performs, against the groups stored now.
            expand_scene(scene, await load_groups(scene))
            body = serialize_document(scene_document(scene), "scene document", MAX_SCENE_BYTES)
            result = await write_store(
                scenes.save, scene, body, overwrite=arguments["overwrite"], dry_run=dry_run
            )
        except ClientFailure as failure:
            return _local_failed(name, failure, dry_run=dry_run)
        previous = scene_document(result.replaced) if result.replaced is not None else None
        return _local_ok(
            name,
            {"scene": scene_summary(scene), "saved": result.stored, "replaced": previous},
            dry_run=dry_run,
        )

    async def delete_scene(arguments: dict[str, Any]) -> Outcome:
        name = "wled_delete_scene"
        dry_run: bool = arguments["dry_run"]
        try:
            scene = await write_store(scenes.delete, arguments["scene_id"], dry_run=dry_run)
        except ClientFailure as failure:
            return _local_failed(name, failure, dry_run=dry_run)
        return _local_ok(
            name,
            {"removed": not dry_run, "deleted": scene_document(scene)},
            dry_run=dry_run,
        )

    async def plan_scene(arguments: dict[str, Any]) -> Outcome:
        name = "wled_plan_scene"
        mode: str = arguments["mode"]
        try:
            scene = await read_store(scenes.load, arguments["scene_id"])
            expanded = expand_scene(scene, await load_groups(scene))
        except ClientFailure as failure:
            return _local_failed(name, failure, dry_run=True)
        plans = await run_bounded(expanded, partial(plan_device, resources))
        return plan_outcome(name, scene, mode, plans)

    return (
        Operation(
            name="wled_list_groups",
            tool_class=ToolClass.READ,
            description=(
                "List the stored device groups with their exact member expansion (device ID, "
                "designated segment IDs and whether the device is still configured). An "
                "optional group_id returns that group with its stored document. Reads the "
                "local data directory only; no device is contacted and nothing is discovered. "
                "Read-only."
            ),
            request_model=ListGroupsRequest,
            execute=list_groups,
            annotations=READ_ONLY,
        ),
        Operation(
            name="wled_save_group",
            tool_class=ToolClass.MANAGE,
            description=(
                "Create or replace a named group of configured devices with optional explicit "
                "segment IDs per member (never 'all'). Stored as a local file in the data "
                "directory; replacing an existing group needs overwrite=true and returns the "
                "previous document. Members must be configured devices. No device is "
                "contacted. dry_run validates and reports without writing."
            ),
            request_model=SaveGroupRequest,
            execute=save_group,
            annotations=DESTRUCTIVE,
        ),
        Operation(
            name="wled_delete_group",
            tool_class=ToolClass.MANAGE,
            description=(
                "Delete one stored group file and return its document. Scenes that name the "
                "group fail their plan until it is stored again. No device is contacted. "
                "dry_run reports without deleting."
            ),
            request_model=DeleteGroupRequest,
            execute=delete_group,
            annotations=DESTRUCTIVE,
        ),
        Operation(
            name="wled_list_scenes",
            tool_class=ToolClass.READ,
            description=(
                "List the stored scenes (ID, name, target count and references). An optional "
                "scene_id returns that scene's document; shareable=true returns the portable "
                "export with device and group references replaced by placeholders (or kept "
                "with include_targets=true) and refuses free text that contains a configured "
                "device host. Reads the local data directory only; no device is contacted. "
                "Read-only."
            ),
            request_model=ListScenesRequest,
            execute=list_scenes,
            annotations=READ_ONLY,
        ),
        Operation(
            name="wled_save_scene",
            tool_class=ToolClass.MANAGE,
            description=(
                "Create or replace a scene from a document (JSON text or object, format "
                "wled-mcp.scene version 1): per target a device or stored group, an optional "
                "master (on, brightness, transition_ms) and segment entries with explicit IDs "
                "and the settable fields (on, brightness, colors, effect_id or effect_name, "
                "palette_id or palette_name, speed, intensity, cct, custom1-3, check1-3). "
                "Effect and palette names resolve per device at plan time; a numeric ID is not "
                "portable. A shared document with placeholders needs target_map. Stored as a "
                "local file; replacing needs overwrite=true. No device is contacted and no "
                "lighting changes. dry_run validates without writing."
            ),
            request_model=SaveSceneRequest,
            execute=save_scene,
            annotations=DESTRUCTIVE,
        ),
        Operation(
            name="wled_delete_scene",
            tool_class=ToolClass.MANAGE,
            description=(
                "Delete one stored scene file and return its document. No device is contacted "
                "and lighting is unchanged. dry_run reports without deleting."
            ),
            request_model=DeleteSceneRequest,
            execute=delete_scene,
            annotations=DESTRUCTIVE,
        ),
        Operation(
            name="wled_plan_scene",
            tool_class=ToolClass.READ,
            description=(
                "Dry-run plan of a stored scene. Expands groups to the exact device and "
                "segment targets, then reads fresh state, effect/palette catalogs and "
                "capabilities of each target device (bounded, at most four devices at once) "
                "and reports per device whether it passes preflight, with the real master and "
                "segment plans, names resolved to IDs per device and refusals (unreachable "
                "device, unknown or ambiguous name, capability mismatch, device not "
                "configured). mode strict (default) blocks every device when one fails; "
                "best_effort skips failing devices. Sends no write to any device and changes "
                "no lighting. The plan is not a reservation. Read-only."
            ),
            request_model=PlanSceneRequest,
            execute=plan_scene,
            annotations=READ_ONLY,
        ),
    )
