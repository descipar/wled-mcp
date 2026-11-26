"""Issue #236: tool groups (TOOLGRP-01..05, ISSUE-236-DEC-001).

The registered set is the intersection of the profile's classes and the selected groups.
Expectations come from tests/tool_contract.py, never from production code.
"""

from __future__ import annotations

import ast
import dataclasses
import json
import re
from typing import Any

import anyio
import pytest
from mcp.client import Client
from mcp.shared.exceptions import MCPError

from tests.test_access_profiles import (
    DEVICE,
    PROFILES,
    SECRET,
    SRC,
    document,
    listed_names,
    registry,
    run_cli,
    served,
    write_config,
)
from tests.tool_contract import (
    EXPECTED_TOOLS,
    TOOL_GROUPS,
    expected_names,
    expected_names_in,
    group_names,
)
from wled_mcp import access, cli
from wled_mcp.access import AccessPolicy
from wled_mcp.config import (
    ConfigurationError,
    access_facts,
    access_line,
    access_policy,
    load_config,
    validate_document,
)
from wled_mcp.guidance import build_instructions
from wled_mcp.server import create_server

# The text of every release before tool groups (golden, AC-236-01).
TODAY = """Read wled_get_state before changing lighting and choose the smallest change.
Use wled_patch_segments to patch selected existing segments; wled_replace_layout replaces
the complete layout and removes active segment IDs omitted from the request. Segment stop
(and stop_y) is exclusive. Omitted fields preserve existing values; they are not resets.
Effect and palette IDs are device-specific: read that device's catalogs rather than guess.
A room (a group saved with kind=room) is where controllers are, at most one room per
controller: use wled_apply_room for a state or scene across a whole room, a plain group for
any other set of controllers, a zone for part of a controller and wled_set_state for one
controller.
Use dry_run=true to inspect a proposed write, then inspect the result's application and
verification fields and read state when needed. A timed-out or uncertain write may already
have applied: never retry it blindly. Overwriting a preset requires overwrite=true and a
durable snapshot is taken first. Authorization belongs to the MCP host; these instructions
and tool annotations do not add a confirmation mechanism or grant access.
"""

SUBSETS: list[list[str]] = [
    ["core"],
    ["presets"],
    ["scenes", "layout"],
    ["signals", "diagnostics", "discovery"],
    ["all"],
]
TOOL_REFERENCE = re.compile(r"\bwled_[a-z][a-z_]*[a-z]\b")


# ------------------------------------------------------------------ membership (AC-236-07)


def test_group_names_equal_the_contract_vocabulary():
    assert access.TOOL_GROUPS == TOOL_GROUPS
    assert access.ALL_GROUPS == frozenset(TOOL_GROUPS)


def test_production_groups_equal_the_contract_groups_in_both_directions(tmp_path):
    actual = {op.name: op.group for op in registry(tmp_path)}
    assert actual == {tool.name: tool.group for tool in EXPECTED_TOOLS}


def test_every_group_holds_a_read_tool_and_core_holds_status_and_devices():
    for group in TOOL_GROUPS:
        assert any(t.group == group and t.tool_class.value == "read" for t in EXPECTED_TOOLS), group
    assert {"wled_get_service_status", "wled_list_devices"} <= group_names("core")


def test_a_group_never_empties_a_profile():
    for profile in PROFILES:
        for group in TOOL_GROUPS:
            assert expected_names_in(profile, [group]), (profile, group)


def test_create_server_refuses_an_unknown_group(tmp_path):
    operations = list(registry(tmp_path))
    bad = dataclasses.replace(operations[0], group="nope")
    with pytest.raises(TypeError, match="group"):
        create_server([bad])


# ------------------------------------------------------- registered set (AC-236-01/04/05)


