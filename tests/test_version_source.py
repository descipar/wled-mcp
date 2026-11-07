"""Issue #21 (A21-01, A21-02) and #70: one version source and non-release build identity.

The package version has exactly one hand-maintained source, ``project.version`` in
``pyproject.toml`` (docs/contract/versioning.md). The runtime reports the installed
distribution's metadata, every other artifact derives it, and a guard over the tracked
files finds any other literal copy. Non-release builds are staged from ``git archive``
with a PEP 440 local label; the staging tests use a temporary Git repository and a
synthetic wheel builder, plus one real offline build of the checked-out commit.
"""

from __future__ import annotations

import importlib.metadata
import os
import re
import shutil
import subprocess
import tomllib
import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest
from packaging.version import Version

import wled_mcp
from deploy import stage_release
from deploy.stage_release import (
    StageError,
    image_tag,
    non_release_version,
    stage,
    stage_non_release,
    uv_build,
)
from tests.test_deployment_artifacts import (
    CONSTRAINTS,
    DOCKERFILE,
    DOCKERIGNORE,
    image_checksum_commands,
    synthetic_wheel,
)
from wled_mcp import cli

ROOT = Path(__file__).resolve().parents[1]
OCI_TAG = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}")


def canonical_version(root: Path = ROOT) -> str:
    """``project.version``: the single version source every other check compares with."""
    with (root / "pyproject.toml").open("rb") as stream:
        return str(tomllib.load(stream)["project"]["version"])


# ------------------------------------------------------------------- one version source


def test_runtime_version_is_the_installed_distribution_metadata():
    assert wled_mcp.__version__ == importlib.metadata.version("wled-mcp")
    assert wled_mcp.__version__ == canonical_version()


def test_console_version_reports_the_canonical_version(capsys):
    with pytest.raises(SystemExit) as exited:
        cli.main(["--version"])
    assert exited.value.code == 0
    assert capsys.readouterr().out == f"wled-mcp {canonical_version()}\n"


def test_main_carries_a_release_version_and_its_identical_image_tag(tmp_path):
    version = canonical_version()
    assert stage_release.RELEASE_VERSION.fullmatch(version), "labels exist only in exports"
    assert image_tag(version) == version
    staged = stage(ROOT, synthetic_wheel(tmp_path, version), tmp_path / "out", "0" * 40, "clean")
    assert staged.name == version
    assert (staged / f"wled_mcp-{version}-py3-none-any.whl").is_file()


# The canonical source, its generated lock entry, retained fixtures of earlier releases
# and historical records (evidence and decision logs quote the version they were run or
# decided against). Everything else derives the version or uses a placeholder.
LITERAL_ALLOWLIST = (
    "pyproject.toml",
    "uv.lock",
    "docs/VALIDATION.md",
    "docs/validation/",
    "docs/DECISIONS.md",
    "docs/decisions/",
    "tests/fixtures/compat/",
)


def literal_pattern(version: str) -> re.Pattern[str]:
    """The version as a whole dotted number (``1.2.3`` but not ``11.2.3`` or ``1.2.3.4``)."""
    return re.compile(rf"(?<![\d.]){re.escape(version)}(?!\d|\.\d)")


def literal_hits(version: str, files: dict[str, str]) -> list[str]:
    pattern = literal_pattern(version)
    hits = []
    for name, text in sorted(files.items()):
        if name.startswith(LITERAL_ALLOWLIST):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if pattern.search(line):
                hits.append(f"{name}:{number}: {line.strip()}")
    return hits


def tracked_text_files() -> dict[str, str]:
    listed = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True, timeout=30
    ).stdout.decode("utf-8")
    files = {}
    for name in filter(None, listed.split("\0")):
        path = ROOT / name
        if not path.is_file():  # deleted in the working tree
            continue
        try:
            files[name] = path.read_text("utf-8")
        except UnicodeDecodeError:
            continue
    return files


def test_no_version_literal_outside_the_allowlist():
    files = tracked_text_files()
    assert "pyproject.toml" in files and "deploy/http/Dockerfile" in files
    assert literal_hits(canonical_version(), files) == []


