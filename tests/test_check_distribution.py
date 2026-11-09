"""Issue #22 (AC-22P-06 to AC-22P-08): the release guard and file checks of the publish workflow.

``scripts/check_distribution.py --release-ref`` refuses every ref other than the tag
``v<project.version>`` on a commit reachable from ``main``; ``--wheel``/``--sdist`` check
already built files without building again. Synthetic versions, temporary Git
repositories and synthetic archives only; nothing is built or installed here.
"""

from __future__ import annotations

import io
import subprocess
import tarfile
from pathlib import Path

import pytest

from tests.test_tool_contract import load_script

script = load_script("check_distribution")
SDIST, WHEEL = "wled_mcp-1.2.3.tar.gz", "wled_mcp-1.2.3-py3-none-any.whl"


def test_release_names_follow_the_version():
    assert script.release_names("1.2.3") == (SDIST, WHEEL)


def test_release_ref_matching_the_version_passes():
    assert script.release_ref_problems("tag", "v1.2.3", "1.2.3") == []
    assert script.release_ref_problems("tag", "v1.2.3rc1", "1.2.3rc1") == []


@pytest.mark.parametrize(
    ("ref_type", "ref_name", "version", "expected"),
    [
        ("tag", "v1.2.4", "1.2.3", ["ref 'v1.2.4' is not the tag 'v1.2.3' of project.version"]),
        ("tag", "1.2.3", "1.2.3", ["ref '1.2.3' is not the tag 'v1.2.3' of project.version"]),
        (
            "branch",
            "main",
            "1.2.3",
            [
                "the workflow ref type is 'branch', not 'tag'",
                "ref 'main' is not the tag 'v1.2.3' of project.version",
            ],
        ),
        ("branch", "v1.2.3", "1.2.3", ["the workflow ref type is 'branch', not 'tag'"]),
        ("", "", "1.2.3", ["the workflow ref type is '', not 'tag'", "ref '' is not"]),
        (
            "tag",
            "v1.2.3+g0123456789ab",
            "1.2.3+g0123456789ab",
            ["project.version '1.2.3+g0123456789ab' is not a release version"],
        ),
        ("tag", "v1.2.3.dev1", "1.2.3.dev1", ["is not a release version"]),
    ],
    ids=[
        "other-tag",
        "tag-without-v",
        "dispatch-on-branch",
        "branch-named-like-tag",
        "no-ref",
        "local-label",
        "dev-release",
    ],
)
def test_release_ref_mismatches_are_refused(ref_type, ref_name, version, expected):
    problems = script.release_ref_problems(ref_type, ref_name, version)
    assert len(problems) == len(expected), problems
    for problem, fragment in zip(problems, expected, strict=True):
        assert fragment in problem


@pytest.mark.parametrize(
    ("names", "expected"),
    [
        ([SDIST, WHEEL], []),
        ([WHEEL], [f"missing {SDIST}"]),
        ([SDIST], [f"missing {WHEEL}"]),
        ([SDIST, WHEEL, "SHA256SUMS"], ["unexpected file SHA256SUMS"]),
        ([SDIST, WHEEL, ".gitignore"], ["unexpected file .gitignore"]),
        (
            ["wled_mcp-1.2.2.tar.gz", WHEEL],
            [f"missing {SDIST}", "unexpected file wled_mcp-1.2.2.tar.gz"],
        ),
    ],
    ids=["exact", "no-sdist", "no-wheel", "checksum-file", "hidden-file", "other-version"],
)
def test_upload_directory_holds_exactly_the_two_files(names, expected):
    assert script.release_directory_problems(names, "1.2.3") == expected


def test_metadata_version_reads_the_header_only():
    text = "Metadata-Version: 2.4\nName: wled-mcp\nVersion: 1.2.3\n\nVersion: 9.9.9\n"
    assert script.metadata_version(text) == "1.2.3"
    assert script.metadata_version("Name: wled-mcp\n\nVersion: 1.2.3\n") is None


@pytest.mark.parametrize(
    ("member", "reason"),
    [
        ("wled_mcp-1.2.3/.git", "Git data"),
        ("wled_mcp-1.2.3/.git/config", "Git data"),
        ("wled_mcp-1.2.3/.agent-runs/issue-1/packet.md", "local run or build output"),
        ("wled_mcp-1.2.3/.artifacts/pytest-temp/x", "local run or build output"),
        ("wled_mcp-1.2.3/.env", "environment file"),
        ("wled_mcp-1.2.3/deploy/.env.local", "environment file"),
        ("wled_mcp-1.2.3/data/devices.toml", "device inventory"),
        ("other-1.2.3/README.md", "outside wled_mcp-1.2.3/"),
    ],
)
def test_sdist_members_that_must_not_be_published(member, reason):
    allowed = ["wled_mcp-1.2.3/PKG-INFO", "wled_mcp-1.2.3/src/wled_mcp/cli.py"]
    assert script.sdist_member_problems(allowed, "1.2.3") == []
    assert script.sdist_member_problems([*allowed, member], "1.2.3") == [f"{member}: {reason}"]


