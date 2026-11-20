# Issue #134: hardware check of the stage-2 features (2026-11-09)

One owner-authorized hardware run of the stage-2 features on the single test controller through the
deployed Streamable HTTP service on the hub. Scope follows
[DEC-027](../DECISIONS.md#dec-027--re-stage-the-open-work-by-value-per-effort) and
[ISSUE-134-DEC-001](../decisions/issue-134.md), bounded to this run and not standing permission.
Host names, addresses and the controller's name are omitted; "the test controller" is the one of
[#11](../VALIDATION.md#issue-11-live-deployment-check-2026-11-06) and
[#12](../VALIDATION.md#issue-12-hardware-acceptance-2026-11-06). The detailed record is a local,
git-ignored file.

## Target and authorization

- WLED 16.0.1 (build 2606300), ESP32-C3, 133 LEDs, one RGB segment; no CCT, RGBW or 2D.
- The deployed HTTP service on the hub, release 0.1.1, profile `full`, device ceiling `manage`, one
  configured device (deliberately the deployed path). One read-only local stdio probe with a separate
  data directory identified the device and wrote nothing.
- Owner chat authority 2026-11-09 (no permalink): release of the device from #11, permission to do
  everything as long as the state is restored at the end, and to use the hub service; the playlist
  question (saving starts it) was asked and covered.

Baseline: off, brightness 47, no active preset or playlist; segment 0 on, brightness 255, effect 0,
speed 128, intensity 128, palette 11; one preset (slot 1, state preset); groups 0, scenes 0; 3
snapshots in the service data directory (from #12).

## Steps and results

Every write was checked by the service's readback; none failed and none was retried.

1. Read-only: `wled_list_presets`, `wled_export_presets`, `wled_list_snapshots`, `wled_list_groups`,
   `wled_list_scenes`, `wled_get_state`, `wled_get_preset` (slot 1): all as expected.
2. Group and scene: `wled_save_group` (one device, segment 0) and two scenes (brightness 80 with
   speed 100, and the restoring 47 and 128). `wled_plan_scene` (strict, one device, preflight ok)
   then `wled_apply_scene`: applied and verified, readback 80 and 100, still off; the restoring scene
   applied and verified (47 and 128). Both scenes and the group deleted.
3. `wled_store_preset` into unused slot 5 (power off, segment red), dry run then real: applied and
   verified; as documented the segment colors in the device state became red while the device stayed
   off and no preset became active.
4. `wled_save_playlist` into slot 6 (one entry, preset 5, repeat 1), dry run then real: applied and
   verified; device stayed off, no playlist active.
5. `wled_export_presets` of slot 5 (one entry, 528 bytes), `wled_import_presets` with id map 5 to 7:
   applied and verified (state route, no backup needed).
6. `wled_delete_preset` slot 7 (snapshot), `wled_restore_preset` from that snapshot into slot 7:
   applied and verified, no overwrite; slots 7, 6 and 5 then deleted, each with a snapshot.
7. `wled_patch_segments` set segment 0 colors back to the baseline: applied and verified.

Final state: off, brightness 47, no active preset or playlist; segment 0 and preset slot 1 identical
to the baseline; groups 0, scenes 0. The LEDs were never lit (every test preset stored with power
off).

## Acceptance criteria of #134

| Criterion | Result |
| --- | --- |
| Read-only first: preset list and export, group and scene listing, plan of a one-device scene | Met (steps 1, 2) |
| Group and scene definitions stored, planned, applied to one device, verified, deleted | Met (step 2) |
| Preset store, import and restore on one unused slot with snapshots and the documented live-output effect, then cleanup; playlist only if the owner accepts that saving starts it | Met (steps 3 to 6); the playlist ran because the owner's answer covered it |
| Every write verified; state, segment and preset list equal the state before; record names what could not be shown | Met for state, segment and preset list. Not fully restored: four new snapshots remain on the hub (below) |
| README limitations and VALIDATION.md "Known limitations" updated | Met by this change |

Not restored: the four snapshots written by the run remain in the service data directory in addition
to the three from #12 (the tools have no snapshot-delete operation); they hold copies of the test
presets only.

## Not shown

Multi-device scenes, CCT, RGBW and 2D (refusal paths are test-covered only); tool profiles and
`discover`; H07 and the live rollback (stay with
[#25](https://github.com/descipar/wled-mcp/issues/25)); restore with `overwrite=true` onto an
occupied slot; playlist import; firmware writes, reboot persistence, other controllers or firmware
versions; visible output of any tested preset (LEDs off by design); restore of a playlist preset
from its snapshot (only a state preset was restored).
