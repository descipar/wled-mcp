# Issue #27 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-09.

## ISSUE-27-DEC-001 — Technical defaults TD-27-1 to TD-27-16 and the three scope defaults

- ID: ISSUE-27-DEC-001
- Status: active for issue #27.
- Authority: technical proposal accepted by the coordinator, 2026-11-09 (TD-27-1 to TD-27-16 and
  OC-27-1 to OC-27-3 of the issue-27 packet); not a human decision. Reversible by the owner.
- Scope: issue #27 only (S3-ZONE-01, S3-ZONE-02).
- Decision: zones are reviewed local files `<data-dir>/zones/<id>.json` (`format` `wled-mcp.zone`,
  `format_version` 1) mapping a name to configured device IDs and `[start, stop)` LED ranges, with a
  required per-device `led_count` as stale-topology anchor, optional `segment` cross-check and a
  `reversed` flag (reporting only). Tools: `wled_list_zones`, `wled_plan_zone` (`read`),
  `wled_apply_zone` (`control`), after `wled_apply_scene`. Lookup by exact ID, then unique
  case-folded name (`AMBIGUOUS_NAME`). Existing active segments only: a zone resolves only when live
  segments tile it exactly, otherwise refused before any write with a stable `reason` and
  `layout_change_required`; geometry is never changed. No new error code. Apply reuses the scene
  machinery (strict default, four in flight) with one hook that resolves segment IDs from the fresh
  read and re-checks at write time. OC-27-1 (zone targets in groups/scenes) and OC-27-2 (zone
  save/delete tool) deferred; OC-27-3 accepted.
- Conditions: ISSUE-17-DEC-001 (agent-authored groups/scenes) is not generalized to zones.
  Refinements live in [contract/zones.md](../contract/zones.md).
- Supersedes / superseded by: none. Follow-ups (zones in scenes/groups, zone save/delete) not created.
