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
CONTRIBUTING = ROOT / "CONTRIBUTING.md"
QUICKSTARTS = ROOT / "docs/QUICKSTARTS.md"
TOOL_CONTRACT = ROOT / "docs/TOOL-CONTRACT.md"
EXAMPLES = (
    "examples/compose.http.example.yaml",
    "examples/mcphub.http.example.json",
    "examples/mcphub.example.json",
    "examples/devices.example.toml",
)
LINK = re.compile(r"\]\(([^)\s]+)\)")
# README.md is also the PyPI project page, where relative links do not resolve (#22,
# ISSUE-22-DEC-005): it links repository files by these absolute URLs.
REPOSITORY = "https://github.com/descipar/wled-mcp/"
REPOSITORY_PREFIXES = (REPOSITORY + "blob/main/", REPOSITORY + "tree/main/")
REFERENCE_DEFINITION = re.compile(r"^ {0,3}\[[^\]]+\]:\s*(\S+)", re.M)
HTML_TARGET = re.compile(r"""\b(?:href|src)\s*=\s*["']?([^"'\s>]+)""", re.I)


def slug(heading: str) -> str:
    """GitHub's anchor for a Markdown heading."""
    text = re.sub(r"[^\w\- ]", "", heading.strip().lower())
    return text.replace(" ", "-")


def anchors(path: Path) -> set[str]:
    text = re.sub(r"```.*?```", "", path.read_text("utf-8"), flags=re.S)
    return {slug(match) for match in re.findall(r"^#{1,6} (.+)$", text, flags=re.M)}


def repository_path(target: str) -> str | None:
    """The checkout path of an absolute link to a file or directory on ``main``, else None."""
    for prefix in REPOSITORY_PREFIXES:
        if target.startswith(prefix):
            return target.removeprefix(prefix)
    return None


def link_targets(text: str) -> set[str]:
    """Link targets without anchor; absolute repository links as checkout paths."""
    targets = set()
    for target in LINK.findall(text):
        target = target.split("#", 1)[0]
        targets.add(repository_path(target) or target)
    return targets


def link_problems(path: Path, text: str) -> list[str]:
    """Local links in ``text`` (read as ``path``) whose file or heading anchor is missing.

    Absolute links to files or directories on ``main`` of this repository are checked
    against the checkout, like relative links.
    """
    problems = []
    for target in LINK.findall(text):
        in_repository = repository_path(target)
        if in_repository is None and ("://" in target or target.startswith("mailto:")):
            continue
        local, _, anchor = (in_repository if in_repository is not None else target).partition("#")
        if in_repository is not None:
            resolved = (ROOT / local).resolve() if local else ROOT
        else:
            resolved = (path.parent / local).resolve() if local else path
        if not resolved.exists():
            problems.append(f"{path.name}: missing {target}")
        elif anchor and resolved.suffix == ".md" and anchor not in anchors(resolved):
            problems.append(f"{path.name}: missing anchor {target}")
    return problems


def relative_link_problems(text: str) -> list[str]:
    """Links that do not resolve on the PyPI project page: anything but https and mailto.

    Covers inline links and images, reference definitions and HTML ``href``/``src``.
    """
    targets = [
        *LINK.findall(text),
        *REFERENCE_DEFINITION.findall(text),
        *HTML_TARGET.findall(text),
    ]
    return [
        f"not an https or mailto link: {target}"
        for target in targets
        if not target.startswith(("https://", "mailto:"))
    ]


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


def contract_tool_rows(text: str) -> dict[str, str]:
    """Tool and hint of the "Tools at a glance" table of docs/TOOL-CONTRACT.md."""
    section = text.split("## Tools at a glance\n", 1)[1].split("\n## ", 1)[0]
    return dict(re.findall(r"^\| `(wled_[a-z_]+)` \| ([a-z-]+) \|", section, flags=re.M))


def tool_table_problems(contract: str, hints: dict[str, str]) -> list[str]:
    """The hint table of the tool contract equals the registered tools and hints."""
    if "## Tools at a glance\n" not in contract:
        return ["TOOL-CONTRACT lacks section '## Tools at a glance'"]
    if contract_tool_rows(contract) != hints:
        return ["TOOL-CONTRACT tool table differs from the registered tools and hints"]
    return []


