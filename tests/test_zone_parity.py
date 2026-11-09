"""Issue #27: zone restrictions on resolved targets over stdio and Streamable HTTP.

The installed console serves a synthetic two-device inventory (``desk`` capped at ``read``,
``shelf`` unrestricted) in the ``control`` profile, once over stdio and once over loopback
HTTP, each with its own data directory holding the same zone files. The ordered steps must
return identical envelopes on both transports. Only ``127.0.0.1`` loopback fakes are
contacted. The profile-level registration (read-only profile serves the list and plan tools
but not the apply) is covered for both transports by the registry-driven tests in
``tests/test_access_profiles.py``.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import anyio
import pytest
from mcp.client import Client

from tests.acceptance_support import LoopbackWLED
from tests.envelopes import strip_correlation_id
from tests.test_access_profiles import http_arguments, http_client, stdio_params, write_fleet
from tests.test_http_cli import TOKEN, clean_env, console, free_port, wait_ready

PAIR = {
    "format": "wled-mcp.zone",
    "format_version": 1,
    "id": "pair",
    "name": "Desk and shelf pair",
    "parts": [
        {"device": "desk", "led_count": 90, "spans": [{"start": 0, "stop": 30}]},
        {"device": "shelf", "led_count": 90, "spans": [{"start": 30, "stop": 60, "segment": 2}]},
    ],
}
STALE = {
    **PAIR,
    "id": "stale",
    "name": "Stale",
    "parts": [{"device": "shelf", "led_count": 120, "spans": [{"start": 0, "stop": 30}]}],
}
CROSSING = {
    **PAIR,
    "id": "crossing",
    "name": "Crossing",
    "parts": [{"device": "shelf", "led_count": 90, "spans": [{"start": 10, "stop": 40}]}],
}
FIELDS = [{"brightness": 33}]

# step -> (tool, arguments, expected ok, expected POSTs to desk, expected POSTs to shelf)
STEPS: dict[str, tuple[str, dict[str, Any], bool, int, int]] = {
    "list": ("wled_list_zones", {}, True, 0, 0),
    "plan_read_capped_device_still_previews": (
        "wled_plan_zone",
        {"zone": "pair", "segments": FIELDS},
        True,
        0,
        0,
    ),
    "plan_by_name": ("wled_plan_zone", {"zone": "desk and shelf pair"}, True, 0, 0),
    "apply_denied_strict": ("wled_apply_zone", {"zone": "pair", "segments": FIELDS}, False, 0, 0),
    "apply_denied_dry_run": (
        "wled_apply_zone",
        {"zone": "pair", "segments": FIELDS, "dry_run": True},
        False,
        0,
        0,
    ),
    "stale_topology": ("wled_apply_zone", {"zone": "stale", "segments": FIELDS}, False, 0, 0),
    "boundary_crossing": (
        "wled_apply_zone",
        {"zone": "crossing", "segments": FIELDS},
        False,
        0,
        0,
    ),
    "apply_master_state_is_not_a_field": (
        "wled_apply_zone",
        {"zone": "pair", "segments": [{"on": True}], "brightness": 5},
        False,
        0,
        0,
    ),
    "apply_best_effort_writes_only_the_permitted_device": (
        "wled_apply_zone",
        {"zone": "pair", "segments": FIELDS, "mode": "best_effort"},
        False,
        0,
        1,
    ),
}


def write_zones(directory: Path) -> None:
    (directory / "zones").mkdir(exist_ok=True)
    for document in (PAIR, STALE, CROSSING):
        (directory / "zones" / f"{document['id']}.json").write_text(
            json.dumps(document), encoding="utf-8"
        )


async def run_steps(
    client: Client, desk: LoopbackWLED, shelf: LoopbackWLED
) -> dict[str, dict[str, Any]]:
    desk.reset()
    shelf.reset()
    records: dict[str, dict[str, Any]] = {}
    for name, (tool, arguments, ok, desk_posts, shelf_posts) in STEPS.items():
        before = desk.count("POST"), shelf.count("POST")
        result = await client.call_tool(tool, arguments)
        assert result.structured_content is not None, name
        envelope = strip_correlation_id(json.loads(json.dumps(result.structured_content)))
        assert envelope["ok"] is ok and result.is_error is (not ok), name
        assert (desk.count("POST") - before[0], shelf.count("POST") - before[1]) == (
            desk_posts,
            shelf_posts,
        ), name
        records[name] = envelope
    return records


@pytest.fixture(scope="module")
def fakes() -> Iterator[tuple[LoopbackWLED, LoopbackWLED]]:
    desk, shelf = LoopbackWLED(), LoopbackWLED()
    try:
        yield desk, shelf
    finally:
        desk.close()
        shelf.close()


@pytest.fixture(scope="module")
def outcomes(
    tmp_path_factory: pytest.TempPathFactory, fakes: tuple[LoopbackWLED, LoopbackWLED]
) -> dict[str, dict[str, dict[str, Any]]]:
    desk, shelf = fakes
    inventory = {"desk": (desk, "read"), "shelf": (shelf, None)}
    access = '[access]\nprofile = "control"\n'

    async def over_stdio(config: Path, data: Path) -> dict[str, dict[str, Any]]:
        with anyio.fail_after(120):
            async with Client(
                stdio_params(config, data), mode="legacy", read_timeout_seconds=30
            ) as client:
                return await run_steps(client, desk, shelf)

    async def over_http(port: int) -> dict[str, dict[str, Any]]:
        with anyio.fail_after(120):
            async with http_client(port) as client:
                return await run_steps(client, desk, shelf)

    stdio_dir = tmp_path_factory.mktemp("zone-stdio")
    write_zones(stdio_dir)
    stdio = anyio.run(over_stdio, write_fleet(stdio_dir, inventory, access), stdio_dir)
    http_dir = tmp_path_factory.mktemp("zone-http")
    write_zones(http_dir)
    config = write_fleet(http_dir, inventory, access)
    port = free_port()
    env = clean_env(WLED_MCP_HTTP_TOKEN=TOKEN)
    with console(config, http_dir, *http_arguments(port, "--profile", "control"), env=env) as (
        process,
        lines,
    ):
        wait_ready(lines, port)
        http = anyio.run(over_http, port)
        assert process.poll() is None
    return {"stdio": stdio, "http": http}


def test_both_transports_return_identical_envelopes_for_every_step(outcomes):
    assert outcomes["stdio"] == outcomes["http"]


def test_the_ceiling_and_the_resolution_refusals_have_the_same_codes_on_both_transports(outcomes):
    for transport in ("stdio", "http"):
        steps = outcomes[transport]
        assert steps["apply_denied_strict"]["error"]["code"] == "ACCESS_DENIED"
        assert steps["apply_denied_dry_run"]["error"]["code"] == "ACCESS_DENIED"
        assert steps["stale_topology"]["error"]["code"] == "VALIDATION_ERROR"
        assert steps["boundary_crossing"]["error"]["code"] == "VALIDATION_ERROR"
        best = steps["apply_best_effort_writes_only_the_permitted_device"]
        assert best["error"]["code"] == "VERIFICATION_MISMATCH"
        entries = {d["device_id"]: d for d in best["data"]["devices"]}
        assert entries["desk"]["error"]["code"] == "ACCESS_DENIED"
        assert entries["shelf"]["ok"] is True
        plan = steps["plan_read_capped_device_still_previews"]
        assert [t["device_id"] for t in plan["data"]["targets"]] == ["desk", "shelf"]
