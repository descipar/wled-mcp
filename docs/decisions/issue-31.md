# Issue #31 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-09.

## ISSUE-31-DEC-001 — Technical defaults TD-31-1 to TD-31-12

- ID: ISSUE-31-DEC-001
- Status: active for issue #31.
- Authority: technical proposal accepted by the coordinator, 2026-11-09 (TD-31-1 to TD-31-12 and two
  optional confirmations of the #31 packet); not a human decision. Reversible by the owner.
- Scope: #31 only (`wled_search_effects`, S3-EFFECT-01/02).
- Decision: one read-only tool `wled_search_effects` (class `read`); optional AND-combined property
  filters with `strict` and `min_confidence` (unknown properties never satisfy a strict filter); each
  catalog property is `{value, confidence, basis, evidence}`, subjective ones never `verified`; a
  shipped versioned JSON catalog with integer `schema_version` rejection; device intersection by exact
  name with `exact`, `id_changed`, name-conflict, ambiguous and absent handling; fixed `no_match`
  reasons; small initial catalog from firmware source at tag `v16.0.1` only; updates by pull request,
  no runtime override or remote fetch; mock tests only. Accepted as proposed: separate properties
  `visibility` and `palette_saturation_need`; firmware below the floor or unrecognizable gets
  `catalog_not_applicable`.
- Conditions: implementation refinements (colour slot count 0 to 3; basis/evidence on each property
  instead of a `provenance` object; firmware floor from `compat.py`) are recorded in
  `docs/contract/effect-search.md`.
- Supersedes / superseded by: none.
