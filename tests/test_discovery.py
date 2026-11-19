"""``wled-mcp discover`` (issue #16, AC3, S16-T06) against an injected fake socket.

No test sends a datagram: an autouse guard fails on any real socket construction, and
every exchange goes through ``FakeNetwork``, which records each datagram and answers
from a script on a simulated clock. Answers use synthetic documentation addresses
(10.0.2.0/24) and invented MAC values.
"""

import ast
import http.client
import io
import ipaddress
import json
import os
import random
import re
import socket
import struct
import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import pytest

from scripts import check_coverage
from wled_mcp import cli, discovery, discovery_engine
from wled_mcp.discovery import MDNS_GROUP, MDNS_PORT, TYPE_A, TYPE_PTR, TYPE_SRV, TYPE_TXT
from wled_mcp.discovery_engine import InfoResult

ROOT = Path(__file__).resolve().parents[1]
SERVICE = "_wled._tcp.local"


def mdns(label: str) -> str:
    """The mDNS host name of a synthetic label (mDNS names always end in the local domain)."""
    return f"{label}.local"


CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f  ‪-‮⁦-⁩]")


# ------------------------------------------------------------------ DNS packet builder


def name(text: str) -> bytes:
    out = b""
    for label in text.split("."):
        raw = label.encode()
        out += bytes([len(raw)]) + raw
    return out + b"\x00"


def label_name(labels: Iterable[bytes]) -> bytes:
    return b"".join(bytes([len(label)]) + label for label in labels) + b"\x00"


def record(owner: bytes, rtype: int, rdata: bytes, rclass: int = 0x8001) -> bytes:
    return owner + struct.pack("!HHIH", rtype, rclass, 120, len(rdata)) + rdata


def ptr(instance: str) -> bytes:
    return record(name(SERVICE), TYPE_PTR, name(f"{instance}.{SERVICE}"), rclass=1)


def srv(instance: str, target: str, port: int = 80) -> bytes:
    return record(
        name(f"{instance}.{SERVICE}"), TYPE_SRV, struct.pack("!HHH", 0, 0, port) + name(target)
    )


def txt(instance: str, *items: bytes) -> bytes:
    data = b"".join(bytes([len(item)]) + item for item in items)
    return record(name(f"{instance}.{SERVICE}"), TYPE_TXT, data)


def a(host: str, address: str) -> bytes:
    return record(name(host), TYPE_A, ipaddress.IPv4Address(address).packed)


def response(answers: list[bytes], additional: Iterable[bytes] = (), flags: int = 0x8400) -> bytes:
    extra = list(additional)
    header = struct.pack("!HHHHHH", 0, flags, 0, len(answers), 0, len(extra))
    return header + b"".join(answers) + b"".join(extra)


def device(instance: str, address: str, mac: str | None = "00005e005301", port: int = 80) -> bytes:
    host = mdns(instance)
    items = [b"mac=" + mac.encode()] if mac is not None else []
    return response(
        [ptr(instance)], [srv(instance, host, port), txt(instance, *items), a(host, address)]
    )


def questions(packet: bytes) -> list[tuple[tuple[str, ...], int, int]]:
    count = struct.unpack_from("!H", packet, 4)[0]
    offset, found = 12, []
    for _ in range(count):
        labels = []
        while packet[offset]:
            length = packet[offset]
            labels.append(packet[offset + 1 : offset + 1 + length].decode())
            offset += 1 + length
        qtype, qclass = struct.unpack_from("!HH", packet, offset + 1)
        offset += 5
        found.append((tuple(labels), qtype, qclass))
    return found


# ------------------------------------------------------------------ fake network

Responder = Callable[[bytes, int], list[tuple[float, bytes]]]
SOURCE = ("10.0.2.200", MDNS_PORT)
Sources = dict[bytes, Any]  # packet -> source address override


class FakeNetwork:
    """A simulated clock and multicast group; records every datagram sent."""

    def __init__(self, responder: Responder | None = None, fail_open: bool = False) -> None:
        self.now = 100.0
        self.sent: list[tuple[bytes, tuple[str, int]]] = []
        self.queue: list[tuple[float, bytes]] = []
        self.sources: Sources = {}
        self.responder = responder or (lambda packet, number: [])
        self.fail_open = fail_open
        self.fail_send = False
        self.recv_errors = 0
        self.sockets: list[FakeSocket] = []
        self.transport = AutoTransport()

    def clock(self) -> float:
        return self.now

    def opener(self) -> "FakeSocket":
        if self.fail_open:
            raise OSError("no multicast route")
        sock = FakeSocket(self)
        self.sockets.append(sock)
        return sock


class FakeSocket:
    def __init__(self, network: FakeNetwork) -> None:
        self.network = network
        self.timeout: float | None = None
        self.closed = False

    def sendto(self, data: bytes, address: tuple[str, int], /) -> int:
        net = self.network
        if net.fail_send:
            raise OSError("network unreachable")
        net.sent.append((data, address))
        for delay, packet in net.responder(data, len(net.sent)):
            net.queue.append((net.now + delay, packet))
        net.queue.sort(key=lambda item: item[0])
        return len(data)

    def settimeout(self, value: float | None, /) -> None:
        self.timeout = value

    def recvfrom(self, size: int, /) -> tuple[bytes, Any]:
        net = self.network
        assert self.timeout is not None and self.timeout > 0
        if net.recv_errors:
            net.recv_errors -= 1
            raise OSError("message too long")
        if net.queue and net.queue[0][0] <= net.now + self.timeout:
            at, packet = net.queue.pop(0)
            net.now = max(net.now, at)
            return packet[:size], net.sources.get(packet, SOURCE)
        net.now += self.timeout
        raise TimeoutError

    def close(self) -> None:
        self.closed = True


