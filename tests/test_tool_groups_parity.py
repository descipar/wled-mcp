"""Issue #236: stdio and Streamable HTTP serve the same tools for the same selection (AC-236-06).

The installed console runs once per transport with profile ``control`` and groups ``core,presets``
against synthetic loopback fakes; names, schemas and the unknown-tool behavior must match each
other and the expectation of tests/tool_contract.py.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import anyio
import pytest
from mcp.client import Client
from mcp.shared.exceptions import MCPError

from tests.acceptance_support import LoopbackWLED
from tests.test_access_profiles import (
    http_arguments,
    http_client,
    listed_names,
    stdio_params,
    write_fleet,
)
from tests.test_http_cli import TOKEN, clean_env, console, free_port, wait_ready
from tests.tool_contract import expected_names_in

PROFILE = "control"
GROUPS = ["core", "presets"]


@pytest.fixture
def fakes() -> Iterator[list[LoopbackWLED]]:
    devices = [LoopbackWLED()]
    try:
        yield devices
    finally:
        for device in devices:
            device.close()


async def observe(client: Client, fake: LoopbackWLED) -> dict[str, Any]:
    tools = {t.name: t.model_dump() for t in (await client.list_tools()).tools}
    before = fake.count()
    errors = set()
    for name in ("wled_apply_room", "wled_replace_layout", "wled_absent"):
        with pytest.raises(MCPError) as caught:
            await client.call_tool(name, {"device_id": "desk"})
        errors.add((caught.value.code, caught.value.message))
    assert fake.count() == before
    status = await client.call_tool("wled_get_service_status", {})
    assert status.structured_content is not None
    groups = status.structured_content["data"]["access"]["tool_groups"]
    return {"tools": tools, "errors": errors, "groups": groups, "instructions": client.instructions}


def test_stdio_and_http_serve_the_same_tools_for_the_same_groups(tmp_path, fakes):
    config = write_fleet(tmp_path, {"desk": (fakes[0], None)})
    options = ("--profile", PROFILE, "--tool-groups", ",".join(GROUPS))

    async def over_stdio() -> dict[str, Any]:
        with anyio.fail_after(90):
            async with Client(
                stdio_params(config, tmp_path, *options), mode="legacy", read_timeout_seconds=30
            ) as client:
                assert await listed_names(client) == expected_names_in(PROFILE, GROUPS)
                return await observe(client, fakes[0])

    async def over_http(port: int) -> dict[str, Any]:
        with anyio.fail_after(90):
            async with http_client(port) as client:
                assert await listed_names(client) == expected_names_in(PROFILE, GROUPS)
                return await observe(client, fakes[0])

    stdio = anyio.run(over_stdio)
    port = free_port()
    env = clean_env(WLED_MCP_HTTP_TOKEN=TOKEN)
    with console(config, tmp_path, *http_arguments(port, *options), env=env) as (process, lines):
        wait_ready(lines, port)
        http = anyio.run(over_http, port)
        assert process.poll() is None
    assert stdio == http
    assert stdio["errors"] == {(-32602, "Unknown tool")}
    assert stdio["groups"] == ["core", "presets"]
    assert "wled_replace_layout" not in stdio["instructions"]
