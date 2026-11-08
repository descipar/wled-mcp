"""Stage an immutable, versioned release directory for both deployment modes.

The directory ``<output>/<version>/`` receives the built wheel, the exported runtime
constraints, the HTTP image Dockerfile with its allowlist ``.dockerignore``, a
``SHA256SUMS`` file and a ``RELEASE`` record (version, source commit, tree state). It is
the source for the stdio hub entry (uvx ``--from``/``--constraints``) and the build
context of the HTTP image. An existing version directory is never overwritten.

Release mode (default) stages a wheel built from the checkout, for example with
``uv build --wheel --no-build-isolation``; its version is ``project.version``.

Non-release mode (``--non-release``) builds the wheel itself from ``git archive`` of the
checked-out commit, with the version rewritten to ``<base>+g<12hex>`` only in the
exported copy (``.dirty`` appended with ``--dirty``, which includes uncommitted changes
to tracked files). No tracked file is edited. ``RELEASE`` then also records
``build_kind=non-release``, the local ``label`` and the derived ``image_tag``. The
scheme is defined in docs/contract/versioning.md.

Local only: nothing is uploaded, published, pushed or deployed.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONSTRAINTS = "requirements-runtime.txt"
IMAGE = "wled-mcp"
COMMIT_DIGITS = 12
RELEASE_VERSION = re.compile(r"\d+\.\d+\.\d+(?:rc\d+)?")
NON_RELEASE_LABEL = re.compile(rf"g[0-9a-f]{{{COMMIT_DIGITS}}}(?:\.dirty)?")
PROJECT_VERSION_LINE = re.compile(r'^version = "(?P<version>[^"]+)"$', flags=re.M)

Builder = Callable[[Path, Path], Path]
"""Builds the wheel of the source tree (first argument) into a directory (second)."""


class StageError(Exception):
    """A staging precondition failed; nothing usable was written."""


def project_version(root: Path) -> str:
    with (root / "pyproject.toml").open("rb") as stream:
        return str(tomllib.load(stream)["project"]["version"])


def wheel_name(version: str) -> str:
    return f"wled_mcp-{version}-py3-none-any.whl"


def image_tag(version: str) -> str:
    """OCI tag of a version: identical for releases, ``+`` mapped to ``-`` otherwise."""
    return version.replace("+", "-")


def non_release_version(base: str, commit: str, dirty: bool) -> str:
    """PEP 440 local version ``<base>+g<12hex>[.dirty]`` of a non-release build."""
    if not RELEASE_VERSION.fullmatch(base):
        raise StageError(f"Base version {base!r} is not a release version X.Y.Z[rcN].")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise StageError(f"Source commit {commit!r} is not a full 40-hex commit.")
    return f"{base}+g{commit[:COMMIT_DIGITS]}" + (".dirty" if dirty else "")


def wheel_metadata_version(wheel: Path, version: str) -> str:
    with zipfile.ZipFile(wheel) as archive:
        metadata = archive.read(f"wled_mcp-{version}.dist-info/METADATA").decode("utf-8")
    for line in metadata.splitlines():
        if line.startswith("Version: "):
            return line.removeprefix("Version: ").strip()
    raise StageError("Wheel metadata has no Version field.")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stage(
    root: Path,
    wheel: Path,
    output: Path,
    commit: str,
    tree_state: str,
    *,
    non_release: bool = False,
) -> Path:
    """Create ``output/<version>`` with verified, checksummed release inputs.

    ``root`` is the source tree whose ``project.version``, constraints and image files
    are staged; for a non-release build it is the exported copy with the rewritten
    version, which must then carry a ``+g<12hex>[.dirty]`` label of ``commit``.
    """
    version = project_version(root)
    base, _, label = version.partition("+")
    if non_release:
        if not NON_RELEASE_LABEL.fullmatch(label) or not RELEASE_VERSION.fullmatch(base):
            raise StageError(f"Version {version} is not a non-release <base>+g<12hex>[.dirty].")
        if not commit.startswith(label[1 : 1 + COMMIT_DIGITS]):
            raise StageError(f"Version {version} does not name source commit {commit}.")
    elif label:
        raise StageError(f"Version {version} has a local label; stage it with --non-release.")
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
    record = f"version={version}\n"
    if non_release:
        record += f"build_kind=non-release\nlabel={label}\n"
    record += f"source_commit={commit}\nsource_tree={tree_state}\n"
    if non_release:
        record += f"image_tag={IMAGE}:{image_tag(version)}\n"
    (staging / "RELEASE").write_text(record, encoding="utf-8", newline="\n")
    staging.rename(target)
    return target


def command_label(command: object) -> str:
    """The program and subcommand of a failed command, for example ``git archive``."""
    parts = command if isinstance(command, (list, tuple)) else [command]
    return " ".join(map(str, parts[:2]))


def stderr_tail(stderr: str | bytes | None, limit: int = 2000) -> str:
    """The end of a failed command's stderr as a message suffix (empty if there is none)."""
    if isinstance(stderr, bytes):
        stderr = stderr.decode("utf-8", errors="replace")
    text = (stderr or "").strip()
    return f"\n{text[-limit:]}" if text else ""


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True, timeout=30
    )
    return result.stdout.strip()


