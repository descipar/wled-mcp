"""Segment input rules shared by ``wled_patch_segments`` (#6) and ``wled_replace_layout`` (#7).

Issue #48, ``ISSUE-48-DEC-001`` (docs/decisions/issue-48.md): both tools apply the same
rules before any write, identically in a dry run, so that inputs the baseline firmware
(profile 0: v0.15.1 source, observed on 16.0.1) cannot represent are refused instead of
surfacing after writes as ``VERIFICATION_MISMATCH``:

* a segment name is at most 32 UTF-8 bytes (the build-independent firmware minimum;
  the firmware truncates by bytes) and must not contain U+0000 (C-string end);
* ``grouping`` is 1-255 and ``spacing`` 0-255 (firmware ``uint8_t`` arguments);
* ``on=true`` with ``brightness=0`` is rejected (the firmware ends ON);
* ``brightness=0`` with omitted ``on`` is accepted only on a segment that is off;
* a positive ``brightness`` with omitted ``on`` on an off segment is sent together with
  the resolved ``on=false`` (the firmware would otherwise switch the segment on).

Issue #19 (``ISSUE-19-DEC-001``..``-003``, docs/contract/segments.md) adds the shared
rules for the WLED 16 segment fields, used by both tools and by ``wled_store_preset``:
capability evidence for colors and ``cct``, field presence for the options, the matrix
geometry (X columns, Y rows, trailing strip, rectangle overlap) and the overlap opt-in.

Module-private to this package; the planners import it, nothing else.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from pydantic import JsonValue

from wled_mcp.capabilities import (
    DeviceCapabilities,
    aggregate_bits,
    color_channels,
    has_cct,
    is_rgb_only,
    is_white_only,
)
from wled_mcp.client import ClientFailure

SEGMENT_NAME_MAX_BYTES = 32
GROUPING_MAX = 255
SPACING_MAX = 255


def check_segment_name(seg_id: int, name: str | None) -> None:
    """Reject a supplied name the firmware would truncate (bytes) or cut at U+0000."""
    if name is None:
        return
    if "\x00" in name:
        raise ClientFailure("VALIDATION_ERROR", f"Segment {seg_id}: name must not contain U+0000.")
    try:
        size = len(name.encode("utf-8"))
    except UnicodeEncodeError:
        raise ClientFailure(
            "VALIDATION_ERROR", f"Segment {seg_id}: name is not valid UTF-8 text."
        ) from None
    if size > SEGMENT_NAME_MAX_BYTES:
        raise ClientFailure(
            "VALIDATION_ERROR",
            f"Segment {seg_id}: name is {size} UTF-8 bytes; the limit is "
            f"{SEGMENT_NAME_MAX_BYTES} bytes (the firmware would truncate it).",
        )


@dataclass(frozen=True)
class SegmentPower:
    """Resolved power for one segment request.

    ``resolved_on`` is the power after the write (``None`` only when the device did not
    report the current power and the request touches neither power nor brightness).
    ``compensate_off`` is true when a positive brightness is requested with omitted
    ``on`` on a segment that is off: the planner must also send ``on=false`` with the
    ``bri`` (targeted compensation shown in the plan).
    """

    resolved_on: bool | None
    compensate_off: bool


def resolve_segment_power(
    seg_id: int, requested_on: bool | None, brightness: int | None, current_on: bool | None
) -> SegmentPower:
    """Apply the shared power/brightness rules before any write.

    ``current_on`` is the fresh readback (``None`` when the device did not report a
    usable value). A new segment of ``wled_replace_layout`` passes its default ``True``.
    """
    ctx = f"Segment {seg_id}: "
    if requested_on is True and brightness == 0:
        raise ClientFailure(
            "VALIDATION_ERROR",
            f"{ctx}on=true with brightness=0 is rejected; pass on=false for off, "
            "or a positive brightness.",
        )
    if requested_on is not None:
        return SegmentPower(resolved_on=requested_on, compensate_off=False)
    if brightness == 0:
        if current_on is not False:
            raise ClientFailure(
                "VALIDATION_ERROR",
                f"{ctx}brightness=0 on a segment that is not off requires an explicit on=false.",
            )
        return SegmentPower(resolved_on=False, compensate_off=False)
    if current_on is None:
        if brightness is not None:
            raise ClientFailure(
                "UNSUPPORTED_CAPABILITY",
                f"{ctx}current segment power is unknown, so a brightness change could "
                "switch it on; pass on explicitly.",
            )
        return SegmentPower(resolved_on=None, compensate_off=False)
    return SegmentPower(
        resolved_on=current_on,
        compensate_off=brightness is not None and current_on is False,
    )


# ============================================================================ issue #19
#
# WLED 16 segment evidence (ISSUE-19-DEC-003, docs/contract/segments.md): the setters for
# CCT, white-only/RGBW colors on new or moved ranges, effect options, 2D bounds and
# orientation and the overlap opt-in (ISSUE-19-DEC-001). Every rule is evaluated before
# any write and identically in a dry run; refusals raise ``ClientFailure``.

CCT_MAX = 255
CUSTOM_MAX = 255
CUSTOM3_MAX = 31  # 5-bit field in the firmware (json.cpp L305)
SOUND_SIMULATION_MAX = 3  # constrained by the firmware (json.cpp L278)
SEGMENT_SET_MAX = 3  # constrained by the firmware (json.cpp L277)
MAP_1D_2D_MAX = 4  # documented mappings (pixels, bar, arc, corner, pinwheel)
BLEND_MODE_MAX = 16  # BLENDMODES 17 (FX_fcn.cpp L1416)
CCT_DEFAULT = 127  # FX.h segment default

Evidence = Literal["state_lc", "info_seglc", "uniform", "aggregate", "field_present", "matrix"]


@dataclass(frozen=True)
class OptionField:
    """An effect/segment option settable only where the readback carries its wire key."""

    name: str
    wire: str
    default: int | bool  # replace create default (FX.h L42-48, L564-586)


OPTION_FIELDS: tuple[OptionField, ...] = (
    OptionField("custom1", "c1", 128),
    OptionField("custom2", "c2", 128),
    OptionField("custom3", "c3", 16),
    OptionField("check1", "o1", False),
    OptionField("check2", "o2", False),
    OptionField("check3", "o3", False),
    OptionField("sound_simulation", "si", 0),
    OptionField("segment_set", "set", 0),
    OptionField("map_1d_2d", "m12", 0),
    OptionField("freeze", "frz", False),
    OptionField("blend_mode", "bm", 0),
)
Y_FIELDS: tuple[tuple[str, str], ...] = (("start_y", "startY"), ("stop_y", "stopY"))
ORIENTATION_FIELDS: tuple[tuple[str, str], ...] = (
    ("reverse_y", "rY"),
    ("mirror_y", "mY"),
    ("transpose", "tp"),
)
MATRIX_FIELDS: tuple[tuple[str, str], ...] = Y_FIELDS + ORIENTATION_FIELDS
# Every #19 setter, public name -> wire key, in the order of the read model.
SEGMENT_FIELDS: tuple[tuple[str, str], ...] = (
    ("cct", "cct"),
    *((field.name, field.wire) for field in OPTION_FIELDS),
    *MATRIX_FIELDS,
)

FREEZE_WARNING = (
    "freeze: segment(s) {ids} will be frozen; turning the master on (from off) unfreezes "
    "every segment in the firmware (json.cpp L389-391)."
)


def _unsupported(message: str) -> ClientFailure:
    return ClientFailure("UNSUPPORTED_CAPABILITY", message)


def _invalid(message: str) -> ClientFailure:
    return ClientFailure("VALIDATION_ERROR", message)


def validate_colors(
    colors: list[list[int]], channels: Literal[3, 4], context: str
) -> list[list[int]]:
    """1-3 slots of exactly ``channels`` integers 0-255; never padded or trimmed."""
    if not colors or len(colors) > 3:
        raise _invalid(f"{context}colors must contain 1-3 slots.")
    normalized: list[list[int]] = []
    for slot in colors:
        if len(slot) != channels:
            raise _invalid(f"{context}expected exactly {channels} channels per color slot.")
        for value in slot:
            if not (isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 255):
                raise _invalid(f"{context}color channels must be integers 0-255.")
        normalized.append(list(slot))
    return normalized


def colors_for_bits(bits: int, colors: list[list[int]], context: str) -> list[list[int]]:
    """Colors for a range with known capability bits (TD-19-3)."""
    channels = color_channels(bits)
    if channels is None:
        raise _unsupported(f"{context}the range reports neither RGB nor white channels.")
    normalized = validate_colors(colors, channels, context)
    if is_white_only(bits) and any(slot[:3] != [0, 0, 0] for slot in normalized):
        raise _invalid(
            f"{context}a white-only range takes four channels with RGB 0 ([0, 0, 0, W])."
        )
    return normalized


def stage1_rgb_uniform(raw_info: Mapping[str, JsonValue], raw_segments: list[JsonValue]) -> bool:
    """The stage-1 new-range rule (ISSUE-7-DEC-004): ``info.leds.lc`` RGB-only and, when
    ``info.leds.seglc`` is reported, aligned and RGB-only for every active segment."""
    lc = aggregate_bits(raw_info)
    leds = raw_info.get("leds")
    seglc = leds.get("seglc") if isinstance(leds, dict) else None
    uniform = lc is not None and is_rgb_only(lc)
    if uniform and seglc is not None:
        uniform = (
            isinstance(seglc, list)
            and len(seglc) == len(raw_segments)
            and all(type(v) is int and is_rgb_only(v) for v in seglc)
        )
    return uniform


def check_colors(
    seg_id: int,
    colors: list[list[int]],
    device: DeviceCapabilities,
    raw_info: Mapping[str, JsonValue],
    raw_segments: list[JsonValue],
    *,
    is_new: bool,
    moved: bool,
) -> tuple[list[list[int]], Evidence]:
    """Channel width for a color write and the evidence it rests on.

    * Existing unchanged range: its per-segment capability (``state_lc`` ->
      ``info_seglc``), else the aggregate ``info.leds.lc`` (ISSUE-6-DEC-003).
    * Moved range: per-segment RGB-only evidence keeps the stage-1 three channels; any
      other width needs the uniform rule (TD-19-4).
    * New range: the stage-1 RGB-only rule, else the uniform rule (TD-19-4).
    """
    ctx = f"Segment {seg_id}: "
    if not colors or len(colors) > 3:
        raise _invalid(f"{ctx}colors must contain 1-3 slots.")
    if is_new:
        if stage1_rgb_uniform(raw_info, raw_segments):
            if any(len(slot) == 4 for slot in colors):
                raise _unsupported(
                    f"{ctx}4-channel colors for a new range need white capability; the "
                    "device reports RGB only."
                )
            return validate_colors(colors, 3, ctx), "uniform"
        if device.uniform_bits is None:
            raise _unsupported(
                f"{ctx}no uniform capability evidence for a new range: info.leds.lc must "
                "equal the reported capability of every active segment."
            )
        return colors_for_bits(device.uniform_bits, colors, ctx), "uniform"
    segment = device.segment(seg_id)
    bits = segment.bits if segment is not None else None
    source = segment.source if segment is not None else None
    if moved:
        if bits is not None and source is not None and is_rgb_only(bits):
            return validate_colors(colors, 3, ctx), source
        if bits is None:
            raise _unsupported(f"{ctx}no per-segment color capability evidence available.")
        if device.uniform_bits is None:
            raise _unsupported(
                f"{ctx}a moved range with white or CCT capability needs uniform evidence: "
                "info.leds.lc must equal the reported capability of every active segment."
            )
        return colors_for_bits(device.uniform_bits, colors, ctx), "uniform"
    if bits is None or source is None:
        if device.aggregate_bits is None:
            raise _unsupported(f"{ctx}no per-segment color capability evidence available.")
        return colors_for_bits(device.aggregate_bits, colors, ctx), "aggregate"
    return colors_for_bits(bits, colors, ctx), source


def check_cct(seg_id: int, device: DeviceCapabilities, *, changed: bool) -> Evidence:
    """``cct`` needs the CCT bit 0x04: per segment for an unchanged range, uniform for a
    new or moved one (TD-19-3, TD-19-4). The aggregate alone never suffices."""
    ctx = f"Segment {seg_id}: "
    bits: int | None
    source: Evidence | None
    if changed:
        bits, source = device.uniform_bits, "uniform"
        if bits is None:
            raise _unsupported(
                f"{ctx}cct on a new or moved range needs uniform capability evidence: "
                "info.leds.lc must equal the reported capability of every active segment."
            )
    else:
        segment = device.segment(seg_id)
        bits = segment.bits if segment is not None else None
        source = segment.source if segment is not None else None
        if bits is None or source is None:
            raise _unsupported(f"{ctx}cct needs per-segment capability evidence (seg[].lc).")
    if not has_cct(bits):
        raise _unsupported(f"{ctx}the range reports no CCT capability (bit 0x04).")
    return source


def option_keys(device: DeviceCapabilities, seg_id: int, *, is_new: bool) -> frozenset[str]:
    """Wire keys the fresh readback proves for a field-presence check (TD-19-5).

    An existing ID: its own segment. A new ID: the keys every active segment carries;
    an empty segment list proves nothing.
    """
    if not is_new:
        segment = device.segment(seg_id)
        return segment.wire_keys if segment is not None else frozenset()
    if not device.segments:
        return frozenset()
    keys = device.segments[0].wire_keys
    for segment in device.segments[1:]:
        keys &= segment.wire_keys
    return keys


def check_fields(
    seg_id: int,
    supplied: Mapping[str, object],
    device: DeviceCapabilities,
    keys: frozenset[str],
) -> list[tuple[str, Evidence]]:
    """Field-presence and matrix evidence for the supplied #19 option and 2D fields.

    ``supplied`` maps public field names to values (``None`` means omitted). Returns
    ``(field, evidence)`` for each supplied field; ``cct`` is checked by ``check_cct``.
    """
    ctx = f"Segment {seg_id}: "
    evidence: list[tuple[str, Evidence]] = []
    for name, wire in SEGMENT_FIELDS:
        if name == "cct" or supplied.get(name) is None:
            continue
        if (name, wire) in MATRIX_FIELDS:
            if device.matrix is None:
                raise _unsupported(
                    f"{ctx}{name} needs a 2D matrix; the device reports no info.leds.matrix."
                )
            evidence.append((name, "matrix"))
        elif wire not in keys:
            raise _unsupported(
                f"{ctx}{name} is settable only where the device reports '{wire}' for this "
                "segment (WLED 16 field); it is absent from the readback."
            )
        else:
            evidence.append((name, "field_present"))
    return evidence


def check_y_pair(seg_id: int, start_y: int | None, stop_y: int | None) -> None:
    if (start_y is None) != (stop_y is None):
        raise _invalid(f"Segment {seg_id}: a 2D bound change requires both start_y and stop_y.")
    if start_y is not None and stop_y is not None and start_y >= stop_y:
        raise _invalid(f"Segment {seg_id}: start_y must be strictly less than stop_y.")


# ---------------------------------------------------------------------------- geometry


@dataclass(frozen=True)
class Rect:
    """A segment's covered area: X ``[start, stop)`` and rows ``[start_y, stop_y)``.

    A 1D range and a trailing strip after the matrix use rows ``[0, 1)``, so overlap is
    plain index intersection there.
    """

    start: int
    stop: int
    start_y: int = 0
    stop_y: int = 1

    def overlaps(self, other: Rect) -> bool:
        return (
            self.start < other.stop
            and other.start < self.stop
            and self.start_y < other.stop_y
            and other.start_y < self.stop_y
        )


@dataclass(frozen=True)
class Geometry:
    """X/Y rules of one device (TD-19-7): 1D when ``matrix`` is None."""

    matrix: tuple[int, int] | None

    def is_trailing(self, start: int) -> bool:
        """A range starting at or after ``width * height`` is the trailing 1D strip."""
        return self.matrix is not None and start >= self.matrix[0] * self.matrix[1]

    def rect(self, start: int, stop: int, start_y: int | None, stop_y: int | None) -> Rect | None:
        """The covered area; ``None`` on a matrix when the rows are unknown."""
        if self.matrix is None or self.is_trailing(start):
            return Rect(start, stop)
        if start_y is None or stop_y is None:
            return None
        return Rect(start, stop, start_y, stop_y)

    def check_x(self, seg_id: int, start: int, stop: int) -> None:
        """On a matrix ``start``/``stop`` are columns: ``0 <= start < stop <= width``.

        The caller has already checked ``0 <= start < stop <= led_count``. Creating or
        moving a range into the trailing strip after the matrix is refused.
        """
        if self.matrix is None:
            return
        ctx = f"Segment {seg_id}: "
        if self.is_trailing(start):
            raise _unsupported(
                f"{ctx}creating or moving a trailing 1D strip after the matrix is not "
                "supported; it is read and preserved only."
            )
        width = self.matrix[0]
        if stop > width:
            raise _invalid(
                f"{ctx}on a matrix, start and stop are X columns and must satisfy "
                f"0 <= start < stop <= width ({width})."
            )

    def check_y(self, seg_id: int, start_y: int, stop_y: int) -> None:
        assert self.matrix is not None
        height = self.matrix[1]
        if not 0 <= start_y < stop_y <= height:
            raise _invalid(
                f"Segment {seg_id}: rows must satisfy 0 <= start_y < stop_y <= height ({height})."
            )


def overlapping_pairs(rects: Mapping[int, Rect]) -> list[tuple[int, int]]:
    """Every overlapping pair, ordered by ``(start, stop, id)`` like the stage-1 check."""
    ordered = sorted(rects.items(), key=lambda item: (item[1].start, item[1].stop, item[0]))
    pairs: list[tuple[int, int]] = []
    for index, (a_id, a_rect) in enumerate(ordered):
        for b_id, b_rect in ordered[index + 1 :]:
            if a_rect.overlaps(b_rect):
                pairs.append((a_id, b_id))
    return pairs


def overlap_plan(rects: Mapping[int, Rect]) -> dict[str, JsonValue]:
    """Plan fields of an ``allow_overlap`` request (ISSUE-19-DEC-001): every overlapping
    pair (lower ID first) and the render order, bottom to top (higher slot on top)."""
    pairs = sorted((min(a, b), max(a, b)) for a, b in overlapping_pairs(rects))
    return {
        "overlaps": [[a, b] for a, b in pairs],
        "render_order": [seg_id for seg_id in sorted(rects)],
    }


def evidence_entries(seg_id: int, items: list[tuple[str, Evidence]]) -> list[JsonValue]:
    return [{"id": seg_id, "field": name, "evidence": source} for name, source in items]
