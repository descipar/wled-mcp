# Issue #130 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-09.

## ISSUE-130-DEC-001 — Serve a tolerant output schema and document the one-time stale-cache transition

- ID: ISSUE-130-DEC-001
- Recorded date: 2026-11-09
- Status: active for issue #130; proposed technical default, not an owner-confirmed decision.
- Authority: agent technical default under the owner's instruction to run #130 through the
  workflow; the owner may overrule.
- Source: owner chat message in the main coordinator session on 2026-11-09 (no permalink),
  "ja, starte #130 über den workflow". The owner did not choose between the options; the choice below is an agent technical default.
- Scope: issue #130 only: the served output schema of the result envelope and of its error
  object, and the documentation of the update behaviour.
- Decision: (1) the served `outputSchema` of every tool sets `additionalProperties: true` on
  the envelope and on the error object, while the models keep `extra="forbid"` for internal
  validation, so later additive envelope or error fields do not break a client that cached
  this schema. (2) The contract documents that a client which cached a schema served before
  this change (0.1.0, 0.1.1 and earlier non-release builds, all with
  `additionalProperties: false`) rejects the top-level `correlation_id` (added after 0.1.0)
  and any later additive field until it refreshes `tools/list`; reloading the hub entry
  clears it (observed about a minute). Clients must ignore unknown fields.
- Applicability / conditions / expiry: applies to the served envelope and error object only;
  fields inside `data` were never affected. Does not change any input schema, error-code
  set or required field.
- Rationale supplied: the confirmed cause is the retained 0.1.0 `tools.json` listing the
  envelope without `correlation_id` under `additionalProperties: false`. A looser output
  schema is a non-breaking, additive change.
- Affected requirement IDs, files, issues and tests: #130; `src/wled_mcp/models.py`;
  `tests/test_upgrade_compat.py`; docs/contract/versioning.md; docs/TOOL-CONTRACT.md;
  docs/DEPLOYMENT.md; CHANGELOG.md.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: coordinator handoff.
- Revalidation needed / next action: owner may overrule; a live hub check after the next
  deployment is not part of this change.
