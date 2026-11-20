# Issue #202 decisions

Read with DECISIONS.md. Recorded 2026-11-19. Owner decision: DEC-035 (items 2 and 4).

## ISSUE-202-DEC-001 — `wled_set_discovery_ranges` implementation defaults TP-202-1 to TP-202-6

- Status: proposed (active for the #202 implementation); technical proposal by the requirements role,
  adopted by the coordinator; not a human decision; the owner can change any item.
- Scope: #202 only (M8); #200 and #203 consume the accessor and shared writer. Contract text:
  docs/contract/discovery.md.
- Decision:
  - TP-202-1 Shared stdlib-only hard-caps module `wled_mcp/discovery_caps.py` for the startup
    validator, the tool and the probe.
  - TP-202-2 Strict dotted-quad CIDR `a.b.c.d/p` (ASCII digits, no netmask/hostmask, no zero padding);
    at most one reason per entry, the first failing in contract order; `duplicate`/`overlap` compare
    only with earlier passed entries.
  - TP-202-3 The tool replaces the whole `[discovery]` table text (inner comments dropped), inserts a
    missing table before the first `[[devices]]`, keeps `ranges = []` when clearing, and refuses
    (nothing written, `INVENTORY_RELOAD_FAILED` stage `validation`) when a self-check of the parsed
    result differs.
  - TP-202-4 Success envelope: `application` `not_attempted`, `verification` `not_requested`,
    `device_id` null; failures carry the writer's `application`.
  - TP-202-5 `dry_run` is snapshot-based: no lock, file read or conflict check.
  - TP-202-6 One shared `InventoryWriter` per process (`Resources.inventory_writer()`); ranges read
    through `Resources.discovery_ranges` (tuple snapshot replaced by reload).
- Conditions: M8; refinements need a recorded rationale; hard caps must not exceed DEC-035.
- Affected: DISC-05, DISC-07, DISC-10, DISC-T03, DISC-T06, DISC-T07. Supersedes / superseded by: none.
