"""Shared discovery engine (issue #199; DISC-01 to DISC-05, DISC-12, DISC-13).

Contract: docs/contract/discovery.md (hard caps, known controllers, coverage report) and
DEC-035. One synchronous, standard-library engine finds WLED controllers by

* several mDNS rounds (``_wled._tcp`` plus the ``_http._tcp`` fallback), where every
  answer is verified through ``GET /json/info``, and
* a bounded unicast ``GET /json/info`` probe of caller-supplied RFC 1918 ranges,

merges both by MAC, marks each candidate ``new``, ``known`` or ``address_changed``
against a caller-supplied inventory snapshot (never modified) and returns a coverage
report that says so when it could not look.

The engine is a library: it reads no configuration, registers nothing, writes nothing to
the inventory or to a device, and sends nothing to an address that was not passed in as a
range, announced by an mDNS answer (and then only if it is an RFC 1918 address) or listed
in the known-device snapshot. Callers wrap it (the CLI directly, the MCP tool through a
worker thread). Process-level rules (single flight, the gap between probe phases) belong
to the caller. Diagnostics go nowhere: the engine prints nothing.
"""

import http.client
import ipaddress
import json
import math
import re
import socket
import threading
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from time import monotonic
from typing import Any, Literal, Protocol

from wled_mcp import discovery
from wled_mcp.client import validate_json
from wled_mcp.discovery import (
    MDNS_GROUP,
    MDNS_PORT,
    SERVICES,
    TYPE_PTR,
    Collector,
    DatagramSocket,
    build_query,
    follow_up_query,
    name_key,
    open_multicast_socket,
    safe_text,
    suggest_id,
    suggest_name,
)

# -- hard caps (TP-4); no parameter, configuration key or environment variable raises them

MAX_RANGES = 4
MIN_PREFIX = 24
MAX_PREFIX = 30
PROBE_PORT = 80
HOST_TIMEOUT = 1.5
MAX_BODY_BYTES = 64 * 1024
MAX_IN_FLIGHT = 32
PROBE_DEADLINE = 20.0
CALL_DEADLINE = 30.0
MDNS_ROUNDS = 3
MDNS_ROUND_GAP = 1.0
MDNS_WINDOW = 6.0
MAX_CANDIDATES = 64
MAX_KNOWN_READS = 16
MAX_ALTERNATE_ADDRESSES = 4
USER_AGENT = "wled-mcp-discovery"

# RFC 1918, built from integers so that no private address literal sits in the source.
_PRIVATE = (
    ipaddress.IPv4Network((10 << 24, 8)),
    ipaddress.IPv4Network(((172 << 24) | (16 << 16), 12)),
    ipaddress.IPv4Network(((192 << 24) | (168 << 16), 16)),
)

CAPS: dict[str, Any] = {
    "ranges": MAX_RANGES,
    "min_prefix": MIN_PREFIX,
    "max_prefix": MAX_PREFIX,
    "address_space": [str(network) for network in _PRIVATE],
    "probe_port": PROBE_PORT,
    "host_timeout_seconds": HOST_TIMEOUT,
    "response_bytes": MAX_BODY_BYTES,
    "in_flight": MAX_IN_FLIGHT,
    "probe_deadline_seconds": PROBE_DEADLINE,
    "call_deadline_seconds": CALL_DEADLINE,
    "mdns_rounds": MDNS_ROUNDS,
    "mdns_window_seconds": MDNS_WINDOW,
    "candidates": MAX_CANDIDATES,
    "known_device_reads": MAX_KNOWN_READS,
}

LIMITS = (
    "Multicast stays in the local network segment and does not cross VLANs or routed "
    "subnets; a container on a bridge network usually cannot use it.",
    "A controller with an empty mDNS name does not announce itself.",
    "A probe reaches only the configured ranges.",
    "Hosts that did not answer in time are unknown, not absent.",
)
LIMIT_NOT_EXHAUSTIVE = (
    "This run was not exhaustive: a method was skipped, partial or failed, or a deadline "
    "or cap left hosts unprobed."
)

