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
        ("`tests/test_patches.py::test_ZZ_*`", "no function test_ZZ_*"),
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


def problems_from_copy(tmp_path: Path, traceability: str) -> list[str]:
    """Run the checker on a synthetic tmp copy of the matrix (the real file stays intact)."""
    copy = tmp_path / "TRACEABILITY.md"
    copy.write_text(traceability, encoding="utf-8")
    return list(checker.check(ROOT, traceability=copy))


@pytest.mark.parametrize("identifier", ["DEV-01", "T05"])
def test_duplicate_row_before_the_real_one_fails(tmp_path, identifier):
    original = row(MATRIX, identifier)
    cells = original.split(" | ")
    cells[2] = "`tests/test_patches.py::test_does_not_exist`"
    bad_first = " | ".join(cells)
    found = problems_from_copy(tmp_path, MATRIX.replace(original, bad_first + "\n" + original))
    assert any(problem.startswith(f"{identifier}: duplicate row") for problem in found)


@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        ("`tests/test_patches.py`", "needs '::test_<name>'"),
        (
            "`tests/test_patches.py::test_T04_persistent_transition_is_never_in_payload"
            "::test_does_not_exist`",
            "more than one '::'",
        ),
        ("`tests/test_patches.py::test_*`", "wildcard must be a test group stem"),
        ("`tests/test_patches.py::test_T*`", "wildcard must be a test group stem"),
        ("`tests/test_patches.py::fleet`", "not a test function"),
        ("`tests/test_patches.py::call_set_state`", "not a test function"),
        ("`tests/patch_support.py::test_x`", "must name a tests/.../test_*.py file"),
        ("`scripts/check_lock.py::main`", "file-level only"),
    ],
)
def test_weak_or_malformed_reference_is_not_evidence(tmp_path, reference, expected):
    original = row(MATRIX, "READ-02")
    mutated = original.replace("| T03 | `", f"| T03 | {reference}, `", 1)
    assert mutated != original
    found = problems_from_copy(tmp_path, MATRIX.replace(original, mutated))
    assert any(problem.startswith("READ-02:") and expected in problem for problem in found)


def test_bare_test_file_alone_does_not_count_as_evidence(tmp_path):
    original = row(MATRIX, "REL-03")
    cells = original.split(" | ")
    cells[2] = "`tests/test_backups.py`"
    found = problems_from_copy(tmp_path, MATRIX.replace(original, " | ".join(cells)))
    assert any(p.startswith("REL-03:") and "needs '::test_<name>'" in p for p in found)


@pytest.mark.parametrize(
    "cell",
    [
        "pending: verified on hardware H05 (#12)",
        "pending: H05 confirmed (#12)",
        "not applicable: succeeded on the bench",
        "not applicable: hub integration OK",
        "pending: CI green, H05 (#12)",
    ],
)
def test_outcome_claim_inside_an_allowed_hardware_cell_fails(tmp_path, cell):
    original = row(MATRIX, "SEG-02")
    mutated = original.replace("pending: H05 (#12)", cell)
    assert mutated != original
    found = problems_from_copy(tmp_path, MATRIX.replace(original, mutated))
    assert any(p.startswith("SEG-02: hardware/deployment cell must not claim") for p in found)


@pytest.mark.parametrize("note", ["Verified on hardware.", "Validated on the hub.", "Done."])
def test_outcome_claim_in_scenario_notes_fails(tmp_path, note):
    original = row(MATRIX, "T02")
    mutated = original.replace("| |", f"| {note} |")
    assert mutated != original
    found = problems_from_copy(tmp_path, MATRIX.replace(original, mutated))
    assert any(p.startswith("T02: notes must not claim an outcome") for p in found)


# ----------------------------------------------------------------- review round 2


def with_reference(reference: str) -> str:
    original = row(MATRIX, "READ-02")
    mutated = original.replace("| T03 | `", f"| T03 | {reference}, `", 1)
    assert mutated != original
    return MATRIX.replace(original, mutated)


def with_hardware_cell(cell: str) -> str:
    original = row(MATRIX, "SEG-02")
    mutated = original.replace("pending: H05 (#12)", cell)
    assert mutated != original
    return MATRIX.replace(original, mutated)


