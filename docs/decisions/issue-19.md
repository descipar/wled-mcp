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
