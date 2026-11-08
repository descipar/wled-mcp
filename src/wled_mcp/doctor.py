"""Read-only ``wled-mcp doctor`` diagnostics (issue #16, S2-SETUP-03, OPS-04).

Contract: docs/contract/cli.md. Checks run in a fixed order and fixed categories:
``runtime``, ``configuration``, ``storage``, ``device`` and, only with an explicit
``--endpoint``, ``endpoint``. Doctor writes nothing: no device POST, no configuration,
data-directory or backup change. Device checks call the registered read-only
``wled_get_state`` operation in-process and read only its versioned result envelope
(``error.code``, ``data.firmware`` and ``data.diagnostics``); the firmware policy stays
in ``compat`` (TD-21-6).
"""

import argparse
import json
import platform
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, get_args
from urllib.parse import urlsplit, urlunsplit

import anyio
import httpx2 as httpx

from wled_mcp import __version__, compat
from wled_mcp.config import (
    MAX_CONFIG_BYTES,
    ConfigurationError,
    InventoryConfig,
    StartupConfig,
    validate_document,
)
from wled_mcp.http_config import ENDPOINT_PATH, TOKEN_ENV, resolve_token
from wled_mcp.setup import (
    CONFIG_ENV,
    DATA_ENV,
    EXIT_OK,
    EXIT_PROBLEM,
    JSON_SCHEMA_VERSION,
    add_format_option,
    backups_writable,
    option_path,
)

Category = Literal["runtime", "configuration", "storage", "device", "endpoint"]
Status = Literal["ok", "warning", "failed", "skipped"]
CATEGORIES: tuple[Category, ...] = get_args(Category)
MAX_PARALLEL_DEVICES = 8
ENDPOINT_TIMEOUT_SECONDS = 10.0
MAX_ENDPOINT_BODY = 65536
_MAX_FIRMWARE_TEXT = 64
_PROTOCOL_VERSION = "2025-11-25"

# OPS-04 conditions and the doctor result that reports each (S16-T08).
OPS04_CONDITIONS: Mapping[str, tuple[str, ...]] = {
    "bad configuration": ("CONFIG_INVALID", "CONFIG_NOT_FOUND", "CONFIG_PATH_NOT_ABSOLUTE"),
    "unsupported firmware": ("FIRMWARE_UNSUPPORTED", "FIRMWARE_UNRECOGNIZED"),
    "unavailable backup storage": ("BACKUPS_NOT_WRITABLE", "DATA_DIR_NOT_FOUND"),
    "offline device": ("DEVICE_UNREACHABLE", "DEVICE_TIMEOUT"),
    "invalid response": ("DEVICE_INVALID_RESPONSE",),
}

