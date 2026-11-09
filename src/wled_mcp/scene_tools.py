"""Group and scene tools of issue #17: definitions, the plan and the apply.

``wled_list_groups``/``wled_list_scenes`` (read), ``wled_save_group``/``wled_delete_group``/
``wled_save_scene``/``wled_delete_scene`` (manage; local files only), ``wled_plan_scene``
(read) and ``wled_apply_scene`` (control, the only device-write path of scenes).

The plan uses bounded read-only requests under the existing per-device lock, with at most
four devices in flight, and builds its master and segment plans with the planners of
``wled_set_state`` and ``wled_patch_segments``. The apply preflights every device with the
same plan (plus the per-device access check), then writes each device through
``Resources.write_verified`` (the write engine that guards the tool class and the per-device
ceiling): the master step first, then the segment step, each replanned under the device lock
and verified by readback. A timed-out or unreadable write is uncertain and is never retried,
replayed or compensated, and nothing is rolled back across devices. A local definition
change reports ``application=not_attempted`` because no device write is attempted;
``data.saved``/``data.removed`` state what happened to the file. Scene contents and names
are never logged.
"""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from functools import partial
from typing import Annotated, Any, Final, Literal, Protocol

import anyio
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError, model_validator

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
from wled_mcp.models import Application, DomainError, Outcome, Verification
from wled_mcp.patches import (
    MasterPlan,
    PatchSegmentsRequest,
    SegmentsPlan,
    SetStateRequest,
    build_segment_patch_plan,
    build_set_state_plan,
    matches_segments,
    matches_set_state,
)
from wled_mcp.preset_tools import DESTRUCTIVE, READ_ONLY
from wled_mcp.readmodels import Collector, as_dict, normalize_state
from wled_mcp.resources import OperationContext, Resources
from wled_mcp.scene_store import DefinitionStore, serialize_document
from wled_mcp.scenes import (
    MAX_DOCUMENT_BYTES as MAX_SCENE_BYTES,
)
from wled_mcp.scenes import (
    BindingFailure,
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
# A live write: not read-only, and not destructive (no stored artifact is replaced).
APPLY_ANNOTATIONS: Final = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False
)
APPLY_RECONCILE: Final = (
    "Read the state of the devices listed in data.devices before any new call. Nothing was "
    "retried, replayed, compensated or rolled back; devices that were not attempted were not "
    "touched."
)
APPLY_NOTES: Final = (
    "A scene is not atomic and not synchronized: each device is written and verified "
    "independently (up to four at a time, master state first, then segments), and nothing is "
    "rolled back or compensated across devices.",
    "A write whose outcome could not be verified is never retried; the device entry says "
    "whether the readback differed or could not be read.",
)
PLAN_NOTES: Final = (
    "The plan is read-only and not a reservation: state, catalogs and reachability can change "
    "before an apply, which plans again under each device lock.",
    "A scene is not atomic and not synchronized: each device is planned and written "
    "independently and nothing is rolled back across devices.",
)


class Labeled(Protocol):
    """What the aggregate outcomes name: a scene, or a zone (issue #27)."""

    @property
    def id(self) -> str: ...

    @property
    def name(self) -> str: ...


Identifier = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")]
SegmentId = Annotated[int, Field(strict=True, ge=0, le=MAX_SEGMENT_ID)]


# ----------------------------------------------------------------------------- requests


class ListGroupsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    group_id: Identifier | None = Field(default=None, description="Stored group ID.")


class GroupMember(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    device: Identifier = Field(description="Configured device ID belonging to this group.")
    segments: list[SegmentId] | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_MEMBER_SEGMENTS,
        description=(
            "Explicit segment IDs designated for group-target segment changes; omitted means "
            "none are designated."
        ),
    )


class SaveGroupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    group_id: Identifier = Field(description="Stored group ID.")
    name: str = Field(min_length=1, max_length=MAX_NAME, description="Human-readable group name.")
    members: list[GroupMember] = Field(
        min_length=1,
        max_length=MAX_MEMBERS,
        description="Configured device members with optional explicit segment IDs.",
    )
    overwrite: bool = Field(
        default=False,
        description="Explicitly replace an existing stored definition; defaults to false.",
    )
    dry_run: bool = Field(
        default=False,
        description="Validate and return the plan without changing devices or stored definitions.",
    )


class DeleteGroupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    group_id: Identifier = Field(description="Stored group ID.")
    dry_run: bool = Field(
        default=False,
        description="Validate and return the plan without changing devices or stored definitions.",
    )


class ListScenesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    scene_id: Identifier | None = Field(default=None, description="Stored scene ID.")
    shareable: bool = Field(
        default=False,
        description="Export a portable scene with target references replaced by placeholders.",
    )
    include_targets: bool = Field(
        default=False, description="Keep actual target references in the shareable export."
    )


class TargetRef(BaseModel):
    """What a placeholder stands for: exactly one of a configured device or a stored group."""

    model_config = ConfigDict(extra="forbid", strict=True)
    device: Identifier | None = Field(
        default=None,
        description="Configured device ID; exactly one of device or group is required.",
    )
    group: Identifier | None = Field(
        default=None, description="Stored group ID; exactly one of device or group is required."
    )

    @model_validator(mode="after")
    def exactly_one(self) -> TargetRef:
        if (self.device is None) == (self.group is None):
            raise ValueError("name exactly one of device or group")
        return self


class SaveSceneRequest(BaseModel):
    """A scene document as JSON text (exact duplicate-key detection) or as an object."""

    model_config = ConfigDict(extra="forbid", strict=True)
    scene: str | dict[str, JsonValue] = Field(
        description=(
            "Version 1 wled-mcp.scene document, as an object or JSON text. targets name a "
            "device/group and master fields and/or segments with ids plus supported mutable "
            "fields. Effect/palette names resolve per device during planning."
        ),
        examples=[
            {
                "format": "wled-mcp.scene",
                "format_version": 1,
                "id": "evening",
                "name": "Evening",
                "targets": [
                    {
                        "device": "desk",
                        "segments": [
                            {"ids": [0], "colors": [[255, 96, 16]], "effect_name": "Solid"}
                        ],
                    }
                ],
            }
        ],
    )
    target_map: dict[Identifier, TargetRef] | None = Field(
        default=None,
        max_length=16,
        description=(
            "Map portable target placeholders to exactly one configured device or stored group."
        ),
    )
    overwrite: bool = Field(
        default=False,
        description="Explicitly replace an existing stored definition; defaults to false.",
    )
    dry_run: bool = Field(
        default=False,
        description="Validate and return the plan without changing devices or stored definitions.",
    )


class DeleteSceneRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    scene_id: Identifier = Field(description="Stored scene ID.")
    dry_run: bool = Field(
        default=False,
        description="Validate and return the plan without changing devices or stored definitions.",
    )


class PlanSceneRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    scene_id: Identifier = Field(description="Stored scene ID.")
    mode: Literal["strict", "best_effort"] = Field(
        default="strict",
        description=(
            "strict blocks all targets if any preflight fails; best_effort skips failing targets."
        ),
    )


class ApplySceneRequest(PlanSceneRequest):
    """The plan's arguments plus ``dry_run``, which returns exactly the plan."""

    dry_run: bool = Field(
        default=False,
        description="Validate and return the plan without changing devices or stored definitions.",
    )


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
    # Extra entry data from a target's ``bind`` (a zone's resolution or its problem).
    extra: dict[str, JsonValue] = field(default_factory=dict)

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
        item.update(self.extra)
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
    resources: Resources,
    context: OperationContext,
    target: ExpandedTarget,
    resolved: list[JsonValue],
    warnings: list[str],
) -> list[dict[str, JsonValue]]:
    """Resolve names per device inside the device operation; build the patch list.

    Appends what each name resolved to and the numeric-ID portability warnings.
    """
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
                resolved.append({"segments": affected, "field": key, "name": query, "id": index})
        patches.extend({"id": segment_id, **fields} for segment_id in entry.ids)
    for key in sorted(numeric):
        warnings.append(
            f"A numeric {key}_id is used as given; numeric IDs are specific to a device and "
            f"firmware. Use {key}_name to resolve it per device."
        )
    return patches


async def plan_device(
    resources: Resources, target: ExpandedTarget, tool_class: ToolClass | None = None
) -> DevicePlan:
    """Read-only preflight of one device: reads, name resolution and the real planners.

    Never raises for a device problem and never sends a write; a failure is the device's
    own refusal, reported in the result. With ``tool_class`` (the apply) the device must
    first admit that class (``Resources.require_access``), before any read of it.
    """
    plan = DevicePlan(target)
    try:
        # An unknown device is UNKNOWN_DEVICE before any device I/O, and before the access
        # check (an unconfigured device has no ceiling to read).
        resources.resolve(target.device_id)
        if tool_class is not None:
            resources.require_access(target.device_id, tool_class)
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
            bound = target
            if target.bind is not None:
                binding = target.bind(state_view, capabilities, raw_info, raw_state)
                bound = dataclasses.replace(target, segments=binding.segments)
                plan.extra.update(binding.data)
            patches = await _resolve_segment_patches(
                resources, context, bound, plan.resolved, plan.warnings
            )
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
        if isinstance(failure, BindingFailure):
            plan.extra["problem"] = dict(failure.problem)
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


