# Issue #17 validation: device groups, scenes, plan and sharing (pull request A)

Evidence for [#17](https://github.com/descipar/wled-mcp/issues/17); contract in
[contract/groups-scenes.md](../contract/groups-scenes.md), decisions in
[ISSUE-17-DEC-001 and -002](../decisions/issue-17.md). Pull request A (definitions, store,
sharing and `wled_plan_scene`) is covered here; `wled_apply_scene` is pull request B, and its
acceptance scenarios are listed as pending.

**All evidence is mock evidence.** The fleet is `tests/scene_support.py`: several stateful
`FakeWLED` devices behind one router with per-device catalogs, an unreachable switch, a delay,
a request log and an in-flight gauge; the console tests use the loopback fake of
`tests/acceptance_support.py` on `127.0.0.1`. Stores use pytest `tmp_path`. No LAN device, no
real data directory and no hardware was used. No multi-device or synchronization behavior of
real controllers is claimed.

## Scenario to test map

| Scenario | Evidence |
| --- | --- |
| AC-17-01 group definitions: unknown device, duplicate member, same device with different segments, bounds, ID pattern, overwrite, zero device I/O, listing shows the expansion and flags a member that left the inventory | `tests/test_groups.py` (all parser rules, round trip); `tests/test_scene_tools.py` `test_save_group_stores_the_document_and_contacts_no_device`, `..._refuses_an_unknown_device_before_writing`, `..._rejects_a_duplicate_device_even_with_different_segments`, `test_group_schema_bounds_...`, `test_save_group_overwrite_dry_run_and_previous_document`, `test_list_groups_shows_the_exact_expansion_and_flags_a_missing_member`, `test_list_groups_counts_unusable_files_and_reports_not_found`, `test_delete_group_...` |
| AC-17-02 scene format 1: strict parse, `format_version` 0-9999 named, newer file untouched and counted, save and delete refuse unreadable files | `tests/test_scenes.py` (version table, field allowlist, bounds, strict JSON, round trip); `tests/test_scene_store.py` `test_a_newer_version_file_is_counted_named_and_never_rewritten`, `test_save_refuses_to_replace_an_unusable_file_even_with_overwrite`; `tests/test_scene_tools.py` `test_save_scene_rejects_other_versions_naming_integers`, `test_save_scene_overwrite_dry_run_and_stored_newer_version`, `test_a_group_file_of_a_newer_version_is_not_replaced_or_deleted` |
| AC-17-03 store durability: atomic save, failed write keeps the previous file, permissions, unwritable directory, `dry_run`, bounds, path-safe IDs, symlinks | `tests/test_scene_store.py` `test_a_failed_replace_keeps_the_previous_file_and_leaves_no_temporary_file`, `..._failed_fsync_or_write...`, `test_an_unwritable_data_directory_...`, `test_directory_is_0700_and_files_are_0600_on_posix` (POSIX CI), `test_dry_run_creates_nothing_and_changes_nothing`, `test_the_item_bound_...`, `test_ids_are_path_safe_before_any_filesystem_access`, `test_directories_and_symlinks_are_refused_not_followed` (symlink part needs privileges: CI Linux), `test_diagnostics_never_carry_names_paths_or_document_text`, `test_concurrent_saves_of_one_id_serialize_and_keep_a_complete_file`; tool level `test_an_unwritable_data_directory_is_a_not_attempted_storage_failure` |
| AC-17-04 plan: exact targets with origin and order, per-device reachability, master and segment plans from the real planners, names resolved per device, ambiguity with bounded candidates, per-device refusals equal to the single-device tools, offline device, zero POST | `tests/test_scene_tools.py` `test_plan_resolves_targets_names_and_plans_without_any_write`, `test_plan_equals_the_single_device_planners_for_the_same_request`, `test_numeric_ids_are_used_as_given_with_a_portability_warning`, `test_an_ambiguous_name_is_refused_per_device_with_bounded_candidates`, `test_an_unknown_name_...`, `test_planner_refusals_equal_the_single_device_tool_refusals` (six refusals compared message by message with `wled_patch_segments dry_run`), `test_cct_is_planned_where_the_range_reports_the_capability`, `test_an_offline_device_is_reported_...`, `test_a_timeout_is_a_per_device_entry_...`, `test_a_device_that_left_the_inventory_fails_preflight_without_device_io`, `test_plan_requests_are_reads_only_and_never_a_post` |
| AC-17-05 duplicate policy | `tests/test_scenes.py` `test_a_device_may_occur_once_after_expansion_naming_device_and_both_origins` (four shapes), `test_the_same_group_twice_is_a_duplicate_...`; `tests/test_scene_tools.py` `test_a_duplicate_device_refuses_the_whole_plan_before_any_device_io`, `test_save_scene_validates_references_and_expansion_before_writing`, `test_a_group_changed_after_saving_is_rechecked_at_plan_time` |
| AC-17-06 ordering and concurrency (read part; the write part is pull request B) | `tests/test_scene_tools.py` `test_at_most_four_devices_are_in_flight_and_results_keep_expansion_order` (8 devices, later ones finish first, gauge reaches exactly 4), `test_fewer_devices_than_the_limit_run_all_at_once`, `test_sixteen_devices_plan_and_seventeen_are_refused_before_io`, `test_the_plan_reads_under_the_existing_per_device_lock` |
| AC-17-07, AC-17-08, AC-17-09 apply policy, per-device outcomes, `apply dry_run` equals the plan | Pull request B. The plan's `mode`, `would_write` and `skipped` are tested in `test_mode_defaults_to_strict_and_blocks_every_device_on_one_failure` and `test_best_effort_with_no_device_passing_is_refused_with_the_first_device_code` |
| AC-17-10 sharing: placeholders, host-token refusal, `include_targets`, `target_map` validation, all or nothing, round trip, retained example | `tests/test_scenes.py` (`export_*`, `target_map_*`, `test_retained_example_parses_with_the_real_parser_and_is_the_canonical_export`); `tests/test_scene_tools.py` `test_shareable_export_carries_no_inventory_identity` (output equals `examples/contracts/scene.json`), `test_export_refuses_a_name_that_contains_a_configured_host`, `test_shared_scene_maps_back_through_target_map_and_round_trips`, `test_target_map_failures_write_nothing_all_or_nothing` |
| AC-17-11 classification | `tests/tool_contract.py` (seven entries, registry order, class, destructive flag), compared with the real registry and annotations by `tests/test_tool_contract.py`; `tests/test_scene_tools.py` `test_new_tools_are_classified_in_the_expected_contract`, `test_annotations_match_the_classes`; every plan and read path performs no POST (`test_plan_requests_are_reads_only_and_never_a_post`). The apply path and its single dispatch function are pull request B |
| AC-17-12 transport parity | `tests/test_scene_parity.py`: thirteen ordered steps (save, list, export, plan in both modes, conflicts, schema error, delete) over the installed console on stdio and on loopback Streamable HTTP, identical envelopes, `text == structuredContent`, `isError == !ok`, zero POST. Apply parity is pull request B |
| AC-17-13 contract evolution | `tests/test_upgrade_compat.py` passes without a migration note (seven tools and the `STORAGE_FAILED` enum value are additive); no existing tool schema changed |
| AC-17-14 hardware honesty | Mocks only; this file and the contract make no hardware claim |

## Reading choices

Choices made where the packet or the technical defaults leave room, for the reviewer and the
coordinator:

1. `wled_save_group` takes typed arguments (`group_id`, `name`, `members`) instead of an inline
   document; the stored file has the TD-17-4 shape and goes through the same strict parser as a
   read. `wled_save_scene` takes an inline document (text or object) as TD-17-5 states.
2. A configured-device check at plan time is per device: a directly named or group member device
   that is not in the inventory is a per-device `UNKNOWN_DEVICE` preflight failure with no
   device I/O (TD-17-4), not a whole-request refusal. Unknown groups, duplicates, device and
   patch limits, and ids-less entries on members without designated segments refuse the whole
   request (TD-17-7). At save time an unknown device is refused.
3. The plan envelope is `ok=true` when the scene would write something under the mode,
   `ok=false` otherwise (strict with a failing target, or best-effort with no passing target),
   with the first failing device's error in expansion order and the complete plan in `data`.
   Every plan outcome is `dry_run=true`.
4. Saving validates references and runs the plan's expansion against the groups stored at that
   moment; a scene that could never be planned is refused. A group changed later is caught at
   plan time.
5. Placeholders are a top-level `placeholders` list present only in a shared document, one
   positional name per target; a stored file never has the key.
6. Explicit `ids` in a segment entry of a group target apply to every member and override the
   member's designated segments; omitted `ids` use the designation.
7. Local definition tools report `application=not_attempted`; `data.saved` / `data.removed`
   state the file effect.
8. The store's write lock is a `threading.Lock` inside the store (all writes run in worker
   threads) rather than an `anyio.Lock` in the tools; the effect (serialized writes per
   process) is the one TD-17-3 states.
