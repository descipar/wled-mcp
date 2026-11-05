"""Keep docs/TRACEABILITY.md honest against docs/REQUIREMENTS.md and the test tree.

Fails when a Must requirement has no row, a row or scenario ID appears twice, a row
has no automated reference, an Evidence cell holds anything but references, a reference
is malformed or names a missing file or test function (found with ``ast``, nothing is
imported), a scenario T01-T21 is unmapped, a hardware/deployment cell is not
``pending: ...`` or ``not applicable: ...``, or the matrix claims an outcome or result.

Evidence cells (structural rule): only backtick references separated by commas; no
free text, no leading/trailing whitespace inside the backticks. Reference forms:

- ``tests/test_<x>.py::test_<name>``: one test function;
- ``tests/test_<x>.py::test_<group>_*``: every test starting with a group stem of at
  least one ``<word>_`` part after ``test_`` (``test_T05_*``, ``test_T05_replace_*``);
  ``test_*`` and ``test_T*`` are catch-alls and rejected;
- ``scripts/<name>.py`` and ``.github/workflows/<name>.yml|yaml``: file-level only,
  directly inside that directory (no ``..`` or other path escape).

Claim rule: hardware/deployment cells, the scenario status and scenario notes must not
assert an outcome (verified, confirmed, tested, checked, accepted, observed, OK, green,
done, ...). Neutral future or negated wording is allowed when the claim word directly
follows ``be``/``not``/``yet`` (``to be done``, ``not yet tested``); base verbs such as
``complete`` or ``verify`` are not claims. "pass" wording is rejected anywhere.

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
ITEM = re.compile(r"`([^`]*)`")
EVIDENCE_PREFIXES = ("tests/", "scripts/", ".github/")
TEST_FILE = re.compile(r"^tests/(?:[A-Za-z0-9_-]+/)*test_\w+\.py$")
SCRIPT_FILE = re.compile(r"^scripts/[A-Za-z0-9_-]+\.py$")
WORKFLOW_FILE = re.compile(r"^\.github/workflows/[A-Za-z0-9_-][A-Za-z0-9_.-]*\.ya?ml$")
TEST_NAME = re.compile(r"^test_\w+$")
# One or more "<word>_" parts after "test_": test_T05_*, test_48_*, test_T05_replace_*.
TEST_GROUP = re.compile(r"^test_(?:[A-Za-z0-9]{2,}_)(?:[A-Za-z0-9]+_)*\*$")
SCENARIOS = [f"T{number:02d}" for number in range(1, 22)]
NOT_APPLICABLE = re.compile(r"^not applicable: \S")
HARDWARE_CELL = re.compile(r"^(pending: \S.*|not applicable: \S.*)$")
RESULT_CLAIM = re.compile(r"\b(pass|passes|passed|passing)\b", re.I)
# Assertive outcome words (past participles and outcome adjectives). A word directly
# after "be", "not" or "yet" is neutral future/negated wording ("to be done").
OUTCOME_CLAIM = re.compile(
    r"(?<!\bbe )(?<!\bnot )(?<!\byet )\b("
    r"verified|verifies|confirmed|confirms|succeeded|succeeds|successful(?:ly)?|success|"
    r"validated|tested|checked|accepted|observed|proven|proved|demonstrated|"
    r"done|completed|works|worked|ok|okay|green|correct|"
    r"pass|passes|passed|passing"
    r")\b",
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
    elif not (SCRIPT_FILE.match(relative) or WORKFLOW_FILE.match(relative)):
        return [
            f"{label}: file reference must be scripts/<name>.py or "
            f".github/workflows/<name>.yml: {span}"
        ]
    path = root / relative
    base = (root / relative.split("/")[0]).resolve()
    if not path.resolve().is_relative_to(base) or not path.is_file():
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
    """Structural rule: the cell is only comma-separated backtick references."""
    problems: list[str] = []
    valid = 0
    for item in (part.strip() for part in cell.split(",")) if cell.strip() else ():
        match = ITEM.fullmatch(item)
        if match is None:
            problems.append(f"{label}: evidence cell may only list backtick references: {item!r}")
            continue
        span = match.group(1)
        if span != span.strip() or not span.startswith(EVIDENCE_PREFIXES):
            problems.append(f"{label}: malformed evidence reference: {item}")
            continue
        found = check_reference(span, root, label)
        problems += found
        valid += not found
    if valid == 0:
        problems.append(f"{label}: no automated evidence reference")
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
        problems += check_claims(mapped[0], scenario, "status")
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
