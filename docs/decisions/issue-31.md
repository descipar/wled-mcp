# Issue #31 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-09.

## ISSUE-31-DEC-001 — Technical defaults TD-31-1 to TD-31-12

- ID: ISSUE-31-DEC-001
- Recorded date: 2026-11-09
- Status: active for issue #31.
- Authority: technical proposal accepted by the coordinator (not a human decision).
- Source: coordinator acceptance on 2026-11-09 of the technical defaults TD-31-1 to
  TD-31-12 and both optional confirmations in the issue-31 requirements packet
  (`.agent-runs/issue-31/packet.md`, pinned to main `ea61e65`); no permalink.
- Scope: issue #31 only (`wled_search_effects`, S3-EFFECT-01 and S3-EFFECT-02).
- Decision: in summary, one read-only tool `wled_search_effects` (class `read`);
  optional AND-combined property filters with `strict` and `min_confidence` semantics where
  unknown properties never satisfy a strict filter; each catalog property is
  `{value, confidence, basis, evidence}` with subjective properties never `verified`;
  a shipped, versioned JSON catalog loaded with integer `schema_version` rejection;
  device intersection by exact name with `exact`, `id_changed`, name-conflict, ambiguous and
  absent handling; fixed `no_match` reasons; a small initial catalog from the firmware source
  at tag `v16.0.1` only; updates by pull request, no runtime override or remote fetch; mock
  tests only. The two optional confirmations are accepted as proposed: two separate
  properties `visibility` and `palette_saturation_need`, and firmware below the floor or
  unrecognizable gets `catalog_not_applicable`.
- Applicability / conditions / expiry: agent proposals, reversible by the owner; implementation
  refinements (colour slot count 0 to 3 instead of 1 to 3, because palette-driven effects
  declare no colour slot; no separate `provenance` object, the basis and evidence sit on each
  property; no `min` firmware field, the floor comes from `compat.py`) are recorded in the
  contract file.
- Rationale supplied: DEC-028 pragmatic delivery and the issue's "small trustworthy initial
  catalog"; no human rationale supplied.
- Affected requirement IDs, files, issues and tests: S3-EFFECT-01, S3-EFFECT-02; #31;
  `docs/contract/effect-search.md`, `tests/test_effect_search.py`.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: issue-31 packet, implementer.
- Revalidation needed / next action: none.