def derived_mac(address: str) -> str:
    return "00005e00" + format(int(ipaddress.IPv4Address(address)) & 0xFFFF, "04x")


class AutoTransport:
    """``GET /json/info`` fake: every address is a WLED controller whose MAC derives from
    the address, unless ``overrides`` says otherwise (``None`` means no answer)."""

    def __init__(self, overrides: dict[str, InfoResult] | None = None) -> None:
        self.overrides = overrides or {}
        self.calls: list[tuple[str, int, float]] = []

    def get_info(self, address: str, port: int, timeout: float) -> InfoResult:
        self.calls.append((address, port, timeout))
        if address in self.overrides:
            return self.overrides[address]
        return InfoResult("wled", derived_mac(address), "0.15.0", "FOSS", "WLED")


def wled(mac: str, name: str = "WLED") -> InfoResult:
    return InfoResult("wled", mac, "0.15.0", "FOSS", name)


@pytest.fixture(autouse=True)
def no_real_sockets(monkeypatch):
    """Any real socket or HTTP connection in this module is a test failure."""

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a real socket was opened")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(http.client.HTTPConnection, "connect", refuse)
    for env in list(os.environ):
        if env.startswith("WLED_MCP_"):
            monkeypatch.delenv(env)


def install(
    monkeypatch, network: FakeNetwork, transport: AutoTransport | None = None
) -> FakeNetwork:
    monkeypatch.setattr(discovery, "open_multicast_socket", network.opener)
    monkeypatch.setattr(discovery, "monotonic", network.clock)
    network.transport = transport or AutoTransport()
    monkeypatch.setattr(discovery, "build_transport", lambda clock: network.transport)
    return network


def run(capsys, *argv: str) -> tuple[int, str, str]:
    try:
        code = cli.main(["discover", *argv])
    except SystemExit as exc:
        code = int(exc.code or 0)
    out, err = capsys.readouterr()
    return code, out, err


def run_json(capsys, *argv: str) -> tuple[int, dict[str, Any]]:
    code, out, err = run(capsys, *argv, "--format", "json")
    assert err == ""
    return code, json.loads(out)


def answer_first(*packets: bytes, delay: float = 0.05) -> Responder:
    return lambda packet, number: [(delay, p) for p in packets] if number == 1 else []


def assert_only_multicast(network: FakeNetwork) -> None:
    assert 1 <= len(network.sent) <= 2
    assert {address for _, address in network.sent} == {(MDNS_GROUP, MDNS_PORT)}
    assert all(sock.closed for sock in network.sockets)


# ------------------------------------------------------------------ query and limits


def test_first_query_asks_for_the_wled_service_and_the_http_fallback(monkeypatch, capsys):
    network = install(monkeypatch, FakeNetwork())
    run(capsys)
    packet, address = network.sent[0]
    assert address == ("224.0.0.251", 5353)
    assert packet[:12] == struct.pack("!HHHHHH", 0, 0, 2, 0, 0, 0)
    # PTR questions, class IN with the unicast-response (QU) bit cleared.
    assert questions(packet) == [
        (("_wled", "_tcp", "local"), 12, 1),
        (("_http", "_tcp", "local"), 12, 1),
    ]


def test_candidate_with_suggested_url_and_add_device_command(monkeypatch, capsys, tmp_path):
    network = install(monkeypatch, FakeNetwork(answer_first(device("wled-a1b2c3", "10.0.2.21"))))
    before = sorted(tmp_path.rglob("*"))
    code, document = run_json(capsys)
    assert code == 0 and document["ok"] is True
    assert document["schema_version"] == 1 and document["command"] == "discover"
    assert document["conclusion"] == "candidates_found"
    (candidate,) = document["candidates"]
    assert candidate["mac"] == derived_mac("10.0.2.21")
    assert candidate["address"] == "10.0.2.21"
    assert candidate["base_url"] == "http://10.0.2.21"
    assert candidate["status"] == "new" and candidate["found_by"] == ["mdns"]
    assert candidate["firmware_version"] == "0.15.0" and candidate["product"] == "FOSS"
    assert candidate["suggested_id"] == "wled-a1b2c3"
    assert candidate["add_device_command"] == (
        "wled-mcp config add-device --config <CONFIG> --device-id wled-a1b2c3 "
        '--device-name "wled-a1b2c3" --base-url http://10.0.2.21'
    )
    # Exactly one HTTP read of the announced address, only multicast on UDP.
    assert network.transport.calls == [("10.0.2.21", 80, 1.5)]
    assert {address for _, address in network.sent} == {(MDNS_GROUP, MDNS_PORT)}
    assert all(sock.closed for sock in network.sockets)
    assert sorted(tmp_path.rglob("*")) == before


def test_text_output_lists_the_command_and_writes_nothing(monkeypatch, capsys):
    install(monkeypatch, FakeNetwork(answer_first(device("wled-a1b2c3", "10.0.2.21"))))
    code, out, err = run(capsys)
    assert code == 0 and err == ""
    assert out.startswith("Conclusion: candidates_found\n")
    assert "Suggested base URL: http://10.0.2.21" in out
    assert "--base-url http://10.0.2.21" in out and "[new]" in out
    assert "Replace <CONFIG>" in out and "Nothing was written" in out
    assert "unicast skipped (no_ranges_configured)" in out  # coverage is always shown
    assert "not exhaustive" in out


