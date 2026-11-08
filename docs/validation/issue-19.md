# Issue #19 validation evidence

Evidence for [issue #19](https://github.com/descipar/wled-mcp/issues/19). Contract:
[contract/segments.md](../contract/segments.md). Requirements: S2-SEG-01, S2-SEG-02 and
S2-T05 of [STAGE-2.md](../STAGE-2.md); scenarios AC-19-01 to AC-19-18 of
[ISSUE-19-DEC-003](../decisions/issue-19.md#issue-19-dec-003--technical-defaults-for-the-capability-model-and-segment-fields).

Hardware honesty (AC-19-18): the only hardware evidence in this project is one RGB-only
1D controller on WLED 16.0.1. Nothing below is a CCT, RGBW-new-range, 2D or overlap
hardware claim; those capabilities stay at the expected tier of DEC-020 (source-reviewed
and mock-tested).

## First pull request: capability model and read side

Mock transport and pure functions only; no LAN, device or hardware access. The stateful
fake `tests/layout_support.py` gained opt-in WLED 16 shapes (`v16`, `matrix`, `buses`)
from the v16.0.1 source pin; its default stays the stage-1 shape, so existing tests run
unchanged.

| Scenario | Evidence |
| --- | --- |
| AC-19-01 per-segment evidence chain `state_lc` -> `info_seglc` -> `null`; RGB-only, RGBW, white-only and CCT (`lc` 4-7) bits; 0.15.1-shaped info without `seg[].lc`; malformed `lc`; unknown never false; uniform bits | `tests/test_segment_capabilities.py::test_state_lc_is_the_first_evidence_source`, `::test_0_15_shape_without_seg_lc_falls_back_to_aligned_seglc`, `::test_mixed_sources_are_reported_per_segment`, `::test_malformed_seg_lc_is_ignored_with_a_warning`, `::test_no_per_segment_evidence_is_unknown_not_false`, `::test_uniform_bits_need_every_segment_equal_to_the_aggregate`, `::test_aggregate_cct_is_none_when_unreported` |
| AC-19-01 `capabilities.matrix` from `info.leds.matrix`, malformed values `null` with a warning, 1D without a warning; 2D matrix plus trailing strip over `wled_get_state` | `tests/test_segment_capabilities.py::test_matrix_is_parsed_strictly`, `::test_one_d_device_reports_no_matrix_without_a_warning`, `::test_get_state_reports_v16_matrix_fields`, `::test_get_state_on_a_1d_v16_device_has_no_2d_fields` |
| AC-19-02 new segment fields from their wire keys, `null` when absent, `null` plus a warning when malformed; additive after `name`; the state example equals the read model's output | `tests/test_segment_capabilities.py::test_new_segment_fields_come_from_their_wire_keys`, `::test_absent_new_fields_are_null`, `::test_malformed_new_field_is_null_with_a_warning`, `::test_new_fields_are_additive_to_the_stage_1_segment_view`, `::test_state_example_matches_the_read_model` (examples/contracts/state.json) |
| AC-19-03 refactor parity: the existing patch, layout, store, import and export suites pass unchanged; `parse_matrix` is the moved function; the write side still uses `info.leds.seglc` only; `CAP_*` stay importable from readmodels | full `pytest` run (no existing test edited except the two coverage fixtures below); `tests/test_segment_capabilities.py::test_bundle_module_uses_the_moved_parse_matrix`, `::test_write_side_lookup_still_uses_info_seglc_only` and `::test_patch_colors_without_seglc_still_refused_despite_seg_lc` (both renamed and flipped by the second pull request, see below), `::test_cap_constants_stay_importable_from_readmodels`; bundle 2D/CCT rules in `tests/test_bundles.py` unchanged |
| WLED 16 fake: omitted Y kept, X/Y clamped to the matrix, trailing strip bounds, capability recomputed after a move, option keys with firmware clamps, stage-1 default shape | `tests/test_segment_capabilities.py::test_fake_default_keeps_the_stage_1_shape`, `::test_fake_matrix_keeps_omitted_y_and_clamps_to_the_matrix`, `::test_fake_matrix_trailing_strip_and_capability_recompute`, `::test_fake_v16_applies_option_keys_with_firmware_clamps` |
| Coverage rows W-SEG-14 to W-SEG-22 partial (read only), W-INFO-02 keys; planned-row checks no longer depend on the live W-SEG-14 status | `tests/test_coverage.py` (C4/C5 fixtures set `Status="planned"` explicitly), `scripts/check_coverage.py` |

Not covered by the first pull request: every write-side scenario (AC-19-04 to AC-19-16)
and transport parity of new input fields (AC-19-15); they belong to the second pull
request.

## Second pull request: segment writes

Mock transport and pure functions only; no LAN, device or hardware access. The stateful
fake now follows the v16.0.1 source more closely (name cleared on the requested X bounds
before clamping and kept on a rows-only change, `si`/`set` constrained to 0-3, `cct`
applied by every build, trailing-strip rows from `startY`/`stopY`); the fake's own tests
pin that behavior. Unless a row names another file, tests are in
`tests/test_segment_capabilities.py`.

Carried review items of the first pull request (PR #108 merge comment), done before the
write changes: `tests/test_segment_capabilities.py::test_replace_colors_without_seglc_still_refused_despite_seg_lc` pinned
the layout planner first (commit 1), then both pins were flipped with the switch into
`::test_write_side_uses_the_seg_lc_chain_without_seglc`; surviving mutants are killed by
`::test_partial_per_segment_evidence_is_not_reported_as_complete`,
`::test_color_trimming_keeps_the_stage_1_seglc_path_not_the_state_lc_chain`,
`::test_stage_1_seglc_lookup_is_kept_for_reference` (boolean `seglc`) and
`tests/test_bundles.py::test_cct_entry_on_a_cct_target_has_no_cct_warning`; the fake by
`::test_fake_matrix_name_follows_the_requested_x_bounds_before_clamping`,
`::test_fake_trailing_strip_rows_follow_start_y_and_stop_y` and
`::test_fake_v16_applies_option_keys_with_firmware_clamps`; examples/contracts/state.json
is v16-shaped and still equals the read model (`::test_state_example_matches_the_read_model`).

| Scenario | Evidence |
| --- | --- |
| AC-19-04 `cct` on a CCT segment: payload `{"id": N, "cct": X}`, readback equal, `applied/verified`; the dry run has the identical payload, zero POSTs and no files | `::test_cct_patch_on_a_cct_segment_is_verified_and_the_dry_run_is_identical`, `::test_cct_on_a_moved_range_uses_the_uniform_rule` |
| AC-19-05 `cct` on an RGB-only segment, with aggregate-only, missing or misaligned evidence, or on a moved range without uniform evidence: `UNSUPPORTED_CAPABILITY`, zero POSTs, dry run and live, whole request refused | `::test_cct_without_evidence_is_unsupported_before_any_post` (5 cases x dry/live) |
| AC-19-06 white handling: existing RGBW unchanged (stage-1 tests), white-only takes `[0, 0, 0, W]`, RGB+CCT takes 3 channels, a moved or new range takes 4 channels only under the uniform rule, never padded or trimmed | `::test_white_only_range_takes_four_channels_with_rgb_zero`, `::test_rgb_cct_range_takes_three_channels`, `::test_moved_range_takes_four_channels_only_under_the_uniform_rule`, `::test_new_range_with_four_channels_on_a_uniform_rgbw_device_is_verified`; `tests/test_layouts.py::test_T06_rgbw_rules` (deliberately updated: uniform RGBW now allows 4 channels on a moved or new range), `::test_T06_rgbw_new_or_moved_range_without_uniform_evidence`, `::test_T06_new_range_capability_evidence` (unchanged) |
| AC-19-07 2D bounds on a matrix: X columns and rows, omitted rows preserved, a rows-only change keeps the name, any 2D field on a 1D device is `UNSUPPORTED_CAPABILITY` | `::test_matrix_x_patch_keeps_rows_and_resends_the_name`, `::test_matrix_rows_only_patch_sends_no_name`, `::test_matrix_patch_bounds_are_refused_before_any_post`, `::test_2d_fields_on_a_1d_device_are_unsupported` |
| AC-19-08 matrix gap closed (`stop` > width is `VALIDATION_ERROR` before any POST), rectangle overlap, explicit rows for a new replace segment, trailing strip preserved but never created or moved | `::test_matrix_patch_bounds_are_refused_before_any_post`, `::test_matrix_replace_uses_rectangles_and_preserves_the_trailing_strip`, `::test_matrix_replace_refusals_send_nothing`, `::test_matrix_create_needs_rows_and_resets_orientation` |
| AC-19-09 orientation only on a matrix, verified | `::test_matrix_orientation_patch_is_verified`, `::test_2d_fields_on_a_1d_device_are_unsupported` |
| AC-19-10 option bounds before any write (schema), field presence per segment and for a new ID on every active segment, readback verified | `::test_option_bounds_are_schema_errors`, `::test_every_option_is_sent_and_verified_where_the_readback_carries_it`, `::test_option_without_its_wire_key_is_unsupported` (10 options x both tools), `::test_freeze_needs_the_frz_key_too`, `::test_new_id_option_needs_the_key_on_every_active_segment` |
| AC-19-11 overlap rejected by default in both tools, `allow_overlap` permits it, the plan lists pairs and render order, dry run identical; `blend_mode` where reported | `::test_patch_overlap_needs_allow_overlap_and_the_plan_lists_pairs`, `::test_replace_overlap_with_blend_mode_and_render_order`, `::test_allow_overlap_without_an_overlap_lists_no_pairs`; existing stage-1 rejection tests in `tests/test_patches.py` and `tests/test_layouts.py` unchanged |
| AC-19-12 replace create defaults where the readback proves the field; `inherited_unexposed_state` lists only unreset keys | `::test_replace_create_sends_the_wled_16_defaults`, `::test_reused_slot_legacy_state_is_reset_where_the_fields_are_reported`, `::test_reused_slot_on_a_stage_1_device_lists_only_unreported_keys`, `::test_matrix_create_needs_rows_and_resets_orientation`; `tests/test_layouts.py::test_T05_fixture_case_exact_post_sequence_and_final_layout` (deliberately updated: `cct` 127 on create) and the regenerated examples/contracts/replace.json and errors.json |
| AC-19-13 a patch omitting new fields sends none; a geometry change resends the name and leaves rows and orientation untouched | `::test_omitted_new_fields_are_never_sent`, `::test_matrix_x_patch_keeps_rows_and_resends_the_name` |
| AC-19-14 uncertain and partial writes keep the stage-1 mappings without replay | `::test_uncertain_cct_write_is_unknown_and_not_replayed`, `::test_ignored_option_is_a_mismatch_with_the_stage_1_mapping_and_no_replay`, `::test_uncertain_matrix_replace_step_stops_the_sequence` |
| AC-19-15 transport parity: identical additive schemas, T06 parity for every new field, tool list unchanged, retained 0.1.0 contract compatible without a migration note | `tests/test_layouts.py::test_T06_issue19_fields_share_bounds_across_both_tools_and_the_store`, `::test_new_input_fields_are_additive_and_identical_in_both_tools`; unchanged `tests/test_tool_contract.py`, `tests/test_http_service.py::test_http_results_match_in_process_server` (HTTP and in-process tool schemas equal), `tests/test_upgrade_compat.py::test_served_contract_stays_compatible_with_retained_release` |
| AC-19-16 `wled_store_preset` takes the wire keys with the same bounds and rules; overlap stays rejected | `::test_store_accepts_wled_16_keys_with_evidence_and_stores_them_verbatim`, `::test_store_refuses_wled_16_keys_without_evidence` (8 cases x dry/live), `::test_store_matrix_rectangles_side_by_side_and_the_unchanged_trailing_strip`, `::test_store_has_no_allow_overlap`; `tests/test_preset_writes.py::test_control_unknown_and_malformed_state_is_refused_by_the_schema` (bounds and the excluded `rpt`, `fxdef`, `i`) |
| AC-19-17 no version-based refusal below 16.0.0; no #19 rule reads the tier | `::test_cct_on_0_15_shaped_info_uses_aligned_seglc_without_a_version_gate`, `::test_no_issue_19_rule_reads_the_firmware_tier` |
| AC-19-18 hardware honesty | This file: no CCT, RGBW-new-range, 2D or overlap hardware claim (expected tier of DEC-020) |
| Coverage W-SEG-13 to W-SEG-22 supported, notes on W-SEG-01, -02 and -20 | docs/WLED-COVERAGE.md, `python scripts/check_coverage.py --update` (57 % of the planned scope, 46 % overall) |

Not covered: any hardware run. A read-only probe of the RGB-only test controller could
confirm the WLED 16 option keys and `seg[].lc` on real firmware; it needs a separate
authorization and is not required by the issue.
