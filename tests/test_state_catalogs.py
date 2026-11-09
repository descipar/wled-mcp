import json
import sys
from pathlib import Path

import anyio
import httpx2 as httpx
import pytest
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters
from pydantic import ValidationError

from tests.state_catalog_support import (
    EFFECTS,
    FXDATA,
    PALETTES,
    SECRET,
    FakeClock,
    Router,
    json_headers,
    make_info,
    make_segment,
    make_state,
)
from tests.test_inventory_client import config, device
from tests.test_version_source import canonical_version
from tests.tool_contract import ToolClass, destructive_names, expected_names, names_of
from wled_mcp.catalogs import (
    PLACEHOLDER_NAME,
    AmbiguousName,
    CatalogEntry,
    catalog_items,
    resolve_name,
)
from wled_mcp.client import ClientFailure
from wled_mcp.compat import firmware_support
from wled_mcp.models import Outcome
from wled_mcp.operations import GetCatalogRequest, GetStateRequest, build_operations
from wled_mcp.readmodels import InfoIdentity
from wled_mcp.resources import Resources

DESK, SHELF = "desk.invalid", "shelf.invalid"


@pytest.fixture
def anyio_backend():
    return "asyncio"


def fleet(**kwargs):
    router = Router()
    router.device(DESK, **kwargs)
    return router


def open_resources(tmp_path, router, clock=None, devices=None, **settings):
    return Resources(
        config(tmp_path, devices=devices, **settings),
        router.transport(),
        clock.clock() if clock else None,
    )


def tools(resources):
    return {operation.name: operation for operation in build_operations(resources)}


async def call(resources, name, **arguments):
    arguments.setdefault("device_id", "desk")
    model = GetStateRequest if name == "wled_get_state" else GetCatalogRequest
    return await tools(resources)[name].execute(model.model_validate(arguments).model_dump())


def assert_read_envelope(result, name, ok=True):
    assert result.ok is ok
    assert result.operation == name
    assert result.application == "not_attempted"
    assert result.verification == "not_requested"
    assert result.dry_run is False


# --------------------------------------------------------------------------- registry


@pytest.mark.anyio
async def test_registry_order_annotations_and_strict_models(tmp_path):
    async with open_resources(tmp_path, fleet()) as resources:
        operations = build_operations(resources)
        # Order and annotations are checked against tests/tool_contract.py centrally.
        assert operations[0].execute.__closure__[0].cell_contents is resources
        assert len(operations[0].execute.__closure__) == 1
        for operation in operations:
            schema = operation.request_model.model_json_schema()
            assert schema["additionalProperties"] is False
    for bad in ({"device_id": "desk", "host": "http://x.invalid"}, {"device_id": 1}, {}):
        with pytest.raises(ValidationError):
            GetStateRequest.model_validate(bad)
    for bad in ({"device_id": "desk", "refresh": 1}, {"device_id": "desk", "refresh": "true"}):
        with pytest.raises(ValidationError):
            GetCatalogRequest.model_validate(bad)


# --------------------------------------------------------------------------- state


