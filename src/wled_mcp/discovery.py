"""``wled-mcp discover`` and the mDNS packet layer of the shared discovery engine.

Contract: docs/contract/cli.md and docs/contract/discovery.md; decisions DEC-035 (which
supersedes ISSUE-16-DEC-001 in part) and ISSUE-16-DEC-002 (standard library only). Runs
only on explicit invocation: never at startup, in ``doctor`` or as a fallback.

This module keeps the bounded mDNS parser (datagram size, record count, name length,
compression pointers that must point backwards; a malformed datagram is dropped, never
fatal), the text sanitizer and the command. The search itself (mDNS rounds, verification
through ``GET /json/info``, the unicast probe, merging, coverage) is
``wled_mcp.discovery_engine``; the command only feeds it and formats the result. Text
taken from the network is sanitized before it is printed.
"""

from __future__ import annotations

import argparse
import ipaddress
import re
import socket
import struct
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING, Any, Protocol

from wled_mcp import setup
from wled_mcp.config import ConfigurationError, validate_document

if TYPE_CHECKING:  # the engine imports this module's parser; the command imports it lazily
    from wled_mcp.discovery_engine import DiscoveryResult, FoundDevice, KnownDevice

MDNS_GROUP = "224.0.0.251"
MDNS_PORT = 5353
SERVICES = (("_wled", "_tcp", "local"), ("_http", "_tcp", "local"))

DEFAULT_TIMEOUT = 3.0
MIN_TIMEOUT = 0.5
MAX_TIMEOUT = 10.0
MAX_CANDIDATES = 64

# Bounds for untrusted answers.
RECEIVE_BUFFER = 9000  # the mDNS maximum datagram size (RFC 6762 section 17)
MAX_DATAGRAMS = 512
MAX_RECEIVE_ERRORS = 16
MAX_RECORDS = 128  # per datagram, all sections together
MAX_NAME_BYTES = 255
MAX_POINTER_JUMPS = 16
MAX_TXT_STRINGS = 64
MAX_HOSTS = 256
MAX_ADDRESSES_PER_HOST = 4
MAX_FOLLOW_UP_BYTES = 1400  # one unfragmented datagram
MAX_TEXT = 63

TYPE_A, TYPE_PTR, TYPE_TXT, TYPE_SRV = 1, 12, 16, 33
CLASS_IN = 1

_MAC = re.compile(r"[0-9a-f]{12}")
_LDH_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?")
_UNSAFE_NAME = re.compile(r"[^A-Za-z0-9 ._-]+")

NETWORK_HINTS = (
    "Discovery uses IPv4 multicast (UDP 5353) and only reaches the local network "
    "segment: it does not cross VLANs or routed subnets, a container on a bridge "
    "network usually cannot send or receive it, and firewalls may block multicast. "
    "Controllers with an empty mDNS name do not announce themselves. You can always "
    "add a controller by address: `wled-mcp config add-device --base-url "
    "http://<address>` (docs/DEPLOYMENT.md)."
)


class MalformedPacket(Exception):
    """A datagram that is not a well-formed DNS response within the bounds."""


Name = tuple[str, ...]


def name_key(name: Name) -> Name:
    """DNS names compare case-insensitively (ASCII only)."""
    return tuple(label.lower() for label in name)


# -- query building ----------------------------------------------------------------


def encode_name(name: Name) -> bytes:
    out = bytearray()
    for label in name:
        raw = label.encode("utf-8")
        if not 1 <= len(raw) <= 63:
            raise ValueError("invalid DNS label")
        out += bytes([len(raw)]) + raw
    out += b"\x00"
    if len(out) > MAX_NAME_BYTES:
        raise ValueError("DNS name too long")
    return bytes(out)


