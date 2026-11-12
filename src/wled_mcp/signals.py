"""Pure planning and comparison for temporary light signals (issue #28, ISSUE-28-DEC-002).

A signal shows one RGB colour on explicitly listed existing segments of one device for a
bounded time and then puts back *only the fields it wrote*, and only when those fields still
hold what the signal set. Everything here is a pure transformation of one fresh
``/json/state`` plus ``/json/info`` read: no I/O, no clock, no ``anyio``. The manager
(``signal_manager.py``) decides when to read and write; the tools (``signal_tools.py``) map
results to envelopes.

The signal writes exactly (docs/contract/signals.md, "Owned fields"):

* per target segment: colour slot 0 (full channel width), the ``Solid`` effect and, only when
  the segment was off, its power;
* the master power, only when the master was off.

All validation, capability, power-coupling and effect rules are those of the existing
planners (``build_segment_patch_plan``, ``build_set_state_plan``); this module adds the
signal-specific refusals, the captured/applied bookkeeping and the conflict comparison.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from pydantic import JsonValue

from wled_mcp.capabilities import color_channels, derive_capabilities, is_white_only
from wled_mcp.client import ClientFailure
from wled_mcp.models import ErrorCode
from wled_mcp.patches import (
    MasterPlan,
    PatchSegmentsRequest,
    SegmentPatch,
    SegmentsPlan,
    SetStateRequest,
    build_segment_patch_plan,
    build_set_state_plan,
    matches_segments,
    matches_set_state,
)

MAX_ACTIVE = 8
MAX_TARGET_SEGMENTS = 16
MAX_DURATION_SECONDS = 300
RETAIN_ENDED = 32
MAX_DIFFERENCES = 20
RETRY_DELAY_SECONDS = 5.0
SHUTDOWN_BUDGET_SECONDS = 5.0
SOLID_EFFECT_NAME = "Solid"
OPERATION_ID_PATTERN = r"^sig-[0-9a-f]{16}$"

# Wire fields the comparison and the restore ignore on purpose; shown in the plan.
IGNORED_FIELDS = (
    "master brightness",
    "transition and one-call transition",
    "segment brightness, speed, intensity and palette",
    "custom sliders, checkboxes and colour temperature",
    "slots 1 and 2 of the colour",
    "names, selection and geometry of untargeted segments",
    "the running preset marker",
)


class SignalRefusal(ClientFailure):
    """A signal request that is refused before any write; ``data`` carries the stable reason."""

    def __init__(
        self,
        reason: str,
        message: str,
        *,
        code: ErrorCode = "VALIDATION_ERROR",
        data: Mapping[str, JsonValue] | None = None,
    ) -> None:
        super().__init__(code, message, reconciliation="Nothing was sent to the device.")
        self.reason = reason
        self.data: dict[str, JsonValue] = {"reason": reason, **(data or {})}


class SignalConflict(ClientFailure):
    """Raised by the restore preparation when an owned field no longer holds the signal value."""

    def __init__(self, differences: Sequence[dict[str, JsonValue]]) -> None:
        super().__init__(
            "VALIDATION_ERROR",
            "An owned field changed after the signal was applied; nothing was restored.",
            reconciliation="Nothing was sent. The device keeps the state found.",
        )
        self.differences = list(differences)


@dataclass(frozen=True)
class SignalSpec:
    device_id: str
    segment_ids: tuple[int, ...]
    color: tuple[int, int, int]
    duration_seconds: int


@dataclass(frozen=True)
class OwnedField:
    """One field the signal wrote: what it was before and what the signal set."""

    scope: Literal["master", "segment"]
    segment_id: int | None
    name: Literal["on", "col0", "fx"]
    captured: JsonValue
    applied: JsonValue

    def public(self) -> dict[str, JsonValue]:
        entry: dict[str, JsonValue] = {"scope": self.scope}
        if self.segment_id is not None:
            entry["id"] = self.segment_id
        entry.update(field=self.name, captured=self.captured, applied=self.applied)
        return entry


@dataclass(frozen=True)
class SignalPlan:
    payload: dict[str, JsonValue]
    owned: tuple[OwnedField, ...]
    geometry: Mapping[int, tuple[int, int]]
    unowned: dict[str, JsonValue]
    public: dict[str, JsonValue]
    warnings: tuple[str, ...]
    segments: SegmentsPlan
    master: MasterPlan | None

    def matches(self, state: JsonValue) -> bool:
        """Readback check of the apply: the same functions every typed write verifies with."""
        return matches_segments(self.segments.expectations, state) and (
            self.master is None or matches_set_state(self.master, state)
        )

    def owned_public(self) -> list[JsonValue]:
        return [field.public() for field in self.owned]

    def restoration_public(self) -> list[JsonValue]:
        return restoration_summary(self.owned)


@dataclass(frozen=True)
class RestorePlan:
    payload: dict[str, JsonValue]
    segments: SegmentsPlan | None
    master: MasterPlan | None

    def matches(self, state: JsonValue) -> bool:
        return (self.segments is None or matches_segments(self.segments.expectations, state)) and (
            self.master is None or matches_set_state(self.master, state)
        )


def restoration_summary(owned: Sequence[OwnedField]) -> list[JsonValue]:
    """What a later restore compares and what it writes, per owned field."""
    summary: list[JsonValue] = []
    for field in owned:
        entry = field.public()
        entry.pop("captured")
        entry.pop("applied")
        entry.update(expected_before_restore=field.applied, restore_to=field.captured)
        summary.append(entry)
    return summary


# ---------------------------------------------------------------------------------- helpers


def _is_int(value: object) -> bool:
    return type(value) is int


def _raw_segments(raw_state: Mapping[str, JsonValue]) -> dict[int, dict[str, JsonValue]]:
    found: dict[int, dict[str, JsonValue]] = {}
    segments = raw_state.get("seg")
    if isinstance(segments, list):
        for segment in segments:
            if isinstance(segment, dict):
                identifier = segment.get("id")
                if isinstance(identifier, int) and not isinstance(identifier, bool):
                    found[identifier] = segment
    return found


def _is_active(segment: Mapping[str, JsonValue]) -> bool:
    start, stop = segment.get("start"), segment.get("stop")
    return _is_int(start) and _is_int(stop) and stop > start  # type: ignore[operator]


def _slot0(segment: Mapping[str, JsonValue]) -> list[int] | None:
    colors = segment.get("col")
    if not isinstance(colors, list) or not colors or not isinstance(colors[0], list):
        return None
    slot = colors[0]
    values = [c for c in slot if isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 255]
    return values if len(slot) in (3, 4) and len(values) == len(slot) else None


def _refuse_unsupported_state(
    spec: SignalSpec,
    state_view: Mapping[str, JsonValue],
    raw_info: Mapping[str, JsonValue],
    raw_state: Mapping[str, JsonValue],
) -> None:
    """The TD-28-7 refusals, in the documented order; the first that applies wins."""
    raw = _raw_segments(raw_state)
    master_on = state_view.get("on")
    for identifier in spec.segment_ids:
        segment = raw.get(identifier)
        if segment is None or not _is_active(segment):
            raise SignalRefusal(
                "segment_unknown",
                f"Segment {identifier} is not an existing active segment; a signal never "
                "creates or changes segments.",
            )
    for identifier in spec.segment_ids:
        segment = raw[identifier]
        if (
            not isinstance(segment.get("on"), bool)
            or not _is_int(segment.get("fx"))
            or _slot0(segment) is None
        ):
            raise SignalRefusal(
                "capture_incomplete",
                f"Segment {identifier} does not report power, effect and colour slot 0, so "
                "its prior state cannot be captured for restoration.",
                code="UNSUPPORTED_CAPABILITY",
            )
    playlist = raw_state.get("pl")
    if _is_int(playlist) and playlist >= 0:  # type: ignore[operator]
        raise SignalRefusal(
            "playlist_active",
            "A playlist is running; a signal cannot restore a playlist position safely.",
        )
    if raw_info.get("live") is True:
        raise SignalRefusal(
            "realtime_active",
            "The device is receiving realtime data; a signal would not be visible or restorable.",
        )
    nightlight = raw_state.get("nl")
    if isinstance(nightlight, dict) and nightlight.get("on") is True:
        raise SignalRefusal(
            "nightlight_active",
            "A nightlight is running; a signal cannot restore a nightlight safely.",
        )
    targets = set(spec.segment_ids)
    frozen_targets = [i for i in spec.segment_ids if raw[i].get("frz") is True]
    if frozen_targets or (master_on is False and any(s.get("frz") is True for s in raw.values())):
        raise SignalRefusal(
            "segment_frozen",
            "A frozen segment is involved; turning the master on unfreezes every segment and "
            "the signal cannot restore that.",
        )
    if master_on is False and any(
        _is_active(segment) and segment.get("on") is not False
        for identifier, segment in raw.items()
        if identifier not in targets
    ):
        raise SignalRefusal(
            "master_off_other_segments",
            "The master is off and another active segment would become visible when the "
            "signal turns the master on; the signal cannot isolate its target.",
        )
    if state_view.get("brightness") == 0 or any(
        raw[i].get("on") is False and raw[i].get("bri") == 0 for i in spec.segment_ids
    ):
        raise SignalRefusal(
            "brightness_zero",
            "The remembered brightness of the master or a target segment is zero; the colour "
            "would be invisible.",
        )


def _color_for(
    identifier: int,
    spec: SignalSpec,
    raw_state: Mapping[str, JsonValue],
    raw_info: Mapping[str, JsonValue],
) -> list[int]:
    """The requested RGB colour at the channel width of the segment (white 0 when 4-wide)."""
    device = derive_capabilities(raw_state, raw_info)
    segment = device.segment(identifier)
    bits = segment.bits if segment is not None and segment.source is not None else None
    if bits is None:
        bits = device.aggregate_bits
    width = None if bits is None else color_channels(bits)
    if bits is None or width is None or is_white_only(bits):
        raise SignalRefusal(
            "color_capability",
            f"Segment {identifier} does not report an RGB or RGBW colour capability the signal "
            "can write (white-only and unknown capability are refused).",
            code="UNSUPPORTED_CAPABILITY",
        )
    return [*spec.color, 0] if width == 4 else list(spec.color)


# ---------------------------------------------------------------------------------- planning


def build_signal_plan(
    spec: SignalSpec,
    state_view: dict[str, JsonValue],
    capabilities: dict[str, JsonValue],
    raw_info: dict[str, JsonValue],
    raw_state: dict[str, JsonValue],
    solid_id: int,
) -> SignalPlan:
    """Refuse unsupported states, capture the owned fields and plan the one combined write."""
    _refuse_unsupported_state(spec, state_view, raw_info, raw_state)
    raw = _raw_segments(raw_state)
    master_on = state_view.get("on") is True
    patches: list[SegmentPatch] = []
    for identifier in spec.segment_ids:
        patches.append(
            SegmentPatch(
                id=identifier,
                colors=[_color_for(identifier, spec, raw_state, raw_info)],
                effect_id=solid_id,
                on=None if raw[identifier].get("on") is True else True,
            )
        )
    request = PatchSegmentsRequest(device_id=spec.device_id, segments=patches)
    segments = build_segment_patch_plan(request, state_view, capabilities, raw_info, raw_state)
    master = (
        None
        if master_on
        else build_set_state_plan(SetStateRequest(device_id=spec.device_id, on=True), state_view)
    )
    payload: dict[str, JsonValue] = {}
    if master is not None:
        payload.update(master.payload)
    payload["seg"] = segments.payload["seg"]

    owned: list[OwnedField] = []
    if master is not None:
        owned.append(OwnedField("master", None, "on", False, True))
    geometry: dict[int, tuple[int, int]] = {}
    unowned_segments: list[JsonValue] = []
    for identifier in spec.segment_ids:
        segment = raw[identifier]
        colors = segments.expectations[identifier]["col"]
        assert isinstance(colors, list) and isinstance(colors[0], list)
        slot = _slot0(segment)
        assert slot is not None
        captured_slot: list[JsonValue] = list(slot)
        owned.append(OwnedField("segment", identifier, "col0", captured_slot, colors[0]))
        owned.append(OwnedField("segment", identifier, "fx", segment["fx"], solid_id))
        if segment.get("on") is False:
            owned.append(OwnedField("segment", identifier, "on", False, True))
        start, stop = segment["start"], segment["stop"]
        assert isinstance(start, int) and isinstance(stop, int)
        geometry[identifier] = (start, stop)
        unowned_segments.append({"id": identifier, "brightness": segment.get("bri")})

    warnings = list(segments.warnings)
    preset = raw_state.get("ps")
    if _is_int(preset) and preset >= 0:  # type: ignore[operator]
        warnings.append(
            "A preset marker is active; any state write clears it and the restore does not "
            "re-activate the preset."
        )
    public: dict[str, JsonValue] = {
        "payload": payload,
        "segments_plan": segments.public,
        "master_plan": None if master is None else master.public,
        "postconditions": [
            "No device POST occurs during dry_run.",
            "Exactly one combined state write is sent and read back before the timer starts.",
            "The restore compares the owned fields first and writes nothing on a difference.",
        ],
    }
    return SignalPlan(
        payload=payload,
        owned=tuple(owned),
        geometry=geometry,
        unowned={"master_brightness": state_view.get("brightness"), "segments": unowned_segments},
        public=public,
        warnings=tuple(warnings),
        segments=segments,
        master=master,
    )


# ---------------------------------------------------------------------------------- comparison


def compare(
    owned: Sequence[OwnedField],
    geometry: Mapping[int, tuple[int, int]],
    raw_state: Mapping[str, JsonValue],
    raw_info: Mapping[str, JsonValue],
) -> list[dict[str, JsonValue]]:
    """Differences between the signal's own values and a fresh read; empty means restorable.

    Same semantics as ``matches_segments`` / ``matches_set_state`` on the owned fields (colour
    slot 0 on its written channels, effect, power) plus the three side-effect checks and the
    geometry of the targets. Unowned fields, counters and animation progress are not looked at.
    """
    found: list[dict[str, JsonValue]] = []

    def add(
        scope: str, identifier: int | None, name: str, expected: JsonValue, seen: JsonValue
    ) -> None:
        if len(found) < MAX_DIFFERENCES:
            entry: dict[str, JsonValue] = {"scope": scope}
            if identifier is not None:
                entry["id"] = identifier
            entry.update(field=name, expected=expected, observed=seen)
            found.append(entry)

    playlist = raw_state.get("pl")
    if _is_int(playlist) and playlist >= 0:  # type: ignore[operator]
        add("device", None, "playlist", -1, playlist)
    if raw_info.get("live") is True:
        add("device", None, "realtime", False, True)
    nightlight = raw_state.get("nl")
    if isinstance(nightlight, dict) and nightlight.get("on") is True:
        add("device", None, "nightlight", False, True)

    raw = _raw_segments(raw_state)
    missing: set[int] = set()
    for identifier, (start, stop) in geometry.items():
        segment = raw.get(identifier)
        if segment is None or not _is_active(segment):
            missing.add(identifier)
            add("segment", identifier, "segment_missing", True, False)
        elif (segment.get("start"), segment.get("stop")) != (start, stop):
            add(
                "segment",
                identifier,
                "geometry_changed",
                [start, stop],
                [segment.get("start"), segment.get("stop")],
            )

    for field in owned:
        if field.scope == "master":
            if raw_state.get("on") is not field.applied:
                add("master", None, "on", field.applied, raw_state.get("on"))
            continue
        assert field.segment_id is not None
        if field.segment_id in missing:
            continue
        segment = raw[field.segment_id]
        if field.name == "col0":
            expected = field.applied
            assert isinstance(expected, list)
            seen = _slot0_loose(segment)
            if seen is None or seen[: len(expected)] != expected:
                add("segment", field.segment_id, "col0", expected, seen)
        elif field.name == "fx":
            if segment.get("fx") != field.applied:
                add("segment", field.segment_id, "fx", field.applied, segment.get("fx"))
        elif segment.get("on") is not field.applied:
            add("segment", field.segment_id, "on", field.applied, segment.get("on"))
    return found


def _slot0_loose(segment: Mapping[str, JsonValue]) -> list[JsonValue] | None:
    colors = segment.get("col")
    if isinstance(colors, list) and colors and isinstance(colors[0], list):
        return list(colors[0])
    return None


# ---------------------------------------------------------------------------------- restore


def build_restore_plan(
    owned: Sequence[OwnedField],
    device_id: str,
    state_view: dict[str, JsonValue],
    capabilities: dict[str, JsonValue],
    raw_info: dict[str, JsonValue],
    raw_state: dict[str, JsonValue],
) -> RestorePlan:
    """The planner output for the captured values of exactly the owned fields."""
    by_segment: dict[int, dict[str, OwnedField]] = {}
    master: MasterPlan | None = None
    for field in owned:
        if field.scope == "master":
            master = build_set_state_plan(
                SetStateRequest(device_id=device_id, on=bool(field.captured)), state_view
            )
        else:
            assert field.segment_id is not None
            by_segment.setdefault(field.segment_id, {})[field.name] = field
    patches: list[SegmentPatch] = []
    for identifier, fields in by_segment.items():
        slot = fields["col0"].captured
        width = len(fields["col0"].applied)  # type: ignore[arg-type]
        assert isinstance(slot, list)
        # The slot is restored at the channel width the planner accepts for the segment.
        fitted = [c for c in slot[:width] if isinstance(c, int)]
        fitted += [0] * (width - len(fitted))
        effect = fields["fx"].captured
        assert isinstance(effect, int)
        patches.append(
            SegmentPatch(
                id=identifier,
                colors=[fitted],
                effect_id=effect,
                on=False if "on" in fields else None,
            )
        )
    segments: SegmentsPlan | None = None
    payload: dict[str, JsonValue] = {}
    if master is not None:
        payload.update(master.payload)
    if patches:
        request = PatchSegmentsRequest(device_id=device_id, segments=patches)
        segments = build_segment_patch_plan(request, state_view, capabilities, raw_info, raw_state)
        payload["seg"] = segments.payload["seg"]
    return RestorePlan(payload=payload, segments=segments, master=master)
