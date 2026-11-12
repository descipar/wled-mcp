"""Issue #62: repository text carries no private identifiers of an installation.

Runs ``scripts/check_private_identifiers.py`` against the real tree and, for negative
controls, against temporary Git repositories with planted values. Planted values are
assembled from parts (``"192.168" + ".1.20"``) so that this file itself stays clean
without allowlist entries; the allowlist covers the literal controls of
``tests/test_deployment_artifacts.py``. No network access.
"""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_private_identifiers.py"


def load_scanner() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_private_identifiers", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve annotations through sys.modules
    spec.loader.exec_module(module)
    return module


scanner = load_scanner()


def rules(path: str, text: str) -> list[str]:
    return [finding.rule for finding in scanner.scan_text(path, text)]


def clean_env(**extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k != scanner.DENYLIST_ENV}
    env.update(extra)
    return env


def git_repo(directory: Path, files: dict[str, str]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(directory)], check=True, timeout=30)
    for name, content in files.items():
        target = directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=directory, check=True, timeout=30)
    return directory


def run(root: Path, *args: str, env: dict[str, str] | None = None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), *args],
        capture_output=True,
        text=True,
        timeout=60,
        env=env if env is not None else clean_env(),
    )


# ------------------------------------------------------------------ the real tree


def test_repository_tree_has_no_private_identifiers():
    result = scanner.check(ROOT, scanner.ALLOWLIST, [])
    assert [finding.report() for finding in result.findings] == []
    assert result.stale == []
    assert result.files > 100, "the scan must cover the tracked tree, not an empty set"


def test_ci_runs_the_scanner_as_its_own_step():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text("utf-8")
    steps = [line.strip() for line in workflow.splitlines() if line.strip().startswith("- run:")]
    command = "- run: uv run --frozen python scripts/check_private_identifiers.py"
    assert command in steps
    pytest_step = next(s for s in steps if s.startswith("- run: uv run --frozen pytest"))
    assert steps.index(command) < steps.index(pytest_step)


def test_scanner_rule_block_is_the_only_exempt_text_of_its_own_file():
    text = SCRIPT.read_text("utf-8")
    block = scanner.rule_definition_lines(text)
    findings = scanner.scan_text(scanner.SELF.as_posix(), text)
    assert findings, "the rule block defines private ranges and must be recognized"
    exempt = scanner.rule_definition_values()
    assert all(finding.line in block and finding.value in exempt for finding in findings)


# ------------------------------------------------------------ rules (R62-6 controls)

LEAKS = [
    ("ipv4-private", "controller at 192.168" + ".1.20"),
    ("ipv4-private", "host 10." + "1.2.3 is reachable"),
    ("ipv4-private", "base_url http://172.31" + ".0.5/json"),
    ("ipv4-private", "fallback 169.254" + ".7.8"),
    ("ipv4-private", "overlay VPN 100.64" + ".0.9"),
    ("ipv6-private", "link-local fe80" + "::1%eth0"),
    ("ipv6-private", "unique-local fd00" + "::12"),
    ("ipv6-private", "host:fd00" + "::1"),
    ("home-path", "backups in /ho" + "me/alex/wled"),
    ("home-path", "checkout /Us" + "ers/alex/src"),
    ("home-path", "checkout /us" + "ers/alex"),
    ("home-path", "checkout C:\\Us" + "ers\\alex\\src"),
    ("home-path", "checkout C:\\US" + "ERS\\ALEX"),
    ("local-hostname", "http://wled-desk" + ".local/json"),
    ("local-hostname", "host wled-desk" + ".lan"),
    ("local-hostname", "host wled-desk" + ".fritz.box"),
    ("local-hostname", "host wled-desk" + ".home.arpa"),
    ("local-hostname", "host hub" + ".internal:8000"),
    ("mac-address", "MAC 02:42" + ":ac:11:00:02"),
    ("mac-address", "MAC 02-42" + "-AC-11-00-02"),
    ("mac-address", '{"mac": "0242ac11' + '0002"}'),
    ("mac-address", "MAC 0242" + ".ac11.0002"),
    ("email", "contact alex.doe" + "@mail.com"),
    ("framing-phrase", "deploy it to the home" + " hub"),
    ("framing-phrase", "the house" + "hold presets"),
    ("framing-phrase", "agreed in the project\n" + "conversation"),
    ("framing-phrase", "the repository remains" + " private"),
    ("framing-phrase", "Private WLED" + " MCP server"),
]