_MAC = re.compile(r"[0-9a-f]{12}")
_VERSION = re.compile(r"[ -~]{1,32}")

Method = Literal["mdns", "unicast"]
METHODS: tuple[Method, ...] = ("mdns", "unicast")


class DiscoveryRangeError(ValueError):
    """A range violates a hard cap; nothing was probed. The value is never echoed."""

    def __init__(self, reason: str, index: int | None = None) -> None:
        super().__init__(f"discovery range rejected: {reason}")
        self.reason = reason
        self.index = index


# -- range validation (defence in depth at probe time)


def _address_allowed(address: ipaddress.IPv4Address) -> bool:
    return any(address in network for network in _PRIVATE)


def validate_ranges(ranges: Iterable[str | ipaddress.IPv4Network]) -> list[ipaddress.IPv4Network]:
    """Parsed networks, or ``DiscoveryRangeError`` before anything is probed."""
    items = list(ranges)
    if len(items) > MAX_RANGES:
        raise DiscoveryRangeError("too_many_ranges")
    parsed: list[ipaddress.IPv4Network] = []
    for index, item in enumerate(items):
        if isinstance(item, ipaddress.IPv4Network):
            network = item
        else:
            text = item if isinstance(item, str) else ""
            if not text or text != text.strip() or "/" not in text:
                raise DiscoveryRangeError("not_ipv4_cidr", index)
            try:
                network = ipaddress.IPv4Network(text, strict=True)
            except ipaddress.NetmaskValueError:
                raise DiscoveryRangeError("not_ipv4_cidr", index) from None
            except ValueError:
                try:
                    ipaddress.IPv4Network(text, strict=False)
                except ValueError:
                    raise DiscoveryRangeError("not_ipv4_cidr", index) from None
                raise DiscoveryRangeError("not_network_address", index) from None
        if network.network_address.is_loopback:
            raise DiscoveryRangeError("loopback", index)
        if network.network_address.is_link_local:
            raise DiscoveryRangeError("link_local", index)
        if not any(network.subnet_of(private) for private in _PRIVATE):
            raise DiscoveryRangeError("not_private", index)
        if network.prefixlen < MIN_PREFIX:
            raise DiscoveryRangeError("too_broad", index)
        if network.prefixlen > MAX_PREFIX:
            raise DiscoveryRangeError("prefix_too_long", index)
        for earlier in parsed:
            if earlier == network:
                raise DiscoveryRangeError("duplicate", index)
            if earlier.overlaps(network):
                raise DiscoveryRangeError("overlap", index)
        parsed.append(network)
    return parsed


# -- the HTTP probe


@dataclass(frozen=True)
class InfoResult:
    """Outcome of one ``GET /json/info``.

    ``wled``: a JSON object that passed the identity check; ``other``: something
    answered but it is not a WLED ``/json/info`` (wrong content, redirect, oversize,
    malformed); ``refused``; ``timeout`` (no usable answer in time); ``error``: the
    transport raised unexpectedly.
    """

    kind: Literal["wled", "other", "refused", "timeout", "error"]
    mac: str | None = None
    version: str | None = None
    product: str | None = None
    name: str | None = None


class Transport(Protocol):
    def get_info(self, address: str, port: int, timeout: float) -> InfoResult: ...


def identify(document: object) -> InfoResult | None:
    """WLED identity check on a parsed ``/json/info`` (docs/SOURCES.md): ``brand`` is
    ``"WLED"``, ``ver`` is a printable string and ``mac`` is 12 hex digits. Never by port."""
    if not isinstance(document, dict) or document.get("brand") != "WLED":
        return None
    version, mac = document.get("ver"), document.get("mac")
    if not isinstance(version, str) or not _VERSION.fullmatch(version):
        return None
    if not isinstance(mac, str):
        return None
    mac = mac.lower().replace(":", "")
    if not _MAC.fullmatch(mac):
        return None
    product, name = document.get("product"), document.get("name")
    return InfoResult(
        "wled",
        mac,
        version,
        safe_text(product, 63) if isinstance(product, str) else None,
        safe_text(name, 63) if isinstance(name, str) else None,
    )


