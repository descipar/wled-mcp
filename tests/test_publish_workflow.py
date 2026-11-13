"""Issues #22 (AC-22P-01 to AC-22P-10) and #151 (D151-09, D151-10): the publish workflow.

The PyPI publish workflow keeps its safety properties, and the MCPB bundle jobs added by #151
(``build-mcpb``, ``release-asset``) stay isolated from it.

``publish_workflow_problems`` reads ``.github/workflows/publish.yml`` and names every way it
could publish from the wrong ref, with wider permissions or credentials, or files other
than the tested ones. The real file has no problem; each synthetic mutation is found.
The checksum hand-over between the jobs is executed with a POSIX shell where available.
Nothing here runs the workflow or contacts an index.
"""

from __future__ import annotations

import json
import re
import shlex
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
    if jobs.get("build-mcpb", {}).get("permissions") != {"contents": "read"}:
        problems.append("build-mcpb job permissions are not exactly contents: read")
    if jobs.get("release-asset", {}).get("permissions") != {"contents": "write"}:
        problems.append("release-asset job permissions are not exactly contents: write")
    for name, job in jobs.items():
        if name != "release-asset" and "write" in str(
            (job.get("permissions") or {}).get("contents")
        ):
            problems.append(f"contents: write outside release-asset (job {name})")
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


def setup_problems(job: dict[str, Any], ci_uv: str | None) -> list[str]:
    """Checkout, uv and Python settings shared by the two jobs that build something."""
    problems = []
    for step in job.get("steps", []):
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
    return [*problems, *setup_problems(job, ci_uv)]


def bundle_steps_in(job: dict[str, Any]) -> bool:
    return "mcpb" in json.dumps(job).lower()


def bundle_job_problems(job: dict[str, Any], ci_uv: str | None) -> list[str]:
    """``build-mcpb`` (D151-09): its own read-only job; the PyPI jobs do not need it."""
    problems = [f"build-mcpb: {problem}" for problem in setup_problems(job, ci_uv)]
    steps = job.get("steps", [])
    runs = [str(step.get("run", "")) for step in steps]
    if "needs" in job or "environment" in job or "if" in job:
        problems.append("build-mcpb: has needs, an environment or a condition")
    builds = [index for index, run in enumerate(runs) if "deploy/build_mcpb.py" in run]
    if len(builds) != 1:
        return [*problems, "build-mcpb: not exactly one step running deploy/build_mcpb.py"]
    build = builds[0]
    run = runs[build]
    if '--version "${GITHUB_REF_NAME#v}"' not in run or "--output mcpb-dist" not in run:
        problems.append("build-mcpb: the bundle is not built for the tag into mcpb-dist")
    guard = step_index(steps, GUARD)
    installs_project = [
        index
        for index, text in enumerate(runs)
        if "uv sync" in text and "--no-install-project" not in text
    ]
    if guard is None or guard > build or any(index < guard for index in installs_project):
        problems.append("build-mcpb: release guard does not run before the bundle build")
    if any("uv build" in text or "dist/" in text.replace("mcpb-dist/", "") for text in runs):
        problems.append("build-mcpb: touches the PyPI distribution directory")
    if installs_project:
        problems.append("build-mcpb: installs the project")
    record = step_index(steps, "MCPB-SHA256SUMS")
    upload = step_index(steps, "actions/upload-artifact@")
    if record is None or record < build:
        problems.append("build-mcpb: checksum is not recorded after the build")
    if upload is None or upload < build or (record is not None and upload < record):
        problems.append("build-mcpb: upload is not after the build and the checksum")
    if "mcpb_sha256sums" not in (job.get("outputs") or {}):
        problems.append("build-mcpb: the checksum is not a job output")
    return problems


FORBIDDEN_RELEASE_COMMANDS = re.compile(
    r"--clobber|gh release (?:create|edit|delete|delete-asset)\b|git push|\bcurl\b|\bwget\b"
    r"|gh api\b|\bunzip\b|\bzipfile\b|\beval\b"
)
TAG_CHECK = "^v[0-9]+\\.[0-9]+\\.[0-9]+(rc[0-9]+)?$"


