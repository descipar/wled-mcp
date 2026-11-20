# Issue #18 decisions

Read with [DECISIONS.md](../DECISIONS.md). Recorded 2026-11-07.

## ISSUE-18-DEC-001 — Write route for supplied preset and playlist objects

- ID: ISSUE-18-DEC-001
- Recorded date: 2026-11-07
- Status: active for issue #18.
- Authority: human decision (repository owner), coordinator session, 2026-11-07, answering
  OD-18-1 of DEC-021: "alles nach empfehlung" (English: "everything as recommended").
- Scope: issue #18 restore, supplied-state save, import and playlist authoring on WLED 16.
- Decision: option A. Supplied objects are written through the JSON API one entry at a
  time with an explicit, documented live effect: state objects use the firmware's
  immediate verbatim write path (applied to the lights, then stored exactly); playlists use
  the native playlist save (the playlist starts playing and is stored firmware-normalized).
  Tool descriptions and the dry run state this effect; there is no automatic return to the
  previous lighting. The storage-only PRE-03 variant is declared unsupported on WLED 16.
- Conditions: supported firmware (DEC-020); each write takes a snapshot first and verifies
  by readback; whole-file `/presets.json` upload stays excluded (PRE-04).
- Supersedes / superseded by: none.

## ISSUE-18-DEC-002 — Capability-model owner

- ID: ISSUE-18-DEC-002
- Recorded date: 2026-11-07
- Status: active for issues #18 and #19.
- Authority: coordinator decision (integration owner under DEC-021); the owner did not
  object when it was announced.
- Scope: shared capability model between #18 and #19 (OD-18-2, D-19-1).
- Decision: #19 owns `src/wled_mcp/capabilities.py`. #18 does not depend on it; it uses
  the fields of the existing read models and an interim rule for raw matrix data.
- Conditions: Track B order (#18 before #19); if #18 needs the module, the coordinator
  revisits this entry instead of duplicating logic.
- Supersedes / superseded by: none.

## ISSUE-18-DEC-003 — Technical defaults for restore, supplied-state save and bundles

- ID: ISSUE-18-DEC-003
- Recorded date: 2026-11-07
- Status: active for issue #18.
- Authority: technical proposal accepted by the coordinator (not a human decision).
- Source: refreshed requirements packet, coordinator session, 2026-11-07; playlist-restore
  item amended the same day after the independent review (correction round 1).
- Scope: issue #18 only (both PRs). Contract text: docs/contract/presets.md.
- Decision:
  - No firmware-version gate (DEC-020, "warns, does not refuse"); below 16.0.0 tools run and
    rely on readback verification (the warning is #21's mechanism).
  - Restore needs the exact `device_id` and firmware `version` of the snapshot
    (ISSUE-8-DEC-003). Default target is the snapshot's preset ID; an occupied destination
    needs `overwrite=true` and the restore takes its own snapshot first.
  - Tools after `wled_delete_preset`, with ISSUE-20-DEC-001 classes: `wled_list_snapshots`
    (read), `wled_restore_preset` (manage, destructive), `wled_store_preset` (manage,
    destructive; `wled_save_preset` keeps no `state` input); PR B: `wled_save_playlist`
    (manage, destructive), `wled_export_presets` (read), `wled_import_presets` (manage,
    destructive).
  - Coverage: PR A W-PRESET-08 supported, W-PRESET-09 partial; PR B W-PRESET-09 supported,
    export/import added to W-PRESET-01, -07, -08.
  - Playlist restore (amended): a finite `repeat` and shuffle `r` are accepted and checked
    by semantic readback; `end = 255` and negative `repeat` stay refused. While `state.pl`
    > 0 (planning and recheck after the snapshot) the playlist route is refused with
    `PRESET_CONFLICT` without a POST; the source snapshot is protected from pruning.
  - PR B: playlist authoring refuses `end = 255` and negative `repeat`, `shuffle` is
    explicit; export selects `state` and `playlist` entries by default (others only with
    `include_unwritable=true`, never importable); bundles are inline, rejected above 192 KiB
    before any device I/O; at most 50 entries per import; lowest free ID 1-250 in bundle
    order without `id_map`; no LED-range or matrix conversion; snapshots before the first
    write; stop at the first failed, mismatched or unknown entry.
- Conditions: the bundle `format_version` follows TD-21-5 (ISSUE-21-DEC-002); #19 takes over
  the interim matrix rule with the capability module.
- Supersedes / superseded by: none.