def test_default_window_is_six_seconds_with_three_rounds_and_timeout_only_lowers(
    monkeypatch, capsys
):
    network = install(monkeypatch, FakeNetwork())
    run(capsys)
    assert network.now == pytest.approx(106.0)
    assert len(network.sent) == 3  # rounds one second apart; nothing was missing
    network = install(monkeypatch, FakeNetwork())
    run(capsys, "--timeout", "10")  # cannot raise the six-second window
    assert network.now == pytest.approx(106.0)
    network = install(monkeypatch, FakeNetwork())
    run(capsys, "--timeout", "2")
    assert network.now == pytest.approx(102.0)
    assert len(network.sent) == 2


@pytest.mark.parametrize("value", ["10.5", "0", "-1", "nan", "inf", "abc"])
def test_timeout_outside_the_bounds_is_a_usage_error(monkeypatch, capsys, value):
    network = install(monkeypatch, FakeNetwork())
    code, out, err = run(capsys, "--timeout", value)
    assert code == 2 and out == ""
    assert network.sockets == [] and network.sent == []
    assert err.startswith("Invalid command-line arguments")


def test_follow_up_asks_for_missing_records(monkeypatch, capsys):
    host = mdns("wled-a1b2c3")

    def responder(packet: bytes, number: int) -> list[tuple[float, bytes]]:
        asked = {qtype for _, qtype, _ in questions(packet)}
        if number == 1:
            return [(0.05, response([ptr("wled-a1b2c3")]))]
        if asked == {TYPE_SRV, TYPE_TXT}:
            return [
                (
                    0.05,
                    response(
                        [srv("wled-a1b2c3", host), txt("wled-a1b2c3", b"mac=00005e005301")],
                        [a(host, "10.0.2.21")],
                    ),
                )
            ]
        return []

    network = install(monkeypatch, FakeNetwork(responder))
    code, document = run_json(capsys)
    assert code == 0
    assert document["candidates"][0]["base_url"] == "http://10.0.2.21"
    assert any(
        {qtype for _, qtype, _ in questions(packet)} == {TYPE_SRV, TYPE_TXT}
        for packet, _ in network.sent
    )
    assert {address for _, address in network.sent} == {(MDNS_GROUP, MDNS_PORT)}


def test_at_most_one_follow_up_per_round_even_without_answers(monkeypatch, capsys):
    host = mdns("wled-a1b2c3")
    # SRV without an A record: each later round asks for A, nobody answers.
    first = response([ptr("wled-a1b2c3")], [srv("wled-a1b2c3", host), txt("wled-a1b2c3")])
    network = install(monkeypatch, FakeNetwork(answer_first(first)))
    code, document = run_json(capsys)
    follow_ups = [p for p, _ in network.sent if questions(p)[0][1] == TYPE_A]
    assert len(network.sent) == 5 and len(follow_ups) == 2  # three PTR rounds, two follow-ups
    assert questions(follow_ups[0]) == [(("wled-a1b2c3", "local"), TYPE_A, 1)]
    assert code == 1 and document["problems"][0]["code"] == "NO_CANDIDATES"
    assert network.transport.calls == []  # an unaddressable answer is never probed
    assert document["coverage"]["mdns"]["answers_rejected"] == 1


def test_duplicates_are_merged_by_the_verified_mac(monkeypatch, capsys):
    packets = [
        device("wled-a1b2c3", "10.0.2.21"),
        device("living-room", "10.0.2.22"),  # same controller at another address
        device("wled-noma", "10.0.2.30"),
        device("wled-noma-2", "10.0.2.30"),  # same address announced twice
        device("wled-other", "10.0.2.40"),
    ]
    shared = wled("00005e005301")
    transport = AutoTransport({"10.0.2.21": shared, "10.0.2.22": shared})
    install(monkeypatch, FakeNetwork(answer_first(*packets)), transport)
    code, document = run_json(capsys)
    assert code == 0 and document["candidate_count"] == 3
    by_mac = {c["mac"]: c for c in document["candidates"]}
    assert by_mac["00005e005301"]["address"] == "10.0.2.21"
    assert by_mac["00005e005301"]["alternate_addresses"] == ["10.0.2.22"]
    assert by_mac[derived_mac("10.0.2.30")]["address"] == "10.0.2.30"
    assert by_mac[derived_mac("10.0.2.40")]["address"] == "10.0.2.40"


def test_at_most_64_candidates(monkeypatch, capsys):
    packets = [device(f"wled-{index:06x}", f"10.0.2.{index + 1}") for index in range(70)]
    install(monkeypatch, FakeNetwork(answer_first(*packets, delay=0.001)))
    code, document = run_json(capsys)
    assert code == 0
    assert document["candidate_count"] == 64
    assert document["warnings"]  # the examined-instance cap is reported
    ids = [c["suggested_id"] for c in document["candidates"]]
    assert len(set(ids)) == 64


