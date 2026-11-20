# Issue #150 decisions

## ISSUE-150-DEC-001 — Selected-controller read-only verification

- Status: active for the bounded issue #150 verification only.
- Authority/source: owner message in the coordinator session, 2026-11-10 (no permalink), identifying
  one WLED controller and authorizing reads (address only in ignored local configuration).
- Scope: LIVE-01, one selected test controller; bounded reads of info, state and `/json/live`.
- Decision: read-only verification against that controller. No writes, discovery, configuration
  changes, deployment, publication or other controllers.
- Conditions/expiry: #150 verification only; not standing permission. Captures stay in the ignored
  runtime directory; only neutral evidence is published.
- Supersedes: none; the #148 authorization is not reused.
