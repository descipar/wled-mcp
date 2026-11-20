"""Issue #200: the MCP tool ``wled_discover_devices`` (DISC-01, DISC-03 to DISC-06,
DISC-11 to DISC-13; DISC-T02, DISC-T04, DISC-T05, DISC-T07 tool side).

Everything runs in process on fakes: the engine runner is replaced (tests/conftest.py makes
the real one refuse), mDNS is the simulated network of tests/test_discovery.py and
``GET /json/info`` is scripted. Addresses are synthetic and MACs are from the RFC 7042
documentation block. No real socket is opened.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import anyio
import pytest
from mcp.client import Client

from tests.discovery_support import FakeEngine, make_resources
from tests.http_support import running_service, sdk_client
from tests.test_discovery import FakeNetwork, answer_first, device
from tests.test_discovery_engine import MAC_A, MAC_B, FakeTransport, wled
from tests.tool_contract import EXPECTED_TOOLS, OPEN_WORLD_TOOLS
from wled_mcp import discovery_tools
from wled_mcp.config import Device
from wled_mcp.discovery_engine import DiscoveryRangeError
from wled_mcp.discovery_tools import PROBE_GAP_SECONDS, propose_ranges
from wled_mcp.operations import build_operations
from wled_mcp.resources import Resources
from wled_mcp.server import create_server

TOOL = "wled_discover_devices"


class StepClock:
    def __init__(self) -> None:
        self.now = 5000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock(monkeypatch) -> StepClock:
    fake = StepClock()
    monkeypatch.setattr(discovery_tools, "clock", fake)
    return fake


def install(monkeypatch, engine: FakeEngine) -> FakeEngine:
    monkeypatch.setattr(discovery_tools, "run_engine", engine)
    return engine


def set_ranges(monkeypatch, *ranges: str) -> None:
    monkeypatch.setattr(Resources, "discovery_ranges", property(lambda self: ranges))


def devices_of(*pairs: tuple[str, str]) -> list[Device]:
    return [Device(id=i, name=f"Example {i}", base_url=u) for i, u in pairs]


async def call(client: Client, arguments: dict[str, Any]) -> dict[str, Any]:
    result = await client.call_tool(TOOL, arguments)
    assert result.structured_content is not None
    assert result.is_error is (not result.structured_content["ok"])
    assert json.loads(result.content[0].text) == result.structured_content  # type: ignore[union-attr]
    return result.structured_content


def served(tmp_path, devices=(("desk", "http://desk.invalid"),), profile="full"):
    resources = make_resources(tmp_path, devices, profile)
    return create_server(build_operations(resources), resources.access), resources


async def execute(resources, **arguments: Any):
    operation = {op.name: op for op in build_operations(resources)}[TOOL]
    return await operation.execute(operation.request_model.model_validate(arguments).model_dump())


# --------------------------------------------------------------------------- contract


@pytest.mark.anyio
@pytest.mark.parametrize("profile", ["read-only", "control", "full"])
async def test_the_tool_is_served_in_every_profile_as_a_read_tool(tmp_path, profile):
    server, _ = served(tmp_path, profile=profile)
    async with Client(server) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
    tool = tools[TOOL]
    hints = tool.annotations
    assert (
        hints.read_only_hint,
        hints.destructive_hint,
        hints.idempotent_hint,
        hints.open_world_hint,
    ) == (True, False, True, True)
    assert OPEN_WORLD_TOOLS == {TOOL, "wled_add_device"}
    assert TOOL in [t.name for t in EXPECTED_TOOLS]
    assert set(tool.input_schema["properties"]) == {"methods", "timeout_seconds", "max_candidates"}
    assert tool.input_schema["additionalProperties"] is False


@pytest.mark.anyio
async def test_the_served_descriptor_is_identical_over_streamable_http(tmp_path):
    server, _ = served(tmp_path)
    async with Client(server) as client:
        local = next(t for t in (await client.list_tools()).tools if t.name == TOOL)
    async with running_service(tmp_path) as running, sdk_client(running) as client:
        remote = next(t for t in (await client.list_tools()).tools if t.name == TOOL)
    assert local.model_dump() == remote.model_dump()


# ------------------------------------------------------------------------- validation


@pytest.mark.anyio
@pytest.mark.parametrize(
    "arguments",
    [
        {"unknown": 1},
        {"timeout_seconds": 0},
        {"timeout_seconds": 31},
        {"max_candidates": 0},
        {"max_candidates": 65},
        {"methods": []},
        {"methods": ["mdns", "mdns"]},
        {"methods": ["ping"]},
        {"methods": ["mdns", "unicast", "mdns"]},
        {"ranges": ["10.0.1.0/24"]},
        {"cidr": "10.0.1.0/24"},
        {"host": "10.0.1.5"},
        {"timeout_seconds": "5"},
    ],
)
async def test_a_bad_request_is_rejected_before_anything_is_probed(
    tmp_path, monkeypatch, arguments
):
    engine = install(monkeypatch, FakeEngine())
    server, _ = served(tmp_path)
    async with Client(server) as client:
        envelope = await call(client, arguments)
    assert envelope["error"]["code"] == "VALIDATION_ERROR"
    assert envelope["application"] == "not_attempted"
    assert engine.calls == []


# --------------------------------------------------------------- result mapping, DISC-03


@pytest.mark.anyio
async def test_candidates_coverage_and_envelope_are_mapped_and_nothing_is_written(
    tmp_path, monkeypatch
):
    network = FakeNetwork(
        answer_first(device("living", "10.0.2.21", MAC_A), device("hall", "10.0.2.23", MAC_B))
    )
    transport = FakeTransport(
        {
            "10.0.2.21": wled(MAC_A, "Living"),
            "10.0.2.23": wled(MAC_B, "Hall"),
            "10.0.2.99": wled(MAC_B, "Hall"),  # the configured controller answers with its MAC
        }
    )
    engine = install(monkeypatch, FakeEngine(network, transport))
    server, resources = served(
        tmp_path, (("living", "http://10.0.2.21"), ("lamp", "http://10.0.2.99"))
    )
    before = sorted(str(p) for p in tmp_path.rglob("*"))
    async with Client(server) as client:
        envelope = await call(client, {"methods": ["mdns"], "timeout_seconds": 8})
    assert envelope["ok"] is True and envelope["device_id"] is None
    assert (envelope["application"], envelope["verification"]) == ("not_attempted", "not_requested")
    assert list(envelope["data"])[0] == "conclusion"  # first key, ISSUE-200-DEC-001
    data = envelope["data"]
    by_status = {c["status"]: c for c in data["candidates"]}
    assert set(by_status) == {"known", "address_changed"}
    assert by_status["known"]["known_device_id"] == "living"
    changed = by_status["address_changed"]
    assert (changed["known_device_id"], changed["configured_address"]) == ("lamp", "10.0.2.99")
    assert data["conclusion"] == data["coverage"]["conclusion"] == "candidates_found"
    assert data["coverage"]["complete"] is False  # unicast was not requested
    assert envelope["warnings"] == [] and "warnings" not in data
    assert engine.calls[0]["methods"] == ("mdns",) and engine.calls[0]["timeout"] == 8
    assert {k.id for k in engine.calls[0]["known"]} == {"living", "lamp"}
    assert transport.addresses <= {"10.0.2.21", "10.0.2.23", "10.0.2.99"}  # only known and found
    assert sorted(str(p) for p in tmp_path.rglob("*")) == before  # no file created or changed
    assert resources.inventory[0].base_url == "http://10.0.2.21"


@pytest.mark.anyio
async def test_a_suggested_id_never_repeats_an_inventory_id(tmp_path, monkeypatch):
    network = FakeNetwork(answer_first(device("living", "10.0.2.21", MAC_A)))
    install(monkeypatch, FakeEngine(network, FakeTransport({"10.0.2.21": wled(MAC_A, "Living")})))
    server, _ = served(tmp_path, (("living", "http://living.invalid"),))
    async with Client(server) as client:
        envelope = await call(client, {"methods": ["mdns"]})
    (candidate,) = envelope["data"]["candidates"]
    assert candidate["status"] == "new" and candidate["suggested_id"] != "living"


@pytest.mark.anyio
async def test_engine_warnings_are_carried_in_the_envelope_field_only(tmp_path, monkeypatch):
    pairs = [(f"n{n}", f"10.0.2.{20 + n}", f"00005e0053{n:02x}") for n in range(1, 4)]
    network = FakeNetwork(answer_first(*(device(i, a, m) for i, a, m in pairs)))
    transport = FakeTransport({a: wled(m, i) for i, a, m in pairs})
    install(monkeypatch, FakeEngine(network, transport))
    server, _ = served(tmp_path)
    async with Client(server) as client:
        envelope = await call(client, {"methods": ["mdns"], "max_candidates": 2})
    assert len(envelope["data"]["candidates"]) == 2
    assert envelope["warnings"] and "warnings" not in envelope["data"]
    assert envelope["data"]["coverage"]["methods"][0]["reason"] == "cap_reached"


# ------------------------------------------------- no configured ranges, DISC-06 / DISC-T04


@pytest.mark.anyio
async def test_without_ranges_only_mdns_runs_and_proposals_are_never_probed(tmp_path, monkeypatch):
    transport = FakeTransport()
    engine = install(monkeypatch, FakeEngine(FakeNetwork(), transport))
    server, _ = served(tmp_path, (("living", "http://10.0.2.21"), ("lamp", "http://10.0.2.22")))
    async with Client(server) as client:
        envelope = await call(client, {})
    data = envelope["data"]
    assert engine.calls[0]["ranges"] == ()
    unicast = next(m for m in data["coverage"]["methods"] if m["method"] == "unicast")
    assert (unicast["status"], unicast["reason"]) == ("skipped", "no_ranges_configured")
    assert data["coverage"]["complete"] is False
    assert data["conclusion"] == "none_found_incomplete" and data["candidates"] == []
    assert data["proposed_ranges"] == [
        {"cidr": "10.0.2.0/24", "derived_from_device_ids": ["living", "lamp"]}
    ]
    # Only the configured controllers are read; the proposed /24 is not swept.
    assert transport.addresses <= {"10.0.2.21", "10.0.2.22"}


@pytest.mark.anyio
async def test_unicast_only_without_ranges_is_not_looked_and_still_ok(tmp_path, monkeypatch):
    engine = install(monkeypatch, FakeEngine())
    server, _ = served(tmp_path, (("living", "http://10.0.2.21"),))
    async with Client(server) as client:
        envelope = await call(client, {"methods": ["unicast"]})
    assert envelope["ok"] is True
    assert envelope["data"]["conclusion"] == "not_looked"
    assert engine.calls[0]["ranges"] == ()
    assert envelope["data"]["proposed_ranges"][0]["cidr"] == "10.0.2.0/24"


@pytest.mark.anyio
async def test_configured_ranges_reach_the_engine_per_call_and_exclude_proposals(
    tmp_path, monkeypatch, clock
):
    transport = FakeTransport({"10.0.2.3": wled(MAC_A, "Shelf")})
    engine = install(monkeypatch, FakeEngine(FakeNetwork(), transport))
    server, _ = served(tmp_path, (("living", "http://10.0.2.21"), ("hall", "http://10.0.3.5")))
    set_ranges(monkeypatch, "10.0.2.0/29")
    async with Client(server) as client:
        envelope = await call(client, {"methods": ["unicast"]})
        set_ranges(monkeypatch, "10.0.2.0/30")  # a later call reads the seam again
        clock.now += PROBE_GAP_SECONDS
        await call(client, {"methods": ["unicast"], "timeout_seconds": 2})
    assert [c["ranges"] for c in engine.calls] == [("10.0.2.0/29",), ("10.0.2.0/30",)]
    data = envelope["data"]
    (candidate,) = data["candidates"]
    assert candidate["address"] == "10.0.2.3" and candidate["found_by"] == ["unicast"]
    assert [p["cidr"] for p in data["proposed_ranges"]] == ["10.0.3.0/24"]
    assert not any(a.startswith("10.0.3.") for a in transport.addresses - {"10.0.3.5"})


# ----------------------------------------------------------------- propose_ranges, T05


def test_proposals_merge_sort_exclude_configured_and_count_what_is_left_out():
    inventory = devices_of(
        ("a", "http://192.168.50.7"),
        ("b", "http://10.0.2.5"),
        ("c", "http://10.0.2.6"),
        ("d", "http://172.16.9.4"),
        ("e", "http://198.51.100.7"),
        ("f", "http://169.254.1.1"),
        ("g", "http://desk.invalid"),
        ("h", "http://shelf.invalid"),
        ("i", "http://10.0.5.5"),
    )
    proposals, omitted, unproposed = propose_ranges(inventory)
    assert [p["cidr"] for p in proposals] == [
        "10.0.2.0/24",
        "10.0.5.0/24",
        "172.16.9.0/24",
        "192.168.50.0/24",
    ]
    assert proposals[0]["derived_from_device_ids"] == ["b", "c"]
    assert omitted == 0
    assert unproposed == [
        {"reason": "host_not_ipv4_literal", "count": 2},
        {"reason": "not_private", "count": 2},
    ]
    configured = propose_ranges(inventory, ["10.0.2.0/24", "not a range"])
    assert [p["cidr"] for p in configured[0]] == ["10.0.5.0/24", "172.16.9.0/24", "192.168.50.0/24"]


def test_more_than_four_proposals_are_truncated_with_a_count():
    inventory = devices_of(*((f"d{n}", f"http://10.0.{n}.5") for n in range(1, 7)))
    proposals, omitted, unproposed = propose_ranges(inventory)
    assert [p["cidr"] for p in proposals] == [f"10.0.{n}.0/24" for n in range(1, 5)]
    assert (omitted, unproposed) == (2, [])


@pytest.mark.anyio
async def test_the_wrapper_reports_omitted_and_unproposed_in_the_coverage(tmp_path, monkeypatch):
    install(monkeypatch, FakeEngine())
    pairs = tuple((f"d{n}", f"http://10.0.{n}.5") for n in range(1, 7)) + (
        ("dns", "http://desk.invalid"),
    )
    server, _ = served(tmp_path, pairs)
    async with Client(server) as client:
        envelope = await call(client, {"methods": ["mdns"]})
    coverage = envelope["data"]["coverage"]
    assert coverage["proposed_ranges_omitted"] == 2
    assert coverage["unproposed_devices"] == [{"reason": "host_not_ipv4_literal", "count": 1}]
    assert len(envelope["data"]["proposed_ranges"]) == 4


# ------------------------------------------------------- single flight and probe gap


@pytest.mark.anyio
async def test_a_second_concurrent_call_fails_fast_and_probes_nothing(tmp_path, monkeypatch):
    engine = install(monkeypatch, FakeEngine())
    engine.release.clear()
    _, resources = served(tmp_path)
    results: list[Any] = []

    async def first() -> None:
        results.append(await execute(resources, methods=["mdns"]))

    async with anyio.create_task_group() as group:
        group.start_soon(first)
        assert await anyio.to_thread.run_sync(engine.started.wait, 10)
        busy = await execute(resources, methods=["mdns"])
        assert busy.ok is False and busy.error.code == "DISCOVERY_BUSY"
        assert busy.error.read_retryable is True and busy.application == "not_attempted"
        assert 1 <= busy.data["retry_after_seconds"] <= 30
        assert len(engine.calls) == 1
        engine.release.set()
    assert results[0].ok is True
    assert (await execute(resources, methods=["mdns"])).ok is True  # released after completion


@pytest.mark.anyio
async def test_the_guard_is_released_after_an_engine_failure(tmp_path, monkeypatch):
    install(monkeypatch, FakeEngine(raises=RuntimeError("boom")))
    _, resources = served(tmp_path)
    with pytest.raises(RuntimeError):
        await execute(resources)
    install(monkeypatch, FakeEngine())
    assert (await execute(resources, methods=["mdns"])).ok is True


@pytest.mark.anyio
async def test_a_cancelled_call_keeps_the_guard_until_the_worker_finishes(tmp_path, monkeypatch):
    engine = install(monkeypatch, FakeEngine())
    engine.release.clear()
    _, resources = served(tmp_path)
    scopes: list[anyio.CancelScope] = []

    async def first() -> None:
        with anyio.CancelScope() as scope:
            scopes.append(scope)
            await execute(resources, methods=["mdns"])

    async with anyio.create_task_group() as group:
        group.start_soon(first)
        assert await anyio.to_thread.run_sync(engine.started.wait, 10)
        scopes[0].cancel()
        busy = await execute(resources, methods=["mdns"])
        assert busy.error.code == "DISCOVERY_BUSY"  # the thread still runs
        engine.release.set()
    assert (await execute(resources, methods=["mdns"])).ok is True


@pytest.mark.anyio
async def test_probe_phases_keep_a_gap_but_mdns_only_runs_do_not(tmp_path, monkeypatch, clock):
    engine = install(monkeypatch, FakeEngine())
    set_ranges(monkeypatch, "10.0.2.0/29")
    _, resources = served(tmp_path)
    assert (await execute(resources, methods=["unicast"])).ok is True
    clock.now += 2.0
    refused = await execute(resources, methods=["unicast"])
    assert refused.error.code == "DISCOVERY_BUSY" and refused.data["retry_after_seconds"] == 3
    assert (await execute(resources, methods=["mdns"])).ok is True  # no gap for mDNS only
    assert len(engine.calls) == 2
    clock.now += PROBE_GAP_SECONDS
    assert (await execute(resources)).ok is True  # both methods: a probe phase again
    refused = await execute(resources)
    assert refused.error.code == "DISCOVERY_BUSY" and refused.data["retry_after_seconds"] == 5


@pytest.mark.anyio
async def test_a_run_without_ranges_is_not_a_probe_phase(tmp_path, monkeypatch, clock):
    install(monkeypatch, FakeEngine())
    _, resources = served(tmp_path)
    assert (await execute(resources)).ok is True
    assert (await execute(resources)).ok is True


# ------------------------------------------------------------------- errors and bounds


@pytest.mark.anyio
async def test_invalid_stored_ranges_are_a_config_error_without_a_value(tmp_path, monkeypatch):
    install(monkeypatch, FakeEngine(raises=DiscoveryRangeError("too_broad", 0)))
    set_ranges(monkeypatch, "10.0.0.0/8")
    server, _ = served(tmp_path)
    async with Client(server) as client:
        envelope = await call(client, {})
    assert (
        envelope["error"]["code"] == "CONFIG_ERROR" and envelope["application"] == "not_attempted"
    )
    assert "10.0.0.0" not in json.dumps(envelope)


@pytest.mark.anyio
async def test_bounds_are_passed_through_and_the_wrapper_raises_no_cap(tmp_path, monkeypatch):
    engine = install(monkeypatch, FakeEngine())
    server, _ = served(tmp_path)
    async with Client(server) as client:
        await call(client, {"methods": ["mdns"], "timeout_seconds": 1, "max_candidates": 1})
        await call(client, {"methods": ["mdns"], "timeout_seconds": 30, "max_candidates": 64})
        await call(client, {"methods": ["mdns"]})
    assert [(c["timeout"], c["max_candidates"]) for c in engine.calls] == [
        (1, 1),
        (30, 64),
        (None, None),
    ]


@pytest.mark.anyio
async def test_mdns_failure_is_reported_in_the_coverage_not_as_an_error(tmp_path, monkeypatch):
    install(monkeypatch, FakeEngine(FakeNetwork(fail_open=True)))
    server, _ = served(tmp_path)
    async with Client(server) as client:
        envelope = await call(client, {})
    assert envelope["ok"] is True and envelope["data"]["conclusion"] == "not_looked"
    mdns = next(m for m in envelope["data"]["coverage"]["methods"] if m["method"] == "mdns")
    assert (mdns["status"], mdns["reason"]) == ("failed", "multicast_unavailable")


# -------------------------------------------------------------------- transport, logging


@pytest.mark.anyio
async def test_stdio_style_and_streamable_http_return_the_same_envelope(tmp_path, monkeypatch):
    def fresh(**kwargs: Any):
        network = FakeNetwork(answer_first(device("living", "10.0.2.21", MAC_A)))
        transport = FakeTransport({"10.0.2.21": wled(MAC_A, "Living")})
        return FakeEngine(network, transport)(**kwargs)

    monkeypatch.setattr(discovery_tools, "run_engine", fresh)
    server, _ = served(
        tmp_path, (("desk", "http://desk.invalid"), ("shelf", "http://shelf.invalid"))
    )
    async with Client(server) as client:
        local = await call(client, {"methods": ["mdns"]})
    async with running_service(tmp_path) as running, sdk_client(running) as client:
        remote = await call(client, {"methods": ["mdns"]})
    for envelope in (local, remote):
        envelope.pop("correlation_id")
    assert local == remote and local["data"]["candidates"][0]["status"] == "new"


@pytest.mark.anyio
async def test_the_call_log_names_no_address_mac_or_range(tmp_path, monkeypatch, caplog):
    network = FakeNetwork(answer_first(device("living", "10.0.2.21", MAC_A)))
    install(monkeypatch, FakeEngine(network, FakeTransport({"10.0.2.21": wled(MAC_A, "Living")})))
    set_ranges(monkeypatch, "10.0.2.0/29")
    server, _ = served(tmp_path, (("desk", "http://10.0.2.99"),))
    with caplog.at_level(logging.DEBUG, logger="wled_mcp"):
        async with Client(server) as client:
            await call(client, {})
    text = "\n".join(r.getMessage() + repr(getattr(r, "call_fields", "")) for r in caplog.records)
    assert TOOL in text
    for secret in ("10.0.2", MAC_A, "00:00:5e"):
        assert secret not in text
