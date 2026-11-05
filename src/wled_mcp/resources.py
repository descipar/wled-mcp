"""One process resource graph; future sessions share clients, caches and device locks."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from functools import partial
from typing import Any, Literal

import anyio
import anyio.lowlevel
import httpx2 as httpx
from pydantic import JsonValue

from wled_mcp.backups import BackupRecord, Firmware, RestorePlan, Snapshot, SnapshotStore
from wled_mcp.catalogs import CatalogCache, Clock
from wled_mcp.client import ClientFailure, Deadline, Endpoint, WLEDClient
from wled_mcp.config import Device, StartupConfig
from wled_mcp.models import DomainError, Outcome

SequenceKind = Literal[
    "success",
    "final_mismatch",
    "failed",
    "stopped",
    "uncertain_unreadable",
    "uncertain_differs",
    "uncertain_matching",
]


@dataclass(frozen=True)
class WriteStep:
    """One single-request write plus the readback check that proves it."""

    action: str
    segment_id: int | None
    payload: dict[str, JsonValue]
    matches: Callable[[JsonValue], bool]


@dataclass(frozen=True)
class SequencePlan:
    """Ordered steps, an exact final check and a bounded observation summary."""

    steps: tuple[WriteStep, ...]
    final_matches: Callable[[JsonValue], bool]
    observe: Callable[[JsonValue], JsonValue]


@dataclass(frozen=True)
class Verdict:
    """One evaluation of a polled readback against a write's postcondition."""

    matched: bool
    observed: JsonValue = None
    # The observed target is identical to its pre-dispatch value (no visible effect yet).
    unchanged: bool = False
    differences: tuple[str, ...] = ()
    interference: tuple[int, ...] = ()
    warnings: tuple[str, ...] = ()
    data: dict[str, JsonValue] = field(default_factory=dict)


@dataclass(frozen=True)
class PolledWrite:
    """One single-POST write whose outcome is decided only by bounded polled readback."""

    endpoint: Endpoint
    payload: dict[str, JsonValue]
    evaluate: Callable[[JsonValue], Verdict]
    data: dict[str, JsonValue]
    reconciliation: str


@dataclass
class _PollRecord:
    plan: PolledWrite | None = None
    post_failed: bool = False
    last: Verdict | None = None


@dataclass
class OperationContext:
    device: Device
    client: WLEDClient
    deadline: Deadline
    dispatched: bool = False
    store: SnapshotStore | None = None
    backup_records: list[BackupRecord] = field(default_factory=list)

    async def backup_preset(
        self, preset_id: int, preset: dict[str, JsonValue], firmware: Firmware
    ) -> BackupRecord:
        """Snapshot seam used by the destructive preset tools (issue #9).

        Call inside the operation (device lock held) with a freshly read preset
        object, right before the POST. A raised BACKUP_FAILED in `prepare` aborts
        before any dispatch. The snapshot is kept even if the write later fails.
        """
        if self.store is None:
            raise ClientFailure("BACKUP_FAILED", "Snapshot storage is not available.")
        # Shielded: a cancelled call must not leave a half-promoted snapshot.
        with anyio.CancelScope(shield=True):
            record = await anyio.to_thread.run_sync(
                partial(self.store.backup_preset, self.device.id, preset_id, preset, firmware)
            )
        self.backup_records.append(record)
        # An outer cancellation that arrived during the shielded write aborts here,
        # before any dispatch; the durable snapshot is kept.
        await anyio.lowlevel.checkpoint()
        return record

    async def read(self, endpoint: Endpoint) -> JsonValue:
        return await self.client.read(self.device, endpoint, self.deadline)