@pytest.mark.parametrize(("rule", "text"), LEAKS, ids=[rule for rule, _ in LEAKS])
def test_each_rule_detects_a_planted_value(rule, text):
    assert rules("docs/NOTES.md", "clean line\n" + text) == [rule]
    (finding,) = scanner.scan_text("docs/NOTES.md", "clean line\n" + text)
    assert finding.line == 2


ALLOWED = [
    "loopback 127.0.0.1 and wildcard 0.0.0.0, service wled-mcp:8000",
    "documentation 192.0.2.10, 198.51.100.255 and 203.0.113.7",
    "IPv6 ::1, :: and 2001:db8::1",
    "Python 3.10.0.1, invalid 999.1.1.1 and 0.0.0.256",
    "documentation MAC 00:00:5E:00:53:01 and 00-00-5e-00-53-ff",
    '{"mac": "00005e005301"}',
    "hosts wled-a.example.invalid, hub.test and wled.example",
    "mail ops@example.org, a@b.invalid and agent <noreply@anthropic.com>",
    "mail admin@mail.example.com, x@lists.example.net and 123+bot@users.noreply.github.com",
    "documentation MAC 0000.5e00.5301 and version 1.2.3.4",
    "commit db0b2edde4d20a07f789d7192314d1e606acb50f319a and time 12:34:56",
    "settings.local.json, .env.local, *.local and the .lan suffix",
    "https://example.com/home/alex and docs/home/readme",
    "a human merge decision; the owner, maintainer and operator; MCPHub on a small host",
]


@pytest.mark.parametrize("text", ALLOWED)
def test_synthetic_and_documentation_values_pass(text):
    assert scanner.scan_text("docs/NOTES.md", text) == []


def test_python_attribute_access_is_not_a_host_name():
    # Assembled so that the quoted source line of this test does not itself match.
    source = "state = threading.local()\nhome = Path.home()\nvalue = self" + ".private\n"
    assert scanner.scan_text("src/module.py", source) == []


@pytest.mark.parametrize(
    "line",
    [
        'BASE = "http://wled-desk' + '.local/json"',
        "HOST = 'wled-desk" + ".lan'",
        'message = f"cannot reach wled-desk' + '.fritz.box now"',
    ],
)
def test_python_strings_with_local_host_names_are_reported(line):
    assert rules("src/module.py", line + "\n") == ["local-hostname"]


HOST = "wled-kitchen" + ".lan"
TRIPLE = "'" * 3


@pytest.mark.parametrize(
    "source",
    [
        f"x = 1  # tested against {HOST}\n",
        f"# tested against {HOST}\n",
        f'def f():\n    """Reads the state.\n\n    See {HOST} for details.\n    """\n',
        f"TEXT = (\n    {TRIPLE}first line\n    {HOST} second line{TRIPLE}\n)\n",
        f'MESSAGE = f"{{name}} at {HOST}"\n',
    ],
    ids=["inline-comment", "comment", "docstring", "multi-line-string", "f-string"],
)
def test_python_comments_and_docstrings_are_checked_for_host_names(source):
    assert rules("src/module.py", source) == ["local-hostname"]
    assert rules("src/module.py", source.replace(HOST, "wled-kitchen.example")) == []


def test_untokenizable_python_is_checked_as_plain_text():
    assert rules("src/broken.py", f"x = (\nhost {HOST}\n") == ["local-hostname"]


# ------------------------------------------------------- end-to-end (R62-6, R62-7)


PLANTED = "10." + "20.30.40"


def test_end_to_end_planted_value_fails_without_echoing_it(tmp_path):
    repo = git_repo(tmp_path / "repo", {"README.md": "clean\n", "docs/x.md": f"a\nb {PLANTED}\n"})
    result = run(repo)
    assert result.returncode == 1
    assert "docs/x.md:2: ipv4-private" in result.stderr
    assert PLANTED not in result.stdout + result.stderr
    shown = run(repo, "--show-values")
    assert f"docs/x.md:2: ipv4-private: {PLANTED}" in shown.stderr


def test_untracked_files_are_scanned_and_ignored_files_are_not(tmp_path):
    repo = git_repo(tmp_path / "repo", {".gitignore": "runtime/\n", "README.md": "clean\n"})
    (repo / "runtime").mkdir()
    (repo / "runtime" / "devices.toml").write_text(PLANTED, encoding="utf-8")
    assert run(repo).returncode == 0
    (repo / "new.md").write_text(PLANTED, encoding="utf-8")
    assert "new.md:1: ipv4-private" in run(repo).stderr


def test_binary_files_are_skipped(tmp_path):
    repo = git_repo(tmp_path / "repo", {"README.md": "clean\n"})
    (repo / "blob.bin").write_bytes(b"\0" + PLANTED.encode())
    (repo / "latin1.txt").write_bytes(b"\xff" + PLANTED.encode())
    assert run(repo).returncode == 0


