"""The process-wide signal manager of issue #28 (ISSUE-28-DEC-002, docs/contract/signals.md).

One ``SignalManager`` belongs to one ``Resources`` graph, so the stdio and the HTTP transport
share the same type, lifecycle and per-device locks (the manager opens one anyio task group in
``Resources.__aenter__`` and closes it in ``__aexit__``). Each signal is run by exactly one
manager task that applies, waits and restores; a calling request only hands work over and awaits
a result, so a dropped connection or a cancelled request never orphans an applied signal and
never causes a write by itself.

The task sets ``CURRENT_TOOL_CLASS`` to ``control`` itself for its whole life instead of
inheriting whatever the spawning request carried (G3, AR-01): the delayed restore is evaluated
as a ``control`` operation against the device's effective ceiling, never as the ambient
"unknown, assume manage" case that a restricted deployment refuses.

Nothing is persisted. A signal that is still active when the process dies stays applied on the
device and its ID is unknown afterwards (docs/contract/signals.md, "Shutdown and restart").
"""

from __future__ import annotations

import logging
import secrets
from collections import deque
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Literal

import anyio
from anyio.abc import TaskGroup
from pydantic import JsonValue

from wled_mcp.access import CURRENT_TOOL_CLASS, ToolClass
from wled_mcp.catalogs import AmbiguousName, UnknownName, load_catalog, resolve_name
from wled_mcp.client import ClientFailure, Endpoint
from wled_mcp.models import ErrorCode, Outcome
from wled_mcp.readmodels import Collector, as_dict, normalize_state
from wled_mcp.signals import (
    MAX_ACTIVE,
    MAX_DIFFERENCES,
    RETAIN_ENDED,
    RETRY_DELAY_SECONDS,
    SHUTDOWN_BUDGET_SECONDS,
    SOLID_EFFECT_NAME,
    RestorePlan,
    SignalConflict,
    SignalPlan,
    SignalRefusal,
    SignalSpec,
    build_restore_plan,
    build_signal_plan,
    compare,
)

if TYPE_CHECKING:
    from wled_mcp.resources import OperationContext, Resources

LOGGER = logging.getLogger("wled_mcp.signals")
RESTORE_OPERATION = "wled_signal_restore"
START_OPERATION = "wled_start_signal"
CLOCK_SLICE_SECONDS = 1.0

Status = Literal["active", "restoring", "restored", "skipped_conflict", "uncertain"]
ENDED_STATUSES: frozenset[str] = frozenset({"restored", "skipped_conflict", "uncertain"})
# A restore that failed before any POST left, with one of these codes, may be tried once more.
RETRYABLE_CODES: frozenset[str] = frozenset({"UNREACHABLE", "TIMEOUT"})


@dataclass
class SignalRecord:
    operation_id: str
    device_id: str
    segment_ids: tuple[int, ...]
    duration_seconds: int
    plan: SignalPlan
    seq: int
    started_at: datetime
    expires_at: datetime | None
    due: float | None
    status: Status = "active"
    ended_by: Literal["expired", "cancelled", "shutdown"] | None = None
    ended_at: datetime | None = None
    restoration: dict[str, JsonValue] | None = None
    # Set once the record is terminal; cancel awaits it, never a second restore.
    done: anyio.Event = field(default_factory=anyio.Event)
    # Wakes the timer wait (cancel, shutdown) and a pending retry pause (shutdown).
    wake: anyio.Event = field(default_factory=anyio.Event)


@dataclass
class StartResult:
    kind: Literal["started", "refused", "unverified"]
    outcome: Outcome | None = None
    record: SignalRecord | None = None
    plan: SignalPlan | None = None
    refusal: ClientFailure | None = None


@dataclass
class _Box:
    """One-shot hand-over from the signal task to the request that started it."""

    event: anyio.Event = field(default_factory=anyio.Event)
    result: StartResult | None = None
    error: BaseException | None = None

    def succeed(self, result: StartResult) -> None:
        if not self.event.is_set():
            self.result = result
            self.event.set()

    def fail(self, error: BaseException) -> None:
        if not self.event.is_set():
            self.error = error
            self.event.set()


@dataclass(frozen=True)
class _Attempt:
    kind: Literal["restored", "skipped_conflict", "uncertain"]
    application: str
    verification: str
    error_code: str | None = None
    differences: tuple[dict[str, JsonValue], ...] = ()
    write_attempted: bool = False
    reason: str | None = None


