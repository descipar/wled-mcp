"""Named physical lighting zones (issue #27, S3-ZONE-01 and S3-ZONE-02).

A zone is a named, reviewed mapping from a physical region to configured device IDs and
explicit LED ranges (``format`` ``wled-mcp.zone``, ``format_version`` 1). Nothing about
geometry is inferred from names, discovered or enrolled; the document states it and the
live layout is checked against it before every use.

This module is pure (no network, no filesystem): the strict document parser, lookup by ID
or name, the cross-zone warnings and ``resolve_part``, which maps one part onto the
*existing* active segments of a device. A zone resolves only when every zone LED belongs to
live segments that lie entirely inside the zone and tile it exactly (TD-27-5, TD-27-6);
anything else is refused with a stable reason and ``layout_change_required``, and the zone
tools never change geometry. Schema evolution follows TD-21-5 through ``formats``.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from pydantic import JsonValue

from wled_mcp.capabilities import derive_capabilities
from wled_mcp.client import ClientFailure
from wled_mcp.formats import check_format, decode_document, echo, invalid, is_int
from wled_mcp.groups import check_definition_id, check_id, check_name
from wled_mcp.models import ErrorCode
from wled_mcp.scenes import BindingFailure

ZONE_FORMAT: Final = "wled-mcp.zone"
ZONE_FORMAT_VERSION: Final = 1
SUPPORTED_ZONE_VERSIONS: Final = frozenset({ZONE_FORMAT_VERSION})
MAX_DOCUMENT_BYTES: Final = 64 * 1024
MAX_ZONES: Final = 100
MAX_PARTS: Final = 16
MAX_SPANS: Final = 16
MAX_LED_COUNT: Final = 65535
MAX_SEGMENT_ID: Final = 254
MAX_DESCRIPTION: Final = 256
MAX_CANDIDATES: Final = 10

ZONE_KEYS: Final = ("format", "format_version", "id", "name", "description", "parts")
REQUIRED_KEYS: Final = ("format", "format_version", "id", "name", "parts")
PART_KEYS: Final = frozenset({"device", "led_count", "spans"})
SPAN_KEYS: Final = frozenset({"start", "stop", "segment", "reversed"})

# Stable reasons carried in data; the error code stays an existing one (TD-27-8).
LAYOUT_REASONS: Final = frozenset({"span_unsegmented", "boundary_crossing", "span_gap"})


@dataclass(frozen=True)
class Span:
    start: int  # LED index range [start, stop), like a segment
    stop: int
    segment: int | None = None  # optional cross-check: must resolve to exactly this ID
    reversed: bool = False  # logical direction is high to low LED index (metadata only)


@dataclass(frozen=True)
class Part:
    device: str
    led_count: int  # the stale-topology anchor: what the installation looked like
    spans: tuple[Span, ...]  # file order is the zone's logical order


@dataclass(frozen=True)
class Zone:
    id: str
    name: str
    description: str | None
    parts: tuple[Part, ...]


# ------------------------------------------------------------------------------ parsing


def _check_int(value: object, low: int, high: int, where: str) -> int:
    if not is_int(value) or not low <= value <= high:  # type: ignore[operator]
        raise invalid(f"{where} must be an integer {low}-{high}.")
    assert isinstance(value, int)
    return value


def _parse_span(value: object, where: str, led_count: int) -> Span:
    if not isinstance(value, dict):
        raise invalid(f"{where} must be an object.")
    unknown = sorted(str(key) for key in value if key not in SPAN_KEYS)
    if unknown:
        raise invalid(f"{where}: unknown key {echo(unknown[0])}.")
    for key in ("start", "stop"):
        if key not in value:
            raise invalid(f"{where}: missing {key!r}.")
    start = _check_int(value["start"], 0, MAX_LED_COUNT - 1, f"{where}: 'start'")
    stop = _check_int(value["stop"], 1, MAX_LED_COUNT, f"{where}: 'stop'")
    if not start < stop <= led_count:
        raise invalid(f"{where}: the range must satisfy 0 <= start < stop <= led_count.")
    segment = (
        _check_int(value["segment"], 0, MAX_SEGMENT_ID, f"{where}: 'segment'")
        if "segment" in value
        else None
    )
    flow = value.get("reversed", False)
    if not isinstance(flow, bool):
        raise invalid(f"{where}: 'reversed' must be true or false.")
    return Span(start, stop, segment, flow)


def _parse_part(value: object, position: int) -> Part:
    where = f"Part {position}"
    if not isinstance(value, dict):
        raise invalid(f"{where} must be an object.")
    unknown = sorted(str(key) for key in value if key not in PART_KEYS)
    if unknown:
        raise invalid(f"{where}: unknown key {echo(unknown[0])}.")
    for key in PART_KEYS:
        if key not in value:
            raise invalid(f"{where}: missing {key!r}.")
    device = check_id(value["device"], f"device ID of part {position}")
    led_count = _check_int(value["led_count"], 1, MAX_LED_COUNT, f"{where}: 'led_count'")
    raw = value["spans"]
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_SPANS:
        raise invalid(f"{where}: 'spans' must list 1-{MAX_SPANS} entries.")
    spans = tuple(
        _parse_span(item, f"{where}, span {index}", led_count)
        for index, item in enumerate(raw, start=1)
    )
    ordered = sorted(enumerate(spans, start=1), key=lambda item: item[1].start)
    for (first, left), (second, right) in zip(ordered, ordered[1:], strict=False):
        if right.start < left.stop:
            raise invalid(
                f"{where}: spans {first} and {second} overlap (conflicting mapping); "
                "adjacent ranges are allowed."
            )
    return Part(device, led_count, spans)


def parse_zone(raw: str | bytes | dict[str, JsonValue]) -> Zone:
    """Strictly validate a zone document (JSON text, bytes or object); VALIDATION_ERROR."""
    document = decode_document(raw, "zone document", MAX_DOCUMENT_BYTES)
    if not isinstance(document, dict):
        raise invalid("A zone document must be a JSON object.")
    check_format(
        document,
        format_name=ZONE_FORMAT,
        label="zone",
        supported=SUPPORTED_ZONE_VERSIONS,
        current=ZONE_FORMAT_VERSION,
    )
    unknown = sorted(str(key) for key in document if key not in ZONE_KEYS)
    if unknown:
        raise invalid(f"Unknown zone key {echo(unknown[0])}.")
    missing = [key for key in REQUIRED_KEYS if key not in document]
    if missing:
        raise invalid(f"Missing zone key {missing[0]!r}.")
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
    raw_parts = document["parts"]
    if not isinstance(raw_parts, list) or not 1 <= len(raw_parts) <= MAX_PARTS:
        raise invalid(f"'parts' must list 1-{MAX_PARTS} entries.")
    parts = tuple(_parse_part(item, number) for number, item in enumerate(raw_parts, start=1))
    seen: set[str] = set()
    for number, part in enumerate(parts, start=1):
        if part.device in seen:
            raise invalid(
                f"Device {part.device!r} is mapped twice (part {number}); merge its ranges "
                "into the 'spans' of one part."
            )
        seen.add(part.device)
    return Zone(
        check_definition_id(document["id"], "zone ID"),
        check_name(document["name"], "zone name"),
        description,
        parts,
    )


def zone_document(zone: Zone) -> dict[str, JsonValue]:
    """The stored (and returned) document of a zone; ``parse_zone`` reads it back."""
    parts: list[JsonValue] = []
    for part in zone.parts:
        spans: list[JsonValue] = []
        for span in part.spans:
            entry: dict[str, JsonValue] = {"start": span.start, "stop": span.stop}
            if span.segment is not None:
                entry["segment"] = span.segment
            if span.reversed:
                entry["reversed"] = True
            spans.append(entry)
        parts.append({"device": part.device, "led_count": part.led_count, "spans": spans})
    document: dict[str, JsonValue] = {
        "format": ZONE_FORMAT,
        "format_version": ZONE_FORMAT_VERSION,
        "id": zone.id,
        "name": zone.name,
    }
    if zone.description is not None:
        document["description"] = zone.description
    document["parts"] = parts
    return document


def zone_summary(zone: Zone, configured: Collection[str]) -> dict[str, JsonValue]:
    return {
        "id": zone.id,
        "name": zone.name,
        "description": zone.description,
        "part_count": len(zone.parts),
        "span_count": sum(len(part.spans) for part in zone.parts),
        "devices": [
            {"device_id": part.device, "in_inventory": part.device in configured}
            for part in zone.parts
        ],
    }


# ------------------------------------------------------------------------------- lookup


class ZoneLookupFailure(ClientFailure):
    """A zone that cannot be selected: not stored, or its name is shared by several."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        candidates: list[JsonValue] | None = None,
        total: int = 0,
    ) -> None:
        super().__init__(code, message, reconciliation="Name the zone by its ID.")
        self.candidates = candidates
        self.total = total


