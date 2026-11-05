# Issue #10 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-05.

## ISSUE-10-DEC-001 — Traceability file, checker and restricted hardware cells

- ID: ISSUE-10-DEC-001
- Recorded date: 2026-11-05
- Status: active for issue #10 only.
- Authority: technical proposal by the requirements agent (packet technical defaults TD-1
  and TD-2), accepted by the coordinator within the human instruction to implement #10
  following the defined workflow (DEC-001). This is not a human decision; the human did
  not choose the file layout, the checker or the vocabulary.
- Source: requirements packet `.agent-runs/issue-10/packet.md` (sections 3 W6/W7 and 8),
  2026-11-05, no permalink.
- Scope: issue #10 traceability artifacts: `docs/TRACEABILITY.md`,
  `scripts/check_traceability.py`, `tests/test_traceability.py`.
- Decision: the requirement-to-evidence matrix lives in a separate
  `docs/TRACEABILITY.md` (linked from README and VALIDATION.md) rather than inside
  VALIDATION.md. A standard-library checker, run by a pytest test in ordinary CI, fails
  on a Must requirement without a row, a row or T-scenario without an existing
  `tests/...py::function` or `scripts/...` reference (functions found with `ast`, nothing
  imported), an unmapped T01–T21 (T17 may be `not applicable: ...`), executed-result
  wording in the matrix, and any hardware/deployment cell other than `pending: ...` or
  `not applicable: ...`.
- Applicability / conditions / expiry: applies while hardware/deployment evidence is
  pending. When #11 or #12 records actual evidence, that work may extend the cell
  vocabulary with an evidence link through its own reviewed change; this entry does not
  pre-approve any hardware or deployment claim.
- Rationale supplied: none by the human. Agent rationale: VALIDATION.md already combines
  the plan with historical per-candidate records, and a mechanical check keeps the matrix
  from drifting or overstating evidence.
- Affected requirement IDs, files, issues and tests: TEST-01 and every Must requirement;
  docs/TRACEABILITY.md, scripts/check_traceability.py, tests/test_traceability.py,
  docs/VALIDATION.md, README.md, .github/workflows/ci.yml, pyproject.toml; #10, #11, #12.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: packet TD-1/TD-2; implementer handoff
  `.agent-runs/issue-10/implementation.md`; reviewer through the coordinator.
- Revalidation needed / next action: independent review of the #10 candidate; a human
  may override the layout or vocabulary at any time.
