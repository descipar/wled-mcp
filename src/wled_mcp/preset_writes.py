"""Single-entry preset writes (issue #18): supplied-state validation, the state and
playlist write routes, destination planning and readback verdicts. No network I/O.

Write route (ISSUE-18-DEC-001, docs/SOURCES.md "Issue-18 WLED 16 preset write
evidence", WLED v16.0.1): a JSON API POST with ``psave``, a non-null ``o`` and no
``playlist`` key is applied to the lights by ``deserializeState`` and then written
verbatim, minus the keys ``o``, ``v``, ``time``, ``error``, ``psave`` and ``bootps``
(state route). A POST with ``playlist``, ``o`` and ``psave`` starts the playlist and
stores it re-serialized from runtime data (playlist route). Neither route can store
without a live effect, and nothing here restores the previous lighting.

Every write targets one ID, is planned inside the device lock, takes a snapshot of an
occupied destination first, rechecks the destination, sends one POST through
``Resources.write_polled`` and is decided by ``/presets.json`` readback only.

WLED 16 segment fields (issue #19, ISSUE-19-DEC-003 TD-19-12): a supplied segment may
carry ``cct``, ``c1``-``c3``, ``o1``-``o3``, ``si``, ``set``, ``m12``, ``frz``, ``bm``,
``startY``/``stopY`` and ``rY``/``mY``/``tp`` with the bounds and the capability,
field-presence and matrix rules of the segment tools (``segment_rules``); overlap stays
rejected here (ISSUE-19-DEC-001 covers only the two segment tools).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from wled_mcp.backups import Firmware
from wled_mcp.capabilities import DeviceCapabilities, derive_capabilities
from wled_mcp.client import ClientFailure
from wled_mcp.presets import (
    MAX_DIFFERENCES,
    MAX_PERSISTENT_ID,
    MIN_PERSISTENT_ID,
    NAME_MAX_BYTES,
    PresetStore,
    classify,
    interference,
    json_equal,
    lowest_free,
    parse_store,
    playlist_ids,
    referencing_playlists,
    unsafe_playlist_members,
)
from wled_mcp.readmodels import as_dict
from wled_mcp.resources import OperationContext, Verdict
from wled_mcp.segment_rules import (
    BLEND_MODE_MAX,
    CCT_MAX,
    CUSTOM3_MAX,
    CUSTOM_MAX,
    GROUPING_MAX,
    MAP_1D_2D_MAX,
    SEGMENT_SET_MAX,
    SOUND_SIMULATION_MAX,
    SPACING_MAX,
    Geometry,
    Rect,
    check_cct,
    check_fields,
    check_segment_name,
    check_y_pair,
    colors_for_bits,
    option_keys,
    overlapping_pairs,
)

Route = Literal["state", "playlist"]

# Keys the firmware removes from the request document before it stores it verbatim.
# Only o and psave are ever sent: the supplied-state schema and the state classification
# of a restored snapshot exclude v, time, error and bootps (bootps would also change the
# boot preset configuration). They are listed so the comparison follows the firmware.
FIRMWARE_REMOVED_KEYS: Final = frozenset({"o", "v", "time", "error", "psave", "bootps"})
# Top-level keys a supplied state object may carry (a subset of STATE_ALLOWED_KEYS).
SUPPLIED_STATE_KEYS: Final = ("on", "bri", "transition", "bs", "mainseg", "seg")
# Keys that survive the firmware's playlist re-serialization; anything else is dropped.
PLAYLIST_ENTRY_KEYS: Final = frozenset({"playlist", "n", "on", "ql"})
PLAYLIST_KEYS: Final = frozenset({"ps", "dur", "transition", "repeat", "end", "r"})
MAX_PLAYLIST_ENTRIES: Final = 100
MAX_PLAYLIST_DURATION: Final = 42_949_670  # tenths of a second (v16.0.1 playlist.cpp)
MAX_TRANSITION: Final = 65_535  # playlist transition, tenths of a second (uint16 entry)
# Master transition: the firmware keeps transitionDelay = tenths * 100 in a uint16_t
# (wled.h), so more than 655 tenths would wrap.
MAX_STATE_TRANSITION: Final = 655
# The firmware masks the blending style with 0x1F (json.cpp, ISSUE-66 evidence).
MAX_BLENDING_STYLE: Final = 31
MAX_PLAYLIST_REPEAT: Final = 254  # stored as repeat + 1 in a byte (v16.0.1 playlist.cpp)
DEFAULT_PLAYLIST_DURATION: Final = 100
QUICK_LOAD_MAX_BYTES: Final = 8

STATE_LIVE_EFFECT: Final = (
    "Applies the supplied state to the lights, then stores it. The lighting before the "
    "write is not restored."
)
PLAYLIST_LIVE_EFFECT: Final = (
    "Starts the playlist, then stores it. The lighting before the write is not restored."
)
WRITE_RECONCILE: Final = (
    "Read the preset with wled_get_preset and the state with wled_get_state before any "
    "new attempt; do not replay the write."
)


def _fail(message: str) -> ClientFailure:
    return ClientFailure(
        "VALIDATION_ERROR", message, reconciliation="Correct the request; nothing was written."
    )


def _unsupported(message: str, reconciliation: str) -> ClientFailure:
    return ClientFailure("UNSUPPORTED_CAPABILITY", message, reconciliation=reconciliation)


def _conflict(message: str, reconciliation: str) -> ClientFailure:
    return ClientFailure("PRESET_CONFLICT", message, reconciliation=reconciliation)


# ------------------------------------------------------------ supplied state input


class SuppliedSegment(BaseModel):
    """One segment of a supplied state object, in WLED wire keys (``id``/``start``/``stop``
    required). Omitted fields are not stored; the bounds follow ``wled_replace_layout``."""

    model_config = ConfigDict(extra="forbid", strict=True)
    id: int = Field(ge=0)
    start: int = Field(ge=0)
    stop: int = Field(ge=1)
    on: bool | None = None
    bri: int | None = Field(default=None, ge=0, le=255)
    col: list[list[int]] | None = None
    fx: int | None = Field(default=None, ge=0)
    pal: int | None = Field(default=None, ge=0)
    sx: int | None = Field(default=None, ge=0, le=255)
    ix: int | None = Field(default=None, ge=0, le=255)
    grp: int | None = Field(default=None, ge=1, le=GROUPING_MAX)
    spc: int | None = Field(default=None, ge=0, le=SPACING_MAX)
    of: int | None = Field(default=None, ge=0)
    rev: bool | None = None
    mi: bool | None = None
    sel: bool | None = None
    # Coarse character bound; the 32 UTF-8 byte rule is checked by check_segment_name.
    n: str | None = Field(default=None, max_length=32)
    # Issue #19 (TD-19-12): the wire keys of the segment tools' #19 fields, same bounds.
    cct: int | None = Field(default=None, ge=0, le=CCT_MAX)
    c1: int | None = Field(default=None, ge=0, le=CUSTOM_MAX)
    c2: int | None = Field(default=None, ge=0, le=CUSTOM_MAX)
    c3: int | None = Field(default=None, ge=0, le=CUSTOM3_MAX)
    o1: bool | None = None
    o2: bool | None = None
    o3: bool | None = None
    si: int | None = Field(default=None, ge=0, le=SOUND_SIMULATION_MAX)
    set: int | None = Field(default=None, ge=0, le=SEGMENT_SET_MAX)
    m12: int | None = Field(default=None, ge=0, le=MAP_1D_2D_MAX)
    frz: bool | None = None
    bm: int | None = Field(default=None, ge=0, le=BLEND_MODE_MAX)
    startY: int | None = Field(default=None, ge=0)  # WLED wire key
    stopY: int | None = Field(default=None, ge=1)  # WLED wire key
    rY: bool | None = None  # WLED wire key
    mY: bool | None = None  # WLED wire key
    tp: bool | None = None

    def fields_19(self) -> dict[str, object]:
        """The #19 values under the public names of the segment tools."""
        return {
            "cct": self.cct,
            "custom1": self.c1,
            "custom2": self.c2,
            "custom3": self.c3,
            "check1": self.o1,
            "check2": self.o2,
            "check3": self.o3,
            "sound_simulation": self.si,
            "segment_set": self.set,
            "map_1d_2d": self.m12,
            "freeze": self.frz,
            "blend_mode": self.bm,
            "start_y": self.startY,
            "stop_y": self.stopY,
            "reverse_y": self.rY,
            "mirror_y": self.mY,
            "transpose": self.tp,
        }