def find_zone(zones: Sequence[Zone], query: str) -> tuple[Zone, list[str]]:
    """The zone with exactly this ID, else the one whose case-folded name equals it.

    An ID wins over a name (with a warning when another zone is named like it). Several
    zones with the same case-folded name are AMBIGUOUS_NAME with bounded candidates; the
    zone is then selected by ID. Returns the zone and warnings.
    """
    for zone in zones:
        if zone.id == query:
            others = [
                other.id
                for other in zones
                if other.id != zone.id and other.name.casefold() == query.casefold()
            ]
            warnings = (
                [f"The value is the ID of one zone and also the name of zone {others[0]!r}."]
                if others
                else []
            )
            return zone, warnings
    named = [zone for zone in zones if zone.name.casefold() == query.casefold()]
    if not named:
        raise ZoneLookupFailure("VALIDATION_ERROR", "No zone has this ID or name.")
    if len(named) > 1:
        candidates: list[JsonValue] = [
            {"id": zone.id, "name": zone.name} for zone in named[:MAX_CANDIDATES]
        ]
        raise ZoneLookupFailure(
            "AMBIGUOUS_NAME",
            f"The name matches {len(named)} zones; select one by its ID.",
            candidates,
            len(named),
        )
    return named[0], []


def document_warnings(zones: Sequence[Zone]) -> list[str]:
    """Cross-zone findings for the listing: name collisions and duplicate mappings."""
    warnings: list[str] = []
    by_name: dict[str, list[str]] = {}
    for zone in zones:
        by_name.setdefault(zone.name.casefold(), []).append(zone.id)
    for ids in by_name.values():
        if len(ids) > 1:
            warnings.append(
                f"Zones {', '.join(repr(i) for i in ids[:MAX_CANDIDATES])} share one name; "
                "select them by ID (ambiguous_name)."
            )
    seen: dict[tuple[str, int, int], str] = {}
    reported: set[tuple[str, str]] = set()
    for zone in zones:
        for part in zone.parts:
            for span in part.spans:
                key = (part.device, span.start, span.stop)
                first = seen.setdefault(key, zone.id)
                if first != zone.id and (first, zone.id) not in reported:
                    reported.add((first, zone.id))
                    warnings.append(
                        f"duplicate_mapping: zones {first!r} and {zone.id!r} map the same "
                        f"range on device {part.device!r}."
                    )
    return warnings


