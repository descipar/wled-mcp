# Issue #1 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-06.

## ISSUE-1-DEC-001 — OPS-04 remainder and #44 placement at stage-1 close

- ID: ISSUE-1-DEC-001
- Status: active.
- Authority: human decision (repository owner), answers in the coordinator session on 2026-11-06 to
  two questions of the stage-1 completion review; no permalink.
- Scope: stage-1 tracker #1, requirement OPS-04 and issue #44.
- Decision: OPS-04 (Should, diagnostics): the diagnostics on main (application version,
  unknown-capability reporting, categorized error codes, safe configuration diagnostics) count as
  delivered for stage 1; consistent actionable diagnostics for every listed condition (for example
  unavailable backup storage) are deferred to #16. Issue #44 (cosmetic #6 follow-ups) belongs to
  stage 2 under #15 and does not block closing stage 1.
- Conditions: stage-1 close-out; the deferred diagnostics design is governed by #16.
- Affected: OPS-04; REQUIREMENTS.md, TRACEABILITY.md; #1, #16, #44, #15. Supersedes: none.
