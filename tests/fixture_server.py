"""Test-only subprocess entry point; never packaged or selected by the CLI."""

from typing import Any, Literal

from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict

from wled_mcp.access import ToolClass
from wled_mcp.models import DomainError, Outcome
from wled_mcp.server import Operation, create_server, run_stdio


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    outcome: Literal["success", "invalid", "uncertain", "crash"]
    value: int


async def execute(arguments: dict[str, Any]) -> Outcome:
    selected = arguments["outcome"]
    if selected == "crash":
        raise RuntimeError("synthetic-secret-never-return")
    if selected == "success":
        return Outcome(
            ok=True,
            operation="fixture",
            device_id=None,
            application="not_attempted",
            verification="not_requested",
            data={"value": arguments["value"]},
        )
    if selected == "invalid":
        return Outcome(
            ok=False,
            operation="fixture",
            device_id=None,
            application="not_attempted",
            verification="not_requested",
            error=DomainError(
                code="VALIDATION_ERROR",
                message="Synthetic rejection.",
                reconciliation="Correct the synthetic request.",
            ),
        )
    return Outcome(
        ok=False,
        operation="fixture",
        device_id="synthetic",
        application="unknown",
        verification="unknown",
        error=DomainError(
            code="WRITE_OUTCOME_UNKNOWN",
            message="Synthetic timeout.",
            reconciliation="Inspect state before deciding a new write.",
        ),
    )


if __name__ == "__main__":
    run_stdio(
        create_server(
            [
                Operation(
                    "fixture",
                    "Synthetic fixture; performs no device operations.",
                    Request,
                    execute,
                    ToolAnnotations(
                        read_only_hint=True, destructive_hint=False, idempotent_hint=True
                    ),
                    tool_class=ToolClass.READ,
                )
            ]
        )
    )
