"""Zone tools of issue #27: ``wled_list_zones``, ``wled_plan_zone`` and ``wled_apply_zone``.

A zone (``zones.py``) is a reviewed, versioned mapping from a physical region to configured
devices and explicit LED ranges, stored as a local file ``<data-dir>/zones/<id>.json`` and
authored outside these tools (OC-27-2). The list tool reads local files only. The plan and
the apply reuse the scene machinery unchanged (TD-27-9): one expanded target per zone part,
``plan_device`` for the fresh read and the real segment planner, ``apply_device`` and
``Resources.write_verified`` for the verified write, strict by default, at most four devices
in flight. What is new is the target's ``bind`` hook: under the device lock, in the plan and
again in the write step, the part is resolved against the device's *existing* active
segments. A zone that does not tile exactly onto segments inside it is refused before any
write, and a layout that changed between preview and write fails the step with
``topology_changed`` and nothing sent. Zone tools never change geometry, never write master
state and never discover or infer anything.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from functools import partial
from typing import Annotated, Any, Literal

import anyio
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from wled_mcp.access import ToolClass
from wled_mcp.client import ClientFailure
from wled_mcp.formats import invalid
from wled_mcp.groups import MAX_DOCUMENT_BYTES as MAX_GROUP_BYTES
from wled_mcp.groups import Group, parse_group
from wled_mcp.models import Outcome
from wled_mcp.preset_tools import READ_ONLY
from wled_mcp.resources import Resources
from wled_mcp.scene_store import DefinitionStore
from wled_mcp.scene_tools import (
    APPLY_ANNOTATIONS,
    MAX_GROUPS,
    DeviceApply,
    DevicePlan,
    _local_failed,
    _local_ok,
    apply_device,
    apply_outcome,
    plan_device,
    plan_outcome,
    run_bounded,
)
from wled_mcp.scenes import (
    ExpandedTarget,
    LiveBinding,
    ResolvedSegments,
    _parse_entry,
)
from wled_mcp.server import Operation
from wled_mcp.zones import (
    MAX_DOCUMENT_BYTES,
    MAX_ZONES,
    Part,
    Zone,
    ZoneLookupFailure,
    ZoneProblem,
    document_warnings,
    find_zone,
    overlapping_zones,
    parse_zone,
    resolve_part,
    zone_document,
    zone_summary,
)

LOGGER = logging.getLogger("wled_mcp.zone_tools")

ZoneRef = Annotated[str, Field(min_length=1, max_length=128)]


# ----------------------------------------------------------------------------- requests


class ListZonesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    zone: ZoneRef | None = None


class PlanZoneRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    zone: ZoneRef
    # One object of segment fields (the scene entry allowlist, no ids, no geometry): every
    # segment inside the zone receives the same fields. Optional for a preview.
    segments: list[dict[str, JsonValue]] | None = Field(default=None, min_length=1, max_length=1)
    mode: Literal["strict", "best_effort"] = "strict"


class ApplyZoneRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    zone: ZoneRef
    segments: list[dict[str, JsonValue]] = Field(min_length=1, max_length=1)
    mode: Literal["strict", "best_effort"] = "strict"
    dry_run: bool = False


# -------------------------------------------------------------------------------- pieces


def _topology_changed(device: str, previous: str) -> ZoneProblem:
    return ZoneProblem(
        "topology_changed",
        f"The device layout changed after the preview ({previous}); nothing was sent. Preview "
        "the zone again.",
        device=device,
    )


def make_binder(
    zone: Zone, part: Part, fields: Mapping[str, JsonValue] | None
) -> Callable[..., LiveBinding]:
    """The ``bind`` hook of one part.

    The first call (the preflight read) records the resolution; a later call (the write
    step, after a fresh read under the device lock) must resolve identically, otherwise the
    step fails ``topology_changed`` before anything is sent.
    """
    expected: list[Any] = []

    def bind(
        state_view: Mapping[str, JsonValue],
        capabilities: Mapping[str, JsonValue],
        raw_info: Mapping[str, JsonValue],
        raw_state: Mapping[str, JsonValue],
    ) -> LiveBinding:
        try:
            resolved = resolve_part(part, state_view, capabilities, raw_info, raw_state)
        except ZoneProblem as problem:
            if expected:
                raise _topology_changed(part.device, problem.reason) from None
            raise
        signature = resolved.signature()
        if not expected:
            expected.append(signature)
        elif expected[0] != signature:
            raise _topology_changed(part.device, "different segments or ranges")
        view = resolved.view()
        view["warnings"] = [*resolved.warnings]
        segments = (ResolvedSegments(resolved.segment_ids, fields),) if fields is not None else ()
        return LiveBinding(segments, {"zone_target": view})

    return bind


def expand_zone(zone: Zone, fields: Mapping[str, JsonValue] | None) -> tuple[ExpandedTarget, ...]:
    """One target per zone part (one device each); segment IDs are bound from the live layout."""
    return tuple(
        ExpandedTarget(
            part.device,
            f"zone:{zone.id}/part:{number}",
            number,
            None,  # master state would touch every LED of the device
            (ResolvedSegments((), fields),) if fields is not None else (),
            bind=make_binder(zone, part, fields),
        )
        for number, part in enumerate(zone.parts, start=1)
    )


def parse_fields(
    segments: Sequence[Mapping[str, JsonValue]] | None,
) -> Mapping[str, JsonValue] | None:
    """Validate the one segment-field object with the scene entry rules; no ids, no geometry."""
    if segments is None:
        return None
    entry = segments[0]
    if "ids" in entry:
        raise invalid(
            "Segment entry: 'ids' is not accepted; the zone decides which segments are changed."
        )
    return _parse_entry(entry, "group", "Segment entry").fields


def _overlapping_groups(plans: Sequence[DevicePlan], groups: Sequence[Group]) -> list[JsonValue]:
    """Stored groups that list a device of the zone with segments the zone resolved to."""
    resolved: dict[str, set[int]] = {}
    for plan in plans:
        target = plan.extra.get("zone_target")
        if isinstance(target, dict) and isinstance(target.get("segment_ids"), list):
            listed = target["segment_ids"]
            assert isinstance(listed, list)
            resolved[plan.target.device_id] = {item for item in listed if isinstance(item, int)}
    found: list[JsonValue] = []
    for group in groups:
        for member in group.members:
            ids = resolved.get(member.device)
            if ids is None:
                continue
            if member.segments is None or ids & set(member.segments):
                found.append(
                    {
                        "group_id": group.id,
                        "device_id": member.device,
                        "segments": list(member.segments) if member.segments else None,
                    }
                )
    return found


# ---------------------------------------------------------------------------------- tools


def build_zone_operations(resources: Resources) -> tuple[Operation, ...]:
    data_dir = resources.config.data_dir
    configured = frozenset(device.id for device in resources.inventory)

    def parse_zone_bytes(raw: bytes) -> Zone:
        return parse_zone(raw)

    def parse_group_bytes(raw: bytes) -> Group:
        return parse_group(raw)

    zones: DefinitionStore[Zone] = DefinitionStore(
        data_dir / "zones",
        "zone",
        parse_zone_bytes,
        lambda item: item.id,
        max_items=MAX_ZONES,
        max_bytes=MAX_DOCUMENT_BYTES,
    )
    groups: DefinitionStore[Group] = DefinitionStore(
        data_dir / "groups",
        "group",
        parse_group_bytes,
        lambda item: item.id,
        max_items=MAX_GROUPS,
        max_bytes=MAX_GROUP_BYTES,
    )

    async def read_store(call: Callable[..., Any], *args: Any) -> Any:
        return await anyio.to_thread.run_sync(call, *args)

    def lookup_failed(name: str, failure: ClientFailure, *, dry_run: bool = False) -> Outcome:
        if isinstance(failure, ZoneLookupFailure) and failure.candidates is not None:
            return Outcome(
                ok=False,
                operation=name,
                device_id=None,
                dry_run=dry_run,
                application="not_attempted",
                verification="not_requested",
                data={"candidates": failure.candidates, "candidate_total": failure.total},
                error=failure.error,
            )
        return _local_failed(name, failure, dry_run=dry_run)

    async def list_zones(arguments: dict[str, Any]) -> Outcome:
        name = "wled_list_zones"
        try:
            listing = await read_store(zones.list_items)
            if arguments["zone"] is not None:
                zone, lookup_warnings = find_zone(listing.items, arguments["zone"])
                return _local_ok(
                    name,
                    {
                        "zone": zone_summary(zone, configured),
                        "document": zone_document(zone),
                        "overlaps_zones": overlapping_zones(zone, listing.items),
                    },
                    warnings=[*lookup_warnings, *listing.warnings],
                )
        except ClientFailure as failure:
            return lookup_failed(name, failure)
        entries: list[JsonValue] = [zone_summary(zone, configured) for zone in listing.items]
        unresolved = [
            f"Zone {zone.id!r} lists a device that is not in the inventory; a plan using it "
            "fails preflight with UNKNOWN_DEVICE."
            for zone in listing.items
            if any(part.device not in configured for part in zone.parts)
        ]
        return _local_ok(
            name,
            {"zones": entries, "count": len(entries), "invalid_count": listing.invalid_count},
            warnings=[*listing.warnings, *document_warnings(listing.items), *unresolved],
        )

    async def prepare(
        arguments: dict[str, Any],
    ) -> tuple[Zone, Mapping[str, JsonValue] | None, tuple[ExpandedTarget, ...], list[str], Any]:
        listing = await read_store(zones.list_items)
        zone, warnings = find_zone(listing.items, arguments["zone"])
        fields = parse_fields(arguments["segments"])
        return zone, fields, expand_zone(zone, fields), warnings, listing.items

    async def extras(
        zone: Zone, others: Sequence[Zone], plans: Sequence[DevicePlan]
    ) -> dict[str, JsonValue]:
        try:
            stored = (await read_store(groups.list_items)).items
        except ClientFailure:
            stored = ()
        return {
            "zone_document": zone_document(zone),
            "overlaps_zones": overlapping_zones(zone, others),
            "overlaps_groups": _overlapping_groups(plans, stored),
            "layout_changes": False,
        }

    def with_warnings(outcome: Outcome, warnings: Sequence[str]) -> Outcome:
        if not warnings:
            return outcome
        return outcome.model_copy(update={"warnings": [*outcome.warnings, *warnings]})

    async def plan_zone(arguments: dict[str, Any]) -> Outcome:
        name = "wled_plan_zone"
        try:
            zone, _fields, targets, warnings, stored = await prepare(arguments)
        except ClientFailure as failure:
            return lookup_failed(name, failure, dry_run=True)
        plans = await run_bounded(targets, partial(plan_device, resources))
        outcome = plan_outcome(
            name,
            zone,
            arguments["mode"],
            plans,
            label="zone",
            extra=await extras(zone, stored, plans),
        )
        return with_warnings(outcome, warnings)

    async def apply_zone(arguments: dict[str, Any]) -> Outcome:
        name = "wled_apply_zone"
        mode: str = arguments["mode"]
        dry_run: bool = arguments["dry_run"]
        try:
            zone, _fields, targets, warnings, stored = await prepare(arguments)
        except ClientFailure as failure:
            return lookup_failed(name, failure, dry_run=dry_run)
        # Preflight of every part first (the plan's own code plus the per-device access
        # check of the class this tool has); nothing is written yet.
        plans = await run_bounded(
            targets, partial(plan_device, resources, tool_class=ToolClass.CONTROL)
        )
        extra = await extras(zone, stored, plans)
        if dry_run:
            return with_warnings(
                plan_outcome(name, zone, mode, plans, label="zone", extra=extra), warnings
            )
        passing = [plan for plan in plans if plan.ok]
        blocked = len(passing) < len(plans) if mode == "strict" else not passing
        written: list[DeviceApply] = []
        if not blocked:
            written = await run_bounded(passing, partial(apply_device, resources, name=name))
        return with_warnings(
            apply_outcome(name, zone, mode, plans, written, label="zone", extra=extra), warnings
        )

    return (
        Operation(
            name="wled_list_zones",
            tool_class=ToolClass.READ,
            description=(
                "List the stored named physical lighting zones (ID, name, devices, number of "
                "LED ranges, whether each device is still configured) with warnings for "
                "ambiguous names and duplicate mappings. An optional zone (ID or name) returns "
                "that zone's stored document and the other zones it overlaps. Zones are "
                "reviewed files in the data directory (format wled-mcp.zone); geometry is "
                "never inferred from names. Reads local files only; no device is contacted. "
                "Read-only."
            ),
            request_model=ListZonesRequest,
            execute=list_zones,
            annotations=READ_ONLY,
        ),
        Operation(
            name="wled_plan_zone",
            tool_class=ToolClass.READ,
            description=(
                "Read-only preview of one zone (ID or unique name): reads the fresh state of "
                "each device of the zone and reports the exact device, segment IDs and LED "
                "ranges in the zone's logical order (flow_reversed marks a reversed span), or "
                "the refusal: stale LED count, segment hint mismatch, a segment crossing the "
                "zone boundary, LEDs no segment covers, an unknown or unreachable device. "
                "Zones use existing active segments only; a refusal says that an explicit "
                "layout change (wled_replace_layout) is required. Optional segments (one "
                "object of segment fields: on, brightness, colors, effect_id or effect_name, "
                "palette_id or palette_name, speed, intensity, cct, custom1-3, check1-3) also "
                "plans the change with the real segment planner. mode strict (default) blocks "
                "every device when one fails. Sends no write and changes no lighting. The "
                "preview is not a reservation. Read-only."
            ),
            request_model=PlanZoneRequest,
            execute=plan_zone,
            annotations=READ_ONLY,
        ),
        Operation(
            name="wled_apply_zone",
            tool_class=ToolClass.CONTROL,
            description=(
                "Apply segment fields (one object: on, brightness, colors, effect_id or "
                "effect_name, palette_id or palette_name, speed, intensity, cct, custom1-3, "
                "check1-3) to exactly the segments inside one zone. Changes the live output "
                "of the zone's devices only: no geometry change, no master state, only "
                "segments fully inside the zone, so no LED outside it is affected. Resolves "
                "the zone against each device's existing segments, preflights every device "
                "(including its access ceiling), then writes each through the verified write "
                "path, replanning under the device lock; a layout that changed since the "
                "preflight fails that device with topology_changed and nothing sent. mode "
                "strict (default) writes nothing anywhere when any device fails preflight; "
                "best_effort skips failing devices. Not atomic and not synchronized: no "
                "rollback or replay, and a write that could not be verified is never retried. "
                "dry_run returns exactly the plan of wled_plan_zone and sends no write."
            ),
            request_model=ApplyZoneRequest,
            execute=apply_zone,
            annotations=APPLY_ANNOTATIONS,
        ),
    )
