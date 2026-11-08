# Device groups and scenes

Contract for named device groups, versioned scenes, the dry-run plan and sharing, introduced by
[#17](https://github.com/descipar/wled-mcp/issues/17) (S2-GROUP-01, S2-GROUP-02). Decisions:
[ISSUE-17-DEC-001 and -002](../decisions/issue-17.md); tool classes follow ISSUE-20-DEC-001.
Evidence is in [validation/issue-17.md](../validation/issue-17.md). Examples use synthetic IDs.

Status: pull request A delivers the definitions, the local store, sharing and
`wled_plan_scene`. **No tool in this document sends a device write.** `wled_apply_scene`
(the only write path, class `control`) is pull request B and is specified here only where its
policy is already fixed.

## Storage

Groups and scenes are local JSON documents in the data directory (ISSUE-17-DEC-001):
`<data-dir>/groups/<id>.json` and `<data-dir>/scenes/<id>.json`. The inventory file is
untouched. Written by the `manage`-class tools, read by the `read`-class tools.

- **IDs** match the device ID pattern `^[a-z0-9][a-z0-9_-]{0,63}$` (separate namespaces for
  groups, scenes and devices) and are the file names; a file whose `id` differs from its name
  is not usable.
- **Bounds:** at most 64 KiB per document, 100 groups, 500 scenes, 10 000 directory entries
  scanned. Files that cannot be used count toward the item bound.
- **Directories** are created at the first save, 0700, files 0600 on POSIX. A symlink or
  non-regular file in place of the directory or of a document is never followed; an
  unwritable data directory is `STORAGE_FAILED` before anything is stored.
- **Atomic save:** temporary file in the same directory, fsync, readback and re-parse, replace,
  directory fsync (best effort, POSIX). A failure removes the temporary file and keeps the
  previous document.
- **Replace and delete:** an existing ID needs `overwrite=true`; the previous document is
  returned (`data.replaced` / `data.deleted`) instead of a snapshot. A file this server cannot
  use is never replaced or deleted: save and delete refuse, with or without `overwrite`.
- **Unusable files** (invalid JSON, wrong shape, `format_version` this server does not read, not
  a regular file) are counted in the listing (`data.invalid_count`, one warning) and never
  named, rewritten, migrated or pruned. Loading one by ID is `VALIDATION_ERROR` with the
  version named when it is an integer 0-9999.
- **Concurrency:** a per-process lock serializes writes. Several server processes sharing one
  data directory are not coordinated; the last replace wins.
- Diagnostics (stderr) carry the kind and exception class only, never an ID, name, path or
  document content.

## Formats and versioning

Both documents are strict JSON: duplicate keys, `NaN` and `Infinity` are rejected, unknown keys
are rejected by name, the nesting and size bounds of the other inline documents apply. They
follow TD-21-5 ([versioning](versioning.md#schema-evolution)): an integer `format_version`
0-9999; any version this server does not read is rejected with the version named
(`Unsupported scene format_version 2; this server reads format_version 1.`); a non-integer,
boolean or out-of-range value gets the generic `'format_version' must be an integer 0-9999.`;
stored files are never rewritten. Both formats are at version 1. A semantic change bumps the
version and adds a migration row; no migration code exists yet. No document carries a
timestamp, address, credential or URL, and no field takes a free URL.

### Group, format `wled-mcp.group` 1

```json
{
  "format": "wled-mcp.group",
  "format_version": 1,
  "id": "shelf",
  "name": "Shelf strips",
  "members": [{"device": "strip_a"}, {"device": "strip_b", "segments": [0, 2]}]
}
```

- `name`: 1-128 characters, not blank, no control characters (the device name rule).
- `members`: 1-16 entries in a defined order. `device` is a configured device ID; `segments` is
  an optional unique list of explicit segment IDs 0-254 (1-64 entries). An absent list never
  means "all segments".
- A device may appear once per group; the same device with different segment lists is rejected
  as a conflict. One device may belong to several groups.
- Saving checks every member against the inventory (`VALIDATION_ERROR` before the write). Every
  use rechecks it: a member that left the inventory is listed with `in_inventory=false` and a
  warning, and a plan reports it as `UNKNOWN_DEVICE` for that device.

### Scene, format `wled-mcp.scene` 1

```json
{
  "format": "wled-mcp.scene",
  "format_version": 1,
  "id": "evening",
  "name": "Evening",
  "description": "Warm, dim lighting",
  "targets": [
    {
      "device": "strip_a",
      "master": {"on": true, "brightness": 120, "transition_ms": 500},
      "segments": [{"ids": [0, 2], "colors": [[255, 147, 41]], "effect_name": "Solid"}]
    },
    {"group": "shelf", "segments": [{"effect_name": "Wipe", "speed": 60}]}
  ]
}
```

- `id` and `name` as above; optional `description` of 1-256 characters without control
  characters; `targets` 1-16 entries.
- A target names exactly one of `device` or `group` (a configured device or a stored group) and
  at least one of `master` and `segments`.
- `master`: `on`, `brightness`, `transition_ms` with the `wled_set_state` bounds; at least `on`
  or `brightness` (the `wled_set_state` rule), so `transition_ms` alone is refused.
- `segments`: 1-16 entries, each with `ids` and the fields below. The same fields apply to every
  listed ID. `ids` is a unique list of explicit segment IDs 0-254 and is required on a `device`
  target; on a `group` target it may be omitted and then means the segments the group
  designates for each member (a member that designates none makes the request fail before any
  device I/O). Explicit `ids` on a group target apply to every member and override the
  designation. A segment ID may be set by one entry only.
- Settable segment fields, validated by the models of `wled_patch_segments`: `on`,
  `brightness`, `colors` (1-3 slots of 3 or 4 integers 0-255; the channel width is checked per
  device and never padded or trimmed), `effect_id` or `effect_name`, `palette_id` or
  `palette_name`, `speed`, `intensity`, `cct`, `custom1`-`custom3`, `check1`-`check3`. At
  least one field per entry; an ID and a name of one kind are mutually exclusive.
- **Not scene fields** (rejected by name): geometry (`start`, `stop`, `start_y`, `stop_y`,
  grouping, spacing, offset, orientation, `transpose`, `map_1d_2d`, `segment_set`), segment
  creation or removal, `freeze`, `blend_mode`, segment names, `selected`, raw state patches,
  timers, nightlight, sync, realtime and pixel streaming (ISSUE-13-DEC-001, ISSUE-19-DEC-002).
  A scene never changes geometry, so `allow_overlap` does not exist for scenes.
- **Names and IDs:** `effect_name` and `palette_name` resolve per device at plan time against
  that device's fresh catalog (exact match, then a unique case-folded match; no fuzzy matching;
  `RSVD` placeholders never match). A numeric `effect_id` or `palette_id` is used as given and
  checked against that device's catalog size; it is not portable between devices or firmware,
  and the plan warns about it. Per-device mapping in format 1 means names, or separate targets
  with explicit IDs.

## Expansion and the duplicate policy

A scene expands to exact device targets in document order; a `group` expands to its members in
member order. Each expanded entry carries its origin: `device`, or `group:<id>/member:<n>` (n
counts from 1), plus the 1-based `target_index`. After expansion a device may occur **once**. A
second occurrence (direct plus group, two groups sharing a device, the same group twice) fails
the whole request before any device I/O with `VALIDATION_ERROR` naming the device and both
origins; nothing is merged. The same refusals apply to a request with more than 16 expanded
devices, more than 64 segment patches for one device, a segment ID set by more than one entry,
an unknown or unusable group, and an entry without `ids` on a member that designates none.

Saving a scene runs the same expansion against the groups stored at that moment and refuses a
scene that could not be planned for a static reason. Groups can change afterwards; a plan
always expands again.

## Tools

All local tools report `device_id=null`, `application=not_attempted` and
`verification=not_requested`: no device write is attempted. `data.saved` / `data.removed` state
what happened to the file. Failures are `VALIDATION_ERROR` (invalid document, unknown reference,
not found, conflict, unusable file) or `STORAGE_FAILED` (the store could not be read or written;
no device was contacted; additive code). Schema errors (a malformed ID, an unknown argument)
use the existing generic `VALIDATION_ERROR` of the tool schema.

| Tool | Class | Result `data` |
| --- | --- | --- |
| `wled_list_groups(group_id?)` | read | `groups[]` (`id`, `name`, `member_count`, `unresolved_members`, `members[]` with `member`, `device_id`, `segments`, `in_inventory`), `count`, `invalid_count`; with `group_id`: `group` and `document` |
| `wled_save_group(group_id, name, members, overwrite=false, dry_run=false)` | manage | `group`, `saved`, `replaced` (previous document or null) |
| `wled_delete_group(group_id, dry_run=false)` | manage | `removed`, `deleted` (the document) |
| `wled_list_scenes(scene_id?, shareable=false, include_targets=false)` | read | `scenes[]` (`id`, `name`, `description`, `target_count`, `references`), `count`, `invalid_count`; with `scene_id`: `scene` and `document` |
| `wled_save_scene(scene, target_map?, overwrite=false, dry_run=false)` | manage | `scene`, `saved`, `replaced` |
| `wled_delete_scene(scene_id, dry_run=false)` | manage | `removed`, `deleted` |
| `wled_plan_scene(scene_id, mode="strict")` | read | see below |

`dry_run` on a save or delete performs the same bounded reads and checks and writes nothing (no
directory, no temporary file); the result has `dry_run=true`. Deleting a group does not edit
scenes: scenes that name it fail their plan until it is stored again.

## Plan: `wled_plan_scene`

Dry run of a stored scene. It expands the scene, then for every expanded device, under that
device's existing lock and one operation deadline, reads fresh state, info and (only when names
are used) the effect and palette catalogs, resolves names, and builds the master and segment
plans with the **same planners** as `wled_set_state` and `wled_patch_segments`. It sends **no
write** to any device (every device request is a read) and changes no lighting. At most 4
devices are in flight; results keep expansion order regardless of completion order. Worst-case
wall time is `ceil(devices / 4)` times the operation timeout. A device that is offline, slow or
locked is a per-device entry, never a failure of the whole plan.

`data`: `scene` (`id`, `name`), `mode`, `max_concurrency` (4), `device_count`, `summary`
(`devices`, `preflight_ok`, `preflight_failed`), `would_write` (device IDs), `skipped` (devices
`best_effort` would skip), `notes`, and `targets[]` in expansion order:

| Field | Meaning |
| --- | --- |
| `device_id`, `origin`, `target_index` | The exact target and where it came from |
| `preflight` | `ok` or `failed` |
| `reachable` | `true` after a successful state read, `false` for `UNREACHABLE`/`TIMEOUT`, `null` when the device was not contacted (for example `UNKNOWN_DEVICE`) |
| `error` | The device's refusal (`code`, `message`, `reconciliation`) or null |
| `candidates`, `candidate_total` | For `AMBIGUOUS_NAME`: at most 10 `{id, name}` candidates |
| `master`, `segments` | `plan`, `payload` and `postconditions` exactly as the single-device planner returns them, including capability evidence, field presence and warnings; null when there is nothing to plan or the device failed |
| `resolved` | Name resolution per device: `segments`, `field`, `name`, `id`. The same name can resolve to different IDs on different devices |
| `warnings` | Read anomalies, planner warnings, the numeric-ID portability warning |

Per-device refusals are the refusals of the single-device tools: unknown name (`VALIDATION_ERROR`),
ambiguous name, missing segment ID, effect or palette index out of range, colors of the wrong
width for the range, `cct` or an option field without capability evidence
(`UNSUPPORTED_CAPABILITY`), an offline device (`UNREACHABLE`, `TIMEOUT`), a device that is not
configured (`UNKNOWN_DEVICE`, no device I/O).

**Policy (`mode`).** `strict` is the default (ISSUE-17-DEC-001): if any target fails preflight,
nothing would be written anywhere. `best_effort` is an explicit opt-in: failing targets are
skipped and reported and the rest would be written. The plan always covers every target. The
envelope reports what an apply would do: `ok=true` when something would be written under the
mode; `ok=false` when strict blocks on a failure or best-effort has no passing device, with the
error of the first failing device in expansion order (the device named in the message and
`data.targets[]` authoritative). A request refused before any device I/O (a duplicate, an
unknown group, a missing or unusable scene) is `ok=false` with no `targets`. Every plan outcome
has `dry_run=true`, `application=not_attempted` and `verification=not_requested`.

The plan is **not a reservation**: state, catalogs and reachability can change before an apply,
which plans again under each device lock. A scene is **not atomic and not synchronized** across
devices.

## Sharing

`wled_list_scenes(scene_id, shareable=true)` returns the export as inline JSON, never a file.
By default the device and group references are replaced by positional placeholders `t1` ... `tn`
(one per target) and the document carries a top-level `placeholders` list (names only, no IDs),
so no inventory identity leaves the server. `include_targets=true` keeps the references and has
no `placeholders` key. The export refuses (naming the scene and the field, never the text) a
`name` or `description` that contains a configured device host, root URL or authority, as a
case-folded substring scan of the current inventory; that check also applies with
`include_targets`. Free text beyond host tokens remains the author's responsibility. A stored
scene never carries `placeholders`.

`wled_save_scene` accepts a stored-form document or a shared document. A document with
`placeholders` needs `target_map` (`{placeholder: {"device": id}` or `{"group": id}}`) with
exactly one entry per placeholder, of the matching kind, naming a configured device or a stored
group. Unmapped, extra, mismatched or unknown entries are refused and nothing is written (all or
nothing); `target_map` on a stored-form document is refused. Mapping a shared scene back to the
original references reproduces the original document. The retained synthetic example
[scene.json](../../examples/contracts/scene.json) is a shareable export and is checked with the
real parser.

## Apply (pull request B, policy already fixed)

`wled_apply_scene` (class `control`, not destructive, also accepting `dry_run` with exactly the
plan above) will write each device through the existing per-device path (lock, deadline,
readback verification, uncertain-write rule: no replay), master step first and then the segment
step, with at most 4 devices in flight, an independent outcome per device, no cross-device
atomicity, frame synchronization or rollback, and the strict/best-effort policy above. A device
failing in the write phase never stops or undoes another. This document is extended by that
pull request.

Access control (#20): the execution-time class guard will live in the write engines of
`Resources` and the preset-import path, not in `Resources.operation`, which also serves reads
and dry runs. Scene apply must therefore reach every device through those write engines, and
its preflight must call the public `Resources.require_access` that #20 adds, once per expanded
device (a scene has no single `device_id`). A `dry_run` does not lower a tool's class
(TD-20-2); `wled_plan_scene` is class `read` because it never writes at all. Pull request A
sends no device write and is not affected; nothing of this is implemented here.

## Not provided

Discovery or implicit enrollment, inventory edits, saving a scene as a preset, scheduling,
triggers, server-orchestrated transitions, synchronized frames, cross-device atomicity,
rollback, restoring the lighting before a scene, a background watcher, per-user ownership,
firmware version gates (DEC-020; capability comes from fresh readbacks), fuzzy name matching
and name mapping between firmware families. No hardware or multi-device claim is made.
