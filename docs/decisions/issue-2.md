# Issue #2 decisions

Recorded 2026-11-04 for [issue #2](https://github.com/descipar/wled-mcp/issues/2).
Read alongside [DECISIONS.md](../DECISIONS.md). These entries are a scoped design
baseline, not an installed API or compatibility claim; an active technical choice is not a
human-confirmed requirement.

## ISSUE-2-DEC-001 — Scoped implementation authority

- Status: active.
- Authority: human instruction plus DEC-001/002/005; issue-2 kickoff, coordinator session,
  2026-11-04.
- Scope/decision: implement issue #2's contract documentation and synthetic examples with
  requirements analysis, implementation and independent review. Does not authorize the
  remaining backlog, merge, deployment, physical writes, publication or a license choice.
- Conditions: selected issue and reviewed candidate only; merge approval stays separate.

## ISSUE-2-DEC-002 — Preservation and representable layouts

- Status: active design baseline, pending commit-specific review/human merge.
- Authority: agent technical design (packet C2-01–06,
  [pinned firmware observations](../SOURCES.md#issue-2-contract-evidence)).
- Scope/decision: preserve omitted existing state; require colors and enumerate defaults for
  new or reused inactive IDs. Counter proven firmware resets with targeted compensation or
  reject before write. Require known allocation and removal behavior, explicit
  old-minus-desired deletion, no silent renumbering; multi-step outcomes remain partial.
  RGB/RGBW widths require range evidence. Zero brightness targets off only with resolved
  false power, preserving remembered brightness; contradictory implicit power changes fail.
  One-call transition uses 100 ms units with half-up rounding.
- Conditions: verified adapter/profile and bounded deadline; unknown firmware, topology or
  unrepresentable requests fail safely. Hardware support unproven.
- Affected: CTRL-01, SEG-01–04; T04–T10.

## ISSUE-2-DEC-003 — Preset storage, snapshots and deferred save/restore

- Status: active design baseline, pending commit-specific review/human merge.
- Authority: agent technical design and source observation (C2-07–09,
  [pinned source](../SOURCES.md#issue-2-contract-evidence)).
- Scope/decision: persistent IDs 1–250, excluding reserved/temporary entries; unknown
  occupied objects never become free. Lowest-free allocation, explicit collision intent,
  pre-dispatch recheck, full capture readback, no write replay. Capture all current segments
  through storage controls, asynchronously, without deliberate activation. Format-1 exact
  snapshots precede overwrite/delete. Restore execution and PRE-03 supplied-state save stay
  capability-gated Should work, deferred pending a proven single-entry storage-only path; no
  apply/save/restore or bulk-upload shortcut.
- Conditions: reviewed profile, durable storage, bounded persistence polling; snapshot
  inspection is not restore acceptance.
- Affected: PRE-01–05, PLAY-01, REL-02; T11–T13.

## ISSUE-2-DEC-004 — Observed outcomes and MCP result parity

- Status: active design baseline, pending commit-specific review/human merge.
- Authority: agent technical design implementing MCP-02/REL-02 (C2-10).
- Scope/decision: separate application from verification using the contract table; ACK is
  insufficient, mismatch after possible dispatch does not prove never applied. Required
  readback precedes mutation success. Structured envelope and JSON text fallback agree,
  `isError = !ok`; protocol errors remain SDK errors.
- Conditions: same outcome schema on both transports; no transactional or exactly-once
  guarantee inferred from readback.
- Affected: MCP-02, REL-01–03, SEG-04, PRE-05; T08–T14/T18.

## ISSUE-2-DEC-005 — Protected stateless HTTP lifecycle

- Status: active design baseline, pending commit-specific review/human merge.
- Authority: DEC-003 plus agent technical design for the lifecycle/defaults (C2-11/12).
- Scope/decision: default listener-free stdio; explicit HTTP `/mcp`, loopback:8000, one
  worker, SDK stateless JSON responses without session IDs or replay store. Exact
  Host/Origin checks and runtime bearer protection (or equivalent proxy without bypass)
  precede device access. Shared process resources/locks; bounded drain; disconnect,
  reconnect or restart never requeue writes.
- Conditions: #3 selects a compatible SDK; #14 proves protocol behavior; no secrets here.
- Affected: MCP-01/03/04, MULTI-01, OPS-03/05, REL-02; T18–T21.
