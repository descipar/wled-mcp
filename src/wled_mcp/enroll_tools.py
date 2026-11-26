"""``wled_add_device`` (issue #203; DISC-05, DISC-08, DISC-10).

Contract: docs/contract/discovery.md, ISSUE-203-DEC-001. Enrolls one controller: one
read-only ``GET /json/info`` of one explicit RFC 1918 IPv4 literal (the shared hard caps of
``discovery_caps`` apply: size, timeout, no redirect, no proxy), then one ``[[devices]]``
entry appended to the inventory file through the shared
:class:`~wled_mcp.inventory_writer.InventoryWriter` and applied in-process. Class ``manage``;
it never writes to a device, never sets ``max_class``, never overwrites or updates an
entry and never resolves a name (no DNS lookup occurs). Rejections carry a fixed reason and
never the offending value, a MAC or an address.
"""

import ipaddress
import re
import tomllib
from dataclasses import dataclass
from typing import Any

import anyio.to_thread
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from wled_mcp import setup
from wled_mcp.access import ToolClass
from wled_mcp.config import ConfigurationError, Device, normalize_mac, validate_document
from wled_mcp.discovery import suggest_id, suggest_name
from wled_mcp.discovery_caps import HOST_TIMEOUT, address_allowed
from wled_mcp.discovery_engine import HttpTransport, InfoResult
from wled_mcp.inventory_writer import InventoryWriteError, WriteResult
from wled_mcp.models import Application, DomainError, ErrorCode, Outcome
from wled_mcp.resources import Resources
from wled_mcp.server import Operation

NAME = "wled_add_device"

_IPV4 = re.compile(r"[0-9]{1,3}(?:\.[0-9]{1,3}){3}", re.ASCII)
_PORT = re.compile(r"[1-9][0-9]{0,4}", re.ASCII)
_FORBIDDEN = re.compile(r"[\s\x00-\x1f\x7f/?#@\\%]|[^\x00-\x7f]")
_GENERIC_NAME = "WLED"

_RECONCILIATION = {
    "STORAGE_FAILED": "Nothing was changed. Check the inventory file and its directory.",
    "INVENTORY_RELOAD_FAILED": (
        "Check the stage in data; the file is unchanged unless the stage says otherwise."
    ),
}
_UNKNOWN_RECONCILIATION = (
    "The file may or may not hold the new entry. Check it, then restart the server."
)
_CONFLICT_TEXT = {
    "id": "The ID is already configured.",
    "base_url": "The address is already configured.",
    "mac": (
        "A configured entry already has this MAC; the controller may have a new address. "
        "There is no update tool: edit the address in the inventory file by hand."
    ),
}


class AddDeviceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    base_url: str = Field(
        max_length=40,
        description="http://<RFC 1918 IPv4 address>[:port]; no host name, no https, no path.",
    )
    device_id: str | None = Field(
        default=None,
        pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$",
        description="New ID; default derived from the controller's name or MAC.",
    )
    name: str | None = Field(default=None, min_length=1, max_length=64)
    expected_mac: str | None = Field(
        default=None, description="Refuse unless the controller reports this MAC (12 hex)."
    )
    dry_run: bool = Field(
        default=False, description="Read and check only; write nothing, reload nothing."
    )

    @field_validator("expected_mac", mode="before")
    @classmethod
    def normalized_mac(cls, value: object) -> object:
        return None if value is None else normalize_mac(value)

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str | None) -> str | None:
        if value is not None and (
            not value.strip() or any(ord(c) < 32 or ord(c) == 127 for c in value)
        ):
            raise ValueError("Invalid device name")
        return value


ANNOTATIONS = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=True
)