class SuppliedState(BaseModel):
    """A light-state object to store as a preset, in WLED wire keys. Only light state:
    control keys (``ps``, ``playlist``, ``win``, ``psave``, ``nl``, ...) do not exist."""

    model_config = ConfigDict(extra="forbid", strict=True)
    on: bool | None = None
    bri: int | None = Field(default=None, ge=0, le=255)
    transition: int | None = Field(default=None, ge=0, le=MAX_STATE_TRANSITION)
    bs: int | None = Field(default=None, ge=0, le=MAX_BLENDING_STYLE)
    mainseg: int | None = Field(default=None, ge=0)
    seg: list[SuppliedSegment] | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def observable(self) -> SuppliedState:
        if self.on is None and self.bri is None and self.seg is None:
            raise ValueError("state needs at least one of on, bri or seg")
        return self


def _segment_power(segment: SuppliedSegment) -> None:
    ctx = f"Segment {segment.id}: "
    if segment.on is True and segment.bri == 0:
        raise _fail(f"{ctx}on=true with bri=0 is rejected; pass on=false for off.")
    if segment.bri == 0 and segment.on is None:
        raise _fail(f"{ctx}bri=0 requires an explicit on=false in a stored preset.")


def state_object(state: SuppliedState, name: str) -> dict[str, JsonValue]:
    """The exact object that is sent and stored (omitted fields are absent, never null)."""
    result: dict[str, JsonValue] = {}
    dumped = state.model_dump(exclude_none=True)
    for key in SUPPLIED_STATE_KEYS:
        if key not in dumped:
            continue
        if key == "seg":
            result["seg"] = [segment.model_dump(exclude_none=True) for segment in state.seg or []]
        else:
            result[key] = dumped[key]
    result["n"] = name
    return result


