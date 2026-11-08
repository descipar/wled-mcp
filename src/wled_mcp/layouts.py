"""Complete layout replacement planning (issue #7).

Pure request -> plan transformation; the planner never calls the network. It consumes
one fresh normalized ``/json/state`` view plus the raw info/state payloads and returns
an explicit ordered sequence of single-object ``seg`` POSTs together with the readback
check of every step and an exact final check.

Technical baseline (accepted by delegated decision, ``ISSUE-7-DEC-003``..``-005``,
docs/decisions/issue-7.md):
baseline profile 0 (WLED v0.15.1 source, observed on 16.0.1), exact stale removal with
one ``stop: 0`` POST per ID (never an array payload, which could purge/renumber slots),
no filler segments, no temporary segment, creates only in ascending ID order within the
observable allocation bound, and no reset of the master state.

WLED 16 segment evidence (ISSUE-19-DEC-003, docs/contract/segments.md): capability for
colors and ``cct`` follows ``capabilities.derive_capabilities`` (new or moved ranges use
the uniform rule, TD-19-4); option fields need field presence, 2D fields a matrix; on a
matrix ``start``/``stop`` are X columns and overlap is rectangle intersection; new IDs
receive the WLED 16 defaults where the readback proves the field (TD-19-6), and
``allow_overlap`` (ISSUE-19-DEC-001) permits an overlapping layout.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from wled_mcp.capabilities import DeviceCapabilities, derive_capabilities
from wled_mcp.client import ClientFailure
from wled_mcp.resources import SequencePlan, WriteStep
from wled_mcp.segment_rules import (
    BLEND_MODE_MAX,
    CCT_DEFAULT,
    CCT_MAX,
    CUSTOM3_MAX,
    CUSTOM_MAX,
    FREEZE_WARNING,
    GROUPING_MAX,
    MAP_1D_2D_MAX,
    OPTION_FIELDS,
    ORIENTATION_FIELDS,
    SEGMENT_FIELDS,
    SEGMENT_SET_MAX,
    SOUND_SIMULATION_MAX,
    SPACING_MAX,
    Geometry,
    Rect,
    SegmentPower,
    check_cct,
    check_colors,
    check_fields,
    check_segment_name,
    check_y_pair,
    evidence_entries,
    option_keys,
    overlap_plan,
    overlapping_pairs,
    resolve_segment_power,
)

# ---------------------------------------------------------------------------- request


class LayoutSegment(BaseModel):
    """One segment of the complete desired layout (id, start and stop are required).

    On a matrix a new segment also needs ``start_y`` and ``stop_y`` (planner rule). The
    #19 fields after ``name`` need fresh capability, field or matrix evidence.
    """

    model_config = ConfigDict(extra="forbid", strict=True)
    id: int = Field(ge=0)
    start: int = Field(ge=0)
    stop: int = Field(ge=1)
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
    # Issue #19 (ISSUE-19-DEC-003 TD-19-2); additive, all optional.
    cct: int | None = Field(default=None, ge=0, le=CCT_MAX)
    custom1: int | None = Field(default=None, ge=0, le=CUSTOM_MAX)
    custom2: int | None = Field(default=None, ge=0, le=CUSTOM_MAX)
    custom3: int | None = Field(default=None, ge=0, le=CUSTOM3_MAX)
    check1: bool | None = None
    check2: bool | None = None
    check3: bool | None = None
    sound_simulation: int | None = Field(default=None, ge=0, le=SOUND_SIMULATION_MAX)
    segment_set: int | None = Field(default=None, ge=0, le=SEGMENT_SET_MAX)
    map_1d_2d: int | None = Field(default=None, ge=0, le=MAP_1D_2D_MAX)
    freeze: bool | None = None
    blend_mode: int | None = Field(default=None, ge=0, le=BLEND_MODE_MAX)
    start_y: int | None = Field(default=None, ge=0)
    stop_y: int | None = Field(default=None, ge=1)
    reverse_y: bool | None = None
    mirror_y: bool | None = None
    transpose: bool | None = None


class ReplaceLayoutRequest(BaseModel):
    """The complete desired active layout. Active IDs not listed here are removed.

    ``allow_overlap`` (ISSUE-19-DEC-001) permits overlapping desired segments.
    """

    model_config = ConfigDict(extra="forbid", strict=True)
    device_id: str = Field(min_length=1, max_length=64)
    segments: list[LayoutSegment] = Field(min_length=1, max_length=64)
    allow_overlap: bool = False
    dry_run: bool = False


# ---------------------------------------------------------------------------- outputs


@dataclass(frozen=True)
class LayoutPlan:
    sequence: SequencePlan
    public: dict[str, JsonValue]
    postconditions: list[JsonValue]
    warnings: list[str]

    @property
    def noop(self) -> bool:
        return not self.sequence.steps


# ---------------------------------------------------------------------------- helpers

# Defaults for newly created IDs (contract "Segments: schema and omissions").
_DEFAULTS: dict[str, JsonValue] = {
    "on": True,
    "brightness": 255,
    "effect_id": 0,
    "palette_id": 0,
    "speed": 128,
    "intensity": 128,
    "grouping": 1,
    "spacing": 0,
    "offset": 0,
    "reverse": False,
    "mirror": False,
    "selected": False,
    "name": "",
}

# public field -> (request attribute, wire key)
_SIMPLE_FIELDS: tuple[tuple[str, str], ...] = (
    ("effect_id", "fx"),
    ("palette_id", "pal"),
    ("speed", "sx"),
    ("intensity", "ix"),
    ("grouping", "grp"),
    ("spacing", "spc"),
    ("offset", "of"),
    ("reverse", "rev"),
    ("mirror", "mi"),
    ("selected", "sel"),
)

Layout = dict[int, tuple[int, int]]
# Keys a new ID inherits from a reused slot unless the create step resets them (TD-19-6).
_RESETTABLE_KEYS: tuple[str, ...] = ("cct", *(field.wire for field in OPTION_FIELDS))


def _fail(message: str) -> ClientFailure:
    return ClientFailure("VALIDATION_ERROR", message)


def _unsupported(message: str) -> ClientFailure:
    return ClientFailure("UNSUPPORTED_CAPABILITY", message)


def _int_slots(value: JsonValue) -> list[list[int]] | None:
    """Normalized color slots as integer lists (already validated by normalization)."""
    if not isinstance(value, list):
        return None
    slots: list[list[int]] = []
    for slot in value:
        if not isinstance(slot, list) or not all(isinstance(c, int) for c in slot):
            return None
        slots.append([c for c in slot if isinstance(c, int)])
    return slots


def _raw_name(raw: dict[str, JsonValue] | None) -> str | None:
    """Missing ``n`` is the empty name; a non-string name is unrepresentable (None)."""
    if raw is None or "n" not in raw:
        return ""
    value = raw["n"]
    return value if isinstance(value, str) else None


def _layout_of(state: JsonValue) -> Layout | None:
    if not isinstance(state, dict):
        return None
    segments = state.get("seg")
    if not isinstance(segments, list):
        return None
    layout: Layout = {}
    for seg in segments:
        if not isinstance(seg, dict):
            return None
        seg_id, start, stop = seg.get("id"), seg.get("start"), seg.get("stop")
        if not isinstance(seg_id, int) or not isinstance(start, int) or not isinstance(stop, int):
            return None
        layout[seg_id] = (start, stop)
    return layout


def _raw_by_id(state: JsonValue) -> dict[int, dict[str, JsonValue]]:
    result: dict[int, dict[str, JsonValue]] = {}
    segments = state.get("seg") if isinstance(state, dict) else None
    if isinstance(segments, list):
        for seg in segments:
            if isinstance(seg, dict):
                seg_id = seg.get("id")
                if isinstance(seg_id, int):
                    result[seg_id] = seg
    return result


def _fields_match(raw: dict[str, JsonValue], fields: dict[str, JsonValue]) -> bool:
    for key, value in fields.items():
        if key == "segment_off_from_zero_bri":
            if raw.get("on") is not False:
                return False
        elif key == "col":
            slots = raw.get("col")
            if not isinstance(slots, list) or not isinstance(value, list):
                return False
            for index, expected in enumerate(value):
                if index >= len(slots) or not isinstance(expected, list):
                    return False
                actual = slots[index]
                if not isinstance(actual, list) or len(actual) < len(expected):
                    return False
                if actual[: len(expected)] != expected:
                    return False
        elif key == "n":
            if raw.get("n", "") != value:
                return False
        elif raw.get(key) != value:
            return False
    return True


def _expectation_from_payload(payload: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Readback fields implied by one segment payload (``id`` is the lookup key)."""
    fields: dict[str, JsonValue] = {}
    for key, value in payload.items():
        if key == "id":
            continue
        if key == "bri" and value == 0:
            fields["segment_off_from_zero_bri"] = True
        else:
            fields[key] = value
    return fields