def _noun(text: str, label: str) -> str:
    return text.replace("A scene", f"A {label}")


def plan_outcome(
    name: str,
    scene: Labeled,
    mode: str,
    plans: Sequence[DevicePlan],
    *,
    dry_run: bool = True,
    label: str = "scene",
    extra: Mapping[str, JsonValue] | None = None,
) -> Outcome:
    """Aggregate a plan. ``ok`` means the scene would write something under ``mode``.

    strict (default): any failing target blocks every device. best_effort: failing targets
    are skipped and the rest would be written. Nothing here sends a write.
    """
    failing = [plan for plan in plans if not plan.ok]
    passing = [plan for plan in plans if plan.ok]
    blocked = bool(failing) if mode == "strict" else not passing
    would_write = [] if blocked else [plan.target.device_id for plan in passing]
    notes = [_noun(note, label) for note in PLAN_NOTES]
    data: dict[str, JsonValue] = {
        label: {"id": scene.id, "name": scene.name},
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
        "notes": [*notes],
        **(extra or {}),
    }
    warnings = [notes[0]]
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


# ------------------------------------------------------------------------------- apply


@dataclass
class StepReport:
    """What one write step (master or segments) of one device reported, unchanged.

    ``application``/``verification``/``error`` are those of ``Resources.write_verified``
    for the step; nothing is reinterpreted.
    """

    step: Literal["master", "segments"]
    application: Application
    verification: Verification
    error: DomainError | None
    data: dict[str, JsonValue] = field(default_factory=dict)

    @property
    def verified(self) -> bool:
        return self.application == "applied" and self.verification == "verified"

    def entry(self) -> dict[str, JsonValue]:
        return {
            "step": self.step,
            "application": self.application,
            "verification": self.verification,
            "ok": self.verified,
            "error": self.error.model_dump(mode="json") if self.error is not None else None,
            **self.data,
        }


@dataclass
class DeviceApply:
    """The independent outcome of one device: its steps and the result they add up to."""

    target: ExpandedTarget
    application: Application = "not_attempted"
    verification: Verification = "not_requested"
    error: DomainError | None = None
    steps: list[StepReport] = field(default_factory=list)
    skipped: str | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.application == "applied" and self.verification == "verified"

    def take(self, step: StepReport) -> None:
        """Adopt a step's result as the device result."""
        self.application, self.verification, self.error = (
            step.application,
            step.verification,
            step.error,
        )

    def entry(self) -> dict[str, JsonValue]:
        return {
            "device_id": self.target.device_id,
            "origin": self.target.origin,
            "target_index": self.target.target_index,
            "application": self.application,
            "verification": self.verification,
            "ok": self.ok,
            "error": self.error.model_dump(mode="json") if self.error is not None else None,
            "step": self.steps[-1].step if self.steps else None,
            "skipped": self.skipped,
            "steps": [step.entry() for step in self.steps],
            "warnings": list(self.warnings),
        }


def _step_data(
    plan: MasterPlan | SegmentsPlan | None, extra: dict[str, JsonValue]
) -> dict[str, JsonValue]:
    data: dict[str, JsonValue] = dict(extra)
    if plan is not None:
        data["plan"] = plan.public
        data["postconditions"] = plan.postconditions
    return data


def _report(
    step: Literal["master", "segments"],
    outcome: Outcome,
    build: Callable[[], dict[str, JsonValue]],
) -> StepReport:
    """The step's result is the engine's outcome, unchanged.

    The write may already have been sent when this runs, so it must not raise: a failure
    while building the report data loses only the data, never the engine's verdict (a
    possibly applied write is never reported as not attempted).
    """
    try:
        data = build()
    except Exception as error:
        LOGGER.warning("scene apply report failure class=%s", type(error).__name__)
        data = {}
    return StepReport(step, outcome.application, outcome.verification, outcome.error, data)


