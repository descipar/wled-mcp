# Issue #4 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-04.

## ISSUE-4-DEC-001 — Scoped implementation authority

- Status: active for issue #4 delivery; human merge decision remains separate.
- Authority/source: human request to implement #4 with the defined workflow, 2026-11-04 (no
  permalink).
- Scope: inventory/client/list-tool foundation, tests, review and PR (C4-01–10). No deployment,
  device calls, merge, license or publication permission; other issue approvals are not reused.

## ISSUE-4-DEC-002 — Validated inventory and fixed endpoint profile

- Status/authority: active agent technical baseline pending review/human merge.
- Decision: strict immutable inventory/settings, configured targets only, list is network-free by
  default, explicit bounded probes, no redirects or environment routing, streamed size/JSON
  limits. HTTPX2 reuses the SDK's locked graph. Limits: [INVENTORY-CLIENT.md](../INVENTORY-CLIENT.md);
  tests T01/T02/T15. Extends issue-3's temporary empty-inventory staging within #4 only.
- No human confirmation of each numeric limit is claimed.

## ISSUE-4-DEC-003 — Deadline, uncertain writes and reconciliation

- Status/authority: active agent design under REL-01–03 and issue-2 outcome rules; evidence
  [HTTPX2 documentation](../SOURCES.md#issue-4-client-evidence).
- Decision: one total deadline covers lock wait, preparation, write and readback; only safe
  transient reads retry once, writes never retry. 20 ms required before dispatch, 25% (up to one
  second) reserved for readback. ACK alone is not proof; a matching readback verifies, mismatch or
  unavailable stays uncertain; cancellation after dispatch may have applied.
- Conditions: internal mocked foundation; no public setter, firmware adapter or exactly-once claim.

## ISSUE-4-DEC-004 — One resource graph per process

- Status/authority: active agent design implementing MCP-04/MULTI-01 foundation.
- Decision: client, immutable inventory, locks, metadata container and inert backup handle are
  process-owned, shared by operation closures, opened and closed in one async lifecycle;
  per-device locks span preparation through verification.
- Conditions: one worker only; logical shared-session tests are not actual Streamable HTTP T19;
  cache freshness, snapshots and HTTP lifecycle remain #5/#8/#14.

## ISSUE-4-DEC-005 — T19/MCP-04 acceptance scoped to the logical foundation

- Status: active for issue #4 acceptance only.
- Authority/source: human answer, 2026-11-05 (no permalink), to whether #4 may count as satisfied
  by the logical foundation with actual HTTP T19 tracked in #14.
- Decision: the merged logical foundation (ISSUE-4-DEC-004) counts as #4's T19/MCP-04
  acceptance; actual concurrent Streamable HTTP evidence (T19) is proven in #14. Not a general
  rule and does not waive T19 for #14.
