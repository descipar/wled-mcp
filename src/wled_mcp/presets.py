"""Pure persistent-preset logic (issue #9): requests, store parsing, classification,
allocation, capture comparison and interference detection. No network and no I/O.

Source facts (pinned v0.15.1, see docs/SOURCES.md "Issue-9 preset evidence"):
persistent IDs are 1-250, ``/presets.json`` keys the entries by decimal ID and keeps a
``"0"`` initializer, a deleted entry is removed from the file, a saved state entry is
serialized by ``serializeState(forPreset=true)`` and a saved name is cut at 32 bytes.
WLED v16.0.1 (docs/SOURCES.md "Issue-66 WLED 16 preset evidence") additionally emits the
top-level light-state key ``bs`` (blending style) in saved state presets and live state.
"""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from typing import Annotated, Any, Final

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from wled_mcp.client import ClientFailure

MIN_PERSISTENT_ID: Final = 1
MAX_PERSISTENT_ID: Final = 250
NAME_MAX_BYTES: Final = 32
MAX_DIFFERENCES: Final = 20
MAX_LISTED_IDS: Final = 20
KEY_NAME_MAX: Final = 32

# Keys that make a stored entry do more than set light state when it is applied
# (deserializeState in json.cpp). An entry containing one is never a plain state preset.
CONTROL_KEYS: Final = frozenset(
    {"psave", "pdel", "ps", "pd", "rb", "win", "playlist", "live", "time", "bootps"}
)
# A plain state preset carries only what serializeState/doSaveState emit for a save
# (json.cpp, presets.cpp at v0.15.1 and v16.0.1). Any other top-level key (rmcpal, wifi,
# np, nl, lor, udpn, ...) is acted on by deserializeState beyond light state, so the
# entry is `unknown`. ``bs`` (v16.0.1 blending style) only selects the transition style
# used by rendering, like ``transition`` (ISSUE-66-DEC-001).
STATE_ALLOWED_KEYS: Final = frozenset(
    {"on", "bri", "transition", "bs", "mainseg", "seg", "n", "ql", "ledmap"}
)
# At least one of these is needed so activation can be observed and verified
# (``bs`` or ``transition`` alone is not observable).
STATE_REQUIRED_ANY: Final = frozenset({"on", "bri", "seg"})
END_RESTORE_ID: Final = 255

# Compared on save only when present in the live state (capture_reference), so ``bs`` is
# not expected from firmware whose live state lacks it.
MASTER_KEYS: Final = ("on", "bri", "transition", "bs", "mainseg")
SEGMENT_KEYS: Final = (
    "start",
    "stop",
    "on",
    "bri",
    "col",
    "fx",
    "sx",
    "ix",
    "pal",
    "grp",
    "spc",
    "of",
    "rev",
    "mi",
    "sel",
)

PresetId = Annotated[int, Field(strict=True, ge=MIN_PERSISTENT_ID, le=MAX_PERSISTENT_ID)]
DeviceId = Annotated[str, Field(min_length=1, max_length=64)]


def validate_preset_name(name: str) -> str:
    """Never trims or truncates: a name is stored exactly as given or rejected."""
    if not name.strip():
        raise ValueError("Preset name must not be blank")
    if any(unicodedata.category(char) == "Cc" for char in name):
        raise ValueError("Preset name must not contain control characters")
    try:
        encoded = name.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("Preset name must be valid Unicode text") from None
    if len(encoded) > NAME_MAX_BYTES:
        raise ValueError("Preset name exceeds 32 UTF-8 bytes")
    return name


class ListPresetsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    device_id: DeviceId


class GetPresetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    device_id: DeviceId
    preset_id: PresetId


class ActivatePresetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    device_id: DeviceId
    preset_id: PresetId
    dry_run: bool = False


class SavePresetRequest(BaseModel):
    """Save the current live state; there is deliberately no supplied-state input."""

    model_config = ConfigDict(extra="forbid", strict=True)
    device_id: DeviceId
    name: str
    preset_id: PresetId | None = None
    overwrite: bool = False
    dry_run: bool = False

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        return validate_preset_name(value)

    @model_validator(mode="after")
    def overwrite_needs_explicit_id(self) -> SavePresetRequest:
        if self.overwrite and self.preset_id is None:
            raise ValueError("overwrite=true requires an explicit preset_id")
        return self


class DeletePresetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    device_id: DeviceId
    preset_id: PresetId
    dry_run: bool = False


# ---------------------------------------------------------------- store parsing


def json_equal(left: object, right: object) -> bool:
    """Structural JSON equality that does not equate ``true`` with ``1``."""
    return json.dumps(left, sort_keys=True, ensure_ascii=True) == json.dumps(
        right, sort_keys=True, ensure_ascii=True
    )


def _canonical_id(key: str) -> int | None:
    if not key.isascii() or not key.isdigit() or str(int(key)) != key:
        return None
    value = int(key)
    return value if 0 <= value <= 255 else None


@dataclass(frozen=True)
class PresetStore:
    """Occupied persistent entries (IDs 1-250) of one ``/presets.json`` reading."""

    entries: dict[int, JsonValue]
    malformed_keys: int = 0

    def require_wellformed(self) -> None:
        """Planning a write over an unrecognizable store is never attempted."""
        if self.malformed_keys:
            raise ClientFailure(
                "INVALID_RESPONSE",
                "The device preset store contains unrecognized keys; no write was planned.",
                reconciliation="Inspect the preset store before any explicitly requested attempt.",
            )


def parse_store(raw: dict[str, JsonValue]) -> PresetStore:
    entries: dict[int, JsonValue] = {}
    malformed = 0
    for key, value in raw.items():
        identifier = _canonical_id(key)
        if identifier is None:
            malformed += 1
            continue
        if not MIN_PERSISTENT_ID <= identifier <= MAX_PERSISTENT_ID:
            continue  # 0 is the file initializer; 251-255 are not persistent targets
        if value is None or (isinstance(value, dict) and not value):
            continue  # null and {} mean absent (a deleted slot)
        entries[identifier] = value
    return PresetStore(dict(sorted(entries.items())), malformed)


def lowest_free(store: PresetStore) -> int | None:
    for identifier in range(MIN_PERSISTENT_ID, MAX_PERSISTENT_ID + 1):
        if identifier not in store.entries:
            return identifier
    return None


# ------------------------------------------------------------- classification


def playlist_ids(playlist: object) -> list[int] | None:
    """Referenced preset IDs of a playlist object, or None when it is not recognizable."""
    if not isinstance(playlist, dict):
        return None
    ids = playlist.get("ps")
    if not isinstance(ids, list) or not ids:
        return None
    if not all(
        type(item) is int and MIN_PERSISTENT_ID <= item <= MAX_PERSISTENT_ID for item in ids
    ):
        return None
    return [item for item in ids if isinstance(item, int)]


def classify(entry: JsonValue) -> tuple[str, bool]:
    """Return (type, malformed) from positive evidence only.

    Types: ``state | playlist | api-command | unknown``. A non-object entry is
    ``unknown`` and malformed (occupied, but it cannot be snapshotted).
    """
    if not isinstance(entry, dict):
        return "unknown", True
    if isinstance(entry.get("win"), str):
        return "api-command", False
    if (
        playlist_ids(entry.get("playlist")) is not None
        and not (CONTROL_KEYS - {"playlist"}) & entry.keys()
    ):
        return "playlist", False
    if entry.keys() <= STATE_ALLOWED_KEYS and STATE_REQUIRED_ANY & entry.keys():
        return "state", False
    return "unknown", False


def unexpected_state_keys(entry: JsonValue) -> list[str]:
    """Sorted top-level key names outside the plain-state allowlist (names only)."""
    if not isinstance(entry, dict):
        return []
    keys = sorted(str(key)[:KEY_NAME_MAX] for key in entry.keys() - STATE_ALLOWED_KEYS)
    return keys[:MAX_DIFFERENCES]


def entry_name(entry: JsonValue) -> str | None:
    if isinstance(entry, dict):
        name = entry.get("n")
        if isinstance(name, str):
            return name
    return None


def playlist_members(entry: JsonValue) -> list[int]:
    """Presets a playlist applies: its ``ps`` list plus a persistent ``end`` preset."""
    if not isinstance(entry, dict):
        return []
    members = playlist_ids(entry.get("playlist")) or []
    end = playlist_end(entry)
    if end is not None and MIN_PERSISTENT_ID <= end <= MAX_PERSISTENT_ID:
        members.append(end)
    return members