def token_env_names(job: dict[str, Any]) -> list[tuple[str, str]]:
    found = [("job", name) for name in (job.get("env") or {}) if "TOKEN" in name.upper()]
    for step in job.get("steps", []):
        found += [
            (str(step.get("name", "?")), name)
            for name in (step.get("env") or {})
            if "TOKEN" in name.upper()
        ]
    return found


def release_asset_job_problems(job: dict[str, Any]) -> list[str]:
    """``release-asset`` (D151-09): the only ``contents: write``, after PyPI and the bundle."""
    problems = []
    needs = job.get("needs")
    if sorted([needs] if isinstance(needs, str) else needs or []) != ["build-mcpb", "publish"]:
        problems.append("release-asset does not need exactly build-mcpb and publish")
    if "if" in job or any("if" in step for step in job.get("steps", [])):
        problems.append("release-asset has a condition, so it could run after a failure")
    if "environment" in job or "env" in job or "continue-on-error" in job:
        problems.append("release-asset has an environment, a job-level env or continue-on-error")
    steps = job.get("steps", [])
    uses = [str(step["uses"]).split("@")[0] for step in steps if "uses" in step]
    if uses != ["actions/download-artifact"]:
        problems.append("release-asset uses an action other than the artifact download")
    runs = [str(step.get("run", "")) for step in steps]
    scripts = "\n".join(runs)
    for step in steps:
        if "continue-on-error" in step:
            problems.append("release-asset step continues on error")
    if re.search(r"\b(uv|uvx|pip|python|npm|npx|node|twine|hatch)\b|checkout|build", scripts):
        problems.append("release-asset builds, installs or checks out")
    found = FORBIDDEN_RELEASE_COMMANDS.findall(scripts)
    if found:
        problems.append(f"release-asset uses a forbidden command: {sorted(set(found))}")
    if "gh release upload" not in scripts:
        problems.append("release-asset does not upload with gh release upload")
    if token_env_names(job) != [("Attach the bundle and its checksum to the release", "GH_TOKEN")]:
        problems.append("the token is not exposed to the upload step alone as GH_TOKEN")
    for step in steps:
        if "gh release" in str(step.get("run", "")) and TAG_CHECK not in str(step["run"]):
            problems.append("the step calling gh does not validate the tag first")
    for step in steps:
        if (
            "GH_TOKEN" in (step.get("env") or {})
            and step["env"]["GH_TOKEN"] != "${{ github.token }}"
        ):
            problems.append("GH_TOKEN is not the workflow token")
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
    bundle_up = settings("build-mcpb", "actions/upload-artifact@")
    bundle_down = settings("release-asset", "actions/download-artifact@")
    if not bundle_up.get("name") or bundle_up.get("name") != bundle_down.get("name"):
        problems.append("bundle artifact names differ between upload and download")
    if bundle_up.get("name") == upload.get("name"):
        problems.append("the bundle shares the artifact name of the PyPI distribution")
    if bundle_up.get("if-no-files-found") != "error":
        problems.append("bundle upload does not fail without files")
    if bundle_up.get("path") != bundle_down.get("path"):
        problems.append("bundle upload and download directories differ")
    return problems


def publish_workflow_problems(text: str, ci_text: str | None = None) -> list[str]:
    """Every way the publish workflow departs from AC-22P-01 to AC-22P-10."""
    workflow = yaml.safe_load(text)
    ci = yaml.safe_load(ci_text if ci_text is not None else CI_WORKFLOW.read_text("utf-8"))
    problems = trigger_problems(workflow) + permission_problems(workflow, text)
    jobs = workflow.get("jobs", {})
    if set(jobs) != {"build", "publish", "build-mcpb", "release-asset"}:
        return [*problems, "jobs are not exactly build, publish, build-mcpb and release-asset"]
    problems += build_job_problems(jobs["build"], uv_version(ci))
    problems += publish_job_problems(jobs["publish"])
    problems += bundle_job_problems(jobs["build-mcpb"], uv_version(ci))
    problems += release_asset_job_problems(jobs["release-asset"])
    for name in ("build", "publish"):
        if bundle_steps_in(jobs[name]):
            problems.append(f"the PyPI job {name} references the MCPB bundle")
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
        if "continue-on-error" in job:
            problems.append("a job continues on error")
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