def overlapping_zones(zone: Zone, others: Sequence[Zone]) -> list[JsonValue]:
    """Other zones whose ranges intersect this one on a shared device (information only)."""
    found: list[JsonValue] = []
    for other in others:
        if other.id == zone.id:
            continue
        for part in zone.parts:
            for other_part in other.parts:
                if other_part.device != part.device:
                    continue
                if any(
                    a.start < b.stop and b.start < a.stop
                    for a in part.spans
                    for b in other_part.spans
                ):
                    found.append({"zone_id": other.id, "device_id": part.device})
    return found


# ---------------------------------------------------------------------------- resolution


class ZoneProblem(BindingFailure):
    """A zone that does not resolve on a live device; ``problem`` is the stable detail."""

    def __init__(
        self,
        reason: str,
        message: str,
        *,
        device: str,
        span: int | None = None,
        code: ErrorCode = "VALIDATION_ERROR",
        extra: Mapping[str, JsonValue] | None = None,
    ) -> None:
        problem: dict[str, JsonValue] = {
            "reason": reason,
            "device_id": device,
            "span": span,
            "layout_change_required": reason in LAYOUT_REASONS,
            "message": message,
        }
        if extra:
            problem.update(extra)
        super().__init__(
            code,
            message,
            problem,
            reconciliation=(
                "Review and apply a layout change explicitly (wled_replace_layout), then "
                "preview the zone again. Nothing was written."
                if reason in LAYOUT_REASONS
                else "Correct the zone or the device, then preview the zone again. Nothing "
                "was written."
            ),
        )
        self.reason = reason


