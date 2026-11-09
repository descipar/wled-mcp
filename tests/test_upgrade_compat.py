"""Issue #21 A21-05 and A21-06: compatibility with the retained data of earlier releases.

Each directory under ``tests/fixtures/compat/`` holds data generated once from an
earlier release source (see its README.md): the served ``tools/list``, an inventory
configuration, a preset snapshot and a ``wled_get_state`` envelope. The tests read
that historical data with the current server:

- A21-05: the current, unfiltered contract (all classes, profile ``full``) passes
  ``contract_problems`` from ``tests/tool_contract.py`` and keeps every retained tool
  and field compatible. A breaking difference fails unless a migration-note entry in
  docs/contract/versioning.md names its tool and JSON pointer. New tools and new
  optional output fields are additive. This module holds no tool list or count: tool
  names come from the retained data, the served registry and the shared helper.
- A21-06: the retained configuration and snapshot load; a newer (synthetic) schema or
  format version is rejected naming the version, and no file is modified.

Mocks and loopback only; no device is contacted.
"""

from __future__ import annotations

import copy
import json
import re
import shutil
import tomllib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import anyio
import httpx2 as httpx
import pytest
from mcp.client import Client

from tests.backup_support import FIRMWARE, make_store
from tests.test_inventory_client import config as synthetic_config
from tests.tool_contract import contract_problems
from wled_mcp.backups import FORMAT_VERSION, SnapshotStore
from wled_mcp.client import ClientFailure
from wled_mcp.config import SCHEMA_VERSION, ConfigurationError, load_config
from wled_mcp.models import Outcome
from wled_mcp.operations import build_operations
from wled_mcp.resources import Resources
from wled_mcp.server import create_server

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "compat"
VERSIONING = ROOT / "docs" / "contract" / "versioning.md"
RETAINED = sorted(path for path in FIXTURES.iterdir() if path.is_dir())
RELEASE_DIR = re.compile(r"\d+\.\d+\.\d+")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def release_ids() -> list[str]:
    return [path.name for path in RETAINED]


def test_retained_fixture_directories_are_release_versions():
    assert RETAINED, "at least the first release's data is retained"
    for path in RETAINED:
        assert RELEASE_DIR.fullmatch(path.name), path.name
        for name in ("README.md", "tools.json", "config.toml", "get_state.json"):
            assert (path / name).is_file(), f"{path.name}/{name}"
        assert list((path / "snapshots").glob("*/*.json")), f"{path.name} has no snapshot"


# ===================================================================== A21-05 contract


def served_tools(tmp_path: Path) -> list[dict[str, Any]]:
    """The current unfiltered ``tools/list`` (every class; profile ``full``)."""

    async def collect() -> list[dict[str, Any]]:
        async with Resources(synthetic_config(tmp_path)) as resources:
            async with Client(create_server(build_operations(resources))) as client:
                tools = (await client.list_tools()).tools
        return [tool.model_dump(mode="json", by_alias=True, exclude_none=True) for tool in tools]

    return anyio.run(collect)


@dataclass(frozen=True)
class Note:
    release: str
    tool: str
    pointer: str


def migration_notes(text: str) -> list[Note]:
    """Machine-readable migration-note rows of docs/contract/versioning.md."""
    match = re.search(
        r"<!-- migration-notes:start -->(.*?)<!-- migration-notes:end -->", text, flags=re.S
    )
    assert match, "versioning.md lacks the migration-notes block"
    notes = []
    for line in match.group(1).strip().splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells[0] in ("Release", "") or set(cells[0]) <= {"-", " "}:
            continue  # header and separator rows
        assert len(cells) == 5, f"migration note needs five columns: {line}"
        release, tool, pointer = (cell.strip("`") for cell in cells[:3])
        assert RELEASE_DIR.fullmatch(release), f"migration note release: {line}"
        assert pointer.startswith("/"), f"migration note pointer: {line}"
        notes.append(Note(release, tool, pointer))
    return notes


def escape(key: str) -> str:
    return key.replace("~", "~0").replace("/", "~1")


