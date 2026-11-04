"""Public inventory operation; all sessions close over the same resource graph."""

from collections.abc import Awaitable, Callable
from typing import Any

import anyio
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from wled_mcp import __version__
from wled_mcp.catalogs import CatalogView, Kind, catalog_items, load_catalog
from wled_mcp.client import ClientFailure, Deadline, Endpoint
from wled_mcp.models import Outcome
from wled_mcp.readmodels import Collector, as_dict, normalize_state, redact_info
from wled_mcp.resources import Resources
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
    )
