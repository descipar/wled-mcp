"""``wled-mcp discover`` (issue #16, AC3, S16-T06) against an injected fake socket.

No test sends a datagram: an autouse guard fails on any real socket construction, and
every exchange goes through ``FakeNetwork``, which records each datagram and answers
from a script on a simulated clock. Answers use synthetic documentation addresses
(192.0.2.0/24) and invented MAC values.
"""

import ipaddress
import json
import os
import random
import re
import socket
import struct
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import pytest

from scripts import check_coverage
from wled_mcp import cli, discovery
from wled_mcp.discovery import MDNS_GROUP, MDNS_PORT, TYPE_A, TYPE_PTR, TYPE_SRV, TYPE_TXT

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


class FakeNetwork:
    """A simulated clock and multicast group; records every datagram sent."""

    def __init__(self, responder: Responder | None = None, fail_open: bool = False) -> None:
        self.now = 100.0
        self.sent: list[tuple[bytes, tuple[str, int]]] = []
        self.queue: list[tuple[float, bytes]] = []
        self.responder = responder or (lambda packet, number: [])
        self.fail_open = fail_open
        self.fail_send = False
        self.recv_errors = 0
        self.sockets: list[FakeSocket] = []

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
            return packet[:size], ("192.0.2.200", MDNS_PORT)
        net.now += self.timeout
        raise TimeoutError

    def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def no_real_sockets(monkeypatch):
    """Any real socket in this module is a test failure, multicast or not."""

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a real socket was opened")

    monkeypatch.setattr(socket, "socket", refuse)
    for env in list(os.environ):
        if env.startswith("WLED_MCP_"):
            monkeypatch.delenv(env)


def install(monkeypatch, network: FakeNetwork) -> FakeNetwork:
    monkeypatch.setattr(discovery, "open_multicast_socket", network.opener)
    monkeypatch.setattr(discovery, "monotonic", network.clock)
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


def test_first_query_is_one_ptr_question_for_the_wled_service(monkeypatch, capsys):
    network = install(monkeypatch, FakeNetwork())
    run(capsys)
    packet, address = network.sent[0]
    assert address == ("224.0.0.251", 5353)
    assert packet[:12] == struct.pack("!HHHHHH", 0, 0, 1, 0, 0, 0)
    # One PTR question, class IN with the unicast-response (QU) bit cleared.
    assert questions(packet) == [(("_wled", "_tcp", "local"), 12, 1)]


def test_candidate_with_suggested_url_and_add_device_command(monkeypatch, capsys, tmp_path):
    network = install(monkeypatch, FakeNetwork(answer_first(device("wled-a1b2c3", "192.0.2.21"))))
    before = sorted(tmp_path.rglob("*"))
    code, document = run_json(capsys)
    assert code == 0 and document["ok"] is True
    assert document["schema_version"] == 1 and document["command"] == "discover"
    assert document["follow_up_sent"] is False and document["queries_sent"] == 1
    (candidate,) = document["candidates"]
    assert candidate["instance"] == "wled-a1b2c3"
    assert candidate["mac"] == "00005e005301"
    assert candidate["addresses"] == ["192.0.2.21"]
    assert candidate["suggested_base_url"] == "http://192.0.2.21"
    assert candidate["alternative_base_url"] == "http://" + mdns("wled-a1b2c3")
    assert candidate["already_configured"] is False
    assert candidate["add_device_command"] == (
        "wled-mcp config add-device --config <CONFIG> --device-id wled-a1b2c3 "
        '--device-name "wled-a1b2c3" --base-url http://192.0.2.21'
    )
    assert_only_multicast(network)
    assert sorted(tmp_path.rglob("*")) == before


def test_text_output_lists_the_command_and_writes_nothing(monkeypatch, capsys):
    install(monkeypatch, FakeNetwork(answer_first(device("wled-a1b2c3", "192.0.2.21", port=8080))))
    code, out, err = run(capsys)
    assert code == 0 and err == ""
    assert "Suggested base URL: http://192.0.2.21:8080" in out
    assert "--base-url http://192.0.2.21:8080" in out
    assert "Replace <CONFIG>" in out and "Nothing was written" in out


def test_default_window_is_three_seconds_and_timeout_is_bounded(monkeypatch, capsys):
    network = install(monkeypatch, FakeNetwork())
    run(capsys)
    assert network.now == pytest.approx(103.0)
    network = install(monkeypatch, FakeNetwork())
    run(capsys, "--timeout", "10")
    assert network.now == pytest.approx(110.0)


@pytest.mark.parametrize("value", ["10.5", "0", "-1", "nan", "inf", "abc"])
def test_timeout_outside_the_bounds_is_a_usage_error(monkeypatch, capsys, value):
    network = install(monkeypatch, FakeNetwork())
    code, out, err = run(capsys, "--timeout", value)
    assert code == 2 and out == ""
    assert network.sockets == [] and network.sent == []
    assert err.startswith("Invalid command-line arguments")


