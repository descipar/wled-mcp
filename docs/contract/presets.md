# Preset restore, supplied-state save, playlists and bundles (issue #18)

Contract for issue #18 (both pull requests). It extends
[Persistent presets](../TOOL-CONTRACT.md#persistent-presets) and
[Snapshot and explicit restoration](../TOOL-CONTRACT.md#snapshot-and-explicit-restoration);
everything stated there (IDs 1-250, name rules, snapshot format 1, ordering of
snapshot, recheck and dispatch, outcome envelope and error codes) applies unchanged.
Decisions: [ISSUE-18-DEC-001](../decisions/issue-18.md#issue-18-dec-001--write-route-for-supplied-preset-and-playlist-objects)
(human: single-entry JSON API writes with a documented live effect) and
[ISSUE-18-DEC-003](../decisions/issue-18.md#issue-18-dec-003--technical-defaults-for-restore-supplied-state-save-and-bundles)
(coordinator, technical defaults). Firmware facts: [SOURCES.md](../SOURCES.md#issue-18-wled-16-preset-write-evidence).
Evidence: [validation/issue-18.md](../validation/issue-18.md) (mock only).

The second pull request adds playlist authoring
([`wled_save_playlist`](#playlist-authoring-wled_save_playlist)), bundle export
([`wled_export_presets`](#export-wled_export_presets)) and import
([`wled_import_presets`](#import-wled_import_presets)) on the same write routes.

## Tools

| Tool | Class | Inputs | Behavior |
| --- | --- | --- | --- |
| `wled_list_snapshots` | read | `device_id`, optional `preset_id` | Valid snapshots of the device, newest first; no device I/O |
| `wled_restore_preset` | manage, destructive | `device_id`, `backup_id`, optional `preset_id`, `overwrite=false`, `dry_run=false` | Writes one snapshot entry back through the state or playlist route |
| `wled_store_preset` | manage, destructive | `device_id`, `name`, `state`, optional `preset_id`, `overwrite=false`, `dry_run=false` | Stores a supplied, validated light-state object through the state route |
| `wled_save_playlist` | manage, destructive | `device_id`, `name`, `entries`, `repeat`, `shuffle`, optional `end_preset_id`, `preset_id`, `overwrite=false`, `dry_run=false` | Creates or replaces one playlist through the playlist route |
| `wled_export_presets` | read | `device_id`, optional `preset_ids`, `include_unwritable=false` | Returns a format-1 preset bundle inline; no write, no file |
| `wled_import_presets` | manage, destructive | `device_id`, `bundle`, optional `id_map`, `effect_map`, `palette_map`, `overwrite_ids`, `dry_run=false` | Plans every entry, then writes them one at a time through the state and playlist routes |

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

## Playlist authoring (`wled_save_playlist`)

Creates or replaces one native playlist entry through the playlist route; the live
effect is that route's ("Starts the playlist, then stores it").

Inputs are strict; an out-of-range value is a schema `VALIDATION_ERROR` with no device
I/O and is never normalized. Bounds follow the pinned v16.0.1 `playlist.cpp` (see
[SOURCES.md](../SOURCES.md#issue-18-wled-16-preset-write-evidence)):

- `name`: the preset name rules (1-32 UTF-8 bytes, no control characters).
- `entries`: 1-100 steps `{preset_id, duration_s, transition_s}` with `preset_id`
  1-250. `duration_s` and `transition_s` are seconds in steps of 0.1 (the firmware
  unit is a tenth; any other value is rejected). `duration_s` 0 keeps the entry until
  playback is advanced, at most 4294967 s (42949670 tenths). `transition_s` is at most
  65.5 s (655 tenths), because the firmware multiplies the per-entry transition by 100
  into its 16-bit live transition. (Restore keeps stored values 0-65535.)
- `repeat` (required): 0 = endless, 1-254 = that many passes; the firmware keeps the
  count plus one in a byte. A negative value (firmware: endless and shuffled) is
  refused.
- `shuffle` (required boolean): sent as `r`.
- `end_preset_id` (optional): an existing state preset 1-250 applied after the last
  pass; omitted means 0 (stay on the last entry). 255 ("restore the previous preset")
  is refused, as for activation.
- `preset_id`, `overwrite`, `dry_run` as for `wled_store_preset` (lowest free ID when
  omitted; `overwrite=true` needs `preset_id`).

The sent object is `{"playlist": {"ps", "dur", "transition", "repeat", "end", "r"},
"n"}` with full per-entry `dur` and `transition` arrays in tenths. Before any write:
every member and the end preset must be an existing plain state preset other than the
destination (`UNSUPPORTED_CAPABILITY`); an occupied destination needs `overwrite=true`
(`PRESET_CONFLICT`) and is snapshotted first; the save is refused with
`PRESET_CONFLICT` while the device reports a running playlist (`state.pl` > 0), during
planning and again after the snapshot, as for the playlist restore; a member that
changes after the snapshot is `PRESET_CONFLICT`. Verification is the semantic playlist
comparison of [Verification](#verification). `wled_save_preset` still refuses to
replace a playlist.

The plan and the result carry `playback`: `starts_playlist: true`, the active preset,
whether it is a member, whether the destination is the active preset marker, and the
running-playlist hazard; `live_before` names the active preset and playlist.

## Bundle format 1

A bundle is a JSON object. The export returns it inline and the import takes it inline,
as an object or as JSON text; the server never writes a bundle file. A bundle is
untrusted input and has no integrity hash or signature. Retained example:
[`examples/contracts/preset-bundle.json`](../../examples/contracts/preset-bundle.json).

| Key | Content |
| --- | --- |
| `format` | `"wled-mcp.preset-bundle"` |
| `format_version` | integer `1` |
| `created_at` | UTC `YYYY-MM-DDTHH:MM:SSZ` |
| `source` | `{"firmware": {"version"}, "capabilities": {"led_count", "max_segments", "matrix"}}`; `matrix` is `{w, h}` or `null`; counts may be `null` |
| `catalog` | `{"effects": {id: name}, "palettes": {id: name}}` for the IDs the state entries reference |
| `presets` | list of `{"source_id", "name", "type", "preset"}`: source ID 1-250, the stored name or `null`, the classified type (`state`, `playlist`, `api-command`, `unknown`) and the stored object verbatim, unknown fields included |

The format has no field for a device ID, base URL, host, IP, MAC, BSSID, credential,
inventory name or `info` dump. Key order is not significant.

Reader rules (TD-21-5 of ISSUE-21-DEC-002). Each is a `VALIDATION_ERROR` before any
device I/O:

- a serialized size above 192 KiB (UTF-8, compact JSON; below the 256 KiB HTTP body
  limit);
- JSON text with a syntax error, a duplicate key, `NaN` or `Infinity`;
- a `format` other than the one above;
- a `format_version` that is not an integer 0-9999, or one other than 1 (the message
  names that version and the supported one);
- an unknown or missing key at any level (named in the message);
- a bad, duplicate or out-of-range `source_id`;
- a `type` that differs from the classification of `preset` (a playlist is never read
  as a state preset);
- a `name` that differs from the object's name.

A semantic change of the format bumps `format_version`.

## Export (`wled_export_presets`)

Reads `/json/info` and `/presets.json` inside the device lock, plus the effect and
palette catalogs when entries reference them; nothing is written.

- Selection: all `state` and `playlist` entries in ID order, or the listed `preset_ids`
  (a missing ID is `PRESET_NOT_FOUND`).
- `api-command`, `unknown` and malformed entries are excluded, listed in
  `data.excluded` and named in a warning. `include_unwritable=true` exports them for
  inspection only; `data.importable` is then false, and an import refuses them.
- Result `data`: `bundle`, `count`, `excluded`, `importable`, `serialized_bytes`.
- An export above 192 KiB fails with `VALIDATION_ERROR` and the hint to select
  `preset_ids`.
- Guard against addresses stored in preset text: an export is refused
  (`VALIDATION_ERROR`, naming only the source IDs) when a string of a selected object
  contains the device's configured host, its reported IP or MAC (both spellings) or the
  Wi-Fi BSSID. This scan covers only this device's host, IP, MAC and BSSID, also for
  entries exported with `include_unwritable`; the export warning says so.

## Import (`wled_import_presets`)

Before any device I/O the bundle is parsed (above), and an import of more than 50
entries is refused with the hint to split it. Then, inside the device lock and one
overall deadline (the per-write operation timeout times the number of entries plus
two), the server reads `/json/info`, `/json/state`, `/presets.json` and, when entries
reference them, the catalogs, and plans every entry.

Planning rules:

- **Destination.** `id_map[source_id]` (keys are decimal source IDs, values 1-250), or
  the lowest free ID 1-250 in bundle order. The import is blocked when two entries get
  the same destination, an `id_map` key is neither a bundle entry nor a playlist
  member, or an `overwrite_ids` ID is not a destination.
- **Occupied destination.** It needs its ID in `overwrite_ids` (`PRESET_CONFLICT`
  otherwise). An occupied entry that is not a JSON object cannot be snapshotted. The
  preview names the existing type, playlists that reference the destination (they are
  not edited) and a destination that is the active preset marker.
- **Capabilities and ranges.** Nothing is rescaled or converted; the caller edits the
  bundle. An entry is blocked when a segment `stop` is beyond the target LED count,
  it has more segments than the target maximum, or a segment ID is not below that
  maximum. An unknown target LED count or segment maximum blocks entries with segments.
- **2D geometry.** `startY`/`stopY` is blocked unless the bundle's and the target's
  `matrix` are both reported and equal. This is the interim rule of ISSUE-18-DEC-002,
  read from raw `info.leds.matrix`.
- **Carried with a warning.** `cct` on a target without the CCT capability bit, and a
  `ledmap` selection, are written verbatim with a warning.
- **Effects and palettes.**
  - An ID is kept when the target catalog has the same name at that ID.
  - Otherwise the entry is blocked. `required_mappings` names the source ID and name
    and, when the name matches exactly one target entry (exact, then case-folded), the
    proposed target ID.
  - `effect_map`/`palette_map` (source ID to target ID) accept a mapping explicitly;
    the mapped ID is written into the entry's `fx`/`pal`.
  - An ID the bundle does not name must be mapped explicitly.
  - Custom palettes (IDs at or above the length of the built-in `/json/pal` catalog)
    cannot be imported or mapped: they are not in the catalog the check reads.
- **Playlists.**
  - Members and a persistent `end` are rewritten through the destinations of the
    bundle's state entries, or through `id_map` to an existing state preset on the
    target; any other reference blocks the playlist.
  - The rewritten object must pass the playlist checks of
    [Restore](#restore-wled_restore_preset). Like restore, an imported playlist keeps
    the stored per-entry transition range 0-65535 tenths; values above 655 wrap in the
    firmware at playback (authoring refuses them).
  - Saving starts a playlist, and the playlist route is refused while one runs. So a
    bundle may hold at most one playlist per import, and the playlist is refused while
    the device reports a running playlist.
- **Unwritable entries.** `api-command`, `unknown` and malformed entries are never
  imported; they block the import.

Any blocking finding makes the whole import `not_attempted` with the first finding's
code (`VALIDATION_ERROR`, `UNSUPPORTED_CAPABILITY`, `PRESET_CONFLICT` or
`INVALID_RESPONSE`) and the full preview in `data.plan`; nothing is written.

A dry run returns the same preview and performs bounded reads only (no POST, no
snapshot, no directory):

- `executable`;
- per entry: source and destination ID, occupancy and existing type, `overwrite`,
  route and its live effect, `write_position`, `member_map`, `catalog_mappings`,
  `blocking` and `warnings`;
- `write_order`, `required_mappings`, `live_effect`, `live_before` and the backup
  advisory.

Execution (R18-IMP-08):

1. Snapshot every occupied destination before the first POST; the snapshots of one
   import are protected from each other's retention pruning. `BACKUP_FAILED` sends
   nothing; snapshots already taken are kept and returned in `data.backup_ids`.
2. Re-read `/presets.json`; a destination that changed since planning is
   `PRESET_CONFLICT` before any POST.
3. Write in `write_order`: state entries in bundle order, then the playlist, so members
   exist before the playlist that references them. Each entry rechecks its destination
   (for the playlist also its members and `state.pl`), sends one POST through its route
   and polls `/presets.json` within its own per-write deadline. Each state entry is
   applied to the lights as it is written; the playlist entry starts playing; the
   lighting before the import is not restored.
4. Stop at the first entry that is not verified; never resend.

Result `data`:

- `entries`: per entry `source_id`, `destination_id`, `route` and `status`
  (`verified`, `unknown`, `mismatch` or `not_attempted`), with `differences`,
  `observed`, `interference`, `reason` or `transport_error` where they apply;
- `completed`, `total`, `backup_ids`, `live_effect`,
  `previous_lighting_restored: false`, and `no_replay: true` after any dispatch.

| Situation | application | verification | error |
| --- | --- | --- | --- |
| All entries verified | applied | verified | none |
| At least one entry verified, then a stop (proven partial steps, final postcondition not reached) | applied | mismatch | the stopping cause: `WRITE_OUTCOME_UNKNOWN`, `VERIFICATION_MISMATCH`, `PRESET_CONFLICT` or `TIMEOUT` |
| First entry sent, readback unreadable | unknown | unknown | `WRITE_OUTCOME_UNKNOWN` |
| First entry sent, readback differs | unknown | mismatch | `VERIFICATION_MISMATCH` |
| Stop before the first POST | not_attempted | not_requested | the cause |

A later call is a new, explicitly requested import that plans from fresh reads; the
import never retries.

## Limits

- Hardware behavior of both routes on WLED 16 is not observed yet; the routes rest on
  the pinned source review. The firmware comment on the immediate write path warns of
  possible `presets.json` corruption; the tool writes one entry and verifies it.
- Below WLED 16.0.0 the tools run without a version gate (DEC-020; ISSUE-18-DEC-003)
  and rely on readback; a mismatch is reported.
- The live output after a state write is not verified; only the stored entry is.
- The playlist bounds (`repeat` byte, per-entry transition x 100, `dur` constraint)
  and the stored form of an authored playlist are source-derived; hardware pending.
- An import of several playlists needs one call per playlist, with the running playlist
  stopped explicitly in between (for example by activating a state preset).
- Bundles are not signed; the import validates their content, not their origin.
