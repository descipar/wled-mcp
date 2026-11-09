"""Scene format 1 (issue #17): strict parser, expansion, duplicate policy and sharing.

A scene describes the desired master and segment state per target (a configured device or
a stored group). It is pure data: no network, no filesystem. It holds no device address,
credential or free URL (no field takes one), only configured IDs, numeric values and
effect/palette names or IDs (S2-GROUP-02). The segment and master fields are validated by
the models of the single-device tools (``SetStateRequest``, ``SegmentPatch``) so a scene
cannot accept a value those tools refuse; the planners decide per device at plan time.

Schema evolution follows TD-21-5 through ``formats.check_format``. A shareable export
replaces device and group references with placeholders and refuses free text that contains
an inventory host token (TD-17-12).
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final, Literal
from urllib.parse import urlsplit

from pydantic import JsonValue, ValidationError

from wled_mcp.client import ClientFailure
from wled_mcp.config import Device
from wled_mcp.formats import ID_RE, check_format, decode_document, echo, invalid, is_int
from wled_mcp.groups import (
    Group,
    check_definition_id,
    check_id,
    check_name,
    check_segment_ids,
)
from wled_mcp.models import ErrorCode
from wled_mcp.patches import SegmentPatch, SetStateRequest

SCENE_FORMAT: Final = "wled-mcp.scene"
SCENE_FORMAT_VERSION: Final = 1
SUPPORTED_SCENE_VERSIONS: Final = frozenset({SCENE_FORMAT_VERSION})
MAX_DOCUMENT_BYTES: Final = 64 * 1024
MAX_TARGETS: Final = 16
MAX_SEGMENT_ENTRIES: Final = 16
MAX_DESCRIPTION: Final = 256
MAX_CATALOG_NAME: Final = 128
# Fixed limits of the request, not configuration (TD-17-9).
MAX_EXPANDED_DEVICES: Final = 16
MAX_SEGMENT_PATCHES: Final = 64  # the `wled_patch_segments` list bound, per device

SCENE_KEYS: Final = (
    "format",
    "format_version",
    "id",
    "name",
    "description",
    "placeholders",
    "targets",
)
REQUIRED_KEYS: Final = ("format", "format_version", "id", "name", "targets")
MASTER_FIELDS: Final = ("on", "brightness", "transition_ms")
NAME_FIELDS: Final = ("effect_name", "palette_name")
# The allowlist of segment fields a scene can set (TD-17-5). Geometry, names, `selected`,
# `freeze`, `blend_mode`, grouping/spacing/offset, orientation and raw state are excluded.
SEGMENT_FIELDS: Final = (
    "on",
    "brightness",
    "colors",
    "effect_id",
    "effect_name",
    "palette_id",
    "palette_name",
    "speed",
    "intensity",
    "cct",
    "custom1",
    "custom2",
    "custom3",
    "check1",
    "check2",
    "check3",
)
EXCLUSIVE: Final = (("effect_id", "effect_name"), ("palette_id", "palette_name"))
TARGET_KEYS: Final = frozenset({"device", "group", "master", "segments"})
ENTRY_KEYS: Final = frozenset({"ids", *SEGMENT_FIELDS})

TargetKind = Literal["device", "group"]


@dataclass(frozen=True)
class SegmentEntry:
    """The same fields for every listed segment ID; ``ids`` None means the member's own."""

    ids: tuple[int, ...] | None
    fields: Mapping[str, JsonValue]


@dataclass(frozen=True)
class SceneTarget:
    kind: TargetKind
    ref: str
    master: Mapping[str, JsonValue] | None
    segments: tuple[SegmentEntry, ...]


@dataclass(frozen=True)
class Scene:
    id: str
    name: str
    description: str | None
    targets: tuple[SceneTarget, ...]
    # Present only in a shareable document: every target reference is one of these.
    placeholders: tuple[str, ...] | None = None


@dataclass(frozen=True)
class ResolvedSegments:
    ids: tuple[int, ...]
    fields: Mapping[str, JsonValue]


@dataclass(frozen=True)
class LiveBinding:
    """What a target's ``bind`` decided from the fresh device read (issue #27)."""

    segments: tuple[ResolvedSegments, ...]
    data: Mapping[str, JsonValue]


