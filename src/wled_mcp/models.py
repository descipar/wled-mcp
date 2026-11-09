"""Domain outcomes independent of MCP transport and device adapters."""

from typing import Any, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    SerializerFunctionWrapHandler,
    model_serializer,
    model_validator,
)

Application = Literal["not_attempted", "applied", "not_applied", "unknown"]
Verification = Literal["not_requested", "verified", "mismatch", "unknown"]
ErrorCode = Literal[
    "CONFIG_ERROR",
    "UNKNOWN_DEVICE",
    "UNREACHABLE",
    "TIMEOUT",
    "INVALID_RESPONSE",
    "VALIDATION_ERROR",
    "UNSUPPORTED_CAPABILITY",
    "AMBIGUOUS_NAME",
    "PRESET_NOT_FOUND",
    "PRESET_CONFLICT",
    "BACKUP_FAILED",
    "STORAGE_FAILED",
    "WRITE_OUTCOME_UNKNOWN",
    "VERIFICATION_MISMATCH",
    "ACCESS_DENIED",
]


class DomainError(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
        # Internal validation stays strict, but the served output schema tolerates unknown
        # fields so a client that cached it keeps accepting later additive fields (#130).
        json_schema_extra={"additionalProperties": True},
    )
    code: ErrorCode
    message: str
    read_retryable: bool = False
    write_retryable: Literal[False] = False
    reconciliation: str


class Outcome(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
        # Internal validation stays strict, but the served output schema tolerates unknown
        # fields so a client that cached it keeps accepting later additive fields (#130).
        json_schema_extra={"additionalProperties": True},
    )
    schema_version: Literal[1] = 1
    ok: bool
    operation: str = Field(min_length=1)
    device_id: str | None
    dry_run: bool = False
    application: Application
    verification: Verification
    data: dict[str, JsonValue] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    error: DomainError | None = None
    # Set by the server dispatcher on every served envelope (issue #20, TD-20-9); never by
    # an operation and never from client input. Optional so direct ``execute`` results and
    # the retained examples stay as they were.
    correlation_id: str | None = None

    @model_serializer(mode="wrap")
    def omit_unset_correlation_id(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        """Leave the key out while no ID is set, so unserved envelopes are unchanged."""
        dumped: dict[str, Any] = handler(self)
        if self.correlation_id is None:
            dumped.pop("correlation_id", None)
        return dumped

    @model_validator(mode="after")
    def consistent_outcome(self) -> Self:
        valid = {
            ("not_attempted", "not_requested", True),
            ("not_attempted", "not_requested", False),
            ("not_applied", "not_requested", False),
            ("applied", "verified", True),
            ("unknown", "unknown", False),
            ("unknown", "mismatch", False),
            ("applied", "mismatch", False),
        }
        if (self.application, self.verification, self.ok) not in valid:
            raise ValueError("Inconsistent application, verification and success states")
        if self.ok != (self.error is None):
            raise ValueError("Successful outcomes have no error; unsuccessful outcomes require one")
        if self.dry_run and self.application != "not_attempted":
            raise ValueError("Dry runs cannot dispatch writes")
        return self
