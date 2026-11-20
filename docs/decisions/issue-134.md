# Issue #134 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-09.

## ISSUE-134-DEC-001 — Hardware run on the test controller and the documentation PR

- ID: ISSUE-134-DEC-001
- Status: active for issue #134 only; the hardware part is spent (the run is complete).
- Authority: human decision (owner chat, main coordinator session, 2026-11-09, no permalink): device
  released from #11; permission to do everything as long as the current state is restored at the end
  (covering saving a playlist, which starts it); run through the deployed HTTP service on the hub;
  start the workflow for the documentation PR.
- Scope: one hardware run of the stage-2 features on the single test controller of #11/#12 (named only
  in the local, git-ignored record), under DEC-027, and the documentation PR recording it.
- Decision: the run and its evidence record are authorized. The main session executed the run; the
  result is in [validation/issue-134.md](../validation/issue-134.md).
- Conditions: that controller and that run only; state restored and recorded. Not standing permission
  for later writes, other devices or other issues.
- Affected: #134; README limitations; VALIDATION.md "Known limitations". Supersedes: none.
