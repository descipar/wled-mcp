# Rooms (ROOM-01 to ROOM-06, #183)

Contract for milestone M7. A room is a stored group with `kind` `room`: it says where controllers
are, and one explicit tool applies a master state or a stored scene to the members of a room. Rooms
were released with milestone M8 (see the changelog). Decisions:
[ISSUE-183-DEC-002](../decisions/m7-m8.md) records the design defaults (technical proposals,
not human decisions; the owner can change any at the merge decision);
[ISSUE-183-DEC-001](../decisions/m7-m8.md) is the bounded live-run authorization. Evidence:
[validation/m7-m8.md](../validation/m7-m8.md). Both transports share these operations.
Examples are synthetic.

Shared mechanics are those of [groups-scenes.md](groups-scenes.md): storage, bounds,
`strict`/`best_effort`, per-device and aggregate outcomes, `WRITE_OUTCOME_UNKNOWN` and
`VERIFICATION_MISMATCH`. Zone resolution is that of [zones.md](zones.md).

## Requirements

| ID | Statement | Evidence |
| --- | --- | --- |
| ROOM-01 | A stored group can be marked as a room (`kind`, default `group`); existing group files stay valid, are never rewritten and plain groups are serialized byte-identically to before. | mocked |
| ROOM-02 | A controller belongs to at most one room; `wled_list_devices` and `wled_list_groups` show rooms and conflicts read-only; a conflict is reported and refuses the room actions before any write, never resolved silently. | mocked |
| ROOM-03 | One explicit action, `wled_apply_room`, applies a master state patch or a stored scene to the members of a room with dry run, capability validation, per-device outcomes and the uncertain-write handling of the scene apply; partial failure never reports overall success. | mocked; one authorized live run on one controller |
| ROOM-04 | A zone inside a room resolves to exact controller, segment and range targets; a room action cannot silently touch a controller or segment outside the room's members and designated segments. | mocked |
| ROOM-05 | Tool descriptions and the served guidance say when to use a room, a group, a zone or a single device. | mocked |
| ROOM-06 | Mocked multi-controller tests cover partial failure, an unreachable member, overlapping groups and an empty room; the live run covers one controller and states that no second controller was available. | mocked; live record in the validation file |

## Format

A room is a group document (`wled-mcp.group`, `format_version` 1) with the optional key `kind`:

```json
{
  "format": "wled-mcp.group",
  "format_version": 1,
  "id": "living",
  "name": "Living room",
  "kind": "room",
  "members": [{"device": "strip_a"}, {"device": "strip_b", "segments": [0, 2]}]
}
```

- `kind` is `"group"` (default when absent) or `"room"`; any other value or type is
  `VALIDATION_ERROR` naming `kind`. Unknown keys are still rejected.