@pytest.mark.parametrize(
    "planted",
    [
        "COPY wled_mcp-1.2.3-py3-none-any.whl /tmp/",
        "    image: wled-mcp:1.2.3",
        '"/app/binaries/wled-mcp/1.2.3+g0123456789ab/requirements-runtime.txt"',
        '__version__ = "1.2.3"',
        "git tag v1.2.3",
    ],
)
def test_literal_guard_finds_planted_copies(planted):
    files = {"examples/x.json": f"first\n{planted}\n", "pyproject.toml": 'version = "1.2.3"\n'}
    assert literal_hits("1.2.3", files) == [f"examples/x.json:2: {planted.strip()}"]


def test_literal_guard_ignores_other_numbers_and_allowlisted_records():
    files = {
        "README.md": "Python 3.13, WLED 11.2.3, 1.2.30, 1.2.3.4 and 0.1.2.3\n",
        "docs/decisions/issue-1.md": "decided for 1.2.3\n",
        "docs/VALIDATION.md": "ran 1.2.3\n",
    }
    assert literal_hits("1.2.3", files) == []


# --------------------------------------------------------------- non-release identity


def test_non_release_version_is_pep440_local_and_maps_to_an_oci_tag():
    commit = "0123456789abcdef0123456789abcdef01234567"
    version = non_release_version("1.2.3", commit, dirty=False)
    assert version == "1.2.3+g0123456789ab"
    parsed = Version(version)
    assert str(parsed) == version, "already in PEP 440 normal form"
    assert parsed.public == "1.2.3" and parsed.local == "g0123456789ab"
    assert parsed > Version("1.2.3") and parsed < Version("1.2.4")
    dirty = non_release_version("1.2.3", commit, dirty=True)
    assert dirty == "1.2.3+g0123456789ab.dirty" and str(Version(dirty)) == dirty
    for value, tag in ((version, "1.2.3-g0123456789ab"), (dirty, "1.2.3-g0123456789ab.dirty")):
        assert image_tag(value) == tag and OCI_TAG.fullmatch(tag)
    assert image_tag("1.2.3") == "1.2.3" and image_tag("1.2.3rc1") == "1.2.3rc1"


@pytest.mark.parametrize(
    ("base", "commit", "message"),
    [
        ("1.2.3+g0123456789ab", "0" * 40, "not a release version"),
        ("1.2", "0" * 40, "not a release version"),
        ("1.2.3.dev1", "0" * 40, "not a release version"),
        ("1.2.3", "0123456789ab", "not a full 40-hex commit"),
        ("1.2.3", "Z" * 40, "not a full 40-hex commit"),
    ],
)
def test_non_release_version_rejects_ambiguous_inputs(base, commit, message):
    with pytest.raises(StageError, match=message):
        non_release_version(base, commit, dirty=False)


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True, timeout=30
    )
    return result.stdout.strip()


@pytest.fixture
def source_repo(tmp_path: Path) -> Path:
    """A committed source tree with the files staging reads, at a synthetic version."""
    repo = tmp_path / "source"
    (repo / "deploy/http").mkdir(parents=True)
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "wled-mcp"\nversion = "1.2.3"\n', encoding="utf-8", newline="\n"
    )
    shutil.copyfile(ROOT / CONSTRAINTS, repo / CONSTRAINTS)
    shutil.copyfile(DOCKERFILE, repo / "deploy/http/Dockerfile")
    shutil.copyfile(DOCKERIGNORE, repo / "deploy/http/Dockerfile.dockerignore")
    git(repo, "init", "-q")
    git(repo, "config", "core.autocrlf", "false")
    git(repo, "add", "-A")
    git(
        repo,
        "-c",
        "user.name=synthetic",
        "-c",
        "user.email=synthetic@invalid",
        "commit",
        "-qm",
        "x",
    )
    return repo


class FakeBuilder:
    """Builds a synthetic wheel of the exported tree and remembers what it saw."""

    def __init__(self) -> None:
        self.versions: list[str] = []
        self.constraints: list[str] = []

    def __call__(self, source: Path, out_dir: Path) -> Path:
        version = canonical_version(source)
        self.versions.append(version)
        self.constraints.append((source / CONSTRAINTS).read_text("utf-8"))
        return synthetic_wheel(out_dir, version)


