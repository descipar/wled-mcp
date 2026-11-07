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