@dataclass(frozen=True)
class LiveSegment:
    id: int
    start: int
    stop: int


@dataclass(frozen=True)
class ResolvedSpan:
    index: int  # 1-based position in the zone part
    span: Span
    segments: tuple[LiveSegment, ...]  # logical order: descending LED order when reversed


@dataclass(frozen=True)
class ResolvedPart:
    device: str
    led_count: int
    spans: tuple[ResolvedSpan, ...]
    warnings: tuple[str, ...]

    @property
    def segment_ids(self) -> tuple[int, ...]:
        return tuple(sorted(seg.id for item in self.spans for seg in item.segments))

    def signature(self) -> tuple[tuple[int, tuple[tuple[int, int, int], ...]], ...]:
        return tuple(
            (item.index, tuple((s.id, s.start, s.stop) for s in item.segments))
            for item in self.spans
        )

    def view(self) -> dict[str, JsonValue]:
        spans: list[JsonValue] = [
            {
                "span": item.index,
                "start": item.span.start,
                "stop": item.span.stop,
                "flow_reversed": item.span.reversed,
                "segments": [
                    {"id": seg.id, "start": seg.start, "stop": seg.stop} for seg in item.segments
                ],
            }
            for item in self.spans
        ]
        ids: list[JsonValue] = [*self.segment_ids]
        return {
            "led_count": self.led_count,
            "segment_ids": ids,
            "spans": spans,
            "layout_changes": False,
        }


def _live_segments(state_view: Mapping[str, JsonValue]) -> list[LiveSegment]:
    raw = state_view.get("segments")
    found: list[LiveSegment] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            seg_id, start, stop = item.get("id"), item.get("start"), item.get("stop")
            if is_int(seg_id) and is_int(start) and is_int(stop) and stop > start:  # type: ignore[operator]
                assert isinstance(seg_id, int) and isinstance(start, int) and isinstance(stop, int)
                found.append(LiveSegment(seg_id, start, stop))
    return sorted(found, key=lambda seg: (seg.start, seg.id))


def _ranges(segments: Sequence[LiveSegment]) -> list[JsonValue]:
    return [{"id": s.id, "start": s.start, "stop": s.stop} for s in segments]


