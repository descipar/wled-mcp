"""Issue #10: the requirement-to-evidence matrix stays complete and honest.

Runs ``scripts/check_traceability.py`` against the real documents and against synthetic
tmp copies with one defect each. The real documents are never modified.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_traceability.py"
MATRIX = (ROOT / "docs" / "TRACEABILITY.md").read_text(encoding="utf-8")
REQUIREMENTS = (ROOT / "docs" / "REQUIREMENTS.md").read_text(encoding="utf-8")


def load_checker() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_traceability", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checker = load_checker()


def row(text: str, first_cell: str) -> str:
    (line,) = [line for line in text.splitlines() if line.startswith(f"| {first_cell} |")]
    return line


def problems_for(traceability: str, requirements: str = REQUIREMENTS) -> list[str]:
    return list(checker.check_texts(requirements, traceability, ROOT))


def test_real_matrix_is_complete_and_consistent():
    assert problems_for(MATRIX) == []
    musts = checker.must_ids(REQUIREMENTS)
    assert len(musts) == 26 and len(set(musts)) == 26
    assert set(checker.table_rows(MATRIX, "Requirement")) == set(musts)
    assert set(checker.table_rows(MATRIX, "Scenario")) == {f"T{n:02d}" for n in range(1, 22)}


def test_console_script_reports_success_on_the_real_documents():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True, timeout=60, cwd=ROOT
    )
    assert result.returncode == 0, result.stderr
    assert "26 Must requirements" in result.stdout


def test_missing_must_row_fails():
    found = problems_for(MATRIX.replace(row(MATRIX, "DEV-02") + "\n", ""))
    assert "DEV-02: Must requirement has no traceability row" in found


def test_new_must_requirement_without_row_fails():
    requirements = REQUIREMENTS + "\n- **ZZZ-01 Must — Synthetic.** Example only.\n"
    assert "ZZZ-01: Must requirement has no traceability row" in problems_for(MATRIX, requirements)


def test_row_for_a_non_must_requirement_fails():
    extra = row(MATRIX, "DEV-01").replace("| DEV-01 |", "| SEG-05 |")
    found = problems_for(
        MATRIX.replace(row(MATRIX, "DEV-01"), row(MATRIX, "DEV-01") + "\n" + extra)
    )
    assert any(problem.startswith("SEG-05: row is not a Must") for problem in found)


@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        ("`tests/test_patches.py::test_does_not_exist`", "no function test_does_not_exist"),
        ("`tests/test_patches.py::test_zz_prefix_*`", "no function test_zz_prefix_*"),
        ("`tests/test_absent_file.py::test_x`", "referenced file does not exist"),
        ("`scripts/absent_script.py`", "referenced file does not exist"),
    ],
)
def test_nonexistent_evidence_reference_fails(reference, expected):
    original = row(MATRIX, "READ-02")
    mutated = original.replace("| T03 | `", f"| T03 | {reference}, `", 1)
    assert mutated != original
    found = problems_for(MATRIX.replace(original, mutated))
    assert any(problem.startswith("READ-02:") and expected in problem for problem in found)


def test_row_without_any_automated_reference_fails():
    original = row(MATRIX, "REL-03")
    cells = original.split(" | ")
    cells[2] = "documented only"
    found = problems_for(MATRIX.replace(original, " | ".join(cells)))
    assert "REL-03: no automated evidence reference" in found


def test_unmapped_scenario_fails():
    found = problems_for(MATRIX.replace(row(MATRIX, "T09") + "\n", ""))
    assert "T09: scenario is not mapped" in found


def test_t17_needs_not_applicable_or_evidence():
    original = row(MATRIX, "T17")
    found = problems_for(MATRIX.replace(original, "| T17 | automated | none | |"))
    assert "T17: no automated evidence reference" in found


@pytest.mark.parametrize(
    "cell",
    ["verified on hardware", "done", "pending", "covered by H05", "not applicable"],
)
def test_hardware_cell_outside_the_vocabulary_fails(cell):
    original = row(MATRIX, "SEG-02")
    mutated = original.replace("pending: H05 (#12)", cell)
    assert mutated != original
    found = problems_for(MATRIX.replace(original, mutated))
    assert any(problem.startswith("SEG-02: hardware/deployment cell") for problem in found)


def test_executed_result_wording_fails():
    original = row(MATRIX, "T02")
    found = problems_for(MATRIX.replace(original, original.replace("| |", "| passed on CI |")))
    assert any("executed-result wording" in problem for problem in found)


def test_console_script_fails_on_a_synthetic_defective_copy(tmp_path):
    copy = tmp_path / "TRACEABILITY.md"
    copy.write_text(MATRIX.replace(row(MATRIX, "MCP-03") + "\n", ""), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--traceability", str(copy)],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=ROOT,
    )
    assert result.returncode == 1
    assert "MCP-03: Must requirement has no traceability row" in result.stderr
    assert result.stdout == ""
    assert (ROOT / "docs" / "TRACEABILITY.md").read_text(encoding="utf-8") == MATRIX
