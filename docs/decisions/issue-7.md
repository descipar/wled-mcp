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
- Affected: SEG-05, TOOL-CONTRACT.md, T06/T07. Supersession: none.


## ISSUE-7-OPEN-001 — OPEN, needs human decision: divergences from #6 handling

- Status: unresolved. This is a question, not an approval; nothing here is
  human-confirmed.
- Context: ISSUE-7-DEC-002 (human) says #7 follows #6 where #6 defines handling. The
  current candidate diverges from #6 in three points: (1) `name` limit 32 UTF-8 bytes
  (#6: 32 characters); (2) `grouping`/`spacing` upper bound 255 (#6: no upper bound);
  (3) the resolved `on` is sent alongside `bri` (#6 sends `bri` alone).
- Also awaiting human confirmation: the agent baselines ISSUE-7-DEC-003, -004 and -005
  above (all status "proposed", none confirmed).
- Options: (A) accept the divergences for #7 and open a follow-up issue to align #6
  (stricter name limit, 255 bounds, `on` with `bri`); (B) align #7 to #6 (character
  limit, no upper bounds, `bri` without `on`), accepting the firmware risks described in
  ISSUE-7-DEC-005 for those fields.
- Behavior stays unchanged until the human answers; the coordinator records the answer.
