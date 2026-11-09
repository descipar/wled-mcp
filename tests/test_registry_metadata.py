"""Issue #24 (AC-24-01 to AC-24-08): registry metadata and listing drafts, offline.

Invariants of the root ``server.json`` (official MCP Registry), the README ownership
marker, the MCPM manifest draft and the hosted-directory copy. The published JSON
schemas are not vendored; one live validation run against them is recorded in
``docs/validation/issue-24.md`` and the checks here are local invariants with a negative
control per rule (a mutated copy must be reported). No network, no device, nothing is
published or submitted.
"""

from __future__ import annotations

import copy
import json
import re
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVER_JSON = ROOT / "server.json"
README = ROOT / "README.md"
MCPM_DRAFT = ROOT / "docs/listings/mcpm-wled-mcp.json"
HOSTED_DRAFT = ROOT / "docs/listings/mcphub-app-submission.md"
MARKETPLACE = ROOT / "docs/MARKETPLACE.md"
QUICKSTART_HTTP = (
    "https://github.com/descipar/wled-mcp/blob/main/docs/QUICKSTARTS.md"
    "#quickstart-streamable-http-service"
)
SCHEMA_URL = "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json"
NAME = re.compile(r"[a-zA-Z0-9.-]+/[a-zA-Z0-9._-]+")
MARKER = re.compile(r"<!--\s*mcp-name:\s*(\S+)\s*-->")
KEBAB = re.compile(r"(@[a-z0-9-]+/)?[a-z0-9]+(-[a-z0-9]+)*")
STATES = ("draft", "validated locally", "submitted", "accepted", "visible", "install-tested")
# Hosts a listing file may link to. Everything else (a LAN or private address, a
# placeholder, a hosted endpoint of ours) must not appear in a listing.
ALLOWED_HOSTS = {"github.com", "pypi.org", "static.modelcontextprotocol.io"}
PRIVATE_VALUE = re.compile(
    r"(^|[\s\"'=])(/(?:Users|home|root|app|data|opt|mnt|srv)/|[A-Za-z]:[\\/])"  # absolute paths
    r"|\b\d{1,3}(?:\.\d{1,3}){3}\b"  # IPv4 address
    r"|localhost|\.local\b|\.lan\b|\.internal\b|@\w+\.\w+"  # host names, e-mail addresses
    r"|(?:bearer|password|passwd|api[_-]?key|authorization)",  # credentials
    re.IGNORECASE,
)


def load(path: Path) -> Any:
    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        keys = [key for key, _ in pairs]
        assert len(keys) == len(set(keys)), f"duplicate key in {path.name}: {sorted(keys)}"
        return dict(pairs)

    return json.loads(path.read_text("utf-8"), object_pairs_hook=no_duplicates)


def project() -> dict[str, Any]:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        return tomllib.load(stream)["project"]


def strings(value: Any, path: str = "") -> list[tuple[str, str]]:
    """Every string value with its JSON path (keys are not values)."""
    if isinstance(value, str):
        return [(path, value)]
    if isinstance(value, dict):
        return [item for k, v in value.items() for item in strings(v, f"{path}.{k}")]
    if isinstance(value, list):
        return [item for i, v in enumerate(value) for item in strings(v, f"{path}[{i}]")]
    return []


# ------------------------------------------------------------------ AC-24-01 marker


def marker_problems(readme: str, name: str) -> list[str]:
    """The README holds exactly one marker, outside a code fence, and it names ``name``."""
    unfenced = re.sub(r"```.*?```", "", readme, flags=re.S)
    found = MARKER.findall(unfenced)
    problems = []
    if len(found) != 1 or readme.count("mcp-name:") != 1:
        problems.append(f"expected exactly one mcp-name marker, found {readme.count('mcp-name:')}")
    problems += [f"marker names {other!r}, not {name!r}" for other in found if other != name]
    return problems