def _observe(state: JsonValue) -> JsonValue:
    if not isinstance(state, dict):
        return None
    layout = _layout_of(state)
    active: list[JsonValue] = (
        []
        if layout is None
        else [{"id": i, "start": a, "stop": b} for i, (a, b) in sorted(layout.items())]
    )
    main = state.get("mainseg")
    return {"active": active, "mainseg": main if isinstance(main, int) else None}


def _step_check(
    layout: Layout,
    seg_id: int | None,
    fields: dict[str, JsonValue],
    main: int | None,
) -> Callable[[JsonValue], bool]:
    expected_layout = dict(layout)

    def matches(state: JsonValue) -> bool:
        if _layout_of(state) != expected_layout or not isinstance(state, dict):
            return False
        if main is not None and state.get("mainseg") != main:
            return False
        if seg_id is not None and fields:
            raw = _raw_by_id(state).get(seg_id)
            return raw is not None and _fields_match(raw, fields)
        return True

    return matches


def _expectation_from_resolved(
    resolved: dict[str, JsonValue], zero_bri: bool, is_new: bool
) -> dict[str, JsonValue]:
    fields: dict[str, JsonValue] = {"start": resolved["start"], "stop": resolved["stop"]}
    if resolved["on"] is not None:
        fields["on"] = resolved["on"]
    brightness = resolved["brightness"]
    if zero_bri:
        fields["segment_off_from_zero_bri"] = True
    elif isinstance(brightness, int) and brightness > 0:
        fields["bri"] = brightness
    if resolved["colors"] is not None:
        fields["col"] = resolved["colors"]
    for public, wire in _SIMPLE_FIELDS:
        if resolved[public] is not None:
            fields[wire] = resolved[public]
    if resolved["name"] is not None:
        fields["n"] = resolved["name"]
    if is_new:
        fields["frz"] = False
    for public, wire in SEGMENT_FIELDS:
        if resolved.get(public) is not None:
            fields[wire] = resolved[public]
    return fields


