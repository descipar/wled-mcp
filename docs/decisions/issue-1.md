# Issue #1 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-06.

## ISSUE-1-DEC-001 — OPS-04 remainder and #44 placement at stage-1 close

- ID: ISSUE-1-DEC-001
- Recorded date: 2026-11-06
- Status: active.
- Authority: human decision (repository owner).
- Source: owner answers in the coordinator session on 2026-11-06 to two questions raised
  by the stage-1 tracker completion review (`.agent-runs/issue-1/completion-stage1.md`);
  no permalink.
- Scope: stage-1 tracker #1, requirement OPS-04 and housekeeping issue #44.
- Decision:
  - OPS-04 (Should, diagnostics): the diagnostics on main (application version,
    unknown-capability reporting, categorized error codes and safe configuration
    diagnostics) count as delivered for stage 1. The remainder, consistent and
    actionable diagnostics for every listed condition (for example unavailable backup
    storage), is explicitly deferred to #16.
  - Issue #44 (cosmetic follow-ups from the #6 review) belongs to stage 2 under #15 and
    does not block closing stage 1.
- Applicability / conditions / expiry: stage-1 close-out. The design of the deferred
  diagnostics is governed by #16.
- Rationale supplied: none beyond choosing the recommended options.
- Affected requirement IDs, files, issues and tests: OPS-04; docs/REQUIREMENTS.md,
  docs/TRACEABILITY.md; issues #1, #16, #44, #15.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: stage-1 close-out implementation, review and
  completion for #1.
- Revalidation needed / next action: record the OPS-04 status in REQUIREMENTS.md, refresh
  stale stage-1 status text, then re-run completion for #1.
