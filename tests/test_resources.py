"""Issue #258: MCP resources for the device list and the catalogs (MCPRES-01..08).

In-memory server against mock routers; no LAN contact. Registration expectations come from
tests/tool_contract.py, never from production code.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx2 as httpx
import pytest
from mcp.client import Client
from mcp.shared.exceptions import MCPError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict

from tests.test_access_profiles import HOSTS, served
from tests.tool_contract import EXPECTED_TOOLS, expected_names, expected_names_in
from wled_mcp.access import ToolClass
from wled_mcp.models import Outcome
from wled_mcp.server import Operation, create_server

DEVICES = "wled://devices"
EFFECTS = "wled://devices/desk/effects"
PALETTES = "wled://devices/desk/palettes"
MAPPING = {
    DEVICES: "wled_list_devices",
    EFFECTS: "wled_get_effects",
    PALETTES: "wled_get_palettes",
}
TEMPLATES = ["wled://devices/{controller}/effects", "wled://devices/{controller}/palettes"]


def text_of(result: Any) -> str:
    assert len(result.contents) == 1
    assert result.contents[0].mime_type == "application/json"
    return result.contents[0].text


def body_of(result: Any) -> dict[str, Any]:
    return json.loads(text_of(result))


def without_correlation(envelope: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in envelope.items() if key != "correlation_id"}


async def resource_surface(client: Client) -> tuple[list[str], list[str]]:
    resources = [str(r.uri) for r in (await client.list_resources()).resources]
    templates = [
        t.uri_template for t in (await client.list_resource_templates()).resource_templates
    ]
    return resources, templates


async def read_error(client: Client, uri: str) -> MCPError:
    with pytest.raises(MCPError) as caught:
        await client.read_resource(uri)
    return caught.value


# ------------------------------------------------------------- AC-258-01 / 02 listing, bodies


@pytest.mark.anyio
async def test_full_profile_lists_the_device_resource_and_both_templates(tmp_path):
    server, _resources, _router = served(tmp_path)
    async with Client(server) as client:
        assert await resource_surface(client) == ([DEVICES], TEMPLATES)
        capabilities = client.session.server_capabilities
        assert capabilities is not None and capabilities.resources is not None
        assert not capabilities.resources.subscribe and not capabilities.resources.list_changed


@pytest.mark.anyio
async def test_device_resource_equals_the_unprobed_list_tool_and_touches_no_device(tmp_path):
    server, _resources, router = served(tmp_path)
    async with Client(server) as client:
        body = body_of(await client.read_resource(DEVICES))
        tool = await client.call_tool("wled_list_devices", {"probe": False})
    assert tool.structured_content is not None
    assert without_correlation(body) == without_correlation(tool.structured_content)
    assert [d["id"] for d in body["data"]["devices"]] == list(HOSTS)
    assert {d["probe_status"] for d in body["data"]["devices"]} == {"untested"}
    assert router.calls == []


@pytest.mark.anyio
@pytest.mark.parametrize("uri", [EFFECTS, PALETTES])
async def test_catalog_resources_equal_the_tool_result_and_share_its_cache(tmp_path, uri):
    server, _resources, router = served(tmp_path)
    tool = MAPPING[uri]
    path = "/json/eff" if uri == EFFECTS else "/json/pal"
    async with Client(server) as client:
        first = body_of(await client.read_resource(uri))
        assert router.count("GET", "desk.invalid", path) == 1
        second = body_of(await client.read_resource(uri))
        via_tool = await client.call_tool(tool, {"device_id": "desk"})
    # One device read in total: the resource never refreshes and fills the tool's cache.
    assert router.count("GET", "desk.invalid", path) == 1
    assert first["data"]["freshness"]["source"] == "device"
    assert second["data"]["freshness"]["source"] == "cache"
    assert via_tool.structured_content is not None
    assert without_correlation(second) == without_correlation(via_tool.structured_content)
    assert first["ok"] is True and first["data"]["count"] > 0
    if uri == EFFECTS:
        assert second["data"]["metadata"]["status"] == "available"
    assert router.posts == []


# ---------------------------------------------------------------- AC-258-03 registration


def tool_operation(name: str, group: str = "core") -> Operation:
    class Request(BaseModel):
        model_config = ConfigDict(extra="forbid", strict=True)

    async def execute(arguments: dict[str, Any]) -> Outcome:  # pragma: no cover
        raise AssertionError("must not run")

    return Operation(
        name=name,
        description=name,
        request_model=Request,
        execute=execute,
        annotations=ToolAnnotations(read_only_hint=True),
        tool_class=ToolClass.READ,
        group=group,
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "present",
    [
        {"wled_list_devices"},
        {"wled_get_effects"},
        {"wled_get_palettes"},
        {"wled_get_effects", "wled_get_palettes"},
        {"wled_list_devices", "wled_get_palettes"},
    ],
)
async def test_a_resource_exists_exactly_when_its_tool_is_registered(present):
    server = create_server([tool_operation(name) for name in sorted(present)])
    absent = {name for name in MAPPING.values() if name not in present}
    async with Client(server) as client:
        resources, templates = await resource_surface(client)
        assert (DEVICES in resources) == ("wled_list_devices" in present)
        assert (TEMPLATES[0] in templates) == ("wled_get_effects" in present)
        assert (TEMPLATES[1] in templates) == ("wled_get_palettes" in present)
        for uri, tool in MAPPING.items():
            if tool in absent:
                error = await read_error(client, uri)
                assert (error.code, error.message) == (-32002, "Resource not found")
                assert "wled_" not in str(error.error.model_dump())


@pytest.mark.anyio
async def test_no_registered_tool_means_no_resources_capability():
    server = create_server([tool_operation("wled_get_state")])
    async with Client(server) as client:
        capabilities = client.session.server_capabilities
        assert capabilities is not None and capabilities.resources is None
        assert [t.name for t in (await client.list_tools()).tools] == ["wled_get_state"]
        assert (await read_error(client, DEVICES)).code in (-32601, -32602, -32002)
    empty = create_server()
    async with Client(empty) as client:
        capabilities = client.session.server_capabilities
        assert capabilities is not None and capabilities.resources is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("profile", "groups"),
    [("read-only", ["core"]), ("control", ["core", "presets"]), ("full", None)],
)
async def test_real_registry_matrix_follows_the_read_tools(tmp_path, profile, groups):
    server, _resources, _router = served(tmp_path, profile, groups)
    names = expected_names_in(profile, groups or ["core"]) if groups else expected_names(profile)
    group_of = {t.name: t.group for t in EXPECTED_TOOLS}
    assert {n for n in MAPPING.values() if n in names} == set(MAPPING.values())
    assert all(group_of[n] == "core" for n in MAPPING.values())
    async with Client(server) as client:
        assert await resource_surface(client) == ([DEVICES], TEMPLATES)
        for uri in MAPPING:
            assert body_of(await client.read_resource(uri))["ok"] is True


@pytest.mark.anyio
async def test_a_ceiling_capped_device_stays_readable(tmp_path):
    server, _resources, router = served(tmp_path, "full", None, desk="read")
    async with Client(server) as client:
        assert body_of(await client.read_resource(EFFECTS))["ok"] is True
    assert router.posts == []


# ------------------------------------------------------------------ AC-258-04 error parity


@pytest.mark.anyio
async def test_unknown_controller_returns_the_tools_error_object(tmp_path):
    server, _resources, router = served(tmp_path)
    async with Client(server) as client:
        tool = await client.call_tool("wled_get_effects", {"device_id": "nobody"})
        assert tool.structured_content is not None
        expected = tool.structured_content["error"]
        for uri in (
            "wled://devices/nobody/effects",
            "wled://devices/nobody/palettes",
            "wled://devices/UPPER/effects",
            "wled://devices/" + "a" * 65 + "/effects",
        ):
            error = await read_error(client, uri)
            assert error.code == -32603
            assert error.message == expected["message"]
            assert error.error.data["error"] == expected
            assert error.error.data["ok"] is False and error.error.data["device_id"] is None
            # The requested controller segment must never be echoed (strict for every URI).
            segment = uri.split("/")[3]
            assert segment not in json.dumps(error.error.data)
    assert router.calls == []


@pytest.mark.anyio
async def test_an_unreachable_controller_returns_the_tools_error_object(tmp_path):
    server, _resources, router = served(tmp_path)
    router.set("desk.invalid", "/json/eff", httpx.Response(500, json={}))
    async with Client(server) as client:
        tool = await client.call_tool("wled_get_effects", {"device_id": "desk"})
        assert tool.is_error and tool.structured_content is not None
        expected = tool.structured_content["error"]
        error = await read_error(client, EFFECTS)
    assert error.error.data["error"] == expected
    assert error.error.data["device_id"] == "desk"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "uri",
    [
        "wled://devices?x=1",
        "wled://devices#frag",
        "wled://devices/desk/effects?refresh=true",
        "wled://devices/desk/effects#x",
        "wled://devices/desk",
        "wled://devices/desk/state",
        "wled://devices/de%73k/effects",
        "wled://devices/a/b/effects",
        "wled://devices/",
        "wled://other",
        "https://example.invalid/effects",
    ],
)
async def test_malformed_or_foreign_uris_get_the_fixed_not_found_error(tmp_path, uri):
    server, _resources, router = served(tmp_path)
    async with Client(server) as client:
        error = await read_error(client, uri)
    assert (error.code, error.message) == (-32002, "Resource not found")
    assert error.error.data is None
    assert router.calls == []


# ------------------------------------------------- AC-258-05 redaction, AC-258-06 read-only


@pytest.mark.anyio
async def test_bodies_errors_and_logs_leak_no_address_or_path(tmp_path, caplog):
    server, _resources, router = served(tmp_path)
    router.set("lamp.invalid", "/json/pal", httpx.Response(500, json={}))
    caplog.set_level(logging.DEBUG, logger="wled_mcp")
    seen: list[str] = []
    async with Client(server) as client:
        for uri in (DEVICES, EFFECTS, PALETTES, "wled://devices/shelf/palettes"):
            seen.append(text_of(await client.read_resource(uri)))
        for uri in ("wled://devices/lamp/palettes", "wled://devices/nobody/effects", "wled://x"):
            seen.append(json.dumps((await read_error(client, uri)).error.model_dump()))
    joined = "\n".join(seen) + "\n" + caplog.text
    for secret in (*HOSTS.values(), str(tmp_path), "http://"):
        assert secret not in joined


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("uri", "kind"), [(DEVICES, "devices"), (EFFECTS, "effects"), (PALETTES, "palettes")]
)
async def test_an_unexpected_exception_logs_only_class_and_kind(uri, kind, caplog, capsys):
    secret = "synthetic-secret-token-in-exception"

    async def explode(arguments: dict[str, Any]) -> Outcome:
        raise RuntimeError(f"http://{secret}.invalid/json?token={secret} desk")

    class Request(BaseModel):
        model_config = ConfigDict(extra="forbid", strict=True)
        device_id: str | None = None

    operation = tool_operation(MAPPING[uri])
    operation = Operation(
        name=operation.name,
        description=operation.description,
        request_model=Request,
        execute=explode,
        annotations=operation.annotations,
        tool_class=operation.tool_class,
        group=operation.group,
    )
    server = create_server([operation])
    caplog.set_level(logging.DEBUG, logger="wled_mcp")
    async with Client(server) as client:
        error = await read_error(client, uri)
    assert (error.code, error.message) == (-32603, "Internal resource failure")
    records = [r for r in caplog.records if r.name == "wled_mcp.catalog_resources"]
    assert len(records) == 1 and records[0].levelno == logging.WARNING
    line = records[0].getMessage()
    assert "RuntimeError" in line and kind in line
    everything = caplog.text + json.dumps(error.error.model_dump(), default=str) + str(error)
    for hidden in (secret, "desk", "http://", "wled://"):
        assert hidden not in everything
    captured = capsys.readouterr()
    assert captured.out == ""


@pytest.mark.anyio
async def test_reads_write_nothing_and_run_no_discovery(tmp_path):
    server, _resources, router = served(tmp_path)
    async with Client(server) as client:
        for uri in (DEVICES, EFFECTS, PALETTES):
            await client.read_resource(uri)
    assert router.posts == []
    assert {method for method, _host, _path in router.calls} <= {"GET"}
    assert {path for _method, _host, path in router.calls} <= {
        "/json/eff",
        "/json/pal",
        "/json/info",
        "/json/fxdata",
    }
    assert list(tmp_path.glob("*.toml")) == []


# ------------------------------------------------------------------ AC-258-09 tools unchanged


@pytest.mark.anyio
async def test_resources_leave_instructions_without_a_mention(tmp_path):
    server, _resources, _router = served(tmp_path)
    async with Client(server) as client:
        assert "wled://" not in (client.instructions or "")
        for tool in (await client.list_tools()).tools:
            assert "wled://" not in (tool.description or "")
