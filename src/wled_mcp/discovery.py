"""``wled-mcp discover``: one-shot IPv4 mDNS discovery of WLED controllers (issue #16).

Contract: docs/contract/cli.md; decisions ISSUE-16-DEC-001 (CLI only, standard library
only, never enrolls) and ISSUE-16-DEC-002 (TD-16-8). Runs only on explicit invocation:
never at startup, in ``doctor`` or as a fallback, and never from an MCP tool.

On the network it sends at most two datagrams, both to the mDNS group 224.0.0.251:5353
from an ephemeral port (a one-shot query, RFC 6762 section 5.1): one PTR question for
``_wled._tcp.local`` and at most one follow-up for SRV, TXT or A records that the
answers left out. It sends nothing to a candidate, reads no candidate over HTTP and
uses no IPv6. Answers are untrusted: parsing is bounded (datagram size, record count,
name length, compression pointers that must point backwards) and a malformed datagram
is dropped, never fatal. Text taken from answers is sanitized before it is printed.
"""

import argparse
import ipaddress
import re
import socket
import struct
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic
from typing import Any, Protocol

from wled_mcp import setup
from wled_mcp.config import ConfigurationError, validate_document

MDNS_GROUP = "224.0.0.251"
MDNS_PORT = 5353
SERVICE = ("_wled", "_tcp", "local")

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
    return len(name) == len(SERVICE) + 1 and name_key(name[1:]) == SERVICE


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
            if key == SERVICE and _is_instance(record.data):
                instance = name_key(record.data)
                if instance not in self.instances:
                    if len(self.instances) >= MAX_CANDIDATES:
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


@dataclass
class Candidate:
    instance: str
    host: str | None
    addresses: list[str]
    port: int | None
    mac: str | None
    local_name: str | None
    already_configured: bool = False
    device_id: str | None = None
    device_name: str | None = None

    @property
    def base_url(self) -> str | None:
        if not self.addresses or not self.port:
            return None
        return _url(self.addresses[0], self.port)

    @property
    def local_url(self) -> str | None:
        if self.local_name is None or not self.port:
            return None
        return _url(self.local_name, self.port)

    def command(self) -> str | None:
        url = self.base_url
        if url is None or self.already_configured:
            return None
        return (
            "wled-mcp config add-device --config <CONFIG> "
            f'--device-id {self.device_id} --device-name "{self.device_name}" '
            f"--base-url {url}"
        )

    def as_json(self) -> dict[str, Any]:
        return {
            "instance": self.instance,
            "host": self.host,
            "addresses": self.addresses,
            "port": self.port,
            "mac": self.mac,
            "suggested_base_url": self.base_url,
            "alternative_base_url": self.local_url,
            "already_configured": self.already_configured,
            "suggested_device_id": self.device_id,
            "suggested_device_name": self.device_name,
            "add_device_command": self.command(),
        }


def _url(host: str, port: int) -> str:
    return f"http://{host}" if port == 80 else f"http://{host}:{port}"


def _local_name(target: Name) -> str | None:
    """The mDNS host name for an LDH name in the ``.local`` domain, else ``None``."""
    if len(target) < 2 or target[-1].lower() != "local":
        return None
    if not all(_LDH_LABEL.fullmatch(label) for label in target):
        return None
    return ".".join(label.lower() for label in target)


def _mac(text: dict[str, bytes] | None) -> str | None:
    if text is None or "mac" not in text:
        return None
    value = text["mac"].decode("ascii", errors="replace").lower().replace(":", "")
    return value if _MAC.fullmatch(value) else None