@pytest.mark.anyio
async def test_state_full_fixture_normalized_raw_redacted(tmp_path):
    router = fleet(
        info=make_info(leds={"count": 90, "maxseg": 32, "lc": 3, "seglc": [1, 3, 1]}),
        state=make_state(
            [
                make_segment(0, 0, 30),
                make_segment(2, 30, 60, on=False, bri=77, col=[[1, 2, 3, 4], [0, 0, 0, 0]]),
                make_segment(
                    5, 60, 90, n="Wall", grp=2, spc=1, of=3, rev=True, mi=True, fx=3, pal=2
                ),
            ],
            ps=4,
            pl=-1,
        ),
    )
    async with open_resources(tmp_path, router, FakeClock()) as resources:
        result = await call(resources, "wled_get_state")
    assert_read_envelope(result, "wled_get_state")
    assert result.device_id == "desk" and result.warnings == []
    data = result.data
    assert data["device"] == {"id": "desk", "name": "Example desk"}
    assert data["freshness"]["source"] == "device"
    assert data["freshness"]["read_at"].endswith("+00:00")
    assert data["firmware"] == {
        "version": "16.0.1",
        "build_id": 2510010,
        "product": "FOSS",
        "brand": "WLED",
        "arch": "esp32",
    }
    caps = data["capabilities"]
    assert (caps["led_count"], caps["max_segments"]) == (90, 32)
    assert (caps["effect_count"], caps["palette_count"]) == (4, 3)
    assert caps["device_wide_color"] == {
        "scope": "aggregate_of_active_segments",
        "rgb": True,
        "white": True,
        "cct": False,
    }
    state = data["state"]
    assert state["default_transition_ms"] == 700
    assert (state["active_preset_id"], state["active_playlist_id"]) == (4, None)
    assert state["main_segment"] == 0
    by_id = {segment["id"]: segment for segment in state["segments"]}
    assert list(by_id) == [0, 2, 5]
    assert by_id[5]["name"] == "Wall"
    assert (by_id[5]["grouping"], by_id[5]["spacing"], by_id[5]["offset"]) == (2, 1, 3)
    assert (by_id[5]["reverse"], by_id[5]["mirror"]) == (True, True)
    assert (by_id[5]["effect_id"], by_id[5]["palette_id"]) == (3, 2)
    assert by_id[0]["reported_color_capability"] == {"rgb": True, "white": False, "cct": False}
    assert by_id[2]["reported_color_capability"] == {"rgb": True, "white": True, "cct": False}
    # raw data retained; only the documented info keys are redacted and listed
    assert data["raw"]["state"] == router.routes[(DESK, "/json/state")]
    raw_info = data["raw"]["info"]
    assert "mac" not in raw_info and "ip" not in raw_info and "bssid" not in raw_info["wifi"]
    assert raw_info["wifi"]["rssi"] == -50 and raw_info["leds"]["seglc"] == [1, 3, 1]
    assert data["raw"]["redacted_info_keys"] == ["mac", "ip", "wifi.bssid"]
    dumped = result.model_dump_json()
    assert "192.0.2.10" not in dumped and "00:00:5E" not in dumped and "00005e" not in dumped
    assert data["diagnostics"]["server_version"] == canonical_version()
    assert data["diagnostics"]["unknown_capabilities"] == []
    # #21 A21-04: additive, informational tier; the default fixture is the tested release.
    assert data["diagnostics"]["firmware_support"] == {
        "tier": "tested",
        "minimum_supported": "16.0.0",
    }
    assert [router.count(DESK, "/json/state"), router.count(DESK, "/json/info")] == [1, 1]
    Outcome.model_validate(result.model_dump())  # stays a valid envelope


@pytest.mark.anyio
async def test_brightness_remembered_versus_effective(tmp_path):
    router = fleet(
        state=make_state(
            [make_segment(0, 0, 10, on=False, bri=90), make_segment(1, 10, 20, bri=40)],
            on=False,
            bri=200,
        ),
        info=make_info(leds={"count": 20, "maxseg": 8, "lc": 1, "seglc": [1, 1]}),
    )
    async with open_resources(tmp_path, router) as resources:
        data = (await call(resources, "wled_get_state")).data
    assert (data["state"]["on"], data["state"]["brightness"]) == (False, 200)
    assert data["state"]["effective_brightness"] == 0
    first, second = data["state"]["segments"]
    assert (first["on"], first["brightness"], first["effective_brightness"]) == (False, 90, 0)
    assert (second["brightness"], second["effective_brightness"]) == (40, 40)


