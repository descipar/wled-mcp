"""Pure, deterministic, bounded SVG renderer of 1D segment layouts (issue #29).

The renderer takes plain dataclasses and returns the SVG text plus a small structured
summary. It performs no I/O, reads no clock, imports nothing from the resource, client or
server layer and holds no write function, so it can be reviewed and tested without any
device mock (TD-29-13).

Safety rules (TD-29-9): the output uses only the elements ``svg``, ``title``, ``desc``,
``g``, ``rect``, ``line`` and ``text``. Every string that does not come from this module
(segment names, device and zone names, notes) passes through :func:`clean_text` and is
escaped; it is only ever placed in element content, never in an attribute. Numbers are
formatted from integers or clamped floats, colours from validated hex digits. The only
URL-shaped string is the SVG namespace; no attribute or reference carries a URL and foreign
text is inert element content.

Bounds (TD-29-3): fixed ``viewBox`` width, no element per LED, at most
:data:`MAX_LANES` segment lanes, :data:`MAX_COLOUR_RECTS` colour rectangles and
:data:`MAX_ZONE_BANDS` zone bands, truncated labels. Whatever exceeds a bound is reported in
text and in the summary, never silently dropped.

Nothing here simulates an effect or claims calibrated colour: the fill is an approximation
of the first colour slot (or of sampled live colours) and the legend says so.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal
from xml.sax.saxutils import escape

from pydantic import JsonValue

MAX_SVG_BYTES = 48 * 1024
VIEWBOX_WIDTH = 1000
MAX_LANES = 64
MAX_COLOUR_RECTS = 256
MAX_ZONE_BANDS = 16
NAME_LIMIT = 24
ZONE_NAME_LIMIT = 32
NOTE_LIMIT = 150
MAX_NOTES = 16
UNIT_TICK_MAX_LEDS = 120

NAMESPACE = "http://www.w3.org/2000/svg"
RANGE_SEMANTICS = "[start,stop) exclusive stop"

LEFT = 170
RIGHT = 20
PLOT_WIDTH = VIEWBOX_WIDTH - LEFT - RIGHT
LANE_HEIGHT = 18
ROW_HEIGHT = 32
NEUTRAL = "#bdbdbd"
GREY_CCT = "#9e9e9e"
OPACITY_FLOOR = 0.25
HEX = re.compile(r"[0-9A-Fa-f]{6}")

LIMITS = (
    "1D only; no matrix or 2D layout is drawn",
    "colours are approximations, not calibrated colour",
    "effects, palettes and animation are not simulated",
    "not a firmware simulator; effect and palette values are not validated by the preview",
)

Source = Literal["observed", "proposed"]


# --------------------------------------------------------------------------------- model


@dataclass(frozen=True)
class LiveRun:
    """``sample_count`` consecutive samples of one colour starting at ``first_led``."""

    first_led: int
    sample_count: int
    rgb: str  # six hex digits


@dataclass(frozen=True)
class LaneModel:
    id: int
    start: int
    stop: int
    name: str | None = None
    on: bool | None = None
    brightness: int | None = None  # effective brightness, 0 when the segment is off
    colors: tuple[tuple[int, ...], ...] | None = None  # colour slots, 3 or 4 channels
    color_capability: Mapping[str, JsonValue] | None = None  # {"rgb", "white", "cct"}
    cct: int | None = None
    effect_id: int | None = None
    change: str | None = None  # proposed layouts: "new", "changed" or "unchanged"
    live_runs: tuple[LiveRun, ...] | None = None  # None: no live drawing for this lane
    live_status: str | None = None


@dataclass(frozen=True)
class ZoneModel:
    id: str
    name: str
    spans: tuple[tuple[int, int, bool], ...]  # (start, stop, reversed)
    status: Literal["drawn", "topology_stale"] = "drawn"


@dataclass(frozen=True)
class LiveModel:
    status: str
    sampling_step: int


@dataclass(frozen=True)
class PreviewModel:
    source: Source
    device: str
    led_count: int | None
    lanes: tuple[LaneModel, ...]
    master_on: bool | None = None
    master_brightness: int | None = None
    zone: ZoneModel | None = None
    live: LiveModel | None = None
    removed_segment_ids: tuple[int, ...] = ()
    notes: tuple[str, ...] = field(default=())


@dataclass(frozen=True)
class Rendered:
    svg: str
    summary: dict[str, JsonValue]


# -------------------------------------------------------------------------------- helpers


def intervals(ranges: list[tuple[int, int]]) -> tuple[list[JsonValue], list[JsonValue]]:
    """Sweep bounded segment ranges; never allocate per physical LED."""
    events: dict[int, int] = {}
    for start, stop in ranges:
        events[start] = events.get(start, 0) + 1
        events[stop] = events.get(stop, 0) - 1
    gaps: list[JsonValue] = []
    overlaps: list[JsonValue] = []
    count, previous = 0, 0
    for point in sorted(events):
        if point > previous:
            if count == 0:
                gaps.append({"start": previous, "stop": point})
            elif count > 1:
                overlaps.append({"start": previous, "stop": point})
        count += events[point]
        previous = point
    return gaps, overlaps


def clean_text(value: object, limit: int) -> str:
    """Text that is safe in XML element content: the one sanitiser for every foreign string.

    Control characters become spaces, format, surrogate and unassigned code points (which
    include the bidirectional controls and the non-characters) are dropped, whitespace is
    collapsed and the result is truncated to ``limit`` characters with an ellipsis. The
    result is not yet escaped; :func:`_text` does that when it is placed in the document.
    """
    out: list[str] = []
    for char in str(value):
        category = unicodedata.category(char)
        if category == "Cc":
            out.append(" ")
        elif category in {"Cf", "Cs", "Cn"}:
            continue
        else:
            out.append(char)
    text = " ".join("".join(out).split())
    return text if len(text) <= limit else text[: max(limit - 1, 0)] + "…"


def _n(value: float) -> str:
    """A deterministic short number for an attribute; only ever fed computed numbers."""
    text = f"{value:.1f}"
    return text[:-2] if text.endswith(".0") else text


def _hex(red: int, green: int, blue: int) -> str:
    return f"#{red:02x}{green:02x}{blue:02x}"


def _valid_slot(slot: tuple[int, ...]) -> bool:
    return len(slot) in (3, 4) and all(
        isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 255 for c in slot
    )


def _nice_step(total: int) -> int:
    """The smallest 1, 2 or 5 times a power of ten that is at least ``total / 9``."""
    target = max(1, -(-total // 9))
    power = 1
    while True:
        for factor in (1, 2, 5):
            if factor * power >= target:
                return factor * power
        power *= 10


@dataclass(frozen=True)
class _Paint:
    fill: str | None  # None: outline only
    mode: str
    opacity: float | None
    notes: tuple[str, ...]


def _paint(lane: LaneModel) -> _Paint:
    opacity = (
        None
        if lane.brightness is None
        else max(OPACITY_FLOOR, round(min(max(lane.brightness, 0), 255) / 255, 2))
    )
    if lane.on is False or lane.brightness == 0:
        return _Paint(None, "off", None, ("off",))
    capability = lane.color_capability
    if (
        capability is not None
        and capability.get("cct") is True
        and capability.get("rgb") is not True
    ):
        note = "cct not rendered" if lane.cct is None else f"cct {lane.cct} not rendered"
        return _Paint(GREY_CCT, "cct_not_rendered", opacity, (note,))
    slot = lane.colors[0] if lane.colors else None
    if slot is None or not _valid_slot(slot):
        return _Paint(NEUTRAL, "unknown", opacity, ("colour unknown",))
    if len(slot) == 4:
        white = slot[3]
        rgb = [min(255, channel + white) for channel in slot[:3]]
        return _Paint(_hex(*rgb), "rgbw_white_added", opacity, ("white added",))
    return _Paint(_hex(*slot), "rgb", opacity, ())


# ------------------------------------------------------------------------------- renderer


class _Canvas:
    """Collects SVG fragments; every method formats numbers and escapes text itself."""

    def __init__(self, total: int) -> None:
        self.total = total
        self.parts: list[str] = []

    def x(self, led: int) -> float:
        return LEFT + led * PLOT_WIDTH / self.total

    def rect(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        *,
        fill: str | None = None,
        opacity: float | None = None,
        stroke: str | None = None,
        dash: bool = False,
    ) -> None:
        attrs = f'x="{_n(x)}" y="{_n(y)}" width="{_n(max(width, 0.5))}" height="{_n(height)}"'
        attrs += f' fill="{fill if fill is not None else "none"}"'
        if opacity is not None and opacity < 1:
            attrs += f' fill-opacity="{opacity:.2f}"'
        if stroke is not None:
            attrs += f' stroke="{stroke}"'
        if dash:
            attrs += ' stroke-dasharray="3 2"'
        self.parts.append(f"<rect {attrs}/>")

    def line(self, x1: float, y1: float, x2: float, y2: float, stroke: str | None = None) -> None:
        extra = f' stroke="{stroke}"' if stroke else ""
        self.parts.append(f'<line x1="{_n(x1)}" y1="{_n(y1)}" x2="{_n(x2)}" y2="{_n(y2)}"{extra}/>')

    def text(
        self, x: float, y: float, content: str, *, size: int | None = None, middle: bool = False
    ) -> None:
        attrs = f'x="{_n(x)}" y="{_n(y)}"'
        if size is not None:
            attrs += f' font-size="{size}"'
        if middle:
            attrs += ' text-anchor="middle"'
        self.parts.append(f"<text {attrs}>{escape(content)}</text>")


def _range_text(start: int, stop: int) -> str:
    return f"[{start},{stop})"


def _pairs(items: list[JsonValue]) -> list[tuple[int, int]]:
    """The (start, stop) pairs of ``intervals`` results; both are always integers."""
    pairs: list[tuple[int, int]] = []
    for item in items:
        assert isinstance(item, dict)
        start, stop = item["start"], item["stop"]
        assert isinstance(start, int) and isinstance(stop, int)
        pairs.append((start, stop))
    return pairs


def _ranges_text(items: list[JsonValue], limit: int = 6) -> str:
    pairs = _pairs(items)
    if not pairs:
        return "none"
    more = f" (+{len(pairs) - limit} more)" if len(pairs) > limit else ""
    return " ".join(_range_text(a, b) for a, b in pairs[:limit]) + more


def _merge_runs(lane: LaneModel, total: int, step: int) -> list[tuple[int, int, str]]:
    """Live runs clipped to the lane and the scale, adjacent equal colours merged."""
    merged: list[tuple[int, int, str]] = []
    for run in lane.live_runs or ():
        if not HEX.fullmatch(run.rgb) or run.sample_count < 1 or run.first_led < 0:
            continue
        begin = max(run.first_led, lane.start)
        end = min(run.first_led + run.sample_count * step, lane.stop, total)
        if end <= begin:
            continue
        colour = "#" + run.rgb.lower()
        if merged and merged[-1][1] == begin and merged[-1][2] == colour:
            merged[-1] = (merged[-1][0], end, colour)
        else:
            merged.append((begin, end, colour))
    return merged


def render_svg(model: PreviewModel) -> Rendered:  # noqa: C901 - one linear layout pass
    valid = sorted((lane for lane in model.lanes if lane.stop > lane.start), key=lambda s: s.id)
    drawn = valid[:MAX_LANES]
    omitted = len(valid) - len(drawn)
    known = model.led_count is not None and model.led_count > 0
    highest = max((lane.stop for lane in drawn), default=1)
    total = model.led_count if known and model.led_count is not None else max(highest, 1)
    led_source = "info" if known else "unknown"
    live = model.live if model.live is not None and model.live.status != "unavailable" else None
    step = max(live.sampling_step, 1) if live is not None else 1

    notes: list[str] = []
    approximations: list[str] = []

    def flag(name: str) -> None:
        if name not in approximations:
            approximations.append(name)

    canvas = _Canvas(total)
    title_device = clean_text(model.device, 64) or "device"
    label_source = (
        "observed layout" if model.source == "observed" else "proposed layout (not applied)"
    )
    if known:
        count_text = f"{total} LEDs"
    else:
        count_text = f"LED count unknown (scale from highest segment end {total})"
        notes.append("LED count unknown; the scale uses the highest drawn segment end.")
    per_led = PLOT_WIDTH / total
    scale_text = (
        f"1 LED = {per_led:.1f} px"
        if total <= PLOT_WIDTH
        else f"1 px = {total / PLOT_WIDTH:.1f} LEDs"
    )
    master = ""
    if model.master_on is not None and model.master_brightness is not None:
        master = (
            f" · master {'on' if model.master_on else 'off'} bri {model.master_brightness}"
            " (shown, not applied)"
        )
    header: list[str] = [
        f"{label_source}: {title_device} · {count_text}",
        f"ranges are [start,stop), stop exclusive · scale {scale_text}{master}",
    ]

    y = 20 + 14 * len(header) + 8

    # Zone bands (#27 overlay): a label and explicit ranges only, never a tiling claim.
    zone_summary: JsonValue = None
    if model.zone is not None:
        zone = model.zone
        zone_name = clean_text(zone.name, ZONE_NAME_LIMIT)
        bands = zone.spans[:MAX_ZONE_BANDS] if zone.status == "drawn" else ()
        canvas.text(4, y + 12, f"zone {zone_name}", size=10)
        shown: list[JsonValue] = []
        for begin, end, backwards in bands:
            begin, end = max(begin, 0), min(end, total)
            if end > begin:
                canvas.rect(
                    canvas.x(begin),
                    y,
                    canvas.x(end) - canvas.x(begin),
                    14,
                    fill="#3b6fd4",
                    opacity=0.3,
                    stroke="#3b6fd4",
                )
            shown.append({"start": begin, "stop": end, "reversed": backwards})
        if zone.status == "drawn":
            spans_text = ", ".join(
                f"{_range_text(b, e)}{' reversed' if r else ''}"
                for b, e, r in zone.spans[:MAX_ZONE_BANDS]
            )
            notes.append(f"zone '{zone_name}': {spans_text} (stored ranges; alignment not checked)")
        else:
            notes.append(
                f"zone '{zone_name}' not drawn: its stored LED count differs (topology_stale)."
            )
        zone_summary = {
            "id": clean_text(zone.id, 64),
            "name": zone_name,
            "status": zone.status,
            "spans": shown,
        }
        y += 22

    # Lanes ----------------------------------------------------------------------------
    extra_rects = MAX_COLOUR_RECTS - len(drawn)
    lane_summary: list[JsonValue] = []
    ranges: list[tuple[int, int]] = []
    clipped_any = False
    unknown_colour = False
    effects_present = False
    live_lanes = 0
    state_lanes = 0
    if not drawn:
        notes.append("No active segments.")
    for lane in drawn:
        paint = _paint(lane)
        lane_notes = list(paint.notes)
        mode = paint.mode
        colour = paint.fill
        begin, end = lane.start, min(lane.stop, total)
        label = clean_text(lane.name, NAME_LIMIT) if lane.name is not None else ""
        canvas.rect(LEFT, y, PLOT_WIDTH, LANE_HEIGHT, fill="none", stroke="#bbbbbb")
        if lane.stop > total or lane.start >= total:
            clipped_any = True
            lane_notes.append("range outside LED count")
            canvas.line(LEFT + PLOT_WIDTH, y - 2, LEFT + PLOT_WIDTH, y + LANE_HEIGHT + 2, "#c0392b")
        if end > begin and begin < total:
            ranges.append((begin, end))
        if lane.effect_id not in (None, 0):
            effects_present = True
        if mode == "unknown":
            unknown_colour = True
        if mode == "rgbw_white_added":
            flag("rgbw_white_added")
        if mode == "cct_not_rendered":
            flag("cct_not_rendered")

        runs = (
            _merge_runs(lane, total, step)
            if live is not None and lane.live_runs is not None
            else None
        )
        if runs is None:
            state_lanes += 1
        else:
            live_lanes += 1
        if runs is not None:
            allowed = 1 + extra_rects
            kept = runs[:allowed]
            extra_rects -= max(len(kept) - 1, 0)
            for run_begin, run_end, run_colour in kept:
                canvas.rect(
                    canvas.x(run_begin),
                    y,
                    canvas.x(run_end) - canvas.x(run_begin),
                    LANE_HEIGHT,
                    fill=run_colour,
                )
            if len(runs) > len(kept):
                lane_notes.append(f"{len(runs) - len(kept)} more runs not drawn")
            if not kept:
                canvas.rect(
                    canvas.x(begin) if begin < total else LEFT + PLOT_WIDTH,
                    y,
                    canvas.x(end) - canvas.x(begin) if end > begin else 0.5,
                    LANE_HEIGHT,
                    stroke="#666666",
                    dash=True,
                )
            if lane.live_status and lane.live_status != "sampled":
                lane_notes.append(f"live {clean_text(lane.live_status, 32)}")
            mode = "live_samples" if kept else mode
            colour = kept[0][2] if kept else None
            if kept:
                flag("live_rgb_brightness_scaled")
        elif end > begin and begin < total:
            if paint.fill is None:
                canvas.rect(
                    canvas.x(begin),
                    y,
                    canvas.x(end) - canvas.x(begin),
                    LANE_HEIGHT,
                    stroke="#666666",
                    dash=True,
                )
            else:
                canvas.rect(
                    canvas.x(begin),
                    y,
                    canvas.x(end) - canvas.x(begin),
                    LANE_HEIGHT,
                    fill=paint.fill,
                    opacity=paint.opacity,
                )
        if lane.change:
            lane_notes.append(lane.change)
        if lane.brightness is not None:
            lane_notes.insert(0, f"bri {lane.brightness}")
        canvas.text(4, y + 12, f"{lane.id} {label}".rstrip(), size=10)
        canvas.text(
            4, y + 26, " · ".join([_range_text(lane.start, lane.stop), *lane_notes]), size=9
        )
        entry: dict[str, JsonValue] = {
            "id": lane.id,
            "start": lane.start,
            "stop": lane.stop,
            "label": label,
            "colour": colour,
            "colour_mode": mode,
            "notes": list(lane_notes),
        }
        if lane.change is not None:
            entry["change"] = lane.change
        lane_summary.append(entry)
        y += ROW_HEIGHT

    if omitted:
        notes.append(
            f"{len(drawn)} of {len(valid)} segments drawn; {omitted} more omitted "
            f"(first {MAX_LANES} by ID)."
        )
    if clipped_any:
        notes.append("Segment ranges beyond the LED count are drawn clipped and marked.")

    # Coverage: gaps and overlaps of the drawn ranges (never inferred wiring) -------------
    gaps, overlaps = intervals(ranges)
    if known:
        if ranges:
            last = max(stop for _, stop in ranges)
            if last < total:
                gaps.append({"start": last, "stop": total})
        elif total:
            gaps = [{"start": 0, "stop": total}]
    canvas.rect(LEFT, y, PLOT_WIDTH, 12, fill="none", stroke="#bbbbbb")
    for gap_start, gap_stop in _pairs(gaps):
        canvas.rect(
            canvas.x(gap_start),
            y,
            canvas.x(gap_stop) - canvas.x(gap_start),
            12,
            fill="#f0f0f0",
            stroke="#888888",
            dash=True,
        )
    for over_start, over_stop in _pairs(overlaps):
        canvas.rect(
            canvas.x(over_start),
            y,
            canvas.x(over_stop) - canvas.x(over_start),
            12,
            fill="#e74c3c",
            opacity=0.45,
            stroke="#c0392b",
        )
    canvas.text(4, y + 10, "gaps / overlaps", size=9)
    y += 22
    notes.append(
        f"gaps: {_ranges_text(gaps)}; overlaps: {_ranges_text(overlaps)} "
        "(scope: drawn segment ranges; not inferred wiring)"
    )

    # Scale axis -----------------------------------------------------------------------
    canvas.parts.append('<g stroke="#444444">')
    canvas.line(LEFT, y, LEFT + PLOT_WIDTH, y)
    if total <= UNIT_TICK_MAX_LEDS:
        # One dashed line instead of one element per LED boundary: a 1 px dash per LED.
        canvas.parts.append(
            f'<line x1="{LEFT}" y1="{y + 2}" x2="{LEFT + PLOT_WIDTH}" y2="{y + 2}" '
            f'stroke-width="4" stroke-dasharray="1 {_n(PLOT_WIDTH / total - 1)}"/>'
        )
    step_label = _nice_step(total)
    ticks = list(range(0, total + 1, step_label))
    if ticks[-1] != total:
        ticks.append(total)
    for led in ticks:
        canvas.line(canvas.x(led), y, canvas.x(led), y + 6)
    canvas.parts.append("</g>")
    for led in ticks:
        canvas.text(canvas.x(led), y + 18, str(led), size=9, middle=True)
    y += 34

    # Legend and notes ------------------------------------------------------------------
    if model.source == "proposed":
        notes.append("Proposed layout: validated by the layout planner; nothing was written.")
        if model.removed_segment_ids:
            shown_ids = ", ".join(str(i) for i in model.removed_segment_ids[:12])
            more = " ..." if len(model.removed_segment_ids) > 12 else ""
            notes.append(f"Segments removed by this layout (not drawn): {shown_ids}{more}")
    colour_basis = (
        "plan"
        if model.source == "proposed"
        else "state_slot_0"
        if live is None
        else "mixed"
        if live_lanes and state_lanes
        else "live_samples"
    )
    if live is not None and step > 1:
        flag("unsampled_leds_unknown")
        notes.append(f"live: sampled every {step} LEDs; unsampled LEDs are unknown.")
    elif live is not None:
        notes.append("live: every LED sampled; brightness-scaled firmware RGB.")
    if unknown_colour:
        notes.append("Segments with unknown colour are drawn neutral grey.")
    if "rgbw_white_added" in approximations:
        notes.append("approx.: white channel added to RGB for RGBW segments.")
    if "cct_not_rendered" in approximations:
        notes.append("CCT segments are drawn grey; colour temperature is not rendered.")
    if effects_present:
        flag("effects_not_simulated")
        notes.append("Segments with a non-default effect: effect not simulated.")
    notes.extend(model.notes)
    if len(notes) > MAX_NOTES:
        notes[MAX_NOTES:] = [f"{len(notes) - MAX_NOTES} more notes not shown."]
    notes.append(
        "Colours approximate the first colour slot (or live samples); not calibrated. "
        "Effects and animation are not simulated; 1D only."
    )
    legend = [clean_text(n, NOTE_LIMIT) for n in notes]

    body_end = y
    legend_parts = _Canvas(total)
    for index, line in enumerate(legend):
        legend_parts.text(4, body_end + 12 + index * 13, line, size=10)
    height = body_end + 12 + len(legend) * 13 + 6

    svg_parts = [
        f'<svg xmlns="{NAMESPACE}" viewBox="0 0 {VIEWBOX_WIDTH} {_n(height)}" '
        f'width="{VIEWBOX_WIDTH}" height="{_n(height)}" role="img">',
        f"<title>{escape(f'Layout preview, {model.source}, {title_device}')}</title>",
        "<desc>Static 1D layout preview. Ranges are [start,stop) with exclusive stop. "
        "Colours are approximate; effects are not simulated.</desc>",
        f'<rect x="0" y="0" width="{VIEWBOX_WIDTH}" height="{_n(height)}" fill="#ffffff"/>',
        '<g font-family="monospace" font-size="11" fill="#1a1a1a">',
    ]
    header_canvas = _Canvas(total)
    header_canvas.text(4, 18, header[0], size=13)
    header_canvas.text(4, 33, header[1], size=10)
    svg_parts.extend(header_canvas.parts)
    svg_parts.extend(canvas.parts)
    svg_parts.extend(legend_parts.parts)
    svg_parts.append("</g></svg>")
    svg = "".join(svg_parts)

    summary: dict[str, JsonValue] = {
        "source": model.source,
        "led_count": total if known else None,
        "led_count_source": led_source,
        "scale": {
            "viewbox_width": VIEWBOX_WIDTH,
            "leds_per_pixel": round(total / PLOT_WIDTH, 4),
        },
        "range_semantics": RANGE_SEMANTICS,
        "segments": lane_summary,
        "omitted_segments": omitted,
        "gaps": gaps,
        "overlaps": overlaps,
        "colour_basis": colour_basis,
        "approximations": list(approximations),
        "limits": list(LIMITS),
    }
    if model.source == "proposed":
        summary["removed_segment_ids"] = list(model.removed_segment_ids)
    if zone_summary is not None:
        summary["zone"] = zone_summary
    if model.live is not None:
        summary["live"] = {
            "requested": True,
            "status": model.live.status,
            "sampling_step": model.live.sampling_step,
        }
    return Rendered(svg, summary)
