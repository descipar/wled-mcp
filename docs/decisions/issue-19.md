# Issue #19 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-07. The capability-model
owner is recorded as [ISSUE-18-DEC-002](issue-18.md#issue-18-dec-002--capability-model-owner).

## ISSUE-19-DEC-001 — Overlapping segments

- ID: ISSUE-19-DEC-001
- Recorded date: 2026-11-07
- Status: active for issue #19.
- Authority: human decision (repository owner).
- Source: owner answer in the coordinator session on 2026-11-07 to the Phase-0
  questions of the stage-2 parallel plan (DEC-021), packet
  `.agent-runs/stage2/issue-19/packet.md` (D-19-2): "alles nach empfehlung"
  (English: "everything as recommended"); no permalink.
- Scope: issue #19 acceptance item "decide overlap/layering explicitly";
  `wled_patch_segments` and `wled_replace_layout`.
- Decision: option B. Overlap stays rejected by default. An explicit request flag
  `allow_overlap=true` in both tools permits it; the plan lists every overlapping pair
  and the render order (higher slot on top), and `blend_mode` (0-16) becomes settable.
- Applicability / conditions / expiry: issue #19 on supported firmware (DEC-020);
  `blend_mode` is settable only where the device reports the field.
- Rationale supplied: none beyond accepting the recommendation; the packet rationale
  (explicit intent, no silent bypass of stage-1 validation) is agent analysis.
- Affected requirement IDs, files, issues and tests: S2-SEG requirements of #19;
  docs/TOOL-CONTRACT.md; patch/layout tests; #94 coverage rows.
- Supersedes / superseded by: extends the stage-1 overlap rejection with an opt-in;
  does not remove it.
- Propagated to roles / packet references: issue-19 packet; refresh before #19 starts.
- Revalidation needed / next action: none before implementation.

## ISSUE-19-DEC-002 — Segment features not exposed

- ID: ISSUE-19-DEC-002
- Recorded date: 2026-11-07
- Status: active for issue #19 and the coverage list (#94).
- Authority: human decision (repository owner).
- Source: owner answer in the coordinator session on 2026-11-07 to the coordinator's
  question about the exclusions proposed in `.agent-runs/stage2/issue-19/packet.md`
  (TD-19-8): "ja, merge #96 und alles nach empfehlung" (English: "yes, merge #96 and
  everything as recommended"); no permalink.
- Scope: segment features of the WLED JSON API that the segment tools do not expose.
- Decision: not exposed are segment repetition `rpt` (creates implicit additional
  segments, contrary to explicit segment IDs), the effect-defaults flag `fxdef`
  (implicit parameter resets) and matrix/panel configuration through `/json/cfg`
  (outside the segment scope). Individual LED control `i` stays excluded by
  ISSUE-13-DEC-001 (SEG-06). Alias and alternative encodings (`len`, the Loxone `lx`/`ly`
  build option, non-array color forms) are not separate features.
- Applicability / conditions / expiry: issue #19 and later stages until a new decision.
- Rationale supplied: none beyond accepting the recommendation; the reasons in
  parentheses are the packet's agent analysis.
- Affected requirement IDs, files, issues and tests: S2-SEG requirements of #19;
  docs/TOOL-CONTRACT.md; docs/WLED-COVERAGE.md excluded rows.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: issue-19 and issue-94 packets.
- Revalidation needed / next action: none.

## ISSUE-19-DEC-003 — Technical defaults for the capability model and segment fields

- ID: ISSUE-19-DEC-003
- Recorded date: 2026-11-08
- Status: active for issue #19 (both pull requests).
- Authority: technical proposal accepted by the coordinator (not a human decision).
- Source: refreshed requirements packet `.agent-runs/stage2/issue-19/packet.md`
  (refresh 1, items TD-19-1 to TD-19-14 and AC-19-01 to AC-19-18), accepted in the
  coordinator session on 2026-11-08 together with the coordinator choices C-19-1 to
  C-19-3 below; recorded with the first #19 pull request.
- Scope: issue #19 only; not a project-wide rule. It applies the human decisions
  ISSUE-19-DEC-001 and -002 and the capability-model ownership of ISSUE-18-DEC-002.
- Decision:
  - TD-19-1 No new tool. Input fields are added to `SegmentPatch`, `LayoutSegment` and
    `SuppliedSegment`, output fields to the `wled_get_state` segment view and
    `capabilities`; no new `required` entry, no removed or renamed field or enum value,
    no tightened schema bound.
  - TD-19-2 Public names and wire keys: `cct` (`cct`, 0-255), `start_y`/`stop_y`
    (`startY`/`stopY`), `reverse_y` (`rY`), `mirror_y` (`mY`), `transpose` (`tp`),
    `map_1d_2d` (`m12`, 0-4), `custom1`/`custom2` (`c1`/`c2`, 0-255), `custom3` (`c3`,
    0-31), `check1`-`check3` (`o1`-`o3`), `sound_simulation` (`si`, 0-3), `segment_set`
    (`set`, 0-3), `freeze` (`frz`), `blend_mode` (`bm`, 0-16) and the request-level
    `allow_overlap` (default false). `SuppliedSegment` uses the wire keys. Custom
    parameters get ranges only; `fxdata` is not parsed.
  - TD-19-3 Per-segment capability evidence: `state.seg[].lc`, else the
    position-aligned `info.leds.seglc` entry, else none. CCT is bit 0x04; four color
    channels need the white bit; a white-only range takes four channels with RGB 0.
    Never decided by product name or firmware version.
  - TD-19-4 New or moved ranges (extends the #7-only ISSUE-7-DEC-004 deliberately):
    `info.leds.lc` is an integer, every active segment's capability equals it and
    contains the required bits; otherwise `UNSUPPORTED_CAPABILITY`. The mixed-bus
    residual risk is documented.
  - TD-19-5 Field presence: an option field is settable only when the target segment's
    fresh readback carries its wire key (a new ID: every active segment); 2D fields need
    `info.leds.matrix` with integer `w`, `h` >= 1. This covers `WLED_DISABLE_2D` builds
    and older firmware without a version gate.
  - TD-19-6 Replace create defaults where TD-19-5 evidence exists: `cct` 127,
    `custom1`/`custom2` 128, `custom3` 16, checks false, `sound_simulation` 0,
    `segment_set` 0, `map_1d_2d` 0, `freeze` false, `blend_mode` 0, orientation false;
    on a matrix a new segment needs explicit `start_y`/`stop_y` (planner rule).
  - TD-19-7 Matrix geometry: X against the width, Y against the height, rectangle
    overlap; a trailing strip range (`start >= width * height`) is read and preserved,
    creating or moving one is `UNSUPPORTED_CAPABILITY`. 1D devices are unchanged.
  - TD-19-8 Plan and dry run carry `capability_evidence` per field (`state_lc`,
    `info_seglc`, `uniform`, `field_present`, `matrix`) and, with `allow_overlap`,
    `overlaps` and `render_order`; `freeze=true` warns that master power-on unfreezes
    all segments.
  - TD-19-9 `src/wled_mcp/capabilities.py` is pure and network-free: `parse_matrix`
    (moved from bundles.py, same semantics), `SegmentCapability`, `DeviceCapabilities`,
    `derive_capabilities(state, info)` and the color helpers that replace the private
    patches.py helpers; the `CAP_*` constants move there and stay importable from
    readmodels.py. No firmware tiering.
  - TD-19-10 Bundles: no behavior change beyond sourcing the matrix and the CCT bit from
    capabilities.py; `format_version` and the `source.capabilities` keys stay, so no
    TD-21-5 bump; new #19 keys in bundle entries stay verbatim-written (residual limit
    in docs/contract/presets.md).
  - TD-19-11 Coverage: the first pull request moves W-SEG-14 to W-SEG-22 from planned to
    partial (read only); the second moves W-SEG-13 to W-SEG-22 to supported, with the
    note changes listed in the packet; W-INFO-02 lists `leds.matrix` and `seg[].lc`.
  - TD-19-12 `wled_store_preset` gains the new wire keys in the second pull request,
    validated by the same capability, field-presence and matrix rules; overlap stays
    rejected there.
  - TD-19-13 Documentation: contract text in docs/contract/segments.md, evidence in
    docs/validation/issue-19.md, one link line each in the "Stage 2 and later files"
    lists; only small in-place corrections elsewhere.
  - TD-19-14 Two pull requests: A (capability model and read side, no change to any
    write payload, validation outcome or bundle behavior) and B (every write-side
    change).
  - Acceptance scenarios AC-19-01 to AC-19-18 as listed in the packet: capability read,
    new read fields, refactor parity (A); CCT, white handling, 2D bounds, the matrix
    X-gap fix, orientation, option bounds, overlap opt-in, replace defaults,
    preservation, uncertain writes, transport parity, store extension (B); no
    version-based refusal below 16.0.0 and hardware honesty (both).
  - Coordinator choices: C-19-1 extend `wled_store_preset` in pull request B (TD-19-12
    stays in #19); C-19-2 two pull requests; C-19-3 start on `main` 57896f9 and merge
    `main` after #105.
- Applicability / conditions / expiry: issue #19 on supported firmware (DEC-020); the
  firmware tier of #21 is not read by any #19 rule (TD-21-6).
- Rationale supplied: packet analysis (agent): evidence-based settability without
  version gates, additive contract changes and a behavior-preserving refactor first.
- Affected requirement IDs, files, issues and tests: S2-SEG-01, S2-SEG-02, S2-T05,
  S2-COMPAT-01/-02, SEG-01 to SEG-05, READ-01, MCP-01/-02, REL-02, PRE-03;
  src/wled_mcp/capabilities.py and the segment, preset and bundle modules;
  docs/contract/segments.md; docs/validation/issue-19.md; docs/WLED-COVERAGE.md;
  tests/test_segment_capabilities.py.
- Supersedes / superseded by: none; ISSUE-18-DEC-003's interim raw-matrix rule is now
  served by capabilities.py with unchanged behavior.
- Propagated to roles / packet references: issue-19 packet refresh 1; implementer and
  reviewer briefs of both pull requests.
- Revalidation needed / next action: none before pull request B.
