"""Issue #20 PR A: tool profiles, per-device ceilings and the guard layers (S2-T02).

In-process tests use the mock fleet only. Console tests start the installed ``wled-mcp``
against synthetic loopback devices on ``127.0.0.1``; nothing contacts a LAN device.
Scenario IDs T20-xx are those of docs/validation/issue-20.md.
"""

from __future__ import annotations

import ast
import dataclasses
import json
import logging
import re
import subprocess
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import anyio
import httpx2 as httpx
import pytest
from mcp import MCPError
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters
from mcp.client.streamable_http import streamable_http_client
from pydantic import BaseModel, ConfigDict

from tests.acceptance_support import LoopbackWLED
from tests.envelopes import strip_correlation_id
from tests.patch_support import WriteRouter
from tests.preset_support import state_entry
from tests.state_catalog_support import FakeClock
from tests.test_http_cli import CONSOLE, TOKEN, clean_env, console, free_port, wait_ready
from tests.tool_contract import (
    CONTROL,
    EXPECTED_TOOLS,
    MANAGE,
    PROFILE_CLASSES,
    READ,
    expected_names,
    expected_tool,
    names_of,
)
from wled_mcp import access, cli
from wled_mcp.access import CURRENT_TOOL_CLASS, AccessPolicy, ToolClass
from wled_mcp.client import ClientFailure
from wled_mcp.config import (
    ConfigurationError,
    Device,
    HTTPSettings,
    StartupConfig,
    access_configured,
    access_facts,
    access_policy,
    load_config,
    validate_document,
)
from wled_mcp.models import Outcome
from wled_mcp.operations import build_operations
from wled_mcp.resources import OperationContext, PolledWrite, Resources, SequencePlan
from wled_mcp.server import Operation, create_server

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "wled_mcp"
HOSTS = {"desk": "desk.invalid", "shelf": "shelf.invalid", "lamp": "lamp.invalid"}
PROFILES = ("read-only", "control", "full")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


# ---------------------------------------------------------------------------- helpers


def make_config(tmp_path: Path, profile: str = "full", **caps: str) -> StartupConfig:
    devices = tuple(
        Device(
            id=identifier,
            name=f"Example {identifier}",
            base_url=f"http://{host}",
            max_class=caps.get(identifier),  # type: ignore[arg-type]
        )
        for identifier, host in HOSTS.items()
    )
    policy = AccessPolicy(
        profile,  # type: ignore[arg-type]
        {identifier: ToolClass(value) for identifier, value in caps.items()},
    )
    return StartupConfig(
        tmp_path / "config.toml",
        tmp_path,
        devices,
        HTTPSettings(operation_timeout_seconds=0.5),
        access=policy,
    )


def make_router() -> WriteRouter:
    router = WriteRouter()
    for host in HOSTS.values():
        router.device(host)
        router.set(host, "/presets.json", {"0": {}, "1": state_entry("Warm")})
    return router


def open_resources(config: StartupConfig, router: WriteRouter) -> Resources:
    resources = Resources(config, router.transport(), FakeClock().clock())
    resources.poll_interval_seconds = 0.005
    return resources


def tree(directory: Path) -> list[str]:
    return sorted(str(path.relative_to(directory)) for path in directory.rglob("*"))


def served(
    tmp_path: Path, profile: str = "full", **caps: str
) -> tuple[Any, Resources, WriteRouter]:
    config = make_config(tmp_path, profile, **caps)
    router = make_router()
    resources = open_resources(config, router)
    return create_server(build_operations(resources), config.access), resources, router


async def listed_names(client: Client) -> list[str]:
    return [tool.name for tool in (await client.list_tools()).tools]


# ----------------------------------------------------------- access.py policy arithmetic


def test_class_order_and_profile_ceilings():
    assert [c.rank for c in (ToolClass.READ, ToolClass.CONTROL, ToolClass.MANAGE)] == [0, 1, 2]
    assert [access.profile_ceiling(p) for p in PROFILES] == [
        ToolClass.READ,
        ToolClass.CONTROL,
        ToolClass.MANAGE,
    ]


def test_production_profiles_equal_the_independent_expectation_both_ways():
    # tests/tool_contract.py keeps its own stdlib-only copy (TD-20-1); neither may drift.
    assert set(access.PROFILES) == set(PROFILE_CLASSES)
    for name in PROFILES:
        assert {c.value for c in access.PROFILES[name]} == {c.value for c in PROFILE_CLASSES[name]}
    assert access.DEFAULT_PROFILE == "full"
    assert {c.value for c in ToolClass} == {c.value for c in (READ, CONTROL, MANAGE)}


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("cap", [None, "read", "control", "manage"])
def test_effective_ceiling_is_the_lower_of_profile_and_cap(profile, cap):
    policy = AccessPolicy(profile, {} if cap is None else {"desk": ToolClass(cap)})  # type: ignore[arg-type]
    expected = min(
        (access.profile_ceiling(profile), *([] if cap is None else [ToolClass(cap)])),
        key=lambda c: c.rank,
    )
    assert policy.ceiling("desk") is expected
    assert policy.ceiling("shelf") is access.profile_ceiling(profile)  # other devices unaffected
    assert policy.ceiling() is access.profile_ceiling(profile)
    for tool_class in ToolClass:
        assert policy.permits(tool_class, "desk") is (tool_class.rank <= expected.rank)


def test_default_policy_is_unrestricted_and_a_manage_cap_changes_nothing():
    assert AccessPolicy().ceiling() is ToolClass.MANAGE
    assert AccessPolicy("full", {"desk": ToolClass.MANAGE}).ceiling("desk") is ToolClass.MANAGE
    assert AccessPolicy("control").ceiling() is ToolClass.CONTROL
    assert AccessPolicy("full", {"desk": ToolClass.CONTROL}).ceiling("desk") is ToolClass.CONTROL
    assert AccessPolicy("full", {"desk": ToolClass.CONTROL}).ceiling("shelf") is ToolClass.MANAGE