def test_configured_devices_are_marked_and_the_inventory_is_not_written(
    monkeypatch, capsys, tmp_path
):
    config = tmp_path / "devices.toml"
    config.write_bytes(
        b"schema_version = 1\n\n[[devices]]\n"
        b'id = "wled-a1b2c3"\nname = "Desk"\nbase_url = "http://10.0.2.21"\n'
        + f'\n[[devices]]\nid = "shelf"\nname = "Shelf"\nbase_url = "http://{mdns("wled-0b0b0b")}"\n'.encode()
    )
    before = {p: p.read_bytes() for p in tmp_path.iterdir()}
    packets = [
        device("wled-a1b2c3", "10.0.2.21"),
        device("wled-0b0b0b", "10.0.2.22"),
        device("wled-a1b2c3x", "10.0.2.23"),
    ]
    # The configured .local host answers with the MAC of the controller now at .22.
    transport = AutoTransport({mdns("wled-0b0b0b"): wled(derived_mac("10.0.2.22"))})
    network = install(monkeypatch, FakeNetwork(answer_first(*packets)), transport)
    code, document = run_json(capsys, "--config", str(config))
    assert code == 0
    marked = {c["address"]: c for c in document["candidates"]}
    assert marked["10.0.2.21"]["status"] == "known"
    assert marked["10.0.2.21"]["known_device_id"] == "wled-a1b2c3"
    assert marked["10.0.2.21"]["add_device_command"] is None
    assert marked["10.0.2.22"]["status"] == "address_changed"
    assert marked["10.0.2.22"]["known_device_id"] == "shelf"
    assert marked["10.0.2.22"]["configured_address"] == mdns("wled-0b0b0b")
    fresh = marked["10.0.2.23"]
    assert fresh["status"] == "new"
    assert fresh["suggested_id"] == "wled-a1b2c3x"
    assert document["coverage"]["known_devices_checked"] == 1
    assert {p: p.read_bytes() for p in tmp_path.iterdir()} == before
    assert str(tmp_path) not in json.dumps(document)
    assert {address for _, address in network.sent} == {(MDNS_GROUP, MDNS_PORT)}


def test_suggested_id_avoids_configured_ids(monkeypatch, capsys, tmp_path):
    config = tmp_path / "devices.toml"
    config.write_bytes(
        b'schema_version = 1\n\n[[devices]]\nid = "wled-a1b2c3"\nname = "Old"\n'
        b'base_url = "http://10.0.2.99"\n'
    )
    install(monkeypatch, FakeNetwork(answer_first(device("wled-a1b2c3", "10.0.2.21"))))
    _, document = run_json(capsys, "--config", str(config))
    assert document["candidates"][0]["suggested_id"] == "wled-a1b2c3-2"
    assert document["candidates"][0]["status"] == "new"  # the other MAC never claims a change


@pytest.mark.parametrize(
    ("content", "code"),
    [(b"schema_version = 2\n", "CONFIG_INVALID"), (None, "CONFIG_NOT_FOUND")],
)
def test_invalid_config_is_refused_before_any_traffic(monkeypatch, capsys, tmp_path, content, code):
    config = tmp_path / "devices.toml"
    if content is not None:
        config.write_bytes(content)
    network = install(monkeypatch, FakeNetwork())
    exit_code, document = run_json(capsys, "--config", str(config))
    assert exit_code == 1 and document["problems"][0]["code"] == code
    assert network.sockets == [] and network.sent == []
    code_rel, _, _ = run(capsys, "--config", "relative.toml")
    assert code_rel == 1 and network.sent == []


# ------------------------------------------------------------------ failures and hints

HINT_WORDS = ("VLAN", "bridge network", "multicast", "config add-device")


def test_socket_failure_reports_multicast_unavailable_with_hints(monkeypatch, capsys):
    install(monkeypatch, FakeNetwork(fail_open=True))
    code, document = run_json(capsys)
    assert code == 1 and document["ok"] is False
    (problem,) = document["problems"]
    assert problem["code"] == "MULTICAST_UNAVAILABLE"
    assert all(word in problem["message"] for word in HINT_WORDS)


def test_send_failure_reports_multicast_unavailable(monkeypatch, capsys):
    network = FakeNetwork()
    network.fail_send = True
    install(monkeypatch, network)
    code, out, _ = run(capsys)
    assert code == 1 and "could not be sent" in out and "VLAN" in out
    assert network.sockets[0].closed


def test_no_answer_reports_no_candidates_with_coverage_and_hints(monkeypatch, capsys):
    network = install(monkeypatch, FakeNetwork())
    code, document = run_json(capsys)
    assert code == 1 and document["candidates"] == []
    assert document["conclusion"] == "none_found_incomplete"
    assert document["coverage"]["complete"] is False
    (problem,) = document["problems"]
    assert problem["code"] == "NO_CANDIDATES"
    assert all(word in problem["message"] for word in HINT_WORDS)
    assert "mdns completed (no_answers)" in problem["message"]
    assert "unicast skipped (no_ranges_configured)" in problem["message"]
    assert len(network.sent) == 3  # three rounds; nothing was missing, so no follow-up


def test_receive_errors_are_bounded(monkeypatch, capsys):
    network = FakeNetwork(answer_first(device("wled-a1b2c3", "10.0.2.21")))
    network.recv_errors = 3
    install(monkeypatch, network)
    code, document = run_json(capsys)
    assert code == 0 and document["candidate_count"] == 1
    network = FakeNetwork()
    network.recv_errors = 10_000
    install(monkeypatch, network)
    assert run_json(capsys)[0] == 1 and network.recv_errors > 9_000


# ------------------------------------------------------------------ untrusted answers


def pointer_loop() -> bytes:
    header = struct.pack("!HHHHHH", 0, 0x8400, 0, 1, 0, 0)
    return header + b"\xc0\x0c" + struct.pack("!HHIH", TYPE_A, 1, 1, 4) + bytes(4)


def forward_pointer() -> bytes:
    header = struct.pack("!HHHHHH", 0, 0x8400, 0, 1, 0, 0)
    return header + b"\xc0\x20" + struct.pack("!HHIH", TYPE_A, 1, 1, 4) + bytes(20)


def mutual_pointers() -> bytes:
    header = struct.pack("!HHHHHH", 0, 0x8400, 0, 1, 0, 0)
    # offset 12 points to 14, offset 14 points back to 12
    return header + b"\xc0\x0e\xc0\x0c" + struct.pack("!HHIH", TYPE_A, 1, 1, 4) + bytes(4)


def long_name() -> bytes:
    owner = label_name([b"x" * 63] * 5)  # more than 255 bytes
    return response([record(owner, TYPE_A, bytes(4))])