# ---------------------------------------------------------------------------- planner


def build_layout_plan(
    request: ReplaceLayoutRequest,
    state_view: dict[str, JsonValue],
    capabilities: dict[str, JsonValue],
    raw_info: dict[str, JsonValue],
    raw_state: dict[str, JsonValue],
) -> LayoutPlan:
    segments = request.segments
    ids = [seg.id for seg in segments]
    if len(set(ids)) != len(ids):
        raise _fail("Segment IDs must be unique within the desired layout.")
    desired = {seg.id: seg for seg in segments}

    view = state_view.get("segments")
    assert isinstance(view, list)
    current: dict[int, dict[str, JsonValue]] = {}
    for item in view:
        assert isinstance(item, dict)
        item_id = item["id"]
        assert isinstance(item_id, int)
        current[item_id] = item
    raw_segments = raw_state.get("seg")
    assert isinstance(raw_segments, list)
    raw_by_id = _raw_by_id(raw_state)

    old = set(current)
    existing = sorted(old & set(desired))
    new = sorted(set(desired) - old)
    stale = sorted(old - set(desired))

    led_count = capabilities.get("led_count")
    max_segments = capabilities.get("max_segments")
    effect_count = capabilities.get("effect_count")
    palette_count = capabilities.get("palette_count")
    if not isinstance(led_count, int):
        raise _unsupported("LED count unknown; layout replacement cannot be validated.")
    if isinstance(max_segments, int):
        if len(desired) > max_segments:
            raise _fail(f"The layout has more segments than the device maximum ({max_segments}).")
        for seg in segments:
            if seg.id >= max_segments:
                raise _fail(
                    f"Segment {seg.id}: ID must be below the device maximum {max_segments}."
                )
    elif new:
        raise _unsupported("Maximum segment count unknown; new IDs cannot be validated.")

    device = derive_capabilities(raw_state, raw_info)
    geometry = Geometry(device.matrix)
    new_keys = option_keys(device, -1, is_new=True)

    # Per-segment validation and resolution --------------------------------------
    resolved_by_id: dict[int, dict[str, JsonValue]] = {}
    payloads: dict[int, dict[str, JsonValue]] = {}
    expectations: dict[int, dict[str, JsonValue]] = {}
    compensation: list[JsonValue] = []
    geometry_changed: set[int] = set()
    capability_evidence: list[JsonValue] = []
    rects: dict[int, Rect] = {}

    for seg in sorted(segments, key=lambda s: s.id):
        ctx = f"Segment {seg.id}: "
        if not 0 <= seg.start < seg.stop <= led_count:
            raise _fail(f"{ctx}range must satisfy 0 <= start < stop <= led_count.")
        length = seg.stop - seg.start
        if seg.offset is not None and not 0 <= seg.offset < length:
            raise _fail(f"{ctx}offset must satisfy 0 <= offset < segment length.")
        effect = seg.effect_id if seg.effect_id is not None else (0 if seg.id in new else None)
        palette = seg.palette_id if seg.palette_id is not None else (0 if seg.id in new else None)
        if effect is not None and isinstance(effect_count, int) and not 0 <= effect < effect_count:
            raise _fail(f"{ctx}effect_id out of catalog range (0..{effect_count - 1}).")
        if (
            palette is not None
            and isinstance(palette_count, int)
            and not 0 <= palette < palette_count
        ):
            raise _fail(f"{ctx}palette_id out of catalog range (0..{palette_count - 1}).")

        cur = current.get(seg.id)
        is_new = cur is None
        check_y_pair(seg.id, seg.start_y, seg.stop_y)
        x_moved = cur is not None and (cur["start"], cur["stop"]) != (seg.start, seg.stop)
        cur_y = _current_y(cur)
        y_moved = cur is not None and seg.start_y is not None and cur_y != (seg.start_y, seg.stop_y)
        _check_matrix_geometry(seg, cur, cur_y, geometry, x_moved=x_moved)
        target_y = (seg.start_y, seg.stop_y) if seg.start_y is not None else cur_y
        rect = geometry.rect(seg.start, seg.stop, *target_y)
        if rect is None:
            raise _unsupported(f"{ctx}2D bounds unknown; the overlap check cannot be made.")
        rects[seg.id] = rect
        moved = x_moved or y_moved

        colors: list[list[int]] | None = None
        if seg.colors is None:
            if is_new:
                raise _fail(f"{ctx}a new segment requires explicit colors.")
        else:
            colors, _source = check_colors(
                seg.id, seg.colors, device, raw_info, raw_segments, is_new=is_new, moved=moved
            )
        supplied = {name: getattr(seg, name) for name, _wire in SEGMENT_FIELDS}
        items = check_fields(seg.id, supplied, device, option_keys(device, seg.id, is_new=is_new))
        if seg.cct is not None:
            items = [("cct", check_cct(seg.id, device, changed=is_new or moved)), *items]
        capability_evidence.extend(evidence_entries(seg.id, items))

        # Shared name and power/brightness rules (ISSUE-48-DEC-001, same helper as #6).
        # A new ID resolves omitted power to its default on=true.
        check_segment_name(seg.id, seg.name)
        cur_on = True if cur is None else cur["on"]
        power = resolve_segment_power(
            seg.id, seg.on, seg.brightness, cur_on if isinstance(cur_on, bool) else None
        )

        if cur is None:
            resolved = _resolve_new(seg, colors, device, new_keys)
            payload = _create_payload(seg, resolved)
            compensation_entries: list[JsonValue] = []
        else:
            cur_raw = raw_by_id.get(seg.id)
            resolved, payload, compensation_entries = _update_plan(
                seg, cur, _raw_name(cur_raw), colors, power, x_moved, y_moved
            )
            if moved:
                geometry_changed.add(seg.id)
        resolved_by_id[seg.id] = resolved
        payloads[seg.id] = payload
        expectations[seg.id] = _expectation_from_resolved(resolved, seg.brightness == 0, is_new)
        compensation.extend(compensation_entries)

    # Desired layout must not overlap itself unless allowed (ISSUE-19-DEC-001) ---------
    desired_pairs = overlapping_pairs(rects)
    if desired_pairs and not request.allow_overlap:
        a_id, b_id = desired_pairs[0]
        raise _fail(
            f"Segments {a_id} and {b_id} overlap in the desired layout; pass "
            "allow_overlap=true to permit overlapping segments."
        )
    allowed_pairs = {frozenset(pair) for pair in desired_pairs}

    # Allocation of new IDs (PD-4): next appended slot is max(active)+1 at the latest.
    bound = max(old) + 1 if old else 0
    base_bound = bound
    for new_id in new:
        if new_id > bound:
            raise _unsupported(
                f"New ID {new_id} cannot be allocated as requested; the known next slot is {bound}."
            )
        bound = max(bound, new_id + 1)

    # Main segment bookkeeping (PD-2) ------------------------------------------------
    main_raw = state_view.get("main_segment")
    main = main_raw if isinstance(main_raw, int) else None
    if main is None and stale:
        raise _unsupported("Main segment ID unknown; stale segments cannot be removed safely.")
    target = main
    if main is not None and main not in desired:
        target = min(desired)
    main_step_first = target is not None and target != main and target in old
    main_step_last = target is not None and target != main and target not in old
    plan_warnings: list[str] = []
    if main_step_last and main in stale:
        plan_warnings.append(
            "main_segment_transient: the firmware sets the main segment to 0 when the old "
            f"main segment is removed; the final step selects ID {target}."
        )
    for new_id in new:
        if new_id < base_bound:
            inherited = [key for key in _RESETTABLE_KEYS if key not in payloads[new_id]]
            if inherited:
                plan_warnings.append(
                    f"inherited_unexposed_state: segment {new_id} reuses an inactive slot; "
                    f"its legacy {', '.join(inherited)} state cannot be observed or reset "
                    "(the device does not report these fields)."
                )
    frozen = [seg.id for seg in sorted(segments, key=lambda s: s.id) if seg.freeze is True]
    if frozen:
        plan_warnings.append(FREEZE_WARNING.format(ids=frozen))

    # Ordering (PD-1) ------------------------------------------------------------------
    layout: Layout = {}
    occupied: dict[int, Rect | None] = {}
    for old_id in sorted(old):
        old_start, old_stop = current[old_id]["start"], current[old_id]["stop"]
        assert isinstance(old_start, int) and isinstance(old_stop, int)
        layout[old_id] = (old_start, old_stop)
        occupied[old_id] = geometry.rect(old_start, old_stop, *_current_y(current[old_id]))
    steps: list[WriteStep] = []
    texts: list[JsonValue] = []
    actions: list[JsonValue] = []
    payload_list: list[JsonValue] = []

    def add(
        action: str,
        seg_id: int | None,
        payload: dict[str, JsonValue],
        text: str,
        fields: dict[str, JsonValue],
        main_expect: int | None,
    ) -> None:
        steps.append(
            WriteStep(
                action,
                seg_id,
                payload,
                _step_check(layout, seg_id, fields, main_expect),
            )
        )
        texts.append(text)
        actions.append(action)
        payload_list.append(payload)

    def blocked(cand: int) -> bool:
        """A step must not create an overlap the final layout does not have."""
        target_rect = rects[cand]
        for other, rect in occupied.items():
            if other == cand or not (rect is None or rect.overlaps(target_rect)):
                continue
            if request.allow_overlap and frozenset((cand, other)) in allowed_pairs:
                continue
            return True
        return False

    main_step_index: int | None = None
    if main_step_first:
        assert target is not None
        main_step_index = len(steps)
        add(
            "set_main",
            None,
            {"mainseg": target},
            f"Redirect main ID to {target} using the validated profile.",
            {},
            target,
        )
    for stale_id in stale:
        del layout[stale_id]
        del occupied[stale_id]
        add(
            "remove",
            stale_id,
            {"seg": {"id": stale_id, "stop": 0}},
            f"Remove ID {stale_id} via a single-object seg payload; verify.",
            {},
            None,
        )

    pending_updates = [i for i in existing if len(payloads[i]) > 1]
    unchanged = [i for i in existing if len(payloads[i]) <= 1]
    pending_creates = list(new)
    while pending_updates or pending_creates:
        candidates = list(pending_updates) + pending_creates[:1]
        chosen: int | None = None
        for cand in candidates:
            if cand in occupied and occupied[cand] == rects[cand]:
                chosen = cand
                break
            if not blocked(cand):
                chosen = cand
                break
        if chosen is None:
            raise _unsupported(
                "No safe intermediate ordering exists without a temporary segment "
                "(overlapping range cycle); nothing was written."
            )
        seg = desired[chosen]
        layout[chosen] = (seg.start, seg.stop)
        occupied[chosen] = rects[chosen]
        seg_payload = payloads[chosen]
        area = _area(seg, geometry)
        if chosen in pending_updates:
            pending_updates.remove(chosen)
            if chosen in geometry_changed:
                text = f"Move ID {chosen} to {area}, preserving omitted fields; verify."
            else:
                text = f"Update ID {chosen} fields; verify."
            action = "update"
        else:
            pending_creates.remove(chosen)
            text = f"Create ID {chosen} at {area} with explicit defaults; verify."
            action = "create"
        add(
            action,
            chosen,
            {"seg": seg_payload},
            text,
            _expectation_from_payload(seg_payload),
            None,
        )
    if main_step_last:
        assert target is not None
        main_step_index = len(steps)
        add(
            "set_main",
            None,
            {"mainseg": target},
            f"Set main ID to {target} after its creation; verify.",
            {},
            target,
        )

    # Final exact check ----------------------------------------------------------------
    final_layout: Layout = {seg.id: (seg.start, seg.stop) for seg in segments}
    final_expect = {i: dict(f) for i, f in expectations.items()}

    def final_matches(state: JsonValue) -> bool:
        if _layout_of(state) != final_layout or not isinstance(state, dict):
            return False
        if target is not None and state.get("mainseg") != target:
            return False
        by_id = _raw_by_id(state)
        for seg_id, fields in final_expect.items():
            raw = by_id.get(seg_id)
            if raw is None or not _fields_match(raw, fields):
                return False
        return True

    unchanged_ids: list[JsonValue] = list(unchanged)
    if not steps:
        plan_warnings.append("The device already matches the requested layout; no write is sent.")
    public: dict[str, JsonValue] = {
        "update_segment_ids": [i for i in existing if i not in unchanged],
        "create_segment_ids": list(new),
        "remove_segment_ids": list(stale),
        "unchanged_segment_ids": unchanged_ids,
        "main_segment_id": target,
        "main_segment": {
            "current": main,
            "target": target,
            "changed": target != main,
            "step": main_step_index,
        },
        "resolved_segments": [resolved_by_id[i] for i in sorted(resolved_by_id)],
        "targeted_compensation": compensation,
        "steps": texts,
        "step_actions": actions,
        "step_payloads": payload_list,
        "warnings": list(plan_warnings),
        "noop": not steps,
    }
    if capability_evidence:
        public["capability_evidence"] = capability_evidence
    if request.allow_overlap:
        public.update(overlap_plan(rects))
    postconditions: list[JsonValue] = [
        "No writes occur during a dry run; a live call re-reads and re-plans under the lock.",
        "After a successful live call the active IDs are exactly "
        f"{sorted(desired)} with the requested ranges.",
        "Omitted fields of existing IDs are preserved; new IDs receive the contract defaults.",
        "No gap fillers, fixed deletion tail, bulk purge, renumbering or master-state change.",
        "On any uncertain or mismatching step the sequence stops: completed and remaining "
        "steps are reported, nothing is replayed, rolled back or corrected.",
    ]
    if request.allow_overlap:
        postconditions.append(
            "Overlapping segments are permitted (allow_overlap); a higher segment ID is "
            "rendered on top, blended with its blend_mode."
        )
    return LayoutPlan(
        sequence=SequencePlan(tuple(steps), final_matches, _observe),
        public=public,
        postconditions=postconditions,
        warnings=plan_warnings,
    )