def build_query(questions: Iterable[tuple[Name, int]]) -> bytes:
    """A standard query, ID 0, with the unicast-response (QU) bit cleared."""
    body = bytearray()
    count = 0
    for name, qtype in questions:
        body += encode_name(name) + struct.pack("!HH", qtype, CLASS_IN)
        count += 1
    return struct.pack("!HHHHHH", 0, 0, count, 0, 0, 0) + bytes(body)


# -- bounded response parsing ------------------------------------------------------


def _read_name(packet: bytes, offset: int) -> tuple[Name, int]:
    """Decode a possibly compressed name; returns it and the offset after it.

    Every compression pointer must point strictly before the label that holds it, and
    at most ``MAX_POINTER_JUMPS`` are followed, so a loop cannot occur.
    """
    labels: list[str] = []
    total = 1
    jumps = 0
    end: int | None = None
    position = offset
    while True:
        if position >= len(packet):
            raise MalformedPacket("name runs past the datagram")
        length = packet[position]
        kind = length & 0xC0
        if kind == 0xC0:
            if position + 1 >= len(packet):
                raise MalformedPacket("truncated pointer")
            target = ((length & 0x3F) << 8) | packet[position + 1]
            if target >= position:
                raise MalformedPacket("forward or self pointer")
            jumps += 1
            if jumps > MAX_POINTER_JUMPS:
                raise MalformedPacket("too many pointers")
            if end is None:
                end = position + 2
            position = target
            continue
        if kind != 0:
            raise MalformedPacket("unsupported label type")
        if length == 0:
            return tuple(labels), (end if end is not None else position + 1)
        start = position + 1
        stop = start + length
        if stop > len(packet):
            raise MalformedPacket("label runs past the datagram")
        total += length + 1
        if total > MAX_NAME_BYTES:
            raise MalformedPacket("name too long")
        labels.append(packet[start:stop].decode("utf-8", errors="replace"))
        position = stop


@dataclass(frozen=True)
class Record:
    name: Name
    rtype: int
    data: Any


def parse_response(packet: bytes) -> list[Record]:
    """Records of an mDNS response, or ``MalformedPacket``; unknown types are skipped."""
    if len(packet) < 12 or len(packet) > RECEIVE_BUFFER:
        raise MalformedPacket("bad datagram size")
    _, flags, qdcount, ancount, nscount, arcount = struct.unpack_from("!HHHHHH", packet)
    if not flags & 0x8000 or (flags >> 11) & 0xF or flags & 0x000F:
        raise MalformedPacket("not a successful standard response")
    if qdcount + ancount + nscount + arcount > MAX_RECORDS:
        raise MalformedPacket("too many records")
    offset = 12
    for _ in range(qdcount):
        _, offset = _read_name(packet, offset)
        offset += 4
        if offset > len(packet):
            raise MalformedPacket("truncated question")
    records: list[Record] = []
    for _ in range(ancount + nscount + arcount):
        name, offset = _read_name(packet, offset)
        if offset + 10 > len(packet):
            raise MalformedPacket("truncated record header")
        rtype, rclass, _, rdlength = struct.unpack_from("!HHIH", packet, offset)
        offset += 10
        rdata_end = offset + rdlength
        if rdata_end > len(packet):
            raise MalformedPacket("record data runs past the datagram")
        if rclass & 0x7FFF == CLASS_IN:  # the top bit is the mDNS cache-flush flag
            data = _record_data(packet, rtype, offset, rdata_end)
            if data is not None:
                records.append(Record(name, rtype, data))
        offset = rdata_end
    return records


def _record_data(packet: bytes, rtype: int, start: int, end: int) -> Any:
    if rtype == TYPE_A:
        if end - start != 4:
            raise MalformedPacket("bad A record")
        return ipaddress.IPv4Address(packet[start:end])
    if rtype == TYPE_PTR:
        target, after = _read_name(packet, start)
        if after != end:
            raise MalformedPacket("bad PTR record")
        return target
    if rtype == TYPE_SRV:
        if end - start < 7:
            raise MalformedPacket("bad SRV record")
        _, _, port = struct.unpack_from("!HHH", packet, start)
        target, after = _read_name(packet, start + 6)
        if after != end:
            raise MalformedPacket("bad SRV record")
        return port, target
    if rtype == TYPE_TXT:
        return _txt(packet[start:end])
    return None