def playlist_end(entry: JsonValue) -> int | None:
    playlist = entry.get("playlist") if isinstance(entry, dict) else None
    end = playlist.get("end") if isinstance(playlist, dict) else None
    return end if type(end) is int else None


def playlist_end_unsafe(entry: JsonValue) -> bool:
    """True when the firmware's use of ``end`` cannot be checked.

    The firmware stores ``end`` in a byte (low 8 bits) before its >250 check, so an
    integer outside 0-255 wraps onto another preset or onto 255; 255 restores whatever
    preset ran before. Both are refused. 251-254 and non-integers resolve to no end.
    """
    end = playlist_end(entry)
    return end is not None and (end == END_RESTORE_ID or not 0 <= end <= END_RESTORE_ID)


def unsafe_playlist_members(store: PresetStore, members: list[int]) -> list[int]:
    """Referenced IDs that are missing or not plain state presets (sorted, unique)."""
    bad = {
        member
        for member in members
        if member not in store.entries or classify(store.entries[member])[0] != "state"
    }
    return sorted(bad)


def referencing_playlists(store: PresetStore, preset_id: int) -> list[int]:
    return [
        identifier
        for identifier, entry in store.entries.items()
        if identifier != preset_id
        and classify(entry)[0] == "playlist"
        and preset_id in playlist_members(entry)
    ]


def interference(before: PresetStore, after: PresetStore, target: int) -> list[int]:
    """IDs other than the target whose occupancy or content differs between readings."""
    changed = []
    for identifier in sorted(set(before.entries) | set(after.entries)):
        if identifier == target:
            continue
        if identifier not in before.entries or identifier not in after.entries:
            changed.append(identifier)
        elif not json_equal(before.entries[identifier], after.entries[identifier]):
            changed.append(identifier)
    return changed


# ------------------------------------------------------------ capture matching


@dataclass(frozen=True)
class CaptureReference:
    """Live fields read just before the save, the expectation for the stored entry."""

    master: dict[str, JsonValue]
    segments: dict[int, dict[str, JsonValue]]

    def summary(self) -> dict[str, JsonValue]:
        return {
            "master_fields": list(self.master),
            "segment_ids": list(self.segments),
        }


def capture_reference(state: dict[str, JsonValue]) -> CaptureReference:
    master = {key: state[key] for key in MASTER_KEYS if key in state}
    segments: dict[int, dict[str, JsonValue]] = {}
    raw_segments = state.get("seg")
    for segment in raw_segments if isinstance(raw_segments, list) else []:
        if not isinstance(segment, dict):
            continue
        identifier = segment.get("id")
        if type(identifier) is not int:
            continue
        fields: dict[str, JsonValue] = {key: segment[key] for key in SEGMENT_KEYS if key in segment}
        name = segment.get("n")
        fields["n"] = name if isinstance(name, str) else ""
        segments[identifier] = fields
    return CaptureReference(master, segments)


_MISSING: Any = object()


def _same(actual: object, expected: object) -> bool:
    return actual is not _MISSING and json_equal(actual, expected)


def compare_capture(entry: JsonValue, name: str, reference: CaptureReference) -> list[str]:
    """Names of fields where the stored entry differs from the pre-dispatch capture.

    Field names only, never values; capture is asynchronous so any difference counts.
    """
    if not isinstance(entry, dict):
        return ["entry"]
    differences: list[str] = []
    if entry.get("n") != name:
        differences.append("n")
    for key, expected in reference.master.items():
        if not _same(entry.get(key, _MISSING), expected):
            differences.append(key)
    stored = entry.get("seg")
    if not isinstance(stored, list):
        differences.append("seg")
        return differences[:MAX_DIFFERENCES]
    # Inactive slots are stored as {"stop": 0} markers without an ID; only real
    # segments (with an ID) are compared.
    active = {
        item["id"]: item
        for item in stored
        if isinstance(item, dict) and type(item.get("id")) is int
    }
    if set(active) != set(reference.segments):
        differences.append("seg.ids")
    for identifier, expected_fields in reference.segments.items():
        got = active.get(identifier)
        if got is None:
            continue
        for key, expected in expected_fields.items():
            default: Any = "" if key == "n" else _MISSING
            if not _same(got.get(key, default), expected):
                differences.append(f"seg[{identifier}].{key}")
    return differences[:MAX_DIFFERENCES]
