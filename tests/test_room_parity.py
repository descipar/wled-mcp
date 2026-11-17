"""Issue #183: the room tools over stdio and Streamable HTTP (AC-183-23).

The installed console serves a synthetic three-device inventory (``desk`` and ``lamp``
unrestricted, ``shelf`` capped at ``read``) in the ``full`` profile (a room is defined by a
manage tool), once over stdio and once over loopback HTTP, each with its own data
directory. The ordered steps (save rooms, a refused conflict, listings, a dry run, strict and
best-effort applies including a lost write, a plain group and a scene) must return identical
envelopes on both transports. Only ``127.0.0.1`` loopback fakes are contacted.
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

STATE = {"on": True, "brightness": 40}
SCENE = {
    "format": "wled-mcp.scene",
    "format_version": 1,
    "id": "bright",
    "name": "Bright",
    "targets": [{"device": "desk", "master": {"on": True, "brightness": 80}}],
}


def save(group_id: str, *devices: str, kind: str = "room") -> dict[str, Any]:
    return {
        "group_id": group_id,
        "name": f"Group {group_id}",
        "members": [{"device": device} for device in devices],
        "kind": kind,
    }


# step -> (tool, arguments, expected ok, POSTs to desk, shelf, lamp, desk mode)
Step = tuple[str, dict[str, Any], bool, int, int, int, str]
STEPS: dict[str, Step] = {
    "save_pair": ("wled_save_group", save("pair", "desk", "shelf"), True, 0, 0, 0, "apply"),
    "save_solo": ("wled_save_group", save("solo", "lamp"), True, 0, 0, 0, "apply"),
    "save_floor_is_a_plain_group": (
        "wled_save_group",
        save("floor", "desk", kind="group"),
        True,
        0,
        0,
        0,
        "apply",
    ),
    "save_conflicting_room": ("wled_save_group", save("clash", "desk"), False, 0, 0, 0, "apply"),
    "save_scene": ("wled_save_scene", {"scene": SCENE}, True, 0, 0, 0, "apply"),
    "list_groups": ("wled_list_groups", {}, True, 0, 0, 0, "apply"),
    "list_devices": ("wled_list_devices", {}, True, 0, 0, 0, "apply"),
    "dry_run_shows_the_capped_member": (
        "wled_apply_room",
        {"room": "pair", "state": STATE, "dry_run": True},
        False,
        0,
        0,
        0,
        "apply",
    ),
    "strict_apply_is_refused_as_a_whole": (
        "wled_apply_room",
        {"room": "pair", "state": STATE},
        False,
        0,
        0,
        0,
        "apply",
    ),
    "best_effort_partial_failure": (
        "wled_apply_room",
        {"room": "pair", "state": STATE, "mode": "best_effort"},
        False,
        1,
        0,
        0,
        "apply",
    ),
    "best_effort_with_a_lost_write": (
        "wled_apply_room",
        {"room": "pair", "state": STATE, "mode": "best_effort"},
        False,
        1,
        0,
        0,
        "reset",
    ),
    "single_member_room_succeeds": (
        "wled_apply_room",
        {"room": "solo", "state": STATE},
        True,
        0,
        0,
        1,
        "apply",
    ),
    "plain_group_is_not_a_room": (
        "wled_apply_room",
        {"room": "floor", "state": STATE},
        False,
        0,
        0,
        0,
        "apply",
    ),
    "scene_outside_the_room_is_refused": (
        "wled_apply_room",
        {"room": "solo", "scene_id": "bright"},
        False,
        0,
        0,
        0,
        "apply",
    ),
    "scene_inside_the_room_best_effort": (
        "wled_apply_room",
        {"room": "pair", "scene_id": "bright", "mode": "best_effort"},
        True,
        1,
        0,
        0,
        "apply",
    ),
}


async def run_steps(
    client: Client, desk: LoopbackWLED, shelf: LoopbackWLED, lamp: LoopbackWLED
) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for name, (tool, arguments, ok, desk_posts, shelf_posts, lamp_posts, mode) in STEPS.items():
        for fake in (desk, shelf, lamp):
            fake.reset("apply")
        desk.reset(mode)  # type: ignore[arg-type]
        result = await client.call_tool(tool, arguments)
        assert result.structured_content is not None, name
        envelope = strip_correlation_id(json.loads(json.dumps(result.structured_content)))
        assert envelope["ok"] is ok and result.is_error is (not ok), (name, envelope["error"])
        assert (desk.count("POST"), shelf.count("POST"), lamp.count("POST")) == (
            desk_posts,
            shelf_posts,
            lamp_posts,
        ), name
        records[name] = envelope
    return records


@pytest.fixture(scope="module")
def fakes() -> Iterator[tuple[LoopbackWLED, LoopbackWLED, LoopbackWLED]]:
    desk, shelf, lamp = LoopbackWLED(), LoopbackWLED(), LoopbackWLED()
    try:
        yield desk, shelf, lamp
    finally:
        for fake in (desk, shelf, lamp):
            fake.close()


@pytest.fixture(scope="module")
def outcomes(
    tmp_path_factory: pytest.TempPathFactory,
    fakes: tuple[LoopbackWLED, LoopbackWLED, LoopbackWLED],
) -> dict[str, dict[str, dict[str, Any]]]:
    desk, shelf, lamp = fakes
    inventory = {"desk": (desk, None), "shelf": (shelf, "read"), "lamp": (lamp, None)}
    access = '[access]\nprofile = "full"\n'

    async def over_stdio(config: Path, data: Path) -> dict[str, dict[str, Any]]:
        with anyio.fail_after(120):
            async with Client(
                stdio_params(config, data), mode="legacy", read_timeout_seconds=30
            ) as client:
                return await run_steps(client, desk, shelf, lamp)

    async def over_http(port: int) -> dict[str, dict[str, Any]]:
        with anyio.fail_after(120):
            async with http_client(port) as client:
                return await run_steps(client, desk, shelf, lamp)

    stdio_dir = tmp_path_factory.mktemp("room-stdio")
    stdio = anyio.run(over_stdio, write_fleet(stdio_dir, inventory, access), stdio_dir)
    http_dir = tmp_path_factory.mktemp("room-http")
    config = write_fleet(http_dir, inventory, access)
    port = free_port()
    env = clean_env(WLED_MCP_HTTP_TOKEN=TOKEN)
    with console(config, http_dir, *http_arguments(port, "--profile", "full"), env=env) as (
        process,
        lines,
    ):
        wait_ready(lines, port)
        http = anyio.run(over_http, port)
        assert process.poll() is None
    return {"stdio": stdio, "http": http}


def test_both_transports_return_identical_envelopes_for_every_step(outcomes):
    assert outcomes["stdio"] == outcomes["http"]


def test_the_room_results_have_the_same_meaning_on_both_transports(outcomes):
    for transport in ("stdio", "http"):
        steps = outcomes[transport]
        assert steps["save_conflicting_room"]["error"]["code"] == "VALIDATION_ERROR"
        listed = {d["id"]: d["room"] for d in steps["list_devices"]["data"]["devices"]}
        assert listed == {"desk": "pair", "shelf": "pair", "lamp": "solo"}
        assert steps["dry_run_shows_the_capped_member"]["dry_run"] is True
        assert steps["strict_apply_is_refused_as_a_whole"]["error"]["code"] == "ACCESS_DENIED"
        partial = steps["best_effort_partial_failure"]
        assert partial["error"]["code"] == "VERIFICATION_MISMATCH"
        assert (partial["application"], partial["verification"]) == ("applied", "mismatch")
        lost = steps["best_effort_with_a_lost_write"]
        assert lost["error"]["code"] == "WRITE_OUTCOME_UNKNOWN"
        assert lost["application"] == "unknown"
        assert "is a group, not a room" in steps["plain_group_is_not_a_room"]["error"]["message"]
        refused = steps["scene_outside_the_room_is_refused"]["data"]["problems"][0]
        assert refused["reason"] == "device_outside_room"
        inside = steps["scene_inside_the_room_best_effort"]["data"]
        assert inside["members_not_targeted"] == ["shelf"]