def assemble(collector: Collector) -> list[Candidate]:
    """Candidates deduplicated by TXT ``mac``, else by IPv4 address, else by instance."""
    merged: dict[tuple[str, str], Candidate] = {}
    for key, name in collector.instances.items():
        service = collector.services.get(key)
        port = service[0] if service is not None and service[0] > 0 else None
        target = service[1] if service is not None else None
        addresses = [str(address) for address in collector.hosts.get(name_key(target or ()), [])]
        candidate = Candidate(
            instance=safe_text(name[0]),
            host=safe_text(".".join(target)) if target else None,
            addresses=addresses,
            port=port,
            mac=_mac(collector.texts.get(key)),
            local_name=_local_name(target) if target else None,
        )
        if candidate.mac is not None:
            identity = ("mac", candidate.mac)
        elif addresses:
            identity = ("address", addresses[0])
        else:
            identity = ("instance", ".".join(key))
        existing = merged.get(identity)
        if existing is None:
            merged[identity] = candidate
            continue
        for address in addresses:
            if address not in existing.addresses:
                existing.addresses.append(address)
        if existing.port is None:
            existing.port = candidate.port
        if existing.host is None:
            existing.host, existing.local_name = candidate.host, candidate.local_name
    return sorted(merged.values(), key=_order)


def _order(candidate: Candidate) -> tuple[int, int, str]:
    if candidate.addresses:
        return 0, int(ipaddress.IPv4Address(candidate.addresses[0])), candidate.instance
    return 1, 0, candidate.instance


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


def annotate(candidates: list[Candidate], hosts: set[str], ids: set[str]) -> None:
    taken = set(ids)
    for candidate in candidates:
        names = {address for address in candidate.addresses}
        if candidate.local_name is not None:
            names.add(candidate.local_name)
        candidate.already_configured = bool(names & hosts)
        candidate.device_id = suggest_id(candidate.instance, taken)
        candidate.device_name = suggest_name(candidate.instance)


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
        sock.bind(("0.0.0.0", 0))
    except BaseException:
        sock.close()
        raise
    return sock


@dataclass
class Outcome:
    candidates: list[Candidate]
    collector: Collector
    queries_sent: int
    follow_up_sent: bool
    multicast_unavailable: bool


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