def test_policy_rejects_an_unknown_profile_and_freezes_its_caps():
    with pytest.raises(ValueError, match="Unknown access profile"):
        AccessPolicy("everything")  # type: ignore[arg-type]
    caps = {"desk": ToolClass.READ}
    policy = AccessPolicy("full", caps)
    caps["desk"] = ToolClass.MANAGE  # the caller's later edit cannot widen the policy
    assert policy.ceiling("desk") is ToolClass.READ
    with pytest.raises(TypeError):
        policy.caps["desk"] = ToolClass.MANAGE  # type: ignore[index]


def test_denial_message_names_only_the_device_and_the_classes():
    text = access.denial_message("desk", ToolClass.MANAGE, ToolClass.READ)
    assert "desk" in text and "manage" in text and "read" in text
    assert "wled_" not in text


# ------------------------------------------- T20-05 class parity and fail-closed registry


def registry(tmp_path: Path) -> tuple[Operation, ...]:
    async def collect() -> tuple[Operation, ...]:
        async with open_resources(make_config(tmp_path), make_router()) as resources:
            return build_operations(resources)

    return anyio.run(collect)


def test_production_classes_equal_the_contract_classes_in_both_directions(tmp_path):
    operations = registry(tmp_path)
    actual = {op.name: op.tool_class.value for op in operations}
    expected = {tool.name: tool.tool_class.value for tool in EXPECTED_TOOLS}
    assert actual == expected
    assert [op.name for op in operations] == [tool.name for tool in EXPECTED_TOOLS]


