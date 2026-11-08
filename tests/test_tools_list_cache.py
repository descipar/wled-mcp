"""#67: ``tools/list`` and the schema lookup build each JSON schema once per server.

Generating the JSON schema of a pydantic model is the dominant cost of ``tools/list``
(about 30 ms of CPU for 27 tools before the change, measured in-process). The registry never
changes after the server is created, so every schema is built on first use and reused. The
served listing must stay what a fresh generation produces.
"""

from __future__ import annotations

import pytest
from mcp.client import Client
from pydantic import BaseModel

from tests.test_access_profiles import served
from wled_mcp.models import Outcome
from wled_mcp.operations import build_operations


@pytest.mark.anyio
async def test_schemas_are_built_once_per_server(tmp_path, monkeypatch):
    server, _resources, _router = served(tmp_path)
    calls: list[str] = []
    original = BaseModel.__dict__["model_json_schema"].__func__

    def counting(cls, *args, **kwargs):
        calls.append(cls.__name__)
        return original(cls, *args, **kwargs)

    monkeypatch.setattr(BaseModel, "model_json_schema", classmethod(counting))
    async with Client(server) as client:
        first = (await client.session.list_tools()).tools
        built = len(calls)
        # One input schema per listed tool and the shared outcome schema.
        assert built == len(first) + 1
        second = (await client.session.list_tools()).tools
        result = await client.call_tool("wled_list_devices", {})
        assert result.structured_content["ok"] is True
        assert len(calls) == built, "a repeat listing or a tool call rebuilt a schema"
        assert [tool.model_dump() for tool in first] == [tool.model_dump() for tool in second]


@pytest.mark.anyio
async def test_cached_listing_equals_fresh_generation(tmp_path):
    server, resources, _router = served(tmp_path)
    async with Client(server) as client:
        listed = {tool.name: tool for tool in (await client.session.list_tools()).tools}
    operations = {operation.name: operation for operation in build_operations(resources)}
    assert list(listed) == list(operations)
    for name, operation in operations.items():
        tool = listed[name]
        assert tool.input_schema == operation.request_model.model_json_schema()
        assert tool.output_schema == Outcome.model_json_schema()
        assert tool.description == operation.description
        assert tool.annotations == operation.annotations
