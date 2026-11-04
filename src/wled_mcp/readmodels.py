"""Pure normalization of WLED /json/state and /json/info (issue #5, read-only).

Required fields fail with INVALID_RESPONSE. Optional fields of the wrong type become
null plus a warning. Unreported capabilities are null, never false. Raw device data is
kept next to the normalized view; only the documented info keys are redacted.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from pydantic import JsonValue

from wled_mcp.client import ClientFailure

# Capability bits per the pinned firmware source (FX.h / const.h at v0.15.1).
CAP_RGB, CAP_WHITE, CAP_CCT = 0x01, 0x02, 0x04
# Raw info keys removed from output (runtime privacy default, ISSUE-5-DEC-006).
REDACTED_KEYS = ("mac", "ip", "wifi.bssid")


def invalid(message: str) -> ClientFailure:
    return ClientFailure("INVALID_RESPONSE", message)


def is_int(value: object) -> bool:
    return type(value) is int


def as_dict(value: JsonValue) -> dict[str, JsonValue]:
    return value if isinstance(value, dict) else {}


@dataclass
class Collector:
    """Warnings with a hard bound so hostile payloads cannot inflate the envelope."""

    limit: int = 20
    items: list[str] = field(default_factory=list)
    dropped: int = 0

    def add(self, message: str) -> None:
        if message in self.items:
            return
        if len(self.items) < self.limit:
            self.items.append(message)
        else:
            self.dropped += 1

    def result(self) -> list[str]:
        if self.dropped:
            return [*self.items, f"{self.dropped} further warnings omitted."]
        return list(self.items)


def opt_int(
    source: dict[str, JsonValue],
    key: str,
    context: str,
    warnings: Collector,
    low: int | None = None,
    high: int | None = None,
) -> int | None:
    if key not in source or source[key] is None:
        return None
    value = source[key]
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or (low is not None and value < low)
        or (high is not None and value > high)
    ):
        warnings.add(f"{context}field '{key}' has an unexpected value; reported as null.")
        return None
    return value


def opt_bool(
    source: dict[str, JsonValue], key: str, context: str, warnings: Collector
) -> bool | None:
    if key not in source or source[key] is None:
        return None
    value = source[key]
    if not isinstance(value, bool):
        warnings.add(f"{context}field '{key}' has an unexpected type; reported as null.")
        return None
    return value


def opt_str(
    source: dict[str, JsonValue], key: str, context: str, warnings: Collector
) -> str | None:
    if key not in source or source[key] is None:
        return None
    value = source[key]
    if not isinstance(value, str):
        warnings.add(f"{context}field '{key}' has an unexpected type; reported as null.")
        return None
    return value


@dataclass(frozen=True)
class InfoIdentity:
    version: str
    build_id: int | None

    @property
    def key(self) -> tuple[str, int | None]:
        return (self.version, self.build_id)


def read_identity(info: JsonValue) -> InfoIdentity:
    """Required: info object with string `ver`. `vid` is optional (null if not an int)."""
    if not isinstance(info, dict) or not isinstance(info.get("ver"), str) or not info["ver"]:
        raise invalid("Device info lacks a firmware version string.")
    vid = info.get("vid")
    version = info["ver"]
    assert isinstance(version, str)
    return InfoIdentity(
        version, vid if isinstance(vid, int) and not isinstance(vid, bool) else None
    )


def redact_info(info: dict[str, JsonValue]) -> tuple[dict[str, JsonValue], list[str]]:
    """Return a deep copy without mac, ip and wifi.bssid, plus the keys actually removed."""
    clean: dict[str, JsonValue] = copy.deepcopy(info)
    removed: list[str] = []
    for key in ("mac", "ip"):
        if key in clean:
            del clean[key]
            removed.append(key)
    wifi = clean.get("wifi")
    if isinstance(wifi, dict) and "bssid" in wifi:
        del wifi["bssid"]
        removed.append("wifi.bssid")
    return clean, removed


def _caps(lc: int) -> dict[str, JsonValue]:
    return {
        "rgb": bool(lc & CAP_RGB),
        "white": bool(lc & CAP_WHITE),
        "cct": bool(lc & CAP_CCT),
    }


def _colors(
    raw: JsonValue, rgb_only: bool, context: str, warnings: Collector
) -> tuple[list[JsonValue] | None, int | None]:
    if raw is None:
        return None, None
    ok = isinstance(raw, list) and all(
        isinstance(slot, list)
        and len(slot) in (3, 4)
        and all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 255 for c in slot)
        for slot in raw
    )
    if not ok or not isinstance(raw, list):
        warnings.add(f"{context}field 'col' has an unexpected shape; reported as null.")
        return None, None
    slots: list[list[JsonValue]] = [list(slot) for slot in raw if isinstance(slot, list)]
    # A fourth channel is dropped only if every slot carries 0 there and the segment is
    # proven RGB-only by its reported capability; the raw state keeps the original.
    if rgb_only and slots and all(len(s) == 4 and s[3] == 0 for s in slots):
        slots = [s[:3] for s in slots]
    widths = {len(s) for s in slots}
    channels = widths.pop() if len(widths) == 1 else None
    return [list(s) for s in slots], channels


def normalize_state(
    state: JsonValue, info: JsonValue, warnings: Collector
) -> tuple[dict[str, JsonValue], dict[str, JsonValue], dict[str, JsonValue], list[str]]:
    """Return (state view, capabilities, firmware, unknown_capabilities)."""
    identity = read_identity(info)
    assert isinstance(info, dict)
    if not isinstance(state, dict):
        raise invalid("Device state is not an object.")
    on = state.get("on")
    bri = state.get("bri")
    segs = state.get("seg")
    if not isinstance(on, bool):
        raise invalid("Device state lacks a boolean 'on'.")
    if not isinstance(bri, int) or isinstance(bri, bool) or not 0 <= bri <= 255:
        raise invalid("Device state lacks an integer 'bri' between 0 and 255.")
    if not isinstance(segs, list) or not all(isinstance(s, dict) for s in segs):
        raise invalid("Device state lacks a segment list.")
    seen: set[int] = set()
    for seg in segs:
        assert isinstance(seg, dict)
        seg_id, start, stop = seg.get("id"), seg.get("start"), seg.get("stop")
        if not isinstance(seg_id, int) or isinstance(seg_id, bool) or seg_id < 0 or seg_id in seen:
            raise invalid("Device state has a segment without a unique non-negative ID.")
        if not is_int(start) or not is_int(stop):
            raise invalid("Device state has a segment without integer bounds.")
        seen.add(seg_id)

    leds = as_dict(info.get("leds"))
    lc = leds.get("lc")
    seglc = leds.get("seglc")
    seg_caps: list[int] | None = None
    if isinstance(seglc, list) and all(is_int(v) for v in seglc):
        if len(seglc) == len(segs):
            seg_caps = [v for v in seglc if isinstance(v, int)]
        else:
            warnings.add("Per-segment capability list does not match the segment list.")

    segments: list[JsonValue] = []
    for index, raw in enumerate(segs):
        assert isinstance(raw, dict)
        ctx = f"Segment {raw['id']}: "
        seg_on = opt_bool(raw, "on", ctx, warnings)
        seg_bri = opt_int(raw, "bri", ctx, warnings, 0, 255)
        caps = seg_caps[index] if seg_caps is not None else None
        colors, channels = _colors(
            raw.get("col"), caps is not None and (caps & 7) == CAP_RGB, ctx, warnings
        )
        segments.append(
            {
                "id": raw["id"],
                "start": raw["start"],
                "stop": raw["stop"],
                "on": seg_on,
                "brightness": seg_bri,
                "effective_brightness": (
                    None if seg_on is None or seg_bri is None else (seg_bri if seg_on else 0)
                ),
                "colors": colors,
                "color_channels": channels,
                "reported_color_capability": None if caps is None else _caps(caps),
                "effect_id": opt_int(raw, "fx", ctx, warnings, 0),
                "palette_id": opt_int(raw, "pal", ctx, warnings, 0),
                "speed": opt_int(raw, "sx", ctx, warnings, 0, 255),
                "intensity": opt_int(raw, "ix", ctx, warnings, 0, 255),
                "grouping": opt_int(raw, "grp", ctx, warnings, 0),
                "spacing": opt_int(raw, "spc", ctx, warnings, 0),
                "offset": opt_int(raw, "of", ctx, warnings, 0),
                "reverse": opt_bool(raw, "rev", ctx, warnings),
                "mirror": opt_bool(raw, "mi", ctx, warnings),
                "selected": opt_bool(raw, "sel", ctx, warnings),
                "name": opt_str(raw, "n", ctx, warnings),
            }
        )

    transition = opt_int(state, "transition", "State: ", warnings, 0)
    preset = opt_int(state, "ps", "State: ", warnings)
    playlist = opt_int(state, "pl", "State: ", warnings)
    main = opt_int(state, "mainseg", "State: ", warnings, 0)
    state_view: dict[str, JsonValue] = {
        "on": on,
        "brightness": bri,
        "effective_brightness": bri if on else 0,
        "default_transition_ms": None if transition is None else transition * 100,
        "active_preset_id": None if preset is None or preset < 0 else preset,
        "active_playlist_id": None if playlist is None or playlist < 0 else playlist,
        "main_segment": main,
        "segments": segments,
    }

    led_count = opt_int(leds, "count", "Info: leds.", warnings, 0)
    max_segments = opt_int(leds, "maxseg", "Info: leds.", warnings, 0)
    effect_count = opt_int(info, "fxcount", "Info: ", warnings, 0)
    palette_count = opt_int(info, "palcount", "Info: ", warnings, 0)
    wide: dict[str, JsonValue] | None = None
    if is_int(lc):
        assert isinstance(lc, int)
        wide = {"scope": "aggregate_of_active_segments", **_caps(lc)}
    capabilities: dict[str, JsonValue] = {
        "led_count": led_count,
        "max_segments": max_segments,
        "effect_count": effect_count,
        "palette_count": palette_count,
        "device_wide_color": wide,
        "segment_color_capability_reported": seg_caps is not None,
    }
    unknown = [
        name
        for name, value in (
            ("led_count", led_count),
            ("max_segments", max_segments),
            ("effect_count", effect_count),
            ("palette_count", palette_count),
            ("device_wide_color", wide),
            ("segment_color_capability", seg_caps),
            ("build_id", identity.build_id),
        )
        if value is None
    ]
    firmware: dict[str, JsonValue] = {
        "version": identity.version,
        "build_id": identity.build_id,
        "product": opt_str(info, "product", "Info: ", warnings),
        "brand": opt_str(info, "brand", "Info: ", warnings),
        "arch": opt_str(info, "arch", "Info: ", warnings),
    }
    return state_view, capabilities, firmware, unknown
