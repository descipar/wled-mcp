# Issue #18 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-07.

## ISSUE-18-DEC-001 — Write route for supplied preset and playlist objects

- ID: ISSUE-18-DEC-001
- Recorded date: 2026-11-07
- Status: active for issue #18.
- Authority: human decision (repository owner).
- Source: owner answer in the coordinator session on 2026-11-07 to the Phase-0
  questions of the stage-2 parallel plan (DEC-021), packet
  `.agent-runs/stage2/issue-18/packet.md` (OD-18-1): "alles nach empfehlung"
  (English: "everything as recommended"); no permalink.
- Scope: issue #18 restore, supplied-state save, import and playlist authoring on
  WLED 16.
- Decision: option A. Supplied objects are written through the JSON API one entry at a
  time with an explicit, documented live effect: state objects use the firmware's
  immediate verbatim write path (applied to the lights, then stored exactly);
  playlists use the native playlist save (the playlist starts playing and is stored
  firmware-normalized). Tool descriptions and the dry run state this effect; there is
  no automatic return to the previous lighting. The storage-only PRE-03 variant is
  declared unsupported on WLED 16 and documented.
- Applicability / conditions / expiry: issue #18 on supported firmware (DEC-020). Each
  write takes a snapshot first and verifies by readback. Whole-file `/presets.json`
  upload stays excluded (PRE-04 and the tool contract are unchanged).
- Rationale supplied: none beyond accepting the recommendation; the packet rationale
  (no storage-only JSON path on WLED 16; single-entry writes avoid whole-file
  corruption risk) is agent analysis.
- Affected requirement IDs, files, issues and tests: PRE-03, PRE-04, S2 preset/playlist
  requirements of #18; docs/TOOL-CONTRACT.md; #94 coverage rows.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: issue-18 packet; refresh before Track B.
- Revalidation needed / next action: none before implementation.

## ISSUE-18-DEC-002 — Capability-model owner

- ID: ISSUE-18-DEC-002
- Recorded date: 2026-11-07
- Status: active for issues #18 and #19.
- Authority: coordinator decision (integration owner under DEC-021); the owner did not
  object when it was announced.
- Source: coordinator session on 2026-11-07, Phase-0 packets for #18 (OD-18-2) and #19
  (D-19-1), which proposed different owners.
- Scope: shared capability model between #18 and #19.
- Decision: #19 owns `src/wled_mcp/capabilities.py` and its minimal shared shape. #18
  does not depend on that module; it uses the fields already provided by the read
  models and an interim rule for raw matrix data.
- Applicability / conditions / expiry: Track B order (#18 before #19). If #18 turns out
  to need the module, the coordinator revisits this entry instead of duplicating logic.
- Rationale supplied: the model's open semantics (per-segment capability, RGBW/CCT,
  matrix geometry) are #19's subject; #18 can proceed without it.
- Affected requirement IDs, files, issues and tests: #18, #19 packets.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: issue-18 and issue-19 packets.
- Revalidation needed / next action: none.
