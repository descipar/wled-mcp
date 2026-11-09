"""Issue #94: the WLED feature coverage list and its figures stay derived and honest.

Runs ``scripts/check_coverage.py`` against the real documents, the real tool registry
and the real CLI parser, and against copies with exactly one defect each. Figures are
tested on synthetic tables, not on the current percentages. The real documents are never
modified; ``--update`` runs only on tmp copies. No device, LAN or GitHub access.
"""

from __future__ import annotations

import argparse
import importlib.util
import socket
import subprocess
import sys
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from types import ModuleType

import pytest

from tests.test_readme import link_problems

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_coverage.py"
COVERAGE_PATH = ROOT / "docs" / "WLED-COVERAGE.md"
COVERAGE = COVERAGE_PATH.read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")


def load_checker() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_coverage", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve their module by name
    spec.loader.exec_module(module)
    return module


checker = load_checker()
CONTEXT = checker.load_context(ROOT)


def row(text: str, row_id: str) -> str:
    (line,) = [line for line in text.splitlines() if line.startswith(f"| {row_id} |")]
    return line


def edit_row(text: str, row_id: str, **changes: str) -> str:
    """The document with named cells of one row replaced."""
    line = row(text, row_id)
    cells = checker.cells(line)
    for name, value in changes.items():
        cells[checker.HEADER.index(name)] = value
    return text.replace(line, "| " + " | ".join(cells) + " |")


def problems(coverage: str = COVERAGE, readme: str = README, context=CONTEXT) -> list[str]:
    """Problems after regenerating the figure blocks, so only the edited check fires."""
    coverage, readme = checker.update_texts(coverage, readme)
    return checker.check_texts(coverage, readme, context)


# --- T94-01, T94-10, T94-11: the real documents --------------------------------------


def test_real_list_passes_every_check():
    assert checker.check_texts(COVERAGE, README, CONTEXT) == []


def test_real_rows_use_every_status_and_area_and_place_every_tool():
    rows, structure = checker.parse_rows(COVERAGE)
    assert structure == []
    # Since #16 delivered W-INFO-09 no real row is "planned"; that status stays valid and
    # is exercised by the synthetic rows below (test_planned_* and the C-rule tests).
    statuses = {r.status for r in rows}
    assert statuses <= set(checker.STATUSES)
    assert set(checker.STATUSES) - statuses <= {"planned"}
    assert {r.area for r in rows} == set(checker.AREAS)
    placed = {ref for r in rows if r.status in checker.DELIVERING for ref in r.references}
    server_only = set(checker.server_only_tools(COVERAGE))
    assert not placed & server_only  # a server-only tool has no WLED feature row
    assert CONTEXT.tools and CONTEXT.tools <= placed | server_only


def test_console_script_reports_success_on_the_real_documents():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True, timeout=120, cwd=ROOT
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("WLED coverage: ")


def test_coverage_links_and_anchors_resolve():
    assert link_problems(COVERAGE_PATH, COVERAGE) == []


def test_readme_links_the_list_inside_the_generated_line():
    assert "docs/WLED-COVERAGE.md" in checker.block(README)
    assert (
        "(https://github.com/descipar/wled-mcp/blob/main/docs/WLED-COVERAGE.md)"
        in (README.split("## Documentation", 1)[1])
    )


def test_loading_the_context_resolves_no_name_and_connects_nowhere(monkeypatch):
    connect = socket.socket.connect

    def refuse(*args, **kwargs):
        raise AssertionError("the coverage check tried a network lookup or connection")

    def loopback_only(sock, address):
        # The Windows event loop builds its internal self-pipe over a loopback pair.
        if address[0] not in ("127.0.0.1", "::1"):
            refuse()
        return connect(sock, address)

    monkeypatch.setattr(socket.socket, "connect", loopback_only)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    context = checker.load_context(ROOT)
    assert checker.check_texts(COVERAGE, README, context) == []


# --- T94-02: stale figures and --update ----------------------------------------------


def copies(tmp_path: Path, coverage: str, readme: str = README) -> tuple[Path, Path]:
    (tmp_path / "docs").mkdir()
    coverage_path = tmp_path / "docs" / "WLED-COVERAGE.md"
    readme_path = tmp_path / "README.md"
    coverage_path.write_text(coverage, encoding="utf-8", newline="\n")
    readme_path.write_text(readme, encoding="utf-8", newline="\n")
    return coverage_path, readme_path


def outside_block(text: str) -> tuple[str, str]:
    before, _, rest = text.partition(checker.START)
    return before, rest.partition(checker.END)[2]


