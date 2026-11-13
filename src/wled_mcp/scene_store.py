"""Local store for group and scene definitions (issue #17, ISSUE-17-DEC-001).

Layout: ``<data-dir>/groups/<id>.json`` and ``<data-dir>/scenes/<id>.json``, one strict
JSON document per item. The store performs no device I/O. It follows the proven backup
pattern (``backups.py``): strict parse on every read, files that cannot be used are
counted and never rewritten, migrated or pruned, directories 0700 and files 0600 on POSIX,
atomic replace (temporary file in the same directory, fsync, replace, directory fsync best
effort), a bound on the directory scan, and symlinks and non-regular files refused.

Save and delete refuse to touch a file that cannot be read by this server (invalid,
written by a newer version, not a regular file), so a stored newer-version document is
never overwritten. A per-process lock per directory serializes writes, also between two
store instances over the same directory (for example two operation sets in one process);
several server processes sharing one data directory are not coordinated. Diagnostics go
to the logging system (stderr) and never carry paths, names or document content.
"""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
import stat
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from pydantic import JsonValue

from wled_mcp.client import ClientFailure
from wled_mcp.formats import invalid, is_definition_id

LOGGER = logging.getLogger("wled_mcp.scene_store")

MAX_DIRECTORY_ENTRIES: Final = 10_000
FILE_NAME_RE: Final = re.compile(r"^([a-z0-9][a-z0-9_-]{0,63})\.json$")

STORE_RECONCILE: Final = (
    "Repair the configured data path; no device was contacted. Then repeat the request explicitly."
)
UNREADABLE_RECONCILE: Final = (
    "The stored file is left untouched. Repair or remove it outside this server, or choose "
    "another ID."
)


_DIRECTORY_LOCKS: dict[str, threading.Lock] = {}
_DIRECTORY_LOCKS_GUARD = threading.Lock()


def _directory_lock(directory: Path) -> threading.Lock:
    """The one write lock of a directory, shared by every store instance over it."""
    key = os.path.normcase(os.path.abspath(directory))
    with _DIRECTORY_LOCKS_GUARD:
        return _DIRECTORY_LOCKS.setdefault(key, threading.Lock())


def storage_failed(
    message: str = "The definition store could not be read or written.",
) -> ClientFailure:
    return ClientFailure("STORAGE_FAILED", message, reconciliation=STORE_RECONCILE)


@dataclass(frozen=True)
class Listing[T]:
    items: tuple[T, ...]
    invalid_count: int
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class SaveResult[T]:
    replaced: T | None
    stored: bool  # False for a dry run


def _is_dir(path: Path) -> bool:
    try:
        return stat.S_ISDIR(path.lstat().st_mode)
    except OSError:
        return False


