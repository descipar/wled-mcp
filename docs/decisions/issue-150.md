# Issue #150 decisions

## ISSUE-150-DEC-001 — Selected-controller read-only verification

- Recorded date: 2026-11-10.
- Status: active for the bounded issue #150 verification only.
- Authority/source: actual owner message in the coordinator session on 2026-11-10
  (no permalink), explicitly identifying one WLED controller and authorizing reads.
  Its address is kept only in ignored local runtime configuration.
- Scope: LIVE-01, one selected test controller; implementation verification with
  necessary bounded reads of info, state and `/json/live`.
- Decision: perform read-only verification against that controller. No physical
  writes, discovery, configuration changes, deployment, publication or other
  controllers are authorized by this answer.
- Conditions/expiry: issue #150 verification only; not standing permission for
  later issues or future hardware operations. Store captures and inventory in the
  project's ignored runtime directory; publish only neutral validation evidence.
- Rationale supplied: the controller is available for reading.
- Affected: LIVE-01, issue #150 work packet and validation evidence.
- Supersedes: no earlier decision; historical issue #148 authorization is not reused.
- Propagation: requirements, implementation and reviewer receive this decision ID
  and its narrow scope in their handoffs.