- `kind` is written only for a room, so a plain group stays byte-identical to a pre-room document.
  The version does not change (new optional key, [versioning](versioning.md#schema-evolution));
  no migration runs and existing files are never rewritten.
- Downgrade: a server from before rooms rejects a room file as an unknown key and counts it in
  `invalid_count`; the file stays untouched. Plain-group files stay readable by older servers
  ([migration note](versioning.md#migration-notes)).
- Limits are those of groups: 1 to 16 members, at most 100 stored groups in total (rooms and
  groups share the bound, the `groups/` directory, locks and atomic save). A room cannot be stored
  empty. A member with `segments` designates those segments for the room; without it the whole
  controller belongs to the room.
- There is no separate store, inventory field or room tool besides the group tools:
  `wled_save_group` (`kind`), `wled_list_groups` and `wled_delete_group`. Nothing is detected,
  named or assigned automatically.

## Belonging and conflicts

Belonging is derived: a controller is in the room whose room-kind group lists it, at most one room
per controller (a plain group may overlap anything). A controller listed by two rooms, with or
without segments, is a *conflict*.

- `wled_save_group kind=room` refuses a member device that another stored room lists
  (`VALIDATION_ERROR`, device and other room named, nothing written; `dry_run` reports the same).
  Replacing the same room ID is allowed. Replacing a room by a save without `kind` turns it into a
  plain group (previous document in `data.replaced`, a warning says the kind changed).
- `wled_list_groups`: every entry has `kind`; `data.room_conflicts` (`device_id`, sorted `rooms`)
  and one warning appear only when a conflict exists.
- `wled_list_devices`: every entry has `room` (room ID or `null`); a device in two rooms has
  `room: null` and `room_conflict` (sorted IDs); `data.room_conflicts` (count) and a warning appear
  only on a conflict. The call reads the local `groups/` directory and contacts no device unless
  `probe=true`. An unusable store never fails the listing: the `room` keys are omitted with a
  warning.
- A hand-edited conflict is caught by the listings and the refusals below; a conflict not
  involving the requested room does not block it.
- The save-time conflict check reads then saves like every store write; two processes saving two
  rooms for one device at the same moment are not coordinated, and the listings and room actions
  still report and refuse the conflict.

## `wled_apply_room`

Class `control` (not read-only, destructive or idempotent), `control` and `full` profiles only, no
`device_id`: the per-device ceiling is checked per member, like a scene. `dry_run` does not lower
the class, so a `read-only` profile has no room preview (it can use `wled_plan_scene` and
`wled_plan_zone`).

Inputs: `room` (stored room ID; lookup by ID only), exactly one of `state` and `scene_id`, `mode`
(`strict` default or `best_effort`), `dry_run`.

- `state`: a master patch: `on`, `brightness` (0-255), `transition_ms` (0-65500), with the
  `wled_set_state` rule (at least `on` or `brightness`). Never segments, geometry or a raw patch
  (rejected by name).
- `scene_id`: a stored scene, which names its own controllers or groups; applied only if
  everything it touches lies inside the room.

Refused as a whole before any device I/O (`VALIDATION_ERROR`, `application` `not_attempted`,
`data.room`, `data.problems` with at most 10 entries of `device_id`, `reason` and `message`, and
`data.problem_total`):

| Reason | Meaning |
| --- | --- |
| (no reason code) | The ID is unknown, names a plain group ("is a group, not a room") or an unusable file; neither `state` nor `scene_id`, or both. |
| `room_conflict` | A member of the requested room is also in another room. |
| `partial_member` | With `state`: a member designates segments, so a master change would switch its other segments too. With a scene: the scene sets `master` on such a member. Use a scene without `master`, or a zone. |
| `device_outside_room` | The scene targets a controller that is not a member. |
| `segment_outside_room` | The scene writes a segment the member does not designate. |

A scene that expands to the same controller twice, to more than 16 controllers or to more than 64
segment patches is refused by the scene rules (same messages). A group named by the scene may be
room-kind; `kind` is only a label there.

Room controllers the scene does not name are not an error: they are listed in
`data.members_not_targeted` with one warning. A member that left the inventory is a per-device
`UNKNOWN_DEVICE` preflight failure without I/O, as for a scene (an empty room writes nothing).

Execution is the scene path unchanged: one target per member (`origin` `room:<id>/member:<n>`; a
scene keeps its own origins), `plan_device` for the fresh read, access ceiling and the master and
segment planners, then `apply_device` and `Resources.write_verified` (master step, then segment
step, each replanned under the device lock and checked by readback), at most four in flight. No
new write primitive, application or verification value, error code or room-level lock. The
envelope is that of `wled_apply_scene` with `data.room` (`id`, `name`), `data.scene` for the scene
path, `data.devices[]` and `data.summary`. Dry run returns the plan (`targets[]`, `would_write`,
`skipped`) and sends no write.

Aggregate: the first-match table of [groups-scenes.md](groups-scenes.md#apply-wled_apply_scene)
applies. Some members applied and others refused, skipped or unverified is `applied` / `mismatch`,
`ok=false`, `VERIFICATION_MISMATCH`; any `unknown` member makes the result `unknown` / `unknown`,
`WRITE_OUTCOME_UNKNOWN`; a `best_effort` run that skipped a member ends `ok=false`; `ok=true` only
when every targeted member is `applied` and `verified`. Not atomic, synchronized, rolled back or
replayed: a timed-out or unreadable write is never retried and the reconciliation text says to
read the state of the listed devices.

## Zones in rooms

`wled_plan_zone` and `wled_apply_zone` take an optional `room` (room ID); without it nothing
changes. With it, before any device I/O: the room exists, is a room, has no conflict for the
zone's devices, and every part's device is a member (`VALIDATION_ERROR`, "the zone extends outside
the room", `data.problems` as above). After the fresh read, in the binding step that already
guards the write (plan and again under the device lock), a member that designates segments admits
only those: another resolved segment fails that part with `data.problem.reason` `outside_room`
(`layout_change_required` false, nothing sent); a member without designated segments admits every
segment of the zone. A layout change between preview and write is still `topology_changed`.
`data.room` (`id`, `name`) is added to plan and apply results; `zone_target` carries the exact
`segment_ids`, spans and LED ranges. A zone call never writes master state.

## When to use what

| Use | When |
| --- | --- |
| a room (`wled_apply_room`) | a state or scene for the controllers of one place; one room per controller |
| a plain group (`wled_apply_scene` with a group target) | any other set of controllers (a floor, all lamps); may overlap rooms |
| a zone (`wled_apply_zone`) | part of a controller or a physical region over several controllers |
| a single device (`wled_set_state`, `wled_patch_segments`) | one controller |

The served `instructions` carry the same statement ([agent-guidance.md](agent-guidance.md)).

## Not provided

A controller in several rooms; automatic room detection, naming or moving; a room field in the
inventory; discovery; scenes without lamp names applied to whichever room (needs a new scene
format version); `wled_list_rooms`, `wled_save_room`, `wled_delete_room` or `wled_plan_room` (the
group tools and `dry_run` are used); translating a master state into segment changes for a partly
assigned member; timers and schedules; per-room permissions; any hardware claim beyond the
recorded live run.