def release_record(target: Path) -> dict[str, str]:
    lines = (target / "RELEASE").read_text("utf-8").splitlines()
    return dict(line.split("=", 1) for line in lines)


def checksums(target: Path) -> dict[str, str]:
    lines = (target / "SHA256SUMS").read_text("utf-8").splitlines()
    return {name: digest for digest, name in (line.split("  ", 1) for line in lines)}


def test_non_release_stage_carries_one_identity_everywhere(source_repo, tmp_path):
    commit = git(source_repo, "rev-parse", "HEAD")
    build = FakeBuilder()
    target = stage_non_release(source_repo, tmp_path / "out", build=build)
    version = f"1.2.3+g{commit[:12]}"
    wheel = f"wled_mcp-{version}-py3-none-any.whl"
    assert target == tmp_path / "out" / version
    assert build.versions == [version], "the exported copy was rewritten before the build"
    with zipfile.ZipFile(target / wheel) as archive:
        metadata = archive.read(f"wled_mcp-{version}.dist-info/METADATA").decode()
    assert f"Version: {version}\n" in metadata
    assert wheel in checksums(target)
    assert (target / "RELEASE").read_text("utf-8").splitlines() == [
        f"version={version}",
        "build_kind=non-release",
        f"label=g{commit[:12]}",
        f"source_commit={commit}",
        "source_tree=clean",
        f"image_tag=wled-mcp:1.2.3-g{commit[:12]}",
    ]
    # No tracked file of the source checkout was edited.
    assert git(source_repo, "status", "--porcelain") == ""
    assert canonical_version(source_repo) == "1.2.3"


def test_repeated_non_release_staging_is_refused_before_building(source_repo, tmp_path):
    build = FakeBuilder()
    target = stage_non_release(source_repo, tmp_path / "out", build=build)
    before = (target / "RELEASE").read_bytes(), (target / "SHA256SUMS").read_bytes()
    with pytest.raises(StageError, match="immutable"):
        stage_non_release(source_repo, tmp_path / "out", build=build)
    assert len(build.versions) == 1, "no second build for an existing directory"
    assert ((target / "RELEASE").read_bytes(), (target / "SHA256SUMS").read_bytes()) == before


def test_uncommitted_changes_are_excluded_unless_dirty_is_requested(source_repo, tmp_path):
    commit = git(source_repo, "rev-parse", "HEAD")
    committed = (source_repo / CONSTRAINTS).read_text("utf-8")
    with (source_repo / CONSTRAINTS).open("a", encoding="utf-8", newline="\n") as stream:
        stream.write("# synthetic uncommitted change\n")
    changed = (source_repo / CONSTRAINTS).read_text("utf-8")

    build = FakeBuilder()
    clean = stage_non_release(source_repo, tmp_path / "out", build=build)
    assert clean.name == f"1.2.3+g{commit[:12]}"
    assert build.constraints == [committed]
    assert (clean / CONSTRAINTS).read_text("utf-8") == committed
    assert release_record(clean)["source_tree"] == "clean"

    dirty = stage_non_release(source_repo, tmp_path / "out", dirty=True, build=build)
    assert dirty.name == f"1.2.3+g{commit[:12]}.dirty"
    assert build.constraints[-1] == changed
    assert (dirty / CONSTRAINTS).read_text("utf-8") == changed
    record = release_record(dirty)
    assert record["source_tree"] == "modified" and record["source_commit"] == commit
    assert record["label"] == f"g{commit[:12]}.dirty"
    assert record["image_tag"] == f"wled-mcp:1.2.3-g{commit[:12]}.dirty"
    # The checkout keeps its change; HEAD, index and stash list are untouched.
    assert (source_repo / CONSTRAINTS).read_text("utf-8") == changed
    assert git(source_repo, "rev-parse", "HEAD") == commit
    assert git(source_repo, "diff", "--cached", "--name-only") == ""
    assert git(source_repo, "stash", "list") == ""


def test_dirty_without_uncommitted_changes_is_refused(source_repo, tmp_path):
    build = FakeBuilder()
    with pytest.raises(StageError, match="no uncommitted changes"):
        stage_non_release(source_repo, tmp_path / "out", dirty=True, build=build)
    assert build.versions == [] and not (tmp_path / "out").exists()