class Empty(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


async def noop(arguments: dict[str, Any]) -> Outcome:  # pragma: no cover - never executed
    raise AssertionError


def test_an_operation_without_a_class_cannot_be_constructed():
    from mcp.types import ToolAnnotations

    with pytest.raises(TypeError, match="tool_class"):
        Operation("wled_x", "x", Empty, noop, ToolAnnotations())  # type: ignore[call-arg]


@pytest.mark.parametrize("value", ["read", "manage", None, 1])
def test_create_server_refuses_a_class_that_is_not_a_tool_class(tmp_path, value):
    operations = list(registry(tmp_path))
    bad = dataclasses.replace(operations[0], tool_class=value)
    with pytest.raises(TypeError, match="ToolClass"):
        create_server([*operations[1:], bad])


# ------------------------------------------------ T20-06 the control/manage split is pinned

# A deliberate change detector: reclassifying a tool must edit these literals (and the
# tests/tool_contract.py entry, and be a recorded decision).
CONTROL_TOOLS = frozenset(
    {
        "wled_set_state",
        "wled_patch_segments",
        "wled_replace_layout",
        "wled_activate_preset",
        # A scene has no device_id: the per-device ceiling is checked per expanded device.
        "wled_apply_scene",
    }
)
MANAGE_TOOLS = frozenset(
    {
        "wled_save_preset",
        "wled_delete_preset",
        "wled_restore_preset",
        "wled_store_preset",
        "wled_save_playlist",
        "wled_import_presets",
        # Local persistent artifacts (stored definitions) are manage as well.
        "wled_save_group",
        "wled_delete_group",
        "wled_save_scene",
        "wled_delete_scene",
    }
)
# Manage tools without a top-level device_id: only the registration filter applies to them.
LOCAL_FILE_TOOLS = frozenset(
    {"wled_save_group", "wled_delete_group", "wled_save_scene", "wled_delete_scene"}
)


def test_control_and_manage_name_sets_are_pinned():
    assert names_of(CONTROL) == CONTROL_TOOLS
    assert names_of(MANAGE) == MANAGE_TOOLS
    assert expected_tool("wled_replace_layout").tool_class is CONTROL  # ISSUE-20-DEC-001 D1
    assert expected_tool("wled_activate_preset").tool_class is CONTROL
    assert names_of(READ) | CONTROL_TOOLS | MANAGE_TOOLS == {t.name for t in EXPECTED_TOOLS}


async def run_tool(resources: Resources, name: str, **arguments: Any) -> Outcome:
    operation = {op.name: op for op in build_operations(resources)}[name]
    validated = operation.request_model.model_validate(arguments).model_dump()
    token = CURRENT_TOOL_CLASS.set(operation.tool_class)
    try:
        return await operation.execute(validated)
    finally:
        CURRENT_TOOL_CLASS.reset(token)


READ_CALLS: dict[str, dict[str, Any]] = {
    "wled_list_devices": {"probe": True},
    "wled_get_service_status": {},
    "wled_get_state": {"device_id": "desk"},
    "wled_get_effects": {"device_id": "desk"},
    "wled_get_palettes": {"device_id": "desk"},
    "wled_list_presets": {"device_id": "desk"},
    "wled_get_preset": {"device_id": "desk", "preset_id": 1},
    "wled_list_snapshots": {"device_id": "desk"},
    "wled_export_presets": {"device_id": "desk"},
    "wled_list_groups": {},
    "wled_list_scenes": {},
    "wled_plan_scene": {"scene_id": "evening"},
}
NEEDS_A_STORED_SCENE = {"wled_plan_scene"}  # refused without one, still a read
CONTROL_CALLS: dict[str, dict[str, Any]] = {
    "wled_set_state": {"device_id": "desk", "on": False},
    "wled_patch_segments": {"device_id": "desk", "segments": [{"id": 0, "brightness": 40}]},
    "wled_replace_layout": {
        "device_id": "desk",
        "segments": [{"id": 0, "start": 0, "stop": 20}],
    },
    "wled_activate_preset": {"device_id": "desk", "preset_id": 1},
    # Refused without a stored scene (the scene tests apply one); it never writes then.
    "wled_apply_scene": {"scene_id": "evening"},
}


def test_the_behavior_check_covers_every_read_and_control_tool():
    assert set(READ_CALLS) == names_of(READ)
    assert set(CONTROL_CALLS) == names_of(CONTROL)


@pytest.mark.anyio
async def test_read_tools_send_no_post_and_write_nothing(tmp_path):
    router = make_router()
    before = tree(tmp_path)
    with anyio.fail_after(30):
        async with open_resources(make_config(tmp_path), router) as resources:
            for name, arguments in READ_CALLS.items():
                outcome = await run_tool(resources, name, **arguments)
                if name not in NEEDS_A_STORED_SCENE:
                    assert outcome.ok, (name, outcome.error)
    assert router.count("POST") == 0
    assert tree(tmp_path) == before


@pytest.mark.anyio
async def test_control_tools_never_send_storage_commands_or_write_files(tmp_path):
    router = make_router()
    before = tree(tmp_path)
    with anyio.fail_after(60):
        async with open_resources(make_config(tmp_path), router) as resources:
            for name, arguments in CONTROL_CALLS.items():
                await run_tool(resources, name, **arguments)
    assert router.posts, "the control tools did reach the device"
    for _host, path, body in router.posts:
        assert path == "/json/state"
        assert isinstance(body, dict) and not {"psave", "pdel"} & set(body)
    assert tree(tmp_path) == before  # no snapshot, bundle or presets file


# ---------------------------------------------------- G1: the registration filter (T20-01)


@pytest.mark.anyio
@pytest.mark.parametrize("profile", PROFILES)
async def test_tools_list_equals_the_profile_expectation_and_each_tool_is_unchanged(
    tmp_path, profile
):
    full_server, _, _ = served(tmp_path / "full")
    restricted, _, _ = served(tmp_path / "restricted", profile)
    with anyio.fail_after(30):
        async with Client(full_server) as everything, Client(restricted) as client:
            names = await listed_names(client)
            assert names == expected_names(profile)
            complete = {t.name: t for t in (await everything.list_tools()).tools}
            for tool in (await client.list_tools()).tools:
                # Restriction removes tools; it never alters a schema or description.
                assert tool.model_dump() == complete[tool.name].model_dump()


@pytest.mark.anyio
@pytest.mark.parametrize("profile", ["read-only", "control"])
async def test_excluded_tool_is_an_unknown_tool_before_any_io(tmp_path, profile):
    server, _, router = served(tmp_path, profile)
    excluded = [n for n in expected_names() if n not in expected_names(profile)]
    assert excluded
    before = tree(tmp_path)
    errors = {}
    with anyio.fail_after(30):
        async with Client(server) as client:
            for name in [*excluded, "wled_made_up"]:
                with pytest.raises(MCPError) as caught:
                    await client.call_tool(name, {"device_id": "desk"})
                errors[name] = (caught.value.code, caught.value.message)
    assert len(set(errors.values())) == 1  # every excluded name looks like any unknown name
    assert errors["wled_made_up"] == (-32602, "Unknown tool")
    assert router.calls == [] and tree(tmp_path) == before
    assert not any(name in message for _, message in errors.values() for name in excluded)


@pytest.mark.parametrize("profile", PROFILES)
def test_sdk_schema_lookup_is_none_for_excluded_tools(tmp_path, profile):
    server, _, _ = served(tmp_path, profile)
    lookup = server.get_tool_input_schema
    for name in expected_names():
        schema = lookup(name)
        if name in expected_names(profile):
            assert isinstance(schema, dict) and schema["type"] == "object"
        else:
            assert schema is None
    assert lookup("wled_made_up") is None


def test_create_server_defaults_to_full_without_caps(tmp_path):
    config = make_config(tmp_path)
    router = make_router()
    operations = build_operations(open_resources(config, router))
    for server in (create_server(operations), create_server(operations, AccessPolicy())):
        assert [n for n in expected_names() if server.get_tool_input_schema(n) is None] == []


def test_build_operations_stays_unfiltered_under_a_restricted_policy(tmp_path):
    config = make_config(tmp_path, "read-only", desk="read")
    operations = build_operations(open_resources(config, make_router()))
    assert [op.name for op in operations] == expected_names()


# -------------------------------------------------------- G2: the per-device ceiling (T20-08)

# A control tool without a device_id: the per-device ceiling is checked per expanded device
# (preflight and write engine), covered by tests/test_scene_apply.py, not by the G2 filter.
DEVICELESS_CONTROL_TOOLS = frozenset({"wled_apply_scene"})
WRITE_CALLS: dict[str, dict[str, Any]] = {
    **{k: v for k, v in CONTROL_CALLS.items() if k not in DEVICELESS_CONTROL_TOOLS},
    "wled_save_preset": {"device_id": "desk", "name": "Mine"},
    "wled_delete_preset": {"device_id": "desk", "preset_id": 1},
    "wled_restore_preset": {"device_id": "desk", "backup_id": "b-20260101T000000Z-aaaaaaaaaaaa"},
    "wled_store_preset": {"device_id": "desk", "name": "Mine", "state": {"on": True}},
    "wled_save_playlist": {
        "device_id": "desk",
        "name": "Cycle",
        "entries": [{"preset_id": 1, "duration_s": 5, "transition_s": 0.7}],
        "repeat": 0,
        "shuffle": False,
    },
    "wled_import_presets": {"device_id": "desk", "bundle": {}},
}
DEVICE_TOOLS = [t.name for t in EXPECTED_TOOLS if t.name != "wled_list_devices"]


def test_the_cap_cases_cover_every_write_tool():
    covered = LOCAL_FILE_TOOLS | DEVICELESS_CONTROL_TOOLS
    assert set(WRITE_CALLS) | covered == names_of(CONTROL, MANAGE)
    assert not set(WRITE_CALLS) & covered


async def call(client: Client, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    result = await client.call_tool(name, arguments)
    assert result.structured_content is not None
    assert result.is_error is (not result.structured_content["ok"])
    return result.structured_content


@pytest.mark.anyio
@pytest.mark.parametrize("cap", ["read", "control"])
async def test_a_device_cap_refuses_every_higher_class_before_any_io_including_dry_run(
    tmp_path, cap
):
    server, _, router = served(tmp_path, "full", desk=cap)
    allowed = {"read": READ_CALLS, "control": {**READ_CALLS, **CONTROL_CALLS}}[cap]
    before = tree(tmp_path)
    with anyio.fail_after(60):
        async with Client(server) as client:
            for name, arguments in WRITE_CALLS.items():
                if name in allowed:
                    continue
                for dry_run in (False, True):
                    envelope = await call(client, name, {**arguments, "dry_run": dry_run})
                    assert envelope["ok"] is False and envelope["device_id"] == "desk"
                    assert envelope["error"]["code"] == "ACCESS_DENIED", name
                    assert envelope["application"] == "not_attempted", name
                    assert envelope["verification"] == "not_requested", name
                    assert envelope["dry_run"] is dry_run, name
                    assert envelope["error"]["write_retryable"] is False
                    assert "wled_" not in envelope["error"]["message"]
    assert router.calls == [] and tree(tmp_path) == before


@pytest.mark.anyio
async def test_reads_stay_allowed_on_a_capped_device_and_other_devices_are_unaffected(tmp_path):
    server, _, router = served(tmp_path, "full", desk="read")
    with anyio.fail_after(60):
        async with Client(server) as client:
            for name, arguments in READ_CALLS.items():
                envelope = await call(client, name, arguments)
                assert envelope["ok"] is (name not in NEEDS_A_STORED_SCENE), name
                assert (envelope["error"] or {}).get("code") != "ACCESS_DENIED", name
            assert router.count("POST") == 0
            other = await call(client, "wled_set_state", {"device_id": "shelf", "brightness": 40})
            assert other["error"] is None or other["error"]["code"] != "ACCESS_DENIED"
            assert router.count("POST", HOSTS["shelf"]) == 1
            assert router.count("POST", HOSTS["desk"]) == 0


@pytest.mark.anyio
async def test_the_effective_class_is_the_lower_of_profile_and_cap(tmp_path):
    # control profile + manage cap: the profile wins (manage tools are not registered);
    # full profile + control cap: the cap wins.
    for profile, cap, listed, refused in (
        ("control", "manage", "wled_set_state", None),
        ("full", "control", "wled_set_state", "wled_save_preset"),
    ):
        server, _, _ = served(tmp_path / f"{profile}-{cap}", profile, desk=cap)
        async with Client(server) as client:
            names = await listed_names(client)
            assert listed in names
            if refused is None:
                assert not names_of(MANAGE) & set(names)
            else:
                assert refused in names  # listed for the deployment, refused for the device
                envelope = await call(client, refused, {**WRITE_CALLS[refused]})
                assert envelope["error"]["code"] == "ACCESS_DENIED"


@pytest.mark.anyio
async def test_an_unknown_device_keeps_its_own_error_and_a_validation_error_comes_first(
    tmp_path,
):
    server, _, router = served(tmp_path, "full", desk="read")
    with anyio.fail_after(30):
        async with Client(server) as client:
            unknown = await call(client, "wled_set_state", {"device_id": "absent", "on": True})
            assert unknown["error"]["code"] == "UNKNOWN_DEVICE"
            invalid = await call(client, "wled_set_state", {"device_id": "desk", "on": "yes"})
            assert invalid["error"]["code"] == "VALIDATION_ERROR"  # schema check precedes G2
    assert router.calls == []


# ------------------------------------------------------ G3: the write-engine guard (T20-04)


async def prepare_none(context: OperationContext) -> dict[str, Any]:  # pragma: no cover
    raise AssertionError("a refused write must not reach prepare")


async def prepare_sequence(context: OperationContext) -> SequencePlan:  # pragma: no cover
    raise AssertionError("a refused write must not reach prepare")


async def prepare_polled(context: OperationContext) -> PolledWrite:  # pragma: no cover
    raise AssertionError("a refused write must not reach prepare")


async def through_each_engine(resources: Resources, device_id: str) -> dict[str, Outcome]:
    never = lambda _value: False  # noqa: E731
    return {
        "write_verified": await resources.write_verified(
            device_id, "synthetic", prepare_none, never
        ),
        "write_sequence_verified": await resources.write_sequence_verified(
            device_id, "synthetic", prepare_sequence
        ),
        "write_polled": await resources.write_polled(device_id, "synthetic", prepare_polled),
    }


def assert_denied(outcome: Outcome, device_id: str) -> None:
    assert outcome.ok is False and outcome.device_id == device_id
    assert outcome.error is not None and outcome.error.code == "ACCESS_DENIED"
    assert (outcome.application, outcome.verification) == ("not_attempted", "not_requested")


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("ambient", "cap"),
    [
        (ToolClass.CONTROL, "read"),  # a control composite reaching a read-capped device
        (ToolClass.MANAGE, "read"),
        (ToolClass.MANAGE, "control"),  # a manage write on a control-capped device
        (ToolClass.READ, None),  # a read-class operation attempting any write
        (ToolClass.READ, "manage"),
    ],
)
async def test_every_engine_refuses_before_the_lock_and_any_io(tmp_path, ambient, cap):
    caps = {} if cap is None else {"desk": cap}
    router = make_router()
    async with open_resources(make_config(tmp_path, "full", **caps), router) as resources:
        token = CURRENT_TOOL_CLASS.set(ambient)
        try:
            lock = resources.locks["desk"]
            async with lock:  # a held lock proves the guard runs before taking it
                with anyio.fail_after(5):
                    outcomes = await through_each_engine(resources, "desk")
        finally:
            CURRENT_TOOL_CLASS.reset(token)
    for outcome in outcomes.values():
        assert_denied(outcome, "desk")
    assert router.calls == []


@pytest.mark.anyio
async def test_the_g3_and_g2_refusals_have_the_same_envelope_shape_including_dry_run(tmp_path):
    router = make_router()
    config = make_config(tmp_path, "full", desk="read")
    async with open_resources(config, router) as resources:
        token = CURRENT_TOOL_CLASS.set(ToolClass.CONTROL)
        try:
            engines = await through_each_engine(resources, "desk")
        finally:
            CURRENT_TOOL_CLASS.reset(token)
        server = create_server(build_operations(resources), config.access)
        async with Client(server) as client:
            live = await client.call_tool("wled_set_state", {"device_id": "desk", "on": True})
            dry = await client.call_tool(
                "wled_set_state", {"device_id": "desk", "on": True, "dry_run": True}
            )
    assert live.structured_content is not None and dry.structured_content is not None
    shape = set(strip_correlation_id(live.structured_content))
    for name, outcome in engines.items():
        dumped = outcome.model_dump(mode="json")
        assert set(dumped) == shape, name  # the same keys, `dry_run` included
        assert dumped["dry_run"] is False, name  # the engines only ever serve real writes
        assert (dumped["error"]["code"], dumped["error"]["write_retryable"]) == (
            "ACCESS_DENIED",
            False,
        )
    assert live.structured_content["dry_run"] is False
    assert dry.structured_content["dry_run"] is True  # G2 carries the caller's dry_run
    assert router.calls == []


@pytest.mark.anyio
async def test_the_import_entry_refuses_before_parsing_or_any_io(tmp_path):
    router = make_router()
    async with open_resources(make_config(tmp_path, "full", desk="read"), router) as resources:
        for ambient in (ToolClass.CONTROL, ToolClass.MANAGE, ToolClass.READ):
            token = CURRENT_TOOL_CLASS.set(ambient)
            try:
                async with resources.locks["desk"]:
                    outcome = await {op.name: op for op in build_operations(resources)}[
                        "wled_import_presets"
                    ].execute({"device_id": "desk", "bundle": "not json", "dry_run": False})
            finally:
                CURRENT_TOOL_CLASS.reset(token)
            assert_denied(outcome, "desk")
    assert router.calls == []


@pytest.mark.anyio
async def test_an_engine_call_outside_a_tool_fails_closed_only_under_a_restriction(tmp_path):
    # In-process callers keep working under the default policy (ambient class unset).
    router = make_router()
    async with open_resources(make_config(tmp_path / "open"), router) as resources:
        assert CURRENT_TOOL_CLASS.get() is None
        resources.require_write("desk")
        resources.require_access("desk", ToolClass.MANAGE)
    for profile, caps in (("control", {}), ("full", {"desk": "control"})):
        async with open_resources(
            make_config(tmp_path / f"{profile}{len(caps)}", profile, **caps), router
        ) as resources:
            assert CURRENT_TOOL_CLASS.get() is None
            with pytest.raises(ClientFailure) as caught:
                resources.require_write("desk")
            assert caught.value.error.code == "ACCESS_DENIED"
    assert router.calls == []


def test_require_access_is_pure_and_lets_unknown_devices_through(tmp_path):
    resources = open_resources(make_config(tmp_path, "full", desk="read"), make_router())
    resources.require_access("desk", ToolClass.READ)
    resources.require_access("shelf", ToolClass.MANAGE)
    resources.require_access("absent", ToolClass.MANAGE)  # resolve() reports UNKNOWN_DEVICE
    with pytest.raises(ClientFailure) as caught:
        resources.require_access("desk", ToolClass.CONTROL)
    error = caught.value.error
    assert error.code == "ACCESS_DENIED" and "desk" in error.message
    assert "wled_" not in error.message and "wled_" not in error.reconciliation


@pytest.mark.anyio
async def test_the_ambient_class_is_set_per_call_visible_in_children_and_reset(tmp_path):
    seen: dict[str, Any] = {}

    async def spy(arguments: dict[str, Any]) -> Outcome:
        seen["inline"] = CURRENT_TOOL_CLASS.get()
        async with anyio.create_task_group() as group:

            async def child() -> None:
                seen["child"] = CURRENT_TOOL_CLASS.get()
                seen["thread"] = await anyio.to_thread.run_sync(CURRENT_TOOL_CLASS.get)

            group.start_soon(child)
        return Outcome(
            ok=True,
            operation="wled_spy",
            device_id=None,
            application="not_attempted",
            verification="not_requested",
        )

    from mcp.types import ToolAnnotations

    server = create_server(
        [Operation("wled_spy", "spy", Empty, spy, ToolAnnotations(), tool_class=ToolClass.CONTROL)]
    )
    async with Client(server) as client:
        await call(client, "wled_spy", {})
    assert seen == {
        "inline": ToolClass.CONTROL,
        "child": ToolClass.CONTROL,
        "thread": ToolClass.CONTROL,
    }
    assert CURRENT_TOOL_CLASS.get() is None


@pytest.mark.anyio
async def test_a_control_composite_cannot_reach_a_read_capped_device_even_when_listed(tmp_path):
    """The composite-path case (#17 scenes, #18 restore): listed, still refused per device."""
    config = make_config(tmp_path, "control", desk="read")
    router = make_router()

    async def composite(arguments: dict[str, Any]) -> Outcome:
        results = [await through_each_engine(resources, d) for d in ("desk", "shelf")]
        denied = {
            d: [o.error.code if o.error else None for o in r.values()]
            for d, r in zip(("desk", "shelf"), results, strict=True)
        }
        return Outcome(
            ok=True,
            operation="wled_composite",
            device_id=None,
            application="not_attempted",
            verification="not_requested",
            data={"codes": denied},  # type: ignore[dict-item]
        )

    from mcp.types import ToolAnnotations

    async with open_resources(config, router) as resources:
        composite_op = Operation(
            "wled_composite", "c", Empty, composite, ToolAnnotations(), tool_class=ToolClass.CONTROL
        )
        server = create_server([composite_op], config.access)
        async with Client(server) as client:
            envelope = await call(client, "wled_composite", {})
    codes = envelope["data"]["codes"]
    assert codes["desk"] == ["ACCESS_DENIED"] * 3
    assert "ACCESS_DENIED" not in codes["shelf"]  # the uncapped device is not refused by G3
    assert router.count("POST", HOSTS["desk"]) == 0


# ------------------------------------------------------- T20-12 one sink, structurally


def test_post_state_is_referenced_only_by_the_engines_and_the_import_path():
    allowed = {"client.py", "resources.py", "bundle_tools.py"}
    users = set()
    for path in sorted(SRC.glob("*.py")):
        tree_ = ast.parse(path.read_text("utf-8"))
        if any(
            isinstance(node, ast.Attribute | ast.Name | ast.FunctionDef | ast.AsyncFunctionDef)
            and getattr(node, "attr", getattr(node, "id", getattr(node, "name", None)))
            == "post_state"
            for node in ast.walk(tree_)
        ):
            users.add(path.name)
    # A new module calling the sink directly bypasses the guard: route it through a
    # Resources engine or an explicit Resources.require_write and extend this test.
    assert users == allowed, users


def test_every_engine_checks_access_as_its_first_statement():
    tree_ = ast.parse((SRC / "resources.py").read_text("utf-8"))
    engines = {
        node.name: node
        for node in ast.walk(tree_)
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name in {"write_verified", "write_sequence_verified", "write_polled"}
    }
    assert set(engines) == {"write_verified", "write_sequence_verified", "write_polled"}
    for name, node in engines.items():
        body = [
            statement
            for statement in node.body
            if not (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant))
        ]
        first = ast.unparse(body[0])
        assert first.startswith("if (refused := self._refused(device_id, operation))"), name


