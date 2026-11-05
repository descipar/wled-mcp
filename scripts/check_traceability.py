"""Keep docs/TRACEABILITY.md honest against docs/REQUIREMENTS.md and the test tree.

Fails when a Must requirement has no row, a row or scenario ID appears twice, a row
has no automated reference, a reference is malformed or names a missing file or test
function (found with ``ast``, nothing is imported), a scenario T01-T21 is unmapped, a
hardware/deployment cell claims more than ``pending: ...`` or ``not applicable: ...``,
or the matrix claims a result.

Reference forms: ``tests/test_<x>.py::test_<name>`` names one test function;
``tests/test_<x>.py::test_<group>_*`` names every test whose name starts with a group
stem such as ``test_T05_`` or ``test_48_``. ``scripts/<x>.py`` and ``.github/...``
references are file-level only.

Standard library only; exit code 0 on success, 1 with findings on stderr.
"""

from __future__ import annotations

import argparse
import ast
import functools
import re
import sys
from pathlib import Path

MUST = re.compile(r"^- \*\*([A-Z]+-\d{2}) Must\b", re.M)
SPAN = re.compile(r"`([^`]*)`")
EVIDENCE_PREFIXES = ("tests/", "scripts/", ".github/")
TEST_FILE = re.compile(r"^tests/(?:[\w-]+/)*test_\w+\.py$")
TEST_NAME = re.compile(r"^test_\w+$")
TEST_GROUP = re.compile(r"^test_[A-Za-z0-9]{2,}_\*$")  # e.g. test_T05_*, test_48_*
SCENARIOS = [f"T{number:02d}" for number in range(1, 22)]
NOT_APPLICABLE = re.compile(r"^not applicable: \S")
HARDWARE_CELL = re.compile(r"^(pending: \S.*|not applicable: \S.*)$")
RESULT_CLAIM = re.compile(r"\b(pass|passes|passed|passing)\b", re.I)
# Hardware/deployment cells and scenario notes must not claim an outcome.
OUTCOME_CLAIM = re.compile(
    r"\b(verified|confirmed|succeeded|successful(?:ly)?|success|ok|green|validated|"
    r"done|completed?|works|worked|proven)\b",
    re.I,
)


def must_ids(requirements: str) -> list[str]:
    return MUST.findall(requirements)


def table_entries(text: str, first_header: str) -> list[tuple[str, list[str]]]:
    """Rows, in order, of the Markdown table whose first header cell is ``first_header``."""
    entries: list[tuple[str, list[str]]] = []
    inside = False
    for line in text.splitlines():
        if not line.startswith("|"):
            inside = False
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells[0] == first_header:
            inside = True
            continue
        if inside and not set(cells[0]) <= {"-", ":", " "}:
            entries.append((cells[0], cells[1:]))
    return entries


def table_rows(text: str, first_header: str) -> dict[str, list[str]]:
    return dict(table_entries(text, first_header))


def duplicate_ids(text: str, first_header: str) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for identifier, _cells in table_entries(text, first_header):
        if identifier in seen and identifier not in duplicates:
            duplicates.append(identifier)
        seen.add(identifier)
    return duplicates