@pytest.mark.anyio
@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("groups", SUBSETS, ids=lambda g: "+".join(g))
async def test_registered_set_is_the_profile_and_group_intersection(tmp_path, profile, groups):
    full, _, _ = served(tmp_path / "full")
    server, _, _ = served(tmp_path / "limited", profile, groups)
    with anyio.fail_after(60):
        async with Client(full) as everything, Client(server) as client:
            names = await listed_names(client)
            assert names == expected_names_in(profile, groups)
            assert set(names) <= set(expected_names(profile))  # a group never widens a profile
            complete = {t.name: t for t in (await everything.list_tools()).tools}
            for tool in (await client.list_tools()).tools:
                assert tool.model_dump() == complete[tool.name].model_dump()


@pytest.mark.anyio
async def test_default_is_all_and_instructions_are_byte_identical(tmp_path):
    server, _, _ = served(tmp_path)
    async with Client(server) as client:
        assert await listed_names(client) == expected_names()
        assert client.instructions == TODAY
    assert build_instructions(expected_names()) == TODAY


@pytest.mark.anyio
async def test_a_disabled_tool_is_an_unknown_tool_before_any_io(tmp_path):
    server, _, router = served(tmp_path, "full", ["core"])
    excluded = [n for n in expected_names() if n not in expected_names_in("full", ["core"])]
    assert excluded
    errors = {}
    with anyio.fail_after(60):
        async with Client(server) as client:
            for name in [*excluded, "wled_made_up"]:
                with pytest.raises(MCPError) as caught:
                    await client.call_tool(name, {"device_id": "desk"})
                errors[name] = (caught.value.code, caught.value.message)
    assert set(errors.values()) == {(-32602, "Unknown tool")}
    assert router.calls == []
    assert server.get_tool_input_schema("wled_apply_room") is None


def test_policy_rejects_a_group_set_without_core_or_with_an_unknown_name():
    with pytest.raises(ValueError):
        AccessPolicy(groups=frozenset({"presets"}))
    with pytest.raises(ValueError):
        AccessPolicy(groups=frozenset({"core", "nope"}))
    assert access.parse_group_names(["presets"]) == {"core", "presets"}
    assert access.parse_group_names(["presets", "all"]) == access.ALL_GROUPS


# ------------------------------------------------------------- instructions (AC-236-08)


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("groups", SUBSETS, ids=lambda g: "+".join(g))
def test_instructions_name_only_registered_tools(profile, groups):
    registered = set(expected_names_in(profile, groups))
    text = build_instructions(registered)
    assert set(TOOL_REFERENCE.findall(text)) <= registered
    assert text.startswith("Read wled_get_state before")


def test_the_layout_and_room_sentences_follow_the_registered_tools():
    only_core = build_instructions(expected_names_in("full", ["core"]))
    assert "wled_replace_layout" not in only_core and "wled_apply_room" not in only_core
    assert "wled_patch_segments" in only_core
    assert "wled_patch_segments" not in build_instructions(expected_names_in("read-only", ["all"]))


# ---------------------------------------------------- references stay in group (AC-236-09)

# Source module -> groups (besides core) whose tool names it may put into user-visible text.
MODULE_GROUPS: dict[str, set[str]] = {
    "operations": {"presets", "layout"},
    "preset_tools": {"presets"},
    "bundle_tools": {"presets"},
    "preset_writes": {"presets"},
    "backups": {"presets"},
    "explain": {"diagnostics"},
    "live_snapshot": {"diagnostics"},
    "preview_tools": {"layout"},
    "room_tools": {"scenes"},
    "rooms": {"scenes"},
    "scene_tools": {"scenes"},
    "zone_tools": {"scenes"},
    "signal_tools": {"signals"},
    "signal_manager": {"signals"},
    "discovery_tools": {"discovery"},
    "discovery_config_tools": {"discovery"},
    "enroll_tools": {"discovery"},
    "config": {"discovery"},
    "guidance": set(TOOL_GROUPS),  # composed from the registered set; see the tests above
}


def test_descriptions_name_only_tools_of_their_own_group_or_core(tmp_path):
    group_of = {t.name: t.group for t in EXPECTED_TOOLS}
    problems = []
    for op in registry(tmp_path):
        for name in set(TOOL_REFERENCE.findall(op.description)) & set(group_of):
            if group_of[name] not in (op.group, "core"):
                problems.append(f"{op.name} names {name}")
    assert not problems, problems