def quickstart_problems(text: str) -> list[str]:
    """The quickstarts stay consistent with the example files they tell users to copy."""
    problems = []
    flat = " ".join(text.split())
    linked = {
        (QUICKSTARTS.parent / target.split("#", 1)[0]).resolve()
        for target in LINK.findall(text)
        if "://" not in target
    }
    for example in EXAMPLES:
        if (ROOT / example).resolve() not in linked:
            problems.append(f"QUICKSTARTS does not link {example}")
    stdio = hub_stdio()
    command = " ".join([stdio["command"], *stdio["args"]])
    if command not in [" ".join(line.split()) for line in code_lines(text)]:
        problems.append("QUICKSTARTS uvx command differs from examples/mcphub.example.json")
    url = hub_http()["url"]
    if f"`{url}`" not in text:
        problems.append("QUICKSTARTS HTTP URL differs from examples/mcphub.http.example.json")
    allowed = option(service()["command"], "--allowed-host")
    if allowed != urlsplit(url).netloc or f"`--allowed-host {allowed}`" not in flat:
        problems.append("QUICKSTARTS Host allowlist differs from the Compose example")
    secret = compose()["secrets"]["wled_mcp_http_token"]["file"].removeprefix("./")
    if f"> {secret})" not in text or f"`{secret}`" not in text:
        problems.append("QUICKSTARTS does not create and name the Compose credential file")
    problems.extend(container_command_problems(text, compose()["name"]))
    return problems


def readme_problems(text: str) -> list[str]:
    """What the README must state so that a new user can follow it (R62-2, R62-3)."""
    problems = []
    flat = " ".join(text.split())
    targets = link_targets(text)
    for target in ("docs/QUICKSTARTS.md", "docs/TOOL-CONTRACT.md", "docs/DEPLOYMENT.md"):
        if target not in targets:
            problems.append(f"README does not link {target}")
    if "wled-mcp config init" not in text:
        problems.append("README try-it path lacks 'wled-mcp config init'")
    if not re.search(r"not affiliated with[^.]*WLED project[^.]*MCPHub", flat):
        problems.append("README lacks the non-affiliation statement")
    if "Apache License 2.0" not in flat or "NOTICE" not in link_targets(text):
        problems.append("README does not state the Apache-2.0 license and NOTICE file")
    for section in (
        "## Try it",
        "## Safety model",
        "## Limitations",
        "## Support",
        "### How this project is developed",
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
        "offline controller",
    ):
        if term not in flat:
            problems.append(f"README safety/validation text lacks {term!r}")
    problems.extend(orientation_problems(text))
    return problems


def orientation_problems(text: str) -> list[str]:
    """What an outside reader learns before the repository is public (#90, DEC-016)."""
    problems = []
    flat = " ".join(text.split())
    targets = link_targets(text)
    for target in (
        "CONTRIBUTING.md",
        "SECURITY.md",
        "AGENTS.md",
        "docs/AGENT-WORKFLOW.md",
        "docs/DECISIONS.md",
        "docs/decisions/README.md",
    ):
        if target not in targets:
            problems.append(f"README does not link {target}")
    for term in (
        "early software",
        "distributed on PyPI",
        "installs from its Git tag",
        "not published to GHCR",
        "There is no support commitment",
        "best effort",
        "There is no security support",
        "Human contributions do not need this workflow",
    ):
        if term not in flat:
            problems.append(f"README orientation text lacks {term!r}")
    return problems


