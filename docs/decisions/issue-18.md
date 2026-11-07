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

## ISSUE-18-DEC-003 — Technical defaults for restore, supplied-state save and bundles

- ID: ISSUE-18-DEC-003
- Recorded date: 2026-11-07
- Status: active for issue #18.
- Authority: technical proposal accepted by the coordinator (not a human decision).
- Source: refreshed requirements packet `.agent-runs/stage2/issue-18/packet.md`
  (items marked P, "Newly answered questions"), accepted in the coordinator session on
  2026-11-07 and recorded with the first #18 pull request; the playlist-restore item
  was amended the same day by coordinator decision on the independent review of
  candidate `01d0c81` (correction round 1).
- Scope: issue #18 only (both pull requests); not a project-wide rule.
- Decision:
  - No firmware-version gate in #18 (consistent with DEC-020, "warns, does not
    refuse"): below 16.0.0 the tools run and rely on readback verification; a mismatch
    is reported, not normalized. The below-16 warning is #21's mechanism.
  - Restore requires the exact `device_id` and the exact firmware `version` of the
    snapshot (ISSUE-8-DEC-003 reused). The default target is the snapshot's preset ID;
    an explicit different ID is allowed. An occupied destination needs
    `overwrite=true` and a snapshot that the restore takes itself before the write
    (instead of a caller-supplied prior snapshot).
  - Tools, in registry order after `wled_delete_preset`, with ISSUE-20-DEC-001
    classes: `wled_list_snapshots` (read, not destructive; server snapshot metadata
    only, newest first, invalid files counted), `wled_restore_preset` (manage,
    destructive), `wled_store_preset` (manage, destructive; the supplied-state save,
    `wled_save_preset` keeps no `state` input); in the second pull request
    `wled_save_playlist` (manage, destructive), `wled_export_presets` (read, not
    destructive), `wled_import_presets` (manage, destructive).
  - Coverage statuses (docs/WLED-COVERAGE.md): first pull request W-PRESET-08
    supported, W-PRESET-09 partial, `wled_list_snapshots` listed as a tool without a
    WLED feature row; second pull request W-PRESET-09 supported and the export/import
    tools added to W-PRESET-01, -07 and -08.
  - Playlist restore (amended 2026-11-07 after the independent review of `01d0c81`):
    a finite `repeat` and shuffle (`r`) are accepted and checked by the semantic
    readback (`repeat`, `r`, `ps` order); `end = 255` and a negative `repeat` stay
    refused. The pinned v16.0.1 source stores them unchanged because the save runs
    before the playlist advances (source-derived, hardware pending). While the device
    reports a running playlist (`state.pl` > 0, read during planning and rechecked
    after the snapshot), the playlist route is refused with `PRESET_CONFLICT` without
    a POST (before any snapshot when found during planning; the post-snapshot recheck
    keeps the snapshot), because the firmware could store the running playlist
    instead. The restore's source snapshot is protected from retention pruning.
  - For the second pull request: playlist authoring refuses `end = 255` and a negative
    `repeat`, and `shuffle` is an explicit field (the running-playlist refusal above
    applies to the playlist route there too); export selects `state` and
    `playlist` entries by default (others only with `include_unwritable=true`, never
    importable); bundle field names as in the packet (R18-EXP-05); bundles are passed
    inline and rejected above 192 KiB serialized before any device I/O; at most 50
    entries per import; lowest free ID 1-250 in bundle order when no `id_map` is
    given; no automatic LED-range or matrix conversion; the interim raw-matrix rule of
    ISSUE-18-DEC-002; snapshots before the first write and stop at the first failed,
    mismatched or unknown entry.
- Applicability / conditions / expiry: issue #18. The bundle `format_version` follows
  the TD-21-5 schema rules (to be recorded by #21 as ISSUE-21-DEC-002: integer version,
  higher or unknown versions rejected with the version named, a semantic change bumps
  the version); if that entry is recorded with different wording, the coordinator
  rechecks the bundle items. #19 takes over the interim matrix rule when it adds the
  capability module.
- Rationale supplied: packet analysis (agent): conservative defaults that keep every
  write single-entry, validated before dispatch and verified by readback.
- Affected requirement IDs, files, issues and tests: PRE-03, PRE-04, PLAY-01,
  S2-PRESET-01 to -03; `tests/tool_contract.py`; docs/WLED-COVERAGE.md;
  docs/contract/presets.md; #19, #20, #21.
- Supersedes / superseded by: none.
- Propagated to roles / packet references: issue-18 packet; #19 and #21 packets when
  they are refreshed.
- Revalidation needed / next action: recheck the bundle items when ISSUE-21-DEC-002 is
  recorded.
