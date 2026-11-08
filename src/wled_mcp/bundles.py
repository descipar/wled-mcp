"""Preset bundle format 1 (issue #18): parser, export builder and import planning.

No network I/O. A bundle is untrusted caller input: it is parsed strictly, bounded in
size before anything else happens and never written to a file by the server. It carries
shareable preset content only: no device ID, address, host, MAC, BSSID, credential,
inventory name or ``info`` dump (S2-PRESET-01). Schema evolution follows TD-21-5
(ISSUE-21-DEC-002): an integer ``format_version``; a higher or unknown version is
rejected with the version named; a semantic change bumps the version.

Import planning (ISSUE-18-DEC-003) is deterministic and complete before any write:
destination IDs from ``id_map`` or the lowest free ID 1-250 in bundle order, explicit
overwrite intent per occupied destination, no automatic LED-range, segment or matrix
conversion, effect and palette IDs kept only when the target names them the same, and
playlist members rewritten through the same destination mapping.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Final, Literal
from urllib.parse import urlsplit

from pydantic import JsonValue

from wled_mcp.capabilities import parse_matrix
from wled_mcp.client import ClientFailure, validate_json
from wled_mcp.models import ErrorCode
from wled_mcp.preset_writes import (
    Route,
    check_playlist_entry,
    live_effect,
    refuse_running_playlist,
)
from wled_mcp.presets import (
    MAX_PERSISTENT_ID,
    MIN_PERSISTENT_ID,
    PresetStore,
    classify,
    entry_name,
    playlist_members,
    referencing_playlists,
)

BUNDLE_FORMAT: Final = "wled-mcp.preset-bundle"
BUNDLE_FORMAT_VERSION: Final = 1
SUPPORTED_FORMAT_VERSIONS: Final = frozenset({BUNDLE_FORMAT_VERSION})
MAX_FORMAT_VERSION: Final = 9999
MAX_BUNDLE_BYTES: Final = 192 * 1024  # below the 256 KiB HTTP request body limit
MAX_IMPORT_ENTRIES: Final = 50
MAX_BUNDLE_ENTRIES: Final = MAX_PERSISTENT_ID
MAX_CATALOG_ID: Final = 65_535
MAX_TEXT: Final = 256
KEY_ECHO: Final = 32

ENVELOPE_KEYS: Final = ("format", "format_version", "created_at", "source", "catalog", "presets")
ENTRY_KEYS: Final = frozenset({"source_id", "name", "type", "preset"})
ENTRY_TYPES: Final = ("state", "playlist", "api-command", "unknown")
WRITABLE_TYPES: Final = ("state", "playlist")
TIMESTAMP_RE: Final = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
CANONICAL_ID_RE: Final = re.compile(r"^(0|[1-9][0-9]{0,4})$")

CatalogKind = Literal["effect", "palette"]

BUNDLE_RECONCILE: Final = "Correct the bundle; nothing was read from or written to the device."


def _bad(message: str) -> ClientFailure:
    return ClientFailure("VALIDATION_ERROR", message, reconciliation=BUNDLE_RECONCILE)


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _echo(key: object) -> str:
    return repr(str(key)[:KEY_ECHO])


def serialized_size(value: object) -> int:
    """UTF-8 size of the compact JSON serialization (the bound of R18-EXP-06)."""
    text = json.dumps(value, allow_nan=False, separators=(",", ":"), ensure_ascii=False)
    return len(text.encode("utf-8"))


def _reject_duplicates(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _reject_constant(_: str) -> JsonValue:
    raise ValueError("non-finite number")


# --------------------------------------------------------------------------- model


@dataclass(frozen=True)
class BundleEntry:
    source_id: int
    name: str | None
    type: str
    preset: JsonValue


@dataclass(frozen=True)
class Bundle:
    created_at: str
    firmware_version: str
    led_count: int | None
    max_segments: int | None
    matrix: tuple[int, int] | None
    effects: dict[int, str]
    palettes: dict[int, str]
    entries: tuple[BundleEntry, ...]


# -------------------------------------------------------------------------- parser


def _decode(raw: str | dict[str, JsonValue]) -> object:
    if isinstance(raw, str):
        try:
            encoded = raw.encode("utf-8")
        except UnicodeEncodeError:
            raise _bad("The bundle text is not valid Unicode.") from None
        if len(encoded) > MAX_BUNDLE_BYTES:
            raise _bad(
                f"The bundle exceeds {MAX_BUNDLE_BYTES} bytes; export or import fewer presets."
            )
        try:
            return json.loads(
                raw, object_pairs_hook=_reject_duplicates, parse_constant=_reject_constant
            )
        except (ValueError, RecursionError):
            raise _bad(
                "The bundle is not strict JSON (syntax errors, duplicate keys, NaN and "
                "Infinity are rejected)."
            ) from None
    return raw


def parse_bundle(raw: str | dict[str, JsonValue]) -> Bundle:
    """Strictly validate a bundle (JSON text or object); raise VALIDATION_ERROR."""
    document = _decode(raw)
    try:
        validate_json(document)
        size = serialized_size(document)
    except (ValueError, TypeError, RecursionError):
        raise _bad("The bundle has an unsupported JSON shape or a non-finite number.") from None
    if size > MAX_BUNDLE_BYTES:
        raise _bad(f"The bundle exceeds {MAX_BUNDLE_BYTES} bytes; export or import fewer presets.")
    if not isinstance(document, dict):
        raise _bad("A preset bundle must be a JSON object.")
    if document.get("format") != BUNDLE_FORMAT:
        raise _bad(f"Not a preset bundle: 'format' must be {BUNDLE_FORMAT!r}.")
    version = document.get("format_version")
    if not _is_int(version) or not 0 <= version <= MAX_FORMAT_VERSION:  # type: ignore[operator]
        raise _bad(f"'format_version' must be an integer 0-{MAX_FORMAT_VERSION}.")
    if version not in SUPPORTED_FORMAT_VERSIONS:
        raise _bad(
            f"Unsupported preset bundle format_version {version}; this server reads "
            f"format_version {BUNDLE_FORMAT_VERSION}."
        )
    unknown = sorted(str(key) for key in document if key not in ENVELOPE_KEYS)
    if unknown:
        raise _bad(f"Unknown bundle key {_echo(unknown[0])}.")
    missing = [key for key in ENVELOPE_KEYS if key not in document]
    if missing:
        raise _bad(f"Missing bundle key {missing[0]!r}.")
    created_at = document["created_at"]
    if not isinstance(created_at, str) or not TIMESTAMP_RE.match(created_at):
        raise _bad("'created_at' must be a UTC timestamp YYYY-MM-DDTHH:MM:SSZ.")
    try:
        datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        raise _bad("'created_at' must be a UTC timestamp YYYY-MM-DDTHH:MM:SSZ.") from None
    version_text, led_count, max_segments, matrix = _parse_source(document["source"])
    effects, palettes = _parse_catalog(document["catalog"])
    return Bundle(
        created_at,
        version_text,
        led_count,
        max_segments,
        matrix,
        effects,
        palettes,
        _parse_entries(document["presets"]),
    )


def _exact_keys(value: object, keys: set[str], where: str) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise _bad(f"'{where}' must be an object.")
    extra = sorted(str(key) for key in value if key not in keys)
    if extra:
        raise _bad(f"Unknown key {_echo(extra[0])} in '{where}'.")
    missing = sorted(key for key in keys if key not in value)
    if missing:
        raise _bad(f"Missing key {missing[0]!r} in '{where}'.")
    return value


def _optional_count(value: object, where: str) -> int | None:
    if value is None:
        return None
    if not _is_int(value) or not 0 <= value <= 1_000_000:  # type: ignore[operator]
        raise _bad(f"'{where}' must be null or a non-negative integer.")
    assert isinstance(value, int)
    return value


def _parse_source(value: object) -> tuple[str, int | None, int | None, tuple[int, int] | None]:
    source = _exact_keys(value, {"firmware", "capabilities"}, "source")
    firmware = _exact_keys(source["firmware"], {"version"}, "source.firmware")
    version = firmware["version"]
    if not isinstance(version, str) or not 0 < len(version) <= 128:
        raise _bad("'source.firmware.version' must be a nonempty string.")
    caps = _exact_keys(
        source["capabilities"], {"led_count", "max_segments", "matrix"}, "source.capabilities"
    )
    matrix_raw = caps["matrix"]
    matrix = parse_matrix(matrix_raw)
    if matrix_raw is not None and matrix is None:
        raise _bad("'source.capabilities.matrix' must be null or {w, h} positive integers.")
    return (
        version,
        _optional_count(caps["led_count"], "source.capabilities.led_count"),
        _optional_count(caps["max_segments"], "source.capabilities.max_segments"),
        matrix,
    )


def _parse_names(value: object, where: str) -> dict[int, str]:
    if not isinstance(value, dict):
        raise _bad(f"'{where}' must be an object of ID to name.")
    names: dict[int, str] = {}
    for key, name in value.items():
        if not CANONICAL_ID_RE.match(key) or int(key) > MAX_CATALOG_ID:
            raise _bad(f"'{where}' key {_echo(key)} is not a catalog ID 0-{MAX_CATALOG_ID}.")
        if not isinstance(name, str) or not 0 < len(name) <= MAX_TEXT:
            raise _bad(f"'{where}' names must be nonempty strings.")
        names[int(key)] = name
    return names


def _parse_catalog(value: object) -> tuple[dict[int, str], dict[int, str]]:
    catalog = _exact_keys(value, {"effects", "palettes"}, "catalog")
    return (
        _parse_names(catalog["effects"], "catalog.effects"),
        _parse_names(catalog["palettes"], "catalog.palettes"),
    )


def _parse_entries(value: object) -> tuple[BundleEntry, ...]:
    if not isinstance(value, list):
        raise _bad("'presets' must be a list.")
    if len(value) > MAX_BUNDLE_ENTRIES:
        raise _bad(f"'presets' holds more than {MAX_BUNDLE_ENTRIES} entries.")
    entries: list[BundleEntry] = []
    seen: set[int] = set()
    for index, raw in enumerate(value):
        where = f"presets[{index}]"
        item = _exact_keys(raw, set(ENTRY_KEYS), where)
        source_id = item["source_id"]
        if not _is_int(source_id) or not MIN_PERSISTENT_ID <= source_id <= MAX_PERSISTENT_ID:  # type: ignore[operator]
            raise _bad(f"'{where}.source_id' must be an integer 1-250.")
        assert isinstance(source_id, int)
        if source_id in seen:
            raise _bad(f"'{where}.source_id' {source_id} appears more than once.")
        seen.add(source_id)
        kind = item["type"]
        if kind not in ENTRY_TYPES:
            raise _bad(f"'{where}.type' must be one of {list(ENTRY_TYPES)}.")
        preset = item["preset"]
        if classify(preset)[0] != kind:
            raise _bad(
                f"'{where}.type' {kind!r} does not match the preset object, which is "
                f"{classify(preset)[0]!r}; a playlist is never treated as a state preset."
            )
        name = item["name"]
        if name is not None and not isinstance(name, str):
            raise _bad(f"'{where}.name' must be a string or null.")
        if name != entry_name(preset):
            raise _bad(f"'{where}.name' differs from the preset object's name.")
        assert isinstance(kind, str)
        entries.append(BundleEntry(source_id, name, kind, preset))
    return tuple(entries)


# -------------------------------------------------------------------------- export


def segments_of(preset: JsonValue) -> list[dict[str, JsonValue]] | None:
    """Segment objects of a state entry (a single object counts as one); None if malformed."""
    if not isinstance(preset, dict):
        return None
    seg = preset.get("seg")
    if seg is None:
        return []
    if isinstance(seg, dict):
        return [seg]
    if isinstance(seg, list) and all(isinstance(item, dict) for item in seg):
        return [item for item in seg if isinstance(item, dict)]
    return None


def referenced_catalog_ids(entries: list[BundleEntry]) -> tuple[set[int], set[int]]:
    effects: set[int] = set()
    palettes: set[int] = set()
    for entry in entries:
        if entry.type != "state":
            continue
        for segment in segments_of(entry.preset) or []:
            fx, pal = segment.get("fx"), segment.get("pal")
            if _is_int(fx):
                assert isinstance(fx, int)
                effects.add(fx)
            if _is_int(pal):
                assert isinstance(pal, int)
                palettes.add(pal)
    return effects, palettes


def build_bundle(
    created_at: str,
    firmware_version: str,
    led_count: int | None,
    max_segments: int | None,
    matrix: tuple[int, int] | None,
    effects: dict[int, str],
    palettes: dict[int, str],
    entries: list[BundleEntry],
) -> dict[str, JsonValue]:
    """The format-1 envelope; preset objects are carried verbatim."""
    return {
        "format": BUNDLE_FORMAT,
        "format_version": BUNDLE_FORMAT_VERSION,
        "created_at": created_at,
        "source": {
            "firmware": {"version": firmware_version},
            "capabilities": {
                "led_count": led_count,
                "max_segments": max_segments,
                "matrix": None if matrix is None else {"w": matrix[0], "h": matrix[1]},
            },
        },
        "catalog": {
            "effects": {str(key): effects[key] for key in sorted(effects)},
            "palettes": {str(key): palettes[key] for key in sorted(palettes)},
        },
        "presets": [
            {
                "source_id": entry.source_id,
                "name": entry.name,
                "type": entry.type,
                "preset": copy.deepcopy(entry.preset),
            }
            for entry in entries
        ],
    }


def address_tokens(base_url: str, info: dict[str, JsonValue]) -> list[str]:
    """Device addresses that must never appear in an export (case-insensitive)."""
    tokens: list[str] = []
    host = urlsplit(base_url).hostname
    if host:
        tokens.append(host)
    for key in ("ip", "mac"):
        value = info.get(key)
        if isinstance(value, str):
            tokens.append(value)
    mac = info.get("mac")
    if isinstance(mac, str) and len(mac) == 12:
        tokens.append(":".join(mac[i : i + 2] for i in range(0, 12, 2)))
    wifi = info.get("wifi")
    bssid = wifi.get("bssid") if isinstance(wifi, dict) else None
    if isinstance(bssid, str):
        tokens.append(bssid)
        tokens.append(bssid.replace(":", ""))
    return sorted({token.casefold() for token in tokens if len(token) >= 4})


def _strings(value: object) -> list[str]:
    found: list[str] = []
    stack: list[object] = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            found.append(item)
        elif isinstance(item, list):
            stack.extend(item)
        elif isinstance(item, dict):
            stack.extend(item.keys())
            stack.extend(item.values())
    return found


def leaking_entries(entries: list[BundleEntry], tokens: list[str]) -> list[int]:
    """Source IDs whose preset text contains a device address (IDs only, never text)."""
    leaking: list[int] = []
    for entry in entries:
        texts = [text.casefold() for text in _strings(entry.preset)]
        if any(token in text for token in tokens for text in texts):
            leaking.append(entry.source_id)
    return leaking


# ------------------------------------------------------------------ import planning


@dataclass(frozen=True)
class Target:
    """Facts of the import target read inside the device lock."""

    store: PresetStore
    firmware_version: str
    led_count: int | None
    max_segments: int | None
    matrix: tuple[int, int] | None
    cct: bool | None
    effects: tuple[str, ...] | None
    palettes: tuple[str, ...] | None
    before: dict[str, JsonValue]


@dataclass(frozen=True)
class Finding:
    code: ErrorCode
    message: str


@dataclass
class PlannedEntry:
    source: BundleEntry
    destination: int | None = None
    allocated: bool = False
    existing: dict[str, JsonValue] | None = None
    existing_type: str | None = None
    route: Route | None = None
    entry: dict[str, JsonValue] | None = None
    members: list[int] = field(default_factory=list)
    member_map: dict[str, JsonValue] = field(default_factory=dict)
    mappings: list[JsonValue] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    position: int | None = None

    def block(self, code: ErrorCode, message: str) -> None:
        self.findings.append(Finding(code, message))

    def preview(self) -> dict[str, JsonValue]:
        return {
            "source_id": self.source.source_id,
            "name": self.source.name,
            "type": self.source.type,
            "destination_id": self.destination,
            "allocated": self.allocated,
            "occupied": self.existing is not None or self.existing_type is not None,
            "existing_type": self.existing_type,
            "overwrite": self.existing is not None,
            "route": self.route,
            "live_effect": None if self.route is None else live_effect(self.route),
            "write_position": self.position,
            "member_map": dict(self.member_map),
            "catalog_mappings": list(self.mappings),
            "blocking": [finding.message for finding in self.findings],
            "warnings": list(self.warnings),
        }


@dataclass
class ImportPlan:
    entries: list[PlannedEntry]
    findings: list[Finding]
    required_mappings: list[JsonValue]
    warnings: list[str]

    @property
    def blocked(self) -> bool:
        return bool(self.findings) or any(entry.findings for entry in self.entries)

    def first_finding(self) -> Finding | None:
        if self.findings:
            return self.findings[0]
        for entry in self.entries:
            if entry.findings:
                return entry.findings[0]
        return None

    def all_warnings(self) -> list[str]:
        """Plan warnings, then each entry's warnings prefixed with its source ID."""
        return [
            *self.warnings,
            *(
                f"Entry {entry.source.source_id}: {warning}"
                for entry in self.entries
                for warning in entry.warnings
            ),
        ]

    def write_order(self) -> list[PlannedEntry]:
        ordered = [entry for entry in self.entries if entry.position is not None]
        return sorted(ordered, key=lambda entry: entry.position or 0)


