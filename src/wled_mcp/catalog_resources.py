"""MCP resources for the device list and the effect/palette catalogs (issue #258).

A catalog resource is a second door to a read tool that already exists: the handler runs the
registered operation of that tool with its default arguments, so validation, the access check,
the per-device lock, the cache, redaction and the structured errors are the tool's own code
(MCPRES-02, MCPRES-04). A resource exists exactly while its tool is registered, which is the
profile's classes AND the selected groups (MCPRES-03); it has no class, group or setting of
its own. Not to be confused with ``resources.Resources`` (the process graph).
"""

import json
import logging
import re
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from mcp import MCPError
from mcp.types import (
    ListResourcesResult,
    ListResourceTemplatesResult,
    PaginatedRequestParams,
    ReadResourceRequestParams,
    ReadResourceResult,
    Resource,
    ResourceTemplate,
    TextResourceContents,
)

from wled_mcp.client import ClientFailure
from wled_mcp.models import Outcome

logger = logging.getLogger(__name__)

DEVICES_URI = "wled://devices"
MIME_TYPE = "application/json"
RESOURCE_NOT_FOUND = -32002
INTERNAL_ERROR = -32603
NOT_FOUND_MESSAGE = "Resource not found"
INTERNAL_MESSAGE = "Internal resource failure"

# A configured device ID (the same shape as the config accepts); anything else cannot be one.
CONTROLLER_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
CATALOG_URI = re.compile(r"wled://devices/([^/?#%\s]+)/(effects|palettes)")

DEVICES_TOOL = "wled_list_devices"
CATALOG_TOOLS = {"effects": "wled_get_effects", "palettes": "wled_get_palettes"}
TEMPLATE_URIS = {
    "effects": "wled://devices/{controller}/effects",
    "palettes": "wled://devices/{controller}/palettes",
}

Runner = Callable[[Any, dict[str, Any]], Awaitable[Outcome]]


def resource_error(outcome: Outcome) -> MCPError:
    """The tool's structured result as the JSON-RPC error data (resources/read has no
    ``isError``); ``data.error`` is the tool's error object."""
    error = outcome.error
    assert error is not None
    return MCPError(
        code=INTERNAL_ERROR, message=error.message, data=outcome.model_dump(mode="json")
    )


def kind_of(tool: str) -> str:
    """The resource kind of a mapped tool: devices, effects or palettes."""
    for kind, name in CATALOG_TOOLS.items():
        if name == tool:
            return kind
    return "devices"


def build_resource_handlers(registry: Mapping[str, Any], run: Runner) -> dict[str, Any]:
    """Handlers for ``Server(...)`` for the resources whose tool is in ``registry``.

    Empty when none is registered, so the server then advertises no resources capability.
    ``run(operation, arguments)`` is the server's tool dispatch (validation, access, class).
    """
    has_devices = DEVICES_TOOL in registry
    kinds = [kind for kind, tool in CATALOG_TOOLS.items() if tool in registry]
    if not has_devices and not kinds:
        return {}

    async def list_resources(ctx: Any, params: PaginatedRequestParams | None) -> Any:
        resources = []
        if has_devices:
            resources.append(
                Resource(
                    uri=DEVICES_URI,
                    name="devices",
                    description="Configured controllers: ID, name, room. No network access.",
                    mime_type=MIME_TYPE,
                )
            )
        return ListResourcesResult(resources=resources)

    async def list_templates(ctx: Any, params: PaginatedRequestParams | None) -> Any:
        return ListResourceTemplatesResult(
            resource_templates=[
                ResourceTemplate(
                    uri_template=TEMPLATE_URIS[kind],
                    name=f"controller-{kind}",
                    description=f"The {kind} catalog of one configured controller (cached).",
                    mime_type=MIME_TYPE,
                )
                for kind in kinds
            ]
        )

    def target(uri: str) -> tuple[str, dict[str, Any], str | None] | None:
        """(tool name, default arguments, controller) of a registered resource, else None."""
        if uri == DEVICES_URI:
            return (DEVICES_TOOL, {}, None) if has_devices else None
        match = CATALOG_URI.fullmatch(uri)
        if match is None or match.group(2) not in kinds:
            return None
        return CATALOG_TOOLS[match.group(2)], {"device_id": match.group(1)}, match.group(1)

    async def read_resource(ctx: Any, params: ReadResourceRequestParams) -> Any:
        found = target(str(params.uri))
        if found is None:
            raise MCPError(code=RESOURCE_NOT_FOUND, message=NOT_FOUND_MESSAGE)
        tool, arguments, controller = found
        if controller is not None and CONTROLLER_PATTERN.fullmatch(controller) is None:
            # Cannot be a configured ID: the tool's own answer, without a device lookup.
            outcome = Outcome(
                ok=False,
                operation=tool,
                device_id=None,
                application="not_attempted",
                verification="not_requested",
                error=ClientFailure("UNKNOWN_DEVICE", "Unknown configured device ID.").error,
            )
        else:
            try:
                outcome = await run(registry[tool], arguments)
            except Exception as exc:
                # Exceptions can contain configuration, URLs or tokens; do not echo them,
                # neither to the client nor to the log: only the class name and the kind.
                logger.warning(
                    "Resource read failed: kind=%s error=%s", kind_of(tool), type(exc).__name__
                )
                raise MCPError(code=INTERNAL_ERROR, message=INTERNAL_MESSAGE) from None
        if not outcome.ok:
            raise resource_error(outcome)
        body = json.dumps(
            outcome.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":")
        )
        return ReadResourceResult(
            contents=[TextResourceContents(uri=str(params.uri), mime_type=MIME_TYPE, text=body)]
        )

    return {
        "on_list_resources": list_resources,
        "on_list_resource_templates": list_templates,
        "on_read_resource": read_resource,
    }
