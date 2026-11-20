# Issue #6 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-04.

## ISSUE-6-DEC-001 — Dependency strategy

- Status: active for issue #6 delivery; human merge decision remains separate.
- Authority/source: human instruction, 2026-11-04 (no permalink): #5 was implemented first and
  is merged into `main`; #6 builds on it.
- Decision: `wled_set_state` and `wled_patch_segments` build on the #5 read surface
  (`wled_get_state`, `wled_get_effects`, `wled_get_palettes`, catalog cache, per-device lock,
  `redact_info`, normalization helpers); the packet refreshes against post-merge `main`.
- Conditions: does not reopen #5 decisions or authorize deployment, device writes, publication
  or merging; a discovered #5 fix is reported, not folded into #6.

## ISSUE-6-DEC-002 — Patch compensation uses the baseline profile

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

## ISSUE-6-DEC-003 — RGB/RGBW detection from `info.leds.lc`

- Status: active for issue #6 delivery; human merge decision remains separate.
- Authority/source: human instruction, 2026-11-04 (no permalink).
- Decision: per-segment channel width comes from `info.leds.seglc[i]` when its length equals the
  state segment list, else `info.leds.lc` as aggregate fallback for an existing unchanged range.
  New or moved ranges need matching range evidence (SEG-03); unknown evidence fails
  `UNSUPPORTED_CAPABILITY` before POST. Bits as in ISSUE-5-DEC-008 (`CAP_RGB=1`, `CAP_WHITE=2`,
  `CAP_CCT=4`); RGB-only is `(cap & 7) == CAP_RGB`, RGBW has RGB and WHITE set. Color arrays
  carry exactly 3 (RGB) or 4 (RGBW) channels; never padded or trimmed silently.
- Conditions: evidence is read-only `/json/info`; no probe writes or guessing from array widths.
- Extended by [ISSUE-19-DEC-003](issue-19.md#issue-19-dec-003--technical-defaults-for-the-capability-model-and-segment-fields) (TD-19-3).