def _refused_step(step: Literal["master", "segments"], message: str) -> StepReport:
    """A step that failed in this module before anything was sent."""
    return StepReport(
        step,
        "not_attempted",
        "not_requested",
        DomainError(code="VALIDATION_ERROR", message=message, reconciliation=PLAN_RECONCILE),
    )


async def _write_master(resources: Resources, target: ExpandedTarget, name: str) -> StepReport:
    """Master state of one device: replan under the lock, one POST, one readback."""
    assert target.master is not None
    box: dict[str, MasterPlan] = {}
    try:
        request = SetStateRequest.model_validate({"device_id": target.device_id, **target.master})
    except ValidationError:
        return _refused_step("master", "The master state is not valid.")

    async def prepare(context: OperationContext) -> dict[str, JsonValue]:
        state_view, _capabilities, _info, _state, _warnings = await _read_state_and_info(context)
        box["plan"] = build_set_state_plan(request, state_view)
        return box["plan"].payload

    def matches(state: JsonValue) -> bool:
        plan = box.get("plan")
        return plan is not None and matches_set_state(plan, state)

    outcome = await resources.write_verified(target.device_id, name, prepare, matches)
    return _report("master", outcome, lambda: _step_data(box.get("plan"), {}))


async def _write_segments(resources: Resources, target: ExpandedTarget, name: str) -> StepReport:
    """Segment state of one device: names resolve against the fresh catalog under the lock."""
    boxed: dict[str, Any] = {}
    resolved: list[JsonValue] = []
    warnings: list[str] = []

    async def prepare(context: OperationContext) -> dict[str, JsonValue]:
        state_view, capabilities, raw_info, raw_state, read_warnings = await _read_state_and_info(
            context
        )
        warnings.extend(read_warnings)
        bound = target
        if target.bind is not None:
            try:
                binding = target.bind(state_view, capabilities, raw_info, raw_state)
            except BindingFailure as failure:
                boxed["problem"] = dict(failure.problem)
                raise
            bound = dataclasses.replace(target, segments=binding.segments)
        try:
            patches = await _resolve_segment_patches(resources, context, bound, resolved, warnings)
        except AmbiguousName as failure:
            boxed["candidates"], boxed["total"] = failure.candidates, failure.total
            raise
        request = PatchSegmentsRequest.model_validate(
            {"device_id": target.device_id, "segments": patches}
        )
        plan = build_segment_patch_plan(request, state_view, capabilities, raw_info, raw_state)
        boxed["plan"] = plan
        warnings.extend(plan.warnings)
        return plan.payload

    def matches(state: JsonValue) -> bool:
        plan: SegmentsPlan | None = boxed.get("plan")
        return plan is not None and matches_segments(plan.expectations, state)

    outcome = await resources.write_verified(target.device_id, name, prepare, matches)

    def build() -> dict[str, JsonValue]:
        extra: dict[str, JsonValue] = {"resolved": resolved, "warnings": list(warnings)}
        if "candidates" in boxed:
            extra["candidates"], extra["candidate_total"] = boxed["candidates"], boxed["total"]
        if "problem" in boxed:
            extra["problem"] = boxed["problem"]
        return _step_data(boxed.get("plan"), extra)

    return _report("segments", outcome, build)


async def apply_device(resources: Resources, plan: DevicePlan, name: str) -> DeviceApply:
    """Write one device: master state first, then segments; never raises, never retries.

    Each step replans against a fresh read under the device lock (the preflight is not a
    reservation) and goes through ``Resources.write_verified``, which guards the tool class
    and the device ceiling, sends one POST and verifies by one readback. The segment step is
    not attempted when the master step is not verified-applied. A step that is not verified
    is the device's result as it stands: no retry, no compensating write.
    """
    target = plan.target
    result = DeviceApply(target)
    dispatching = False
    try:
        master: StepReport | None = None
        if target.master is not None:
            dispatching = True
            master = await _write_master(resources, target, name)
            result.steps.append(master)
            result.take(master)
            if not master.verified:
                if target.segments:
                    result.skipped = (
                        "The segment step was not attempted because the master step was not "
                        "verified."
                    )
                return result
        if target.segments:
            dispatching = True
            segments = await _write_segments(resources, target, name)
            result.steps.append(segments)
            result.take(segments)
            if (
                master is not None
                and not segments.verified
                and segments.application == "not_attempted"
            ):
                # The master step is proven, the segment step was refused before any POST:
                # "proven partial steps, final postcondition not reached".
                result.application, result.verification = "applied", "mismatch"
                result.skipped = (
                    "The master step was applied and verified; the segment step was refused "
                    "before it was sent."
                )
        result.warnings.extend(warning for step in result.steps for warning in _step_warnings(step))
    except Exception as error:  # a bug here must not hide the other devices
        LOGGER.warning("scene apply failure class=%s", type(error).__name__)
        if dispatching and result.steps:
            result.application, result.verification = "unknown", "unknown"
            result.error = DomainError(
                code="WRITE_OUTCOME_UNKNOWN",
                message="Write outcome could not be verified.",
                reconciliation="Perform an explicit read; do not replay the write.",
            )
        elif not result.steps:
            result.take(_refused_step("master", "Applying failed for this device."))
    return result