# ---------------------------------------------------------------------------- geometry


def _current_y(cur: dict[str, JsonValue] | None) -> tuple[int | None, int | None]:
    if cur is None:
        return None, None
    start_y, stop_y = cur.get("start_y"), cur.get("stop_y")
    return (
        start_y if isinstance(start_y, int) else None,
        stop_y if isinstance(stop_y, int) else None,
    )


def _check_matrix_geometry(
    seg: LayoutSegment,
    cur: dict[str, JsonValue] | None,
    cur_y: tuple[int | None, int | None],
    geometry: Geometry,
    *,
    x_moved: bool,
) -> None:
    """Matrix rules (TD-19-7): X columns, explicit rows for a new ID, trailing strip."""
    if geometry.matrix is None:
        return
    ctx = f"Segment {seg.id}: "
    cur_start = cur["start"] if cur is not None else None
    if isinstance(cur_start, int) and geometry.is_trailing(cur_start):
        if x_moved:
            raise _unsupported(
                f"{ctx}is the trailing 1D strip after the matrix; moving it is not supported."
            )
        if seg.start_y is not None and (seg.start_y, seg.stop_y) != cur_y:
            raise _unsupported(
                f"{ctx}is the trailing 1D strip after the matrix; its rows are not changed."
            )
        return
    geometry.check_x(seg.id, seg.start, seg.stop)
    if cur is None and seg.start_y is None:
        raise _fail(f"{ctx}on a matrix a new segment needs explicit start_y and stop_y.")
    if seg.start_y is not None and seg.stop_y is not None:
        geometry.check_y(seg.id, seg.start_y, seg.stop_y)


