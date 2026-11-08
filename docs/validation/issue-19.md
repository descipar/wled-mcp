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
| AC-19-03 refactor parity: the existing patch, layout, store, import and export suites pass unchanged; `parse_matrix` is the moved function; the write side still uses `info.leds.seglc` only; `CAP_*` stay importable from readmodels | full `pytest` run (no existing test edited except the two coverage fixtures below); `tests/test_segment_capabilities.py::test_bundle_module_uses_the_moved_parse_matrix`, `::test_write_side_lookup_still_uses_info_seglc_only`, `::test_patch_colors_without_seglc_still_refused_despite_seg_lc`, `::test_cap_constants_stay_importable_from_readmodels`; bundle 2D/CCT rules in `tests/test_bundles.py` unchanged |
| WLED 16 fake: omitted Y kept, X/Y clamped to the matrix, trailing strip bounds, capability recomputed after a move, option keys with firmware clamps, stage-1 default shape | `tests/test_segment_capabilities.py::test_fake_default_keeps_the_stage_1_shape`, `::test_fake_matrix_keeps_omitted_y_and_clamps_to_the_matrix`, `::test_fake_matrix_trailing_strip_and_capability_recompute`, `::test_fake_v16_applies_option_keys_with_firmware_clamps` |
| Coverage rows W-SEG-14 to W-SEG-22 partial (read only), W-INFO-02 keys; planned-row checks no longer depend on the live W-SEG-14 status | `tests/test_coverage.py` (C4/C5 fixtures set `Status="planned"` explicitly), `scripts/check_coverage.py` |

Not covered by the first pull request: every write-side scenario (AC-19-04 to AC-19-16)
and transport parity of new input fields (AC-19-15); they belong to the second pull
request.
