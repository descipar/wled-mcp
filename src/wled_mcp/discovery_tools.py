"""``wled_discover_devices``: the MCP face of the shared discovery engine (issue #200).

Contract: docs/contract/discovery.md (DISC-01, DISC-03 to DISC-06, DISC-11 to DISC-13) and
ISSUE-198-DEC-001, ISSUE-200-DEC-001. The tool runs only when a client calls it, reads the
configured ranges and the inventory per call, never writes (no file, no device) and never
scans a proposal: ``proposed_ranges`` is computed from inventory addresses by a pure function
and is never handed to the engine. A run that could not look says so in the coverage report;
it is never an error and never "nothing found".

The synchronous engine runs in a worker thread. A process-wide guard (the resource graph is
shared by stdio and Streamable HTTP) allows one run at a time and keeps a minimum gap between
probe-phase starts (``DISCOVERY_BUSY``). The engine runner and the clock are module
attributes looked up per call, so tests substitute them and no test opens a real socket.
"""

from __future__ import annotations

import ipaddress
import math
import threading
from collections.abc import Iterable, Sequence
from time import monotonic
from typing import Any, Literal, cast

import anyio.to_thread
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from wled_mcp import discovery_engine, setup
from wled_mcp.access import ToolClass
from wled_mcp.config import Device
from wled_mcp.discovery_caps import PRIVATE_NETWORKS  # RFC 1918, the shared hard-cap definition
from wled_mcp.discovery_engine import (
    CALL_DEADLINE,
    MAX_RANGES,
    DiscoveryRangeError,
    DiscoveryResult,
    KnownDevice,
)
from wled_mcp.models import DomainError, Outcome
from wled_mcp.resources import Resources
from wled_mcp.server import Operation

OPERATION = "wled_discover_devices"
PROBE_GAP_SECONDS = 5.0  # TP-4: minimum gap between probe-phase starts per process
MAX_TIMEOUT_SECONDS = 30
MAX_PROPOSED_CANDIDATES = 64