@dataclass(frozen=True)
class Mappings:
    """Caller-supplied explicit mappings (all keys are source IDs)."""

    ids: dict[int, int]
    effects: dict[int, int]
    palettes: dict[int, int]
    overwrite: frozenset[int]


def _catalog_proposal(names: tuple[str, ...], wanted: str) -> int | None:
    for matches in (
        [index for index, name in enumerate(names) if name == wanted],
        [
            index
            for index, name in enumerate(names)
            if name.strip().casefold() == wanted.strip().casefold()
        ],
    ):
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            return None
    return None


def _map_catalog(
    kind: CatalogKind,
    source_id: int,
    source_names: dict[int, str],
    target_names: tuple[str, ...] | None,
    explicit: dict[int, int],
    planned: PlannedEntry,
    required: dict[tuple[str, int], dict[str, JsonValue]],
) -> int | None:
    """Target ID for one source effect/palette ID, or None (a finding is recorded)."""
    label = f"{kind}_map"
    source_name = source_names.get(source_id)
    if target_names is None:
        planned.block(
            "UNSUPPORTED_CAPABILITY",
            f"The target {kind} catalog could not be read; {kind} {source_id} cannot be checked.",
        )
        return None
    if source_id in explicit:
        target_id = explicit[source_id]
        if target_id >= len(target_names):
            planned.block(
                "VALIDATION_ERROR",
                f"{label} maps {kind} {source_id} to {target_id}, outside the target catalog "
                f"(0-{len(target_names) - 1}).",
            )
            return None
        planned.mappings.append(
            {
                "kind": kind,
                "source_id": source_id,
                "source_name": source_name,
                "target_id": target_id,
                "target_name": target_names[target_id],
                "basis": "explicit",
            }
        )
        return target_id
    if source_name is None:
        planned.block(
            "UNSUPPORTED_CAPABILITY",
            f"The bundle does not name {kind} {source_id}, so its identity on the target "
            f"cannot be checked; map it explicitly in {label}.",
        )
        required.setdefault((kind, source_id), {"kind": kind, "source_id": source_id})
        return None
    if source_id < len(target_names) and target_names[source_id] == source_name:
        return source_id
    proposal = _catalog_proposal(target_names, source_name)
    record: dict[str, JsonValue] = {
        "kind": kind,
        "source_id": source_id,
        "source_name": source_name,
        "proposed_target_id": proposal,
        "proposed_target_name": None if proposal is None else target_names[proposal],
    }
    required.setdefault((kind, source_id), record)
    hint = (
        f'accept the unique name match with {label} {{"{source_id}": {proposal}}}'
        if proposal is not None
        else f"no unique name match exists; choose a target ID in {label}"
    )
    planned.block(
        "UNSUPPORTED_CAPABILITY",
        f"{kind.capitalize()} {source_id} is named differently on the target; {hint}.",
    )
    return None


