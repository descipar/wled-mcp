"""S3-EXPLAIN-01/-02 (#30): read-only, evidence-separated explanation of ineffective changes.

Mock fleet only; no LAN device. Scenario IDs X30-1..X30-8 are those of the issue work packet.
"""

import dataclasses
import json
import logging

import httpx2 as httpx
import pytest
from mcp import MCPError
from mcp.client import Client

from tests.patch_support import WriteRouter
from tests.state_catalog_support import FakeClock, make_info, make_segment, make_state
from tests.test_access_profiles import make_config, make_router
from tests.test_access_profiles import open_resources as open_access
from tests.test_state_catalogs import DESK, call, fleet, open_resources
from wled_mcp import explain
from wled_mcp.diagnostics import LastControl
from wled_mcp.operations import build_operations
from wled_mcp.server import create_server

TOOL = "wled_explain_lighting"
FALLBACK = {"UNATTRIBUTED_MISMATCH", "INSUFFICIENT_EVIDENCE"}


@pytest.fixture
def anyio_backend():
    return "asyncio"


def codes(result):
    return [c["code"] for c in result.data["inferred_causes"]]


def causes(result):
    return {c["code"]: c for c in result.data["inferred_causes"]}


def observations(result):
    return {o["id"]: o for o in result.data["observations"]}


def remember(resources, application="unknown", verification="mismatch", code=None):
    resources.monitor.last_control.record("desk", "wled_set_state", application, verification, code)


@pytest.mark.anyio
async def test_x30_1_competing_explanations_are_all_listed_capped_and_unattributed(tmp_path):
    """S3-EXPLAIN-01: playlist, realtime and mismatch coexist; none is ranked or named."""
    router = fleet(info=make_info(live=True, lm="UDP"), state=make_state(pl=3, ps=3))
    async with open_resources(tmp_path, router) as resources:
        remember(resources, code="VERIFICATION_MISMATCH")
        result = await call(resources, TOOL)
    assert result.ok and result.data["conclusion"] == "candidates_only"
    assert {"PLAYBACK_ACTIVE", "REALTIME_INPUT_ACTIVE", "LAST_WRITE_VERIFICATION_MISMATCH"} <= set(
        codes(result)
    )
    assert not FALLBACK & set(codes(result))
    for cause in result.data["inferred_causes"]:
        assert cause["confidence"] in {"low", "medium", "unknown"}
        assert cause["next_checks"] and cause["evidence"] is not None
        text = (cause["statement"] + " ".join(cause["next_checks"])).lower()
        assert not any(word in text for word in ("user", "automation", "home assistant", "app "))
    assert "actor" not in json.dumps(result.data["inferred_causes"]).lower()
    assert any("never name an actor" in limit for limit in result.data["limits"])


@pytest.mark.anyio
async def test_x30_1_realtime_override_weakens_the_realtime_candidate(tmp_path):
    """S3-EXPLAIN-02: lor above zero is contradicting evidence, never a hidden fact."""
    router = fleet(info=make_info(live=True), state=make_state(lor=1))
    async with open_resources(tmp_path, router) as resources:
        result = await call(resources, TOOL)
    cause = causes(result)["REALTIME_INPUT_ACTIVE"]
    assert cause["confidence"] == "low" and cause["contradicting_evidence"] == ["state.lor"]


@pytest.mark.anyio
async def test_x30_2_missing_indicators_are_unknown_never_false(tmp_path):
    """S3-EXPLAIN-02: absent firmware keys, including ver, stay explicit."""
    info = make_info()
    for key in ("live", "lm", "ver", "fxcount", "palcount"):
        info.pop(key, None)
    state = make_state()
    for key in ("pl", "ps", "nl", "lor", "udpn"):
        state.pop(key, None)
    async with open_resources(tmp_path, fleet(info=info, state=state)) as resources:
        result = await call(resources, TOOL)
    assert result.ok
    seen = observations(result)
    for ident in (
        "info.live",
        "info.lm",
        "info.ver",
        "info.fxcount",
        "info.palcount",
        "state.pl",
        "state.nl.on",
        "state.lor",
        "state.udpn.recv",
    ):
        assert seen[ident]["status"] == "unknown", ident
        assert seen[ident]["missing_indicator"] is True and seen[ident]["value"] is None
    assert result.data["firmware"]["version"] is None
    assert set(codes(result)) == FALLBACK