def validate_supplied_state(
    state: SuppliedState,
    capabilities: dict[str, JsonValue],
    raw_info: dict[str, JsonValue],
    raw_state: dict[str, JsonValue],
) -> None:
    """Range and capability rules against the target's reported capabilities.

    Consistent with ``wled_replace_layout``: ``0 <= start < stop <= led_count`` (on a
    matrix ``start``/``stop`` are X columns up to the width and ``startY``/``stopY`` rows),
    unique IDs below the reported segment maximum, no overlap (rectangles on a matrix),
    offset below the length, effect and palette IDs inside the catalogs, 1-3 color slots
    of the device's channel width, the shared name rule, no ``on=true`` with ``bri=0`` and
    the #19 capability, field-presence and matrix evidence (TD-19-12).
    """
    if state.on is True and state.bri == 0:
        raise _fail("on=true with bri=0 is rejected; pass on=false for off.")
    segments = state.seg or []
    if not segments:
        if state.mainseg is not None:
            raise _fail("mainseg needs the segments it selects from (seg).")
        return
    led_count = capabilities.get("led_count")
    max_segments = capabilities.get("max_segments")
    effect_count = capabilities.get("effect_count")
    palette_count = capabilities.get("palette_count")
    if not isinstance(led_count, int):
        raise _unsupported(
            "LED count unknown; the supplied segments cannot be validated.",
            "Read the device with wled_get_state; nothing was written.",
        )
    if not isinstance(max_segments, int):
        raise _unsupported(
            "Maximum segment count unknown; the supplied segments cannot be validated.",
            "Read the device with wled_get_state; nothing was written.",
        )
    ids = [segment.id for segment in segments]
    if len(set(ids)) != len(ids):
        raise _fail("Segment IDs must be unique.")
    if len(segments) > max_segments:
        raise _fail(f"More segments than the device maximum ({max_segments}).")
    if state.mainseg is not None and state.mainseg not in ids:
        raise _fail("mainseg must name one of the supplied segment IDs.")
    device = derive_capabilities(raw_state, raw_info)
    geometry = Geometry(device.matrix)
    rects: dict[int, Rect] = {}
    for segment in sorted(segments, key=lambda item: item.id):
        ctx = f"Segment {segment.id}: "
        if segment.id >= max_segments:
            raise _fail(f"{ctx}ID must be below the device maximum {max_segments}.")
        if not 0 <= segment.start < segment.stop <= led_count:
            raise _fail(f"{ctx}range must satisfy 0 <= start < stop <= led_count.")
        if segment.of is not None and not segment.of < segment.stop - segment.start:
            raise _fail(f"{ctx}offset must satisfy 0 <= offset < segment length.")
        if (
            segment.fx is not None
            and isinstance(effect_count, int)
            and not segment.fx < effect_count
        ):
            raise _fail(f"{ctx}fx out of catalog range (0..{effect_count - 1}).")
        if (
            segment.pal is not None
            and isinstance(palette_count, int)
            and not segment.pal < palette_count
        ):
            raise _fail(f"{ctx}pal out of catalog range (0..{palette_count - 1}).")
        check_segment_name(segment.id, segment.n)
        _segment_power(segment)
        try:
            rects[segment.id] = _check_segment_19(segment, device, geometry)
        except ClientFailure as failure:
            raise _store_failure(failure) from None
        if segment.col is not None:
            if device.aggregate_bits is None:
                raise _unsupported(
                    f"{ctx}no RGB or RGBW color capability evidence for the device.",
                    "Omit col or read the device with wled_get_state; nothing was written.",
                )
            try:
                colors_for_bits(device.aggregate_bits, segment.col, ctx)
            except ClientFailure as failure:
                raise _store_failure(failure) from None
    pairs = overlapping_pairs(rects)
    if pairs:
        a_id, b_id = pairs[0]
        raise _fail(f"Segments {a_id} and {b_id} overlap.")


