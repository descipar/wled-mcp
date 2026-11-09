"""CI scope gate for documentation-only pull requests (#159)."""

import ast
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("ci_scope", ROOT / "scripts" / "ci_scope.py")
assert _spec is not None and _spec.loader is not None
ci_scope = importlib.util.module_from_spec(_spec)
sys.modules["ci_scope"] = ci_scope
_spec.loader.exec_module(ci_scope)

Entry = tuple[str, str, str]


def _m(path: str, status: str = "M", mode: str = "100644") -> Entry:
    return (status, mode, path)


DOCS_ONLY = [
    [_m("docs/X.md")],
    [_m("docs/validation/x.md")],
    [_m("README.md")],
    [_m("AGENTS.md"), _m("docs/a.md"), _m("docs/b.md", "A")],
    [_m("docs/gone.md", "D", "000000")],
    [_m("docs/a.md", "D", "000000"), _m("docs/b.md", "A")],  # rename: both sides
]
FULL = [
    [],
    [_m("src/wled_mcp/x.py")],
    [_m("tests/test_x.py")],
    [_m("scripts/check_lock.py")],
    [_m(".github/workflows/ci.yml")],
    [_m("pyproject.toml")],
    [_m("uv.lock")],
    [_m("requirements-runtime.txt")],
    [_m("docs/a.md"), _m("src/a.py")],
    [_m("docs/data.json")],
    [_m("docs/img.png")],
    [_m("docs/x.yml")],
    [_m("agents/coordinator.md")],
    [_m("examples/x.md")],
    [_m("tests/notes.md")],
    [_m(".github/PULL_REQUEST_TEMPLATE.md")],
    [_m("docs/.hidden.md")],
    [_m(".env.md")],
    [_m("README.MD")],
    [_m("docs/a.md", "D", "000000"), _m("src/x.md", "A")],  # rename out of docs
    [_m("src/a.py", "D", "000000"), _m("docs/a.md", "A")],  # rename into docs
    [_m("docs/run.md", mode="100755")],
    [_m("docs/link.md", mode="120000")],
    [_m("docs/../src/x.md")],
]


@pytest.mark.parametrize("entries", DOCS_ONLY)
def test_documentation_only_diffs(entries: list[Entry]) -> None:
    assert ci_scope.classify_paths(entries)[0] is True


@pytest.mark.parametrize("entries", FULL)
def test_everything_else_runs_the_complete_suite(entries: list[Entry]) -> None:
    assert ci_scope.classify_paths(entries)[0] is False


def test_other_events_never_use_the_reduced_set() -> None:
    def fail(*_a: object, **_k: object) -> None:
        raise AssertionError("git must not be consulted")

    for event in ("push", "workflow_dispatch", "schedule", ""):
        assert ci_scope.decide(event, fail)[0] is False


def _done(stdout: str) -> "subprocess.CompletedProcess[str]":
    return subprocess.CompletedProcess([], 0, stdout, "")


@pytest.mark.parametrize(
    "failure",
    [
        subprocess.CalledProcessError(128, "git"),
        subprocess.TimeoutExpired("git", 60),
        FileNotFoundError("git"),
    ],
)
def test_git_failure_is_undeterminable_and_full(failure: Exception) -> None:
    def run(*_a: object, **_k: object) -> None:
        raise failure

    docs_only, reason = ci_scope.decide("pull_request", run)
    assert docs_only is False and reason.startswith("undeterminable")


@pytest.mark.parametrize("parents", ["abc", "abc p1", "abc p1 p2 p3"])
def test_non_merge_shape_is_full(parents: str) -> None:
    docs_only, reason = ci_scope.decide("pull_request", lambda *_a, **_k: _done(parents))
    assert docs_only is False and reason.startswith("undeterminable")