def test_outside_a_git_work_tree_fails_closed(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "README.md").write_text("clean\n", encoding="utf-8")
    env = clean_env(GIT_CEILING_DIRECTORIES=str(tmp_path))
    result = run(plain, env=env)
    assert result.returncode == 2
    assert "not a Git work tree" in result.stderr


def test_denylist_literal_is_found_case_insensitively_without_echo(tmp_path):
    secret = "acme-" + "lab-unit"
    repo = git_repo(tmp_path / "repo", {"README.md": f"clean\nsee {secret.upper()}\n"})
    denylist = tmp_path / "deny.txt"
    denylist.write_text(f"# private values\n\n{'unused-entry'}\n{secret}\n", encoding="utf-8")
    result = run(repo, env=clean_env(**{scanner.DENYLIST_ENV: str(denylist)}))
    assert result.returncode == 1
    assert "README.md:2: denylist entry 2" in result.stderr
    assert secret not in result.stderr.lower() + result.stdout.lower()


def test_denylist_in_the_ignored_runtime_directory_is_the_default(tmp_path):
    secret = "acme-" + "lab-unit"
    repo = git_repo(tmp_path / "repo", {".gitignore": "runtime/\n", "README.md": secret})
    assert run(repo).returncode == 0
    (repo / "runtime").mkdir()
    (repo / "runtime" / "private-denylist.txt").write_text(secret, encoding="utf-8")
    result = run(repo)
    assert result.returncode == 1
    assert "README.md:1: denylist entry 1" in result.stderr


def test_absent_denylist_is_skipped_with_a_note(tmp_path):
    repo = git_repo(tmp_path / "repo", {"README.md": "clean\n"})
    result = run(repo)
    assert result.returncode == 0
    assert "no private denylist" in result.stderr


@pytest.mark.parametrize("content", ["ab\n", "x\n# comment\n"])
def test_short_denylist_entries_are_rejected(tmp_path, content):
    repo = git_repo(tmp_path / "repo", {"README.md": "clean\n"})
    denylist = tmp_path / "deny.txt"
    denylist.write_text(content, encoding="utf-8")
    result = run(repo, env=clean_env(**{scanner.DENYLIST_ENV: str(denylist)}))
    assert result.returncode == 2
    assert "shorter than 3 characters" in result.stderr


def test_configured_denylist_must_exist(tmp_path):
    repo = git_repo(tmp_path / "repo", {"README.md": "clean\n"})
    missing = tmp_path / "missing.txt"
    result = run(repo, env=clean_env(**{scanner.DENYLIST_ENV: str(missing)}))
    assert result.returncode == 2


# ---------------------------------------------------------------- allowlist (R62-8)


def allow(path: str, value: str) -> str:
    return f'[[allow]]\npath = "{path}"\nvalue = "{value}"\nreason = "synthetic control"\n\n'


def test_allowlist_exempts_only_its_own_path_and_value(tmp_path):
    other = "10." + "20.30.41"
    files = {
        "tests/control.py": f'LEAK = "{PLANTED}"\nOTHER = "{other}"\n',
        "docs/x.md": f"copy {PLANTED}\n",
        scanner.ALLOWLIST.as_posix(): allow("tests/control.py", PLANTED),
    }
    result = run(git_repo(tmp_path / "repo", files))
    assert result.returncode == 1
    reported = [line for line in result.stderr.splitlines() if line.startswith("ERROR")]
    assert reported == [
        "ERROR: docs/x.md:1: ipv4-private",
        "ERROR: tests/control.py:2: ipv4-private",
    ]


def test_stale_allowlist_entry_fails(tmp_path):
    files = {
        "README.md": "clean\n",
        scanner.ALLOWLIST.as_posix(): allow("README.md", PLANTED),
    }
    result = run(git_repo(tmp_path / "repo", files))
    assert result.returncode == 1
    assert "stale allowlist entry for README.md" in result.stderr
    assert PLANTED not in result.stderr


def test_malformed_allowlist_entry_fails_closed(tmp_path):
    files = {
        "README.md": "clean\n",
        scanner.ALLOWLIST.as_posix(): f'[[allow]]\npath = "README.md"\nvalue = "{PLANTED}"\n',
    }
    result = run(git_repo(tmp_path / "repo", files))
    assert result.returncode == 2
    assert "needs nonempty path, value and reason" in result.stderr