def test_readme_marker_equals_the_registry_name():
    name = load(SERVER_JSON)["name"]
    text = README.read_text("utf-8")
    assert marker_problems(text, name) == []
    assert name == "io.github.descipar/wled-mcp"  # DEC-012 identity
    # Placed after the intro paragraph, before the status paragraph, without a link inside.
    assert text.index("mcp-name:") < text.index("**Status:**")
    assert "](" not in re.search(r"<!--.*?mcp-name.*?-->", text, flags=re.S).group(0)


def test_the_marker_reaches_the_package_description():
    # The registry reads the description of the PyPI release, which hatchling takes from
    # the README (METADATA is checked on the built wheel by scripts/check_distribution.py).
    assert project()["readme"] == "README.md"
    assert (ROOT / "pyproject.toml").read_text("utf-8").count("readme = ") == 1


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda t: MARKER.sub("", t), "found 0"),
        (lambda t: t.replace("io.github.descipar/", "io.github.other/"), "names"),
        (lambda t: t + "\n<!-- mcp-name: io.github.descipar/wled-mcp -->\n", "found 2"),
        (lambda t: t.replace("<!--", "```\n<!--").replace("-->", "-->\n```"), "found 1"),
    ],
    ids=["removed", "other-name", "duplicate", "inside-code-fence"],
)
def test_marker_check_reports_a_mutated_readme(mutate: Callable[[str], str], expected: str):
    mutated = mutate(README.read_text("utf-8"))
    assert any(expected in p for p in marker_problems(mutated, "io.github.descipar/wled-mcp"))


# ---------------------------------------------------------------- AC-24-02 / 04 / 05


def compose(arguments: list[dict[str, Any]]) -> list[str]:
    """The command line a client builds from ``server.json`` arguments (variables -> paths)."""
    line: list[str] = []
    for argument in arguments:
        value = argument.get("value")
        for key in argument.get("variables", {}):
            if value is not None:
                value = value.replace("{" + key + "}", f"/synthetic/{key}")
        if argument["type"] == "named":
            line.append(argument["name"])
        if value is not None:
            line.append(value)
    return line


