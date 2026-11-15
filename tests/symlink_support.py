"""Shared helper for tests that need a symbolic link (#242).

Creating a symlink fails on hosts without the privilege (Windows without Developer Mode and
not elevated: ``WinError 1314``) and on file systems without support. Such a host skips the
test with a stated reason; a real error (a missing parent, an existing path) still fails.
"""

from pathlib import Path

import pytest


def symlink_or_skip(link: Path, target: Path, *, target_is_directory: bool = False) -> None:
    """Create ``link`` pointing at ``target`` or skip the calling test if the host cannot."""
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except (FileExistsError, FileNotFoundError):
        raise
    except (OSError, NotImplementedError):
        # No error text: it names local paths.
        pytest.skip(
            "the host cannot create symbolic links (no privilege or no file system support)"
        )
