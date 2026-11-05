"""Public inventory operation; all sessions close over the same resource graph."""

from collections.abc import Awaitable, Callable
from typing import Any

import anyio
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from wled_mcp import __version__
from wled_mcp.catalogs import CatalogView, Kind, catalog_items, load_catalog
from wled_mcp.client import ClientFailure, Deadline, Endpoint
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
from wled_mcp.readmodels import Collector, as_dict, normalize_state, redact_info
from wled_mcp.resources import OperationContext, Resources, SequencePlan
from wled_mcp.server import Operation


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
            },
        }
        return _read_success(name, device_id, data, warnings.result())

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
            freshness: dict[str, JsonValue] = {
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
            description=(
                "Read the palette catalog with original device IDs and names and freshness. "
                "Cached per device for a configured time; refresh=true bypasses the cache. "
                "Read-only."
            ),
            request_model=GetCatalogRequest,
            execute=catalog_operation("palettes"),
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
                plan = build_segment_patch_plan(
                    request, state_view, capabilities, raw_info, raw_state
                )
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

        plan_box: dict[str, SegmentsPlan] = {}

        async def prepare(context: OperationContext) -> dict[str, JsonValue]:
            state_view, capabilities, raw_info, raw_state, _warnings = await _read_state_and_info(
                context
            )
            plan_box["plan"] = build_segment_patch_plan(
                request, state_view, capabilities, raw_info, raw_state
            )
            return plan_box["plan"].payload

        def matches(state: JsonValue) -> bool:
            plan = plan_box.get("plan")
            return plan is not None and matches_segments(plan.expectations, state)

        outcome = await resources.write_verified(device_id, name, prepare, matches)
        return _enrich_segments_outcome(outcome, plan_box.get("plan"))

    async def replace_layout(arguments: dict[str, Any]) -> Outcome:
        name = "wled_replace_layout"
        request = ReplaceLayoutRequest.model_validate(arguments)
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
                        capabilities,
                        raw_info,
                        raw_state,
                        warnings,
                    ) = await _read_state_and_info(context)
                plan = build_layout_plan(request, state_view, capabilities, raw_info, raw_state)
            except ClientFailure as failure:
                return _translate_pre_dispatch(name, device_id, failure)
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
            plan_box["plan"] = build_layout_plan(
                request, state_view, capabilities, raw_info, raw_state
            )
            read_warnings.extend(warnings)
            return plan_box["plan"].sequence

        outcome = await resources.write_sequence_verified(device_id, name, prepare)
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
            description=(
                "Patch one or more existing active segments by explicit ID. Omitted "
                "fields and unrelated segments are preserved. No segment creation or "
                "removal. dry_run performs bounded reads only and returns the plan."
            ),
            request_model=PatchSegmentsRequest,
            execute=patch_segments,
            annotations=MUTATION,
        ),
        Operation(
            name="wled_replace_layout",
            description=(
                "Replace the complete active segment layout. Every desired ID needs id, "
                "start and stop; active IDs not listed are removed one by one (exact "
                "single-segment removal, no filler segments, no bulk purge). Omitted fields "
                "of existing IDs are preserved; new IDs need colors and receive documented "
                "defaults. Master state is never changed. Each step is read back; an "
                "uncertain or mismatching step stops the sequence without replay. dry_run "
                "performs bounded reads only and returns the ordered plan."
            ),
            request_model=ReplaceLayoutRequest,
            execute=replace_layout,
            annotations=DESTRUCTIVE,
        ),
    )


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
    return outcome.model_copy(update={"data": merged})


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
        *_build_read_operations(resources),
        *_build_write_operations(resources),
    )
