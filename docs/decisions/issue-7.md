# Issue #7 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-04.

## ISSUE-7-DEC-001 — Requirements first, implementation after prerequisites

- Status: active for issue #7 only.
- Authority/source: actual human answer in the current issue-7 workflow session,
  2026-11-04, to the question how to handle the unmet prerequisites #5 and #6;
  no chat permalink exists.
- Scope/decision: prepare only the requirements packet for #7. Implementation
  starts after #5 and #6 are merged; the packet is then refreshed against the new
  main. No code, device access, merge or issue write is authorized by this entry.
- Conditions: this is not a general policy for unmet prerequisites; that question
  remains unresolved in [DECISIONS.md](../DECISIONS.md). Other issues do not reuse it.
- Rationale supplied: none beyond the choice itself.
- Affected: issue-7 requirements packet and the start condition of its
  implementation. Supersession: none.
- Propagation: coordinator passes this ID with the packet to later roles.

## ISSUE-7-DEC-002 — Layout replacement exposes the additional Should options

- Status: active for issue #7 delivery (SEG-05); the human merge decision
  remains separate.
- Authority/source: actual human answer in the same session, 2026-11-04, to the
  packet question D1 (core fields only versus additional Should segment options).
  The answer was the single word "zusätzlich", read as selecting the alternative;
  no chat permalink exists.
- Scope/decision: `wled_replace_layout` also exposes the Should segment options
  `grouping`, `spacing`, `offset`, `reverse`, `mirror`, `selected` and `name`
  beyond the core fields (`id`, `start`, `stop`, `on`, `brightness`, `colors`,
  effect/palette, `speed`, `intensity`).
- Conditions: if #6 already defines handling for any of these fields, #7 follows
  #6 rather than diverging. CCT, 2D and pixel streaming stay out of scope unless
  separately decided. Omitted fields on existing IDs are preserved; new IDs get
  the contract defaults. Requires refreshing the packet's tests and contract text.
- Rationale supplied: none beyond the choice itself.
- Affected: SEG-05, T05–T08 field coverage, TOOL-CONTRACT.md. Supersession: none.
- Propagation: coordinator passes this ID with the packet to later roles.

## ISSUE-7-DEC-003 — Step order and allocation bound (agent technical baseline)

- Status: proposed agent baseline for issue #7; NOT human-confirmed. Review point for
  the reviewer and the human merge decision.
- Authority/source: implementer proposals PD-1, PD-2, PD-4 of the requirements packet,
  recorded with the implementation (2026-11-05).
- Scope/decision: the sequence is [main redirect when its target is already active],
  exact single-object removals ascending, updates/creates chosen so no step overlaps a
  segment still at an old range (creates strictly ascending), [main redirect after the
  creation of a new target]. The main segment moves only when the old main is not part of
  the desired layout, to the lowest desired ID. A new ID `n` is accepted iff
  `n <= max(active)+1`, chained ascending; the bound is a lower bound of the slot count
  because the single-object path never purges. A range cycle is rejected, never solved
  with a temporary segment.