def scanner_source(*, insert: str = "", end_at_bottom: bool = False) -> str:
    """The scanner source with a line added inside its rule block, or the END moved."""
    source = SCRIPT.read_text("utf-8")
    marker = "\n" + scanner.RULES_END + "\n"
    assert source.count(marker) == 1
    if end_at_bottom:
        return source.replace(marker, "\n") + scanner.RULES_END + "\n"
    return source.replace(marker, "\n" + insert + scanner.RULES_END + "\n")


@pytest.mark.parametrize(
    "source",
    [
        scanner_source(insert=f'_NOTE = "{HOST} at {PLANTED}"\n'),
        scanner_source(end_at_bottom=True),
    ],
    ids=["extra-line-in-block", "end-marker-moved"],
)
def test_rule_block_cannot_be_widened(tmp_path, source):
    result = run(git_repo(tmp_path / "repo", {scanner.SELF.as_posix(): source}))
    assert result.returncode == 2
    assert "rule-definition block holds more than the rule constants" in result.stderr


def test_values_inside_the_rule_block_are_exempt_only_as_rule_definitions(tmp_path):
    host_network = "192.168" + ".1.77/32"
    last_range = '"' + str(scanner.PRIVATE_V4[-1]) + '",'
    source = scanner_source(insert=f"# see {PLANTED}\n")
    assert source.count(last_range) == 1
    source = source.replace(last_range, f'{last_range}\n        "{host_network}",')
    result = run(git_repo(tmp_path / "repo", {scanner.SELF.as_posix(): source}))
    assert result.returncode == 1
    reported = [line for line in result.stderr.splitlines() if line.startswith("ERROR")]
    assert len(reported) == 2 and all(line.endswith(": ipv4-private") for line in reported)


def test_rule_values_outside_the_scanner_rule_block_are_reported(tmp_path):
    source = SCRIPT.read_text("utf-8") + f'\nLEAK = "{PLANTED}"\n'
    result = run(git_repo(tmp_path / "repo", {scanner.SELF.as_posix(): source}))
    assert result.returncode == 1
    leak_line = source.count("\n")
    reported = [line for line in result.stderr.splitlines() if line.startswith("ERROR")]
    assert reported == [f"ERROR: {scanner.SELF.as_posix()}:{leak_line}: ipv4-private"]


# ------------------------------------------------- CI denylist step (#90, DEC-018)

WORKFLOW = ROOT / ".github/workflows/ci.yml"
DENYLIST_STEP = "Provide private denylist from secret"
SCANNER_RUN = "uv run --frozen python scripts/check_private_identifiers.py"
SECRET_REF = "${{ secrets.WLED_MCP_PRIVATE_DENYLIST }}"
EXPANSION = re.compile(r"\$\{?PRIVATE_DENYLIST\b")


def workflow_steps(text: str) -> list[dict]:
    return yaml.safe_load(text)["jobs"]["checks"]["steps"]


def denylist_step_problems(text: str) -> list[str]:
    """How the workflow could leak or skip the private denylist (R90-07, D3)."""
    problems = []
    workflow = yaml.safe_load(text)
    triggers = workflow.get("on", workflow.get(True))
    if "pull_request_target" in (triggers or {}):
        problems.append("workflow runs on pull_request_target")
    if workflow.get("permissions") != {"contents": "read"}:
        problems.append("workflow permissions are wider than contents: read")
    steps = workflow_steps(text)
    names = [step.get("name") for step in steps]
    runs = [step.get("run", "") for step in steps]
    if DENYLIST_STEP not in names or SCANNER_RUN not in runs:
        return [*problems, "denylist step or scanner step missing"]
    index = names.index(DENYLIST_STEP)
    if index + 1 != runs.index(SCANNER_RUN):
        problems.append("denylist step does not directly precede the scanner step")
    step = steps[index]
    if step.get("env") != {"PRIVATE_DENYLIST": SECRET_REF}:
        problems.append("secret is not passed through the step env")
    for run in runs:
        if "${{ secrets." in run:
            problems.append("a run script interpolates a secret")
        if "set -x" in run or "--show-values" in run:
            problems.append("a run script traces commands or prints values")
    for line in step["run"].splitlines():
        line = line.strip()
        if re.search(r"\bcat\b", line):
            problems.append("denylist step prints a file")
        if EXPANSION.search(line) and not (
            line.startswith('if [ -z "${PRIVATE_DENYLIST}" ]') or line.endswith('> "${denylist}"')
        ):
            problems.append(f"denylist content used outside the temp file: {line}")
        if "${GITHUB_WORKSPACE}" in line or "github.workspace" in line:
            problems.append("denylist file inside the workspace")
    return problems