def server_problems(document: dict[str, Any], meta: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if document.get("$schema") != SCHEMA_URL:
        problems.append("$schema is not the 2025-12-11 server schema")
    name = document.get("name", "")
    if not NAME.fullmatch(name) or not 3 <= len(name) <= 200:
        problems.append("name does not match the registry pattern")
    description = document.get("description", "")
    if not 1 <= len(description) <= 100:
        problems.append(f"description has {len(description)} characters, allowed 1 to 100")
    if "Unofficial" not in description or "not affiliated with the WLED project" not in description:
        problems.append("description lacks the unofficial / not affiliated statement")
    if "WLED" not in document.get("title", "") or "unofficial" not in document["title"].lower():
        problems.append("title lacks the unofficial marking")
    if "remotes" in document:
        problems.append("remotes present: HTTP is self-hosted and not a public endpoint")
    if document.get("repository", {}).get("url") != meta["urls"]["Repository"]:
        problems.append("repository.url differs from the pyproject Repository URL")
    if document.get("repository", {}).get("source") != "github":
        problems.append("repository.source is not github")
    packages = document.get("packages", [])
    if len(packages) != 1:
        return [*problems, f"expected exactly one package, found {len(packages)}"]
    package = packages[0]
    expected = {
        "registryType": "pypi",
        "identifier": meta["name"],
        "runtimeHint": "uvx",
        "transport": {"type": "stdio"},
    }
    for key, want in expected.items():
        if package.get(key) != want:
            problems.append(f"package.{key} is {package.get(key)!r}, not {want!r}")
    if package.get("environmentVariables"):
        problems.append("environmentVariables present: the inventory is passed by path")
    if compose(package.get("packageArguments", [])) != [
        "--transport",
        "stdio",
        "--config",
        "/synthetic/config_path",
        "--data-dir",
        "/synthetic/data_dir",
    ]:
        problems.append("packageArguments do not compose to the stdio launch")
    for argument in package.get("packageArguments", []):
        for key, variable in argument.get("variables", {}).items():
            if not (
                variable.get("isRequired") is True
                and variable.get("format") == "filepath"
                and variable.get("isSecret") is False
                and variable.get("description")
                and not {"default", "value", "placeholder"} & variable.keys()
            ):
                problems.append(f"variable {key} is not a required, non-secret filepath")
    for key, value in strings({k: v for k, v in document.items() if k != "$schema"}):
        if PRIVATE_VALUE.search(value):
            problems.append(f"{key} looks like a private value: {value!r}")
    problems += [
        f"{key} links to {urlsplit(value).hostname!r}"
        for key, value in strings(document)
        if value.startswith(("http://", "https://"))
        and (value.startswith("http://") or urlsplit(value).hostname not in ALLOWED_HOSTS)
    ]
    return problems


def test_server_json_is_valid_for_this_project():
    assert server_problems(load(SERVER_JSON), project()) == []


def test_server_json_launch_composes_to_the_documented_stdio_command():
    package = load(SERVER_JSON)["packages"][0]
    assert compose(package["runtimeArguments"]) == ["--isolated", "--python", "3.13"]
    # The README step 3 (and the hub example) pass exactly these runtime and package flags.
    readme = README.read_text("utf-8")
    step = next(line for line in readme.splitlines() if "--transport stdio --config" in line)
    runtime = " ".join(compose(package["runtimeArguments"]))
    assert step.strip().startswith(runtime), step
    for flag in ("--transport stdio", "--config", "--data-dir"):
        assert flag in step
    assert [a["name"] for a in package["packageArguments"] if a["type"] == "named"] == [
        "--transport",
        "--config",
        "--data-dir",
    ]


def test_https_urls_only_in_the_links_and_no_hosted_endpoint():
    document = load(SERVER_JSON)
    urls = {key for key, value in strings(document) if value.startswith("https://")}
    assert urls == {".$schema", ".repository.url", ".websiteUrl"}
    assert "remotes" not in document and "http" not in json.dumps(document["packages"])


def mutated(*edits: Callable[[dict[str, Any]], object]) -> dict[str, Any]:
    document = copy.deepcopy(load(SERVER_JSON))
    for edit in edits:
        edit(document)
    return document


@pytest.mark.parametrize(
    ("edit", "expected"),
    [
        (
            lambda d: d.update({"$schema": SCHEMA_URL.replace("2025-12-11", "2025-07-09")}),
            "$schema",
        ),
        (lambda d: d.update(name="wled-mcp"), "name does not match"),
        (lambda d: d.update(name="io.github.descipar/wled mcp"), "name does not match"),
        (lambda d: d.update(description="x" * 101), "101 characters"),
        (lambda d: d.update(description=""), "0 characters"),
        (lambda d: d.update(description="MCP server for WLED LED controllers"), "unofficial"),
        (lambda d: d.update(title="WLED MCP"), "title"),
        (
            lambda d: d.update(remotes=[{"type": "streamable-http", "url": "https://x.test/mcp"}]),
            "remotes",
        ),
        (
            lambda d: d["repository"].update(url="https://github.com/other/wled-mcp"),
            "repository.url",
        ),
        (lambda d: d["packages"].append(copy.deepcopy(d["packages"][0])), "exactly one package"),
        (lambda d: d["packages"][0].update(identifier="other-package"), "package.identifier"),
        (lambda d: d["packages"][0].update(registryType="npm"), "package.registryType"),
        (lambda d: d["packages"][0].update(runtimeHint="npx"), "package.runtimeHint"),
        (
            lambda d: d["packages"][0].update(transport={"type": "streamable-http"}),
            "package.transport",
        ),
        (
            lambda d: d["packages"][0].update(environmentVariables=[{"name": "X"}]),
            "environmentVariables",
        ),
        (lambda d: d["packages"][0]["packageArguments"].pop(0), "do not compose"),
        (
            lambda d: d["packages"][0]["packageArguments"][1].update(value="/srv/x/devices.toml"),
            "do not compose",
        ),
        (
            lambda d: d["packages"][0]["packageArguments"][1]["variables"]["config_path"].update(
                isSecret=True
            ),
            "non-secret",
        ),
        (
            lambda d: d["packages"][0]["packageArguments"][1]["variables"]["config_path"].update(
                isRequired=False
            ),
            "required",
        ),
        (
            lambda d: d["packages"][0]["packageArguments"][1]["variables"]["config_path"].update(
                format="string"
            ),
            "filepath",
        ),
        (
            lambda d: d["packages"][0]["packageArguments"][2]["variables"]["data_dir"].update(
                default="/data/wled"
            ),
            "variable data_dir",
        ),
        (lambda d: d.update(websiteUrl="http://192.0.2.10/readme"), "private value"),
        (lambda d: d.update(websiteUrl="https://example.com/wled-mcp"), "links to 'example.com'"),
        (
            lambda d: d["packages"][0]["runtimeArguments"].append(
                {"type": "positional", "value": "/srv/x/y"}
            ),
            "private value",
        ),
    ],
)
def test_server_json_check_reports_a_mutated_copy(
    edit: Callable[[dict[str, Any]], object], expected: str
):
    problems = server_problems(mutated(edit), project())
    assert any(expected in problem for problem in problems), problems


# ------------------------------------------------------------------ AC-24-06 MCPM draft


def mcpm_problems(document: dict[str, Any], meta: dict[str, Any]) -> list[str]:
    problems = [
        f"missing {key}"
        for key in ("name", "display_name", "description", "repository", "license", "installations")
        if key not in document
    ]
    if problems:
        return problems
    if not KEBAB.fullmatch(document["name"]):
        problems.append("name is not kebab-case")
    if document.get("is_official") is True:
        problems.append("is_official is true")
    if "tools" in document:
        problems.append("tools array present (not maintained by hand)")
    if document["repository"] != {"type": "git", "url": meta["urls"]["Repository"]}:
        problems.append("repository differs from the pyproject Repository URL")
    if document["license"] != meta["license"]:
        problems.append("license differs from pyproject")
    description = document["description"]
    if "Unofficial" not in description or "not affiliated with the WLED project" not in description:
        problems.append("description lacks the unofficial / not affiliated statement")
    if "unofficial" not in document["display_name"].lower():
        problems.append("display_name lacks the unofficial marking")
    uvx = document["installations"].get("uvx", {})
    if uvx.get("type") != "uvx" or uvx.get("command") != "uvx":
        problems.append("installations.uvx is not a uvx installation")
    args = uvx.get("args", [])
    if args[-2:] != ["--transport", "stdio"]:
        problems.append("uvx args do not end with --transport stdio")
    start = args.index("--from") + 1 if "--from" in args else 0
    if args[start : start + 2] != [meta["name"], meta["name"]]:
        problems.append("uvx args do not run the package through --from")
    if any(re.search(r"==|@|[\d]+\.[\d]+\.[\d]+", arg) for arg in args):
        problems.append("uvx args pin a version")
    if "--config" in args or "--data-dir" in args:
        problems.append("paths must come from the environment variables")
    arguments = document.get("arguments", {})
    env = uvx.get("env", {})
    if set(env) != {"WLED_MCP_CONFIG", "WLED_MCP_DATA_DIR"} or set(env) != set(arguments):
        problems.append("env variables and arguments differ")
    problems += [
        f"env {k} is not a ${{...}} reference" for k, v in env.items() if v != "${" + k + "}"
    ]
    problems += [
        f"argument {k} is not required"
        for k, v in arguments.items()
        if v.get("required") is not True
    ]
    if any(dist.get("type") == "http" for dist in document["installations"].values()):
        problems.append("an http installation would advertise a remote endpoint")
    version = meta["version"]
    problems += [f"{k} contains the current version" for k, v in strings(document) if version in v]
    problems += [
        f"{key} looks like a private value: {value!r}"
        for key, value in strings({k: v for k, v in document.items() if k != "arguments"})
        if PRIVATE_VALUE.search(value)
    ]
    for key, value in strings(arguments):
        if key.endswith(".example") and not value.startswith("/path/to/"):
            problems.append(f"{key} is not a synthetic example path")
    problems += [
        f"{key} links to {urlsplit(value).hostname!r}"
        for key, value in strings(document)
        if value.startswith(("http://", "https://"))
        and (value.startswith("http://") or urlsplit(value).hostname not in ALLOWED_HOSTS)
    ]
    return problems


def test_mcpm_draft_has_the_required_fields_and_the_uvx_launch():
    document = load(MCPM_DRAFT)
    assert mcpm_problems(document, project()) == []
    assert document["installations"]["uvx"]["args"][-2:] == ["--transport", "stdio"]


@pytest.mark.parametrize(
    ("edit", "expected"),
    [
        (lambda d: d.pop("license"), "missing license"),
        (lambda d: d.pop("installations"), "missing installations"),
        (lambda d: d.update(name="WLED_MCP"), "kebab-case"),
        (lambda d: d.update(is_official=True), "is_official"),
        (lambda d: d.update(tools=[{"name": "x"}]), "tools array"),
        (
            lambda d: d["repository"].update(url="https://github.com/other/wled-mcp"),
            "repository differs",
        ),
        (lambda d: d.update(license="MIT"), "license differs"),
        (lambda d: d.update(description="MCP server for WLED"), "unofficial"),
        (lambda d: d.update(display_name="WLED MCP"), "display_name"),
        (
            lambda d: d["installations"]["uvx"]["args"].__setitem__(4, "wled-mcp==1.2.3"),
            "pin a version",
        ),
        (
            lambda d: d["installations"]["uvx"]["args"].extend(["--config", "/x/y.toml"]),
            "environment variables",
        ),
        (
            lambda d: d["installations"]["uvx"]["env"].update(
                WLED_MCP_CONFIG="/srv/x/devices.toml"
            ),
            "reference",
        ),
        (lambda d: d["installations"]["uvx"]["env"].pop("WLED_MCP_DATA_DIR"), "differ"),
        (lambda d: d["arguments"]["WLED_MCP_CONFIG"].update(required=False), "not required"),
        (
            lambda d: d["arguments"]["WLED_MCP_CONFIG"].update(example="/srv/x/devices.toml"),
            "synthetic example",
        ),
        (
            lambda d: d["installations"].update(
                remote={"type": "http", "url": "https://x.test/mcp"}
            ),
            "http installation",
        ),
        (lambda d: d.update(homepage="https://example.com/x"), "links to 'example.com'"),
        (
            lambda d: d.update(description=d["description"] + " v" + project()["version"]),
            "current version",
        ),
    ],
)
def test_mcpm_check_reports_a_mutated_copy(edit: Callable[[dict[str, Any]], object], expected: str):
    document = copy.deepcopy(load(MCPM_DRAFT))
    edit(document)
    problems = mcpm_problems(document, project())
    assert any(expected in problem for problem in problems), problems


# ---------------------------------------------- AC-24-05 / 07 hosted copy and self-hosted HTTP


def hosted_problems(text: str) -> list[str]:
    lowered = text.lower()
    problems = []
    if "status: **draft**" not in lowered:
        problems.append("status is not draft")
    if "unofficial" not in lowered or "not affiliated with" not in lowered:
        problems.append("lacks the unofficial / not affiliated statement")
    if re.search(r"!\[|<img|\.(?:png|svg|jpe?g|webp)\b", lowered):
        problems.append("embeds or references an image")
    if re.search(r"\b(?:we|our|my|i)\b", re.sub(r"`[^`]*`", "", lowered)):
        problems.append("not impersonal")
    if "unverified" not in lowered and "were not observed" not in lowered:
        problems.append("does not say the form fields are unverified")
    if re.search(r"officially (?:endorsed|supported)|endorsed by the wled", lowered):
        problems.append("claims endorsement")
    if QUICKSTART_HTTP not in text:
        problems.append("lacks the self-hosted HTTP quickstart link")
    if project()["version"] in text:
        problems.append("contains the current version literal")
    if re.search(r"==\d+\.\d+\.\d+", text) or "<version>" not in text:
        problems.append("does not use a <version> placeholder")
    problems += [
        f"links to {urlsplit(url).hostname!r}"
        for url in re.findall(r"https?://[^\s)>\]`]+", text)
        if urlsplit(url).scheme == "http" or urlsplit(url).hostname not in ALLOWED_HOSTS
    ]
    return problems


def test_hosted_copy_is_a_neutral_unofficial_draft():
    assert hosted_problems(HOSTED_DRAFT.read_text("utf-8")) == []


@pytest.mark.parametrize(
    ("edit", "expected"),
    [
        (lambda t: t.replace("Status: **draft**", "Status: **submitted**"), "not draft"),
        (lambda t: t.replace("not affiliated with", "partnered with"), "not affiliated"),
        (lambda t: t + "\n![logo](wled.png)\n", "image"),
        (lambda t: t + "\nWe maintain this server.\n", "impersonal"),
        (
            lambda t: t.replace("unverified", "known").replace("were not observed", "are listed"),
            "unverified",
        ),
        (lambda t: t + "\nOfficially endorsed by the community.\n", "endorsement"),
        (
            lambda t: t.replace(QUICKSTART_HTTP, "https://github.com/descipar/wled-mcp"),
            "quickstart",
        ),
        (lambda t: t + "\nEndpoint: http://192.0.2.10/mcp\n", "links to"),
        (lambda t: t + f"\nversion {project()['version']}\n", "version literal"),
    ],
)
def test_hosted_check_reports_a_mutated_copy(edit: Callable[[str], str], expected: str):
    problems = hosted_problems(edit(HOSTED_DRAFT.read_text("utf-8")))
    assert any(expected in problem for problem in problems), problems


def test_marketplace_states_that_http_is_self_hosted_and_links_the_quickstart():
    text = MARKETPLACE.read_text("utf-8")
    section = text.split("## HTTP is self-hosted", 1)[1].split("\n## ", 1)[0]
    assert (
        "no `remotes`" in section and "QUICKSTARTS.md#quickstart-streamable-http-service" in section
    )
    assert "self-hosted" in HOSTED_DRAFT.read_text("utf-8")
    assert (
        "self-hosted" in MCPM_DRAFT.read_text("utf-8") or "HTTP" in load(MCPM_DRAFT)["description"]
    )


# ------------------------------------------------------------------ AC-24-08 status table


def status_rows(text: str) -> list[tuple[str, str, str]]:
    section = text.split("## Status per route", 1)[1].split("\n## ", 1)[0]
    rows = []
    for line in section.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(cells) >= 2 and not set(cells[0]) <= {"-", " "}:
            rows.append((cells[0], cells[1], line))
    return rows[1:]  # header


def test_status_table_has_one_row_per_route_with_a_vocabulary_state():
    rows = status_rows(MARKETPLACE.read_text("utf-8"))
    routes = [route for route, _, _ in rows]
    assert [r.split(" (")[0] for r in routes] == [
        "Official MCP Registry",
        "MCPM / MCPHub local catalog",
        "Hosted mcphub.app directory",
        "MCPHub fresh-install test",
    ]
    for route, state, line in rows:
        assert state in (*STATES, "not run", "not planned"), (route, state)
        if state == "not planned":  # a dropped route cites the owner decision (ISSUE-24-DEC-003)
            assert "ISSUE-24-DEC-003" in line, route
    # Nothing was submitted or published: no route may claim a later state than local
    # validation until real evidence exists (this test is updated with that evidence).
    assert {state for _, state, _ in rows} <= {
        "draft",
        "validated locally",
        "not planned",
        "not run",
    }
    states = dict((route.split(" (")[0], state) for route, state, _ in rows)
    assert states["Official MCP Registry"] == "validated locally"
    assert states["MCPHub fresh-install test"] == "not run"


def test_status_table_cites_the_decision_and_the_decision_file_records_it():
    decision = (ROOT / "docs/decisions/issue-24.md").read_text("utf-8")
    assert "## ISSUE-24-DEC-003" in decision
    assert "ISSUE-24-DEC-003" in (ROOT / "docs/DECISIONS.md").read_text("utf-8")
