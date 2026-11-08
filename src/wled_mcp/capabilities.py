"""Pure device capability model (issue #19, ISSUE-18-DEC-002, ISSUE-19-DEC-003 TD-19-9).

One place derives every capability fact the read and write paths use, from the same
fresh ``/json/state`` and ``/json/info`` payloads; it never calls the network and never
decides by product name or firmware version (DEC-020, TD-21-6).

WLED 16 segment evidence (ISSUE-19-DEC-003, source pin v16.0.1 29b389d):
``serializeSegment`` emits ``seg[].lc`` per segment; ``serializeInfo`` keeps the
deprecated position-aligned ``info.leds.seglc`` and the aggregate ``info.leds.lc``, and
reports ``info.leds.matrix {w, h}`` only on a 2D build with a configured matrix.

Per-segment capability evidence (TD-19-3): ``state.seg[].lc`` (source ``state_lc``),
else the position-aligned ``info.leds.seglc`` entry (source ``info_seglc``), else none.
Unknown capability is ``None``, never ``0``/``False``.

Write side (#19 second pull request): ``wled_patch_segments``, ``wled_replace_layout``
and ``wled_store_preset`` read per-segment capability from ``derive_capabilities`` (the
chain above) instead of the stage-1 ``seglc_bits``. ``aggregate_bits`` stays the
fallback for an existing unchanged range (ISSUE-6-DEC-003); new or moved ranges use
``DeviceCapabilities.uniform_bits`` (TD-19-4). ``seglc_bits`` is kept for reference only.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal

from pydantic import JsonValue

# Capability bits per the pinned firmware source (FX.h SEG_CAPABILITY_*).
CAP_RGB: Final = 0x01
CAP_WHITE: Final = 0x02
CAP_CCT: Final = 0x04
CAP_MAX: Final = 0xFF  # ``seg[].lc`` is a uint8_t in the pinned source

CapabilitySource = Literal["state_lc", "info_seglc"]


def _is_int(value: object) -> bool:
    return type(value) is int


def _leds(info: Mapping[str, JsonValue]) -> Mapping[str, JsonValue]:
    leds = info.get("leds")
    return leds if isinstance(leds, dict) else {}


def valid_bits(value: object) -> int | None:
    """A capability bitfield is an integer 0-255 (booleans rejected); else None."""
    if _is_int(value) and 0 <= value <= CAP_MAX:  # type: ignore[operator]
        assert isinstance(value, int)
        return value
    return None


# ---------------------------------------------------------------------------- matrix


def parse_matrix(value: object) -> tuple[int, int] | None:
    """A reported 2D size ``{w, h}`` (both positive integers), else None."""
    if not isinstance(value, dict) or set(value) - {"w", "h"}:
        return None
    width, height = value.get("w"), value.get("h")
    if _is_int(width) and _is_int(height) and width > 0 and height > 0:  # type: ignore[operator]
        assert isinstance(width, int) and isinstance(height, int)
        return width, height
    return None


def matrix_of(info: Mapping[str, JsonValue]) -> tuple[int, int] | None:
    """The device matrix from ``info.leds.matrix``; None when absent or malformed."""
    return parse_matrix(_leds(info).get("matrix"))


# ---------------------------------------------------------------------------- color helpers


def is_rgb_only(cap: int) -> bool:
    return (cap & (CAP_RGB | CAP_WHITE | CAP_CCT)) == CAP_RGB


def is_rgbw(cap: int) -> bool:
    return (cap & (CAP_RGB | CAP_WHITE)) == (CAP_RGB | CAP_WHITE)


def has_cct(cap: int) -> bool:
    return bool(cap & CAP_CCT)


def required_color_channels(cap: int) -> Literal[3, 4] | None:
    """3 for a proven RGB-only range, 4 for RGBW, else None (no supported width)."""
    if is_rgb_only(cap):
        return 3
    if is_rgbw(cap):
        return 4
    return None


def is_white_only(cap: int) -> bool:
    """A white channel without RGB (with or without the CCT bit)."""
    return (cap & (CAP_RGB | CAP_WHITE)) == CAP_WHITE


def color_channels(cap: int) -> Literal[3, 4] | None:
    """Channel width of a color slot for #19 writes (TD-19-3).

    Four channels need the white bit (RGBW, or white-only with RGB 0); three channels
    need RGB without white. The CCT bit does not change the width. ``None`` when the
    range has neither RGB nor white (for example an on/off bus).
    """
    if cap & CAP_WHITE:
        return 4
    if cap & CAP_RGB:
        return 3
    return None


def color_flags(cap: int) -> dict[str, JsonValue]:
    return {"rgb": bool(cap & CAP_RGB), "white": bool(cap & CAP_WHITE), "cct": has_cct(cap)}


# ---------------------------------------------------------------------------- stage-1 lookups


def aggregate_bits(info: Mapping[str, JsonValue]) -> int | None:
    """``info.leds.lc`` when it is an integer (booleans rejected), else None."""
    lc = _leds(info).get("lc")
    return lc if isinstance(lc, int) and _is_int(lc) else None


def aggregate_cct(info: Mapping[str, JsonValue]) -> bool | None:
    """Whether the aggregate ``info.leds.lc`` carries the CCT bit; None when unreported."""
    lc = aggregate_bits(info)
    return None if lc is None else has_cct(lc)


def seglc_bits(
    info: Mapping[str, JsonValue], seg_id: int, segments: Sequence[JsonValue]
) -> int | None:
    """Return the capability bitfield for ``seg_id`` from ``info.leds.seglc``.

    ``seglc`` is used only when its length equals the segment list and the
    target ID resolves to a position in that list. Otherwise ``None`` means
    no per-segment evidence; the caller may fall back to ``info.leds.lc`` for
    an *unchanged* range only (``ISSUE-6-DEC-003``).
    """
    seglc = _leds(info).get("seglc")
    if not isinstance(seglc, list) or len(seglc) != len(segments):
        return None
    for index, seg in enumerate(segments):
        if isinstance(seg, dict) and seg.get("id") == seg_id:
            value = seglc[index]
            if isinstance(value, int) and not isinstance(value, bool):
                return value
            return None
    return None


# ---------------------------------------------------------------------------- full model


@dataclass(frozen=True)
class SegmentCapability:
    """Capability evidence for one active segment of a fresh state read."""

    id: int
    bits: int | None
    source: CapabilitySource | None
    start: int | None
    stop: int | None
    start_y: int | None
    stop_y: int | None
    wire_keys: frozenset[str]


@dataclass(frozen=True)
class DeviceCapabilities:
    """Device-level capability facts from one fresh state + info pair."""

    led_count: int | None
    max_segments: int | None
    aggregate_bits: int | None
    matrix: tuple[int, int] | None
    segments: tuple[SegmentCapability, ...]
    # ``info.leds.lc`` when every listed segment reports exactly that value (TD-19-4);
    # ``None`` for an empty segment list, which is no evidence for a new range.
    uniform_bits: int | None

    def segment(self, seg_id: int) -> SegmentCapability | None:
        for seg in self.segments:
            if seg.id == seg_id:
                return seg
        return None

    @property
    def per_segment_reported(self) -> bool:
        """True when every segment has per-segment evidence (an empty list counts)."""
        return all(seg.bits is not None for seg in self.segments)


def aligned_seglc(info: Mapping[str, JsonValue], count: int) -> list[int] | None:
    """``info.leds.seglc`` when it holds exactly ``count`` capability bitfields.

    Each entry must be a ``valid_bits`` value (integer 0-255, booleans rejected), the same
    range as ``state.seg[].lc``: both are the firmware's uint8_t ``getLightCapabilities()``.
    """
    seglc = _leds(info).get("seglc")
    if not isinstance(seglc, list) or len(seglc) != count:
        return None
    values = [valid_bits(v) for v in seglc]
    if any(v is None for v in values):
        return None
    return [v for v in values if v is not None]


def _count(leds: Mapping[str, JsonValue], key: str) -> int | None:
    value = leds.get(key)
    return value if isinstance(value, int) and _is_int(value) and value >= 0 else None


def derive_capabilities(
    state: Mapping[str, JsonValue], info: Mapping[str, JsonValue]
) -> DeviceCapabilities:
    """Derive capability facts; tolerant of malformed optional fields (they give None).

    Segments without an integer ``id`` are skipped; required-shape validation belongs to
    ``readmodels.normalize_state``.
    """
    raw = state.get("seg")
    segs = [s for s in raw if isinstance(s, dict)] if isinstance(raw, list) else []
    seglc = aligned_seglc(info, len(segs))
    segments: list[SegmentCapability] = []
    for index, seg in enumerate(segs):
        seg_id = seg.get("id")
        if not isinstance(seg_id, int) or not _is_int(seg_id):
            continue
        bits = valid_bits(seg.get("lc"))
        source: CapabilitySource | None = "state_lc" if bits is not None else None
        if bits is None and seglc is not None:
            bits, source = seglc[index], "info_seglc"

        def coord(key: str, seg: dict[str, JsonValue] = seg) -> int | None:
            value = seg.get(key)
            return value if isinstance(value, int) and _is_int(value) and value >= 0 else None

        segments.append(
            SegmentCapability(
                id=seg_id,
                bits=bits,
                source=source,
                start=coord("start"),
                stop=coord("stop"),
                start_y=coord("startY"),
                stop_y=coord("stopY"),
                wire_keys=frozenset(seg),
            )
        )
    leds = _leds(info)
    aggregate = aggregate_bits(info)
    # An empty segment list proves nothing about any range, so it has no uniform bits.
    uniform = (
        aggregate
        if aggregate is not None and segments and all(seg.bits == aggregate for seg in segments)
        else None
    )
    return DeviceCapabilities(
        led_count=_count(leds, "count"),
        max_segments=_count(leds, "maxseg"),
        aggregate_bits=aggregate,
        matrix=matrix_of(info),
        segments=tuple(segments),
        uniform_bits=uniform,
    )
