# Issue #8 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-05. All entries apply
to issue #8 only and are not reusable for other issues, stages or operations.
Decision numbers refer to the open points OD-1 to OD-10 of the issue-8 work packet.

## ISSUE-8-DEC-001 — Restore execution is deferred

- Status: active for issue #8 only.
- Authority/source: human answer in the main session's chat (structured question),
  2026-11-05; no permalink.
- Scope/decision: restore execution is deferred. `wled_restore_preset` is not
  registered. #8 provides a read-only inspect/plan helper and a documented
  manual restoration procedure, as the issue's last acceptance item allows.
- Conditions: a live restore path needs separate sourced requirements and decisions.
- Rationale supplied: none beyond the choice itself.
- Affected: PRE-04, T12, TOOL-CONTRACT.md restore text. Supersession: none.
- Propagation: coordinator passes this ID with the packet to later roles.

## ISSUE-8-DEC-002 — Store plus Resources interface; proof by synthetic operation

- Status: active for issue #8 only.
- Authority/source: human answer in the main session's chat (structured question),
  2026-11-05; no permalink.
- Scope/decision: #8 delivers the snapshot store and the `Resources` interface.
  "Backup failure aborts before POST" is shown with a synthetic destructive
  operation in tests with zero POSTs. #9 wires the real preset tools.
- Conditions: no production destructive preset tool is added by #8.
- Rationale supplied: none beyond the choice itself.
- Affected: resources.py, backups.py, T12 tests. Supersession: none.
- Propagation: coordinator passes this ID with the packet to later roles.

## ISSUE-8-DEC-003 — Delegated: layout, ID, envelope, compatibility, errors, retention, guard, fsync, source

- Status: active for issue #8 only.
- Authority/source: the owner delegated OD-3 to OD-10 to the main session in
  the main session's chat, 2026-11-05, scoped to the open points of issue #8. The
  main session accepted the requirements agent's proposed defaults. The content
  was decided by the main session, not personally dictated by the owner; no permalink.
- Scope/decision:
  - OD-3: layout `backups/<device_id>/<backup_id>.json`; ID `b-<UTC>-<12 hex>`;
    exclusive create, never overwrite.
  - OD-4: reject unknown top-level keys, preserve unknown fields inside `preset`;
    1 MiB size cap; store no MAC, URL or hash.
  - OD-5: restore planning needs exact `device_id` and exact firmware `version`;
    a different target preset ID only through an explicit target.
  - OD-6: no new error codes.
  - OD-7: retention order `created_at` then `backup_id`; never delete
    invalid, temporary, foreign or symlink files; a prune failure is only a warning.
  - OD-8: repository guard against runtime backups in Git as a test and/or a
    `scripts/check_distribution.py` change.
  - OD-9: directory fsync is best effort, documented, skipped on Windows.
  - OD-10: the caller supplies the freshly read preset object inside the device
    lock; the store does no device I/O.
- Conditions: any new decision arising during implementation goes back to the
  main session rather than being decided by an agent.
- Rationale supplied: fail-closed behavior, no secrets or identifiers persisted,
  minimal scope matching the requirements, a clean seam for #9.
- Affected: PRE-04, OPS-02, OPS-03, REL-02, T11-T13, TOOL-CONTRACT.md, backups.py.
- Supersession: none.
- Propagation: coordinator passes these IDs with the packet to implementer and reviewer.
