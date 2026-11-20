# Issue #98 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-07.

## ISSUE-98-DEC-001 — Expected tool-contract helper design

- ID: ISSUE-98-DEC-001
- Status: active for issue #98 and every later tool-adding issue.
- Authority: technical proposal TD-98-1 to TD-98-9 accepted by the coordinator, 2026-11-07; not a
  human decision.
- Scope: plan step (b) of docs/STAGE-2-PARALLEL-PLAN.md.
- Decision: the expected tool contract lives in `tests/tool_contract.py` (standard library only, not
  shipped). It lists every tool in registry order with its class (`read`, `control`, `manage` per
  ISSUE-20-DEC-001) and a destructive flag, and derives per-profile expectations. Tests and
  `scripts/check_distribution.py` compare the real registry and served `tools/list` against it in both
  directions. A PR that adds a tool adds it there with its class.
- Conditions: until a later decision; #20 adds `wled_get_service_status` and enforces profiles.
- Affected: #98; #17-#20 packets. Supersedes / superseded by: none.
