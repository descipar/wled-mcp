"""``wled_explain_lighting``: read-only, evidence-separated explanation of an ineffective change.

One fresh ``/json/state`` and one fresh ``/json/info`` GET (issue #30, S3-EXPLAIN-01/-02) are
combined with process-local evidence (the last control outcome and the last observed
reachability). The result keeps observed facts, inferred candidate causes and explicit
uncertainty apart. It never writes, stops playback, disables an input, names an actor or
claims causality, and it reads only an allowlist of indicators.
"""

import json
import re
from datetime import datetime, timedelta
from typing import Any, cast

from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from wled_mcp.access import ToolClass
from wled_mcp.client import ClientFailure, Endpoint
from wled_mcp.diagnostics import LastControl
from wled_mcp.models import Outcome
from wled_mcp.readmodels import Collector, as_dict, normalize_state
from wled_mcp.resources import Resources
from wled_mcp.server import Operation

MAX_DATA_BYTES = 32 * 1024
MAX_CAUSES = 16
STALE_AFTER_SECONDS = 300
NAME = "wled_explain_lighting"

LIMITS: tuple[str, ...] = (
    "Single non-atomic snapshot of /json/state and /json/info; no history and no "
    "continuous observation.",
    "Candidate causes are not causality proof and never name an actor; the origin of a "
    "control or realtime input is not attributed.",
    "Process-memory evidence is lost on restart; entries older than 300 seconds are stale.",
    "Only allowlisted indicators are read; realtime, sync and network configuration are "
    "not inspected, and a missing indicator is unknown, never false.",
)
UNATTRIBUTED_LIMIT = (
    "No observed indicator explains the reported change; the absence of an indicator does "
    "not prove the absence of a cause."
)

_SAFE_TEXT = re.compile(r"[A-Za-z][A-Za-z0-9 .+_-]{0,31}")
_ADDRESS_LIKE = re.compile(r"\d+\.\d+\.\d+")
_SAFE_VERSION = re.compile(r"[0-9][0-9A-Za-z.+_-]{0,31}")