def _plan_state(
    planned: PlannedEntry,
    bundle: Bundle,
    target: Target,
    mappings: Mappings,
    required: dict[tuple[str, int], dict[str, JsonValue]],
) -> None:
    preset = copy.deepcopy(planned.source.preset)
    assert isinstance(preset, dict)
    segments = segments_of(preset)
    if segments is None:
        planned.block("UNSUPPORTED_CAPABILITY", "The entry's 'seg' value is not recognizable.")
        return
    active = [segment for segment in segments if _is_int(segment.get("id"))]
    if active and (target.led_count is None or target.max_segments is None):
        planned.block(
            "UNSUPPORTED_CAPABILITY",
            "The target's LED count or segment maximum is unknown; the segments cannot be checked.",
        )
    if target.max_segments is not None and len(active) > target.max_segments:
        planned.block(
            "UNSUPPORTED_CAPABILITY",
            f"The entry has {len(active)} segments; the target allows {target.max_segments}.",
        )
    two_d = False
    for segment in segments:
        identifier = segment.get("id")
        stop = segment.get("stop")
        label = f"Segment {identifier}" if _is_int(identifier) else "A segment"
        if (
            _is_int(identifier)
            and target.max_segments is not None
            and identifier >= target.max_segments  # type: ignore[operator]
        ):
            planned.block(
                "UNSUPPORTED_CAPABILITY",
                f"{label}: ID is not below the target maximum {target.max_segments}.",
            )
        if _is_int(stop) and target.led_count is not None and stop > target.led_count:  # type: ignore[operator]
            planned.block(
                "UNSUPPORTED_CAPABILITY",
                f"{label}: stop {stop} exceeds the target LED count {target.led_count}; "
                "nothing is rescaled, edit the bundle.",
            )
        if "startY" in segment or "stopY" in segment:
            two_d = True
        if "cct" in segment and target.cct is not True:
            message = (
                "The entry carries 'cct', but the target reports no CCT capability; it is "
                "written verbatim."
            )
            if message not in planned.warnings:
                planned.warnings.append(message)
        for key, kind, names, explicit, available in (
            ("fx", "effect", bundle.effects, mappings.effects, target.effects),
            ("pal", "palette", bundle.palettes, mappings.palettes, target.palettes),
        ):
            value = segment.get(key)
            if not _is_int(value):
                continue
            assert isinstance(value, int)
            mapped = _map_catalog(
                kind,  # type: ignore[arg-type]
                value,
                names,
                available,
                explicit,
                planned,
                required,
            )
            if mapped is not None and mapped != value:
                segment[key] = mapped
    if two_d and (bundle.matrix is None or target.matrix is None or bundle.matrix != target.matrix):
        planned.block(
            "UNSUPPORTED_CAPABILITY",
            "The entry has 2D segment geometry (startY/stopY), and the source and target "
            "matrix sizes are not both reported and equal; no matrix conversion is done.",
        )
    if "ledmap" in preset:
        planned.warnings.append(
            "The entry selects a ledmap, a file on the device that is not part of the bundle."
        )
    planned.route = "state"
    planned.entry = preset