class HttpTransport:
    """GET ``/json/info`` only: no redirects, no proxy, no connection reuse, a fixed
    ``User-Agent``, a total time bound and at most ``MAX_BODY_BYTES`` read."""

    def __init__(
        self,
        connection_factory: Callable[..., Any] = http.client.HTTPConnection,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._factory = connection_factory
        self._clock = clock

    def get_info(self, address: str, port: int, timeout: float) -> InfoResult:
        deadline = self._clock() + timeout
        connection: Any = None
        aborted = threading.Event()

        def abort() -> None:
            # A total per-request bound: socket timeouts apply per operation, so a
            # server that drips bytes could otherwise hold the request open.
            aborted.set()
            sock = getattr(connection, "sock", None)
            try:
                if sock is not None:
                    sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                if connection is not None:
                    connection.close()
            except OSError:
                pass

        timer = threading.Timer(timeout, abort)
        timer.daemon = True
        try:
            connection = self._factory(address, port, timeout=timeout)
            timer.start()
            connection.request(
                "GET",
                "/json/info",
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json",
                    "Connection": "close",
                },
            )
            response = connection.getresponse()
            if response.status != 200:  # redirects are not followed
                return InfoResult("other")
            body = bytearray()
            while len(body) <= MAX_BODY_BYTES:
                if self._clock() > deadline or aborted.is_set():
                    return InfoResult("timeout")
                chunk = response.read(min(4096, MAX_BODY_BYTES + 1 - len(body)))
                if not chunk:
                    break
                body += chunk
            if aborted.is_set():
                return InfoResult("timeout")
            if len(body) > MAX_BODY_BYTES:
                return InfoResult("other")
            document = json.loads(bytes(body))
            validate_json(document)
        except ConnectionRefusedError:
            return InfoResult("refused")
        except (TimeoutError, OSError):
            return InfoResult("timeout")
        except (http.client.HTTPException, ValueError, RecursionError):
            return InfoResult("timeout" if aborted.is_set() else "other")
        finally:
            timer.cancel()
            if connection is not None:
                connection.close()
        return identify(document) or InfoResult("other")


def _safe_get(transport: Transport, address: str, port: int, timeout: float) -> InfoResult:
    try:
        return transport.get_info(address, port, timeout)
    except Exception:  # an unexpected transport failure must not abort the run
        return InfoResult("error")


def probe_many(
    targets: Sequence[tuple[str, int]],
    transport: Transport,
    timeout: float,
    deadline: float,
    clock: Callable[[], float],
) -> list[InfoResult | None]:
    """Probe ``targets`` with at most ``MAX_IN_FLIGHT`` requests in flight.

    Stops scheduling at ``deadline``; targets never started are ``None`` (``not_probed``).
    """
    results: list[InfoResult | None] = [None] * len(targets)
    if not targets:
        return results
    pending: dict[Future[InfoResult], int] = {}

    def settle(done: set[Future[InfoResult]]) -> None:
        for future in done:
            results[pending.pop(future)] = future.result()

    def grace() -> float:
        # Real time a request may still run past the deadline: its own per-request bound.
        return max(0.0, deadline - clock()) + timeout

    pool = ThreadPoolExecutor(max_workers=min(MAX_IN_FLIGHT, len(targets)))
    try:
        for index, (address, port) in enumerate(targets):
            while len(pending) >= MAX_IN_FLIGHT:
                done, _ = wait(pending, timeout=grace(), return_when=FIRST_COMPLETED)
                if not done:
                    break
                settle(done)
            if len(pending) >= MAX_IN_FLIGHT or clock() >= deadline:
                break
            pending[pool.submit(_safe_get, transport, address, port, timeout)] = index
        done, _ = wait(pending, timeout=grace())
        settle(done)
        for future, index in pending.items():  # stragglers: no usable answer in time
            future.cancel()
            results[index] = InfoResult("timeout")
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return results


