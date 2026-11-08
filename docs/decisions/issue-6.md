# Issue #6 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-04.

## ISSUE-6-DEC-001 — Dependency strategy

- Status: active for issue #6 delivery; human merge decision remains separate.
- Authority/source: actual human instruction in the current session, 2026-11-04,
  that issue #5 was implemented first and is now merged into `main`; #6 starts on
  that foundation. No chat permalink exists.
- Scope/decision: implementation of #6 (`wled_set_state` and
  `wled_patch_segments`) builds on the read-tool surface delivered by #5
  (`wled_get_state`, `wled_get_effects`, `wled_get_palettes`, catalog cache, per
  -device lock, `redact_info`, normalization helpers). The packet refreshes
  against the post-merge `main` SHA; no coordination with an in-flight #5 branch
  is needed.
- Conditions: this does not reopen or renegotiate #5's accepted decisions. It
  does not authorize deployment, device writes, publication or merging #6. If a
  #5 fix is discovered during #6 implementation, return that finding instead of
  silently extending #6 scope.
- Rationale supplied: #5 was deliberately done first so #6 can reuse its reads.
- Affected: all of #6's acceptance items and its tests. Supersedes: none.
- Propagation: coordinator passes this ID with the packet to the requirements,
  implementer and reviewer roles.

## ISSUE-6-DEC-002 — Patch compensation uses the baseline profile

- Status: active for issue #6 delivery; human merge decision remains separate.
- Authority/source: actual human instruction in the current session, 2026-11-04,
  that `wled_patch_segments` uses the baseline profile 0 for geometry/field
  compensation until a real firmware fingerprint exists. No chat permalink.
- Scope/decision: `wled_patch_segments` compensates documented firmware side
  effects (such as name clearing on geometry changes) under a single statically
  reviewed baseline compensation profile labeled "profile 0". Profile 0 assumes
  the pinned v0.15.1 WLED source behavior (see
  [SOURCES.md](../SOURCES.md#issue-2-contract-evidence)): RGB-only color
  semantics, per-segment capability from `info.leds.seglc`, geometry-change name
  clearing and the single-object segment edit path. When a device's observed
  identity or capability evidence differs materially from profile 0 (for
  example `info.leds.seglc` absent or length-mismatched, or a segment reports
  CCT or white where RGB-only compensation would be wrong), compensation is
  refused with `UNSUPPORTED_CAPABILITY` before any POST.
- Conditions: this is a scoped baseline, not a general multi-profile system.
  Issue #4 (firmware fingerprinting) has not landed a verified profile yet, so
  no runtime profile selection is implemented in #6. When #4 (or a later
  dedicated issue) delivers verified profiles, the compensation plan may widen,
  but that is a later decision. The baseline reflects the pinned source only;
  no actual device observation is claimed. CCT and 2D matrix behavior remain
  out of #6 scope entirely, as in SEG-05/SEG-06.
- Rationale supplied: a reviewed deterministic baseline keeps #6 implementable
  without inventing unverified firmware behavior.
- Affected: SEG-01 compensation plan, SEG-03 capability evidence, SEG-04 plan
  display, T04/T06 acceptance tests. Supersedes: none.
- Propagation: coordinator passes this ID with the packet to the requirements,
  implementer and reviewer roles.

## ISSUE-6-DEC-003 — RGB/RGBW detection from `info.leds.lc`

- Status: active for issue #6 delivery; human merge decision remains separate.
- Authority/source: actual human instruction in the current session, 2026-11-04,
  that per-segment channel width is derived from the capability bitfield in
  `/json/info` (`info.leds.lc` aggregate and `info.leds.seglc` per-segment
  position-aligned). No chat permalink.
- Scope/decision: per-segment color-channel width is derived from the capability
  bits already read by #5: `info.leds.seglc[i]` when its length equals the
  state segment list, else `info.leds.lc` as the aggregate fallback for an
  existing unchanged range. New or moved ranges require matching range
  evidence per SEG-03; unknown evidence fails `UNSUPPORTED_CAPABILITY` before
  POST. The same `CAP_RGB=1`, `CAP_WHITE=2`, `CAP_CCT=4` bit layout applies as
  in #5 (ISSUE-5-DEC-008). RGB-only means `(cap & 7) == CAP_RGB`; RGBW means
  `(cap & (CAP_RGB | CAP_WHITE)) == (CAP_RGB | CAP_WHITE)`. Color arrays must
  carry exactly 3 channels for RGB-only and 4 for RGBW; the server never pads
  or trims silently.
- Conditions: evidence source is read-only `/json/info`; no probe writes or
  guessing from array widths. Contract wording in TOOL-CONTRACT.md Segment
  schema (SEG-03) continues to apply.
- Rationale supplied: aligns #6 with the pinned-source-based capability
  interpretation already accepted in #5.
- Affected: SEG-03 validation, SEG-01 patch acceptance, T04/T06 color-channel
  tests. Supersedes: none.
- Propagation: coordinator passes this ID with the packet to the requirements,
  implementer and reviewer roles.
- Extended by [ISSUE-19-DEC-003](issue-19.md#issue-19-dec-003--technical-defaults-for-the-capability-model-and-segment-fields) (TD-19-3) for #19 and later writes.
