"""Shared discovery engine (issue #199; DISC-01 to DISC-05 engine side, DISC-13).

Everything runs on fakes: a scripted ``Transport`` for ``GET /json/info``, the fake
multicast network of ``tests/test_discovery.py`` on a simulated clock, and a fake
``http.client`` connection for the default transport. An autouse guard fails any real
socket or HTTP connection. Addresses are synthetic RFC 1918 values and invented MACs.
"""

import http.client
import ipaddress
import json
import socket
import struct
import threading
import time
from typing import Any

import pytest

from tests.test_discovery import (
    FakeNetwork,
    a,
    answer_first,
    device,
    mdns,
    name,
    record,
    response,
)
from wled_mcp import discovery, discovery_engine
from wled_mcp.discovery import TYPE_PTR, TYPE_SRV, TYPE_TXT
from wled_mcp.discovery_engine import (
    DiscoveryRangeError,
    HttpTransport,
    InfoResult,
    KnownDevice,
    run_discovery,
    validate_ranges,
)

MAC_A = "00005e005301"
MAC_B = "00005e005302"
MAC_C = "00005e005303"


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a real socket was opened")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(http.client.HTTPConnection, "connect", refuse)


def wled(mac: str, name: str = "WLED") -> InfoResult:
    return InfoResult("wled", mac, "0.15.0", "FOSS", name)


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0
        self.lock = threading.Lock()

    def __call__(self) -> float:
        with self.lock:
            return self.now


class FakeTransport:
    """Scripted ``GET /json/info``; thread-safe, records calls and peak concurrency."""

    def __init__(
        self,
        answers: dict[str, InfoResult] | None = None,
        default: InfoResult | None = None,
        clock: Clock | None = None,
        step: float = 0.0,
        raises: tuple[str, ...] = (),
        delay: float = 0.0,
    ) -> None:
        self.answers = answers or {}
        self.default = default or InfoResult("timeout")
        self.clock, self.step, self.raises, self.delay = clock, step, raises, delay
        self.calls: list[tuple[str, int, float]] = []
        self.lock = threading.Lock()
        self.active = 0
        self.peak = 0

    def get_info(self, address: str, port: int, timeout: float) -> InfoResult:
        with self.lock:
            self.calls.append((address, port, timeout))
            self.active += 1
            self.peak = max(self.peak, self.active)
            if self.clock is not None:
                self.clock.now += self.step
        try:
            if self.delay:
                time.sleep(self.delay)
            if address in self.raises:
                raise RuntimeError("boom")
            return self.answers.get(address, self.default)
        finally:
            with self.lock:
                self.active -= 1

    @property
    def addresses(self) -> set[str]:
        return {address for address, _, _ in self.calls}


def unicast(ranges: list[str], transport: FakeTransport, **kwargs: Any):
    """A unicast-only run (no socket is ever opened)."""

    def no_socket() -> Any:
        raise AssertionError("mDNS was not requested")

    return run_discovery(
        methods=("unicast",),
        ranges=ranges,
        transport=transport,
        opener=no_socket,
        clock=kwargs.pop("clock", Clock()),
        **kwargs,
    )


def method(result, which: str) -> dict[str, Any]:
    return next(m for m in result.coverage["methods"] if m["method"] == which)


# ------------------------------------------------------------------ identification (DISC-T01)