# -- inputs and outputs


@dataclass(frozen=True)
class KnownDevice:
    """One configured controller of the inventory snapshot (read-only)."""

    id: str
    host: str
    mac: str | None = None
    port: int = 80


@dataclass
class FoundDevice:
    address: str
    base_url: str
    suggested_id: str
    suggested_name: str
    mac: str
    firmware_version: str
    product: str | None
    found_by: list[str]
    status: Literal["new", "known", "address_changed"] = "new"
    known_device_id: str | None = None
    configured_address: str | None = None
    alternate_addresses: list[str] = field(default_factory=list)
    instance: str | None = None  # mDNS instance name; not part of ``as_dict``

    def as_dict(self) -> dict[str, Any]:
        document: dict[str, Any] = {
            "address": self.address,
            "base_url": self.base_url,
            "suggested_id": self.suggested_id,
            "suggested_name": self.suggested_name,
            "mac": self.mac,
            "firmware_version": self.firmware_version,
            "product": self.product,
            "found_by": list(self.found_by),
            "status": self.status,
        }
        if self.known_device_id is not None:
            document["known_device_id"] = self.known_device_id
        if self.configured_address is not None:
            document["configured_address"] = self.configured_address
        if self.alternate_addresses:
            document["alternate_addresses"] = list(self.alternate_addresses)
        return document


@dataclass
class DiscoveryResult:
    candidates: list[FoundDevice]
    coverage: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    malformed_responses: int = 0
    dropped_datagrams: int = 0
    queries_sent: int = 0  # mDNS datagrams sent (rounds plus follow-ups)
    follow_up_sent: bool = False
    truncated: bool = False  # more mDNS instances answered than were examined

    @property
    def conclusion(self) -> str:
        return str(self.coverage["conclusion"])

    def as_dict(self) -> dict[str, Any]:
        return {
            "conclusion": self.conclusion,
            "candidates": [candidate.as_dict() for candidate in self.candidates],
            "coverage": self.coverage,
            "warnings": list(self.warnings),
        }


@dataclass
class _Sighting:
    """One verified answer: a MAC at an address, seen by one method."""

    mac: str
    address: str
    info: InfoResult
    method: Method
    instance: str | None = None


@dataclass
class _MethodState:
    requested: bool
    status: str = "skipped"
    reason: str | None = None

    def report(self, method: Method) -> dict[str, Any]:
        document: dict[str, Any] = {
            "method": method,
            "requested": self.requested,
            "status": self.status,
        }
        if self.reason is not None:
            document["reason"] = self.reason
        return document


def _clamp(value: float | None, cap: float) -> float:
    if value is None or isinstance(value, bool) or not value > 0 or not math.isfinite(value):
        return cap
    return min(float(value), cap)


# -- mDNS


def _mdns_phase(
    opener: Callable[[], DatagramSocket],
    clock: Callable[[], float],
    collector: Collector,
    window: float,
) -> tuple[int, int] | None:
    """Up to ``MDNS_ROUNDS`` rounds ``MDNS_ROUND_GAP`` apart inside ``window``.

    Returns the rounds and follow-up datagrams sent, or ``None`` when the socket could not
    be opened or the first query could not be sent.
    """
    destination = (MDNS_GROUP, MDNS_PORT)
    try:
        sock = opener()
    except OSError:
        return None
    sent = follow_ups = 0
    try:
        start = clock()
        query = build_query([(service, TYPE_PTR) for service in SERVICES])
        for number in range(MDNS_ROUNDS):
            at = start + number * MDNS_ROUND_GAP
            if number and at >= start + window:
                break
            if number:  # wait for the round time, collecting answers
                discovery.listen(sock, at, clock, collector)
            try:
                sock.sendto(query, destination)
            except OSError:
                if number == 0:
                    return None
                break
            sent += 1
            follow_up = follow_up_query(collector.missing_questions()) if number else None
            if follow_up is not None:
                try:
                    sock.sendto(follow_up, destination)
                    follow_ups += 1
                except OSError:
                    pass  # best effort; the next round asks again
        discovery.listen(sock, start + window, clock, collector)
    finally:
        sock.close()
    return sent, follow_ups


