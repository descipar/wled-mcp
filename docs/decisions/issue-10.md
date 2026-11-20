# Issue #10 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-05.

## ISSUE-10-DEC-001 — Traceability file, checker and restricted hardware cells

- ID: ISSUE-10-DEC-001
- Status: active for issue #10 only.
- Authority: technical proposal by the requirements agent (TD-1, TD-2), accepted by the coordinator
  under DEC-001; not a human decision. Source: #10 packet, 2026-11-05.
- Scope: `docs/TRACEABILITY.md`, `scripts/check_traceability.py`, `tests/test_traceability.py`.
- Decision: the requirement-to-evidence matrix lives in `docs/TRACEABILITY.md`, not inside
  VALIDATION.md. A standard-library checker run by a pytest test in ordinary CI fails on: a Must
  requirement without a row; a row or T-scenario without an existing `tests/...py::function` or
  `scripts/...` reference (found with `ast`, nothing imported); an unmapped T01–T21 (T17 may be
  `not applicable: ...`); executed-result wording in the matrix; any hardware/deployment cell other
  than `pending: ...` or `not applicable: ...`.
- Conditions: while hardware/deployment evidence is pending. #11 or #12 may extend the cell
  vocabulary with an evidence link through their own reviewed change; no hardware or deployment claim
  is pre-approved.
- Affected: TEST-01 and every Must requirement; #10, #11, #12. Supersedes / superseded by: none.
