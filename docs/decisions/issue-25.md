# Issue #25 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-12.

## ISSUE-25-DEC-001 — Drop the opt-in simulator

- ID: ISSUE-25-DEC-001
- Recorded date: 2026-11-12
- Status: active for issue #25 only.
- Authority: human decision (owner chat answer in the main coordinator session; recorded by the
  coordinator).
- Source: owner message in the main session on 2026-11-12 (no permalink): "Simulator streichen"
  (English: "drop the simulator"), answering the coordinator's explanation of the simulator and
  its options (drop it, file it as a Backlog issue, or keep it deferred).
- Scope: the opt-in synthetic demo/simulator part of S2-LAUNCH-01 and of #25 only.
- Decision: the opt-in synthetic demo/simulator is dropped, not deferred. It is not built and no
  Backlog issue is opened for it. The reproducible no-hardware evidence stays with the existing
  test doubles (synthetic loopback and fake controllers in `tests/`), which are test code and
  not a user-facing feature.
- Applicability / conditions / expiry: bounded to the simulator. The remaining S2-LAUNCH-01 and
  S2-LAUNCH-02 work of #25 (live rollback, launch report, hardware observations, external route
  status) is unchanged. The owner may reinstate a simulator later as a new issue; this
  decision is then superseded for that issue only.
- Rationale supplied: none beyond the instruction; the coordinator's explanation noted that the
  launch does not need it and that it adds surface and maintenance.
- Affected requirement IDs, files, issues and tests: S2-LAUNCH-01 (simulator sentence);
  docs/STAGE-2.md, docs/STAGE-5.md, issue #25 (body updated 2026-11-12).
- Supersedes / superseded by: supersedes, for the simulator only, the deferral of the simulator
  in [DEC-023](../DECISIONS.md#dec-023--staged-first-public-release) item 3 ("deferred, not
  dropped").
- Propagated to roles / packet references: coordinator; issue #25 body.
- Revalidation needed / next action: none.

## ISSUE-25-DEC-002 — Hardware use and scope of the launch-report PR

- ID: ISSUE-25-DEC-002
- Recorded date: 2026-11-13
- Status: active for issue #25 only; the hardware part is spent once the run below is recorded.
- Authority: human decision (owner instruction to the coordinator session, 2026-11-13, no
  permalink).
- Source: the owner's kickoff message for the launch-report packet.
- Scope: the launch report and the prepared rollback checklist of #25 (checkboxes 3 to 5 as far
  as the evidence allows). The selected WLED test controller (named only in the local,
  git-ignored reference) may be used for read and write checks if needed for the report, with a
  restorable state kept first, a small call count and the scope recorded.
- Decision: the report and the checklist may be prepared, and one bounded hardware run of the
  published release 0.3.0 on that controller is authorized. The run is recorded in
  [validation/launch-report.md](../validation/launch-report.md).
- Not authorized by this decision: the restart or rollback of the deployed service (checkbox 2
  of #25 stays open and needs its own owner authorization), any publication, release, tag,
  registry submission, MCPHub deployment, and any visibility or license change.
- Applicability / conditions / expiry: that controller and that run only; not standing
  permission for other writes, devices or issues. Merge approval stays with the owner.
- Rationale supplied: evidence that the published artifact works on hardware.
- Affected requirement IDs, files, issues and tests: S2-LAUNCH-01, S2-LAUNCH-02, #25;
  docs/validation/launch-report.md, docs/validation/issue-25-rollback-plan.md.
- Supersedes / superseded by: none; ISSUE-25-DEC-001 is unchanged.
- Propagated to roles / packet references: reviewer via the coordinator handoff.
- Revalidation needed / next action: none for this run; the rollback needs a separate
  authorization.

## ISSUE-25-DEC-003 — Restart, rollback and hub-entry changes for the live rollback

- ID: ISSUE-25-DEC-003
- Recorded date: 2026-11-13
- Status: active for issue #25 only; **not yet exercised** (no restart, rollback or hub change
  has been made).
- Authority: owner authorization as relayed to the packet session by the coordinator in three
  messages on 2026-11-13 (no permalink; recorded as relayed, not verified by this session).
- Scope: item 1 of #25 (S2-COMPAT-03, live part): back up the inventory, data directory and the
  wled-mcp hub entry, roll the deployed HTTP service back to the previous release following
  DEPLOYMENT.md, check it with read-only calls only, restore the release it ran before, and
  restore the hub entry; change only the wled-mcp entry; keep hostnames, addresses and
  credentials out of committed files.
- Decision: the run is authorized in that scope. It stops and reports, without improvising, if a
  true rollback needs an artifact that is not available or a choice the owner has not made.
- Not authorized: publishing, releasing, tagging, registry submission, other hub entries; the
  waiver ISSUE-24-DEC-005 is unchanged and no fresh-install test is claimed.
- Superseded part: the sentence "restart and rollback are not authorized" of ISSUE-25-DEC-002
  no longer holds for the scope above; the hardware part of DEC-002 is unchanged.
- Update 2026-11-13 (relayed owner decisions, no permalink): (a) rollback target: the owner chose
  release 0.2.0, staged on the deployed target first; (b) hub entry: the owner has **not** answered
  whether the wled-mcp hub entry may be changed, so the hub-entry part of the scope above is
  **pending** and not exercised; the default is not to touch the entry and to verify the service
  directly on the target (read-only through the hub if reachable), stopping and reporting if the
  rollback cannot be verified without changing it; (c) the hub itself is never reinstalled
  ([DEC-037](../DECISIONS.md#dec-037--no-mcphub-reinstall-in-project-steps)).
- Observation (2026-11-13, read-only): the deployed service ran 0.3.0 with only its image and the
  staged directories of 0.3.0 and 0.1.2. A later attempt to start the run failed because the target
  was unreachable from the session (name resolution); nothing was changed.
- Update 2026-11-13, later (relayed owner answer, no permalink): the wled-mcp entry on the hub
  **may** be changed for the #25 rollback, this issue only, not standing. Bounds: only that entry;
  back it up first and restore it afterwards, recording both states without hostnames or
  addresses; no other hub entry, no hub reinstall (DEC-037); no publish, release, tag or registry
  step. The entry is changed only if the rollback verification needs it; otherwise it stays
  untouched and the report says so. This replaces the "pending" state of the hub-entry part above.
- Observation: a retry of the target access after this answer still failed with the same
  name-resolution error; no change was made.
- Revalidation needed / next action: reachability of the target, then the owner's go for the run.
