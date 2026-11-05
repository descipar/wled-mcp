"""Keep docs/TRACEABILITY.md honest against docs/REQUIREMENTS.md and the test tree.

Fails when a Must requirement has no row, a row has no automated reference, a
referenced file or test function does not exist (found with ``ast``, nothing is
imported), a scenario T01-T21 is unmapped, a hardware/deployment cell claims more
than ``pending: ...`` or ``not applicable: ...``, or the matrix claims a result.
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
REFERENCE = re.compile(r"`((?:tests|scripts|\.github)/[^`:]+)(?:::([A-Za-z_][\w]*\*?))?[^`]*`")
SCENARIOS = [f"T{number:02d}" for number in range(1, 22)]
NOT_APPLICABLE = re.compile(r"^not applicable: \S")
HARDWARE_CELL = re.compile(r"^(pending: \S.*|not applicable: \S.*)$")
RESULT_CLAIM = re.compile(r"\b(pass|passes|passed|passing)\b", re.I)


def must_ids(requirements: str) -> list[str]:
    return MUST.findall(requirements)


def table_rows(text: str, first_header: str) -> dict[str, list[str]]:
    """Rows of the Markdown table whose first header cell is ``first_header``."""
    rows: dict[str, list[str]] = {}
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
            rows[cells[0]] = cells[1:]
    return rows


@functools.cache
def test_names(path: Path) -> frozenset[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return frozenset(
        node.name for node in tree.body if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    )


def check_references(cell: str, root: Path, label: str) -> list[str]:
    problems: list[str] = []
    references = REFERENCE.findall(cell)
    if not references:
        problems.append(f"{label}: no automated evidence reference")
    for relative, function in references:
        path = root / relative
        if not path.is_file():
            problems.append(f"{label}: referenced file does not exist: {relative}")
            continue
        if not function:
            continue
        names = test_names(path)
        found = (
            any(name.startswith(function[:-1]) for name in names)
            if function.endswith("*")
            else function in names
        )
        if not found:
            problems.append(f"{label}: no function {function} in {relative}")
    return problems


def check_texts(requirements: str, traceability: str, root: Path) -> list[str]:
    problems: list[str] = []
    musts = must_ids(requirements)
    if not musts:
        problems.append("REQUIREMENTS: no Must requirement found")
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
    scenarios = table_rows(traceability, "Scenario")
    for scenario in SCENARIOS:
        mapped = scenarios.get(scenario)
        if mapped is None:
            problems.append(f"{scenario}: scenario is not mapped")
            continue
        if len(mapped) != 3:
            problems.append(f"{scenario}: expected Status, Evidence and Notes cells")
            continue
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