def _txt(data: bytes) -> dict[str, bytes]:
    entries: dict[str, bytes] = {}
    offset = 0
    strings = 0
    while offset < len(data):
        strings += 1
        if strings > MAX_TXT_STRINGS:
            raise MalformedPacket("too many TXT strings")
        length = data[offset]
        item = data[offset + 1 : offset + 1 + length]
        if len(item) != length:
            raise MalformedPacket("TXT string runs past the record")
        offset += 1 + length
        key, _, value = item.partition(b"=")
        text_key = key.decode("ascii", errors="replace").lower()
        if text_key and text_key not in entries:  # RFC 6763: the first one counts
            entries[text_key] = value
    return entries


# -- collecting answers --------------------------------------------------------------


def _is_instance(name: Name) -> bool:
    return len(name) == 4 and name_key(name[1:]) in SERVICES


@dataclass
class Collector:
    """Bounded record store across all received datagrams."""

    instances: dict[Name, Name] = field(default_factory=dict)  # key -> original name
    services: dict[Name, tuple[int, Name]] = field(default_factory=dict)
    texts: dict[Name, dict[str, bytes]] = field(default_factory=dict)
    hosts: dict[Name, list[ipaddress.IPv4Address]] = field(default_factory=dict)
    datagrams: int = 0
    malformed: int = 0
    truncated: bool = False
    dropped_sources: int = 0

    @property
    def received(self) -> int:
        return self.datagrams + self.dropped_sources

    def feed(self, packet: bytes) -> None:
        self.datagrams += 1
        try:
            records = parse_response(packet)
        except MalformedPacket:
            self.malformed += 1
            return
        # PTR records first, so that SRV/TXT in the same datagram find their instance.
        for record in sorted(records, key=lambda r: r.rtype != TYPE_PTR):
            self._add(record)

    def _add(self, record: Record) -> None:
        key = name_key(record.name)
        if record.rtype == TYPE_PTR:
            if key in SERVICES and _is_instance(record.data) and key == name_key(record.data[1:]):
                instance = name_key(record.data)
                if instance not in self.instances:
                    # The bound is per service, so many `_http._tcp` hosts of a network
                    # cannot crowd out `_wled._tcp` instances.
                    same = sum(1 for other in self.instances if other[1:] == key)
                    if same >= MAX_CANDIDATES:
                        self.truncated = True
                        return
                    self.instances[instance] = record.data
        elif record.rtype == TYPE_SRV:
            if _is_instance(record.name) and key in self.instances:
                self.services.setdefault(key, record.data)
        elif record.rtype == TYPE_TXT:
            if _is_instance(record.name) and key in self.instances:
                self.texts.setdefault(key, record.data)
        elif record.rtype == TYPE_A:
            address = record.data
            if not _usable_address(address):
                return
            known = self.hosts.get(key)
            if known is None:
                if len(self.hosts) >= MAX_HOSTS:
                    return
                known = self.hosts[key] = []
            if address not in known and len(known) < MAX_ADDRESSES_PER_HOST:
                known.append(address)

    def missing_questions(self) -> list[tuple[Name, int]]:
        """Questions for records the answers left out (for the one follow-up query)."""
        questions: list[tuple[Name, int]] = []
        for key, name in self.instances.items():
            service = self.services.get(key)
            if service is None:
                questions.append((name, TYPE_SRV))
            elif not self.hosts.get(name_key(service[1])) and service[1]:
                questions.append((service[1], TYPE_A))
            if key not in self.texts:
                questions.append((name, TYPE_TXT))
        return questions


