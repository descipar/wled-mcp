"""Versioned per-device preset snapshot store (issue #8).

Layout: ``<backups>/<device_id>/<backup_id>.json``. The store performs no device
I/O: callers pass a freshly read preset object while holding the device lock.
The read-only plan helper executes nothing; ``wled_restore_preset`` (issue #18,
``preset_tools``) executes one restore and uses the helper as its final check.
Diagnostics go to the logging system (stderr) and never carry paths or payloads.
"""

import json
import logging
import os
import re
import secrets
import stat
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from pydantic import JsonValue

from wled_mcp.client import ClientFailure
from wled_mcp.models import ErrorCode

LOGGER = logging.getLogger("wled_mcp.backups")

FORMAT_VERSION = 1
MAX_SNAPSHOT_BYTES = 1024 * 1024
MAX_DIRECTORY_ENTRIES = 10_000
MAX_PRESET_ID = 250
ID_ATTEMPTS = 5

DEVICE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
BACKUP_ID_RE = re.compile(r"^b-(\d{8}T\d{6}Z)-[0-9a-f]{12}$")
FILE_NAME_RE = re.compile(r"^(b-\d{8}T\d{6}Z-[0-9a-f]{12})\.json$")
TIMESTAMP_RE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")

ENVELOPE_KEYS = frozenset(
    {"format_version", "backup_id", "device_id", "preset_id", "firmware", "created_at", "preset"}
)

_SAFE = {
    "BACKUP_FAILED": "Preset snapshot could not be stored durably; no write was sent.",
    "READ_FAILED": "Preset snapshot storage could not be read.",
}
BACKUP_RECONCILE = "Repair the configured data path before an explicitly requested new attempt."


def fail(code: ErrorCode, message: str, retryable: bool = False) -> ClientFailure:
    # Nothing was written to the device on a backup failure, so no device read is needed.
    reconciliation = BACKUP_RECONCILE if code == "BACKUP_FAILED" else None
    return ClientFailure(code, message, retryable=retryable, reconciliation=reconciliation)


@dataclass(frozen=True)
class Firmware:
    version: str
    build_id: str | int | None = None


@dataclass(frozen=True)
class Snapshot:
    backup_id: str
    device_id: str
    preset_id: int
    firmware: Firmware
    created_at: str
    preset: dict[str, JsonValue]


@dataclass(frozen=True)
class BackupRecord:
    backup_id: str
    device_id: str
    preset_id: int
    created_at: str
    pruned: int = 0
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class SnapshotListing:
    snapshots: tuple[Snapshot, ...]
    invalid_count: int
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class RestorePlan:
    """Read-only inspection result; the plan itself executes nothing (ISSUE-8-DEC-001).

    ``as_data`` describes the manual procedure; ``wled_restore_preset`` (#18) executes.
    """

    backup_id: str
    device_id: str
    source_preset_id: int
    target_preset_id: int
    firmware_version: str
    destination_occupied: bool
    prior_backup_id: str | None
    steps: tuple[str, ...] = field(default_factory=tuple)

    def as_data(self) -> dict[str, JsonValue]:
        return {
            "execution": "deferred",
            "backup_id": self.backup_id,
            "device_id": self.device_id,
            "source_preset_id": self.source_preset_id,
            "target_preset_id": self.target_preset_id,
            "firmware_version": self.firmware_version,
            "destination_occupied": self.destination_occupied,
            "prior_backup_id": self.prior_backup_id,
            "manual_steps": list(self.steps),
        }


