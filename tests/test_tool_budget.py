"""#235: the served tool list is the main fixed token cost, so its size is guarded.

A client sends the name, description and input schema of every registered tool with each model
request. The limits below sit a few percent above the measured size after the slimming of
#235 and the simplified segment schema of #246 (docs/validation/m7-m8.md). Growth is allowed,
but it must be a deliberate decision: raise the number here and record the new measurement in
that document.

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
from tests.tool_contract import EXPECTED_TOOLS
from wled_mcp.guidance import PROMPT_DESCRIPTION, PROMPT_TEXT
from wled_mcp.schema_slim import SEGMENT_MODEL_NAMES

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
    "wled_patch_segments": 6000,
    "wled_replace_layout": 6350,
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
    "wled_preview_layout": 6400,
    "wled_start_signal": 2650,
    "wled_get_signal_status": 800,
    "wled_cancel_signal": 800,
    "wled_discover_devices": 1000,
    "wled_set_discovery_ranges": 800,
    "wled_add_device": 1200,
}
# The same measure summed over the tools a profile serves.
PROFILE_BUDGET = {"full": 64850, "control": 45450, "read-only": 21850}

# The same measure summed over the tools of one group in the ``full`` profile (#236). Groups
# are disjoint, so a selection costs the sum of its groups.
GROUP_BUDGET = {
    "core": 11700,
    "presets": 14850,
    "scenes": 17450,
    "layout": 12950,
    "signals": 4250,
    "diagnostics": 2050,
    "discovery": 3050,
}

GROW = (
    "The served tool list grew past its budget. If the growth is deliberate, raise the limit in "
    "tests/test_tool_budget.py and record the new measurement in the issue-235/246 validation "
    "notes."
)


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
        "and the issue-235/246 validation notes"
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
async def test_each_tool_group_stays_within_its_budget(tmp_path):
    tools = await listing(tmp_path, "full")
    group_of = {tool.name: tool.group for tool in EXPECTED_TOOLS}
    assert set(GROUP_BUDGET) == set(group_of.values())
    totals: dict[str, int] = dict.fromkeys(GROUP_BUDGET, 0)
    for tool in tools:
        totals[group_of[tool.name]] += cost(tool)
    over = {g: (n, GROUP_BUDGET[g]) for g, n in totals.items() if n > GROUP_BUDGET[g]}
    assert not over, f"{GROW} Over group budget (size, limit): {over}"


@pytest.mark.anyio
async def test_segment_models_advertise_no_null_branch_for_optional_fields(tmp_path):
    """#246: the served segment definitions list the non-null form of each optional field."""
    tools = {tool.name: tool for tool in await listing(tmp_path, "full")}
    for name in ("wled_patch_segments", "wled_replace_layout", "wled_preview_layout"):
        defs = tools[name].input_schema["$defs"]
        for model in SEGMENT_MODEL_NAMES:
            if model not in defs:
                continue
            required = set(defs[model].get("required", ()))
            for field, prop in defs[model]["properties"].items():
                nulls = [o for o in prop.get("anyOf", []) if o == {"type": "null"}]
                assert not nulls or field in required, f"{name}/{model}/{field}"


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


# Representative (profile, groups) configurations: the instructions and every tool description
# must resolve under each (the instructions name only registered tools, #236).
GUIDANCE_CONFIGS = [
    ("full", None),
    ("full", ["core"]),
    ("control", ["core", "presets"]),
    ("read-only", ["diagnostics", "signals"]),
    ("full", ["scenes", "discovery"]),
]


@pytest.mark.anyio
@pytest.mark.parametrize(("profile", "groups"), GUIDANCE_CONFIGS)
async def test_served_guidance_resolves_every_tool_and_field_reference(tmp_path, profile, groups):
    server, _resources, _router = served(tmp_path, profile, groups)
    async with Client(server) as client:
        tools = (await client.session.list_tools()).tools
        instructions = client.instructions or ""
        prompt = await client.get_prompt("change_lighting_safely")
    names = {tool.name for tool in tools}
    full_set = profile == "full" and groups is None
    properties = {tool.name: property_names(tool.input_schema) for tool in tools}
    everything = set().union(*properties.values())

    texts = {
        "instructions": instructions,
        "prompt description": PROMPT_DESCRIPTION,
        "prompt": PROMPT_TEXT,
        **{tool.name: tool.description or "" for tool in tools},
    }
    assert prompt.messages[0].content.text == PROMPT_TEXT
    unresolved = []
    for source, text in texts.items():
        for reference in TOOL_REFERENCE.findall(text):
            if reference not in names and (source == "instructions" or profile == "full"):
                # Descriptions of a profile-limited server may still name a tool of their own
                # group that the profile removed (schemas stay unchanged, #236).
                unresolved.append(f"{source}: tool {reference}")
        mentioned = set(TOOL_REFERENCE.findall(text)) & names
        known = (
            everything
            if source not in names
            else properties[source].union(*(properties[other] for other in mentioned))
        )
        # The static safety sentences and the prompt keep their write-field wording on
        # restricted servers (#236, DEC-028); only the tool descriptions are field-checked.
        for field in FIELD_REFERENCE.findall(text) if (source in names or full_set) else ():
            if field not in known:
                unresolved.append(f"{source}: field {field}")
    assert not unresolved, unresolved
