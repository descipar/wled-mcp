"""Cross-process exclusive file lock for the inventory writer (issue #201, TP-201-2).

An OS-level lock (``fcntl.flock`` on POSIX, ``msvcrt.locking`` on Windows) on a sibling
lock file plus an in-process lock, so threads of one process and separate processes (the
server and the CLI) serialize alike. The OS releases the lock when the holder exits, so a
crash never leaves a stale lock; the lock file itself is never deleted.
"""

import os
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

DEFAULT_TIMEOUT_SECONDS = 5.0
_POLL_SECONDS = 0.02
_thread_lock = threading.Lock()


def config_lock_path(config_path: Path) -> Path:
    """The sibling lock file of an inventory file: ``.<filename>.lock`` (TP-201-2)."""
    return config_path.with_name(f".{config_path.name}.lock")


def config_backup_path(config_path: Path) -> Path:
    """The one-generation backup of an inventory file: ``<filename>.bak`` (TP-201-1)."""
    return config_path.with_name(f"{config_path.name}.bak")


class LockTimeout(Exception):
    """The lock stayed held by another writer for the whole bounded wait."""


def _try_lock(fd: int) -> bool:
    if os.name == "nt":
        import msvcrt

        try:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)  # type: ignore[attr-defined,unused-ignore]
        except OSError:
            return False
        return True
    import fcntl

    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def _unlock(fd: int) -> None:
    if os.name == "nt":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)  # type: ignore[attr-defined,unused-ignore]
        return
    import fcntl

    fcntl.flock(fd, fcntl.LOCK_UN)


@contextmanager
def exclusive_lock(path: Path, timeout: float) -> Iterator[None]:
    """Hold the exclusive lock on ``path`` (created if missing); ``LockTimeout`` after ``timeout``.

    ``OSError`` from opening the lock file (for example a read-only directory) propagates.
    """
    deadline = time.monotonic() + timeout
    if not _thread_lock.acquire(timeout=max(0.0, timeout)):
        raise LockTimeout
    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            if os.name == "nt" and os.fstat(fd).st_size == 0:
                os.write(fd, b"\0")  # a byte range must exist to be locked
            while not _try_lock(fd):
                if time.monotonic() >= deadline:
                    raise LockTimeout
                time.sleep(_POLL_SECONDS)
            try:
                yield
            finally:
                _unlock(fd)
        finally:
            os.close(fd)
    finally:
        _thread_lock.release()