def synthetic_sdist(directory: Path, version: str, pkg_version: str, extra: str = "") -> Path:
    path = directory / f"wled_mcp-{version}.tar.gz"
    members = {
        f"wled_mcp-{version}/PKG-INFO": f"Metadata-Version: 2.4\nVersion: {pkg_version}\n",
        f"wled_mcp-{version}/src/wled_mcp/__init__.py": "",
    }
    if extra:
        members[f"wled_mcp-{version}/{extra}"] = "synthetic"
    with tarfile.open(path, "w:gz") as archive:
        for name, text in members.items():
            data = text.encode("utf-8")
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return path


def test_check_sdist_accepts_a_matching_archive(tmp_path):
    script.check_sdist(synthetic_sdist(tmp_path, "1.2.3", "1.2.3"), "1.2.3")


@pytest.mark.parametrize(
    ("pkg_version", "extra", "message"),
    [
        ("1.2.4", "", "PKG-INFO Version is not 1.2.3"),
        ("1.2.3", ".git", "Git data"),
        ("1.2.3", "devices.toml", "device inventory"),
    ],
)
def test_check_sdist_refuses_a_wrong_version_or_private_files(
    tmp_path, pkg_version, extra, message
):
    with pytest.raises(SystemExit, match=message):
        script.check_sdist(synthetic_sdist(tmp_path, "1.2.3", pkg_version, extra), "1.2.3")


def test_check_sdist_refuses_another_file_name(tmp_path):
    path = synthetic_sdist(tmp_path, "1.2.3", "1.2.3")
    with pytest.raises(SystemExit, match="not the source distribution of 1.2.4"):
        script.check_sdist(path, "1.2.4")