@pytest.mark.anyio
async def test_zero_white_trimmed_only_for_proven_rgb_only(tmp_path):
    zero_w = [[255, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
    nonzero_w = [[255, 0, 0, 9], [0, 0, 0, 0], [0, 0, 0, 0]]
    router = fleet(
        # seg0 proven RGB-only, seg1 proven RGB-only but nonzero W, seg2 RGB+white,
        # seg3 has no per-segment evidence because seglc covers only three entries.
        info=make_info(leds={"count": 40, "maxseg": 8, "lc": 3, "seglc": [1, 1, 3]}),
        state=make_state(
            [
                make_segment(0, 0, 10, col=zero_w),
                make_segment(1, 10, 20, col=nonzero_w),
                make_segment(2, 20, 30, col=zero_w),
            ]
        ),
    )
    async with open_resources(tmp_path, router) as resources:
        result = await call(resources, "wled_get_state")
    segments = result.data["state"]["segments"]
    assert segments[0]["colors"] == [[255, 0, 0], [0, 0, 0], [0, 0, 0]]
    assert segments[0]["color_channels"] == 3
    assert segments[1]["colors"][0] == [255, 0, 0, 9] and segments[1]["color_channels"] == 4
    assert segments[2]["colors"][0] == [255, 0, 0, 0] and segments[2]["color_channels"] == 4
    # raw state keeps the original four-channel arrays
    assert result.data["raw"]["state"]["seg"][0]["col"] == zero_w

    unknown = fleet(info=make_info(leds={"count": 40, "maxseg": 8, "lc": 1}))
    async with open_resources(tmp_path, unknown) as resources:
        result = await call(resources, "wled_get_state")
    first = result.data["state"]["segments"][0]
    assert first["colors"][0] == [255, 160, 0, 0] and first["reported_color_capability"] is None
    assert "segment_color_capability" in result.data["diagnostics"]["unknown_capabilities"]
    # device-wide aggregate is not proof of per-segment capability: still not trimmed
    assert result.data["capabilities"]["device_wide_color"]["rgb"] is True

    mismatch = fleet(info=make_info(leds={"count": 40, "maxseg": 8, "lc": 1, "seglc": [1]}))
    async with open_resources(tmp_path, mismatch) as resources:
        result = await call(resources, "wled_get_state")
    assert result.ok and result.data["state"]["segments"][0]["color_channels"] == 4
    assert any("capability" in warning for warning in result.warnings)


@pytest.mark.anyio
async def test_missing_optional_facts_are_null_not_false(tmp_path):
    router = fleet(
        info={"ver": "0.14.0"},
        state={"on": True, "bri": 1, "seg": [{"id": 0, "start": 0, "stop": 5}]},
    )
    async with open_resources(tmp_path, router) as resources:
        result = await call(resources, "wled_get_state")
    assert result.ok
    caps = result.data["capabilities"]
    assert caps["led_count"] is caps["max_segments"] is caps["effect_count"] is None
    assert caps["palette_count"] is caps["device_wide_color"] is None
    assert result.data["firmware"] == {
        "version": "0.14.0",
        "build_id": None,
        "product": None,
        "brand": None,
        "arch": None,
    }
    assert result.data["diagnostics"]["unknown_capabilities"] == [
        "led_count",
        "max_segments",
        "effect_count",
        "palette_count",
        "device_wide_color",
        "segment_color_capability",
        "build_id",
    ]
    state = result.data["state"]
    assert state["default_transition_ms"] is None and state["main_segment"] is None
    segment = state["segments"][0]
    assert segment["name"] is None and segment["colors"] is None and segment["on"] is None
    assert segment["effective_brightness"] is None and segment["grouping"] is None


@pytest.mark.anyio
async def test_optional_wrong_types_become_null_with_warning(tmp_path):
    state = make_state([make_segment(0, 0, 10, sx="fast", col="red", n=5, rev=1)], transition=True)
    router = fleet(state=state, info=make_info(fxcount="many"))
    async with open_resources(tmp_path, router) as resources:
        result = await call(resources, "wled_get_state")
    assert result.ok
    segment = result.data["state"]["segments"][0]
    assert segment["speed"] is None and segment["colors"] is None
    assert segment["name"] is None and segment["reverse"] is None
    assert result.data["state"]["default_transition_ms"] is None
    assert result.data["capabilities"]["effect_count"] is None
    assert len(result.warnings) >= 5


@pytest.mark.anyio
@pytest.mark.parametrize(
    "state,info",
    [
        (make_state([make_segment(1, 0, 5), make_segment(1, 5, 9)]), None),
        (make_state([make_segment(-1, 0, 5)]), None),
        (make_state(bri=True), None),
        (make_state(bri="5"), None),
        (make_state(bri=256), None),
        (make_state(bri=1.5), None),
        (make_state(on=1), None),
        (make_state(seg={"id": 0}), None),
        (make_state([{"id": 0, "start": "0", "stop": 5}]), None),
        (make_state([{"id": True, "start": 0, "stop": 5}]), None),
        (make_state(), {"vid": 5}),
        (make_state(), {"ver": 12}),
        (make_state(), {"ver": ""}),
    ],
)
async def test_missing_or_malformed_required_fields_are_invalid_response(tmp_path, state, info):
    router = fleet(state=state, info=info if info is not None else make_info())
    async with open_resources(tmp_path, router) as resources:
        result = await call(resources, "wled_get_state")
    assert_read_envelope(result, "wled_get_state", ok=False)
    assert result.error.code == "INVALID_RESPONSE" and result.data == {}


@pytest.mark.anyio
async def test_state_and_info_are_never_cached(tmp_path):
    router = fleet()
    async with open_resources(tmp_path, router, FakeClock()) as resources:
        first = await call(resources, "wled_get_state")
        router.set(DESK, "/json/state", make_state(on=False, bri=9))
        router.set(DESK, "/json/info", make_info(vid=2510011, ver="16.1.0"))
        second = await call(resources, "wled_get_state")
    assert first.data["state"]["on"] is True and second.data["state"]["on"] is False
    assert second.data["firmware"]["version"] == "16.1.0"
    assert router.count(DESK, "/json/state") == 2 and router.count(DESK, "/json/info") == 2
    assert len(resources.metadata_cache) == 0


# --------------------------------------------------------------------------- multi device


@pytest.mark.anyio
@pytest.mark.parametrize("failure", ["reset", "timeout", "503"])
async def test_offline_device_fails_alone_and_others_unaffected(tmp_path, failure):
    router = Router()
    router.device(DESK)
    router.device(SHELF)
    broken = {
        "reset": httpx.ReadError(SECRET),
        "timeout": httpx.ReadTimeout(SECRET),
        "503": httpx.Response(503, json={"secret": SECRET}),
    }[failure]
    router.set(SHELF, "/json/state", broken)
    results = {}
    async with open_resources(
        tmp_path, router, devices=[device(), device("shelf")], read_retries=0
    ) as resources:

        async def read(device_id):
            results[device_id] = await call(resources, "wled_get_state", device_id=device_id)

        async with anyio.create_task_group() as group:
            group.start_soon(read, "desk")
            group.start_soon(read, "shelf")
        # a failed device never blocks a later read of the healthy one
        again = await call(resources, "wled_get_state", device_id="desk")
    assert results["desk"].ok and again.ok
    expected = {"reset": "UNREACHABLE", "timeout": "TIMEOUT", "503": "INVALID_RESPONSE"}[failure]
    bad = results["shelf"]
    assert_read_envelope(bad, "wled_get_state", ok=False)
    assert bad.device_id == "shelf" and bad.error.code == expected
    assert SECRET not in bad.model_dump_json() and "shelf.invalid" not in bad.model_dump_json()
    assert router.count(SHELF, "/json/info") == 0  # failed on state, nothing else attempted
    assert router.count(DESK) == 4


@pytest.mark.anyio
async def test_read_touches_only_the_selected_device_and_unknown_id_makes_no_http(tmp_path):
    router = Router()
    router.device(DESK)
    router.device(SHELF)
    async with open_resources(tmp_path, router, devices=[device(), device("shelf")]) as resources:
        await call(resources, "wled_get_state", device_id="shelf")
        await call(resources, "wled_get_effects", device_id="shelf")
        assert router.count(DESK) == 0
        before = len(router.calls)
        for name in ("wled_get_state", "wled_get_effects", "wled_get_palettes"):
            result = await call(resources, name, device_id="http://foreign.invalid")
            assert result.error.code == "UNKNOWN_DEVICE" and result.device_id is None
            assert_read_envelope(result, name, ok=False)
        assert len(router.calls) == before


# --------------------------------------------------------------------------- T15


def _bad_responses(state_like=True):
    huge = httpx.Response(200, headers=json_headers(), content=b"{" + b" " * 5000 + b"}")
    return {
        "redirect": (
            httpx.Response(302, headers={"location": "http://foreign.invalid/x"}),
            "INVALID_RESPONSE",
        ),
        "html": (
            httpx.Response(200, text=SECRET, headers={"content-type": "text/html"}),
            "INVALID_RESPONSE",
        ),
        "malformed": (
            httpx.Response(200, content=SECRET.encode(), headers=json_headers()),
            "INVALID_RESPONSE",
        ),
        "oversize": (huge, "INVALID_RESPONSE"),
        "compressed": (
            httpx.Response(
                200,
                stream=httpx.ByteStream(b"{}"),
                headers=json_headers(**{"content-encoding": "gzip"}),
            ),
            "INVALID_RESPONSE",
        ),
        "nan": (
            httpx.Response(200, content=b'{"on":NaN}', headers=json_headers()),
            "INVALID_RESPONSE",
        ),
        "wrong_shape": (
            httpx.Response(200, json=[SECRET] if state_like else {"x": 1}),
            "INVALID_RESPONSE",
        ),
        "reset": (httpx.ReadError(SECRET), "UNREACHABLE"),
        "timeout": (httpx.ReadTimeout(SECRET), "TIMEOUT"),
        "status": (httpx.Response(500, json={"detail": SECRET}), "INVALID_RESPONSE"),
    }


@pytest.mark.anyio
@pytest.mark.parametrize("case", list(_bad_responses()))  # one fresh response per test
@pytest.mark.parametrize(
    "tool,path",
    [
        ("wled_get_state", "/json/state"),
        ("wled_get_state", "/json/info"),
        ("wled_get_effects", "/json/eff"),
        ("wled_get_effects", "/json/info"),
        ("wled_get_palettes", "/json/pal"),
    ],
)
async def test_hostile_device_responses_give_stable_errors_without_echo(tmp_path, case, tool, path):
    response, code = _bad_responses(path in ("/json/state", "/json/info"))[case]
    router = fleet()
    router.set(DESK, path, response)
    async with open_resources(
        tmp_path, router, max_response_bytes=4096, read_retries=0
    ) as resources:
        result = await call(resources, tool)
    assert_read_envelope(result, tool, ok=False)
    assert result.error.code == code
    dumped = result.model_dump_json()
    assert SECRET not in dumped and "desk.invalid" not in dumped and "foreign.invalid" not in dumped
    assert result.data == {}
    if case == "status":
        assert "500" in result.error.message
    assert result.error.message  # actionable but bounded


@pytest.mark.anyio
async def test_status_message_names_resource_and_numeric_status(tmp_path):
    router = fleet()
    router.set(DESK, "/json/info", httpx.Response(404, text=SECRET))
    async with open_resources(tmp_path, router) as resources:
        result = await call(resources, "wled_get_effects")
    assert "404" in result.error.message and "info" in result.error.message


# --------------------------------------------------------------------------- catalogs


@pytest.mark.anyio
async def test_effect_catalog_preserves_ids_gaps_placeholders_and_metadata(tmp_path):
    names = ["Solid", "RSVD", "Blink", "RSVD", "42", "Ünïcode ☀", "Blink", "blink"]
    router = fleet(eff=names, fxdata=[f"d{i}" for i in range(8)], info=make_info(fxcount=8))
    async with open_resources(tmp_path, router) as resources:
        result = await call(resources, "wled_get_effects")
    assert_read_envelope(result, "wled_get_effects")
    items = result.data["effects"]
    assert [(i["id"], i["name"]) for i in items] == list(enumerate(names))
    assert [i["id"] for i in items if i.get("placeholder")] == [1, 3]
    assert all("placeholder" not in i for i in items if i["name"] != PLACEHOLDER_NAME)
    assert items[5]["metadata"] == {"fxdata": "d5"}
    assert result.data["count"] == 8 and result.warnings == []
    assert result.data["metadata"] == {"status": "available", "reason": None}
    freshness = result.data["freshness"]
    assert freshness["source"] == "device" and freshness["age_seconds"] == 0.0
    assert freshness["cache_ttl_seconds"] == 300 and freshness["refreshed"] is False
    assert freshness["firmware"] == {"version": "16.0.1", "build_id": 2510010}
    assert router.count(DESK, "/json/pal") == 0


@pytest.mark.anyio
async def test_palette_catalog_no_metadata_and_count_mismatch_warning(tmp_path):
    router = fleet(pal=["Default", "RSVD", "Party"], info=make_info(palcount=5))
    async with open_resources(tmp_path, router) as resources:
        result = await call(resources, "wled_get_palettes")
    assert [i["id"] for i in result.data["palettes"]] == [0, 1, 2]
    # "RSVD" is only a placeholder marker for effects; palettes are never flagged
    assert all("placeholder" not in i and "metadata" not in i for i in result.data["palettes"])
    assert "metadata" not in result.data
    assert len(result.warnings) == 1 and "5" in result.warnings[0]
    assert router.count(DESK, "/json/fxdata") == 0 and router.count(DESK, "/json/eff") == 0


@pytest.mark.anyio
async def test_empty_catalog_and_effect_count_mismatch(tmp_path):
    router = fleet(eff=[], fxdata=[], info=make_info(fxcount=3))
    async with open_resources(tmp_path, router) as resources:
        result = await call(resources, "wled_get_effects")
    assert result.ok and result.data["effects"] == [] and result.data["count"] == 0
    assert len(result.warnings) == 1 and result.data["metadata"]["status"] == "available"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "fxdata,reason",
    [
        (httpx.Response(404, text=SECRET), "INVALID_RESPONSE"),
        (
            httpx.Response(200, text=SECRET, headers={"content-type": "text/html"}),
            "INVALID_RESPONSE",
        ),
        (httpx.ReadError(SECRET), "UNREACHABLE"),
        (httpx.ReadTimeout(SECRET), "TIMEOUT"),
        ([1, 2, 3, 4, 5, 6], "INVALID_RESPONSE"),
        ({"not": "a list"}, "INVALID_RESPONSE"),
        (
            httpx.Response(200, headers=json_headers(), content=b'["' + b"x" * 5000 + b'"]'),
            "INVALID_RESPONSE",
        ),
        # truncated, invalid JSON below the size limit, as observed live in #11
        (
            httpx.Response(200, headers=json_headers(), content=b'["a","b","c'),
            "INVALID_RESPONSE",
        ),
        (["only", "two"], "length_mismatch"),
    ],
)
async def test_optional_fxdata_failure_keeps_names_and_succeeds(tmp_path, fxdata, reason):
    router = fleet(fxdata=fxdata)
    router.set(DESK, "/json/info", make_info(fxcount=6))
    async with open_resources(
        tmp_path, router, max_response_bytes=4096, read_retries=0
    ) as resources:
        result = await call(resources, "wled_get_effects")
    assert_read_envelope(result, "wled_get_effects")
    assert [i["name"] for i in result.data["effects"]] == EFFECTS
    assert all("metadata" not in item for item in result.data["effects"])
    assert result.data["metadata"] == {"status": "unavailable", "reason": reason}
    assert len(result.warnings) == 1 and SECRET not in result.model_dump_json()


@pytest.mark.anyio
async def test_fxdata_never_supplies_names_and_effect_failure_is_an_error(tmp_path):
    router = fleet(eff=httpx.Response(500, text=SECRET))
    async with open_resources(tmp_path, router) as resources:
        result = await call(resources, "wled_get_effects")
    assert not result.ok and result.error.code == "INVALID_RESPONSE" and result.data == {}
    assert router.count(DESK, "/json/fxdata") == 0  # not even requested without names
    # fxdata with more entries than names never creates entries
    router = fleet(eff=["Solid"], fxdata=["a", "b", "c"])
    async with open_resources(tmp_path, router) as resources:
        result = await call(resources, "wled_get_effects")
    assert [i["name"] for i in result.data["effects"]] == ["Solid"]
    assert result.data["metadata"]["reason"] == "length_mismatch"


@pytest.mark.anyio
async def test_hanging_fxdata_does_not_consume_the_whole_deadline(tmp_path):
    router = fleet()

    async def hang():
        await anyio.sleep_forever()

    router.set(DESK, "/json/fxdata", hang)
    async with open_resources(
        tmp_path, router, operation_timeout_seconds=0.4, read_retries=0
    ) as resources:
        started = anyio.current_time()
        result = await call(resources, "wled_get_effects")
        elapsed = anyio.current_time() - started
    assert result.ok and result.data["metadata"] == {"status": "unavailable", "reason": "TIMEOUT"}
    assert [i["name"] for i in result.data["effects"]] == EFFECTS
    assert elapsed < 0.4


# --------------------------------------------------------------------------- cache


@pytest.mark.anyio
async def test_cache_hit_reads_only_info_and_reports_source_and_age(tmp_path):
    router, clock = fleet(), FakeClock()
    async with open_resources(tmp_path, router, clock, catalog_cache_seconds=60) as resources:
        first = await call(resources, "wled_get_effects")
        clock.advance(25)
        second = await call(resources, "wled_get_effects")
        palettes = await call(resources, "wled_get_palettes")  # separate kind, own entry
        again = await call(resources, "wled_get_palettes")
    assert first.data["freshness"]["source"] == "device"
    assert second.data["freshness"]["source"] == "cache"
    assert second.data["freshness"]["age_seconds"] == 25.0
    assert second.data["freshness"]["fetched_at"] == first.data["freshness"]["fetched_at"]
    assert second.data["effects"] == first.data["effects"]
    assert palettes.data["freshness"]["source"] == "device"
    assert again.data["freshness"]["source"] == "cache"
    assert router.count(DESK, "/json/eff") == 1 and router.count(DESK, "/json/fxdata") == 1
    assert router.count(DESK, "/json/pal") == 1
    assert router.count(DESK, "/json/info") == 4  # exactly one fresh info read per call


@pytest.mark.anyio
async def test_cache_expiry_refresh_and_ttl_zero(tmp_path):
    router, clock = fleet(), FakeClock()
    async with open_resources(tmp_path, router, clock, catalog_cache_seconds=60) as resources:
        await call(resources, "wled_get_palettes")
        clock.advance(59.9)
        assert (await call(resources, "wled_get_palettes")).data["freshness"]["source"] == "cache"
        clock.advance(0.1)  # exactly the TTL: expired entries are never served
        expired = await call(resources, "wled_get_palettes")
        assert expired.data["freshness"]["source"] == "device"
        assert router.count(DESK, "/json/pal") == 2
        router.set(DESK, "/json/pal", ["Default", "New"])
        forced = await call(resources, "wled_get_palettes", refresh=True)
        assert forced.data["freshness"]["refreshed"] is True
        assert forced.data["freshness"]["source"] == "device"
        assert [i["name"] for i in forced.data["palettes"]] == ["Default", "New"]
        after = await call(resources, "wled_get_palettes")
        assert after.data["palettes"] == forced.data["palettes"]
        assert after.data["freshness"]["source"] == "cache"
    router, clock = fleet(), FakeClock()
    async with open_resources(tmp_path, router, clock, catalog_cache_seconds=0) as resources:
        for _ in range(3):
            result = await call(resources, "wled_get_effects")
            assert result.data["freshness"]["source"] == "device"
            assert result.data["freshness"]["cache_ttl_seconds"] == 0
        assert len(resources.metadata_cache) == 0
    assert router.count(DESK, "/json/eff") == 3


@pytest.mark.anyio
async def test_failed_refresh_keeps_previous_entry_and_no_stale_fallback(tmp_path):
    router, clock = fleet(), FakeClock()
    async with open_resources(tmp_path, router, clock, read_retries=0) as resources:
        await call(resources, "wled_get_effects")
        router.set(DESK, "/json/eff", httpx.ReadError(SECRET))
        failed = await call(resources, "wled_get_effects", refresh=True)
        assert not failed.ok and failed.error.code == "UNREACHABLE" and failed.data == {}
        router.set(DESK, "/json/eff", list(EFFECTS))
        kept = await call(resources, "wled_get_effects")
        assert kept.data["freshness"]["source"] == "cache"  # old entry still live
        router.set(DESK, "/json/info", httpx.ReadTimeout(SECRET))
        info_down = await call(resources, "wled_get_effects")
        assert not info_down.ok and info_down.error.code == "TIMEOUT"  # no stale fallback
        router.set(DESK, "/json/info", make_info())
        clock.advance(10_000)
        router.set(DESK, "/json/eff", httpx.ReadError(SECRET))
        expired = await call(resources, "wled_get_effects")
        assert not expired.ok  # expired entry is not served as a fallback
        assert len(resources.metadata_cache) == 0


@pytest.mark.anyio
@pytest.mark.parametrize(
    "changed",
    [{"ver": "16.1.0"}, {"vid": 2510011}, {"vid": None}],
)
async def test_firmware_identity_change_invalidates(tmp_path, changed):
    router, clock = fleet(), FakeClock()
    async with open_resources(tmp_path, router, clock) as resources:
        await call(resources, "wled_get_effects")
        router.set(DESK, "/json/eff", ["Solid", "Brand new"])
        info = make_info(**changed)
        if changed.get("vid", 0) is None:
            del info["vid"]
        router.set(DESK, "/json/info", info)
        result = await call(resources, "wled_get_effects")
    assert result.data["freshness"]["source"] == "device"
    assert [i["name"] for i in result.data["effects"]] == ["Solid", "Brand new"]
    assert result.data["freshness"]["firmware"]["version"] == info["ver"]
    assert router.count(DESK, "/json/eff") == 2


@pytest.mark.anyio
async def test_cache_is_isolated_per_device_and_kind_and_concurrent_misses_agree(tmp_path):
    router = Router()
    router.device(DESK, eff=["Solid", "Desk only"])
    router.device(SHELF, eff=["Solid", "Shelf only"])
    out = {}
    async with open_resources(
        tmp_path, router, FakeClock(), devices=[device(), device("shelf")]
    ) as resources:

        async def read(label, device_id):
            out[label] = await call(resources, "wled_get_effects", device_id=device_id)

        async with anyio.create_task_group() as group:
            for label, device_id in (
                ("d1", "desk"),
                ("d2", "desk"),
                ("s1", "shelf"),
                ("s2", "shelf"),
            ):
                group.start_soon(read, label, device_id)
        assert router.count(DESK, "/json/eff") == 1 and router.count(SHELF, "/json/eff") == 1
        assert out["d1"].data["effects"] == out["d2"].data["effects"]
        assert out["d1"].data["effects"][1]["name"] == "Desk only"
        assert out["s1"].data["effects"][1]["name"] == "Shelf only"
        assert sorted(o.data["freshness"]["source"] for o in out.values()) == [
            "cache",
            "cache",
            "device",
            "device",
        ]
        assert len(resources.metadata_cache) == 2
        await call(resources, "wled_get_palettes", device_id="desk")
        assert len(resources.metadata_cache) == 3


# --------------------------------------------------------------------------- resolver


def entry_for(names):
    from datetime import UTC, datetime

    return CatalogEntry(
        tuple(names), None, None, InfoIdentity("16.0.1", 1), 0.0, datetime.now(UTC), ()
    )


def test_resolver_exact_casefold_ambiguity_and_placeholders():
    entry = entry_for(["Solid", "RSVD", "Blink", "blink", "  Wipe ", "Fade", "fade", "FADE", "Ünï"])
    assert resolve_name(entry, "effects", "Blink") == 2  # exact beats case-folded ambiguity
    assert resolve_name(entry, "effects", "blink") == 3
    assert resolve_name(entry, "effects", "wipe") == 4  # trimmed + folded, unique
    assert resolve_name(entry, "effects", " SOLID ") == 0
    assert resolve_name(entry, "effects", "ÜNÏ") == 8
    with pytest.raises(AmbiguousName) as caught:
        resolve_name(entry, "effects", "fAdE")
    assert caught.value.error.code == "AMBIGUOUS_NAME"
    assert caught.value.candidates == [
        {"id": 5, "name": "Fade"},
        {"id": 6, "name": "fade"},
        {"id": 7, "name": "FADE"},
    ]
    for missing in ("Wip", "", "   ", "RSVD", "rsvd"):
        with pytest.raises(ClientFailure) as unknown:
            resolve_name(entry, "effects", missing)
        assert unknown.value.error.code == "VALIDATION_ERROR"
    # the placeholder name only matters for effects; a palette called RSVD is a real name
    assert resolve_name(entry, "palettes", "RSVD") == 1


def test_resolver_candidates_are_bounded_and_duplicates_ambiguous():
    entry = entry_for(["Same"] * 40)
    with pytest.raises(AmbiguousName) as caught:
        resolve_name(entry, "palettes", "Same")
    assert len(caught.value.candidates) == 10 and caught.value.total == 40
    assert caught.value.candidates[0] == {"id": 0, "name": "Same"}


def test_catalog_items_never_use_fxdata_for_names():
    entry = CatalogEntry(
        ("A",), ("x@y",), None, InfoIdentity("v", None), 0.0, entry_for([]).fetched_at, ()
    )
    assert catalog_items(entry, "effects") == [
        {"id": 0, "name": "A", "metadata": {"fxdata": "x@y"}}
    ]


# --------------------------------------------------------------------------- stdio


@pytest.mark.anyio
async def test_real_stdio_lists_four_tools_with_strict_schemas_and_envelope_parity():
    root = Path(__file__).resolve().parents[1]
    with anyio.fail_after(30):
        params = StdioServerParameters(
            command=sys.executable, cwd=root, args=["-m", "tests.state_fixture"]
        )
        async with Client(params, mode="legacy", read_timeout_seconds=10) as client:
            listed = (await client.list_tools()).tools
            assert [t.name for t in listed] == expected_names()
            read_only_names = names_of(ToolClass.READ)
            destructive = destructive_names()
            for tool in listed:
                assert tool.input_schema["additionalProperties"] is False
                if tool.name in read_only_names:
                    assert tool.annotations.read_only_hint is True
                    assert tool.annotations.destructive_hint is False
                    assert tool.annotations.idempotent_hint is True
                    assert tool.annotations.open_world_hint is False
                else:
                    assert tool.annotations.read_only_hint is False
                    assert tool.annotations.destructive_hint is (tool.name in destructive)
                    assert tool.annotations.idempotent_hint is False
                    assert tool.annotations.open_world_hint is False
                assert tool.output_schema["additionalProperties"] is True  # tolerant output, #130
            schema = {t.name: t.input_schema for t in listed}
            assert schema["wled_get_effects"]["properties"]["refresh"]["type"] == "boolean"
            assert set(schema["wled_get_state"]["required"]) == {"device_id"}

            outcomes = {}
            for name, args in [
                ("wled_get_state", {"device_id": "desk"}),
                ("wled_get_effects", {"device_id": "desk"}),
                ("wled_get_effects", {"device_id": "desk", "refresh": True}),
                ("wled_get_palettes", {"device_id": "desk"}),
                ("wled_get_state", {"device_id": "shelf"}),
                ("wled_get_effects", {"device_id": "shelf"}),
                ("wled_get_state", {"device_id": "nope"}),
            ]:
                result = await client.call_tool(name, args)
                envelope = result.structured_content
                assert json.loads(result.content[0].text) == envelope
                Outcome.model_validate(envelope)
                assert result.is_error == (not envelope["ok"])
                outcomes[(name, args["device_id"])] = envelope
            assert outcomes[("wled_get_state", "desk")]["ok"]
            assert outcomes[("wled_get_effects", "desk")]["data"]["count"] == len(EFFECTS)
            assert outcomes[("wled_get_palettes", "desk")]["data"]["count"] == len(PALETTES)
            assert outcomes[("wled_get_state", "shelf")]["error"]["code"] == "INVALID_RESPONSE"
            assert outcomes[("wled_get_effects", "shelf")]["error"]["code"] == "INVALID_RESPONSE"
            assert outcomes[("wled_get_state", "nope")]["error"]["code"] == "UNKNOWN_DEVICE"
            assert SECRET not in json.dumps(list(outcomes.values()))
            assert FXDATA  # fixture metadata is served by the subprocess mock

            for name, args in [
                ("wled_get_effects", {"device_id": "desk", "refresh": 1}),
                ("wled_get_palettes", {"device_id": "desk", "refresh": "yes"}),
                ("wled_get_state", {"device_id": "desk", "host": "http://foreign.invalid"}),
                ("wled_get_state", {}),
            ]:
                result = await client.call_tool(name, args)
                assert result.is_error
                assert result.structured_content["error"]["code"] == "VALIDATION_ERROR"


def test_contract_examples_are_valid_envelopes_and_redacted():
    folder = Path(__file__).resolve().parents[1] / "examples/contracts"
    for name, expected_cases in (
        ("state.json", {"state", "unknown_device"}),
        ("catalogs.json", {"effects_fresh", "effects_cache_hit_after_42s", "palettes"}),
    ):
        cases = json.loads((folder / name).read_text(encoding="utf-8"))["cases"]
        assert expected_cases <= set(cases)
        for case in cases.values():
            envelope = Outcome.model_validate(case["expected"])
            assert envelope.application == "not_attempted"
            assert "192.0.2.10" not in json.dumps(case["expected"])
    state = json.loads((folder / "state.json").read_text(encoding="utf-8"))["cases"]["state"]
    assert state["expected"]["data"]["raw"]["redacted_info_keys"] == ["mac", "ip", "wifi.bssid"]
    example = state["expected"]["data"]
    assert example["diagnostics"]["firmware_support"] == firmware_support(
        example["raw"]["info"]["ver"]
    )
    assert example["firmware"]["version"] == example["raw"]["info"]["ver"]
    effects = json.loads((folder / "catalogs.json").read_text(encoding="utf-8"))["cases"]
    assert (
        effects["effects_cache_hit_after_42s"]["expected"]["data"]["freshness"]["source"] == "cache"
    )
    assert (
        effects["effects_metadata_unavailable"]["expected"]["data"]["metadata"]["status"]
        == "unavailable"
    )
