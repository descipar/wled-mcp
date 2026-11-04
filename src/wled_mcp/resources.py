"""One process resource graph; future sessions share clients, caches and device locks."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

import anyio
import httpx2 as httpx
from pydantic import JsonValue

from wled_mcp.client import ClientFailure, Deadline, Endpoint, WLEDClient
from wled_mcp.config import Device, StartupConfig
from wled_mcp.models import DomainError, Outcome


@dataclass(frozen=True)
class BackupHandle:
    directory: Path
    retain_per_device: int


@dataclass
class OperationContext:
    device: Device
    client: WLEDClient
    deadline: Deadline
    dispatched: bool = False

    async def read(self, endpoint: Endpoint) -> JsonValue:
        return await self.client.read(self.device, endpoint, self.deadline)


class Resources:
    def __init__(
        self, config: StartupConfig, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self.config = config
        self.inventory = config.devices
        self._devices = {device.id: device for device in self.inventory}
        self.client = WLEDClient(config.http, transport)
        self.locks = {device.id: anyio.Lock() for device in self.inventory}
        self.metadata_cache: dict[str, JsonValue] = {}
        self.backups = BackupHandle(config.data_dir / "backups", config.backups.retain_per_device)

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
                    yield OperationContext(device, self.client, deadline)
        except TimeoutError:
            raise ClientFailure("TIMEOUT", "Operation deadline expired.", retryable=True) from None

    async def write_verified(
        self,
        device_id: str,
        operation: str,
        prepare: Callable[[OperationContext], Awaitable[dict[str, JsonValue]]],
        matches: Callable[[JsonValue], bool],
    ) -> Outcome:
        """Internal foundation, not a public setter. Prepare validates a full future plan."""
        dispatched = False
        try:
            async with self.operation(device_id) as context:
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