def _mdns_targets(
    collector: Collector,
) -> tuple[list[tuple[str, str, int]], int, int]:
    """(instance, address, port) probe targets, responders and unusable answers."""
    targets: list[tuple[str, str, int]] = []
    rejected = 0
    for key, name in collector.instances.items():
        service = collector.services.get(key)
        port = service[0] if service is not None else None
        addresses = (
            [str(a) for a in collector.hosts.get(name_key(service[1]), [])]
            if service is not None
            else []
        )
        usable = [a for a in addresses if _address_allowed(ipaddress.IPv4Address(a))]
        if port != PROBE_PORT or not usable:
            rejected += 1
            continue
        targets.extend((safe_text(name[0]), address, PROBE_PORT) for address in usable)
    return targets, len(collector.instances), rejected


# -- the run


def run_discovery(
    *,
    methods: Iterable[str] = METHODS,
    ranges: Iterable[str | ipaddress.IPv4Network] = (),
    known: Iterable[KnownDevice] = (),
    timeout: float | None = None,
    max_candidates: int | None = None,
    transport: Transport | None = None,
    opener: Callable[[], DatagramSocket] = open_multicast_socket,
    clock: Callable[[], float] = monotonic,
) -> DiscoveryResult:
    """Run discovery once and return candidates plus the coverage report.

    ``ranges`` are probed as given after re-validation against the hard caps
    (``DiscoveryRangeError`` before anything is sent). ``known`` is a snapshot that is
    only read. ``timeout`` and ``max_candidates`` can only lower the caps.
    """
    requested = {m for m in methods if m in METHODS}
    networks = validate_ranges(ranges) if "unicast" in requested else []
    known_list = list(known)
    http_transport: Transport = transport or HttpTransport(clock=clock)
    call_timeout = _clamp(timeout, CALL_DEADLINE)
    host_timeout = min(HOST_TIMEOUT, call_timeout)
    limit = (
        MAX_CANDIDATES
        if not isinstance(max_candidates, int) or isinstance(max_candidates, bool)
        else max(1, min(max_candidates, MAX_CANDIDATES))
    )
    started = clock()
    call_deadline = started + call_timeout
    states = {m: _MethodState(m in requested) for m in METHODS}
    for state in states.values():
        if not state.requested:
            state.reason = "not_requested"
    sightings: list[_Sighting] = []
    warnings: list[str] = []
    internal_error = {"mdns": False, "unicast": False}
    collector = Collector()
    mdns_report: dict[str, Any] | None = None
    follow_ups_sent = 0
    unicast_report: dict[str, Any] | None = None
    not_probed_total = 0

    if "mdns" in requested:
        state = states["mdns"]
        window = min(MDNS_WINDOW, call_timeout)
        phase = _mdns_phase(opener, clock, collector, window)
        if phase is None:
            state.status, state.reason = "failed", "multicast_unavailable"
        else:
            rounds, follow_ups_sent = phase
            targets, responders, rejected = _mdns_targets(collector)
            results = probe_many(
                [(address, port) for _, address, port in targets],
                http_transport,
                host_timeout,
                call_deadline,
                clock,
            )
            verified_instances: set[str] = set()
            unprobed = 0
            for (instance, address, _), result in zip(targets, results, strict=True):
                if result is None:
                    unprobed += 1
                elif result.kind == "error":
                    internal_error["mdns"] = True
                elif result.kind == "wled" and result.mac is not None:
                    verified_instances.add(instance)
                    sightings.append(_Sighting(result.mac, address, result, "mdns", instance))
            attempted = len({t[0] for t in targets})
            rejected += max(0, attempted - len(verified_instances))
            state.status = "completed"
            if responders == 0:
                state.reason = "no_answers"
            if unprobed:
                state.status, state.reason = "partial", "deadline_reached"
                not_probed_total += unprobed
            if collector.truncated:
                state.status, state.reason = "partial", "cap_reached"
                warnings.append(
                    "More mDNS instances answered than were examined; the rest were ignored."
                )
            if internal_error["mdns"]:
                state.status, state.reason = "partial", "internal_error"
            mdns_report = {
                "rounds_sent": rounds,
                "window_seconds": window,
                "services_queried": [".".join(service) for service in SERVICES],
                "responders": responders,
                "answers_verified": len(verified_instances),
                "answers_rejected": rejected,
            }

    if "unicast" in requested:
        state = states["unicast"]
        if not networks:
            state.reason = "no_ranges_configured"
        else:
            phase_deadline = min(clock() + PROBE_DEADLINE, call_deadline)
            targets_u: list[tuple[str, int]] = []
            owners: list[int] = []
            counters: list[dict[str, Any]] = []
            for index, network in enumerate(networks):
                hosts = [str(host) for host in network.hosts()]
                counters.append(
                    {
                        "cidr": str(network),
                        "hosts_total": len(hosts),
                        "hosts_probed": 0,
                        "answered_wled": 0,
                        "answered_other": 0,
                        "refused": 0,
                        "timed_out": 0,
                        "not_probed": 0,
                    }
                )
                targets_u.extend((host, PROBE_PORT) for host in hosts)
                owners.extend([index] * len(hosts))
            results_u = probe_many(targets_u, http_transport, host_timeout, phase_deadline, clock)
            for (address, _), owner, result in zip(targets_u, owners, results_u, strict=True):
                row = counters[owner]
                if result is None:
                    row["not_probed"] += 1
                    not_probed_total += 1
                    continue
                row["hosts_probed"] += 1
                if result.kind == "wled" and result.mac is not None:
                    row["answered_wled"] += 1
                    sightings.append(_Sighting(result.mac, address, result, "unicast"))
                elif result.kind == "other":
                    row["answered_other"] += 1
                elif result.kind == "refused":
                    row["refused"] += 1
                elif result.kind == "timeout":
                    row["timed_out"] += 1
                else:
                    internal_error["unicast"] = True
            deadline_hit = any(row["not_probed"] for row in counters)
            state.status = "completed"
            if deadline_hit:
                state.status, state.reason = "partial", "deadline_reached"
            if internal_error["unicast"]:
                state.status, state.reason = "partial", "internal_error"
            unicast_report = {"ranges": counters, "deadline_reached": deadline_hit}

    candidates = _merge(sightings)
    # Known-controller marking: reads only configured hosts, never rewrites anything.
    checked, unmatched = _mark_known(
        candidates, known_list, http_transport, host_timeout, call_deadline, clock
    )
    taken = {device.id for device in known_list}
    labels: dict[str, str] = {}
    for sighting in sightings:  # the first label seen per MAC; a generic name is no label
        label = sighting.instance or sighting.info.name
        if label and label != "WLED":
            labels.setdefault(sighting.mac, label)
    for candidate in candidates:
        label = labels.get(candidate.mac) or f"wled-{candidate.mac[-6:]}"
        candidate.suggested_id = suggest_id(label, taken)
        candidate.suggested_name = suggest_name(label)
    if len(candidates) > limit:
        candidates = candidates[:limit]
        warnings.append("The candidate cap was reached; more controllers answered than are listed.")
        for state in states.values():
            if state.status == "completed":
                state.status, state.reason = "partial", "cap_reached"

    ran = [s for s in states.values() if s.requested and s.status in ("completed", "partial")]
    complete = (
        len(requested) == len(METHODS)
        and all(s.status == "completed" for s in states.values())
        and not_probed_total == 0
    )
    if not ran:
        conclusion = "not_looked"
    elif candidates:
        conclusion = "candidates_found"
    else:
        conclusion = "none_found_complete" if complete else "none_found_incomplete"

    coverage: dict[str, Any] = {
        "schema": 1,
        "conclusion": conclusion,
        "complete": complete and bool(ran),
        "methods": [states[m].report(m) for m in METHODS],
    }
    if mdns_report is not None:
        coverage["mdns"] = mdns_report
    if unicast_report is not None:
        coverage["unicast"] = unicast_report
    coverage.update(
        {
            "known_devices_checked": checked,
            "known_devices_unmatched": unmatched,
            "caps": dict(CAPS),
            "limits": [*LIMITS, *([] if coverage["complete"] else [LIMIT_NOT_EXHAUSTIVE])],
        }
    )
    queries_sent = (mdns_report["rounds_sent"] + follow_ups_sent) if mdns_report else 0
    return DiscoveryResult(
        candidates,
        coverage,
        warnings,
        collector.malformed,
        collector.dropped_sources,
        queries_sent,
        follow_ups_sent > 0,
        collector.truncated,
    )