async def read_device(
    context: OperationContext,
) -> tuple[dict[str, JsonValue], dict[str, JsonValue], dict[str, JsonValue], dict[str, JsonValue]]:
    """Fresh state and info under the active lock and deadline: view, capabilities, info, state."""
    state = await context.read(Endpoint.STATE)
    info = await context.read(Endpoint.INFO)
    view, capabilities, _firmware, _unknown = normalize_state(state, info, Collector())
    return view, capabilities, as_dict(info), as_dict(state)


class SignalManager:
    def __init__(self, resources: Resources) -> None:
        self._resources = resources
        self._records: dict[str, SignalRecord] = {}
        self._ended: deque[str] = deque()
        # Device ID -> operation ID for every starting, active or restoring signal.
        self._reserved: dict[str, str] = {}
        # Operation ID -> finished event of its task (starting tasks have no record yet).
        self._running: dict[str, anyio.Event] = {}
        self._stack: AsyncExitStack | None = None
        self._group: TaskGroup | None = None
        self._closing = False
        self._seq = 0
        # Tests install a manual timer here, like ``Resources.poll_interval_seconds``.
        self.sleep_until: Callable[[float, anyio.Event], Awaitable[None]] = self._sleep_until
        self.shutdown_budget_seconds = SHUTDOWN_BUDGET_SECONDS

    # ------------------------------------------------------------------------- lifecycle

    async def open(self) -> None:
        if self._group is not None:
            return
        stack = AsyncExitStack()
        self._group = await stack.enter_async_context(anyio.create_task_group())
        self._stack = stack
        self._closing = False

    async def shutdown(self) -> None:
        """Orderly stop: admission closes, every active signal gets one conditional restore.

        All restores run concurrently inside their own tasks; this call only waits for them,
        shielded from the caller's cancellation and bounded by one total budget. Whatever has
        not finished is abandoned (its POST, if any, is uncertain) and may stay applied.
        """
        group = self._group
        if group is None or self._closing:
            return
        self._closing = True
        for record in list(self._records.values()):
            if record.status in ("active", "restoring"):
                self._request_end(record, "shutdown")
                record.wake.set()
        pending = list(self._running.values())
        with anyio.CancelScope(shield=True):
            with anyio.move_on_after(self.shutdown_budget_seconds) as budget:
                for finished in pending:
                    await finished.wait()
            if budget.cancelled_caught:
                abandoned = sum(1 for finished in pending if not finished.is_set())
                LOGGER.warning("signal event=shutdown_incomplete abandoned=%d", abandoned)
                group.cancel_scope.cancel()
                for finished in pending:
                    await finished.wait()

    async def close(self) -> None:
        stack, self._stack = self._stack, None
        group, self._group = self._group, None
        if stack is None or group is None:
            return
        group.cancel_scope.cancel()
        await stack.aclose()

    # ------------------------------------------------------------------------ admission

    def check_admission(self, device_id: str) -> None:
        """Raise the refusal a start would get now; no reservation is made."""
        if self._closing:
            raise SignalRefusal(
                "shutting_down", "The service is shutting down and accepts no new signals."
            )
        active = self._reserved.get(device_id)
        if active is not None:
            data: dict[str, JsonValue] = {}
            if active in self._records:
                data["active_operation_id"] = active
            raise SignalRefusal(
                "signal_active",
                "A signal is already starting, active or restoring on this device; cancel it "
                "or wait for it to end. Signals are never queued or replaced.",
                data=data,
            )
        if len(self._reserved) >= MAX_ACTIVE:
            raise SignalRefusal(
                "signal_limit",
                f"At most {MAX_ACTIVE} signals can run at the same time in this process.",
                data={"max_active": MAX_ACTIVE},
            )

    def _admit(self, device_id: str) -> str:
        if self._group is None:
            raise RuntimeError("The signal manager is not running.")
        self.check_admission(device_id)
        operation_id = "sig-" + secrets.token_hex(8)
        # No await between the check and the reservation: two concurrent starts cannot both win.
        self._reserved[device_id] = operation_id
        return operation_id

    def _release(self, device_id: str, operation_id: str) -> None:
        if self._reserved.get(device_id) == operation_id:
            del self._reserved[device_id]

    # -------------------------------------------------------------------------- tool API

    async def preview(self, spec: SignalSpec) -> SignalPlan:
        """The plan a start would use now (bounded reads under the lock); no record, no slot."""
        self.check_admission(spec.device_id)
        async with self._resources.operation(spec.device_id) as context:
            view, capabilities, info, state = await read_device(context)
            solid_id = await self._solid_id(context)
        return build_signal_plan(spec, view, capabilities, info, state, solid_id)

    async def start(self, spec: SignalSpec) -> StartResult:
        operation_id = self._admit(spec.device_id)
        box = _Box()
        finished = anyio.Event()
        self._running[operation_id] = finished
        assert self._group is not None
        try:
            self._group.start_soon(self._run, spec, operation_id, box, finished)
        except BaseException:
            self._running.pop(operation_id, None)
            self._release(spec.device_id, operation_id)
            raise
        # Cancelling this wait (a dropped connection) leaves the task running on its own.
        await box.event.wait()
        if box.error is not None:
            raise box.error
        assert box.result is not None
        return box.result

    async def cancel(self, operation_id: str) -> tuple[SignalRecord, bool]:
        """End a signal now (conditional restore) and wait for its result.

        Returns the record and whether it had already ended before this call.
        """
        record = self._records.get(operation_id)
        if record is None:
            raise self.unknown(operation_id)
        already_ended = record.status in ENDED_STATUSES
        if record.status == "active" and self._request_end(record, "cancelled"):
            record.wake.set()
        await record.done.wait()
        return record, already_ended

    def get(self, operation_id: str) -> SignalRecord:
        record = self._records.get(operation_id)
        if record is None:
            raise self.unknown(operation_id)
        return record

    @staticmethod
    def unknown(operation_id: str) -> SignalRefusal:
        return SignalRefusal(
            "unknown_signal",
            "No signal with this operation ID is known to this process. Signals are kept in "
            "memory only; after a restart every ID is unknown.",
        )

    def listing(self) -> list[SignalRecord]:
        """Active signals first, then the retained ended ones, each newest first."""
        records = sorted(self._records.values(), key=lambda record: record.seq, reverse=True)
        return [r for r in records if r.status not in ENDED_STATUSES] + [
            r for r in records if r.status in ENDED_STATUSES
        ]

    def active_count(self) -> int:
        return sum(1 for r in self._records.values() if r.status not in ENDED_STATUSES)

    def view(self, record: SignalRecord) -> dict[str, JsonValue]:
        resources = self._resources
        remaining: float | None = None
        if record.status == "active" and record.due is not None:
            remaining = max(0.0, round(record.due - resources.clock.monotonic(), 1))
        return {
            "operation_id": record.operation_id,
            "device_id": record.device_id,
            "segment_ids": list(record.segment_ids),
            "status": record.status,
            "ended_by": record.ended_by,
            "started_at": record.started_at.isoformat(),
            "expires_at": None if record.expires_at is None else record.expires_at.isoformat(),
            "ended_at": None if record.ended_at is None else record.ended_at.isoformat(),
            "duration_seconds": record.duration_seconds,
            "remaining_seconds": remaining,
            "owned": record.plan.owned_public(),
            "unowned_observed": record.plan.unowned,
            "restoration": record.restoration,
        }

    # --------------------------------------------------------------------- state changes

    def _request_end(
        self, record: SignalRecord, by: Literal["expired", "cancelled", "shutdown"]
    ) -> bool:
        """Synchronous check-and-set: only the first of cancel, expiry and shutdown wins."""
        if record.status != "active":
            return False
        record.status = "restoring"
        record.ended_by = by
        return True

    def _register(self, record: SignalRecord) -> None:
        self._records[record.operation_id] = record
        if self._closing:
            self._request_end(record, "shutdown")

    def _retain(self, operation_id: str) -> None:
        """Keep the newest ``RETAIN_ENDED`` ended records; older ones are forgotten."""
        self._ended.append(operation_id)
        while len(self._ended) > RETAIN_ENDED:
            self._records.pop(self._ended.popleft(), None)

    def _conclude(self, record: SignalRecord, attempt: _Attempt, attempts: int) -> None:
        resources = self._resources
        record.restoration = {
            "result": attempt.kind,
            "application": attempt.application,
            "verification": attempt.verification,
            "error_code": attempt.error_code,
            "differences": list(attempt.differences),
            "write_attempted": attempt.write_attempted,
            "attempts": attempts,
            "reason": attempt.reason,
        }
        record.status = attempt.kind
        record.ended_at = resources.clock.now()
        self._release(record.device_id, record.operation_id)
        self._retain(record.operation_id)
        if attempt.write_attempted:
            # Evidence for wled_explain_lighting (#30): a delayed write of this server's own.
            resources.monitor.last_control.record(
                record.device_id,
                RESTORE_OPERATION,
                attempt.application,
                attempt.verification,
                attempt.error_code,
            )
        self._log(attempt.kind, record, attempt.error_code)
        record.done.set()

    def _log(self, event: str, record: SignalRecord, code: str | None = None) -> None:
        parts = [f"event={event}", f"operation_id={record.operation_id}", f"status={record.status}"]
        if record.ended_by is not None:
            parts.append(f"ended_by={record.ended_by}")
        if code is not None:
            parts.append(f"error_code={code}")
        if self._resources.monitor.is_configured(record.device_id):
            parts.append(f"device_id={record.device_id}")
        LOGGER.info("signal %s", " ".join(parts))

    # ----------------------------------------------------------------------- signal task

    async def _run(
        self, spec: SignalSpec, operation_id: str, box: _Box, finished: anyio.Event
    ) -> None:
        # Explicit class for the whole task: apply, wait and every restore (TD-28-14).
        CURRENT_TOOL_CLASS.set(ToolClass.CONTROL)
        record: SignalRecord | None = None
        try:
            record = await self._apply(spec, operation_id, box)
            if record is not None:
                ended_by = await self._await_end(record)
                await self._restore(record, ended_by)
        except anyio.get_cancelled_exc_class():
            if record is not None and record.status not in ENDED_STATUSES:
                # Abandoned at shutdown: a POST that was in flight is uncertain.
                self._conclude(
                    record,
                    _Attempt(
                        "uncertain",
                        "unknown",
                        "unknown",
                        "TIMEOUT",
                        write_attempted=True,
                        reason="shutdown_abandoned",
                    ),
                    attempts=1,
                )
            raise
        except Exception:
            LOGGER.error("signal event=internal_failure operation_id=%s", operation_id)
            if record is not None and record.status not in ENDED_STATUSES:
                self._conclude(
                    record,
                    _Attempt("uncertain", "unknown", "unknown", reason="internal_failure"),
                    attempts=1,
                )
            box.fail(RuntimeError("Signal task failed."))
        finally:
            self._release(spec.device_id, operation_id)
            self._running.pop(operation_id, None)
            box.fail(RuntimeError("Signal task ended without a result."))
            finished.set()

    async def _solid_id(self, context: OperationContext) -> int:
        try:
            view = await load_catalog(context, self._resources.metadata_cache, "effects")
            return resolve_name(view.entry, "effects", SOLID_EFFECT_NAME)
        except (UnknownName, AmbiguousName):
            raise SignalRefusal(
                "effect_unavailable",
                "The device has no unambiguous 'Solid' effect.",
                code="UNSUPPORTED_CAPABILITY",
            ) from None

    async def _apply(self, spec: SignalSpec, operation_id: str, box: _Box) -> SignalRecord | None:
        resources = self._resources
        plans: dict[str, SignalPlan] = {}
        failures: dict[str, ClientFailure] = {}

        async def prepare(context: OperationContext) -> dict[str, JsonValue]:
            try:
                view, capabilities, info, state = await read_device(context)
                solid_id = await self._solid_id(context)
                plans["plan"] = build_signal_plan(spec, view, capabilities, info, state, solid_id)
            except ClientFailure as failure:
                failures["failure"] = failure
                raise
            return plans["plan"].payload

        def matches(state: JsonValue) -> bool:
            plan = plans.get("plan")
            return plan is not None and plan.matches(state)

        with anyio.CancelScope(shield=True):
            outcome = await resources.write_verified(
                spec.device_id, START_OPERATION, prepare, matches
            )
        plan = plans.get("plan")
        if not outcome.ok and (outcome.application == "not_attempted" or plan is None):
            self._release(spec.device_id, operation_id)
            box.succeed(StartResult("refused", outcome=outcome, refusal=failures.get("failure")))
            return None
        assert plan is not None
        now = resources.clock.now()
        self._seq += 1
        if not outcome.ok:
            # The POST may have reached the device: never auto-restore (no blind replay).
            record = SignalRecord(
                operation_id,
                spec.device_id,
                spec.segment_ids,
                spec.duration_seconds,
                plan,
                self._seq,
                started_at=now,
                expires_at=None,
                due=None,
                status="uncertain",
                ended_at=now,
                restoration={
                    "result": "not_attempted",
                    "application": "not_attempted",
                    "verification": "not_requested",
                    "error_code": outcome.error.code if outcome.error else None,
                    "differences": [],
                    "write_attempted": False,
                    "attempts": 0,
                    "reason": "apply_unverified",
                },
            )
            record.done.set()
            self._register(record)
            self._release(spec.device_id, operation_id)
            self._retain(operation_id)
            self._log("uncertain", record, outcome.error.code if outcome.error else None)
            box.succeed(StartResult("unverified", outcome=outcome, record=record, plan=plan))
            return None
        record = SignalRecord(
            operation_id,
            spec.device_id,
            spec.segment_ids,
            spec.duration_seconds,
            plan,
            self._seq,
            started_at=now,
            expires_at=now + timedelta(seconds=spec.duration_seconds),
            due=resources.clock.monotonic() + spec.duration_seconds,
        )
        self._register(record)
        self._log("started", record)
        box.succeed(StartResult("started", outcome=outcome, record=record, plan=plan))
        return record

    async def _sleep_until(self, due: float, wake: anyio.Event) -> None:
        """Wait until the monotonic clock reaches ``due`` or ``wake`` is set (slices re-read it)."""
        clock = self._resources.clock
        while not wake.is_set():
            remaining = due - clock.monotonic()
            if remaining <= 0:
                return
            with anyio.move_on_after(min(remaining, CLOCK_SLICE_SECONDS)):
                await wake.wait()

    async def _await_end(self, record: SignalRecord) -> Literal["expired", "cancelled", "shutdown"]:
        if record.ended_by is None:
            assert record.due is not None
            await self.sleep_until(record.due, record.wake)
            self._request_end(record, "expired")  # no-op when cancel or shutdown won the race
        assert record.ended_by is not None
        return record.ended_by

    async def _restore(
        self, record: SignalRecord, ended_by: Literal["expired", "cancelled", "shutdown"]
    ) -> None:
        attempts = 0
        while True:
            attempts += 1
            attempt = await self._attempt(record)
            retry = (
                attempt.kind == "uncertain"
                and not attempt.write_attempted
                and attempt.error_code in RETRYABLE_CODES
                and ended_by == "expired"
                and attempts == 1
                and not self._closing
            )
            if not retry:
                break
            # A failure before any POST left is not a replay: one fresh attempt after a pause.
            await self.sleep_until(
                self._resources.clock.monotonic() + RETRY_DELAY_SECONDS, record.wake
            )
        self._conclude(record, attempt, attempts)

    async def _attempt(self, record: SignalRecord) -> _Attempt:
        """One fresh read, compare and conditional restore under the device lock."""
        conflicts: dict[str, SignalConflict] = {}
        plans: dict[str, RestorePlan] = {}

        async def prepare(context: OperationContext) -> dict[str, JsonValue]:
            view, capabilities, info, state = await read_device(context)
            differences = compare(record.plan.owned, record.plan.geometry, state, info)
            if differences:
                conflicts["conflict"] = SignalConflict(differences)
                raise conflicts["conflict"]
            plans["plan"] = build_restore_plan(
                record.plan.owned, record.device_id, view, capabilities, info, state
            )
            return plans["plan"].payload

        def matches(state: JsonValue) -> bool:
            plan = plans.get("plan")
            return plan is not None and plan.matches(state)

        outcome = await self._resources.write_verified(
            record.device_id, RESTORE_OPERATION, prepare, matches
        )
        if outcome.ok:
            return _Attempt("restored", "applied", "verified", write_attempted=True)
        conflict = conflicts.get("conflict")
        if conflict is not None and outcome.application == "not_attempted":
            return _Attempt(
                "skipped_conflict",
                "not_attempted",
                "not_requested",
                differences=tuple(conflict.differences[:MAX_DIFFERENCES]),
            )
        code: ErrorCode | None = outcome.error.code if outcome.error is not None else None
        return _Attempt(
            "uncertain",
            outcome.application,
            outcome.verification,
            code,
            write_attempted=outcome.application != "not_attempted",
        )
