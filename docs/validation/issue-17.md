# Issue #17 validation: device groups, scenes, plan, apply and sharing

Evidence for [#17](https://github.com/descipar/wled-mcp/issues/17); contract in
[contract/groups-scenes.md](../contract/groups-scenes.md), decisions in
[ISSUE-17-DEC-001 and -002](../decisions/issue-17.md). Pull request A (definitions, store,
sharing and `wled_plan_scene`) and pull request B (`wled_apply_scene`, the executor, the policy
and the aggregate outcome) are covered here.

**All evidence is mock evidence.** The fleet is `tests/scene_support.py`: several stateful
`FakeWLED` devices behind one router with per-device catalogs, an unreachable switch, a delay,
a request log, an in-flight gauge (overall and per host) and the failure injections of
`FakeWLED` (ignored POST, failed POST, lost readback, a stalled POST); the console tests use the loopback fake of
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
| AC-17-06 ordering and concurrency | Read part (pull request A): `tests/test_scene_tools.py` `test_at_most_four_devices_are_in_flight_and_results_keep_expansion_order` (8 devices, later ones finish first, gauge reaches exactly 4), `test_fewer_devices_than_the_limit_run_all_at_once`, `test_sixteen_devices_plan_and_seventeen_are_refused_before_io`, `test_the_plan_reads_under_the_existing_per_device_lock`. Write part (pull request B): `tests/test_scene_apply.py` `test_at_most_four_devices_are_written_at_once_and_results_keep_expansion_order` (8 devices, later ones finish first, report in document order, gauge exactly 4), `test_the_write_phase_itself_is_bounded_not_only_the_preflight` (gauge inside the POST), `test_two_scenes_on_one_device_serialize_under_the_existing_lock` (per-host gauge 1), `test_apply_writes_every_device_master_first_then_segments_and_verifies` (POST order per device), `test_a_device_with_only_one_kind_of_target_gets_exactly_one_post` |
| AC-17-07 policy: `strict` writes nothing if any preflight fails, `best_effort` skips only failing devices, a write-phase failure never stops the others | `tests/test_scene_apply.py` `test_strict_writes_nothing_anywhere_when_one_target_fails_preflight` (five refusal kinds: offline, ambiguous name, missing segment, no CCT evidence, locked device; zero POST on every device and unchanged state), `test_strict_is_the_default_and_best_effort_must_be_requested`, `test_best_effort_skips_only_the_failing_device_and_writes_the_rest` (four kinds), `..._with_every_device_passing_is_a_full_success`, `..._with_no_device_passing_writes_nothing_with_the_first_error`, `test_an_unconfigured_device_is_a_per_device_unknown_device_refusal` (direct and group member, no I/O for it), `test_a_request_refused_as_a_whole_does_no_device_io`, `test_a_device_failing_in_the_write_phase_never_stops_or_undoes_another` (three failure kinds in both modes), `test_a_device_below_control_fails_preflight_before_any_read_of_it` |
| AC-17-08 outcomes: per-device verified, mismatch, unknown and not-attempted pass through unchanged; no replay; the aggregate mapping; no compensation; "not atomic, not synchronized" | `tests/test_scene_apply.py` `test_a_device_failing_in_the_write_phase_...` (lost readback is `unknown/unknown`, an ignored or failed POST is `unknown/mismatch`, the segment step is skipped with the reason, exact POST counts), `test_an_uncertain_segment_step_is_never_replayed` (drop, failed POST, lost readback on the segment POST: exactly 2 POSTs), `test_no_device_is_ever_written_twice_and_nothing_is_compensated`, `test_a_timed_out_write_is_uncertain_and_never_retried`, `test_a_proven_master_step_with_a_refused_segment_step_is_a_partial_device` (`applied/mismatch`), `test_the_aggregate_follows_the_documented_mapping_for_every_combination` (258 combinations of six device situations against an independent statement of the rule), `test_a_strict_block_marks_every_passing_device_as_not_written`, `test_a_stopped_scene_leaves_unstarted_devices_untouched_and_never_replays`, `test_a_bug_in_one_device_...` and `test_a_bug_after_a_step_may_have_been_sent_is_reported_as_unknown`, `test_a_bug_after_the_master_write_keeps_the_engine_verdict` and `test_a_bug_after_an_uncertain_master_write_stays_unknown` (a failure while building a step's report data never turns a sent write into not attempted), `test_apply_never_logs_scene_names_ids_or_device_content`; the wording is asserted in `test_apply_registers_as_control_with_the_write_annotations` and the envelope `warnings` |
| AC-17-09 `wled_apply_scene dry_run=true` equals the plan and sends no POST | `tests/test_scene_apply.py` `test_apply_dry_run_returns_exactly_the_plan_and_sends_no_post` (both modes, with and without a failing device), `test_apply_dry_run_of_a_refused_request_equals_the_plan_refusal`, `test_apply_dry_run_applies_the_same_ceiling_as_an_apply`; over both transports `tests/test_scene_parity.py` `test_the_apply_over_a_real_transport_writes_master_then_segments_and_verifies` |
| AC-17-10 sharing: placeholders, host-token refusal, `include_targets`, `target_map` validation, all or nothing, round trip, retained example | `tests/test_scenes.py` (`export_*`, `target_map_*`, `test_retained_example_parses_with_the_real_parser_and_is_the_canonical_export`); `tests/test_scene_tools.py` `test_shareable_export_carries_no_inventory_identity` (output equals `examples/contracts/scene.json`), `test_export_refuses_a_name_that_contains_a_configured_host`, `test_shared_scene_maps_back_through_target_map_and_round_trips`, `test_target_map_failures_write_nothing_all_or_nothing` |
| AC-17-11 classification | `tests/tool_contract.py` (eight scene tools, 26 in total, registry order, class, destructive flag), compared with the real registry and annotations by `tests/test_tool_contract.py`; `tests/test_scene_tools.py` `test_new_tools_are_classified_in_the_expected_contract`, `test_annotations_match_the_classes`; `tests/test_scene_apply.py` `test_apply_is_a_control_tool_and_not_destructive`, `test_apply_registers_as_control_with_the_write_annotations`; `tests/test_access_profiles.py` pins `wled_apply_scene` in the control set. Every plan and read path performs no POST (`test_plan_requests_are_reads_only_and_never_a_post`). The apply reaches devices only through the write engine, the seam #20 guards: `test_the_preflight_calls_require_access_once_per_expanded_device` (public check, class `control`, before any read of the device), `test_the_write_engine_refuses_a_class_the_preflight_no_longer_matches` (G3 refuses the write, zero POST), `test_a_device_below_control_...` (profile cap), `test_an_unrestricted_deployment_is_not_affected_by_the_checks` |
| AC-17-12 transport parity | `tests/test_scene_parity.py`: eighteen ordered steps (save, list, export, plan in both modes, apply dry run, schema error and missing scene, a real apply twice, conflicts, delete) over the installed console on stdio and on loopback Streamable HTTP, identical envelopes, `text == structuredContent`, `isError == !ok`; only the two real applies send POSTs (master and segment step each), checked cumulatively per step by `test_only_the_real_applies_send_device_posts` |
| AC-17-13 contract evolution | `tests/test_upgrade_compat.py` passes without a migration note (eight tools and the `STORAGE_FAILED` enum value are additive); no existing tool schema changed |
| AC-17-14 hardware honesty | Mocks only; this file and the contract make no hardware claim |

## Carried items of the pull request A review

| Item | Evidence |
| --- | --- |
| Store-level ID check is the refusal, not a missing file (mutant M16) | `tests/test_scene_store.py` `test_the_store_id_check_is_the_refusal_not_a_missing_file` (an existing directory, a planted file outside it, the message `ID is not valid`) |
| Windows device names are not group or scene IDs | `test_windows_device_names_are_not_usable_ids` (all 22 names, store, scene parser and group parser), `test_names_that_only_resemble_a_device_name_stay_valid` |
| One store lock per directory | `test_two_store_instances_over_one_directory_cannot_create_the_same_id` |
| Leak check scans every exported string | `tests/test_scenes.py` `test_export_scans_every_exported_string_not_only_name_and_description`, `test_export_scans_the_kept_target_references_only_when_they_are_kept`; `tests/test_scene_tools.py` `test_export_refuses_a_catalog_name_that_contains_a_configured_host` |
| `bundles.py` uses the shared `format_version` helper | `formats.check_format` takes the reconciliation text; `tests/test_bundles.py` is unchanged and passes (messages and reconciliation are identical) |
| `DESTRUCTIVE` comment; segment `effect_name`/`palette_name` wording in `docs/TOOL-CONTRACT.md` | Documentation corrections; the segment tools accept numeric IDs only |

## Reading choices (pull request B)

1. The aggregate treats "a device is unknown" as `application=unknown` (a lost readback and a
   readback that differs after a possible dispatch), mapping both to `unknown/unknown` +
   `WRITE_OUTCOME_UNKNOWN` as TD-17-10 words it. The device entries keep the exact
   verification (`unknown` or `mismatch`), so nothing is hidden.
2. `wled_apply_scene dry_run=true` runs the plan with the per-device ceiling check of class
   `control`; the read-class `wled_plan_scene` has no such check. Both are otherwise identical
   (`data` and envelope, `operation` aside). A preview is not a lower class (TD-20-2), and a
   read-only deployment still previews with `wled_plan_scene`.
3. A proven master step followed by a segment step that was refused before it was sent
   (state changed after the preflight) is `applied/mismatch` for the device, the existing
   "proven partial steps" row, with the segment step's error and `skipped` text.
4. Master and segments are two `write_verified` calls (two lock acquisitions, as TD-17-9's
   worst-case wall time states). Another writer can interleave between them on that device;
   the segment step replans against the state it then reads.
5. The error of an aggregate that wrote nothing is the first refusal in expansion order,
   whether it came from the preflight or from a write refused before dispatch, with the device
   named in the message.
6. A stopped call returns no result (cancellation is not an outcome); the contract says which
   devices are untouched and which are uncertain.
7. The apply annotations (`readOnly=false`, `destructive=false`) are a local constant in
   `scene_tools.py` because `operations.py` imports this module.

## Reading choices (pull request A)

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
10. `docs/TOOL-CONTRACT.md` listed `effect_name`/`palette_name` for the segment tools in
   "Segments: schema and omissions". Pull request B corrects that section (numeric IDs only;
   names exist only in scenes), as it did the coverage notes (W-SEG-05, W-SEG-07).

## Commands run

Run on Windows 11 with `uv run --frozen` in the isolated worktree of the branch, on the
candidate after merging `main` (#116). CI results are in the pull request.

| Command | Result |
| --- | --- |
| `pytest` (all tests except the two known-problem files) | 2491 passed, 25 skipped |
| `pytest tests/test_inventory_client.py tests/test_hw_http_probe.py` | 171 passed, 6 failed, 5 errors: the known Windows-only failures, unrelated to #17 |
| the #17 tests (`test_groups`, `test_scenes`, `test_scene_store`, `test_scene_tools`, `test_scene_parity`, `test_scene_apply`) | 658 passed, 2 skipped (POSIX permission bits, directory symlink) |
| `ruff check`, `ruff format --check` | clean |
| `mypy` (strict) | no issues in 43 source files |
| `scripts/check_traceability.py`, `scripts/check_coverage.py` (after `--update`), `scripts/sync_agents.py --check`, `scripts/check_private_identifiers.py`, `scripts/check_agent_setup.py` | pass; coverage 89 features, 58 % of the planned scope, 47 % overall (no row changes status; ten rows name `wled_apply_scene` as a delivering tool) |
| `scripts/check_distribution.py` | fails locally only at the stdio handshake of the `uvx` step because the checkout path contains a space; CI is authoritative |
| mutation spot checks by hand on the apply code (strict not blocking, best-effort blocking, segments run after a failed master, concurrency 8, unknown rule dropped, no `require_access`, dry run writing, partial device not marked, `ok` for a partial result, results in completion order) and on the carried items (shared directory lock, reserved names, store ID check, leak scan of names, of the scene ID and of kept references) | every mutant is killed by a test listed above |

## Known limits

- Mock evidence only. Whether real controllers accept the planned payloads is the evidence of the
  single-device tools (their hardware acceptance is recorded separately); the apply adds no new
  write path, only the composition of those two planners and the shared write engine per device.
  A single-controller smoke of one scene (capture, apply, restore) needs its own authorization
  naming the device and the operations; **no multi-device or synchronization behavior of real
  controllers is claimed**, and hardware acceptance of #17 is not part of this evidence.
- Several server processes on one data directory are not coordinated; the lock is per
  directory inside one process.
- Plan results are a snapshot of one moment; the apply plans again under each device lock.
- A stopped call returns no result: devices not yet started are untouched and writes in flight
  are uncertain (contract: "Stopped scenes"). The HTTP service's graceful drain is only the
  operation timeout plus two seconds, shorter than a 16-device scene can take.
- Master and segments of one device are two write operations; another writer may interleave
  between them.
- The directory-symlink and POSIX permission tests run only on POSIX hosts (CI).
