"""Public inventory operation; all sessions close over the same resource graph."""

from typing import Any

import anyio
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, JsonValue

from wled_mcp.client import ClientFailure, Deadline, Endpoint
from wled_mcp.models import Outcome
from wled_mcp.resources import Resources
from wled_mcp.server import Operation


class ListDevicesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    probe: bool = False


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
    )