ACTIONS: Mapping[str, str] = {
    "CONFIG_PATH_MISSING": "Pass --config or set WLED_MCP_CONFIG.",
    "CONFIG_PATH_NOT_ABSOLUTE": "Use an absolute configuration path.",
    "CONFIG_NOT_FOUND": "Create it with `wled-mcp config init` or fix the path.",
    "CONFIG_UNREADABLE": "Check the file permissions and that the path is a regular file.",
    "CONFIG_INVALID": "Fix the named entries and run `wled-mcp config validate`.",
    "DATA_DIR_MISSING": "Pass --data-dir or set WLED_MCP_DATA_DIR.",
    "DATA_DIR_NOT_ABSOLUTE": "Use an absolute data directory path.",
    "DATA_DIR_NOT_FOUND": "Create the data directory; the server never creates it.",
    "BACKUPS_NOT_WRITABLE": (
        "Make <data-dir>/backups (or the data directory) writable for the service user; "
        "snapshot-taking writes fail with BACKUP_FAILED until then."
    ),
    "DEVICES_NONE": "Add a device with `wled-mcp config add-device`.",
    "DEVICE_UNREACHABLE": "Check power, network path and the configured base_url.",
    "DEVICE_TIMEOUT": "Check the network path or raise http.operation_timeout_seconds.",
    "DEVICE_INVALID_RESPONSE": "Check that the base_url points at a WLED controller.",
    "DEVICE_READ_FAILED": "Read the device with wled_get_state for the full error.",
    "FIRMWARE_UNSUPPORTED": "Update WLED to 16.0.0 or later (docs/contract/compatibility.md).",
    "FIRMWARE_UNRECOGNIZED": "Check the firmware build; see docs/contract/compatibility.md.",
    "CAPABILITIES_UNKNOWN": "Fields are reported as unknown; tools stay conservative.",
    "PLATFORM_EXPERIMENTAL": "See the support matrix in docs/contract/compatibility.md.",
    "PLATFORM_UNTESTED": "See the support matrix in docs/contract/compatibility.md.",
    "PYTHON_UNTESTED": "Use the Python version listed in docs/contract/compatibility.md.",
    "BUILD_UNKNOWN": "Install the package; a source tree has no version metadata.",
    "ENDPOINT_URL_INVALID": "Pass an http(s) URL without credentials, query or fragment.",
    "ENDPOINT_CREDENTIAL_MISSING": f"Set {TOKEN_ENV} or pass --http-token-file.",
    "ENDPOINT_CREDENTIAL_INVALID": "Use the same credential file or value as the service.",
    "ENDPOINT_UNREACHABLE": "Check that the service runs and the URL, port and network path.",
    "ENDPOINT_TIMEOUT": "Check that the service runs and responds.",
    "ENDPOINT_HOST_ORIGIN_REJECTED": (
        "Add the URL's host[:port] with --allowed-host on the service (Host/Origin check)."
    ),
    "ENDPOINT_CREDENTIAL_REJECTED": "Use the credential the service was started with.",
    "ENDPOINT_PROTOCOL_ERROR": "Check that the URL points at the MCP endpoint (/mcp).",
    "ENDPOINT_OTHER_SERVER": "The endpoint answers MCP but is not wled-mcp.",
}


@dataclass(frozen=True)
class Check:
    category: Category
    status: Status
    code: str
    message: str
    device_index: int | None = None
    device_id: str | None = None
    # Export-safe facts only (see ``export``).
    facts: dict[str, Any] = field(default_factory=dict)

    @property
    def action(self) -> str | None:
        return ACTIONS.get(self.code) if self.status in ("failed", "warning") else None


@dataclass
class Report:
    checks: list[Check] = field(default_factory=list)
    runtime: dict[str, Any] = field(default_factory=dict)
    device_count: int | None = None
    offline: bool = False
    endpoint_checked: bool = False

    @property
    def exit_code(self) -> int:
        return EXIT_PROBLEM if any(c.status == "failed" for c in self.checks) else EXIT_OK

    def add(self, *checks: Check) -> None:
        self.checks.extend(checks)


# -- runtime -----------------------------------------------------------------------


def build_kind(version: str) -> Literal["release", "non-release", "unknown"]:
    """From the package version label (docs/contract/versioning.md)."""
    if version == "0+unknown":
        return "unknown"
    return "non-release" if "+" in version else "release"


def runtime_checks(report: Report, system: str, python: tuple[int, ...]) -> None:
    kind = build_kind(__version__)
    platform_tier = compat.platform_tier(system)
    python_tier = compat.python_tier(python)
    python_text = ".".join(str(part) for part in python[:3])
    report.runtime = {
        "package_version": __version__,
        "build_kind": kind,
        "python_version": python_text,
        "python_tier": python_tier,
        "platform_tier": platform_tier,
    }
    report.add(
        Check(
            "runtime",
            "ok",
            "RUNTIME_OK",
            f"wled-mcp {__version__} ({kind} build), Python {python_text}.",
        )
    )
    if kind == "unknown":
        report.add(
            Check("runtime", "warning", "BUILD_UNKNOWN", "No installed package version found.")
        )
    if python_tier != "supported":
        report.add(
            Check(
                "runtime",
                "warning",
                "PYTHON_UNTESTED",
                f"Python {python_text} is not covered by CI (DEC-020).",
            )
        )
    if platform_tier == "experimental":
        report.add(
            Check("runtime", "warning", "PLATFORM_EXPERIMENTAL", "This platform is experimental.")
        )
    elif platform_tier == "untested":
        report.add(Check("runtime", "warning", "PLATFORM_UNTESTED", "This platform is untested."))


# -- configuration and storage ------------------------------------------------------


