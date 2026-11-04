# Issue #4 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-04.

## ISSUE-4-DEC-001 — Scoped implementation authority

- Status: active for issue #4 delivery; human merge decision remains separate.
- Authority/source: actual human request to implement issue #4 with the defined
  workflow during the active issue-3 run, 2026-11-04; no chat permalink exists.
- Scope: inventory/client/list-tool foundation, tests, independent review and PR.
  No deployment, physical device calls, merge, license or publication permission.
- Rationale supplied: follow defined workflow; no additional rationale supplied.
- Affected: C4-01–10. Supersession: none; other issue approvals are not reused.
- Propagation: coordinator supplied packet/DEC-001–005 and relevant issue-2/3
  references; implementer returns these new IDs for explicit reviewer propagation.

## ISSUE-4-DEC-002 — Validated inventory and fixed endpoint profile

- Status/authority: active agent technical baseline pending review/human merge.
- Source: issue-4 packet C4-01–05/10; installed HTTPX2 API and package metadata.
- Decision: strict immutable inventory/settings, configured targets only, list is
  network-free by default, explicit bounded probes, no redirects/environment
  routing, streamed size/JSON limits. HTTPX2 reuses the SDK's locked maintained
  graph instead of adding a separate older HTTP stack.
- Rationale: bounded predictable target selection and safe errors; full domain
  tools remain later issues. No human confirmation of each numeric limit claimed.
- Conditions/affected: [documented limits](../INVENTORY-CLIENT.md), T01/T02/T15,
  config/client/list examples. Extends issue-3's temporary empty-inventory staging
  within #4 only; does not alter its historical authority or HTTP refusal.
- Propagation: coordinator receives IDs with candidate for reviewer handoff.

## ISSUE-4-DEC-003 — Deadline, uncertain writes and reconciliation

- Status/authority: active agent design under REL-01–03 and issue-2 outcome rules.
- Source: C4-06/07 and [HTTPX2 documentation](../SOURCES.md#issue-4-client-evidence).
- Decision: one total deadline includes lock wait/preparation/write/readback;
  only safe transient reads retry once, writes never retry. Require 20 ms before
  dispatch and reserve 25% (up to one second) for readback. ACK alone is not proof.
  Match verifies postcondition; mismatch/unavailable remains uncertain.
- Rationale: per-I/O timeouts do not bound a whole operation; avoid unsafe replay.
- Conditions: internal mocked foundation, no public setter/firmware adapter or
  exactly-once claim. Cancellation after dispatch may have applied.
- Affected: T09/T10, resources/client/tests. Supersession: none.
- Propagation: coordinator receives IDs with candidate for reviewer handoff.

## ISSUE-4-DEC-004 — One resource graph per process

- Status/authority: active agent design implementing MCP-04/MULTI-01 foundation.
- Source: C4-08/09; confirmed dual-transport scope DEC-003 and issue-2 design.
- Decision: client, immutable inventory, locks, metadata container and inert backup
  handle are process-owned, shared by operation closures, opened/closed in one
  async lifecycle. Per-device locks span preparation through verification.
- Rationale: same-controller serialization with independent controller progress.
- Conditions: one worker only; external clients/processes remain outside locks.
  Logical shared-session tests are not actual Streamable HTTP T19 completion.
  Cache freshness/snapshots/HTTP lifecycle remain #5/#8/#14.
- Affected: T10/logical T19 and CLI/resources/tests. Supersession: none.
- Propagation: coordinator receives IDs with candidate for reviewer handoff.
