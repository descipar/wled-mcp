"""#131: every file that enters the wheel or the staged release has an end-of-line rule.

Without a rule ``* text=auto`` checks a file out with CRLF on Windows, which changes the bytes
of a wheel or a staged directory built there. The test asks git, so it also covers new files
under ``src/``.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGED = (
    "LICENSE",
    "NOTICE",
    "README.md",
    "pyproject.toml",
    "requirements-runtime.txt",
    "deploy/http/Dockerfile",
    "deploy/http/Dockerfile.dockerignore",
    "deploy/mcpb/manifest.template.json",
    "deploy/mcpb/server/main.py",
    "deploy/mcpb/schema/mcpb-manifest-v0.3.schema.json",
)

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")


def eol_attribute(paths: list[str]) -> dict[str, str]:
    result = subprocess.run(
        ["git", "check-attr", "eol", "--", *paths],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    found = {}
    for line in result.stdout.splitlines():
        path, _, value = line.rpartition(": ")
        found[path.removesuffix(": eol")] = value
    return found


def tracked_package_sources() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--", "src/wled_mcp"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.split()


def test_packaged_files_have_an_lf_rule():
    paths = [*PACKAGED, *tracked_package_sources()]
    assert len(paths) > len(PACKAGED), "no package sources found"
    missing = {path: value for path, value in eol_attribute(paths).items() if value != "lf"}
    assert missing == {}
