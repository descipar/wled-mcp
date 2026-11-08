"""Preset workflow tools of issue #18: snapshot listing, restore, supplied-state save,
playlist authoring and (through ``bundle_tools``) bundle export and import.

The single-entry writers use the single-entry routes of ``preset_writes`` on the shared
``Resources.write_polled`` engine: planned and rechecked inside the device lock, a
snapshot of an occupied destination first, exactly one POST, a ``/presets.json``
readback verdict and no replay. Their live effect is stated in the description, the
dry-run plan and the result (ISSUE-18-DEC-001).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import partial
from typing import Annotated, Any

import anyio
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from wled_mcp.access import ToolClass
from wled_mcp.backups import Firmware, Snapshot
from wled_mcp.client import ClientFailure, Endpoint
from wled_mcp.models import Outcome
from wled_mcp.playlists import SavePlaylistRequest, playback_notes, playlist_object
from wled_mcp.preset_writes import (
    WRITE_RECONCILE,
    Destination,
    Route,
    SuppliedState,
    check_playlist_entry,
    check_playlist_members,
    entry_verdict,
    expected_entry,
    live_before,
    live_effect,
    plan_destination,
    playback_warnings,
    postconditions,
    refuse_running_playlist,
    route_payload,
    secure_destination,
    state_object,
    validate_supplied_state,
)
from wled_mcp.presets import (
    DeviceId,
    PresetId,
    PresetStore,
    classify,
    entry_name,
    json_equal,
    parse_store,
    validate_preset_name,
)
from wled_mcp.readmodels import Collector, as_dict, normalize_state, read_identity
from wled_mcp.resources import OperationContext, PolledWrite, Resources
from wled_mcp.server import Operation

BackupId = Annotated[str, Field(min_length=1, max_length=64)]

READ_ONLY = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)
# Storage writers replace or create a persistent entry and change the live output. The
# hint is advisory; authorization belongs to the MCP host/client.
DESTRUCTIVE = ToolAnnotations(
    read_only_hint=False, destructive_hint=True, idempotent_hint=False, open_world_hint=False
)


class ListSnapshotsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    device_id: DeviceId
    preset_id: PresetId | None = None


class RestorePresetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    device_id: DeviceId
    backup_id: BackupId
    preset_id: PresetId | None = None
    overwrite: bool = False
    dry_run: bool = False


class StorePresetRequest(BaseModel):
    """Store a supplied, validated light-state object; the save applies it live first."""

    model_config = ConfigDict(extra="forbid", strict=True)
    device_id: DeviceId
    name: str
    state: SuppliedState
    preset_id: PresetId | None = None
    overwrite: bool = False
    dry_run: bool = False

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        return validate_preset_name(value)

    @model_validator(mode="after")
    def overwrite_needs_explicit_id(self) -> StorePresetRequest:
        if self.overwrite and self.preset_id is None:
            raise ValueError("overwrite=true requires an explicit preset_id")
        return self


def _not_attempted(name: str, device_id: str | None, failure: ClientFailure) -> Outcome:
    return Outcome(
        ok=False,
        operation=name,
        device_id=device_id,
        application="not_attempted",
        verification="not_requested",
        error=failure.error,
    )


async def _read_store(context: OperationContext) -> PresetStore:
    return parse_store(as_dict(await context.read(Endpoint.PRESETS)))


def _firmware(info: JsonValue) -> Firmware:
    identity = read_identity(info)
    return Firmware(identity.version, identity.build_id)


@dataclass
class WritePlan:
    """Everything one single-entry write needs; built inside the device lock."""

    route: Route
    entry: dict[str, JsonValue]
    destination: Destination
    before: dict[str, JsonValue]
    warnings: list[str]
    details: dict[str, JsonValue]


Planner = Callable[[OperationContext, bool], Awaitable[WritePlan]]


def build_preset_workflow_operations(resources: Resources) -> tuple[Operation, ...]:
    """Issue #18 tools in registry order: list snapshots, restore, store, save playlist,
    export, import."""
    from wled_mcp.bundle_tools import build_bundle_operations  # imports this module

    def known(device_id: str) -> str | None:
        return device_id if any(d.id == device_id for d in resources.inventory) else None

    # ------------------------------------------------------------- shared writing

    def plan_data(plan: WritePlan) -> dict[str, JsonValue]:
        destination = plan.destination
        return {
            "preset_id": destination.preset_id,
            "allocated": destination.allocated,
            "route": plan.route,
            "live_effect": live_effect(plan.route),
            "previous_lighting_restored": False,
            "will_overwrite": destination.existing is not None,
            "existing_type": destination.existing_type,
            "live_before": plan.before,
            **plan.details,
        }

    async def dry_run(name: str, device_id: str, planner: Planner) -> Outcome:
        try:
            async with resources.operation(device_id) as context:
                plan = await planner(context, False)
            advisory: dict[str, JsonValue] = (
                await anyio.to_thread.run_sync(resources.backups.plan_backup, device_id)
                if plan.destination.existing is not None
                else {"backup_required": False}
            )
        except ClientFailure as failure:
            return _not_attempted(name, device_id, failure)
        preset_id = plan.destination.preset_id
        return Outcome(
            ok=True,
            operation=name,
            device_id=device_id,
            dry_run=True,
            application="not_attempted",
            verification="not_requested",
            data={
                "plan": {**plan_data(plan), **advisory},
                "payload": route_payload(plan.route, plan.entry, preset_id),
                "postconditions": postconditions(plan.route, preset_id),
            },
            warnings=plan.warnings,
        )

    async def write(name: str, device_id: str, planner: Planner) -> Outcome:
        box: dict[str, WritePlan] = {}

        async def prepare(context: OperationContext) -> PolledWrite:
            plan = await planner(context, True)
            box["plan"] = plan
            destination = plan.destination
            expected = expected_entry(plan.route, plan.entry, destination.preset_id)
            data = plan_data(plan)
            data.pop("will_overwrite")
            data["overwrote"] = destination.existing is not None
            return PolledWrite(
                endpoint=Endpoint.PRESETS,
                payload=route_payload(plan.route, plan.entry, destination.preset_id),
                evaluate=lambda value: entry_verdict(plan.route, expected, destination, value),
                data=data,
                reconciliation=WRITE_RECONCILE,
            )

        outcome = await resources.write_polled(device_id, name, prepare)
        planned = box.get("plan")
        if planned is None or not planned.warnings:
            return outcome
        return outcome.model_copy(update={"warnings": [*planned.warnings, *outcome.warnings]})

    async def live_state(context: OperationContext) -> dict[str, JsonValue]:
        return as_dict(await context.read(Endpoint.STATE))

    # -------------------------------------------------------------- list snapshots

    async def list_snapshots(arguments: dict[str, Any]) -> Outcome:
        name = "wled_list_snapshots"
        request = ListSnapshotsRequest.model_validate(arguments)
        device_id = request.device_id
        try:
            device = resources.resolve(device_id)
            # The device lock orders the listing with snapshot writes; no device I/O.
            async with resources.operation(device_id):
                listing = await anyio.to_thread.run_sync(
                    resources.backups.list_snapshots, device_id
                )
        except ClientFailure as failure:
            return _not_attempted(name, known(device_id), failure)
        items: list[JsonValue] = []
        for snapshot in sorted(
            listing.snapshots, key=lambda s: (s.created_at, s.backup_id), reverse=True
        ):
            if request.preset_id is not None and snapshot.preset_id != request.preset_id:
                continue
            kind, _malformed = classify(snapshot.preset)
            items.append(
                {
                    "backup_id": snapshot.backup_id,
                    "preset_id": snapshot.preset_id,
                    "created_at": snapshot.created_at,
                    "firmware_version": snapshot.firmware.version,
                    "type": kind,
                    "name": entry_name(snapshot.preset),
                    "restorable": kind in ("state", "playlist"),
                }
            )
        return Outcome(
            ok=True,
            operation=name,
            device_id=device_id,
            application="not_attempted",
            verification="not_requested",
            data={
                "device": {"id": device.id, "name": device.name},
                "source": "server snapshot store (no device read)",
                "snapshots": items,
                "count": len(items),
                "invalid_count": listing.invalid_count,
            },
            warnings=list(listing.warnings),
        )

    # --------------------------------------------------------------------- restore

    async def load_snapshot(device_id: str, backup_id: str) -> Snapshot:
        return await anyio.to_thread.run_sync(resources.backups.load, device_id, backup_id)

    def restore_planner(request: RestorePresetRequest) -> Planner:
        device_id = request.device_id

        async def planner(context: OperationContext, executing: bool) -> WritePlan:
            snapshot = await load_snapshot(device_id, request.backup_id)
            # The prior snapshot of an occupied destination must not prune the source.
            context.protected_backups.add(snapshot.backup_id)
            kind, _malformed = classify(snapshot.preset)
            if kind not in ("state", "playlist"):
                raise ClientFailure(
                    "UNSUPPORTED_CAPABILITY",
                    f"A snapshot of type '{kind}' is not restored by this server.",
                    reconciliation="Inspect it with wled_list_snapshots; nothing was written.",
                )
            route: Route = "playlist" if kind == "playlist" else "state"
            members = check_playlist_entry(snapshot.preset) if route == "playlist" else []
            firmware = _firmware(await context.read(Endpoint.INFO))
            if firmware.version != snapshot.firmware.version:
                raise ClientFailure(
                    "UNSUPPORTED_CAPABILITY",
                    "The snapshot was taken on a different firmware version than the device "
                    "reports; restore requires the exact version.",
                    reconciliation="Nothing was written; inspect the snapshot explicitly.",
                )
            target = request.preset_id if request.preset_id is not None else snapshot.preset_id
            store = await _read_store(context)
            destination = plan_destination(store, target, request.overwrite, route)
            if route == "playlist":
                check_playlist_members(store, members, target)
            before = live_before(await live_state(context))
            if route == "playlist":
                refuse_running_playlist(before)
            warnings = [*destination.warnings, *playback_warnings(route, before, target)]
            if destination.existing is not None and json_equal(
                destination.existing, snapshot.preset
            ):
                warnings.append("The destination already holds the snapshot's object.")
            if executing:
                await secure_destination(context, destination, firmware, _read_store)
                if route == "playlist":
                    try:
                        check_playlist_members(destination.pre_store, members, target)
                    except ClientFailure:
                        raise ClientFailure(
                            "PRESET_CONFLICT",
                            "A playlist member changed after planning; nothing was written.",
                            reconciliation="Inspect the members with wled_get_preset; the "
                            "snapshot taken for the destination is kept.",
                        ) from None
                    refuse_running_playlist(live_before(await live_state(context)))
                prior = context.backup_records[-1].backup_id if context.backup_records else None
                # The #8 plan helper confirms device, firmware, target and prior snapshot.
                await anyio.to_thread.run_sync(
                    partial(
                        resources.backups.plan_restore,
                        device_id,
                        request.backup_id,
                        firmware_version=firmware.version,
                        destination_occupied=destination.existing is not None,
                        target_preset_id=target,
                        overwrite=request.overwrite,
                        prior_backup_id=prior,
                    )
                )
            details: dict[str, JsonValue] = {
                "source_backup_id": snapshot.backup_id,
                "source_preset_id": snapshot.preset_id,
                "snapshot_type": kind,
                "firmware_version": firmware.version,
            }
            return WritePlan(route, snapshot.preset, destination, before, warnings, details)

        return planner

    async def restore_preset(arguments: dict[str, Any]) -> Outcome:
        name = "wled_restore_preset"
        request = RestorePresetRequest.model_validate(arguments)
        device_id = request.device_id
        try:
            resources.resolve(device_id)
        except ClientFailure as failure:
            return _not_attempted(name, None, failure)
        planner = restore_planner(request)
        if request.dry_run:
            return await dry_run(name, device_id, planner)
        return await write(name, device_id, planner)

    # ----------------------------------------------------------------------- store

    def store_planner(request: StorePresetRequest) -> Planner:
        async def planner(context: OperationContext, executing: bool) -> WritePlan:
            store = await _read_store(context)
            destination = plan_destination(store, request.preset_id, request.overwrite, "state")
            state_raw = await context.read(Endpoint.STATE)
            info_raw = await context.read(Endpoint.INFO)
            collector = Collector()
            _view, capabilities, _fw, _unknown = normalize_state(state_raw, info_raw, collector)
            validate_supplied_state(
                request.state, capabilities, as_dict(info_raw), as_dict(state_raw)
            )
            entry = state_object(request.state, request.name)
            if classify(entry)[0] != "state":  # defensive: the input model allows state only
                raise ClientFailure("VALIDATION_ERROR", "The supplied object is not plain state.")
            firmware = _firmware(info_raw)
            before = live_before(as_dict(state_raw))
            warnings = [
                *collector.result(),
                *destination.warnings,
                *playback_warnings("state", before, destination.preset_id),
            ]
            if executing:
                await secure_destination(context, destination, firmware, _read_store)
            return WritePlan("state", entry, destination, before, warnings, {})

        return planner

    async def store_preset(arguments: dict[str, Any]) -> Outcome:
        name = "wled_store_preset"
        request = StorePresetRequest.model_validate(arguments)
        device_id = request.device_id
        try:
            resources.resolve(device_id)
        except ClientFailure as failure:
            return _not_attempted(name, None, failure)
        planner = store_planner(request)
        if request.dry_run:
            return await dry_run(name, device_id, planner)
        return await write(name, device_id, planner)

    # ------------------------------------------------------------- save playlist

    def playlist_planner(request: SavePlaylistRequest) -> Planner:
        async def planner(context: OperationContext, executing: bool) -> WritePlan:
            entry = playlist_object(request)
            members = check_playlist_entry(entry)  # the schema already bounds every value
            store = await _read_store(context)
            destination = plan_destination(store, request.preset_id, request.overwrite, "playlist")
            target = destination.preset_id
            check_playlist_members(store, members, target)
            before = live_before(await live_state(context))
            refuse_running_playlist(before)
            firmware = _firmware(await context.read(Endpoint.INFO))
            warnings = [*destination.warnings, *playback_warnings("playlist", before, target)]
            if executing:
                await secure_destination(context, destination, firmware, _read_store)
                try:
                    check_playlist_members(destination.pre_store, members, target)
                except ClientFailure:
                    raise ClientFailure(
                        "PRESET_CONFLICT",
                        "A playlist member changed after planning; nothing was written.",
                        reconciliation="Inspect the members with wled_get_preset; a snapshot "
                        "taken for the destination is kept.",
                    ) from None
                refuse_running_playlist(live_before(await live_state(context)))
            details: dict[str, JsonValue] = {
                "playback": playback_notes(members, before, target),
                "firmware_version": firmware.version,
            }
            return WritePlan("playlist", entry, destination, before, warnings, details)

        return planner

    async def save_playlist(arguments: dict[str, Any]) -> Outcome:
        name = "wled_save_playlist"
        request = SavePlaylistRequest.model_validate(arguments)
        device_id = request.device_id
        try:
            resources.resolve(device_id)
        except ClientFailure as failure:
            return _not_attempted(name, None, failure)
        planner = playlist_planner(request)
        if request.dry_run:
            return await dry_run(name, device_id, planner)
        return await write(name, device_id, planner)

    return (
        Operation(
            name="wled_list_snapshots",
            tool_class=ToolClass.READ,
            description=(
                "List the server's stored preset snapshots of one configured device, newest "
                "first, with backup_id, preset_id, time, firmware version, type and name, "
                "optionally for one preset_id. Reads the server's data directory only, never "
                "the device. Invalid snapshot files are counted, not shown. Read-only."
            ),
            request_model=ListSnapshotsRequest,
            execute=list_snapshots,
            annotations=READ_ONLY,
        ),
        Operation(
            name="wled_restore_preset",
            tool_class=ToolClass.MANAGE,
            description=(
                "Restore exactly one snapshot entry (state preset or playlist) to its preset "
                "ID or an explicit preset_id. LIVE EFFECT: a state snapshot is applied to the "
                "lights, then stored verbatim; a playlist snapshot starts playing, then is "
                "stored. The previous lighting is not restored. Requires the same device and "
                "the exact firmware version; an occupied destination needs overwrite=true "
                "and is snapshotted first. API-command and unknown snapshots are refused. One "
                "POST, verified by bounded /presets.json polling, never replayed. dry_run "
                "performs bounded reads only."
            ),
            request_model=RestorePresetRequest,
            execute=restore_preset,
            annotations=DESTRUCTIVE,
        ),
        Operation(
            name="wled_store_preset",
            tool_class=ToolClass.MANAGE,
            description=(
                "Store a supplied light-state object (WLED keys on, bri, transition, bs, "
                "mainseg, seg) as a preset under a name, in the lowest free ID or an explicit "
                "preset_id. LIVE EFFECT: the state is applied to the lights, then stored "
                "verbatim; the previous lighting is not restored, and storing without a live "
                "change is not supported on WLED 16. Validated against the device's ranges "
                "before any write; control keys are not accepted. An occupied ID needs "
                "overwrite=true and is snapshotted first. One POST, verified by bounded "
                "/presets.json polling, never replayed. dry_run performs bounded reads only."
            ),
            request_model=StorePresetRequest,
            execute=store_preset,
            annotations=DESTRUCTIVE,
        ),
        Operation(
            name="wled_save_playlist",
            tool_class=ToolClass.MANAGE,
            description=(
                "Create or replace one native WLED playlist under a name, in the lowest free "
                "ID or an explicit preset_id. entries: 1-100 existing state presets with "
                "duration_s (0 = until advanced) and transition_s (at most 65.5), both in "
                "steps of 0.1 s; repeat 0 = endless or 1-254 passes; shuffle; optional "
                "end_preset_id (an existing state preset; 'restore previous' is not offered). "
                "LIVE EFFECT: saving starts the playlist, then the firmware stores it; the "
                "previous lighting is not restored. Refused while any playlist runs. An "
                "occupied ID needs overwrite=true and is snapshotted first. One POST, verified "
                "semantically by bounded /presets.json polling, never replayed. dry_run "
                "performs bounded reads only."
            ),
            request_model=SavePlaylistRequest,
            execute=save_playlist,
            annotations=DESTRUCTIVE,
        ),
        *build_bundle_operations(resources),
    )
