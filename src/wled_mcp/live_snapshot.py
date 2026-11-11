"""Bounded, sample-only LED observations; never a simulation or a writer."""

import json
from typing import Any, cast

from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from wled_mcp.access import ToolClass
from wled_mcp.client import ClientFailure, Endpoint
from wled_mcp.layout_preview import intervals
from wled_mcp.models import Outcome
from wled_mcp.readmodels import Collector, as_dict, normalize_state
from wled_mcp.resources import Resources
from wled_mcp.server import Operation

MAX_SEGMENTS = 128
MAX_RUNS = 512
MAX_OUTPUT_BYTES = 128 * 1024


class LiveSnapshotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    device_id: str = Field(min_length=1, max_length=64, description="Configured controller ID.")
    max_runs: int = Field(
        default=MAX_RUNS,
        ge=1,
        le=MAX_RUNS,
        description="Global color-run budget across all segments, including overlaps.",
    )


def map_snapshot(
    segments: list[JsonValue],
    live: dict[str, JsonValue],
    led_count: int | None,
    max_runs: int,
    matrix: bool = False,
) -> dict[str, JsonValue]:
    colors = cast(list[str], live["leds"])
    step = cast(int, live["n"])
    matrix = matrix or "w" in live or "h" in live
    remaining = max_runs
    result: list[JsonValue] = []
    ranges: list[tuple[int, int]] = []
    active = [as_dict(s) for s in segments if as_dict(s).get("start") != as_dict(s).get("stop")]
    for segment in active[:MAX_SEGMENTS]:
        start, stop = cast(int, segment["start"]), cast(int, segment["stop"])
        item: dict[str, JsonValue] = {
            "id": segment["id"],
            "start": start,
            "stop": stop,
            "runs": [],
            "returned_samples": 0,
        }
        result.append(item)
        if (
            matrix
            or segment.get("start_y") not in {None, 0}
            or cast(int, segment.get("stop_y") or 1) > 1
        ):
            item["status"] = "unmapped_matrix"
            continue
        if led_count is None or start < 0 or stop <= start or stop > led_count:
            item["status"] = "unknown_or_stale_geometry"
            continue
        ranges.append((start, stop))
        first, end = (start + step - 1) // step, (stop + step - 1) // step
        expected = end - first
        available = max(0, min(end, len(colors)) - first)
        item["expected_samples"] = expected
        item["available_samples"] = available
        item["unsampled_leds"] = stop - start - expected
        runs: list[dict[str, JsonValue]] = []
        returned = 0
        for index in range(first, min(end, len(colors))):
            color = colors[index].upper()
            if runs and runs[-1]["rgb"] == color:
                runs[-1]["sample_count"] = cast(int, runs[-1]["sample_count"]) + 1
            elif remaining:
                runs.append({"first_led": index * step, "sample_count": 1, "rgb": color})
                remaining -= 1
            else:
                break
            returned += 1
        item["runs"] = cast(list[JsonValue], runs)
        item["returned_samples"] = returned
        item["status"] = (
            "truncated"
            if returned < available
            else "missing_samples"
            if available < expected
            else "no_samples"
            if expected == 0
            else "sampled"
        )
    gaps, overlaps = intervals(ranges)
    if not matrix and led_count is not None and ranges:
        last = max(stop for _, stop in ranges)
        if last < led_count:
            gaps.append({"start": last, "stop": led_count})
    elif not matrix and led_count is not None and not active:
        gaps = [{"start": 0, "stop": led_count}] if led_count else []
    return {
        "status": "unmapped_matrix" if matrix else "available" if colors else "empty",
        "sampling_step": step,
        "source_sample_count": len(colors),
        "led_count": led_count,
        "expected_source_samples": (led_count + step - 1) // step
        if led_count is not None and not matrix
        else None,
        "reported_geometry": {k: live[k] for k in ("w", "h") if k in live},
        "segments": result,
        "omitted_segments": max(0, len(active) - MAX_SEGMENTS),
        "source_count_matches_geometry": (len(colors) == (led_count + step - 1) // step)
        if led_count is not None and not matrix
        else None,
        "coverage_complete": not matrix
        and len(active) <= MAX_SEGMENTS
        and all(s.get("status") in {"sampled", "no_samples"} for s in map(as_dict, result)),
        "gaps": gaps,
        "overlaps": overlaps,
        "coverage_scope": "returned_valid_segment_ranges",
        "returned_runs": max_runs - remaining,
        "max_runs": max_runs,
        "max_segments": MAX_SEGMENTS,
    }


def build_live_operation(resources: Resources) -> Operation:
    async def execute(arguments: dict[str, Any]) -> Outcome:
        name, device_id = "wled_get_live_snapshot", arguments["device_id"]
        try:
            async with resources.operation(device_id) as context:
                started = resources.clock.now().isoformat()
                state = await context.read(Endpoint.STATE)
                info = await context.read(Endpoint.INFO)
                warnings = Collector()
                view, capabilities, firmware, _ = normalize_state(state, info, warnings)
                try:
                    live = as_dict(await context.read(Endpoint.LIVE))
                except ClientFailure as failure:
                    if failure.http_status not in {404, 501}:
                        raise
                    data: dict[str, JsonValue] = {
                        "status": "unavailable",
                        "http_status": failure.http_status,
                        "reason": "Live endpoint missing, disabled or unsupported; cause unknown.",
                        "segments": [],
                    }
                else:
                    leds = as_dict(as_dict(info).get("leds"))
                    data = map_snapshot(
                        cast(list[JsonValue], view["segments"]),
                        live,
                        cast(int | None, capabilities["led_count"]),
                        arguments["max_runs"],
                        isinstance(leds.get("matrix"), dict),
                    )
                data.update(
                    {
                        "source": "/json/live",
                        "read_started_at": started,
                        "captured_at": resources.clock.now().isoformat(),
                        "firmware": firmware,
                        "observation": (
                            "Sequential non-atomic reads; sampled colors only. "
                            "Unsampled LEDs are unknown. Firmware brightness-scaled RGB "
                            "includes approximate white-channel conversion; not calibrated "
                            "color, animation, persistence or causality proof."
                        ),
                    }
                )
            output = {"data": data, "warnings": list(warnings.result())}
            if len(json.dumps(output, separators=(",", ":")).encode("utf-8")) > MAX_OUTPUT_BYTES:
                raise ClientFailure("INVALID_RESPONSE", "Live snapshot exceeds output size limit.")
            return Outcome(
                ok=True,
                operation=name,
                device_id=device_id,
                application="not_attempted",
                verification="not_requested",
                data=data,
                warnings=list(warnings.result()),
            )
        except ClientFailure as failure:
            known = any(d.id == device_id for d in resources.inventory)
            return Outcome(
                ok=False,
                operation=name,
                device_id=device_id if known else None,
                application="not_attempted",
                verification="not_requested",
                error=failure.error,
            )

    return Operation(
        name="wled_get_live_snapshot",
        tool_class=ToolClass.READ,
        description="Read one bounded sampled LED color observation per active 1D segment. "
        "Reports downsampling, gaps, overlaps, unavailable endpoints and unmapped matrix geometry. "
        "Exclusive segment stops; no animation simulation, calibrated-color or causality proof.",
        request_model=LiveSnapshotRequest,
        execute=execute,
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
        ),
    )
