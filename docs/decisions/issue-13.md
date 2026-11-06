# Issue #13 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-06.

## ISSUE-13-DEC-001 — Should/Later scope for stage 1

- ID: ISSUE-13-DEC-001
- Recorded date: 2026-11-06
- Status: active for issue #13 and the stage-1 scope boundary it defines.
- Authority: human decision (repository owner).
- Source: owner answers in the coordinator session on 2026-11-06 to two grouped
  questions based on the requirements packet `.agent-runs/issue-13/packet.md`
  (Q1: option A; Q2: accept as proposed); no permalink.
- Scope: issue #13; stage-1 inclusion/deferral of DEV-03, SEG-05, SEG-06, PRE-03,
  PLAY-01, ADV-01 and ADV-02.
- Decision:
  - DEV-03 inventory change: stage 1 provides a documented restart procedure with
    rollback to the previous inventory file; no new code. In-process reload and a
    configuration validate command are deferred to #16.
  - SEG-05: the implemented segment options count as delivered; CCT, 2D and the
    remaining segment fields are deferred to #19.
  - PRE-03 supplied-state preset save, a restore tool and playlist authoring are
    deferred to #18.
  - ADV-01 restricted raw state patch is excluded from stage 1; enabling it stays
    rejected at startup; no owning issue.
  - ADV-02 timers and SEG-06 pixel art/realtime streaming are excluded; no new issue.
- Applicability / conditions / expiry: stage 1 scope. Deferred items are governed by
  their owning stage-2 issues; this entry does not decide their design.
- Rationale supplied: the owner accepted the packet's recommendations without adding
  a separate rationale; the packet rationale (DEV-03 allows a documented restart;
  no storage-only preset path proven; raw patch needs a demonstrated gap) is agent
  analysis, not a human statement.
- Affected requirement IDs, files, issues and tests: DEV-03, SEG-05, SEG-06, PRE-03,
  PRE-04 (restore tool pointer), PLAY-01, ADV-01, ADV-02, T17; docs/REQUIREMENTS.md, docs/TOOL-CONTRACT.md,
  docs/IMPLEMENTATION-PLAN.md, docs/VALIDATION.md, docs/TRACEABILITY.md,
  docs/DEPLOYMENT.md, README.md; issues #16, #18, #19.
- Supersedes / superseded by: none. Resolves the "deferred to #13" items of
  ISSUE-2-DEC-003, ISSUE-8-DEC-001 and ISSUE-9-DEC-001 OD-1 by moving them to #18.
- Propagated to roles / packet references: implementation and review packets for #13.
- Revalidation needed / next action: documentation implementation; add deferral notes
  to #16, #18 and #19.

## ISSUE-13-DEC-002 — Completion handling of conditional acceptance boxes

- ID: ISSUE-13-DEC-002
- Recorded date: 2026-11-06
- Status: active for issue #13 only.
- Authority: technical proposal by the requirements agent, accepted by the coordinator.
  Not a human decision; the human may veto it before #13 is closed.
- Source: requirements packet `.agent-runs/issue-13/packet.md`.
- Scope: issue #13 completion.
- Decision: acceptance boxes whose condition is shown to be false (raw state not
  included; no newly included behavior; no scope expansion) are checked with an
  evidence line "not applicable: <reason>, ISSUE-13-DEC-001". The T17 traceability
  cell keeps its "not applicable" form and cites ISSUE-13-DEC-001.
- Applicability / conditions / expiry: #13 only.
- Rationale supplied: see the packet.
- Affected requirement IDs, files, issues and tests: T17; issue #13 body.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: completion for #13.
- Revalidation needed / next action: none.