def configuration_check(
    report: Report, raw: str | None
) -> tuple[Path | None, InventoryConfig | None]:
    def failed(code: str, message: str) -> tuple[None, None]:
        report.add(Check("configuration", "failed", code, message))
        return None, None

    if raw is None:
        return failed("CONFIG_PATH_MISSING", "No configuration path was given.")
    path = Path(raw)
    if not path.is_absolute():
        return failed("CONFIG_PATH_NOT_ABSOLUTE", "The configuration path is not absolute.")
    try:
        if not path.exists():
            return failed("CONFIG_NOT_FOUND", "The configuration file does not exist.")
        if not path.is_file():
            return failed("CONFIG_UNREADABLE", "The configuration path is not a regular file.")
        with path.open("rb") as stream:
            content = stream.read(MAX_CONFIG_BYTES + 1)
    except (OSError, ValueError):
        return failed("CONFIG_UNREADABLE", "The configuration file could not be read.")
    try:
        inventory = validate_document(content)
    except ConfigurationError as exc:
        return failed("CONFIG_INVALID", str(exc))
    report.device_count = len(inventory.devices)
    report.add(
        Check(
            "configuration",
            "ok",
            "CONFIG_VALID",
            f"Configuration valid: schema 1, {len(inventory.devices)} device(s).",
            facts={"device_count": len(inventory.devices)},
        )
    )
    return path, inventory


def storage_checks(report: Report, raw: str | None) -> Path | None:
    def failed(code: str, message: str) -> None:
        report.add(Check("storage", "failed", code, message))

    if raw is None:
        failed("DATA_DIR_MISSING", "No data directory was given.")
        return None
    data = Path(raw)
    if not data.is_absolute():
        failed("DATA_DIR_NOT_ABSOLUTE", "The data directory path is not absolute.")
        return None
    if not data.is_dir():
        failed("DATA_DIR_NOT_FOUND", "The data directory does not exist or is not a directory.")
        return None
    report.add(Check("storage", "ok", "DATA_DIR_OK", "The data directory exists."))
    if backups_writable(data):
        report.add(
            Check(
                "storage",
                "ok",
                "BACKUPS_WRITABLE",
                "The backups location is writable (advisory check; nothing created; "
                "hard-link support is not verified without writing).",
            )
        )
    else:
        failed("BACKUPS_NOT_WRITABLE", "The backups location is not writable.")
    return data


# -- devices -------------------------------------------------------------------------


def _bounded_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    if len(value) > _MAX_FIRMWARE_TEXT or not value.isprintable():
        return None
    return value


def device_checks(index: int, device_id: str, envelope: Mapping[str, Any]) -> list[Check]:
    """Classify one ``wled_get_state`` result envelope (read, never extended)."""

    def check(status: Status, code: str, message: str, **facts: Any) -> Check:
        return Check("device", status, code, message, index, device_id, facts)

    if not envelope.get("ok"):
        error = envelope.get("error") or {}
        code = error.get("code") if isinstance(error, Mapping) else None
        mapped = {
            "UNREACHABLE": ("DEVICE_UNREACHABLE", "The device could not be reached."),
            "TIMEOUT": ("DEVICE_TIMEOUT", "The device did not answer within the timeout."),
            "INVALID_RESPONSE": (
                "DEVICE_INVALID_RESPONSE",
                "The device answered with an invalid WLED response.",
            ),
        }.get(str(code), ("DEVICE_READ_FAILED", "The device state could not be read."))
        return [check("failed", *mapped, error_code=str(code) if code else None)]
    data = envelope.get("data") or {}
    diagnostics = data.get("diagnostics") or {}
    firmware = data.get("firmware") or {}
    support = diagnostics.get("firmware_support") or {}
    tier_value = support.get("tier")
    tier: compat.Tier = "unrecognized"
    for known in get_args(compat.Tier):
        if tier_value == known:
            tier = known
    firmware_facts = {
        "ver": _bounded_text(firmware.get("version")),
        "vid": firmware.get("build_id") if type(firmware.get("build_id")) is int else None,
        "arch": _bounded_text(firmware.get("arch")),
        "tier": tier,
        "minimum_supported": _bounded_text(support.get("minimum_supported")),
    }
    checks = [check("ok", "DEVICE_REACHABLE", "The device answered a read-only state read.")]
    warning = compat.support_warning(tier)
    if warning is None:
        checks.append(
            check("ok", "FIRMWARE_SUPPORTED", f"Firmware tier `{tier}`.", **firmware_facts)
        )
    else:
        code = "FIRMWARE_UNSUPPORTED" if tier == "unsupported" else "FIRMWARE_UNRECOGNIZED"
        checks.append(check("warning", code, warning, **firmware_facts))
    unknown = diagnostics.get("unknown_capabilities") or []
    names = sorted({name for name in unknown if isinstance(name, str) and name.isidentifier()})
    if names:
        checks.append(
            check(
                "warning",
                "CAPABILITIES_UNKNOWN",
                "The device did not report: " + ", ".join(names) + ".",
                unknown_capabilities=names,
            )
        )
    else:
        checks.append(
            check("ok", "CAPABILITIES_KNOWN", "All essential capabilities were reported.")
        )
    return checks


