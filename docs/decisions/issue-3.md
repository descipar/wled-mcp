# Issue #3 decisions

Recorded 2026-11-04. Read with [DECISIONS.md](../DECISIONS.md).

## ISSUE-3-DEC-001 — Scoped implementation

- Status: active for #3 candidate delivery; merge approval remains separate.
- Authority/source: actual human request to implement #3 with the defined workflow
  in the coordinator session on 2026-11-04; no chat permalink available.
- Scope: implementation/tests, independent review, reviewable PR. No merge,
  deployment, physical-device actions, license selection or publication.
- Rationale supplied: follow the workflow; no additional rationale supplied.
- Affected: C3-01–10; package, tests, CI, documentation. Supersession: none.
- Propagation: coordinator supplied scope and DEC-001–005 to roles; implementer
  returns new decision IDs for explicit reviewer propagation.

## ISSUE-3-DEC-002 — Runtime and artifact reproducibility

- Status: active agent technical baseline, pending review/human merge.
- Authority/source: agent design; official PyPI metadata and SDK source inspected
  2026-11-04. [Sources](../SOURCES.md#issue-3-bootstrap-evidence).
- Scope: Python 3.13 only, official MCP SDK 2.3.0, locked runtime/dev/build graph,
  installed locked hatchling 1.27.0 without build isolation, private wheel and
  generated runtime constraints for uvx with installed-version verification.
- Rationale: exercise a narrow maintained runtime; uvx does not consume uv.lock.
- Conditions: expand support with checks; no publication/license inferred.
- Affected: C3-01/02/08/09, packaging/lock/export/scripts/CI. Supersession: none.
- Propagation: implementation handoff returns IDs/evidence to coordinator.

## ISSUE-3-DEC-003 — Safe staged configuration and transport

- Status: active agent technical staging, pending review/human merge.
- Authority/source: agent design under #3/#4/#14 boundaries, requirements packet,
  and merged ISSUE-2-DEC-004/005; no new human behavior confirmation.
- Scope: only schema_version=1/devices=[]; reject unsupported configuration until
  #4. Empty production registry; explicit programmatic fixture injection in tests.
  Shared SDK factory and domain envelopes; HTTP fails before listening until #14.
- Rationale: test real installed stdio without invented device tools, ignored
  configuration or unprotected unfinished HTTP service.
- Conditions: bootstrap only; both transports remain required; T18–T21 pending.
- Affected: C3-03–07/10, config/CLI/models/server/tests. Supersession: none.
- Propagation: coordinator accepted staging in packet; implementer returns IDs
  for explicit reviewer handoff.
