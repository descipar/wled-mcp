# Issue #30 decisions

## ISSUE-30-DEC-001 — Selected-controller read-only live run

- Recorded date: 2026-11-11.
- Status: active for the bounded issue #30 / milestone M2 live run only.
- Authority/source: actual owner message in the coordinator session on 2026-11-11
  (no permalink), authorizing the read-only live run and naming one controller. Its name and
  address are kept only in ignored local runtime configuration and in the maintainer's local
  notes, never in a committed file.
- Scope: S3-EXPLAIN-01/-02, the M2 exit criterion; one selected test controller, the
  `read-only` profile over stdio, the `wled_explain_lighting` tool.
- Decision: perform the bounded read-only run proposed by the coordinator: at most two tool
  calls, each reading `/json/state` and `/json/info` once. No physical writes, discovery,
  configuration or firmware changes, deployment, publication or other controllers are
  authorized by this answer.
- Conditions/expiry: issue #30 only; consumed by the run recorded in
  [validation/issue-30.md](../validation/issue-30.md) and not standing permission for later
  issues or future hardware operations. Captures and the inventory stay in the project's
  ignored runtime directory; only neutral evidence is published.
- Rationale supplied: the controller is available for reading.
- Affected: S3-EXPLAIN-01/-02, M2 exit evidence.
- Supersedes: no earlier decision; ISSUE-150-DEC-001 is not reused.
- Propagation: this run was carried out by the coordinator session; no other role needed it.