@pytest.mark.anyio
@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("groups", SUBSETS, ids=lambda g: "+".join(g))
async def test_served_tools_list_names_no_tool_of_an_unselected_group(tmp_path, profile, groups):
    """The whole served tools/list JSON (descriptions, input and output schemas) never names
    a tool of a group that is not selected. Same-group references removed only by the profile
    are pre-existing and tolerated."""
    server, _, _ = served(tmp_path, profile, groups)
    selected = {"core", *(TOOL_GROUPS if groups == ["all"] else groups)}
    foreign = {t.name for t in EXPECTED_TOOLS if t.group not in selected}
    async with Client(server) as client:
        tools = (await client.list_tools()).tools
    problems = []
    for tool in tools:
        text = json.dumps(tool.model_dump(mode="json"))
        for name in set(TOOL_REFERENCE.findall(text)) & foreign:
            problems.append(f"{tool.name} names {name}")
    assert not problems, problems


def test_runtime_texts_stay_within_their_group():
    group_of = {t.name: t.group for t in EXPECTED_TOOLS}
    problems = []
    for path in sorted(SRC.glob("*.py")):
        tree = ast.parse(path.read_text("utf-8"))
        docs = {
            id(node.body[0].value)
            for node in ast.walk(tree)
            if isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
            and node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
        }
        allowed = MODULE_GROUPS.get(path.stem, set()) | {"core"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if id(node) in docs:
                    continue
                for name in set(TOOL_REFERENCE.findall(node.value)) & set(group_of):
                    if group_of[name] not in allowed:
                        problems.append(f"{path.name}:{node.lineno} names {name}")
    assert not problems, (
        "a text names a tool of another group; reword it or make a deliberate edit of "
        f"MODULE_GROUPS: {problems}"
    )


# ------------------------------------------------------------ configuration (AC-236-02/03)


def test_the_file_key_is_optional_and_parsed():
    plain = validate_document(document())
    assert plain.access.tool_groups is None and access_policy(plain).groups == access.ALL_GROUPS
    assert access_facts(plain) is None
    filed = validate_document(document('[access]\ntool_groups = ["presets", "presets"]\n'))
    assert access_policy(filed).groups == {"core", "presets"}
    assert access_facts(filed) == {
        "profile": "full",
        "capped_devices": 0,
        "tool_groups": "core,presets",
    }
    assert "tool_groups" not in access_facts(validate_document(document("[access]\n")))  # type: ignore[operator]
    assert access_policy(
        validate_document(document('[access]\ntool_groups = ["all"]\n'))
    ).groups == (access.ALL_GROUPS)


@pytest.mark.parametrize(
    ("access_text", "located"),
    [
        ("tool_groups = []", "access.tool_groups: invalid (expected a non-empty list"),
        (f'tool_groups = "{SECRET}"', "access.tool_groups: invalid (expected a non-empty list"),
        ("tool_groups = [1]", "access.tool_groups[0]: invalid"),
        (f'tool_groups = ["presets", "{SECRET}"]', "access.tool_groups[1]: unknown group (valid: "),
        ('tool_groups = ["Presets"]', "access.tool_groups[0]: unknown group"),
        ("tool_groups = [" + ",".join(['"core"'] * 17) + "]", "access.tool_groups: invalid"),
    ],
)
def test_invalid_group_lists_are_positional_and_value_free(access_text, located):
    with pytest.raises(ConfigurationError) as caught:
        validate_document(document(f"[access]\n{access_text}\n"))
    message = str(caught.value)
    assert located in message and SECRET not in message
    assert "core, presets, scenes, layout, signals, diagnostics, discovery, all" in message or (
        "[0]: invalid" in message
    )


def test_option_precedence_is_option_then_file_then_all(tmp_path):
    plain = write_config(tmp_path / "plain")
    filed = write_config(tmp_path / "filed", '[access]\ntool_groups = ["presets"]\n')
    for path, option, expected in (
        (plain, None, access.ALL_GROUPS),
        (plain, "scenes,layout", {"core", "scenes", "layout"}),
        (filed, None, {"core", "presets"}),
        (filed, "signals", {"core", "signals"}),
        (filed, "all", access.ALL_GROUPS),
        (filed, "core", {"core"}),
        (plain, "presets,presets", {"core", "presets"}),
    ):
        loaded = load_config(str(path), str(path.parent), {}, tool_groups=option)
        assert loaded.access.groups == frozenset(expected), (path.parent.name, option)


@pytest.mark.parametrize("value", ["", ",", "presets,", ",presets", f"x{SECRET}", "Presets", "a b"])
def test_invalid_option_values_name_the_position_and_never_echo(tmp_path, value):
    path = write_config(tmp_path)
    with pytest.raises(ConfigurationError) as caught:
        load_config(str(path), str(tmp_path), {}, tool_groups=value)
    message = str(caught.value)
    assert message.startswith("--tool-groups: ") and "at position " in message
    assert "(valid: core, presets, scenes, layout, signals, diagnostics, discovery, all)" in message
    assert SECRET not in message


def test_cli_exits_2_for_an_unknown_group_and_for_a_subcommand_combination(
    tmp_path, capsys, monkeypatch
):
    monkeypatch.setattr(cli.anyio, "run", lambda *args: pytest.fail("must not serve"))
    config = write_config(tmp_path)
    base = ["--config", str(config), "--data-dir", str(tmp_path)]
    code, out, err = run_cli(capsys, *base, "--tool-groups", f"presets,{SECRET}")
    assert (code, out) == (2, "")
    assert err.startswith("Startup configuration error: --tool-groups: unknown group at position 2")
    assert SECRET not in err
    code, out, err = run_cli(capsys, "--tool-groups", "core", "config", "validate")
    assert code == 2 and "Invalid command-line arguments" in err
    bad = write_config(tmp_path / "bad", f'[access]\ntool_groups = ["{SECRET}"]\n')
    code, out, err = run_cli(capsys, "--config", str(bad), "--data-dir", str(bad.parent))
    assert code == 2 and "access.tool_groups[0]: unknown group" in err and SECRET not in err


def test_serve_hands_the_resolved_groups_to_the_service(tmp_path, monkeypatch, capsys):
    config = write_config(tmp_path, '[access]\ntool_groups = ["presets"]\n', DEVICE)
    captured: list[Any] = []
    monkeypatch.setattr(cli.anyio, "run", lambda function, *args: captured.append(args[0]))
    argv = ["--config", str(config), "--data-dir", str(tmp_path)]
    assert cli.main(argv) == 0
    assert captured[-1].access.groups == frozenset({"core", "presets"})
    assert cli.main([*argv, "--tool-groups", "all"]) == 0
    assert captured[-1].access.groups == access.ALL_GROUPS


def test_the_option_has_no_environment_variable(tmp_path, monkeypatch):
    monkeypatch.setenv("WLED_MCP_TOOL_GROUPS", "core")
    path = write_config(tmp_path)
    assert load_config(str(path), str(tmp_path)).access.groups == access.ALL_GROUPS


def test_config_validate_and_doctor_line_report_groups_only_when_set():
    filed = validate_document(document('[access]\ntool_groups = ["scenes"]\n'))
    facts = access_facts(filed)
    assert facts is not None
    assert access_line(facts).endswith(
        "Tool groups (as configured; a serve --tool-groups overrides it): core,scenes."
    )
    plain = access_facts(validate_document(document("[access]\n")))
    assert plain is not None and "Tool groups" not in access_line(plain)


# ------------------------------------------------------------------------- status (AC-236-10)


@pytest.mark.anyio
@pytest.mark.parametrize("groups", [None, ["presets"]])
async def test_the_status_tool_reports_the_effective_groups(tmp_path, groups):
    server, _, _ = served(tmp_path, "control", groups)
    async with Client(server) as client:
        result = await client.call_tool("wled_get_service_status", {})
    assert result.structured_content is not None
    reported = result.structured_content["data"]["access"]["tool_groups"]
    assert reported == sorted(TOOL_GROUPS if groups is None else {"core", *groups})
    assert reported == sorted(reported)
