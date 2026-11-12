"""Signal tools (issue #28): schemas, dry run, access context, both transports.

Mock controllers, a controlled clock and loopback only; nothing contacts a LAN device. Scenario
IDs T28-xx are those of docs/validation/issue-28.md.
"""

from __future__ import annotations

import json
from typing import Any

import anyio
import pytest
from mcp import MCPError
from mcp.client import Client
from pydantic import ValidationError

from tests.http_support import running_service, sdk_client
from tests.signal_support import (
    BASE_COLOR,
    SOLID,
    WIPE,
    FakeController,
    Fleet,
    ManualTimer,
    host_of,
    make_env,
    signal_env,
)
from tests.state_catalog_support import FakeClock
from wled_mcp.server import create_server
from wled_mcp.signal_tools import (
    CancelSignalRequest,
    GetSignalStatusRequest,
    StartSignalRequest,
)

START = {"device_id": "desk", "segment_ids": [0], "color": [255, 0, 0], "duration_seconds": 10}
SIGNAL_TOOLS = ("wled_start_signal", "wled_get_signal_status", "wled_cancel_signal")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


# ------------------------------------------------------------------ T28-14 contract surface


@pytest.mark.parametrize(
    "arguments",
    [
        {**START, "duration_seconds": 0},
        {**START, "duration_seconds": 301},
        {**START, "segment_ids": []},
        {**START, "segment_ids": list(range(17))},
        {**START, "segment_ids": [0, 0]},
        {**START, "segment_ids": [-1]},
        {**START, "color": [255, 0]},
        {**START, "color": [255, 0, 256]},
        {**START, "color": [True, 0, 0]},
        {**START, "colour": [1, 2, 3]},
    ],
)
def test_the_start_schema_enforces_every_bound(arguments):
    with pytest.raises(ValidationError):
        StartSignalRequest.model_validate(arguments)
    assert StartSignalRequest.model_validate(START).dry_run is False
    for model in (GetSignalStatusRequest, CancelSignalRequest):
        with pytest.raises(ValidationError):
            model.model_validate({"operation_id": "sig-NOT-HEX-0123456"})


@pytest.mark.anyio
async def test_descriptions_state_the_limits_and_every_property_is_described(tmp_path):
    env = make_env(tmp_path)
    tools = {name: env.operations[name] for name in SIGNAL_TOOLS}
    for operation in tools.values():
        schema = operation.request_model.model_json_schema()
        for model in [schema, *schema.get("$defs", {}).values()]:
            for name, prop in model.get("properties", {}).items():
                assert prop.get("description"), (operation.name, name)
        assert operation.annotations.destructive_hint is False
    for name in ("wled_start_signal", "wled_cancel_signal"):
        text = tools[name].description.lower()
        assert "best effort" in text and "never replayed" in text and "restore" in text
    start = tools["wled_start_signal"].description.lower()
    assert "not a scheduler" in start and "memory" in start and "only if they still hold" in start
    assert "does not contact any device" in tools["wled_get_signal_status"].description


# ------------------------------------------------------------------------- T28-01 dry run


@pytest.mark.anyio
async def test_dry_run_returns_the_real_plan_and_reserves_nothing(tmp_path):
    async with signal_env(tmp_path) as env:
        dry = await env.start(dry_run=True)
        assert dry.ok and dry.dry_run and dry.application == "not_attempted"
        assert not env.ctl.posts and env.signals.listing() == []
        assert "operation_id" not in dry.data and dry.data["owned"]
        assert dry.data["restoration_plan"][0]["restore_to"] is False  # type: ignore[index]

        real = await env.start()
        assert real.data["plan"]["payload"] == dry.data["plan"]["payload"]  # type: ignore[index]
        assert real.data["owned"] == dry.data["owned"]
        assert env.ctl.posts == [dry.data["plan"]["payload"]]  # type: ignore[index]

        # A dry run refuses what a start would refuse, as an ordinary error envelope.
        blocked = await env.start(dry_run=True)
        assert not blocked.ok and blocked.dry_run and blocked.data["reason"] == "signal_active"
        assert blocked.data["active_operation_id"] == real.data["operation_id"]
        env.ctl.edit(pl=1)
        await env.call("wled_cancel_signal", operation_id=real.data["operation_id"])
        refused = await env.start(dry_run=True)
        assert refused.data["reason"] == "playlist_active" and len(env.ctl.posts) == 1


# ------------------------------------------------------ T28-12 profiles and device ceilings