9. Coordination with #20 (refreshed #20 packet): the seven new tools are plain `Operation`
   constructions in `scene_tools.build_scene_operations`, appended at the tail of the registry,
   with their class only in `tests/tool_contract.py`; `tool_class` is not added here (#20 adds
   the required field to existing and new constructions, whichever merges second adds it to the
   other's). The TD-17-16 premise that the guard sits in `Resources.operation` is stale: the guard
   will be in the write engines and a public `Resources.require_access`, noted for pull request B
   in the contract. `tests/test_scene_parity.py` compares served envelopes through one helper
   (`comparable`) so a later per-call field (`correlation_id`) is a one-line change.
10. `docs/TOOL-CONTRACT.md` still lists `effect_name`/`palette_name` for the segment tools in
   "Segments: schema and omissions". That pre-existing statement is outside the sections this
   pull request may edit; the coverage notes (W-SEG-05, W-SEG-07) are corrected.

## Commands run

Run on Windows 11 with `uv run --frozen` in the isolated worktree of the branch. Results are
filled in below from the final candidate; CI results are in the pull request.

| Command | Result |
| --- | --- |
| `pytest` (all tests except the two known-problem files) | 2020 passed, 25 skipped (after merging `main` with #112) |
| `pytest tests/test_inventory_client.py tests/test_hw_http_probe.py` | 170 passed, 6 failed, 5 errors: the known Windows-only failures, unrelated to #17 |
| new #17 tests (`test_groups`, `test_scenes`, `test_scene_store`, `test_scene_tools`, `test_scene_parity`) | 287 passed, 2 skipped (POSIX permission bits, directory symlink) |
| `ruff check`, `ruff format --check` | clean |
| `mypy` (strict) | no issues in 41 source files |
| `scripts/check_traceability.py`, `scripts/check_coverage.py` (after `--update`), `scripts/sync_agents.py --check`, `scripts/check_private_identifiers.py`, `scripts/check_agent_setup.py` | pass; coverage unchanged by this pull request (89 features; 58 % of the planned scope, 47 % overall after #112) |
| `scripts/check_distribution.py` | fails locally only at the stdio handshake of the `uvx` step because the checkout path contains a space; CI is authoritative |

## Known limits

- Mock evidence only. Whether real controllers accept the planned payloads is the evidence of the
  single-device tools; scenes add no new write behavior in pull request A.
- Several server processes on one data directory are not coordinated.
- Plan results are a snapshot of one moment; the apply of pull request B plans again.
- The directory-symlink and POSIX permission tests run only on POSIX hosts (CI).
- The pull request B scenarios (AC-17-07 to AC-17-09, the apply parts of AC-17-06, -08, -11 and
  -12) have no evidence yet and #17 stays open for them.