def _area(seg: LayoutSegment, geometry: Geometry) -> str:
    text = f"[{seg.start},{seg.stop})"
    if geometry.matrix is not None and seg.start_y is not None:
        text += f" rows [{seg.start_y},{seg.stop_y})"
    return text


# ---------------------------------------------------------------------------- per segment


def _public(
    seg_id: int,
    start: int,
    stop: int,
    on: bool | None,
    brightness: int | None,
    colors: list[list[int]] | None,
    channels: int | None,
    values: dict[str, JsonValue],
    name: str | None,
) -> dict[str, JsonValue]:
    effective = brightness if on else 0
    if on is None or brightness is None:
        effective = None
    resolved: dict[str, JsonValue] = {
        "id": seg_id,
        "start": start,
        "stop": stop,
        "on": on,
        "brightness": brightness,
        "effective_brightness": effective,
        "colors": [list(slot) for slot in colors] if colors is not None else None,
        "color_channels": channels,
        "name": name,
    }
    resolved.update(values)
    return resolved


def _new_field_values(
    seg: LayoutSegment, device: DeviceCapabilities, new_keys: frozenset[str]
) -> dict[str, JsonValue]:
    """#19 values of a new ID: supplied, else the WLED default where the readback proves
    the field (TD-19-6), else ``None`` (not sent). ``frz`` is always reset (stage 1)."""
    values: dict[str, JsonValue] = {}
    if seg.cct is not None:
        values["cct"] = seg.cct
    else:
        values["cct"] = CCT_DEFAULT if "cct" in new_keys else None
    for field in OPTION_FIELDS:
        supplied = getattr(seg, field.name)
        if supplied is not None:
            values[field.name] = supplied
        elif field.wire == "frz" or field.wire in new_keys:
            values[field.name] = field.default
        else:
            values[field.name] = None
    values["start_y"] = seg.start_y
    values["stop_y"] = seg.stop_y
    for name, _wire in ORIENTATION_FIELDS:
        supplied = getattr(seg, name)
        values[name] = (
            supplied if supplied is not None else (False if device.matrix is not None else None)
        )
    return values