- Conditions: pinned v0.15.1 source evidence only (docs/SOURCES.md#issue-7-layout-evidence);
  no hardware evidence; revisit when H05 or another firmware profile is evidenced.
- Affected: SEG-02, T05/T09, replace.json. Supersession: none.

## ISSUE-7-DEC-004 — Range-capability evidence for new ranges (agent technical baseline)

- Status: proposed agent baseline for issue #7; NOT human-confirmed.
- Authority/source: implementer proposal PD-3 (2026-11-05).
- Scope/decision: colors for a new range are accepted only under profile-0 uniform
  RGB-only evidence: `info.leds.lc` has `(lc & 7) == CAP_RGB` and `info.leds.seglc` is
  absent or aligned with the segment list with every entry RGB-only. Three channels only;
  four channels, any white/CCT bit, a missing or non-integer `lc` or misaligned `seglc`
  give `UNSUPPORTED_CAPABILITY`. Moved existing ranges use their own `seglc` entry
  (RGB-only accepted, four channels refused). A coverage-based rule would reject the
  repository's own replace case (new ID 6 outside the old coverage) and is not used.
- Conditions: on a mixed-bus device active segments may not cover the new range; this is a
  documented profile-0 assumption (ISSUE-6-DEC-002/-003 semantics).
- Affected: SEG-03, T06. Supersession: none.

## ISSUE-7-DEC-005 — Smaller technical limits and no-op behavior (agent technical baseline)

- Status: proposed agent baseline for issue #7; NOT human-confirmed.
- Authority/source: implementer proposals PD-5 to PD-8, PD-11, PD-12 (2026-11-05).
- Scope/decision: grouping 1-255 and spacing 0-255 (pinned `uint8_t` arguments); `name` at
  most 32 UTF-8 bytes (stricter than the 32-character cap of #6, which is unchanged);
  existing IDs without a difference get no POST and an entirely unchanged request is an
  `ok` no-op (`not_attempted`, zero POSTs); reused inactive slots are forced to the
  documented defaults plus `frz=false` and unexposed inherited state is only reported;
  effect/palette are IDs only (as #6); `wled_replace_layout` carries
  `destructive_hint=true`; the resolved `on` is sent with every `bri` because the firmware
  turns an off segment on when `bri>0` is sent alone.
- Conditions: none beyond ISSUE-7-DEC-002 (CCT, 2D and pixel streaming stay out of scope).
- Affected: SEG-05, TOOL-CONTRACT.md, T06/T07.
- Supersession (partial): the name byte limit, the 255 bounds for grouping/spacing and
  the resolved `on` sent with `bri` are superseded by
  [ISSUE-7-DEC-006](#issue-7-dec-006--align-7-with-6-limits-and-bri-handling). The
  remaining parts (no-op behavior, reused-slot defaults, ID-only effect/palette,
  `destructive_hint`) are unchanged and still only proposed.


## ISSUE-7-OPEN-001 — RESOLVED by ISSUE-7-DEC-006: divergences from #6 handling

- Status: resolved; superseded by
  [ISSUE-7-DEC-006](#issue-7-dec-006--align-7-with-6-limits-and-bri-handling). The
  original question is kept below for history.
- Context: ISSUE-7-DEC-002 (human) says #7 follows #6 where #6 defines handling. The
  earlier candidate diverged from #6 in three points: (1) `name` limit 32 UTF-8 bytes
  (#6: 32 characters); (2) `grouping`/`spacing` upper bound 255 (#6: no upper bound);
  (3) the resolved `on` was sent alongside `bri` (#6 sends `bri` alone).
- Options were: (A) accept the divergences and open a follow-up to align #6; (B) align
  #7 to #6. The human chose (B) in DEC-006.
- Still open: ISSUE-7-DEC-003, -004 and -005 remain agent technical proposals, NOT
  human-confirmed (pending review and the human merge decision).

## ISSUE-7-DEC-006 — Align #7 with #6 limits and bri handling

- ID: ISSUE-7-DEC-006
- Recorded date: 2026-11-05
- Status: active for issue #7 only.
- Authority: human decision.
- Source: the human chat message "B" in the current issue-7 workflow session,
  2026-11-05, answering ISSUE-7-OPEN-001 (relayed by the coordinator); no permalink.
- Scope: issue #7 / `wled_replace_layout` only. Not a project default and not a change
  to #6.
- Decision: option B. `wled_replace_layout` aligns with `wled_patch_segments` (#6):
  `name` limit 32 characters, no extra upper bound for `grouping` (>= 1) and `spacing`
  (>= 0), and `bri` is sent as #6 sends it (no extra resolved `on` alongside `bri`; an
  explicit requested `on` is sent). Values the firmware cannot hold are not rejected by
  #7 either.
- Applicability / conditions: valid unless it breaks a hard requirement (SEG-02 new-ID
  defaults, SEG-04 verification, firmware correctness); no such conflict was found. New
  IDs still receive every default explicitly (including `on=true`).
- Rationale supplied: none beyond the choice itself.
- Affected: SEG-05, T05/T06, TOOL-CONTRACT.md, VALIDATION.md, `layouts.py`.
- Supersedes / superseded by: resolves ISSUE-7-OPEN-001; partially supersedes
  ISSUE-7-DEC-005 (see there).
- Propagated to: implementation handoff `.agent-runs/issue-7/implementation.md`.
- Clarification note (coordinator reading, not a separate human answer): "bri handling
  as #6" covers only how `bri` is sent. The brightness=0 rejections of #7
  (`brightness=0` without explicit `on=false` on an ON segment; `on=true` with
  `brightness=0`) follow the general power/brightness contract, stay in force and differ
  from #6, which accepts them.
- Revalidation / next action: known limits shared with #6, documented in
  TOOL-CONTRACT.md: names longer than the firmware buffer (32 bytes ESP8266, 64
  ESP32; multibyte characters count as several bytes) are truncated silently by the
  firmware, grouping/spacing above 255 wrap in the firmware `uint8_t` arguments, and a
  `bri > 0` sent without `on` may switch an off segment on (the final readback then
  reports `VERIFICATION_MISMATCH` against the preserved `on=false`).
