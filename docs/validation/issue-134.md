# Issue #134: hardware check of the stage-2 features (2026-11-09)

One owner-authorized hardware run of the stage-2 features on the single test controller, through
the deployed Streamable HTTP service on the hub. Scope and limits follow
[DEC-027](../DECISIONS.md#dec-027--re-stage-the-open-work-by-value-per-effort) and
[ISSUE-134-DEC-001](../decisions/issue-134.md). Host names, addresses, paths and the controller's
name are omitted; "the test controller" is the controller of
[#11](../VALIDATION.md#issue-11-live-deployment-check-2026-11-06) and
[#12](../VALIDATION.md#issue-12-hardware-acceptance-2026-11-06). The detailed run record is a local,
git-ignored file; this page is the committed evidence.

## Target

- Controller: WLED 16.0.1 (build 2606300), ESP32-C3, 133 LEDs, one RGB segment (0 to 133); no CCT,
  RGBW or 2D.
- Path: the deployed HTTP service on the hub, release 0.1.1, access profile `full`, device ceiling
  `manage`, one configured device. A local stdio probe was used once, read-only and with a separate
  data directory, to identify the device; it wrote nothing.
- The hub service was used on purpose so the deployed HTTP path is exercised, not a local build.

## Authorization

Owner chat authority on 2026-11-09 (no permalink): release of the device from #11, permission to do
everything as long as the current state is restored at the end, and to use the HTTP service on the
hub rather than a local version. The playlist question (saving starts it) was asked explicitly and
was covered by that answer. Recorded as [ISSUE-134-DEC-001](../decisions/issue-134.md); it is bounded
to this run and is not standing permission.

## Baseline

State: off, brightness 47, no active preset or playlist; segment 0 on, brightness 255, colors
`[[138,189,255],[0,0,255],[0,0,0]]`, effect 0, speed 128, intensity 128, palette 11. Presets: one
entry (slot 1, a state preset). Groups 0, scenes 0. Snapshots in the service data directory: 3 (from
#12).

## Steps and results

Every write was checked by the service's readback; none failed and none was retried.

1. Read-only: `wled_list_presets`, `wled_export_presets`, `wled_list_snapshots`,
   `wled_list_groups`, `wled_list_scenes`, `wled_get_state`, `wled_get_preset` (slot 1). All answered
   as expected.
2. Group and scene: `wled_save_group` (one device, segment 0) and two scenes through it (master
   brightness 80 with segment speed 100, and the restoring values 47 and 128). `wled_plan_scene` of
   the first scene: strict, one device, preflight ok, payloads `{on:false,bri:80}` and
   `{seg:[{id:0,sx:100}]}`. `wled_apply_scene`: applied and verified; the state readback showed
   brightness 80, speed 100, still off. Applying the restoring scene: applied and verified, readback
   47 and 128. Both scenes and the group were then deleted (removed).
3. Preset store: `wled_store_preset` into the unused slot 5 (power off, segment 0 red), dry run then
   real: applied and verified. Live-output effect, as documented: the segment colors in the device
   state became red although the device stayed off; no preset became active.
4. Playlist: `wled_save_playlist` into slot 6 (one entry, preset 5, one second, repeat 1), dry run
   then real: applied and verified; stored with the entry list, duration, transition, repeat and
   end values requested. The device stayed off and no playlist became active.
5. Bundle: `wled_export_presets` of slot 5 (one entry, 528 bytes, importable), then
   `wled_import_presets` with the id map 5 to 7, dry run then real: applied and verified (state
   route, no backup needed).
6. Restore and cleanup: `wled_delete_preset` of slot 7 (snapshot taken), then `wled_restore_preset`
   from that snapshot into slot 7: applied and verified, no overwrite. Slots 7, 6 and 5 were then
   deleted, each with a snapshot.
7. `wled_patch_segments` set segment 0 colors back to the baseline: applied and verified.

## Final state

Off, brightness 47, no active preset or playlist; segment 0 identical to the baseline; presets: slot
1 only, its content identical to the baseline (`wled_get_preset`); groups 0, scenes 0. The LEDs were
never lit, because every test preset was stored with power off.

## Acceptance criteria of #134

| Criterion | Result |
| --- | --- |
| Read-only first: preset list and export, group and scene listing, plan of a one-device scene | Met (step 1 and the plan in step 2) |
| Group and scene definitions stored as local files, planned, applied to one device, verified by readback, deleted | Met (step 2) |
| Preset store, import and restore on one unused slot with snapshots, with the documented live-output effect, then cleanup; playlist only if the owner accepts that saving starts it | Met (steps 3 to 6); the playlist was run because the owner's answer covered it |
| Every write verified by readback; state, segment and preset list equal the state before; the record names what could not be shown | Met for state, segment and preset list. Not fully restored: four new snapshots remain in the service data directory (see below). The list of items not shown follows below |
| README limitations and VALIDATION.md "Known limitations" updated to what was verified | Met by this change |

## Not restored

The four snapshots written by the run (slot 7 deleted and restored, then slots 7, 6 and 5 deleted)
remain in the service data directory on the hub, in addition to the three from #12. The tools have
no snapshot-delete operation, so they were not removed; they are the restore source for those
slots and hold copies of the test presets only.

## Not shown

- Multi-device scenes, CCT, RGBW and 2D (refusal paths are covered by tests, not hardware).
- Tool profiles and `discover`.
- H07 and the live rollback (they stay with [#25](https://github.com/descipar/wled-mcp/issues/25)).
- Restore with `overwrite=true` onto an occupied slot.
- Playlist import.
- Firmware writes, reboot persistence and other controllers or firmware versions.
- Visible output of any of the tested presets (the LEDs stayed off by design).
- A restore of a playlist preset from its snapshot (only a state preset was restored).