def contributing_problems(text: str) -> list[str]:
    """The minimal contribution guidance (#90, DEC-005, DEC-013, DEC-019)."""
    problems = []
    flat = " ".join(text.split())
    targets = {target.split("#", 1)[0] for target in LINK.findall(text)}
    for target in ("SECURITY.md", "docs/DEVELOPMENT.md", "docs/AGENT-WORKFLOW.md", "LICENSE"):
        if target not in targets:
            problems.append(f"CONTRIBUTING does not link {target}")
    for term in (
        "https://github.com/descipar/wled-mcp/issues",
        "no other channel",
        "Use synthetic examples",
        "no security support",
        "never contact LAN devices",
        "scripts/check_private_identifiers.py` must pass",
        "human contributions do not need to follow it",
        "no commitment to answer",
        "Section 5",
    ):
        if term not in flat:
            problems.append(f"CONTRIBUTING lacks {term!r}")
    return problems


def test_readme_states_the_safety_model_and_orientation():
    assert readme_problems(README.read_text("utf-8")) == []


def test_quickstarts_follow_the_example_files():
    assert quickstart_problems(QUICKSTARTS.read_text("utf-8")) == []


def test_tool_contract_table_follows_the_registry():
    assert tool_table_problems(TOOL_CONTRACT.read_text("utf-8"), tool_hints()) == []


def test_registry_hint_classes_use_the_readme_vocabulary():
    # The tool set itself is checked against tests/tool_contract.py centrally.
    hints = tool_hints()
    assert sorted(set(hints.values())) == ["destructive", "read-only", "write"]


@pytest.mark.parametrize(
    "path", [README, PROJECT, CONTRIBUTING, QUICKSTARTS], ids=lambda path: path.name
)
def test_local_links_and_anchors_resolve(path):
    assert link_problems(path, path.read_text("utf-8")) == []


def test_link_check_rejects_missing_files_and_anchors():
    text = README.read_text("utf-8")
    quickstarts = f"({REPOSITORY}blob/main/docs/QUICKSTARTS.md#inventory)"
    assert quickstarts in text
    broken = text.replace(quickstarts, f"({REPOSITORY}blob/main/docs/QUICKSTART.md)", 1)
    assert f"README.md: missing {REPOSITORY}blob/main/docs/QUICKSTART.md" in link_problems(
        README, broken
    )
    broken = text.replace("#inventory)", "#inventories)", 1)
    assert (
        f"README.md: missing anchor {REPOSITORY}blob/main/docs/QUICKSTARTS.md#inventories"
        in link_problems(README, broken)
    )
    # The same for the relative links of the other documents.
    project = PROJECT.read_text("utf-8")
    relative = re.search(r"\]\(((?!https?:|mailto:|#)[^)\s#]+\.md)\)", project)
    assert relative, "docs/PROJECT.md has no relative Markdown link to mutate"
    broken = project.replace(f"]({relative.group(1)})", "](MISSING.md)", 1)
    assert "PROJECT.md: missing MISSING.md" in link_problems(PROJECT, broken)


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        (f"{REPOSITORY}tree/main/docs/decisions", None),
        (f"{REPOSITORY}tree/main/no-such-dir", "missing"),
        (f"{REPOSITORY}blob/main/README.md#support", None),
        (f"{REPOSITORY}blob/main/README.md#no-such-heading", "missing anchor"),
        (f"{REPOSITORY}issues/22", None),
        ("https://example.invalid/docs/QUICKSTART.md", None),
    ],
    ids=["dir", "missing-dir", "anchor", "missing-anchor", "issue", "external"],
)
def test_link_check_maps_repository_urls_to_the_checkout(target, expected):
    problems = link_problems(README, f"Text [x]({target}).\n")
    assert problems == ([] if expected is None else [f"README.md: {expected} {target}"])


def test_readme_has_only_absolute_links():
    # The PyPI project page renders README.md without the repository (AC-22R-README-07).
    text = README.read_text("utf-8")
    assert relative_link_problems(text) == []
    assert len(LINK.findall(text)) > 30, "README links were not found"


