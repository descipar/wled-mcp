"""Signal tools of issue #28: start, status and cancel of a temporary signal.

A temporary signal is a bounded, explicit, conditional colour on existing segments of one
configured device (docs/contract/signals.md). The planning is ``signals.py``, the lifecycle is
``SignalManager``; this module holds the request models, the tool descriptions and the mapping
of results onto the shared outcome envelope. The tools add no write path: the apply and every
restore use ``Resources.write_verified`` under the shared per-device lock.
"""

from __future__ import annotations

from typing import Annotated, Any, get_args

from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from wled_mcp.access import ToolClass
from wled_mcp.client import ClientFailure
from wled_mcp.models import Application, DomainError, ErrorCode, Outcome, Verification
from wled_mcp.preset_tools import READ_ONLY
from wled_mcp.resources import Resources
from wled_mcp.server import Operation
from wled_mcp.signal_manager import SignalManager, SignalRecord, StartResult
from wled_mcp.signals import (
    MAX_ACTIVE,
    MAX_DURATION_SECONDS,
    MAX_TARGET_SEGMENTS,
    OPERATION_ID_PATTERN,
    RETAIN_ENDED,
    SignalRefusal,
    SignalSpec,
)

START = "wled_start_signal"
STATUS = "wled_get_signal_status"
CANCEL = "wled_cancel_signal"

START_ANNOTATIONS = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False
)
CANCEL_ANNOTATIONS = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)

TIMING_NOTE = (
    "Timing is best effort. The duration is measured on the process clock from the verified "
    "apply; the restore starts at expiry plus the lock wait and device round trips, so the "
    "signal can last longer, and the exact duration is not guaranteed, in particular not "
    "across a device or network outage. If the device is unreachable the signal may never be "
    "restored."
)
NO_PERSISTENCE_NOTE = (
    "Signals are kept in memory only: after a crash, kill or restart a signal that was still "
    "active stays on the device and its ID is unknown. An orderly shutdown makes one bounded "
    "restore attempt."
)

OperationId = Annotated[str, Field(pattern=OPERATION_ID_PATTERN)]


class StartSignalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    device_id: str = Field(
        min_length=1,
        max_length=64,
        description="Configured device ID; never a URL or discovered host.",
    )
    segment_ids: list[Annotated[int, Field(ge=0)]] = Field(
        min_length=1,
        max_length=MAX_TARGET_SEGMENTS,
        description=(
            "Unique IDs of existing active segments that show the signal; the signal never "
            "creates, resizes or removes segments."
        ),
    )
    color: list[Annotated[int, Field(ge=0, le=255)]] = Field(
        min_length=3,
        max_length=3,
        description=(
            "Signal colour as exactly three RGB channels, 0 to 255 each; a segment that "
            "reports four channels gets white 0. The effect is always Solid and the device's "
            "own brightness applies."
        ),
    )
    duration_seconds: int = Field(
        ge=1,
        le=MAX_DURATION_SECONDS,
        description="How long the signal is intended to last, 1 to 300 seconds; best effort.",
    )
    dry_run: bool = Field(
        default=False,
        description=(
            "Read the device and return the plan, the owned fields and the restoration plan "
            "without any write, signal record or reservation."
        ),
    )

    @field_validator("segment_ids")
    @classmethod
    def unique_segments(cls, value: list[int]) -> list[int]:
        if len(set(value)) != len(value):
            raise ValueError("segment_ids must be unique")
        return value


class GetSignalStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    operation_id: OperationId | None = Field(
        default=None,
        description=(
            "Operation ID returned by wled_start_signal. Omit to list all active signals and "
            "the most recent ended ones, newest first."
        ),
    )


class CancelSignalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    operation_id: OperationId = Field(
        description="Operation ID returned by wled_start_signal; cancelling ends it now."
    )


# ----------------------------------------------------------------------------- envelopes


def _limits() -> dict[str, JsonValue]:
    return {
        "max_active_signals": MAX_ACTIVE,
        "max_target_segments": MAX_TARGET_SEGMENTS,
        "max_duration_seconds": MAX_DURATION_SECONDS,
        "retained_ended_signals": RETAIN_ENDED,
    }


def _refusal(
    name: str, device_id: str | None, failure: ClientFailure, *, dry_run: bool = False
) -> Outcome:
    data = failure.data if isinstance(failure, SignalRefusal) else {}
    return Outcome(
        ok=False,
        operation=name,
        device_id=device_id,
        dry_run=dry_run,
        application="not_attempted",
        verification="not_requested",
        data=dict(data),
        error=failure.error,
    )


