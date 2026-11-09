"""Decide whether a pull request changes documentation only (issue #159).

``python scripts/ci_scope.py`` prints ``docs_only=true|false`` and ``reason=...`` for
``$GITHUB_OUTPUT`` and always exits 0: any doubt (other event, git failure, unexpected
commit shape, empty diff, non-document path) yields ``false`` and the workflow then runs
the complete suite. ``python scripts/ci_scope.py tests`` prints the test files of the
reduced documentation run.
"""

import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import PurePosixPath

# Test files that read repository documents. ``tests/test_ci_scope.py`` keeps this list
# and ``DOC_READER_EXCLUSIONS`` complete with a static scan (drift guard).
DOC_READER_TESTS: tuple[str, ...] = (
    "tests/test_acceptance_parity.py",
    "tests/test_coverage.py",
    "tests/test_deployment_artifacts.py",
    "tests/test_diagnostics.py",
    "tests/test_private_identifiers.py",
    "tests/test_readme.py",
    "tests/test_registry_metadata.py",
    "tests/test_traceability.py",
    "tests/test_upgrade_compat.py",
    "tests/test_version_source.py",
)

# Files that mention document paths without reading a repository document, or that run
# as a direct workflow step or through one of the tests above.
DOC_READER_EXCLUSIONS: dict[str, str] = {
    "tests/test_backups.py": "path-prefix check on `git ls-files`; never opens a document",
    "tests/test_gitattributes.py": "`git check-attr` on a path; depends on .gitattributes only",
    "tests/test_check_distribution.py": "synthetic sdist member names",
    "tests/test_scene_store.py": "synthetic file name in a temporary directory",
    "tests/test_sync_agents.py": "builds its own temporary tree; real tree via check_agent_setup",
    "tests/test_ci_scope.py": "reads only the workflow file and synthetic trees",
    "scripts/ci_scope.py": "classifies path strings; reads no document",
    "scripts/sync_agents.py": "exercised through check_agent_setup, a direct step",
    "scripts/check_agent_setup.py": "direct step of the reduced run",
    "scripts/check_coverage.py": "exercised through tests/test_coverage.py",
    "scripts/check_traceability.py": "exercised through tests/test_traceability.py",
    "scripts/check_private_identifiers.py": "direct step of the reduced run",
}

_Entry = tuple[str, str, str]  # (status, mode, path) from `git diff --raw`
_Run = Callable[..., "subprocess.CompletedProcess[str]"]


def _is_doc_path(path: str) -> bool:
    parts = PurePosixPath(path).parts
    if not parts or path.startswith("/") or any(p.startswith(".") for p in parts):
        return False
    if not path.endswith(".md"):
        return False
    return len(parts) == 1 or parts[0] == "docs"


def classify_paths(entries: Sequence[_Entry]) -> tuple[bool, str]:
    """Documentation only: every entry is a plain markdown document, none empty."""
    if not entries:
        return False, "empty diff"
    for status, mode, path in entries:
        if not _is_doc_path(path):
            return False, f"not a documentation path: {path!r}"
        if status != "D" and mode != "100644":
            return False, f"unexpected file mode {mode}: {path!r}"
    return True, f"{len(entries)} documentation path(s)"


def changed_entries(run: _Run = subprocess.run) -> list[_Entry]:
    """Entries of the merge commit against its first parent; raise when undeterminable."""
    parents = run(
        ["git", "rev-list", "--parents", "-n", "1", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    ).stdout.split()
    if len(parents) != 3:  # the commit and exactly two parents
        raise ValueError(f"expected a merge commit with two parents, found {len(parents) - 1}")
    raw = run(
        ["git", "diff", "--raw", "-z", "--no-abbrev", "--no-renames", "HEAD^1", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    ).stdout
    fields = raw.split("\0")
    entries: list[_Entry] = []
    index = 0
    while index < len(fields) and fields[index]:
        meta = fields[index].lstrip(":").split()
        entries.append((meta[4][0], meta[1], fields[index + 1]))
        index += 2
    return entries


def decide(event: str, run: _Run = subprocess.run) -> tuple[bool, str]:
    if event != "pull_request":
        return False, f"event {event or 'unknown'} runs the complete suite"
    try:
        return classify_paths(changed_entries(run))
    except Exception as error:  # fail safe: any doubt means the complete suite
        return False, f"undeterminable: {type(error).__name__}"


def main(argv: Sequence[str], env: dict[str, str]) -> int:
    if list(argv) == ["tests"]:
        print(" ".join(DOC_READER_TESTS))
        return 0
    docs_only, reason = decide(env.get("GITHUB_EVENT_NAME", ""))
    print(f"docs_only={'true' if docs_only else 'false'}")
    print(f"reason={reason}")
    print(f"scope: docs_only={docs_only} ({reason})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    import os

    sys.exit(main(sys.argv[1:], dict(os.environ)))