_THIS_NETWORK = ipaddress.IPv4Network("0.0.0.0/8")
_RESERVED = ipaddress.IPv4Network("240.0.0.0/4")  # includes 255.255.255.255


def _usable_address(address: ipaddress.IPv4Address) -> bool:
    return not (
        address in _THIS_NETWORK
        or address in _RESERVED
        or address.is_multicast
        or address.is_loopback
    )


def follow_up_query(questions: list[tuple[Name, int]]) -> bytes | None:
    """One datagram with as many missing-record questions as fit, or ``None``."""
    chosen: list[tuple[Name, int]] = []
    for question in questions:
        try:
            candidate = build_query([*chosen, question])
        except ValueError:
            continue
        if len(candidate) > MAX_FOLLOW_UP_BYTES:
            break
        chosen.append(question)
    return build_query(chosen) if chosen else None


# -- candidates ------------------------------------------------------------------------


def safe_text(value: str, limit: int = MAX_TEXT * 4) -> str:
    """ASCII printable text only; every other character (control, format, separator,
    non-ASCII, the replacement character of invalid UTF-8) becomes ``?``.

    One rule for text and JSON output: it can be written to any stdout encoding.
    """
    cleaned = "".join(c if c.isascii() and c.isprintable() else "?" for c in value)
    return cleaned[:limit]


def suggest_id(instance: str, taken: set[str]) -> str:
    """A configuration-valid ID from the instance name, unique against ``taken``."""
    base = re.sub(r"[^a-z0-9]+", "-", instance.lower()).strip("-")[:56] or "wled"
    suggestion, number = base, 2
    while suggestion in taken:
        suggestion = f"{base}-{number}"
        number += 1
    taken.add(suggestion)
    return suggestion


def suggest_name(instance: str) -> str:
    """A display name restricted to letters, digits, space, ``.``, ``_`` and ``-``.

    The name is printed inside double quotes in a copyable command, so it must not
    carry characters that a POSIX shell, PowerShell or cmd.exe would interpret.
    """
    name = " ".join(_UNSAFE_NAME.sub(" ", instance).split())[:MAX_TEXT]
    # A leading dash would be read as an option by the add-device command.
    return name.lstrip("- ") or "WLED"


# -- the network exchange ----------------------------------------------------------------


class DatagramSocket(Protocol):
    def sendto(self, data: bytes, address: tuple[str, int], /) -> int: ...

    def recvfrom(self, size: int, /) -> tuple[bytes, Any]: ...

    def settimeout(self, value: float | None, /) -> None: ...

    def close(self) -> None: ...


