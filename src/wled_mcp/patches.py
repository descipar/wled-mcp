"""Typed master and segment patch planning (issue #6).

Pure request -> plan transformation. The planner never calls the network. It
consumes a fresh normalized `/json/state` view plus the raw info payload and
returns the exact WLED payload plus a public plan + postconditions.

Baseline compensation follows ``ISSUE-6-DEC-002`` (profile 0, pinned v0.15.1
WLED source): RGB-only semantics, per-segment capability from
``info.leds.seglc``, single-object segment edit path, geometry-change name
compensation. Per-segment channel width follows ``ISSUE-6-DEC-003``:
``info.leds.seglc[i]`` when its length equals the state segment list, else
``info.leds.lc`` as the aggregate for an existing *unchanged* range.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from wled_mcp.client import ClientFailure
from wled_mcp.readmodels import CAP_CCT, CAP_RGB, CAP_WHITE, as_dict
from wled_mcp.segment_rules import (
    GROUPING_MAX,
    SPACING_MAX,
    SegmentPower,
    check_segment_name,
    resolve_segment_power,
)

# ---------------------------------------------------------------------------- requests


class SetStateRequest(BaseModel):
    """Master patch. At least one of ``on`` / ``brightness`` must be present.

    Transition is a one-call ``tt`` value in milliseconds. Persistent
    ``transition`` is never touched.
    """

    model_config = ConfigDict(extra="forbid", strict=True)
    device_id: str = Field(min_length=1, max_length=64)
    on: bool | None = None
    brightness: int | None = Field(default=None, ge=0, le=255)
    transition_ms: int | None = Field(default=None, ge=0, le=65500)
    dry_run: bool = False


class SegmentPatch(BaseModel):
    """One explicit segment patch. At least one mutable field must be set.

    ``start`` and ``stop`` must be supplied together when either is present.
    """

    model_config = ConfigDict(extra="forbid", strict=True)
    id: int = Field(ge=0)
    start: int | None = Field(default=None, ge=0)
    stop: int | None = Field(default=None, ge=1)
    on: bool | None = None
    brightness: int | None = Field(default=None, ge=0, le=255)
    colors: list[list[int]] | None = None
    effect_id: int | None = Field(default=None, ge=0)
    palette_id: int | None = Field(default=None, ge=0)
    speed: int | None = Field(default=None, ge=0, le=255)
    intensity: int | None = Field(default=None, ge=0, le=255)
    grouping: int | None = Field(default=None, ge=1, le=GROUPING_MAX)
    spacing: int | None = Field(default=None, ge=0, le=SPACING_MAX)
    offset: int | None = Field(default=None, ge=0)
    reverse: bool | None = None
    mirror: bool | None = None
    selected: bool | None = None
    # Coarse character bound; the 32 UTF-8 byte limit is checked by the planner.
    name: str | None = Field(default=None, max_length=32)


class PatchSegmentsRequest(BaseModel):
    """Nonempty list of segment patches. Omitted segments are untouched."""

    model_config = ConfigDict(extra="forbid", strict=True)
    device_id: str = Field(min_length=1, max_length=64)
    segments: list[SegmentPatch] = Field(min_length=1, max_length=64)
    dry_run: bool = False


# ---------------------------------------------------------------------------- outputs


@dataclass(frozen=True)
class MasterPlan:
    payload: dict[str, JsonValue]
    public: dict[str, JsonValue]
    postconditions: list[JsonValue]
    # Normalized postcondition keys the readback must match (subset of the
    # normalized state view keys). ``expect_on`` is the resolved master power.
    expect_on: bool | None
    expect_brightness: int | None


@dataclass(frozen=True)
class SegmentsPlan:
    payload: dict[str, JsonValue]
    public: dict[str, JsonValue]
    postconditions: list[JsonValue]
    # Expected per-segment field maps, keyed by segment id.
    expectations: dict[int, dict[str, JsonValue]]


# ---------------------------------------------------------------------------- helpers


def _fail(message: str) -> ClientFailure:
    return ClientFailure("VALIDATION_ERROR", message)


def _unsupported(message: str) -> ClientFailure:
    return ClientFailure("UNSUPPORTED_CAPABILITY", message)


def _segment_capability_bits(
    info: dict[str, JsonValue], seg_id: int, segments: list[JsonValue]
) -> int | None:
    """Return the capability bitfield for ``seg_id`` from ``info.leds.seglc``.

    ``seglc`` is used only when its length equals the segment list and the
    target ID resolves to a position in that list. Otherwise ``None`` means
    no per-segment evidence; the caller may fall back to ``info.leds.lc`` for
    an *unchanged* range only (``ISSUE-6-DEC-003``).
    """
    leds = as_dict(info.get("leds"))
    seglc = leds.get("seglc")
    if not isinstance(seglc, list) or len(seglc) != len(segments):
        return None
    for index, seg in enumerate(segments):
        if isinstance(seg, dict) and seg.get("id") == seg_id:
            value = seglc[index]
            if isinstance(value, int) and not isinstance(value, bool):
                return value
            return None
    return None


def _aggregate_capability_bits(info: dict[str, JsonValue]) -> int | None:
    leds = as_dict(info.get("leds"))
    lc = leds.get("lc")
    if isinstance(lc, int) and not isinstance(lc, bool):
        return lc
    return None


def _is_rgb_only(cap: int) -> bool:
    return (cap & (CAP_RGB | CAP_WHITE | CAP_CCT)) == CAP_RGB


def _is_rgbw(cap: int) -> bool:
    return (cap & (CAP_RGB | CAP_WHITE)) == (CAP_RGB | CAP_WHITE)


def _required_color_channels(cap: int) -> Literal[3, 4] | None:
    if _is_rgb_only(cap):
        return 3
    if _is_rgbw(cap):
        return 4
    return None


def _validate_colors(
    colors: list[list[int]], channels: Literal[3, 4], context: str
) -> list[list[int]]:
    if not colors or len(colors) > 3:
        raise _fail(f"{context}colors must contain 1-3 slots.")
    normalized: list[list[int]] = []
    for slot in colors:
        if len(slot) != channels:
            raise _fail(f"{context}expected exactly {channels} channels per color slot.")
        for value in slot:
            if not (isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 255):
                raise _fail(f"{context}color channels must be integers 0-255.")
        normalized.append(list(slot))
    return normalized


def _wire_transition(ms: int) -> int:
    """Nearest 100 ms, half upward. Reject 1-49 ms (round to zero)."""
    if ms == 0:
        return 0
    if 1 <= ms <= 49:
        raise _fail("transition_ms 1-49 rounds to zero; pass 0 or at least 50.")
    return (ms + 50) // 100


# ---------------------------------------------------------------------------- master plan


def build_set_state_plan(request: SetStateRequest, state_view: dict[str, JsonValue]) -> MasterPlan:
    if request.on is None and request.brightness is None:
        raise _fail("wled_set_state requires at least one of 'on' or 'brightness'.")

    current_on = state_view.get("on")
    current_brightness = state_view.get("brightness")
    assert isinstance(current_on, bool)
    assert isinstance(current_brightness, int)

    # Resolve power after applying omitted-field rules.
    resolved_on: bool
    if request.on is not None:
        resolved_on = request.on
    else:
        resolved_on = current_on

    # Brightness rules (CTRL-01 + "Power, brightness and transition"):
    #   * on=true, brightness=0 is rejected.
    #   * brightness=0 with resolved on=true is rejected before POST and
    #     explicit on=false is suggested.
    #   * turning on (false -> true) without an explicit positive brightness
    #     requires a known positive remembered brightness.
    if request.on is True and request.brightness == 0:
        raise _fail(
            "on=true with brightness=0 is rejected; pass on=false for off, "
            "or pass a positive brightness."
        )
    if request.brightness == 0 and resolved_on is True:
        raise _fail("brightness=0 with resolved on=true is rejected; pass on=false explicitly.")
    if request.on is True and current_on is False and request.brightness is None:
        if current_brightness == 0:
            raise _fail(
                "Cannot turn on without an explicit positive brightness; "
                "remembered brightness is zero."
            )

    # Pinned v0.15.1 firmware couples master power to brightness
    # (``on = root["on"] | (bri > 0)``): a positive ``bri`` alone switches an off
    # master on. An omitted ``on`` is preserved by sending the resolved
    # ``on=false`` together with ``bri`` (targeted compensation,
    # ``ISSUE-52-DEC-001``); the master stays off and remembers the brightness.
    compensate_off = (
        request.on is None
        and request.brightness is not None
        and request.brightness > 0
        and current_on is False
    )

    payload: dict[str, JsonValue] = {}
    if request.on is not None:
        payload["on"] = request.on
    elif compensate_off:
        payload["on"] = False
    if request.brightness is not None:
        payload["bri"] = request.brightness

    requested_ms: int | None = None
    effective_ms: int | None = None
    wire_units: int | None = None
    if request.transition_ms is not None:
        requested_ms = request.transition_ms
        wire_units = _wire_transition(request.transition_ms)
        effective_ms = wire_units * 100
        payload["tt"] = wire_units

    # Expected postcondition. Every master write sends ``on`` explicitly or a
    # power-coupled ``bri``, so the resolved power is always verified: a silent
    # power flip is a mismatch, never a verified success (``ISSUE-52-DEC-001``).
    # For ``bri=0`` the resolved power is off; remembered brightness is kept
    # (readback may still show the previous nonzero value).
    expect_on: bool = resolved_on
    expect_brightness = request.brightness if request.brightness is not None else None
    targeted_compensation: list[JsonValue] = [{"on": False}] if compensate_off else []

    public_plan: dict[str, JsonValue] = {
        "on": request.on,
        "brightness": request.brightness,
        "transition": {
            "requested_ms": requested_ms,
            "effective_ms": effective_ms,
            "wire_units": wire_units,
        },
        "resolved": {
            "on": resolved_on,
            "brightness": (
                request.brightness if request.brightness is not None else current_brightness
            ),
        },
        "persistent_transition_touched": False,
        "targeted_compensation": targeted_compensation,
    }
    postconditions: list[JsonValue] = [
        "No device POST or filesystem mutation occurs during dry_run.",
        "Persistent 'transition' is never written; only one-call 'tt' applies.",
        "The readback verifies the resolved master power.",
    ]
    if compensate_off:
        postconditions.append(
            "A positive brightness on an off master is sent with on=false so the omitted "
            "power is preserved; the readback verifies the master stays off."
        )
    if request.transition_ms is not None:
        postconditions.append(
            f"transition_ms {requested_ms} maps to wire units {wire_units} "
            f"(effective {effective_ms} ms); zero is immediate."
        )
    if request.brightness == 0 and resolved_on is False:
        postconditions.append(
            "brightness=0 targets off/effective zero; remembered brightness is preserved."
        )
    return MasterPlan(
        payload=payload,
        public=public_plan,
        postconditions=postconditions,
        expect_on=expect_on,
        expect_brightness=expect_brightness,
    )


def matches_set_state(expected: MasterPlan, state: JsonValue) -> bool:
    """Postcondition check for ``write_verified``.

    The readback is the raw ``/json/state`` object. Verify the resolved master
    power and the requested brightness; master ``bri`` readback is remembered
    brightness while ``on`` reflects actual power; animation of unrelated fields
    is ignored.
    """
    if not isinstance(state, dict):
        return False
    if expected.expect_on is not None and state.get("on") is not expected.expect_on:
        return False
    if expected.expect_brightness is not None:
        value = state.get("bri")
        # bri=0 with on=false is accepted either as a true 0 readback or as
        # "off while remembered is preserved"; the planner only enforces
        # equality for strictly positive expectations.
        if expected.expect_brightness > 0:
            if value != expected.expect_brightness:
                return False
        else:
            # Expecting zero means we also asked for off: the state must be off.
            if state.get("on") is not False:
                return False
    return True


# ---------------------------------------------------------------------------- segment plan


def _normalize_patch_colors(
    patch: SegmentPatch, cap: int | None, is_range_change: bool
) -> list[list[int]] | None:
    """Enforce RGB-only/RGBW channel widths per ``ISSUE-6-DEC-003``."""
    if patch.colors is None:
        return None
    if cap is None:
        raise _unsupported(
            f"Segment {patch.id}: no per-segment color capability evidence available; "
            "patch with a color change requires info.leds.seglc coverage."
        )
    channels = _required_color_channels(cap)
    if channels is None:
        raise _unsupported(
            f"Segment {patch.id}: unsupported color capability "
            "(only RGB and RGBW are supported in this profile)."
        )
    if is_range_change and channels == 4:
        # New or moved ranges require matching range evidence per SEG-03; we
        # accept RGBW evidence only for *unchanged* ranges per DEC-003 wording.
        # A range-change that supplies RGBW colors needs explicit RGBW range
        # evidence; absent a dedicated check, refuse conservatively.
        raise _unsupported(
            f"Segment {patch.id}: range change with 4-channel colors is not "
            "supported under baseline profile 0."
        )
    return _validate_colors(patch.colors, channels, f"Segment {patch.id}: ")


def _range_overlap(
    layout: list[tuple[int, int, int]], check_id: int, start: int, stop: int
) -> bool:
    for seg_id, seg_start, seg_stop in layout:
        if seg_id == check_id:
            continue
        if seg_start < stop and start < seg_stop:
            return True
    return False


def _segment_payload(
    patch: SegmentPatch,
    normalized_colors: list[list[int]] | None,
    compensate_name: str | None,
    range_change: bool,
    power: SegmentPower,
) -> dict[str, JsonValue]:
    """Build the exact WLED segment object for one patched ID.

    Omitted fields are *not* sent. The exceptions are baseline profile 0 targeted
    compensations: the existing name on a geometry change (``compensate_name``) and
    the resolved ``on=false`` with a positive ``bri`` on an off segment (#48).
    """
    entry: dict[str, JsonValue] = {"id": patch.id}
    if patch.start is not None and patch.stop is not None:
        entry["start"] = patch.start
        entry["stop"] = patch.stop
    if patch.on is not None:
        entry["on"] = patch.on
    elif power.compensate_off:
        entry["on"] = False
    if patch.brightness is not None:
        entry["bri"] = patch.brightness
    if normalized_colors is not None:
        entry["col"] = [list(slot) for slot in normalized_colors]
    if patch.effect_id is not None:
        entry["fx"] = patch.effect_id
    if patch.palette_id is not None:
        entry["pal"] = patch.palette_id
    if patch.speed is not None:
        entry["sx"] = patch.speed
    if patch.intensity is not None:
        entry["ix"] = patch.intensity
    if patch.grouping is not None:
        entry["grp"] = patch.grouping
    if patch.spacing is not None:
        entry["spc"] = patch.spacing
    if patch.offset is not None:
        entry["of"] = patch.offset
    if patch.reverse is not None:
        entry["rev"] = patch.reverse
    if patch.mirror is not None:
        entry["mi"] = patch.mirror
    if patch.selected is not None:
        entry["sel"] = patch.selected
    if patch.name is not None:
        entry["n"] = patch.name
    elif range_change and compensate_name is not None and "n" not in entry:
        # Profile 0 side effect: geometry changes clear the segment name.
        # Resend the existing name to preserve it.
        entry["n"] = compensate_name
    return entry


def _resolve_public_segment(
    patch: SegmentPatch,
    current: dict[str, JsonValue],
    normalized_colors: list[list[int]] | None,
    compensate_name: str | None,
) -> dict[str, JsonValue]:
    """Produce the public plan's post-patch view of this segment (dry-run)."""
    _MUTABLE = (
        ("effect_id", patch.effect_id),
        ("palette_id", patch.palette_id),
        ("speed", patch.speed),
        ("intensity", patch.intensity),
        ("grouping", patch.grouping),
        ("spacing", patch.spacing),
        ("offset", patch.offset),
        ("reverse", patch.reverse),
        ("mirror", patch.mirror),
        ("selected", patch.selected),
    )

    def pick(field: str, override: object) -> JsonValue:
        if override is not None:
            return override  # type: ignore[return-value]
        value = current.get(field)
        return value

    start = patch.start if patch.start is not None else current.get("start")
    stop = patch.stop if patch.stop is not None else current.get("stop")
    on_value = patch.on if patch.on is not None else current.get("on")
    bri = patch.brightness if patch.brightness is not None else current.get("brightness")
    effective: int | None = None
    if isinstance(on_value, bool) and isinstance(bri, int):
        effective = bri if on_value else 0
    colors: JsonValue
    if normalized_colors is not None:
        colors = [list(slot) for slot in normalized_colors]
    else:
        current_colors = current.get("colors")
        if isinstance(current_colors, list) and all(
            isinstance(slot, list) for slot in current_colors
        ):
            colors = [list(slot) for slot in current_colors if isinstance(slot, list)]
        else:
            colors = None
    name_override = patch.name if patch.name is not None else compensate_name
    name_value = name_override if name_override is not None else current.get("name")
    resolved: dict[str, JsonValue] = {
        "id": patch.id,
        "start": start if isinstance(start, int) else None,
        "stop": stop if isinstance(stop, int) else None,
        "on": on_value if isinstance(on_value, bool) else None,
        "brightness": bri if isinstance(bri, int) else None,
        "effective_brightness": effective,
        "colors": colors,
        "name": name_value if isinstance(name_value, str) else None,
    }
    for field, override in _MUTABLE:
        resolved[field] = pick(field, override)
    return resolved


def _patch_expectation(
    patch: SegmentPatch, normalized_colors: list[list[int]] | None, power: SegmentPower
) -> dict[str, JsonValue]:
    """Normalized postcondition fields for ``matches_segments`` readback."""
    expectation: dict[str, JsonValue] = {}
    if patch.start is not None:
        expectation["start"] = patch.start
    if patch.stop is not None:
        expectation["stop"] = patch.stop
    if patch.on is not None:
        expectation["on"] = patch.on
    if patch.brightness is not None:
        if patch.brightness == 0:
            # bri=0 switches the segment off in the pinned firmware; verify the
            # segment reports on=False rather than requiring raw bri=0.
            expectation["segment_off_from_zero_bri"] = True
        else:
            expectation["bri"] = patch.brightness
            # A sent bri couples power in the firmware: always verify the resolved
            # on, so an unexpected power flip is a mismatch, never a silent success.
            if power.resolved_on is not None:
                expectation["on"] = power.resolved_on
    if normalized_colors is not None:
        expectation["col"] = [list(slot) for slot in normalized_colors]
    if patch.effect_id is not None:
        expectation["fx"] = patch.effect_id
    if patch.palette_id is not None:
        expectation["pal"] = patch.palette_id
    if patch.speed is not None:
        expectation["sx"] = patch.speed
    if patch.intensity is not None:
        expectation["ix"] = patch.intensity
    if patch.grouping is not None:
        expectation["grp"] = patch.grouping
    if patch.spacing is not None:
        expectation["spc"] = patch.spacing
    if patch.offset is not None:
        expectation["of"] = patch.offset
    if patch.reverse is not None:
        expectation["rev"] = patch.reverse
    if patch.mirror is not None:
        expectation["mi"] = patch.mirror
    if patch.selected is not None:
        expectation["sel"] = patch.selected
    if patch.name is not None:
        expectation["n"] = patch.name
    return expectation


def build_segment_patch_plan(
    request: PatchSegmentsRequest,
    state_view: dict[str, JsonValue],
    capabilities: dict[str, JsonValue],
    raw_info: dict[str, JsonValue],
    raw_state: dict[str, JsonValue],
) -> SegmentsPlan:
    # Validate uniqueness.
    seen: set[int] = set()
    for patch in request.segments:
        if patch.id in seen:
            raise _fail(f"Segment ID {patch.id} appears more than once in the patch list.")
        seen.add(patch.id)

    # Mutable-field presence check (something other than id must be set).
    for patch in request.segments:
        has_change = any(
            getattr(patch, field) is not None
            for field in (
                "start",
                "stop",
                "on",
                "brightness",
                "colors",
                "effect_id",
                "palette_id",
                "speed",
                "intensity",
                "grouping",
                "spacing",
                "offset",
                "reverse",
                "mirror",
                "selected",
                "name",
            )
        )
        if not has_change:
            raise _fail(f"Segment {patch.id}: patch must contain at least one mutable field.")
        check_segment_name(patch.id, patch.name)
        # Both start and stop together (SEG-03). Range change implies both.
        if (patch.start is None) != (patch.stop is None):
            raise _fail(f"Segment {patch.id}: a range change requires both 'start' and 'stop'.")
        if patch.start is not None and patch.stop is not None and patch.start >= patch.stop:
            raise _fail(f"Segment {patch.id}: start must be strictly less than stop.")

    # Current layout + per-segment lookup.
    segments_view = state_view.get("segments")
    assert isinstance(segments_view, list)
    layout_by_id: dict[int, dict[str, JsonValue]] = {}
    for seg in segments_view:
        if isinstance(seg, dict) and isinstance(seg.get("id"), int):
            seg_id = seg["id"]
            assert isinstance(seg_id, int)
            layout_by_id[seg_id] = seg

    # Confirm every targeted ID exists in the current active layout
    # (``wled_patch_segments`` targets existing active IDs only — SEG-01).
    for patch in request.segments:
        if patch.id not in layout_by_id:
            raise _fail(
                f"Segment {patch.id}: not an existing active segment; patch cannot add segments."
            )

    # Shared power/brightness rules (ISSUE-48-DEC-001, same helper as #7).
    powers: dict[int, SegmentPower] = {}
    for patch in request.segments:
        current_on = layout_by_id[patch.id].get("on")
        powers[patch.id] = resolve_segment_power(
            patch.id,
            patch.on,
            patch.brightness,
            current_on if isinstance(current_on, bool) else None,
        )

    led_count = capabilities.get("led_count")
    max_segments = capabilities.get("max_segments")
    effect_count = capabilities.get("effect_count")
    palette_count = capabilities.get("palette_count")

    # Resolve LED-count bounds for geometry changes.
    for patch in request.segments:
        if patch.start is not None and patch.stop is not None:
            if not isinstance(led_count, int):
                raise _unsupported(f"Segment {patch.id}: LED count unknown; range change rejected.")
            if not 0 <= patch.start < patch.stop <= led_count:
                raise _fail(
                    f"Segment {patch.id}: range must satisfy 0 <= start < stop <= led_count."
                )
            length = patch.stop - patch.start
            if patch.offset is not None and not 0 <= patch.offset < length:
                raise _fail(
                    f"Segment {patch.id}: offset must satisfy 0 <= offset < resulting length."
                )

    # Effect / palette existence (when the device reported counts).
    for patch in request.segments:
        if patch.effect_id is not None and isinstance(effect_count, int):
            if not 0 <= patch.effect_id < effect_count:
                raise _fail(
                    f"Segment {patch.id}: effect_id out of catalog range (0..{effect_count - 1})."
                )
        if patch.palette_id is not None and isinstance(palette_count, int):
            if not 0 <= patch.palette_id < palette_count:
                raise _fail(
                    f"Segment {patch.id}: palette_id out of catalog range (0..{palette_count - 1})."
                )

    # Build proposed layout (for overlap checks when geometry changes).
    proposed_layout: list[tuple[int, int, int]] = []
    patched_ids = {patch.id for patch in request.segments}
    for seg in segments_view:
        assert isinstance(seg, dict)
        seg_id, start, stop = seg.get("id"), seg.get("start"), seg.get("stop")
        if isinstance(seg_id, int) and isinstance(start, int) and isinstance(stop, int):
            if seg_id in patched_ids:
                continue
            proposed_layout.append((seg_id, start, stop))
    geometry_change = False
    for patch in request.segments:
        current = layout_by_id[patch.id]
        start = patch.start if patch.start is not None else current.get("start")
        stop = patch.stop if patch.stop is not None else current.get("stop")
        assert isinstance(start, int) and isinstance(stop, int)
        if patch.start is not None or patch.stop is not None:
            geometry_change = True
        proposed_layout.append((patch.id, start, stop))

    if geometry_change:
        for patch in request.segments:
            if patch.start is None and patch.stop is None:
                continue
            start = patch.start if patch.start is not None else layout_by_id[patch.id]["start"]
            stop = patch.stop if patch.stop is not None else layout_by_id[patch.id]["stop"]
            assert isinstance(start, int) and isinstance(stop, int)
            if _range_overlap(proposed_layout, patch.id, start, stop):
                raise _fail(
                    f"Segment {patch.id}: range change would overlap another active segment."
                )

    # Max-segments limit is not changed by a patch (we never add segments
    # here), so no cardinality check beyond what the firmware already enforces.
    if isinstance(max_segments, int) and len(layout_by_id) > max_segments:
        # defensive; normalized state should already honor this.
        raise _unsupported(
            "Device reports more active segments than the declared max; refusing patch."
        )

    raw_segments = raw_state.get("seg")
    assert isinstance(raw_segments, list)

    # Per-segment payload + expectations.
    payload_segments: list[JsonValue] = []
    resolved_segments: list[JsonValue] = []
    expectations: dict[int, dict[str, JsonValue]] = {}
    compensation: list[JsonValue] = []
    for patch in request.segments:
        current = layout_by_id[patch.id]
        power = powers[patch.id]
        is_range_change = patch.start is not None and patch.stop is not None
        if patch.colors is not None:
            seglc_cap = _segment_capability_bits(raw_info, patch.id, raw_segments)
            agg_cap = _aggregate_capability_bits(raw_info)
            if seglc_cap is not None:
                cap_for_colors: int | None = seglc_cap
            elif not is_range_change and agg_cap is not None:
                # Unchanged range may fall back to the aggregate per DEC-003.
                cap_for_colors = agg_cap
            else:
                cap_for_colors = None
            normalized_colors = _normalize_patch_colors(patch, cap_for_colors, is_range_change)
        else:
            normalized_colors = None
        compensate_name: str | None = None
        if is_range_change:
            existing_name = current.get("name")
            if isinstance(existing_name, str) and existing_name:
                compensate_name = existing_name
        entry = _segment_payload(patch, normalized_colors, compensate_name, is_range_change, power)
        payload_segments.append(entry)
        if patch.name is None and compensate_name is not None and "n" in entry:
            compensation.append({"id": patch.id, "name": compensate_name})
        if power.compensate_off:
            compensation.append({"id": patch.id, "on": False})
        resolved_segments.append(
            _resolve_public_segment(patch, current, normalized_colors, compensate_name)
        )
        expectations[patch.id] = _patch_expectation(patch, normalized_colors, power)

    payload: dict[str, JsonValue] = {"seg": payload_segments}

    preserve_ids: list[JsonValue] = [
        seg_id for seg_id in sorted(layout_by_id) if seg_id not in patched_ids
    ]
    update_ids: list[JsonValue] = [seg_id for seg_id in sorted(patched_ids)]
    empty_list: list[JsonValue] = []
    public_plan: dict[str, JsonValue] = {
        "update_segment_ids": update_ids,
        "create_segment_ids": list(empty_list),
        "remove_segment_ids": list(empty_list),
        "resolved_segments": resolved_segments,
        "preserve_segment_ids": preserve_ids,
        "targeted_compensation": compensation,
    }
    postconditions: list[JsonValue] = [
        "No device POST or filesystem mutation occurs during dry_run.",
        "Omitted segment fields and all unrelated active segments are preserved.",
        "Applying this plan requires fresh validation under the per-device lock.",
    ]
    if geometry_change:
        postconditions.append(
            "Baseline profile 0 resends existing segment names to counter "
            "geometry-change name clearing."
        )
    if any(power.compensate_off for power in powers.values()):
        postconditions.append(
            "A positive brightness on an off segment is sent with on=false so the omitted "
            "power is preserved; the readback verifies the segment stays off."
        )
    return SegmentsPlan(
        payload=payload,
        public=public_plan,
        postconditions=postconditions,
        expectations=expectations,
    )


def matches_segments(expectations: dict[int, dict[str, JsonValue]], state: JsonValue) -> bool:
    """Compare only the explicitly requested fields on the exact patched IDs."""
    if not isinstance(state, dict):
        return False
    segments = state.get("seg")
    if not isinstance(segments, list):
        return False
    by_id: dict[int, dict[str, JsonValue]] = {}
    for seg in segments:
        if isinstance(seg, dict) and isinstance(seg.get("id"), int):
            seg_id = seg["id"]
            assert isinstance(seg_id, int)
            by_id[seg_id] = seg
    for seg_id, fields in expectations.items():
        current = by_id.get(seg_id)
        if current is None:
            return False
        for key, value in fields.items():
            if key == "segment_off_from_zero_bri":
                # bri=0 request: the segment must now report on=False;
                # remembered bri may stay nonzero in the pinned firmware.
                if current.get("on") is not False:
                    return False
                continue
            if key == "col":
                raw_slots = current.get("col")
                if not isinstance(raw_slots, list):
                    return False
                expected_slots = value
                assert isinstance(expected_slots, list)
                # Only compare the leading slots we actually sent.
                for index, expected_slot in enumerate(expected_slots):
                    if index >= len(raw_slots):
                        return False
                    raw_slot = raw_slots[index]
                    if not isinstance(raw_slot, list):
                        return False
                    assert isinstance(expected_slot, list)
                    for channel_index, expected_channel in enumerate(expected_slot):
                        if channel_index >= len(raw_slot):
                            return False
                        if raw_slot[channel_index] != expected_channel:
                            return False
                continue
            if current.get(key) != value:
                return False
    return True
