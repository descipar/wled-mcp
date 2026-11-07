"""Issue #62: the README is a usable entry point that stays consistent with the examples.

Cross-checks README.md against the example files it tells users to copy, the installed
tool registry and the repository tree, and checks that README.md and docs/PROJECT.md
have no broken local links. Each check has a negative control on a mutated copy. No
network or device access.
"""

from __future__ import annotations

import functools
import re
from pathlib import Path
from urllib.parse import urlsplit

import anyio
import pytest

from tests.test_deployment_artifacts import (
    code_lines,
    compose,
    container_command_problems,
    hub_http,
    hub_stdio,
    option,
    service,
)
from tests.test_inventory_client import config
from wled_mcp.operations import build_operations
from wled_mcp.resources import Resources

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
PROJECT = ROOT / "docs/PROJECT.md"
EXAMPLES = (
    "examples/compose.http.example.yaml",
    "examples/mcphub.http.example.json",
    "examples/mcphub.example.json",
    "examples/devices.example.toml",
)
LINK = re.compile(r"\]\(([^)\s]+)\)")


def slug(heading: str) -> str:
    """GitHub's anchor for a Markdown heading."""
    text = re.sub(r"[^\w\- ]", "", heading.strip().lower())
    return text.replace(" ", "-")


def anchors(path: Path) -> set[str]:
    text = re.sub(r"```.*?```", "", path.read_text("utf-8"), flags=re.S)
    return {slug(match) for match in re.findall(r"^#{1,6} (.+)$", text, flags=re.M)}


def link_problems(path: Path, text: str) -> list[str]:
    """Local links in ``text`` (read as ``path``) whose file or heading anchor is missing."""
    problems = []
    for target in LINK.findall(text):
        if "://" in target or target.startswith("mailto:"):
            continue
        local, _, anchor = target.partition("#")
        resolved = (path.parent / local).resolve() if local else path
        if not resolved.exists():
            problems.append(f"{path.name}: missing {target}")
        elif anchor and resolved.suffix == ".md" and anchor not in anchors(resolved):
            problems.append(f"{path.name}: missing anchor {target}")
    return problems


def hint_class(operation) -> str:
    if operation.annotations.read_only_hint:
        return "read-only"
    return "destructive" if operation.annotations.destructive_hint else "write"


@functools.cache
def tool_hints() -> dict[str, str]:
    """Hint class of every registered tool, from the real registry's annotations."""

    async def collect() -> dict[str, str]:
        # A synthetic inventory; building the registry contacts no device.
        async with Resources(config(ROOT / ".artifacts")) as resources:
            return {op.name: hint_class(op) for op in build_operations(resources)}

    return dict(anyio.run(collect))


def readme_tool_rows(text: str) -> dict[str, str]:
    return dict(re.findall(r"^\| `(wled_[a-z_]+)` \| ([a-z-]+) \|", text, flags=re.M))


def readme_problems(text: str, hints: dict[str, str]) -> list[str]:
    """What the README must state so that a new user can follow it (R62-2, R62-3)."""
    problems = []
    flat = " ".join(text.split())
    targets = {target.split("#", 1)[0] for target in LINK.findall(text)}
    for example in EXAMPLES:
        if example not in targets:
            problems.append(f"README does not link {example}")
    stdio = hub_stdio()
    command = " ".join([stdio["command"], *stdio["args"]])
    if command not in [" ".join(line.split()) for line in code_lines(text)]:
        problems.append("README uvx command differs from examples/mcphub.example.json")
    url = hub_http()["url"]
    if f"`{url}`" not in text:
        problems.append("README HTTP URL differs from examples/mcphub.http.example.json")
    allowed = option(service()["command"], "--allowed-host")
    if allowed != urlsplit(url).netloc or f"`--allowed-host {allowed}`" not in flat:
        problems.append("README Host allowlist differs from the Compose example")
    secret = compose()["secrets"]["wled_mcp_http_token"]["file"].removeprefix("./")
    if f"> {secret})" not in text or f"`{secret}`" not in text:
        problems.append("README does not create and name the Compose credential file")
    problems.extend(container_command_problems(text, compose()["name"]))
    if readme_tool_rows(text) != hints:
        problems.append("README tool table differs from the registered tools and hints")
    if not re.search(r"not affiliated with[^.]*WLED project[^.]*MCPHub", flat):
        problems.append("README lacks the non-affiliation statement")
    if "Apache License 2.0" not in flat or "(NOTICE)" not in flat:
        problems.append("README does not state the Apache-2.0 license and NOTICE file")
    for section in (
        "## Requirements",
        "## Quickstart: stdio via uvx",
        "## Quickstart: Streamable HTTP service",
        "## Inventory",
        "## Safety model",
        "## Validation status and limitations",
    ):
        if section + "\n" not in text:
            problems.append(f"README lacks section {section!r}")
    for term in (
        "dry_run",
        "possibly applied",
        "snapshot",
        "No discovery",
        "WLED 16.0.1",
        "Hardware acceptance is partial",
        "(H07) moved to stage 2 ([#25](https://github.com/descipar/wled-mcp/issues/25))",
    ):
        if term not in flat:
            problems.append(f"README safety/validation text lacks {term!r}")
    return problems


