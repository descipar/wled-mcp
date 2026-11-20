# Issue #7 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-04. No chat permalinks exist.

Delegation (applies to DEC-003 to DEC-005 and DEC-007 to DEC-009): in chat messages of 2026-11-05 the owner delegated the choice to the main session ("entscheide du bei dec 003 bis 005 wie du es am besten findest in hinblick auf das ganze projekte und zukünftige stages" (English: "you decide on dec 003 to 005 as you think best with regard to the whole project and future stages"); "bei den weiteren offen delegiere ich das auch an dich zum entscheiden" (English: "for the further open points I delegate the decision to you as well")). The content was decided by the main session under that delegation, not dictated by the owner; scope is issue #7 only, never generalized.

## ISSUE-7-DEC-001 — Requirements first, implementation after prerequisites

- Status: active for issue #7 only.
- Authority/source: human answer in the issue-7 workflow session, 2026-11-04, on the unmet prerequisites #5 and #6.
- Scope/decision: prepare only the requirements packet for #7; implementation starts after #5 and #6 are merged and the packet is refreshed against the new main. No code, device access, merge or issue write is authorized.
- Conditions: not a general policy for unmet prerequisites (still unresolved in [DECISIONS.md](../DECISIONS.md)).

## ISSUE-7-DEC-002 — Layout replacement exposes the additional Should options

- Status: active for issue #7 delivery (SEG-05); the human merge decision remains separate.
- Authority/source: human answer, 2026-11-04, to packet question D1 ("zusätzlich" (English: "additionally")).
- Scope/decision: `wled_replace_layout` also exposes the Should segment options `grouping`, `spacing`, `offset`, `reverse`, `mirror`, `selected` and `name` beyond the core fields (`id`, `start`, `stop`, `on`, `brightness`, `colors`, effect/palette, `speed`, `intensity`).
- Conditions: where #6 defines handling for a field, #7 follows #6. CCT, 2D and pixel streaming stay out of scope. Omitted fields on existing IDs are preserved; new IDs get the contract defaults.

## ISSUE-7-DEC-003 — Step order and allocation bound (agent technical baseline)

