"""Public inventory operation; all sessions close over the same resource graph."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import anyio
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from wled_mcp import __version__, compat
from wled_mcp.access import ToolClass
from wled_mcp.backups import Firmware
from wled_mcp.catalogs import (
    AmbiguousName,
    CatalogView,
    Kind,
    UnknownName,
    catalog_items,
    load_catalog,
    resolve_name,
)
from wled_mcp.client import ClientFailure, Deadline, Endpoint
from wled_mcp.effect_search import SearchEffectsRequest, search, shipped_catalog
from wled_mcp.layouts import LayoutPlan, ReplaceLayoutRequest, build_layout_plan
from wled_mcp.models import Outcome
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
from wled_mcp.preset_tools import build_preset_workflow_operations
from wled_mcp.presets import (
    ActivatePresetRequest,
    CaptureReference,
    DeletePresetRequest,
    GetPresetRequest,
    ListPresetsRequest,
    PresetStore,
    SavePresetRequest,
    capture_reference,
    classify,
    compare_capture,
    entry_name,
    interference,
    json_equal,
    lowest_free,
    parse_store,
    playlist_end_unsafe,
    playlist_members,
    referencing_playlists,
    unexpected_state_keys,
    unsafe_playlist_members,
)
from wled_mcp.readmodels import (
    Collector,
    as_dict,
    normalize_state,
    read_identity,
    redact_info,
)
from wled_mcp.resources import OperationContext, PolledWrite, Resources, SequencePlan, Verdict
from wled_mcp.scene_tools import build_scene_operations
from wled_mcp.server import Operation
from wled_mcp.status_tool import build_status_operation
from wled_mcp.zone_tools import build_zone_operations


class ListDevicesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    probe: bool = False


class GetStateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    device_id: str = Field(min_length=1, max_length=64)


class GetCatalogRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    device_id: str = Field(min_length=1, max_length=64)
    refresh: bool = False


READ_ONLY = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)

MUTATION = ToolAnnotations(
    # Typed mutations are explicit state changes; they are not snapshot/preset
    # destructive. Annotations are hints only, not an authorization barrier.
    read_only_hint=False,
    destructive_hint=False,
    idempotent_hint=False,
    open_world_hint=False,
)

DESTRUCTIVE = ToolAnnotations(
    # Replacing the layout discards every active segment that is not listed. The hint is
    # advisory; authorization belongs to the MCP host/client.
    read_only_hint=False,
    destructive_hint=True,
    idempotent_hint=False,
    open_world_hint=False,
)


def _read_failure(
    resources: Resources, operation: str, device_id: str, failure: ClientFailure
) -> Outcome:
    """Failed read: nothing was written. Only configured IDs are echoed back."""
    known = any(device.id == device_id for device in resources.inventory)
    return Outcome(
        ok=False,
        operation=operation,
        device_id=device_id if known else None,
        application="not_attempted",
        verification="not_requested",
        error=failure.error,
    )


def _read_success(
    operation: str, device_id: str, data: dict[str, JsonValue], warnings: list[str]
) -> Outcome:
    return Outcome(
        ok=True,
        operation=operation,
        device_id=device_id,
        application="not_attempted",
        verification="not_requested",
        data=data,
        warnings=warnings,
    )


def _build_read_operations(resources: Resources) -> tuple[Operation, ...]:
    """State and catalog reads. Each call holds the per-device lock (so it cannot interleave
    with a future write workflow) and one deadline; other devices stay independent."""

    def device_data(device_id: str) -> dict[str, JsonValue]:
        device = resources.resolve(device_id)
        return {"id": device.id, "name": device.name}

    async def get_state(arguments: dict[str, Any]) -> Outcome:
        name, device_id = "wled_get_state", arguments["device_id"]
        try:
            async with resources.operation(device_id) as context:
                # Sequential, never cached, not an atomic snapshot of the device.
                state = await context.read(Endpoint.STATE)
                info = await context.read(Endpoint.INFO)
                read_at = resources.clock.now()
            warnings = Collector()
            view, capabilities, firmware, unknown = normalize_state(state, info, warnings)
        except ClientFailure as failure:
            return _read_failure(resources, name, device_id, failure)
        raw_info, removed = redact_info(as_dict(info))
        # Informational only (TD-21-6): never refuses and never changes other behavior.
        support = compat.firmware_support(firmware["version"])
        tier_warning = compat.support_warning(compat.classify(firmware["version"]))
        data: dict[str, JsonValue] = {
            "device": device_data(device_id),
            "freshness": {"source": "device", "read_at": read_at.isoformat()},
            "firmware": firmware,
            "capabilities": capabilities,
            "state": view,
            "raw": {"state": state, "info": raw_info, "redacted_info_keys": list(removed)},
            "diagnostics": {
                "server_version": __version__,
                "unknown_capabilities": list(unknown),
                "firmware_support": support,
            },
        }
        leading = [tier_warning] if tier_warning is not None else []
        return _read_success(name, device_id, data, [*leading, *warnings.result()])

    def freshness_of(view: CatalogView) -> dict[str, JsonValue]:
        entry = view.entry
        return {
            "source": view.source,
            "fetched_at": entry.fetched_at.isoformat(),
            "age_seconds": view.age_seconds,
            "cache_ttl_seconds": resources.metadata_cache.ttl_seconds,
            "firmware": {
                "version": entry.identity.version,
                "build_id": entry.identity.build_id,
            },
            "refreshed": view.refreshed,
        }

    async def search_effects(arguments: dict[str, Any]) -> Outcome:
        name, device_id = "wled_search_effects", arguments["device_id"]
        request = SearchEffectsRequest.model_validate(arguments)
        try:
            async with resources.operation(device_id) as context:
                view = await load_catalog(
                    context, resources.metadata_cache, "effects", request.refresh
                )
            device = device_data(device_id)
        except ClientFailure as failure:
            return _read_failure(resources, name, device_id, failure)
        data, warnings = search(
            shipped_catalog(), view.entry.names, view.entry.identity.version, request
        )
        data = {"device": device, **data, "freshness": freshness_of(view)}
        return _read_success(name, device_id, data, warnings)

    def catalog_operation(kind: Kind) -> Callable[[dict[str, Any]], Awaitable[Outcome]]:
        name = "wled_get_effects" if kind == "effects" else "wled_get_palettes"

        async def execute(arguments: dict[str, Any]) -> Outcome:
            device_id = arguments["device_id"]
            try:
                async with resources.operation(device_id) as context:
                    view: CatalogView = await load_catalog(
                        context, resources.metadata_cache, kind, arguments["refresh"]
                    )
                device = device_data(device_id)
            except ClientFailure as failure:
                return _read_failure(resources, name, device_id, failure)
            entry = view.entry
            freshness = freshness_of(view)
            items = catalog_items(entry, kind)
            data: dict[str, JsonValue] = {
                "device": device,
                kind: items,
                "count": len(items),
                "freshness": freshness,
            }
            if kind == "effects":
                data["metadata"] = {
                    "status": "available" if entry.fxdata is not None else "unavailable",
                    "reason": entry.metadata_reason,
                }
            return _read_success(name, device_id, data, list(view.warnings))

        return execute

    return (
        Operation(
            name="wled_get_state",
            tool_class=ToolClass.READ,
            description=(
                "Read normalized state, raw state and essential firmware/capability facts of "
                "one configured device. Always fresh, never cached; state and info are read "
                "one after the other, not as an atomic snapshot. Read-only."
            ),
            request_model=GetStateRequest,
            execute=get_state,
            annotations=READ_ONLY,
        ),
        Operation(
            name="wled_get_effects",
            tool_class=ToolClass.READ,
            description=(
                "Read the effect catalog with original device IDs and names, optional raw "
                "fxdata metadata and freshness. Cached per device for a configured time; "
                "refresh=true bypasses the cache. Read-only."
            ),
            request_model=GetCatalogRequest,
            execute=catalog_operation("effects"),
            annotations=READ_ONLY,
        ),
        Operation(
            name="wled_get_palettes",
            tool_class=ToolClass.READ,
            description=(
                "Read the palette catalog with original device IDs and names and freshness. "
                "Cached per device for a configured time; refresh=true bypasses the cache. "
                "Read-only."
            ),
            request_model=GetCatalogRequest,
            execute=catalog_operation("palettes"),
            annotations=READ_ONLY,
        ),
        Operation(
            name="wled_search_effects",
            tool_class=ToolClass.READ,
            description=(
                "Search the effects of one device by curated properties (motion, flashing, "
                "colour count, palette use, strip length, visibility, palette saturation "
                "need). Returns the device's exact effect IDs and names with per-result "
                "explanation; unknown properties never satisfy a strict filter. Subjective "
                "properties are recommendations, flashing is not a safety guarantee. "
                "Read-only; apply a result with an existing control tool."
            ),
            request_model=SearchEffectsRequest,
            execute=search_effects,
            annotations=READ_ONLY,
        ),
    )


async def _read_state_and_info(
    context: OperationContext,
) -> tuple[
    dict[str, JsonValue],
    dict[str, JsonValue],
    dict[str, JsonValue],
    dict[str, JsonValue],
    list[str],
]:
    """Fresh ``/json/state`` + ``/json/info`` read under the active lock + deadline."""
    state = await context.read(Endpoint.STATE)
    info = await context.read(Endpoint.INFO)
    collector = Collector()
    view, capabilities, _firmware, _unknown = normalize_state(state, info, collector)
    return view, capabilities, as_dict(info), as_dict(state), collector.result()


def _dry_run_outcome(
    operation: str, device_id: str, data: dict[str, JsonValue], warnings: list[str]
) -> Outcome:
    return Outcome(
        ok=True,
        operation=operation,
        device_id=device_id,
        dry_run=True,
        application="not_attempted",
        verification="not_requested",
        data=data,
        warnings=warnings,
    )


def _build_write_operations(resources: Resources) -> tuple[Operation, ...]:
    """Master and segment patch tools. Both share the per-device write/verify lock."""

    async def set_state(arguments: dict[str, Any]) -> Outcome:
        name = "wled_set_state"
        request = SetStateRequest.model_validate(arguments)
        device_id = request.device_id
        try:
            resources.resolve(device_id)
        except ClientFailure as failure:
            return _read_failure(resources, name, device_id, failure)

        if request.dry_run:
            try:
                async with resources.operation(device_id) as context:
                    (
                        state_view,
                        _capabilities,
                        _info,
                        _raw_state,
                        warnings,
                    ) = await _read_state_and_info(context)
                plan = build_set_state_plan(request, state_view)
            except ClientFailure as failure:
                return _translate_pre_dispatch(name, device_id, failure)
            return _dry_run_outcome(
                name,
                device_id,
                {
                    "plan": plan.public,
                    "payload": plan.payload,
                    "postconditions": plan.postconditions,
                },
                warnings,
            )

        plan_box: dict[str, MasterPlan] = {}

        async def prepare(context: OperationContext) -> dict[str, JsonValue]:
            state_view, _capabilities, _info, _raw_state, _warnings = await _read_state_and_info(
                context
            )
            plan_box["plan"] = build_set_state_plan(request, state_view)
            return plan_box["plan"].payload

        def matches(state: JsonValue) -> bool:
            plan = plan_box.get("plan")
            return plan is not None and matches_set_state(plan, state)

        outcome = await resources.write_verified(device_id, name, prepare, matches)
        return _enrich_outcome_with_plan(outcome, plan_box.get("plan"))

    async def patch_segments(arguments: dict[str, Any]) -> Outcome:
        name = "wled_patch_segments"
        request = PatchSegmentsRequest.model_validate(arguments)
        device_id = request.device_id
        name_failure: dict[str, JsonValue] = {}
        try:
            resources.resolve(device_id)
        except ClientFailure as failure:
            return _read_failure(resources, name, device_id, failure)

        if request.dry_run:
            try:
                async with resources.operation(device_id) as context:
                    (
                        state_view,
                        capabilities,
                        raw_info,
                        raw_state,
                        warnings,
                    ) = await _read_state_and_info(context)
                    resolved = await _resolve_segment_names(
                        resources, context, request, name_failure
                    )
                    plan = build_segment_patch_plan(
                        resolved, state_view, capabilities, raw_info, raw_state
                    )
            except ClientFailure as failure:
                return _with_name_failure(
                    _translate_pre_dispatch(name, device_id, failure), name_failure
                )
            return _dry_run_outcome(
                name,
                device_id,
                {
                    "plan": plan.public,
                    "payload": plan.payload,
                    "postconditions": plan.postconditions,
                },
                [*warnings, *plan.warnings],
            )

        plan_box: dict[str, SegmentsPlan] = {}

        async def prepare(context: OperationContext) -> dict[str, JsonValue]:
            state_view, capabilities, raw_info, raw_state, _warnings = await _read_state_and_info(
                context
            )
            resolved = await _resolve_segment_names(resources, context, request, name_failure)
            plan_box["plan"] = build_segment_patch_plan(
                resolved, state_view, capabilities, raw_info, raw_state
            )
            return plan_box["plan"].payload

        def matches(state: JsonValue) -> bool:
            plan = plan_box.get("plan")
            return plan is not None and matches_segments(plan.expectations, state)

        outcome = await resources.write_verified(device_id, name, prepare, matches)
        return _with_name_failure(
            _enrich_segments_outcome(outcome, plan_box.get("plan")), name_failure
        )

    async def replace_layout(arguments: dict[str, Any]) -> Outcome:
        name = "wled_replace_layout"
        request = ReplaceLayoutRequest.model_validate(arguments)
        device_id = request.device_id
        name_failure: dict[str, JsonValue] = {}
        try:
            resources.resolve(device_id)
        except ClientFailure as failure:
            return _read_failure(resources, name, device_id, failure)

        if request.dry_run:
            try:
                async with resources.operation(device_id) as context:
                    (
                        state_view,
                        capabilities,
                        raw_info,
                        raw_state,
                        warnings,
                    ) = await _read_state_and_info(context)
                    resolved = await _resolve_segment_names(
                        resources, context, request, name_failure
                    )
                    plan = build_layout_plan(
                        resolved, state_view, capabilities, raw_info, raw_state
                    )
            except ClientFailure as failure:
                return _with_name_failure(
                    _translate_pre_dispatch(name, device_id, failure), name_failure
                )
            return _dry_run_outcome(
                name,
                device_id,
                {"plan": plan.public, "postconditions": plan.postconditions},
                [*warnings, *plan.warnings],
            )

        plan_box: dict[str, LayoutPlan] = {}
        read_warnings: list[str] = []

        async def prepare(context: OperationContext) -> SequencePlan:
            state_view, capabilities, raw_info, raw_state, warnings = await _read_state_and_info(
                context
            )
            resolved = await _resolve_segment_names(resources, context, request, name_failure)
            plan_box["plan"] = build_layout_plan(
                resolved, state_view, capabilities, raw_info, raw_state
            )
            read_warnings.extend(warnings)
            return plan_box["plan"].sequence

        outcome = _with_name_failure(
            await resources.write_sequence_verified(device_id, name, prepare), name_failure
        )
        planned = plan_box.get("plan")
        if planned is None or (not outcome.ok and outcome.application == "not_attempted"):
            return outcome
        plan = planned
        return outcome.model_copy(
            update={
                "data": {
                    **outcome.data,
                    "plan": plan.public,
                    "postconditions": plan.postconditions,
                },
                "warnings": [*read_warnings, *plan.warnings],
            }
        )

    return (
        Operation(
            name="wled_set_state",
            tool_class=ToolClass.CONTROL,
            description=(
                "Apply a typed master patch: optional on/brightness/transition_ms. "
                "Omitted fields remain unchanged. Transition is a one-call tt (ms) "
                "that does not touch persistent 'transition'. dry_run performs "
                "bounded reads only and returns the resolved plan."
            ),
            request_model=SetStateRequest,
            execute=set_state,
            annotations=MUTATION,
        ),
        Operation(
            name="wled_patch_segments",
            tool_class=ToolClass.CONTROL,
            description=(
                "Patch one or more existing active segments by explicit ID. Omitted "
                "fields and unrelated segments are preserved. No segment creation or "
                "removal. cct, effect options, 2D bounds/orientation and blend_mode are "
                "settable only where the fresh readback proves the capability or field; "
                "overlapping segments need allow_overlap=true. dry_run performs bounded "
                "reads only and returns the plan."
            ),
            request_model=PatchSegmentsRequest,
            execute=patch_segments,
            annotations=MUTATION,
        ),
        Operation(
            name="wled_replace_layout",
            tool_class=ToolClass.CONTROL,
            description=(
                "Replace the complete active segment layout. Every desired ID needs id, "
                "start and stop; active IDs not listed are removed one by one (exact "
                "single-segment removal, no filler segments, no bulk purge). Omitted fields "
                "of existing IDs are preserved; new IDs need colors (and start_y/stop_y on "
                "a matrix) and receive documented defaults. cct, effect options, 2D fields "
                "and blend_mode need fresh capability or field evidence; overlapping "
                "segments need allow_overlap=true. Master state is never changed. Each step "
                "is read back; an "
                "uncertain or mismatching step stops the sequence without replay. dry_run "
                "performs bounded reads only and returns the ordered plan."
            ),
            request_model=ReplaceLayoutRequest,
            execute=replace_layout,
            annotations=DESTRUCTIVE,
        ),
    )


# ------------------------------------------------------------------ preset tools (#9)

CAPTURE_WARNING = (
    "Capture is asynchronous and not an atomic photograph of the strip; external changes "
    "can race with the save."
)
ACTIVATION_NOOP_WARNING = (
    "The firmware ignores re-selecting the preset that is already active, so a verified "
    "result cannot prove that this call re-applied it."
)
PLAYLIST_RUNNING_WARNING = (
    "This playlist is already running; a verified result cannot prove that it was restarted."
)


def saved_type_warning(kind: str, unexpected: list[str]) -> str:
    """Names only the unexpected top-level keys; never the preset name or any value."""
    keys = ", ".join(unexpected) if unexpected else "none"
    return (
        f"The stored entry is classified '{kind}', not a plain state preset on this firmware, "
        f"and will not be activated by this server (unexpected top-level keys: {keys})."
    )


PRESET_RECONCILE = (
    "Read the presets with wled_list_presets or wled_get_preset before any new attempt; "
    "do not replay the write."
)


def _preset_failure(code: Any, message: str, reconciliation: str) -> ClientFailure:
    return ClientFailure(code, message, reconciliation=reconciliation)


def _not_found() -> ClientFailure:
    return _preset_failure(
        "PRESET_NOT_FOUND",
        "No preset is stored under this ID.",
        "List the stored presets with wled_list_presets before choosing an ID.",
    )


def _firmware(info: JsonValue) -> Firmware:
    identity = read_identity(info)
    return Firmware(identity.version, identity.build_id)


async def _read_store(context: OperationContext) -> PresetStore:
    return parse_store(as_dict(await context.read(Endpoint.PRESETS)))


def _entry_summary(identifier: int, entry: JsonValue) -> dict[str, JsonValue]:
    kind, malformed = classify(entry)
    item: dict[str, JsonValue] = {"id": identifier, "name": entry_name(entry), "type": kind}
    if malformed:
        item["malformed"] = True
    return item


def _build_preset_operations(resources: Resources) -> tuple[Operation, ...]:
    """Persistent preset tools. Every call holds the per-device lock and one deadline;
    stored data is always read fresh, never cached."""

    def device_data(device_id: str) -> dict[str, JsonValue]:
        device = resources.resolve(device_id)
        return {"id": device.id, "name": device.name}

    def store_warnings(store: PresetStore) -> list[str]:
        if not store.malformed_keys:
            return []
        return [f"{store.malformed_keys} unrecognized key(s) in the preset store were skipped."]

    async def read_view(name: str, device_id: str) -> tuple[PresetStore, str] | Outcome:
        try:
            async with resources.operation(device_id) as context:
                store = await _read_store(context)
                read_at = resources.clock.now().isoformat()
        except ClientFailure as failure:
            return _read_failure(resources, name, device_id, failure)
        return store, read_at

    async def list_presets(arguments: dict[str, Any]) -> Outcome:
        name, device_id = "wled_list_presets", arguments["device_id"]
        viewed = await read_view(name, device_id)
        if isinstance(viewed, Outcome):
            return viewed
        store, read_at = viewed
        presets: list[JsonValue] = [_entry_summary(i, e) for i, e in store.entries.items()]
        data: dict[str, JsonValue] = {
            "device": device_data(device_id),
            "freshness": {"source": "device", "read_at": read_at},
            "presets": presets,
            "count": len(presets),
        }
        return _read_success(name, device_id, data, store_warnings(store))

    async def get_preset(arguments: dict[str, Any]) -> Outcome:
        name, device_id, preset_id = (
            "wled_get_preset",
            arguments["device_id"],
            arguments["preset_id"],
        )
        viewed = await read_view(name, device_id)
        if isinstance(viewed, Outcome):
            return viewed
        store, read_at = viewed
        entry = store.entries.get(preset_id)
        if entry is None:
            return _read_failure(resources, name, device_id, _not_found())
        summary = _entry_summary(preset_id, entry)
        data: dict[str, JsonValue] = {
            "device": device_data(device_id),
            "freshness": {"source": "device", "read_at": read_at},
            "preset_id": preset_id,
            "name": summary["name"],
            "type": summary["type"],
            "preset": entry,
        }
        if summary.get("malformed"):
            data["malformed"] = True
        return _read_success(name, device_id, data, store_warnings(store))

    # ------------------------------------------------------------ activation

    @dataclass
    class ActivationPlan:
        kind: str
        members: list[int]
        before_ps: int | None
        before_pl: int | None
        warnings: list[str]

    async def plan_activation(
        context: OperationContext, request: ActivatePresetRequest
    ) -> ActivationPlan:
        store = await _read_store(context)
        entry = store.entries.get(request.preset_id)
        if entry is None:
            raise _not_found()
        kind, _malformed = classify(entry)
        members: list[int] = []
        if kind == "playlist":
            if playlist_end_unsafe(entry):
                raise _preset_failure(
                    "UNSUPPORTED_CAPABILITY",
                    "The playlist's end preset restores the previous preset (255) or is outside "
                    "0-255 (the firmware wraps it); it cannot be checked and is not activated.",
                    "Inspect the playlist with wled_get_preset.",
                )
            members = playlist_members(entry)
            bad = unsafe_playlist_members(store, members)
            if bad:
                raise _preset_failure(
                    "UNSUPPORTED_CAPABILITY",
                    "The playlist references presets that are missing or not plain state "
                    f"presets (IDs {bad[:20]}); it is not activated.",
                    "Inspect the playlist and its members with wled_get_preset.",
                )
        elif kind != "state":
            raise _preset_failure(
                "UNSUPPORTED_CAPABILITY",
                f"A preset of type '{kind}' is not activated by this server.",
                "Inspect it with wled_get_preset; only state presets and playlists of "
                "state presets can be activated.",
            )
        state = as_dict(await context.read(Endpoint.STATE))
        ps, pl = state.get("ps"), state.get("pl")
        before_ps = ps if type(ps) is int else None
        before_pl = pl if type(pl) is int else None
        warnings = list(store_warnings(store))
        if kind == "playlist":
            if before_pl == request.preset_id:
                warnings.append(PLAYLIST_RUNNING_WARNING)
        elif before_ps == request.preset_id:
            warnings.append(ACTIVATION_NOOP_WARNING)
        return ActivationPlan(kind, members, before_ps, before_pl, warnings)

    def activation_verdict(
        request: ActivatePresetRequest, plan: ActivationPlan, value: JsonValue
    ) -> Verdict:
        state = as_dict(value)
        ps, pl = state.get("ps"), state.get("pl")
        now_ps = ps if type(ps) is int else None
        now_pl = pl if type(pl) is int else None
        matched = (now_pl if plan.kind == "playlist" else now_ps) == request.preset_id
        observed: JsonValue = {
            "active_preset_id": now_ps if now_ps is not None and now_ps > 0 else None,
            "active_playlist_id": now_pl if now_pl is not None and now_pl > 0 else None,
        }
        return Verdict(
            matched=matched,
            observed=observed,
            unchanged=(now_ps, now_pl) == (plan.before_ps, plan.before_pl),
        )

    async def activate_preset(arguments: dict[str, Any]) -> Outcome:
        name = "wled_activate_preset"
        request = ActivatePresetRequest.model_validate(arguments)
        device_id = request.device_id
        try:
            resources.resolve(device_id)
        except ClientFailure as failure:
            return _read_failure(resources, name, device_id, failure)
        payload: dict[str, JsonValue] = {"ps": request.preset_id}
        if request.dry_run:
            try:
                async with resources.operation(device_id) as context:
                    plan = await plan_activation(context, request)
            except ClientFailure as failure:
                return _translate_pre_dispatch(name, device_id, failure)
            return _dry_run_outcome(
                name,
                device_id,
                {
                    "plan": {
                        "preset_id": request.preset_id,
                        "type": plan.kind,
                        "member_ids": list(plan.members),
                        "writes_storage": False,
                    },
                    "payload": payload,
                    "postconditions": [
                        "state.pl equals the playlist ID"
                        if plan.kind == "playlist"
                        else "state.ps equals the preset ID"
                    ],
                },
                plan.warnings,
            )
        box: dict[str, ActivationPlan] = {}

        async def prepare(context: OperationContext) -> PolledWrite:
            plan = box["plan"] = await plan_activation(context, request)
            return PolledWrite(
                endpoint=Endpoint.STATE,
                payload=payload,
                evaluate=lambda value: activation_verdict(request, plan, value),
                data={"preset_id": request.preset_id, "type": plan.kind},
                reconciliation=(
                    "Read the state with wled_get_state before any new attempt; "
                    "do not replay the write."
                ),
            )

        outcome = await resources.write_polled(device_id, name, prepare)
        planned = box.get("plan")
        if planned is None or not planned.warnings:
            return outcome
        return outcome.model_copy(update={"warnings": [*planned.warnings, *outcome.warnings]})

    # ------------------------------------------------------------------ save

    @dataclass
    class SavePlan:
        preset_id: int
        allocated: bool
        existing: dict[str, JsonValue] | None
        existing_type: str | None
        reference: CaptureReference
        firmware: Firmware
        pre_store: PresetStore
        warnings: list[str]

    async def plan_save(
        context: OperationContext, request: SavePresetRequest, *, dry_run: bool
    ) -> SavePlan:
        store = await _read_store(context)
        store.require_wellformed()
        existing: dict[str, JsonValue] | None = None
        existing_type: str | None = None
        warnings: list[str] = []
        if request.preset_id is None:
            chosen = lowest_free(store)
            if chosen is None:
                raise _preset_failure(
                    "PRESET_CONFLICT",
                    "No free persistent preset ID (1-250) is available; nothing was written.",
                    "Delete a preset explicitly or choose an occupied ID with overwrite=true.",
                )
            preset_id, allocated = chosen, True
        else:
            preset_id, allocated = request.preset_id, False
            current = store.entries.get(preset_id)
            if current is not None:
                if not request.overwrite:
                    raise _preset_failure(
                        "PRESET_CONFLICT",
                        "The preset ID is occupied; overwrite=true is required to replace it.",
                        "Inspect it with wled_get_preset, then repeat with overwrite=true or "
                        "omit preset_id to use a free ID.",
                    )
                existing_type, malformed = classify(current)
                if malformed or not isinstance(current, dict):
                    raise _preset_failure(
                        "VALIDATION_ERROR",
                        "The existing entry is not a JSON object and cannot be snapshotted.",
                        "Inspect it with wled_get_preset; it is not overwritten.",
                    )
                if existing_type == "playlist":
                    raise _preset_failure(
                        "UNSUPPORTED_CAPABILITY",
                        "Replacing a playlist is not supported.",
                        "Inspect it with wled_get_preset; delete it explicitly and save to a "
                        "free ID if replacement is intended.",
                    )
                if existing_type != "state":
                    warnings.append(
                        f"The existing '{existing_type}' entry is replaced by a state preset."
                    )
                existing = current
        state_raw = await context.read(Endpoint.STATE)
        info_raw = await context.read(Endpoint.INFO)
        collector = Collector()
        normalize_state(state_raw, info_raw, collector)  # validates the live state shape
        warnings.extend(collector.result())
        firmware = _firmware(info_raw)
        reference = capture_reference(as_dict(state_raw))
        pre_store = store
        if not dry_run:
            if existing is not None:
                await context.backup_preset(preset_id, existing, firmware)
            fresh = await _read_store(context)
            fresh.require_wellformed()
            current_entry = fresh.entries.get(preset_id)
            if existing is None and current_entry is not None:
                raise _preset_failure(
                    "PRESET_CONFLICT",
                    "The preset ID was occupied by another client after planning; "
                    "no alternative ID was chosen and nothing was written.",
                    "Read the presets and request a new save explicitly.",
                )
            if existing is not None and not json_equal(current_entry, existing):
                raise _preset_failure(
                    "PRESET_CONFLICT",
                    "The preset changed after it was snapshotted; nothing was written.",
                    "Read the preset again; the snapshot taken for the earlier state is kept.",
                )
            pre_store = fresh
        return SavePlan(
            preset_id, allocated, existing, existing_type, reference, firmware, pre_store, warnings
        )

    def save_verdict(request: SavePresetRequest, plan: SavePlan, value: JsonValue) -> Verdict:
        store = parse_store(as_dict(value))
        entry = store.entries.get(plan.preset_id)
        before = plan.existing
        changed = interference(plan.pre_store, store, plan.preset_id)
        if entry is None:
            return Verdict(
                matched=False,
                observed=None,
                unchanged=before is None,
                differences=("entry",),
                interference=tuple(changed),
            )
        differences = compare_capture(entry, request.name, plan.reference)
        kind = classify(entry)[0]
        warnings: tuple[str, ...] = (CAPTURE_WARNING,)
        if kind != "state":
            # Reported, never corrected: no extra write and no change to the outcome.
            warnings += (saved_type_warning(kind, unexpected_state_keys(entry)),)
        return Verdict(
            matched=not differences,
            observed=entry,
            unchanged=before is not None and json_equal(entry, before),
            differences=tuple(differences),
            interference=tuple(changed),
            warnings=warnings,
            data={"preset": entry, "type": kind},
        )

    def save_postconditions(request: SavePresetRequest, plan: SavePlan) -> list[JsonValue]:
        return [
            f"/presets.json entry {plan.preset_id} has name equal to the requested name",
            "entry master fields and every active segment match the pre-dispatch capture",
            "unrelated entries are unchanged (differences are reported as interference)",
        ]

    async def save_preset(arguments: dict[str, Any]) -> Outcome:
        name = "wled_save_preset"
        request = SavePresetRequest.model_validate(arguments)
        device_id = request.device_id
        try:
            resources.resolve(device_id)
        except ClientFailure as failure:
            return _read_failure(resources, name, device_id, failure)
        if request.dry_run:
            try:
                async with resources.operation(device_id) as context:
                    plan = await plan_save(context, request, dry_run=True)
                advisory = (
                    await anyio.to_thread.run_sync(resources.backups.plan_backup, device_id)
                    if plan.existing is not None
                    else {"backup_required": False}
                )
            except ClientFailure as failure:
                return _translate_pre_dispatch(name, device_id, failure)
            payload = save_payload(request, plan.preset_id)
            return _dry_run_outcome(
                name,
                device_id,
                {
                    "plan": {
                        "preset_id": plan.preset_id,
                        "allocated": plan.allocated,
                        "will_overwrite": plan.existing is not None,
                        "existing_type": plan.existing_type,
                        "capture": plan.reference.summary(),
                        **advisory,
                    },
                    "payload": payload,
                    "postconditions": save_postconditions(request, plan),
                },
                [*plan.warnings, CAPTURE_WARNING],
            )
        box: dict[str, SavePlan] = {}

        async def prepare(context: OperationContext) -> PolledWrite:
            plan = box["plan"] = await plan_save(context, request, dry_run=False)
            return PolledWrite(
                endpoint=Endpoint.PRESETS,
                payload=save_payload(request, plan.preset_id),
                evaluate=lambda value: save_verdict(request, plan, value),
                data={
                    "preset_id": plan.preset_id,
                    "name": request.name,
                    "allocated": plan.allocated,
                    "overwrote": plan.existing is not None,
                },
                reconciliation=PRESET_RECONCILE,
            )

        outcome = await resources.write_polled(device_id, name, prepare)
        planned = box.get("plan")
        if planned is None or not planned.warnings:
            return outcome
        return outcome.model_copy(update={"warnings": [*planned.warnings, *outcome.warnings]})

    def save_payload(request: SavePresetRequest, preset_id: int) -> dict[str, JsonValue]:
        # Storage controls only: no on/bri/seg/ps, so nothing is applied to the strip.
        return {"psave": preset_id, "n": request.name, "ib": True, "sb": True, "sc": False}

    # ---------------------------------------------------------------- delete

    @dataclass
    class DeletePlan:
        existing: dict[str, JsonValue]
        existing_type: str
        pre_store: PresetStore
        warnings: list[str]

    async def plan_delete(
        context: OperationContext, request: DeletePresetRequest, *, dry_run: bool
    ) -> DeletePlan:
        store = await _read_store(context)
        store.require_wellformed()
        current = store.entries.get(request.preset_id)
        if current is None:
            raise _not_found()
        kind, malformed = classify(current)
        if malformed or not isinstance(current, dict):
            raise _preset_failure(
                "VALIDATION_ERROR",
                "The entry is not a JSON object and cannot be snapshotted; it is not deleted.",
                "Inspect it with wled_get_preset.",
            )
        state_raw = await context.read(Endpoint.STATE)
        info_raw = await context.read(Endpoint.INFO)
        collector = Collector()
        normalize_state(state_raw, info_raw, collector)
        firmware = _firmware(info_raw)
        warnings = collector.result()
        users = referencing_playlists(store, request.preset_id)
        if users:
            warnings.append(f"Playlist(s) {users[:20]} reference this preset; they are not edited.")
        if as_dict(state_raw).get("ps") == request.preset_id:
            warnings.append("The preset is the currently active preset marker (state.ps).")
        pre_store = store
        if not dry_run:
            await context.backup_preset(request.preset_id, current, firmware)
            fresh = await _read_store(context)
            fresh.require_wellformed()
            if not json_equal(fresh.entries.get(request.preset_id), current):
                raise _preset_failure(
                    "PRESET_CONFLICT",
                    "The preset changed after it was snapshotted; nothing was deleted.",
                    "Read the preset again; the snapshot taken for the earlier state is kept.",
                )
            pre_store = fresh
        return DeletePlan(current, kind, pre_store, warnings)

    def delete_verdict(request: DeletePresetRequest, plan: DeletePlan, value: JsonValue) -> Verdict:
        store = parse_store(as_dict(value))
        entry = store.entries.get(request.preset_id)
        changed = interference(plan.pre_store, store, request.preset_id)
        if entry is None:
            return Verdict(matched=True, interference=tuple(changed))
        return Verdict(
            matched=False,
            observed=entry,
            unchanged=json_equal(entry, plan.existing),
            differences=("entry",),
            interference=tuple(changed),
        )

    async def delete_preset(arguments: dict[str, Any]) -> Outcome:
        name = "wled_delete_preset"
        request = DeletePresetRequest.model_validate(arguments)
        device_id = request.device_id
        try:
            resources.resolve(device_id)
        except ClientFailure as failure:
            return _read_failure(resources, name, device_id, failure)
        payload: dict[str, JsonValue] = {"pdel": request.preset_id}
        postconditions: list[JsonValue] = [
            f"/presets.json has no entry (absent, null or empty) for ID {request.preset_id}",
            "unrelated entries are unchanged (differences are reported as interference)",
        ]
        if request.dry_run:
            try:
                async with resources.operation(device_id) as context:
                    plan = await plan_delete(context, request, dry_run=True)
                advisory = await anyio.to_thread.run_sync(resources.backups.plan_backup, device_id)
            except ClientFailure as failure:
                return _translate_pre_dispatch(name, device_id, failure)
            return _dry_run_outcome(
                name,
                device_id,
                {
                    "plan": {
                        "preset_id": request.preset_id,
                        "existing_type": plan.existing_type,
                        **advisory,
                    },
                    "payload": payload,
                    "postconditions": postconditions,
                },
                plan.warnings,
            )
        box: dict[str, DeletePlan] = {}

        async def prepare(context: OperationContext) -> PolledWrite:
            plan = box["plan"] = await plan_delete(context, request, dry_run=False)
            return PolledWrite(
                endpoint=Endpoint.PRESETS,
                payload=payload,
                evaluate=lambda value: delete_verdict(request, plan, value),
                data={"preset_id": request.preset_id, "deleted_type": plan.existing_type},
                reconciliation=PRESET_RECONCILE,
            )

        outcome = await resources.write_polled(device_id, name, prepare)
        planned = box.get("plan")
        if planned is None or not planned.warnings:
            return outcome
        return outcome.model_copy(update={"warnings": [*planned.warnings, *outcome.warnings]})

    return (
        Operation(
            name="wled_list_presets",
            tool_class=ToolClass.READ,
            description=(
                "List the persistent presets (IDs 1-250) of one configured device with ID, "
                "name and type (state, playlist, api-command or unknown). Empty slots and "
                "reserved IDs are omitted. Always read fresh from the device, never cached. "
                "Read-only."
            ),
            request_model=ListPresetsRequest,
            execute=list_presets,
            annotations=READ_ONLY,
        ),
        Operation(
            name="wled_get_preset",
            tool_class=ToolClass.READ,
            description=(
                "Read one stored preset exactly as the device holds it, with its type. The "
                "object may contain stored commands; it is returned to the caller unchanged. "
                "PRESET_NOT_FOUND for an empty slot. Always fresh. Read-only."
            ),
            request_model=GetPresetRequest,
            execute=get_preset,
            annotations=READ_ONLY,
        ),
        Operation(
            name="wled_activate_preset",
            tool_class=ToolClass.CONTROL,
            description=(
                "Activate an existing state preset or a playlist made only of state presets. "
                "Changes the live output and may interrupt current playback; never writes "
                "storage. API-command and unknown entries are refused. Verified by bounded "
                "state readback. dry_run performs bounded reads only."
            ),
            request_model=ActivatePresetRequest,
            execute=activate_preset,
            annotations=MUTATION,
        ),
        Operation(
            name="wled_save_preset",
            tool_class=ToolClass.MANAGE,
            description=(
                "Save the CURRENT live state under a name (at most 32 UTF-8 bytes) into the "
                "lowest free persistent ID, or into an explicit preset_id. Replacing an "
                "occupied ID needs overwrite=true and takes a durable snapshot first; "
                "playlists are never replaced. Sends storage controls only (no state fields), "
                "so nothing is applied or activated, but firmware side effects of saving "
                "are not verified. Outcome is decided by bounded /presets.json polling; an "
                "uncertain outcome is never replayed. No supplied-state input exists. "
                "dry_run performs bounded reads only."
            ),
            request_model=SavePresetRequest,
            execute=save_preset,
            annotations=DESTRUCTIVE,
        ),
        Operation(
            name="wled_delete_preset",
            tool_class=ToolClass.MANAGE,
            description=(
                "Delete exactly one stored preset (any type) after a durable snapshot. "
                "Referencing playlists and the active-preset marker are not edited; a "
                "warning names them. Outcome is decided by bounded /presets.json polling "
                "for absence; an uncertain outcome is never replayed. dry_run performs "
                "bounded reads only."
            ),
            request_model=DeletePresetRequest,
            execute=delete_preset,
            annotations=DESTRUCTIVE,
        ),
    )


async def _resolve_segment_names[T: (PatchSegmentsRequest, ReplaceLayoutRequest)](
    resources: Resources,
    context: OperationContext,
    request: T,
    failure_data: dict[str, JsonValue],
) -> T:
    """Translate the complete request under its device lock before pure planning."""
    views: dict[Kind, CatalogView] = {}
    segments = []
    try:
        for segment in request.segments:
            updates: dict[str, Any] = {}
            for field, kind in (("effect", "effects"), ("palette", "palettes")):
                query = getattr(segment, f"{field}_name")
                if query is None:
                    continue
                catalog_kind: Kind = "effects" if kind == "effects" else "palettes"
                if catalog_kind not in views:
                    views[catalog_kind] = await load_catalog(
                        context, resources.metadata_cache, catalog_kind
                    )
                updates[f"{field}_id"] = resolve_name(
                    views[catalog_kind].entry, catalog_kind, query
                )
                updates[f"{field}_name"] = None
            segments.append(segment.model_copy(update=updates))
    except (AmbiguousName, UnknownName) as failure:
        failure_data.update(candidates=failure.candidates, candidate_total=failure.total)
        raise
    return request.model_copy(update={"segments": segments})


def _with_name_failure(outcome: Outcome, data: dict[str, JsonValue]) -> Outcome:
    if data and outcome.application == "not_attempted":
        return outcome.model_copy(update={"data": {**outcome.data, **data}})
    return outcome


def _translate_pre_dispatch(name: str, device_id: str, failure: ClientFailure) -> Outcome:
    """Pre-dispatch failures map to the shared not_attempted/not_requested envelope."""
    return Outcome(
        ok=False,
        operation=name,
        device_id=device_id,
        application="not_attempted",
        verification="not_requested",
        error=failure.error,
    )


def _enrich_outcome_with_plan(outcome: Outcome, plan: MasterPlan | None) -> Outcome:
    if plan is None:
        return outcome
    extra: dict[str, JsonValue] = {
        "plan": plan.public,
        "postconditions": plan.postconditions,
    }
    merged = {**outcome.data, **extra}
    return outcome.model_copy(update={"data": merged})


def _enrich_segments_outcome(outcome: Outcome, plan: SegmentsPlan | None) -> Outcome:
    if plan is None:
        return outcome
    extra: dict[str, JsonValue] = {
        "plan": plan.public,
        "postconditions": plan.postconditions,
    }
    merged = {**outcome.data, **extra}
    update: dict[str, Any] = {"data": merged}
    if plan.warnings:
        update["warnings"] = [*outcome.warnings, *plan.warnings]
    return outcome.model_copy(update=update)


def build_operations(resources: Resources) -> tuple[Operation, ...]:
    async def list_devices(arguments: dict[str, Any]) -> Outcome:
        entries: list[JsonValue] = [
            {"id": device.id, "name": device.name, "probe_status": "untested"}
            for device in resources.inventory
        ]
        if arguments["probe"]:
            # At most eight workers; no per-device task explosion. Each worker/device
            # has one deadline; maximum complete-call duration is ceil(N/8)*timeout.
            iterator = iter(enumerate(resources.inventory))

            async def worker() -> None:
                for index, device in iterator:
                    try:
                        value = await resources.client.read(
                            device,
                            Endpoint.INFO,
                            Deadline.after(resources.config.http.operation_timeout_seconds),
                        )
                        if not isinstance(value, dict) or not isinstance(value.get("ver"), str):
                            raise ClientFailure(
                                "INVALID_RESPONSE", "Missing WLED firmware identity."
                            )
                        entries[index] = {
                            "id": device.id,
                            "name": device.name,
                            "probe_status": "reachable",
                        }
                    except ClientFailure as failure:
                        entries[index] = {
                            "id": device.id,
                            "name": device.name,
                            "probe_status": "failed",
                            "error": failure.error.model_dump(mode="json"),
                        }

            async with anyio.create_task_group() as group:
                for _ in range(min(8, len(entries))):
                    group.start_soon(worker)
        return Outcome(
            ok=True,
            operation="wled_list_devices",
            device_id=None,
            application="not_attempted",
            verification="not_requested",
            data={"devices": entries},
        )

    return (
        Operation(
            name="wled_list_devices",
            tool_class=ToolClass.READ,
            description=(
                "List configured IDs/names without network by default. "
                "Optional bounded read-only probes; no discovery or writes."
            ),
            request_model=ListDevicesRequest,
            execute=list_devices,
            annotations=ToolAnnotations(
                read_only_hint=True,
                destructive_hint=False,
                idempotent_hint=True,
                open_world_hint=False,
            ),
        ),
        build_status_operation(resources),
        *_build_read_operations(resources),
        *_build_write_operations(resources),
        *_build_preset_operations(resources),
        *build_preset_workflow_operations(resources),
        *build_scene_operations(resources),
        *build_zone_operations(resources),
    )
