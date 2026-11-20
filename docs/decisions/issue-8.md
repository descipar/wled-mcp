# Issue #8 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-05. All entries apply to issue #8
only and are not reusable elsewhere. OD-n refers to the open points of the issue-8 packet.

## ISSUE-8-DEC-001 — Restore execution is deferred

- Status: active for issue #8 only.
- Authority/source: human answer in the main session chat, 2026-11-05; no permalink.
- Decision: restore execution is deferred; `wled_restore_preset` is not registered. #8 provides a
  read-only inspect/plan helper and a documented manual restoration procedure. A live restore
  path needs separate sourced requirements and decisions. (PRE-04, T12.)

## ISSUE-8-DEC-002 — Store plus Resources interface; proof by synthetic operation

- Status: active for issue #8 only.
- Authority/source: human answer in the main session chat, 2026-11-05; no permalink.
- Decision: #8 delivers the snapshot store and the `Resources` interface; "backup failure aborts
  before POST" is shown with a synthetic destructive operation (zero POSTs); #9 wires the real
  preset tools. No production destructive preset tool is added by #8.

## ISSUE-8-DEC-003 — Delegated: layout, ID, envelope, compatibility, errors, retention, guard, fsync, source

- Status: active for issue #8 only.
- Authority/source: the owner delegated OD-3 to OD-10 to the main session (chat, 2026-11-05); the
  main session accepted the requirements agent's defaults. Decided by the main session, not
  dictated by the owner; no permalink.
- Decision:
  - OD-3: layout `backups/<device_id>/<backup_id>.json`; ID `b-<UTC>-<12 hex>`; exclusive create,
    never overwrite.
  - OD-4: reject unknown top-level keys, preserve unknown fields inside `preset`; 1 MiB cap; store
    no MAC, URL or hash.
  - OD-5: restore planning needs exact `device_id` and firmware `version`; a different target
    preset ID only through an explicit target.
  - OD-6: no new error codes.
  - OD-7: retention order `created_at` then `backup_id`; never delete invalid, temporary, foreign
    or symlink files; a prune failure is only a warning.
  - OD-8: repository guard against runtime backups in Git (test and/or `scripts/check_distribution.py`).
  - OD-9: directory fsync best effort, documented, skipped on Windows.
  - OD-10: the caller supplies the freshly read preset object inside the device lock; the store
    does no device I/O.
- Conditions: new decisions during implementation go back to the main session.