@pytest.mark.anyio
async def test_x30_3_stale_and_absent_process_memory(tmp_path):
    """S3-EXPLAIN-01: process evidence older than 300 s is stale and capped at low."""
    clock = FakeClock()
    async with open_resources(tmp_path, fleet(), clock) as resources:
        remember(resources)
        clock.advance(120)
        fresh = await call(resources, TOOL)
        clock.advance(200)
        stale = await call(resources, TOOL)
    assert observations(fresh)["last_control"]["stale"] is False
    assert causes(fresh)["LAST_WRITE_VERIFICATION_MISMATCH"]["confidence"] == "medium"
    entry = observations(stale)["last_control"]
    assert entry["stale"] is True and entry["age_seconds"] == 320
    assert causes(stale)["LAST_WRITE_VERIFICATION_MISMATCH"]["confidence"] == "low"
    async with open_resources(tmp_path, fleet(), clock) as restarted:  # a new process
        result = await call(restarted, TOOL)
    entry = observations(result)["last_control"]
    assert entry["status"] == "unknown" and entry["missing_indicator"] is True
    assert "LAST_WRITE_VERIFICATION_MISMATCH" not in codes(result)


@pytest.mark.anyio
async def test_x30_4_an_unattributable_mismatch_stays_unattributed(tmp_path):
    """S3-EXPLAIN-01: no indicator, so no cause is invented."""
    async with open_resources(tmp_path, fleet()) as resources:
        remember(resources, code="VERIFICATION_MISMATCH")
        result = await call(resources, TOOL)
    assert set(codes(result)) == {"LAST_WRITE_VERIFICATION_MISMATCH", *FALLBACK}
    assert result.data["conclusion"] == "insufficient_evidence"
    assert explain.UNATTRIBUTED_LIMIT in result.data["limits"]
    assert all(causes(result)[code]["confidence"] == "unknown" for code in FALLBACK)


@pytest.mark.anyio
async def test_x30_5_categories_are_separate_and_a_clean_device_claims_no_cause(tmp_path):
    """S3-EXPLAIN-02: capability, reachability and verification are different findings."""
    async with open_resources(tmp_path, fleet()) as resources:
        clean = await call(resources, TOOL)
        out_of_range = await call(resources, TOOL, requested={"effect_id": 99, "palette_id": 1})
        in_range = await call(resources, TOOL, requested={"effect_id": 3})
        rgb_only = await call(resources, TOOL, segment_id=0, requested={"white_channel": True})
        missing = await call(resources, TOOL, segment_id=42)
    assert set(codes(clean)) == FALLBACK and clean.data["conclusion"] == "insufficient_evidence"
    assert codes(out_of_range).count("REQUESTED_CAPABILITY_UNSUPPORTED") == 1
    assert out_of_range.data["conclusion"] == "observed_blocker"
    assert observations(out_of_range)["capability.palette_id"]["value"] == {"supported": True}
    assert set(codes(in_range)) == FALLBACK
    assert "REQUESTED_CAPABILITY_UNSUPPORTED" in codes(rgb_only)
    assert not missing.ok and missing.error.code == "VALIDATION_ERROR"
    white = make_info(leds={"count": 90, "maxseg": 32, "lc": 3, "seglc": [3, 3, 3]})
    async with open_resources(tmp_path, fleet(info=white)) as resources:
        capable = await call(resources, TOOL, segment_id=0, requested={"white_channel": True})
    assert "REQUESTED_CAPABILITY_UNSUPPORTED" not in codes(capable)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "failure,code",
    [
        (httpx.ConnectError("synthetic-secret"), "DEVICE_UNREACHABLE"),
        (httpx.ReadTimeout("synthetic-secret"), "DEVICE_TIMEOUT"),
    ],
)
async def test_x30_5_unreachable_and_timeout_keep_the_error_and_use_only_memory(
    tmp_path, failure, code
):
    """S3-EXPLAIN-01: a failed read is an error plus process-memory observations."""
    router = fleet()
    async with open_resources(tmp_path, router, read_retries=0) as resources:
        assert (await call(resources, "wled_get_state")).ok  # the monitor now knows the device
        router.set(DESK, "/json/state", failure)
        result = await call(resources, TOOL)
    assert not result.ok and result.error.code in {"UNREACHABLE", "TIMEOUT"}
    assert codes(result) == [code] and result.data["conclusion"] == "candidates_only"
    entry = observations(result)["reachability"]
    assert entry["source"] == "process_memory" and entry["value"]["state"] == "reachable"
    assert "synthetic-secret" not in result.model_dump_json()
    assert result.application == "not_attempted"