async def read_devices(
    config: StartupConfig, transport: httpx.AsyncBaseTransport | None = None
) -> list[list[Check]]:
    """At most eight concurrent in-process ``wled_get_state`` calls; GET requests only."""
    from wled_mcp.operations import build_operations
    from wled_mcp.resources import Resources

    results: list[list[Check]] = [[] for _ in config.devices]
    async with Resources(config, transport) as resources:
        get_state = next(op for op in build_operations(resources) if op.name == "wled_get_state")
        iterator = iter(enumerate(config.devices))

        async def worker() -> None:
            for index, device in iterator:
                outcome = await get_state.execute({"device_id": device.id})
                envelope = outcome.model_dump(mode="json")
                results[index] = device_checks(index, device.id, envelope)

        async with anyio.create_task_group() as group:
            for _ in range(min(MAX_PARALLEL_DEVICES, len(config.devices))):
                group.start_soon(worker)
    return results


# -- endpoint ------------------------------------------------------------------------


def endpoint_url(raw: str) -> str | None:
    """Validated MCP endpoint URL; an empty path becomes ``/mcp``."""
    try:
        parts = urlsplit(raw)
        parts.port  # noqa: B018 - raises ValueError for an invalid port
    except ValueError:
        return None
    if (
        parts.scheme not in ("http", "https")
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
        or any(c.isspace() for c in raw)
    ):
        return None
    path = parts.path if parts.path not in ("", "/") else ENDPOINT_PATH
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def _rpc_result(response: httpx.Response, request_id: int) -> dict[str, Any] | None:
    content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
    body = response.content[:MAX_ENDPOINT_BODY].decode("utf-8", errors="replace")
    messages: list[Any] = []
    try:
        if content_type == "application/json":
            messages.append(json.loads(body))
        elif content_type == "text/event-stream":
            for line in body.splitlines():
                if line.startswith("data:"):
                    messages.append(json.loads(line[5:].strip()))
    except ValueError:
        return None
    for message in messages:
        if (
            isinstance(message, dict)
            and message.get("jsonrpc") == "2.0"
            and message.get("id") == request_id
            and isinstance(message.get("result"), dict)
        ):
            result: dict[str, Any] = message["result"]
            return result
    return None