def inline_refs(schema: Any, defs: dict[str, Any], stack: tuple[str, ...] = ()) -> Any:
    """Expand local ``$ref``s so a renamed model class is not a schema change."""
    if isinstance(schema, list):
        return [inline_refs(item, defs, stack) for item in schema]
    if not isinstance(schema, dict):
        return schema
    ref = schema.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/$defs/"):
        name = ref.removeprefix("#/$defs/")
        if name in stack:
            return {"$ref": "<recursive>"}
        rest = {k: v for k, v in schema.items() if k != "$ref"}
        return inline_refs({**defs[name], **rest}, defs, (*stack, name))
    return {k: inline_refs(v, defs, stack) for k, v in schema.items() if k != "$defs"}


def normalized(tool: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for key in ("inputSchema", "outputSchema"):
        schema = tool.get(key, {})
        result[key] = inline_refs(schema, schema.get("$defs", {}))
    result["annotations"] = tool.get("annotations", {})
    return result


# Keywords whose change never breaks a client; everything else is compared.
DOCUMENTATION = frozenset({"title", "description", "examples"})
# Input keywords that tighten when the number grows (or shrinks, for the maxima).
LOWER_BOUNDS = frozenset({"minimum", "exclusiveMinimum", "minLength", "minItems"})
UPPER_BOUNDS = frozenset({"maximum", "exclusiveMaximum", "maxLength", "maxItems"})


def schema_breaks(old: Any, new: Any, pointer: str, *, inbound: bool) -> Iterator[str]:
    """Breaking differences from ``old`` to ``new`` (TD-21-4), as ``pointer: reason``.

    ``inbound`` is true for an input schema (what clients send) and false for an
    output schema (what clients read). Additions a client cannot notice are allowed:
    new optional input properties, looser input bounds, extra input enum values, new
    output properties and new output enum values.
    """
    if type(old) is not type(new):
        yield f"{pointer}: type changed"
        return
    if isinstance(old, list):
        if len(old) != len(new):
            yield f"{pointer}: {len(old)} entries became {len(new)}"
            return
        for index, (a, b) in enumerate(zip(old, new, strict=True)):
            yield from schema_breaks(a, b, f"{pointer}/{index}", inbound=inbound)
        return
    if not isinstance(old, dict):
        if old != new:
            yield f"{pointer}: {old!r} became {new!r}"
        return
    for key in sorted(set(old) | set(new)):
        here = f"{pointer}/{escape(key)}"
        if key in DOCUMENTATION:
            continue
        if key not in new:
            if inbound and key in LOWER_BOUNDS | UPPER_BOUNDS | {"pattern", "const"}:
                continue  # an input constraint was dropped: looser
            yield f"{here}: removed"
            continue
        if key not in old:
            if inbound and key == "required":
                if new[key]:
                    yield f"{here}: newly required {new[key]}"
            elif key != "properties" and (inbound or key not in ("required", "enum")):
                yield f"{here}: added"  # a new constraint or keyword; additions are above
            continue
        a, b = old[key], new[key]
        if key == "properties" and isinstance(a, dict) and isinstance(b, dict):
            for name in sorted(set(a) - set(b)):
                yield f"{here}/{escape(name)}: removed"
            for name in sorted(set(a) & set(b)):
                yield from schema_breaks(
                    a[name], b[name], f"{here}/{escape(name)}", inbound=inbound
                )
            # New properties: optional inputs and output fields are additive; a new
            # required input is reported through ``required``.
        elif key == "required" and isinstance(a, list) and isinstance(b, list):
            grown, shrunk = set(b) - set(a), set(a) - set(b)
            if inbound and grown:
                yield f"{here}: newly required {sorted(grown)}"
            if not inbound and shrunk:
                yield f"{here}: no longer guaranteed {sorted(shrunk)}"
        elif key == "enum" and isinstance(a, list) and isinstance(b, list):
            removed = [value for value in a if value not in b]
            if removed:
                yield f"{here}: values removed {removed}"
        elif inbound and key in LOWER_BOUNDS and _numbers(a, b):
            if b > a:
                yield f"{here}: tightened {a} -> {b}"
        elif inbound and key in UPPER_BOUNDS and _numbers(a, b):
            if b < a:
                yield f"{here}: tightened {a} -> {b}"
        elif key == "additionalProperties" and isinstance(a, bool) and isinstance(b, bool):
            # An output schema that starts to allow unknown properties is the additive
            # direction (#130, versioning.md "Contract evolution"); only an input that
            # stops accepting them is a break.
            if a != b and inbound and not b:
                yield f"{here}: {a} became {b}"
        else:
            yield from schema_breaks(a, b, here, inbound=inbound)


def _numbers(a: Any, b: Any) -> bool:
    return all(isinstance(v, int | float) and not isinstance(v, bool) for v in (a, b))


def tool_breaks(old: dict[str, Any], new: dict[str, Any] | None) -> list[str]:
    if new is None:
        return ["/: tool removed or renamed"]
    before, after = normalized(old), normalized(new)
    problems = list(
        schema_breaks(before["inputSchema"], after["inputSchema"], "/inputSchema", inbound=True)
    )
    problems += schema_breaks(
        before["outputSchema"], after["outputSchema"], "/outputSchema", inbound=False
    )
    for hint in sorted(set(before["annotations"]) | set(after["annotations"])):
        if before["annotations"].get(hint) != after["annotations"].get(hint):
            problems.append(f"/annotations/{hint}: changed")
    return problems


def allowed(tool: str, problem: str, notes: list[Note]) -> bool:
    pointer = problem.split(": ", 1)[0]
    return any(
        note.tool == tool
        and (
            note.pointer == "/" or pointer == note.pointer or pointer.startswith(note.pointer + "/")
        )
        for note in notes
    )


def contract_breaks(
    retained: list[dict[str, Any]], served: list[dict[str, Any]], notes: list[Note]
) -> list[str]:
    """Unannounced breaking differences between a retained and the served contract."""
    current = {tool["name"]: tool for tool in served}
    problems = []
    for old in retained:
        name = old["name"]
        problems += [
            f"{name}{problem}"
            for problem in tool_breaks(old, current.get(name))
            if not allowed(name, problem, notes)
        ]
    return problems


def retained_tools(release: Path) -> list[dict[str, Any]]:
    return json.loads((release / "tools.json").read_text("utf-8"))


@pytest.fixture(scope="module")
def served(tmp_path_factory) -> list[dict[str, Any]]:
    return served_tools(tmp_path_factory.mktemp("served"))


@pytest.mark.parametrize("release", RETAINED, ids=release_ids())
def test_served_contract_stays_compatible_with_retained_release(release, served):
    assert contract_problems([tool["name"] for tool in served], "full") == []
    notes = migration_notes(VERSIONING.read_text("utf-8"))
    assert contract_breaks(retained_tools(release), served, notes) == []


def test_migration_notes_parse_and_name_retained_tools():
    notes = migration_notes(VERSIONING.read_text("utf-8"))
    names = {tool["name"] for release in RETAINED for tool in retained_tools(release)}
    assert all(note.tool in names | {"-"} for note in notes), "a note names an unknown tool"
    text = "\n".join(
        [
            "<!-- migration-notes:start -->",
            "| Release | Tool | JSON pointer | Change | Migration |",
            "| --- | --- | --- | --- | --- |",
            "| `9.1.0` | `wled_example` | `/inputSchema/properties/x` | renamed | use `y` |",
            "<!-- migration-notes:end -->",
        ]
    )
    assert migration_notes(text) == [Note("9.1.0", "wled_example", "/inputSchema/properties/x")]


# ---- negative and positive controls on mutated copies of the served contract


def first(served: list[dict[str, Any]], predicate) -> dict[str, Any]:
    for tool in served:
        if predicate(tool):
            return tool
    raise AssertionError("no served tool fits the control")


def with_properties(tool: dict[str, Any]) -> bool:
    return bool(tool["inputSchema"].get("properties"))


def bounded(tool: dict[str, Any]) -> bool:
    return any(
        "maximum" in prop or "maxLength" in prop
        for prop in normalized(tool)["inputSchema"].get("properties", {}).values()
    )


def mutate(served: list[dict[str, Any]], name: str, change) -> list[dict[str, Any]]:
    copied = copy.deepcopy(served)
    for tool in copied:
        if tool["name"] == name:
            change(tool)
    return copied


def rename_input(tool: dict[str, Any]) -> None:
    props = tool["inputSchema"]["properties"]
    key = sorted(props)[0]
    props[f"{key}_renamed"] = props.pop(key)


def require_all(tool: dict[str, Any]) -> None:
    schema = tool["inputSchema"]
    schema["required"] = sorted(set(schema.get("required", [])) | set(schema["properties"]))


def tighten_bound(tool: dict[str, Any]) -> None:
    schema = tool["inputSchema"]
    for prop in schema["properties"].values():
        target = schema["$defs"][prop["$ref"].rsplit("/", 1)[1]] if "$ref" in prop else prop
        for key in ("maximum", "maxLength"):
            if key in target:
                target[key] -= 1
                return
    raise AssertionError("no bounded input")


def flip_annotation(tool: dict[str, Any]) -> None:
    tool["annotations"]["readOnlyHint"] = not tool["annotations"]["readOnlyHint"]


def drop_output_field(tool: dict[str, Any]) -> None:
    tool["outputSchema"]["properties"].pop(sorted(tool["outputSchema"]["properties"])[0])


def drop_error_code(tool: dict[str, Any]) -> None:
    codes = tool["outputSchema"]["$defs"]["DomainError"]["properties"]["code"]["enum"]
    codes.remove(codes[-1])


@pytest.mark.parametrize(
    ("pick", "change", "fragment"),
    [
        (lambda t: True, None, "/: tool removed or renamed"),
        (with_properties, rename_input, ": removed"),
        (with_properties, require_all, "newly required"),
        (bounded, tighten_bound, "tightened"),
        (lambda t: True, flip_annotation, "/annotations/readOnlyHint: changed"),
        (lambda t: True, drop_output_field, "/outputSchema/properties/"),
        (
            lambda t: "DomainError" in t["outputSchema"].get("$defs", {}),
            drop_error_code,
            "values removed",
        ),
    ],
    ids=[
        "tool-removed",
        "field-renamed",
        "input-required",
        "input-tightened",
        "annotation-changed",
        "output-field-removed",
        "error-code-removed",
    ],
)
def test_breaking_changes_fail_without_and_pass_with_a_migration_note(
    served, pick, change, fragment
):
    retained = copy.deepcopy(served)  # the controls compare the served contract with itself
    target = first(served, pick)["name"]
    if change is None:
        mutated = [tool for tool in served if tool["name"] != target]
    else:
        mutated = mutate(served, target, change)
    problems = contract_breaks(retained, mutated, [])
    assert problems and all(problem.startswith(target) for problem in problems), problems
    assert any(fragment in problem for problem in problems), problems
    pointers = {problem.removeprefix(target).split(": ", 1)[0] for problem in problems}
    notes = [Note("9.0.0", target, pointer) for pointer in pointers]
    assert contract_breaks(retained, mutated, notes) == []
    assert contract_breaks(retained, mutated, [Note("9.0.0", "wled_other", "/")]) == problems


def add_optional_input(tool: dict[str, Any]) -> None:
    tool["inputSchema"].setdefault("properties", {})["synthetic_option"] = {
        "type": "boolean",
        "default": False,
    }


def add_output_field(tool: dict[str, Any]) -> None:
    tool["outputSchema"]["properties"]["synthetic_field"] = {"type": "string"}


def loosen_and_reword(tool: dict[str, Any]) -> None:
    tool["description"] += " Reworded."
    schema = tool["inputSchema"]
    schema["required"] = []


def add_error_code(tool: dict[str, Any]) -> None:
    defs = tool["outputSchema"].get("$defs", {})
    if "DomainError" in defs:
        defs["DomainError"]["properties"]["code"]["enum"].append("SYNTH")


@pytest.mark.parametrize(
    "change",
    [add_optional_input, add_output_field, loosen_and_reword, add_error_code, "new-tool"],
    ids=["optional-input", "output-field", "loosened-input", "output-enum-value", "new-tool"],
)
def test_additive_changes_pass_without_a_migration_note(served, change):
    retained = copy.deepcopy(served)
    if change == "new-tool":
        extra = copy.deepcopy(served[0])
        extra["name"] = "wled_synthetic_new_tool"
        mutated = [*served, extra]
    else:  # applied to every served tool at once
        mutated = copy.deepcopy(served)
        for tool in mutated:
            change(tool)
        assert mutated != retained
    assert contract_breaks(retained, mutated, []) == []


def test_renamed_model_class_is_not_a_schema_change(served):
    retained = copy.deepcopy(served)
    target = first(served, lambda t: "DomainError" in t["outputSchema"].get("$defs", {}))

    def rename(tool: dict[str, Any]) -> None:
        text = json.dumps(tool["outputSchema"]).replace("DomainError", "RenamedError")
        tool["outputSchema"] = json.loads(text)

    assert contract_breaks(retained, mutate(served, target["name"], rename), []) == []


# ===================================================================== A21-06 data


def file_states(directory: Path) -> dict[str, tuple[bytes, int]]:
    return {
        str(path.relative_to(directory)): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def install(release: Path, tmp_path: Path) -> tuple[Path, Path]:
    """Lay out the retained data as the release's server would have left it."""
    data = tmp_path / "data"
    shutil.copytree(release / "snapshots", data / "backups")
    (data / "config").mkdir()
    config = data / "config" / "devices.toml"
    shutil.copyfile(release / "config.toml", config)
    return config, data


@pytest.mark.parametrize("release", RETAINED, ids=release_ids())
def test_retained_configuration_loads_unchanged(release, tmp_path):
    config, data = install(release, tmp_path)
    before = file_states(data)
    loaded = load_config(str(config), str(data), {})
    raw = tomllib.loads(config.read_text("utf-8"))
    assert raw["schema_version"] == SCHEMA_VERSION
    assert [device.id for device in loaded.devices] == [d["id"] for d in raw["devices"]]
    assert file_states(data) == before


@pytest.mark.parametrize("release", RETAINED, ids=release_ids())
def test_retained_snapshots_load_list_and_are_never_rewritten(release, tmp_path):
    _config, data = install(release, tmp_path)
    store = SnapshotStore(data / "backups", 20)
    before = file_states(data / "backups")
    for path in sorted((data / "backups").glob("*/*.json")):
        device_id, backup_id = path.parent.name, path.stem
        snapshot = store.load(device_id, backup_id)
        assert snapshot.backup_id == backup_id and snapshot.device_id == device_id
        listing = store.list_snapshots(device_id)
        assert backup_id in [item.backup_id for item in listing.snapshots]
        assert listing.invalid_count == 0
        # A new snapshot by the current server leaves the retained file untouched.
        store.backup_preset(device_id, 7, {"n": "after upgrade", "on": True}, FIRMWARE)
    after = file_states(data / "backups")
    assert {name: after[name] for name in before} == before


@pytest.mark.parametrize("newer", [SCHEMA_VERSION + 1, SCHEMA_VERSION + 41])
def test_newer_configuration_is_rejected_naming_its_version(tmp_path, newer):
    release = RETAINED[-1]
    config, data = install(release, tmp_path)
    text = config.read_text("utf-8")
    config.write_text(
        text.replace(f"schema_version = {SCHEMA_VERSION}", f"schema_version = {newer}", 1),
        encoding="utf-8",
        newline="\n",
    )
    before = file_states(data)
    with pytest.raises(ConfigurationError) as caught:
        load_config(str(config), str(data), {})
    message = str(caught.value)
    assert f"schema_version {newer};" in message
    assert f"reads schema_version {SCHEMA_VERSION}" in message
    assert "newer server version" in message
    assert file_states(data) == before


@pytest.mark.parametrize("newer", [FORMAT_VERSION + 1, FORMAT_VERSION + 41])
def test_newer_snapshot_is_rejected_naming_its_version_and_kept(tmp_path, newer):
    release = RETAINED[-1]
    _config, data = install(release, tmp_path)
    path = sorted((data / "backups").glob("*/*.json"))[0]
    document = json.loads(path.read_text("utf-8"))
    document["format_version"] = newer
    path.write_text(json.dumps(document), encoding="utf-8", newline="\n")
    store = SnapshotStore(data / "backups", 20)
    before = file_states(data / "backups")
    with pytest.raises(ClientFailure) as caught:
        store.load(path.parent.name, path.stem)
    assert caught.value.error.message == (
        f"Unsupported snapshot format version {newer}; this server reads format version "
        f"{FORMAT_VERSION}."
    )
    listing = store.list_snapshots(path.parent.name)
    assert listing.invalid_count == 1 and path.stem not in [s.backup_id for s in listing.snapshots]
    assert file_states(data / "backups") == before


def test_newer_snapshot_survives_pruning_by_the_current_server(tmp_path):
    # Retention counts valid snapshots only; an unreadable newer file is never deleted.
    store = make_store(tmp_path, retain=1)
    newer = store.backup_preset("desk", 5, {"n": "x"}, FIRMWARE)
    path = store.directory / "desk" / f"{newer.backup_id}.json"
    document = json.loads(path.read_text("utf-8"))
    document["format_version"] = FORMAT_VERSION + 1
    path.write_text(json.dumps(document), encoding="utf-8", newline="\n")
    content = path.read_bytes()
    for preset_id in (6, 7, 8):
        store.backup_preset("desk", preset_id, {"n": "y"}, FIRMWARE)
    assert path.read_bytes() == content


# ------------------------------------------------------------- envelope stays a superset


def leaves(value: Any, pointer: str = "") -> Iterator[tuple[str, Any]]:
    if isinstance(value, dict) and value:
        for key, item in value.items():
            yield from leaves(item, f"{pointer}/{escape(key)}")
    elif isinstance(value, list) and value:
        # The length is a value of its own, so only new object keys inside elements add.
        # The pointer could only collide with an object key literally named "#length";
        # neither the envelope nor the retained WLED payloads have such a key.
        yield f"{pointer}/#length", len(value)
        for index, item in enumerate(value):
            yield from leaves(item, f"{pointer}/{index}")
    else:
        yield pointer, value


def envelope_difference(old: Any, new: Any) -> tuple[list[str], list[str]]:
    """(missing, changed) leaf pointers of ``old`` in ``new``; extra leaves are additions."""
    before, after = dict(leaves(old)), dict(leaves(new))
    missing = sorted(set(before) - set(after))
    changed = sorted(p for p in set(before) & set(after) if before[p] != after[p])
    return missing, changed


def test_list_elements_are_compared_by_index_and_length():
    old = {"segments": [{"id": 0, "on": True}], "unknown": ["a"]}
    added_key = {"segments": [{"id": 0, "on": True, "cct": 127}], "unknown": ["a"]}
    assert envelope_difference(old, added_key) == ([], [])
    changed = {"segments": [{"id": 0, "on": False}], "unknown": ["a"]}
    assert envelope_difference(old, changed) == ([], ["/segments/0/on"])
    grown = {"segments": [{"id": 0, "on": True}], "unknown": ["a", "b"]}
    assert envelope_difference(old, grown) == ([], ["/unknown/#length"])
    shrunk = {"segments": [{"id": 0, "on": True}], "unknown": []}
    assert envelope_difference(old, shrunk) == (["/unknown/#length", "/unknown/0"], [])
    no_segment = {"segments": [], "unknown": ["a"]}
    assert envelope_difference(old, no_segment)[0] == [
        "/segments/#length",
        "/segments/0/id",
        "/segments/0/on",
    ]


# Values that legitimately differ between the release that wrote the fixture and now.
VARYING = ("/data/diagnostics/server_version", "/data/freshness/read_at")


@pytest.mark.parametrize("release", RETAINED, ids=release_ids())
def test_get_state_envelope_only_adds_to_the_retained_one(release, tmp_path):
    retained = json.loads((release / "get_state.json").read_text("utf-8"))
    Outcome.model_validate(retained)  # the current model still reads the old envelope
    raw = retained["data"]["raw"]

    def device(request: httpx.Request) -> httpx.Response:
        routes = {"/json/info": raw["info"], "/json/state": raw["state"]}
        return httpx.Response(200, json=routes[request.url.path])

    async def current() -> dict[str, Any]:
        async with Resources(synthetic_config(tmp_path), httpx.MockTransport(device)) as res:
            operation = {op.name: op for op in build_operations(res)}["wled_get_state"]
            outcome = await operation.execute({"device_id": retained["device_id"]})
        return outcome.model_dump(mode="json")

    current_envelope = anyio.run(current)
    missing, changed = envelope_difference(retained, current_envelope)
    # The device name comes from the synthetic test inventory, not the retained one.
    changed = [p for p in changed if p not in VARYING and p != "/data/device/name"]
    assert (missing, changed) == ([], [])
    added = set(dict(leaves(current_envelope))) - set(dict(leaves(retained)))
    assert added >= {"/data/diagnostics/firmware_support/tier"}


# ================================================================ additive output (#130)


def served_envelope(tmp_path: Path) -> dict[str, Any]:
    """A real served result envelope (``wled_list_devices`` on the synthetic inventory)."""

    async def call() -> dict[str, Any]:
        async with Resources(synthetic_config(tmp_path)) as resources:
            async with Client(create_server(build_operations(resources))) as client:
                result = await client.call_tool("wled_list_devices", {})
        assert not result.is_error
        return dict(result.structured_content)

    return anyio.run(call)


def test_every_served_output_schema_tolerates_unknown_envelope_and_error_fields(served):
    for tool in served:
        schema = normalized(tool)["outputSchema"]
        assert schema["additionalProperties"] is True, tool["name"]
        assert schema["properties"]["error"]["anyOf"][0]["additionalProperties"] is True, tool[
            "name"
        ]
        # Loosening must not weaken what the envelope guarantees.
        assert {"ok", "operation", "device_id", "application", "verification"} <= set(
            schema["required"]
        )


def test_current_envelope_accepts_future_additive_fields(served, tmp_path):
    import jsonschema  # a dependency of mcp; not skipped, so a missing one fails loudly

    envelope = served_envelope(tmp_path)
    assert "correlation_id" in envelope
    future = copy.deepcopy(envelope) | {"future_top_level_field": 1}
    future["error"] = {
        "code": "CONFIG_ERROR",
        "message": "m",
        "read_retryable": False,
        "write_retryable": False,
        "reconciliation": "r",
        "future_error_field": ["x"],
    }
    for tool in served:
        jsonschema.validate(envelope, tool["outputSchema"])
        jsonschema.validate(future, tool["outputSchema"])


def test_schema_cached_from_the_first_release_rejects_current_envelope(tmp_path):
    """The documented one-time transition (#130), not a behaviour to keep.

    A client that cached a 0.1.0 ``outputSchema`` (``additionalProperties: false``, no
    ``correlation_id``) rejects every envelope that carries the later top-level field until
    it refreshes ``tools/list``. Schemas served from the #130 change on tolerate additive
    fields (test above), so this cannot recur for them.
    """
    import jsonschema  # a dependency of mcp; not skipped, so a missing one fails loudly

    envelope = served_envelope(tmp_path)
    for release in RETAINED:
        for tool in retained_tools(release):
            with pytest.raises(jsonschema.ValidationError, match="Additional properties"):
                jsonschema.validate(envelope, tool["outputSchema"])
            without = {k: v for k, v in envelope.items() if k != "correlation_id"}
            jsonschema.validate(without, tool["outputSchema"])