def test_follow_up_asks_once_for_missing_records(monkeypatch, capsys):
    host = mdns("wled-a1b2c3")

    def responder(packet: bytes, number: int) -> list[tuple[float, bytes]]:
        if number == 1:
            return [(0.05, response([ptr("wled-a1b2c3")]))]
        asked = {qtype for _, qtype, _ in questions(packet)}
        assert asked == {TYPE_SRV, TYPE_TXT}
        return [
            (
                0.05,
                response(
                    [srv("wled-a1b2c3", host), txt("wled-a1b2c3", b"mac=00005e005301")],
                    [a(host, "192.0.2.21")],
                ),
            )
        ]

    network = install(monkeypatch, FakeNetwork(responder))
    code, document = run_json(capsys)
    assert code == 0 and document["follow_up_sent"] is True
    assert document["candidates"][0]["suggested_base_url"] == "http://192.0.2.21"
    assert_only_multicast(network)
    assert len(network.sent) == 2


def test_never_more_than_one_follow_up_even_without_answers(monkeypatch, capsys):
    host = mdns("wled-a1b2c3")
    # SRV without an A record: the follow-up asks for A, nobody answers, no third query.
    first = response([ptr("wled-a1b2c3")], [srv("wled-a1b2c3", host), txt("wled-a1b2c3")])
    network = install(monkeypatch, FakeNetwork(answer_first(first)))
    code, document = run_json(capsys, "--timeout", "10")
    assert len(network.sent) == 2
    assert questions(network.sent[1][0]) == [(("wled-a1b2c3", "local"), TYPE_A, 1)]
    assert_only_multicast(network)
    (candidate,) = document["candidates"]
    assert candidate["suggested_base_url"] is None and candidate["add_device_command"] is None
    assert code == 1 and document["problems"][0]["code"] == "NO_CANDIDATES"


def test_duplicates_are_merged_by_mac_then_by_address(monkeypatch, capsys):
    packets = [
        device("wled-a1b2c3", "192.0.2.21", mac="00005e005301"),
        device("living-room", "192.0.2.22", mac="00005E005301"),  # same controller
        device("wled-noma", "192.0.2.30", mac=None),
        device("wled-noma-2", "192.0.2.30", mac=None),  # same address, no MAC
        device("wled-other", "192.0.2.40", mac="00005e005302"),
    ]
    install(monkeypatch, FakeNetwork(answer_first(*packets)))
    code, document = run_json(capsys)
    assert code == 0 and document["candidate_count"] == 3
    by_mac = {c["mac"]: c for c in document["candidates"]}
    assert by_mac["00005e005301"]["addresses"] == ["192.0.2.21", "192.0.2.22"]
    assert by_mac["00005e005301"]["suggested_base_url"] == "http://192.0.2.21"
    assert by_mac[None]["addresses"] == ["192.0.2.30"]
    assert by_mac["00005e005302"]["addresses"] == ["192.0.2.40"]


def test_at_most_64_candidates(monkeypatch, capsys):
    packets = [
        device(f"wled-{index:06x}", f"192.0.2.{index + 1}", mac=f"00005e0053{index:02x}")
        for index in range(70)
    ]
    install(monkeypatch, FakeNetwork(answer_first(*packets, delay=0.001)))
    code, document = run_json(capsys)
    assert code == 0
    assert document["candidate_count"] == 64 and document["truncated"] is True
    ids = [c["suggested_device_id"] for c in document["candidates"]]
    assert len(set(ids)) == 64


def test_configured_devices_are_marked_and_the_inventory_is_not_written(
    monkeypatch, capsys, tmp_path
):
    config = tmp_path / "devices.toml"
    config.write_bytes(
        b"schema_version = 1\n\n[[devices]]\n"
        b'id = "wled-a1b2c3"\nname = "Desk"\nbase_url = "http://192.0.2.21"\n'
        + f'\n[[devices]]\nid = "shelf"\nname = "Shelf"\nbase_url = "http://{mdns("wled-0b0b0b")}"\n'.encode()
    )
    before = {p: p.read_bytes() for p in tmp_path.iterdir()}
    packets = [
        device("wled-a1b2c3", "192.0.2.21", mac="00005e005301"),
        device("wled-0b0b0b", "192.0.2.22", mac="00005e005303"),
        device("wled-a1b2c3x", "192.0.2.23", mac="00005e005304"),
    ]
    network = install(monkeypatch, FakeNetwork(answer_first(*packets)))
    code, document = run_json(capsys, "--config", str(config))
    assert code == 0
    marked = {c["addresses"][0]: c for c in document["candidates"]}
    assert marked["192.0.2.21"]["already_configured"] is True
    assert marked["192.0.2.21"]["add_device_command"] is None
    assert marked["192.0.2.22"]["already_configured"] is True  # matched by .local name
    fresh = marked["192.0.2.23"]
    assert fresh["already_configured"] is False
    assert fresh["suggested_device_id"] == "wled-a1b2c3x"
    assert {p: p.read_bytes() for p in tmp_path.iterdir()} == before
    assert str(tmp_path) not in json.dumps(document)
    assert_only_multicast(network)