@pytest.mark.parametrize(
    ("planted", "expected"),
    [
        (
            "See [the guide](docs/QUICKSTARTS.md).",
            "not an https or mailto link: docs/QUICKSTARTS.md",
        ),
        ("See [support](#support).", "not an https or mailto link: #support"),
        ("![diagram](docs/diagram.png)", "not an https or mailto link: docs/diagram.png"),
        ("[guide]: docs/QUICKSTARTS.md", "not an https or mailto link: docs/QUICKSTARTS.md"),
        ('<img src="docs/diagram.png" alt="x">', "not an https or mailto link: docs/diagram.png"),
        ('<a href="./SECURITY.md">x</a>', "not an https or mailto link: ./SECURITY.md"),
        (
            "[plain](http://example.invalid/)",
            "not an https or mailto link: http://example.invalid/",
        ),
    ],
    ids=["file", "fragment", "image", "reference", "html-img", "html-a", "plain-http"],
)
def test_relative_link_check_rejects_each_link_form(planted, expected):
    text = README.read_text("utf-8") + "\n" + planted + "\n"
    assert relative_link_problems(text) == [expected]


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        (
            "(../examples/mcphub.http.example.json)",
            "(DEPLOYMENT.md)",
            "QUICKSTARTS does not link examples/mcphub.http.example.json",
        ),
        (
            "--isolated --python 3.13",
            "--python 3.13 --isolated",
            "QUICKSTARTS uvx command differs from examples/mcphub.example.json",
        ),
        (
            "`http://wled-mcp:8000/mcp`",
            "`http://wled-mcp:8080/mcp`",
            "QUICKSTARTS HTTP URL differs from examples/mcphub.http.example.json",
        ),
        (
            "`--allowed-host wled-mcp:8000`",
            "`--allowed-host localhost:8000`",
            "QUICKSTARTS Host allowlist differs from the Compose example",
        ),
        (
            "> secrets/wled_mcp_http_token)",
            "> token.txt)",
            "QUICKSTARTS does not create and name the Compose credential file",
        ),
        (
            "docker compose -p wled-mcp-http -f compose.yaml ps",
            "docker compose ps",
            "unscoped compose command:    docker compose ps",
        ),
    ],
)
def test_quickstart_check_rejects_regressions(old, new, expected):
    text = QUICKSTARTS.read_text("utf-8")
    assert old in text
    assert expected in quickstart_problems(text.replace(old, new))


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("| `wled_delete_preset` | destructive |", "| `wled_delete_preset` | write |"),
        ("| `wled_get_preset` | read-only |", "| `wled_get_presets` | read-only |"),
    ],
)
def test_tool_table_check_rejects_drift(old, new):
    text = TOOL_CONTRACT.read_text("utf-8")
    assert old in text
    assert tool_table_problems(text.replace(old, new, 1), tool_hints()) == [
        "TOOL-CONTRACT tool table differs from the registered tools and hints"
    ]


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        (
            "docs/QUICKSTARTS.md",
            "docs/QUICKSTART.md",
            "README does not link docs/QUICKSTARTS.md",
        ),
        (
            "wled-mcp config init",
            "wled-mcp config show",
            "README try-it path lacks 'wled-mcp config init'",
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
            "## Support\n",
            "## Help\n",
            "README lacks section '## Support'",
        ),
        (
            "not published to GHCR",
            "published to GHCR",
            "README orientation text lacks 'not published to GHCR'",
        ),
        (
            "installs from its Git tag",
            "is not installable",
            "README orientation text lacks 'installs from its Git tag'",
        ),
        (
            "There is no support commitment.",
            "Support is provided.",
            "README orientation text lacks 'There is no support commitment'",
        ),
        (
            "Human contributions do not need this workflow.",
            "Human contributions must follow this workflow.",
            "README orientation text lacks 'Human contributions do not need this workflow'",
        ),
        (
            f"[CONTRIBUTING.md]({REPOSITORY}blob/main/CONTRIBUTING.md)",
            "CONTRIBUTING.md",
            "README does not link CONTRIBUTING.md",
        ),
        (
            f"[NOTICE]({REPOSITORY}blob/main/NOTICE)",
            "NOTICE",
            "README does not state the Apache-2.0 license and NOTICE file",
        ),
        (
            f"[docs/DECISIONS.md]({REPOSITORY}blob/main/docs/DECISIONS.md)",
            "docs/DECISIONS.md",
            "README does not link docs/DECISIONS.md",
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
    assert expected in readme_problems(text.replace(old, new))


COMPATIBILITY = ROOT / "docs/contract/compatibility.md"


def table_pairs(text: str) -> list[tuple[str, str]]:
    """(Area, Status) of every data row of the table rows in ``text``."""
    rows = [line for line in text.splitlines() if line.startswith("| ")]
    pairs = []
    for line in rows:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells[0] == "Area" or set(cells[0]) <= {"-", " "}:
            continue
        pairs.append((cells[0], cells[1]))
    return pairs


def readme_support_table(text: str) -> list[tuple[str, str]]:
    section = text.split("## Compatibility\n", 1)[1].split("\n## ", 1)[0]
    return table_pairs(section)


def compatibility_matrix(text: str) -> list[tuple[str, str]]:
    match = re.search(r"<!-- support-matrix:start -->(.*?)<!-- support-matrix:end -->", text, re.S)
    assert match, "compatibility.md lacks the support-matrix block"
    return table_pairs(match.group(1))


def support_table_problems(readme: str, compatibility: str) -> list[str]:
    """#21 A21-08: the README support table matches compatibility.md, row for row."""
    problems = []
    if "## Compatibility\n" not in readme:
        return ["README lacks section '## Compatibility'"]
    if "docs/contract/compatibility.md" not in link_targets(readme):
        problems.append("README does not link docs/contract/compatibility.md")
    shown, matrix = readme_support_table(readme), compatibility_matrix(compatibility)
    if not matrix:
        problems.append("compatibility.md support matrix is empty")
    if shown != matrix:
        problems.append(f"README support table {shown} differs from compatibility.md {matrix}")
    return problems


def test_readme_support_table_matches_the_compatibility_matrix():
    readme, compatibility = README.read_text("utf-8"), COMPATIBILITY.read_text("utf-8")
    assert support_table_problems(readme, compatibility) == []
    assert ("Windows", "experimental") in compatibility_matrix(compatibility)
    assert ("WLED 16.0.1", "tested") in compatibility_matrix(compatibility)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("| Windows | experimental |", "| Windows | supported |"),
        ("| macOS | experimental |\n", ""),
        (
            f"({REPOSITORY}blob/main/docs/contract/compatibility.md)",
            f"({REPOSITORY}blob/main/docs/contract/versioning.md)",
        ),
    ],
)
def test_support_table_check_rejects_drift(old, new):
    readme, compatibility = README.read_text("utf-8"), COMPATIBILITY.read_text("utf-8")
    assert old in readme
    assert support_table_problems(readme.replace(old, new, 1), compatibility) != []


