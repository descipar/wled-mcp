# Validation: live hardware and deployment checks

## Issue #128: behavior with a settings PIN and an OTA lock (2026-11-12)

Read-only probes and a minimal write set on one controller in three lock states, within
[ISSUE-128-DEC-001](../decisions/m3-m6.md) (read-only probes) and
[ISSUE-128-DEC-002](../decisions/m3-m6.md) (write set); neither is standing permission. The
controller is "the secured test controller" of
[#11](../VALIDATION.md#issue-11-live-deployment-check-2026-11-06) and
[#12](../VALIDATION.md#issue-12-hardware-acceptance-2026-11-06). No host names, addresses or PIN or
passphrase values were stored; raw outputs are local, git-ignored files.

### Target and authorization

- WLED 16.0.1 (build 2606300), ESP32-C3, 133 LEDs, one RGB segment; firmware tier `tested`.
- A local stdio server (release 0.3.0 source tree) with a separate data directory and one configured
  device; read-only probes used profile `read-only` and five tools (`wled_get_state`,
  `wled_get_effects`, `wled_get_palettes`, `wled_list_presets`, `wled_get_preset`); write runs used
  profile `full` and a fixed allowlist. No discovery, no other device, no credential sent.
- Owner chat authority 2026-11-12 (no permalink): the owner set each lock state and confirmed it
  before each run. The lock configuration cannot be read through the JSON API, so it rests on that
  statement.

| State | Settings PIN | OTA lock |
| --- | --- | --- |
| A | on | on |
| B | on | off |
| C | off | on |

### Results

Read probes (one run per state): all five calls succeeded in A, B and C (firmware 16.0.1, 216
effects, 72 palettes, 1 preset, slot 1 readable). No read was refused; the two effect-metadata
warnings (IDs 122 and 179) are identical in all states and without any lock.

Write set (one run per state, dry run before every write, no retry), baseline master off,
brightness 47, segment 0 speed 128, one preset (slot 1): master brightness change and restore,
segment 0 speed change and restore, `wled_store_preset` into unused slot 5 then
`wled_delete_preset` of slot 5 (snapshot taken), final read compared with the baseline. Every step
was applied and verified by readback in A, B and C; state and presets equal the baseline each time;
nothing was refused, failed, uncertain or retried. The delete snapshots stay in the local probe data
directory.

### Acceptance criteria of #128

| Criterion | Result |
| --- | --- |
| Separate states (PIN, later OTA lock) recorded neutrally, no PIN or passphrase committed | Met for A, B and C |
| Read-only probes first with each lock active | Met |
| Minimal write set with each lock, restorable state kept | Met for A, B and C; state restored and checked each time |
| A refusal surfaces as a clear, non-retried error; no bypass; no security setting changed | Partly met: not observed on hardware because no read was refused. A mock test covers HTTP 401 and 403 as `INVALID_RESPONSE` with the status, one request, no retry; the server has no path that sends credentials or changes a security setting |
| Result in `docs/validation/`, README limitations and `docs/contract/compatibility.md`; planned-test note replaced | Met |
| HTTP authentication or a credentialed proxy | Out of scope, unchanged |

Result per lock (settings PIN, OTA lock, both): the five probed reads and the minimal write set are
supported with no change observed, matching the WLED documentation (PIN for the settings pages, OTA
lock for firmware updates).

### Not shown

Writes outside the minimal set (layout replacement, preset restore, import, playlists, signals,
groups, scenes) under a lock; settings pages or firmware update under a lock; read tools outside
the five; other controllers or firmware; the deployed HTTP service on the hub; a refusal of a read
on hardware (none occurred).

## Issue #134: hardware check of the stage-2 features (2026-11-09)

One owner-authorized hardware run of the stage-2 features on the single test controller through the
deployed Streamable HTTP service on the hub. Scope follows
[DEC-027](../DECISIONS.md#dec-027--re-stage-the-open-work-by-value-per-effort) and
[ISSUE-134-DEC-001](../decisions/m3-m6.md), bounded to this run and not standing permission.
Host names, addresses and the controller's name are omitted; "the test controller" is the one of
[#11](../VALIDATION.md#issue-11-live-deployment-check-2026-11-06) and
[#12](../VALIDATION.md#issue-12-hardware-acceptance-2026-11-06). The detailed record is a local,
git-ignored file.

### Target and authorization

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

### Steps and results

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

### Acceptance criteria of #134

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

### Not shown

Multi-device scenes, CCT, RGBW and 2D (refusal paths are test-covered only); tool profiles and
`discover`; H07 and the live rollback (stay with
[#25](https://github.com/descipar/wled-mcp/issues/25)); restore with `overwrite=true` onto an
occupied slot; playlist import; firmware writes, reboot persistence, other controllers or firmware
versions; visible output of any tested preset (LEDs off by design); restore of a playlist preset
from its snapshot (only a state preset was restored).

## Issue #25: live H07 offline-controller check (2026-11-11)

One owner-authorized live check of H07 (behavior with an unreachable configured controller) on the
deployed Streamable HTTP service, as moved from #12 by ISSUE-12-DEC-007 item 6. Real device names and
addresses are omitted. The method is the approved one in [VALIDATION.md](../VALIDATION.md): no unplugging
of a production device and no networking change. Authorization: owner chat, 2026-11-11, bounded to this
run (temporary inventory entry and service restart), not standing permission.

### Target and procedure

- Release 0.1.2 HTTP service, profile `full`, device ceiling `manage`, one real controller (WLED
  16.0.1, ESP32-C3) plus a temporary device `h07-offline` at `http://192.0.2.1` (RFC 5737 documentation
  address, not routed), so no real device was touched.
- Steps: copy the inventory, `config add-device`, `config validate` (exit 0, 2 devices), restart only
  the service; read-only calls through the hub (no write tool called); restore the copy, validate
  (1 device), restart, confirm with a probe; temporary copies removed.

### Observations

| Check | Result |
| --- | --- |
| `wled_list_devices` without probe | both IDs listed, `probe_status: untested`, no network |
| `wled_list_devices` with probe | real controller `reachable`; `h07-offline` `failed`, `TIMEOUT`, `read_retryable: true`, `write_retryable: false`, reconciliation "Read the configured device explicitly; never replay the write." |
| `wled_get_state` on `h07-offline` | `ok: false`, `TIMEOUT`, `application: not_attempted` |
| `wled_get_state` on the real controller, same window | `ok: true`, unaffected |
| `wled_get_service_status` | `reachable: 1`, `failed: 1`; `error_code: TIMEOUT` for `h07-offline` |
| After rollback and restart | probe lists only the real controller, `reachable` |

The offline controller fails alone, with retryable-read and non-retryable-write classification, and does
not degrade the other controller (DEV-02, REL-01). Elapsed time per failing call was not measured.

### Limits

- One run, one build, one real controller; the target is a non-routed address (connect-timeout path),
  not a controller dropping mid-request (simulated T09 evidence only).
- No write was attempted against the offline entry; the not-attempted write path on hardware is covered
  by mocks only (REL-02).
- Closes only the H07 box of #25; other #25 acceptance items are not addressed.

## Issue #25: live rollback checklist for the deployed target

Status: executed once on 2026-11-13 (0.3.0 to 0.2.0 and back); results are in the
[launch report](releases.md#3-upgrade-and-rollback-evidence). Covers acceptance item 1 of
[#25](https://github.com/descipar/wled-mcp/issues/25) (S2-COMPAT-03, live part) and follows
[DEPLOYMENT.md](../DEPLOYMENT.md#http-service-update-rollback-recreation-removal); authorization
[ISSUE-25-DEC-003](../decisions/stage-2.md). The run restarts the deployed HTTP service twice and touches
only its Compose project, never the hub (never reinstalled,
[DEC-037](../DECISIONS.md#dec-037--no-mcphub-reinstall-in-project-steps)).

- **Preconditions:** release N runs and an older release P is retained as an image and release directory
  (staged per DEC-026 from a clean checkout of the tag); quiet window with no call or signal in flight;
  read tools only, profile unchanged; backups first on the target and outside the repository (compose
  file, inventory, whole data tree with file counts and a checksum list); the CHANGELOG between P and N
  shows no data or inventory format change, otherwise stop and ask.
- **Steps:** record before (`ps`, image tag, logs, authenticated `ping`, status, devices, one state);
  validate the inventory with P on a copy; set `image:` to P and `up -d --no-deps`; verify on P (health,
  startup line, `ping` 200, tool count equals P's, data written by N present); prove no controller write
  (only `class=read` calls, unchanged checksum list); restore `image:` to N and verify again; keep both
  images and release directories, never prune backups.
- **Record:** versions with provenance, exact commands, time from `up -d` to the first `ping`, tool counts,
  the no-write proof, deviations from DEPLOYMENT.md and what was not run, without hostnames, addresses,
  paths or tokens.
- **Stop when:** no older release is retained or buildable; the service is not ready on P and restoring
  the previous compose file does not bring it back at once; a data or inventory format differs; the run
  would need a new artifact, tag or publication.

## Live check of the second release (2026-11-08)

One owner-authorized live check of the second release on the same target class and single test controller
as the first deployment check ([#11](../VALIDATION.md#issue-11-live-deployment-check-2026-11-06)): one
controller on WLED 16.0.1 (ESP32-C3, 133 LEDs, one segment), reads, master power and brightness and
segment effects; each write run authorized separately, none standing permission. Host names, addresses and
paths omitted. Not a broad hardware acceptance.

- **Staging ([DEC-026](../DECISIONS.md#dec-026--stage-releases-on-the-target-machine)):** clean clone of the
  release tag on the aarch64 target, `uv sync --locked`, offline wheel build, `deploy/stage_release.py`,
  `sha256sum -c` OK; `check_distribution.py` not run on the target. A staging run on a Windows checkout
  produced other hashes ([#131](https://github.com/descipar/wled-mcp/issues/131)); that directory was
  discarded. Hub configuration and compose file backed up; no rollback was run.
- **HTTP service:** recreated, `healthy` about 33 s after start. The first hub call failed once ("data
  must NOT have additional properties") and succeeded about a minute later after the hub refreshed its tool
  list ([#130](https://github.com/descipar/wled-mcp/issues/130)). Status: second-release version,
  `streamable-http`, profile `full`, device `reachable`. Reads: device list with probe, state (tier
  `tested`), catalogs, presets, snapshots, groups (empty). Master-only writes: brightness 47 to 60 and
  back, power on at 47, 120, 47 and off (200 clearly visible by the owner); about 55 s effect run in five
  calm phases (no strobe or sparkle, no presets, 13 verified writes); restoration to effect 0, palette 11,
  speed and intensity 128, original colors, brightness 47, master off, readbacks equal to the earlier
  state. Counters before the visible tests: 10 calls, all ok, 7 read and 3 control. Owner remark: went
  well; some effects were barely visible (pale palettes, low brightness; noted on
  [#31](https://github.com/descipar/wled-mcp/issues/31)).
- **stdio (README route, temporary):** hub entry via `uvx ... --from git+...@<release tag>`, cold first
  start about 50 s; device list with probe `reachable`, state equal to baseline, status `stdio`, one write
  (brightness 47 to 60 and back, verified). Entry deleted at the owner's request, HTTP entry untouched; the
  transports were never used at the same time.
- **Not run:** scenes, groups, preset save, delete, restore, import and export and playlists on the
  controller; segment geometry; CCT and 2D; a rollback of the HTTP service; an unreachable controller
  (H07); settings PIN or OTA lock ([#128](https://github.com/descipar/wled-mcp/issues/128));
  `check_distribution.py` on the target.
- **Findings:** #130 (cached output schema rejected after the update), #131 (different bytes when staging
  on Windows); DEPLOYMENT.md said a Git source is never pinned to a tag while the README uses one, now
  reconciled.
