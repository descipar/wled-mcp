# Issue #98 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-07.

## ISSUE-98-DEC-001 — Expected tool-contract helper design

- ID: ISSUE-98-DEC-001
- Recorded date: 2026-11-07
- Status: active for issue #98 and every later tool-adding issue.
- Authority: technical proposal accepted by the coordinator (not a human decision).
- Source: requirements packet `.agent-runs/stage2/issue-98/packet.md`, TD-98-1 to
  TD-98-9, accepted in the coordinator session on 2026-11-07.
- Scope: plan step (b) of docs/STAGE-2-PARALLEL-PLAN.md.
- Decision: the expected tool contract lives in `tests/tool_contract.py` (standard
  library only, not shipped in the wheel). It lists every tool in registry order with
  its class (`read`, `control`, `manage` per ISSUE-20-DEC-001) and a destructive flag,
  and derives per-profile expectations. Tests and `scripts/check_distribution.py`
  compare the real registry and the served `tools/list` against it in both directions
  instead of hard-coded lists or counts. A PR that adds a tool adds it to this helper
  with its class.
- Applicability / conditions / expiry: until a later decision; #20 adds
  `wled_get_service_status` and enforces the profiles.
- Rationale supplied: packet analysis (agent): removes the tool-list merge hotspot.
- Affected requirement IDs, files, issues and tests: #98; #17, #18, #19, #20 packets.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: issue-98 packet; #17-#20 packets when they
  are refreshed.
- Revalidation needed / next action: none.
