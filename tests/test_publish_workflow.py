"""Issue #22 (AC-22P-01 to AC-22P-10): the PyPI publish workflow keeps its safety properties.

``publish_workflow_problems`` reads ``.github/workflows/publish.yml`` and names every way it
could publish from the wrong ref, with wider permissions or credentials, or files other
than the tested ones. The real file has no problem; each synthetic mutation is found.
The checksum hand-over between the jobs is executed with a POSIX shell where available.
Nothing here runs the workflow or contacts an index.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "publish.yml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

GUARD = "scripts/check_distribution.py --release-ref"
PUBLISH_ACTION = "pypa/gh-action-pypi-publish"
CREDENTIAL_INPUTS = {"password", "user", "repository-url", "repository_url"}
FORBIDDEN_TRIGGERS = {"push", "pull_request", "pull_request_target", "schedule", "workflow_run"}
# `uses: owner/repo@<40 hex> # vX.Y.Z` on one line (AC-22P-05).
PINNED = re.compile(r"uses: [\w.-]+/[\w./-]+@[0-9a-f]{40} # v\d+\.\d+\.\d+$")
TWINE = re.compile(r"uvx --from twine==(\S+) twine check --strict dist/\*")


def uv_version(workflow: dict[str, Any]) -> str | None:
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            if str(step.get("uses", "")).startswith("astral-sh/setup-uv@"):
                return str(step.get("with", {}).get("version"))
    return None


def step_index(steps: list[dict[str, Any]], fragment: str) -> int | None:
    for index, step in enumerate(steps):
        if fragment in str(step.get("run", "")) or fragment in str(step.get("uses", "")):
            return index
    return None


def trigger_problems(workflow: dict[str, Any]) -> list[str]:
    triggers = workflow.get("on", workflow.get(True)) or {}
    if isinstance(triggers, str):
        triggers = {triggers: None}
    elif isinstance(triggers, list):
        triggers = dict.fromkeys(triggers)
    problems = [f"forbidden trigger {name}" for name in sorted(FORBIDDEN_TRIGGERS & set(triggers))]
    release = triggers.get("release") or {}
    if set(triggers) != {"release", "workflow_dispatch"} or release.get("types") != ["published"]:
        problems.append("triggers are not exactly a published release and workflow_dispatch")
    return problems


def permission_problems(workflow: dict[str, Any], text: str) -> list[str]:
    problems = []
    if workflow.get("permissions") != {}:
        problems.append("top-level permissions are not empty")
    jobs = workflow["jobs"]
    if jobs.get("build", {}).get("permissions") != {"contents": "read"}:
        problems.append("build job permissions are not exactly contents: read")
    if jobs.get("publish", {}).get("permissions") != {"id-token": "write"}:
        problems.append("publish job permissions are not exactly id-token: write")
    if "write-all" in text or "read-all" in text:
        problems.append("blanket write-all or read-all permissions")
    return problems


def publish_job_problems(job: dict[str, Any]) -> list[str]:
    problems = []
    environment = job.get("environment")
    if isinstance(environment, dict):
        environment = environment.get("name")
    if environment != "pypi":
        problems.append("publish job does not run in the pypi environment")
    needs = job.get("needs")
    if needs != "build" and needs != ["build"]:
        problems.append("publish job does not need the build job")
    steps = job.get("steps", [])
    uses = [str(step["uses"]).split("@")[0] for step in steps if "uses" in step]
    if "actions/checkout" in uses:
        problems.append("publish job checks out the repository")
    if any(name not in ("actions/download-artifact", PUBLISH_ACTION) for name in uses):
        problems.append("publish job uses an action other than download and publish")
    for step in steps:
        run = str(step.get("run", ""))
        if re.search(r"\b(uv|uvx|pip|python|twine|hatch)\b", run) or "build" in run:
            problems.append("publish job builds or installs")
    if not uses or uses[-1] != PUBLISH_ACTION or uses.count(PUBLISH_ACTION) != 1:
        problems.append("publish job does not end with exactly one publish action")
    if step_index(steps, "sha256sum --strict --check") is None:
        problems.append("publish job does not re-check the downloaded checksums")
    for step in steps:
        if str(step.get("uses", "")).startswith(PUBLISH_ACTION):
            inputs = set(step.get("with") or {})
            if inputs & CREDENTIAL_INPUTS:
                problems.append("publish action gets credentials or another index")
            skip = (step.get("with") or {}).get("skip-existing", False)
            if str(skip).lower() == "true":
                problems.append("publish action skips existing files")
    return problems


def build_job_problems(job: dict[str, Any], ci_uv: str | None) -> list[str]:
    problems = []
    steps = job.get("steps", [])
    runs = [str(step.get("run", "")) for step in steps]
    builds = [index for index, run in enumerate(runs) if "uv build" in run]
    if len(builds) != 1 or "--no-build-isolation" not in runs[builds[0]]:
        return [*problems, "not exactly one uv build --no-build-isolation"]
    build = builds[0]
    guard = step_index(steps, GUARD)
    # Installing the project runs its build backend, so the guard comes before it too.
    installs_project = [
        index
        for index, run in enumerate(runs)
        if "uv sync" in run and "--no-install-project" not in run
    ]
    if guard is None or guard > build or any(index < guard for index in installs_project):
        problems.append("release guard does not run before the build")
    locked = [index for index in installs_project if "uv sync --locked" in runs[index]]
    if not locked or min(locked) > build:
        problems.append("build does not follow uv sync --locked")
    twine = [TWINE.search(run) for run in runs]
    versions = [match.group(1) for match in twine if match]
    if len(versions) != 1 or Version(versions[0]) < Version("6.1.0"):
        problems.append("no strict twine check with an exact twine >= 6.1.0")
    smoke = [
        index
        for index, run in enumerate(runs)
        if "check_distribution.py" in run and "--release-ref" not in run
    ]
    if not smoke or not all("--wheel" in runs[index] for index in smoke):
        problems.append("smoke test does not check the built wheel")
    elif min(smoke) < build:
        problems.append("smoke test runs before the build")
    upload = step_index(steps, "actions/upload-artifact@")
    if upload is None or (guard is not None and upload < guard) or upload < build:
        problems.append("upload is not after the guard and the build")
    if step_index(steps, "sha256sum --strict --check") is None:
        problems.append("build job does not confirm the tested checksums")
    for step in steps:
        uses = str(step.get("uses", ""))
        settings = step.get("with") or {}
        if (
            uses.startswith("actions/checkout@")
            and settings.get("persist-credentials") is not False
        ):
            problems.append("checkout keeps credentials")
        if uses.startswith("astral-sh/setup-uv@"):
            if settings.get("enable-cache") is not False:
                problems.append("setup-uv cache is enabled")
            if str(settings.get("version")) != ci_uv:
                problems.append("uv version differs from ci.yml")
    if (job.get("env") or {}).get("UV_PYTHON_DOWNLOADS") != "never":
        problems.append("Python downloads are not disabled")
    return problems


def artifact_problems(workflow: dict[str, Any]) -> list[str]:
    def settings(job: str, action: str) -> dict[str, Any]:
        for step in workflow["jobs"].get(job, {}).get("steps", []):
            if str(step.get("uses", "")).startswith(action):
                return dict(step.get("with") or {})
        return {}

    upload = settings("build", "actions/upload-artifact@")
    download = settings("publish", "actions/download-artifact@")
    problems = []
    if not upload.get("name") or upload.get("name") != download.get("name"):
        problems.append("artifact names differ between upload and download")
    if upload.get("if-no-files-found") != "error":
        problems.append("upload does not fail without files")
    if download.get("path") != (settings("publish", PUBLISH_ACTION).get("packages-dir", "dist")):
        problems.append("publish action does not upload the downloaded directory")
    return problems


def publish_workflow_problems(text: str, ci_text: str | None = None) -> list[str]:
    """Every way the publish workflow departs from AC-22P-01 to AC-22P-10."""
    workflow = yaml.safe_load(text)
    ci = yaml.safe_load(ci_text if ci_text is not None else CI_WORKFLOW.read_text("utf-8"))
    problems = trigger_problems(workflow) + permission_problems(workflow, text)
    jobs = workflow.get("jobs", {})
    if set(jobs) != {"build", "publish"}:
        return [*problems, "jobs are not exactly build and publish"]
    problems += build_job_problems(jobs["build"], uv_version(ci))
    problems += publish_job_problems(jobs["publish"])
    problems += artifact_problems(workflow)
    if "secrets." in text:
        problems.append("workflow references secrets")
    if "actions/cache" in text:
        problems.append("workflow uses a cache action")
    for job in jobs.values():
        if job.get("permissions", {}).get("id-token") and job is not jobs["publish"]:
            problems.append("id-token outside the publish job")
        if not isinstance(job.get("timeout-minutes"), int):
            problems.append("job without timeout-minutes")
        for step in job.get("steps", []):
            if "${{" in str(step.get("run", "")):
                problems.append("a run script interpolates an expression")
    concurrency = workflow.get("concurrency") or {}
    if "github.ref" not in str(concurrency.get("group")):
        problems.append("concurrency group is not per ref")
    if concurrency.get("cancel-in-progress") is not False:
        problems.append("a running publish can be cancelled")
    for number, line in enumerate(text.splitlines(), 1):
        if "uses:" in line and not PINNED.search(line.strip()):
            problems.append(f"line {number}: action not pinned to a commit SHA with # vX.Y.Z")
    return problems


def test_publish_workflow_has_no_problem():
    assert publish_workflow_problems(WORKFLOW.read_text("utf-8")) == []


def test_publish_workflow_uses_the_ci_uv_version():
    ci = yaml.safe_load(CI_WORKFLOW.read_text("utf-8"))
    publish = yaml.safe_load(WORKFLOW.read_text("utf-8"))
    assert uv_version(ci) is not None and uv_version(publish) == uv_version(ci)


PUBLISH_PIN = "pypa/gh-action-pypi-publish@7245906fb61fa33a13554f9d5fb856fe61758086 # v1.14.3"
CHECKOUT_PIN = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1"


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ("  workflow_dispatch:\n", "  workflow_dispatch:\n  push:\n", "forbidden trigger push"),
        (
            "  workflow_dispatch:\n",
            "  workflow_dispatch:\n  pull_request_target:\n",
            "forbidden trigger pull_request_target",
        ),
        ("types: [published]", "types: [created]", "triggers are not exactly"),
        ("permissions: {}\n", "permissions: write-all\n", "top-level permissions"),
        (
            "      contents: read\n",
            "      contents: read\n      id-token: write\n",
            "build job permissions are not exactly",
        ),
        ("      contents: read\n", "      contents: write\n", "build job permissions"),
        (
            "      id-token: write\n",
            "      id-token: write\n      contents: read\n",
            "publish job permissions are not exactly",
        ),
        (
            "    environment:\n      name: pypi\n      url: https://pypi.org/project/wled-mcp/\n",
            "",
            "does not run in the pypi environment",
        ),
        (
            "    environment:\n      name: pypi\n",
            "    environment:\n      name: testpypi\n",
            "pypi",
        ),
        ("    needs: build\n", "", "does not need the build job"),
        (
            "          packages-dir: dist/\n",
            "          packages-dir: dist/\n          password: ${{ secrets.PYPI_API_TOKEN }}\n",
            "publish action gets credentials",
        ),
        (
            "          packages-dir: dist/\n",
            "          packages-dir: dist/\n          password: placeholder\n",
            "publish action gets credentials",
        ),
        (
            "          packages-dir: dist/\n",
            "          packages-dir: dist/\n          repository-url: https://test.pypi.org/legacy/\n",
            "another index",
        ),
        (
            "          packages-dir: dist/\n",
            "          packages-dir: dist/\n          skip-existing: true\n",
            "skips existing files",
        ),
        (
            "      UV_PYTHON_DOWNLOADS: never\n",
            "      UV_PYTHON_DOWNLOADS: never\n      TOKEN: ${{ secrets.TOKEN }}\n",
            "workflow references secrets",
        ),
        (PUBLISH_PIN, "pypa/gh-action-pypi-publish@v1.14.3", "action not pinned"),
        (PUBLISH_PIN, PUBLISH_PIN.split(" #")[0], "action not pinned"),
        (CHECKOUT_PIN, "actions/checkout@3d3c42e5", "action not pinned"),
        ("          persist-credentials: false\n", "", "checkout keeps credentials"),
        (
            '--wheel "dist/wled_mcp-${version}-py3-none-any.whl" ',
            "",
            "smoke test does not check the built wheel",
        ),
        (
            "name: python-distribution\n          path: dist/\n          if-no",
            "name: other\n          path: dist/\n          if-no",
            "artifact names differ",
        ),
        ("          if-no-files-found: error\n", "", "upload does not fail without files"),
        (
            "    steps:\n      - uses: actions/download-artifact@",
            f"    steps:\n      - uses: {CHECKOUT_PIN}\n        with:\n"
            "          persist-credentials: false\n      - uses: actions/download-artifact@",
            "publish job checks out the repository",
        ),
        (
            "          cd dist\n          sha256sum --strict",
            "          cd dist\n          uv build\n          sha256sum --strict",
            "publish job builds or installs",
        ),
        ("twine==7.0.0", "twine==6.0.1", "exact twine >= 6.1.0"),
        ("twine check --strict", "twine check", "exact twine >= 6.1.0"),
        ("          enable-cache: false\n", "", "setup-uv cache is enabled"),
        ('          version: "0.11.14"\n', '          version: "0.11.13"\n', "uv version differs"),
        ("      UV_PYTHON_DOWNLOADS: never\n", "", "Python downloads are not disabled"),
        ("  cancel-in-progress: false\n", "  cancel-in-progress: true\n", "can be cancelled"),
        ("    timeout-minutes: 15\n", "", "job without timeout-minutes"),
        (
            "        run: uv sync --locked --no-install-project\n",
            "        run: uv sync --locked\n",
            "release guard does not run before the build",
        ),
        (
            '          version="${GITHUB_REF_NAME#v}"\n',
            "          version=${{ github.ref_name }}\n",
            "interpolates an expression",
        ),
    ],
)
def test_publish_workflow_check_rejects_regressions(old, new, expected):
    text = WORKFLOW.read_text("utf-8")
    assert old in text, old
    problems = publish_workflow_problems(text.replace(old, new, 1))
    assert any(expected in problem for problem in problems), problems


def move_step(text: str, start: str, end: str, before: str) -> str:
    """Cut the step text from ``start`` up to ``end`` and insert it before ``before``."""
    first = text.index(start)
    block = text[first : text.index(end, first)]
    rest = text.replace(block, "", 1)
    return rest.replace(before, block + before, 1)


def test_publish_workflow_check_rejects_a_guard_after_the_build():
    text = WORKFLOW.read_text("utf-8")
    moved = move_step(
        text,
        "      - name: Release guard\n",
        "      - run: uv sync --locked\n",
        "      - name: Record the checksums",
    )
    assert moved != text
    assert "release guard does not run before the build" in publish_workflow_problems(moved)


def test_publish_workflow_check_rejects_a_guard_after_the_upload():
    text = WORKFLOW.read_text("utf-8")
    moved = move_step(
        text,
        "      - name: Release guard\n",
        "      - run: uv sync --locked\n",
        "  publish:\n",
    )
    assert "release guard does not run before the build" in publish_workflow_problems(moved)


def test_publish_workflow_check_rejects_a_second_build():
    text = WORKFLOW.read_text("utf-8")
    old = "      - name: Check the package metadata\n"
    doubled = text.replace(old, "      - run: uv build --wheel --no-build-isolation\n" + old)
    assert "not exactly one uv build --no-build-isolation" in publish_workflow_problems(doubled)


# --------------------------------------------- checksum hand-over between the two jobs


def step_script(job: str, name: str) -> str:
    workflow = yaml.safe_load(WORKFLOW.read_text("utf-8"))
    (step,) = [s for s in workflow["jobs"][job]["steps"] if s.get("name") == name]
    return str(step["run"])


def gnu_tools() -> bool:
    if shutil.which("bash") is None or shutil.which("sha256sum") is None:
        return False
    probe = subprocess.run(
        ["find", ".", "-maxdepth", "0", "-printf", "%P"], capture_output=True, timeout=30
    )
    return probe.returncode == 0


GNU_SHELL = pytest.mark.skipif(not gnu_tools(), reason="needs bash, sha256sum and GNU find")


def run_script(script: str, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-e", "-c", script],
        cwd=cwd,
        env={"PATH": "/usr/bin:/bin", **env},
        capture_output=True,
        text=True,
        timeout=60,
    )


def built_dist(workspace: Path) -> Path:
    dist = workspace / "dist"
    dist.mkdir(parents=True)
    (dist / "wled_mcp-1.2.3.tar.gz").write_bytes(b"synthetic sdist")
    (dist / "wled_mcp-1.2.3-py3-none-any.whl").write_bytes(b"synthetic wheel")
    return dist


@GNU_SHELL
@pytest.mark.parametrize("tamper", [None, "modified", "extra", "missing"])
def test_publish_job_accepts_only_the_tested_files(tmp_path, tamper):
    build_temp, publish_temp = tmp_path / "build-temp", tmp_path / "publish-temp"
    build_temp.mkdir()
    publish_temp.mkdir()
    built = built_dist(tmp_path / "build")
    record = run_script(
        step_script("build", "Record the checksums of the built files"),
        built.parent,
        {"RUNNER_TEMP": str(build_temp)},
    )
    assert record.returncode == 0, record.stderr
    sums = (build_temp / "SHA256SUMS").read_text("utf-8")
    downloaded = tmp_path / "publish" / "dist"
    shutil.copytree(built, downloaded)
    if tamper == "modified":
        (downloaded / "wled_mcp-1.2.3-py3-none-any.whl").write_bytes(b"other wheel")
    elif tamper == "extra":
        (downloaded / "SHA256SUMS").write_text(sums, encoding="utf-8")
    elif tamper == "missing":
        (downloaded / "wled_mcp-1.2.3.tar.gz").unlink()
    verify = run_script(
        step_script("publish", "Verify the downloaded files against the tested checksums"),
        downloaded.parent,
        {"RUNNER_TEMP": str(publish_temp), "SHA256SUMS": sums.rstrip("\n")},
    )
    assert (verify.returncode == 0) is (tamper is None), verify.stdout + verify.stderr


@GNU_SHELL
def test_build_job_refuses_a_third_file_in_dist(tmp_path):
    temp = tmp_path / "temp"
    temp.mkdir()
    built = built_dist(tmp_path / "build")
    (built / "extra.whl").write_bytes(b"x")
    record = run_script(
        step_script("build", "Record the checksums of the built files"),
        built.parent,
        {"RUNNER_TEMP": str(temp)},
    )
    assert record.returncode != 0