def test_the_import_path_checks_access_before_parsing_the_bundle():
    text = (SRC / "bundle_tools.py").read_text("utf-8")
    start = text.index("async def import_presets")
    body = text[start:]
    assert body.index("resources.require_write(device_id)") < body.index("parse_bundle(")


def test_no_environment_variable_selects_a_profile():
    # TD-20-7: only the option and the file select a profile.
    text = "".join(path.read_text("utf-8") for path in SRC.glob("*.py"))
    assert not re.search(r"WLED_MCP_[A-Z_]*PROFILE", text)


# ================================================ configuration and CLI (T20-07, T20-10)

SECRET = "synthetic-secret-marker"
DEVICE = '[[devices]]\nid = "desk"\nname = "Example desk"\nbase_url = "http://desk.invalid"\n'


def document(access: str = "", device: str = DEVICE) -> bytes:
    return f"schema_version = 1\n{access}{device}".encode()


def test_access_settings_are_additive_and_optional():
    plain = validate_document(document())
    assert plain.access.profile == "full" and plain.devices[0].max_class is None
    assert not access_configured(plain) and access_facts(plain) is None
    configured = validate_document(
        document(
            '[access]\nprofile = "control"\n',
            DEVICE + 'max_class = "read"\n[[devices]]\nid = "shelf"\nname = "S"\n'
            'base_url = "http://shelf.invalid"\n',
        )
    )
    assert configured.access.profile == "control"
    assert [d.max_class for d in configured.devices] == ["read", None]
    assert access_facts(configured) == {"profile": "control", "capped_devices": 1}
    assert access_policy(configured) == AccessPolicy("control", {"desk": ToolClass.READ})
    # An empty [access] table is still a configured (default) setting.
    assert access_facts(validate_document(document("[access]\n"))) == {
        "profile": "full",
        "capped_devices": 0,
    }


