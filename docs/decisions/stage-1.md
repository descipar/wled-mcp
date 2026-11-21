# Decisions: stage 1 core (issues #1 to #14)

## Issue #1 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-06.

### ISSUE-1-DEC-001 — OPS-04 remainder and #44 placement at stage-1 close

- ID: ISSUE-1-DEC-001
- Status: active.
- Authority: human decision (repository owner), answers in the coordinator session on 2026-11-06 to
  two questions of the stage-1 completion review; no permalink.
- Scope: stage-1 tracker #1, requirement OPS-04 and issue #44.
- Decision: OPS-04 (Should, diagnostics): the diagnostics on main (application version,
  unknown-capability reporting, categorized error codes, safe configuration diagnostics) count as
  delivered for stage 1; consistent actionable diagnostics for every listed condition (for example
  unavailable backup storage) are deferred to #16. Issue #44 (cosmetic #6 follow-ups) belongs to
  stage 2 under #15 and does not block closing stage 1.
- Conditions: stage-1 close-out; the deferred diagnostics design is governed by #16.
- Affected: OPS-04; REQUIREMENTS.md, TRACEABILITY.md; #1, #16, #44, #15. Supersedes: none.

## Issue #2 decisions

Recorded 2026-11-04 for [issue #2](https://github.com/descipar/wled-mcp/issues/2).
Read alongside [DECISIONS.md](../DECISIONS.md). These entries are a scoped design
baseline, not an installed API or compatibility claim; an active technical choice is not a
human-confirmed requirement.

### ISSUE-2-DEC-001 — Scoped implementation authority

- Status: active.
- Authority: human instruction plus DEC-001/002/005; issue-2 kickoff, coordinator session,
  2026-11-04.
- Scope/decision: implement issue #2's contract documentation and synthetic examples with
  requirements analysis, implementation and independent review. Does not authorize the
  remaining backlog, merge, deployment, physical writes, publication or a license choice.
- Conditions: selected issue and reviewed candidate only; merge approval stays separate.

### ISSUE-2-DEC-002 — Preservation and representable layouts

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

### ISSUE-2-DEC-003 — Preset storage, snapshots and deferred save/restore

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

### ISSUE-2-DEC-004 — Observed outcomes and MCP result parity

- Status: active design baseline, pending commit-specific review/human merge.
- Authority: agent technical design implementing MCP-02/REL-02 (C2-10).
- Scope/decision: separate application from verification using the contract table; ACK is
  insufficient, mismatch after possible dispatch does not prove never applied. Required
  readback precedes mutation success. Structured envelope and JSON text fallback agree,
  `isError = !ok`; protocol errors remain SDK errors.
- Conditions: same outcome schema on both transports; no transactional or exactly-once
  guarantee inferred from readback.
- Affected: MCP-02, REL-01–03, SEG-04, PRE-05; T08–T14/T18.

### ISSUE-2-DEC-005 — Protected stateless HTTP lifecycle

- Status: active design baseline, pending commit-specific review/human merge.
- Authority: DEC-003 plus agent technical design for the lifecycle/defaults (C2-11/12).
- Scope/decision: default listener-free stdio; explicit HTTP `/mcp`, loopback:8000, one
  worker, SDK stateless JSON responses without session IDs or replay store. Exact
  Host/Origin checks and runtime bearer protection (or equivalent proxy without bypass)
  precede device access. Shared process resources/locks; bounded drain; disconnect,
  reconnect or restart never requeue writes.
- Conditions: #3 selects a compatible SDK; #14 proves protocol behavior; no secrets here.
- Affected: MCP-01/03/04, MULTI-01, OPS-03/05, REL-02; T18–T21.

## Issue #3 decisions

Recorded 2026-11-04. Read with [DECISIONS.md](../DECISIONS.md).

### ISSUE-3-DEC-001 — Scoped implementation

- Status: active for #3 candidate delivery; merge approval remains separate.
- Authority/source: human request to implement #3 with the defined workflow, coordinator session,
  2026-11-04; no permalink.
- Scope: implementation/tests, independent review, reviewable PR. No merge, deployment,
  physical-device actions, license selection or publication.
- Affected: C3-01–10. Supersession: none.

### ISSUE-3-DEC-002 — Runtime and artifact reproducibility

- Status: active agent technical baseline, pending review/human merge.
- Authority/source: agent design; PyPI metadata and SDK source inspected 2026-11-04
  ([Sources](../SOURCES.md#issue-3-bootstrap-evidence)).
- Scope: Python 3.13 only, official MCP SDK 2.3.0, locked runtime/dev/build graph, locked hatchling
  1.27.0 without build isolation, private wheel and generated runtime constraints for uvx with
  installed-version verification (uvx does not consume uv.lock).
- Conditions: expand support with checks; no publication/license inferred.
- Affected: C3-01/02/08/09. Supersession: none.

### ISSUE-3-DEC-003 — Safe staged configuration and transport

- Status: active agent technical staging, pending review/human merge.
- Authority/source: agent design under #3/#4/#14 boundaries and ISSUE-2-DEC-004/005; no new human
  behavior confirmation.
- Scope: only schema_version=1/devices=[]; unsupported configuration rejected until #4. Empty
  production registry; programmatic fixture injection in tests. Shared SDK factory and domain
  envelopes; HTTP fails before listening until #14.
- Conditions: bootstrap only; both transports remain required; T18–T21 pending.
- Affected: C3-03–07/10. Supersession: none.

## Issue #4 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-04.

### ISSUE-4-DEC-001 — Scoped implementation authority

- Status: active for issue #4 delivery; human merge decision remains separate.
- Authority/source: human request to implement #4 with the defined workflow, 2026-11-04 (no
  permalink).
- Scope: inventory/client/list-tool foundation, tests, review and PR (C4-01–10). No deployment,
  device calls, merge, license or publication permission; other issue approvals are not reused.

### ISSUE-4-DEC-002 — Validated inventory and fixed endpoint profile

- Status/authority: active agent technical baseline pending review/human merge.
- Decision: strict immutable inventory/settings, configured targets only, list is network-free by
  default, explicit bounded probes, no redirects or environment routing, streamed size/JSON
  limits. HTTPX2 reuses the SDK's locked graph. Limits: [INVENTORY-CLIENT.md](../INVENTORY-CLIENT.md);
  tests T01/T02/T15. Extends issue-3's temporary empty-inventory staging within #4 only.
- No human confirmation of each numeric limit is claimed.

### ISSUE-4-DEC-003 — Deadline, uncertain writes and reconciliation

- Status/authority: active agent design under REL-01–03 and issue-2 outcome rules; evidence
  [HTTPX2 documentation](../SOURCES.md#issue-4-client-evidence).
- Decision: one total deadline covers lock wait, preparation, write and readback; only safe
  transient reads retry once, writes never retry. 20 ms required before dispatch, 25% (up to one
  second) reserved for readback. ACK alone is not proof; a matching readback verifies, mismatch or
  unavailable stays uncertain; cancellation after dispatch may have applied.
- Conditions: internal mocked foundation; no public setter, firmware adapter or exactly-once claim.

### ISSUE-4-DEC-004 — One resource graph per process

- Status/authority: active agent design implementing MCP-04/MULTI-01 foundation.
- Decision: client, immutable inventory, locks, metadata container and inert backup handle are
  process-owned, shared by operation closures, opened and closed in one async lifecycle;
  per-device locks span preparation through verification.
- Conditions: one worker only; logical shared-session tests are not actual Streamable HTTP T19;
  cache freshness, snapshots and HTTP lifecycle remain #5/#8/#14.

### ISSUE-4-DEC-005 — T19/MCP-04 acceptance scoped to the logical foundation

- Status: active for issue #4 acceptance only.
- Authority/source: human answer, 2026-11-05 (no permalink), to whether #4 may count as satisfied
  by the logical foundation with actual HTTP T19 tracked in #14.
- Decision: the merged logical foundation (ISSUE-4-DEC-004) counts as #4's T19/MCP-04
  acceptance; actual concurrent Streamable HTTP evidence (T19) is proven in #14. Not a general
  rule and does not waive T19 for #14.

## Issue #5 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-04.

### ISSUE-5-DEC-001 — Scoped implementation authority

- Status: active for issue #5 delivery; human merge decision remains separate.
- Authority/source: human request to implement issue #5 using the defined workflow, current
  session, 2026-11-04.
- Scope: read-only state/info/catalog tools, tests, documentation, independent review and PR.
  No deployment, physical device calls, merge, license or publication; does not authorize
  #6–#14.

### ISSUE-5-DEC-002 — Read surface, freshness and error mapping

- Status/authority: active agent technical baseline pending review/human merge.
- Decision: three read tools (`wled_get_state`, `wled_get_effects`, `wled_get_palettes`).
  State and info are never cached; each call reads fresh under one deadline (not an atomic
  snapshot). Unreported capabilities are `null`, not `false`. Problems are envelope errors
  with existing codes. A 4th color channel is trimmed only for a proven RGB-only segment.
  Diagnostics cover server version and unknown capabilities (partial OPS-04).

### ISSUE-5-DEC-003 — Catalog identity, placeholders and optional fxdata

- Status/authority: active agent technical baseline; not human-confirmed.
- Decision: catalog ID is the array index of the device list, preserved without reindexing.
  Count mismatch warns. Placeholder slots are flagged and not name-matched. `/json/fxdata`
  is optional, never a name source; failure yields `ok=true` with metadata unavailable.

### ISSUE-5-DEC-004 — Catalog cache and firmware-aware invalidation

- Status/authority: active agent technical baseline; not human-confirmed.
- Decision: per-device/per-kind cache with TTL (`catalog_cache_seconds`, 0 disables) and
  `refresh`. A non-refresh hit performs one fresh info read; changed `ver`/`vid`
  invalidates; an info failure returns an error. Expired entries are never served; a failed
  refresh keeps the old entry.

### ISSUE-5-DEC-005 — Name resolution as internal shared helper

- Status/authority: active agent technical baseline; not human-confirmed.
- Decision: unique exact, then unique case-folded match; otherwise `AMBIGUOUS_NAME` with
  bounded candidates; no fuzzy auto-resolve. No new public parameter; end-to-end use is #6.
- Closed out by #149: `wled_patch_segments` and `wled_replace_layout` accept names through
  this resolver; see [segment names](../contract/segment-names.md).

### ISSUE-5-DEC-006 — Raw info redaction

- Status/authority: active agent default, open to human change.
- Decision: remove `mac`, `ip` and `wifi.bssid` from `raw.info`, listing removed keys
  (runtime output, separate from commit privacy, DEC-005).

### ISSUE-5-DEC-007 — Reads use the per-device lock

- Status/authority: active agent technical baseline; not human-confirmed.
- Decision: read tools run through the per-device operation (lock plus one deadline); reads
  on one device serialize, different devices stay independent, concurrent catalog misses are
  single-flight. `refreshed` means a cache bypass was requested; `source` states provenance.

### ISSUE-5-DEC-008 — Capability source in firmware output

- Status/authority: active agent observation from the pinned v0.15.1 source
  ([SOURCES.md](../SOURCES.md)); not verified on hardware.
- Decision: aggregate capability from `info.leds.lc`, per-segment from `info.leds.seglc`
  aligned by position only when its length equals the segment list. Bits RGB=1, W=2, CCT=4;
  RGB-only is `(lc & 7) == 1`. Unavailable effect slots are the literal `RSVD`.

### ISSUE-5-DEC-009 — Helper-level evidence accepted for ambiguous-name criterion

- Status: active for issue #5 acceptance only.
- Authority/source: human answer, current session, 2026-11-04.
- Scope: the single acceptance item "Noncontiguous effect/palette IDs remain unchanged;
  ambiguous names return candidate matches". Not a general rule.
- Decision: the tested internal resolver (`AMBIGUOUS_NAME`, ISSUE-5-DEC-005) is accepted as
  sufficient evidence for that item; public resolution through setters is #6. Does not waive
  H01/H02 or other items. Refines DEC-005's deferral for acceptance purposes only.

## Issue #6 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-04.

### ISSUE-6-DEC-001 — Dependency strategy

- Status: active for issue #6 delivery; human merge decision remains separate.
- Authority/source: human instruction, 2026-11-04 (no permalink): #5 was implemented first and
  is merged into `main`; #6 builds on it.
- Decision: `wled_set_state` and `wled_patch_segments` build on the #5 read surface
  (`wled_get_state`, `wled_get_effects`, `wled_get_palettes`, catalog cache, per-device lock,
  `redact_info`, normalization helpers); the packet refreshes against post-merge `main`.
- Conditions: does not reopen #5 decisions or authorize deployment, device writes, publication
  or merging; a discovered #5 fix is reported, not folded into #6.

### ISSUE-6-DEC-002 — Patch compensation uses the baseline profile

- Status: active for issue #6 delivery; human merge decision remains separate.
- Authority/source: human instruction, 2026-11-04 (no permalink).
- Decision: `wled_patch_segments` compensates documented firmware side effects (such as name
  clearing on geometry changes) under one statically reviewed "profile 0" based on the pinned
  v0.15.1 source ([SOURCES.md](../SOURCES.md#issue-2-contract-evidence)): RGB-only colors,
  per-segment capability from `info.leds.seglc`, geometry-change name clearing, single-object
  segment edit path. If a device's evidence differs materially (`seglc` absent or length
  mismatch, CCT or white reported), compensation is refused with `UNSUPPORTED_CAPABILITY`
  before any POST.
- Conditions: a scoped baseline, not a multi-profile system; no runtime profile selection until
  #4 or a later issue delivers verified profiles; no device observation claimed; CCT and 2D
  stay out of scope (SEG-05/SEG-06).

### ISSUE-6-DEC-003 — RGB/RGBW detection from `info.leds.lc`

- Status: active for issue #6 delivery; human merge decision remains separate.
- Authority/source: human instruction, 2026-11-04 (no permalink).
- Decision: per-segment channel width comes from `info.leds.seglc[i]` when its length equals the
  state segment list, else `info.leds.lc` as aggregate fallback for an existing unchanged range.
  New or moved ranges need matching range evidence (SEG-03); unknown evidence fails
  `UNSUPPORTED_CAPABILITY` before POST. Bits as in ISSUE-5-DEC-008 (`CAP_RGB=1`, `CAP_WHITE=2`,
  `CAP_CCT=4`); RGB-only is `(cap & 7) == CAP_RGB`, RGBW has RGB and WHITE set. Color arrays
  carry exactly 3 (RGB) or 4 (RGBW) channels; never padded or trimmed silently.
- Conditions: evidence is read-only `/json/info`; no probe writes or guessing from array widths.
- Extended by [ISSUE-19-DEC-003](stage-2.md#issue-19-dec-003--technical-defaults-for-the-capability-model-and-segment-fields) (TD-19-3).

## Issue #7 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-04. No chat permalinks exist.

Delegation (applies to DEC-003 to DEC-005 and DEC-007 to DEC-009): in chat messages of 2026-11-05 the owner delegated the choice to the main session ("entscheide du bei dec 003 bis 005 wie du es am besten findest in hinblick auf das ganze projekte und zukünftige stages" (English: "you decide on dec 003 to 005 as you think best with regard to the whole project and future stages"); "bei den weiteren offen delegiere ich das auch an dich zum entscheiden" (English: "for the further open points I delegate the decision to you as well")). The content was decided by the main session under that delegation, not dictated by the owner; scope is issue #7 only, never generalized.

### ISSUE-7-DEC-001 — Requirements first, implementation after prerequisites

- Status: active for issue #7 only.
- Authority/source: human answer in the issue-7 workflow session, 2026-11-04, on the unmet prerequisites #5 and #6.
- Scope/decision: prepare only the requirements packet for #7; implementation starts after #5 and #6 are merged and the packet is refreshed against the new main. No code, device access, merge or issue write is authorized.
- Conditions: not a general policy for unmet prerequisites (still unresolved in [DECISIONS.md](../DECISIONS.md)).

### ISSUE-7-DEC-002 — Layout replacement exposes the additional Should options

- Status: active for issue #7 delivery (SEG-05); the human merge decision remains separate.
- Authority/source: human answer, 2026-11-04, to packet question D1 ("zusätzlich" (English: "additionally")).
- Scope/decision: `wled_replace_layout` also exposes the Should segment options `grouping`, `spacing`, `offset`, `reverse`, `mirror`, `selected` and `name` beyond the core fields (`id`, `start`, `stop`, `on`, `brightness`, `colors`, effect/palette, `speed`, `intensity`).
- Conditions: where #6 defines handling for a field, #7 follows #6. CCT, 2D and pixel streaming stay out of scope. Omitted fields on existing IDs are preserved; new IDs get the contract defaults.

### ISSUE-7-DEC-003 — Step order and allocation bound (agent technical baseline)

- Status: active for issue #7 only, accepted by delegated decision (2026-11-05); originally an implementer proposal (PD-1, PD-2, PD-4), not human-confirmed.
- Authority/source: delegated decision (see top).
- Scope/decision (SEG-02, T05/T09): sequence is [main redirect when its target is already active], exact single-object removals ascending, updates/creates ordered so no step overlaps a segment still at an old range (creates strictly ascending), [main redirect after creation of a new target]. Main moves only when the old main is not in the desired layout, to the lowest desired ID. A new ID `n` is accepted iff `n <= max(active)+1`, chained ascending. A range cycle is rejected, never solved with a temporary segment.
- Conditions: pinned v0.15.1 source evidence only (docs/SOURCES.md#issue-7-layout-evidence), no hardware evidence; revisit with H05 or stage-2 #19.

### ISSUE-7-DEC-004 — Range-capability evidence for new ranges (agent technical baseline)

- Status: active for issue #7 only, accepted by delegated decision (2026-11-05); originally implementer proposal PD-3.
- Authority/source: delegated decision (see top).
- Scope/decision (SEG-03, T06): colors for a new range are accepted only under profile-0 uniform RGB-only evidence: `info.leds.lc` has `(lc & 7) == CAP_RGB` and `info.leds.seglc` is absent or aligned with the segment list, all RGB-only. Four channels, any white/CCT bit, missing or non-integer `lc` or misaligned `seglc` give `UNSUPPORTED_CAPABILITY`. Moved existing ranges use their own `seglc` entry.
- Conditions: on a mixed-bus device active segments may not cover the new range; documented profile-0 assumption (ISSUE-6-DEC-002/-003). Stage-2 #19 extends it deliberately.

### ISSUE-7-DEC-005 — Smaller technical limits and no-op behavior (agent technical baseline)

- Status: active for issue #7 only, accepted by delegated decision (2026-11-05) only for the parts compatible with ISSUE-7-DEC-006; originally PD-5 to PD-8, PD-11, PD-12.
- Authority/source: delegated decision (see top).
- Scope/decision (SEG-05, T06/T07): unchanged IDs get no POST and a fully unchanged request is an `ok` no-op (`not_attempted`, zero POSTs); reused inactive slots are forced to the documented defaults plus `frz=false`, unexposed inherited state only reported; effect/palette are IDs only; `wled_replace_layout` carries `destructive_hint=true`; grouping 1-255, spacing 0-255, `name` at most 32 bytes and the resolved `on` sent with every `bri` were set here.
- Supersession (partial): the name limit, the 255 bounds and the `on`-with-`bri` rule are superseded by [ISSUE-7-DEC-006](#issue-7-dec-006--align-7-with-6-limits-and-bri-handling); the rest is unchanged.

### ISSUE-7-OPEN-001 — RESOLVED by ISSUE-7-DEC-006: divergences from #6 handling

- Status: resolved; superseded by [ISSUE-7-DEC-006](#issue-7-dec-006--align-7-with-6-limits-and-bri-handling). The question was whether to keep three divergences from #6 (name 32 bytes vs characters, 255 upper bound for grouping/spacing, `on` sent with `bri`) or align #7 to #6; the owner chose alignment.

### ISSUE-7-DEC-006 — Align #7 with #6 limits and bri handling

- ID: ISSUE-7-DEC-006
- Status: superseded (2026-11-05) by [ISSUE-48-DEC-001](hardening.md#issue-48-dec-001--shared-67-handling-of-firmware-segment-limits) for the name limit, the grouping/spacing bounds and the `bri` sending rule; kept for history. Its new-ID defaults condition remains valid for #7.
- Authority: human decision ("B", answering ISSUE-7-OPEN-001, 2026-11-05).
- Scope: `wled_replace_layout` only (SEG-05).
- Decision: align with `wled_patch_segments` (#6): `name` limit 32 characters, no extra upper bound for `grouping` (>= 1) and `spacing` (>= 0), `bri` sent as #6 sends it (an explicit requested `on` is sent). New IDs still receive every default explicitly (including `on=true`).
- Clarification (confirmed by [ISSUE-7-DEC-007](#issue-7-dec-007--narrow-reading-of-dec-006-confirmed)): "bri handling as #6" covers only how `bri` is sent; the brightness=0 rejections of #7 stay.
- Known shared limits (TOOL-CONTRACT.md): over-long names truncated by the firmware, grouping/spacing above 255 wrap, `bri > 0` without `on` may switch an off segment on (readback then reports `VERIFICATION_MISMATCH`).

### ISSUE-7-DEC-007 — Narrow reading of DEC-006 confirmed

- Status: active for issue #7 only (2026-11-05).
- Authority/source: delegated decision (see top).
- Decision: #7 shares the `bri` sending behavior with #6 but keeps stricter validation: it rejects `brightness=0` without `on=false` on an enabled segment, and `on=true` with `brightness=0` (fails early, avoids importing the #6 `on:true` + `bri:0` defect).

### ISSUE-7-DEC-008 — check_distribution.py edit accepted

- Status: active for issue #7 only (2026-11-05).
- Authority/source: delegated decision (see top).
- Decision: the `scripts/check_distribution.py` edit (tool list and count), outside the packet path list, is accepted as a necessary mechanical consequence of adding a tool.

### ISSUE-7-DEC-009 — Follow-up issue for shared #6/#7 limits

- Status: active for issue #7 only (2026-11-05).
- Authority/source: delegated decision (see top).
- Decision: a follow-up issue for the shared #6/#7 firmware limits (name truncation, grouping/spacing wrap, `bri > 0` switching an off segment on) and the #6 `on:true` + `bri:0` defect is decided; created by the main session as [#48](https://github.com/descipar/wled-mcp/issues/48).

### Still open for issue #7

- The human merge decision (PR #47 stays Draft).
- Hardware evidence (H05) and any firmware profile other than the pinned one.

## Issue #8 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-05. All entries apply to issue #8
only and are not reusable elsewhere. OD-n refers to the open points of the issue-8 packet.

### ISSUE-8-DEC-001 — Restore execution is deferred

- Status: active for issue #8 only.
- Authority/source: human answer in the main session chat, 2026-11-05; no permalink.
- Decision: restore execution is deferred; `wled_restore_preset` is not registered. #8 provides a
  read-only inspect/plan helper and a documented manual restoration procedure. A live restore
  path needs separate sourced requirements and decisions. (PRE-04, T12.)

### ISSUE-8-DEC-002 — Store plus Resources interface; proof by synthetic operation

- Status: active for issue #8 only.
- Authority/source: human answer in the main session chat, 2026-11-05; no permalink.
- Decision: #8 delivers the snapshot store and the `Resources` interface; "backup failure aborts
  before POST" is shown with a synthetic destructive operation (zero POSTs); #9 wires the real
  preset tools. No production destructive preset tool is added by #8.

### ISSUE-8-DEC-003 — Delegated: layout, ID, envelope, compatibility, errors, retention, guard, fsync, source

- Status: active for issue #8 only.
- Authority/source: the owner delegated OD-3 to OD-10 to the main session (chat, 2026-11-05); the
  main session accepted the requirements agent's defaults. Decided by the main session, not
  dictated by the owner; no permalink.
- Decision:
  - OD-3: layout `backups/<device_id>/<backup_id>.json`; ID `b-<UTC>-<12 hex>`; exclusive create,
    never overwrite.
  - OD-4: reject unknown top-level keys, preserve unknown fields inside `preset`; 1 MiB cap; store
    no MAC, URL or hash.
  - OD-5: restore planning needs exact `device_id` and firmware `version`; a different target
    preset ID only through an explicit target.
  - OD-6: no new error codes.
  - OD-7: retention order `created_at` then `backup_id`; never delete invalid, temporary, foreign
    or symlink files; a prune failure is only a warning.
  - OD-8: repository guard against runtime backups in Git (test and/or `scripts/check_distribution.py`).
  - OD-9: directory fsync best effort, documented, skipped on Windows.
  - OD-10: the caller supplies the freshly read preset object inside the device lock; the store
    does no device I/O.
- Conditions: new decisions during implementation go back to the main session.

## Issue #9 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-05; issue #9 only.

### ISSUE-9-DEC-001 — Content decisions OD-1 to OD-7

- Status: active for issue #9 only.
- Authority/source: the main session relayed a user chat message (2026-11-05) delegating
  content decisions for #9 to the main session, which accepted the requirements agent's
  proposals (delegation not independently verifiable; no permalink). Not dictated by the owner.
- Decision:
  - OD-1: PRE-03 (supplied-state save) and restore execution stay deferred to #13
    (ISSUE-2-DEC-003, ISSUE-8-DEC-001).
  - OD-2: `wled_save_preset` with `overwrite=true` on a playlist is `UNSUPPORTED_CAPABILITY`
    without snapshot or POST; state, api-command and unknown entries may be overwritten after a
    snapshot; delete is allowed for any occupied entry after a snapshot.
  - OD-3: types `state | playlist | api-command | unknown` on positive evidence only; only state
    presets and playlists made of state presets are activatable. `state` uses an allowlist of
    top-level keys a firmware save emits (`on`, `bri`, `transition`, `mainseg`, `seg`, `n`, `ql`,
    `ledmap`) with at least one of `on`, `bri`, `seg`; playlists check `playlist.ps` plus a
    persistent `end` preset (`end=255` is not activatable).
  - OD-4: delete is verified against the pinned v0.15.1 source (SOURCES.md); without evidence it
    ships as an explicit `UNSUPPORTED_CAPABILITY` path and returns to the human.
  - OD-5 to OD-7: unrelated changes during verification are warnings; deleting a referenced or
    active preset is allowed with a warning; any difference at the deadline is
    `VERIFICATION_MISMATCH`; save and delete carry the destructive hint, activate does not;
    `overwrite=true` on a free explicit ID needs no snapshot. "Null POSTs" means zero mutating
    POSTs on backup failure or validation rejection. PLAY-01: inspect/activate, reject editing.
- Conditions: new or critical decisions go back to the main session; hardware writes, merge,
  deployment and publication are not covered.
- Supersession: none.

## Issue #10 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-05.

### ISSUE-10-DEC-001 — Traceability file, checker and restricted hardware cells

- ID: ISSUE-10-DEC-001
- Status: active for issue #10 only.
- Authority: technical proposal by the requirements agent (TD-1, TD-2), accepted by the coordinator
  under DEC-001; not a human decision. Source: #10 packet, 2026-11-05.
- Scope: `docs/TRACEABILITY.md`, `scripts/check_traceability.py`, `tests/test_traceability.py`.
- Decision: the requirement-to-evidence matrix lives in `docs/TRACEABILITY.md`, not inside
  VALIDATION.md. A standard-library checker run by a pytest test in ordinary CI fails on: a Must
  requirement without a row; a row or T-scenario without an existing `tests/...py::function` or
  `scripts/...` reference (found with `ast`, nothing imported); an unmapped T01–T21 (T17 may be
  `not applicable: ...`); executed-result wording in the matrix; any hardware/deployment cell other
  than `pending: ...` or `not applicable: ...`.
- Conditions: while hardware/deployment evidence is pending. #11 or #12 may extend the cell
  vocabulary with an evidence link through their own reviewed change; no hardware or deployment claim
  is pre-approved.
- Affected: TEST-01 and every Must requirement; #10, #11, #12. Supersedes / superseded by: none.

## Issue #11 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-06. Sources are coordinator-session instructions without permalink.

### ISSUE-11-DEC-001 — Scoped implementation authority for #11

- ID: ISSUE-11-DEC-001
- Status: active for issue #11 only.
- Authority: human decision (request to start #11 under the defined workflow, DEC-001).
- Scope: #11 implementation on its feature branch (deployment artifacts, docs, device-free tests, review, PR); OPS-01–05, MCP-01–04, TEST-01.
- Decision: implement under the defined workflow. Excluded: merge, deployment to any hub or home server, hub registration, LAN or device contact, physical writes, image/registry/package publication, license selection, router forwarding.
- Conditions: local developer-machine checks (image build, `docker compose config`, loopback run) are allowed and labeled "local developer machine, not target". Live checks H02/H03 and any deployment need a separate instruction naming mode(s) and target.

### ISSUE-11-DEC-002 — Technical deployment defaults TD-1 to TD-9

- ID: ISSUE-11-DEC-002
- Status: active for issue #11 only.
- Authority: technical proposal by the requirements agent, accepted by the coordinator within ISSUE-11-DEC-001; not a human decision, the owner may veto at review.
- Scope: #11 deployment artifacts and documentation (OPS-01–05, MCP-01/03/04).
- Decision:
  - TD-1 Both modes consume a pre-staged versioned directory `/app/binaries/wled-mcp/<version>/` (wheel, `requirements-runtime.txt`, `SHA256SUMS`).
  - TD-2 HTTP base image: official `python:3.13.<patch>-slim-<debian>`, exact tag.
  - TD-3 Image built locally on the target, tag `wled-mcp:<version>`, no push; wheel installed with `--constraint`; non-root UID 10001; exec-form `ENTRYPOINT ["wled-mcp"]`.
  - TD-4 Separate Compose project on the external hub network, no host port, `restart: unless-stopped`, `stop_grace_period` above the 122 s drain bound, read-only root fs, tmpfs `/tmp`, all capabilities dropped, `no-new-privileges`.
  - TD-5 Healthcheck is a TCP connect; an authenticated `ping` is the stronger manual check.
  - TD-6 Credential via Compose `secrets:` from a git-ignored file, read with `--http-token-file`.
  - TD-7 Stdio hub entry sets persistent `UV_CACHE_DIR`, `UV_TOOL_DIR`, `UV_PYTHON_INSTALL_DIR`; a runtime/ABI change needs an environment rebuild.
  - TD-8 Static YAML checks use a dev-only parser; `docker compose config` is opt-in, never required in CI.
  - TD-9 Placement: `deploy/http/Dockerfile` (+ allowlist `.dockerignore`), `examples/compose.http.example.yaml`, hub examples in `examples/`.
- Conditions: implementer refinements are in DEPLOYMENT.md. Network/service names, credential storage, hub field schema and architecture stay deployment-time facts. A human veto of a default needs a refreshed packet and tests.

### ISSUE-11-DEC-003 — Bounded live test installation on the hub host

- ID: ISSUE-11-DEC-003
- Status: active for issue #11 only; the operation it authorized has taken place.
- Authority: human decision.
- Scope: one operation: test installation of release 0.1.0 (source commit `0da1249`) in both modes on one hub host, with one authorized test controller for read tests and master power on/off only (OPS-01/02/05, MCP-01/03/04, H02/H03).
- Decision: installation, hub registration of each mode and the read and power on/off checks were authorized. Not authorized: other controllers, other writes, device configuration changes, publication, merge.
- Conditions: bounded to that run, no standing permission for deployments, updates, rollbacks, removal, other hosts or devices. Controller and host details stay in the local, git-ignored run record. Evidence: [VALIDATION.md](../VALIDATION.md#issue-11-live-deployment-check-2026-11-06).

### ISSUE-11-DEC-004 — Follow-up after the live check

- ID: ISSUE-11-DEC-004
- Status: active for issue #11 only.
- Authority: human decision accepting coordinator proposals ("setze deine Vorschläge um" (English: "implement your proposals")); the mode choice is an agent choice inside that approval.
- Scope: the live installation of ISSUE-11-DEC-003 and its documentation (OPS-05).
- Decision: keep exactly one mode active against the controllers (the coordinator selected Streamable HTTP); remove the stdio hub entry only; document the live results in a follow-up PR; track underscore hostnames in `base_url` as [issue #61](https://github.com/descipar/wled-mcp/issues/61); re-run the #11 completion check afterwards.
- Conditions: no further deployments, update/rollback, HTTP removal, devices or writes beyond ISSUE-11-DEC-003. A later human preference for stdio supersedes the mode choice.

### ISSUE-11-DEC-005 — Live version update/rollback moves to stage 2

- ID: ISSUE-11-DEC-005
- Status: active for issue #11 only.
- Authority: human decision ("rollback und update sehe ich erst in stage 2, das kann hier raus" (English: "I see rollback and update only in stage 2, that can be taken out here")).
- Scope: the live-evidence expectation of #11 (OPS-02/05, MCP-01/03/04, READ-01 deployment cells).
- Decision: live version-to-version update and rollback are not part of #11; they move to stage 2, tracked by [#21](https://github.com/descipar/wled-mcp/issues/21) (S2-COMPAT-03) and [#25](https://github.com/descipar/wled-mcp/issues/25) (S2-LAUNCH-01). The documented update, rollback and recreation procedures in [DEPLOYMENT.md](../DEPLOYMENT.md) stay #11 scope.
- Conditions: narrows only the live-evidence expectation, authorizes no live operation. Superseded in part by ISSUE-11-DEC-008: drain on the target and load measurements are tracked by #12.

### ISSUE-11-DEC-006 — Live removal test of the HTTP service

- ID: ISSUE-11-DEC-006
- Status: active for issue #11 only; the operation it authorized has taken place.
- Authority: human decision ("entfernen des http dienstes teste doch einfach mal" (English: "just test removing the http service")).
- Scope: one operation on the target of ISSUE-11-DEC-003: remove the HTTP hub entry, service container and image per [DEPLOYMENT.md](../DEPLOYMENT.md), then redeploy from the retained release so HTTP stays active (OPS-05).
- Decision: removal test and redeploy authorized. Not authorized: deleting the data directory, credential file or release directory, changes to the hub container or network, other hosts, device writes.
- Conditions: bounded to that run.

### ISSUE-11-DEC-007 — Remaining box 5/6 live checks on the test controller

- ID: ISSUE-11-DEC-007
- Status: active for issue #11 only; the operation it authorized has taken place.
- Authority: human decision ("5 und 6 testen, dafür ist das bekannte [test controller] gerät freigegeben. wenn du dir merkst wie das aktuelle preset dort ist, ist auch das schreiben zum testen freigegeben" (English: "test 5 and 6; the known [test controller] device is released for that. If you remember what the current preset there is, writing for testing is released too"); device name replaced by its role).
- Scope: one operation on the target and single test controller of ISSUE-11-DEC-003: acceptance boxes 5 and 6 (H02 catalog and preset reads per mode, comparison with the device catalog, stdio re-registration and environment rebuild, hub container recreation, removal of the stdio entry); READ-01/02, PRE-01, OPS-01/02/05, MCP-01/04.
- Decision: the checks were authorized; device writes only after recording a restorable baseline. The run recorded a baseline, performed no device writes and found final state and presets equal to it. Hub container recreation interrupted all hub entries for about 30 s, announced to the owner beforehand. Not authorized: other controllers or hosts, hub image updates, device configuration changes, deleting the data directory, publication, merge.
- Conditions: bounded to that run. ISSUE-11-DEC-004 stays in force, so the stdio entry was removed again. Superseded in part by ISSUE-11-DEC-008: drain on the target and load measurements moved to #12.

### ISSUE-11-DEC-008 — Drain and load live checks move to #12

- ID: ISSUE-11-DEC-008
- Status: active for issue #11 only.
- Authority: human decision (answer "b" to the coordinator's options after the completion run for PR #64 returned NEEDS_DECISION).
- Scope: the #11 live-evidence expectation for two checks (MCP-04, OPS-01).
- Decision: two checks move to [#12](https://github.com/descipar/wled-mcp/issues/12): (1) drain of an in-flight call on SIGTERM on the target; (2) load measurements on the target ([DEPLOYMENT.md](../DEPLOYMENT.md)). Automated drain coverage (T21) remains the #11 evidence.
- Conditions: narrows only the #11 pending list; authorizes no live operation; running them needs its own instruction. Supersedes only the wording listing these two as remaining #11 items in ISSUE-11-DEC-005 and ISSUE-11-DEC-007.

## Issue #12 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-06. Human sources are owner replies in the coordinator session, also recorded as coordinator comments on [#12](https://github.com/descipar/wled-mcp/issues/12); no permalinks. Device and host names stay in the local, git-ignored run record.

### ISSUE-12-DEC-001 — One test controller released for #12 hardware testing

- ID: ISSUE-12-DEC-001
- Status: active for issue #12 only.
- Authority: human decision.
- Scope: one designated test controller for the #12 hardware acceptance run (H04-H06; CTRL-01, SEG-01-04, PRE-01-05, READ-01/02, TEST-01).
- Decision: the controller is released completely for #12 testing, including state, segment, layout and preset save/activate/delete writes. Condition: state, segment layout and presets file are captured before any write and restored afterwards; restoration is verified and recorded.
- Conditions: that controller only; no configuration, firmware, reboot or network change; not standing permission. A failed or unverifiable restoration is reported to the owner, not retried blindly.

### ISSUE-12-DEC-002 — Technical defaults for the #12 run

- ID: ISSUE-12-DEC-002
- Status: active for issue #12 only, superseded in part (TD-12-1) by ISSUE-12-DEC-004.
- Authority: technical proposal by the requirements agent, accepted by the coordinator; not a human decision, the owner may veto.
- Scope: #12 live run plan, harness and evidence recording (READ-01/02, SEG-04, PRE-05, OPS-01/02/05, MCP-03/04, TEST-01).
- Decision:
  - TD-12-1 Exercise Streamable HTTP only (ISSUE-11-DEC-004 keeps one active mode); stdio items are cited #11 observations or recorded as not exercised. Superseded in part by [ISSUE-12-DEC-004](#issue-12-dec-004--stdio-via-uvx-stays-in-12-scope).
  - TD-12-2 Preset tests use explicit slot 250, plus an optional lowest-free allocation check deleted immediately; preset 1 is never written.
  - TD-12-3 No controller reboot; persistence is the `/presets.json` readback of PRE-05; power-cycle survival is recorded as not run.
  - TD-12-4 Opt-in standard-library HTTP probe `scripts/hw_http_probe.py` (ping, `tools/list`, read-only tool allowlist, bursts with latency percentiles, body bound); never prints the credential, never run in CI.
  - TD-12-5 [TRACEABILITY.md](../TRACEABILITY.md) keeps its cell forms; ISSUE-10-DEC-001 unchanged.
  - TD-12-6 stdio "own execution context": the #11 stdio hub reads already ran from the hub-managed subprocess; cited, not repeated.
  - TD-12-7 Restoration: R1 presets file byte-equal preferred (parsed-equal with recognized empty test slots and identical preset 1 accepted, difference recorded); R2 state field by field (only `ps`/`pl` markers and empty-vs-absent segment name may differ); R3 configuration file hash equal.
- Conditions: bounded to the #12 run; a material deviation goes back to the coordinator.

### ISSUE-12-DEC-003 — Service stop/start and load on the deployed HTTP service

- ID: ISSUE-12-DEC-003
- Status: confirmed retroactively by the owner for the #12 run only (2026-11-06); issue #12 only.
- Authority: coordinator interpretation of the instruction to implement #12 and of acceptance box 7; confirmed retroactively by the owner ("ja, war in ordnung" (English: "yes, that was fine")) after the coordinator announced the plan and asked about two short outages of about 2 s. Not standing permission.
- Scope: the deployed Streamable HTTP service of #11 on the existing target (MCP-04, OPS-01/05; drain D1-D3, load L1-L6).
- Decision: stopping and starting the service (SIGTERM drain checks) and load measurements against it are within #12 scope. Not authorized: image rebuild, inventory or secret edits, hub entry or hub container changes, other hosts or services.
- Conditions: bounded to the #12 run; the service is left running as the one active mode (ISSUE-11-DEC-004). Source context: [ISSUE-11-DEC-008](#issue-11-dec-008--drain-and-load-live-checks-move-to-12) asked for an own instruction.

### ISSUE-12-DEC-004 — stdio via uvx stays in #12 scope

- ID: ISSUE-12-DEC-004
- Status: active for issue #12 only.
- Authority: human decision ("nein, auch stdio in #12" (English: "no, stdio in #12 too")).
- Scope: the remaining #12 acceptance work (MCP-04, OPS-01/02/05, CTRL-01, SEG-01-04, PRE-01-05, TEST-01).
- Decision: stdio via uvx stays in #12 scope; the stdio live checks (drain when the entry is stopped, load, H04-H06 as applicable) are required and not moved to stage 2. Supersedes TD-12-1 of ISSUE-12-DEC-002 for the remaining work; the first run's HTTP-only scope stays as recorded.
- Conditions: defines scope, not an operation approval (second run: ISSUE-12-DEC-005).

### ISSUE-12-DEC-005 — Authorization of the second #12 live run

- ID: ISSUE-12-DEC-005
- Status: used by the second #12 live run on 2026-11-06; expired after that run.
- Authority: human decision ("ja zu den 3 fragen" (English: "yes to the 3 questions")).
- Scope: the deployed HTTP service and hub entry on the target, a temporary stdio hub entry on the same hub, and the test controller of ISSUE-12-DEC-001.
- Decision: (1) update the HTTP deployment to a build from current main and stop/start it; (2) temporarily register a stdio hub entry and disable the HTTP entry during the stdio tests, then remove the stdio entry and re-enable HTTP; (3) reuse the test controller with state, layout and presets captured and restored. No test may depend on a quick human reaction.
- Conditions: this run only. ISSUE-12-DEC-001 conditions apply to controller writes; ISSUE-11-DEC-004 held because HTTP was disabled while stdio was registered. Evidence: [VALIDATION.md](../VALIDATION.md#issue-12-hardware-acceptance-run-2-2026-11-06).

### ISSUE-12-DEC-006 — stdio host-level no-drain accepted as a documented limitation

- ID: ISSUE-12-DEC-006
- Status: active.
- Authority: human decision ("ja, ist in ordnung. stdio ist ja nur die zweite wahl für heute, ich bevorzuge http" (English: "yes, that is fine. stdio is only the second choice for today anyway, I prefer http")).
- Scope: #12, stdio via uvx and its host-owned subprocess lifecycle (MCP-04 drain evidence).
- Decision: the MCP host (MCPHub) closing the stdio connection on entry disable or stop without draining in-flight calls (second run) is accepted as a documented limitation for #12. Streamable HTTP is the preferred mode; no code change.
- Conditions: #12 and the stdio host lifecycle only; not a deprecation of stdio or change of the two-transport scope. Guidance stays: read state before retrying a cut-off write. ISSUE-12-DEC-004 unchanged. Evidence: [VALIDATION.md](../VALIDATION.md#issue-12-hardware-acceptance-run-2-2026-11-06).

### ISSUE-12-DEC-007 — Remaining #12 scope after the second run, and a third run

- ID: ISSUE-12-DEC-007
- Status: active for issue #12; item 2 (the run authorization) was used by the third #12 live run on 2026-11-06 and expired after that run.
- Authority: human decision ("stimme zu" (English: "I agree")) to the coordinator's six-point proposal; item 6 also recorded on [#25](https://github.com/descipar/wled-mcp/issues/25).
- Scope: items left open after the second run (boxes 1, 3 and 7 of #12, relevance of H07); H02, H04, H07, MCP-04.
- Decision:
  1. H02: comparison "with the WLED UI" is satisfied by comparing tool output with the controller endpoints the UI renders (state, info, effect, palette, preset data); no screenshot required.
  2. One short owner-watched run through the deployed HTTP service on the test controller of ISSUE-12-DEC-001 verifies visible effect animation, a speed change and (owner request) brightness transitions (E3); capture before, restore after. Authorizes the third run only.
  3. stdio H04 as exercised in the second run (power/brightness rules, verified color and effect writes via `wled_replace_layout` and `wled_patch_segments`) is sufficient; same domain code as HTTP.
  4. stdio drain evidence at host level is sufficient (ISSUE-12-DEC-006); no server-side SIGTERM observation in stdio mode.
  5. stdio load measured through the hub within its rate limit is sufficient; HTTP is fully measured; load beyond the rate limit or without the hub hop is not required.
  6. Live H07 (unreachable configured controller on the target) moves to stage 2 ([#25](https://github.com/descipar/wled-mcp/issues/25)); mocked coverage (T02, T09) remains the stage-1 evidence; a live run needs its own authorization.
- Conditions: #12 only; item 2 bounded to the third run, HTTP entry and one controller; items 1 and 3-5 are sufficiency rules for #12, not general rules. Narrows ISSUE-12-DEC-004 without removing stdio. Evidence: [VALIDATION.md](../VALIDATION.md#issue-12-hardware-acceptance-run-3-2026-11-06).

### ISSUE-12-DEC-008 — No separate visual check of an intensity change for H04

- ID: ISSUE-12-DEC-008
- Status: active for issue #12 only.
- Authority: human decision ("rückmeldung und speedtest genügen" (English: "feedback and the speed test are sufficient")).
- Scope: the H04 item "speed/intensity visible behavior" for #12 (CTRL-01).
- Decision: no separate visual check of an intensity change is needed. Verified readback of intensity writes (run 1 H04) plus the owner-confirmed visible speed change of run 3 (E2) are sufficient. Complements ISSUE-12-DEC-007 item 2.
- Conditions: #12 only; not a general rule that readback replaces visual checks; no new hardware run authorized. Evidence: [VALIDATION.md](../VALIDATION.md#issue-12-hardware-acceptance-run-3-2026-11-06).

## Issue #13 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-06.

### ISSUE-13-DEC-001 — Should/Later scope for stage 1

- ID: ISSUE-13-DEC-001
- Recorded date: 2026-11-06
- Status: active for issue #13 and the stage-1 scope boundary it defines.
- Authority/source: human decision, owner answers in the coordinator session, 2026-11-06, to two
  grouped questions of the requirements packet (Q1: option A; Q2: accept as proposed); no
  permalink.
- Scope: stage-1 inclusion/deferral of DEV-03, SEG-05, SEG-06, PRE-03, PLAY-01, ADV-01, ADV-02.
- Decision:
  - DEV-03 inventory change: stage 1 provides a documented restart procedure with rollback to the
    previous inventory file; no new code. In-process reload and a configuration validate command
    are deferred to #16.
  - SEG-05: implemented segment options count as delivered; CCT, 2D and the remaining segment
    fields are deferred to #19.
  - PRE-03 supplied-state preset save, a restore tool and playlist authoring are deferred to #18.
  - ADV-01 restricted raw state patch is excluded from stage 1; enabling it stays rejected at
    startup; no owning issue.
  - ADV-02 timers and SEG-06 pixel art/realtime streaming are excluded; no new issue.
- Conditions: stage 1 scope; deferred items are governed by their owning issues. Resolves the
  "deferred to #13" items of ISSUE-2-DEC-003, ISSUE-8-DEC-001 and ISSUE-9-DEC-001 OD-1 by moving
  them to #18. Affects DEV-03, SEG-05/06, PRE-03/04, PLAY-01, ADV-01/02, T17.

### ISSUE-13-DEC-002 — Completion handling of conditional acceptance boxes

- ID: ISSUE-13-DEC-002
- Recorded date: 2026-11-06
- Status: active for issue #13 only; technical proposal accepted by the coordinator, not a human
  decision; the owner may veto before #13 is closed.
- Decision: acceptance boxes whose condition is shown false (raw state not included; no newly
  included behavior; no scope expansion) are checked with the evidence line "not applicable:
  <reason>, ISSUE-13-DEC-001". The T17 traceability cell keeps its "not applicable" form and
  cites ISSUE-13-DEC-001.

## Issue #14 decisions

Recorded 2026-11-05. Read with [DECISIONS.md](../DECISIONS.md). Only ISSUE-14-DEC-001
carries human authority; ISSUE-14-DEC-002 to -005 are agent technical designs refining the
documented contract, vetoable at review.

### ISSUE-14-DEC-001 — Scoped implementation authority

- Status: active for the #14 candidate; merge approval remains separate.
- Authority/source: human request to implement #14 with the defined workflow (DEC-001),
  coordinator session, 2026-11-05.
- Scope: implementation, tests, documentation, independent review and a PR. No merge,
  deployment, device or LAN action, publication, license selection or image/registry release.
- Supersession: none. Ends ISSUE-3-DEC-003's "HTTP fails before listening until #14" for
  this candidate only.

### ISSUE-14-DEC-002 — Access pipeline

- Status: active agent technical design, pending review/human merge.
- Authority/source: agent design checked against SDK 2.3.0, starlette 1.10.0, uvicorn 0.54.0;
  contract [TOOL-CONTRACT.md](../TOOL-CONTRACT.md#transport-access-and-lifecycle).
- Decision: an own pure-ASGI guard is the outermost layer and answers from headers only, in
  order: Host (exact allowlist) 403; Origin (exact allowlist when present) 403; bearer 401
  with `WWW-Authenticate: Bearer`; path other than `/mcp` 404; method other than POST 405;
  then the SDK stateless JSON app with a 256 KiB body limit. The SDK's own Host/Origin
  validation stays as defense in depth but the guard owns the status codes.
  `X-Forwarded-*` is never trusted; rejections log one fixed-class line, never header values.
- Affected: MCP-03, T18/T20.

### ISSUE-14-DEC-003 — Credential and configuration rules

- Status: active agent technical design, pending review/human merge.
- Scope: HTTP startup configuration only; stdio unaffected.
- Decision: exactly one bearer source (`WLED_MCP_HTTP_TOKEN` or `--http-token-file`); 32 to
  512 printable ASCII characters; a file is absolute, regular, at most 1 KiB, read once
  (rotation is a restart). Constant-time comparison over SHA-256 digests; single
  `Authorization: Bearer` header. No lockout or rate limiting in v1. Path fixed at `/mcp`.
  Defaults 127.0.0.1:8000 with allowed hosts `127.0.0.1:8000` and `localhost:8000`; any other
  host or port needs an explicit `--allowed-host`, which replaces the defaults (exact
  `host[:port]` or `scheme://host[:port]`, no wildcards, at most 16 entries). HTTP-only
  options with stdio, option abbreviations and a token CLI value fail with exit 2.
- Affected: MCP-03, OPS-03, T20.

### ISSUE-14-DEC-004 — Lifecycle

- Status: active agent technical design, pending review/human merge.
- Scope: HTTP process lifecycle and disconnect handling.
- Decision: stateless JSON, one worker, no sessions or server streams; a stale
  `Mcp-Session-Id` is ignored and DELETE is 405. One process-owned resource graph, closed
  once after the listener drained. The service owns SIGINT/SIGTERM (SIGBREAK on Windows) so
  a graceful stop exits 0; a second SIGINT forces exit and leaves interrupted writes
  uncertain. Drain timeout is the operation timeout rounded up plus 2 s (maximum 122 s). No
  unauthenticated health route; liveness is a TCP connect or authenticated `ping`. A
  dispatched handler keeps running on client disconnect (observed), so no extra shield.
- Deviation from the packet: resources close after `serve()` returns, not in the ASGI lifespan.
- Affected: MCP-04, REL-02, OPS-05, T21.

### ISSUE-14-DEC-005 — Evidence scope

- Status: active; limits what this candidate may claim.
- Authority/source: ISSUE-4-DEC-005 (actual HTTP T19 belongs to #14).
- Decision: the HTTP evidence is mock and loopback software evidence for T18-T21, not
  deployment, hub integration, resource measurement or hardware evidence (#10/#11, H02/H03);
  resource measurements stay pending; Windows signal delivery is a documented skip.
