# Issue #19 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-07. The capability-model
owner is recorded as [ISSUE-18-DEC-002](issue-18.md#issue-18-dec-002--capability-model-owner).

## ISSUE-19-DEC-001 — Overlapping segments

- ID: ISSUE-19-DEC-001
- Recorded date: 2026-11-07
- Status: active for issue #19.
- Authority: human decision (repository owner), coordinator session, 2026-11-07, answering
  the Phase-0 questions of DEC-021 (D-19-2): "alles nach empfehlung" (English: "everything
  as recommended").
- Scope: `wled_patch_segments` and `wled_replace_layout` overlap handling.
- Decision: option B. Overlap stays rejected by default. An explicit request flag
  `allow_overlap=true` in both tools permits it; the plan lists every overlapping pair and
  the render order (higher slot on top), and `blend_mode` (0-16) becomes settable.
- Conditions: supported firmware (DEC-020); `blend_mode` settable only where the device
  reports the field.
- Supersedes / superseded by: extends the stage-1 overlap rejection with an opt-in.

## ISSUE-19-DEC-002 — Segment features not exposed

- ID: ISSUE-19-DEC-002
- Recorded date: 2026-11-07
- Status: active for issue #19 and the coverage list (#94).
- Authority: human decision (repository owner), coordinator session, 2026-11-07, on the
  exclusions proposed in TD-19-8: "ja, merge #96 und alles nach empfehlung" (English: "yes,
  merge #96 and everything as recommended").
- Scope: segment features of the WLED JSON API that the segment tools do not expose.
- Decision: not exposed are segment repetition `rpt`, the effect-defaults flag `fxdef` and
  matrix/panel configuration through `/json/cfg`. Individual LED control `i` stays excluded
  by ISSUE-13-DEC-001 (SEG-06). Alias and alternative encodings (`len`, the Loxone
  `lx`/`ly` build option, non-array color forms) are not separate features.
- Conditions: issue #19 and later stages until a new decision.
- Supersedes / superseded by: none.

## ISSUE-19-DEC-003 — Technical defaults for the capability model and segment fields

- ID: ISSUE-19-DEC-003
- Recorded date: 2026-11-08
- Status: active for issue #19 (both pull requests).
- Authority: technical proposal accepted by the coordinator (not a human decision).
- Source: refreshed requirements packet (TD-19-1 to TD-19-14, AC-19-01 to AC-19-18),
  coordinator session, 2026-11-08.
- Scope: issue #19 only; applies ISSUE-19-DEC-001/-002 and ISSUE-18-DEC-002.
- Decision (contract text in docs/contract/segments.md):
  - TD-19-1 No new tool; additive input fields on `SegmentPatch`, `LayoutSegment`,
    `SuppliedSegment`, output fields on the `wled_get_state` segment view and `capabilities`.
  - TD-19-2 Public names and wire keys: `cct`, `start_y`/`stop_y` (`startY`/`stopY`),
    `reverse_y` (`rY`), `mirror_y` (`mY`), `transpose` (`tp`), `map_1d_2d` (`m12`, 0-4),
    `custom1`-`custom3` (`c1`-`c3`; 0-255, 0-255, 0-31), `check1`-`check3` (`o1`-`o3`),
    `sound_simulation` (`si`, 0-3), `segment_set` (`set`, 0-3), `freeze` (`frz`),
    `blend_mode` (`bm`, 0-16), request-level `allow_overlap` (default false).
  - TD-19-3 Per-segment capability evidence: `state.seg[].lc`, else the position-aligned
    `info.leds.seglc` entry, else none; CCT is bit 0x04; never by product name or firmware.
  - TD-19-4 New or moved ranges: `info.leds.lc` is an integer, every active segment's
    capability equals it and has the required bits; otherwise `UNSUPPORTED_CAPABILITY`.
  - TD-19-5 An option field is settable only when the target segment's fresh readback
    carries its wire key; 2D fields need `info.leds.matrix` with integer `w`, `h` >= 1.
  - TD-19-6 Replace create defaults where evidence exists (`cct` 127, `custom1`/`custom2`
    128, `custom3` 16, others 0/false); on a matrix a new segment needs explicit
    `start_y`/`stop_y`.
  - TD-19-7 Matrix geometry: X against width, Y against height; a trailing strip range is
    read and preserved, creating or moving one is `UNSUPPORTED_CAPABILITY`.
  - TD-19-8 Plan and dry run carry `capability_evidence` per field and, with
    `allow_overlap`, `overlaps` and `render_order`; `freeze=true` warns that master power-on
    unfreezes all segments.
  - TD-19-9 `src/wled_mcp/capabilities.py` is pure and network-free (`parse_matrix`,
    `SegmentCapability`, `DeviceCapabilities`, `derive_capabilities`, color helpers); no
    firmware tiering.
  - TD-19-10 Bundles: no behavior change beyond sourcing matrix and CCT bit from
    capabilities.py; `format_version` unchanged.
  - TD-19-11 Coverage: W-SEG-14..22 planned to partial (PR A), W-SEG-13..22 to supported
    (PR B); W-INFO-02 lists `leds.matrix` and `seg[].lc`.
  - TD-19-12 `wled_store_preset` gains the new wire keys in PR B under the same rules;
    overlap stays rejected there.
  - TD-19-13 Contract text in docs/contract/segments.md, evidence in
    docs/validation/issue-19.md.
  - TD-19-14 Two pull requests: A (capability model and read side, no write change) and B
    (all write-side changes).
  - Coordinator choices: C-19-1 extend `wled_store_preset` in PR B; C-19-2 two PRs; C-19-3
    start on `main` and merge `main` after #105.
- Conditions: supported firmware (DEC-020); the firmware tier of #21 is not read by any #19
  rule (TD-21-6).
- Supersedes / superseded by: extends ISSUE-6-DEC-003 (see S-2); ISSUE-18-DEC-003's
  interim raw-matrix rule is now served by capabilities.py.
- Amendment (2026-11-08, full review of PR B; coordinator, not a human decision):
  - S-1 `blend_mode` is settable without `allow_overlap`, with field presence only (a
    coordinator reading of ISSUE-19-DEC-001, to be confirmed with the owner at the next
    DEC-022 revalidation).
  - S-2 TD-19-3 extends the ISSUE-6-DEC-003 evidence source from `/json/info` `leds.seglc`
    to `/json/state` `seg[].lc` (read-only); the aggregate fallback for an existing
    unchanged range is kept.
  - (a) A new range keeps the stage-1 RGB-only rule of ISSUE-7-DEC-004 beside TD-19-4.
  - (b) `capability_evidence` appears only when a #19 field is supplied; no colors.
  - (d) In `wled_store_preset` an existing ID with unchanged X and rows uses its own
    evidence, other entries the uniform rule; an existing trailing strip is never moved.
  - N-3 The store's color width keeps the stage-1 aggregate `info.leds.lc` rule.
  - (f) Unapplied or uncertain writes keep the stage-1 outcome mappings (`unknown/mismatch`,
    `applied/mismatch`, `unknown/unknown` with `WRITE_OUTCOME_UNKNOWN`).
  - N-4 A carried nit edit of tests/test_upgrade_compat.py outside the path list was
    coordinator-assigned.