def test_ci_feeds_the_denylist_secret_safely():
    assert denylist_step_problems(WORKFLOW.read_text("utf-8")) == []


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        (
            '"${PRIVATE_DENYLIST}" > "${denylist}"',
            f'"{SECRET_REF}" > "${{denylist}}"',
            "a run script interpolates a secret",
        ),
        ("umask 077\n", "set -x\n          umask 077\n", "a run script traces commands"),
        (
            "umask 077\n",
            'echo "${PRIVATE_DENYLIST}"\n          umask 077\n',
            'denylist content used outside the temp file: echo "${PRIVATE_DENYLIST}"',
        ),
        ("umask 077\n", 'cat "${denylist}"\n          umask 077\n', "prints a file"),
        (
            f"PRIVATE_DENYLIST: {SECRET_REF}",
            "PRIVATE_DENYLIST: ${{ vars.DENYLIST }}",
            "secret is not passed through the step env",
        ),
        (
            f"      - run: {SCANNER_RUN}\n",
            "",
            "denylist step or scanner step missing",
        ),
        ("  pull_request:\n", "  pull_request_target:\n", "pull_request_target"),
        ("  contents: read\n", "  contents: write\n", "permissions are wider"),
    ],
)
def test_denylist_step_check_rejects_regressions(old, new, expected):
    text = WORKFLOW.read_text("utf-8")
    assert old in text
    assert any(expected in problem for problem in denylist_step_problems(text.replace(old, new)))


def test_denylist_step_check_rejects_a_step_after_the_scanner():
    text = WORKFLOW.read_text("utf-8")
    scanner_line = f"      - run: {SCANNER_RUN}\n"
    moved = text.replace(scanner_line, "").replace(
        "      - name: " + DENYLIST_STEP, scanner_line + "      - name: " + DENYLIST_STEP
    )
    assert "denylist step does not directly precede the scanner step" in (
        denylist_step_problems(moved)
    )


def find_bash() -> str | None:
    """A POSIX bash; on Windows Git's bash (``bash`` on PATH may be the WSL launcher)."""
    if os.name != "nt":
        return shutil.which("bash")
    exec_path = subprocess.run(
        ["git", "--exec-path"], capture_output=True, text=True, timeout=30, check=False
    ).stdout.strip()
    if not exec_path:
        return None
    git_root = Path(exec_path).parents[2]
    for candidate in (git_root / "bin" / "bash.exe", git_root / "usr" / "bin" / "bash.exe"):
        if candidate.is_file():
            return str(candidate)
    return None


def run_denylist_step(tmp_path: Path, secret: str) -> tuple[subprocess.CompletedProcess, Path]:
    bash = find_bash()
    if bash is None:
        pytest.skip("no POSIX bash available to execute the workflow step")
    (step,) = [
        s for s in workflow_steps(WORKFLOW.read_text("utf-8")) if s.get("name") == DENYLIST_STEP
    ]
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    github_env = tmp_path / "github-env"
    github_env.write_text("", encoding="utf-8")
    env = clean_env(
        PRIVATE_DENYLIST=secret,
        RUNNER_TEMP=runner_temp.as_posix(),
        GITHUB_ENV=github_env.as_posix(),
    )
    result = subprocess.run(
        [bash, "-e", "-c", step["run"]], capture_output=True, text=True, timeout=60, env=env
    )
    return result, github_env


def test_ci_denylist_step_without_secret_runs_rule_checks_only(tmp_path):
    result, github_env = run_denylist_step(tmp_path, "")
    assert result.returncode == 0, result.stderr
    assert "rule checks only" in result.stdout
    assert github_env.read_text("utf-8") == ""
    assert not (tmp_path / "runner-temp" / "private-denylist.txt").exists()


def test_ci_denylist_step_feeds_the_scanner_without_echoing_the_secret(tmp_path):
    secret = "acme-" + "lab-unit"
    result, github_env = run_denylist_step(tmp_path, f"# synthetic entries\n{secret}")
    assert result.returncode == 0, result.stderr
    assert secret not in result.stdout + result.stderr
    (line,) = github_env.read_text("utf-8").splitlines()
    name, _, value = line.partition("=")
    assert name == scanner.DENYLIST_ENV
    denylist = Path(value)
    assert denylist.parent == tmp_path / "runner-temp"
    assert secret in denylist.read_text("utf-8")
    repo = git_repo(tmp_path / "repo", {"README.md": f"clean\nsee {secret}\n"})
    scan = run(repo, env=clean_env(**{scanner.DENYLIST_ENV: value}))
    assert scan.returncode == 1
    assert "README.md:2: denylist entry 1" in scan.stderr
    assert secret not in scan.stdout + scan.stderr
