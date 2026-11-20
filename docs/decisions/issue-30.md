# Issue #30 decisions

## ISSUE-30-DEC-001 — Selected-controller read-only live run

- Status: active for the bounded issue #30 / milestone M2 live run only.
- Authority/source: owner message in the coordinator session, 2026-11-11 (no permalink), authorizing
  the read-only live run and naming one controller (name and address only in ignored local files).
- Scope: S3-EXPLAIN-01/-02, the M2 exit criterion; one selected test controller, `read-only` profile
  over stdio, tool `wled_explain_lighting`.
- Decision: a bounded read-only run: at most two tool calls, each reading `/json/state` and
  `/json/info` once. No writes, discovery, configuration or firmware changes, deployment, publication
  or other controllers.
- Conditions/expiry: issue #30 only; consumed by the run in
  [validation/issue-30.md](../validation/issue-30.md); not standing permission. Captures stay in the
  ignored runtime directory; only neutral evidence is published.
- Supersedes: none; ISSUE-150-DEC-001 is not reused.