def _error_code(restoration: dict[str, JsonValue]) -> ErrorCode:
    code = restoration.get("error_code")
    for known in get_args(ErrorCode):
        if code == known:
            return known  # type: ignore[no-any-return]
    return "WRITE_OUTCOME_UNKNOWN"


def _axes(restoration: dict[str, JsonValue]) -> tuple[Application, Verification]:
    """The application/verification pair of an uncertain restoration, always a valid pair."""
    pair = (restoration.get("application"), restoration.get("verification"))
    if pair == ("not_attempted", "not_requested"):
        return "not_attempted", "not_requested"
    if pair == ("unknown", "mismatch"):
        return "unknown", "mismatch"
    return "unknown", "unknown"


def _restoration_failure(restoration: dict[str, JsonValue]) -> DomainError:
    return DomainError(
        code=_error_code(restoration),
        message="The restoration could not be established.",
        reconciliation=(
            "Read the device state and compare it with the captured values in data.signal.owned; "
            "restore explicitly if needed. Nothing is retried or replayed."
        ),
    )


def _record_warnings(record: SignalRecord) -> list[str]:
    restoration = record.restoration or {}
    attempts = restoration.get("attempts")
    if restoration.get("result") == "restored" and isinstance(attempts, int) and attempts > 1:
        return [
            "The restoration needed a second attempt after the device could not be reached "
            "at expiry; the signal lasted longer than requested."
        ]
    return []