def _step_warnings(step: StepReport) -> list[str]:
    value = step.data.get("warnings")
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _device_error(device_id: str, error: DomainError) -> DomainError:
    """A device's refusal as the aggregate's error, with the device named."""
    return DomainError(
        code=error.code,
        message=f"Device {device_id!r}: {error.message}",
        read_retryable=error.read_retryable,
        reconciliation=APPLY_RECONCILE,
    )


def _preflight_entry(plan: DevicePlan, reason: str) -> dict[str, JsonValue]:
    """A device that was not written: the preflight refusal (if any) and why it was skipped."""
    item: dict[str, JsonValue] = {
        "device_id": plan.target.device_id,
        "origin": plan.target.origin,
        "target_index": plan.target.target_index,
        "application": "not_attempted",
        "verification": "not_requested",
        "ok": False,
        "error": plan.error.model_dump(mode="json") if plan.error is not None else None,
        "step": None,
        "skipped": reason,
        "steps": [],
        "warnings": list(plan.warnings),
    }
    item.update(plan.extra)  # a zone's resolution or problem; empty for scenes
    if plan.candidates is not None:
        item["candidates"] = plan.candidates
        item["candidate_total"] = plan.candidate_total
    return item


def apply_outcome(
    name: str,
    scene: Labeled,
    mode: str,
    plans: Sequence[DevicePlan],
    results: Sequence[DeviceApply],
    *,
    label: str = "scene",
    extra: Mapping[str, JsonValue] | None = None,
) -> Outcome:
    """Aggregate an apply onto the shared envelope; ``data.devices`` is authoritative.

    No new application or verification value: the aggregate maps onto the existing table.
    Nothing was dispatched to any device -> ``not_attempted/not_requested``; at least one
    device ``unknown`` -> ``unknown/unknown`` + ``WRITE_OUTCOME_UNKNOWN``; every device
    applied and verified -> ``applied/verified``; otherwise some devices were applied and the
    rest were skipped, refused or did not verify -> ``applied/mismatch`` +
    ``VERIFICATION_MISMATCH`` (the "proven partial steps" row). The aggregate never claims
    a state a device did not report.
    """
    by_device = {result.target.device_id: result for result in results}
    entries: list[dict[str, JsonValue]] = []
    for plan in plans:
        result = by_device.get(plan.target.device_id)
        if result is not None:
            entries.append(result.entry())
        elif not plan.ok:
            reason = (
                "Skipped: it failed preflight and the mode is best_effort."
                if mode == "best_effort"
                else "Not written: it failed preflight and the mode is strict, which writes "
                "nothing when any target fails."
            )
            entries.append(_preflight_entry(plan, reason))
        else:
            entries.append(
                _preflight_entry(
                    plan,
                    "Not written: another device failed preflight and the mode is strict, "
                    "which writes nothing when any target fails."
                    if mode == "strict"
                    else "Not written: no device passed preflight.",
                )
            )
    counts = {"verified": 0, "mismatch": 0, "unknown": 0, "not_attempted": 0}
    for item in entries:
        verification = item["verification"]
        key = {"verified": "verified", "mismatch": "mismatch", "unknown": "unknown"}.get(
            str(verification), "not_attempted"
        )
        counts[key] += 1
    notes = [_noun(note, label) for note in APPLY_NOTES]
    data: dict[str, JsonValue] = {
        label: {"id": scene.id, "name": scene.name},
        "mode": mode,
        "max_concurrency": MAX_CONCURRENCY,
        "device_count": len(plans),
        "summary": {"devices": len(plans), **counts},
        "devices": [*entries],
        "notes": [*notes],
        **(extra or {}),
    }
    warnings = [notes[0]]

    def failed(application: Application, verification: Verification, error: DomainError) -> Outcome:
        return Outcome(
            ok=False,
            operation=name,
            device_id=None,
            application=application,
            verification=verification,
            data=data,
            warnings=warnings,
            error=error,
        )

    if any(result.application == "unknown" for result in results):
        unknown = sum(1 for result in results if result.application == "unknown")
        return failed(
            "unknown",
            "unknown",
            DomainError(
                code="WRITE_OUTCOME_UNKNOWN",
                message=(
                    f"The write outcome of {unknown} device(s) could not be established; "
                    "other devices may have been applied. See data.devices."
                ),
                reconciliation=APPLY_RECONCILE,
            ),
        )
    if not any(result.application == "applied" for result in results):
        # Nothing reached any device: the first refusal in expansion order, device named.
        refusals = [
            (
                plan.target.device_id,
                by_device[plan.target.device_id].error
                if plan.target.device_id in by_device
                else plan.error,
            )
            for plan in plans
        ]
        first = next(((device, error) for device, error in refusals if error is not None), None)
        return failed(
            "not_attempted",
            "not_requested",
            _device_error(*first)
            if first is not None
            else DomainError(
                code="VALIDATION_ERROR",
                message="No device was written.",
                reconciliation=APPLY_RECONCILE,
            ),
        )
    if len(results) == len(plans) and all(result.ok for result in results):
        return Outcome(
            ok=True,
            operation=name,
            device_id=None,
            application="applied",
            verification="verified",
            data=data,
            warnings=warnings,
        )
    verified = counts["verified"]
    return failed(
        "applied",
        "mismatch",
        DomainError(
            code="VERIFICATION_MISMATCH",
            message=(
                f"{verified} of {len(plans)} device(s) were applied and verified; the others "
                "were skipped, not attempted or did not verify. See data.devices."
            ),
            reconciliation=APPLY_RECONCILE,
        ),
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

    async def apply_scene(arguments: dict[str, Any]) -> Outcome:
        name = "wled_apply_scene"
        mode: str = arguments["mode"]
        dry_run: bool = arguments["dry_run"]
        try:
            scene = await read_store(scenes.load, arguments["scene_id"])
            expanded = expand_scene(scene, await load_groups(scene))
        except ClientFailure as failure:
            return _local_failed(name, failure, dry_run=dry_run)
        # Preflight of every device first, with the plan's own code plus the per-device
        # access check of the class this tool has. Nothing is written yet.
        plans = await run_bounded(
            expanded, partial(plan_device, resources, tool_class=ToolClass.CONTROL)
        )
        if dry_run:
            return plan_outcome(name, scene, mode, plans)
        passing = [plan for plan in plans if plan.ok]
        blocked = len(passing) < len(plans) if mode == "strict" else not passing
        written: list[DeviceApply] = []
        if not blocked:
            written = await run_bounded(passing, partial(apply_device, resources, name=name))
        return apply_outcome(name, scene, mode, plans, written)

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
                " Use dry_run=true when the requested replacement or deletion is unclear."
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
                " Use dry_run=true when the requested replacement or deletion is unclear."
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
                " Use dry_run=true when the requested replacement or deletion is unclear."
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
                " Use dry_run=true when the requested replacement or deletion is unclear."
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
        Operation(
            name="wled_apply_scene",
            tool_class=ToolClass.CONTROL,
            description=(
                "Apply a stored scene: changes the live output of every target device. Expands "
                "groups, preflights every device with the plan (fresh reads, names resolved per "
                "device, capability checks, the device's access ceiling), then writes each "
                "device through the verified write path: master state first, then segments, "
                "each replanned under the device lock and checked by readback. At most four "
                "devices are written at once, at most 16 per scene. mode strict (default) "
                "writes nothing anywhere when any target fails preflight; best_effort skips "
                "failing devices and writes the rest. The result lists one independent "
                "outcome per device in data.devices. A scene is not atomic and not "
                "synchronized: there is no rollback, compensation or replay, a write that "
                "could not be verified is never retried, and if the call is stopped "
                "(timeout, shutdown) devices not yet started are untouched while writes in "
                "flight may or may not have been applied. dry_run returns exactly the plan "
                "of wled_plan_scene and sends no write."
            ),
            request_model=ApplySceneRequest,
            execute=apply_scene,
            annotations=APPLY_ANNOTATIONS,
        ),
    )