def _store_failure(failure: ClientFailure) -> ClientFailure:
    """A shared segment-rule refusal with the store's reconciliation text."""
    error = failure.error
    if error.code == "UNSUPPORTED_CAPABILITY":
        return _unsupported(
            error.message,
            "Omit the field or read the device with wled_get_state; nothing was written.",
        )
    return _fail(error.message)


def _check_segment_19(
    segment: SuppliedSegment, device: DeviceCapabilities, geometry: Geometry
) -> Rect:
    """Matrix geometry and #19 field evidence of one supplied segment; returns its area.

    An existing ID whose range (and rows) stay the same is "unchanged" and uses its own
    per-segment evidence; any other entry is a new or moved range (uniform rule, TD-19-4).
    """
    ctx = f"Segment {segment.id}: "
    check_y_pair(segment.id, segment.startY, segment.stopY)
    cur = device.segment(segment.id)
    cur_x = (cur.start, cur.stop) if cur is not None else None
    cur_y = (cur.start_y, cur.stop_y) if cur is not None else (None, None)
    same_x = cur_x == (segment.start, segment.stop)
    if geometry.matrix is not None:
        if geometry.is_trailing(segment.start):
            if not same_x:
                raise ClientFailure(
                    "UNSUPPORTED_CAPABILITY",
                    f"{ctx}creating or moving a trailing 1D strip after the matrix is not "
                    "supported; it is read and preserved only.",
                )
            if segment.startY is not None and (segment.startY, segment.stopY) != cur_y:
                raise ClientFailure(
                    "UNSUPPORTED_CAPABILITY",
                    f"{ctx}is the trailing 1D strip after the matrix; its rows are not changed.",
                )
        else:
            geometry.check_x(segment.id, segment.start, segment.stop)
            if segment.startY is None and cur is None:
                raise ClientFailure(
                    "VALIDATION_ERROR",
                    f"{ctx}on a matrix a segment that does not exist yet needs explicit "
                    "startY and stopY.",
                )
            if segment.startY is not None and segment.stopY is not None:
                geometry.check_y(segment.id, segment.startY, segment.stopY)
    target_y = (segment.startY, segment.stopY) if segment.startY is not None else cur_y
    rect = geometry.rect(segment.start, segment.stop, *target_y)
    if rect is None:
        raise ClientFailure(
            "UNSUPPORTED_CAPABILITY", f"{ctx}2D bounds unknown; the overlap check cannot be made."
        )
    unchanged = same_x and (segment.startY is None or (segment.startY, segment.stopY) == cur_y)
    supplied = segment.fields_19()
    check_fields(segment.id, supplied, device, option_keys(device, segment.id, is_new=cur is None))
    if segment.cct is not None:
        check_cct(segment.id, device, changed=not unchanged)
    return rect