# ------------------------------------------------------- tag commit reachable from main


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        [
            "git",
            "-c",
            "user.name=synthetic",
            "-c",
            "user.email=synthetic@invalid",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "tag.gpgsign=false",
            *args,
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return result.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """main with two commits, mirrored as origin/main, and a side commit off main."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "commit", "-q", "--allow-empty", "-m", "first")
    git(repo, "commit", "-q", "--allow-empty", "-m", "second")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(repo, "switch", "-q", "-c", "side")
    git(repo, "commit", "-q", "--allow-empty", "-m", "side")
    git(repo, "switch", "-q", "main")
    return repo


def test_annotated_tag_on_main_passes(repo):
    git(repo, "tag", "-a", "-m", "release", "v1.2.3", "main~1")
    git(repo, "checkout", "-q", "--detach", "v1.2.3")
    head = git(repo, "rev-parse", "HEAD")
    assert script.tag_commit_problems(repo, "v1.2.3", head) == []
    assert script.tag_commit_problems(repo, "v1.2.3", None) == []


def test_tag_off_main_is_refused(repo):
    git(repo, "tag", "v1.2.3", "side")
    git(repo, "checkout", "-q", "--detach", "v1.2.3")
    assert script.tag_commit_problems(repo, "v1.2.3", None) == [
        "the tagged commit is not reachable from main"
    ]


def test_checkout_other_than_the_tag_or_workflow_commit_is_refused(repo):
    git(repo, "tag", "v1.2.3", "main~1")
    git(repo, "checkout", "-q", "--detach", "main")
    workflow_commit = git(repo, "rev-parse", "main~1")
    assert script.tag_commit_problems(repo, "v1.2.3", workflow_commit) == [
        "tag 'v1.2.3' does not point at the checked-out commit",
        "the checked-out commit is not the workflow commit",
    ]
    assert script.tag_commit_problems(repo, "v9.9.9", None) == [
        "tag 'v9.9.9' does not point at the checked-out commit"
    ]


def test_missing_main_history_is_refused(repo):
    git(repo, "tag", "v1.2.3", "main")
    git(repo, "update-ref", "-d", "refs/remotes/origin/main")
    git(repo, "checkout", "-q", "--detach", "v1.2.3")
    problems = script.tag_commit_problems(repo, "v1.2.3", None)
    assert problems == [f"{script.MAIN_REF} is missing; fetch the full history of main"]


def test_release_guard_reads_the_runner_environment(repo, capsys):
    version = script.VERSION
    git(repo, "tag", f"v{version}", "main")
    git(repo, "checkout", "-q", "--detach", f"v{version}")
    head = git(repo, "rev-parse", "HEAD")
    environ = {"GITHUB_REF_TYPE": "tag", "GITHUB_REF_NAME": f"v{version}", "GITHUB_SHA": head}
    script.check_release_ref(repo, environ)
    assert "Release guard: PASS" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="not 'tag'"):
        script.check_release_ref(repo, {**environ, "GITHUB_REF_TYPE": "branch"})
    with pytest.raises(SystemExit, match="not the workflow commit"):
        script.check_release_ref(repo, {**environ, "GITHUB_SHA": "0" * 40})


# ------------------------------------------------------------- options and no rebuild


class Stop(Exception):
    pass


def test_release_ref_mode_builds_nothing(monkeypatch, tmp_path):
    seen: list[tuple[Path, dict[str, str]]] = []
    monkeypatch.setattr(script, "check_release_ref", lambda root, env: seen.append((root, env)))
    monkeypatch.setattr(script, "run", lambda *a: pytest.fail(f"unexpected command {a[0]}"))
    script.main(["--release-ref"])
    assert len(seen) == 1 and seen[0][0] == script.ROOT


def stop_at_first_step(monkeypatch) -> tuple[list[list[str]], list[Path]]:
    """Record the first command or wheel inspection of ``main`` and stop there."""
    commands: list[list[str]] = []
    opened: list[Path] = []

    def command(argv: list[str], cwd: Path, env: dict[str, str]) -> str:
        commands.append(argv)
        raise Stop

    def inspect(path: Path) -> None:
        opened.append(path)
        raise Stop

    monkeypatch.setattr(script, "run", command)
    monkeypatch.setattr(script.zipfile, "ZipFile", inspect)
    return commands, opened


def test_given_wheel_is_inspected_without_building(monkeypatch):
    commands, opened = stop_at_first_step(monkeypatch)
    wheel = Path("dist") / script.release_names(script.VERSION)[1]
    with pytest.raises(Stop):
        script.main(["--wheel", str(wheel)])
    assert commands == [] and opened == [wheel.resolve()]


def test_without_options_the_wheel_is_built_first(monkeypatch):
    commands, opened = stop_at_first_step(monkeypatch)
    with pytest.raises(Stop):
        script.main([])
    assert opened == [] and commands[0][:2] == ["uv", "build"] and "--wheel" in commands[0]


def test_given_wheel_with_another_name_is_refused_before_any_command(monkeypatch):
    monkeypatch.setattr(script, "run", lambda *a: pytest.fail(f"unexpected command {a[0]}"))
    with pytest.raises(SystemExit, match="is not the wheel of"):
        script.main(["--wheel", "dist/wled_mcp-0.0.0-py3-none-any.whl"])


@pytest.mark.parametrize(
    "argv",
    [["--release-ref", "--wheel", "x.whl"], ["--sdist", "x.tar.gz"]],
)
def test_contradictory_options_are_refused(argv, capsys):
    with pytest.raises(SystemExit) as exited:
        script.parse_args(argv)
    assert exited.value.code == 2
    assert capsys.readouterr().out == ""


def test_no_option_keeps_the_building_check():
    options = script.parse_args([])
    assert not options.release_ref and options.wheel is None and options.sdist is None


# ------------------------------------------- AC-22R-03: Requires-Dist equals the declaration

DECLARED = ["mcp>=2.3.0,<3", "pydantic>=2.12.0,<3", "anyio>=4.10,<5"]


def synthetic_metadata(*requires: str) -> str:
    lines = ["Metadata-Version: 2.4", "Name: wled-mcp", "Version: 1.2.3"]
    lines += [f"Requires-Dist: {text}" for text in requires]
    # A body line that looks like a header must not count (it is the README).
    return "\n".join(lines) + "\n\nRequires-Dist: not-a-header==1\n"


def test_requires_dist_matching_the_declaration_passes_in_any_specifier_order():
    # Hatchling writes `mcp<3,>=2.3.0`; the comparison is on parsed requirements.
    metadata = synthetic_metadata("anyio<5,>=4.10", "MCP<3,>=2.3.0", "pydantic<3,>=2.12.0")
    assert script.requires_dist_problems(metadata, DECLARED) == []


def test_requires_dist_of_the_project_is_read_from_pyproject():
    names = [text.split(">", 1)[0].split("<", 1)[0] for text in script.project_dependencies()]
    assert "anyio" in names and "mcp" in names


@pytest.mark.parametrize(
    ("requires", "expected"),
    [
        (
            ("mcp<3,>=2.3.0", "pydantic<3,>=2.12.0"),
            ["Requires-Dist lacks 'anyio>=4.10,<5'"],
        ),
        (
            ("mcp<3,>=2.3.0", "pydantic<3,>=2.12.0", "anyio<5,>=4.10", "uvicorn==0.54.0"),
            [
                "Requires-Dist 'uvicorn==0.54.0' is an exact pin",
                "Requires-Dist has undeclared 'uvicorn==0.54.0'",
            ],
        ),
        (
            ("mcp==2.3.0", "pydantic<3,>=2.12.0", "anyio<5,>=4.10"),
            [
                "Requires-Dist 'mcp==2.3.0' is an exact pin",
                "Requires-Dist lacks 'mcp>=2.3.0,<3'",
                "Requires-Dist has undeclared 'mcp==2.3.0'",
            ],
        ),
        (
            ("mcp<4,>=2.3.0", "pydantic<3,>=2.12.0", "anyio<5,>=4.10"),
            ["Requires-Dist lacks 'mcp>=2.3.0,<3'", "Requires-Dist has undeclared 'mcp<4,>=2.3.0'"],
        ),
    ],
    ids=["missing-entry", "extra-exact-pin", "exact-pin-instead-of-range", "other-range"],
)
def test_requires_dist_check_rejects_drift_and_exact_pins(requires, expected):
    assert script.requires_dist_problems(synthetic_metadata(*requires), DECLARED) == expected