class BindingFailure(ClientFailure):
    """A refusal of ``bind`` that carries a structured, content-free ``problem`` mapping."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        problem: Mapping[str, JsonValue],
        *,
        reconciliation: str | None = None,
    ) -> None:
        super().__init__(code, message, reconciliation=reconciliation)
        self.problem = dict(problem)


_View = Mapping[str, JsonValue]
# fresh view, capabilities, raw info, raw state -> segments to patch and report data
Binder = Callable[[_View, _View, _View, _View], LiveBinding]


@dataclass(frozen=True)
class ExpandedTarget:
    """One device after expansion, with the exact targets it receives.

    ``bind`` is ``None`` for scenes. A zone sets it: it runs after the fresh read, under the
    device lock, in the plan and again in the write step, and decides the segment IDs from
    the live layout (and may refuse by raising ``BindingFailure`` before anything is sent).
    """

    device_id: str
    origin: str  # "device", "group:<id>/member:<n>" or "zone:<id>/part:<n>"
    target_index: int  # 1-based position of the scene target
    master: Mapping[str, JsonValue] | None
    segments: tuple[ResolvedSegments, ...]
    bind: Binder | None = field(default=None, compare=False, repr=False)


# --------------------------------------------------------------------------- parsing


def _field_message(where: str, error: ValidationError) -> ClientFailure:
    """Names the offending field only; never quotes the supplied value."""
    location = ".".join(str(part) for part in error.errors()[0]["loc"] if part != "id")
    return invalid(f"{where}: field {location or 'value'!r} is invalid.")


def _parse_master(value: object, where: str) -> dict[str, JsonValue]:
    if not isinstance(value, dict) or not value:
        raise invalid(f"{where}: 'master' must be a nonempty object.")
    unknown = sorted(str(key) for key in value if key not in MASTER_FIELDS)
    if unknown:
        raise invalid(f"{where}: unknown master field {echo(unknown[0])}.")
    if "on" not in value and "brightness" not in value:
        raise invalid(f"{where}: master needs at least one of 'on' or 'brightness'.")
    try:
        SetStateRequest.model_validate({"device_id": "scene", **value})
    except ValidationError as error:
        raise _field_message(f"{where}: master", error) from None
    return {key: value[key] for key in MASTER_FIELDS if key in value}


def _check_colors(value: object, where: str) -> None:
    ok = (
        isinstance(value, list)
        and 1 <= len(value) <= 3
        and all(
            isinstance(slot, list)
            and len(slot) in (3, 4)
            and all(is_int(channel) and 0 <= channel <= 255 for channel in slot)
            for slot in value
        )
    )
    if not ok:
        raise invalid(
            f"{where}: 'colors' must hold 1-3 slots of 3 or 4 integers 0-255 (the channel "
            "count is checked per device)."
        )


def _parse_entry(value: object, kind: TargetKind, where: str) -> SegmentEntry:
    if not isinstance(value, dict):
        raise invalid(f"{where} must be an object.")
    unknown = sorted(str(key) for key in value if key not in ENTRY_KEYS)
    if unknown:
        raise invalid(f"{where}: unknown or unsupported segment field {echo(unknown[0])}.")
    ids: tuple[int, ...] | None = None
    if "ids" in value:
        ids = check_segment_ids(value["ids"], where, "ids")
    elif kind == "device":
        raise invalid(f"{where}: a device target needs explicit 'ids'.")
    fields = {key: value[key] for key in SEGMENT_FIELDS if key in value}
    if not fields:
        raise invalid(f"{where}: set at least one field.")
    for first, second in EXCLUSIVE:
        if first in fields and second in fields:
            raise invalid(f"{where}: '{first}' and '{second}' are mutually exclusive.")
    for key in NAME_FIELDS:
        if key in fields:
            check_name_text(fields[key], f"{where}: '{key}'")
    if "colors" in fields:
        _check_colors(fields["colors"], where)
    numeric = {
        key: item for key, item in fields.items() if key not in NAME_FIELDS and key != "colors"
    }
    try:
        SegmentPatch.model_validate({"id": 0, **numeric})
    except ValidationError as error:
        raise _field_message(where, error) from None
    return SegmentEntry(ids, fields)


def check_name_text(value: object, where: str) -> None:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > MAX_CATALOG_NAME
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        raise invalid(
            f"{where} must be a nonblank catalog name of at most {MAX_CATALOG_NAME} characters."
        )


def _parse_target(value: object, position: int) -> SceneTarget:
    where = f"Target {position}"
    if not isinstance(value, dict):
        raise invalid(f"{where} must be an object.")
    unknown = sorted(str(key) for key in value if key not in TARGET_KEYS)
    if unknown:
        raise invalid(f"{where}: unknown key {echo(unknown[0])}.")
    if ("device" in value) == ("group" in value):
        raise invalid(f"{where}: name exactly one of 'device' or 'group'.")
    kind: TargetKind = "device" if "device" in value else "group"
    ref = check_id(value[kind], f"{kind} reference of target {position}")
    if "master" not in value and "segments" not in value:
        raise invalid(f"{where}: set 'master' and/or 'segments'.")
    master = _parse_master(value["master"], where) if "master" in value else None
    entries: tuple[SegmentEntry, ...] = ()
    if "segments" in value:
        raw = value["segments"]
        if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_SEGMENT_ENTRIES:
            raise invalid(f"{where}: 'segments' must list 1-{MAX_SEGMENT_ENTRIES} entries.")
        entries = tuple(
            _parse_entry(item, kind, f"{where}, segment entry {index}")
            for index, item in enumerate(raw, start=1)
        )
        if kind == "device":
            seen: set[int] = set()
            for entry in entries:
                assert entry.ids is not None
                for segment_id in entry.ids:
                    if segment_id in seen:
                        raise invalid(
                            f"{where}: segment ID {segment_id} is set by more than one entry."
                        )
                    seen.add(segment_id)
    return SceneTarget(kind, ref, master, entries)


def parse_scene(raw: str | bytes | dict[str, JsonValue], *, allow_placeholders: bool) -> Scene:
    """Strictly validate a scene document (JSON text, bytes or object); VALIDATION_ERROR.

    ``allow_placeholders`` is true for a shared document that is about to be mapped; the
    stored form (``False``) never carries placeholders.
    """
    document = decode_document(raw, "scene document", MAX_DOCUMENT_BYTES)
    if not isinstance(document, dict):
        raise invalid("A scene document must be a JSON object.")
    check_format(
        document,
        format_name=SCENE_FORMAT,
        label="scene",
        supported=SUPPORTED_SCENE_VERSIONS,
        current=SCENE_FORMAT_VERSION,
    )
    unknown = sorted(str(key) for key in document if key not in SCENE_KEYS)
    if unknown:
        raise invalid(f"Unknown scene key {echo(unknown[0])}.")
    missing = [key for key in REQUIRED_KEYS if key not in document]
    if missing:
        raise invalid(f"Missing scene key {missing[0]!r}.")
    description: str | None = None
    if "description" in document:
        text = document["description"]
        if (
            not isinstance(text, str)
            or not text.strip()
            or len(text) > MAX_DESCRIPTION
            or any(ord(char) < 32 or ord(char) == 127 for char in text)
        ):
            raise invalid(
                f"'description' must be 1-{MAX_DESCRIPTION} characters without control characters."
            )
        description = text
    raw_targets = document["targets"]
    if not isinstance(raw_targets, list) or not 1 <= len(raw_targets) <= MAX_TARGETS:
        raise invalid(f"'targets' must list 1-{MAX_TARGETS} entries.")
    targets = tuple(
        _parse_target(item, position) for position, item in enumerate(raw_targets, start=1)
    )
    placeholders: tuple[str, ...] | None = None
    if "placeholders" in document:
        if not allow_placeholders:
            raise invalid("A stored scene cannot carry 'placeholders'; map them with target_map.")
        placeholders = _parse_placeholders(document["placeholders"], targets)
    return Scene(
        check_definition_id(document["id"], "scene ID"),
        check_name(document["name"], "scene name"),
        description,
        targets,
        placeholders,
    )


def _parse_placeholders(value: object, targets: Sequence[SceneTarget]) -> tuple[str, ...]:
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_TARGETS:
        raise invalid(f"'placeholders' must list 1-{MAX_TARGETS} names.")
    names: list[str] = []
    for item in value:
        if not isinstance(item, str) or ID_RE.match(item) is None:
            raise invalid("Placeholder names must match [a-z0-9][a-z0-9_-]{0,63}.")
        names.append(item)
    if len(set(names)) != len(names):
        raise invalid("Placeholder names must be unique.")
    used = {target.ref for target in targets}
    if used != set(names):
        raise invalid("'placeholders' must list exactly the references the targets use.")
    return tuple(names)


# --------------------------------------------------------------------------- document


def scene_document(scene: Scene) -> dict[str, JsonValue]:
    """The stored (and returned) document of a scene; ``parse_scene`` reads it back."""
    targets: list[JsonValue] = []
    for target in scene.targets:
        entry: dict[str, JsonValue] = {target.kind: target.ref}
        if target.master is not None:
            entry["master"] = dict(target.master)
        if target.segments:
            segments: list[JsonValue] = []
            for item in target.segments:
                segment: dict[str, JsonValue] = {}
                if item.ids is not None:
                    segment["ids"] = list(item.ids)
                segment.update(item.fields)
                segments.append(segment)
            entry["segments"] = segments
        targets.append(entry)
    document: dict[str, JsonValue] = {
        "format": SCENE_FORMAT,
        "format_version": SCENE_FORMAT_VERSION,
        "id": scene.id,
        "name": scene.name,
    }
    if scene.description is not None:
        document["description"] = scene.description
    if scene.placeholders is not None:
        document["placeholders"] = list(scene.placeholders)
    document["targets"] = targets
    return document


def scene_summary(scene: Scene) -> dict[str, JsonValue]:
    return {
        "id": scene.id,
        "name": scene.name,
        "description": scene.description,
        "target_count": len(scene.targets),
    }


# --------------------------------------------------------------------------- expansion


def _origin(kind: TargetKind, group_id: str | None, member: int | None) -> str:
    return "device" if kind == "device" else f"group:{group_id}/member:{member}"


def expand_scene(scene: Scene, groups: Mapping[str, Group]) -> tuple[ExpandedTarget, ...]:
    """Pure expansion in document order (a group in member order) with the duplicate rule.

    A device may occur once after expansion; a second occurrence (direct plus group, or two
    groups sharing a device) is refused naming the device and both origins, and nothing is
    merged. Raises VALIDATION_ERROR before any device I/O for an unknown group, a segment
    entry without IDs on a member that designates none, repeated segment IDs, more than 16
    devices or more than 64 segment patches for one device. Whether a device is configured
    is a per-device preflight question and is not decided here.
    """
    expanded: list[ExpandedTarget] = []
    first_seen: dict[str, tuple[int, str]] = {}
    for position, target in enumerate(scene.targets, start=1):
        if target.kind == "device":
            members: list[tuple[str, tuple[int, ...] | None, str]] = [
                (target.ref, None, _origin("device", None, None))
            ]
        else:
            group = groups.get(target.ref)
            if group is None:
                raise invalid(f"Target {position} names group {target.ref!r}, which is not stored.")
            members = [
                (member.device, member.segments, _origin("group", group.id, number))
                for number, member in enumerate(group.members, start=1)
            ]
        for device_id, designated, origin in members:
            previous = first_seen.get(device_id)
            if previous is not None:
                raise invalid(
                    f"Device {device_id!r} is targeted twice: by target {previous[0]} "
                    f"({previous[1]}) and by target {position} ({origin}). A device may "
                    "appear once per scene after groups are expanded; nothing is merged."
                )
            first_seen[device_id] = (position, origin)
            expanded.append(
                ExpandedTarget(
                    device_id,
                    origin,
                    position,
                    target.master,
                    _resolve_segments(target, designated, device_id, position),
                )
            )
            if len(expanded) > MAX_EXPANDED_DEVICES:
                raise invalid(
                    f"The scene expands to more than {MAX_EXPANDED_DEVICES} devices; split it."
                )
    return tuple(expanded)


def _resolve_segments(
    target: SceneTarget, designated: tuple[int, ...] | None, device_id: str, position: int
) -> tuple[ResolvedSegments, ...]:
    resolved: list[ResolvedSegments] = []
    seen: set[int] = set()
    total = 0
    for index, entry in enumerate(target.segments, start=1):
        ids = entry.ids if entry.ids is not None else designated
        if ids is None:
            raise invalid(
                f"Target {position}, segment entry {index}: no 'ids' and device {device_id!r} "
                "designates no segments in its group; list the IDs or designate them in the group."
            )
        for segment_id in ids:
            if segment_id in seen:
                raise invalid(
                    f"Target {position}: segment ID {segment_id} of device {device_id!r} is set "
                    "by more than one entry."
                )
            seen.add(segment_id)
        total += len(ids)
        resolved.append(ResolvedSegments(ids, entry.fields))
    if total > MAX_SEGMENT_PATCHES:
        raise invalid(
            f"Device {device_id!r} would receive {total} segment patches; the limit is "
            f"{MAX_SEGMENT_PATCHES}."
        )
    return tuple(resolved)


def group_references(scene: Scene) -> list[str]:
    """Distinct group IDs the scene names, in first-use order."""
    return list(dict.fromkeys(t.ref for t in scene.targets if t.kind == "group"))


# --------------------------------------------------------------------------- sharing


def inventory_tokens(devices: Collection[Device]) -> list[str]:
    """Host, root URL and authority of every configured device, casefolded."""
    tokens: set[str] = set()
    for device in devices:
        parts = urlsplit(device.base_url)
        for candidate in (parts.hostname, parts.netloc, device.base_url):
            if candidate and len(candidate) >= 4:
                tokens.add(candidate.casefold())
    return sorted(tokens)


def exported_strings(scene: Scene, *, include_targets: bool) -> list[tuple[str, str]]:
    """Every string value a shareable export of ``scene`` carries, with its field path.

    The fixed envelope (``format``) is not scanned. The target references are scanned only
    when the export keeps them; otherwise they are placeholders. Catalog names are included:
    they are free text just like the name and the description.
    """
    found: list[tuple[str, str]] = [("id", scene.id), ("name", scene.name)]
    if scene.description is not None:
        found.append(("description", scene.description))
    for position, target in enumerate(scene.targets, start=1):
        if include_targets:
            found.append((f"targets.{position}.{target.kind}", target.ref))
        for index, entry in enumerate(target.segments, start=1):
            for key in NAME_FIELDS:
                value = entry.fields.get(key)
                if isinstance(value, str):
                    found.append((f"targets.{position}.segments.{index}.{key}", value))
    return found


def leaking_fields(
    scene: Scene, tokens: Sequence[str], *, include_targets: bool = False
) -> list[str]:
    """Paths of the exported string values that contain an inventory token (never the text)."""
    return [
        path
        for path, text in exported_strings(scene, include_targets=include_targets)
        if any(token in text.casefold() for token in tokens)
    ]


def export_scene(scene: Scene, *, include_targets: bool, tokens: Sequence[str]) -> Scene:
    """The shareable form: placeholders ``t1``..``tn`` unless ``include_targets``.

    Raises VALIDATION_ERROR naming the scene and field (not the text) when any exported
    string value (ID, name, description, effect or palette name and, with
    ``include_targets``, the target references) contains an inventory host token.
    """
    leaks = leaking_fields(scene, tokens, include_targets=include_targets)
    if leaks:
        raise invalid(
            f"Scene {scene.id!r}: field {leaks[0]!r} contains a configured device host; edit "
            "the text before sharing."
        )
    if include_targets:
        return scene
    names = tuple(f"t{number}" for number in range(1, len(scene.targets) + 1))
    targets = tuple(
        SceneTarget(target.kind, name, target.master, target.segments)
        for target, name in zip(scene.targets, names, strict=True)
    )
    return Scene(scene.id, scene.name, scene.description, targets, names)


@dataclass(frozen=True)
class TargetMapping:
    kind: TargetKind
    ref: str


def apply_target_map(
    scene: Scene,
    target_map: Mapping[str, TargetMapping],
    *,
    devices: Collection[str],
    groups: Collection[str],
) -> Scene:
    """Replace every placeholder, all or nothing, validated against inventory and groups."""
    assert scene.placeholders is not None
    unmapped = [name for name in scene.placeholders if name not in target_map]
    if unmapped:
        raise invalid(f"Placeholder {unmapped[0]!r} has no entry in target_map.")
    unknown = sorted(name for name in target_map if name not in scene.placeholders)
    if unknown:
        raise invalid(f"target_map names {echo(unknown[0])}, which is not a placeholder.")
    targets: list[SceneTarget] = []
    for target in scene.targets:
        mapping = target_map[target.ref]
        if mapping.kind != target.kind:
            raise invalid(
                f"Placeholder {target.ref!r} stands for a {target.kind}; map it to a {target.kind}."
            )
        known = devices if mapping.kind == "device" else groups
        if mapping.ref not in known:
            raise invalid(
                f"Placeholder {target.ref!r} maps to {mapping.kind} {mapping.ref!r}, which is "
                f"not {'configured' if mapping.kind == 'device' else 'a stored group'}."
            )
        targets.append(SceneTarget(target.kind, mapping.ref, target.master, target.segments))
    return Scene(scene.id, scene.name, scene.description, tuple(targets), None)


def check_references(scene: Scene, *, devices: Collection[str], groups: Collection[str]) -> None:
    """Every device is configured and every group is stored (checked when a scene is saved)."""
    for position, target in enumerate(scene.targets, start=1):
        if target.kind == "device" and target.ref not in devices:
            raise invalid(
                f"Target {position} names device {target.ref!r}, which is not configured."
            )
        if target.kind == "group" and target.ref not in groups:
            raise invalid(
                f"Target {position} names group {target.ref!r}, which is not stored or cannot "
                "be used."
            )