@pytest.mark.parametrize(
    ("content", "located"),
    [
        (document(f'[access]\nprofile = "{SECRET}"\n'), "access.profile: invalid"),
        (document("[access]\nprofile = 3\n"), "access.profile: invalid"),
        (document(f'[access]\n{SECRET} = "full"\n'), "access: unsupported field"),
        (document(f'access = "{SECRET}"\n', DEVICE), "access: invalid"),
        (document(device=DEVICE + f'max_class = "{SECRET}"\n'), "devices[0].max_class: invalid"),
        (document(device=DEVICE + "max_class = 2\n"), "devices[0].max_class: invalid"),
        (document(device=DEVICE + 'max_class = "Read"\n'), "devices[0].max_class: invalid"),
    ],
)
def test_invalid_access_settings_are_positional_and_value_free(content, located):
    with pytest.raises(ConfigurationError) as caught:
        validate_document(content)
    message = str(caught.value)
    assert located in message
    assert SECRET not in message


def test_access_locators_sort_after_the_device_entries():
    content = document('[access]\nprofile = "nope"\n', DEVICE + 'max_class = "nope"\n')
    with pytest.raises(ConfigurationError) as caught:
        validate_document(content)
    assert "(devices[0].max_class: invalid, access.profile: invalid)" in str(caught.value)