def _plan_playlist(
    planned: PlannedEntry,
    target: Target,
    by_source: dict[int, PlannedEntry],
    mappings: Mappings,
    state_destinations: set[int],
) -> None:
    preset = copy.deepcopy(planned.source.preset)
    assert isinstance(preset, dict)
    playlist = preset.get("playlist")
    assert isinstance(playlist, dict)

    def resolve(member: int) -> int | None:
        source = by_source.get(member)
        if source is not None:
            if source.source.type != "state" or source.destination is None:
                planned.block(
                    "UNSUPPORTED_CAPABILITY",
                    f"Member {member} is a '{source.source.type}' entry of the bundle; "
                    "members must be state presets.",
                )
                return None
            return source.destination
        if member in mappings.ids:
            destination = mappings.ids[member]
            current = target.store.entries.get(destination)
            if destination in state_destinations or (
                current is not None and classify(current)[0] == "state"
            ):
                return destination
            planned.block(
                "UNSUPPORTED_CAPABILITY",
                f"Member {member} is mapped to {destination}, which is not an existing state "
                "preset on the target.",
            )
            return None
        planned.block(
            "UNSUPPORTED_CAPABILITY",
            f"Member {member} is neither in the bundle nor mapped in id_map to an existing "
            "state preset on the target.",
        )
        return None

    members = playlist.get("ps")
    assert isinstance(members, list)
    rewritten: list[JsonValue] = []
    for member in members:
        assert isinstance(member, int)
        destination = resolve(member)
        planned.member_map[str(member)] = destination
        rewritten.append(destination if destination is not None else member)
    playlist["ps"] = rewritten
    end = playlist.get("end")
    if _is_int(end) and MIN_PERSISTENT_ID <= end <= MAX_PERSISTENT_ID:  # type: ignore[operator]
        assert isinstance(end, int)
        destination = resolve(end)
        planned.member_map[f"end:{end}"] = destination
        if destination is not None:
            playlist["end"] = destination
    try:
        members_out = check_playlist_entry(preset)
    except ClientFailure as failure:
        planned.block(failure.error.code, failure.error.message)
        members_out = []
    if planned.destination is not None and planned.destination in members_out:
        planned.block(
            "UNSUPPORTED_CAPABILITY",
            "The playlist would reference its own destination ID.",
        )
    try:
        refuse_running_playlist(target.before)
    except ClientFailure as failure:
        planned.block(failure.error.code, failure.error.message)
    planned.members = members_out
    planned.route = "playlist"
    planned.entry = preset