def open_multicast_socket() -> DatagramSocket:
    """An IPv4 UDP socket on an ephemeral port; answers come back to that port."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)
        sock.bind(("0.0.0.0", 0))  # noqa: S104 - explicit one-shot mDNS UDP reply socket
    except BaseException:
        sock.close()
        raise
    return sock


def _from_mdns_port(source: Any) -> bool:
    """RFC 6762 section 6: a response comes from IPv4 port 5353.

    Only the address family and port are checked. Whether the sender is on-link cannot be
    verified from user space here, so a response from any IPv4 address with source port
    5353 is accepted; answers are unauthenticated.
    """
    if not isinstance(source, tuple) or len(source) != 2:
        return False
    host, port = source
    if port != MDNS_PORT or not isinstance(host, str):
        return False
    try:
        ipaddress.IPv4Address(host)
    except ValueError:
        return False
    return True


def listen(
    sock: DatagramSocket, until: float, clock: Callable[[], float], collector: Collector
) -> None:
    errors = 0
    while collector.received < MAX_DATAGRAMS:
        remaining = until - clock()
        if remaining <= 0:
            return
        sock.settimeout(remaining)
        try:
            packet, source = sock.recvfrom(RECEIVE_BUFFER)
        except TimeoutError:
            return
        except OSError:  # for example a datagram larger than the buffer on Windows
            errors += 1
            if errors >= MAX_RECEIVE_ERRORS:
                return
            continue
        if not _from_mdns_port(source):
            collector.dropped_sources += 1
            continue
        collector.feed(packet)


# -- the command -------------------------------------------------------------------------


def _configured(raw: str | None) -> list[KnownDevice]:
    """Known controllers of the configuration given with ``--config`` (read-only)."""
    from wled_mcp.discovery_engine import KnownDevice

    if raw is None:
        return []
    path = Path(raw)
    if not path.is_absolute():
        raise setup.Refusal("PATH_NOT_ABSOLUTE", "The --config path must be absolute.")
    content, _ = setup._read_regular(path)
    try:
        inventory = validate_document(content)
    except ConfigurationError as exc:
        raise setup.Refusal("CONFIG_INVALID", f"The configuration is invalid: {exc}") from None
    known: list[KnownDevice] = []
    for device in inventory.devices:
        _, host, port = setup.url_identity(device.base_url)
        known.append(KnownDevice(device.id, host.rstrip("."), None, port))
    return known


def configured_ranges(config: object | None) -> tuple[str, ...]:
    """The discovery ranges of the stored configuration.

    A seam: the ``[discovery].ranges`` key does not exist yet (#202 adds it to the
    validator and fills this in). The command has no range option: a scan never runs over
    ranges that were not configured, so until then only mDNS runs.
    """
    return ()


def build_transport(clock: Callable[[], float]) -> Any:
    from wled_mcp.discovery_engine import HttpTransport

    return HttpTransport(clock=clock)


def _timeout(value: float | None) -> float | None:
    if value is None:
        return None
    if not MIN_TIMEOUT <= value <= MAX_TIMEOUT:  # also rejects NaN
        raise setup.UsageError(
            f"--timeout must be between {MIN_TIMEOUT:g} and {MAX_TIMEOUT:g} seconds."
        )
    return value


def _add_command(candidate: FoundDevice) -> str:
    return (
        "wled-mcp config add-device --config <CONFIG> "
        f'--device-id {candidate.suggested_id} --device-name "{candidate.suggested_name}" '
        f"--base-url {candidate.base_url}"
    )


def _candidate_json(candidate: FoundDevice) -> dict[str, Any]:
    document = candidate.as_dict()
    document["add_device_command"] = _add_command(candidate) if candidate.status == "new" else None
    # Version-1 compatibility fields of the pre-engine output, kept additively.
    document.update(
        {
            "instance": candidate.instance,
            "host": None,
            "addresses": [candidate.address, *candidate.alternate_addresses],
            "port": 80,
            "suggested_base_url": candidate.base_url,
            "alternative_base_url": None,
            "already_configured": candidate.status != "new",
            "suggested_device_id": candidate.suggested_id,
            "suggested_device_name": candidate.suggested_name,
        }
    )
    return document


def _reason_text(coverage: dict[str, Any]) -> str:
    """One sentence that says what was and was not looked at (never a bare 'nothing')."""
    parts = []
    for method in coverage["methods"]:
        text = f"{method['method']} {method['status']}"
        if method.get("reason"):
            text += f" ({method['reason']})"
        parts.append(text)
    return "Methods: " + ", ".join(parts) + "."


def run_discover(
    args: argparse.Namespace,
    environ: Mapping[str, str],
    opener: Callable[[], DatagramSocket] = open_multicast_socket,
    clock: Callable[[], float] = monotonic,
) -> setup.CommandResult:
    from wled_mcp import discovery_engine

    command = "discover"
    timeout = _timeout(args.timeout)
    known = _configured(setup.option_path(args.config, setup.CONFIG_ENV, environ))
    result = discovery_engine.run_discovery(
        ranges=configured_ranges(known),
        known=known,
        timeout=timeout,
        transport=build_transport(clock),
        opener=opener,
        clock=clock,
    )
    coverage = result.coverage
    conclusion = result.conclusion
    problems: list[dict[str, str]] = []
    if not result.candidates:
        mdns_failed = any(
            m["method"] == "mdns" and m["status"] == "failed" for m in coverage["methods"]
        )
        if mdns_failed:
            code, lead = "MULTICAST_UNAVAILABLE", "The mDNS query could not be sent. "
        elif conclusion == "not_looked":
            code, lead = "NOT_LOOKED", "No discovery method could run. "
        else:
            code, lead = "NO_CANDIDATES", "No WLED controller was found"
            lead += (
                " (the run was complete). "
                if conclusion == "none_found_complete"
                else " (the run was not exhaustive). "
            )
        problems.append(
            {"code": code, "message": lead + _reason_text(coverage) + " " + NETWORK_HINTS}
        )
    data: dict[str, Any] = {
        "timeout_seconds": timeout,
        "queries_sent": result.queries_sent,  # v1 compatibility: mDNS datagrams sent
        "follow_up_sent": result.follow_up_sent,  # v1 compatibility
        "truncated": result.truncated,  # v1 compatibility
        "conclusion": conclusion,
        "candidate_count": len(result.candidates),
        "malformed_responses": result.malformed_responses,
        "dropped_datagrams": result.dropped_datagrams,
        "candidates": [_candidate_json(candidate) for candidate in result.candidates],
        "coverage": coverage,
        "warnings": result.warnings,
        "problems": problems,
    }
    return setup.CommandResult(
        command, setup.EXIT_PROBLEM if problems else setup.EXIT_OK, _text(result, problems), data
    )


def _text(result: DiscoveryResult, problems: list[dict[str, str]]) -> list[str]:
    lines = [f"Conclusion: {result.conclusion}"]
    for candidate in result.candidates:
        lines.append(f"- {candidate.suggested_name} [{candidate.status}]")
        lines.append(f"  MAC: {candidate.mac}")
        lines.append(f"  Suggested base URL: {candidate.base_url}")
        lines.append(f"  Firmware: {candidate.firmware_version}")
        lines.append(f"  Found by: {', '.join(candidate.found_by)}")
        if candidate.alternate_addresses:
            lines.append(f"  Other addresses: {', '.join(candidate.alternate_addresses)}")
        if candidate.status == "known":
            lines.append(f"  Already configured as {candidate.known_device_id}.")
        elif candidate.status == "address_changed":
            lines.append(
                f"  Configured as {candidate.known_device_id} at "
                f"{candidate.configured_address}, but it answered at another address. "
                "Nothing was rewritten; edit the configuration yourself."
            )
        else:
            lines.append(f"  Add with: {_add_command(candidate)}")
    lines.extend(result.warnings)
    if any(c.status == "new" for c in result.candidates):
        lines.append(
            "Replace <CONFIG> with the absolute configuration path (or set "
            "WLED_MCP_CONFIG and omit --config). Nothing was written; review each "
            "suggestion before adding it, then restart the server."
        )
    if result.candidates:
        lines.append(_reason_text(result.coverage))
    if not result.coverage["complete"]:
        lines.append(result.coverage["limits"][-1])
    lines.extend(problem["message"] for problem in problems)
    return lines


def handler(args: argparse.Namespace, environ: Mapping[str, str]) -> setup.CommandResult:
    # Module globals looked up per call, so tests can substitute the socket and clock.
    return run_discover(args, environ, open_multicast_socket, monotonic)


def register(commands: Any) -> None:
    parser = commands.add_parser(
        "discover",
        help="List WLED controllers found by mDNS and verified over HTTP (writes nothing).",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--config",
        help="Absolute configuration path (WLED_MCP_CONFIG); marks configured devices.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        help=(
            f"Lower the overall deadline in seconds (from {MIN_TIMEOUT:g} to "
            f"{MAX_TIMEOUT:g}; the default is the built-in limit)."
        ),
    )
    setup.add_format_option(parser)