# ---------------------------------------------------------------------- playlists


def _per_entry(value: object, count: int, default: int | None) -> list[int] | None:
    """Per-entry values as the firmware expands them: a scalar for all, a list padded with
    its last value and cut at ``count``; ``None`` when absent without a default."""
    if value is None:
        return None if default is None else [default] * count
    if type(value) is int:
        return [value] * count
    assert isinstance(value, list)
    if not all(type(item) is int for item in value):
        return []  # not a firmware-written list; never equal to an expected expansion
    values = [item for item in value if type(item) is int][:count]
    return values + [values[-1]] * (count - len(values)) if values else []


def _check_per_entry(value: object, label: str, upper: int) -> None:
    if value is None:
        return
    items = value if isinstance(value, list) else [value]
    if isinstance(value, list) and not value:
        raise _unsupported(
            f"The playlist's {label} list is empty.", "Inspect the snapshot; nothing was written."
        )
    if not all(type(item) is int and 0 <= item <= upper for item in items):
        raise _unsupported(
            f"The playlist's {label} values must be integers 0-{upper} (tenths of a second).",
            "Inspect the snapshot; nothing was written.",
        )


def check_playlist_entry(entry: dict[str, JsonValue]) -> list[int]:
    """Refuse a playlist object the firmware's re-serialization would not reproduce.

    Returns the member IDs (``ps`` plus a persistent ``end``). Unknown fields, which the
    firmware drops, block the write instead of being discarded silently.
    """
    reconcile = "Inspect the snapshot with wled_list_snapshots; nothing was written."
    unknown = sorted(str(key)[:32] for key in entry.keys() - PLAYLIST_ENTRY_KEYS)
    playlist = entry.get("playlist")
    if not isinstance(playlist, dict):
        raise _unsupported("The playlist object is not recognizable.", reconcile)
    unknown += sorted(f"playlist.{str(key)[:32]}" for key in playlist.keys() - PLAYLIST_KEYS)
    if unknown:
        raise _unsupported(
            "The firmware's playlist save would drop these fields, so the stored object "
            f"would differ: {unknown[:MAX_DIFFERENCES]}.",
            reconcile,
        )
    if entry.get("on", True) is not True:
        raise _unsupported(
            "The firmware stores every playlist with on=true; this object differs.", reconcile
        )
    name = entry.get("n")
    if name is not None and not (isinstance(name, str) and _fits(name, NAME_MAX_BYTES)):
        raise _unsupported(
            "The playlist name is not a string of at most 32 UTF-8 bytes; the firmware "
            "would store it differently.",
            reconcile,
        )
    quick = entry.get("ql")
    if "ql" in entry and not (
        isinstance(quick, str) and quick and _fits(quick, QUICK_LOAD_MAX_BYTES)
    ):
        raise _unsupported(
            "The playlist quick-load label is not a nonempty string of at most 8 UTF-8 bytes.",
            reconcile,
        )
    members = playlist_ids(playlist)
    if members is None or len(members) > MAX_PLAYLIST_ENTRIES:
        raise _unsupported(
            f"The playlist needs 1-{MAX_PLAYLIST_ENTRIES} member IDs from "
            f"{MIN_PERSISTENT_ID}-{MAX_PERSISTENT_ID}.",
            reconcile,
        )
    _check_per_entry(playlist.get("dur"), "dur", MAX_PLAYLIST_DURATION)
    _check_per_entry(playlist.get("transition"), "transition", MAX_TRANSITION)
    repeat = playlist.get("repeat", 0)
    # The firmware keeps repeat + 1 in a byte, so more than 254 would wrap (255: endless).
    if type(repeat) is not int or not 0 <= repeat <= MAX_PLAYLIST_REPEAT:
        raise _unsupported(
            f"The playlist repeat count must be an integer 0-{MAX_PLAYLIST_REPEAT}.", reconcile
        )
    end = playlist.get("end", 0)
    if type(end) is not int or not 0 <= end <= MAX_PERSISTENT_ID:
        raise _unsupported(
            "The playlist end preset must be 0 or a persistent ID 1-250 (255, 'restore the "
            "previous preset', is refused).",
            reconcile,
        )
    shuffle = playlist.get("r", False)
    if not (isinstance(shuffle, bool) or shuffle in (0, 1)):
        raise _unsupported("The playlist shuffle flag must be a boolean.", reconcile)
    return [*members, end] if end else list(members)