def test_unrelated_validation_messages_are_unchanged():
    with pytest.raises(ConfigurationError) as caught:
        validate_document(document(device=DEVICE.replace("http://desk.invalid", "ftp://x")))
    assert str(caught.value).startswith(
        "Invalid inventory configuration (devices[0].base_url: invalid): "
    )


def write_config(directory: Path, access: str = "", device: str = DEVICE) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "config.toml"
    path.write_bytes(document(access, device))
    return path


def test_profile_precedence_is_option_then_file_then_full(tmp_path):
    plain = write_config(tmp_path / "plain")
    filed = write_config(tmp_path / "filed", '[access]\nprofile = "read-only"\n')
    for path, option, expected in (
        (plain, None, "full"),
        (plain, "control", "control"),
        (filed, None, "read-only"),
        (filed, "full", "full"),
        (filed, "control", "control"),
    ):
        loaded = load_config(str(path), str(path.parent), {}, profile=option)
        assert loaded.access.profile == expected, (path.parent.name, option)


def test_load_config_carries_the_device_caps_and_ignores_the_environment(tmp_path):
    path = write_config(tmp_path, device=DEVICE + 'max_class = "control"\n')
    environ = {"WLED_MCP_PROFILE": "read-only", "WLED_MCP_ACCESS_PROFILE": "read-only"}
    loaded = load_config(str(path), str(tmp_path), environ)
    assert loaded.access == AccessPolicy("full", {"desk": ToolClass.CONTROL})


def test_retained_and_shipped_configurations_are_unchanged_by_the_new_keys():
    paths = [
        *sorted((ROOT / "tests" / "fixtures" / "compat").glob("*/config.toml")),
        *sorted((ROOT / "examples").glob("*.toml")),
    ]
    assert paths
    for path in paths:
        inventory = validate_document(path.read_bytes())
        assert not access_configured(inventory), path
        assert access_policy(inventory) == AccessPolicy(), path


def run_cli(capsys, *argv: str) -> tuple[int, str, str]:
    try:
        code = cli.main(list(argv))
    except SystemExit as exc:
        code = int(exc.code or 0)
    out, err = capsys.readouterr()
    return code, out, err


@pytest.mark.parametrize("value", ["admin", "READ-ONLY", "", f"x{SECRET}"])
def test_an_invalid_profile_option_is_a_usage_error_without_echo(tmp_path, capsys, value):
    config = write_config(tmp_path)
    code, out, err = run_cli(
        capsys, "--config", str(config), "--data-dir", str(tmp_path), "--profile", value
    )
    assert code == 2 and out == ""
    assert err == "Invalid command-line arguments. Use --help for supported options.\n"


@pytest.mark.parametrize("command", [["doctor"], ["config", "validate"], ["discover"]])
def test_the_profile_option_before_a_subcommand_is_a_usage_error(capsys, command):
    code, out, err = run_cli(capsys, "--profile", "read-only", *command)
    assert code == 2 and out == ""
    assert "Invalid command-line arguments" in err


