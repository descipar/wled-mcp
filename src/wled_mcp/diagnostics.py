"""Runtime diagnostics: correlation IDs, bounded call logs and the service monitor (issue #20).

Everything here is local and passive. The call log is one structured line per tool call on
stderr (stdout is reserved for stdio MCP) built only from an allowlist of fields whose values
come from fixed sets or from configuration, never from arguments, URLs, headers, bodies or
credentials. The monitor keeps the last observed outcome per configured device, written by an
observer on the device client, so it adds no request and never turns "not observed" into
"healthy". Nothing is sent anywhere and no file is written.
"""

import json
import logging
import secrets
import sys
import time
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, cast, get_args

from wled_mcp.access import ToolClass
from wled_mcp.config import ConfigurationError
from wled_mcp.models import ErrorCode

LOG_LEVEL_ENV = "WLED_MCP_LOG_LEVEL"
LOG_FORMAT_ENV = "WLED_MCP_LOG_FORMAT"
LOG_LINE_LIMIT = 512
CALL_LOGGER = logging.getLogger("wled_mcp.calls")
PACKAGE_LOGGER = logging.getLogger("wled_mcp")

LogLevel = Literal["warning", "info"]
LogFormat = Literal["text", "json"]
LOG_LEVELS: tuple[str, ...] = get_args(LogLevel)
LOG_FORMATS: tuple[str, ...] = get_args(LogFormat)
_LEVELS = {"warning": logging.WARNING, "info": logging.INFO}

# Error codes the call log and the counters may carry: the domain codes plus two
# dispatcher-level outcomes that have no envelope.
UNKNOWN_TOOL = "UNKNOWN_TOOL"
INTERNAL_FAILURE = "INTERNAL_FAILURE"
LOGGED_ERROR_CODES: frozenset[str] = frozenset(get_args(ErrorCode)) | {
    UNKNOWN_TOOL,
    INTERNAL_FAILURE,
}


def new_correlation_id() -> str:
    """16 lowercase hex characters from the OS CSPRNG; never derived from client input."""
    return secrets.token_hex(8)


# ------------------------------------------------------------------------------ call log


@dataclass(frozen=True)
class CallRecord:
    """What one tool call may reveal to a log line; every field is bounded by construction."""

    tool: str
    correlation_id: str
    duration_ms: int
    ok: bool
    tool_class: ToolClass | None = None
    device_id: str | None = None
    application: str | None = None
    verification: str | None = None
    error_code: str | None = None

    def fields(self) -> dict[str, str | int | bool]:
        """The allowlisted line fields in a fixed order; absent facts are omitted."""
        candidates: list[tuple[str, str | int | bool | None]] = [
            ("event", "tool_call"),
            ("tool", self.tool),
            ("class", None if self.tool_class is None else self.tool_class.value),
            ("device_id", self.device_id),
            ("ok", self.ok),
            ("application", self.application),
            ("verification", self.verification),
            ("error_code", self.error_code),
            ("duration_ms", self.duration_ms),
            ("correlation_id", self.correlation_id),
        ]
        return {key: value for key, value in candidates if value is not None}


def _render_text(fields: Mapping[str, str | int | bool]) -> str:
    return " ".join(
        f"{key}={str(value).lower() if isinstance(value, bool) else value}"
        for key, value in fields.items()
    )


def log_call(record: CallRecord) -> None:
    """Emit one line: INFO when the call succeeded, WARNING when it failed."""
    fields = record.fields()
    CALL_LOGGER.log(
        logging.INFO if record.ok else logging.WARNING,
        "%s",
        _render_text(fields),
        extra={"call_fields": fields},
    )


