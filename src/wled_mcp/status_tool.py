"""``wled_get_service_status``: local runtime facts, never a device request (issue #20).

The tool reads only process memory (the access policy, the monitor's last observed outcome
per device and its call counters). It sends no request, probes nothing and writes no file;
``wled_list_devices`` with ``probe=true`` stays the explicit live check. A device this process
has not talked to is ``unknown``, never healthy, and there is deliberately no aggregate
"healthy" flag.
"""

from typing import Any

from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, JsonValue

from wled_mcp import __version__
from wled_mcp.access import ToolClass
from wled_mcp.models import Outcome
from wled_mcp.resources import Resources
from wled_mcp.server import Operation

LIVENESS = (
    "alive: this process answered a tool call. Process liveness is a TCP connect to the "
    "service port or an authenticated MCP ping; neither contacts a device."
)
READINESS_BASIS = (
    "Last observed outcome of a request this process sent to each configured device; "
    "this tool sends none. 'unknown' means no request has been observed since start, "
    "not that the device is healthy."
)


class ServiceStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


def service_status(resources: Resources) -> dict[str, JsonValue]:
    """The status document; pure over in-memory state (no I/O, no clock besides reads)."""
    monitor = resources.monitor
    policy = resources.access
    devices = monitor.device_states()
    counts = {"unknown": 0, "reachable": 0, "failed": 0}
    for entry in devices:
        counts[str(entry["state"])] += 1
    access_devices: list[Any] = []
    for device in resources.inventory:
        cap = policy.caps.get(device.id)
        access_devices.append(
            {
                "device_id": device.id,
                "max_class": None if cap is None else cap.value,
                "effective_class": policy.ceiling(device.id).value,
            }
        )
    document: dict[str, Any] = {
        "service": {
            "name": "wled-mcp",
            "version": __version__,
            "transport": monitor.transport,
            "uptime_seconds": monitor.uptime_seconds(),
        },
        "access": {"profile": policy.profile, "devices": access_devices},
        "liveness": {"status": "alive", "definition": LIVENESS},
        "readiness": {"basis": READINESS_BASIS, "counts": counts, "devices": devices},
        "calls": monitor.call_counts(),
        "backups": {"writable_at_startup": monitor.backups_writable},
    }
    return document


def build_status_operation(resources: Resources) -> Operation:
    async def get_service_status(arguments: dict[str, Any]) -> Outcome:
        return Outcome(
            ok=True,
            operation="wled_get_service_status",
            device_id=None,
            application="not_attempted",
            verification="not_requested",
            data=service_status(resources),
        )

    return Operation(
        name="wled_get_service_status",
        tool_class=ToolClass.READ,
        description=(
            "Report local service facts: version, transport, uptime, access profile and "
            "per-device ceilings, the last observed outcome per device and call counters. "
            "Never contacts a device; a device not yet observed is 'unknown', not healthy. "
            "Use wled_list_devices with probe=true for a live check."
        ),
        request_model=ServiceStatusRequest,
        execute=get_service_status,
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
    )
