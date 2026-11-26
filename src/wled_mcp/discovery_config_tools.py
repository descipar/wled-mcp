"""``wled_set_discovery_ranges`` (issue #202; DISC-05, DISC-07, DISC-10, DISC-11).

Contract: docs/contract/discovery.md, ISSUE-202-DEC-001. Replaces the stored
``[discovery].ranges`` list of the inventory file through the shared
:class:`~wled_mcp.inventory_writer.InventoryWriter` (lock, baseline, backup, atomic
replace, validation, rollback) and applies it in-process. Class ``manage``; it writes only
the local inventory file and never contacts a device or the network. Entries are checked
against the shared hard caps; rejections carry an index and a fixed reason, never the value.
"""

import tomllib
from typing import Any

import anyio.to_thread
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from wled_mcp.access import ToolClass
from wled_mcp.config import ConfigurationError, validate_document
from wled_mcp.discovery_caps import CAPS, MAX_RANGES, check_ranges
from wled_mcp.inventory_writer import InventoryWriteError, WriteResult
from wled_mcp.models import DomainError, Outcome
from wled_mcp.resources import Resources
from wled_mcp.server import Operation
from wled_mcp.setup import set_discovery_ranges

NAME = "wled_set_discovery_ranges"

_RECONCILIATION = {
    "STORAGE_FAILED": "Nothing was changed. Check the inventory file and its directory.",
    "INVENTORY_CONFLICT": (
        "Nothing was written. Run `wled-mcp config validate`, restart the server, then repeat."
    ),
    "INVENTORY_RELOAD_FAILED": (
        "Check the stage in data; the file is unchanged unless the stage says otherwise."
    ),
}
_UNKNOWN_RECONCILIATION = (
    "The file may or may not hold the new ranges. Check it, then restart the server."
)


class SetDiscoveryRangesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    ranges: list[str] = Field(
        max_length=MAX_RANGES,
        description=(
            "The complete new list (replaces the stored one; [] clears it). IPv4 CIDR "
            "a.b.c.d/p, RFC 1918, /24 to /30, at most 4, no overlap."
        ),
    )
    dry_run: bool = Field(
        default=False,
        description="Validate and show the final list without writing; no file is read.",
    )


ANNOTATIONS = ToolAnnotations(
    read_only_hint=False, destructive_hint=True, idempotent_hint=True, open_world_hint=False
)


def _outcome(
    ok: bool,
    *,
    dry_run: bool,
    data: dict[str, JsonValue],
    application: str = "not_attempted",
    error: DomainError | None = None,
) -> Outcome:
    verification = {"unknown": "unknown"}.get(application, "not_requested")
    return Outcome.model_validate(
        {
            "ok": ok,
            "operation": NAME,
            "device_id": None,
            "dry_run": dry_run,
            "application": application,
            "verification": verification,
            "data": data,
            "error": error.model_dump() if error is not None else None,
        }
    )


def _candidate_edit(requested: list[str], seen: dict[str, tuple[str, ...]]) -> Any:
    """Edit callback: the text edit plus a self-check of the parsed result (TP-202-3)."""

    def edit(current: bytes) -> bytes | None:
        try:
            before = validate_document(current).discovery.ranges
        except ConfigurationError:
            raise _invalid_candidate() from None
        seen["before"] = tuple(before)
        if list(before) == requested:
            return None
        candidate = set_discovery_ranges(current.decode("utf-8"), requested).encode("utf-8")
        try:
            old = tomllib.loads(current.decode("utf-8"))
            new = tomllib.loads(candidate.decode("utf-8"))
        except (tomllib.TOMLDecodeError, UnicodeError):
            raise _invalid_candidate() from None
        stored = new.pop("discovery", None)
        old.pop("discovery", None)
        if stored != {"ranges": requested} or new != old:
            raise _invalid_candidate()
        return candidate

    return edit


def _invalid_candidate() -> InventoryWriteError:
    return InventoryWriteError(
        "INVENTORY_RELOAD_FAILED",
        "The inventory file cannot be edited safely (for example a hand-written dotted-key or "
        "inline form of [discovery]); nothing was written.",
        {"stage": "validation"},
    )


def build_discovery_config_operations(resources: Resources) -> tuple[Operation, ...]:
    async def set_ranges(arguments: dict[str, Any]) -> Outcome:
        requested: list[str] = list(arguments["ranges"])
        dry_run: bool = arguments["dry_run"]
        rejected = check_ranges(requested)
        if rejected:
            return _outcome(
                False,
                dry_run=dry_run,
                data={"rejected": [{"index": i, "reason": r} for i, r in rejected]},
                error=DomainError(
                    code="VALIDATION_ERROR",
                    message=(
                        f"{len(rejected)} range(s) violate the discovery limits; see "
                        "data.rejected for the index and reason of each."
                    ),
                    reconciliation="Nothing was written. Correct the listed entries and retry.",
                ),
            )
        before = resources.discovery_ranges
        if dry_run:
            return _outcome(
                True,
                dry_run=True,
                data={
                    "ranges_before": list(before),
                    "ranges_after": [*requested],
                    "changed": tuple(requested) != before,
                    "written": False,
                    "reloaded": False,
                    "backup": False,
                    "caps": CAPS,
                },
            )
        seen: dict[str, tuple[str, ...]] = {}
        try:
            result: WriteResult = await anyio.to_thread.run_sync(
                resources.inventory_writer().update, _candidate_edit(requested, seen)
            )
        except InventoryWriteError as error:
            unknown = error.application == "unknown"
            return _outcome(
                False,
                dry_run=False,
                application="unknown" if unknown else "not_applied",
                data=dict(error.data),
                error=DomainError(
                    code=error.code,
                    message=error.message,
                    reconciliation=(
                        _UNKNOWN_RECONCILIATION if unknown else _RECONCILIATION[error.code]
                    ),
                ),
            )
        ranges_before = seen.get("before", before)
        return _outcome(
            True,
            dry_run=False,
            data={
                "ranges_before": list(ranges_before),
                "ranges_after": list(result.discovery_ranges),
                "changed": ranges_before != result.discovery_ranges,
                "written": result.written,
                "reloaded": result.reloaded,
                "backup": result.backup,
                "caps": CAPS,
            },
        )

    return (
        Operation(
            name=NAME,
            tool_class=ToolClass.MANAGE,
            group="discovery",
            description=(
                "Replace the whole stored discovery range list (not a merge; [] clears it, "
                "leaving mDNS only). IPv4 CIDR, RFC 1918, /24 to /30, at most 4. Writes only "
                "the local inventory file, applied without restart; no device is contacted. "
                "Use dry_run=true to see the exact final list first. Hand edits of the file "
                "need a restart."
            ),
            request_model=SetDiscoveryRangesRequest,
            execute=set_ranges,
            annotations=ANNOTATIONS,
        ),
    )
