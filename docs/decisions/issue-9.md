# Issue #9 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-05; issue #9 only.

## ISSUE-9-DEC-001 — Content decisions OD-1 to OD-7

- Status: active for issue #9 only.
- Authority/source: the main session relayed a user chat message (2026-11-05) delegating
  content decisions for #9 to the main session, which accepted the requirements agent's
  proposals (delegation not independently verifiable; no permalink). Not dictated by the owner.
- Decision:
  - OD-1: PRE-03 (supplied-state save) and restore execution stay deferred to #13
    (ISSUE-2-DEC-003, ISSUE-8-DEC-001).
  - OD-2: `wled_save_preset` with `overwrite=true` on a playlist is `UNSUPPORTED_CAPABILITY`
    without snapshot or POST; state, api-command and unknown entries may be overwritten after a
    snapshot; delete is allowed for any occupied entry after a snapshot.
  - OD-3: types `state | playlist | api-command | unknown` on positive evidence only; only state
    presets and playlists made of state presets are activatable. `state` uses an allowlist of
    top-level keys a firmware save emits (`on`, `bri`, `transition`, `mainseg`, `seg`, `n`, `ql`,
    `ledmap`) with at least one of `on`, `bri`, `seg`; playlists check `playlist.ps` plus a
    persistent `end` preset (`end=255` is not activatable).
  - OD-4: delete is verified against the pinned v0.15.1 source (SOURCES.md); without evidence it
    ships as an explicit `UNSUPPORTED_CAPABILITY` path and returns to the human.
  - OD-5 to OD-7: unrelated changes during verification are warnings; deleting a referenced or
    active preset is allowed with a warning; any difference at the deadline is
    `VERIFICATION_MISMATCH`; save and delete carry the destructive hint, activate does not;
    `overwrite=true` on a free explicit ID needs no snapshot. "Null POSTs" means zero mutating
    POSTs on backup failure or validation rejection. PLAY-01: inspect/activate, reject editing.
- Conditions: new or critical decisions go back to the main session; hardware writes, merge,
  deployment and publication are not covered.
- Supersession: none.