def plan_import(bundle: Bundle, target: Target, mappings: Mappings) -> ImportPlan:
    """Complete, deterministic import plan; findings block the whole import."""
    store = target.store
    findings: list[Finding] = []
    warnings: list[str] = []
    planned = [PlannedEntry(source=entry) for entry in bundle.entries]
    by_source = {entry.source.source_id: entry for entry in planned}
    if len(planned) > MAX_IMPORT_ENTRIES:
        findings.append(
            Finding(
                "VALIDATION_ERROR",
                f"The bundle holds {len(planned)} entries; at most {MAX_IMPORT_ENTRIES} are "
                "imported per call. Split the bundle.",
            )
        )
    playlists = [entry for entry in planned if entry.source.type == "playlist"]
    if len(playlists) > 1:
        findings.append(
            Finding(
                "VALIDATION_ERROR",
                f"The bundle holds {len(playlists)} playlists; saving a playlist starts it and "
                "a second save is refused while one runs, so import one playlist per call.",
            )
        )
    if bundle.firmware_version != target.firmware_version:
        warnings.append(
            f"The bundle was exported from firmware {bundle.firmware_version!r}; the target "
            f"reports {target.firmware_version!r}. Nothing is converted."
        )
    # Destinations: id_map first, then the lowest free ID in bundle order.
    explicit = {
        entry.source.source_id: mappings.ids[entry.source.source_id]
        for entry in planned
        if entry.source.type in WRITABLE_TYPES and entry.source.source_id in mappings.ids
    }
    duplicates = sorted(
        {dest for dest in explicit.values() if list(explicit.values()).count(dest) > 1}
    )
    if duplicates:
        findings.append(
            Finding("VALIDATION_ERROR", f"id_map assigns destination(s) {duplicates} twice.")
        )
    taken = set(store.entries) | set(explicit.values())
    for entry in planned:
        if entry.source.type not in WRITABLE_TYPES:
            entry.block(
                "UNSUPPORTED_CAPABILITY",
                f"A '{entry.source.type}' entry is never imported; remove it from the bundle.",
            )
            continue
        source_id = entry.source.source_id
        if source_id in explicit:
            entry.destination = explicit[source_id]
            continue
        free = next(
            (i for i in range(MIN_PERSISTENT_ID, MAX_PERSISTENT_ID + 1) if i not in taken), None
        )
        if free is None:
            entry.block("PRESET_CONFLICT", "No free persistent preset ID (1-250) is left.")
            continue
        entry.destination, entry.allocated = free, True
        taken.add(free)
    destinations = {entry.destination for entry in planned if entry.destination is not None}
    unused = sorted(mappings.overwrite - destinations)
    if unused:
        findings.append(
            Finding(
                "VALIDATION_ERROR",
                f"overwrite_ids {unused[:20]} are not destinations of this import.",
            )
        )
    referenced = {member for entry in playlists for member in playlist_members(entry.source.preset)}
    stale = sorted(set(mappings.ids) - set(by_source) - referenced)
    if stale:
        findings.append(
            Finding(
                "VALIDATION_ERROR",
                f"id_map keys {stale[:20]} are neither bundle entries nor playlist members.",
            )
        )
    active_preset = target.before.get("active_preset_id")
    for entry in planned:
        destination = entry.destination
        if destination is None:
            continue
        if destination == active_preset:
            entry.warnings.append(
                f"Destination {destination} is the active preset marker (state.ps); it is replaced."
            )
        current = store.entries.get(destination)
        if current is None:
            continue
        kind, malformed = classify(current)
        entry.existing_type = kind
        if destination not in mappings.overwrite:
            entry.block(
                "PRESET_CONFLICT",
                f"Destination {destination} holds a '{kind}' entry; add {destination} to "
                "overwrite_ids to replace it (a snapshot is taken first).",
            )
        if malformed or not isinstance(current, dict):
            entry.block(
                "VALIDATION_ERROR",
                f"Destination {destination} is not a JSON object and cannot be snapshotted.",
            )
            continue
        entry.existing = current
        if kind != entry.source.type:
            entry.warnings.append(
                f"The existing '{kind}' entry is replaced by a {entry.source.type} entry."
            )
        users = [i for i in referencing_playlists(store, destination) if i not in destinations]
        if users:
            entry.warnings.append(
                f"Playlist(s) {users[:20]} reference destination {destination}; they are not "
                "edited and will use the new entry."
            )
    if store.malformed_keys:
        findings.append(
            Finding(
                "INVALID_RESPONSE",
                "The target preset store contains unrecognized keys; no import is planned.",
            )
        )
    required: dict[tuple[str, int], dict[str, JsonValue]] = {}
    state_destinations = {
        entry.destination
        for entry in planned
        if entry.source.type == "state" and entry.destination is not None
    }
    for entry in planned:
        if entry.destination is None:
            continue
        if entry.source.type == "state":
            _plan_state(entry, bundle, target, mappings, required)
    for entry in planned:
        if entry.destination is not None and entry.source.type == "playlist":
            _plan_playlist(entry, target, by_source, mappings, state_destinations)
    # Members before the playlists that reference them: states in bundle order, then lists.
    position = 0
    for kind in ("state", "playlist"):
        for entry in planned:
            if entry.destination is not None and entry.source.type == kind:
                entry.position = position
                position += 1
    active = target.before.get("active_playlist_id")
    if isinstance(active, int) and not playlists:
        warnings.append(
            f"Playlist {active} is running; each state entry is applied to the lights as it "
            "is written and may interrupt it."
        )
    return ImportPlan(planned, findings, list(required.values()), warnings)


def parse_id_keys(raw: dict[str, int] | None, lower: int, upper: int, label: str) -> dict[int, int]:
    """Map keys are decimal IDs (JSON object keys are strings)."""
    result: dict[int, int] = {}
    for key, value in (raw or {}).items():
        if not CANONICAL_ID_RE.match(key) or not lower <= int(key) <= upper:
            raise ValueError(f"{label} keys must be decimal IDs {lower}-{upper}")
        result[int(key)] = value
    return result
