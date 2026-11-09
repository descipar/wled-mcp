# Issue #134 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-09.

## ISSUE-134-DEC-001 — Hardware run on the test controller and the documentation PR

- ID: ISSUE-134-DEC-001
- Recorded date: 2026-11-09
- Status: active for issue #134 only; the hardware part is spent (the run is complete).
- Authority: human decision (delegated owner chat authority).
- Source: owner messages in the main coordinator session on 2026-11-09 (no permalink): release
  of the device from #11; permission to do everything as long as the current state is
  restored at the end; instruction to run it through the deployed HTTP service on the hub
  rather than a local version; and the instruction to start the workflow for the documentation
  PR. The question whether saving a playlist (which starts it) was acceptable was asked
  explicitly and was covered by the permission to do everything.
- Scope: one hardware run of the stage-2 features on the single test controller of #11/#12
  (named only in the local, git-ignored record), under DEC-027, and the documentation PR that
  records it.
- Decision: the run and its evidence record are authorized. The run was executed by the main
  session; the coordinator ran no hardware action. The result is recorded in
  [validation/issue-134.md](../validation/issue-134.md).
- Applicability / conditions / expiry: that controller and that run only; the state was
  restored and the restoration is recorded. Not standing permission for later writes, other
  devices or other issues.
- Rationale supplied: exercising the deployed HTTP path at the same time.
- Affected requirement IDs, files, issues and tests: #134; README limitations;
  VALIDATION.md "Known limitations".
- Supersedes / superseded by: none.
- Propagated to roles / packet references: reviewer via the coordinator handoff.
- Revalidation needed / next action: none for this run. Completion after a human-authorized merge.