class DefinitionStore[T]:
    """One directory of definitions of one kind (``group`` or ``scene``)."""

    def __init__(
        self,
        directory: Path,
        kind: str,
        parse: Callable[[bytes], T],
        id_of: Callable[[T], str],
        *,
        max_items: int,
        max_bytes: int,
    ) -> None:
        self.directory = directory
        self.kind = kind
        self._parse = parse
        self._id_of = id_of
        self.max_items = max_items
        self.max_bytes = max_bytes
        self._lock = _directory_lock(directory)

    # -- helpers ---------------------------------------------------------------

    def _check_id(self, identifier: str) -> None:
        if not is_definition_id(identifier):
            raise invalid(f"The {self.kind} ID is not valid.")

    def _path(self, identifier: str) -> Path:
        self._check_id(identifier)
        return self.directory / f"{identifier}.json"

    def _unreadable(self, identifier: str, detail: str) -> ClientFailure:
        return invalid(
            f"The stored {self.kind} {identifier!r} cannot be used: {detail}",
            UNREADABLE_RECONCILE,
        )

    def _not_found(self, identifier: str) -> ClientFailure:
        return invalid(f"No {self.kind} with ID {identifier!r} is stored.")

    def _read(self, identifier: str, path: Path) -> bytes:
        """Raw bytes of a regular file; FileNotFoundError means absent."""
        try:
            if not stat.S_ISREG(path.lstat().st_mode):  # no FIFO, device, symlink or directory
                raise self._unreadable(identifier, "it is not a regular file.")
            # O_NONBLOCK: a file swapped for a FIFO after lstat must not hang the server.
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
            fd = os.open(path, flags)
        except FileNotFoundError:
            raise
        except ClientFailure:
            raise
        except OSError:
            raise self._unreadable(identifier, "it is not a readable regular file.") from None
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise self._unreadable(identifier, "it is not a regular file.")
            with os.fdopen(fd, "rb", closefd=False) as handle:
                return handle.read(self.max_bytes + 1)
        except ClientFailure:
            raise
        except OSError:
            LOGGER.warning("definition store read failure kind=%s", self.kind)
            raise storage_failed() from None
        finally:
            os.close(fd)

    def _decode(self, identifier: str, raw: bytes) -> T:
        try:
            item = self._parse(raw)
        except ClientFailure as failure:
            raise self._unreadable(identifier, failure.error.message) from None
        if self._id_of(item) != identifier:
            raise self._unreadable(identifier, "its ID does not match the file name.")
        return item

    def _load_existing(self, identifier: str) -> T | None:
        """The stored item, ``None`` when absent; raises when the file cannot be used."""
        path = self._path(identifier)
        if not _is_dir(self.directory):
            return None
        try:
            raw = self._read(identifier, path)
        except FileNotFoundError:
            return None
        return self._decode(identifier, raw)

    def _count(self) -> int:
        if not _is_dir(self.directory):
            return 0
        try:
            with os.scandir(self.directory) as entries:
                matched = 0
                for count, entry in enumerate(entries):
                    if count >= MAX_DIRECTORY_ENTRIES:
                        # A partial count cannot prove that there is room for a new item.
                        raise storage_failed(
                            "Definition directory scan limit reached; no file stored."
                        )
                    if FILE_NAME_RE.match(entry.name):
                        matched += 1
                return matched
        except OSError:
            LOGGER.warning("definition store scan failure kind=%s", self.kind)
            raise storage_failed() from None

    # -- read ------------------------------------------------------------------

    def load(self, identifier: str) -> T:
        item = self._load_existing(identifier)
        if item is None:
            raise self._not_found(identifier)
        return item

    def list_items(self) -> Listing[T]:
        """Valid items by ID; unusable entries are counted, never named."""
        if not _is_dir(self.directory):
            return Listing((), 0)
        found: list[T] = []
        invalid_count = 0
        warnings: list[str] = []
        try:
            with os.scandir(self.directory) as entries:
                for count, entry in enumerate(entries):
                    if count >= MAX_DIRECTORY_ENTRIES:
                        warnings.append(
                            f"{self.kind} directory scan limit reached; listing is partial."
                        )
                        break
                    match = FILE_NAME_RE.match(entry.name)
                    if match is None:
                        continue  # temporary and foreign names are not definitions
                    try:
                        found.append(self.load(match.group(1)))
                    except ClientFailure as failure:
                        if failure.error.code == "STORAGE_FAILED":
                            raise
                        invalid_count += 1
        except OSError:
            LOGGER.warning("definition store scan failure kind=%s", self.kind)
            raise storage_failed() from None
        found.sort(key=self._id_of)
        if invalid_count:
            warnings.append(
                f"{invalid_count} stored {self.kind} file(s) cannot be used by this server "
                "and were left untouched."
            )
        return Listing(tuple(found), invalid_count, tuple(warnings))

    # -- write -----------------------------------------------------------------

    def save(self, item: T, body: bytes, *, overwrite: bool, dry_run: bool) -> SaveResult[T]:
        """Store ``body`` (the serialized document of ``item``) atomically.

        An existing ID needs ``overwrite``; a file that cannot be used is never replaced.
        ``dry_run`` performs the same checks with bounded reads and writes nothing.
        """
        identifier = self._id_of(item)
        if len(body) > self.max_bytes:
            raise invalid(f"The {self.kind} document exceeds {self.max_bytes} bytes.")
        with self._lock:
            previous = self._load_existing(identifier)
            if previous is not None and not overwrite:
                raise invalid(
                    f"A {self.kind} with ID {identifier!r} already exists; pass overwrite=true "
                    "to replace it."
                )
            if previous is None and self._count() >= self.max_items:
                raise invalid(
                    f"The store holds the maximum of {self.max_items} {self.kind}s; delete one "
                    "first."
                )
            if dry_run:
                return SaveResult(previous, False)
            try:
                self._write(identifier, body)
            except ClientFailure:
                raise
            except Exception as error:  # never leak path or document text
                LOGGER.warning(
                    "definition store write failure kind=%s class=%s",
                    self.kind,
                    type(error).__name__,
                )
                raise storage_failed(
                    f"The {self.kind} could not be stored durably; any previous version is intact."
                ) from None
            return SaveResult(previous, True)

    def delete(self, identifier: str, *, dry_run: bool) -> T:
        """Remove one usable definition; returns the removed document."""
        with self._lock:
            item = self.load(identifier)
            if dry_run:
                return item
            try:
                self._path(identifier).unlink()
                self._fsync_directory(self.directory)
            except OSError as error:
                LOGGER.warning(
                    "definition store delete failure kind=%s class=%s",
                    self.kind,
                    type(error).__name__,
                )
                raise storage_failed(f"The {self.kind} could not be deleted.") from None
            return item

    def _write(self, identifier: str, body: bytes) -> None:
        try:
            self.directory.mkdir(mode=0o700)
            self._fsync_directory(self.directory.parent)
        except FileExistsError:
            pass
        if not _is_dir(self.directory):  # a symlink or file in its place is never followed
            raise storage_failed(f"The {self.kind} directory is not a usable directory.")
        final = self.directory / f"{identifier}.json"
        temp = self.directory / f".{identifier}.{secrets.token_hex(6)}.tmp"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(temp, flags, 0o600)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(body)
                handle.flush()
                os.fsync(handle.fileno())
            if temp.read_bytes() != body:
                raise OSError("temporary file readback mismatch")
            self._decode(identifier, temp.read_bytes())
            os.replace(temp, final)
        except BaseException:
            temp.unlink(missing_ok=True)
            raise
        self._fsync_directory(self.directory)

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


def serialize_document(document: dict[str, JsonValue], label: str, max_bytes: int) -> bytes:
    """The exact bytes stored: indented strict JSON with a trailing newline."""
    try:
        text = json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False)
        body = (text + "\n").encode("utf-8")
    except (ValueError, TypeError, RecursionError):
        raise invalid(f"The {label} is not a finite JSON document.") from None
    if len(body) > max_bytes:
        raise invalid(f"The {label} would exceed {max_bytes} bytes.")
    return body
