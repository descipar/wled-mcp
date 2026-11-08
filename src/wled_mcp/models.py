"""Domain outcomes independent of MCP transport and device adapters."""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

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
    "WRITE_OUTCOME_UNKNOWN",
    "VERIFICATION_MISMATCH",
    "ACCESS_DENIED",
]


class DomainError(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    code: ErrorCode
    message: str
    read_retryable: bool = False
    write_retryable: Literal[False] = False
    reconciliation: str


class Outcome(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
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
