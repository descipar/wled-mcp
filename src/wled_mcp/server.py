"""Shared SDK adapter; production starts with no operations until later issues."""

import json
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import anyio
from mcp import MCPError
from mcp.server.context import ServerRequestContext
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    ListToolsResult,
    PaginatedRequestParams,
    TextContent,
    Tool,
    ToolAnnotations,
)
from pydantic import BaseModel, ValidationError

from wled_mcp import __version__
from wled_mcp.access import CURRENT_TOOL_CLASS, AccessPolicy, ToolClass, denial_message
from wled_mcp.diagnostics import (
    INTERNAL_FAILURE,
    UNKNOWN_TOOL,
    CallRecord,
    ServiceMonitor,
    log_call,
    new_correlation_id,
)
from wled_mcp.models import DomainError, Outcome


@dataclass(frozen=True)
class Operation:
    """Explicit programmatic registration; no dynamic CLI or environment imports."""

    name: str
    description: str
    request_model: type[BaseModel]
    execute: Callable[[dict[str, Any]], Awaitable[Outcome]]
    annotations: ToolAnnotations
    # Required, no default (issue #20, TD-20-3): an operation without a class cannot exist.
    tool_class: ToolClass = field(kw_only=True)


def to_tool_result(outcome: Outcome, correlation_id: str | None = None) -> CallToolResult:
    if correlation_id is not None:
        outcome = outcome.model_copy(update={"correlation_id": correlation_id})
    envelope = outcome.model_dump(mode="json")
    return CallToolResult(
        content=[TextContent(text=json.dumps(envelope, ensure_ascii=False, separators=(",", ":")))],
        structured_content=envelope,
        is_error=not outcome.ok,
    )


def create_server(
    operations: Sequence[Operation] = (),
    access: AccessPolicy | None = None,
    monitor: ServiceMonitor | None = None,
) -> Server[None]:
    """Build one domain/tool graph for the selected transport.

    ``access`` selects the profile (G1) and the per-device ceilings (G2); ``None`` means
    profile ``full`` without caps. An operation outside the profile is not registered, so
    ``tools/list``, ``tools/call`` and the SDK schema lookup all see one registry and a
    disabled tool is indistinguishable from an unknown one.

    ``monitor`` receives the call counters and says which device IDs may appear in the call
    log; the service passes the one held by its ``Resources``. Without it the counters are
    discarded and no device ID is logged.
    """
    policy = access if access is not None else AccessPolicy()
    calls = monitor if monitor is not None else ServiceMonitor()
    for operation in operations:
        if not isinstance(operation.tool_class, ToolClass):
            raise TypeError("Every operation needs a ToolClass")
    registered = {operation.name: operation for operation in operations}
    if len(registered) != len(operations):
        raise ValueError("Duplicate operation names")
    registry = {
        name: operation
        for name, operation in registered.items()
        if policy.permits_class(operation.tool_class)
    }

    async def list_tools(
        ctx: ServerRequestContext[None], params: PaginatedRequestParams | None
    ) -> ListToolsResult:
        return ListToolsResult(
            tools=[
                Tool(
                    name=operation.name,
                    description=operation.description,
                    input_schema=operation.request_model.model_json_schema(),
                    output_schema=Outcome.model_json_schema(),
                    annotations=operation.annotations,
                )
                for operation in registry.values()
            ]
        )

    async def dispatch(
        operation: Operation, raw_arguments: dict[str, Any], named: list[str]
    ) -> Outcome:
        try:
            validated = operation.request_model.model_validate(raw_arguments)
        except ValidationError:
            return Outcome(
                ok=False,
                operation=operation.name,
                device_id=None,
                application="not_attempted",
                verification="not_requested",
                error=DomainError(
                    code="VALIDATION_ERROR",
                    message="Arguments do not match the tool schema.",
                    reconciliation="Correct the arguments using the published input schema.",
                ),
            )
        arguments = validated.model_dump()
        device_id = arguments.get("device_id")
        if isinstance(device_id, str):
            # Kept for the call line when the tool crashes and there is no envelope.
            named.append(device_id)
        if isinstance(device_id, str) and not policy.permits(operation.tool_class, device_id):
            # G2: refused before the tool runs, so before any lock, file or device I/O.
            # dry_run does not lower a tool's class (TD-20-2).
            return Outcome(
                ok=False,
                operation=operation.name,
                device_id=device_id,
                dry_run=arguments.get("dry_run") is True,
                application="not_attempted",
                verification="not_requested",
                error=DomainError(
                    code="ACCESS_DENIED",
                    message=denial_message(
                        device_id, operation.tool_class, policy.ceiling(device_id)
                    ),
                    reconciliation=(
                        "Nothing was sent. The deployment profile or the device's "
                        "maximum class does not allow this class of operation."
                    ),
                ),
            )
        # G3: the class stays visible to the write engines for the whole call.
        token = CURRENT_TOOL_CLASS.set(operation.tool_class)
        try:
            return await operation.execute(arguments)
        finally:
            CURRENT_TOOL_CLASS.reset(token)

    async def call_tool(
        ctx: ServerRequestContext[None], params: CallToolRequestParams
    ) -> CallToolResult:
        # The ID is generated here, per call, and never read from the request (TD-20-9).
        correlation_id = new_correlation_id()
        started = time.perf_counter()
        named: list[str] = []  # the validated device ID of this call, if it has one

        def finish(
            operation: Operation | None,
            tool: str,
            ok: bool,
            *,
            outcome: Outcome | None = None,
            error_code: str | None = None,
        ) -> None:
            tool_class = None if operation is None else operation.tool_class
            code = error_code or (outcome.error.code if outcome and outcome.error else None)
            calls.record_call(tool_class, ok, code)
            raw_device = named[0] if outcome is None and named else None
            application = None if outcome is None else outcome.application
            if outcome is not None:
                raw_device = outcome.device_id
            elif code == INTERNAL_FAILURE and tool_class is not ToolClass.READ:
                # A crash cannot tell "not attempted" from "possibly applied".
                application = "unknown"
            log_call(
                CallRecord(
                    tool=tool,
                    correlation_id=correlation_id,
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    ok=ok,
                    tool_class=tool_class,
                    # Only configured IDs: an unknown ID is client input.
                    device_id=raw_device if calls.is_configured(raw_device) else None,
                    application=application,
                    verification=None if outcome is None else outcome.verification,
                    error_code=code,
                )
            )

        operation = registry.get(params.name)
        if operation is None:
            # A disabled tool and a made-up name look the same, also in the log.
            finish(None, "unknown_tool", False, error_code=UNKNOWN_TOOL)
            raise MCPError(code=-32602, message="Unknown tool")
        try:
            outcome = await dispatch(operation, params.arguments or {}, named)
        except Exception:
            # Exceptions can contain configuration, URLs or tokens; do not echo them.
            finish(operation, operation.name, False, error_code=INTERNAL_FAILURE)
            raise MCPError(
                code=-32603,
                message=f"Internal operation failure (correlation_id={correlation_id})",
            ) from None
        finish(operation, operation.name, outcome.ok, outcome=outcome)
        return to_tool_result(outcome, correlation_id)

    return Server(
        "wled-mcp",
        version=__version__,
        on_list_tools=list_tools,
        on_call_tool=call_tool,
        get_tool_input_schema=lambda name: (
            registry[name].request_model.model_json_schema() if name in registry else None
        ),
    )


async def serve_stdio(server: Server[None]) -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def run_stdio(server: Server[None]) -> None:
    anyio.run(serve_stdio, server)