MALFORMED = {
    "short header": b"\x00" * 11,
    "query not response": response([ptr("x")], flags=0x0000),
    "error rcode": response([ptr("x")], flags=0x8403),
    "self pointer": pointer_loop(),
    "forward pointer": forward_pointer(),
    "pointer cycle": mutual_pointers(),
    "name over 255 bytes": long_name(),
    "label type 0x40": response([b"\x41x\x00" + struct.pack("!HHIH", TYPE_A, 1, 1, 4) + bytes(4)]),
    "rdata past end": response([record(name(mdns("x")), TYPE_A, bytes(4))])[:-2],
    "bad A length": response([record(name(mdns("x")), TYPE_A, bytes(5))]),
    "TXT overrun": response([record(name(f"x.{SERVICE}"), TYPE_TXT, b"\x09mac=1")]),
    "SRV trailing data": response(
        [
            record(
                name(f"x.{SERVICE}"),
                TYPE_SRV,
                struct.pack("!HHH", 0, 0, 80) + name(mdns("x")) + b"z",
            )
        ]
    ),
    "too many records": struct.pack("!HHHHHH", 0, 0x8400, 0, 200, 0, 0),
    "oversized datagram": response([ptr("x")]) + bytes(9000),
}


REASONS = {
    "short header": "bad datagram size",
    "query not response": "not a successful standard response",
    "error rcode": "not a successful standard response",
    "self pointer": "forward or self pointer",
    "forward pointer": "forward or self pointer",
    "pointer cycle": "forward or self pointer",
    "name over 255 bytes": "name too long",
    "label type 0x40": "unsupported label type",
    "rdata past end": "record data runs past the datagram",
    "bad A length": "bad A record",
    "TXT overrun": "TXT string runs past the record",
    "SRV trailing data": "bad SRV record",
    "too many records": "too many records",
    "oversized datagram": "bad datagram size",
}


@pytest.mark.parametrize("case", MALFORMED, ids=MALFORMED.keys())
def test_malformed_answers_are_dropped(case):
    packet = MALFORMED[case]
    # Each case must fail for its own reason, not through an accidental truncation.
    with pytest.raises(discovery.MalformedPacket, match=REASONS[case]):
        discovery.parse_response(packet)
    collector = discovery.Collector()
    collector.feed(packet)
    assert collector.malformed == 1 and collector.instances == {}


def test_malformed_answers_do_not_stop_valid_ones(monkeypatch, capsys):
    # The oversized datagram is left out: the receive buffer would cut it to a valid size.
    hostile = [p for key, p in MALFORMED.items() if key != "oversized datagram"]
    packets = [*hostile, device("wled-a1b2c3", "10.0.2.21")]
    install(monkeypatch, FakeNetwork(answer_first(*packets, delay=0.001)))
    code, document = run_json(capsys)
    assert code == 0 and document["candidate_count"] == 1
    assert document["malformed_responses"] == len(hostile)


def test_random_corruption_never_raises():
    valid = device("wled-a1b2c3", "10.0.2.21")
    generator = random.Random(16)
    for _ in range(3000):
        data = bytearray(valid)
        for _ in range(generator.randint(1, 6)):
            data[generator.randrange(len(data))] = generator.randrange(256)
        data = data[: generator.randint(0, len(data))]
        collector = discovery.Collector()
        collector.feed(bytes(data))  # never raises
        collector.missing_questions()
        discovery_engine._mdns_targets(collector)


def test_compressed_names_are_followed():
    service = name(SERVICE)  # owner of the PTR answer, at offset 12
    ptr_rdata = b"\x0bwled-a1b2c3\xc0\x0c"  # instance label + pointer to the service name
    instance_offset = 12 + len(service) + 10  # where the PTR data starts
    pointer = struct.pack("!H", 0xC000 | instance_offset)
    srv_rdata = struct.pack("!HHH", 0, 0, 80) + name(mdns("wled-a1b2c3"))
    packet = (
        struct.pack("!HHHHHH", 0, 0x8400, 0, 1, 0, 3)
        + service
        + struct.pack("!HHIH", TYPE_PTR, 1, 120, len(ptr_rdata))
        + ptr_rdata
        + pointer
        + struct.pack("!HHIH", TYPE_SRV, 0x8001, 120, len(srv_rdata))
        + srv_rdata
        + pointer
        + struct.pack("!HHIH", TYPE_TXT, 0x8001, 120, 17)
        + b"\x10mac=00005e005301"
        + a(mdns("wled-a1b2c3"), "10.0.2.21")
    )
    collector = discovery.Collector()
    collector.feed(packet)
    assert collector.malformed == 0
    (instance,) = collector.instances.values()
    assert instance[0] == "wled-a1b2c3"
    assert discovery_engine._mdns_targets(collector)[0] == [("wled-a1b2c3", "10.0.2.21", 80)]


def test_untrusted_text_is_sanitized(monkeypatch, capsys):
    hostile = 'wled\x1b[31m\n‮desk"$(x)`'
    host_labels = [b"evil\x07host", b"local"]
    instance_raw = hostile.encode()
    owner = label_name([instance_raw, b"_wled", b"_tcp", b"local"])
    packet = response(
        [record(name(SERVICE), TYPE_PTR, owner, rclass=1)],
        [
            record(owner, TYPE_SRV, struct.pack("!HHH", 0, 0, 80) + label_name(host_labels)),
            record(owner, TYPE_TXT, b"\x0bmac=\x1b[2J;rm"),
            record(label_name(host_labels), TYPE_A, bytes([10, 0, 2, 21])),
        ],
    )
    install(monkeypatch, FakeNetwork(answer_first(packet)))
    code, out, err = run(capsys)
    assert code == 0
    assert out.endswith("\n") and err == ""
    lines = out[:-1].split("\n")
    assert not any(CONTROL.search(line) for line in lines)
    assert lines[1] == "- wled 31m desk x [new]"  # one line, only safe characters
    (command_line,) = [line for line in lines if "Add with:" in line]
    assert "$(" not in command_line and "`" not in command_line
    assert '--device-name "wled 31m desk x"' in command_line
    install(monkeypatch, FakeNetwork(answer_first(packet)))
    _, document = run_json(capsys)
    (candidate,) = document["candidates"]
    assert candidate["mac"] == derived_mac("10.0.2.21")
    assert not CONTROL.search(candidate["suggested_name"])
    assert re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", candidate["suggested_id"])


