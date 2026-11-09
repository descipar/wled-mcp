# Issue #130 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-09.

## ISSUE-130-DEC-001 — Serve a tolerant output schema and document the one-time stale-cache transition

- ID: ISSUE-130-DEC-001
- Recorded date: 2026-11-09
- Status: active for issue #130; owner-confirmed on 2026-11-09 (the choice was first an agent
  technical default).
- Authority: human decision (delegated owner chat authority); the technical content was proposed
  by the coordinator.
- Source: owner chat messages in the main coordinator session on 2026-11-09 (no permalink).
  First, "ja, starte #130 über den workflow" (English: "yes, start #130 through the workflow"),
  which did not choose between the options. Later the owner was asked whether to merge PR #139
  and whether the decision "both" (relax the served output schema for additive fields and
  document the reload procedure) was acceptable, and answered "beides und dann stage 2
  anschauen und abschließen" (English: "both, and then look at stage 2 and close it"),
  typing errors kept.
- Scope: issue #130 only: the served output schema of the result envelope and of its error
  object, and the documentation of the update behaviour.
- Decision: (1) the served `outputSchema` of every tool sets `additionalProperties: true` on
  the envelope and on the error object, while the models keep `extra="forbid"` for internal
  validation, so later additive envelope or error fields do not break a client that cached
  this schema. (2) The contract documents that a client which cached a schema served before
  this change (all with `additionalProperties: false`) rejects a later additive field until
  it refreshes `tools/list`. The observed case is a build from before the `correlation_id`
  of #119; the tagged releases already serve that field, so updating from them needs no
  reload. Reloading the hub entry cleared it (about a minute observed once; other clients
  may cache longer). Clients must ignore unknown fields.
- Applicability / conditions / expiry: applies to the served envelope and error object only;
  fields inside `data` were never affected. Does not change any input schema, error-code
  set or required field.
- Rationale supplied: the confirmed cause (for the pre-#119 build path) is the retained
  first-release fixture, generated from a build before #119, listing the envelope without
  `correlation_id` under `additionalProperties: false`. A looser output
  schema is a non-breaking, additive change.
- Affected requirement IDs, files, issues and tests: #130; `src/wled_mcp/models.py`;
  `tests/test_upgrade_compat.py`; docs/contract/versioning.md; docs/TOOL-CONTRACT.md;
  docs/DEPLOYMENT.md; CHANGELOG.md.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: coordinator handoff.
- Revalidation needed / next action: none for the decision; a live hub check after the next
  deployment is not part of this change.
