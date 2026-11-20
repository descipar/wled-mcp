# Issue #130 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-09.

## ISSUE-130-DEC-001 — Serve a tolerant output schema and document the one-time stale-cache transition

- ID: ISSUE-130-DEC-001
- Status: active for issue #130; owner-confirmed on 2026-11-09 (first an agent technical default).
- Authority: human decision (owner chat, main coordinator session, no permalink); technical content
  proposed by the coordinator. The owner answered the question whether "both" (relax the served
  output schema for additive fields and document the reload procedure) was acceptable with "beides
  und dann stage 2 anschauen und abschließen" (English: "both, and then look at stage 2 and close it").
- Scope: #130 only: the served output schema of the result envelope and error object, and the
  documentation of the update behaviour.
- Decision: (1) the served `outputSchema` of every tool sets `additionalProperties: true` on the
  envelope and the error object; the models keep `extra="forbid"` internally, so later additive
  fields do not break clients that cached the schema. (2) The contract documents that a client that
  cached a schema served before this change rejects a later additive field until it refreshes
  `tools/list` (observed case: a build from before the `correlation_id` of #119; tagged releases
  already serve that field; reloading the hub entry cleared it, about a minute once). Clients must
  ignore unknown fields.
- Conditions: envelope and error object only; fields inside `data` were never affected; no change to
  input schemas, error codes or required fields.
- Affected: `src/wled_mcp/models.py`, `tests/test_upgrade_compat.py`, docs/contract/versioning.md.
  Supersedes / superseded by: none.
