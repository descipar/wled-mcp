"""Issue #236: the documented group cost table and example configurations stay honest.

The table in docs/contract/profiles.md ("Token cost") must match the live registry (tool counts
exactly, characters and tokens within 3 %), and every ```toml tool-group-example block must
validate.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from mcp.client import Client

from tests.test_access_profiles import served
from tests.test_tool_budget import cost
from tests.tool_contract import EXPECTED_TOOLS, TOOL_GROUPS
from wled_mcp.config import access_policy, validate_document

PROFILES_DOC = Path(__file__).resolve().parents[1] / "docs/contract/profiles.md"
TOLERANCE = 0.03
COLUMNS = ("full", "control", "read-only")


def parse_table(text: str) -> dict[str, list[tuple[int, int, int]]]:
    block = re.search(r"<!-- group-cost:start -->(.*?)<!-- group-cost:end -->", text, re.S)
    assert block, "profiles.md lacks the group-cost block"
    rows: dict[str, list[tuple[int, int, int]]] = {}
    for line in block.group(1).splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 7 or cells[0] in ("Group", "---"):
            continue
        values = []
        for index in range(3):
            count = int(cells[1 + 2 * index])
            chars, tokens = re.fullmatch(r"(\d+) \((\d+)\)", cells[2 + 2 * index]).groups()  # type: ignore[union-attr]
            values.append((count, int(chars), int(tokens)))
        rows[cells[0]] = values
    return rows


@pytest.mark.anyio
async def test_the_documented_group_costs_match_the_registry_within_three_percent(tmp_path):
    documented = parse_table(PROFILES_DOC.read_text("utf-8"))
    assert set(documented) == {*TOOL_GROUPS, "all groups"}
    group_of = {tool.name: tool.group for tool in EXPECTED_TOOLS}
    problems = []
    for column, profile in enumerate(COLUMNS):
        server, _, _ = served(tmp_path / profile, profile)
        async with Client(server) as client:
            tools = (await client.list_tools()).tools
        measured = {group: [0, 0] for group in (*TOOL_GROUPS, "all groups")}
        for tool in tools:
            for key in (group_of[tool.name], "all groups"):
                measured[key][0] += 1
                measured[key][1] += cost(tool)
        for group, (count, chars) in measured.items():
            doc_count, doc_chars, doc_tokens = documented[group][column]
            tokens = round(chars / 3.5)
            if doc_count != count:
                problems.append(f"{group}/{profile}: {count} tools, documented {doc_count}")
            for label, doc, now in (("chars", doc_chars, chars), ("tokens", doc_tokens, tokens)):
                if abs(doc - now) > TOLERANCE * now:
                    problems.append(f"{group}/{profile}: {label} measured {now}, documented {doc}")
    assert not problems, (
        "docs/contract/profiles.md 'Token cost' table is stale; update it and the examples "
        f"deliberately: {problems}"
    )


def test_every_tool_group_example_validates():
    text = PROFILES_DOC.read_text("utf-8")
    blocks = re.findall(r"```toml tool-group-example\n(.*?)```", text, re.S)
    assert len(blocks) >= 3
    device = '[[devices]]\nid = "desk"\nname = "Example desk"\nbase_url = "http://192.0.2.10"\n'
    for block in blocks:
        validated = validate_document((block + device).encode())
        groups = access_policy(validated).groups
        assert "core" in groups and groups <= frozenset(TOOL_GROUPS)
