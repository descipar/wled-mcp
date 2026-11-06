"""Stage an immutable, versioned release directory for both deployment modes.

The directory ``<output>/<version>/`` receives the built wheel, the exported runtime
constraints, the HTTP image Dockerfile with its allowlist ``.dockerignore``, a
``SHA256SUMS`` file and a ``RELEASE`` record (version, source commit, tree state). It is
the source for the stdio hub entry (uvx ``--from``/``--constraints``) and the build
context of the HTTP image. An existing version directory is never overwritten.

Local only: nothing is uploaded, published, pushed or deployed. Build the wheel first,
for example with ``uv build --wheel --no-build-isolation``.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONSTRAINTS = "requirements-runtime.txt"


class StageError(Exception):
    """A staging precondition failed; nothing usable was written."""


def project_version(root: Path) -> str:
    with (root / "pyproject.toml").open("rb") as stream:
        return str(tomllib.load(stream)["project"]["version"])


def wheel_name(version: str) -> str:
    return f"wled_mcp-{version}-py3-none-any.whl"


def wheel_metadata_version(wheel: Path, version: str) -> str:
    with zipfile.ZipFile(wheel) as archive:
        metadata = archive.read(f"wled_mcp-{version}.dist-info/METADATA").decode("utf-8")
    for line in metadata.splitlines():
        if line.startswith("Version: "):
            return line.removeprefix("Version: ").strip()
    raise StageError("Wheel metadata has no Version field.")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stage(root: Path, wheel: Path, output: Path, commit: str, tree_state: str) -> Path:
    """Create ``output/<version>`` with verified, checksummed release inputs."""
    version = project_version(root)
    if wheel.name != wheel_name(version):
        raise StageError(f"Expected wheel {wheel_name(version)}, got {wheel.name}.")
    try:
        found = wheel_metadata_version(wheel, version)
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        raise StageError("Wheel is unreadable or lacks wled-mcp metadata.") from exc
    if found != version:
        raise StageError(f"Wheel metadata version {found} differs from project {version}.")
    target = output / version
    if target.exists():
        raise StageError(f"Release directory {target} already exists; releases are immutable.")
    staging = output / f".{version}.partial"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    shutil.copyfile(wheel, staging / wheel.name)
    shutil.copyfile(root / CONSTRAINTS, staging / CONSTRAINTS)
    shutil.copyfile(root / "deploy/http/Dockerfile", staging / "Dockerfile")
    shutil.copyfile(root / "deploy/http/Dockerfile.dockerignore", staging / ".dockerignore")
    names = sorted(path.name for path in staging.iterdir())
    sums = "".join(f"{sha256(staging / name)}  {name}\n" for name in names)
    (staging / "SHA256SUMS").write_text(sums, encoding="utf-8", newline="\n")
    record = f"version={version}\nsource_commit={commit}\nsource_tree={tree_state}\n"
    (staging / "RELEASE").write_text(record, encoding="utf-8", newline="\n")
    staging.rename(target)
    return target


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True, timeout=30
    )
    return result.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--wheel", type=Path, help="Built wheel (default: dist/<name>).")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".artifacts" / "release",
        help="Parent directory for <version>/ (default: .artifacts/release).",
    )
    args = parser.parse_args(argv)
    version = project_version(ROOT)
    wheel = args.wheel or ROOT / "dist" / wheel_name(version)
    commit = git(ROOT, "rev-parse", "HEAD")
    tree_state = "clean" if not git(ROOT, "status", "--porcelain") else "modified"
    try:
        target = stage(ROOT, wheel.resolve(), args.output.resolve(), commit, tree_state)
    except StageError as exc:
        print(f"Staging failed: {exc}", file=sys.stderr)
        return 1
    print(f"Staged {target}")
    print((target / "SHA256SUMS").read_text(encoding="utf-8"), end="")
    print((target / "RELEASE").read_text(encoding="utf-8"), end="")
    if tree_state != "clean":
        print("Warning: source tree has uncommitted changes.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