def test_status_change_without_update_fails_and_update_repairs_only_the_blocks(tmp_path, capsys):
    changed = edit_row(COVERAGE, "W-STATE-01", Status="partial")
    found = checker.check_texts(changed, README, CONTEXT)
    assert "C8 docs/WLED-COVERAGE.md: figure block is stale; run check_coverage.py --update" in (
        found
    )
    assert "C8 README.md: figure block is stale; run check_coverage.py --update" in found
    assert len(found) == 2

    coverage_path, readme_path = copies(tmp_path, changed)
    args = ["--coverage", str(coverage_path), "--readme", str(readme_path)]
    assert checker.main(args) == 1
    assert checker.main([*args, "--update"]) == 0
    updated = coverage_path.read_text(encoding="utf-8")
    updated_readme = readme_path.read_text(encoding="utf-8")
    assert outside_block(updated) == outside_block(changed)
    assert outside_block(updated_readme) == outside_block(README)
    assert checker.block(updated) != checker.block(COVERAGE)
    assert checker.main(args) == 0
    capsys.readouterr()


def test_missing_markers_fail_and_update_refuses_to_guess(tmp_path):
    readme = README.replace(checker.START + "\n", "", 1)
    assert "C8 README.md: missing or repeated wled-coverage markers" in problems(readme=readme)
    coverage_path, readme_path = copies(tmp_path, COVERAGE, readme)
    args = ["--coverage", str(coverage_path), "--readme", str(readme_path), "--update"]
    assert checker.main(args) == 1
    assert readme_path.read_text(encoding="utf-8") == readme


# --- T94-03: figures on synthetic tables ---------------------------------------------

SYNTHETIC_HEAD = (
    "| ID | Feature | WLED key / route | Status | Delivered by | Link | Notes |\n"
    "| --- | --- | --- | --- | --- | --- | --- |\n"
)


def synthetic(*statuses: tuple[str, str]) -> list:
    lines = [
        f"| W-{area}-{index:02d} | Feature | `key` | {status} | - | - | - |"
        for index, (area, status) in enumerate(statuses, start=1)
    ]
    rows, structure = checker.parse_rows(SYNTHETIC_HEAD + "\n".join(lines))
    assert structure == []
    return rows


def test_figures_weigh_partial_half_and_drop_excluded_from_the_planned_scope():
    rows = synthetic(
        *[("SEG", "supported")] * 3,
        *[("SEG", "partial")] * 2,
        ("SEG", "excluded"),
        ("SEG", "planned"),
        ("SEG", "unplanned"),
    )
    overall, areas = checker.tally(rows)
    assert (overall.score, overall.total, overall.in_scope) == (4, 8, 7)
    assert (overall.overall, overall.planned_scope) == (50, 57)
    assert areas["SEG"].by_status == overall.by_status
    assert checker.readme_block(rows).startswith(
        "WLED feature coverage: 57 % of the planned scope, 50 % of WLED overall "
    )


def test_figures_per_area_round_half_up_and_show_na_without_scope():
    rows = synthetic(
        ("STATE", "partial"),
        *[("STATE", "unplanned")] * 3,
        ("SYS", "excluded"),
        ("SYS", "excluded"),
    )
    _, areas = checker.tally(rows)
    assert (areas["STATE"].overall, areas["STATE"].planned_scope) == (13, 13)  # 12.5 %
    assert (areas["SYS"].overall, areas["SYS"].planned_scope) == (0, None)
    text = checker.coverage_block(rows)
    assert "| Master state (STATE) | 4 | 0 | 1 | 0 | 3 | 0 | 13 % | 13 % |" in text
    assert "| System and maintenance (SYS) | 2 | 0 | 0 | 0 | 0 | 2 | n/a | 0 % |" in text
    assert "(0.5 of 6 features)" in text and "(0.5 of 4 features" in text
    assert "Segments (SEG)" not in text  # areas without rows are not shown


@pytest.mark.parametrize(
    ("score", "denominator", "expected"),
    [
        (Fraction(1, 2), 4, 13),  # 12.5 rounds up
        (Fraction(5, 2), 8, 31),  # 31.25 rounds down
        (Fraction(7, 2), 4, 88),  # 87.5 rounds up
        (Fraction(1, 3), 1, 33),
        (Fraction(0), 3, 0),
        (Fraction(1), 0, None),
    ],
)
def test_percent_rounds_half_up(score, denominator, expected):
    assert checker.percent(score, denominator) == expected


# --- T94-04, T94-05: tools and CLI commands ------------------------------------------


def test_unregistered_tool_fails_c3():
    # A synthetic name that no registry provides.
    assert "wled_synthetic_unregistered" not in CONTEXT.tools
    changed = edit_row(COVERAGE, "W-PRESET-06", **{"Delivered by": "`wled_synthetic_unregistered`"})
    found = problems(changed)
    assert "C3 W-PRESET-06: wled_synthetic_unregistered is not a registered tool" in found
    assert any(p.startswith("C7 wled_delete_preset:") for p in found)


