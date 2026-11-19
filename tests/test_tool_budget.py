"""#235: the served tool list is the main fixed token cost, so its size is guarded.

A client sends the name, description and input schema of every registered tool with each model
request. The limits below sit a few percent above the measured size after the slimming of
#235 (docs/validation/issue-235.md). Growth is allowed, but it must be a deliberate decision:
raise the number here and record the new measurement in that document.

The second half checks that the served guidance resolves: every tool name and every
``field=true``-style reference in the served instructions, prompt and tool descriptions names
something that exists.
"""

from __future__ import annotations

import json
import re

import pytest
from mcp.client import Client

from tests.test_access_profiles import served
from wled_mcp.guidance import INSTRUCTIONS, PROMPT_DESCRIPTION, PROMPT_TEXT

# Characters of compact JSON: name + description + input schema, one tool.
TOOL_BUDGET = {
    "wled_list_devices": 350,
    "wled_get_service_status": 400,
    "wled_get_state": 400,
    "wled_get_effects": 1000,
    "wled_get_palettes": 400,
    "wled_search_effects": 1750,
    "wled_get_live_snapshot": 650,
    "wled_explain_lighting": 1350,
    "wled_set_state": 1350,
    "wled_patch_segments": 7250,
    "wled_replace_layout": 7550,
    "wled_list_presets": 450,
    "wled_get_preset": 500,
    "wled_activate_preset": 600,
    "wled_save_preset": 1150,
    "wled_delete_preset": 700,
    "wled_list_snapshots": 600,
    "wled_restore_preset": 1100,
    "wled_store_preset": 4600,
    "wled_save_playlist": 2150,
    "wled_export_presets": 900,
    "wled_import_presets": 2150,
    "wled_list_groups": 650,
    "wled_save_group": 2000,
    "wled_delete_group": 650,
    "wled_list_scenes": 900,
    "wled_save_scene": 2600,
    "wled_delete_scene": 600,
    "wled_plan_scene": 1050,
    "wled_apply_scene": 1600,
    "wled_list_zones": 750,
    "wled_plan_zone": 1950,
    "wled_apply_zone": 2150,
    "wled_apply_room": 2300,
    "wled_preview_layout": 7650,
    "wled_start_signal": 2650,
    "wled_get_signal_status": 800,
    "wled_cancel_signal": 800,
    "wled_discover_devices": 1000,
    "wled_set_discovery_ranges": 800,
    "wled_add_device": 1200,
}
# The same measure summed over the tools a profile serves.
PROFILE_BUDGET = {"full": 68000, "control": 48800, "read-only": 22400}

GROW = (
    "The served tool list grew past its budget. If the growth is deliberate, raise the limit in "
    "tests/test_tool_budget.py and record the new measurement in the issue-235 validation notes."
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def size(value: object) -> int:
    return len(json.dumps(value, separators=(",", ":"), ensure_ascii=False))


def cost(tool) -> int:
    return size(tool.name) + size(tool.description or "") + size(tool.input_schema)


async def listing(tmp_path, profile: str):
    server, _resources, _router = served(tmp_path, profile)
    async with Client(server) as client:
        return (await client.session.list_tools()).tools


@pytest.mark.anyio
async def test_every_served_tool_has_a_budget_and_stays_within_it(tmp_path):
    tools = await listing(tmp_path, "full")
    assert {tool.name for tool in tools} == set(TOOL_BUDGET), (
        "a tool was added or removed: update TOOL_BUDGET in tests/test_tool_budget.py "
        "and the issue-235 validation notes"
    )
    over = {tool.name: (cost(tool), TOOL_BUDGET[tool.name]) for tool in tools}
    over = {name: pair for name, pair in over.items() if pair[0] > pair[1]}
    assert not over, f"{GROW} Over budget (size, limit): {over}"


@pytest.mark.anyio
@pytest.mark.parametrize("profile", sorted(PROFILE_BUDGET))
async def test_profile_total_stays_within_its_budget(tmp_path, profile):
    tools = await listing(tmp_path, profile)
    total = sum(cost(tool) for tool in tools)
    assert total <= PROFILE_BUDGET[profile], f"{GROW} Profile {profile}: {total} characters."


@pytest.mark.anyio
async def test_served_schemas_carry_no_generated_titles_or_null_defaults(tmp_path):
    """The slimming reaches every served schema, including nested definitions."""
    tools = await listing(tmp_path, "full")
    assert tools

    def walk(node, where):
        if isinstance(node, list):
            for index, item in enumerate(node):
                walk(item, f"{where}/{index}")
        elif isinstance(node, dict):
            assert not isinstance(node.get("title"), str), where
            if "anyOf" in node:
                assert node.get("default", 0) is not None, where
            for key, child in node.items():
                if key in ("properties", "$defs"):
                    for name, sub in child.items():
                        walk(sub, f"{where}/{key}/{name}")
                elif key not in ("default", "enum", "const", "examples"):
                    walk(child, f"{where}/{key}")

    for tool in tools:
        walk(tool.input_schema, f"{tool.name}/input")
        walk(tool.output_schema, f"{tool.name}/output")


# ------------------------------------------------------------------ guidance resolution


TOOL_REFERENCE = re.compile(r"\bwled_[a-z][a-z_]*[a-z]\b")
FIELD_REFERENCE = re.compile(r"\b([a-z][a-z0-9_]*)=(?:true|false)\b")


def property_names(schema: dict) -> set[str]:
    names: set[str] = set()
    for model in [schema, *schema.get("$defs", {}).values()]:
        names.update(model.get("properties", {}))
    return names


@pytest.mark.anyio
async def test_served_guidance_resolves_every_tool_and_field_reference(tmp_path):
    server, _resources, _router = served(tmp_path, "full")
    async with Client(server) as client:
        tools = (await client.session.list_tools()).tools
        assert client.instructions == INSTRUCTIONS
        prompt = await client.get_prompt("change_lighting_safely")
    names = {tool.name for tool in tools}
    properties = {tool.name: property_names(tool.input_schema) for tool in tools}
    everything = set().union(*properties.values())

    texts = {
        "instructions": INSTRUCTIONS,
        "prompt description": PROMPT_DESCRIPTION,
        "prompt": PROMPT_TEXT,
        **{tool.name: tool.description or "" for tool in tools},
    }
    assert prompt.messages[0].content.text == PROMPT_TEXT
    unresolved = []
    for source, text in texts.items():
        for reference in TOOL_REFERENCE.findall(text):
            if reference not in names:
                unresolved.append(f"{source}: tool {reference}")
        mentioned = set(TOOL_REFERENCE.findall(text)) & names
        known = (
            everything
            if source not in names
            else properties[source].union(*(properties[other] for other in mentioned))
        )
        for field in FIELD_REFERENCE.findall(text):
            if field not in known:
                unresolved.append(f"{source}: field {field}")
    assert not unresolved, unresolved