# ------------------------------------------------ the MCPB bundle jobs (#151, D151-09)


def job_text(text: str, job: str) -> tuple[int, int]:
    """Start and end offset of the text of one job (jobs are the two-space-indented keys)."""
    start = text.index(f"\n  {job}:\n") + 1
    following = re.search(r"\n  [a-z][a-z-]*:\n|\n  # ", text[start + 1 :])
    return start, len(text) if following is None else start + 1 + following.start()


def edit_job(text: str, job: str, old: str, new: str, count: int = 1) -> str:
    """Replace ``old`` inside one job only (``count=-1``: every occurrence in that job)."""
    start, end = job_text(text, job)
    segment = text[start:end]
    assert old in segment, (job, old)
    return text[:start] + segment.replace(old, new, count) + text[end:]


NEEDS = "    needs: [build-mcpb, publish]\n"
TAG_TEST = "=~ ^v[0-9]+\\.[0-9]+\\.[0-9]+(rc[0-9]+)?$ ]]"
ENV_LINE = "          GH_TOKEN: ${{ github.token }}\n"
SETUP_UV = "astral-sh/setup-uv@68559e99cc807c1eb7e9238fd43a15bba460eec2 # v10.3.3"
GH_INSERT = "          gh --version\n"
CONTENTS_WRITE = "      contents: write\n"


def real_workflow() -> dict[str, Any]:
    return dict(yaml.safe_load(WORKFLOW.read_text("utf-8")))


def test_the_real_workflow_has_the_four_jobs_and_one_write_permission():
    workflow = real_workflow()
    permissions = {name: job.get("permissions") for name, job in workflow["jobs"].items()}
    assert permissions == {
        "build": {"contents": "read"},
        "publish": {"id-token": "write"},
        "build-mcpb": {"contents": "read"},
        "release-asset": {"contents": "write"},
    }
    assert workflow["permissions"] == {}
    # The PyPI path does not depend on the bundle; the release step depends on both.
    assert workflow["jobs"]["publish"]["needs"] == "build"
    assert "needs" not in workflow["jobs"]["build"]
    assert "needs" not in workflow["jobs"]["build-mcpb"]
    assert workflow["jobs"]["release-asset"]["needs"] == ["build-mcpb", "publish"]
    assert "if" not in workflow["jobs"]["release-asset"]


def test_the_pypi_jobs_do_not_mention_the_bundle():
    jobs = real_workflow()["jobs"]
    assert not bundle_steps_in(jobs["build"]) and not bundle_steps_in(jobs["publish"])