def _listen(
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


def discover(
    timeout: float,
    opener: Callable[[], DatagramSocket] = open_multicast_socket,
    clock: Callable[[], float] = monotonic,
) -> Outcome:
    """Send the PTR query, listen for ``timeout`` seconds, send at most one follow-up."""
    collector = Collector()
    destination = (MDNS_GROUP, MDNS_PORT)
    try:
        sock = opener()
    except OSError:
        return Outcome([], collector, 0, False, True)
    sent = 0
    follow_up = False
    try:
        start = clock()
        try:
            sock.sendto(build_query([(SERVICE, TYPE_PTR)]), destination)
        except OSError:
            return Outcome([], collector, 0, False, True)
        sent = 1
        _listen(sock, start + min(1.0, timeout / 2), clock, collector)
        query = follow_up_query(collector.missing_questions())
        if query is not None and clock() < start + timeout:
            try:
                sock.sendto(query, destination)
                sent, follow_up = 2, True
            except OSError:
                pass
        _listen(sock, start + timeout, clock, collector)
    finally:
        sock.close()
    return Outcome(assemble(collector), collector, sent, follow_up, False)


# -- the command -------------------------------------------------------------------------


def _configured(
    raw: str | None,
) -> tuple[set[str], set[str]]:
    """Hosts and IDs of the configuration given with ``--config`` (read-only)."""
    if raw is None:
        return set(), set()
    path = Path(raw)
    if not path.is_absolute():
        raise setup.Refusal("PATH_NOT_ABSOLUTE", "The --config path must be absolute.")
    content, _ = setup._read_regular(path)
    try:
        inventory = validate_document(content)
    except ConfigurationError as exc:
        raise setup.Refusal("CONFIG_INVALID", f"The configuration is invalid: {exc}") from None
    hosts = {setup.url_identity(device.base_url)[1].rstrip(".") for device in inventory.devices}
    return hosts, {device.id for device in inventory.devices}


def _timeout(value: float | None) -> float:
    if value is None:
        return DEFAULT_TIMEOUT
    if not MIN_TIMEOUT <= value <= MAX_TIMEOUT:  # also rejects NaN
        raise setup.UsageError(
            f"--timeout must be between {MIN_TIMEOUT:g} and {MAX_TIMEOUT:g} seconds."
        )
    return value


def run_discover(
    args: argparse.Namespace,
    environ: Mapping[str, str],
    opener: Callable[[], DatagramSocket] = open_multicast_socket,
    clock: Callable[[], float] = monotonic,
) -> setup.CommandResult:
    command = "discover"
    timeout = _timeout(args.timeout)
    hosts, ids = _configured(setup.option_path(args.config, setup.CONFIG_ENV, environ))
    outcome = discover(timeout, opener, clock)
    annotate(outcome.candidates, hosts, ids)
    usable = [c for c in outcome.candidates if c.base_url is not None]
    problems: list[dict[str, str]] = []
    if outcome.multicast_unavailable:
        problems.append(
            {
                "code": "MULTICAST_UNAVAILABLE",
                "message": "The mDNS query could not be sent. " + NETWORK_HINTS,
            }
        )
    elif not usable:
        problems.append(
            {
                "code": "NO_CANDIDATES",
                "message": f"No WLED controller answered within {timeout:g} s. " + NETWORK_HINTS,
            }
        )
    data: dict[str, Any] = {
        "timeout_seconds": timeout,
        "queries_sent": outcome.queries_sent,
        "follow_up_sent": outcome.follow_up_sent,
        "candidate_count": len(outcome.candidates),
        "truncated": outcome.collector.truncated,
        "malformed_responses": outcome.collector.malformed,
        "dropped_datagrams": outcome.collector.dropped_sources,
        "candidates": [candidate.as_json() for candidate in outcome.candidates],
        "problems": problems,
    }
    return setup.CommandResult(
        command, setup.EXIT_PROBLEM if problems else setup.EXIT_OK, _text(outcome, problems), data
    )


def _text(outcome: Outcome, problems: list[dict[str, str]]) -> list[str]:
    lines: list[str] = []
    for candidate in outcome.candidates:
        lines.append(f"- {candidate.instance}")
        if candidate.mac is not None:
            lines.append(f"  MAC: {candidate.mac}")
        if candidate.base_url is not None:
            lines.append(f"  Suggested base URL: {candidate.base_url}")
        else:
            lines.append("  No IPv4 address or port was received; add it manually if needed.")
        if candidate.local_url is not None:
            lines.append(
                f"  Alternative: {candidate.local_url} (needs a resolver for .local names; "
                "the address can change with DHCP)"
            )
        if len(candidate.addresses) > 1:
            lines.append(f"  Other addresses: {', '.join(candidate.addresses[1:])}")
        if candidate.already_configured:
            lines.append("  Already configured.")
        command = candidate.command()
        if command is not None:
            lines.append(f"  Add with: {command}")
    if outcome.collector.truncated:
        lines.append(f"Only the first {MAX_CANDIDATES} answering instances are listed.")
    if outcome.candidates and any(c.command() for c in outcome.candidates):
        lines.append(
            "Replace <CONFIG> with the absolute configuration path (or set "
            "WLED_MCP_CONFIG and omit --config). Nothing was written; review each "
            "suggestion before adding it, then restart the server."
        )
    lines.extend(problem["message"] for problem in problems)
    if not lines:
        lines.append("No candidates.")
    return lines


def handler(args: argparse.Namespace, environ: Mapping[str, str]) -> setup.CommandResult:
    # Module globals looked up per call, so tests can substitute the socket and clock.
    return run_discover(args, environ, open_multicast_socket, monotonic)


def register(commands: Any) -> None:
    parser = commands.add_parser(
        "discover",
        help="List WLED controllers that answer one mDNS query (writes nothing).",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--config",
        help="Absolute configuration path (WLED_MCP_CONFIG); marks configured devices.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        help=f"Listen window in seconds (default {DEFAULT_TIMEOUT:g}, at most {MAX_TIMEOUT:g}).",
    )
    setup.add_format_option(parser)
