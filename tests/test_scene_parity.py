"""Issue #17 (AC-17-12): groups, scenes, the plan and the apply over stdio and HTTP.

The installed console serves the same synthetic inventory once over stdio and once over
loopback Streamable HTTP, each with its own empty data directory. The ordered steps save a
group and scenes, list, share, plan, apply and delete; every step must return identical
envelopes on both transports, ``text == structuredContent`` and ``isError == !ok``. Only the
real ``wled_apply_scene`` step sends POSTs to the loopback device (the master step and the
segment step); every other step sends none. Only ``127.0.0.1`` is contacted.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import anyio
import httpx2 as httpx
import pytest
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters
from mcp.client.streamable_http import streamable_http_client

from tests.acceptance_support import LoopbackWLED
from tests.scene_support import canonical_scene, device_target, scene_document
from tests.test_acceptance_parity import DESK, http_args, write_inventory
from tests.test_http_cli import CONSOLE, TOKEN, clean_env, console, free_port, wait_ready

SHELF = {"group_id": "shelf", "name": "Shelf", "members": [{"device": DESK, "segments": [0, 2]}]}


def evening() -> dict[str, Any]:
    document = canonical_scene()
    document["targets"] = [
        {"group": "shelf", "master": {"on": True, "brightness": 90}},
    ]
    document["targets"][0]["segments"] = [
        {"colors": [[255, 120, 20]], "effect_name": "Wipe", "palette_name": "Party", "speed": 60}
    ]
    return document


# step name -> (tool, arguments, expected ok)
STEPS: dict[str, tuple[str, dict[str, Any], bool]] = {
    "save_group": ("wled_save_group", SHELF, True),
    "list_groups": ("wled_list_groups", {}, True),
    "save_scene": ("wled_save_scene", {"scene": evening()}, True),
    "save_scene_again_conflict": ("wled_save_scene", {"scene": evening()}, False),
    "list_scenes": ("wled_list_scenes", {}, True),
    "export_scene": ("wled_list_scenes", {"scene_id": "evening", "shareable": True}, True),
    "plan_strict": ("wled_plan_scene", {"scene_id": "evening"}, True),
    "plan_best_effort": ("wled_plan_scene", {"scene_id": "evening", "mode": "best_effort"}, True),
    "apply_dry_run": ("wled_apply_scene", {"scene_id": "evening", "dry_run": True}, True),
    "apply_schema_error": ("wled_apply_scene", {"scene_id": "evening", "mode": "eager"}, False),
    "apply_missing_scene": ("wled_apply_scene", {"scene_id": "absent"}, False),
    "apply": ("wled_apply_scene", {"scene_id": "evening"}, True),
    "save_duplicate_scene": (
        "wled_save_scene",
        {
            "scene": scene_document(
                device_target(DESK), {"group": "shelf", "master": {"on": True}}, id="dup"
            )
        },
        False,
    ),
    "schema_error": ("wled_plan_scene", {"scene_id": "evening", "mode": "eager"}, False),
    "plan_missing_scene": ("wled_plan_scene", {"scene_id": "absent"}, False),
    "apply_again": ("wled_apply_scene", {"scene_id": "evening"}, True),
    "delete_scene": ("wled_delete_scene", {"scene_id": "evening"}, True),
    "delete_group": ("wled_delete_group", {"group_id": "shelf"}, True),
}


async def run_steps(client: Client, fake: LoopbackWLED) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    fake.reset()
    for name, (tool, arguments, _ok) in STEPS.items():
        result = await client.call_tool(tool, arguments)
        assert len(result.content) == 1 and result.content[0].type == "text", name
        records[name] = {
            "text": json.loads(result.content[0].text),
            "structured": result.structured_content,
            "is_error": result.is_error,
            "posts": fake.count("POST"),
        }
    return records


async def over_stdio(config: Path, data: Path, fake: LoopbackWLED) -> dict[str, dict[str, Any]]:
    params = StdioServerParameters(
        command=str(CONSOLE), cwd=data, args=["--config", str(config), "--data-dir", str(data)]
    )
    with anyio.fail_after(120):
        async with Client(params, mode="legacy", read_timeout_seconds=30) as client:
            return await run_steps(client, fake)


async def over_http(port: int, fake: LoopbackWLED) -> dict[str, dict[str, Any]]:
    with anyio.fail_after(120):
        async with httpx.AsyncClient(headers={"Authorization": f"Bearer {TOKEN}"}) as http:
            transport = streamable_http_client(
                f"http://127.0.0.1:{port}/mcp", http_client=http, terminate_on_close=False
            )
            async with Client(transport, mode="legacy", read_timeout_seconds=30) as client:
                return await run_steps(client, fake)


@pytest.fixture(scope="module")
def fake() -> Iterator[LoopbackWLED]:
    device = LoopbackWLED()
    try:
        yield device
    finally:
        device.close()


@pytest.fixture(scope="module")
def outcomes(
    tmp_path_factory: pytest.TempPathFactory, fake: LoopbackWLED
) -> dict[str, dict[str, dict[str, Any]]]:
    stdio_dir = tmp_path_factory.mktemp("scene-stdio")
    stdio = anyio.run(over_stdio, write_inventory(stdio_dir, fake), stdio_dir, fake)
    http_dir = tmp_path_factory.mktemp("scene-http")
    config = write_inventory(http_dir, fake)
    port = free_port()
    env = clean_env(WLED_MCP_HTTP_TOKEN=TOKEN)
    with console(config, http_dir, *http_args(port), env=env) as (process, lines):
        wait_ready(lines, port)
        http = anyio.run(over_http, port, fake)
        assert process.poll() is None
    return {"stdio": stdio, "http": http}


@pytest.mark.parametrize("name", list(STEPS))
@pytest.mark.parametrize("transport", ["stdio", "http"])
def test_text_equals_structured_and_is_error_equals_not_ok(outcomes, transport, name):
    record = outcomes[transport][name]
    envelope = record["structured"]
    assert envelope is not None and record["text"] == envelope
    assert record["is_error"] is (not envelope["ok"])
    assert envelope["ok"] is STEPS[name][2], envelope.get("error")


def comparable(record: dict[str, Any]) -> dict[str, Any]:
    """The one place that prepares a served result for the stdio/HTTP comparison.

    Today the envelopes are compared as they are; a field that differs per call (for
    example a correlation ID added later by #20) is stripped here and nowhere else.
    """
    return record


@pytest.mark.parametrize("name", list(STEPS))
def test_stdio_and_http_return_identical_envelopes(outcomes, name):
    assert comparable(outcomes["stdio"][name]) == comparable(outcomes["http"][name])


# The real applies send one master POST and one segment POST each; nothing else writes.
POSTS_PER_APPLY = 2
APPLY_STEPS = ("apply", "apply_again")


def expected_posts() -> dict[str, int]:
    total, expected = 0, {}
    for name in STEPS:
        total += POSTS_PER_APPLY if name in APPLY_STEPS else 0
        expected[name] = total
    return expected


@pytest.mark.parametrize("transport", ["stdio", "http"])
def test_only_the_real_applies_send_device_posts(outcomes, transport):
    expected = expected_posts()
    assert {name: record["posts"] for name, record in outcomes[transport].items()} == expected


@pytest.mark.parametrize("transport", ["stdio", "http"])
def test_the_apply_over_a_real_transport_writes_master_then_segments_and_verifies(
    outcomes, transport
):
    result = outcomes[transport]["apply"]["structured"]
    assert (result["application"], result["verification"], result["ok"]) == (
        "applied",
        "verified",
        True,
    )
    assert result["dry_run"] is False and result["device_id"] is None
    (device,) = result["data"]["devices"]
    assert device["device_id"] == DESK and device["origin"] == "group:shelf/member:1"
    assert [step["step"] for step in device["steps"]] == ["master", "segments"]
    dry = outcomes[transport]["apply_dry_run"]["structured"]
    plan = outcomes[transport]["plan_strict"]["structured"]
    assert dry["dry_run"] is True and dry["data"] == plan["data"]
    assert outcomes[transport]["apply_schema_error"]["structured"]["error"]["code"] == (
        "VALIDATION_ERROR"
    )
    assert outcomes[transport]["apply_missing_scene"]["structured"]["data"] == {}


@pytest.mark.parametrize("transport", ["stdio", "http"])
def test_the_plan_over_a_real_transport_resolves_names_and_blocks_nothing(outcomes, transport):
    plan = outcomes[transport]["plan_strict"]["structured"]
    assert plan["dry_run"] is True and plan["application"] == "not_attempted"
    (target,) = plan["data"]["targets"]
    assert target["device_id"] == DESK and target["origin"] == "group:shelf/member:1"
    assert [r["field"] for r in target["resolved"]] == ["effect", "palette"]
    assert plan["data"]["would_write"] == [DESK]
    assert outcomes[transport]["save_scene_again_conflict"]["structured"]["error"]["code"] == (
        "VALIDATION_ERROR"
    )
    assert outcomes[transport]["schema_error"]["structured"]["error"]["code"] == "VALIDATION_ERROR"
