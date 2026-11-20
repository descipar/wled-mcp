# Issue #52 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-05.

## ISSUE-52-DEC-001 — Master power is preserved when only brightness is sent

- ID: ISSUE-52-DEC-001
- Status: active for issue #52 only.
- Authority: delegated decision; the owner delegated the #52/#53 decisions to the coordinator
  ("decide as much as possible yourself", 2026-11-05, no permalink). Based on the requirements
  packet (D1-D8) and the pinned v0.15.1 source; no hardware observation.
- Scope: master part of `wled_set_state`; segment tools follow
  [ISSUE-48-DEC-001](issue-48.md) as a model only.
- Decision:
  - D1: positive `brightness` with omitted `on` on an off master sends `{"on": false, "bri": X}`;
    the master stays off with X remembered.
  - D2: `plan.targeted_compensation` is always present: `[]` or `[{"on": false}]`; `plan.on` stays
    `null`, `plan.resolved.on` is `false`; dry run shows the same with zero writes.
  - D3: every master write verifies the resolved `on`; a power flip is `VERIFICATION_MISMATCH`.
  - D4: a state without a boolean master `on` is already `INVALID_RESPONSE` before planning.
  - D5: `tt` unchanged; transition effect stays unverified (#12).
  - D6: existing master rejections (`on=true` with `brightness=0`; `brightness=0` without `on=false`
    on an on master) unchanged.
  - D7: `wled_set_state` has no segment fields; the compensating `on=false` leaves segment power alone.
  - D8: an external power change between read and write remains a documented residual risk.
- Conditions: profile 0 (pinned source); revisit with #12 hardware evidence.
- Affected: CTRL-01, T04, `patches.py`, TOOL-CONTRACT. Supersedes: no recorded decision.