def test_hostile_path_cannot_inject_output_lines() -> None:
    _, reason = ci_scope.classify_paths([_m("src/x\ndocs_only=true")])
    assert "\n" not in reason


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _merge_repo(tmp_path: Path, files: dict[str, str]) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "docs").mkdir()
    (repo / "docs" / "a.md").write_text("a\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "checkout", "-q", "-b", "topic")
    for name, text in files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "topic")
    _git(repo, "checkout", "-q", "main")
    (repo / "src_side.py").write_text("o = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "main moves")
    _git(repo, "merge", "-q", "--no-ff", "-m", "merge", "topic")
    return repo


def _runner(repo: Path):  # type: ignore[no-untyped-def]
    def run(cmd: list[str], **kwargs: object) -> "subprocess.CompletedProcess[str]":
        return subprocess.run(cmd, cwd=repo, **kwargs)  # type: ignore[call-overload,no-any-return]

    return run


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        ({"docs/a.md": "changed\n"}, True),
        ({"docs/a.md": "changed\n", "src/a.py": "x = 1\n"}, False),
    ],
)
def test_real_merge_commit(tmp_path: Path, files: dict[str, str], expected: bool) -> None:
    repo = _merge_repo(tmp_path, files)
    # The base side added a code file; only the topic side may count, and the diff is
    # taken against the first parent.
    assert ci_scope.decide("pull_request", _runner(repo))[0] is expected


def test_plain_commit_is_full(tmp_path: Path) -> None:
    repo = _merge_repo(tmp_path, {"docs/a.md": "changed\n"})
    _git(repo, "reset", "-q", "--hard", "HEAD^1")
    assert ci_scope.decide("pull_request", _runner(repo))[0] is False


def test_cli_output_contract_and_exit_code(capsys: pytest.CaptureFixture[str]) -> None:
    assert ci_scope.main([], {"GITHUB_EVENT_NAME": "push"}) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 2
    assert lines[0] == "docs_only=false" and lines[1].startswith("reason=")
    assert ci_scope.main(["tests"], {}) == 0
    assert capsys.readouterr().out.split() == list(ci_scope.DOC_READER_TESTS)


# --- drift guard: every file that reads documents is classified ---------------------------

_ROOT_DOCS = ("README", "CONTRIBUTING", "CHANGELOG", "AGENTS", "CLAUDE", "SECURITY")


def _docstring_ids(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                ids.add(id(body[0].value))
    return ids


def _is_marker(text: str) -> bool:
    if "docs" in re.split(r"[/\\]", text) or text.endswith(".md") or text == "ls-files":
        return True
    return len(text) < 40 and text.startswith(_ROOT_DOCS)


def reader_files(root: Path) -> set[str]:
    """Python files with a string constant (not a docstring) that names a document.

    Static and best effort (DEC-028): a reader that builds its path without any such literal
    is not found. Adding a reader changes tests/ or scripts/ and so runs the full suite.
    """
    found: set[str] = set()
    for folder in ("tests", "scripts", "deploy", "src"):
        for path in sorted((root / folder).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            skip = _docstring_ids(tree)
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Constant)
                    and isinstance(node.value, str)
                    and id(node) not in skip
                    and _is_marker(node.value)
                ):
                    found.add(path.relative_to(root).as_posix())
                    break
    return found


def classification_problems(
    root: Path, readers: tuple[str, ...], exclusions: dict[str, str]
) -> list[str]:
    unknown = reader_files(root) - set(readers) - set(exclusions)
    problems = [f"unclassified reader: {p}" for p in sorted(unknown)]
    problems += [f"listed twice: {p}" for p in sorted(set(readers) & set(exclusions))]
    problems += [f"missing file: {p}" for p in (*readers, *exclusions) if not (root / p).is_file()]
    problems += [f"empty reason: {p}" for p, why in exclusions.items() if not why.strip()]
    problems += [f"not a test file: {p}" for p in readers if not p.startswith("tests/test_")]
    return problems


def test_every_document_reader_is_classified() -> None:
    problems = classification_problems(
        ROOT, ci_scope.DOC_READER_TESTS, ci_scope.DOC_READER_EXCLUSIONS
    )
    assert problems == []


