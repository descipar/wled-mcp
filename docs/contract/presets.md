# Preset restore, supplied-state save and snapshot listing (issue #18)

Contract for the first issue-#18 pull request. It extends
[Persistent presets](../TOOL-CONTRACT.md#persistent-presets) and
[Snapshot and explicit restoration](../TOOL-CONTRACT.md#snapshot-and-explicit-restoration);
everything stated there (IDs 1-250, name rules, snapshot format 1, ordering of
snapshot, recheck and dispatch, outcome envelope and error codes) applies unchanged.
Decisions: [ISSUE-18-DEC-001](../decisions/issue-18.md#issue-18-dec-001--write-route-for-supplied-preset-and-playlist-objects)
(human: single-entry JSON API writes with a documented live effect) and
[ISSUE-18-DEC-003](../decisions/issue-18.md#issue-18-dec-003--technical-defaults-for-restore-supplied-state-save-and-bundles)
(coordinator, technical defaults). Firmware facts: [SOURCES.md](../SOURCES.md#issue-18-wled-16-preset-write-evidence).
Evidence: [validation/issue-18.md](../validation/issue-18.md) (mock only).

Playlist authoring and preset import/export follow in the second #18 pull request.

## Tools

| Tool | Class | Inputs | Behavior |
| --- | --- | --- | --- |
| `wled_list_snapshots` | read | `device_id`, optional `preset_id` | Valid snapshots of the device, newest first; no device I/O |
| `wled_restore_preset` | manage, destructive | `device_id`, `backup_id`, optional `preset_id`, `overwrite=false`, `dry_run=false` | Writes one snapshot entry back through the state or playlist route |
| `wled_store_preset` | manage, destructive | `device_id`, `name`, `state`, optional `preset_id`, `overwrite=false`, `dry_run=false` | Stores a supplied, validated light-state object through the state route |

All inputs are strict (`extra=forbid`; booleans are not integers). `wled_save_preset`
is unchanged and still has no `state` input.

## Live effect

WLED 16 has no JSON API path that stores a supplied object without acting on it
(ISSUE-18-DEC-001). Both writers therefore state their live effect in the tool
description, the dry-run plan (`plan.live_effect`) and the result (`data.live_effect`,
`data.previous_lighting_restored: false`):

- State route: "Applies the supplied state to the lights, then stores it. The lighting
  before the write is not restored."
- Playlist route: "Starts the playlist, then stores it. The lighting before the write
  is not restored."

There is no "apply, save, re-apply the previous lighting" emulation. The plan and
result report the active preset and playlist before the write (`live_before`). A
state write warns when a running playlist may be interrupted; the playlist route is
refused while a playlist runs (see [Restore](#restore-wled_restore_preset)). A warning
also names the active preset marker when it is the destination, and the playlists that
reference an overwritten destination (they are not edited). The PRE-03 variant
"without changing live output" is not supported on WLED 16; no input requests it.

## Write routes

Each write is exactly one POST to `/json/state`, never repeated:

- State route: the entry plus `"psave": <id>` and `"o": true`, without a `playlist`
  key. The firmware applies it and writes the request immediately, minus `o`, `v`,
  `time`, `error`, `psave` and `bootps`; it adds `"n": "Preset <id>"` when no name is
  sent.
- Playlist route: `{"playlist": ..., "n": ..., "ql": ..., "psave": <id>, "o": true}`
  (name and quick-load label only when present). The firmware starts the playlist and
  stores it re-serialized from its runtime data: per-entry `dur` and `transition`
  arrays, `repeat`, `end`, `r`, `on: true`, the name and the label. Unknown fields are
  dropped by the firmware.

No whole-file `/presets.json` upload, no `/upload` or `/edit`, no bulk restore
(W-PRESET-10 stays excluded).

## Sequence

Inside the device lock and one operation deadline:

1. Validate the request (schema, name, supplied state). Restore loads the snapshot and
   refuses an `api-command`, `unknown` or malformed snapshot before any device read.
2. Read the device: restore reads `/json/info` (firmware) and requires the snapshot's
   exact firmware `version`; both read `/presets.json` and `/json/state`; the store
   reads `/json/info` for capabilities.
3. Choose the destination: `wled_store_preset` uses `preset_id` or the lowest free ID
   (1-250); `wled_restore_preset` uses `preset_id` or the snapshot's preset ID. An
   occupied destination without `overwrite=true` is `PRESET_CONFLICT`;
   `overwrite=true` without `preset_id` is invalid for the store tool. A store that is
   not well-formed, or an occupied entry that is not a JSON object, is refused.
4. Dry run stops here: `plan`, the exact `payload`, `postconditions` and the advisory
   `backup_required`/`backup_storage_writable`; no POST, no snapshot, no directory.
5. Snapshot an occupied destination (`BACKUP_FAILED` sends nothing), re-read
   `/presets.json` and recheck: a free destination that became occupied or an occupied
   one that changed is `PRESET_CONFLICT`; no other ID is chosen. Restore then confirms
   device, firmware, target and the new prior snapshot with `SnapshotStore.plan_restore`.
6. One POST; poll `/presets.json` until the postcondition holds or the deadline ends.

The result carries `backup_id` (the snapshot taken by this call, also on a failed or
uncertain write), and restore also `source_backup_id`, `source_preset_id`,
`snapshot_type` and `firmware_version`.

## Verification

- State route: the stored entry must equal the sent object minus the firmware-removed
  keys, exactly (`json_equal`, unknown fields included, key order not significant),
  with the firmware's default name when none was sent. Any difference is reported by
  top-level key name.
- Playlist route (semantic): same `ps`; per-entry `dur` (default 100) and `transition`
  (compared only when sent) after the firmware's expansion of a scalar or short list;
  `repeat`, `end`, `r`; `on` absent or true; name and quick-load label.
- Unrelated entries that changed are reported as interference, never corrected.
- A timed-out or failed POST is decided by readback; unreadable readback until the
  deadline is `WRITE_OUTCOME_UNKNOWN`, a readable different entry is
  `VERIFICATION_MISMATCH`; `data.no_replay` is true and nothing is resent or rolled
  back. A later call is a new, explicitly requested invocation that plans from fresh
  reads.

## Supplied state (`wled_store_preset`)

`state` uses WLED wire keys and allows only light state: top-level `on`, `bri` (0-255),
`transition` (0-655 tenths: the firmware keeps `transition` x 100 ms in a 16-bit value,
so larger values would wrap), `bs` (0-31: the firmware masks the blending style with
`0x1F`), `mainseg`, `seg` (1-64 segments) and at
least one of `on`, `bri`, `seg`. Segments need `id`, `start`, `stop` and may carry
`on`, `bri`, `col`, `fx`, `pal`, `sx`, `ix`, `grp` (1-255), `spc` (0-255), `of`, `rev`,
`mi`, `sel`, `n`. Any other key, including every control or side-effect key (`ps`,
`pd`, `playlist`, `psave`, `pdel`, `win`, `nl`, `udpn`, `lor`, `rmcpal`, `wifi`, `np`,
`rb`, `live`, `time`, `bootps`, `ledmap`, `o`, `v`, `ib`, `sb`, `sc`, `n` at top level),
is a schema `VALIDATION_ERROR` with no device I/O. Omitted fields are absent in the
stored object, never `null`.

Before any write, against the device's reported capabilities (consistent with
`wled_replace_layout`): `0 <= start < stop <= led_count`, unique segment IDs below the
reported maximum and no more segments than it, no overlap, `of` below the segment
length, `fx`/`pal` inside the reported catalog counts, 1-3 color slots with exactly the
device's channel width (RGB 3, RGBW 4; no evidence with colors is
`UNSUPPORTED_CAPABILITY`), segment names of at most 32 UTF-8 bytes without U+0000,
`mainseg` naming a supplied segment, and no `on=true` with `bri=0` (master or
segment). A segment `bri=0` needs an explicit `on=false`, because the stored preset is
applied later regardless of the then-current power. Unknown LED count or segment
maximum is `UNSUPPORTED_CAPABILITY`.

## Restore (`wled_restore_preset`)

Restores exactly one snapshot entry; the snapshot file is never changed. Requirements:
the same configured device (snapshots are per device), the exact firmware `version`
recorded in the snapshot (otherwise `UNSUPPORTED_CAPABILITY`), and a `state` or
`playlist` snapshot. State snapshots are sent and stored verbatim, including
firmware-written segment fields the tools do not expose.

A playlist snapshot is refused (`UNSUPPORTED_CAPABILITY`, also in the dry run) when the
firmware's playlist save would not reproduce it: top-level keys other than `playlist`,
`n`, `on`, `ql` or playlist keys other than `ps`, `dur`, `transition`, `repeat`,
`end`, `r` (they would be dropped); `on` other than true; a name over 32 UTF-8 bytes
or an empty or over-8-byte label; no or more than 100 members; `dur` outside
0-42949670 or `transition` outside 0-65535 tenths; `end` other than 0 or 1-250 (255
is refused as for activation); or a negative `repeat` (the firmware reads it as
shuffle). A finite `repeat` and shuffle (`r`) are accepted (ISSUE-18-DEC-003): from the
pinned source the save runs before the playlist advances, so `repeat` and the member
order are stored unchanged; the semantic readback compares `repeat`, `r` and the `ps`
order and reports any deviation as `VERIFICATION_MISMATCH` (source-derived,
hardware pending; see [SOURCES.md](../SOURCES.md#issue-18-wled-16-preset-write-evidence)).
Because saving starts the playlist, every member and a persistent `end` must be an
existing plain state preset other than the destination itself; a member that changes
between planning and the post-snapshot recheck is `PRESET_CONFLICT`.

The playlist route is refused with `PRESET_CONFLICT` before any snapshot or POST when
the device reports a running playlist (`state.pl` > 0), and again if one is running
when the state is re-read after the snapshot: with a playlist already running the
firmware's `loadPlaylist` can keep it, and the save would then store the running
playlist in the destination instead of the snapshot's.

The restore's source snapshot is protected from retention pruning for the whole
operation, so the prior snapshot of an occupied destination never deletes it.

## Snapshot listing (`wled_list_snapshots`)

Reads only the server's data directory under the device lock; the device is never
contacted. Returns `snapshots` (newest first by `created_at`, then `backup_id`), each
with `backup_id`, `preset_id`, `created_at`, `firmware_version`, `type`, `name` and
`restorable` (`state` or `playlist`), plus `count` and `invalid_count`. Invalid files
are counted with a warning, never named or changed. `preset_id` filters the list. An
unknown device fails before any filesystem access.

## Limits

- Hardware behavior of both routes on WLED 16 is not observed yet; the routes rest on
  the pinned source review. The firmware comment on the immediate write path warns of
  possible `presets.json` corruption; the tool writes one entry and verifies it.
- Below WLED 16.0.0 the tools run without a version gate (DEC-020; ISSUE-18-DEC-003)
  and rely on readback; a mismatch is reported.
- The live output after a state write is not verified; only the stored entry is.
