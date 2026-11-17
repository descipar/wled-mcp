# Issue #201 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-17. The owner decision for
milestone M8 is [DEC-035](../DECISIONS.md#dec-035--agent-driven-discovery-and-enrollment); this
file holds only the technical proposals for the inventory writer.

## ISSUE-201-DEC-001 — Inventory writer defaults TP-201-1 to TP-201-5

- ID: ISSUE-201-DEC-001
- Recorded date: 2026-11-17
- Status: proposed (active for the #201 implementation); coordinator technical proposal, not a
  human decision. The owner can change any item at the merge decision of the #201 PR or later.
- Authority: technical proposal (not a human decision).
- Source: requirements packet for issue #201 (ignored local file); the contract text is
  [contract/discovery.md](../contract/discovery.md#reload-semantics).
- Scope: issue #201 and its users #202 and #203 (milestone M8). Not a global rule.
- Decision:
  - TP-201-1 Backup: one sibling file `<config filename>.bak`, mode copied, replaced by every
    successful write, written atomically before the replace; a backup failure is
    `STORAGE_FAILED` with nothing changed. `config add-device` and `config init --force` keep it
    too.
  - TP-201-2 Lock: sibling file `.<config filename>.lock`, OS-level exclusive lock plus an
    in-process lock, bounded wait (5 s), timeout is `STORAGE_FAILED` `data.reason` `locked`
    (CLI: `CONFIG_LOCKED`); never deleted, so a crashed holder leaves no stale lock.
  - TP-201-3 Baseline for `file_changed`: SHA-256 of the bytes loaded at startup
    (`StartupConfig.config_sha256`), advanced by each own write; no baseline always conflicts.
  - TP-201-4 Error mapping in one `InventoryWriteError`: lock, permission and I/O failures are
    `STORAGE_FAILED`; bytes differing from the baseline are `INVENTORY_CONFLICT`; an invalid
    candidate, a changed profile or `max_class`, or a dropped ID are `INVENTORY_RELOAD_FAILED`
    before the replace; an apply failure restores the previous bytes (`not_applied`, or
    `unknown` if the restore fails).
  - TP-201-5 An unchanged candidate writes nothing and makes no backup; edits are a callback
    `edit(current: bytes) -> bytes | None`; #201 adds no `[discovery]` or `devices[].mac` key.
- Applicability / conditions / expiry: M8 implementation; refinements need a recorded rationale.
  Implementation refinement: the profile is compared with the loaded file, not the running
  policy, so a `serve --profile` option does not block every write; caps are compared with the
  running policy.
- Rationale supplied: none from the owner; the rationale is agent analysis in the packet (the
  configuration directory must be writable anyway; it is the only directory the CLI knows
  without `--data-dir`; a lock avoids stale lock files).
- Affected requirement IDs, files, issues and tests: DISC-09, DISC-10, DISC-T06;
  `src/wled_mcp/inventory_writer.py`, `src/wled_mcp/filelock.py`, `tests/test_inventory_writer.py`.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: packet for #201; #202 and #203 packets cite it.
- Revalidation needed / next action: none before #202.
