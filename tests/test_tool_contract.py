"""Registry and distribution check against the expected tool contract (#98, T98-01..06).

The registry is built on a synthetic inventory; nothing contacts a device.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from dataclasses import replace
from pathlib import Path
from types import ModuleType

import anyio
import pytest

from tests.test_inventory_client import config
from tests.tool_contract import (
    DEFAULT_PROFILE,
    EXPECTED_TOOLS,
    IDEMPOTENT_CONTROL_TOOLS,
    PROFILE_CLASSES,
    ToolClass,
    contract_invariant_problems,
    contract_problems,
    expected_names,
    expected_tool,
    names_of,
)
from wled_mcp.operations import build_operations
from wled_mcp.resources import Resources
from wled_mcp.server import Operation

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "tests" / "tool_contract.py"


def registry(tmp_path: Path) -> list[Operation]:
    async def collect() -> list[Operation]:
        async with Resources(config(tmp_path)) as resources:
            return list(build_operations(resources))

    return anyio.run(collect)


def load_script(name: str) -> ModuleType:
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# ----------------------------------------------------------------- T98-01 helper data


def test_contract_data_is_self_consistent():
    assert contract_invariant_problems() == []
    assert EXPECTED_TOOLS, "the contract lists the registered tools"
    assert all(isinstance(tool.tool_class, ToolClass) for tool in EXPECTED_TOOLS)
    assert all(isinstance(tool.destructive, bool) for tool in EXPECTED_TOOLS)


def test_contract_module_imports_only_the_standard_library():
    tree = ast.parse(CONTRACT.read_text("utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0 and node.module is not None
            imported.add(node.module.split(".")[0])
    assert imported <= sys.stdlib_module_names, imported - sys.stdlib_module_names


def test_profiles_are_cumulative_and_default_to_all_tools():
    # ISSUE-20-DEC-001: read-only < control < full; the default profile is full.
    read_only, control, full = (set(expected_names(p)) for p in ("read-only", "control", "full"))
    assert read_only < control < full
    assert DEFAULT_PROFILE == "full"
    assert expected_names() == [tool.name for tool in EXPECTED_TOOLS]
    assert read_only == names_of(ToolClass.READ)
    assert control - read_only == names_of(ToolClass.CONTROL)
    assert full - control == names_of(ToolClass.MANAGE)
    assert set(PROFILE_CLASSES) == {"read-only", "control", "full"}


def test_profile_expectations_keep_registry_order():
    order = expected_names()
    for profile in PROFILE_CLASSES:
        names = expected_names(profile)
        assert names == sorted(names, key=order.index), profile


def test_read_tools_are_never_flagged_destructive():
    assert not any(tool.destructive for tool in EXPECTED_TOOLS if tool.tool_class is ToolClass.READ)


def test_expected_tool_lookup_rejects_unknown_names():
    first = EXPECTED_TOOLS[0]
    assert expected_tool(first.name) is first
    with pytest.raises(KeyError):
        expected_tool("wled_not_a_tool")


# ------------------------------------------------------------ T98-02 registry parity


def test_registry_matches_the_contract_in_both_directions(tmp_path):
    assert contract_problems([operation.name for operation in registry(tmp_path)]) == []


def test_extra_registered_tool_is_reported_as_unexpected(tmp_path):
    operations = registry(tmp_path)
    extra = replace(operations[0], name="wled_synthetic_extra")
    problems = contract_problems([operation.name for operation in [*operations, extra]])
    assert len(problems) == 1
    assert problems[0].startswith("unexpected: wled_synthetic_extra ")


def test_contract_tool_absent_from_the_registry_is_reported_as_missing(tmp_path):
    names = [operation.name for operation in registry(tmp_path)]
    absent = names.pop(len(names) // 2)
    assert contract_problems(names) == [
        f"missing: {absent} is expected for profile {DEFAULT_PROFILE} but not present"
    ]


def test_swapped_registry_order_is_reported(tmp_path):
    names = [operation.name for operation in registry(tmp_path)]
    names[0], names[1] = names[1], names[0]
    problems = contract_problems(names)
    assert len(problems) == 1 and problems[0].startswith("order: ")


def test_duplicate_and_profile_specific_problems():
    names = expected_names()
    assert contract_problems([*names, names[0]]) == [f"duplicate: {names[0]} is listed 2 times"]
    # Served by a full server but not expected for a read-only profile.
    problems = contract_problems(names, profile="read-only")
    assert sorted(problems) == sorted(
        f"unexpected: {name} is present but not expected for profile read-only"
        for name in names_of(ToolClass.CONTROL, ToolClass.MANAGE)
    )
    assert contract_problems(expected_names("read-only"), profile="read-only") == []


# -------------------------------------------------------------- T98-03 annotations


def test_registry_annotations_follow_the_contract_classes(tmp_path):
    operations = registry(tmp_path)
    assert operations, "the registry builds operations"
    for operation in operations:
        expected = expected_tool(operation.name)
        is_read = expected.tool_class is ToolClass.READ
        hints = operation.annotations
        assert hints.read_only_hint is is_read, operation.name
        assert hints.destructive_hint is expected.destructive, operation.name
        assert hints.idempotent_hint is (is_read or operation.name in IDEMPOTENT_CONTROL_TOOLS), (
            operation.name
        )
        assert hints.open_world_hint is False, operation.name


# ------------------------------------------------------- T98-05 distribution check


def test_distribution_check_loads_the_source_contract():
    script = load_script("check_distribution")
    assert script.CONTRACT_PATH == CONTRACT
    assert script.EXPECTED_TOOL_NAMES == expected_names()


def test_distribution_check_follows_a_changed_contract(tmp_path):
    script = load_script("check_distribution")
    changed = tmp_path / "tool_contract.py"
    source = CONTRACT.read_text("utf-8")
    entry = '    ExpectedTool("wled_list_devices", READ, destructive=False),\n'
    assert source.count(entry) == 1
    extra = '    ExpectedTool("wled_synthetic_extra", MANAGE, destructive=True),\n'
    changed.write_text(source.replace(entry, entry + extra), encoding="utf-8")
    names = script.expected_tool_names(changed)
    assert names[:2] == [expected_names()[0], "wled_synthetic_extra"]
    assert names[2:] == expected_names()[1:]


def test_distribution_check_rejects_an_unusable_contract(tmp_path):
    script = load_script("check_distribution")
    broken = tmp_path / "tool_contract.py"
    broken.write_text("def expected_names():\n    return []\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="ordered list of tool names"):
        script.expected_tool_names(broken)


# ------------------------------------------------------------- T98-06 probe guards


def test_hardware_read_only_probe_plan_uses_only_read_tools():
    probe = load_script("hw_read_only_probe")
    assert probe.READ_ONLY_TOOLS <= names_of(ToolClass.READ)
