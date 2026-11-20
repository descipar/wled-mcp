# Issue #201 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-17. The owner decision for M8 is
[DEC-035](../DECISIONS.md#dec-035--agent-driven-discovery-and-enrollment); this file holds only the
technical proposals for the inventory writer.

## ISSUE-201-DEC-001 — Inventory writer defaults TP-201-1 to TP-201-5

- ID: ISSUE-201-DEC-001
- Status: proposed (active for the #201 implementation); coordinator technical proposal, not a human
  decision; the owner can change any item at the merge decision or later.
- Source: requirements packet for #201; contract text in
  [contract/discovery.md](../contract/discovery.md#reload-semantics).
- Scope: #201 and its users #202, #203 (M8). Not a global rule.
- Decision:
  - TP-201-1 Backup: one sibling `<config filename>.bak`, mode copied, atomically replaced by every
    successful write; backup failure is `STORAGE_FAILED` with nothing changed. `config add-device`
    and `config init --force` keep it too.
  - TP-201-2 Lock: sibling `.<config filename>.lock`, OS exclusive lock plus in-process lock, 5 s
    bounded wait; timeout is `STORAGE_FAILED` `data.reason` `locked` (CLI `CONFIG_LOCKED`); never deleted.
  - TP-201-3 `file_changed` baseline: SHA-256 of the bytes loaded at startup
    (`StartupConfig.config_sha256`), advanced by each own write; no baseline always conflicts.
  - TP-201-4 One `InventoryWriteError`: lock/permission/I/O failures are `STORAGE_FAILED`; bytes
    differing from baseline are `INVENTORY_CONFLICT`; invalid candidate, changed profile or
    `max_class`, or dropped ID are `INVENTORY_RELOAD_FAILED` before the replace; an apply failure
    restores the previous bytes (`not_applied`, or `unknown` if the restore fails).
  - TP-201-5 An unchanged candidate writes nothing and makes no backup; edits are a callback
    `edit(current: bytes) -> bytes | None`; no `[discovery]` or `devices[].mac` key added by #201.
- Conditions: M8 implementation. Refinement: the profile is compared with the loaded file, not the
  running policy (so `serve --profile` does not block writes); caps are compared with the running policy.
- Affected: DISC-09, DISC-10, DISC-T06. Supersedes / superseded by: none.