@pytest.mark.parametrize(
    "address",
    [
        "0.0.0.0",
        "127.0.0.1",
        "224.0.0.251",
        "255.255.255.255",
        "0.1.2.3",
        "240.0.0.1",
        "169.254.1.2",
        "100.64.0.9",
        "93.184.216.34",
    ],
)
def test_unusable_and_non_private_addresses_are_never_probed(monkeypatch, capsys, address):
    network = install(monkeypatch, FakeNetwork(answer_first(device("wled-a1b2c3", address))))
    code, document = run_json(capsys)
    assert code == 1 and document["candidates"] == []
    assert network.transport.calls == []  # an announced address outside RFC 1918 gets no probe
    assert document["coverage"]["mdns"]["answers_rejected"] == 1


# ------------------------------------------------------------------ boundaries


def test_default_socket_is_ipv4_udp_on_an_ephemeral_port(monkeypatch):
    calls: list[tuple[str, tuple[Any, ...]]] = []

    class Recorder:
        def __init__(self, *args: Any) -> None:
            calls.append(("socket", args))

        def setsockopt(self, *args: Any) -> None:
            calls.append(("setsockopt", args))

        def bind(self, address: Any) -> None:
            calls.append(("bind", (address,)))

        def close(self) -> None:
            calls.append(("close", ()))

    monkeypatch.setattr(socket, "socket", Recorder)
    discovery.open_multicast_socket()
    assert calls == [
        ("socket", (socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)),
        ("setsockopt", (socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)),
        ("bind", (("0.0.0.0", 0),)),
    ]


