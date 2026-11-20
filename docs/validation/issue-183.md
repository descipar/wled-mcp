# Issue #183 validation: rooms

Evidence for [#183](https://github.com/descipar/wled-mcp/issues/183) (milestone M7); contract in
[contract/rooms.md](../contract/rooms.md), decisions in
[ISSUE-183-DEC-001 and -002](../decisions/issue-183.md).

**The implementation evidence is mock evidence.** Tests use the synthetic fleet of
`tests/scene_support.py` (stateful `FakeWLED` controllers `strip_a`, `strip_b`, `strip_c`), the
loopback fakes of `tests/acceptance_support.py` and pytest `tmp_path`; the network guard stays intact.
No LAN device or real data directory was used while implementing. The live run (authorized by
ISSUE-183-DEC-001) is recorded in "Live run record" (one controller only).

## Requirement to test map

| ID | Scenario | Evidence |
| --- | --- | --- |
| ROOM-01 / AC-183-01 | `kind` absent, `group`, `room`; other values and types, unknown key and `format_version` 2 rejected | `tests/test_groups.py` (kind and misspelled-key tests) |
| ROOM-01 / AC-183-02 | Plain group serialized byte-identically (golden JSON), retained plain-group file listed and never rewritten, a room round-trips | `tests/test_groups.py`; `tests/test_room_tools.py`; existing group and scene tests unchanged |
| ROOM-01 / AC-183-03 | Save a room; replace by a save without `kind` (previous document and warning); shared 100-group bound; `dry_run` writes nothing | `tests/test_room_tools.py` |
| ROOM-02 / AC-183-04 | `wled_list_groups` shows `kind`, `room_conflicts` and a warning; overlapping plain groups are no conflict | `tests/test_room_tools.py` |
| ROOM-02 / AC-183-05 | `wled_list_devices` shows `room` (null), `room_conflict`, no device I/O, works with `probe`, an unusable store never fails the list | `tests/test_room_tools.py` |
| ROOM-02 / AC-183-06 | A room with a device of another room is refused before any write; the same room ID may change | `tests/test_room_tools.py`; pure rules in `tests/test_rooms.py` |
| ROOM-03 / AC-183-07 | State on a three-member room: one master POST each, master only, verified, member order | `tests/test_room_tools.py` |
| ROOM-03 / AC-183-08 | Partial failure (dropped write, lost readback) is never overall success, POST count pinned, nothing replayed; timed-out write uncertain and never retried | `tests/test_room_tools.py` |
| ROOM-03, ROOM-06 / AC-183-09 | Unreachable member: strict writes nothing, `best_effort` writes the others and is `ok=false` | `tests/test_room_tools.py` |
| ROOM-03 / AC-183-10 | `dry_run` is the plan, no POST, applies the ceiling, shows an unreachable member | `tests/test_room_tools.py` |
| ROOM-03 / AC-183-11 | Capability validation fails only the member that cannot take the change; strict blocks all | `tests/test_room_tools.py` |
| ROOM-03, ROOM-06 / AC-183-12 | Empty room, strict and `best_effort`; plain group, unknown ID, unusable file refused before I/O | `tests/test_room_tools.py` |
| ROOM-02, ROOM-06 / AC-183-13 | Overlapping groups; duplicate rule before I/O; a device in two rooms refuses both rooms and leaves another room usable | `tests/test_room_tools.py` |
| ROOM-03, ROOM-04 / AC-183-14 | Scene path: inside applies, untouched members listed; outside device, outside segment and master on a partial member refused as a whole; at most 10 problems with the total | `tests/test_room_tools.py` |
| ROOM-04 / AC-183-15 | State refused for a partly assigned member before any I/O | `tests/test_room_tools.py` |
| ROOM-03 / AC-183-16 | Exactly one of `state` and `scene_id`; bounds; on-or-brightness rule; segment fields rejected by name | `tests/test_room_tools.py` |
| ROOM-04 / AC-183-17 | Zone in a room: exact targets and `data.room`; zone outside the room refused before I/O; segment-only POST; `topology_changed` | `tests/test_zone_tools.py` (seven room tests) |
| ROOM-04 / AC-183-18 | Without `room` the zone tools are unchanged | `tests/test_zone_tools.py`, `tests/test_zone_parity.py` unchanged |
| ROOM-03 / AC-183-19 | Access: `control`, not destructive, absent from `read-only`; capped member fails preflight; `wled_save_group` stays `manage` | `tests/test_room_tools.py`, `tests/test_access_profiles.py` |
| ROOM-03 / AC-183-20 | Tool contract entry at the registry position; additions only against the retained 0.1.0 list | `tests/tool_contract.py`, `tests/test_tool_contract.py`, `tests/test_upgrade_compat.py` |
| ROOM-05 / AC-183-21 | Budget per tool and per profile | `tests/test_tool_budget.py`; [issue-235.md](issue-235.md#rooms-183) |
| ROOM-05 / AC-183-22 | Guidance names the room, group, zone and device decision; references resolve | `tests/test_agent_guidance.py`, `tests/test_tool_budget.py`, `tests/test_room_tools.py` |
| ROOM-03 / AC-183-23 | Stdio and Streamable HTTP return identical envelopes | `tests/test_room_parity.py` (installed console, `full` profile, `shelf` capped at `read`) |
| ROOM-03 / AC-183-24 | No room, scene, group or device name in logs | `tests/test_room_tools.py`; `tests/test_private_identifiers.py` |
| ROOM-05 / AC-183-25 | README (200 lines, tool table equals registry), coverage rule C7, migration-note parser | `tests/test_readme.py`, `tests/test_coverage.py`, `tests/test_upgrade_compat.py`, `scripts/check_coverage.py` |
| reuse guard | Room state apply and the equivalent scene apply return equal envelopes apart from `room`/`scene`, `operation`, origin and notes | `tests/test_room_tools.py` |

## Commands run (implementation, no device, no LAN)

| Command | Result |
| --- | --- |
| `uv run pytest -n auto -q` | 3631 passed, 47 skipped, 8 subtests passed |
| ruff check and format (CI file list), `ruff check src --select S --ignore S101`, `mypy` | pass (62 source files) |
| `sync_agents.py --check`, `check_agent_setup.py`, `check_lock.py`, `check_private_identifiers.py`, `check_traceability.py`, `check_coverage.py` | pass |

## Reading choices

- A room is derived from stored room-kind groups; there is no inventory field, so there is one source of
  truth and `wled_add_device` is untouched.
- `data.room_conflicts` is omitted when there is no conflict, so existing results keep their shape
  (apart from `room: null` per device and `kind` per group).
- The conflict check on save reads then saves; two processes saving two rooms at once are not
  coordinated (the same limit as every store write; listings and room actions still report the conflict).
- `dry_run` of `wled_apply_room` stays class `control` (TD-20-2), so `read-only` has no room preview; it
  can use `wled_plan_scene` and `wled_plan_zone`.

## Limits

- Mock evidence for the implementation; partial failure, unreachable member, strict versus best-effort
  across devices and conflicts between controllers are mocks only (the live run has one controller).
- Not delivered (carried): scene format 2 or room targets in scenes, a separate plan tool, room listing
  and save tools besides the group tools, a master state for a partly assigned member, scheduling.

## Live run script (ISSUE-183-DEC-001; carried out by the coordinator session)

Bounds are those of ISSUE-183-DEC-001: the one test controller; room and group listing, a dry run, live
state changes through `wled_apply_room` (power, brightness, colour or effect on the existing segment)
and the restore; baseline power off, brightness 47, presets exactly `[1 "Solid"]`, restored and verified
by read-back; one or two evidence runs (DEC-028) against the exact PASS-ready candidate commit; expires
when #183 closes. Not authorized: preset store, overwrite or delete, playlists, configuration, network
or firmware settings, OTA, reboot, geometry changes, other controllers, hub deployment, discovery. Stop
and ask on any unexpected state, failed restoration or uncertain write; never retry blindly. A local
build over stdio with a scratch data directory; the hub is not touched (DEC-037).

Steps: P0 read-only probe and baseline check; L1 local room save, listing, refused second room and
refused plain group; L2 dry runs (zero POSTs); L3 state path (one master POST); L4 scene path (one
segment POST, colour and Solid on segment 0); L5 restore through the room path and read-back equal to
P0 (at most one corrective write); L6 optional read-only `wled_plan_zone room=...`. About four POSTs per
run, each a single verified POST of the existing engine.

## Live run record

Run 1, 2026-11-16, candidate `e7cf3d4ce98405a08a7f9d08705d3fd0be5408f1` (PASS-reviewed head of the pull
request), local stdio build with a scratch data directory; the hub was untouched. One run was enough
(DEC-028). Controller: WLED 16.0.1, ESP32-C3, 133 LEDs, one RGB segment, presets exactly `[1 "Solid"]`.

| Step | Result |
| --- | --- |
| P0 | Baseline as specified: power off, brightness 47, one segment, presets `[1 "Solid"]`. |
| L1 (local) | Room stored; listings showed `kind` and `room`, no conflict; a second room for the same controller refused (`VALIDATION_ERROR`, `application=not_attempted`); `wled_apply_room` on a plain group refused, no device contacted. |
| L2 | Dry runs (state and scene): `ok`, `would_write=[controller]`, `application=not_attempted`; device unchanged. |
| L3 | `state={on:true, brightness:60}`: `applied`/`verified`, one master step; read-back on, brightness 60. |
| L4 | Scene (colour `[255,96,16]`, Solid, segment 0) through the room: `applied`/`verified`, one segments step; read-back matched. |
| L5 | Restore through the room path: both `applied`/`verified`; read-back equals the baseline (power off, brightness 47, segment values, presets); raw state equals P0 apart from timestamps and counters; no corrective write. |

Four device writes in total (master, segments, segments, master). No preset, playlist, configuration,
network, firmware, reboot, discovery or geometry operation, no other controller. L6 was not run.
**Limit:** one controller only; multi-device failure behavior is mocks only. Raw captures stay in the
ignored `.agent-runs/m7/issue-183/live/` directory.