def playlist_differences(stored: JsonValue, expected: dict[str, JsonValue]) -> list[str]:
    """Semantic comparison after the firmware's playlist re-serialization (names only)."""
    if not isinstance(stored, dict) or classify(stored)[0] != "playlist":
        return ["entry"]
    got = as_dict(stored.get("playlist"))
    want = as_dict(expected.get("playlist"))
    ids = want.get("ps")
    assert isinstance(ids, list)
    count = len(ids)
    differences: list[str] = []
    if not json_equal(got.get("ps"), ids):
        differences.append("playlist.ps")
    for key, default in (("dur", DEFAULT_PLAYLIST_DURATION), ("transition", None)):
        wanted = _per_entry(want.get(key), count, default)
        if wanted is None:
            continue
        value = got.get(key)
        if not (type(value) is int or (isinstance(value, list) and value)):
            differences.append(f"playlist.{key}")
        elif _per_entry(value, count, default) != wanted:
            differences.append(f"playlist.{key}")
    for key, default_value in (("repeat", 0), ("end", 0)):
        if not json_equal(got.get(key, default_value), want.get(key, default_value)):
            differences.append(f"playlist.{key}")
    if bool(got.get("r", False)) != bool(want.get("r", False)):
        differences.append("playlist.r")
    if stored.get("on", True) is not True:
        differences.append("on")
    for key in ("n", "ql"):
        if stored.get(key) != expected.get(key):
            differences.append(key)
    return differences[:MAX_DIFFERENCES]


def state_differences(stored: JsonValue, expected: dict[str, JsonValue]) -> list[str]:
    """Top-level keys where the stored object differs from the sent object (names only).

    The comparison is exact (``json_equal``), unknown fields included; key order is not
    significant.
    """
    if not isinstance(stored, dict):
        return ["entry"]
    differences = [
        str(key)[:32]
        for key in sorted(set(stored) | set(expected))
        if key not in stored or key not in expected or not json_equal(stored[key], expected[key])
    ]
    return differences[:MAX_DIFFERENCES]