def with_note(note: str) -> str:
    original = row(MATRIX, "T02")
    mutated = original.replace("| |", f"| {note} |")
    assert mutated != original
    return MATRIX.replace(original, mutated)


@pytest.mark.parametrize(
    "reference",
    [
        "`scripts/../pyproject.toml`",
        "`scripts/../tests/test_patches.py`",
        "`.github/../pyproject.toml`",
        "`.github/workflows/../../pyproject.toml`",
        "`scripts/sub/check_lock.py`",
        "`scripts/check_lock.txt`",
        "`.github/CODEOWNERS`",
    ],
)
def test_file_reference_cannot_escape_its_directory(tmp_path, reference):
    found = problems_from_copy(tmp_path, with_reference(reference))
    assert any(
        p.startswith("READ-02:") and "must be scripts/<name>.py or .github/workflows/" in p
        for p in found
    ), found


@pytest.mark.parametrize(
    ("evidence_cell", "expected"),
    [
        ("`tests/test_layouts.py::test_T05_main_id_handling` verified on hardware", "only list"),
        ("see `tests/test_layouts.py::test_T05_main_id_handling`", "only list"),
        ("`tests/test_layouts.py::test_T05_main_id_handling`, tested on H05", "only list"),
        ("` tests/test_layouts.py::test_T05_main_id_handling`", "malformed evidence reference"),
        ("`tests/test_layouts.py::test_T05_main_id_handling `", "malformed evidence reference"),
    ],
)
def test_evidence_cell_holds_only_references(tmp_path, evidence_cell, expected):
    original = row(MATRIX, "SEG-02")
    cells = original.split(" | ")
    cells[2] = evidence_cell
    found = problems_from_copy(tmp_path, MATRIX.replace(original, " | ".join(cells)))
    assert any(p.startswith("SEG-02:") and expected in p for p in found), found


@pytest.mark.parametrize(
    "cell",
    [
        "pending: tested on H05 (#12)",
        "pending: H05 checked (#12)",
        "pending: H05 accepted (#12)",
        "pending: H05 observed (#12)",
        "not applicable: observed correct",
        "not applicable: demonstrated on the bench",
    ],
)
def test_further_outcome_claims_in_hardware_cells_fail(tmp_path, cell):
    found = problems_from_copy(tmp_path, with_hardware_cell(cell))
    assert any(p.startswith("SEG-02: hardware/deployment cell must not claim") for p in found)


@pytest.mark.parametrize("note", ["Tested on the hub.", "Checked with H05.", "Accepted."])
def test_further_outcome_claims_in_notes_fail(tmp_path, note):
    found = problems_from_copy(tmp_path, with_note(note))
    assert any(p.startswith("T02: notes must not claim an outcome") for p in found)


@pytest.mark.parametrize(
    "cell",
    [
        "pending: complete H05 checklist (#12)",
        "pending: H05 to be done (#12)",
        "pending: not yet tested on hardware (#12)",
        "pending: verify and restore the layout with H05 (#12)",
        "not applicable: will be checked by #12 if hardware becomes available",
    ],
)
def test_neutral_future_wording_in_hardware_cells_is_accepted(tmp_path, cell):
    assert problems_from_copy(tmp_path, with_hardware_cell(cell)) == []


@pytest.mark.parametrize("note", ["To be done in #12.", "Complete the H05 checklist later."])
def test_neutral_future_wording_in_notes_is_accepted(tmp_path, note):
    assert problems_from_copy(tmp_path, with_note(note)) == []


@pytest.mark.parametrize(
    "reference",
    [
        "`tests/test_layouts.py::test_T05_preserved_*`",
        "`tests/test_layouts.py::test_T09_failed_post_*`",
        "`tests/test_patches.py::test_52_off_master_*`",
        "`scripts/check_lock.py`",
        "`.github/workflows/ci.yml`",
    ],
)
def test_narrow_group_wildcards_and_contained_files_are_accepted(tmp_path, reference):
    assert problems_from_copy(tmp_path, with_reference(reference)) == []


@pytest.mark.parametrize(
    "reference", ["`tests/test_layouts.py::test_*`", "`tests/test_layouts.py::test_T*`"]
)
def test_catch_all_wildcards_stay_rejected(tmp_path, reference):
    found = problems_from_copy(tmp_path, with_reference(reference))
    assert any("wildcard must be a test group stem" in p for p in found)


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
