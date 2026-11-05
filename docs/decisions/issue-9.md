# Issue #9 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-05. All entries apply
to issue #9 only and are not reusable for other issues, stages or operations.
Decision numbers refer to the open points OD-1 to OD-7 of the issue-9 work packet.

## ISSUE-9-DEC-001 — Content decisions OD-1 to OD-7

- Status: active for issue #9 only.
- Authority/source: the main session relayed a user chat message (2026-11-05)
  delegating content decisions for issue #9 to the main session; the main session
  then accepted the requirements agent's proposals. The content was decided by the
  main session, not dictated by the human. The coordinator could not verify the
  delegation independently; no permalink.
- Scope/decision:
  - OD-1: PRE-03 (supplied-state save) and restore execution are not part of #9;
    they stay deferred to #13 (ISSUE-2-DEC-003, ISSUE-8-DEC-001). The #9 acceptance
    checklist does not require them.
  - OD-2: `wled_save_preset` with `overwrite=true` on a playlist is rejected as
    `UNSUPPORTED_CAPABILITY` without snapshot or POST. State, api-command and
    unknown occupied entries may be overwritten after a snapshot. Delete is allowed
    for any occupied entry after a snapshot.
  - OD-3: types `state | playlist | api-command | unknown` on positive evidence
    only; only state presets and playlists whose entries are all state presets
    are activatable.
  - OD-4: the delete mechanism is verified against the pinned v0.15.1 source and
    recorded in SOURCES.md. Without source evidence, delete ships as an explicit
    `UNSUPPORTED_CAPABILITY` path with a documented limitation and returns to the
    human; nothing is guessed.
  - OD-5 to OD-7: unrelated changes during verification are warnings; deleting a
    referenced or active preset is allowed with a warning; any difference at the
    deadline is `VERIFICATION_MISMATCH`; save and delete carry the destructive
    hint, activate does not; `overwrite=true` on a free explicit ID needs no
    snapshot.
  - "Null POSTs" means zero mutating POSTs when backup fails or validation rejects.
  - PLAY-01 follows the issue's acceptance items (inspect/activate existing
    playlists, reject editing).
- Conditions: new or critical decisions go back to the main session. Hardware
  writes, merge, deployment and publication are not covered.
- Affected: PRE-01-05, PLAY-01, REL-02, T11-T13, TOOL-CONTRACT.md, SOURCES.md,
  tests, scripts/check_distribution.py (mechanical tool-list change accepted).
- Supersession: none.
- Propagation: passed with the packet to implementer and reviewer.
