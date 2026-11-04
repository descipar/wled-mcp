"""Shared SDK adapter; production starts with no operations until later issues."""

import json
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
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
from wled_mcp.models import DomainError, Outcome


@dataclass(frozen=True)
class Operation:
    """Explicit programmatic registration; no dynamic CLI or environment imports."""

    name: str
    description: str
    request_model: type[BaseModel]
    execute: Callable[[dict[str, Any]], Awaitable[Outcome]]
    annotations: ToolAnnotations


def to_tool_result(outcome: Outcome) -> CallToolResult:
    envelope = outcome.model_dump(mode="json")
    return CallToolResult(
        content=[TextContent(text=json.dumps(envelope, ensure_ascii=False, separators=(",", ":")))],
        structured_content=envelope,
        is_error=not outcome.ok,
    )


def create_server(operations: Sequence[Operation] = ()) -> Server[None]:
    """Build one domain/tool graph for the selected transport."""
    registry = {operation.name: operation for operation in operations}
    if len(registry) != len(operations):
        raise ValueError("Duplicate operation names")

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

    async def call_tool(
        ctx: ServerRequestContext[None], params: CallToolRequestParams
    ) -> CallToolResult:
        operation = registry.get(params.name)
        if operation is None:
            raise MCPError(code=-32602, message="Unknown tool")
        try:
            validated = operation.request_model.model_validate(params.arguments or {})
        except ValidationError:
            return to_tool_result(
                Outcome(
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
            )
        try:
            result = await operation.execute(validated.model_dump())
        except Exception:
            # Exceptions can contain configuration, URLs or tokens; do not echo them.
            raise MCPError(code=-32603, message="Internal operation failure") from None
        return to_tool_result(result)

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
