# Issue #13 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-06.

## ISSUE-13-DEC-001 — Should/Later scope for stage 1

- ID: ISSUE-13-DEC-001
- Recorded date: 2026-11-06
- Status: active for issue #13 and the stage-1 scope boundary it defines.
- Authority/source: human decision, owner answers in the coordinator session, 2026-11-06, to two
  grouped questions of the requirements packet (Q1: option A; Q2: accept as proposed); no
  permalink.
- Scope: stage-1 inclusion/deferral of DEV-03, SEG-05, SEG-06, PRE-03, PLAY-01, ADV-01, ADV-02.
- Decision:
  - DEV-03 inventory change: stage 1 provides a documented restart procedure with rollback to the
    previous inventory file; no new code. In-process reload and a configuration validate command
    are deferred to #16.
  - SEG-05: implemented segment options count as delivered; CCT, 2D and the remaining segment
    fields are deferred to #19.
  - PRE-03 supplied-state preset save, a restore tool and playlist authoring are deferred to #18.
  - ADV-01 restricted raw state patch is excluded from stage 1; enabling it stays rejected at
    startup; no owning issue.
  - ADV-02 timers and SEG-06 pixel art/realtime streaming are excluded; no new issue.
- Conditions: stage 1 scope; deferred items are governed by their owning issues. Resolves the
  "deferred to #13" items of ISSUE-2-DEC-003, ISSUE-8-DEC-001 and ISSUE-9-DEC-001 OD-1 by moving
  them to #18. Affects DEV-03, SEG-05/06, PRE-03/04, PLAY-01, ADV-01/02, T17.

## ISSUE-13-DEC-002 — Completion handling of conditional acceptance boxes

- ID: ISSUE-13-DEC-002
- Recorded date: 2026-11-06
- Status: active for issue #13 only; technical proposal accepted by the coordinator, not a human
  decision; the owner may veto before #13 is closed.
- Decision: acceptance boxes whose condition is shown false (raw state not included; no newly
  included behavior; no scope expansion) are checked with the evidence line "not applicable:
  <reason>, ISSUE-13-DEC-001". The T17 traceability cell keeps its "not applicable" form and
  cites ISSUE-13-DEC-001.
