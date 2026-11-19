# Issue #202 decisions

Read with DECISIONS.md. Recorded 2026-11-19. Owner decision: DEC-035 (items 2 and 4). Technical proposals below by the requirements role.

## ISSUE-202-DEC-001 — `wled_set_discovery_ranges` implementation defaults TP-202-1 to TP-202-6

- Status: proposed (active for the #202 implementation); technical defaults for the #202 implementation; not a human decision; the owner can change any item at the merge decision or later.
- Authority: technical proposal (requirements role, adopted by the coordinator for implementation).
- Source: requirements packet for issue #202 (ignored local file); contract text docs/contract/discovery.md.
- Scope: issue #202 only (milestone M8); #200 and #203 consume the accessor and the shared writer. Not a global rule.
- Decision:
  - TP-202-1 Shared hard-caps module `wled_mcp/discovery_caps.py` (stdlib only) used by the startup validator, the tool and the probe; the engine re-exports its old names.
  - TP-202-2 Range syntax is strict dotted-quad CIDR `a.b.c.d/p` (ASCII digits, no netmask or hostmask notation, no zero padding); every entry gets at most one reason, the first failing in the contract order; `duplicate`/`overlap` compare with earlier entries that passed.
  - TP-202-3 The tool replaces the whole `[discovery]` table text (comments inside that table are dropped), inserts a missing table before the first `[[devices]]`, keeps `ranges = []` when clearing, and refuses (writes nothing, `INVENTORY_RELOAD_FAILED` stage `validation`) when a self-check of the parsed result differs (for example a hand-written dotted-key or inline-table form).
  - TP-202-4 Success envelope is `application` `not_attempted`, `verification` `not_requested`, `device_id` null (local-file precedent); failures carry the writer's `application`.
  - TP-202-5 `dry_run` is snapshot-based: no lock, no file read, no conflict check.
  - TP-202-6 One shared `InventoryWriter` per process on `Resources.inventory_writer()`; ranges are read through `Resources.discovery_ranges` (tuple snapshot, replaced by reload).
- Applicability / conditions / expiry: M8 implementation; refinements need a recorded rationale; hard caps must not exceed DEC-035.
- Rationale supplied: none from the owner; agent analysis in the packet.
- Affected requirement IDs, files, issues and tests: DISC-05, DISC-07, DISC-10, DISC-T03, DISC-T06, DISC-T07; files in sections A to G.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: packet for #202; #200 and #203 packets cite the accessor and writer.
- Revalidation needed / next action: none before implementation; refresh the packet if the owner overrides an item.