def build_signal_operations(resources: Resources) -> tuple[Operation, ...]:
    signals: SignalManager = resources.signals

    def unknown_device(name: str, failure: ClientFailure) -> Outcome:
        return Outcome(
            ok=False,
            operation=name,
            device_id=None,
            application="not_attempted",
            verification="not_requested",
            error=failure.error,
        )

    async def start_signal(arguments: dict[str, Any]) -> Outcome:
        request = StartSignalRequest.model_validate(arguments)
        device_id = request.device_id
        try:
            resources.resolve(device_id)
        except ClientFailure as failure:
            return unknown_device(START, failure)
        r, g, b = request.color
        spec = SignalSpec(
            device_id, tuple(request.segment_ids), (r, g, b), request.duration_seconds
        )
        timing: dict[str, JsonValue] = {
            "best_effort": True,
            "duration_seconds": request.duration_seconds,
            "note": TIMING_NOTE,
        }
        if request.dry_run:
            try:
                plan = await signals.preview(spec)
            except ClientFailure as failure:
                return _refusal(START, device_id, failure, dry_run=True)
            return Outcome(
                ok=True,
                operation=START,
                device_id=device_id,
                dry_run=True,
                application="not_attempted",
                verification="not_requested",
                data={
                    "plan": plan.public,
                    "owned": plan.owned_public(),
                    "restoration_plan": plan.restoration_public(),
                    "unowned_observed": plan.unowned,
                    "timing": timing,
                },
                warnings=[*plan.warnings, NO_PERSISTENCE_NOTE],
            )
        try:
            result = await signals.start(spec)
        except SignalRefusal as failure:
            return _refusal(START, device_id, failure)
        return _start_outcome(result, timing)

    def _start_outcome(result: StartResult, timing: dict[str, JsonValue]) -> Outcome:
        outcome = result.outcome
        assert outcome is not None
        if result.kind == "refused":
            data: dict[str, JsonValue] = {}
            if isinstance(result.refusal, SignalRefusal):
                data = dict(result.refusal.data)
            return outcome.model_copy(update={"operation": START, "data": data})
        record, plan = result.record, result.plan
        assert record is not None and plan is not None
        if result.kind == "unverified":
            return outcome.model_copy(
                update={
                    "data": {
                        "operation_id": record.operation_id,
                        "reason": "apply_unverified",
                        "captured": plan.owned_public(),
                        "no_replay": True,
                    },
                    "warnings": [
                        "The write may have been applied. No timer was started and nothing will "
                        "be restored automatically; read the state and use the captured values "
                        "to restore explicitly if needed."
                    ],
                }
            )
        data = {
            "operation_id": record.operation_id,
            "status": record.status,
            "segment_ids": list(record.segment_ids),
            "started_at": record.started_at.isoformat(),
            "expires_at": None if record.expires_at is None else record.expires_at.isoformat(),
            "duration_seconds": record.duration_seconds,
            "owned": plan.owned_public(),
            "restoration_plan": plan.restoration_public(),
            "unowned_observed": plan.unowned,
            "timing": timing,
            "plan": plan.public,
        }
        return outcome.model_copy(
            update={"data": data, "warnings": [*plan.warnings, TIMING_NOTE, NO_PERSISTENCE_NOTE]}
        )

    async def get_status(arguments: dict[str, Any]) -> Outcome:
        identifier: str | None = arguments["operation_id"]
        if identifier is not None:
            try:
                record = signals.get(identifier)
            except SignalRefusal as failure:
                return _refusal(STATUS, None, failure)
            return Outcome(
                ok=True,
                operation=STATUS,
                device_id=record.device_id,
                application="not_attempted",
                verification="not_requested",
                data={"signal": signals.view(record), "count": 1, "limits": _limits()},
                warnings=_record_warnings(record),
            )
        records = signals.listing()
        return Outcome(
            ok=True,
            operation=STATUS,
            device_id=None,
            application="not_attempted",
            verification="not_requested",
            data={
                "signals": [signals.view(record) for record in records],
                "count": len(records),
                "active_count": signals.active_count(),
                "limits": _limits(),
            },
            warnings=[NO_PERSISTENCE_NOTE],
        )

    def _cancel_outcome(record: SignalRecord, already_ended: bool) -> Outcome:
        restoration = record.restoration or {}
        data: dict[str, JsonValue] = {"signal": signals.view(record)}
        common: dict[str, Any] = {
            "operation": CANCEL,
            "device_id": record.device_id,
            "data": data,
        }
        if already_ended:
            return Outcome(
                ok=True,
                application="not_attempted",
                verification="not_requested",
                warnings=["The signal had already ended; nothing was changed by this call."],
                **common,
            )
        result = restoration.get("result")
        if result == "restored":
            return Outcome(ok=True, application="applied", verification="verified", **common)
        if result == "skipped_conflict":
            return Outcome(
                ok=True,
                application="not_attempted",
                verification="not_requested",
                warnings=[
                    "The signal is cancelled but nothing was restored: an owned field no longer "
                    "holds the signal value (see data.signal.restoration.differences). The "
                    "device keeps the state it was found in."
                ],
                **common,
            )
        application, verification = _axes(restoration)
        return Outcome(
            ok=False,
            application=application,
            verification=verification,
            error=_restoration_failure(restoration),
            **common,
        )

    async def cancel_signal(arguments: dict[str, Any]) -> Outcome:
        try:
            record, already_ended = await signals.cancel(arguments["operation_id"])
        except SignalRefusal as failure:
            return _refusal(CANCEL, None, failure)
        return _cancel_outcome(record, already_ended)

    return (
        Operation(
            name=START,
            tool_class=ToolClass.CONTROL,
            description=(
                "Show an RGB colour on explicitly listed existing segments of one configured "
                "device for a bounded time (1 to 300 seconds), then restore exactly the fields "
                "this tool changed (colour slot 0, the Solid effect, and segment or master "
                "power only when it turned them on), but only if they still hold what the "
                "signal set. If someone changed them meanwhile the result is skipped_conflict "
                "and nothing is overwritten; a restoration that cannot be established is "
                "uncertain and is never replayed. Returns an operation ID and the captured "
                "prior values. One signal per device and at most eight per process; a second "
                "start is refused, not queued. Refused before any write: a running playlist, "
                "realtime data, an active nightlight, frozen segments, a master that is off "
                "while other segments would light up, zero brightness. Not a scheduler: no "
                "recurrence, no deferred start, no preset created or changed. Changes the live "
                "output only. " + TIMING_NOTE + " " + NO_PERSISTENCE_NOTE + " dry_run reads "
                "the device and returns the plan without any write."
            ),
            request_model=StartSignalRequest,
            execute=start_signal,
            annotations=START_ANNOTATIONS,
        ),
        Operation(
            name=STATUS,
            tool_class=ToolClass.READ,
            description=(
                "Read the state of temporary signals from this process: one signal by "
                "operation ID, or all active signals and the most recent ended ones (status "
                "active, restoring, restored, skipped_conflict or uncertain, with the owned "
                "fields and the restoration result). Reads process memory only and does not "
                "contact any device. " + NO_PERSISTENCE_NOTE + " Read-only."
            ),
            request_model=GetSignalStatusRequest,
            execute=get_status,
            annotations=READ_ONLY,
        ),
        Operation(
            name=CANCEL,
            tool_class=ToolClass.CONTROL,
            description=(
                "End a temporary signal now by operation ID: the server re-reads the device and "
                "restores the fields the signal changed, only if they still hold the signal "
                "value, then returns the result (restored, skipped_conflict or uncertain). "
                "There is no cancel-without-restore; patch the segment to keep a colour. "
                "Cancelling an ended signal changes nothing. A restore that cannot be "
                "established is uncertain and is never replayed. " + TIMING_NOTE
            ),
            request_model=CancelSignalRequest,
            execute=cancel_signal,
            annotations=CANCEL_ANNOTATIONS,
        ),
    )
