"""Tool-free inventory writer: lock, validate, back up, replace atomically, reload (issue #201).

Contract: docs/contract/discovery.md ("Reload semantics"), ISSUE-201-DEC-001. The tools of
#202 and #203 call :meth:`InventoryWriter.update` with an edit callback; this module
registers no tool, never contacts a device or the network, and never logs a path or file
content. ``update`` blocks (file I/O and a bounded lock wait); tools run it through
``anyio.to_thread``.
"""

import hashlib
import stat
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from wled_mcp.access import AccessPolicy
from wled_mcp.config import ConfigurationError, Device, InventoryConfig, validate_document
from wled_mcp.filelock import (
    DEFAULT_TIMEOUT_SECONDS,
    LockTimeout,
    LockUnavailable,
    config_backup_path,
    config_lock_path,
    exclusive_lock,
)
from wled_mcp.setup import Refusal, _check_parent, _read_regular, atomic_write

WriteErrorCode = Literal["STORAGE_FAILED", "INVENTORY_CONFLICT", "INVENTORY_RELOAD_FAILED"]
WriteApplication = Literal["not_applied", "unknown"]


@dataclass(frozen=True)
class WriteResult:
    written: bool  # False for an unchanged candidate
    reloaded: bool  # the apply callback ran
    backup: bool  # the previous file was kept in <config>.bak
    devices: tuple[Device, ...]  # inventory now in effect
    sha256: str
    discovery_ranges: tuple[str, ...] = ()  # stored ranges now in effect


class InventoryWriteError(Exception):
    """A refused or failed write; ``data`` holds fixed text only (no paths or values)."""

    def __init__(
        self,
        code: WriteErrorCode,
        message: str,
        data: Mapping[str, str],
        application: WriteApplication = "not_applied",
    ) -> None:
        super().__init__(message)
        self.code: WriteErrorCode = code
        self.message = message
        self.data = dict(data)
        self.application: WriteApplication = application


_PARENT_CODES = frozenset({"PARENT_MISSING", "PARENT_INACCESSIBLE"})


def _storage(reason: str, message: str) -> InventoryWriteError:
    return InventoryWriteError("STORAGE_FAILED", message, {"reason": reason})


def _reload_failed(
    stage: str, message: str, application: WriteApplication = "not_applied"
) -> InventoryWriteError:
    return InventoryWriteError("INVENTORY_RELOAD_FAILED", message, {"stage": stage}, application)


class InventoryWriter:
    def __init__(
        self,
        config_path: Path,
        baseline_sha256: str | None,
        access: AccessPolicy,
        apply: Callable[[InventoryConfig], None],
        *,
        lock_timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._path = config_path
        self._baseline = baseline_sha256
        self._access = access
        self._apply = apply
        self._lock_timeout = lock_timeout

    def update(self, edit: Callable[[bytes], bytes | None]) -> WriteResult:
        """Apply ``edit(current bytes)`` (``None``: no change) under the cross-process lock.

        Order: read, baseline check, edit, unchanged check, validate, access and ID
        checks, backup, atomic replace, apply, baseline update. Every failure before the
        replace leaves the file untouched; a failing apply restores the previous bytes.
        """
        try:
            with exclusive_lock(config_lock_path(self._path), self._lock_timeout):
                return self._update_locked(edit)
        except LockTimeout:
            raise _storage(
                "locked", "The inventory is being written by another process; nothing was changed."
            ) from None
        except LockUnavailable:
            raise _storage(
                "not_writable",
                "The inventory lock file could not be created in the configuration directory; "
                "nothing was changed.",
            ) from None

    def _update_locked(self, edit: Callable[[bytes], bytes | None]) -> WriteResult:
        try:
            _check_parent(self._path.parent)
            current, info = _read_regular(self._path)
        except Refusal as refusal:
            if refusal.code in _PARENT_CODES:
                raise _storage(
                    "not_writable",
                    "The inventory directory is missing or not writable; nothing was changed.",
                ) from None
            raise _storage(
                "unreadable",
                "The inventory file is missing, not a regular file or could not be read; "
                "nothing was changed.",
            ) from None
        digest = hashlib.sha256(current).hexdigest()
        if self._baseline is None or digest != self._baseline:
            raise InventoryWriteError(
                "INVENTORY_CONFLICT",
                "The inventory file changed outside this server after it was loaded; nothing "
                "was written. Run `wled-mcp config validate` and restart the server.",
                {"conflict": "file_changed"},
            )
        candidate = edit(current)
        if candidate is None or candidate == current:
            unchanged = self._parse(current)
            return WriteResult(
                False,
                False,
                False,
                tuple(unchanged.devices) if unchanged else (),
                digest,
                tuple(unchanged.discovery.ranges) if unchanged else (),
            )
        validated = self._validate(current, candidate)
        mode = stat.S_IMODE(info.st_mode)
        try:
            atomic_write(config_backup_path(self._path), current, mode)
        except OSError:
            raise _storage(
                "backup_failed", "The inventory backup could not be written; nothing was changed."
            ) from None
        try:
            atomic_write(self._path, candidate, mode)
        except OSError:
            raise _storage(
                "write_failed", "The inventory could not be written; the file is unchanged."
            ) from None
        try:
            self._apply(validated)
        except Exception:
            raise self._restore(current, mode) from None
        self._baseline = hashlib.sha256(candidate).hexdigest()
        return WriteResult(
            True,
            True,
            True,
            tuple(validated.devices),
            self._baseline,
            tuple(validated.discovery.ranges),
        )

    @staticmethod
    def _parse(content: bytes) -> InventoryConfig | None:
        try:
            return validate_document(content)
        except ConfigurationError:  # not reachable for bytes equal to the loaded baseline
            return None

    def _validate(self, current: bytes, candidate: bytes) -> InventoryConfig:
        """The candidate must validate, keep the access settings and keep every device ID."""
        try:
            validated = validate_document(candidate)
            before = validate_document(current)
        except ConfigurationError:
            raise _reload_failed(
                "validation", "The changed inventory is invalid; nothing was written."
            ) from None
        # The tool registry is built once: profile and caps cannot change in-process. The
        # profile is compared with the loaded file (a serve --profile option may override
        # it in the running policy); caps are compared with the running policy.
        caps = {d.id: d.max_class for d in validated.devices if d.max_class is not None}
        running = {device_id: cap.value for device_id, cap in self._access.caps.items()}
        if validated.access.profile != before.access.profile or caps != running:
            raise _reload_failed(
                "access",
                "The change would alter the access profile or a device maximum class, which "
                "needs a restart; nothing was written.",
            )
        if {d.id for d in before.devices} - {d.id for d in validated.devices}:
            raise _reload_failed(
                "validation",
                "The change would remove a configured device ID; nothing was written.",
            )
        return validated

    def _restore(self, previous: bytes, mode: int) -> InventoryWriteError:
        try:
            atomic_write(self._path, previous, mode)
        except OSError:
            return _reload_failed(
                "reload",
                "The running inventory could not be reloaded and the previous file could not "
                "be restored; check the file, then restart the server.",
                "unknown",
            )
        return _reload_failed(
            "reload",
            "The running inventory could not be reloaded; the previous file was restored.",
        )
