"""``wled_preview_layout`` of issue #29: a static SVG preview, read-only by construction.

The adapter reads what the renderer needs and nothing else: ``/json/state`` and
``/json/info`` of one configured device (plus ``/json/live`` on request), the stored zones
as local files, and for a proposed layout the existing pure planner ``build_layout_plan``
over that same fresh read. It holds no write function, so it is class ``read`` in every
profile even for a proposed layout (the precedent is ``wled_plan_zone``). All drawing is in
``layout_preview.py``; this module only maps validated read models onto its plain
dataclasses, enforces the output bounds and builds the standard tool result.

The SVG is delivered as the string ``data.svg`` of the normal envelope (TD-29-1) so both
transports return it identically. A preview is never a statement about physical colour or
firmware animation, and 2D/matrix devices are refused instead of guessed (ISSUE-27-DEC-001).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any, cast

import anyio
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from wled_mcp.access import ToolClass
from wled_mcp.client import ClientFailure, Endpoint
from wled_mcp.layout_preview import (
    MAX_COLOUR_RECTS,
    MAX_SVG_BYTES,
    LaneModel,
    LiveModel,
    LiveRun,
    PreviewModel,
    ZoneModel,
    render_svg,
)
from wled_mcp.layouts import LayoutSegment, ReplaceLayoutRequest, build_layout_plan
from wled_mcp.live_snapshot import MAX_OUTPUT_BYTES, map_snapshot
from wled_mcp.models import Outcome
from wled_mcp.preset_tools import READ_ONLY
from wled_mcp.readmodels import Collector, as_dict, normalize_state
from wled_mcp.resources import Resources
from wled_mcp.scene_store import DefinitionStore
from wled_mcp.server import Operation
from wled_mcp.zone_tools import ZoneRef
from wled_mcp.zones import (
    MAX_DOCUMENT_BYTES,
    MAX_ZONES,
    Zone,
    ZoneLookupFailure,
    find_zone,
    parse_zone,
)

NAME = "wled_preview_layout"
MEDIA_TYPE = "image/svg+xml"
IGNORED_NAMES_WARNING = (
    "effect_name and palette_name are not resolved by the preview; effects and palettes "
    "are not rendered."
)


class PreviewLayoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    device_id: str = Field(min_length=1, max_length=64, description="Configured controller ID.")
    segments: list[LayoutSegment] | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description=(
            "Optional complete proposed layout (the segments of wled_replace_layout). Omit to "
            "draw the layout the device reports now. A proposal is validated by the layout "
            "planner and never written."
        ),
    )
    allow_overlap: bool = Field(
        default=False,
        description="Same meaning as in wled_replace_layout; only valid together with segments.",
    )
    zone: ZoneRef | None = Field(
        default=None,
        description="Optional stored zone ID or unique name whose ranges are drawn as bands.",
    )
    live_samples: bool = Field(
        default=False,
        description=(
            "Colour the observed layout from one bounded /json/live sample read; not valid "
            "together with segments."
        ),
    )


# -------------------------------------------------------------------------------- mapping


def _int(value: JsonValue) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _slots(value: JsonValue) -> tuple[tuple[int, ...], ...] | None:
    if not isinstance(value, list):
        return None
    slots = [
        tuple(c for c in slot if isinstance(c, int)) for slot in value if isinstance(slot, list)
    ]
    return tuple(slots) if slots else None


def _lane(
    entry: dict[str, JsonValue], change: str | None = None, live: dict[str, JsonValue] | None = None
) -> LaneModel:
    start, stop, seg_id = _int(entry["start"]), _int(entry["stop"]), _int(entry["id"])
    assert start is not None and stop is not None and seg_id is not None
    on, name = entry.get("on"), entry.get("name")
    capability = entry.get("reported_color_capability")
    runs: tuple[LiveRun, ...] | None = None
    if live is not None:
        runs = tuple(
            LiveRun(
                cast(int, run["first_led"]), cast(int, run["sample_count"]), cast(str, run["rgb"])
            )
            for run in cast(list[dict[str, JsonValue]], live.get("runs") or [])
        )
    return LaneModel(
        id=seg_id,
        start=start,
        stop=stop,
        name=name if isinstance(name, str) else None,
        on=on if isinstance(on, bool) else None,
        brightness=_int(entry.get("effective_brightness")),
        colors=_slots(entry.get("colors")),
        color_capability=capability if isinstance(capability, dict) else None,
        cct=_int(entry.get("cct")),
        effect_id=_int(entry.get("effect_id")),
        change=change,
        live_runs=runs,
        live_status=cast(str, live["status"]) if live is not None and "status" in live else None,
    )


def _is_matrix(
    capabilities: dict[str, JsonValue], info: dict[str, JsonValue], segments: Sequence[JsonValue]
) -> bool:
    """A matrix is declared by the device or implied by a segment beyond one row."""
    if capabilities.get("matrix") is not None:
        return True
    if isinstance(as_dict(info.get("leds")).get("matrix"), dict):
        return True
    for item in segments:
        segment = as_dict(item)
        stop_y = _int(segment.get("stop_y"))
        if segment.get("start_y") not in {None, 0} or (stop_y or 1) > 1:
            return True
    return False


def _zone_model(zone: Zone, device_id: str, led_count: int | None) -> ZoneModel:
    part = next(part for part in zone.parts if part.device == device_id)
    if part.led_count != led_count:
        return ZoneModel(zone.id, zone.name, (), "topology_stale")
    spans = tuple((s.start, s.stop, s.reversed) for s in part.spans)
    return ZoneModel(zone.id, zone.name, spans, "drawn")


# ----------------------------------------------------------------------------------- tool


def build_preview_operation(resources: Resources) -> Operation:
    def parse_zone_bytes(raw: bytes) -> Zone:
        return parse_zone(raw)

    zones: DefinitionStore[Zone] = DefinitionStore(
        resources.config.data_dir / "zones",
        "zone",
        parse_zone_bytes,
        lambda item: item.id,
        max_items=MAX_ZONES,
        max_bytes=MAX_DOCUMENT_BYTES,
    )

    def failed(device_id: str, failure: ClientFailure) -> Outcome:
        known = any(device.id == device_id for device in resources.inventory)
        data: dict[str, JsonValue] = {}
        if isinstance(failure, ZoneLookupFailure) and failure.candidates is not None:
            data = {"candidates": failure.candidates, "candidate_total": failure.total}
        return Outcome(
            ok=False,
            operation=NAME,
            device_id=device_id if known else None,
            application="not_attempted",
            verification="not_requested",
            data=data,
            error=failure.error,
        )

    async def execute(arguments: dict[str, Any]) -> Outcome:
        device_id: str = arguments["device_id"]
        proposed: list[dict[str, Any]] | None = arguments["segments"]
        try:
            resources.resolve(device_id)
            if proposed is not None and arguments["live_samples"]:
                raise ClientFailure(
                    "VALIDATION_ERROR",
                    "live_samples describes the current device and cannot be combined with "
                    "a proposed layout.",
                    reconciliation="Preview the observed layout with live_samples, or omit it.",
                )
            if proposed is None and arguments["allow_overlap"]:
                raise ClientFailure(
                    "VALIDATION_ERROR",
                    "allow_overlap applies to a proposed layout; pass segments or omit it.",
                    reconciliation="Pass segments or remove allow_overlap.",
                )
            warnings: list[str] = []
            zone: Zone | None = None
            if arguments["zone"] is not None:
                listing = await anyio.to_thread.run_sync(zones.list_items)
                zone, lookup_warnings = find_zone(listing.items, arguments["zone"])
                warnings += [*lookup_warnings, *listing.warnings]
                if not any(part.device == device_id for part in zone.parts):
                    raise ClientFailure(
                        "VALIDATION_ERROR",
                        "The zone has no part for this device.",
                        reconciliation="Name a zone that maps this device, or omit zone.",
                    )
            request: ReplaceLayoutRequest | None = None
            if proposed is not None:
                names_given = any(
                    item.get("effect_name") is not None or item.get("palette_name") is not None
                    for item in proposed
                )
                if names_given:
                    warnings.append(IGNORED_NAMES_WARNING)
                request = ReplaceLayoutRequest.model_validate(
                    {
                        "device_id": device_id,
                        "segments": [
                            {**item, "effect_name": None, "palette_name": None} for item in proposed
                        ],
                        "allow_overlap": arguments["allow_overlap"],
                        "dry_run": True,
                    }
                )

            live_view: dict[str, JsonValue] | None = None
            live_unavailable = False
            async with resources.operation(device_id) as context:
                state = await context.read(Endpoint.STATE)
                info = await context.read(Endpoint.INFO)
                collector = Collector()
                view, capabilities, _firmware, _unknown = normalize_state(state, info, collector)
                raw_info, raw_state = as_dict(info), as_dict(state)
                observed = cast(list[JsonValue], view["segments"])
                if _is_matrix(capabilities, raw_info, observed):
                    raise ClientFailure(
                        "UNSUPPORTED_CAPABILITY",
                        "2D/matrix preview is not supported in this version.",
                        reconciliation="Only 1D layouts are drawn; no 2D geometry is inferred.",
                    )
                led_count = _int(capabilities["led_count"])
                plan = (
                    build_layout_plan(request, view, capabilities, raw_info, raw_state)
                    if request is not None
                    else None
                )
                if arguments["live_samples"]:
                    try:
                        live = as_dict(await context.read(Endpoint.LIVE))
                    except ClientFailure as failure:
                        if failure.http_status not in {404, 501}:
                            raise
                        live_unavailable = True
                    else:
                        live_view = map_snapshot(observed, live, led_count, MAX_COLOUR_RECTS, False)
            captured_at = resources.clock.now().isoformat()
            warnings = [*collector.result(), *warnings]

            if plan is not None:
                warnings += plan.warnings
                public = plan.public
                change: dict[int, str] = {}
                for key, label in (
                    ("create_segment_ids", "new"),
                    ("update_segment_ids", "changed"),
                    ("unchanged_segment_ids", "unchanged"),
                ):
                    for item in cast(list[JsonValue], public[key]):
                        change[cast(int, item)] = label
                lanes = tuple(
                    _lane(entry, change.get(cast(int, entry["id"])))
                    for entry in cast(list[dict[str, JsonValue]], public["resolved_segments"])
                )
                removed = tuple(cast(list[int], public["remove_segment_ids"]))
                live_model = None
            else:
                by_id = {
                    cast(int, as_dict(item)["id"]): as_dict(item)
                    for item in cast(list[JsonValue], (live_view or {}).get("segments", []))
                }
                lanes = tuple(
                    _lane(as_dict(item), live=by_id.get(cast(int, as_dict(item)["id"])))
                    for item in observed
                )
                removed = ()
                live_model = None
                if live_unavailable:
                    live_model = LiveModel("unavailable", 1)
                    warnings.append("live samples unavailable (cause unknown)")
                elif live_view is not None:
                    live_model = LiveModel(
                        cast(str, live_view["status"]), cast(int, live_view["sampling_step"])
                    )
            status = live_model.status if live_model is not None else None
            if status == "unmapped_matrix":
                raise ClientFailure(
                    "UNSUPPORTED_CAPABILITY", "2D/matrix preview is not supported in this version."
                )

            rendered = render_svg(
                PreviewModel(
                    source="proposed" if plan is not None else "observed",
                    device=device_id,
                    led_count=led_count,
                    lanes=lanes,
                    master_on=cast("bool | None", view["on"]) if plan is None else None,
                    master_brightness=_int(view["brightness"]) if plan is None else None,
                    zone=_zone_model(zone, device_id, led_count) if zone is not None else None,
                    live=live_model,
                    removed_segment_ids=removed,
                    notes=tuple(warnings),
                )
            )
            data: dict[str, JsonValue] = {
                "source": rendered.summary["source"],
                "media_type": MEDIA_TYPE,
                "svg": rendered.svg,
                **{k: v for k, v in rendered.summary.items() if k != "source"},
                "observation": (
                    "Fresh non-atomic reads; nothing was written. The drawing approximates the "
                    "first colour slot (or sampled live colours); it is not calibrated colour "
                    "and does not simulate effects or animation."
                ),
            }
            if plan is None:
                data["captured_at"] = captured_at
            if led_count is None:
                data["limits"] = [
                    *cast(list[JsonValue], data["limits"]),
                    "LED count unknown; the scale uses the highest drawn segment end",
                ]
            if (
                len(rendered.svg.encode("utf-8")) > MAX_SVG_BYTES
                or len(json.dumps(data, separators=(",", ":")).encode("utf-8")) > MAX_OUTPUT_BYTES
            ):
                raise ClientFailure(
                    "INVALID_RESPONSE", "Layout preview exceeds the output size limit."
                )
            return Outcome(
                ok=True,
                operation=NAME,
                device_id=device_id,
                application="not_attempted",
                verification="not_requested",
                data=data,
                warnings=warnings,
            )
        except ClientFailure as failure:
            return failed(device_id, failure)

    return Operation(
        name=NAME,
        tool_class=ToolClass.READ,
        description=(
            "Read-only static SVG preview of one 1D device's segment layout, returned as the "
            "string data.svg (image/svg+xml) with a structured summary. Without segments it "
            "draws the observed layout (source observed); with segments it draws a proposed "
            "complete layout validated by the layout planner (source proposed) and writes "
            "nothing. Shows segment IDs, names, LED ranges with exclusive stops, a scale, "
            "gaps, overlaps and approximate colours; optional zone bands (zone) and optional "
            "live colour samples (live_samples). Colours are approximations, not calibrated "
            "colour; effects are not simulated and nothing is animated. 1D only: a matrix "
            "device is refused with UNSUPPORTED_CAPABILITY. Sends no write and changes no "
            "lighting. Read-only."
        ),
        request_model=PreviewLayoutRequest,
        execute=execute,
        annotations=READ_ONLY,
    )