def _resolve_new(
    seg: LayoutSegment,
    colors: list[list[int]] | None,
    device: DeviceCapabilities,
    new_keys: frozenset[str],
) -> dict[str, JsonValue]:
    assert colors is not None
    width = len(colors[0])
    slots = [list(slot) for slot in colors] + [[0] * width for _ in range(3 - len(colors))]
    values: dict[str, JsonValue] = {}
    for public, _wire in _SIMPLE_FIELDS:
        supplied = getattr(seg, public)
        values[public] = supplied if supplied is not None else _DEFAULTS[public]
    values.update(_new_field_values(seg, device, new_keys))
    on = seg.on if seg.on is not None else True
    brightness = seg.brightness if seg.brightness is not None else 255
    name = seg.name if seg.name is not None else ""
    return _public(seg.id, seg.start, seg.stop, on, brightness, slots, width, values, name)


def _create_payload(seg: LayoutSegment, resolved: dict[str, JsonValue]) -> dict[str, JsonValue]:
    payload: dict[str, JsonValue] = {
        "id": seg.id,
        "start": seg.start,
        "stop": seg.stop,
        "on": resolved["on"],
        "bri": resolved["brightness"],
        "col": resolved["colors"],
        "frz": resolved["freeze"],
        "n": resolved["name"],
    }
    for public, wire in _SIMPLE_FIELDS:
        payload[wire] = resolved[public]
    for public, wire in SEGMENT_FIELDS:
        if resolved[public] is not None and wire not in payload:
            payload[wire] = resolved[public]
    return payload