class DiscoverDevicesRequest(BaseModel):
    """No range, host, port, interface or cap field exists (TP-12)."""

    model_config = ConfigDict(extra="forbid", strict=True)
    methods: list[Literal["mdns", "unicast"]] | None = Field(
        default=None, min_length=1, max_length=2
    )
    timeout_seconds: float | None = Field(default=None, ge=1, le=MAX_TIMEOUT_SECONDS)
    max_candidates: int | None = Field(default=None, ge=1, le=MAX_PROPOSED_CANDIDATES)

    @field_validator("methods")
    @classmethod
    def unique_methods(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and len(set(value)) != len(value):
            raise ValueError("methods must be unique")
        return value


# -- engine seam (module attributes, replaced by tests) ------------------------------------


def run_engine(**kwargs: Any) -> DiscoveryResult:
    """The synchronous engine; looked up per call. Tests replace it (see tests/conftest.py)."""
    return discovery_engine.run_discovery(**kwargs)


clock = monotonic


# -- single flight and probe gap -------------------------------------------------------------


class DiscoveryGuard:
    """One run at a time per process and a minimum gap between probe-phase starts."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._running = False
        self._busy_until = 0.0
        self._last_probe_start: float | None = None

    def reset(self) -> None:
        with self._lock:
            self._running = False
            self._busy_until = 0.0
            self._last_probe_start = None

    def enter(self, probing: bool, deadline_seconds: float) -> int | None:
        """None when the run may start; otherwise the whole seconds to wait (at least 1)."""
        now = clock()
        with self._lock:
            if self._running:
                return _wait(self._busy_until - now)
            if probing and self._last_probe_start is not None:
                remaining = self._last_probe_start + PROBE_GAP_SECONDS - now
                if remaining > 0:
                    return _wait(remaining)
            self._running = True
            self._busy_until = now + deadline_seconds
            if probing:
                self._last_probe_start = now
            return None

    def leave(self) -> None:
        with self._lock:
            self._running = False


def _wait(seconds: float) -> int:
    return max(1, min(MAX_TIMEOUT_SECONDS, math.ceil(seconds)))


GUARD = DiscoveryGuard()


# -- pure helpers --------------------------------------------------------------------------


def known_devices(inventory: Iterable[Device]) -> list[KnownDevice]:
    """The inventory snapshot for the engine (MAC unknown until devices[].mac exists)."""
    known: list[KnownDevice] = []
    for device in inventory:
        _, host, port = setup.url_identity(device.base_url)
        known.append(KnownDevice(device.id, host.rstrip("."), None, port))
    return known


def propose_ranges(
    inventory: Iterable[Device], configured: Iterable[str] = ()
) -> tuple[list[dict[str, JsonValue]], int, list[dict[str, JsonValue]]]:
    """TP-7: /24 networks of RFC 1918 IPv4 literals of the inventory (pure, no I/O).

    Returns ``(proposals, omitted, unproposed)``. Duplicates are merged, the list is sorted
    ascending and excludes networks that overlap a configured range; at most ``MAX_RANGES``
    are returned and ``omitted`` counts the rest. Hosts that are not IPv4 literals or not
    private are counted per reason in ``unproposed`` and never resolved.
    """
    existing: list[ipaddress.IPv4Network] = []
    for text in configured:
        try:
            existing.append(ipaddress.IPv4Network(text, strict=False))
        except ValueError:
            continue  # the engine reports an invalid stored range; nothing to exclude
    sources: dict[ipaddress.IPv4Network, list[str]] = {}
    unproposed = {"host_not_ipv4_literal": 0, "not_private": 0}
    for device in inventory:
        _, host, _ = setup.url_identity(device.base_url)
        try:
            address = ipaddress.IPv4Address(host.rstrip("."))
        except ValueError:
            unproposed["host_not_ipv4_literal"] += 1
            continue
        if not any(address in network for network in PRIVATE_NETWORKS):
            unproposed["not_private"] += 1
            continue
        network = ipaddress.IPv4Network((address, 24), strict=False)
        if any(network.overlaps(other) for other in existing):
            continue
        sources.setdefault(network, []).append(device.id)
    ordered = sorted(sources)
    proposals: list[dict[str, JsonValue]] = [
        {"cidr": str(network), "derived_from_device_ids": cast(JsonValue, sources[network])}
        for network in ordered[:MAX_RANGES]
    ]
    unlisted: list[dict[str, JsonValue]] = [
        {"reason": reason, "count": count} for reason, count in unproposed.items() if count
    ]
    return proposals, max(0, len(ordered) - MAX_RANGES), unlisted


# -- the operation -------------------------------------------------------------------------


def _failure(code: Literal["DISCOVERY_BUSY", "CONFIG_ERROR"], **fields: Any) -> Outcome:
    if code == "DISCOVERY_BUSY":
        wait = fields["retry_after_seconds"]
        message = "Another discovery run is active or the pause between probe runs has not passed."
        reconciliation = f"Nothing was probed. Retry after {wait} seconds."
        data: dict[str, JsonValue] = {"retry_after_seconds": wait}
        retryable = True
    else:
        message = "The stored discovery ranges are invalid; nothing was probed."
        reconciliation = "Correct the discovery ranges in the configuration file; restart."
        data = {}
        retryable = False
    return Outcome(
        ok=False,
        operation=OPERATION,
        device_id=None,
        application="not_attempted",
        verification="not_requested",
        data=data,
        error=DomainError(
            code=code, message=message, read_retryable=retryable, reconciliation=reconciliation
        ),
    )


def build_discovery_operation(resources: Resources) -> Operation:
    async def discover(arguments: dict[str, Any]) -> Outcome:
        methods: Sequence[str] = arguments["methods"] or ("mdns", "unicast")
        # Per call, never cached (ISSUE-200-DEC-001).
        ranges = tuple(resources.discovery_ranges)
        inventory = resources.inventory
        probing = "unicast" in methods and bool(ranges)
        timeout = arguments["timeout_seconds"]
        deadline = float(MAX_TIMEOUT_SECONDS if timeout is None else timeout)
        deadline = min(deadline, float(CALL_DEADLINE))
        wait = GUARD.enter(probing, deadline)
        if wait is not None:
            return _failure("DISCOVERY_BUSY", retry_after_seconds=wait)
        try:
            result = await anyio.to_thread.run_sync(
                lambda: run_engine(
                    methods=tuple(methods),
                    ranges=ranges,
                    known=known_devices(inventory),
                    timeout=timeout,
                    max_candidates=arguments["max_candidates"],
                )
            )
        except DiscoveryRangeError:
            return _failure("CONFIG_ERROR")
        finally:
            GUARD.leave()
        proposals, omitted, unproposed = propose_ranges(inventory, ranges)
        coverage: dict[str, JsonValue] = dict(cast(dict[str, JsonValue], result.coverage))
        coverage["proposed_ranges_omitted"] = omitted
        coverage["unproposed_devices"] = cast(JsonValue, unproposed)
        data: dict[str, JsonValue] = {
            "conclusion": result.conclusion,  # first key: what a text-only client reads first
            "candidates": cast(JsonValue, [c.as_dict() for c in result.candidates]),
            "coverage": coverage,
            "proposed_ranges": cast(JsonValue, proposals),
        }
        return Outcome(
            ok=True,
            operation=OPERATION,
            device_id=None,
            application="not_attempted",
            verification="not_requested",
            data=data,
            warnings=list(result.warnings),
        )

    return Operation(
        name=OPERATION,
        tool_class=ToolClass.READ,
        description=(
            "Search the local network for WLED controllers: mDNS plus a bounded read of the "
            "stored discovery ranges, never over ranges that were not stored. Returns "
            "candidates (new, known or address_changed), a coverage report that says what "
            "was and was not looked at, and proposed_ranges derived from inventory addresses "
            "(never probed). Writes nothing; storing ranges or adding a controller is a "
            "separate configuration-write call. Never report 'nothing found' unless "
            "conclusion is none_found_complete."
        ),
        request_model=DiscoverDevicesRequest,
        execute=discover,
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=True,
        ),
    )
