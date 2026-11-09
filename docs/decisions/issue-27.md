# Issue #27 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-09.

## ISSUE-27-DEC-001 — Technical defaults TD-27-1 to TD-27-16 and the three scope defaults

- ID: ISSUE-27-DEC-001
- Recorded date: 2026-11-09
- Status: active for issue #27.
- Authority: technical proposal accepted by the coordinator (not a human decision).
- Source: coordinator acceptance on 2026-11-09 of the technical defaults TD-27-1 to TD-27-16
  and the defaults of the three scope confirmations OC-27-1 to OC-27-3 in the issue-27
  requirements packet (`.agent-runs/issue-27/packet.md`, pinned to main `7213dcb`); no
  permalink.
- Scope: issue #27 only (named physical lighting zones, S3-ZONE-01 and S3-ZONE-02).
- Decision: in summary, zones are reviewed local files `<data-dir>/zones/<id>.json`
  (`format` `wled-mcp.zone`, `format_version` 1) mapping a name to configured device IDs and
  explicit `[start, stop)` LED ranges per device, with a required `led_count` per device as
  the stale-topology anchor, an optional `segment` cross-check and a `reversed` flag that is
  reporting metadata only. Three tools: `wled_list_zones` and `wled_plan_zone` (class
  `read`) and `wled_apply_zone` (class `control`), registered after `wled_apply_scene`.
  Lookup is by exact ID, then unique case-folded name (`AMBIGUOUS_NAME` otherwise). Policy:
  existing active segments only; a zone resolves only when live segments inside it tile it
  exactly, otherwise the call is refused before any write with a stable `reason` and
  `layout_change_required`; geometry is never changed by a zone tool, and no layout is
  generated. No new error code. The apply reuses the scene machinery (`plan_device`,
  `apply_device`, `Resources.write_verified`, strict default, four in flight) with one
  additive hook that resolves the segment IDs from the fresh read and re-checks them at write
  time. Zone targets inside groups or scenes (OC-27-1) and a zone save or delete tool
  (OC-27-2) are deferred; the existing-segments-only policy (OC-27-3) is accepted.
- Applicability / conditions / expiry: agent proposals, reversible by the owner. The
  ISSUE-17-DEC-001 owner decision (agent-authored groups and scenes, strict default) applies
  to groups and scenes only and is not generalized to zones. Implementation refinements are
  recorded in [contract/zones.md](../contract/zones.md): the request takes one object of
  segment fields (`segments` holds exactly one entry, because several entries would address
  the same segments twice); the preflight entry of a refused device carries the `problem`;
  the matrix refusal and the unknown LED count are `UNSUPPORTED_CAPABILITY`.
- Rationale supplied: DEC-028 pragmatic delivery and the issue's rule that a zone command
  cannot silently affect LEDs outside the requested region; no human rationale supplied.
- Affected requirement IDs, files, issues and tests: S3-ZONE-01, S3-ZONE-02; #27;
  `docs/contract/zones.md`, `tests/test_zones.py`, `tests/test_zone_tools.py`,
  `tests/test_zone_parity.py`.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: issue-27 packet, implementer.
- Revalidation needed / next action: none. Carried (not created): a follow-up for zone
  targets in scenes and groups (needs scene `format_version` 2) and one for a zone
  save/delete tool; each would need the `Stage 3: ` prefix, the `stage:3` label and a
  sub-issue link to #26 (DEC-010).