class Resources:
    def __init__(
        self,
        config: StartupConfig,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.config = config
        self.clock = clock if clock is not None else Clock()
        self.inventory = config.devices
        self._devices = {device.id: device for device in self.inventory}
        self.client = WLEDClient(config.http, transport)
        self.locks = {device.id: anyio.Lock() for device in self.inventory}
        # One shared effect/palette catalog cache (issue #5); never holds state/info.
        self.metadata_cache = CatalogCache(config.http.catalog_cache_seconds, self.clock)
        # Poll interval for persistent-file/activation readbacks (tests shorten it).
        self.poll_interval_seconds = 0.1
        self.backups = SnapshotStore(
            config.data_dir / "backups",
            config.backups.retain_per_device,
            lambda: self.clock.now(),
        )

    async def __aenter__(self) -> "Resources":
        return self

    async def __aexit__(self, *args: object) -> None:
        with anyio.CancelScope(shield=True):
            await self.client.aclose()

    def resolve(self, device_id: str) -> Device:
        try:
            return self._devices[device_id]
        except KeyError:
            raise ClientFailure("UNKNOWN_DEVICE", "Unknown configured device ID.") from None

    @asynccontextmanager
    async def operation(self, device_id: str) -> AsyncIterator[OperationContext]:
        device = self.resolve(device_id)
        deadline = Deadline.after(self.config.http.operation_timeout_seconds)
        try:
            with anyio.fail_after(deadline.remaining()):
                async with self.locks[device_id]:
                    yield OperationContext(device, self.client, deadline, store=self.backups)
        except TimeoutError:
            raise ClientFailure("TIMEOUT", "Operation deadline expired.", retryable=True) from None

    async def load_snapshot(self, device_id: str, backup_id: str) -> Snapshot:
        """Validated read of one snapshot; unknown devices fail before any filesystem access."""
        self.resolve(device_id)
        return await anyio.to_thread.run_sync(self.backups.load, device_id, backup_id)

    async def plan_restore(self, device_id: str, backup_id: str, **facts: Any) -> RestorePlan:
        """Read-only restoration plan from caller-supplied device facts (no device I/O)."""
        self.resolve(device_id)
        return await anyio.to_thread.run_sync(
            partial(self.backups.plan_restore, device_id, backup_id, **facts)
        )

    async def write_verified(
        self,
        device_id: str,
        operation: str,
        prepare: Callable[[OperationContext], Awaitable[dict[str, JsonValue]]],
        matches: Callable[[JsonValue], bool],
    ) -> Outcome:
        """Internal foundation, not a public setter. Prepare validates a full future plan."""
        seen: list[OperationContext] = []
        outcome = await self._write_verified(device_id, operation, prepare, matches, seen)
        records = seen[0].backup_records if seen else []
        if not records:
            return outcome
        warnings = [w for record in records for w in record.warnings]
        return outcome.model_copy(
            update={
                "data": {**outcome.data, "backup_id": records[-1].backup_id},
                "warnings": [*outcome.warnings, *warnings],
            }
        )

    async def _write_verified(
        self,
        device_id: str,
        operation: str,
        prepare: Callable[[OperationContext], Awaitable[dict[str, JsonValue]]],
        matches: Callable[[JsonValue], bool],
        seen: list[OperationContext],
    ) -> Outcome:
        dispatched = False
        try:
            async with self.operation(device_id) as context:
                seen.append(context)
                payload = await prepare(context)
                body = self.client.encode_payload(payload)
                remaining = context.deadline.remaining()
                if remaining < 0.02:
                    raise ClientFailure(
                        "TIMEOUT", "Insufficient remaining write/verification budget."
                    )
                # Reserve 25% (at most one second) for bounded readback after dispatch.
                reserve = min(1.0, remaining * 0.25)
                dispatch_deadline = Deadline(context.deadline.expires - reserve)
                dispatch_deadline.remaining()
                dispatched = context.dispatched = True
                try:
                    await self.client.post_state(context.device, body, dispatch_deadline)
                except ClientFailure:
                    pass  # ACK/errors never establish the postcondition or trigger replay.
                try:
                    state = await context.read(Endpoint.STATE)
                except ClientFailure:
                    return self._uncertain(device_id, operation)
                if matches(state):
                    return Outcome(
                        ok=True,
                        operation=operation,
                        device_id=device_id,
                        application="applied",
                        verification="verified",
                        data={"state": state},
                    )
                return Outcome(
                    ok=False,
                    operation=operation,
                    device_id=device_id,
                    application="unknown",
                    verification="mismatch",
                    error=DomainError(
                        code="VERIFICATION_MISMATCH",
                        message="Readback did not match the requested postcondition.",
                        reconciliation="Inspect state explicitly; do not replay the write.",
                    ),
                )
        except ClientFailure as failure:
            if dispatched:
                return self._uncertain(device_id, operation)
            return Outcome(
                ok=False,
                operation=operation,
                device_id=device_id,
                application="not_attempted",
                verification="not_requested",
                error=failure.error,
            )
        except Exception:
            if dispatched:
                return self._uncertain(device_id, operation)
            return Outcome(
                ok=False,
                operation=operation,
                device_id=device_id,
                application="not_attempted",
                verification="not_requested",
                error=DomainError(
                    code="VALIDATION_ERROR",
                    message="Operation preparation failed.",
                    reconciliation="Correct the requested plan before writing.",
                ),
            )

    async def write_sequence_verified(
        self,
        device_id: str,
        operation: str,
        prepare: Callable[[OperationContext], Awaitable[SequencePlan]],
    ) -> Outcome:
        """Multi-step write under ONE lock and deadline; every step is read back.

        Exactly one POST attempt per step, never replayed. A step that is uncertain
        or fails verification stops the sequence: no later (especially destructive)
        step is dispatched and nothing is rolled back or corrected. Unlike
        `write_verified`, this does not carry `backup_id` or prune warnings into the
        outcome (segment/layout writes need no snapshot). The preset tools use
        `write_polled`, which does carry them.
        """
        plan: SequencePlan | None = None
        statuses: list[str] = []
        in_flight: int | None = None
        observed: JsonValue = None
        try:
            async with self.operation(device_id) as context:
                plan = await prepare(context)
                if not plan.steps:
                    return Outcome(
                        ok=True,
                        operation=operation,
                        device_id=device_id,
                        application="not_attempted",
                        verification="not_requested",
                        data={"steps_report": [], "completed_steps": 0, "remaining_steps": []},
                    )
                bodies = [self.client.encode_payload(step.payload) for step in plan.steps]
                last_state: JsonValue = None
                total = len(plan.steps)
                for index, step in enumerate(plan.steps):
                    try:
                        remaining = context.deadline.remaining()
                        if remaining < 0.02:
                            raise ClientFailure(
                                "TIMEOUT", "Insufficient remaining write/verification budget."
                            )
                        reserve = min(1.0, remaining * 0.25)
                        dispatch_deadline = Deadline(context.deadline.expires - reserve)
                        dispatch_deadline.remaining()
                    except ClientFailure as failure:
                        return self._sequence_outcome(
                            device_id, operation, plan, statuses, "stopped", observed, failure.error
                        )
                    context.dispatched = True
                    in_flight = index
                    post_failed = False
                    try:
                        await self.client.post_state(
                            context.device, bodies[index], dispatch_deadline
                        )
                    except ClientFailure:
                        post_failed = True  # ACK/errors never establish the postcondition.
                    try:
                        last_state = await context.read(Endpoint.STATE)
                    except ClientFailure:
                        statuses.append("uncertain")
                        in_flight = None
                        return self._sequence_outcome(
                            device_id, operation, plan, statuses, "uncertain_unreadable", observed
                        )
                    observed = plan.observe(last_state)
                    is_last = index == total - 1
                    matched = step.matches(last_state)
                    if post_failed:
                        if matched and is_last and plan.final_matches(last_state):
                            statuses.append("verified")
                            in_flight = None
                            break
                        statuses.append("uncertain")
                        in_flight = None
                        kind: SequenceKind = (
                            "uncertain_matching" if matched else "uncertain_differs"
                        )
                        return self._sequence_outcome(
                            device_id, operation, plan, statuses, kind, observed
                        )
                    if not matched:
                        statuses.append("failed")
                        in_flight = None
                        return self._sequence_outcome(
                            device_id, operation, plan, statuses, "failed", observed
                        )
                    statuses.append("verified")
                    in_flight = None
                if not plan.final_matches(last_state):
                    return self._sequence_outcome(
                        device_id, operation, plan, statuses, "final_mismatch", observed
                    )
                return self._sequence_outcome(
                    device_id, operation, plan, statuses, "success", observed, state=last_state
                )
        except ClientFailure as failure:
            if plan is not None and context_dispatched(statuses, in_flight):
                if in_flight is not None:
                    statuses.append("uncertain")
                    return self._sequence_outcome(
                        device_id, operation, plan, statuses, "uncertain_unreadable", observed
                    )
                return self._sequence_outcome(
                    device_id, operation, plan, statuses, "stopped", observed, failure.error
                )
            return Outcome(
                ok=False,
                operation=operation,
                device_id=device_id,
                application="not_attempted",
                verification="not_requested",
                error=failure.error,
            )
        except Exception:
            if plan is not None and context_dispatched(statuses, in_flight):
                if in_flight is not None:
                    statuses.append("uncertain")
                return self._sequence_outcome(
                    device_id, operation, plan, statuses, "uncertain_unreadable", observed
                )
            return Outcome(
                ok=False,
                operation=operation,
                device_id=device_id,
                application="not_attempted",
                verification="not_requested",
                error=DomainError(
                    code="VALIDATION_ERROR",
                    message="Operation preparation failed.",
                    reconciliation="Correct the requested plan before writing.",
                ),
            )

    async def write_polled(
        self,
        device_id: str,
        operation: str,
        prepare: Callable[[OperationContext], Awaitable[PolledWrite]],
    ) -> Outcome:
        """Single-POST write decided only by bounded polled readback (issue #9).

        `prepare` runs inside the device lock and the one operation deadline, validates
        everything (including snapshot and collision recheck) and raises before dispatch
        on any problem, so nothing is sent. After the single POST (never replayed) the
        readback endpoint is polled until the postcondition holds or the deadline ends.
        The last readable observation survives an expired deadline.
        """
        seen: list[OperationContext] = []
        outcome = await self._write_polled(device_id, operation, prepare, seen)
        records = seen[0].backup_records if seen else []
        if not records:
            return outcome
        warnings = [w for record in records for w in record.warnings]
        return outcome.model_copy(
            update={
                "data": {**outcome.data, "backup_id": records[-1].backup_id},
                "warnings": [*outcome.warnings, *warnings],
            }
        )

    async def _write_polled(
        self,
        device_id: str,
        operation: str,
        prepare: Callable[[OperationContext], Awaitable[PolledWrite]],
        seen: list[OperationContext],
    ) -> Outcome:
        record = _PollRecord()
        dispatched = False
        try:
            async with self.operation(device_id) as context:
                seen.append(context)
                plan = record.plan = await prepare(context)
                body = self.client.encode_payload(plan.payload)
                remaining = context.deadline.remaining()
                if remaining < 0.02:
                    raise ClientFailure(
                        "TIMEOUT", "Insufficient remaining write/verification budget."
                    )
                reserve = min(1.0, remaining * 0.25)
                dispatch_deadline = Deadline(context.deadline.expires - reserve)
                dispatch_deadline.remaining()
                dispatched = context.dispatched = True
                try:
                    await self.client.post_state(context.device, body, dispatch_deadline)
                except ClientFailure:
                    record.post_failed = True  # ACK/errors never establish the postcondition.
                while True:
                    try:
                        value = await context.read(plan.endpoint)
                    except ClientFailure:
                        value = None  # unreadable poll; the last readable observation stays
                    if isinstance(value, dict):  # anything else is an unreadable poll
                        verdict = plan.evaluate(value)
                        if verdict.matched:
                            return self._polled_success(device_id, operation, plan, verdict, record)
                        record.last = verdict
                    # Raises TIMEOUT at the deadline; handled below with the last observation.
                    await anyio.sleep(min(self.poll_interval_seconds, context.deadline.remaining()))
        except ClientFailure as failure:
            if dispatched:
                return self._polled_uncertain(device_id, operation, record)
            return Outcome(
                ok=False,
                operation=operation,
                device_id=device_id,
                application="not_attempted",
                verification="not_requested",
                error=failure.error,
            )
        except Exception:
            if dispatched:
                return self._polled_uncertain(device_id, operation, record)
            return Outcome(
                ok=False,
                operation=operation,
                device_id=device_id,
                application="not_attempted",
                verification="not_requested",
                error=DomainError(
                    code="VALIDATION_ERROR",
                    message="Operation preparation failed.",
                    reconciliation="Correct the requested plan before writing.",
                ),
            )

    @staticmethod
    def _polled_success(
        device_id: str,
        operation: str,
        plan: PolledWrite,
        verdict: Verdict,
        record: _PollRecord,
    ) -> Outcome:
        data: dict[str, JsonValue] = {**plan.data, **verdict.data}
        warnings = list(verdict.warnings)
        if verdict.interference:
            data["interference"] = list(verdict.interference)
            warnings.append(
                "Unrelated preset entries changed during the operation (IDs in data.interference);"
                " they were reported, not corrected."
            )
        if record.post_failed:
            warnings.append("Transport error during write; outcome reconciled by readback.")
        return Outcome(
            ok=True,
            operation=operation,
            device_id=device_id,
            application="applied",
            verification="verified",
            data=data,
            warnings=warnings,
        )

    @staticmethod
    def _polled_uncertain(device_id: str, operation: str, record: _PollRecord) -> Outcome:
        plan, last = record.plan, record.last
        data: dict[str, JsonValue] = dict(plan.data) if plan is not None else {}
        data["no_replay"] = True
        reconciliation = (
            plan.reconciliation
            if plan is not None
            else "Perform an explicit read; do not replay the write."
        )
        # A failed POST with the target still unchanged cannot be told from "not applied".
        if last is not None and not (record.post_failed and last.unchanged):
            data["observed"] = last.observed
            if last.differences:
                data["differences"] = list(last.differences)
            if last.interference:
                data["interference"] = list(last.interference)
            return Outcome(
                ok=False,
                operation=operation,
                device_id=device_id,
                application="unknown",
                verification="mismatch",
                data=data,
                error=DomainError(
                    code="VERIFICATION_MISMATCH",
                    message="Readback did not match the requested postcondition.",
                    reconciliation=reconciliation,
                ),
            )
        return Outcome(
            ok=False,
            operation=operation,
            device_id=device_id,
            application="unknown",
            verification="unknown",
            data=data,
            error=DomainError(
                code="WRITE_OUTCOME_UNKNOWN",
                message="Write outcome could not be verified.",
                reconciliation=reconciliation,
            ),
        )

    @staticmethod
    def _sequence_outcome(
        device_id: str,
        operation: str,
        plan: SequencePlan,
        statuses: list[str],
        kind: SequenceKind,
        observed: JsonValue,
        error: DomainError | None = None,
        state: JsonValue = None,
    ) -> Outcome:
        report: list[JsonValue] = []
        remaining: list[JsonValue] = []
        for index, step in enumerate(plan.steps):
            status = statuses[index] if index < len(statuses) else "not_dispatched"
            entry: dict[str, JsonValue] = {
                "index": index,
                "action": step.action,
                "id": step.segment_id,
            }
            report.append({**entry, "status": status})
            if status != "verified":
                remaining.append(entry)
        verified = statuses.count("verified")
        data: dict[str, JsonValue] = {
            "steps_report": report,
            "completed_steps": verified,
            "remaining_steps": remaining,
        }
        if kind == "success":
            data["state"] = state
            return Outcome(
                ok=True,
                operation=operation,
                device_id=device_id,
                application="applied",
                verification="verified",
                data=data,
            )
        data["observed"] = observed
        data["no_replay"] = True
        mismatch = DomainError(
            code="VERIFICATION_MISMATCH",
            message="Readback did not match the planned postcondition.",
            reconciliation="Inspect state explicitly; do not replay the write.",
        )
        if kind in ("final_mismatch", "failed"):
            return Outcome(
                ok=False,
                operation=operation,
                device_id=device_id,
                application="applied" if verified else "unknown",
                verification="mismatch",
                data=data,
                error=mismatch,
            )
        if kind == "stopped":
            assert error is not None
            return Outcome(
                ok=False,
                operation=operation,
                device_id=device_id,
                application="applied" if verified else "not_attempted",
                verification="mismatch" if verified else "not_requested",
                data=data if verified else {},
                error=error,
            )
        if kind == "uncertain_differs":
            return Outcome(
                ok=False,
                operation=operation,
                device_id=device_id,
                application="unknown",
                verification="mismatch",
                data=data,
                error=mismatch,
            )
        return Outcome(
            ok=False,
            operation=operation,
            device_id=device_id,
            application="unknown",
            verification="unknown",
            data=data,
            error=DomainError(
                code="WRITE_OUTCOME_UNKNOWN",
                message="Write outcome could not be verified.",
                reconciliation="Perform an explicit read; do not replay the write.",
            ),
        )

    @staticmethod
    def _uncertain(device_id: str, operation: str) -> Outcome:
        return Outcome(
            ok=False,
            operation=operation,
            device_id=device_id,
            application="unknown",
            verification="unknown",
            error=DomainError(
                code="WRITE_OUTCOME_UNKNOWN",
                message="Write outcome could not be verified.",
                reconciliation="Perform an explicit read; do not replay the write.",
            ),
        )


def context_dispatched(statuses: list[str], in_flight: int | None) -> bool:
    """True once any step of a sequence may have reached the device."""
    return bool(statuses) or in_flight is not None
