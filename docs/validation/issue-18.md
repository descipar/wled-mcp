# Issue #18 validation evidence

Evidence for [issue #18](https://github.com/descipar/wled-mcp/issues/18). Contract:
[contract/presets.md](../contract/presets.md). Requirements: PRE-03, PRE-04 (restore
execution), PLAY-01 and S2-PRESET-01 to -03 of [STAGE-2.md](../STAGE-2.md).

## First pull request: restore, supplied-state save, snapshot listing

Mock transport and `tmp_path` only; no LAN, device or hardware access. The stateful
fake `tests/preset_support.py` models the WLED v16.0.1 write routes recorded in
[SOURCES.md](../SOURCES.md#issue-18-wled-16-preset-write-evidence); the tests set the
firmware version explicitly (16.0.1). Nothing here is hardware acceptance.

| Scenario | Evidence |
| --- | --- |
| A18-01 state route: supplied state stored verbatim and verified, live effect in plan and result, firmware-removed keys excluded, one POST | `tests/test_preset_writes.py::test_supplied_state_is_applied_then_stored_verbatim_with_one_post`, `::test_dry_run_states_the_live_effect_and_sends_nothing`, `::test_any_stored_difference_including_unknown_fields_is_a_mismatch`, `::test_minimal_state_and_omitted_fields_are_absent_not_null` |
| A18-02 unknown/control keys, out-of-range segments and bad names refused with zero POSTs; occupied ID without `overwrite` is a conflict; snapshot before the POST; backup failure sends nothing | `tests/test_preset_writes.py::test_control_unknown_and_malformed_state_is_refused_by_the_schema`, `::test_preset_name_rules_are_enforced`, `::test_overwrite_needs_an_explicit_preset_id`, `::test_out_of_range_state_is_refused_before_any_write`, `::test_colors_need_capability_evidence`, `::test_occupied_id_without_overwrite_is_a_conflict`, `::test_overwrite_takes_a_snapshot_before_the_single_post`, `::test_backup_failure_sends_nothing`, `::test_free_destination_taken_after_planning_is_a_conflict`, `::test_unknown_device_touches_nothing` |
| A18-03 state restore to its own free ID, an explicit different ID and an occupied ID (overwrite plus new snapshot); firmware mismatch, api-command/unknown snapshot, destination changed after planning; dry run sends nothing and creates no file | `tests/test_restore.py::test_state_snapshot_restores_verbatim_to_its_own_free_id`, `::test_state_snapshot_restores_to_an_explicit_different_free_id`, `::test_occupied_destination_needs_overwrite_and_takes_a_new_snapshot_first`, `::test_firmware_version_mismatch_is_refused`, `::test_api_command_and_unknown_snapshots_are_refused_without_device_io`, `::test_destination_changed_after_planning_is_a_conflict`, `::test_dry_run_sends_nothing_and_creates_no_file`, `::test_missing_malformed_and_foreign_backup_ids`, `::test_nameless_state_snapshot_expects_the_firmware_default_name` |
| A18-04 playlist restore through the playlist route, semantic verification, unknown or unreproducible playlist fields block in the preview, playback effect named | `tests/test_restore.py::test_playlist_snapshot_restores_through_the_playlist_route`, `::test_unreproducible_or_unsafe_playlist_blocks_in_preview_and_write`, `::test_playlist_semantic_difference_is_a_mismatch`, `::test_playlist_dry_run_names_the_playback_effect`, `::test_playlist_quick_load_label_is_sent_and_verified`, `::test_unusable_stored_playlist_values_are_a_mismatch_not_a_crash` |
| A18-05 timeout with unreadable readback is `unknown`, no resend; a second call is a new invocation | `tests/test_preset_writes.py::test_timeout_with_unreadable_readback_is_unknown_and_not_resent`, `::test_timeout_after_apply_reconciles_by_readback`, `tests/test_restore.py::test_timeout_with_unreadable_readback_is_unknown_and_not_resent` |
| A18-06 `wled_list_snapshots` lists valid metadata newest first, counts invalid files, reads no device | `tests/test_restore.py::test_list_snapshots_newest_first_counts_invalid_and_reads_no_device`, `::test_list_snapshots_empty_and_unknown_device` |
| A18-14 transport parity for the new tools | `tests/test_preset_writes.py::test_protocol_envelope_and_schema_errors_for_the_new_tools` (in-process MCP client: strict schemas, live effect in descriptions, text fallback equals structured content, schema errors as `VALIDATION_ERROR`); both transports serve the same registry, compared generically by `tests/test_http_service.py::test_http_results_match_in_process_server` and `tests/test_http_cli.py` (`tools/list` equals `tests/tool_contract.py`) |
| A18-15 log privacy | `tests/test_preset_writes.py::test_logs_carry_no_preset_names_or_objects` |
| Registry and coverage | `tests/tool_contract.py` (three new entries), `tests/test_tool_contract.py`, `tests/test_coverage.py`, `tests/test_readme.py` |

Firmware facts that shaped the behavior (pinned source review, not observed on
hardware): the playlist save runs after `loadPlaylist` but before the playlist advances,
so a finite `repeat` and shuffle are stored unchanged and are accepted (readback checks
them); a playlist that is already running could be stored instead, so the playlist route
is refused while one runs; a state write without a name is stored as `Preset <id>`.

### Correction round 1 (review of `01d0c81`)

| Finding | Fix | Evidence |
| --- | --- | --- |
| M-1 restore pruned its own source at the retention limit | Source `backup_id` protected from pruning for the operation (`OperationContext.protected_backups` passed to `SnapshotStore.backup_preset`) | `tests/test_restore.py::test_restore_at_the_retention_limit_keeps_its_source_snapshot` |
| S1 finite `repeat` and shuffle wrongly refused | Accepted; semantic readback compares `repeat`, `r`, `ps` order | `tests/test_restore.py::test_finite_repeat_and_shuffle_restore_and_verify_semantically`, `::test_shuffled_member_order_in_readback_is_a_mismatch` |
| S1 nested-playlist hazard | Playlist route refused with `PRESET_CONFLICT` while `state.pl` > 0, at planning and after the snapshot | `tests/test_restore.py::test_running_playlist_blocks_the_playlist_route_before_any_write`, `::test_playlist_started_after_the_snapshot_is_a_conflict` |
| S2 `transition` above 655 wraps in the firmware | Bounded to 0-655 tenths | `tests/test_preset_writes.py::test_control_unknown_and_malformed_state_is_refused_by_the_schema`, `::test_state_transition_and_blending_style_upper_bounds_are_accepted` |
| S3 member recheck after the snapshot untested | Recheck failure is `PRESET_CONFLICT`, zero POSTs | `tests/test_restore.py::test_playlist_member_changed_after_the_snapshot_is_a_conflict` |
| N1 firmware-removed keys | Comparison test; `v`, `time`, `error`, `bootps` noted as unreachable | `tests/test_preset_writes.py::test_firmware_removed_keys_are_excluded_from_the_expected_entry` |
| N2 interference | Test in the new files | `tests/test_restore.py::test_unrelated_entry_changed_during_the_write_is_reported_as_interference` |
| N3 fake stores `r` as the firmware's integer | `tests/preset_support.py` | covered by the S1 tests |
| N5 `bs` | Bounded to 0-31 (firmware mask `0x1F`) | schema rejection and upper-bound tests above |
| N6 referencing playlists on overwrite | Warning names them | `tests/test_restore.py::test_overwriting_a_playlist_member_names_the_referencing_playlists` |

Hardware: not run. A hardware check of both routes on the shared WLED 16 controller
needs its own human authorization naming the controller and a captured, restorable
baseline (DEC-021 "Hardware"). Until then the hardware outcome is pending.

### Commands and results

Local run on Windows (2026-11-07, branch `stage2/issue-18-preset-writes`, after correction round 1); the exact
candidate commit and the Linux CI run are recorded in the pull request description.

| Command | Result |
| --- | --- |
| `uv run --frozen pytest` | 1286 passed, 18 skipped; 6 failed and 5 errors in `tests/test_inventory_client.py` and `tests/test_hw_http_probe.py`, the same Windows-only failures as on `main` |
| `uv run --frozen pytest tests/test_preset_writes.py tests/test_restore.py` | 104 passed |
| `uv run --frozen ruff check` / `ruff format --check` (CI path list) | pass |
| `uv run --frozen mypy` (strict) | no issues in 28 source files |
| `uv run --frozen python scripts/check_traceability.py` | pass |
| `uv run --frozen python scripts/check_coverage.py` | pass (43 % of the planned scope, 34 % overall) |
| `python scripts/sync_agents.py --check`, `scripts/check_agent_setup.py`, `scripts/check_lock.py`, `scripts/check_private_identifiers.py` | pass |
| `uv run --frozen python scripts/check_distribution.py` | fails locally only at the uvx stdio handshake (checkout path contains a space), as on `main`; Linux CI is the reference |
