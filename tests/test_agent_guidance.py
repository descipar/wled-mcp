"""AGENT-01/02: served guidance and nested schemas, without device access."""

import os
import sys
from pathlib import Path

import anyio
import pytest
from mcp import MCPError
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters

from tests.http_support import running_service, sdk_client
from wled_mcp.scenes import parse_scene
from wled_mcp.zone_tools import parse_fields


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def guidance(client):
    instructions = client.instructions
    assert instructions
    for fact in (
        "wled_get_state",
        "wled_patch_segments",
        "wled_replace_layout",
        "exclusive",
        "Omitted",
        "device-specific",
        "dry_run=true",
        "uncertain",
        "snapshot",
        "overwrite=true",
    ):
        assert fact in instructions
    listing = await client.list_prompts()
    assert [p.name for p in listing.prompts] == ["change_lighting_safely"]
    assert not listing.prompts[0].arguments
    prompt = await client.get_prompt("change_lighting_safely")
    assert len(prompt.messages) == 1
    assert prompt.messages[0].role == "user"
    assert prompt.messages[0].content.type == "text"
    assert "never blindly retry" in prompt.messages[0].content.text
    with pytest.raises(MCPError) as caught:
        await client.get_prompt("missing")
    assert caught.value.code == -32602
    with pytest.raises(MCPError):
        await client.get_prompt("change_lighting_safely", {"unexpected": "value"})
    tools = (await client.list_tools()).tools
    for tool in tools:
        if any(word in tool.name for word in ("segment", "layout", "scene", "zone")):
            schema = tool.input_schema
            for model in [schema, *schema.get("$defs", {}).values()]:
                for name, prop in model.get("properties", {}).items():
                    assert prop.get("description"), (tool.name, name)
                    if name in {"stop", "stop_y"}:
                        assert "exclusive" in prop["description"].lower()
        if tool.annotations.destructive_hint:
            assert "Use dry_run=true" in tool.description
            assert any(
                word in tool.description.lower()
                for word in ("remove", "delete", "replace", "overwrit")
            )
    scene_schema = next(t for t in tools if t.name == "wled_save_scene").input_schema
    scene = scene_schema["properties"]["scene"]["examples"][0]
    assert parse_scene(scene, allow_placeholders=False).id == "evening"
    for name in ("wled_plan_zone", "wled_apply_zone"):
        schema = next(t for t in tools if t.name == name).input_schema
        example = schema["properties"]["segments"]["examples"][0]
        assert parse_fields(example) == {"colors": [[255, 96, 16]], "effect_name": "Solid"}
    return instructions, listing.model_dump(), prompt.model_dump()


@pytest.mark.anyio
async def test_guidance_and_schemas_match_over_stdio_and_http(tmp_path):
    """Both actual transports serve the same static content; guidance executes no tools."""
    config = tmp_path / "devices.toml"
    config.write_text("schema_version = 1\ndevices = []\n")
    params = StdioServerParameters(
        command=str(
            Path(sys.executable).parent / ("wled-mcp.exe" if os.name == "nt" else "wled-mcp")
        ),
        args=["--config", str(config), "--data-dir", str(tmp_path)],
        cwd=Path(__file__).resolve().parents[1],
    )
    with anyio.fail_after(30):
        async with Client(params, mode="legacy", read_timeout_seconds=5) as client:
            stdio = await guidance(client)
        async with running_service(tmp_path) as run, sdk_client(run, "legacy") as client:
            http = await guidance(client)
            assert run.executions == []
            assert run.router.calls == []
    assert stdio == http
