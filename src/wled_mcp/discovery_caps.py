"""Hard caps for discovery ranges, shared by startup, tool and probe (DISC-05, #202).

Standard library only, so that the configuration validator, the MCP tool and the probe
engine can all import it. No parameter, configuration key or environment variable raises a
number here (DEC-035). Rejections carry a fixed reason and never the offending value.
"""

import ipaddress
import re
from collections.abc import Iterable, Sequence
from typing import Any

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
MDNS_WINDOW = 6.0
MAX_CANDIDATES = 64
MAX_KNOWN_READS = 16

# RFC 1918, built from integers so that no private address literal sits in the source.
PRIVATE_NETWORKS = (
    ipaddress.IPv4Network((10 << 24, 8)),
    ipaddress.IPv4Network(((172 << 24) | (16 << 16), 12)),
    ipaddress.IPv4Network(((192 << 24) | (168 << 16), 16)),
)

CAPS: dict[str, Any] = {
    "ranges": MAX_RANGES,
    "min_prefix": MIN_PREFIX,
    "max_prefix": MAX_PREFIX,
    "address_space": [str(network) for network in PRIVATE_NETWORKS],
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

# Strict dotted-quad CIDR: ASCII digits only, so netmask and hostmask notation, whitespace
# and non-ASCII digits never reach ipaddress.
_CIDR = re.compile(r"[0-9]{1,3}(?:\.[0-9]{1,3}){3}/[0-9]{1,2}", re.ASCII)


class DiscoveryRangeError(ValueError):
    """A range violates a hard cap; nothing was probed. The value is never echoed."""

    def __init__(self, reason: str, index: int | None = None) -> None:
        super().__init__(f"discovery range rejected: {reason}")
        self.reason = reason
        self.index = index


def address_allowed(address: ipaddress.IPv4Address) -> bool:
    return any(address in network for network in PRIVATE_NETWORKS)


def _padded(part: str) -> bool:
    return len(part) > 1 and part.startswith("0")


def _parse(item: object) -> ipaddress.IPv4Network | str:
    """The network, or the fixed reason when the entry is not a strict network."""
    if isinstance(item, ipaddress.IPv4Network):
        return item
    if not isinstance(item, str) or not _CIDR.fullmatch(item):
        return "not_ipv4_cidr"
    address, prefix = item.split("/")
    if _padded(prefix) or any(_padded(octet) for octet in address.split(".")):
        return "not_ipv4_cidr"
    try:
        return ipaddress.IPv4Network(item, strict=True)
    except ipaddress.NetmaskValueError:
        return "not_ipv4_cidr"
    except ValueError:
        try:
            ipaddress.IPv4Network(item, strict=False)
        except ValueError:
            return "not_ipv4_cidr"
        return "not_network_address"


def _reason(network: ipaddress.IPv4Network, earlier: Iterable[ipaddress.IPv4Network]) -> str | None:
    if network.network_address.is_loopback:
        return "loopback"
    if network.network_address.is_link_local:
        return "link_local"
    if not any(network.subnet_of(private) for private in PRIVATE_NETWORKS):
        return "not_private"
    if network.prefixlen < MIN_PREFIX:
        return "too_broad"
    if network.prefixlen > MAX_PREFIX:
        return "prefix_too_long"
    for other in earlier:
        if other == network:
            return "duplicate"
        if other.overlaps(network):
            return "overlap"
    return None


def check_ranges(ranges: Sequence[object]) -> list[tuple[int, str]]:
    """Every ``(index, reason)``: the first failing reason per entry, ascending index.

    Order per entry: syntax, network address, loopback, link-local, private, prefix
    bounds, then duplicate or overlap against earlier entries that passed. The entry
    count is not checked here (the schema and the probe path do that).
    """
    rejected: list[tuple[int, str]] = []
    accepted: list[ipaddress.IPv4Network] = []
    for index, item in enumerate(ranges):
        parsed = _parse(item)
        reason = parsed if isinstance(parsed, str) else _reason(parsed, accepted)
        if reason is not None:
            rejected.append((index, reason))
        elif not isinstance(parsed, str):
            accepted.append(parsed)
    return rejected


def validate_ranges(ranges: Iterable[object]) -> list[ipaddress.IPv4Network]:
    """Parsed networks, or ``DiscoveryRangeError`` on the first violation (probe time)."""
    items = list(ranges)
    if len(items) > MAX_RANGES:
        raise DiscoveryRangeError("too_many_ranges")
    rejected = check_ranges(items)
    if rejected:
        index, reason = rejected[0]
        raise DiscoveryRangeError(reason, index)
    return [
        item if isinstance(item, ipaddress.IPv4Network) else ipaddress.IPv4Network(str(item))
        for item in items
    ]