def test_unknown_cli_command_fails_c3_and_a_known_one_passes():
    unknown = edit_row(
        COVERAGE, "W-INFO-03", **{"Delivered by": "`wled_list_devices`, `cli: wled-mcp frobnicate`"}
    )
    assert "C3 W-INFO-03: 'wled-mcp frobnicate' is not a CLI command" in problems(unknown)
    changed = edit_row(
        COVERAGE, "W-INFO-03", **{"Delivered by": "`wled_list_devices`, `cli: wled-mcp discover`"}
    )
    nested = replace(
        CONTEXT, cli_commands=frozenset({("discover",), ("config",), ("config", "validate")})
    )
    assert problems(changed, context=nested) == []
    changed = edit_row(
        COVERAGE, "W-INFO-03", **{"Delivered by": "`wled_list_devices`, `cli: wled-mcp config`"}
    )
    assert problems(changed, context=nested) == []
    changed = edit_row(COVERAGE, "W-INFO-03", **{"Delivered by": "`wled_list_devices`, `doctor`"})
    assert "C3 W-INFO-03: unrecognized reference 'doctor'" in problems(changed, context=nested)


def test_cli_commands_reads_nested_subcommands_from_a_parser_builder(monkeypatch):
    from wled_mcp import cli

    def build_parser() -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser()
        commands = parser.add_subparsers()
        commands.add_parser("discover")
        config = commands.add_parser("config").add_subparsers()
        config.add_parser("validate")
        return parser

    monkeypatch.setattr(cli, "build_parser", build_parser, raising=False)
    assert checker.cli_commands() == {("discover",), ("config",), ("config", "validate")}


def test_cli_commands_reads_the_real_parser_without_output(capsys):
    commands = checker.cli_commands()
    assert all(isinstance(command, tuple) and command for command in commands)
    assert capsys.readouterr() == ("", "")


def test_registered_tool_without_a_row_fails_c7_and_the_server_only_list_places_it():
    changed = edit_row(COVERAGE, "W-CAT-01", Status="unplanned", **{"Delivered by": "-"})
    changed = edit_row(changed, "W-CAT-02", Status="unplanned", **{"Delivered by": "-"})
    message = (
        "C7 wled_get_effects: registered tool is in no supported/partial row and not listed "
        "as server-only"
    )
    assert problems(changed) == [message]
    listed = changed.replace(
        checker.SERVER_ONLY + "\n",
        checker.SERVER_ONLY + "\n\n- `wled_get_effects`: synthetic reason.\n",
        1,
    )
    assert problems(listed) == []


def test_server_only_entry_for_an_unregistered_tool_fails_c7():
    changed = COVERAGE.replace(
        checker.SERVER_ONLY + "\n",
        checker.SERVER_ONLY + "\n\n- `wled_synthetic_unregistered`: synthetic reason.\n",
        1,
    )
    assert problems(changed) == [
        "C7 wled_synthetic_unregistered: listed as server-only but not registered"
    ]


def test_supported_row_without_a_reference_fails_c3():
    changed = edit_row(COVERAGE, "W-STATE-03", **{"Delivered by": "-"})
    assert "C3 W-STATE-03: supported row names no tool or CLI command" in problems(changed)
    changed = edit_row(COVERAGE, "W-STATE-03", **{"Delivered by": "wled_set_state"})
    assert "C3 W-STATE-03: Delivered by must be backticked references or -" in problems(changed)


# --- T94-06: planned rows ------------------------------------------------------------


@pytest.mark.parametrize(
    ("link", "expected"),
    [
        ("-", "C5 W-SEG-14: planned row must link exactly one issue"),
        (
            "[#18](https://github.com/descipar/wled-mcp/issues/18), "
            "[#19](https://github.com/descipar/wled-mcp/issues/19)",
            "C5 W-SEG-14: planned row must link exactly one issue",
        ),
        (
            "[#94](https://github.com/descipar/wled-mcp/issues/94)",
            "C5 W-SEG-14: issue #94 is not in the stage-2/3 maps",
        ),
        (
            "[#15](https://github.com/descipar/wled-mcp/issues/15)",
            "C5 W-SEG-14: issue #15 is not in the stage-2/3 maps",
        ),
    ],
)
def test_planned_row_needs_one_roadmap_issue(link, expected):
    # The row is made planned explicitly; its live status changes as #19 progresses.
    row = {"Status": "planned", "Delivered by": "-", "Link": link}
    assert problems(edit_row(COVERAGE, "W-SEG-14", **row)) == [expected]


def test_roadmap_issues_come_from_the_stage_maps():
    assert {16, 17, 18, 19, 20, 27, 31} <= CONTEXT.roadmap_issues
    assert not {1, 15, 26} & CONTEXT.roadmap_issues  # trackers are not owners