async def endpoint_checks(
    raw_url: str,
    token_file: str | None,
    environ: Mapping[str, str],
    transport: httpx.AsyncBaseTransport | None = None,
) -> list[Check]:
    def result(status: Status, code: str, message: str, **facts: Any) -> list[Check]:
        return [Check("endpoint", status, code, message, facts=facts)]

    url = endpoint_url(raw_url)
    if url is None:
        return result("failed", "ENDPOINT_URL_INVALID", "The endpoint URL is not usable.")
    if token_file is None and environ.get(TOKEN_ENV) is None:
        return result("failed", "ENDPOINT_CREDENTIAL_MISSING", "No HTTP credential configured.")
    try:
        token = resolve_token(token_file, environ)
    except ConfigurationError as exc:
        return result("failed", "ENDPOINT_CREDENTIAL_INVALID", str(exc))
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": _PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "wled-mcp-doctor", "version": __version__},
        },
    }
    try:
        async with httpx.AsyncClient(
            transport=transport,
            timeout=ENDPOINT_TIMEOUT_SECONDS,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            response = await client.post(url, json=initialize, headers=headers)
            if response.status_code in (403, 421):
                return result(
                    "failed",
                    "ENDPOINT_HOST_ORIGIN_REJECTED",
                    "The service rejected the request's Host/Origin.",
                )
            if response.status_code == 401:
                return result(
                    "failed", "ENDPOINT_CREDENTIAL_REJECTED", "The service rejected the credential."
                )
            initialized = _rpc_result(response, 1) if response.status_code == 200 else None
            if initialized is None or not isinstance(initialized.get("protocolVersion"), str):
                return result(
                    "failed",
                    "ENDPOINT_PROTOCOL_ERROR",
                    "The endpoint did not answer MCP initialize.",
                )
            negotiated = str(initialized["protocolVersion"])[:32]
            ping_headers = {**headers, "MCP-Protocol-Version": negotiated}
            session = response.headers.get("mcp-session-id")
            if session:
                ping_headers["Mcp-Session-Id"] = session
            ping = await client.post(
                url, json={"jsonrpc": "2.0", "id": 2, "method": "ping"}, headers=ping_headers
            )
            if ping.status_code != 200 or _rpc_result(ping, 2) is None:
                return result(
                    "failed", "ENDPOINT_PROTOCOL_ERROR", "The endpoint did not answer MCP ping."
                )
            if session:
                try:
                    await client.delete(url, headers=ping_headers)
                except httpx.HTTPError:
                    pass
    except httpx.TimeoutException:
        return result("failed", "ENDPOINT_TIMEOUT", "The endpoint did not answer in time.")
    except httpx.HTTPError:
        return result("failed", "ENDPOINT_UNREACHABLE", "The endpoint could not be reached.")
    server = initialized.get("serverInfo")
    name = server.get("name") if isinstance(server, dict) else None
    if name != "wled-mcp":
        return result(
            "warning",
            "ENDPOINT_OTHER_SERVER",
            "The endpoint speaks MCP but is not wled-mcp.",
            protocol_version=negotiated,
        )
    return result(
        "ok",
        "ENDPOINT_OK",
        f"MCP initialize and ping succeeded (protocol {negotiated}).",
        protocol_version=negotiated,
    )


# -- orchestration and output ----------------------------------------------------------


@dataclass(frozen=True)
class DoctorOptions:
    config: str | None
    data_dir: str | None
    offline: bool = False
    endpoint: str | None = None
    http_token_file: str | None = None


async def diagnose(
    options: DoctorOptions,
    environ: Mapping[str, str],
    *,
    device_transport: httpx.AsyncBaseTransport | None = None,
    endpoint_transport: httpx.AsyncBaseTransport | None = None,
    system: str | None = None,
    python: Sequence[int] | None = None,
) -> Report:
    report = Report(offline=options.offline, endpoint_checked=options.endpoint is not None)
    runtime_checks(
        report,
        platform.system() if system is None else system,
        tuple(sys.version_info[:3] if python is None else python),
    )
    path, inventory = configuration_check(report, option_path(options.config, CONFIG_ENV, environ))
    data = storage_checks(report, option_path(options.data_dir, DATA_ENV, environ))
    if inventory is None or path is None:
        report.add(
            Check(
                "device", "skipped", "DEVICES_SKIPPED", "Device checks need a valid configuration."
            )
        )
    elif not inventory.devices:
        report.add(Check("device", "warning", "DEVICES_NONE", "No devices are configured."))
    elif options.offline:
        report.add(Check("device", "skipped", "DEVICES_OFFLINE", "Skipped (--offline)."))
    else:
        config = StartupConfig(
            path,
            data if data is not None else path.parent,
            tuple(inventory.devices),
            inventory.http,
            inventory.backups,
        )
        for checks in await read_devices(config, device_transport):
            report.add(*checks)
    if options.endpoint is not None:
        report.add(
            *await endpoint_checks(
                options.endpoint, options.http_token_file, environ, endpoint_transport
            )
        )
    return report


def export(report: Report) -> dict[str, Any]:
    """Sanitized, shareable summary (TD-16-6); an allowlist, never a filtered copy.

    Contains no device ID or name, URL, host, address, MAC, Wi-Fi field, path,
    credential, message text or raw response; devices appear as ``devices[i]``.
    """
    checks: list[dict[str, Any]] = []
    devices: dict[int, dict[str, Any]] = {}
    for check in report.checks:
        entry: dict[str, Any] = {
            "category": check.category,
            "status": check.status,
            "code": check.code,
        }
        if check.device_index is not None:
            entry["device"] = f"devices[{check.device_index}]"
            device = devices.setdefault(check.device_index, {"device": entry["device"]})
            for key in ("ver", "vid", "arch", "tier", "minimum_supported"):
                if key in check.facts:
                    device.setdefault("firmware", {})[key] = check.facts[key]
            if "unknown_capabilities" in check.facts:
                device["unknown_capabilities"] = list(check.facts["unknown_capabilities"])
        if "protocol_version" in check.facts:
            entry["protocol_version"] = check.facts["protocol_version"]
        checks.append(entry)
    return {
        "schema_version": JSON_SCHEMA_VERSION,
        "command": "doctor",
        "export": True,
        "ok": report.exit_code == EXIT_OK,
        "runtime": dict(report.runtime),
        "transport_flags": {
            "offline": report.offline,
            "endpoint_checked": report.endpoint_checked,
        },
        "device_count": report.device_count,
        "checks": checks,
        "devices": [devices[index] for index in sorted(devices)],
    }


def full_json(report: Report) -> dict[str, Any]:
    """Local JSON output; includes messages and configured device IDs, never URLs."""
    return {
        "schema_version": JSON_SCHEMA_VERSION,
        "command": "doctor",
        "ok": report.exit_code == EXIT_OK,
        "runtime": dict(report.runtime),
        "device_count": report.device_count,
        "checks": [
            {
                "category": check.category,
                "status": check.status,
                "code": check.code,
                "message": check.message,
                "action": check.action,
                **(
                    {"device": f"devices[{check.device_index}]", "device_id": check.device_id}
                    if check.device_index is not None
                    else {}
                ),
            }
            for check in report.checks
        ],
    }


def render_text(report: Report) -> str:
    lines = ["wled-mcp doctor (read-only)"]
    for check in report.checks:
        where = ""
        if check.device_index is not None:
            where = f" devices[{check.device_index}] ({check.device_id})"
        lines.append(f"[{check.status}] {check.category}{where} {check.code}: {check.message}")
        if check.action is not None:
            lines.append(f"    action: {check.action}")
    failed = sum(check.status == "failed" for check in report.checks)
    warnings = sum(check.status == "warning" for check in report.checks)
    lines.append(f"Summary: {failed} failed, {warnings} warning(s).")
    return "\n".join(lines)


def register(commands: Any) -> None:
    doctor = commands.add_parser("doctor", help="Read-only diagnostics; changes nothing.")
    doctor.add_argument("--config", help="Absolute configuration path (WLED_MCP_CONFIG).")
    doctor.add_argument("--data-dir", help="Absolute data directory (WLED_MCP_DATA_DIR).")
    doctor.add_argument("--offline", action="store_true", help="Skip the device reads.")
    doctor.add_argument("--endpoint", help="Also check a Streamable HTTP MCP endpoint URL.")
    doctor.add_argument(
        "--http-token-file",
        help=f"Absolute credential file for --endpoint (or environment {TOKEN_ENV}).",
    )
    doctor.add_argument(
        "--export",
        action="store_true",
        help="Print only the sanitized, shareable JSON summary.",
    )
    add_format_option(doctor)


def run(args: argparse.Namespace, environ: Mapping[str, str]) -> int:
    options = DoctorOptions(
        config=args.config,
        data_dir=args.data_dir,
        offline=args.offline,
        endpoint=args.endpoint,
        http_token_file=args.http_token_file,
    )
    report = anyio.run(_diagnose, options, environ)
    if args.export:
        text = json.dumps(export(report), ensure_ascii=False, sort_keys=True)
    elif args.format == "json":
        text = json.dumps(full_json(report), ensure_ascii=False, sort_keys=True)
    else:
        text = render_text(report)
    sys.stdout.write(text + "\n")
    sys.stdout.flush()
    return report.exit_code


async def _diagnose(options: DoctorOptions, environ: Mapping[str, str]) -> Report:
    return await diagnose(options, environ)