def test_support_table_check_rejects_a_matrix_change_not_shown_in_the_readme():
    readme, compatibility = README.read_text("utf-8"), COMPATIBILITY.read_text("utf-8")
    changed = compatibility.replace("| WLED 16.0.1 | tested |", "| WLED 16.0.1 | expected |")
    assert changed != compatibility
    assert support_table_problems(readme, changed) != []


def test_contributing_states_the_minimal_rules():
    assert contributing_problems(CONTRIBUTING.read_text("utf-8")) == []


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        (
            "Use synthetic\n  examples",
            "Use real\n  examples",
            "CONTRIBUTING lacks 'Use synthetic examples'",
        ),
        (
            "[SECURITY.md](SECURITY.md)",
            "SECURITY.md",
            "CONTRIBUTING does not link SECURITY.md",
        ),
        (
            "never contact LAN devices",
            "may contact LAN devices",
            "CONTRIBUTING lacks 'never contact LAN devices'",
        ),
        (
            "human contributions do not need to follow it",
            "human contributions must follow it",
            "CONTRIBUTING lacks 'human contributions do not need to follow it'",
        ),
        (
            "There is no commitment to answer",
            "Answers are guaranteed",
            "CONTRIBUTING lacks 'no commitment to answer'",
        ),
    ],
)
def test_contributing_check_rejects_regressions(old, new, expected):
    text = CONTRIBUTING.read_text("utf-8")
    assert old in text
    assert expected in contributing_problems(text.replace(old, new))