def export_tree(root: Path, ref: str, destination: Path) -> None:
    """Extract the tracked files of ``ref`` (``git archive``) into ``destination``."""
    archive = subprocess.run(
        ["git", "archive", "--format=tar", ref],
        cwd=root,
        capture_output=True,
        check=True,
        timeout=60,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(destination, filter="data")


def rewrite_version(pyproject: Path, version: str) -> None:
    """Set ``project.version`` in an exported copy; refuse anything ambiguous."""
    text = pyproject.read_text("utf-8")
    if len(PROJECT_VERSION_LINE.findall(text)) != 1:
        raise StageError("Exported pyproject.toml has no single 'version = \"...\"' line.")
    rewritten = PROJECT_VERSION_LINE.sub(f'version = "{version}"', text)
    pyproject.write_text(rewritten, encoding="utf-8", newline="\n")
    if project_version(pyproject.parent) != version:
        raise StageError("The rewritten version line is not project.version.")


def uv_build(source: Path, out_dir: Path) -> Path:
    """Build the wheel of ``source`` offline with the current interpreter's hatchling."""
    command = ["uv", "build", "--offline", "--wheel", "--no-build-isolation"]
    command += ["--python", sys.executable, "--out-dir", str(out_dir)]
    result = subprocess.run(command, cwd=source, capture_output=True, text=True, timeout=300)
    if result.returncode:
        raise StageError(f"Wheel build failed: {result.stderr.strip()[-2000:]}")
    wheels = sorted(out_dir.glob("wled_mcp-*.whl"))
    if len(wheels) != 1:
        raise StageError(f"Expected one built wheel, found {[w.name for w in wheels]}.")
    return wheels[0]


def stage_non_release(
    root: Path, output: Path, *, dirty: bool = False, build: Builder = uv_build
) -> Path:
    """Build and stage the checked-out commit (plus tracked changes with ``dirty``)."""
    commit = git(root, "rev-parse", "HEAD")
    modified = bool(git(root, "status", "--porcelain", "--untracked-files=no"))
    ref = commit
    if dirty:
        if not modified:
            raise StageError("--dirty given, but tracked files have no uncommitted changes.")
        # A dangling commit object of the working tree; the checkout, index and stash list
        # stay unchanged. The identity only labels that temporary object.
        identity = ("-c", "user.name=wled-mcp staging", "-c", "user.email=staging@invalid")
        ref = git(root, *identity, "stash", "create")
    with tempfile.TemporaryDirectory(prefix="wled-mcp-non-release-") as temporary:
        source = Path(temporary) / "source"
        source.mkdir()
        export_tree(root, ref, source)
        version = non_release_version(project_version(source), commit, dirty)
        if (output / version).exists():
            raise StageError(
                f"Release directory {output / version} already exists; releases are immutable."
            )
        rewrite_version(source / "pyproject.toml", version)
        out_dir = Path(temporary) / "dist"
        out_dir.mkdir()
        wheel = build(source, out_dir)
        tree_state = "modified" if dirty else "clean"
        return stage(source, wheel, output, commit, tree_state, non_release=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--wheel", type=Path, help="Built wheel (default: dist/<name>).")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".artifacts" / "release",
        help="Parent directory for <version>/ (default: .artifacts/release).",
    )
    parser.add_argument(
        "--non-release",
        action="store_true",
        help="Build HEAD from git archive as <version>+g<12hex> and stage it.",
    )
    parser.add_argument(
        "--dirty",
        action="store_true",
        help="With --non-release: include uncommitted tracked changes (+g<12hex>.dirty).",
    )
    args = parser.parse_args(argv)
    if args.dirty and not args.non_release:
        parser.error("--dirty requires --non-release")
    if args.wheel and args.non_release:
        parser.error("--non-release builds its own wheel; --wheel is not accepted")
    try:
        if args.non_release:
            if not args.dirty and git(ROOT, "status", "--porcelain", "--untracked-files=no"):
                print(
                    "Note: uncommitted changes are not included; use --dirty to include them.",
                    file=sys.stderr,
                )
            target = stage_non_release(ROOT, args.output.resolve(), dirty=args.dirty)
            tree_state = "clean"
        else:
            version = project_version(ROOT)
            wheel = args.wheel or ROOT / "dist" / wheel_name(version)
            commit = git(ROOT, "rev-parse", "HEAD")
            tree_state = "clean" if not git(ROOT, "status", "--porcelain") else "modified"
            target = stage(ROOT, wheel.resolve(), args.output.resolve(), commit, tree_state)
    except StageError as exc:
        print(f"Staging failed: {exc}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(
            f"Staging failed: {command_label(exc.cmd)} exited {exc.returncode}."
            f"{stderr_tail(exc.stderr)}",
            file=sys.stderr,
        )
        return 1
    except subprocess.TimeoutExpired as exc:
        print(
            f"Staging failed: {command_label(exc.cmd)} did not finish within "
            f"{exc.timeout:g} seconds.",
            file=sys.stderr,
        )
        return 1
    print(f"Staged {target}")
    print((target / "SHA256SUMS").read_text(encoding="utf-8"), end="")
    print((target / "RELEASE").read_text(encoding="utf-8"), end="")
    if tree_state != "clean":
        print("Warning: source tree has uncommitted changes.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