class RequestedChange(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    white_channel: bool | None = Field(
        default=None, description="The change needs a white channel on the segment."
    )
    effect_id: int | None = Field(default=None, ge=0, le=65535, description="Effect ID to check.")
    palette_id: int | None = Field(default=None, ge=0, le=65535, description="Palette ID to check.")


class ExplainRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    device_id: str = Field(min_length=1, max_length=64, description="Configured controller ID.")
    segment_id: int | None = Field(
        default=None, ge=0, le=65535, description="Segment the change was meant for."
    )
    requested: RequestedChange | None = Field(
        default=None,
        description="Optional requested properties checked against reported capability ranges.",
    )


# --------------------------------------------------------------------------- evidence


def _typed(value: JsonValue, kind: str) -> tuple[str, JsonValue]:
    """(status, bounded value) of one raw indicator; absent is unknown, mistyped unavailable."""
    if value is None:
        return "unknown", None
    if kind == "bool" and isinstance(value, bool):
        return "observed", value
    if kind == "int" and isinstance(value, int) and not isinstance(value, bool):
        if -1 <= value <= 1_000_000:
            return "observed", value
        return "unavailable", None
    if kind == "lor" and isinstance(value, int) and not isinstance(value, bool):
        return ("observed", value) if 0 <= value <= 2 else ("unavailable", None)
    if kind == "text" and isinstance(value, str):
        ok = _SAFE_TEXT.fullmatch(value) and not _ADDRESS_LIKE.search(value)
        return "observed", value if ok else "other"
    if kind == "version" and isinstance(value, str):
        return "observed", value if _SAFE_VERSION.fullmatch(value) else "other"
    return "unavailable", None


# id, kind, source, key path, value kind
INDICATORS: tuple[tuple[str, str, str, tuple[str, ...], str], ...] = (
    ("state.on", "device_state", "/json/state", ("on",), "bool"),
    ("state.bri", "device_state", "/json/state", ("bri",), "int"),
    ("state.pl", "playback", "/json/state", ("pl",), "int"),
    ("state.ps", "playback", "/json/state", ("ps",), "int"),
    ("state.nl.on", "nightlight", "/json/state", ("nl", "on"), "bool"),
    ("state.lor", "realtime", "/json/state", ("lor",), "lor"),
    ("state.udpn.recv", "sync", "/json/state", ("udpn", "recv"), "bool"),
    ("info.live", "realtime", "/json/info", ("live",), "bool"),
    ("info.lm", "realtime", "/json/info", ("lm",), "text"),
    ("info.ver", "capability", "/json/info", ("ver",), "version"),
    ("info.leds.count", "capability", "/json/info", ("leds", "count"), "int"),
    ("info.fxcount", "capability", "/json/info", ("fxcount",), "int"),
    ("info.palcount", "capability", "/json/info", ("palcount",), "int"),
)


def _dig(root: dict[str, JsonValue], path: tuple[str, ...]) -> JsonValue:
    node: JsonValue = root
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def _observation(
    ident: str,
    kind: str,
    source: str,
    status: str,
    value: JsonValue,
    at: datetime | None,
    now: datetime,
) -> dict[str, JsonValue]:
    age = None if at is None else max(0, int((now - at).total_seconds()))
    return {
        "id": ident,
        "kind": kind,
        "source": source,
        "observed_at": None if at is None else at.isoformat(),
        "age_seconds": age,
        "stale": age is not None and source == "process_memory" and age > STALE_AFTER_SECONDS,
        "status": status,
        "value": value,
        "missing_indicator": status == "unknown",
    }


def _last_control_observation(record: LastControl | None, now: datetime) -> dict[str, JsonValue]:
    if record is None:
        return _observation(
            "last_control", "last_control", "process_memory", "unknown", None, None, now
        )
    value: dict[str, JsonValue] = {
        "operation": record.operation,
        "application": record.application,
        "verification": record.verification,
        "error_code": record.error_code,
    }
    return _observation(
        "last_control", "last_control", "process_memory", "observed", value, record.finished_at, now
    )


def _cause(
    code: str,
    confidence: str,
    evidence: list[str],
    statement: str,
    next_checks: list[str],
    contradicting: list[str] | None = None,
) -> dict[str, JsonValue]:
    return {
        "code": code,
        "confidence": confidence,
        "evidence": cast(list[JsonValue], evidence),
        "contradicting_evidence": cast(list[JsonValue], contradicting or []),
        "statement": statement,
        "next_checks": cast(list[JsonValue], next_checks),
    }


READ_STATE = "Read wled_get_state for the full normalized state (a read-only check)."


def _requested_checks(
    requested: RequestedChange | None,
    segment_id: int | None,
    segments: list[JsonValue],
    values: dict[str, JsonValue],
    now: datetime,
) -> tuple[list[dict[str, JsonValue]], list[dict[str, JsonValue]]]:
    """Range and capability checks only; no catalog read."""
    observations: list[dict[str, JsonValue]] = []
    causes: list[dict[str, JsonValue]] = []
    if requested is None:
        return observations, causes

    def record(ident: str, supported: bool | None, evidence: list[str], statement: str) -> None:
        status = "unknown" if supported is None else "observed"
        observations.append(
            _observation(
                ident, "capability", "/json/info", status, {"supported": supported}, now, now
            )
        )
        if supported is False:
            causes.append(
                _cause(
                    "REQUESTED_CAPABILITY_UNSUPPORTED",
                    "high",
                    evidence,
                    statement,
                    ["Read wled_get_effects, wled_get_palettes or wled_get_state for valid IDs."],
                )
            )

    for field, count_key, label in (
        ("effect_id", "info.fxcount", "effect"),
        ("palette_id", "info.palcount", "palette"),
    ):
        wanted = getattr(requested, field)
        if wanted is None:
            continue
        count = values.get(count_key)
        supported = None if not isinstance(count, int) else wanted < count
        record(
            f"capability.{field}",
            supported,
            [count_key],
            f"The requested {label} ID is outside the range this firmware reports.",
        )
    if requested.white_channel:
        chosen = [
            as_dict(s)
            for s in segments
            if (segment_id is not None and as_dict(s).get("id") == segment_id)
            or (segment_id is None and as_dict(s).get("start") != as_dict(s).get("stop"))
        ]
        flags = [as_dict(as_dict(s).get("reported_color_capability")) for s in chosen]
        known = [f["white"] for f in flags if isinstance(f.get("white"), bool)]
        supported = None if not known else any(known)
        record(
            "capability.white_channel",
            supported,
            ["info.leds.count"],
            "The selected segment reports no white channel.",
        )
    return observations, causes


def explain(
    request: ExplainRequest,
    state: JsonValue,
    info: JsonValue,
    last: LastControl | None,
    started: datetime,
    now: datetime,
) -> dict[str, JsonValue]:
    """The result document from one state/info pair and process memory; pure."""
    state_d, info_d = as_dict(state), as_dict(info)
    observations: list[dict[str, JsonValue]] = []
    values: dict[str, JsonValue] = {}
    for ident, kind, source, path, value_kind in INDICATORS:
        root = state_d if source == "/json/state" else info_d
        status, value = _typed(_dig(root, path), value_kind)
        values[ident] = value
        observations.append(_observation(ident, kind, source, status, value, now, now))
    # The capability model needs a well-formed pair; an unusable one only loses that check.
    segments: list[JsonValue] = []
    try:
        view, _, _, _ = normalize_state(state, info, Collector())
        segments = cast(list[JsonValue], view["segments"])
    except ClientFailure:
        pass
    if request.segment_id is not None and state_d.get("seg") is not None:
        raw = state_d.get("seg")
        ids = {as_dict(s).get("id") for s in raw} if isinstance(raw, list) else set()
        if request.segment_id not in ids:
            raise ClientFailure("VALIDATION_ERROR", "The segment ID is not in the device state.")
    extra_obs, causes = _requested_checks(
        request.requested, request.segment_id, segments, values, now
    )
    observations.extend(extra_obs)
    last_obs = _last_control_observation(last, now)
    observations.append(last_obs)
    stale = bool(last_obs["stale"])

    on, bri = values["state.on"], values["state.bri"]
    if on is False or bri == 0:
        causes.append(
            _cause(
                "MASTER_OFF_OR_ZERO_BRIGHTNESS",
                "high",
                ["state.on", "state.bri"],
                "Master power is off or master brightness is zero, so segment changes are "
                "not visible.",
                [READ_STATE, "Decide manually whether master power or brightness should change."],
            )
        )
    pl = values["state.pl"]
    if isinstance(pl, int) and pl >= 0:
        causes.append(
            _cause(
                "PLAYBACK_ACTIVE",
                "medium",
                ["state.pl", "state.ps"],
                "A playlist is reported as running; it can replace the light state when it "
                "advances.",
                ["Read wled_list_presets to inspect it; stopping playback is a manual decision."],
            )
        )
    if values["info.live"] is True:
        override = values["state.lor"]
        weakened = isinstance(override, int) and override > 0
        causes.append(
            _cause(
                "REALTIME_INPUT_ACTIVE",
                "low" if weakened else "medium",
                ["info.live", "info.lm", "state.lor"],
                "The device reports receiving realtime data, which can override the "
                "configured light state.",
                ["Check manually which realtime source is configured; it is not inspected here."],
                ["state.lor"] if weakened else None,
            )
        )
    if values["state.nl.on"] is True:
        causes.append(
            _cause(
                "NIGHTLIGHT_ACTIVE",
                "medium",
                ["state.nl.on"],
                "A nightlight fade is reported as active and can change brightness over time.",
                [READ_STATE],
            )
        )
    if values["state.udpn.recv"] is True:
        causes.append(
            _cause(
                "SYNC_RECEIVE_ENABLED",
                "low",
                ["state.udpn.recv"],
                "UDP sync receive is enabled, so another sender could change this device; "
                "that is a possibility, not an observed event.",
                ["Review the device's sync settings manually; they are not read by this tool."],
            )
        )
    indicator_causes = len(causes)
    if last is not None and last.verification == "mismatch":
        causes.append(
            _cause(
                "LAST_WRITE_VERIFICATION_MISMATCH",
                "low" if stale else "medium",
                ["last_control"],
                "The last control outcome this process recorded did not read back as requested.",
                [READ_STATE],
            )
        )
    elif last is not None and last.application == "unknown":
        causes.append(
            _cause(
                "LAST_WRITE_UNCERTAIN",
                "low" if stale else "medium",
                ["last_control"],
                "The last control outcome this process recorded may or may not have been applied.",
                [READ_STATE, "Do not replay the write; reconcile from a fresh read."],
            )
        )
    limits = list(LIMITS)
    if indicator_causes == 0:
        limits.append(UNATTRIBUTED_LIMIT)
        causes.append(
            _cause(
                "UNATTRIBUTED_MISMATCH",
                "unknown",
                [],
                "No observed indicator attributes the reported ineffective change.",
                ["Compare wled_get_state with the intended state and retry the read later."],
            )
        )
        causes.append(
            _cause(
                "INSUFFICIENT_EVIDENCE",
                "unknown",
                [],
                "The available indicators are insufficient to name a candidate cause.",
                ["Read wled_get_live_snapshot for sampled output colors (a read-only check)."],
            )
        )
    if any(c["confidence"] == "high" for c in causes):
        conclusion = "observed_blocker"
    elif indicator_causes:
        conclusion = "candidates_only"
    else:
        conclusion = "insufficient_evidence"
    version = values["info.ver"]
    vid = info_d.get("vid")
    return {
        "device_id": request.device_id,
        "read_started_at": started.isoformat(),
        "captured_at": now.isoformat(),
        "firmware": {
            "version": version,
            "build_id": vid if isinstance(vid, int) and not isinstance(vid, bool) else None,
        },
        "observations": cast(list[JsonValue], observations),
        "inferred_causes": cast(list[JsonValue], causes),
        "conclusion": conclusion,
        "limits": cast(list[JsonValue], limits),
    }


def _checked(data: dict[str, JsonValue]) -> dict[str, JsonValue]:
    causes = data.get("inferred_causes")
    too_many = isinstance(causes, list) and len(causes) > MAX_CAUSES
    if too_many or len(json.dumps(data, separators=(",", ":")).encode("utf-8")) > MAX_DATA_BYTES:
        raise ClientFailure("INVALID_RESPONSE", "Explanation exceeds the output size limit.")
    return data


def _failure_document(
    request: ExplainRequest,
    failure: ClientFailure,
    before: dict[str, Any] | None,
    last: LastControl | None,
    started: datetime,
    now: datetime,
) -> dict[str, JsonValue]:
    """Unreachable/timeout: process memory only, never an invented device observation."""
    observations: list[dict[str, JsonValue]] = []
    if before is not None and before.get("state") != "unknown":
        age = int(before.get("age_seconds", 0))
        reachable = before["state"] == "reachable"
        observations.append(
            _observation(
                "reachability",
                "reachability",
                "process_memory",
                "observed",
                {
                    "state": "reachable" if reachable else "failed",
                    "error_code": before.get("error_code"),
                },
                now - timedelta(seconds=age),
                now,
            )
        )
    else:
        observations.append(
            _observation(
                "reachability", "reachability", "process_memory", "unknown", None, None, now
            )
        )
    observations.append(_last_control_observation(last, now))
    code = "DEVICE_TIMEOUT" if failure.error.code == "TIMEOUT" else "DEVICE_UNREACHABLE"
    causes = [
        _cause(
            code,
            "medium",
            ["reachability"],
            "This read did not complete, so the device state is unknown; a light change "
            "may not have reached the device.",
            ["Run the doctor command or wled_list_devices with probe=true to check reachability."],
        )
    ]
    return {
        "device_id": request.device_id,
        "read_started_at": started.isoformat(),
        "captured_at": now.isoformat(),
        "observations": cast(list[JsonValue], observations),
        "inferred_causes": cast(list[JsonValue], causes),
        "conclusion": "candidates_only",
        "limits": cast(list[JsonValue], list(LIMITS)),
    }


def build_explain_operation(resources: Resources) -> Operation:
    async def execute(arguments: dict[str, Any]) -> Outcome:
        request = ExplainRequest.model_validate(arguments)
        device_id = request.device_id
        known = any(d.id == device_id for d in resources.inventory)
        monitor = resources.monitor
        before = next((s for s in monitor.device_states() if s["device_id"] == device_id), None)
        last = monitor.last_control.latest(device_id)
        started = resources.clock.now()
        try:
            async with resources.operation(device_id) as context:
                started = resources.clock.now()
                state = await context.read(Endpoint.STATE)
                info = await context.read(Endpoint.INFO)
                now = resources.clock.now()
            data = _checked(explain(request, state, info, last, started, now))
            return Outcome(
                ok=True,
                operation=NAME,
                device_id=device_id,
                application="not_attempted",
                verification="not_requested",
                data=data,
            )
        except ClientFailure as failure:
            data = {}
            if known and failure.error.code in {"UNREACHABLE", "TIMEOUT"}:
                data = _failure_document(
                    request, failure, before, last, started, resources.clock.now()
                )
            return Outcome(
                ok=False,
                operation=NAME,
                device_id=device_id if known else None,
                application="not_attempted",
                verification="not_requested",
                data=data,
                error=failure.error,
            )

    return Operation(
        name=NAME,
        tool_class=ToolClass.READ,
        description=(
            "Explain why a light change may not appear or persist on one configured device. "
            "Reads fresh state and info once, adds process-local evidence and returns observed "
            "facts, candidate causes with confidence, explicit insufficient-evidence statements "
            "and next checks. Never writes, stops playback or names an actor; no causality proof."
        ),
        request_model=ExplainRequest,
        execute=execute,
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
        ),
    )
