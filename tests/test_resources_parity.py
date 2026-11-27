"""Issue #258: stdio and Streamable HTTP serve the same catalog resources (AC-258-07, MCPRES-06).

The installed console runs once per transport against synthetic loopback fakes; the resource
list, templates, read bodies and the error data of a failed read must match each other.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import anyio
import pytest
from mcp.client import Client
from mcp.shared.exceptions import MCPError

from tests.acceptance_support import LoopbackWLED
from tests.test_access_profiles import http_arguments, http_client, stdio_params, write_fleet
from tests.test_http_cli import TOKEN, clean_env, console, free_port, wait_ready

OPTIONS = ("--profile", "control", "--tool-groups", "core,presets")
EFFECTS = "wled://devices/desk/effects"


@pytest.fixture
def fakes() -> Iterator[list[LoopbackWLED]]:
    devices = [LoopbackWLED()]
    try:
        yield devices
    finally:
        for device in devices:
            device.close()


def stable(envelope: dict[str, Any]) -> dict[str, Any]:
    """Drop what differs per call or per process start: correlation ID and cache timestamps."""
    body = {key: value for key, value in envelope.items() if key != "correlation_id"}
    freshness = body.get("data", {}).get("freshness")
    if isinstance(freshness, dict):
        for key in ("fetched_at", "age_seconds"):
            freshness.pop(key, None)
    return body


async def observe(client: Client, fake: LoopbackWLED) -> dict[str, Any]:
    resources = [str(r.uri) for r in (await client.list_resources()).resources]
    templates = [
        t.uri_template for t in (await client.list_resource_templates()).resource_templates
    ]
    bodies = {}
    for uri in ("wled://devices", EFFECTS, "wled://devices/desk/palettes"):
        bodies[uri] = stable(json.loads((await client.read_resource(uri)).contents[0].text))
    errors = {}
    for uri in ("wled://devices/nobody/effects", "wled://devices/desk/state"):
        with pytest.raises(MCPError) as caught:
            await client.read_resource(uri)
        data = caught.value.error.data
        errors[uri] = (caught.value.code, caught.value.message, data and stable(data))
    assert [r for r in fake.requests if r[0] != "GET"] == []
    return {"resources": resources, "templates": templates, "bodies": bodies, "errors": errors}


def test_stdio_and_http_serve_the_same_resources(tmp_path, fakes):
    config = write_fleet(tmp_path, {"desk": (fakes[0], None)})

    async def over_stdio() -> dict[str, Any]:
        with anyio.fail_after(90):
            async with Client(
                stdio_params(config, tmp_path, *OPTIONS), mode="legacy", read_timeout_seconds=30
            ) as client:
                return await observe(client, fakes[0])

    async def over_http(port: int) -> dict[str, Any]:
        with anyio.fail_after(90):
            async with http_client(port) as client:
                return await observe(client, fakes[0])

    stdio = anyio.run(over_stdio)
    port = free_port()
    env = clean_env(WLED_MCP_HTTP_TOKEN=TOKEN)
    with console(config, tmp_path, *http_arguments(port, *OPTIONS), env=env) as (process, lines):
        wait_ready(lines, port)
        http = anyio.run(over_http, port)
        assert process.poll() is None
    assert stdio == http
    assert stdio["resources"] == ["wled://devices"]
    assert len(stdio["templates"]) == 2
    assert stdio["bodies"][EFFECTS]["ok"] is True
    code, _message, data = stdio["errors"]["wled://devices/nobody/effects"]
    assert (code, data["error"]["code"]) == (-32603, "UNKNOWN_DEVICE")
    assert stdio["errors"]["wled://devices/desk/state"][:2] == (-32002, "Resource not found")