def test_suggested_id_avoids_configured_ids(monkeypatch, capsys, tmp_path):
    config = tmp_path / "devices.toml"
    config.write_bytes(
        b'schema_version = 1\n\n[[devices]]\nid = "wled-a1b2c3"\nname = "Old"\n'
        b'base_url = "http://192.0.2.99"\n'
    )
    install(monkeypatch, FakeNetwork(answer_first(device("wled-a1b2c3", "192.0.2.21"))))
    _, document = run_json(capsys, "--config", str(config))
    assert document["candidates"][0]["suggested_device_id"] == "wled-a1b2c3-2"


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


def test_no_answer_reports_no_candidates_with_hints(monkeypatch, capsys):
    network = install(monkeypatch, FakeNetwork())
    code, document = run_json(capsys)
    assert code == 1 and document["candidates"] == []
    (problem,) = document["problems"]
    assert problem["code"] == "NO_CANDIDATES"
    assert all(word in problem["message"] for word in HINT_WORDS)
    assert len(network.sent) == 1  # nothing was missing, so no follow-up


def test_receive_errors_are_bounded(monkeypatch, capsys):
    network = FakeNetwork(answer_first(device("wled-a1b2c3", "192.0.2.21")))
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


@pytest.mark.parametrize("packet", MALFORMED.values(), ids=MALFORMED.keys())
def test_malformed_answers_are_dropped(packet):
    with pytest.raises(discovery.MalformedPacket):
        discovery.parse_response(packet)
    collector = discovery.Collector()
    collector.feed(packet)
    assert collector.malformed == 1 and collector.instances == {}


def test_malformed_answers_do_not_stop_valid_ones(monkeypatch, capsys):
    # The oversized datagram is left out: the receive buffer would cut it to a valid size.
    hostile = [p for key, p in MALFORMED.items() if key != "oversized datagram"]
    packets = [*hostile, device("wled-a1b2c3", "192.0.2.21")]
    install(monkeypatch, FakeNetwork(answer_first(*packets, delay=0.001)))
    code, document = run_json(capsys)
    assert code == 0 and document["candidate_count"] == 1
    assert document["malformed_responses"] == len(hostile)


def test_random_corruption_never_raises():
    valid = device("wled-a1b2c3", "192.0.2.21")
    generator = random.Random(16)
    for _ in range(3000):
        data = bytearray(valid)
        for _ in range(generator.randint(1, 6)):
            data[generator.randrange(len(data))] = generator.randrange(256)
        data = data[: generator.randint(0, len(data))]
        collector = discovery.Collector()
        collector.feed(bytes(data))  # never raises
        collector.missing_questions()
        discovery.assemble(collector)


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
        + a(mdns("wled-a1b2c3"), "192.0.2.21")
    )
    collector = discovery.Collector()
    collector.feed(packet)
    assert collector.malformed == 0
    (candidate,) = discovery.assemble(collector)
    assert candidate.mac == "00005e005301" and candidate.base_url == "http://192.0.2.21"


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
            record(label_name(host_labels), TYPE_A, bytes([192, 0, 2, 21])),
        ],
    )
    install(monkeypatch, FakeNetwork(answer_first(packet)))
    code, out, err = run(capsys)
    assert code == 0
    assert out.endswith("\n") and err == ""
    lines = out[:-1].split("\n")
    assert not any(CONTROL.search(line) for line in lines)
    assert lines[0] == '- wled?[31m??desk"$(x)`'  # one line, control characters replaced
    (command_line,) = [line for line in lines if "Add with:" in line]
    assert "$(" not in command_line and "`" not in command_line
    assert '--device-name "wled 31m desk x"' in command_line
    assert "Alternative:" not in out  # not an LDH host name, so no .local URL
    install(monkeypatch, FakeNetwork(answer_first(packet)))
    _, document = run_json(capsys)
    (candidate,) = document["candidates"]
    assert candidate["mac"] is None and candidate["alternative_base_url"] is None
    for value in (candidate["instance"], candidate["host"], candidate["suggested_device_name"]):
        assert not CONTROL.search(value)
    assert re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", candidate["suggested_device_id"])


@pytest.mark.parametrize("address", ["0.0.0.0", "127.0.0.1", "224.0.0.251", "255.255.255.255"])
def test_unusable_addresses_are_not_suggested(monkeypatch, capsys, address):
    install(monkeypatch, FakeNetwork(answer_first(device("wled-a1b2c3", address))))
    code, document = run_json(capsys)
    assert code == 1 and document["candidates"][0]["suggested_base_url"] is None


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


def test_discovery_is_never_used_outside_the_discover_command():
    package = ROOT / "src" / "wled_mcp"
    users = sorted(
        path.name
        for path in package.glob("*.py")
        if path.name != "discovery.py"
        and re.search(r"\bimport\b.*\bdiscovery\b|\bdiscovery\.", path.read_text(encoding="utf-8"))
    )
    assert users == ["cli.py"]
    source = (package / "cli.py").read_text(encoding="utf-8")
    assert source.count("discovery.") == 2  # register + the discover dispatch only
    assert "224.0.0.251" not in "".join(
        p.read_text(encoding="utf-8") for p in package.glob("*.py") if p.name != "discovery.py"
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