CASES = [
    # permissions and scope of contents: write
    ("release-asset", CONTENTS_WRITE, "      contents: read\n", "release-asset job permissions"),
    (
        "release-asset",
        CONTENTS_WRITE,
        CONTENTS_WRITE + "      id-token: write\n",
        "release-asset job permissions",
    ),
    (
        "release-asset",
        CONTENTS_WRITE,
        CONTENTS_WRITE + "      pull-requests: write\n",
        "release-asset job permissions",
    ),
    ("build-mcpb", "      contents: read\n", CONTENTS_WRITE, "contents: write outside"),
    ("build", "      contents: read\n", CONTENTS_WRITE, "contents: write outside"),
    ("publish", "      id-token: write\n", "      id-token: write\n" + CONTENTS_WRITE, "outside"),
    (
        "build-mcpb",
        "      contents: read\n",
        "      contents: read\n      id-token: write\n",
        "build-mcpb job permissions",
    ),
    # ordering and gating
    ("release-asset", NEEDS, "    needs: [build-mcpb]\n", "does not need exactly"),
    ("release-asset", NEEDS, "    needs: [publish]\n", "does not need exactly"),
    ("release-asset", NEEDS, "    needs: [build-mcpb, publish, build]\n", "does not need exactly"),
    ("release-asset", NEEDS, NEEDS + "    if: always()\n", "has a condition"),
    ("release-asset", NEEDS, NEEDS + "    if: ${{ !cancelled() }}\n", "has a condition"),
    ("release-asset", NEEDS, NEEDS + "    if: ${{ failure() }}\n", "has a condition"),
    (
        "release-asset",
        "      - name: Verify the downloaded bundle",
        "      - if: always()\n        run: echo x\n      - name: Verify the downloaded bundle",
        "has a condition",
    ),
    ("release-asset", NEEDS, NEEDS + "    continue-on-error: true\n", "continue-on-error"),
    ("release-asset", NEEDS, NEEDS + "    environment: pypi\n", "an environment"),
    ("build-mcpb", "    permissions:\n", "    needs: build\n    permissions:\n", "has needs"),
    (
        "build-mcpb",
        "    permissions:\n",
        "    environment: pypi\n    permissions:\n",
        "has needs, an environment",
    ),
    (
        "build-mcpb",
        "    permissions:\n",
        "    continue-on-error: true\n    permissions:\n",
        "a job continues on error",
    ),
    (
        "publish",
        "    needs: build\n",
        "    needs: [build, release-asset]\n",
        "does not need the build",
    ),
    (
        "publish",
        "    needs: build\n",
        "    needs: [build, build-mcpb]\n",
        "does not need the build",
    ),
    # what the write job may contain
    (
        "release-asset",
        "    steps:\n",
        f"    steps:\n      - uses: {CHECKOUT_PIN}\n",
        "other than the artifact download",
    ),
    (
        "release-asset",
        "    steps:\n",
        f"    steps:\n      - uses: {SETUP_UV}\n",
        "other than the artifact download",
    ),
    (
        "release-asset",
        "    steps:\n",
        "    steps:\n      - run: uv run python x.py\n",
        "builds, installs or checks out",
    ),
    (
        "release-asset",
        "    steps:\n",
        "    steps:\n      - run: npx @anthropic-ai/mcpb pack\n",
        "builds, installs or checks out",
    ),
    (
        "release-asset",
        GH_INSERT,
        GH_INSERT + "          gh release upload t x --clobber\n",
        "forbidden",
    ),
    ("release-asset", GH_INSERT, GH_INSERT + "          gh release create t\n", "forbidden"),
    ("release-asset", GH_INSERT, GH_INSERT + "          gh release edit t\n", "forbidden"),
    ("release-asset", GH_INSERT, GH_INSERT + "          gh release delete t\n", "forbidden"),
    (
        "release-asset",
        GH_INSERT,
        GH_INSERT + "          gh release delete-asset t x\n",
        "forbidden",
    ),
    ("release-asset", GH_INSERT, GH_INSERT + "          git push origin HEAD:main\n", "forbidden"),
    (
        "release-asset",
        GH_INSERT,
        GH_INSERT + "          curl -sSf https://x.invalid/y\n",
        "forbidden",
    ),
    ("release-asset", GH_INSERT, GH_INSERT + "          gh api -X DELETE repos/x/y\n", "forbidden"),
    ("release-asset", GH_INSERT, GH_INSERT + '          unzip "${name}"\n', "forbidden"),
    (
        "release-asset",
        "gh release upload",
        "gh release edit",
        "does not upload with gh release upload",
    ),
    # the token
    (
        "release-asset",
        NEEDS,
        NEEDS + "    env:\n" + ENV_LINE.replace("    ", "", 1),
        "job-level env",
    ),
    (
        "release-asset",
        "        env:\n          MCPB_SHA256SUMS:",
        "        env:\n" + ENV_LINE + "          MCPB_SHA256SUMS:",
        "not exposed to the upload step alone",
    ),
    (
        "release-asset",
        ENV_LINE,
        ENV_LINE + "          GITHUB_TOKEN: ${{ github.token }}\n",
        "not exposed to the upload step alone",
    ),
    (
        "release-asset",
        ENV_LINE,
        "          GH_TOKEN: ${{ github.event.release.body }}\n",
        "not the workflow token",
    ),
    # untrusted input
    ("release-asset", TAG_TEST, "== v* ]]", "does not validate the tag"),
    (
        "release-asset",
        'name="wled-mcp-${GITHUB_REF_NAME#v}.mcpb"\n          export',
        'name="wled-mcp-${{ github.ref_name }}.mcpb"\n          export',
        "interpolates an expression",
    ),
    # artifact hand-over
    (
        "release-asset",
        "          name: mcpb-bundle\n",
        "          name: other\n",
        "bundle artifact names",
    ),
    (
        "release-asset",
        "          path: mcpb-dist/\n",
        "          path: elsewhere/\n",
        "directories differ",
    ),
    (
        "build-mcpb",
        "          name: mcpb-bundle\n",
        "          name: python-distribution\n",
        "bundle artifact names",
    ),
    (
        "build-mcpb",
        "          if-no-files-found: error\n",
        "",
        "bundle upload does not fail without files",
    ),
    # the build-mcpb job itself
    ("build-mcpb", "          persist-credentials: false\n", "", "checkout keeps credentials"),
    ("build-mcpb", "          enable-cache: false\n", "", "setup-uv cache is enabled"),
    (
        "build-mcpb",
        '          version: "0.11.14"\n',
        '          version: "0.11.13"\n',
        "uv version differs",
    ),
    ("build-mcpb", "      UV_PYTHON_DOWNLOADS: never\n", "", "Python downloads are not disabled"),
    ("build-mcpb", "    timeout-minutes: 15\n", "", "job without timeout-minutes"),
    (
        "build-mcpb",
        "run: uv sync --locked --no-install-project\n",
        "run: uv sync --locked\n",
        "release guard does not run before the bundle build",
    ),
    (
        "build-mcpb",
        '--version "${GITHUB_REF_NAME#v}" --output mcpb-dist',
        "--output mcpb-dist",
        "not built for the tag",
    ),
    (
        "build-mcpb",
        "          test ! -e mcpb-dist\n",
        "          test ! -e mcpb-dist\n          uv build --no-build-isolation\n",
        "touches the PyPI distribution directory",
    ),
    (
        "build-mcpb",
        "      - run: git diff --exit-code\n",
        "      - run: git diff --exit-code\n      - run: uv sync --locked\n",
        "installs the project",
    ),
    (
        "build-mcpb",
        "      mcpb_sha256sums: ${{ steps.mcpb-checksums",
        "      other: ${{ steps.mcpb-checksums",
        "not a job output",
    ),
]