@functools.cache
def test_names(path: Path) -> frozenset[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return frozenset(
        node.name for node in tree.body if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    )


def check_reference(span: str, root: Path, label: str) -> list[str]:
    relative, _, function = span.partition("::")
    if "::" in function:
        return [f"{label}: more than one '::' in one reference: {span}"]
    if relative.startswith("tests/"):
        if not TEST_FILE.match(relative):
            return [f"{label}: test reference must name a tests/.../test_*.py file: {span}"]
        if not function:
            return [f"{label}: test reference needs '::test_<name>': {span}"]
        if function.endswith("*"):
            if not TEST_GROUP.match(function):
                return [f"{label}: wildcard must be a test group stem such as test_T05_*: {span}"]
        elif not TEST_NAME.match(function):
            return [f"{label}: referenced name is not a test function: {span}"]
    elif function:
        return [f"{label}: scripts/ and .github/ references are file-level only: {span}"]
    path = root / relative
    if not path.is_file():
        return [f"{label}: referenced file does not exist: {relative}"]
    if not function:
        return []
    names = test_names(path)
    found = (
        any(name.startswith(function[:-1]) for name in names)
        if function.endswith("*")
        else function in names
    )
    return [] if found else [f"{label}: no function {function} in {relative}"]


def check_references(cell: str, root: Path, label: str) -> list[str]:
    spans = [span for span in SPAN.findall(cell) if span.startswith(EVIDENCE_PREFIXES)]
    if not spans:
        return [f"{label}: no automated evidence reference"]
    problems: list[str] = []
    for span in spans:
        problems += check_reference(span, root, label)
    return problems


def check_claims(cell: str, label: str, kind: str) -> list[str]:
    claim = OUTCOME_CLAIM.search(cell)
    if claim is None:
        return []
    return [f"{label}: {kind} must not claim an outcome ({claim.group()!r})"]


def check_texts(requirements: str, traceability: str, root: Path) -> list[str]:
    problems: list[str] = []
    musts = must_ids(requirements)
    if not musts:
        problems.append("REQUIREMENTS: no Must requirement found")
    for header in ("Requirement", "Scenario"):
        for identifier in duplicate_ids(traceability, header):
            problems.append(f"{identifier}: duplicate row in the {header} table")
    rows = table_rows(traceability, "Requirement")
    for must in musts:
        if must not in rows:
            problems.append(f"{must}: Must requirement has no traceability row")
    for requirement, cells in rows.items():
        if requirement not in musts:
            problems.append(f"{requirement}: row is not a Must requirement in REQUIREMENTS.md")
        if len(cells) != 3:
            problems.append(f"{requirement}: expected Scenarios, Evidence and Hardware cells")
            continue
        problems += check_references(cells[1], root, requirement)
        if not HARDWARE_CELL.match(cells[2]):
            problems.append(
                f"{requirement}: hardware/deployment cell must be 'pending: ...' or "
                f"'not applicable: ...', found {cells[2]!r}"
            )
        problems += check_claims(cells[2], requirement, "hardware/deployment cell")
    scenarios = table_rows(traceability, "Scenario")
    for scenario in SCENARIOS:
        mapped = scenarios.get(scenario)
        if mapped is None:
            problems.append(f"{scenario}: scenario is not mapped")
            continue
        if len(mapped) != 3:
            problems.append(f"{scenario}: expected Status, Evidence and Notes cells")
            continue
        problems += check_claims(mapped[2], scenario, "notes")
        if scenario == "T17" and NOT_APPLICABLE.match(mapped[0]):
            continue
        if mapped[0] not in {"automated", "automated, partly deferred"}:
            problems.append(f"{scenario}: unexpected status {mapped[0]!r}")
        problems += check_references(mapped[1], root, scenario)
    for number, line in enumerate(traceability.splitlines(), start=1):
        if RESULT_CLAIM.search(line):
            problems.append(f"TRACEABILITY.md:{number}: executed-result wording is not allowed")
    return problems


def check(
    root: Path, requirements: Path | None = None, traceability: Path | None = None
) -> list[str]:
    requirements = requirements or root / "docs" / "REQUIREMENTS.md"
    traceability = traceability or root / "docs" / "TRACEABILITY.md"
    return check_texts(
        requirements.read_text(encoding="utf-8"),
        traceability.read_text(encoding="utf-8"),
        root,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check docs/TRACEABILITY.md.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--requirements", type=Path, help="Override docs/REQUIREMENTS.md.")
    parser.add_argument("--traceability", type=Path, help="Override docs/TRACEABILITY.md.")
    args = parser.parse_args(argv)
    requirements = args.requirements or args.root / "docs" / "REQUIREMENTS.md"
    problems = check(args.root, requirements, args.traceability)
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        return 1
    count = len(must_ids(requirements.read_text(encoding="utf-8")))
    print(f"Traceability: {count} Must requirements and T01-T21 mapped to existing evidence.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