def test_drift_guard_negative_controls(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_new.py").write_text('p = "docs/NEW.md"\n')
    (tmp_path / "tests" / "test_quiet.py").write_text('"""Mentions docs/X.md."""\nx = 1\n')
    (tmp_path / "tests" / "test_listed.py").write_text('p = "README.md"\n')
    listed = ("tests/test_listed.py",)
    assert classification_problems(tmp_path, listed, {}) == [
        "unclassified reader: tests/test_new.py"
    ]
    assert "missing file: tests/test_gone.py" in classification_problems(
        tmp_path, (*listed, "tests/test_gone.py"), {"tests/test_new.py": "r"}
    )
    assert "empty reason: tests/test_new.py" in classification_problems(
        tmp_path, listed, {"tests/test_new.py": " "}
    )
    assert "listed twice: tests/test_listed.py" in classification_problems(
        tmp_path, listed, {"tests/test_listed.py": "r", "tests/test_new.py": "r"}
    )


# --- workflow shape -----------------------------------------------------------------------

GATED = (
    "ruff check",
    "ruff format",
    "mypy",
    "scripts/check_lock.py",
    "uv run --frozen pytest",
    "scripts/check_distribution.py",
)
ALWAYS = ("check_agent_setup.py", "check_private_identifiers.py", "git diff --exit-code")
FULL_ONLY = "steps.scope.outputs.docs_only != 'true'"
REDUCED_ONLY = "steps.scope.outputs.docs_only == 'true'"


def workflow_problems(text: str) -> list[str]:
    workflow = yaml.safe_load(text)
    job = workflow["jobs"]["checks"]
    steps = job["steps"]
    problems: list[str] = []
    if workflow.get("permissions") != {"contents": "read"}:
        problems.append("permissions changed")
    if "if" in job:
        problems.append("job-level if would drop a required check name")
    if steps[0].get("with", {}).get("fetch-depth") != 2:
        problems.append("checkout must use fetch-depth 2")
    gate = [i for i, s in enumerate(steps) if s.get("id") == "scope"]
    if len(gate) != 1:
        return [*problems, "exactly one gate step with id scope is required"]
    run = steps[gate[0]].get("run", "")
    if "scripts/ci_scope.py" not in run or "$GITHUB_OUTPUT" not in run or "${{" in run:
        problems.append("gate step must append ci_scope output without interpolation")
    for i, step in enumerate(steps):
        command = step.get("run", "")
        condition = step.get("if")
        if "ci_scope.py tests" in command:
            if condition != REDUCED_ONLY:
                problems.append("reduced step needs the docs_only == 'true' condition")
            if "$(python scripts/ci_scope.py tests)" not in command:
                problems.append("reduced step must take its files from ci_scope.py")
        elif any(g in command for g in GATED):
            if condition != FULL_ONLY:
                problems.append(f"full-suite step lacks the fail-safe condition: {command}")
            if i < gate[0]:
                problems.append(f"gated step precedes the gate: {command}")
        elif any(a in command for a in ALWAYS) and condition is not None:
            problems.append(f"step must always run: {command}")
    commands = " ".join(s.get("run", "") for s in steps)
    if not all(g in commands for g in GATED) or "ci_scope.py tests" not in commands:
        problems.append("expected steps are missing")
    return problems


def test_workflow_gate_shape() -> None:
    assert workflow_problems((ROOT / ".github/workflows/ci.yml").read_text()) == []


def test_workflow_shape_negative_controls() -> None:
    text = (ROOT / ".github/workflows/ci.yml").read_text()
    assert workflow_problems(text.replace("docs_only != 'true'", "docs_only == 'false'", 1))
    assert workflow_problems(text.replace("fetch-depth: 2", "fetch-depth: 1"))
    assert workflow_problems(text.replace("contents: read", "contents: write", 1))
    assert workflow_problems(text.replace("  checks:\n", "  checks:\n    if: false\n", 1))
    assert workflow_problems(
        text.replace(
            "- run: uv run --frozen python scripts/check_agent_setup.py",
            "- if: always()\n        run: uv run --frozen python scripts/check_agent_setup.py",
        )
    )
