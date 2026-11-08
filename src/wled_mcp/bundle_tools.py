"""Preset bundle export and import tools of issue #18.

Export reads ``/json/info``, ``/presets.json`` and, for referenced IDs only, the effect
and palette catalogs; it returns a format-1 bundle inline and never writes a file.
Import parses and bounds the bundle before any device I/O, plans every entry inside the
device lock, takes every required snapshot before the first write, rechecks all
destinations, then writes entries one at a time through the single-entry state or
playlist route (one POST each, decided by ``/presets.json`` readback, never resent) and
stops at the first entry that is not verified (R18-IMP-08, ISSUE-18-DEC-003).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC
from typing import Annotated, Any, Final

import anyio
from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from wled_mcp.access import ToolClass
from wled_mcp.backups import Firmware
from wled_mcp.bundles import (
    MAX_BUNDLE_BYTES,
    MAX_CATALOG_ID,
    MAX_IMPORT_ENTRIES,
    WRITABLE_TYPES,
    Bundle,
    BundleEntry,
    ImportPlan,
    Mappings,
    PlannedEntry,
    Target,
    address_tokens,
    build_bundle,
    leaking_entries,
    parse_bundle,
    parse_id_keys,
    plan_import,
    referenced_catalog_ids,
    serialized_size,
)
from wled_mcp.capabilities import aggregate_cct, matrix_of
from wled_mcp.catalogs import load_catalog
from wled_mcp.client import ClientFailure, Deadline, Endpoint
from wled_mcp.config import Device
from wled_mcp.models import DomainError, Outcome
from wled_mcp.preset_tools import DESTRUCTIVE, READ_ONLY
from wled_mcp.preset_writes import (
    PLAYLIST_LIVE_EFFECT,
    STATE_LIVE_EFFECT,
    Destination,
    check_playlist_members,
    entry_verdict,
    expected_entry,
    live_before,
    refuse_running_playlist,
    route_payload,
)
from wled_mcp.presets import (
    MAX_PERSISTENT_ID,
    MIN_PERSISTENT_ID,
    DeviceId,
    PresetId,
    PresetStore,
    classify,
    entry_name,
    json_equal,
    parse_store,
)
from wled_mcp.readmodels import as_dict, is_int, read_identity
from wled_mcp.resources import OperationContext, Resources
from wled_mcp.server import Operation

CatalogId = Annotated[int, Field(strict=True, ge=0, le=MAX_CATALOG_ID)]

IMPORT_RECONCILE: Final = (
    "Read the presets with wled_list_presets and wled_get_preset before any new attempt; "
    "do not replay the import. Verified entries stay written; snapshots are kept."
)
BLOCKED_RECONCILE: Final = (
    "Adjust the bundle, id_map, effect_map, palette_map or overwrite_ids as listed in "
    "data.plan; nothing was written."
)
IMPORT_LIVE_EFFECT: Final = (
    "Each state entry is applied to the lights as it is written, and a playlist entry starts "
    "playing; the lighting before the import is not restored."
)


class ExportPresetsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    device_id: DeviceId
    preset_ids: list[PresetId] | None = Field(default=None, min_length=1, max_length=250)
    include_unwritable: bool = False

    @field_validator("preset_ids")
    @classmethod
    def unique(cls, value: list[int] | None) -> list[int] | None:
        if value is not None and len(set(value)) != len(value):
            raise ValueError("preset_ids must be unique")
        return value


class ImportPresetsRequest(BaseModel):
    """Import a bundle; JSON text keeps duplicate-key and NaN detection exact."""

    model_config = ConfigDict(extra="forbid", strict=True)
    device_id: DeviceId
    bundle: str | dict[str, JsonValue]
    id_map: dict[str, PresetId] | None = Field(default=None, max_length=250)
    effect_map: dict[str, CatalogId] | None = Field(default=None, max_length=512)
    palette_map: dict[str, CatalogId] | None = Field(default=None, max_length=512)
    overwrite_ids: list[PresetId] | None = Field(default=None, max_length=250)
    dry_run: bool = False

    @field_validator("id_map")
    @classmethod
    def id_keys(cls, value: dict[str, int] | None) -> dict[str, int] | None:
        parse_id_keys(value, MIN_PERSISTENT_ID, MAX_PERSISTENT_ID, "id_map")
        return value

    @field_validator("effect_map", "palette_map")
    @classmethod
    def catalog_keys(cls, value: dict[str, int] | None) -> dict[str, int] | None:
        parse_id_keys(value, 0, MAX_CATALOG_ID, "catalog map")
        return value

    @field_validator("overwrite_ids")
    @classmethod
    def unique(cls, value: list[int] | None) -> list[int] | None:
        if value is not None and len(set(value)) != len(value):
            raise ValueError("overwrite_ids must be unique")
        return value


def _failed(name: str, device_id: str | None, failure: ClientFailure, **extra: Any) -> Outcome:
    return Outcome(
        ok=False,
        operation=name,
        device_id=device_id,
        dry_run=bool(extra.pop("dry_run", False)),
        application="not_attempted",
        verification="not_requested",
        data=extra.pop("data", {}),
        warnings=extra.pop("warnings", []),
        error=failure.error,
    )


def _count(leds: dict[str, JsonValue], key: str) -> int | None:
    value = leds.get(key)
    return value if isinstance(value, int) and is_int(value) and value >= 0 else None


def _conflict(message: str) -> ClientFailure:
    return ClientFailure(
        "PRESET_CONFLICT",
        message,
        reconciliation="Read the presets again; snapshots taken by this import are kept.",
    )


# --------------------------------------------------------------------- execution


@dataclass
class EntryResult:
    planned: PlannedEntry
    status: str = "not_attempted"
    reason: str | None = None
    differences: list[str] = field(default_factory=list)
    interference: list[int] = field(default_factory=list)
    observed: JsonValue = None
    transport_error: bool = False

    def data(self) -> dict[str, JsonValue]:
        result: dict[str, JsonValue] = {
            "source_id": self.planned.source.source_id,
            "destination_id": self.planned.destination,
            "route": self.planned.route,
            "status": self.status,
        }
        if self.reason is not None:
            result["reason"] = self.reason
        if self.differences:
            result["differences"] = list(self.differences)
        if self.interference:
            result["interference"] = list(self.interference)
        if self.status == "mismatch":
            result["observed"] = self.observed
        if self.transport_error:
            result["transport_error"] = True
        return result


@dataclass
class Progress:
    results: list[EntryResult] = field(default_factory=list)
    backup_ids: list[str] = field(default_factory=list)
    backup_warnings: list[str] = field(default_factory=list)
    dispatched: bool = False
    stop_error: DomainError | None = None


def _destination_unchanged(store: PresetStore, planned: PlannedEntry) -> None:
    assert planned.destination is not None
    current = store.entries.get(planned.destination)
    if planned.existing is None and current is not None:
        raise _conflict(
            f"Destination {planned.destination} was occupied by another client after "
            "planning; no other ID was chosen and it was not written."
        )
    if planned.existing is not None and not json_equal(current, planned.existing):
        raise _conflict(
            f"Destination {planned.destination} changed after it was snapshotted; it was "
            "not written."
        )


def build_bundle_operations(resources: Resources) -> tuple[Operation, ...]:
    """Export and import tools, in registry order."""

    def poll_interval() -> float:
        return resources.poll_interval_seconds

    @asynccontextmanager
    async def locked(device: Device, seconds: float) -> AsyncIterator[None]:
        """The device lock for one import, bounded by its overall deadline."""
        try:
            with anyio.fail_after(seconds):
                async with resources.locks[device.id]:
                    yield
        except TimeoutError:
            raise ClientFailure("TIMEOUT", "Operation deadline expired.", retryable=True) from None

    def context_for(device: Device, deadline: Deadline) -> OperationContext:
        return OperationContext(device, resources.client, deadline, store=resources.backups)

    # ------------------------------------------------------------------ export

    async def export_presets(arguments: dict[str, Any]) -> Outcome:
        name = "wled_export_presets"
        request = ExportPresetsRequest.model_validate(arguments)
        device_id = request.device_id
        try:
            device = resources.resolve(device_id)
        except ClientFailure as failure:
            return _failed(name, None, failure)
        warnings: list[str] = []
        try:
            async with resources.operation(device_id) as context:
                info = as_dict(await context.read(Endpoint.INFO))
                identity = read_identity(info)
                store = parse_store(as_dict(await context.read(Endpoint.PRESETS)))
                selected, excluded = _select(store, request, warnings)
                fx_ids, pal_ids = referenced_catalog_ids(selected)
                effects = await _names(context, "effects", fx_ids, warnings)
                palettes = await _names(context, "palettes", pal_ids, warnings)
        except ClientFailure as failure:
            return _failed(name, device_id, failure)
        leaking = leaking_entries(selected, address_tokens(device.base_url, info))
        if leaking:
            return _failed(
                name,
                device_id,
                ClientFailure(
                    "VALIDATION_ERROR",
                    f"Preset(s) {leaking[:20]} contain text that matches a device address; "
                    "they are not exported.",
                    reconciliation="Export other presets with preset_ids; nothing was returned.",
                ),
            )
        leds = as_dict(info.get("leds"))
        created_at = resources.clock.now().astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        bundle = build_bundle(
            created_at,
            identity.version,
            _count(leds, "count"),
            _count(leds, "maxseg"),
            matrix_of(info),
            effects,
            palettes,
            selected,
        )
        size = serialized_size(bundle)
        if size > MAX_BUNDLE_BYTES:
            return _failed(
                name,
                device_id,
                ClientFailure(
                    "VALIDATION_ERROR",
                    f"The bundle would exceed {MAX_BUNDLE_BYTES} bytes ({size}).",
                    reconciliation="Select fewer presets with preset_ids.",
                ),
            )
        return Outcome(
            ok=True,
            operation=name,
            device_id=device_id,
            application="not_attempted",
            verification="not_requested",
            data={
                "bundle": bundle,
                "count": len(selected),
                "excluded": excluded,
                "importable": all(entry.type in WRITABLE_TYPES for entry in selected),
                "serialized_bytes": size,
            },
            warnings=warnings,
        )

    def _select(
        store: PresetStore, request: ExportPresetsRequest, warnings: list[str]
    ) -> tuple[list[BundleEntry], list[JsonValue]]:
        if store.malformed_keys:
            warnings.append(
                f"{store.malformed_keys} unrecognized key(s) of /presets.json were not exported."
            )
        ids = request.preset_ids if request.preset_ids is not None else list(store.entries)
        missing = [identifier for identifier in ids if identifier not in store.entries]
        if missing:
            raise ClientFailure(
                "PRESET_NOT_FOUND",
                f"Preset(s) {missing[:20]} do not exist on the device.",
                reconciliation="List the presets with wled_list_presets.",
            )
        selected: list[BundleEntry] = []
        excluded: list[JsonValue] = []
        for identifier in ids:
            entry = store.entries[identifier]
            kind, malformed = classify(entry)
            if kind in WRITABLE_TYPES or request.include_unwritable:
                selected.append(BundleEntry(identifier, entry_name(entry), kind, entry))
            else:
                excluded.append({"source_id": identifier, "type": kind, "malformed": malformed})
        if excluded:
            warnings.append(
                f"{len(excluded)} api-command or unknown entr(ies) were excluded (see "
                "data.excluded); include_unwritable=true exports them for inspection only, "
                "they are never imported."
            )
        if any(entry.type not in WRITABLE_TYPES for entry in selected):
            warnings.append(
                "The bundle contains api-command or unknown entries for inspection; an import "
                "of this bundle is refused until they are removed. They are carried verbatim; "
                "the address check covers only this device's host, IP, MAC and BSSID, so "
                "review them before sharing."
            )
        return selected, excluded

    async def _names(
        context: OperationContext, kind: Any, ids: set[int], warnings: list[str]
    ) -> dict[int, str]:
        if not ids:
            return {}
        view = await load_catalog(context, resources.metadata_cache, kind)
        names = view.entry.names
        unknown = sorted(identifier for identifier in ids if identifier >= len(names))
        if unknown:
            warnings.append(
                f"{kind.capitalize()} ID(s) {unknown[:20]} are not in the device catalog; "
                "an import must map them explicitly."
            )
        return {
            identifier: names[identifier] for identifier in sorted(ids) if identifier < len(names)
        }

    # ------------------------------------------------------------------ import

    async def read_target(context: OperationContext, bundle: Bundle) -> tuple[Target, Firmware]:
        info = as_dict(await context.read(Endpoint.INFO))
        identity = read_identity(info)
        state = as_dict(await context.read(Endpoint.STATE))
        store = parse_store(as_dict(await context.read(Endpoint.PRESETS)))
        writable = [entry for entry in bundle.entries if entry.type == "state"]
        fx_ids, pal_ids = referenced_catalog_ids(writable)
        effects = palettes = None
        if fx_ids:
            effects = (await load_catalog(context, resources.metadata_cache, "effects")).entry.names
        if pal_ids:
            palettes = (
                await load_catalog(context, resources.metadata_cache, "palettes")
            ).entry.names
        leds = as_dict(info.get("leds"))
        target = Target(
            store=store,
            firmware_version=identity.version,
            led_count=_count(leds, "count"),
            max_segments=_count(leds, "maxseg"),
            matrix=matrix_of(info),
            cct=aggregate_cct(info),
            effects=effects,
            palettes=palettes,
            before=live_before(state),
        )
        return target, Firmware(identity.version, identity.build_id)

    def plan_data(plan: ImportPlan, bundle: Bundle, target: Target) -> dict[str, JsonValue]:
        has_playlist = any(entry.route == "playlist" for entry in plan.entries)
        return {
            "executable": not plan.blocked,
            "entries": [entry.preview() for entry in plan.entries],
            "write_order": [entry.source.source_id for entry in plan.write_order()],
            "required_mappings": list(plan.required_mappings),
            "blocking": [finding.message for finding in plan.findings],
            "live_effect": IMPORT_LIVE_EFFECT,
            "route_effects": {
                "state": STATE_LIVE_EFFECT,
                **({"playlist": PLAYLIST_LIVE_EFFECT} if has_playlist else {}),
            },
            "previous_lighting_restored": False,
            "live_before": target.before,
            "bundle": {
                "format_version": 1,
                "created_at": bundle.created_at,
                "source_firmware_version": bundle.firmware_version,
                "entries": len(bundle.entries),
            },
        }

    async def write_entry(
        context: OperationContext, result: EntryResult, progress: Progress
    ) -> None:
        """One entry: recheck, one POST, readback until verified or the entry deadline."""
        planned = result.planned
        assert planned.destination is not None and planned.entry is not None
        assert planned.route is not None
        store = parse_store(as_dict(await context.read(Endpoint.PRESETS)))
        store.require_wellformed()
        _destination_unchanged(store, planned)
        if planned.route == "playlist":
            try:
                check_playlist_members(store, planned.members, planned.destination)
            except ClientFailure:
                raise _conflict(
                    "A playlist member changed after planning; it was not written."
                ) from None
            refuse_running_playlist(live_before(as_dict(await context.read(Endpoint.STATE))))
        destination = Destination(
            planned.destination,
            planned.allocated,
            planned.existing,
            planned.existing_type,
            store,
            [],
        )
        expected = expected_entry(planned.route, planned.entry, planned.destination)
        body = resources.client.encode_payload(
            route_payload(planned.route, planned.entry, planned.destination)
        )
        remaining = context.deadline.remaining()
        if remaining < 0.02:
            raise ClientFailure("TIMEOUT", "Insufficient remaining write/verification budget.")
        dispatch_deadline = Deadline(context.deadline.expires - min(1.0, remaining * 0.25))
        dispatch_deadline.remaining()
        # From here the entry may have been applied: never resend, never not_attempted.
        progress.dispatched = True
        result.status = "unknown"
        try:
            await resources.client.post_state(context.device, body, dispatch_deadline)
        except ClientFailure:
            result.transport_error = True
        last = None
        route = planned.route
        while True:
            try:
                value = await context.read(Endpoint.PRESETS)
            except ClientFailure:
                value = None
            if isinstance(value, dict):
                verdict = entry_verdict(route, expected, destination, value)
                if verdict.matched:
                    result.status = "verified"
                    result.interference = list(verdict.interference)
                    return
                last = verdict
            try:
                await anyio.sleep(min(poll_interval(), context.deadline.remaining()))
            except ClientFailure:
                break
        if last is not None and not (result.transport_error and last.unchanged):
            result.status = "mismatch"
            result.differences = list(last.differences)
            result.interference = list(last.interference)
            result.observed = last.observed

    async def execute(
        device: Device,
        context: OperationContext,
        plan: ImportPlan,
        firmware: Firmware,
        progress: Progress,
        overall: Deadline,
        per_write: float,
    ) -> None:
        order = plan.write_order()
        for planned in order:
            if planned.existing is not None:
                assert planned.destination is not None
                record = await context.backup_preset(
                    planned.destination, planned.existing, firmware
                )
                # A later snapshot of this import must not prune an earlier one.
                context.protected_backups.add(record.backup_id)
                progress.backup_ids.append(record.backup_id)
                progress.backup_warnings.extend(record.warnings)
        fresh = parse_store(as_dict(await context.read(Endpoint.PRESETS)))
        fresh.require_wellformed()
        for planned in order:
            _destination_unchanged(fresh, planned)
        for result in progress.results:
            entry_deadline = Deadline(min(overall.expires, anyio.current_time() + per_write))
            try:
                await write_entry(context_for(device, entry_deadline), result, progress)
            except ClientFailure as failure:
                if result.status == "not_attempted":
                    result.reason = failure.error.message
                    progress.stop_error = failure.error
                    return
                raise
            if result.status != "verified":
                return

    def outcome_of(
        name: str,
        device_id: str,
        progress: Progress,
        plan: ImportPlan,
        warnings: list[str],
    ) -> Outcome:
        results = progress.results
        verified = sum(1 for result in results if result.status == "verified")
        failing = next((result for result in results if result.status != "verified"), None)
        data: dict[str, JsonValue] = {
            "entries": [result.data() for result in results],
            "completed": verified,
            "total": len(results),
            "backup_ids": list(progress.backup_ids),
            "live_effect": IMPORT_LIVE_EFFECT,
            "previous_lighting_restored": False,
        }
        if progress.dispatched:
            data["no_replay"] = True
        interference = sorted({i for result in results for i in result.interference})
        all_warnings = [*plan.all_warnings(), *warnings, *progress.backup_warnings]
        if interference:
            data["interference"] = list[JsonValue](interference)
            all_warnings.append(
                "Unrelated preset entries changed during the import (IDs in "
                "data.interference); they were reported, not corrected."
            )
        if any(result.transport_error for result in results):
            all_warnings.append("Transport error during a write; outcome decided by readback.")
        if failing is None:
            return Outcome(
                ok=True,
                operation=name,
                device_id=device_id,
                application="applied",
                verification="verified",
                data=data,
                warnings=all_warnings,
            )
        if failing.status == "unknown":
            error = DomainError(
                code="WRITE_OUTCOME_UNKNOWN",
                message=f"The outcome of entry {failing.planned.source.source_id} could not be "
                "verified; later entries were not attempted.",
                reconciliation=IMPORT_RECONCILE,
            )
            fallback = ("unknown", "unknown")
        elif failing.status == "mismatch":
            error = DomainError(
                code="VERIFICATION_MISMATCH",
                message=f"Entry {failing.planned.source.source_id} did not match on readback; "
                "later entries were not attempted.",
                reconciliation=IMPORT_RECONCILE,
            )
            fallback = ("unknown", "mismatch")
        else:
            error = progress.stop_error or DomainError(
                code="VALIDATION_ERROR",
                message="The import stopped before this entry.",
                reconciliation=IMPORT_RECONCILE,
            )
            fallback = ("not_attempted", "not_requested")
        # Proven partial steps with the final postcondition not reached (R18-IMP-08).
        application, verification = ("applied", "mismatch") if verified else fallback
        return Outcome(
            ok=False,
            operation=name,
            device_id=device_id,
            application=application,  # type: ignore[arg-type]
            verification=verification,  # type: ignore[arg-type]
            data=data,
            warnings=all_warnings,
            error=error,
        )

    async def import_presets(arguments: dict[str, Any]) -> Outcome:
        name = "wled_import_presets"
        request = ImportPresetsRequest.model_validate(arguments)
        device_id = request.device_id
        try:
            device = resources.resolve(device_id)
        except ClientFailure as failure:
            return _failed(name, None, failure, dry_run=request.dry_run)
        try:
            # G3 for the import path, which posts outside the shared write engines: refused
            # before the bundle is parsed, before the lock and before any device I/O.
            resources.require_write(device_id)
        except ClientFailure as failure:
            return _failed(name, device_id, failure, dry_run=request.dry_run)
        try:
            # Size, strict JSON, envelope and entry count before any device I/O.
            bundle = parse_bundle(request.bundle)
        except ClientFailure as failure:
            return _failed(name, device_id, failure, dry_run=request.dry_run)
        if len(bundle.entries) > MAX_IMPORT_ENTRIES:
            return _failed(
                name,
                device_id,
                ClientFailure(
                    "VALIDATION_ERROR",
                    f"The bundle holds {len(bundle.entries)} entries; at most "
                    f"{MAX_IMPORT_ENTRIES} are imported per call.",
                    reconciliation="Split the bundle; nothing was read or written.",
                ),
                dry_run=request.dry_run,
            )
        mappings = Mappings(
            ids=parse_id_keys(request.id_map, MIN_PERSISTENT_ID, MAX_PERSISTENT_ID, "id_map"),
            effects=parse_id_keys(request.effect_map, 0, MAX_CATALOG_ID, "effect_map"),
            palettes=parse_id_keys(request.palette_map, 0, MAX_CATALOG_ID, "palette_map"),
            overwrite=frozenset(request.overwrite_ids or ()),
        )
        per_write = resources.config.http.operation_timeout_seconds
        writes = sum(1 for entry in bundle.entries if entry.type in WRITABLE_TYPES)
        # One overall deadline from the per-write baseline: planning and snapshots, the
        # recheck and every entry's write and verification.
        overall_seconds = per_write * (writes + 2)
        progress = Progress()
        plan: ImportPlan | None = None
        warnings: list[str] = []
        try:
            async with locked(device, overall_seconds + 1.0):
                overall = Deadline.after(overall_seconds)
                context = context_for(
                    device, Deadline(min(overall.expires, anyio.current_time() + per_write))
                )
                target, firmware = await read_target(context, bundle)
                plan = plan_import(bundle, target, mappings)
                preview = plan_data(plan, bundle, target)
                if request.dry_run or plan.blocked:
                    if any(entry.existing is not None for entry in plan.entries):
                        preview.update(
                            await anyio.to_thread.run_sync(resources.backups.plan_backup, device_id)
                        )
                    else:
                        preview["backup_required"] = False
                    data: dict[str, JsonValue] = {"plan": preview}
                    finding = plan.first_finding()
                    if finding is not None:
                        return _failed(
                            name,
                            device_id,
                            ClientFailure(
                                finding.code, finding.message, reconciliation=BLOCKED_RECONCILE
                            ),
                            dry_run=request.dry_run,
                            data=data,
                            warnings=plan.all_warnings(),
                        )
                    return Outcome(
                        ok=True,
                        operation=name,
                        device_id=device_id,
                        dry_run=True,
                        application="not_attempted",
                        verification="not_requested",
                        data=data,
                        warnings=plan.all_warnings(),
                    )
                progress.results = [EntryResult(planned) for planned in plan.write_order()]
                await execute(device, context, plan, firmware, progress, overall, per_write)
        except ClientFailure as failure:
            if plan is None or not progress.dispatched:
                return _failed(
                    name,
                    device_id,
                    failure,
                    data={"backup_ids": list(progress.backup_ids)} if progress.backup_ids else {},
                    warnings=progress.backup_warnings,
                )
            # The overall deadline expired after a dispatch: an in-flight entry stays
            # unknown; an entry stopped before its POST reports this cause.
            progress.stop_error = progress.stop_error or failure.error
            warnings.append("The import's overall deadline expired.")
        except Exception:
            if plan is None or not progress.dispatched:
                return _failed(
                    name,
                    device_id,
                    ClientFailure("VALIDATION_ERROR", "Import preparation failed."),
                    data={"backup_ids": list(progress.backup_ids)} if progress.backup_ids else {},
                )
            warnings.append("The import stopped unexpectedly after a write.")
        assert plan is not None
        return outcome_of(name, device_id, progress, plan, warnings)

    return (
        Operation(
            name="wled_export_presets",
            tool_class=ToolClass.READ,
            description=(
                "Export presets of one configured device as a portable, versioned bundle "
                "(format wled-mcp.preset-bundle, format_version 1), returned inline. By "
                "default all state presets and playlists, or the listed preset_ids; "
                "api-command and unknown entries only with include_unwritable=true, for "
                "inspection (never importable). Preset objects are carried verbatim with "
                "their type. Contains no device ID, address, host, MAC, BSSID, credential or "
                "inventory data. Read-only; the server writes no file."
            ),
            request_model=ExportPresetsRequest,
            execute=export_presets,
            annotations=READ_ONLY,
        ),
        Operation(
            name="wled_import_presets",
            tool_class=ToolClass.MANAGE,
            description=(
                "Import a preset bundle (object or JSON text, at most 192 KiB and 50 entries, "
                "at most one playlist) into one configured device. LIVE EFFECT: each state "
                "entry is applied to the lights as it is written, and a playlist entry starts "
                "playing; the previous lighting is not restored. Destination IDs come from "
                "id_map (source ID -> destination) or the lowest free IDs in bundle order; an "
                "occupied destination needs its ID in overwrite_ids and is snapshotted before "
                "the first write. Nothing is rescaled or converted: a segment beyond the "
                "target LED count, too many segments, differing 2D geometry or an effect/"
                "palette ID named differently on the target blocks the import until the bundle "
                "is edited or effect_map/palette_map is given. Playlist members are rewritten "
                "through the same mapping and written first. One POST per entry, verified by "
                "/presets.json polling, never replayed; it stops at the first unverified entry "
                "and reports each entry. dry_run performs bounded reads only."
            ),
            request_model=ImportPresetsRequest,
            execute=import_presets,
            annotations=DESTRUCTIVE,
        ),
    )