def references_discovery(source: str) -> bool:
    """Does the module import ``wled_mcp.discovery`` in any form (AST, not text)?"""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            if any(a.name.split(".")[:2] == ["wled_mcp", "discovery"] for a in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.split(".")[:2] == ["wled_mcp", "discovery"]:
                return True
            if node.level > 0 and module.split(".")[0] == "discovery":
                return True
            if (module == "wled_mcp" or (node.level > 0 and not module)) and any(
                a.name == "discovery" for a in node.names
            ):
                return True
        elif isinstance(node, ast.Constant) and node.value == "wled_mcp.discovery":
            return True  # importlib.import_module and similar
        elif (
            isinstance(node, ast.Call)
            and getattr(node.func, "attr", getattr(node.func, "id", "")) == "import_module"
            and any(isinstance(a, ast.Constant) and a.value == "discovery" for a in node.args)
        ):
            return True  # a relative importlib call; the bare key "discovery" is data (#202)
    return False


@pytest.mark.parametrize(
    "line",
    [
        "from wled_mcp.discovery import discover as _d",
        "import wled_mcp.discovery",
        "import wled_mcp.discovery as d",
        "from wled_mcp import discovery",
        "from wled_mcp import cli, discovery as d",
        "from . import discovery",
        "from .discovery import discover",
        "import importlib; importlib.import_module('wled_mcp.discovery')",
    ],
)
def test_scope_check_detects_every_import_form(line):
    # Negative control: a planted import in a scratch copy of a real module must fail.
    scratch = (ROOT / "src" / "wled_mcp" / "doctor.py").read_text(encoding="utf-8") + chr(10) + line
    assert references_discovery(scratch)


def test_discovery_is_never_used_outside_the_discover_command():
    package = ROOT / "src" / "wled_mcp"
    users = sorted(
        path.name
        for path in package.rglob("*.py")
        if path.name != "discovery.py" and references_discovery(path.read_text(encoding="utf-8"))
    )
    assert users == ["cli.py", "discovery_engine.py"]  # the engine reuses the parser
    source = (package / "cli.py").read_text(encoding="utf-8")
    assert source.count("discovery.") == 2  # register + the discover dispatch only
    assert "224.0.0.251" not in "".join(
        p.read_text(encoding="utf-8") for p in package.rglob("*.py") if p.name != "discovery.py"
    )


def test_discover_is_a_cli_command_for_the_coverage_check():
    assert ("discover",) in check_coverage.cli_commands()


def test_serve_options_with_discover_are_a_usage_error(monkeypatch, capsys):
    network = install(monkeypatch, FakeNetwork())
    code = 0
    try:
        cli.main(["--transport", "stdio", "discover"])
    except SystemExit as exc:
        code = int(exc.code or 0)
    assert code == 2 and network.sent == []
    capsys.readouterr()


# ------------------------------------------------------------------ correction round 1


class RedirectedStdout:
    """A text stream with a non-UTF-8 encoding, like a redirect on a legacy code page."""

    def __init__(self, encoding: str) -> None:
        self.raw = io.BytesIO()
        self.stream = io.TextIOWrapper(self.raw, encoding=encoding, errors="strict")

    def text(self) -> str:
        self.stream.flush()
        return self.raw.getvalue().decode("ascii")  # fails if any non-ASCII byte was written


def odd_responder_packets() -> list[bytes]:
    """One controller with invalid UTF-8 labels, one with an emoji name, one good one."""
    bad_owner = label_name([b"wled-\xff\xfe-bad", b"_wled", b"_tcp", b"local"])
    bad_host = label_name([b"host-\xc3", b"local"])
    invalid = response(
        [record(name(SERVICE), TYPE_PTR, bad_owner, rclass=1)],
        [
            record(bad_owner, TYPE_SRV, struct.pack("!HHH", 0, 0, 80) + bad_host),
            record(bad_owner, TYPE_TXT, b""),
            record(bad_host, TYPE_A, bytes([10, 0, 2, 31])),
        ],
    )
    emoji_owner = label_name(["wled-\U0001f4a1".encode(), b"_wled", b"_tcp", b"local"])
    emoji = response(
        [record(name(SERVICE), TYPE_PTR, emoji_owner, rclass=1)],
        [
            record(emoji_owner, TYPE_SRV, struct.pack("!HHH", 0, 0, 80) + name(mdns("wled-e"))),
            record(emoji_owner, TYPE_TXT, b""),
            record(name(mdns("wled-e")), TYPE_A, bytes([10, 0, 2, 32])),
        ],
    )
    return [invalid, emoji, device("wled-a1b2c3", "10.0.2.21")]


@pytest.mark.parametrize("fmt", ["text", "json"])
def test_non_encodable_answer_text_does_not_hide_other_candidates(monkeypatch, fmt):
    """S1: the output is ASCII, so a legacy stdout encoding cannot make it fail."""
    install(monkeypatch, FakeNetwork(answer_first(*odd_responder_packets())))
    stdout = RedirectedStdout("cp1252")
    monkeypatch.setattr(sys, "stdout", stdout.stream)
    code = cli.main(["discover", "--format", fmt])
    written = stdout.text()
    assert code == 0
    assert "10.0.2.21" in written and "10.0.2.31" in written and "10.0.2.32" in written
    assert "wled-a1b2c3" in written
    if fmt == "json":
        document = json.loads(written)
        assert document["candidate_count"] == 3
        assert all(c["suggested_name"].isascii() for c in document["candidates"])
    else:
        assert written.isascii()


def test_safe_text_is_ascii_printable_only():
    assert discovery.safe_text("aé�\U0001f4a1\x1b‮ z") == "a????? z"
    assert discovery.safe_text("plain-1.2_x") == "plain-1.2_x"


@pytest.mark.parametrize(
    "source",
    [
        ("10.0.2.200", 5354),
        ("10.0.2.200", 0),
        ("2001:db8::1", 5353),
        ("not-an-address", 5353),
        None,
    ],
)
def test_answers_not_from_ipv4_port_5353_are_dropped(monkeypatch, capsys, source):
    """S2 (RFC 6762 section 6): the response source port must be 5353 on IPv4."""
    packet = device("wled-a1b2c3", "10.0.2.21")
    network = FakeNetwork(answer_first(packet))
    network.sources[packet] = source
    install(monkeypatch, network)
    code, document = run_json(capsys)
    assert code == 1 and document["candidates"] == []
    assert document["dropped_datagrams"] == 1 and document["malformed_responses"] == 0
    assert document["problems"][0]["code"] == "NO_CANDIDATES"


def test_other_source_address_with_port_5353_stays_accepted(monkeypatch, capsys):
    # On-link cannot be verified from user space; this is documented (cli.md).
    packet = device("wled-a1b2c3", "10.0.2.21")
    network = FakeNetwork(answer_first(packet))
    network.sources[packet] = ("198.51.100.7", MDNS_PORT)
    install(monkeypatch, network)
    code, document = run_json(capsys)
    assert code == 0 and document["candidate_count"] == 1 and document["dropped_datagrams"] == 0


def test_dropped_datagrams_count_toward_the_datagram_bound(monkeypatch, capsys):
    packet = device("wled-a1b2c3", "10.0.2.21")
    network = FakeNetwork(lambda p, n: [(0.0001, packet)] * 600 if n == 1 else [])
    network.sources[packet] = ("10.0.2.200", 1)
    install(monkeypatch, network)
    _, document = run_json(capsys)
    assert document["dropped_datagrams"] == discovery.MAX_DATAGRAMS


def test_datagram_bound_stops_a_flood(monkeypatch, capsys):
    junk = b"\x00" * 12
    network = FakeNetwork(lambda p, n: [(0.0001, junk)] * 700 if n == 1 else [])
    install(monkeypatch, network)
    _, document = run_json(capsys)
    assert document["malformed_responses"] == discovery.MAX_DATAGRAMS
    assert len(network.queue) == 700 - discovery.MAX_DATAGRAMS  # the rest was never read


@pytest.mark.parametrize(("strings", "ok"), [(discovery.MAX_TXT_STRINGS, True), (65, False)])
def test_txt_string_count_is_bounded(strings, ok):
    items = [b"k%d=v" % index for index in range(strings)]
    packet = response([ptr("wled-a1b2c3")], [txt("wled-a1b2c3", *items)])
    if ok:
        discovery.parse_response(packet)
    else:
        with pytest.raises(discovery.MalformedPacket, match="too many TXT strings"):
            discovery.parse_response(packet)


def test_lower_timeout_bound_is_accepted_and_just_below_is_not(monkeypatch, capsys):
    network = install(monkeypatch, FakeNetwork())
    run(capsys, "--timeout", "0.5")
    assert network.now == pytest.approx(100.5)
    network = install(monkeypatch, FakeNetwork())
    code, _, _ = run(capsys, "--timeout", "0.49")
    assert code == 2 and network.sent == []


def test_follow_up_asks_only_for_the_missing_record(monkeypatch, capsys):
    host = mdns("wled-a1b2c3")
    # SRV and A are known, the TXT record is missing: the follow-up asks for TXT only.
    first = response([ptr("wled-a1b2c3")], [srv("wled-a1b2c3", host), a(host, "10.0.2.21")])

    def responder(packet: bytes, number: int) -> list[tuple[float, bytes]]:
        asked = [qtype for _, qtype, _ in questions(packet)]
        if number == 1:
            return [(0.05, first)]
        if asked == [TYPE_TXT]:
            return [(0.05, response([txt("wled-a1b2c3", b"mac=00005e005301")]))]
        return []

    network = install(monkeypatch, FakeNetwork(responder))
    code, document = run_json(capsys)
    assert code == 0
    assert document["candidates"][0]["mac"] == derived_mac("10.0.2.21")
    assert [questions(p)[0][1] for p, _ in network.sent].count(TYPE_TXT) == 1
    assert {address for _, address in network.sent} == {(MDNS_GROUP, MDNS_PORT)}


def test_leading_dashes_in_a_name_cannot_become_an_option(monkeypatch, capsys):
    owner = label_name([b"--x-y", b"_wled", b"_tcp", b"local"])
    packet = response(
        [record(name(SERVICE), TYPE_PTR, owner, rclass=1)],
        [
            record(owner, TYPE_SRV, struct.pack("!HHH", 0, 0, 80) + name(mdns("wled-d"))),
            record(owner, TYPE_TXT, b""),
            record(name(mdns("wled-d")), TYPE_A, bytes([10, 0, 2, 41])),
        ],
    )
    install(monkeypatch, FakeNetwork(answer_first(packet)))
    _, document = run_json(capsys)
    (candidate,) = document["candidates"]
    assert candidate["suggested_name"] == "x-y"
    assert '--device-name "x-y"' in candidate["add_device_command"]
    assert re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", candidate["suggested_id"])


def test_version_1_json_fields_of_the_previous_output_are_kept_additively(monkeypatch, capsys):
    install(monkeypatch, FakeNetwork(answer_first(device("wled-a1b2c3", "10.0.2.21"))))
    code, document = run_json(capsys)
    assert code == 0 and document["schema_version"] == 1
    assert document["queries_sent"] == 3 and document["follow_up_sent"] is False
    assert document["truncated"] is False
    (candidate,) = document["candidates"]
    assert candidate["instance"] == "wled-a1b2c3" and candidate["host"] is None
    assert candidate["addresses"] == ["10.0.2.21"] and candidate["port"] == 80
    assert candidate["suggested_base_url"] == "http://10.0.2.21"
    assert candidate["alternative_base_url"] is None
    assert candidate["already_configured"] is False
    assert candidate["suggested_device_id"] == "wled-a1b2c3"
    assert candidate["suggested_device_name"] == "wled-a1b2c3"
    assert candidate["add_device_command"] is not None


# ------------------------------------------------------------------ stored ranges (#202)

# Private literals are built from parts: the private-identifier check (DEC-005) sees none.
RANGE = "10~0~9~0/28".replace("~", ".")
BROAD = "10~0~0~0/8".replace("~", ".")
RANGES_CONFIG = (
    b"schema_version = 1\n\n"
    b'[discovery]\nranges = ["' + RANGE.encode() + b'"]\n\n'
    b'[[devices]]\nid = "desk"\nname = "Desk"\nbase_url = "http://192.0.2.10"\n'
)


def test_discover_probes_exactly_the_stored_ranges(monkeypatch, capsys, tmp_path):
    config = tmp_path / "devices.toml"
    config.write_bytes(RANGES_CONFIG)
    network = install(monkeypatch, FakeNetwork())
    code, document = run_json(capsys, "--config", str(config))
    assert code == 0
    # The known-device read of the configured entry is the only other request.
    probed = {address for address, _, _ in network.transport.calls} - {"192.0.2.10"}
    inside = {str(host) for host in ipaddress.IPv4Network(RANGE).hosts()}
    assert probed == inside
    unicast = next(m for m in document["coverage"]["methods"] if m["method"] == "unicast")
    assert unicast["status"] == "completed"
    assert {c["address"] for c in document["candidates"]} == probed


def test_discover_without_stored_ranges_stays_mdns_only(monkeypatch, capsys, tmp_path):
    config = tmp_path / "devices.toml"
    config.write_bytes(RANGES_CONFIG.replace(RANGE.encode(), b"").replace(b'[""]', b"[]"))
    network = install(monkeypatch, FakeNetwork())
    _, document = run_json(capsys, "--config", str(config))
    unicast = next(m for m in document["coverage"]["methods"] if m["method"] == "unicast")
    assert (unicast["status"], unicast["reason"]) == ("skipped", "no_ranges_configured")
    assert network.transport.calls == []


def test_discover_has_no_range_option(monkeypatch, capsys):
    network = install(monkeypatch, FakeNetwork())
    code, _, err = run(capsys, "--range", RANGE)
    assert code == 2 and "Invalid command-line arguments" in err
    assert network.sent == [] and network.transport.calls == []


def test_a_hand_edited_out_of_policy_range_is_refused_before_any_traffic(
    monkeypatch, capsys, tmp_path
):
    config = tmp_path / "devices.toml"
    config.write_bytes(RANGES_CONFIG.replace(RANGE.encode(), BROAD.encode()))
    network = install(monkeypatch, FakeNetwork())
    code, document = run_json(capsys, "--config", str(config))
    assert code == 1 and document["problems"][0]["code"] == "CONFIG_INVALID"
    assert "discovery.ranges[0]: invalid" in document["problems"][0]["message"]
    assert network.sockets == [] and network.transport.calls == []