@pytest.mark.parametrize(("job", "old", "new", "expected"), CASES)
def test_bundle_jobs_are_checked(job, old, new, expected):
    mutated = edit_job(
        WORKFLOW.read_text("utf-8"), job, old, new, count=-1 if old == TAG_TEST else 1
    )
    problems = publish_workflow_problems(mutated)
    assert any(expected in problem for problem in problems), problems


def test_bundle_steps_in_a_pypi_job_are_reported():
    text = WORKFLOW.read_text("utf-8")
    old = "      - name: Check the package metadata\n"
    smuggled = edit_job(text, "build", old, "      - run: echo mcpb\n" + old)
    assert "the PyPI job build references the MCPB bundle" in publish_workflow_problems(smuggled)
    old = "      - uses: pypa/gh-action"
    smuggled = edit_job(text, "publish", old, "      - run: echo mcpb\n" + old)
    assert "the PyPI job publish references the MCPB bundle" in publish_workflow_problems(smuggled)


def test_a_missing_or_extra_job_is_reported():
    text = WORKFLOW.read_text("utf-8")
    cut = text[: job_text(text, "release-asset")[0]].rstrip() + "\n"
    assert any("jobs are not exactly" in p for p in publish_workflow_problems(cut))
    extra = text + "\n  extra:\n    runs-on: ubuntu-latest\n    timeout-minutes: 1\n    steps: []\n"
    assert any("jobs are not exactly" in p for p in publish_workflow_problems(extra))


def test_the_bundle_build_follows_the_release_guard():
    text = WORKFLOW.read_text("utf-8")
    start, end = job_text(text, "build-mcpb")
    segment = text[start:end]
    guard = segment.index("      - name: Release guard\n")
    build = segment.index("      - name: Build the MCPB bundle\n")
    record = segment.index("      - name: Record the MCPB bundle checksum\n")
    moved = segment[:guard] + segment[build:record] + segment[guard:build] + segment[record:]
    assert moved != segment
    problems = publish_workflow_problems(text[:start] + moved + text[end:])
    assert "build-mcpb: release guard does not run before the bundle build" in problems