def resolve_part(
    part: Part,
    state_view: Mapping[str, JsonValue],
    capabilities: Mapping[str, JsonValue],
    raw_info: Mapping[str, JsonValue],
    raw_state: Mapping[str, JsonValue],
) -> ResolvedPart:
    """Map a part onto the live active segments; raises ``ZoneProblem`` before any write.

    Order of checks (packet section 4): live LED count against the zone's ``led_count``
    (``topology_stale``), a matrix device (1D only), then per span: no segment at all
    (``span_unsegmented``), a segment that is not fully inside the span
    (``boundary_crossing``: straddling the edge, larger than the zone or overlapping from
    outside), uncovered LEDs (``span_gap``) and a ``segment`` hint that names another set
    (``segment_mismatch``).
    """
    device = part.device
    live_count = capabilities.get("led_count")
    if not is_int(live_count):
        raise ZoneProblem(
            "led_count_unknown",
            "The device does not report its LED count; the zone cannot be checked.",
            device=device,
            code="UNSUPPORTED_CAPABILITY",
        )
    if live_count != part.led_count:
        raise ZoneProblem(
            "topology_stale",
            f"The device reports {live_count} LEDs but the zone was written for "
            f"{part.led_count}; re-author the zone or fix the device.",
            device=device,
            extra={"expected_led_count": part.led_count, "live_led_count": live_count},
        )
    if derive_capabilities(raw_state, raw_info).matrix is not None:
        raise ZoneProblem(
            "matrix_unsupported",
            "Zones are one-dimensional; this device is configured as a matrix.",
            device=device,
            code="UNSUPPORTED_CAPABILITY",
        )
    live = _live_segments(state_view)
    resolved: list[ResolvedSpan] = []
    warnings: list[str] = []
    for index, span in enumerate(part.spans, start=1):
        where = f"span {index} [{span.start},{span.stop})"
        hint: dict[str, JsonValue] = {"span": {"start": span.start, "stop": span.stop}}
        touching = [s for s in live if s.start < span.stop and s.stop > span.start]
        if not touching:
            raise ZoneProblem(
                "span_unsegmented",
                f"{where}: no active segment covers these LEDs; a zone apply cannot light "
                "them without an explicit layout change.",
                device=device,
                span=index,
                extra={"layout_hint": hint},
            )
        outside = [s for s in touching if s.start < span.start or s.stop > span.stop]
        if outside:
            first = outside[0]
            raise ZoneProblem(
                "boundary_crossing",
                f"{where}: segment {first.id} [{first.start},{first.stop}) is not inside "
                "the zone; applying would change LEDs outside it. An explicit layout "
                "change is required.",
                device=device,
                span=index,
                extra={"layout_hint": {**hint, "segments": _ranges(outside)}},
            )
        gap_start = _first_gap(touching, span)
        if gap_start is not None:
            raise ZoneProblem(
                "span_gap",
                f"{where}: LEDs from {gap_start} on are covered by no active segment; an "
                "explicit layout change is required.",
                device=device,
                span=index,
                extra={"layout_hint": {**hint, "uncovered_from": gap_start}},
            )
        if span.segment is not None and {s.id for s in touching} != {span.segment}:
            raise ZoneProblem(
                "segment_mismatch",
                f"{where}: the zone names segment {span.segment}, but the range is covered "
                f"by segments {sorted(s.id for s in touching)}.",
                device=device,
                span=index,
                extra={"expected_segment": span.segment},
            )
        for left, right in zip(touching, touching[1:], strict=False):
            if right.start < left.stop:
                warnings.append(
                    f"{where}: segments {left.id} and {right.id} overlap in the live layout "
                    "(not caused by the zone)."
                )
        ordered = tuple(sorted(touching, key=lambda s: s.start, reverse=span.reversed))
        resolved.append(ResolvedSpan(index, span, ordered))
    seen: set[int] = set()
    for item in resolved:
        for seg in item.segments:
            assert seg.id not in seen  # spans of a part never overlap
            seen.add(seg.id)
    return ResolvedPart(device, part.led_count, tuple(resolved), tuple(warnings))


def _first_gap(touching: Sequence[LiveSegment], span: Span) -> int | None:
    """The first LED of the span that no segment covers; segments are sorted by start."""
    cursor = span.start
    for seg in touching:
        if seg.start > cursor:
            return cursor
        cursor = max(cursor, seg.stop)
    return cursor if cursor < span.stop else None