- Status: active for issue #7 only, accepted by delegated decision (2026-11-05); originally an implementer proposal (PD-1, PD-2, PD-4), not human-confirmed.
- Authority/source: delegated decision (see top).
- Scope/decision (SEG-02, T05/T09): sequence is [main redirect when its target is already active], exact single-object removals ascending, updates/creates ordered so no step overlaps a segment still at an old range (creates strictly ascending), [main redirect after creation of a new target]. Main moves only when the old main is not in the desired layout, to the lowest desired ID. A new ID `n` is accepted iff `n <= max(active)+1`, chained ascending. A range cycle is rejected, never solved with a temporary segment.
- Conditions: pinned v0.15.1 source evidence only (docs/SOURCES.md#issue-7-layout-evidence), no hardware evidence; revisit with H05 or stage-2 #19.

## ISSUE-7-DEC-004 — Range-capability evidence for new ranges (agent technical baseline)

- Status: active for issue #7 only, accepted by delegated decision (2026-11-05); originally implementer proposal PD-3.
- Authority/source: delegated decision (see top).
- Scope/decision (SEG-03, T06): colors for a new range are accepted only under profile-0 uniform RGB-only evidence: `info.leds.lc` has `(lc & 7) == CAP_RGB` and `info.leds.seglc` is absent or aligned with the segment list, all RGB-only. Four channels, any white/CCT bit, missing or non-integer `lc` or misaligned `seglc` give `UNSUPPORTED_CAPABILITY`. Moved existing ranges use their own `seglc` entry.
- Conditions: on a mixed-bus device active segments may not cover the new range; documented profile-0 assumption (ISSUE-6-DEC-002/-003). Stage-2 #19 extends it deliberately.

## ISSUE-7-DEC-005 — Smaller technical limits and no-op behavior (agent technical baseline)

- Status: active for issue #7 only, accepted by delegated decision (2026-11-05) only for the parts compatible with ISSUE-7-DEC-006; originally PD-5 to PD-8, PD-11, PD-12.
- Authority/source: delegated decision (see top).
- Scope/decision (SEG-05, T06/T07): unchanged IDs get no POST and a fully unchanged request is an `ok` no-op (`not_attempted`, zero POSTs); reused inactive slots are forced to the documented defaults plus `frz=false`, unexposed inherited state only reported; effect/palette are IDs only; `wled_replace_layout` carries `destructive_hint=true`; grouping 1-255, spacing 0-255, `name` at most 32 bytes and the resolved `on` sent with every `bri` were set here.
- Supersession (partial): the name limit, the 255 bounds and the `on`-with-`bri` rule are superseded by [ISSUE-7-DEC-006](#issue-7-dec-006--align-7-with-6-limits-and-bri-handling); the rest is unchanged.

## ISSUE-7-OPEN-001 — RESOLVED by ISSUE-7-DEC-006: divergences from #6 handling

- Status: resolved; superseded by [ISSUE-7-DEC-006](#issue-7-dec-006--align-7-with-6-limits-and-bri-handling). The question was whether to keep three divergences from #6 (name 32 bytes vs characters, 255 upper bound for grouping/spacing, `on` sent with `bri`) or align #7 to #6; the owner chose alignment.

## ISSUE-7-DEC-006 — Align #7 with #6 limits and bri handling

- ID: ISSUE-7-DEC-006
- Status: superseded (2026-11-05) by [ISSUE-48-DEC-001](issue-48.md#issue-48-dec-001--shared-67-handling-of-firmware-segment-limits) for the name limit, the grouping/spacing bounds and the `bri` sending rule; kept for history. Its new-ID defaults condition remains valid for #7.
- Authority: human decision ("B", answering ISSUE-7-OPEN-001, 2026-11-05).
- Scope: `wled_replace_layout` only (SEG-05).
- Decision: align with `wled_patch_segments` (#6): `name` limit 32 characters, no extra upper bound for `grouping` (>= 1) and `spacing` (>= 0), `bri` sent as #6 sends it (an explicit requested `on` is sent). New IDs still receive every default explicitly (including `on=true`).
- Clarification (confirmed by [ISSUE-7-DEC-007](#issue-7-dec-007--narrow-reading-of-dec-006-confirmed)): "bri handling as #6" covers only how `bri` is sent; the brightness=0 rejections of #7 stay.
- Known shared limits (TOOL-CONTRACT.md): over-long names truncated by the firmware, grouping/spacing above 255 wrap, `bri > 0` without `on` may switch an off segment on (readback then reports `VERIFICATION_MISMATCH`).

## ISSUE-7-DEC-007 — Narrow reading of DEC-006 confirmed

- Status: active for issue #7 only (2026-11-05).
- Authority/source: delegated decision (see top).
- Decision: #7 shares the `bri` sending behavior with #6 but keeps stricter validation: it rejects `brightness=0` without `on=false` on an enabled segment, and `on=true` with `brightness=0` (fails early, avoids importing the #6 `on:true` + `bri:0` defect).

## ISSUE-7-DEC-008 — check_distribution.py edit accepted

- Status: active for issue #7 only (2026-11-05).
- Authority/source: delegated decision (see top).
- Decision: the `scripts/check_distribution.py` edit (tool list and count), outside the packet path list, is accepted as a necessary mechanical consequence of adding a tool.

## ISSUE-7-DEC-009 — Follow-up issue for shared #6/#7 limits

- Status: active for issue #7 only (2026-11-05).
- Authority/source: delegated decision (see top).
- Decision: a follow-up issue for the shared #6/#7 firmware limits (name truncation, grouping/spacing wrap, `bri > 0` switching an off segment on) and the #6 `on:true` + `bri:0` defect is decided; created by the main session as [#48](https://github.com/descipar/wled-mcp/issues/48).

## Still open for issue #7

- The human merge decision (PR #47 stays Draft).
- Hardware evidence (H05) and any firmware profile other than the pinned one.