class LineFormatter(logging.Formatter):
    """Text or JSON, one bounded line per record, for every ``wled_mcp`` logger."""

    def __init__(self, fmt: LogFormat = "text") -> None:
        super().__init__()
        self.fmt = fmt

    def format(self, record: logging.LogRecord) -> str:
        stamp = datetime.fromtimestamp(record.created, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        message = record.getMessage().replace("\r", " ").replace("\n", " ")
        fields = getattr(record, "call_fields", None)
        if self.fmt == "json":
            document: dict[str, Any] = {"ts": stamp, "level": record.levelname.lower()}
            if isinstance(fields, dict):
                document.update(fields)
            else:
                document.update(logger=record.name, message=message)
            line = json.dumps(document, ensure_ascii=True, separators=(",", ":"))
            if len(line) > LOG_LINE_LIMIT and "message" in document:
                excess = len(line) - LOG_LINE_LIMIT
                document["message"] = message[: max(0, len(message) - excess - 8)] + "..."
                line = json.dumps(document, ensure_ascii=True, separators=(",", ":"))
            return line
        line = f"{stamp} {record.levelname} {record.name}: {message}"
        if len(line) > LOG_LINE_LIMIT:
            line = line[: LOG_LINE_LIMIT - 3] + "..."
        return line


@dataclass(frozen=True)
class LogSettings:
    level: LogLevel = "warning"
    fmt: LogFormat = "text"


def load_log_settings(environ: Mapping[str, str]) -> LogSettings:
    """Read the two logging variables; an invalid value is named by variable, never echoed."""
    level = environ.get(LOG_LEVEL_ENV, "warning").strip().lower() or "warning"
    fmt = environ.get(LOG_FORMAT_ENV, "text").strip().lower() or "text"
    if level not in LOG_LEVELS:
        raise ConfigurationError(f"{LOG_LEVEL_ENV}: unsupported value (use warning or info).")
    if fmt not in LOG_FORMATS:
        raise ConfigurationError(f"{LOG_FORMAT_ENV}: unsupported value (use text or json).")
    return LogSettings(level=cast(LogLevel, level), fmt=cast(LogFormat, fmt))


_INSTALLED = "_wled_mcp_handler"


class _StderrHandler(logging.StreamHandler):  # type: ignore[type-arg]
    """Writes to whatever ``sys.stderr`` is at emit time (never stdout, which is MCP's)."""

    def __init__(self) -> None:
        super().__init__(sys.stderr)

    @property
    def stream(self) -> Any:
        return sys.stderr

    @stream.setter
    def stream(self, value: Any) -> None:
        return None


def configure_logging(settings: LogSettings) -> logging.Handler:
    """Route ``wled_mcp`` records to stderr in the selected format; idempotent.

    Only the package logger takes the configured level; the root logger and third-party
    libraries (whose INFO lines can contain device URLs) stay at WARNING.
    """
    root = logging.getLogger()
    handler = next((h for h in root.handlers if getattr(h, _INSTALLED, False)), None)
    if handler is None:
        handler = _StderrHandler()
        setattr(handler, _INSTALLED, True)
        root.addHandler(handler)
    handler.setFormatter(LineFormatter(settings.fmt))
    if root.level == logging.NOTSET or root.level > logging.WARNING:
        root.setLevel(logging.WARNING)
    PACKAGE_LOGGER.setLevel(_LEVELS[settings.level])
    return handler


# ---------------------------------------------------------------------------- the monitor


@dataclass(frozen=True)
class Observation:
    """The last outcome of a request this process sent to one configured device."""

    at: float
    error_code: str | None  # None: the request succeeded


class ServiceMonitor:
    """Process-local counters and per-device last-observed outcomes; no I/O, no requests."""

    def __init__(
        self,
        device_ids: Iterable[str] = (),
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        self._clock = monotonic if monotonic is not None else time.monotonic
        self.started_at = self._clock()
        self.device_ids: tuple[str, ...] = tuple(device_ids)
        self.transport = "unknown"
        # None until a startup check ran; never reported as writable without one.
        self.backups_writable: bool | None = None
        self._observed: dict[str, Observation] = {}
        self._calls: Counter[str] = Counter()
        self._classes: Counter[str] = Counter()
        self._errors: Counter[str] = Counter()

    # -- device observations --------------------------------------------------------

    def is_configured(self, device_id: object) -> bool:
        return isinstance(device_id, str) and device_id in self.device_ids

    def observe(self, device_id: str, error_code: str | None) -> None:
        """Record the outcome of one request that reached the transport."""
        if device_id in self.device_ids:
            self._observed[device_id] = Observation(self._clock(), error_code)

    def device_states(self) -> list[dict[str, Any]]:
        """Readiness per configured device: unknown, reachable or failed, with age."""
        now = self._clock()
        states: list[dict[str, Any]] = []
        for device_id in self.device_ids:
            seen = self._observed.get(device_id)
            if seen is None:
                states.append({"device_id": device_id, "state": "unknown"})
                continue
            entry: dict[str, Any] = {
                "device_id": device_id,
                "state": "reachable" if seen.error_code is None else "failed",
                "age_seconds": max(0, int(now - seen.at)),
            }
            if seen.error_code is not None:
                entry["error_code"] = seen.error_code
            states.append(entry)
        return states

    # -- call counters --------------------------------------------------------------

    def record_call(
        self, tool_class: ToolClass | None, ok: bool, error_code: str | None = None
    ) -> None:
        """Count one dispatched call; keys stay inside fixed sets, so memory is bounded."""
        self._calls["total"] += 1
        self._calls["ok" if ok else "failed"] += 1
        if error_code == UNKNOWN_TOOL:
            self._calls["unknown_tool"] += 1
        elif error_code == INTERNAL_FAILURE:
            self._calls["internal_failure"] += 1
        if tool_class is not None:
            self._classes[tool_class.value] += 1
        if error_code is not None and error_code in LOGGED_ERROR_CODES:
            self._errors[error_code] += 1

    def call_counts(self) -> dict[str, Any]:
        calls = {
            key: self._calls[key]
            for key in ("total", "ok", "failed", "unknown_tool", "internal_failure")
        }
        return {
            **calls,
            "by_class": {
                tool_class.value: self._classes[tool_class.value] for tool_class in ToolClass
            },
            "by_error_code": {code: self._errors[code] for code in sorted(self._errors)},
        }

    def uptime_seconds(self) -> int:
        return max(0, int(self._clock() - self.started_at))