class FakeResponse:
    def __init__(self, status: int, body: bytes) -> None:
        self.status, self.body, self.offset = status, body, 0

    def read(self, size: int) -> bytes:
        chunk = self.body[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk


class FakeConnection:
    """Replaces ``http.client.HTTPConnection``; records the one request it is given."""

    instances: list["FakeConnection"] = []
    status = 200
    body = b""
    error: Exception | None = None

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.host, self.port, self.timeout = host, port, timeout
        self.requests: list[tuple[str, str, dict[str, str]]] = []
        self.closed = False
        FakeConnection.instances.append(self)

    def request(self, method: str, path: str, headers: dict[str, str]) -> None:
        self.requests.append((method, path, headers))

    def getresponse(self) -> FakeResponse:
        if self.error is not None:
            raise self.error
        return FakeResponse(self.status, self.body)

    def close(self) -> None:
        self.closed = True


def probe(
    body: bytes = b"",
    status: int = 200,
    error: Exception | None = None,
) -> tuple[InfoResult, FakeConnection]:
    FakeConnection.instances = []
    FakeConnection.status, FakeConnection.body, FakeConnection.error = status, body, error
    result = HttpTransport(connection_factory=FakeConnection).get_info("10.0.0.5", 80, 1.5)
    (connection,) = FakeConnection.instances
    return result, connection


def info_body(**fields: Any) -> bytes:
    document = {"brand": "WLED", "ver": "0.15.0", "mac": "00:00:5E:00:53:01", "product": "FOSS"}
    document.update(fields)
    return json.dumps({k: v for k, v in document.items() if v is not None}).encode()


def test_wled_info_is_identified_and_the_request_is_one_plain_get():
    result, connection = probe(info_body(name="Desk"))
    assert result == InfoResult("wled", MAC_A, "0.15.0", "FOSS", "Desk")
    assert connection.requests == [
        (
            "GET",
            "/json/info",
            {
                "User-Agent": "wled-mcp-discovery",
                "Accept": "application/json",
                "Connection": "close",
            },
        )
    ]
    assert (connection.host, connection.port, connection.timeout) == ("10.0.0.5", 80, 1.5)
    assert connection.closed


@pytest.mark.parametrize(
    "body",
    [
        b'{"hello": "world"}',  # JSON, but not WLED
        b"<html>router login</html>",  # not JSON
        b"{not json",
        b"[]",
        b'"WLED"',
        info_body(brand="Other"),
        info_body(brand=None),
        info_body(ver=None),
        info_body(ver=12),
        info_body(mac=None),
        info_body(mac="zz:00:5e:00:53:01"),
        info_body(mac="00005e00530"),  # eleven digits
        info_body(mac=["00005e005301"]),
        b"[" * 100 + b"]" * 100,  # deeper than the JSON bounds
    ],
)
def test_answers_that_fail_the_identity_check_are_other(body):
    result, _ = probe(body)
    assert result.kind == "other"


def test_oversized_redirecting_and_error_answers_are_other():
    assert probe(info_body() + b" " * (discovery_engine.MAX_BODY_BYTES + 1))[0].kind == "other"
    exactly = info_body()
    padded = exactly + b" " * (discovery_engine.MAX_BODY_BYTES - len(exactly))
    assert probe(padded)[0].kind == "wled"  # exactly at the bound is still accepted
    for status in (301, 302, 307, 401, 404, 500):
        result, connection = probe(info_body(), status=status)
        assert result.kind == "other"
        assert len(connection.requests) == 1  # a redirect is not followed


def test_transport_failures_are_classified():
    assert probe(error=ConnectionRefusedError())[0].kind == "refused"
    assert probe(error=TimeoutError())[0].kind == "timeout"
    assert probe(error=OSError("no route"))[0].kind == "timeout"
    assert probe(error=http.client.BadStatusLine("x"))[0].kind == "other"


def test_slow_body_is_cut_off_by_the_total_time_bound():
    clock = Clock()

    class Slow(FakeResponse):
        def read(self, size: int) -> bytes:
            clock.now += 1.0  # each chunk takes a second
            return super().read(size)

    class SlowConnection(FakeConnection):
        def getresponse(self) -> FakeResponse:
            return Slow(200, b" " * 20000)

    result = HttpTransport(connection_factory=SlowConnection, clock=clock).get_info(
        "10.0.0.5", 80, 1.5
    )
    assert result.kind == "timeout"


def test_unusual_text_in_info_is_sanitized():
    result, _ = probe(info_body(name="desk\x1b[2J\n‮", product="xé"))
    assert result.kind == "wled"
    assert result.name == "desk?[2J??" and result.product == "x?"


# ------------------------------------------------------------------ caps at probe time (DISC-T03)


@pytest.mark.parametrize(
    ("cidr", "reason"),
    [
        ("8.8.8.0/24", "not_private"),
        ("127.0.0.0/24", "loopback"),
        ("169.254.1.0/24", "link_local"),
        ("100.64.0.0/24", "not_private"),
        ("224.0.0.0/24", "not_private"),
        ("172.15.255.0/24", "not_private"),
        ("172.32.0.0/24", "not_private"),
        ("192.169.0.0/24", "not_private"),
        ("10.0.0.0/23", "too_broad"),
        ("10.0.0.0/8", "too_broad"),
        ("10.0.0.5/24", "not_network_address"),
        ("10.0.0.0/31", "prefix_too_long"),
        ("10.0.0.4/32", "prefix_too_long"),
        ("10.0.0.0", "not_ipv4_cidr"),
        ("10.0.0.0/24 ", "not_ipv4_cidr"),
        ("2001:db8::/64", "not_ipv4_cidr"),
        ("example.invalid/24", "not_ipv4_cidr"),
        ("", "not_ipv4_cidr"),
        ("10.0.0.0/33", "not_ipv4_cidr"),
    ],
)
def test_ranges_outside_the_caps_probe_nothing(cidr, reason):
    transport = FakeTransport(default=wled(MAC_A))
    with pytest.raises(DiscoveryRangeError) as raised:
        unicast(["10.0.1.0/24", cidr], transport)
    assert raised.value.reason == reason and raised.value.index == 1
    assert cidr.strip() == "" or cidr not in str(raised.value)  # the value is never echoed
    assert transport.calls == []


def test_fifth_range_duplicate_and_overlap_are_rejected():
    five = [f"10.0.{index}.0/24" for index in range(5)]
    with pytest.raises(DiscoveryRangeError, match="too_many_ranges"):
        validate_ranges(five)
    with pytest.raises(DiscoveryRangeError, match="duplicate"):
        validate_ranges(["10.0.0.0/24", "10.0.0.0/24"])
    with pytest.raises(DiscoveryRangeError, match="overlap"):
        validate_ranges(["10.0.0.0/25", "10.0.0.0/24"])


def test_valid_private_ranges_are_accepted_and_network_objects_are_checked_too():
    ranges = validate_ranges(["10.0.0.0/24", "172.16.5.0/28", "192.168.1.0/30", "10.9.0.0/24"])
    assert len(ranges) == 4
    with pytest.raises(DiscoveryRangeError):
        validate_ranges([ipaddress.IPv4Network("8.8.8.0/24")])  # a hand-built object is checked too


def test_unicast_probes_only_usable_hosts_on_port_80_of_the_given_ranges():
    transport = FakeTransport(default=InfoResult("refused"))
    result = unicast(["192.168.7.0/30", "10.1.1.0/29"], transport)
    assert transport.addresses == {
        "192.168.7.1",
        "192.168.7.2",
        *(f"10.1.1.{n}" for n in range(1, 7)),
    }
    assert {port for _, port, _ in transport.calls} == {80}
    rows = result.coverage["unicast"]["ranges"]
    assert [(r["cidr"], r["hosts_total"], r["refused"]) for r in rows] == [
        ("192.168.7.0/30", 2, 2),
        ("10.1.1.0/29", 6, 6),
    ]


def test_without_ranges_unicast_is_skipped_and_nothing_is_probed():
    transport = FakeTransport(default=wled(MAC_A))
    result = unicast([], transport)
    assert method(result, "unicast") == {
        "method": "unicast",
        "requested": True,
        "status": "skipped",
        "reason": "no_ranges_configured",
    }
    assert transport.calls == [] and result.coverage["conclusion"] == "not_looked"


def test_ranges_are_ignored_when_unicast_is_not_requested():
    network = FakeNetwork()
    transport = FakeTransport(default=wled(MAC_A))
    result = run_discovery(
        methods=("mdns",),
        ranges=["10.0.1.0/24"],
        transport=transport,
        opener=network.opener,
        clock=network.clock,
    )
    assert transport.calls == []
    assert method(result, "unicast")["reason"] == "not_requested"
    assert "unicast" not in result.coverage


def test_lower_values_are_honored_and_higher_ones_are_clamped():
    transport = FakeTransport(default=InfoResult("refused"))
    unicast(["10.0.0.0/30"], transport, timeout=0.5)
    assert {t for _, _, t in transport.calls} == {0.5}
    transport = FakeTransport(default=InfoResult("refused"))
    unicast(["10.0.0.0/30"], transport, timeout=1000)
    assert {t for _, _, t in transport.calls} == {discovery_engine.HOST_TIMEOUT}
    for bad in (0, -1, float("nan"), float("inf")):
        transport = FakeTransport(default=InfoResult("refused"))
        unicast(["10.0.0.0/30"], transport, timeout=bad)  # ignored, never raises
        assert {t for _, _, t in transport.calls} <= {discovery_engine.HOST_TIMEOUT}
    answers = {f"10.0.0.{n}": wled(f"00005e0000{n:02x}") for n in range(1, 11)}
    capped = unicast(["10.0.0.0/24"], FakeTransport(answers), max_candidates=3)
    assert len(capped.candidates) == 3 and capped.warnings
    assert method(capped, "unicast")["reason"] == "cap_reached"
    huge = unicast(["10.0.0.0/24"], FakeTransport(answers), max_candidates=10_000)
    assert len(huge.candidates) == 10 and not huge.warnings


def test_the_default_caps_are_reported_read_only():
    result = unicast(["10.0.0.0/30"], FakeTransport())
    caps = result.coverage["caps"]
    assert caps["ranges"] == 4 and caps["in_flight"] == 32 and caps["candidates"] == 64
    caps["ranges"] = 99  # a copy: the module constants are untouched
    assert discovery_engine.CAPS["ranges"] == 4


# ------------------------------------------------------------------ mDNS and verification


def service_device(
    service: str, instance: str, address: str, port: int = 80, mac: str = MAC_A
) -> bytes:
    full = f"{instance}.{service}.local"
    host = mdns(instance)
    owner = name(full)
    return response(
        [record(name(f"{service}.local"), TYPE_PTR, owner, rclass=1)],
        [
            record(owner, TYPE_SRV, struct.pack("!HHH", 0, 0, port) + name(host)),
            record(owner, TYPE_TXT, bytes([len(b"mac=" + mac.encode())]) + b"mac=" + mac.encode()),
            a(host, address),
        ],
    )


def mdns_run(network: FakeNetwork, transport: FakeTransport, **kwargs: Any):
    return run_discovery(
        methods=("mdns",), transport=transport, opener=network.opener, clock=network.clock, **kwargs
    )


def test_wled_service_answer_is_verified_and_listed():
    network = FakeNetwork(answer_first(device("desk", "10.0.2.21")))
    transport = FakeTransport({"10.0.2.21": wled(MAC_A, "Desk")})
    result = mdns_run(network, transport)
    (candidate,) = result.candidates
    assert (candidate.mac, candidate.address, candidate.found_by) == (MAC_A, "10.0.2.21", ["mdns"])
    assert candidate.suggested_id == "desk" and candidate.status == "new"
    report = result.coverage["mdns"]
    assert report["rounds_sent"] == 3 and report["window_seconds"] == 6.0
    assert (report["responders"], report["answers_verified"], report["answers_rejected"]) == (
        1,
        1,
        0,
    )
    assert report["services_queried"] == ["_wled._tcp.local", "_http._tcp.local"]
    assert result.conclusion == "candidates_found"


def test_http_service_fallback_is_verified_through_info():
    packet = service_device("_http._tcp", "plain-http", "10.0.2.50")
    network = FakeNetwork(answer_first(packet))
    result = mdns_run(network, FakeTransport({"10.0.2.50": wled(MAC_B)}))
    (candidate,) = result.candidates
    assert candidate.mac == MAC_B and candidate.found_by == ["mdns"]


def test_non_wled_http_service_is_rejected_and_counted():
    packet = service_device("_http._tcp", "printer", "10.0.2.51")
    network = FakeNetwork(answer_first(packet))
    transport = FakeTransport({"10.0.2.51": InfoResult("other")})
    result = mdns_run(network, transport)
    assert result.candidates == []
    assert transport.addresses == {"10.0.2.51"}
    report = result.coverage["mdns"]
    assert (report["responders"], report["answers_verified"], report["answers_rejected"]) == (
        1,
        0,
        1,
    )
    assert result.conclusion == "none_found_incomplete"


def test_unverified_wled_service_answer_is_not_listed():
    network = FakeNetwork(answer_first(device("ghost", "10.0.2.22")))
    for answer in (InfoResult("other"), InfoResult("timeout"), InfoResult("refused")):
        result = mdns_run(network, FakeTransport({"10.0.2.22": answer}))
        assert result.candidates == []
        assert result.coverage["mdns"]["answers_rejected"] == 1
        network.sent.clear()
        network.now = 100.0


def test_announced_port_other_than_80_is_not_probed():
    network = FakeNetwork(answer_first(device("odd", "10.0.2.23", port=8080)))
    transport = FakeTransport(default=wled(MAC_A))
    result = mdns_run(network, transport)
    assert result.candidates == [] and transport.calls == []
    assert result.coverage["mdns"]["answers_rejected"] == 1


def test_socket_failure_means_the_method_failed_and_nothing_was_looked_at():
    network = FakeNetwork(fail_open=True)
    result = mdns_run(network, FakeTransport())
    assert method(result, "mdns")["status"] == "failed"
    assert method(result, "mdns")["reason"] == "multicast_unavailable"
    assert result.conclusion == "not_looked" and result.coverage["complete"] is False
    assert "mdns" not in result.coverage
    network = FakeNetwork()
    network.fail_send = True
    result = mdns_run(network, FakeTransport())
    assert method(result, "mdns")["reason"] == "multicast_unavailable"
    assert network.sockets[0].closed


def test_mdns_only_run_sends_nothing_but_multicast_and_one_read_per_answer():
    network = FakeNetwork(answer_first(device("a", "10.0.2.21"), device("b", "10.0.2.22")))
    transport = FakeTransport(default=wled(MAC_A))
    mdns_run(network, transport)
    assert {address for _, address in network.sent} == {(discovery.MDNS_GROUP, 5353)}
    assert transport.addresses == {"10.0.2.21", "10.0.2.22"}


# ------------------------------------------------------------------ merging (DISC-T02)


def test_methods_and_addresses_merge_by_mac():
    network = FakeNetwork(answer_first(device("desk", "10.0.2.21")))
    answers = {
        "10.0.2.21": wled(MAC_A, "Desk"),
        "10.0.2.30": wled(MAC_A, "Desk"),  # same controller, second address (unicast)
        "10.0.2.31": wled(MAC_B),
    }
    transport = FakeTransport(answers)
    result = run_discovery(
        ranges=["10.0.2.0/24"], transport=transport, opener=network.opener, clock=network.clock
    )
    desk, other = result.candidates
    assert (desk.mac, desk.address, desk.alternate_addresses) == (MAC_A, "10.0.2.21", ["10.0.2.30"])
    assert desk.found_by == ["mdns", "unicast"]
    assert (other.mac, other.found_by, other.status) == (MAC_B, ["unicast"], "new")
    assert other.suggested_id == f"wled-{MAC_B[-6:]}"  # a generic name gives no label
    assert {c.suggested_id for c in result.candidates} == {"desk", "wled-005302"}


def test_at_most_four_alternate_addresses_are_kept():
    answers = {f"10.0.3.{n}": wled(MAC_A) for n in range(1, 8)}
    (candidate,) = unicast(["10.0.3.0/24"], FakeTransport(answers)).candidates
    assert candidate.address == "10.0.3.1"
    assert candidate.alternate_addresses == [f"10.0.3.{n}" for n in range(2, 6)]


def test_candidate_dictionary_has_the_contract_fields():
    result = unicast(["10.0.3.0/24"], FakeTransport({"10.0.3.9": wled(MAC_A, "Desk")}))
    (document,) = result.as_dict()["candidates"]
    assert document == {
        "address": "10.0.3.9",
        "base_url": "http://10.0.3.9",
        "suggested_id": "desk",
        "suggested_name": "Desk",
        "mac": MAC_A,
        "firmware_version": "0.15.0",
        "product": "FOSS",
        "found_by": ["unicast"],
        "status": "new",
    }


# ------------------------------------------------------------------ known controllers


def test_known_by_address_by_stored_mac_and_by_extra_read_without_touching_the_snapshot():
    known = [
        KnownDevice("by-address", "10.0.4.10"),
        KnownDevice("by-mac", "10.0.5.99", MAC_B),  # moved: stored MAC matches elsewhere
        KnownDevice("by-read", "10.0.5.77"),  # no MAC stored: one extra read
        KnownDevice("gone", "10.0.5.88"),  # does not answer
    ]
    snapshot = list(known)
    answers = {
        "10.0.4.10": wled(MAC_A),
        "10.0.4.20": wled(MAC_B),
        "10.0.4.30": wled(MAC_C),
        "10.0.4.40": wled("00005e005304"),
        "10.0.5.77": wled(MAC_C),  # the configured host now reports the MAC found at .30
    }
    result = unicast(["10.0.4.0/24"], FakeTransport(answers), known=known)
    by_address = {c.address: c for c in result.candidates}
    assert by_address["10.0.4.10"].status == "known"
    assert by_address["10.0.4.10"].known_device_id == "by-address"
    moved = by_address["10.0.4.20"]
    assert (moved.status, moved.known_device_id) == ("address_changed", "by-mac")
    assert moved.configured_address == "10.0.5.99"
    read = by_address["10.0.4.30"]
    assert (read.status, read.known_device_id) == ("address_changed", "by-read")
    assert read.configured_address == "10.0.5.77"
    fresh = by_address["10.0.4.40"]
    assert fresh.status == "new" and fresh.known_device_id is None
    assert fresh.configured_address is None
    # Only the entries without a MAC that no candidate matched were read.
    assert result.coverage["known_devices_checked"] == 2
    assert result.coverage["known_devices_unmatched"] == 1  # "gone" did not answer
    assert known == snapshot  # never modified


def test_unanswering_known_device_never_claims_a_change():
    known = [KnownDevice("silent", "10.0.4.5")]
    result = unicast(["10.0.4.0/24"], FakeTransport({"10.0.4.40": wled(MAC_A)}), known=known)
    (candidate,) = result.candidates
    assert candidate.status == "new" and candidate.configured_address is None
    assert result.coverage["known_devices_unmatched"] == 1


def test_no_extra_read_when_every_candidate_is_already_matched():
    known = [KnownDevice("a", "10.0.4.10"), KnownDevice("b", "10.0.4.55")]
    transport = FakeTransport({"10.0.4.10": wled(MAC_A)})
    result = unicast(["10.0.4.0/28"], transport, known=known)
    assert result.coverage["known_devices_checked"] == 0
    assert "10.0.4.55" not in transport.addresses


def test_at_most_sixteen_known_devices_are_read():
    known = [KnownDevice(f"d{n}", f"10.0.5.{n}") for n in range(100, 120)]
    transport = FakeTransport({"10.0.4.40": wled(MAC_A)})
    result = unicast(["10.0.4.0/24"], transport, known=known)
    assert result.coverage["known_devices_checked"] == 16
    assert len(transport.addresses & {k.host for k in known}) == 16


def test_suggested_id_is_unique_against_known_ids_and_the_list():
    known = [KnownDevice("desk", "10.0.4.200", MAC_C)]
    answers = {
        "10.0.4.1": wled(MAC_A, "Desk"),
        "10.0.4.2": wled(MAC_B, "Desk"),
    }
    result = unicast(["10.0.4.0/24"], FakeTransport(answers), known=known)
    assert [c.suggested_id for c in result.candidates] == ["desk-2", "desk-3"]


# ------------------------------------------------------------------ coverage precedence (DISC-T04)


def test_rule_1_no_method_ran_is_not_looked():
    network = FakeNetwork(fail_open=True)
    result = run_discovery(
        ranges=[], transport=FakeTransport(), opener=network.opener, clock=network.clock
    )
    assert result.conclusion == "not_looked" and result.coverage["complete"] is False
    assert run_discovery(methods=(), transport=FakeTransport()).conclusion == "not_looked"
    only_unicast = unicast([], FakeTransport())
    assert only_unicast.conclusion == "not_looked"


def test_rule_3_mdns_completed_without_answers_and_unicast_skipped_is_incomplete():
    network = FakeNetwork()
    result = run_discovery(
        ranges=[], transport=FakeTransport(), opener=network.opener, clock=network.clock
    )
    assert method(result, "mdns")["status"] == "completed"
    assert method(result, "mdns")["reason"] == "no_answers"
    assert result.conclusion == "none_found_incomplete"
    assert result.coverage["complete"] is False
    assert discovery_engine.LIMIT_NOT_EXHAUSTIVE in result.coverage["limits"]


def test_rule_3_a_deadline_that_leaves_hosts_not_probed_is_incomplete():
    clock = Clock()
    transport = FakeTransport(default=InfoResult("refused"), clock=clock, step=1.0)
    result = unicast(["10.0.6.0/24"], transport, clock=clock)
    row = result.coverage["unicast"]["ranges"][0]
    assert row["not_probed"] > 0 and row["hosts_probed"] + row["not_probed"] == 254
    assert row["hosts_probed"] <= 20 + discovery_engine.MAX_IN_FLIGHT  # the 20 s phase deadline
    assert result.coverage["unicast"]["deadline_reached"] is True
    assert method(result, "unicast")["status"] == "partial"
    assert method(result, "unicast")["reason"] == "deadline_reached"
    assert result.conclusion == "none_found_incomplete"


def test_the_caller_timeout_also_bounds_the_whole_call():
    clock = Clock()
    transport = FakeTransport(default=InfoResult("refused"), clock=clock, step=1.0)
    result = unicast(["10.0.6.0/24"], transport, clock=clock, timeout=3)
    row = result.coverage["unicast"]["ranges"][0]
    assert row["not_probed"] > 0
    assert row["hosts_probed"] <= 3 + discovery_engine.MAX_IN_FLIGHT


def test_rule_3_timed_out_hosts_do_not_block_a_complete_none_found():
    network = FakeNetwork()
    transport = FakeTransport(default=InfoResult("timeout"))
    result = run_discovery(
        ranges=["10.0.6.0/28"], transport=transport, opener=network.opener, clock=network.clock
    )
    row = result.coverage["unicast"]["ranges"][0]
    assert (row["hosts_probed"], row["timed_out"], row["not_probed"]) == (14, 14, 0)
    assert method(result, "mdns")["status"] == method(result, "unicast")["status"] == "completed"
    assert result.conclusion == "none_found_complete" and result.coverage["complete"] is True
    assert discovery_engine.LIMIT_NOT_EXHAUSTIVE not in result.coverage["limits"]


def test_rule_2_candidates_found_keeps_complete_independent_of_the_candidates():
    # Unicast only: found something, but the run was not exhaustive.
    partial = unicast(["10.0.6.0/28"], FakeTransport({"10.0.6.3": wled(MAC_A)}))
    assert partial.conclusion == "candidates_found" and partial.coverage["complete"] is False
    # Both methods completed: complete as well.
    network = FakeNetwork()
    both = run_discovery(
        ranges=["10.0.6.0/28"],
        transport=FakeTransport({"10.0.6.3": wled(MAC_A)}),
        opener=network.opener,
        clock=network.clock,
    )
    assert both.conclusion == "candidates_found" and both.coverage["complete"] is True


def test_a_failed_mdns_with_a_working_probe_is_looked_but_not_complete():
    network = FakeNetwork(fail_open=True)
    result = run_discovery(
        ranges=["10.0.6.0/30"],
        transport=FakeTransport(),
        opener=network.opener,
        clock=network.clock,
    )
    assert method(result, "mdns")["status"] == "failed"
    assert result.conclusion == "none_found_incomplete" and result.coverage["complete"] is False


# ------------------------------------------------------------------ partial failure, concurrency


def test_one_raising_host_does_not_abort_the_run():
    answers = {"10.0.7.9": wled(MAC_A)}
    transport = FakeTransport(answers, default=InfoResult("refused"), raises=("10.0.7.3",))
    result = unicast(["10.0.7.0/28"], transport)
    assert [c.mac for c in result.candidates] == [MAC_A]
    assert method(result, "unicast")["status"] == "partial"
    assert method(result, "unicast")["reason"] == "internal_error"
    assert result.coverage["complete"] is False
    assert result.coverage["unicast"]["ranges"][0]["hosts_probed"] == 14


def test_a_raising_verification_is_a_partial_mdns_and_the_rest_continues():
    network = FakeNetwork(answer_first(device("a", "10.0.2.21"), device("b", "10.0.2.22")))
    transport = FakeTransport({"10.0.2.22": wled(MAC_B)}, raises=("10.0.2.21",))
    result = mdns_run(network, transport)
    assert [c.mac for c in result.candidates] == [MAC_B]
    assert method(result, "mdns")["status"] == "partial"
    assert method(result, "mdns")["reason"] == "internal_error"


def test_in_flight_requests_never_exceed_the_cap_and_do_overlap():
    transport = FakeTransport(default=InfoResult("refused"), delay=0.002)
    result = unicast(["10.0.8.0/24", "10.0.9.0/24"], transport)
    assert len(transport.calls) == 508
    assert 1 < transport.peak <= discovery_engine.MAX_IN_FLIGHT
    assert result.coverage["unicast"]["ranges"][1]["hosts_probed"] == 254


def test_engine_prints_nothing(capsys):
    network = FakeNetwork(answer_first(device("a", "10.0.2.21")))
    run_discovery(
        ranges=["10.0.8.0/30"],
        transport=FakeTransport(default=wled(MAC_A)),
        opener=network.opener,
        clock=network.clock,
    )
    out, err = capsys.readouterr()
    assert out == "" and err == ""


def test_result_dictionary_is_json_serializable_and_complete():
    network = FakeNetwork(answer_first(device("a", "10.0.2.21")))
    result = run_discovery(
        ranges=["10.0.8.0/30"],
        transport=FakeTransport(default=wled(MAC_A)),
        opener=network.opener,
        clock=network.clock,
    )
    document = json.loads(json.dumps(result.as_dict()))
    assert set(document) == {"conclusion", "candidates", "coverage", "warnings"}
    coverage = document["coverage"]
    assert coverage["schema"] == 1 and coverage["conclusion"] == "candidates_found"
    assert {"methods", "mdns", "unicast", "known_devices_checked", "caps", "limits"} <= set(
        coverage
    )


# ------------------------------------------------------------------ slow responders


class BlockingConnection(FakeConnection):
    """``getresponse`` or ``read`` blocks until the transport closes the connection."""

    where = "headers"

    def __init__(self, host: str, port: int, timeout: float) -> None:
        super().__init__(host, port, timeout)
        self.released = threading.Event()

    def getresponse(self) -> Any:
        if self.where == "headers":
            self.released.wait(10)
            raise OSError("closed")
        connection = self

        class Drip(FakeResponse):
            def read(self, size: int) -> bytes:
                connection.released.wait(10)
                raise OSError("closed")

        return Drip(200, b"")

    def close(self) -> None:
        super().close()
        self.released.set()


@pytest.mark.parametrize("where", ["headers", "body"])
def test_a_responder_that_never_finishes_is_cut_off_at_the_per_request_bound(where):
    BlockingConnection.where = where
    transport = HttpTransport(connection_factory=BlockingConnection)
    started = time.monotonic()
    result = transport.get_info("10.0.0.5", 80, 0.1)
    assert result.kind == "timeout"
    assert time.monotonic() - started < 3


def test_stragglers_count_as_timed_out_and_the_run_does_not_wait_for_them():
    release = threading.Event()

    class Hung:
        def get_info(self, address: str, port: int, timeout: float) -> InfoResult:
            release.wait(30)
            return InfoResult("refused")

    started = time.monotonic()
    try:
        result = run_discovery(
            methods=("unicast",),
            ranges=["10.0.0.0/30"],
            transport=Hung(),
            timeout=0.2,
        )
        assert time.monotonic() - started < 5
    finally:
        release.set()
    row = result.coverage["unicast"]["ranges"][0]
    assert (row["hosts_probed"], row["timed_out"], row["not_probed"]) == (2, 2, 0)
    assert result.conclusion == "none_found_incomplete"
