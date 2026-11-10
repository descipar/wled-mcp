"""Expected MCP tool contract: the one hand-maintained list of tools (ISSUE-98-DEC-001).

Standard library only, so it stays an expectation and never a copy of the registry.
Tests compare the real registry and every served ``tools/list`` with it, and
``scripts/check_distribution.py`` loads it by path from the source checkout.

A pull request that adds a tool adds one ``ExpectedTool`` entry here at its registry
position, with its class (ISSUE-20-DEC-001 vocabulary) and its destructive flag.
"""

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType


class ToolClass(StrEnum):
    """Tool classes of ISSUE-20-DEC-001; profiles include whole classes."""

    READ = "read"
    CONTROL = "control"
    MANAGE = "manage"


@dataclass(frozen=True)
class ExpectedTool:
    name: str
    tool_class: ToolClass
    destructive: bool


READ = ToolClass.READ
CONTROL = ToolClass.CONTROL
MANAGE = ToolClass.MANAGE

# Registry order; the only tool list in the test suite.
EXPECTED_TOOLS: tuple[ExpectedTool, ...] = (
    ExpectedTool("wled_list_devices", READ, destructive=False),
    ExpectedTool("wled_get_service_status", READ, destructive=False),
    ExpectedTool("wled_get_state", READ, destructive=False),
    ExpectedTool("wled_get_effects", READ, destructive=False),
    ExpectedTool("wled_get_palettes", READ, destructive=False),
    ExpectedTool("wled_search_effects", READ, destructive=False),
    ExpectedTool("wled_get_live_snapshot", READ, destructive=False),
    ExpectedTool("wled_set_state", CONTROL, destructive=False),
    ExpectedTool("wled_patch_segments", CONTROL, destructive=False),
    ExpectedTool("wled_replace_layout", CONTROL, destructive=True),
    ExpectedTool("wled_list_presets", READ, destructive=False),
    ExpectedTool("wled_get_preset", READ, destructive=False),
    ExpectedTool("wled_activate_preset", CONTROL, destructive=False),
    ExpectedTool("wled_save_preset", MANAGE, destructive=True),
    ExpectedTool("wled_delete_preset", MANAGE, destructive=True),
    ExpectedTool("wled_list_snapshots", READ, destructive=False),
    ExpectedTool("wled_restore_preset", MANAGE, destructive=True),
    ExpectedTool("wled_store_preset", MANAGE, destructive=True),
    ExpectedTool("wled_save_playlist", MANAGE, destructive=True),
    ExpectedTool("wled_export_presets", READ, destructive=False),
    ExpectedTool("wled_import_presets", MANAGE, destructive=True),
    ExpectedTool("wled_list_groups", READ, destructive=False),
    ExpectedTool("wled_save_group", MANAGE, destructive=True),
    ExpectedTool("wled_delete_group", MANAGE, destructive=True),
    ExpectedTool("wled_list_scenes", READ, destructive=False),
    ExpectedTool("wled_save_scene", MANAGE, destructive=True),
    ExpectedTool("wled_delete_scene", MANAGE, destructive=True),
    ExpectedTool("wled_plan_scene", READ, destructive=False),
    ExpectedTool("wled_apply_scene", CONTROL, destructive=False),
    ExpectedTool("wled_list_zones", READ, destructive=False),
    ExpectedTool("wled_plan_zone", READ, destructive=False),
    ExpectedTool("wled_apply_zone", CONTROL, destructive=False),
)

# Cumulative profiles (ISSUE-20-DEC-001); expectation data only, enforcement is #20.
PROFILE_CLASSES: Mapping[str, frozenset[ToolClass]] = MappingProxyType(
    {
        "read-only": frozenset({READ}),
        "control": frozenset({READ, CONTROL}),
        "full": frozenset({READ, CONTROL, MANAGE}),
    }
)
DEFAULT_PROFILE = "full"

NAME_PATTERN = re.compile(r"^wled_[a-z0-9_]+$")


def expected_tool(name: str) -> ExpectedTool:
    """The entry for one expected tool; KeyError names an unknown tool."""
    for tool in EXPECTED_TOOLS:
        if tool.name == name:
            return tool
    raise KeyError(name)


def expected_names(profile: str = DEFAULT_PROFILE) -> list[str]:
    """Ordered tool names a server with ``profile`` registers and serves."""
    classes = PROFILE_CLASSES[profile]
    return [tool.name for tool in EXPECTED_TOOLS if tool.tool_class in classes]


def names_of(*classes: ToolClass) -> frozenset[str]:
    """Names of the expected tools in any of ``classes``."""
    return frozenset(tool.name for tool in EXPECTED_TOOLS if tool.tool_class in classes)


def destructive_names() -> frozenset[str]:
    return frozenset(tool.name for tool in EXPECTED_TOOLS if tool.destructive)


def contract_problems(actual: Sequence[str], profile: str = DEFAULT_PROFILE) -> list[str]:
    """Differences between actual ordered tool names and the expectation, both directions.

    Reports tools that are present but not expected, expected but missing, listed more
    than once, and a different order of the common tools. An empty list means equal.
    """
    expected = expected_names(profile)
    counts = Counter(actual)
    seen = set(counts)
    problems = [
        f"duplicate: {name} is listed {count} times" for name, count in counts.items() if count > 1
    ]
    problems += [
        f"unexpected: {name} is present but not expected for profile {profile}"
        for name in dict.fromkeys(actual)
        if name not in expected
    ]
    problems += [
        f"missing: {name} is expected for profile {profile} but not present"
        for name in expected
        if name not in seen
    ]
    common_actual = [name for name in dict.fromkeys(actual) if name in expected]
    common_expected = [name for name in expected if name in seen]
    if common_actual != common_expected:
        problems.append(f"order: {common_actual} differs from expected {common_expected}")
    return problems


def contract_invariant_problems() -> list[str]:
    """Self-consistency of the expectation data (unique, well-formed names)."""
    names = [tool.name for tool in EXPECTED_TOOLS]
    problems = [f"duplicate expected tool: {name}" for name in names if names.count(name) > 1]
    problems += [f"malformed tool name: {name}" for name in names if not NAME_PATTERN.match(name)]
    if DEFAULT_PROFILE not in PROFILE_CLASSES:
        problems.append(f"default profile {DEFAULT_PROFILE} is not defined")
    return problems