@pytest.mark.anyio
async def test_profiles_and_ceilings_gate_start_and_cancel_but_not_the_status(tmp_path):
    controllers = {host_of("desk"): FakeController(), host_of("shelf"): FakeController()}
    env = make_env(
        tmp_path,
        controllers,
        device_ids=("desk", "shelf"),
        profile="full",
        caps={"desk": "read"},
    )
    server = create_server(list(env.operations.values()), env.resources.access)
    async with env.resources, Client(server) as client:
        for dry_run in (False, True):
            denied = await client.call_tool("wled_start_signal", {**START, "dry_run": dry_run})
            envelope = denied.structured_content
            assert envelope is not None and envelope["error"]["code"] == "ACCESS_DENIED"
            assert envelope["application"] == "not_attempted" and envelope["dry_run"] is dry_run
        status = await client.call_tool("wled_get_signal_status", {})
        assert status.structured_content is not None and status.structured_content["ok"]
        allowed = await client.call_tool("wled_start_signal", {**START, "device_id": "shelf"})
        assert allowed.structured_content is not None and allowed.structured_content["ok"]
        assert not controllers[host_of("desk")].post_attempts

    read_only = make_env(tmp_path / "ro", device_ids=("desk",), profile="read-only")
    server = create_server(list(read_only.operations.values()), read_only.resources.access)
    async with read_only.resources, Client(server) as client:
        names = [tool.name for tool in (await client.list_tools()).tools]
        assert "wled_get_signal_status" in names
        assert not {"wled_start_signal", "wled_cancel_signal"} & set(names)
        for name in ("wled_start_signal", "wled_cancel_signal"):
            with pytest.raises(MCPError) as caught:
                await client.call_tool(name, {})
            assert caught.value.message == "Unknown tool"


# -------------------------------------------------- T28-15 both transports share one manager


def masked(envelope: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(envelope)
    for key in ("correlation_id", "operation_id", "started_at", "expires_at", "ended_at"):
        text = _mask(text, key)
    return json.loads(text)  # type: ignore[no-any-return]


def _mask(text: str, key: str) -> str:
    import re

    return re.sub(rf'"{key}": ?"[^"]*"', f'"{key}": "<{key}>"', text)


@pytest.mark.anyio
async def test_in_process_and_loopback_http_share_the_manager_and_survive_a_dropped_client(
    tmp_path,
):
    clock = FakeClock()
    controller = FakeController()
    fleet = Fleet({host_of("desk"): controller, host_of("shelf"): FakeController()})
    with anyio.fail_after(60):
        async with running_service(tmp_path, fleet, clock=clock) as run:  # type: ignore[arg-type]
            timer = ManualTimer(clock)
            run.resources.signals.sleep_until = timer.sleep_until
            async with Client(run.server) as local, sdk_client(run) as remote:
                # One tool list, one schema set, whichever transport serves it.
                listed = [(await c.list_tools()).tools for c in (local, remote)]
                assert [t.model_dump() for t in listed[0]] == [t.model_dump() for t in listed[1]]
                assert set(SIGNAL_TOOLS) <= {t.name for t in listed[0]}

                started = await remote.call_tool("wled_start_signal", START)
                assert started.structured_content is not None and started.structured_content["ok"]
                identifier = started.structured_content["data"]["operation_id"]
                assert started.is_error is False and json.loads(started.content[0].text) == (
                    started.structured_content
                )
            # The first HTTP client is gone: that is not a write, not a cancel, not a restore.
            assert len(controller.posts) == 1 and controller.segment(0)["fx"] == SOLID

            async with sdk_client(run) as other, Client(run.server) as local:
                for client in (other, local):
                    status = await client.call_tool(
                        "wled_get_signal_status", {"operation_id": identifier}
                    )
                    assert status.structured_content is not None
                    assert status.structured_content["data"]["signal"]["status"] == "active"
                timer.advance(10)
                with anyio.fail_after(10):
                    await run.resources.signals.get(identifier).done.wait()
                final = await other.call_tool(
                    "wled_get_signal_status", {"operation_id": identifier}
                )
                assert final.structured_content is not None
                assert final.structured_content["data"]["signal"]["status"] == "restored"
                assert len(controller.posts) == 2
                assert controller.segment(0)["fx"] == WIPE
                assert controller.segment(0)["col"][0] == BASE_COLOR
                # Both transports reach the same record, and so the same envelope.
                via_http = await other.call_tool(
                    "wled_get_signal_status", {"operation_id": identifier}
                )
                via_local = await local.call_tool(
                    "wled_get_signal_status", {"operation_id": identifier}
                )
                assert masked(via_http.structured_content or {}) == masked(
                    via_local.structured_content or {}
                )