def test_the_workflow_adds_no_action_and_pins_every_one():
    text = WORKFLOW.read_text("utf-8")
    actions = {
        line.split("uses:", 1)[1].split("@")[0].strip()
        for line in text.splitlines()
        if "uses:" in line
    }
    assert actions == {
        "actions/checkout",
        "actions/setup-python",
        "astral-sh/setup-uv",
        "actions/upload-artifact",
        "actions/download-artifact",
        PUBLISH_ACTION,
    }
    assert "secrets." not in text and "--clobber" not in text


# -------------------------- MCPB checksum hand-over and the release upload (#151, D151-10)

TAG = "v1.2.3"
BUNDLE = "wled-mcp-1.2.3.mcpb"
HOSTILE_TAGS = [
    "v1.2.3;touch pwned",
    "v1.2.3$(touch pwned)",
    "v1.2.3\nv1.2.4",
    "v1.2.3 ",
    "1.2.3",
    "v1.2",
    "v1.2.3-rc.1",
    "v1.2.3rc",
    "main",
    "",
]
BUILD_STEP = ("build-mcpb", "Record the MCPB bundle checksum")
VERIFY_STEP = ("release-asset", "Verify the downloaded bundle against the tested checksum")
UPLOAD_STEP = ("release-asset", "Attach the bundle and its checksum to the release")


def built_bundle(workspace: Path, name: str = BUNDLE) -> Path:
    bundle_dir = workspace / "mcpb-dist"
    bundle_dir.mkdir(parents=True)
    (bundle_dir / name).write_bytes(b"synthetic bundle")
    return bundle_dir


def record_bundle(tmp_path: Path, tag: str = TAG) -> subprocess.CompletedProcess[str]:
    temp = tmp_path / "build-temp"
    temp.mkdir(exist_ok=True)
    (tmp_path / "summary.txt").touch()
    (tmp_path / "output.txt").touch()
    return run_script(
        step_script(*BUILD_STEP),
        tmp_path / "build",
        {
            "RUNNER_TEMP": str(temp),
            "GITHUB_REF_NAME": tag,
            "GITHUB_SHA": "0" * 40,
            "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.txt"),
            "GITHUB_OUTPUT": str(tmp_path / "output.txt"),
        },
    )


@GNU_SHELL
@pytest.mark.parametrize("case", ["tested", "extra", "missing", "other-version"])
def test_bundle_build_step_records_exactly_the_one_tested_file(tmp_path, case):
    bundle_dir = built_bundle(
        tmp_path / "build", "wled-mcp-1.2.4.mcpb" if case == "other-version" else BUNDLE
    )
    if case == "extra":
        (bundle_dir / "extra.mcpb").write_bytes(b"x")
    elif case == "missing":
        (bundle_dir / BUNDLE).unlink()
    result = record_bundle(tmp_path)
    assert (result.returncode == 0) is (case == "tested"), result.stdout + result.stderr
    if case == "tested":
        output = (tmp_path / "output.txt").read_text("utf-8")
        sums = (tmp_path / "build-temp" / "MCPB-SHA256SUMS").read_text("utf-8")
        assert output == f"mcpb_sha256sums<<MCPB_SHA256SUMS_END\n{sums}MCPB_SHA256SUMS_END\n"
        assert sums.endswith(f"  {BUNDLE}\n") and sums.count("\n") == 1
        assert "not tested by the project" in (tmp_path / "summary.txt").read_text("utf-8").lower()


def verify_bundle(workspace: Path, sums: str, tag: str = TAG) -> subprocess.CompletedProcess[str]:
    temp = workspace / "temp"
    temp.mkdir(exist_ok=True)
    return run_script(
        step_script(*VERIFY_STEP),
        workspace,
        {"RUNNER_TEMP": str(temp), "GITHUB_REF_NAME": tag, "MCPB_SHA256SUMS": sums},
    )


def recorded_sums(tmp_path: Path) -> str:
    built_bundle(tmp_path / "build")
    assert record_bundle(tmp_path).returncode == 0
    return (tmp_path / "build-temp" / "MCPB-SHA256SUMS").read_text("utf-8")


