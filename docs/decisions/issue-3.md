# Issue #3 decisions

Recorded 2026-11-04. Read with [DECISIONS.md](../DECISIONS.md).

## ISSUE-3-DEC-001 — Scoped implementation

- Status: active for #3 candidate delivery; merge approval remains separate.
- Authority/source: human request to implement #3 with the defined workflow, coordinator session,
  2026-11-04; no permalink.
- Scope: implementation/tests, independent review, reviewable PR. No merge, deployment,
  physical-device actions, license selection or publication.
- Affected: C3-01–10. Supersession: none.

## ISSUE-3-DEC-002 — Runtime and artifact reproducibility

- Status: active agent technical baseline, pending review/human merge.
- Authority/source: agent design; PyPI metadata and SDK source inspected 2026-11-04
  ([Sources](../SOURCES.md#issue-3-bootstrap-evidence)).
- Scope: Python 3.13 only, official MCP SDK 2.3.0, locked runtime/dev/build graph, locked hatchling
  1.27.0 without build isolation, private wheel and generated runtime constraints for uvx with
  installed-version verification (uvx does not consume uv.lock).
- Conditions: expand support with checks; no publication/license inferred.
- Affected: C3-01/02/08/09. Supersession: none.

## ISSUE-3-DEC-003 — Safe staged configuration and transport

- Status: active agent technical staging, pending review/human merge.
- Authority/source: agent design under #3/#4/#14 boundaries and ISSUE-2-DEC-004/005; no new human
  behavior confirmation.
- Scope: only schema_version=1/devices=[]; unsupported configuration rejected until #4. Empty
  production registry; programmatic fixture injection in tests. Shared SDK factory and domain
  envelopes; HTTP fails before listening until #14.
- Conditions: bootstrap only; both transports remain required; T18–T21 pending.
- Affected: C3-03–07/10. Supersession: none.