@pytest.mark.anyio
async def test_x30_6_exactly_two_gets_and_never_a_write(tmp_path):
    """S3-EXPLAIN-02: one state read, one info read, no POST, nothing applied."""
    router = WriteRouter()
    router.device(DESK)
    async with open_resources(tmp_path, router) as resources:
        result = await call(resources, TOOL)
    assert router.calls == [("GET", DESK, "/json/state"), ("GET", DESK, "/json/info")]
    assert router.posts == []
    assert (result.application, result.verification) == ("not_attempted", "not_requested")
    assert result.dry_run is False and result.data["captured_at"].endswith("+00:00")


@pytest.mark.anyio
async def test_x30_7_registered_in_the_read_only_profile_as_a_read_tool(tmp_path):
    """S3-EXPLAIN-02: read class, advisory annotations, every profile."""
    for profile in ("read-only", "control", "full"):
        config = make_config(tmp_path, profile)
        async with open_access(config, make_router()) as resources:
            server = create_server(build_operations(resources), config.access)
            async with Client(server) as client:
                tool = next(t for t in (await client.list_tools()).tools if t.name == TOOL)
                assert tool.annotations is not None
                assert tool.annotations.read_only_hint is True
                assert tool.annotations.destructive_hint is False
                result = await client.call_tool(TOOL, {"device_id": "desk"})
                assert result.structured_content is not None and result.structured_content["ok"]
                refused = await client.call_tool(TOOL, {"device_id": "desk", "surprise": 1})
                assert refused.structured_content["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.anyio
async def test_x30_8_sensitive_values_never_reach_the_result_or_the_log(tmp_path, caplog):
    """S3-EXPLAIN-02: allowlisted indicators only; long or address-like text becomes other."""
    sentinels = ("192.0.2.77", "00:00:5E:00:53:99", "bssid-sentinel", "ssid-sentinel")
    info = make_info(
        ip=sentinels[0],
        mac=sentinels[1],
        lm="L" * 200,
        wifi={"bssid": sentinels[2], "ssid": sentinels[3] * 30, "rssi": -40},
        lip="198.51.100.9",
    )
    config = make_config(tmp_path, "read-only")
    router = make_router()
    router.set("desk.invalid", "/json/info", info)
    caplog.set_level(logging.INFO, logger="wled_mcp")
    async with open_access(config, router) as resources:
        server = create_server(build_operations(resources), config.access, resources.monitor)
        async with Client(server) as client:
            result = await client.call_tool(TOOL, {"device_id": "desk"})
    document = json.dumps(result.structured_content) + caplog.text
    for sentinel in (*sentinels, "L" * 33, "198.51.100.9"):
        assert sentinel not in document
    assert observations_of(result)["info.lm"]["value"] == "other"
    assert set(observations_of(result)) >= {"info.live", "state.pl"}


def observations_of(result):
    return {o["id"]: o for o in result.structured_content["data"]["observations"]}


@pytest.mark.anyio
async def test_x30_8_size_and_cause_caps_fail_safely(tmp_path, monkeypatch):
    """S3-EXPLAIN-02: overflow is a safe INVALID_RESPONSE, not an oversized document."""
    async with open_resources(tmp_path, fleet()) as resources:
        monkeypatch.setattr(explain, "MAX_DATA_BYTES", 200)
        too_big = await call(resources, TOOL)
        monkeypatch.setattr(explain, "MAX_DATA_BYTES", 32 * 1024)
        monkeypatch.setattr(explain, "MAX_CAUSES", 1)
        too_many = await call(resources, TOOL)
    for result in (too_big, too_many):
        assert not result.ok and result.error.code == "INVALID_RESPONSE"
        assert result.data == {} and len(result.model_dump_json()) < 1024


@pytest.mark.anyio
async def test_x30_8_the_dispatcher_hook_records_only_allowlisted_outcomes(tmp_path):
    """S3-EXPLAIN-01: a real control outcome becomes evidence; refusals and unknowns do not."""
    config = make_config(tmp_path, "full", shelf="read")
    router = WriteRouter()
    for host in ("desk.invalid", "shelf.invalid", "lamp.invalid"):
        router.device(host)
    async with open_access(config, router) as resources:
        store = resources.monitor.last_control
        server = create_server(build_operations(resources), config.access, resources.monitor)
        async with Client(server) as client:
            await client.call_tool("wled_get_state", {"device_id": "desk"})
            await client.call_tool("wled_set_state", {"device_id": "shelf", "on": False})
            await client.call_tool(
                "wled_set_state", {"device_id": "desk", "on": True, "dry_run": True}
            )
            with pytest.raises(MCPError):
                await client.call_tool("wled_absent_tool", {"device_id": "desk"})
            assert store.latest("desk") is None and store.latest("shelf") is None
            # The mock device ACKs without changing state: a readback mismatch.
            await client.call_tool("wled_set_state", {"device_id": "desk", "on": False})
            explained = await client.call_tool(TOOL, {"device_id": "desk"})
        record = store.latest("desk")
    assert record is not None
    assert (record.operation, record.application, record.verification) == (
        "wled_set_state",
        "unknown",
        "mismatch",
    )
    assert record.error_code == "VERIFICATION_MISMATCH"
    assert {f.name for f in dataclasses.fields(LastControl)} == {
        "operation",
        "finished_at",
        "application",
        "verification",
        "error_code",
    }
    body = explained.structured_content["data"]
    assert "LAST_WRITE_VERIFICATION_MISMATCH" in [c["code"] for c in body["inferred_causes"]]


@pytest.mark.anyio
async def test_a_master_off_device_is_an_observed_blocker_with_competitors_listed(tmp_path):
    """S3-EXPLAIN-01: an observed blocker does not hide other candidates."""
    state = make_state([make_segment(0, 0, 30)], on=False, nl={"on": True}, udpn={"recv": True})
    async with open_resources(tmp_path, fleet(state=state)) as resources:
        result = await call(resources, TOOL)
    assert result.data["conclusion"] == "observed_blocker"
    assert causes(result)["MASTER_OFF_OR_ZERO_BRIGHTNESS"]["confidence"] == "high"
    assert {"NIGHTLIGHT_ACTIVE", "SYNC_RECEIVE_ENABLED"} <= set(codes(result))


@pytest.mark.anyio
async def test_a_config_only_possibility_does_not_hide_insufficient_evidence(tmp_path):
    """S3-EXPLAIN-01: firmware-default sync receive is a possibility, not an explanation."""
    state = make_state(nl={"on": False}, lor=0, udpn={"send": False, "recv": True})
    info = make_info(live=False, lm="")
    async with open_resources(tmp_path, fleet(info=info, state=state)) as resources:
        result = await call(resources, TOOL)
    assert FALLBACK <= set(codes(result)) and "SYNC_RECEIVE_ENABLED" in codes(result)
    assert result.data["conclusion"] == "insufficient_evidence"
    assert explain.UNATTRIBUTED_LIMIT in result.data["limits"]
    assert observations(result)["info.lm"]["value"] == ""  # idle, not "other"


@pytest.mark.anyio
async def test_an_indicator_candidate_still_gives_candidates_only(tmp_path):
    """S3-EXPLAIN-01: a real candidate next to sync receive is not downgraded."""
    state = make_state(pl=2, udpn={"recv": True})
    async with open_resources(tmp_path, fleet(state=state)) as resources:
        result = await call(resources, TOOL)
    assert result.data["conclusion"] == "candidates_only"
    assert not FALLBACK & set(codes(result))


@pytest.mark.anyio
async def test_realtime_source_text_allows_a_slash_but_not_an_address(tmp_path):
    """S3-EXPLAIN-02: lm keeps its bound; only safe names are echoed."""
    seen = {}
    for lm in ("USB Adalight/TPM2", "x/10.0.0.1"):
        async with open_resources(tmp_path, fleet(info=make_info(lm=lm))) as resources:
            seen[lm] = observations(await call(resources, TOOL))["info.lm"]["value"]
    assert seen == {"USB Adalight/TPM2": "USB Adalight/TPM2", "x/10.0.0.1": "other"}


@pytest.mark.anyio
async def test_a_segment_id_without_a_state_segment_list_is_a_validation_error(tmp_path):
    """S3-EXPLAIN-02: the contract's segment check does not silently pass."""
    state = make_state()
    del state["seg"]
    async with open_resources(tmp_path, fleet(state=state)) as resources:
        result = await call(resources, TOOL, segment_id=0)
    assert not result.ok and result.error.code == "VALIDATION_ERROR"
