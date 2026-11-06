# Issue #2 decisions

Recorded 2026-11-04 for [issue #2](https://github.com/descipar/wled-mcp/issues/2).
Read alongside [DECISIONS.md](../DECISIONS.md), especially DEC-001–005. These
entries establish a scoped design baseline, not an installed API or compatibility
claim. An active technical choice is not a new human-confirmed requirement.

## ISSUE-2-DEC-001 — Scoped implementation authority

- Status: active.
- Authority: human instruction plus governing workflow rules DEC-001/002/005.
- Source: current issue-2 implementation kickoff in the coordinator session,
  2026-11-04; no source permalink is available. The live issue has no prerequisites
  and belongs to stage 1 through parent #1.
- Scope/decision: implement issue #2's contract documentation and synthetic
  examples with requirements analysis, implementation and independent review.
  This does not authorize the remaining backlog, merge, deployment, physical
  writes, publication or a license choice.
- Conditions/expiry: selected issue and reviewed candidate only; human merge
  approval remains separate. No further behavior answer was requested/received.
- Rationale supplied: follow the defined workflow; no additional rationale supplied.
- Affected: this issue's allowed documentation/examples; C2-01–12.
- Supersession: none.
- Propagation: coordinator passed scope and DEC-001–005 in the requirements packet;
  implementer read them. Reviewer must receive this record at the candidate SHA.
- Revalidation: changed issue scope or candidate requires refreshed review.

## ISSUE-2-DEC-002 — Preservation and representable layouts

- Status: active design baseline, pending commit-specific review/human merge.
- Authority: agent technical design; not a new human confirmation.
- Source: issue-2 requirements packet C2-01–06 and the
  [pinned firmware observations](../SOURCES.md#issue-2-contract-evidence).
- Scope/decision: preserve omitted existing state; require colors and enumerate
  defaults for new/reused inactive IDs. Counter proven firmware resets with
  targeted compensation, or reject before write. Require known allocation and
  removal behavior, explicit old-minus-desired deletion, no silent renumbering.
  Single-object deletion can avoid bulk purge; multi-step outcomes remain partial.
  RGB/RGBW widths require range evidence. Zero brightness targets off only with
  resolved false power, preserving remembered brightness; contradictory implicit
  power changes fail. One-call transition uses 100 ms units with half-up rounding.
- Conditions: verified adapter/profile and bounded deadline; unknown firmware,
  topology or unrepresentable requests fail safely. Hardware support is unproven.
- Design rationale: firmware passthrough can clear names, renumber IDs and couple
  power/brightness; explicit normalization prevents false success and hidden resets.
- Affected: CTRL-01, SEG-01–04; TOOL-CONTRACT/REQUIREMENTS; patch/replace/error
  examples; T04–T10, downstream #5–#7/#10.
- Supersession: replaces provisional issue-2 defaults; no human decision superseded.
- Propagation: implementer applied packet; coordinator forwards IDs to reviewer.
- Revalidation: profile/semantics change refreshes fixtures and review.

## ISSUE-2-DEC-003 — Preset storage, snapshots and deferred save/restore

- Status: active design baseline, pending commit-specific review/human merge.
- Authority: agent technical design and source observation.
- Source: C2-07–09, [pinned presets/API source](../SOURCES.md#issue-2-contract-evidence).
- Scope/decision: persistent IDs 1–250, excluding reserved/temporary entries;
  unknown occupied objects never become free. Lowest-free allocation, explicit
  collision intent, pre-dispatch recheck, full capture readback, no write replay.
  Capture all current segments with brightness/bounds through storage controls;
  capture is asynchronous, without deliberate activation. Format-1 exact snapshots
  precede overwrite/delete. Restore execution and PRE-03 supplied-state save remain
  capability-gated Should work, deferred pending a proven single-entry storage-only
  path; no apply/save/restore or bulk-upload shortcut.
- Conditions: reviewed profile, validated durable storage, bounded persistence
  polling. Snapshot inspection/export is not actual restore acceptance.
- Design rationale: avoid accidental slot reuse, unbacked loss, duplicate saves
  and hidden live-output changes; reviewed source does not prove a safe supplied-
  state/restore path. No rationale is attributed to the owner for these defaults.
- Affected: PRE-01–05, PLAY-01, REL-02; contract/requirements/architecture; preset,
  snapshot/error examples; T11–T13; #8/#9/#10/#13.
- Supersession: settles provisional ranges/defaults; none of DEC-001–005 superseded.
- Propagation: implementer applied packet; coordinator forwards IDs to reviewer.
- Revalidation: safe storage path/firmware profile changes require explicit tests.

## ISSUE-2-DEC-004 — Observed outcomes and MCP result parity

- Status: active design baseline, pending commit-specific review/human merge.
- Authority: agent technical design implementing existing MCP-02/REL-02.
- Source: C2-10 and official MCP tools specification linked in SOURCES.md.
- Scope/decision: separate application from verification using the contract table;
  ACK is insufficient, mismatch after possible dispatch does not prove never
  applied. Required readback precedes mutation success. Structured envelope and
  JSON text fallback agree, `isError = !ok`; protocol errors remain SDK errors.
- Conditions: same outcome schema across both transports; no causal/transactional
  or exactly-once guarantee inferred from readback.
- Design rationale: machine-readable partial/uncertain outcomes prevent unsafe
  automatic replay and apparently successful device errors.
- Affected: MCP-02, REL-01–03, SEG-04, PRE-05; contract/examples; T08–T14/T18.
- Supersession: none.
- Propagation: implementer applied packet; coordinator forwards IDs to reviewer.
- Revalidation: outcome/schema changes require parity and uncertainty tests.

## ISSUE-2-DEC-005 — Protected stateless HTTP lifecycle

- Status: active design baseline, pending commit-specific review/human merge.
- Authority: DEC-003 confirmed transport scope plus agent technical design for
  its concrete lifecycle/defaults; not human confirmation of each CLI choice.
- Source: C2-11/12, live #2 transport update, MCP transport specification.
- Scope/decision: default listener-free stdio; explicit HTTP `/mcp`, loopback:8000,
  one worker, SDK stateless JSON responses without session IDs or replay store.
  Initialization/negotiation remain required. Exact Host/Origin checks and runtime
  bearer protection (or equivalent proxy without bypass) precede device access,
  including loopback/all methods. Shared process resources/locks; bounded drain;
  disconnect/reconnect/restart never requeue writes.
- Conditions: #3 selects a compatible SDK; #14 proves actual protocol behavior.
  Real bind/allowlist/secret values remain integration inputs; no secrets here.
- Design rationale: supports independent multi-client service access with shared
  coordination and a small lifecycle; hub auth alone cannot protect its endpoint.
- Affected: MCP-01/03/04, MULTI-01, OPS-03/05, REL-02; contract/architecture/
  requirements/plan; T18–T21; #14 implementation, #10 acceptance, #11 integration.
- Supersession: settles proposed session strategy; confirmed dual transport remains.
- Propagation: implementer applied packet; coordinator forwards IDs to reviewer.
- Revalidation: SDK/protocol or access/lifecycle changes refresh protocol tests.