def test_an_invalid_profile_in_the_file_exits_2_at_startup_without_serving(
    tmp_path, capsys, monkeypatch
):
    config = write_config(tmp_path, f'[access]\nprofile = "{SECRET}"\n')
    monkeypatch.setattr(cli.anyio, "run", lambda *args: pytest.fail("must not serve"))
    code, out, err = run_cli(capsys, "--config", str(config), "--data-dir", str(tmp_path))
    assert code == 2 and out == ""
    assert "access.profile: invalid" in err and SECRET not in err


@pytest.mark.parametrize(
    ("access", "option", "expected"),
    [
        ("", None, "full"),
        ('[access]\nprofile = "control"\n', None, "control"),
        ('[access]\nprofile = "control"\n', "read-only", "read-only"),
    ],
)
def test_serve_hands_the_resolved_policy_to_the_service(
    tmp_path, capsys, monkeypatch, access, option, expected
):
    config = write_config(tmp_path, access, DEVICE + 'max_class = "read"\n')
    captured: list[Any] = []
    monkeypatch.setattr(cli.anyio, "run", lambda function, *args: captured.append(args[0]))
    argv = ["--config", str(config), "--data-dir", str(tmp_path)]
    assert cli.main([*argv, *(["--profile", option] if option else [])]) == 0
    assert captured[0].access == AccessPolicy(expected, {"desk": ToolClass.READ})  # type: ignore[arg-type]


@pytest.mark.anyio
async def test_serve_passes_the_policy_to_create_server_and_logs_one_startup_event(
    tmp_path, monkeypatch, caplog
):
    received: dict[str, Any] = {}

    def fake_create(operations, access=None, monitor=None):
        received["access"] = access
        return object()

    async def fake_stdio(server):
        received["served"] = server

    monkeypatch.setattr(cli, "create_server", fake_create)
    monkeypatch.setattr(cli, "serve_stdio", fake_stdio)
    config = make_config(tmp_path, "control", desk="read")
    with caplog.at_level(logging.INFO, logger="wled_mcp"):
        await cli.serve(config)
    assert received["access"] == config.access and "served" in received
    events = [r.getMessage() for r in caplog.records if r.name == "wled_mcp"]
    assert events == ["service starting: transport=stdio profile=control capped_devices=1"]
    assert "desk" not in events[0] and str(tmp_path) not in events[0]


@pytest.mark.anyio
async def test_serve_http_passes_the_policy_to_create_server_and_logs_the_event(
    tmp_path, monkeypatch, caplog
):
    import wled_mcp.http_service as http_service

    received: dict[str, Any] = {}

    class Dummy:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def serve(self) -> None:
            received["served"] = True

    def fake_create(operations, access=None, monitor=None):
        received["access"] = access
        return object()

    monkeypatch.setattr(cli, "create_server", fake_create)
    monkeypatch.setattr(http_service, "build_http_app", lambda server, settings: object())
    monkeypatch.setattr(http_service, "HTTPService", Dummy)
    monkeypatch.setattr(http_service, "announce", lambda settings: None)
    config = make_config(tmp_path, "read-only")
    with caplog.at_level(logging.INFO, logger="wled_mcp"):
        await cli.serve_http(config, object())  # type: ignore[arg-type]
    assert received == {"access": config.access, "served": True}
    assert [r.getMessage() for r in caplog.records if r.name == "wled_mcp"] == [
        "service starting: transport=streamable-http profile=read-only capped_devices=0"
    ]


# ============================ the installed console over both transports (T20-01/02/08/09)


def write_fleet(
    directory: Path, fleet: dict[str, tuple[LoopbackWLED, str | None]], access: str = ""
) -> Path:
    text = f"schema_version = 1\n[http]\noperation_timeout_seconds = 3\n{access}"
    for identifier, (fake, cap) in fleet.items():
        text += (
            f'[[devices]]\nid = "{identifier}"\nname = "Example {identifier}"\n'
            f'base_url = "{fake.base_url}"\n' + (f'max_class = "{cap}"\n' if cap else "")
        )
    config = directory / "service.toml"
    config.write_text(text, encoding="utf-8")
    return config


def stdio_params(config: Path, data: Path, *args: str) -> StdioServerParameters:
    return StdioServerParameters(
        command=str(CONSOLE),
        cwd=data,
        args=["--config", str(config), "--data-dir", str(data), *args],
        env=clean_env(),
    )


@asynccontextmanager
async def http_client(port: int) -> AsyncIterator[Client]:
    async with httpx.AsyncClient(headers={"Authorization": f"Bearer {TOKEN}"}) as http:
        transport = streamable_http_client(
            f"http://127.0.0.1:{port}/mcp", http_client=http, terminate_on_close=False
        )
        async with Client(transport, mode="legacy", read_timeout_seconds=30) as client:
            yield client


def http_arguments(port: int, *extra: str) -> list[str]:
    return [
        "--transport",
        "streamable-http",
        "--port",
        str(port),
        "--allowed-host",
        f"127.0.0.1:{port}",
        *extra,
    ]


async def unknown_tool_error(client: Client, name: str) -> tuple[int, str]:
    with pytest.raises(MCPError) as caught:
        await client.call_tool(name, {"device_id": "desk", "on": True})
    return caught.value.code, caught.value.message


async def profile_session(client: Client, profile: str, fakes: list[LoopbackWLED]) -> None:
    assert await listed_names(client) == expected_names(profile)
    excluded = [name for name in expected_names() if name not in expected_names(profile)]
    before = sum(fake.count() for fake in fakes)
    errors = {name: await unknown_tool_error(client, name) for name in [*excluded, "wled_absent"]}
    assert set(errors.values()) == {(-32602, "Unknown tool")}
    assert sum(fake.count() for fake in fakes) == before  # no device request for any of them
    if "wled_set_state" in expected_names(profile):
        result = await client.call_tool("wled_set_state", {"device_id": "desk", "brightness": 33})
        assert result.structured_content is not None and result.structured_content["ok"] is True


@pytest.fixture
def fakes() -> Iterator[list[LoopbackWLED]]:
    devices = [LoopbackWLED(), LoopbackWLED()]
    try:
        yield devices
    finally:
        for device in devices:
            device.close()


