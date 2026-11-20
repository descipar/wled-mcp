# Issue #19 validation evidence

Evidence for [issue #19](https://github.com/descipar/wled-mcp/issues/19). Contract:
[contract/segments.md](../contract/segments.md). Requirements: S2-SEG-01, S2-SEG-02 and
S2-T05 of [STAGE-2.md](../STAGE-2.md); scenarios AC-19-01 to AC-19-18 of
[ISSUE-19-DEC-003](../decisions/issue-19.md#issue-19-dec-003--technical-defaults-for-the-capability-model-and-segment-fields).

Hardware honesty (AC-19-18): the only hardware evidence in this project is one RGB-only 1D
controller on WLED 16.0.1. Nothing below is a CCT, RGBW-new-range, 2D or overlap hardware claim;
those capabilities stay at the expected tier of DEC-020 (source-reviewed and mock-tested).

## First pull request: capability model and read side

Mock transport and pure functions only. The stateful fake `tests/layout_support.py` gained opt-in
WLED 16 shapes (`v16`, `matrix`, `buses`) from the v16.0.1 source pin; its default stays the stage-1
shape. All tests are in `tests/test_segment_capabilities.py` unless named otherwise.

| Scenario | Evidence |
| --- | --- |
| AC-19-01 per-segment evidence chain `state_lc` -> `info_seglc` -> `null`; RGB-only, RGBW, white-only, CCT bits; 0.15.1 info without `seg[].lc`; malformed `lc`; unknown never false; uniform bits | `test_state_lc_is_the_first_evidence_source`, `test_0_15_shape_without_seg_lc_falls_back_to_aligned_seglc`, `test_no_per_segment_evidence_is_unknown_not_false` and four more |
| AC-19-01 `capabilities.matrix` from `info.leds.matrix`, malformed `null` with a warning, 1D without a warning | `test_matrix_is_parsed_strictly`, `test_get_state_reports_v16_matrix_fields` and two more |
| AC-19-02 new segment fields from their wire keys, `null` when absent or malformed (with a warning), additive; state example equals the read model | `test_new_segment_fields_come_from_their_wire_keys`, `test_state_example_matches_the_read_model` (examples/contracts/state.json) and three more |
| AC-19-03 refactor parity: existing patch, layout, store, import and export suites pass unchanged; write side still uses `info.leds.seglc` only; `CAP_*` importable from readmodels | full `pytest` run; `test_bundle_module_uses_the_moved_parse_matrix`, `test_cap_constants_stay_importable_from_readmodels`; `tests/test_bundles.py` unchanged |
| WLED 16 fake: omitted Y kept, X/Y clamped, trailing strip bounds, capability recomputed after a move, option keys with firmware clamps | four `test_fake_*` tests |
| Coverage rows W-SEG-14 to W-SEG-22 partial (read only), W-INFO-02 | `tests/test_coverage.py`, `scripts/check_coverage.py` |

Not covered by the first pull request: every write-side scenario (AC-19-04 to AC-19-16) and
transport parity of new input fields (AC-19-15); they belong to the second pull request.

## Second pull request: segment writes

Mock transport and pure functions only. The fake now follows the v16.0.1 source more closely (name
cleared on the requested X bounds before clamping, `si`/`set` constrained to 0-3, `cct` applied by
every build, trailing-strip rows from `startY`/`stopY`); its own tests pin that. Carried review items
of PR #108 were done first: the write-side CCT lookup moved from `info.leds.seglc` to the
`seg[].lc` chain (pin flipped in `test_write_side_uses_the_seg_lc_chain_without_seglc`), surviving
mutants were killed by new tests, and examples/contracts/state.json is v16-shaped.

| Scenario | Evidence |
| --- | --- |
| AC-19-04 `cct` on a CCT segment: payload `{"id": N, "cct": X}`, readback equal, `applied/verified`; dry run identical with zero POSTs | `test_cct_patch_on_a_cct_segment_is_verified_and_the_dry_run_is_identical` |
| AC-19-05 `cct` on an RGB-only segment, aggregate-only, missing or misaligned evidence, or a moved range without uniform evidence: `UNSUPPORTED_CAPABILITY`, zero POSTs, whole request refused | `test_cct_without_evidence_is_unsupported_before_any_post` (5 cases x dry/live) |
| AC-19-06 white handling: existing RGBW unchanged, white-only takes `[0, 0, 0, W]`, RGB+CCT takes 3 channels, moved or new range takes 4 only under the uniform rule | `test_white_only_range_takes_four_channels_with_rgb_zero`, `test_moved_range_takes_four_channels_only_under_the_uniform_rule`; `tests/test_layouts.py::test_T06_rgbw_rules` (deliberately updated) and two more |
| AC-19-07 2D bounds on a matrix, omitted rows preserved, rows-only change keeps the name, any 2D field on a 1D device is `UNSUPPORTED_CAPABILITY` | `test_matrix_x_patch_keeps_rows_and_resends_the_name`, `test_2d_fields_on_a_1d_device_are_unsupported` and two more |
| AC-19-08 matrix gap closed (`stop` > width is `VALIDATION_ERROR` before any POST), rectangle overlap, explicit rows for a new replace segment, trailing strip preserved but never created or moved | `test_matrix_patch_bounds_are_refused_before_any_post`, `test_matrix_replace_uses_rectangles_and_preserves_the_trailing_strip` and two more |
| AC-19-09 orientation only on a matrix, verified | `test_matrix_orientation_patch_is_verified` |
| AC-19-10 option bounds before any write, field presence per segment and for a new ID on every active segment, readback verified | `test_option_bounds_are_schema_errors`, `test_option_without_its_wire_key_is_unsupported` (10 options x both tools) and three more |
| AC-19-11 overlap rejected by default in both tools, `allow_overlap` permits it, plan lists pairs and render order, dry run identical; `blend_mode` where reported | `test_patch_overlap_needs_allow_overlap_and_the_plan_lists_pairs`, `test_replace_overlap_with_blend_mode_and_render_order`; stage-1 rejection tests unchanged |
| AC-19-12 replace create defaults where the readback proves the field; `inherited_unexposed_state` lists only unreset keys | `test_replace_create_sends_the_wled_16_defaults`, `test_reused_slot_on_a_stage_1_device_lists_only_unreported_keys`; `tests/test_layouts.py::test_T05_fixture_case_exact_post_sequence_and_final_layout` (updated: `cct` 127 on create), regenerated examples |
| AC-19-13 a patch omitting new fields sends none; a geometry change resends the name, rows and orientation untouched | `test_omitted_new_fields_are_never_sent` |
| AC-19-14 uncertain and partial writes keep the stage-1 mappings without replay | `test_uncertain_cct_write_is_unknown_and_not_replayed`, `test_uncertain_matrix_replace_step_stops_the_sequence` and one more |
| AC-19-15 transport parity: identical additive schemas, T06 parity for every new field, tool list unchanged, retained 0.1.0 contract compatible without a migration note | `tests/test_layouts.py::test_new_input_fields_are_additive_and_identical_in_both_tools`, `tests/test_http_service.py::test_http_results_match_in_process_server`, `tests/test_upgrade_compat.py` |
| AC-19-16 `wled_store_preset` takes the wire keys with the same bounds and rules; overlap stays rejected | `test_store_accepts_wled_16_keys_with_evidence_and_stores_them_verbatim`, `test_store_refuses_wled_16_keys_without_evidence` (8 cases x dry/live), `test_store_has_no_allow_overlap` |
| AC-19-17 no version-based refusal below 16.0.0; no #19 rule reads the tier | `test_no_issue_19_rule_reads_the_firmware_tier` |
| AC-19-18 hardware honesty | This file: no CCT, RGBW-new-range, 2D or overlap hardware claim |
| Coverage W-SEG-13 to W-SEG-22 supported | docs/WLED-COVERAGE.md, `scripts/check_coverage.py --update` (57 % of the planned scope, 46 % overall) |

Stage-1 hardware evidence: the replace runs on the RGB-only test controller predate the extended
create payload. The 11 keys a create step may now add (`cct`, `c1`-`c3`, `o1`-`o3`, `si`, `set`,
`m12`, `bm`) rest on mock and source evidence only.

Review round 1 (b219017): the store no longer moves an existing trailing strip, the patch tool
accepts unchanged bounds on a trailing strip, and eight tests were added for surviving mutants
(overlap swap, rows-change counts as moved for CCT, unknown rows block a geometry change, all
overlapping pairs listed, store option on a new ID, and others).

Not covered: any hardware run. A read-only probe of the RGB-only test controller could confirm the
WLED 16 option keys and `seg[].lc` on real firmware; it needs separate authorization and is not
required by the issue.