# -- merging and known marking


def _merge(sightings: list[_Sighting]) -> list[FoundDevice]:
    """Merge by MAC; the lowest address is primary, the rest are alternates."""
    grouped: dict[str, list[_Sighting]] = {}
    for sighting in sightings:
        grouped.setdefault(sighting.mac, []).append(sighting)
    devices: list[FoundDevice] = []
    for mac, group in grouped.items():
        addresses = sorted({s.address for s in group}, key=lambda a: int(ipaddress.IPv4Address(a)))
        info = group[0].info
        devices.append(
            FoundDevice(
                address=addresses[0],
                base_url=f"http://{addresses[0]}",
                suggested_id="",
                suggested_name="",
                mac=mac,
                firmware_version=info.version or "",
                product=info.product,
                found_by=[m for m in METHODS if any(s.method == m for s in group)],
                alternate_addresses=addresses[1 : 1 + MAX_ALTERNATE_ADDRESSES],
                instance=next((s.instance for s in group if s.instance), None),
            )
        )
    return sorted(devices, key=lambda d: int(ipaddress.IPv4Address(d.address)))


def _mark_known(
    candidates: list[FoundDevice],
    known: list[KnownDevice],
    transport: Transport,
    timeout: float,
    deadline: float,
    clock: Callable[[], float],
) -> tuple[int, int]:
    """Set status and known fields; returns ``(known_devices_checked, _unmatched)``."""
    by_mac = {device.mac: device for device in known if device.mac}
    by_host = {device.host: device for device in known}
    pending: list[FoundDevice] = []
    for candidate in candidates:
        addresses = [candidate.address, *candidate.alternate_addresses]
        entry = by_mac.get(candidate.mac)
        if entry is None:
            entry = next((by_host[a] for a in addresses if a in by_host), None)
        if entry is None:
            pending.append(candidate)
            continue
        _apply(candidate, entry, addresses)
    checked = unmatched = 0
    matched = {c.known_device_id for c in candidates if c.known_device_id}
    unread = [d for d in known if not d.mac and d.id not in matched]
    if pending and unread:
        reads = unread[:MAX_KNOWN_READS]
        results = probe_many([(d.host, d.port) for d in reads], transport, timeout, deadline, clock)
        checked = sum(1 for result in results if result is not None)
        for entry, result in zip(reads, results, strict=True):
            if result is None or result.kind != "wled" or result.mac is None:
                unmatched += 1
                continue
            for candidate in pending:
                if candidate.mac == result.mac and candidate.status == "new":
                    _apply(candidate, entry, [candidate.address, *candidate.alternate_addresses])
    return checked, unmatched


def _apply(candidate: FoundDevice, entry: KnownDevice, addresses: list[str]) -> None:
    candidate.known_device_id = entry.id
    if entry.host in addresses:
        candidate.status = "known"
    else:
        candidate.status = "address_changed"
        candidate.configured_address = entry.host