@pytest.mark.parametrize("profile", PROFILES)
def test_stdio_console_serves_exactly_the_profile_tools(tmp_path, fakes, profile):
    config = write_fleet(tmp_path, {"desk": (fakes[0], None), "shelf": (fakes[1], None)})

    async def run() -> None:
        with anyio.fail_after(90):
            async with Client(
                stdio_params(config, tmp_path, "--profile", profile),
                mode="legacy",
                read_timeout_seconds=30,
            ) as client:
                await profile_session(client, profile, fakes)

    before = tree(tmp_path)
    anyio.run(run)
    assert tree(tmp_path) == before


@pytest.mark.parametrize("profile", PROFILES)
def test_http_console_serves_exactly_the_profile_tools(tmp_path, fakes, profile):
    config = write_fleet(tmp_path, {"desk": (fakes[0], None), "shelf": (fakes[1], None)})
    port = free_port()
    env = clean_env(WLED_MCP_HTTP_TOKEN=TOKEN)

    async def run() -> None:
        with anyio.fail_after(90):
            async with http_client(port) as client:
                await profile_session(client, profile, fakes)

    before = tree(tmp_path)
    with console(config, tmp_path, *http_arguments(port, "--profile", profile), env=env) as (
        process,
        lines,
    ):
        wait_ready(lines, port)
        anyio.run(run)
        assert process.poll() is None
    assert tree(tmp_path) == before


def test_the_file_profile_applies_and_the_option_overrides_it(tmp_path, fakes):
    config = write_fleet(
        tmp_path,
        {"desk": (fakes[0], None), "shelf": (fakes[1], None)},
        access='[access]\nprofile = "read-only"\n',
    )

    async def names(*args: str) -> list[str]:
        with anyio.fail_after(90):
            async with Client(
                stdio_params(config, tmp_path, *args), mode="legacy", read_timeout_seconds=30
            ) as client:
                return await listed_names(client)

    assert anyio.run(names) == expected_names("read-only")
    assert anyio.run(names, "--profile", "control") == expected_names("control")
    assert anyio.run(names, "--profile", "full") == expected_names("full")


def test_an_invalid_profile_option_never_reaches_a_server_process(tmp_path, fakes):
    config = write_fleet(tmp_path, {"desk": (fakes[0], None)})
    result = subprocess.run(
        [str(CONSOLE), "--config", str(config), "--data-dir", str(tmp_path), "--profile", "root"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=tmp_path,
        env=clean_env(),
    )
    assert result.returncode == 2 and result.stdout == ""
    assert result.stderr == "Invalid command-line arguments. Use --help for supported options.\n"
    assert fakes[0].count() == 0


def mask(envelope: dict[str, Any]) -> dict[str, Any]:
    """Drop the volatile fields: a state read's ``read_at`` and the per-call ID."""
    masked = strip_correlation_id(json.loads(json.dumps(envelope)))
    (masked.get("data", {}).get("freshness") or {}).pop("read_at", None)
    return masked


async def mixed_session(client: Client, brightness: int) -> dict[str, Any]:
    """Interleave refused, allowed and excluded calls; return what each one answered."""
    results: dict[str, Any] = {}
    results["names"] = await listed_names(client)
    results["denied"] = (
        await client.call_tool("wled_set_state", {"device_id": "desk", "brightness": brightness})
    ).structured_content
    results["allowed"] = (
        await client.call_tool("wled_set_state", {"device_id": "shelf", "brightness": brightness})
    ).structured_content
    results["read"] = (
        await client.call_tool("wled_get_state", {"device_id": "desk"})
    ).structured_content
    results["dry_run_denied"] = (
        await client.call_tool(
            "wled_set_state", {"device_id": "desk", "brightness": brightness, "dry_run": True}
        )
    ).structured_content
    results["excluded"] = await unknown_tool_error(client, "wled_save_preset")
    return results


def test_concurrent_http_clients_and_a_stdio_process_see_the_same_list_and_refusals(
    tmp_path, fakes
):
    desk, shelf = fakes
    config = write_fleet(
        tmp_path,
        {"desk": (desk, "read"), "shelf": (shelf, None)},
        access='[access]\nprofile = "control"\n',
    )
    port = free_port()
    env = clean_env(WLED_MCP_HTTP_TOKEN=TOKEN)
    outcomes: dict[str, dict[str, Any]] = {}

    async def drive(label: str, brightness: int, open_client: Any) -> None:
        async with open_client() as client:
            outcomes[label] = await mixed_session(client, brightness)

    async def run() -> None:
        def stdio() -> Any:
            return Client(stdio_params(config, tmp_path), mode="legacy", read_timeout_seconds=30)

        with anyio.fail_after(120):
            async with anyio.create_task_group() as group:
                group.start_soon(drive, "http-a", 41, lambda: http_client(port))
                group.start_soon(drive, "http-b", 42, lambda: http_client(port))
                group.start_soon(drive, "stdio", 43, stdio)

    before = tree(tmp_path)
    with console(config, tmp_path, *http_arguments(port), env=env) as (process, lines):
        wait_ready(lines, port)
        anyio.run(run)
        assert process.poll() is None
    assert tree(tmp_path) == before
    assert set(outcomes) == {"http-a", "http-b", "stdio"}
    for label, result in outcomes.items():
        assert result["names"] == expected_names("control"), label
        assert result["excluded"] == (-32602, "Unknown tool"), label
        for key in ("denied", "dry_run_denied"):
            assert result[key]["error"]["code"] == "ACCESS_DENIED", (label, key)
            assert result[key]["application"] == "not_attempted", (label, key)
            assert result[key]["device_id"] == "desk"
        assert result["allowed"]["ok"] is True and result["allowed"]["device_id"] == "shelf"
        assert result["read"]["ok"] is True
    # Identical refusals on every client, apart from the dry-run marker's own request.
    assert mask(outcomes["http-a"]["denied"]) == mask(outcomes["stdio"]["denied"])
    assert mask(outcomes["http-a"]["read"]) == mask(outcomes["stdio"]["read"])
    assert desk.count("POST") == 0, "the read-capped device never received a write"
    assert desk.count("GET") >= 3  # reads on the capped device stay allowed
    assert shelf.state["bri"] in (41, 42, 43)
    assert shelf.count("POST") == 3