@GNU_SHELL
@pytest.mark.parametrize(
    "tamper", [None, "modified", "extra", "missing", "other-name", "two-lines", "empty-sums"]
)
def test_release_asset_verifies_the_downloaded_bundle(tmp_path, tamper):
    sums = recorded_sums(tmp_path)
    workspace = tmp_path / "release"
    shutil.copytree(tmp_path / "build" / "mcpb-dist", workspace / "mcpb-dist")
    bundle = workspace / "mcpb-dist" / BUNDLE
    if tamper == "modified":
        bundle.write_bytes(b"other bundle")
    elif tamper == "extra":
        (workspace / "mcpb-dist" / "SHA256SUMS").write_text(sums, encoding="utf-8")
    elif tamper == "missing":
        bundle.unlink()
    elif tamper == "other-name":
        sums = sums.replace(BUNDLE, "wled-mcp-1.2.4.mcpb")
    elif tamper == "two-lines":
        sums += sums.replace(BUNDLE, "other.mcpb")
    elif tamper == "empty-sums":
        sums = ""
    result = verify_bundle(workspace, sums.rstrip("\n"))
    assert (result.returncode == 0) is (tamper is None), result.stdout + result.stderr
    names = sorted(path.name for path in (workspace / "mcpb-dist").iterdir())
    if tamper is None:
        assert names == [BUNDLE, f"{BUNDLE}.sha256"]
        # The checksum asset carries the tested value, in sha256sum format.
        assert (workspace / "mcpb-dist" / f"{BUNDLE}.sha256").read_text("utf-8") == sums
    else:
        assert not any(name.endswith(".sha256") for name in names if name != "SHA256SUMS")


@GNU_SHELL
@pytest.mark.parametrize("tag", HOSTILE_TAGS)
def test_release_asset_verify_step_rejects_a_hostile_tag(tmp_path, tag):
    sums = recorded_sums(tmp_path)
    workspace = tmp_path / "release"
    shutil.copytree(tmp_path / "build" / "mcpb-dist", workspace / "mcpb-dist")
    result = verify_bundle(workspace, sums.rstrip("\n"), tag)
    assert result.returncode != 0
    assert not (workspace / "pwned").exists()
    assert sorted(p.name for p in (workspace / "mcpb-dist").iterdir()) == [BUNDLE]


GH_STUB = """#!/bin/bash
# Records every call and answers from files; no network.
printf '%s\\t' "$@" >> "${GH_LOG}"
printf '\\n' >> "${GH_LOG}"
case "$1 $2" in
  "release view") cat "${GH_NAMES}" ;;
  "release download")
    while [ $# -gt 0 ]; do
      case "$1" in --pattern) pattern="$2"; shift ;; --dir) dir="$2"; shift ;; esac
      shift
    done
    cp "${GH_REMOTE}/${pattern}" "${dir}/${pattern}"
    ;;
  "release upload") [ -z "${GH_FAIL_UPLOAD:-}" ] || exit 1 ;;
esac
"""


