"""LIVE-01: sampled provenance, global bounds and fixed read-only decoding."""

import json

import httpx2 as httpx
import pytest
from pydantic import ValidationError

from tests.state_catalog_support import make_info, make_segment, make_state
from tests.test_state_catalogs import DESK, call, fleet, open_resources
from wled_mcp.access import AccessPolicy
from wled_mcp.client import validate_live
from wled_mcp.live_snapshot import LiveSnapshotRequest, map_snapshot
from wled_mcp.operations import build_operations
from wled_mcp.server import create_server


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_sample_runs_use_only_actual_indices_and_report_gaps_overlaps_missing():
    segments = [make_segment(2, 1, 5), make_segment(9, 4, 7), make_segment(12, 1, 2)]
    result = map_snapshot(segments, {"leds": ["ff0000", "ff0000", "00ff00"], "n": 2}, 9, 10)
    by_id = {s["id"]: s for s in result["segments"]}
    assert by_id[2]["runs"] == [
        {"first_led": 2, "sample_count": 1, "rgb": "FF0000"},
        {"first_led": 4, "sample_count": 1, "rgb": "00FF00"},
    ]
    assert by_id[2]["unsampled_leds"] == 2
    assert by_id[9]["status"] == "missing_samples"
    assert by_id[12]["status"] == "no_samples"
    assert result["gaps"] == [{"start": 0, "stop": 1}, {"start": 7, "stop": 9}]
    assert result["overlaps"] == [{"start": 1, "stop": 2}, {"start": 4, "stop": 5}]
    assert not result["source_count_matches_geometry"] and not result["coverage_complete"]


def test_downsampling_runs_do_not_expand_a_long_strip_and_budget_is_global():
    colors = ["FF0000", "00FF00"] * 2048
    segments = [make_segment(i, 0, 1000000) for i in range(150)]
    result = map_snapshot(segments, {"leds": colors, "n": 1000}, 1000000, 3)
    assert result["returned_runs"] == 3
    assert sum(len(s["runs"]) for s in result["segments"]) == 3
    assert result["omitted_segments"] == 22
    assert result["segments"][0]["status"] == "truncated"
    assert len(json.dumps(result)) < 128 * 1024
    merged = map_snapshot([make_segment(3, 0, 5)], {"leds": ["ABCDEF"] * 3, "n": 2}, 5, 1)
    assert merged["segments"][0]["runs"] == [{"first_led": 0, "sample_count": 3, "rgb": "ABCDEF"}]
    assert merged["segments"][0]["unsampled_leds"] == 2


def test_matrix_empty_and_stale_geometry_are_explicit():
    segments = [make_segment(3, 0, 4), make_segment(9, 0, 0)]
    matrix = map_snapshot(segments, {"leds": ["000000"], "n": 2, "w": 1, "h": 1}, 4, 3)
    assert matrix["status"] == "unmapped_matrix"
    assert matrix["reported_geometry"] == {"w": 1, "h": 1}
    assert matrix["segments"][0]["runs"] == [] and len(matrix["segments"]) == 1
    empty = map_snapshot(segments, {"leds": [], "n": 1}, 4, 3)
    assert empty["status"] == "empty"
    assert empty["segments"][0]["status"] == "missing_samples"
    stale = map_snapshot(segments, {"leds": ["000000"], "n": 1}, 1, 3)
    assert stale["segments"][0]["status"] == "unknown_or_stale_geometry"


@pytest.mark.parametrize(
    "value",
    [
        [],
        {},
        {"leds": [], "n": True},
        {"leds": [], "n": 0},
        {"leds": ["bad"], "n": 1},
        {"leds": ["000000"] * 4097, "n": 1},
        {"leds": [], "n": 1, "w": 2},
        {"leds": [], "n": 1, "w": True, "h": 2},
    ],
)
def test_dedicated_decoder_rejects_malformed_or_oversized_live(value):
    with pytest.raises(ValueError):
        validate_live(value)


@pytest.mark.parametrize("max_runs", [0, 513, True, "3"])
def test_request_budget_is_strict(max_runs):
    with pytest.raises(ValidationError):
        LiveSnapshotRequest(device_id="desk", max_runs=max_runs)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "response,status,code",
    [
        ({"leds": ["000000"] * 90, "n": 1}, "available", None),
        (httpx.Response(404), "unavailable", None),
        (httpx.Response(501), "unavailable", None),
        (httpx.Response(500), None, "INVALID_RESPONSE"),
        ({"leds": ["invalid"], "n": 1}, None, "INVALID_RESPONSE"),
        (httpx.ConnectError("synthetic-secret"), None, "UNREACHABLE"),
        (httpx.ReadTimeout("synthetic-secret"), None, "TIMEOUT"),
    ],
)
async def test_fixed_endpoint_reads_and_distinguishable_failures(tmp_path, response, status, code):
    router = fleet()
    router.set(DESK, "/json/live", response)
    async with open_resources(tmp_path, router, read_retries=0) as resources:
        result = await call(resources, "wled_get_live_snapshot")
        create_server(build_operations(resources), access=AccessPolicy("read-only", {}))
    assert result.application == "not_attempted" and result.verification == "not_requested"
    if status:
        assert result.ok and result.data["status"] == status
        if status == "unavailable":
            assert result.data["http_status"] == response.status_code
            assert result.data["segments"] == []
        assert result.data["source"] == "/json/live"
        assert result.data["captured_at"].endswith("+00:00")
    else:
        assert not result.ok and result.error.code == code
        assert "synthetic-secret" not in result.model_dump_json()
    assert router.calls == [(DESK, "/json/state"), (DESK, "/json/info"), (DESK, "/json/live")]


@pytest.mark.anyio
async def test_output_byte_limit_fails_safely_without_raw_sensitive_info(tmp_path):
    router = fleet(info=make_info(ver="x" * 140000), state=make_state([make_segment(0, 0, 1)]))
    router.set(DESK, "/json/live", {"leds": ["000000"], "n": 1})
    async with open_resources(tmp_path, router) as resources:
        result = await call(resources, "wled_get_live_snapshot")
    assert not result.ok and result.error.code == "INVALID_RESPONSE"
    assert len(result.model_dump_json()) < 1024
