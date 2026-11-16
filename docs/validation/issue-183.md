# Issue #183 validation: rooms

Evidence for [#183](https://github.com/descipar/wled-mcp/issues/183) (milestone M7); contract in
[contract/rooms.md](../contract/rooms.md), decisions in
[ISSUE-183-DEC-001 and -002](../decisions/issue-183.md).

**The implementation evidence is mock evidence.** Tests use the synthetic fleet of
`tests/scene_support.py` (stateful `FakeWLED` controllers named `strip_a`, `strip_b`, `strip_c`),
the loopback fakes of `tests/acceptance_support.py` on `127.0.0.1` and pytest `tmp_path`; the
network guard of the test suite stays intact. No LAN device, no real data directory and no
hardware was used while implementing. The live run below is a separate step that is authorized
by ISSUE-183-DEC-001; its result is in the section "Live run record" (one controller only).

## Requirement to test map

| ID | Scenario | Evidence |
| --- | --- | --- |
| ROOM-01 / AC-183-01 | `kind` absent, `group`, `room`; other values and types, an unknown key and `format_version` 2 are rejected | `tests/test_groups.py` `test_a_group_without_kind_is_a_plain_group_and_an_explicit_group_kind_loads`, `test_any_other_kind_value_or_type_is_rejected_naming_the_key`, `test_a_misspelled_key_is_still_rejected_and_version_two_by_number` |
| ROOM-01 / AC-183-02 | Backward compatibility: plain group serialized byte-identically (golden JSON), a retained plain-group file is listed and never rewritten, a room round-trips | `test_a_plain_group_is_serialized_exactly_as_before_and_a_room_carries_kind`; `tests/test_room_tools.py` `test_a_retained_plain_group_file_is_listed_and_never_rewritten`, `test_saving_a_room_stores_kind_and_a_plain_group_stays_byte_identical`; the existing group and scene tests pass unchanged |
| ROOM-01 / AC-183-03 | Save a room; replace by a save without `kind` (previous document and warning); shared 100-group bound; `dry_run` writes nothing | `test_replacing_a_room_by_a_save_without_kind_demotes_it_and_warns`, `test_rooms_and_groups_share_the_group_bound`, `test_a_dry_run_save_of_a_room_writes_nothing_and_reports_a_conflict` |
| ROOM-02 / AC-183-04 | `wled_list_groups` shows `kind`, `room_conflicts` and a warning; overlapping plain groups are no conflict | `test_list_groups_reports_a_conflicting_pair_and_ignores_overlapping_plain_groups` |
| ROOM-02 / AC-183-05 | `wled_list_devices` shows `room` (null), `room_conflict`, no device I/O, works with `probe`, an unusable store never fails the list | `test_list_devices_shows_the_room_without_any_device_io`, `test_list_devices_reports_a_device_in_two_rooms_without_choosing_one`, `test_list_devices_with_probe_keeps_the_room_and_an_unusable_store_never_fails_it` |
| ROOM-02 / AC-183-06 | A room with a device of another room is refused before any write; the same room ID may change | `test_a_room_with_a_device_of_another_room_is_refused_but_the_same_room_may_change`; pure rules in `tests/test_rooms.py` |
| ROOM-03 / AC-183-07 | State on a three-member room: one master POST each, master only, verified, member order and origins | `test_a_state_reaches_every_member_with_one_master_post_each_and_verifies` |
| ROOM-03 / AC-183-08 | Partial failure: dropped write and lost readback; never overall success, POST count pinned, nothing replayed or rolled back; timed-out write | `test_a_partial_failure_is_never_overall_success_and_nothing_is_replayed`, `test_a_write_that_times_out_is_uncertain_and_never_retried` |
| ROOM-03, ROOM-06 / AC-183-09 | Unreachable member: strict writes nothing, `best_effort` writes the others and is `ok=false` | `test_an_unreachable_member_blocks_strict_and_is_skipped_by_best_effort` |
| ROOM-03 / AC-183-10 | `dry_run` is the plan, no POST, applies the ceiling, shows an unreachable member | `test_a_dry_run_is_the_plan_sends_no_write_and_shows_an_unreachable_member`, `test_a_member_capped_below_control_fails_preflight_and_the_mode_decides` |
| ROOM-03 / AC-183-11 | Capability validation fails only the member that cannot take the change; strict blocks all | `test_a_capability_a_member_lacks_fails_only_that_member_and_strict_blocks_all` |
| ROOM-03, ROOM-06 / AC-183-12 | Empty room (all members left the inventory), strict and `best_effort`; plain group, unknown ID, unusable file refused before I/O | `test_a_room_whose_members_all_left_the_inventory_writes_and_reads_nothing`, `test_a_plain_group_an_unknown_id_and_an_unusable_file_are_refused_before_any_io` |
| ROOM-02, ROOM-06 / AC-183-13 | Overlapping groups; duplicate rule before I/O; a device in two rooms refuses both rooms and leaves another room usable | `test_a_scene_may_reach_the_room_through_a_group_and_a_room_group_is_just_a_group`, `test_a_device_in_two_rooms_refuses_both_rooms_and_leaves_another_room_usable` |
| ROOM-03, ROOM-04 / AC-183-14 | Scene path: inside applies; untouched members listed; outside device, outside segment and master on a partial member refused as a whole; at most 10 problems with the total | `test_a_scene_inside_the_room_applies_and_untouched_members_are_listed`, `test_a_scene_touching_anything_outside_the_room_is_refused_as_a_whole`, `test_a_member_with_designated_segments_accepts_a_scene_inside_them`, `test_the_refusal_lists_at_most_ten_problems_and_the_total` |
| ROOM-04 / AC-183-15 | State refused for a partly assigned member before any I/O | `test_a_state_is_refused_for_a_partly_assigned_member_before_any_io` |
| ROOM-03 / AC-183-16 | Exactly one of `state` and `scene_id`; bounds; on-or-brightness rule; segment fields rejected by name | `test_the_request_needs_exactly_one_of_state_and_scene_id_and_a_bounded_master` |
| ROOM-04 / AC-183-17 | Zone in a room: exact targets and `data.room`; zone outside the room refused before I/O; `outside_room`; segment-only POST; `topology_changed` | `tests/test_zone_tools.py` `test_a_zone_inside_a_room_resolves_to_exact_targets_and_names_the_room`, `test_apply_in_a_room_writes_only_the_zone_segments_and_never_master`, `test_a_whole_device_member_allows_every_segment_of_the_zone`, `test_a_zone_with_a_device_outside_the_room_is_refused_before_any_io`, `test_a_zone_segment_outside_the_designated_segments_fails_that_part`, `test_a_layout_change_between_preview_and_write_is_still_topology_changed_in_a_room`, `test_a_conflicting_room_a_plain_group_and_an_unknown_room_are_refused_up_front` |
| ROOM-04 / AC-183-18 | Without `room` the zone tools are unchanged | the existing `tests/test_zone_tools.py` and `tests/test_zone_parity.py` pass unchanged; the plan without `room` has no `data.room` |
| ROOM-03 / AC-183-19 | Access: `control`, not destructive, absent from `read-only`; a capped member fails preflight; the write engine refuses a ceiling that dropped; `wled_save_group` stays `manage` | `tests/test_room_tools.py` (classification, ceiling and engine tests), `tests/test_access_profiles.py` (registry-driven profile tests with the new entries) |
| ROOM-03 / AC-183-20 | Tool contract: entry at the registry position; additions only against the retained 0.1.0 list | `tests/tool_contract.py`, `tests/test_tool_contract.py`, `tests/test_upgrade_compat.py` (unchanged, green) |
| ROOM-05 / AC-183-21 | Budget per tool and per profile | `tests/test_tool_budget.py`; numbers in [issue-235.md](issue-235.md#rooms-183) |
| ROOM-05 / AC-183-22 | Guidance names the room, group, zone and device decision; references still resolve | `tests/test_agent_guidance.py` (instructions and prompt over stdio and HTTP), `tests/test_tool_budget.py::test_served_guidance_resolves_every_tool_and_field_reference`, description checks in `tests/test_room_tools.py` |
| ROOM-03 / AC-183-23 | Stdio and Streamable HTTP return identical envelopes for the ordered steps | `tests/test_room_parity.py` (installed console on stdio and loopback HTTP, `full` profile, `shelf` capped at `read`) |
| ROOM-03 / AC-183-24 | No room, scene, group or device name in logs | `test_the_room_action_never_logs_room_scene_group_or_device_names`; `tests/test_private_identifiers.py` |
| ROOM-05 / AC-183-25 | README (200 lines, tool table equals the registry), coverage rule C7, migration-note parser | `tests/test_readme.py`, `tests/test_coverage.py`, `tests/test_upgrade_compat.py`, `scripts/check_coverage.py` |
| reuse guard | The room state apply and the equivalent scene apply return equal envelopes apart from `room`/`scene`, `operation`, origin and notes | `test_a_room_state_equals_the_scene_apply_it_reuses_apart_from_the_room_and_origin` |

## Commands run (implementation, no device, no LAN)

| Command | Result |
| --- | --- |
| `uv run pytest -n auto -q` | 3631 passed, 47 skipped, 8 subtests passed |
| `uv run ruff check` and `ruff format --check` on the CI file list; `ruff check src --select S --ignore S101` | pass |
| `uv run mypy` | no issues in 62 source files |
| `uv run python scripts/sync_agents.py --check`, `scripts/check_agent_setup.py`, `scripts/check_lock.py` | pass |
| `uv run python scripts/check_private_identifiers.py` | no private identifiers (rule checks only; no denylist locally) |
| `uv run python scripts/check_traceability.py`, `scripts/check_coverage.py` | pass |

## Reading choices

- A room is derived from stored room-kind groups; there is no inventory field, so a controller
  never has two competing sources of truth and `wled_add_device` is untouched.
- `data.room_conflicts` of `wled_list_devices` and `wled_list_groups` is omitted when there is no
  conflict, so existing results without rooms keep their exact shape (apart from `room: null`
  on each device entry and `kind` on each group entry).
- The conflict check on save reads the store and then saves; two processes saving two rooms
  at the same moment are not coordinated (the same limit as every other store write; the
  listings and the room actions still report and refuse the conflict).
- `dry_run` of `wled_apply_room` stays class `control` (TD-20-2), so the `read-only` profile has
  no room preview; it can use `wled_plan_scene` and `wled_plan_zone`.

## Limits

- Mock evidence for the implementation. Partial failure, an unreachable member, strict versus
  best-effort across several devices and conflicts between controllers are evidenced by mocks
  only; the live run has one controller.
- No second controller is available, so no real multi-controller room has been exercised.
- Not delivered (carried): scene format 2 or room targets inside scenes, a separate plan tool,
  room listing and save tools besides the group tools, a master state for a partly assigned
  member, any scheduling.

## Live run script (ISSUE-183-DEC-001; carried out by the coordinator session)

Bounds are those of ISSUE-183-DEC-001 and nothing wider: the one test controller; room and group
listing (read), a dry run, live state changes through `wled_apply_room` (power, brightness,
colour or effect on the existing segment) and the restore; baseline power off, brightness 47,
preset list exactly `[1 "Solid"]`, restored and verified by read-back; one or two evidence runs
(DEC-028), each preceded by a dry run and a read-only probe; only against the exact PASS-ready
candidate commit (record its full SHA); expires when #183 closes. Not authorized, so not in the
script: preset store, overwrite or delete, playlists, configuration, network or firmware
settings, OTA, reboot, geometry or segment creation or removal, any other controller, hub
deployment, discovery, writes to the deployed data directory or inventory. Stop and ask the owner
on any unexpected state, failed restoration or uncertain write; never retry an uncertain write
blindly. The controller's address and inventory stay in ignored local configuration; the record
says "the test controller" and gives firmware and LED/segment facts only (DEC-005).

Access: a local build of the candidate (stdio, optionally the same steps over loopback HTTP as the
second run) with its own scratch data directory and a one-device inventory entry for the test
controller, deleted afterwards. The hub, its inventory and its data are not touched (DEC-037).

Run 1 is required; Run 2 is optional (only if Run 1 raises a question or to cover the other
transport; never a matrix).

| Step | Call | Device I/O |
| --- | --- | --- |
| P0 | Read-only probe before each run: `wled_list_devices probe=true`, `wled_get_state` (full state saved locally), `wled_list_presets`. Verify the baseline (power off, brightness 47, presets exactly `[1 "Solid"]`, one segment); record the segment's colour, effect, palette, speed and intensity. Stop if it differs. | reads |
| L1 | Local only: `wled_save_group group_id=test-room kind=room` with the controller as a whole-device member; `wled_list_groups` (shows `kind`, no conflict); `wled_list_devices` (shows `room`); `wled_save_group kind=room dry_run=true` of a second room naming the same controller (expected refusal, device and other room named); `wled_apply_room` on a plain group ID (expected refusal "is a group, not a room"). | none |
| L2 | Dry run: `wled_apply_room room=test-room state={on:true, brightness:60} dry_run=true`, and the same with a stored scene (below). Expect `dry_run=true`, `would_write=[the controller]`, zero POSTs. | reads only |
| L3 | State path: `wled_apply_room room=test-room state={on:true, brightness:60}` (no `transition_ms`). Expect `applied/verified`, one master POST. Read back. | one master POST |
| L4 | Scene path: `wled_save_scene` (local file) with one `group` target `test-room`, no master, and segments `{ids:[0], colors:[[255,96,16]], effect_name:"Solid"}` (segment 0 must exist in the baseline; colour and effect only, no geometry). `wled_apply_room room=test-room scene_id=<it>`. Expect `applied/verified`, one segment POST. Read back. | one segment POST |
| L5 | Restore through the same room path and verify by read-back: a second scene with the recorded baseline segment values (colour, effect, palette, speed, intensity) and `wled_apply_room ... state={on:false, brightness:47}`. Then the reads of P0 again: power off, brightness 47, one segment with the baseline values, presets exactly `[1 "Solid"]`. If anything differs: at most one corrective write with `wled_set_state` or `wled_patch_segments` using the baseline values, re-read, and report to the owner. | up to two POSTs (one corrective at most) |
| L6 | Optional, read-only: a synthetic zone file over the controller's existing single segment; `wled_plan_zone zone=<it> room=test-room` (resolves to the exact segment and range, `data.room`). No zone apply. | reads only |

If the baseline has no usable segment 0 or the controller is on, stop and ask instead of
improvising. Colours are low-brightness and restored within the run. Expected device writes per
run: about four POSTs (master, segment, segment restore, master restore); every write step is a
single verified POST through the existing engine, and the POST count is taken from the
controller read-backs and the candidate's own results (`data.devices[].steps[]`), not from added
instrumentation. Raw captures stay in the ignored `.agent-runs/m7/issue-183/live/` directory.

## Live run record

Run 1 of the script above, 2026-11-16, against candidate `e7cf3d4ce98405a08a7f9d08705d3fd0be5408f1`
(PASS-reviewed head of the pull request), local build over stdio with a scratch data directory and a
one-device inventory entry; the hub, its inventory and its data were not touched. One run was enough
(DEC-028); Run 2 was not needed.

The test controller: WLED 16.0.1, ESP32-C3, 133 LEDs, one RGB segment (0 to 133), preset list
exactly `[1 "Solid"]`.

| Step | Result |
| --- | --- |
| P0 | Baseline as specified: power off, brightness 47, one segment (colour 0 `[138,189,255]`, effect 0 Solid, palette 11, speed 128, intensity 128), presets `[1 "Solid"]`. |
| L1 (local) | `wled_save_group kind=room` stored the room; `wled_list_groups` showed `kind` `room` and `group` and no conflict; `wled_list_devices` showed `room` on the controller; saving a second room for the same controller (`dry_run=true`) was refused (`VALIDATION_ERROR`, device and room named, `application=not_attempted`); `wled_apply_room` on a plain group was refused ("is a group, not a room", no device contacted). |
| L2 | `wled_apply_room` with `dry_run=true`, state and scene: `ok`, `dry_run=true`, `application=not_attempted`, `would_write=[controller]`, preflight ok; the device state afterwards was unchanged. |
| L3 | `state={on:true, brightness:60}`: `ok`, `applied`/`verified`, one master step; read-back on, brightness 60. |
| L4 | Scene with colour `[255,96,16]` and effect Solid on segment 0 through the room: `ok`, `applied`/`verified`, one segments step; read-back colour 0 `[255,96,16]`. |
| L5 | Restore through the room path (baseline segment scene, then `state={on:false, brightness:47}`): both `ok`, `applied`/`verified`. Read-back equals the baseline: power off, brightness 47, one segment with the baseline colours, effect, palette, speed and intensity, presets `[1 "Solid"]`; the full state and the raw WLED state compare equal to P0 (apart from read timestamps and runtime counters). No corrective write was needed. |

Four device writes in total (master, segments, segments, master), each a single verified POST of
the existing engine. No preset, playlist, configuration, network, firmware, reboot, discovery or
geometry operation, and no other controller. L6 (the optional zone check) was not run.

**Limit:** only one controller was available; partial failure, an unreachable member, strict
versus best-effort across several devices and conflicts between controllers are evidenced by mocks
only, not by this run. The raw captures stay in the ignored `.agent-runs/m7/issue-183/live/`
directory.