class _Rejected(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def parse_base_url(text: str) -> tuple[ipaddress.IPv4Address, int, str]:
    """Address, port and canonical stored URL of ``http://<IPv4 literal>[:port][/]``.

    Raises ``_Rejected`` with ``invalid_url``, ``not_ipv4_literal`` or ``not_private``.
    No name is ever resolved.
    """
    if not text.startswith("http://"):
        raise _Rejected("invalid_url")
    rest = text[len("http://") :]
    if rest.endswith("/"):
        rest = rest[:-1]
    if not rest or _FORBIDDEN.search(rest):
        raise _Rejected("invalid_url")
    if "[" in rest or "]" in rest:
        raise _Rejected("not_ipv4_literal")
    host, colon, port_text = rest.partition(":")
    if not host or ":" in port_text:
        raise _Rejected("invalid_url")
    port = 80
    if colon:
        if not _PORT.fullmatch(port_text) or int(port_text) > 65535:
            raise _Rejected("invalid_url")
        port = int(port_text)
    if not _IPV4.fullmatch(host):
        raise _Rejected("not_ipv4_literal")
    try:
        address = ipaddress.IPv4Address(host)  # rejects octets above 255 and zero padding
    except ValueError:
        raise _Rejected("not_ipv4_literal") from None
    if not address_allowed(address):
        raise _Rejected("not_private")
    return address, port, f"http://{address}" + ("" if port == 80 else f":{port}")


def fetch_info(address: str, port: int) -> InfoResult:
    """The one verification read; a module attribute so that tests replace it."""
    return HttpTransport().get_info(address, port, HOST_TIMEOUT)


@dataclass(frozen=True)
class _Plan:
    address: str
    port: int
    base_url: str
    device_id: str | None
    name: str | None
    expected_mac: str | None


def _conflict(
    devices: tuple[Device, ...] | list[Device],
    device_id: str | None,
    base_url: str,
    mac: str | None,
) -> InventoryWriteError | None:
    """First conflict in the order ``id``, ``base_url``, ``mac``; an entry is never replaced."""
    identity = setup.url_identity(base_url)
    checks = (
        ("id", lambda d: device_id is not None and d.id == device_id),
        ("base_url", lambda d: setup.url_identity(d.base_url) == identity),
        ("mac", lambda d: mac is not None and d.mac == mac),
    )
    for kind, matches in checks:
        for device in devices:
            if matches(device):
                return InventoryWriteError(
                    "INVENTORY_CONFLICT",
                    f"{_CONFLICT_TEXT[kind]} Nothing was written; an existing entry is never "
                    "overwritten.",
                    {"conflict": kind, "known_device_id": device.id},
                )
    return None


def _labels(info: InfoResult) -> str:
    """Label for default ID and name: the reported name, else ``wled-<last 6 of MAC>``."""
    if info.name and info.name != _GENERIC_NAME:
        return info.name
    return f"wled-{(info.mac or '')[-6:]}"


def _entry(plan: _Plan, info: InfoResult, taken: set[str]) -> dict[str, str]:
    label = _labels(info)
    return {
        "id": plan.device_id or suggest_id(label, set(taken)),
        "name": plan.name or suggest_name(label),
        "base_url": plan.base_url,
        "mac": info.mac or "",
    }


def _invalid_candidate() -> InventoryWriteError:
    return InventoryWriteError(
        "INVENTORY_RELOAD_FAILED",
        "The inventory file cannot be edited safely (for example a hand-written inline "
        "devices array); nothing was written.",
        {"stage": "validation"},
    )


def _edit(plan: _Plan, info: InfoResult, written: dict[str, str]) -> Any:
    """Edit callback, authoritative under the writer's lock: recheck, append, self-check."""

    def edit(current: bytes) -> bytes | None:
        try:
            document = validate_document(current)
        except ConfigurationError:
            raise _invalid_candidate() from None
        refused = _conflict(document.devices, plan.device_id, plan.base_url, info.mac)
        if refused is not None:
            raise refused
        entry = _entry(plan, info, {d.id for d in document.devices})
        candidate = setup.append_device(
            current.decode("utf-8"),
            setup.device_block(entry["id"], entry["name"], entry["base_url"], entry["mac"]),
        ).encode("utf-8")
        try:
            old = tomllib.loads(current.decode("utf-8"))
            new = tomllib.loads(candidate.decode("utf-8"))
        except (tomllib.TOMLDecodeError, UnicodeError):
            raise _invalid_candidate() from None
        if new != {**old, "devices": [*old.get("devices", []), entry]}:
            raise _invalid_candidate()
        written.update(entry)
        return candidate

    return edit


def _outcome(
    ok: bool,
    *,
    dry_run: bool,
    data: dict[str, JsonValue],
    device_id: str | None = None,
    application: Application = "not_attempted",
    error: DomainError | None = None,
) -> Outcome:
    return Outcome.model_validate(
        {
            "ok": ok,
            "operation": NAME,
            "device_id": device_id,
            "dry_run": dry_run,
            "application": "not_attempted" if dry_run else application,
            "verification": "unknown"
            if application == "unknown" and not dry_run
            else "not_requested",
            "data": data,
            "error": error.model_dump() if error is not None else None,
        }
    )


def _failure(
    code: ErrorCode,
    message: str,
    reconciliation: str,
    *,
    dry_run: bool,
    application: Application = "not_attempted",
    data: dict[str, JsonValue] | None = None,
) -> Outcome:
    return _outcome(
        False,
        dry_run=dry_run,
        application=application,
        data=data or {},
        error=DomainError(code=code, message=message, reconciliation=reconciliation),
    )


def _write_failure(
    error: InventoryWriteError, *, dry_run: bool, application: Application
) -> Outcome:
    unknown = error.application == "unknown"
    if error.code == "INVENTORY_CONFLICT":
        reconciliation = (
            "Nothing was written. Run `wled-mcp config validate`, restart the server, then repeat."
            if error.data.get("conflict") == "file_changed"
            else "Nothing was written and no entry changed. Choose another ID or address."
        )
    else:
        reconciliation = _UNKNOWN_RECONCILIATION if unknown else _RECONCILIATION[error.code]
    return _failure(
        error.code,
        error.message,
        reconciliation,
        dry_run=dry_run,
        application="unknown" if unknown else application,
        data=dict(error.data),
    )


_FETCH_FAILURES: dict[str, tuple[ErrorCode, str, str]] = {
    "other": (
        "NOT_WLED",
        "The address answered, but not as a WLED controller; nothing was written.",
        "Check the address. Nothing was written.",
    ),
    "refused": (
        "UNREACHABLE",
        "The controller refused the connection; nothing was written.",
        "Check the address and that the controller is on. Nothing was written.",
    ),
    "timeout": (
        "TIMEOUT",
        "The controller did not answer in time; nothing was written.",
        "Nothing was written (the call only reads); repeating it is safe.",
    ),
    "error": (
        "INVALID_RESPONSE",
        "The controller answer could not be read; nothing was written.",
        "Nothing was written. Check the address, then repeat.",
    ),
}


def build_enroll_operations(resources: Resources) -> tuple[Operation, ...]:
    async def add_device(arguments: dict[str, Any]) -> Outcome:
        dry_run: bool = arguments["dry_run"]
        try:
            address, port, base_url = parse_base_url(arguments["base_url"])
        except _Rejected as rejected:
            return _failure(
                "VALIDATION_ERROR",
                "base_url must be http://<RFC 1918 IPv4 address>[:port] (no host name, https, "
                "path, query or credentials).",
                "Nothing was read or written. Correct the address and retry.",
                dry_run=dry_run,
                data={"field": "base_url", "reason": rejected.reason},
            )
        plan = _Plan(
            str(address),
            port,
            base_url,
            arguments["device_id"],
            arguments["name"],
            arguments["expected_mac"],
        )
        snapshot = resources.inventory
        refused = _conflict(snapshot, plan.device_id, plan.base_url, None)
        if refused is not None:  # before any network request
            return _write_failure(refused, dry_run=dry_run, application="not_attempted")
        info: InfoResult = await anyio.to_thread.run_sync(fetch_info, plan.address, plan.port)
        if info.kind != "wled" or info.mac is None:
            code, message, reconciliation = _FETCH_FAILURES[info.kind]
            return _failure(
                code, message, reconciliation, dry_run=dry_run, application="not_applied"
            )
        if plan.expected_mac is not None and info.mac != plan.expected_mac:
            return _failure(
                "VALIDATION_ERROR",
                "The controller reports a different MAC than expected_mac; nothing was written.",
                "Check the address and expected_mac. Nothing was written.",
                dry_run=dry_run,
                application="not_applied",
                data={"field": "expected_mac", "reason": "mac_mismatch"},
            )
        refused = _conflict(snapshot, plan.device_id, plan.base_url, info.mac)
        if refused is not None:
            return _write_failure(refused, dry_run=dry_run, application="not_applied")
        verified: dict[str, JsonValue] = {
            "firmware_version": info.version,
            "product": info.product,
        }
        if dry_run:
            entry = _entry(plan, info, {d.id for d in snapshot})
            return _outcome(
                True,
                dry_run=True,
                device_id=entry["id"],
                data={
                    "entry": dict(entry),
                    "verified": verified,
                    "inventory_size": len(snapshot) + 1,
                    "reloaded": False,
                    "written": False,
                },
            )
        written: dict[str, str] = {}
        try:
            result: WriteResult = await anyio.to_thread.run_sync(
                resources.inventory_writer().update, _edit(plan, info, written)
            )
        except InventoryWriteError as error:
            return _write_failure(error, dry_run=False, application="not_applied")
        return _outcome(
            True,
            dry_run=False,
            device_id=written["id"],
            data={
                "entry": dict(written),
                "verified": verified,
                "inventory_size": len(result.devices),
                "reloaded": result.reloaded,
                "written": result.written,
            },
        )

    return (
        Operation(
            name=NAME,
            tool_class=ToolClass.MANAGE,
            group="discovery",
            description=(
                "Add one WLED controller to the inventory (client-confirmed configuration "
                "write). Makes one read-only GET /json/info of the given RFC 1918 IPv4 address, "
                "checks it is WLED, then appends one entry (with its MAC) to the local "
                "inventory file, applied without restart. Never writes to the device; refuses "
                "duplicate ID, address or MAC and never overwrites an entry. Host names are "
                "added by hand. Use dry_run=true to check first."
            ),
            request_model=AddDeviceRequest,
            execute=add_device,
            annotations=ANNOTATIONS,
        ),
    )