def test_readme_follows_the_examples_registry_and_safety_model():
    assert readme_problems(README.read_text("utf-8"), tool_hints()) == []


def test_registry_has_the_twelve_documented_tools():
    hints = tool_hints()
    assert len(hints) == 12
    assert sorted(set(hints.values())) == ["destructive", "read-only", "write"]


@pytest.mark.parametrize("path", [README, PROJECT], ids=lambda path: path.name)
def test_local_links_and_anchors_resolve(path):
    assert link_problems(path, path.read_text("utf-8")) == []


def test_link_check_rejects_missing_files_and_anchors():
    text = README.read_text("utf-8")
    broken = text.replace("(docs/DEPLOYMENT.md#changing-the-inventory)", "(docs/DEPLOY.md)", 1)
    assert "README.md: missing docs/DEPLOY.md" in link_problems(README, broken)
    broken = text.replace("#changing-the-inventory)", "#changing-inventory)", 1)
    assert "README.md: missing anchor docs/DEPLOYMENT.md#changing-inventory" in link_problems(
        README, broken
    )


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        (
            "(examples/mcphub.http.example.json)",
            "(docs/DEPLOYMENT.md)",
            "README does not link examples/mcphub.http.example.json",
        ),
        (
            "--isolated --python 3.13",
            "--python 3.13 --isolated",
            "README uvx command differs from examples/mcphub.example.json",
        ),
        (
            "`http://wled-mcp:8000/mcp`",
            "`http://wled-mcp:8080/mcp`",
            "README HTTP URL differs from examples/mcphub.http.example.json",
        ),
        (
            "`--allowed-host wled-mcp:8000`",
            "`--allowed-host localhost:8000`",
            "README Host allowlist differs from the Compose example",
        ),
        (
            "> secrets/wled_mcp_http_token)",
            "> token.txt)",
            "README does not create and name the Compose credential file",
        ),
        (
            "docker compose -p wled-mcp-http -f compose.yaml ps",
            "docker compose ps",
            "unscoped compose command:    docker compose ps",
        ),
        (
            "| `wled_delete_preset` | destructive |",
            "| `wled_delete_preset` | write |",
            "README tool table differs from the registered tools and hints",
        ),
        (
            "| `wled_get_preset` | read-only |",
            "| `wled_get_presets` | read-only |",
            "README tool table differs from the registered tools and hints",
        ),
        (
            "It is not affiliated with",
            "It is affiliated with",
            "README lacks the non-affiliation statement",
        ),
        (
            "Hardware acceptance is partial:",
            "Hardware acceptance is complete:",
            "README safety/validation text lacks 'Hardware acceptance is partial'",
        ),
        (
            "## Safety model",
            "## Safety",
            "README lacks section '## Safety model'",
        ),
        (
            "is reported as\n  possibly applied",
            "is reported as\n  failed",
            "README safety/validation text lacks 'possibly applied'",
        ),
    ],
)
def test_readme_check_rejects_regressions(old, new, expected):
    text = README.read_text("utf-8")
    assert old in text
    assert expected in readme_problems(text.replace(old, new), tool_hints())