def _update_plan(
    seg: LayoutSegment,
    cur: dict[str, JsonValue],
    cur_name: str | None,
    colors: list[list[int]] | None,
    power: SegmentPower,
    moved: bool,
    y_moved: bool = False,
) -> tuple[dict[str, JsonValue], dict[str, JsonValue], list[JsonValue]]:
    ctx = f"Segment {seg.id}: "
    length = seg.stop - seg.start
    payload: dict[str, JsonValue] = {"id": seg.id}
    compensation: list[JsonValue] = []
    if moved:
        payload["start"] = seg.start
        payload["stop"] = seg.stop
        cur_offset = cur["offset"]
        if seg.offset is None:
            if not isinstance(cur_offset, int):
                raise _unsupported(f"{ctx}unrepresentable preservation plan (offset unknown).")
            if cur_offset >= length:
                raise _fail(
                    f"{ctx}the existing offset would be clamped by the firmware; "
                    "supply offset explicitly."
                )
    if y_moved:
        # Rows only: the firmware keeps the name (json.cpp L144-151 compares start/stop).
        payload["startY"] = seg.start_y
        payload["stopY"] = seg.stop_y
    # Power and brightness (ISSUE-48-DEC-001, shared with #6): an explicit on accompanies a
    # sent bri; a positive bri with omitted on on an off segment is sent with the resolved
    # on=false (targeted compensation), because the firmware would otherwise switch the
    # segment on. On a segment that is on, bri is sent alone (the firmware keeps it on).
    cur_on = cur["on"]
    if seg.brightness is not None:
        if seg.brightness == 0:
            if cur_on is not False:
                payload["bri"] = 0
                payload["on"] = False
        elif cur["brightness"] != seg.brightness:
            payload["bri"] = seg.brightness
            if power.compensate_off:
                payload["on"] = False
                compensation.append({"id": seg.id, "on": False})
    if seg.on is not None and "on" not in payload and (seg.on != cur_on or "bri" in payload):
        payload["on"] = seg.on
    if colors is not None:
        current_colors = cur["colors"]
        same = isinstance(current_colors, list) and current_colors[: len(colors)] == colors
        if not same:
            payload["col"] = [list(slot) for slot in colors]
    for public, wire in _SIMPLE_FIELDS:
        supplied = getattr(seg, public)
        if supplied is not None and supplied != cur[public]:
            payload[wire] = supplied
    for public, wire in SEGMENT_FIELDS:
        if public in ("start_y", "stop_y"):
            continue
        supplied = getattr(seg, public)
        if supplied is not None and supplied != cur.get(public):
            payload[wire] = supplied
    # Name: geometry changes clear the name in profile 0, so resend it.
    resolved_name = seg.name if seg.name is not None else cur_name
    if moved and resolved_name is None:
        raise _unsupported(f"{ctx}unrepresentable preservation plan (name unknown).")
    if seg.name is not None and seg.name != cur_name:
        payload["n"] = seg.name
    elif moved and resolved_name:
        payload["n"] = resolved_name
        if seg.name is None:
            compensation.append({"id": seg.id, "name": resolved_name})

    values: dict[str, JsonValue] = {}
    for public, _wire in _SIMPLE_FIELDS:
        supplied = getattr(seg, public)
        values[public] = supplied if supplied is not None else cur[public]
    for public, _wire in SEGMENT_FIELDS:
        supplied = getattr(seg, public)
        values[public] = supplied if supplied is not None else cur.get(public)
    brightness = seg.brightness if seg.brightness is not None else cur["brightness"]
    brightness_value = brightness if isinstance(brightness, int) else None
    if colors is not None:
        current_slots = _int_slots(cur["colors"])
        resolved_colors: list[list[int]] | None = [list(slot) for slot in colors] + (
            current_slots[len(colors) :] if current_slots is not None else []
        )
    else:
        resolved_colors = _int_slots(cur["colors"])
    channels = cur["color_channels"]
    if colors is not None:
        channels = len(colors[0])
    resolved = _public(
        seg.id,
        seg.start,
        seg.stop,
        power.resolved_on,
        brightness_value,
        resolved_colors,
        channels if isinstance(channels, int) else None,
        values,
        resolved_name,
    )
    return resolved, payload, compensation
