# Issue #52 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-05.

## ISSUE-52-DEC-001 — Master power is preserved when only brightness is sent

- ID: ISSUE-52-DEC-001
- Recorded date: 2026-11-05
- Status: active for issue #52 only.
- Authority: delegated decision. The human delegated the #52/#53 decisions to the
  coordinator ("decide as much as possible yourself", 2026-11-05, no permalink). The
  content was decided by the coordinator, not dictated by the human.
- Source: requirements packet `.agent-runs/issue-52/packet.md` (recommendations D1-D8),
  pinned v0.15.1 source reading (`json.cpp` master `on = root["on"] | (bri > 0)`,
  `led.cpp` `toggleOnOff`); no hardware observation.
- Scope: master part of `wled_set_state`. Segment tools stay governed by
  [ISSUE-48-DEC-001](issue-48.md), which serves as the model, not as a binding rule.
- Decision:
  - D1: positive `brightness` with omitted `on` on an off master is compensated by
    sending `{"on": false, "bri": X}`; the master stays off with X remembered.
  - D2: `plan.targeted_compensation` is always present for `wled_set_state`: `[]` or
    `[{"on": false}]`; `plan.on` stays `null`, `plan.resolved.on` is `false`; dry run shows
    the same with zero writes.
  - D3: every master write verifies the resolved `on`; a power flip is
    `VERIFICATION_MISMATCH`, never a silent success.
  - D4: a state without a boolean master `on` is already `INVALID_RESPONSE` before
    planning; documented and covered by a regression test, no new code path.
  - D5: `tt` handling unchanged; any visible transition effect stays unverified (#12).
  - D6: existing master rejections (`on=true` with `brightness=0`, `brightness=0` without
    `on=false` on an on master) already match the contract; unchanged.
  - D7: `wled_set_state` has no segment fields; the compensating `on=false` does not
    change segment power.
  - D8: an external power change between read and write remains a documented residual
    risk, as for segments.
- Applicability / conditions: profile 0 (pinned source); revisit with #12 hardware evidence.
- Rationale: consistent with ISSUE-48-DEC-001 and the existing contract text ("positive
  brightness preserves omitted `on`", T04, CTRL-01); compensation keeps ordinary
  brightness changes usable without forcing callers to pass `on`.
- Affected: CTRL-01, T04, docs/TOOL-CONTRACT.md, docs/VALIDATION.md, docs/SOURCES.md,
  `patches.py`, tests/test_patches.py, tests/layout_support.py,
  examples/contracts/patch.json.
- Supersedes: the undocumented #6 test assertion that the master payload excludes `on`;
  no recorded decision is superseded.
- Propagated to: packet, implementer and reviewer handoffs.