def route_payload(
    route: Route, entry: dict[str, JsonValue], preset_id: int
) -> dict[str, JsonValue]:
    """The one POST body: the entry plus ``psave`` and a non-null ``o``."""
    if route == "playlist":
        body: dict[str, JsonValue] = {
            key: entry[key] for key in ("playlist", "n", "ql") if key in entry
        }
    else:
        body = dict(entry)
    body["psave"] = preset_id
    body["o"] = True
    return body


def expected_entry(
    route: Route, entry: dict[str, JsonValue], preset_id: int
) -> dict[str, JsonValue]:
    """What the readback must show: the sent object minus the firmware-removed keys (state)
    or its playlist fields (playlist), with the firmware's default name when none is sent."""
    if route == "playlist":
        expected = {key: entry[key] for key in ("playlist", "n", "ql") if key in entry}
    else:
        expected = {k: v for k, v in entry.items() if k not in FIRMWARE_REMOVED_KEYS}
    if expected.get("n") is None:
        expected["n"] = f"Preset {preset_id}"  # savePreset/doSaveState default name
    return expected


def _fits(text: str, limit: int) -> bool:
    try:
        return len(text.encode("utf-8")) <= limit
    except UnicodeEncodeError:
        return False


def live_effect(route: Route) -> str:
    return PLAYLIST_LIVE_EFFECT if route == "playlist" else STATE_LIVE_EFFECT


# ------------------------------------------------------------ destination planning


@dataclass
class Destination:
    preset_id: int
    allocated: bool
    existing: dict[str, JsonValue] | None
    existing_type: str | None
    pre_store: PresetStore
    warnings: list[str]


def plan_destination(
    store: PresetStore, preset_id: int | None, overwrite: bool, route: Route
) -> Destination:
    """Choose and check the one destination ID (no I/O)."""
    store.require_wellformed()
    warnings: list[str] = []
    if preset_id is None:
        chosen = lowest_free(store)
        if chosen is None:
            raise _conflict(
                "No free persistent preset ID (1-250) is available; nothing was written.",
                "Delete a preset explicitly or choose an occupied ID with overwrite=true.",
            )
        return Destination(chosen, True, None, None, store, warnings)
    current = store.entries.get(preset_id)
    if current is None:
        return Destination(preset_id, False, None, None, store, warnings)
    if not overwrite:
        raise _conflict(
            "The destination preset ID is occupied; overwrite=true is required to replace it.",
            "Inspect it with wled_get_preset, then repeat with overwrite=true or choose a free ID.",
        )
    kind, malformed = classify(current)
    if malformed or not isinstance(current, dict):
        raise _fail("The existing entry is not a JSON object and cannot be snapshotted.")
    if kind != route:
        warnings.append(f"The existing '{kind}' entry is replaced by a {route} entry.")
    users = referencing_playlists(store, preset_id)
    if users:
        warnings.append(
            f"Playlist(s) {users[:20]} reference this preset; they are not edited and will "
            "use the new entry."
        )
    return Destination(preset_id, False, current, kind, store, warnings)


async def secure_destination(
    context: OperationContext,
    destination: Destination,
    firmware: Firmware,
    read_store: Callable[[OperationContext], Awaitable[PresetStore]],
) -> None:
    """Snapshot an occupied destination, then recheck it (changed => PRESET_CONFLICT)."""
    if destination.existing is not None:
        await context.backup_preset(destination.preset_id, destination.existing, firmware)
    fresh = await read_store(context)
    fresh.require_wellformed()
    current = fresh.entries.get(destination.preset_id)
    if destination.existing is None and current is not None:
        raise _conflict(
            "The destination preset ID was occupied by another client after planning; no "
            "alternative ID was chosen and nothing was written.",
            "Read the presets and request the write again explicitly.",
        )
    if destination.existing is not None and not json_equal(current, destination.existing):
        raise _conflict(
            "The destination preset changed after it was snapshotted; nothing was written.",
            "Read the preset again; the snapshot taken for the earlier state is kept.",
        )
    destination.pre_store = fresh