def test_planned_row_with_a_reference_fails_c4():
    # Status and link are set explicitly: W-SEG-14 itself is supported since #19.
    row = {
        "Status": "planned",
        "Delivered by": "`wled_patch_segments`",
        "Link": "[#19](https://github.com/descipar/wled-mcp/issues/19)",
    }
    changed = edit_row(COVERAGE, "W-SEG-14", **row)
    assert problems(changed) == ["C4 W-SEG-14: planned row must not name a Delivered by reference"]


@pytest.mark.parametrize("status", ["unplanned", "excluded"])
def test_non_delivering_row_with_a_reference_fails_c4(status):
    changed = edit_row(COVERAGE, "W-SYS-01", Status=status, **{"Delivered by": "`wled_set_state`"})
    assert f"C4 W-SYS-01: {status} row must not name a Delivered by reference" in problems(changed)


# --- T94-07: excluded rows -----------------------------------------------------------


@pytest.mark.parametrize(
    ("link", "expected"),
    [
        ("-", "C6 W-SEG-24: excluded row links no decision"),
        ("ISSUE-19-DEC-099", "C6 W-SEG-24: decision ISSUE-19-DEC-099 has no recorded entry"),
        ("DEC-999", "C6 W-SEG-24: decision DEC-999 has no recorded entry"),
    ],
)
def test_excluded_row_needs_an_existing_decision(link, expected):
    assert problems(edit_row(COVERAGE, "W-SEG-24", Link=link)) == [expected]


def test_excluded_row_with_a_superseded_decision_fails_c6():
    # A real entry whose recorded status is "superseded ... by ISSUE-48-DEC-001".
    assert checker.superseded(CONTEXT.decisions["ISSUE-7-DEC-006"])
    changed = edit_row(COVERAGE, "W-SEG-24", Link="ISSUE-7-DEC-006")
    assert problems(changed) == ["C6 W-SEG-24: decision ISSUE-7-DEC-006 is superseded"]


def test_decision_entries_read_shared_and_issue_records():
    decisions = CONTEXT.decisions
    assert decisions["DEC-020"].startswith("active")
    assert decisions["ISSUE-13-DEC-001"].startswith("active")
    assert decisions["ISSUE-19-DEC-002"].startswith("active")
    assert decisions["ISSUE-94-DEC-001"].startswith("active")
    assert not checker.superseded(decisions["ISSUE-12-DEC-001"])  # "superseded in part"
    assert not checker.superseded("active for issue #12 only, superseded in part (TD-12-1)")


# --- T94-08: structure ---------------------------------------------------------------


def test_duplicate_row_id_fails_c1():
    line = row(COVERAGE, "W-UM-01")
    changed = COVERAGE.replace(line, line + "\n" + line)
    assert "C1 W-UM-01: duplicate row ID" in problems(changed)


def test_unknown_status_fails_c2():
    changed = edit_row(COVERAGE, "W-UM-01", Status="maybe")
    assert "C2 W-UM-01: unknown status 'maybe'" in problems(changed)


def test_malformed_header_fails_c1():
    header = "| ID | Feature | WLED key / route | Status | Delivered by | Link | Notes |"
    changed = COVERAGE.replace(header, header.replace("| Link |", "| Issue |"), 1)
    assert any(p.startswith("C1 line ") and "table header differs" in p for p in problems(changed))


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ("| W-UM-01 |", "| W-XX-01 |", "C1 line"),
        ("| W-UM-01 |", "| W-UM-1 |", "C1 line"),
        ("| W-UM-01 | Usermod state, information and settings |", "| W-UM-01 | - |", "C1 W-UM-01"),
    ],
)
def test_malformed_ids_and_empty_cells_fail_c1(old, new, expected):
    found = problems(COVERAGE.replace(old, new, 1))
    assert any(p.startswith(expected) for p in found), found


# --- T94-09: basis -------------------------------------------------------------------


def test_basis_without_a_recorded_commit_fails_c9():
    commit = "29b389df1c1aaec6ff53aea742d17063b985906c"
    assert commit in CONTEXT.sources
    changed = COVERAGE.replace(commit, "0" * 40, 1)
    assert problems(changed) == ["C9: Basis names no WLED commit recorded in docs/SOURCES.md"]


def test_basis_without_the_firmware_floor_fails_c9():
    changed = COVERAGE.replace("WLED 16.0.0", "WLED 0.15.0", 1)
    assert problems(changed) == ["C9: Basis does not state the WLED 16.0.0 floor (DEC-020)"]
    changed = COVERAGE.replace("**Basis:**", "Basis:", 1)
    assert problems(changed) == ["C9: no **Basis:** paragraph"]
