# Issue #25 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-12.

## ISSUE-25-DEC-001 — Drop the opt-in simulator

- ID: ISSUE-25-DEC-001
- Recorded date: 2026-11-12
- Status: active for issue #25 only.
- Authority: human decision (owner chat answer, main coordinator session, 2026-11-12):
  "Simulator streichen" (English: "drop the simulator").
- Scope: the opt-in synthetic demo/simulator part of S2-LAUNCH-01 and of #25 only.
- Decision: the simulator is dropped, not deferred; it is not built and no Backlog issue is
  opened. No-hardware evidence stays with the existing test doubles in `tests/`.
- Conditions: the rest of S2-LAUNCH-01/-02 is unchanged; the owner may reinstate a simulator
  later as a new issue.
- Supersedes / superseded by: supersedes, for the simulator only, the deferral in
  [DEC-023](../DECISIONS.md#dec-023--staged-first-public-release) item 3.

## ISSUE-25-DEC-002 — Hardware use and scope of the launch-report PR

- ID: ISSUE-25-DEC-002
- Recorded date: 2026-11-13
- Status: active for issue #25 only; the hardware part is spent once the run is recorded.
- Authority: human decision (owner instruction, coordinator session, 2026-11-13).
- Scope: the launch report and prepared rollback checklist of #25. The selected test
  controller (named only in the local reference) may be used for read and write checks with a
  restorable state kept first, a small call count and the scope recorded.
- Decision: the report and checklist may be prepared, and one bounded hardware run of the
  published release 0.3.0 on that controller is authorized
  ([validation/launch-report.md](../validation/launch-report.md)).
- Not authorized: restart or rollback of the deployed service (checkbox 2 needs its own
  authorization), publication, release, tag, registry submission, MCPHub deployment,
  visibility or license change.
- Conditions: that controller and that run only; merge approval stays with the owner.
- Supersedes / superseded by: none.

## ISSUE-25-DEC-003 — Restart, rollback and hub-entry changes for the live rollback

- ID: ISSUE-25-DEC-003
- Recorded date: 2026-11-13
- Status: active for issue #25 only; exercised once on 2026-11-13 (rollback 0.3.0 to 0.2.0
  and restore; the hub entry was not changed).
- Authority: owner authorization relayed to the packet session by the coordinator in three
  messages on 2026-11-13 (recorded as relayed, not verified by this session).
- Scope: item 1 of #25 (S2-COMPAT-03, live part): back up inventory, data directory and the
  wled-mcp hub entry, roll the deployed HTTP service back to the previous release following
  DEPLOYMENT.md, check with read-only calls only, restore the release it ran before and the
  hub entry; change only the wled-mcp entry; no hostnames, addresses or credentials in files.
- Decision: the run is authorized in that scope; it stops and reports if a true rollback
  needs an artifact or choice that is not available. Rollback target: release 0.2.0, staged
  on the target first. The hub entry may be changed for this rollback (this issue only, not
  standing), only if the verification needs it, backed up first and restored afterwards; no
  other hub entry, no hub reinstall ([DEC-037](../DECISIONS.md#dec-037--no-mcphub-reinstall-in-project-steps)),
  no publish, release, tag or registry step.
- Not authorized: other hub entries; ISSUE-24-DEC-005 waiver unchanged, no fresh-install test.
- Superseded part: "restart and rollback are not authorized" of ISSUE-25-DEC-002 no longer
  holds for this scope; its hardware part is unchanged.
- Executed 2026-11-13 after the owner's "go": record in
  [validation/launch-report.md](../validation/launch-report.md#3-upgrade-and-rollback-evidence);
  the hub entry was not changed. The later update to 0.4.0
  ([validation/deploy-0.4.0.md](../validation/deploy-0.4.0.md)) ran on a separate owner
  instruction, outside this decision.