class Upload:
    """A workspace with the files the upload step finds and a stubbed ``gh``."""

    def __init__(self, tmp_path: Path, remote: dict[str, bytes] | None = None):
        self.tmp = tmp_path
        sums = f"{'0' * 64}  {BUNDLE}\n"
        self.local = {BUNDLE: b"synthetic bundle", f"{BUNDLE}.sha256": sums.encode()}
        self.workspace = tmp_path / "release"
        (self.workspace / "mcpb-dist").mkdir(parents=True)
        for name, data in self.local.items():
            (self.workspace / "mcpb-dist" / name).write_bytes(data)
        self.remote_dir = tmp_path / "remote"
        self.remote_dir.mkdir()
        for name, data in (remote or {}).items():
            (self.remote_dir / name).write_bytes(data)
        (tmp_path / "names.txt").write_text("".join(f"{n}\n" for n in remote or {}), "utf-8")
        (tmp_path / "gh-stub.sh").write_text(GH_STUB, encoding="utf-8", newline="\n")
        (tmp_path / "temp").mkdir()
        self.log = tmp_path / "gh.log"
        self.log.touch()

    def run(self, tag: str = TAG, fail_upload: bool = False) -> subprocess.CompletedProcess[str]:
        stub = shlex.quote((self.tmp / "gh-stub.sh").as_posix())
        script = f'gh() {{ bash {stub} "$@"; }}\n' + step_script(*UPLOAD_STEP)
        env = {
            "RUNNER_TEMP": str(self.tmp / "temp"),
            "GITHUB_REF_NAME": tag,
            "GITHUB_REPOSITORY": "example/repository",
            "GH_TOKEN": "synthetic-token-value",
            "GH_LOG": str(self.log),
            "GH_NAMES": str(self.tmp / "names.txt"),
            "GH_REMOTE": str(self.remote_dir),
        }
        if fail_upload:
            env["GH_FAIL_UPLOAD"] = "1"
        return run_script(script, self.workspace, env)

    def calls(self) -> list[list[str]]:
        lines = self.log.read_text("utf-8").splitlines()
        return [line.rstrip("\t").split("\t") for line in lines]

    def uploads(self) -> list[list[str]]:
        return [call for call in self.calls() if call[:2] == ["release", "upload"]]


@GNU_SHELL
def test_first_run_uploads_both_assets_without_clobber(tmp_path):
    attach = Upload(tmp_path)
    result = attach.run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert attach.uploads() == [
        ["release", "upload", TAG, BUNDLE],
        ["release", "upload", TAG, f"{BUNDLE}.sha256"],
    ]
    verbs = {tuple(call[:2]) for call in attach.calls()} - {("--version",)}
    assert verbs <= {("release", "view"), ("release", "upload")}
    assert all("--clobber" not in call for call in attach.calls())
    # Release and token come from the environment, never from the command line.
    assert "synthetic-token-value" not in attach.log.read_text("utf-8")


@GNU_SHELL
def test_an_identical_existing_asset_is_accepted_as_a_no_op(tmp_path):
    probe = Upload(tmp_path / "probe")
    attach = Upload(tmp_path / "run", remote=probe.local)
    result = attach.run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert attach.uploads() == []
    downloads = [call for call in attach.calls() if call[:2] == ["release", "download"]]
    assert len(downloads) == 2


@GNU_SHELL
def test_one_identical_asset_present_uploads_only_the_missing_one(tmp_path):
    probe = Upload(tmp_path / "probe")
    attach = Upload(tmp_path / "run", remote={BUNDLE: probe.local[BUNDLE]})
    result = attach.run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert attach.uploads() == [["release", "upload", TAG, f"{BUNDLE}.sha256"]]


@GNU_SHELL
@pytest.mark.parametrize("which", [BUNDLE, f"{BUNDLE}.sha256"])
def test_a_different_existing_asset_fails_and_nothing_is_replaced(tmp_path, which):
    probe = Upload(tmp_path / "probe")
    remote = dict(probe.local)
    remote[which] = b"different bytes already attached"
    attach = Upload(tmp_path / "run", remote=remote)
    result = attach.run()
    assert result.returncode != 0
    assert attach.uploads() == []
    assert (attach.remote_dir / which).read_bytes() == b"different bytes already attached"


@GNU_SHELL
def test_a_failing_upload_fails_the_job(tmp_path):
    attach = Upload(tmp_path)
    assert attach.run(fail_upload=True).returncode != 0


@GNU_SHELL
@pytest.mark.parametrize("missing", [BUNDLE, f"{BUNDLE}.sha256"])
def test_a_missing_local_file_stops_before_any_upload(tmp_path, missing):
    attach = Upload(tmp_path)
    (attach.workspace / "mcpb-dist" / missing).unlink()
    assert attach.run().returncode != 0
    assert attach.uploads() == []


@GNU_SHELL
@pytest.mark.parametrize("tag", HOSTILE_TAGS)
def test_a_hostile_tag_reaches_gh_never(tmp_path, tag):
    attach = Upload(tmp_path)
    result = attach.run(tag=tag)
    assert result.returncode != 0
    assert attach.calls() == []
    assert not (attach.workspace / "pwned").exists()