def labelled_tree(tmp_path: Path, version: str) -> Path:
    root = tmp_path / "tree"
    (root / "deploy/http").mkdir(parents=True)
    (root / "pyproject.toml").write_text(f'[project]\nversion = "{version}"\n', encoding="utf-8")
    shutil.copyfile(ROOT / CONSTRAINTS, root / CONSTRAINTS)
    shutil.copyfile(DOCKERFILE, root / "deploy/http/Dockerfile")
    shutil.copyfile(DOCKERIGNORE, root / "deploy/http/Dockerfile.dockerignore")
    return root


@pytest.mark.parametrize(
    ("version", "non_release", "commit", "message"),
    [
        ("1.2.3+g0123456789ab", False, "0123456789ab" + "0" * 28, "stage it with --non-release"),
        ("1.2.3+g0123456789ab", True, "f" * 40, "does not name source commit"),
        ("1.2.3+local", True, "0" * 40, "not a non-release"),
        ("1.2.3", True, "0" * 40, "not a non-release"),
    ],
)
def test_stage_rejects_a_label_that_does_not_match_the_build_kind(
    tmp_path, version, non_release, commit, message
):
    root = labelled_tree(tmp_path, version)
    wheel = synthetic_wheel(tmp_path, version)
    with pytest.raises(StageError, match=message):
        stage(root, wheel, tmp_path / "out", commit, "clean", non_release=non_release)
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(
    "argv",
    [["--dirty"], ["--non-release", "--wheel", "dist/x.whl"]],
)
def test_stage_cli_rejects_contradictory_options(argv, capsys):
    with pytest.raises(SystemExit) as exited:
        stage_release.main(argv)
    assert exited.value.code == 2
    assert capsys.readouterr().out == ""


POSIX_SHELL = pytest.mark.skipif(
    os.name == "nt" or shutil.which("sh") is None or shutil.which("sha256sum") is None,
    reason="runs the image's POSIX checksum step; needs sh and sha256sum",
)


def run_checksum_step(work: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", "-c", " && ".join(image_checksum_commands())],
        cwd=work,
        capture_output=True,
        text=True,
        timeout=30,
    )


@POSIX_SHELL
@pytest.mark.parametrize("extra_wheel", [False, True])
def test_image_checksum_step_accepts_exactly_one_non_release_wheel(
    source_repo, tmp_path, extra_wheel
):
    target = stage_non_release(source_repo, tmp_path / "out", build=FakeBuilder())
    work = tmp_path / "wled-mcp-release"
    work.mkdir()
    wheel = next(target.glob("wled_mcp-*.whl")).name
    for name in (wheel, CONSTRAINTS, "SHA256SUMS"):
        shutil.copyfile(target / name, work / name)
    if extra_wheel:  # a second wheel in the context is rejected even if unlisted
        synthetic_wheel(work, "1.2.2")
    result = run_checksum_step(work)
    assert (result.returncode == 0) is (not extra_wheel), result.stdout + result.stderr


@pytest.mark.skipif(shutil.which("uv") is None, reason="needs uv for the offline wheel build")
def test_non_release_build_of_the_checkout_produces_matching_wheel_metadata(tmp_path):
    """Real ``git archive`` export and offline hatchling build of the checked-out commit."""
    commit = git(ROOT, "rev-parse", "HEAD")
    base = git(ROOT, "show", "HEAD:pyproject.toml")
    base_version = tomllib.loads(base)["project"]["version"]
    built: list[Path] = []

    def build(source: Path, out_dir: Path) -> Path:
        built.append(uv_build(source, out_dir))
        return built[-1]

    builder: Callable[[Path, Path], Path] = build
    target = stage_non_release(ROOT, tmp_path / "out", build=builder)
    version = f"{base_version}+g{commit[:12]}"
    assert target.name == version and built[0].name == f"wled_mcp-{version}-py3-none-any.whl"
    with zipfile.ZipFile(target / built[0].name) as archive:
        metadata = archive.read(f"wled_mcp-{version}.dist-info/METADATA").decode()
        assert "wled_mcp/cli.py" in archive.namelist()
    assert f"Version: {version}\n" in metadata
    assert release_record(target)["image_tag"] == f"wled-mcp:{base_version}-g{commit[:12]}"