def check_playlist_members(store: PresetStore, members: list[int], target: int) -> None:
    """Saving a playlist starts it, so every member must be an existing state preset."""
    bad = sorted(
        {*unsafe_playlist_members(store, members), *([target] if target in members else [])}
    )
    if bad:
        raise _unsupported(
            "The playlist references presets that are missing, not plain state presets or the "
            f"destination itself (IDs {bad[:20]}); saving would start it, so nothing is written.",
            "Inspect the members with wled_get_preset.",
        )


def entry_verdict(
    route: Route, expected: dict[str, JsonValue], destination: Destination, value: JsonValue
) -> Verdict:
    """Readback verdict for one written entry; unrelated changes are interference."""
    store = parse_store(as_dict(value))
    entry = store.entries.get(destination.preset_id)
    changed = tuple(interference(destination.pre_store, store, destination.preset_id))
    before = destination.existing
    if entry is None:
        return Verdict(
            matched=False,
            observed=None,
            unchanged=before is None,
            differences=("entry",),
            interference=changed,
        )
    differences = (
        playlist_differences(entry, expected)
        if route == "playlist"
        else state_differences(entry, expected)
    )
    return Verdict(
        matched=not differences,
        observed=entry,
        unchanged=before is not None and json_equal(entry, before),
        differences=tuple(differences),
        interference=changed,
        data={"preset": entry, "type": classify(entry)[0]},
    )


def postconditions(route: Route, preset_id: int) -> list[JsonValue]:
    stored = (
        "equals the sent object except the firmware-removed keys o, v, time, error, psave "
        "and bootps (exact, unknown fields included)"
        if route == "state"
        else "is a playlist with the same members, per-entry durations and transitions, "
        "repeat, end, shuffle and name (semantic, after firmware re-serialization)"
    )
    return [
        f"/presets.json entry {preset_id} {stored}",
        "unrelated entries are unchanged (differences are reported as interference)",
    ]


def live_before(state: dict[str, JsonValue]) -> dict[str, JsonValue]:
    ps, pl = state.get("ps"), state.get("pl")
    return {
        "active_preset_id": ps if type(ps) is int and ps > 0 else None,
        "active_playlist_id": pl if type(pl) is int and pl > 0 else None,
    }


def playback_warnings(route: Route, before: dict[str, JsonValue], target: int) -> list[str]:
    warnings: list[str] = []
    running = before.get("active_playlist_id")
    # The playlist route refuses a running playlist (refuse_running_playlist).
    if isinstance(running, int) and route == "state":
        warnings.append(
            f"Playlist {running} is running; the write changes the live output and may "
            "interrupt it."
        )
    if before.get("active_preset_id") == target:
        warnings.append(
            "The destination is the currently active preset marker (state.ps); it is replaced."
        )
    return warnings


def refuse_running_playlist(before: dict[str, JsonValue]) -> None:
    """The playlist route must not run while a playlist plays.

    With a playlist already running, the firmware's ``loadPlaylist`` may keep it (nested
    playlist) and the save would then store the running playlist instead of the sent
    one (v16.0.1 playlist.cpp, presets.cpp). Checked during planning and again after the
    snapshot, before any POST.
    """
    running = before.get("active_playlist_id")
    if isinstance(running, int):
        raise _conflict(
            f"Playlist {running} is running; saving a playlist now could store the running "
            "playlist instead of this one, so nothing was written.",
            "Stop the running playlist explicitly (for example by activating a state preset) "
            "and request the write again.",
        )
