"""Issue #151 (DIST-04, D151-01 to D151-14): the Claude Desktop MCPB bundle, offline.

``deploy/build_mcpb.py`` renders the manifest from ``deploy/mcpb/manifest.template.json``,
validates it against the vendored upstream schema and packs a deterministic archive. These
tests read the packed bundle and the documents only: no Claude Desktop, no network, no
device, nothing is published. The release workflow side is in ``test_publish_workflow.py``.
Contract: ``docs/contract/mcpb-bundle.md``.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import jsonschema
import pytest

from deploy import build_mcpb
from deploy.build_mcpb import BundleError
from tests.test_registry_metadata import (
    ALLOWED_HOSTS,
    PRIVATE_VALUE,
    compose,
    load,
    project,
    strings,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / build_mcpb.SCHEMA
TEMPLATE = ROOT / build_mcpb.TEMPLATE
SERVER_JSON = ROOT / "server.json"
README = ROOT / "README.md"
MARKETPLACE = ROOT / "docs/MARKETPLACE.md"
PUBLISHING = ROOT / "docs/PUBLISHING.md"
CONTRACT = ROOT / "docs/contract/mcpb-bundle.md"
# Provenance of the vendored schema (tag v2.1.2 of modelcontextprotocol/mcpb, docs/SOURCES.md).
SCHEMA_SHA256 = "3a0ac9d845711a1b9b17dfa5a52f8b60628239d6a86a9db417206a9efc78592d"
SCHEMA_BYTES = 7902
MEMBERS = ["LICENSE", "NOTICE", "manifest.json", "server/main.py"]


def version() -> str:
    return str(project()["version"])


def manifest() -> dict[str, Any]:
    return build_mcpb.render_manifest(version())


def built(tmp_path: Path, name: str = "out") -> Path:
    target, _ = build_mcpb.build(tmp_path / name)
    return target


def members(bundle: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(bundle) as archive:
        return {info.filename: archive.read(info) for info in archive.infolist()}


def mutated(*edits: Callable[[dict[str, Any]], object]) -> dict[str, Any]:
    document = copy.deepcopy(manifest())
    for edit in edits:
        edit(document)
    return document


# ------------------------------------------------------- D151-01 schema validation


def test_the_vendored_schema_is_a_valid_draft7_schema():
    schema = json.loads(SCHEMA.read_text("utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"


def test_the_rendered_manifest_validates_against_the_vendored_schema():
    schema = json.loads(SCHEMA.read_text("utf-8"))
    errors = list(jsonschema.Draft7Validator(schema).iter_errors(manifest()))
    assert errors == []
    assert build_mcpb.validate_manifest(manifest()) == []


@pytest.mark.parametrize(
    ("edit", "expected"),
    [
        (lambda d: d["server"].pop("entry_point"), "'entry_point' is a required property"),
        (lambda d: d["server"].pop("mcp_config"), "'mcp_config' is a required property"),
        (lambda d: d.update(extra="x"), "Additional properties"),
        (lambda d: d["server"].update(type="uv"), "is not one of"),
        (lambda d: d["server"]["mcp_config"].update(cwd="/"), "Additional properties"),
        (lambda d: d["user_config"]["data_dir"].pop("title"), "'title' is a required property"),
        (lambda d: d["user_config"]["data_dir"].update(type="path"), "is not one of"),
        (lambda d: d["user_config"]["data_dir"].update(secret=True), "Additional properties"),
        (lambda d: d.update(manifest_version="0.4"), "manifest_version"),
        (lambda d: d.pop("manifest_version"), "manifest_version is not"),
        (lambda d: d.pop("author"), "'author' is a required property"),
        (lambda d: d.update(version="1.2"), "not semver"),
        (lambda d: d.update(version="0.4.0rc1"), "not semver"),
        (lambda d: d["repository"].update(url="http://github.com/descipar/wled-mcp"), "https URL"),
        (lambda d: d.update(homepage="not a url"), "homepage is not a plain https URL"),
        (lambda d: d.update(support="https://user:pw" + "@github.com/x"), "support is not a plain"),
        (lambda d: d.update(documentation=7), "documentation"),
        (lambda d: d["compatibility"].update(platforms=["plan9"]), "is not one of"),
        (
            lambda d: d["server"]["mcp_config"]["args"].append("${user_config.unknown}"),
            "user_config.unknown is referenced but not defined",
        ),
        (
            lambda d: d["user_config"].update(
                extra={"type": "string", "title": "T", "description": "D"}
            ),
            "user_config.extra is defined but never used",
        ),
        (
            lambda d: d.update(description="REPLACE_WITH_VERSION"),
            "placeholder is left",
        ),
        (
            lambda d: d["author"].update(name="REPLACE_WITH_AUTHOR"),
            "placeholder is left",
        ),
    ],
)
def test_manifest_check_reports_a_mutated_copy(edit, expected):
    problems = build_mcpb.validate_manifest(mutated(edit))
    assert any(expected in problem for problem in problems), problems


# --------------------------------------------------------- D151-02 schema provenance


def test_the_vendored_schema_is_the_recorded_upstream_file():
    data = SCHEMA.read_bytes()
    assert hashlib.sha256(data).hexdigest() == SCHEMA_SHA256
    assert len(data) == SCHEMA_BYTES and b"\r" not in data
    sources = (ROOT / "docs/SOURCES.md").read_text("utf-8")
    assert SCHEMA_SHA256 in sources and "Copyright 2025 Anthropic, PBC." in sources


# ------------------------------------------------------- D151-03 packed contents


def test_the_packed_bundle_holds_exactly_the_four_members(tmp_path):
    bundle = built(tmp_path)
    assert bundle.name == f"wled-mcp-{version()}.mcpb"
    with zipfile.ZipFile(bundle) as archive:
        assert archive.testzip() is None
        assert [info.filename for info in archive.infolist()] == MEMBERS
        assert not any(info.is_dir() or info.filename.endswith("/") for info in archive.infolist())
    found = members(bundle)
    assert found["LICENSE"] == (ROOT / "LICENSE").read_bytes()
    assert found["NOTICE"] == (ROOT / "NOTICE").read_bytes()
    assert found["server/main.py"] == (ROOT / build_mcpb.STUB).read_bytes()
    assert json.loads(found["manifest.json"])["name"] == "wled-mcp"
    assert bundle.stat().st_size < 1024 * 1024


def test_the_bundle_carries_no_inventory_secret_or_repository_data(tmp_path):
    names = list(members(built(tmp_path)))
    for name in names:
        parts = name.split("/")
        assert not name.startswith(("/", "\\")) and ".." not in parts and "\\" not in name
        assert not re.search(r"\.toml$|\.env|\.git|\.pem$|\.key$|devices", name, re.IGNORECASE)
    # Nothing but the four planned members, so nothing from the working tree can slip in.
    assert names == MEMBERS


@pytest.mark.parametrize(
    "name",
    ["../escape.txt", "/abs.txt", "a/../../b", "dir/", "back\\slash", "C:/drive", ""],
)
def test_pack_refuses_an_unsafe_member_name(name):
    entries = {
        "manifest.json": build_mcpb.manifest_bytes(manifest()),
        "server/main.py": b"",
        name: b"x",
    }
    with pytest.raises(BundleError, match="unsafe archive member name"):
        build_mcpb.pack(entries)


def test_pack_refuses_a_manifest_whose_entry_point_is_not_in_the_archive():
    entries = {"manifest.json": build_mcpb.manifest_bytes(manifest())}
    with pytest.raises(BundleError, match="entry_point"):
        build_mcpb.pack(entries)
    with pytest.raises(BundleError, match="manifest.json is missing"):
        build_mcpb.pack({"server/main.py": b""})


def test_the_entry_point_stub_never_runs_a_server():
    result = subprocess.run(
        [sys.executable, "-I", str(ROOT / build_mcpb.STUB)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 2 and result.stdout == ""
    assert "uvx" in result.stderr and "placeholder" in result.stderr


# ------------------------------------------------------------- D151-04 version


def test_manifest_and_pin_carry_project_version_in_the_archive(tmp_path):
    packed = json.loads(members(built(tmp_path))["manifest.json"])
    assert packed == manifest()
    assert packed["version"] == version()  # a release version is its own semver form
    args = packed["server"]["mcp_config"]["args"]
    assert args[args.index("--from") + 1] == f"wled-mcp=={version()}"
    assert args[args.index("--from") + 2] == "wled-mcp"
    for text in strings(packed):
        assert "REPLACE_WITH_" not in text


def test_a_different_requested_version_fails_without_writing(tmp_path, capsys):
    output = tmp_path / "out"
    with pytest.raises(BundleError) as failure:
        build_mcpb.build(output, expected_version="9.9.9")
    assert "9.9.9" in str(failure.value) and version() in str(failure.value)
    assert not output.exists()
    assert build_mcpb.main(["--version", "9.9.9", "--output", str(output)]) == 1
    captured = capsys.readouterr()
    assert "9.9.9" in captured.err and version() in captured.err and captured.out == ""
    assert not output.exists()


def test_a_release_candidate_maps_to_semver_only_in_the_version_field():
    candidate = build_mcpb.render_manifest("0.4.0rc1", author="Synthetic Author")
    assert candidate["version"] == "0.4.0-rc.1"
    args = candidate["server"]["mcp_config"]["args"]
    assert "wled-mcp==0.4.0rc1" in args and not any("-rc." in arg for arg in args)
    assert build_mcpb.validate_manifest(candidate) == []
    assert "wled-mcp==0.4.0rc1" in candidate["long_description"]


@pytest.mark.parametrize(
    "bad", ["1.2", "1.2.3+g123456789abc", "1.2.3.dev1", "v1.2.3", "1.2.3rc", "1.2.3-rc.1", ""]
)
def test_only_a_release_version_can_be_rendered(bad):
    with pytest.raises(BundleError, match="not a release version"):
        build_mcpb.render_manifest(bad, author="Synthetic Author")


def synthetic_root(tmp_path: Path, new_version: str) -> Path:
    """A copy of the inputs with another ``project.version`` (the real checkout is untouched)."""
    root = tmp_path / "root"
    shutil.copytree(ROOT / "deploy/mcpb", root / "deploy/mcpb")
    for name in ("LICENSE", "NOTICE"):
        shutil.copyfile(ROOT / name, root / name)
    text = (ROOT / "pyproject.toml").read_text("utf-8")
    edited = text.replace(f'version = "{version()}"', f'version = "{new_version}"', 1)
    assert edited != text
    (root / "pyproject.toml").write_text(edited, encoding="utf-8", newline="\n")
    return root


def test_a_release_candidate_build_names_the_file_with_the_pep440_version(tmp_path):
    root = synthetic_root(tmp_path, "0.4.0rc1")
    target, _ = build_mcpb.build(tmp_path / "out", expected_version="0.4.0rc1", root=root)
    assert target.name == "wled-mcp-0.4.0rc1.mcpb"
    packed = json.loads(members(target)["manifest.json"])
    assert packed["version"] == "0.4.0-rc.1"
    assert "wled-mcp==0.4.0rc1" in packed["server"]["mcp_config"]["args"]


def test_the_author_comes_from_pyproject_and_is_not_tracked_elsewhere():
    name = project()["authors"][0]["name"]
    assert manifest()["author"] == {"name": name}
    assert name not in TEMPLATE.read_text("utf-8")
    assert name not in SCHEMA.read_text("utf-8")


# --------------------------------------------------------------- D151-05 launch


def test_the_launch_is_the_documented_pinned_uvx_stdio_command():
    config = manifest()["server"]["mcp_config"]
    package = load(SERVER_JSON)["packages"][0]
    mapped = [
        arg.replace("/synthetic/config_path", "${user_config.config_path}").replace(
            "/synthetic/data_dir", "${user_config.data_dir}"
        )
        for arg in compose(package["packageArguments"])
    ]
    assert config["command"] == "uvx"
    assert config["args"] == [
        *compose(package["runtimeArguments"]),
        "--from",
        f"wled-mcp=={version()}",
        "wled-mcp",
        *mapped,
    ]
    assert mapped[:2] == ["--transport", "stdio"]


def test_the_launch_has_no_http_option_no_token_and_no_environment():
    config = manifest()["server"]["mcp_config"]
    args = config["args"]
    assert args.count("--transport") == 1 and args[args.index("--transport") + 1] == "stdio"
    for arg in args:
        assert not re.search(r"--(host|port|allowed|token|bearer|auth|http|tls|cert)", arg), arg
    assert set(config) == {"command", "args"}  # no env, no platform overrides
    assert re.fullmatch(r"wled-mcp==\d+\.\d+\.\d+(rc\d+)?", args[args.index("--from") + 1])
    assert "--constraints" not in args and "--index-url" not in args


# ------------------------------------------------------------ D151-06 user_config


def test_user_config_asks_for_exactly_the_two_required_non_secret_paths():
    document = manifest()
    options = document["user_config"]
    assert set(options) == {"config_path", "data_dir"}
    assert options["config_path"]["type"] == "file"
    assert options["data_dir"]["type"] == "directory"
    for name, option in options.items():
        assert option["required"] is True, name
        assert not {"default", "sensitive", "multiple", "min", "max"} & option.keys(), name
        assert option["title"] and option["description"]
    args = document["server"]["mcp_config"]["args"]
    referenced = {m for arg in args for m in re.findall(r"\$\{user_config\.(\w+)\}", arg)}
    assert referenced == set(options)
    for arg in args:  # each reference is a whole argument, so paths with spaces stay one value
        if "user_config" in arg:
            assert re.fullmatch(r"\$\{user_config\.\w+\}", arg), arg


def test_the_manifest_holds_no_private_value_and_links_only_to_known_hosts():
    document = manifest()
    for path, value in strings({k: v for k, v in document.items() if k != "server"}):
        assert not PRIVATE_VALUE.search(value), (path, value)
    for path, value in strings(document):
        for url in re.findall(r"https?://[^\s)>\]`\"']+", value):
            parts = urlsplit(url)
            assert parts.scheme == "https" and parts.hostname in ALLOWED_HOSTS, (path, url)


# ------------------------------------------------------------- D151-07 identity


def test_the_identity_is_unofficial_and_follows_pyproject_and_the_registry_entry():
    document, meta, registry = manifest(), project(), load(SERVER_JSON)
    assert document["description"] == registry["description"]
    assert "unofficial" in document["display_name"].lower()
    for field in (document["description"], document["long_description"]):
        assert "nofficial" in field and "not affiliated with the WLED project" in field
    assert not {"icon", "icons", "screenshots"} & document.keys()  # no WLED logo (DEC-012)
    assert document["license"] == meta["license"]
    assert document["repository"] == {"type": "git", "url": meta["urls"]["Repository"]}
    assert document["homepage"] == document["documentation"] == meta["urls"]["Documentation"]
    assert document["support"] == meta["urls"]["Issues"]
    assert document["keywords"] == meta["keywords"]
    assert document["name"] == meta["name"]
    assert "not part of the bundle" in document["long_description"]


# ------------------------------------------------------------ D151-08 determinism


def test_two_builds_are_byte_identical_with_fixed_stored_entries(tmp_path):
    first, second = built(tmp_path, "one"), built(tmp_path, "two")
    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as archive:
        infos = archive.infolist()
    names = [info.filename for info in infos]
    assert names == sorted(names)
    for info in infos:
        assert info.date_time == (1980, 1, 1, 0, 0, 0)
        assert info.compress_type == zipfile.ZIP_STORED
        assert info.create_system == 3 and info.external_attr == 0o100644 << 16


def test_pack_ignores_the_order_in_which_entries_were_given():
    entries = {
        "manifest.json": build_mcpb.manifest_bytes(manifest()),
        "server/main.py": b"x",
        "NOTICE": b"n",
        "LICENSE": b"l",
    }
    reversed_entries = dict(reversed(list(entries.items())))
    assert build_mcpb.pack(entries) == build_mcpb.pack(reversed_entries)


def test_the_printed_checksum_line_is_the_sha256sum_format_of_the_file(tmp_path, capsys):
    assert build_mcpb.main(["--output", str(tmp_path / "out")]) == 0
    line = capsys.readouterr().out
    bundle = tmp_path / "out" / f"wled-mcp-{version()}.mcpb"
    assert line == f"{hashlib.sha256(bundle.read_bytes()).hexdigest()}  {bundle.name}\n"
    if shutil.which("sha256sum") and shutil.which("bash"):
        (tmp_path / "out" / "SHA256SUMS").write_text(line, encoding="utf-8", newline="\n")
        # `sha256sum` tools on Windows use a binary marker in their own output only; checking
        # a two-space line works with every GNU build, so it stays a real check where run.
        check = subprocess.run(
            ["sha256sum", "--check", "SHA256SUMS"],
            cwd=tmp_path / "out",
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert check.returncode == 0, check.stdout + check.stderr


# ------------------------------------------------------------ D151-11 docs wording

README_PHRASES = ("built along with each release", "not tested by the project", "without warranty")
DOC_PHRASES = ("built along with each release", "not tested by the project", "no warranty")


def paragraph_with(text: str, needle: str) -> str:
    (found,) = [block for block in re.split(r"\n\s*\n", text) if needle in block]
    return found


def anchor_of(heading: str) -> str:
    slug = re.sub(r"[^a-z0-9 -]", "", heading.lower())
    return slug.strip().replace(" ", "-")


def wording_problems(text: str, phrases: tuple[str, ...]) -> list[str]:
    flat = re.sub(r"\s+", " ", text.lower())
    return [f"lacks {phrase!r}" for phrase in phrases if phrase not in flat]


def readme_problems(readme: str, marketplace: str) -> list[str]:
    block = paragraph_with(readme, "MCPB")
    problems = wording_problems(block, README_PHRASES)
    link = re.search(
        r"\]\((https://github\.com/descipar/wled-mcp/blob/main/docs/MARKETPLACE\.md#([\w-]+))\)",
        block,
    )
    if link is None:
        problems.append("no link to the MARKETPLACE section")
    else:
        headings = [anchor_of(m) for m in re.findall(r"^#+ (.+)$", marketplace, flags=re.M)]
        if link.group(2) not in headings:
            problems.append("the link anchor does not resolve")
    return problems


def test_readme_states_the_bundle_limits_and_links_the_section():
    text, marketplace = README.read_text("utf-8"), MARKETPLACE.read_text("utf-8")
    assert readme_problems(text, marketplace) == []
    assert "uv" in paragraph_with(text, "MCPB")  # the prerequisite is named
    assert text.count("\n") <= 200


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ("built along with each release", "built with each release", "built along"),
        ("not tested by the project", "tested by the project", "not tested"),
        ("without warranty", "with a warranty", "without warranty"),
        ("MARKETPLACE.md#claude-desktop-mcpb-bundle", "MARKETPLACE.md", "no link"),
        ("MARKETPLACE.md#claude-desktop-mcpb-bundle", "MARKETPLACE.md#mcpb", "does not resolve"),
    ],
)
def test_readme_check_rejects_regressions(old, new, expected):
    text = README.read_text("utf-8")
    assert old in text
    problems = readme_problems(text.replace(old, new, 1), MARKETPLACE.read_text("utf-8"))
    assert any(expected in problem for problem in problems), problems


def section(text: str, heading: str) -> str:
    return text.split(f"\n{heading}\n", 1)[1].split("\n## ", 1)[0]


def test_marketplace_and_publishing_state_the_bundle_limits():
    market = section(MARKETPLACE.read_text("utf-8"), "## Claude Desktop MCPB bundle")
    publishing = section(PUBLISHING.read_text("utf-8"), "## MCPB bundle (#151)")
    for text in (market, publishing):
        assert wording_problems(text, DOC_PHRASES) == []
        flat = re.sub(r"\s+", " ", text)
        assert "unsigned" in flat.lower()
    flat_market = re.sub(r"\s+", " ", market)
    assert "No Claude Desktop install run was made" in flat_market
    assert "whether Claude Desktop accepts" in flat_market
    # The job has not run: no document may claim it did (first run: the next release).
    for text in (market, publishing):
        assert re.search(r"not (yet )?run|next release", text), text[:80]


@pytest.mark.parametrize("phrase", DOC_PHRASES)
def test_doc_wording_check_reports_a_removed_phrase(phrase):
    text = section(MARKETPLACE.read_text("utf-8"), "## Claude Desktop MCPB bundle")
    flat = re.sub(r"\s+", " ", text)
    assert wording_problems(flat, DOC_PHRASES) == []
    removed = re.sub(re.escape(phrase), "x", flat, flags=re.IGNORECASE)
    assert removed != flat
    assert wording_problems(removed, DOC_PHRASES) == [f"lacks {phrase!r}"]


def test_the_contract_lists_every_scenario_and_the_requirement():
    text = CONTRACT.read_text("utf-8")
    assert "DIST-04" in text
    for number in range(1, 15):
        assert f"D151-{number:02d}" in text, number
    assert "DIST-04" in (ROOT / "docs/STAGE-5.md").read_text("utf-8")
    assert "contract/mcpb-bundle.md" in (ROOT / "docs/TOOL-CONTRACT.md").read_text("utf-8")
    assert "validation/issue-151.md" in (ROOT / "docs/VALIDATION.md").read_text("utf-8")
    assert "not yet run" in (ROOT / "docs/validation/issue-151.md").read_text("utf-8").lower()


# --------------------------------------------------------- D151-12 template placeholder


def test_the_template_names_the_version_only_by_its_placeholder():
    text = TEMPLATE.read_text("utf-8")
    assert "REPLACE_WITH_VERSION" in text and "REPLACE_WITH_AUTHOR" in text
    assert version() not in text
    # No full X.Y.Z literal: only the placeholder, the manifest version 0.3 and Python 3.13.
    assert not re.search(r"\d+\.\d+\.\d+", text)


# ------------------------------------------------------------- D151-14 command line


def test_the_command_line_writes_one_bundle_and_prints_one_checksum_line(tmp_path):
    output = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, "-I", str(ROOT / "deploy/build_mcpb.py"), "--output", str(output)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert re.fullmatch(rf"[0-9a-f]{{64}}  wled-mcp-{re.escape(version())}\.mcpb\n", result.stdout)
    assert result.stderr == ""
    assert [path.name for path in output.iterdir()] == [f"wled-mcp-{version()}.mcpb"]


def test_an_existing_bundle_is_never_replaced(tmp_path, capsys):
    output = tmp_path / "out"
    output.mkdir()
    existing = output / f"wled-mcp-{version()}.mcpb"
    existing.write_bytes(b"already attached elsewhere")
    assert build_mcpb.main(["--output", str(output)]) == 1
    captured = capsys.readouterr()
    assert "already exists" in captured.err and captured.out == ""
    assert existing.read_bytes() == b"already attached elsewhere"
    assert [path.name for path in output.iterdir()] == [existing.name]


def test_a_validation_failure_writes_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(build_mcpb, "validate_manifest", lambda *args, **kwargs: ["synthetic"])
    output = tmp_path / "out"
    assert build_mcpb.main(["--output", str(output)]) == 1
    captured = capsys.readouterr()
    assert "manifest is invalid: synthetic" in captured.err and captured.out == ""
    assert not output.exists()


def test_an_unusable_output_location_fails_cleanly(tmp_path, capsys):
    blocker = tmp_path / "file"
    blocker.write_text("not a directory", encoding="utf-8")
    assert build_mcpb.main(["--output", str(blocker / "out")]) == 1
    captured = capsys.readouterr()
    assert captured.err.startswith("build_mcpb:") and captured.out == ""
    assert blocker.read_text("utf-8") == "not a directory"


def test_the_output_option_is_required(capsys):
    with pytest.raises(SystemExit) as exited:
        build_mcpb.main([])
    assert exited.value.code == 2
    assert "--output" in capsys.readouterr().err