def _reject_duplicates(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _reject_constant(_: str) -> JsonValue:
    raise ValueError("non-finite number")


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _invalid(message: str) -> ClientFailure:
    return fail("VALIDATION_ERROR", message)


def _parse_timestamp(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def _check_preset_id(value: object) -> int:
    if not _is_int(value) or not 1 <= value <= MAX_PRESET_ID:  # type: ignore[operator]
        raise _invalid(f"Preset ID must be an integer from 1 to {MAX_PRESET_ID}.")
    assert isinstance(value, int)
    return value


def _check_firmware(value: object) -> Firmware:
    if not isinstance(value, dict) or set(value) - {"version", "build_id"}:
        raise _invalid("Snapshot firmware identity is malformed.")
    version, build = value.get("version"), value.get("build_id")
    if not isinstance(version, str) or not 0 < len(version) <= 128:
        raise _invalid("Snapshot firmware version is malformed.")
    if build is not None and not (
        _is_int(build) or (isinstance(build, str) and 0 < len(build) <= 128)
    ):
        raise _invalid("Snapshot firmware build identity is malformed.")
    assert build is None or isinstance(build, (str, int))
    return Firmware(version, build)


def _check_preset(value: object) -> dict[str, JsonValue]:
    if not isinstance(value, dict) or not value:
        raise _invalid("Snapshot preset must be a nonempty JSON object.")
    return value


def parse_snapshot(raw: bytes, device_id: str, backup_id: str) -> Snapshot:
    """Strictly validate one format-1 file body against the requested device and ID."""
    if len(raw) > MAX_SNAPSHOT_BYTES:
        raise _invalid("Snapshot file exceeds the size limit.")
    try:
        document = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicates,
            parse_constant=_reject_constant,
        )
    except (ValueError, RecursionError):
        raise _invalid("Snapshot file is not valid strict JSON.") from None
    if not isinstance(document, dict) or set(document) != ENVELOPE_KEYS:
        raise _invalid("Snapshot envelope has missing or unknown keys.")
    version = document["format_version"]
    if not _is_int(version) or version != FORMAT_VERSION:
        # Issue #21 (TD-21-5): name a plausible integer version; the file stays untouched.
        if isinstance(version, int) and not isinstance(version, bool) and 0 <= version <= 9999:
            raise _invalid(
                f"Unsupported snapshot format version {version}; this server reads format "
                f"version {FORMAT_VERSION}."
            )
        raise _invalid("Unsupported snapshot format version.")
    if document["backup_id"] != backup_id:
        raise _invalid("Snapshot backup ID does not match its identity.")
    if document["device_id"] != device_id:
        raise _invalid("Snapshot belongs to a different device.")
    created = document["created_at"]
    if not isinstance(created, str) or not TIMESTAMP_RE.match(created):
        raise _invalid("Snapshot timestamp is malformed.")
    try:
        _parse_timestamp(created)
    except ValueError:
        raise _invalid("Snapshot timestamp is malformed.") from None
    match = BACKUP_ID_RE.match(backup_id)
    if match is None or match.group(1) != created.translate(str.maketrans("", "", "-:")):
        raise _invalid("Snapshot timestamp does not match its backup ID.")
    return Snapshot(
        backup_id,
        device_id,
        _check_preset_id(document["preset_id"]),
        _check_firmware(document["firmware"]),
        created,
        _check_preset(document["preset"]),
    )


def _device_dir_ok(path: Path) -> bool:
    try:
        return stat.S_ISDIR(path.lstat().st_mode)
    except OSError:
        return False


class SnapshotStore:
    """Process-shared store; mutations are serialized by the caller's device lock."""

    def __init__(
        self,
        directory: Path,
        retain_per_device: int,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.directory = directory
        self.retain_per_device = retain_per_device
        self._now = now if now is not None else (lambda: datetime.now(UTC))

    # -- path safety -------------------------------------------------------

    @staticmethod
    def _check_device(device_id: str) -> None:
        if not isinstance(device_id, str) or not DEVICE_ID_RE.match(device_id):
            raise _invalid("Device ID is not a valid configured identifier.")

    @staticmethod
    def _check_backup_id(backup_id: str) -> None:
        if not isinstance(backup_id, str) or not BACKUP_ID_RE.match(backup_id):
            raise _invalid("Backup ID is malformed.")

    def _device_dir(self, device_id: str) -> Path:
        self._check_device(device_id)
        return self.directory / device_id

    # -- dry run -----------------------------------------------------------

    def plan_backup(self, device_id: str) -> dict[str, JsonValue]:
        """Dry-run report; strictly read-only (advisory os.access, no mkdir/temp files)."""
        path = self._device_dir(device_id)
        probe = path
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        writable = os.access(probe, os.W_OK | os.X_OK)
        return {"backup_required": True, "backup_storage_writable": writable}

    # -- read --------------------------------------------------------------

    def load(self, device_id: str, backup_id: str) -> Snapshot:
        self._check_device(device_id)
        self._check_backup_id(backup_id)
        device_dir = self._device_dir(device_id)
        path = device_dir / f"{backup_id}.json"
        if not _device_dir_ok(self.directory) or not _device_dir_ok(device_dir):
            raise fail("PRESET_NOT_FOUND", "No snapshot with this ID exists for the device.")
        try:
            if not stat.S_ISREG(path.lstat().st_mode):  # no FIFO/device/symlink/dir open
                raise _invalid("Snapshot is not a readable regular file.")
            # O_NONBLOCK: a file swapped for a FIFO after lstat must not hang under the lock.
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
            fd = os.open(path, flags)
        except FileNotFoundError:
            raise fail(
                "PRESET_NOT_FOUND", "No snapshot with this ID exists for the device."
            ) from None
        except OSError:
            raise _invalid("Snapshot is not a readable regular file.") from None
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise _invalid("Snapshot is not a readable regular file.")
            with os.fdopen(fd, "rb", closefd=False) as handle:
                raw = handle.read(MAX_SNAPSHOT_BYTES + 1)
        except OSError:
            raise fail("BACKUP_FAILED", _SAFE["READ_FAILED"]) from None
        finally:
            os.close(fd)
        return parse_snapshot(raw, device_id, backup_id)

    def list_snapshots(self, device_id: str) -> SnapshotListing:
        """Valid snapshots oldest first; invalid entries are counted, never named."""
        device_dir = self._device_dir(device_id)
        if not _device_dir_ok(self.directory) or not _device_dir_ok(device_dir):
            return SnapshotListing((), 0)
        valid: list[Snapshot] = []
        invalid = 0
        warnings: list[str] = []
        try:
            with os.scandir(device_dir) as entries:
                for count, entry in enumerate(entries):
                    if count >= MAX_DIRECTORY_ENTRIES:
                        warnings.append("Backup directory scan limit reached; listing is partial.")
                        break
                    match = FILE_NAME_RE.match(entry.name)
                    if match is None:
                        continue  # temp, foreign and unknown names are not snapshots
                    try:
                        valid.append(self.load(device_id, match.group(1)))
                    except ClientFailure:
                        invalid += 1
        except OSError:
            raise fail("BACKUP_FAILED", _SAFE["READ_FAILED"]) from None
        valid.sort(key=lambda item: (item.created_at, item.backup_id))
        if invalid:
            warnings.append(f"{invalid} invalid snapshot file(s) ignored and left untouched.")
        return SnapshotListing(tuple(valid), invalid, tuple(warnings))

    # -- write -------------------------------------------------------------

    def backup_preset(
        self,
        device_id: str,
        preset_id: int,
        preset: dict[str, JsonValue],
        firmware: Firmware,
        protect: frozenset[str] = frozenset(),
    ) -> BackupRecord:
        """Durably store one preset object; raise BACKUP_FAILED/VALIDATION_ERROR otherwise.

        Call inside the device lock, with a freshly read object, immediately before
        the destructive write. Prune runs only after the new snapshot is durable and
        never deletes the new snapshot or a ``protect``ed one (for example the source
        of a running restore).
        """
        try:
            return self._backup(device_id, preset_id, preset, firmware, protect)
        except ClientFailure as failure:
            if failure.error.code == "VALIDATION_ERROR":
                raise
            LOGGER.warning("snapshot store failure device=%s", device_id)
            raise
        except Exception as error:  # never leak path/payload text
            LOGGER.warning(
                "snapshot store failure device=%s class=%s", device_id, type(error).__name__
            )
            raise fail("BACKUP_FAILED", _SAFE["BACKUP_FAILED"]) from None

    def _backup(
        self,
        device_id: str,
        preset_id: int,
        preset: dict[str, JsonValue],
        firmware: Firmware,
        protect: frozenset[str] = frozenset(),
    ) -> BackupRecord:
        self._check_device(device_id)
        _check_preset_id(preset_id)
        _check_preset(preset)
        _check_firmware({"version": firmware.version, "build_id": firmware.build_id})
        device_dir = self._device_dir(device_id)
        # Full serialization/size check with a placeholder ID before any filesystem effect.
        self._serialize(
            "b-00000000T000000Z-000000000000",
            device_id,
            preset_id,
            firmware,
            "2000-01-01T00:00:00Z",
            preset,
        )
        try:
            # Concurrent first snapshots of different devices may race on `backups/`;
            # an existing directory is fine (validated below). Sync the parent only
            # when this call created the directory.
            for directory in (self.directory, device_dir):
                created_directory = False
                try:
                    directory.mkdir(mode=0o700)
                    created_directory = True
                except FileExistsError:
                    pass
                if not _device_dir_ok(directory):
                    raise fail("BACKUP_FAILED", _SAFE["BACKUP_FAILED"])
                if created_directory:
                    self._fsync_directory(directory.parent)
        except OSError:
            raise fail("BACKUP_FAILED", _SAFE["BACKUP_FAILED"]) from None
        if not _device_dir_ok(self.directory) or not _device_dir_ok(device_dir):
            raise fail("BACKUP_FAILED", _SAFE["BACKUP_FAILED"])
        for _ in range(ID_ATTEMPTS):
            created = self._now().astimezone(UTC).replace(microsecond=0)
            stamp = created.strftime("%Y%m%dT%H%M%SZ")
            backup_id = f"b-{stamp}-{secrets.token_hex(6)}"
            created_at = created.strftime("%Y-%m-%dT%H:%M:%SZ")
            body = self._serialize(backup_id, device_id, preset_id, firmware, created_at, preset)
            if self._promote(device_dir, backup_id, body, device_id):
                break
        else:
            raise fail("BACKUP_FAILED", _SAFE["BACKUP_FAILED"])
        pruned, warnings = self._prune(device_id, keep=backup_id, protect=protect)
        return BackupRecord(backup_id, device_id, preset_id, created_at, pruned, warnings)

    @staticmethod
    def _serialize(
        backup_id: str,
        device_id: str,
        preset_id: int,
        firmware: Firmware,
        created_at: str,
        preset: dict[str, JsonValue],
    ) -> bytes:
        envelope: dict[str, JsonValue] = {
            "format_version": FORMAT_VERSION,
            "backup_id": backup_id,
            "device_id": device_id,
            "preset_id": preset_id,
            "firmware": {"version": firmware.version, "build_id": firmware.build_id},
            "created_at": created_at,
            "preset": preset,
        }
        try:
            text = json.dumps(envelope, indent=2, ensure_ascii=False, allow_nan=False)
            if json.loads(text)["preset"] != preset:
                raise ValueError("preset is not exactly representable as JSON")
        except (ValueError, TypeError, RecursionError):
            raise _invalid("Preset object is not a finite JSON object.") from None
        body = (text + "\n").encode("utf-8")
        if len(body) > MAX_SNAPSHOT_BYTES:
            raise _invalid("Preset snapshot would exceed the size limit.")
        return body

    def _promote(self, device_dir: Path, backup_id: str, body: bytes, device_id: str) -> bool:
        """Write temp, fsync, validate, link to final name, fsync dir, revalidate.

        Returns False on an ID collision (caller regenerates). Never overwrites.
        """
        temp = device_dir / f".{backup_id}.tmp"
        final = device_dir / f"{backup_id}.json"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(temp, flags, 0o600)
        except FileExistsError:
            return False
        linked = False
        try:
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(body)
                    handle.flush()
                    os.fsync(handle.fileno())
                if temp.read_bytes() != body:
                    raise OSError("temporary snapshot readback mismatch")
                parse_snapshot(temp.read_bytes(), device_id, backup_id)
                try:
                    os.link(temp, final)
                except FileExistsError:
                    return False
                linked = True
                self._fsync_directory(device_dir)
                if final.read_bytes() != body:
                    raise OSError("final snapshot readback mismatch")
                parse_snapshot(final.read_bytes(), device_id, backup_id)
            except ClientFailure:
                raise fail("BACKUP_FAILED", _SAFE["BACKUP_FAILED"]) from None
            except OSError:
                raise fail("BACKUP_FAILED", _SAFE["BACKUP_FAILED"]) from None
        except ClientFailure:
            if linked:
                final.unlink(missing_ok=True)  # exclusively created by this call
            raise
        finally:
            temp.unlink(missing_ok=True)
        return True

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        """Best effort: POSIX only, skipped on Windows, errors tolerated."""
        if os.name == "nt":
            return
        try:
            fd = os.open(path, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(fd)
        except OSError:
            pass
        finally:
            os.close(fd)

    # -- retention ---------------------------------------------------------

    def _prune(
        self, device_id: str, keep: str, protect: frozenset[str] = frozenset()
    ) -> tuple[int, tuple[str, ...]]:
        """Delete oldest valid snapshots beyond retention; failure is a warning only.

        ``keep`` and ``protect``ed IDs are never deleted; younger snapshots go instead.
        """
        try:
            listing = self.list_snapshots(device_id)
            ordered = [item for item in listing.snapshots]
            excess = len(ordered) - self.retain_per_device
            removed = 0
            warnings = list(listing.warnings)
            for item in ordered:
                if excess <= 0:
                    break
                if item.backup_id == keep or item.backup_id in protect:
                    continue
                path = self._device_dir(device_id) / f"{item.backup_id}.json"
                try:
                    if not stat.S_ISREG(path.lstat().st_mode):
                        continue  # symlinks and non-files are never deleted
                    path.unlink()
                except OSError:
                    warnings.append("Retention pruning could not remove an old snapshot.")
                    LOGGER.warning("snapshot prune failure device=%s", device_id)
                    continue
                removed += 1
                excess -= 1
            return removed, tuple(warnings)
        except Exception as error:
            LOGGER.warning(
                "snapshot prune failure device=%s class=%s", device_id, type(error).__name__
            )
            return 0, ("Retention pruning was skipped; the new snapshot is intact.",)

    # -- restoration planning (read-only, no device I/O, no writes) --------

    def plan_restore(
        self,
        device_id: str,
        backup_id: str,
        *,
        firmware_version: str,
        destination_occupied: bool,
        target_preset_id: int | None = None,
        overwrite: bool = False,
        prior_backup_id: str | None = None,
    ) -> RestorePlan:
        """Inspect a snapshot and plan an explicit manual restoration.

        The caller supplies current device facts. Exact device ID and exact firmware
        version are required; a different target ID must be passed explicitly. An
        occupied destination needs overwrite intent plus a valid prior snapshot of it.
        """
        snapshot = self.load(device_id, backup_id)
        if snapshot.firmware.version != firmware_version:
            raise fail(
                "UNSUPPORTED_CAPABILITY",
                "Snapshot firmware version differs from the device; restoration is not planned.",
            )
        target = (
            snapshot.preset_id if target_preset_id is None else _check_preset_id(target_preset_id)
        )
        if destination_occupied:
            if not overwrite:
                raise _invalid(
                    "Destination preset is occupied; explicit overwrite intent required."
                )
            if prior_backup_id is None:
                raise _invalid(
                    "Destination preset is occupied; a prior snapshot of it is required."
                )
            prior = self.load(device_id, prior_backup_id)
            if prior.preset_id != target:
                raise _invalid("Prior snapshot does not cover the destination preset.")
        steps = (
            "Confirm device ID, firmware version and the snapshot contents offline.",
            "Re-read the destination preset; if it changed since this plan, plan again.",
            "Store exactly this one preset object by hand through a verified single-entry path.",
            "Read /presets.json back and compare the stored object, unknown fields included.",
            "Do not bulk-restore, activate as a substitute, or retry blindly after a timeout.",
        )
        return RestorePlan(
            snapshot.backup_id,
            device_id,
            snapshot.preset_id,
            target,
            snapshot.firmware.version,
            destination_occupied,
            prior_backup_id if destination_occupied else None,
            steps,
        )
