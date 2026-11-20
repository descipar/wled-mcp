# Issue #29 validation: static SVG layout preview

Evidence for [#29](https://github.com/descipar/wled-mcp/issues/29) (acceptance scenario S3-T03,
requirements S3-PREVIEW-01 and S3-PREVIEW-02); contract in
[contract/layout-preview.md](../contract/layout-preview.md), decisions in
[ISSUE-29-DEC-001](../decisions/issue-29.md).

**All evidence is mock and fixture evidence.** The pure renderer is tested with synthetic models; the
tool runs against the GET-only mock router of `tests/state_catalog_support.py` (any other method fails,
so every test also shows nothing was written) and the loopback fake of `tests/acceptance_support.py`;
zone files use pytest `tmp_path`. No LAN device or hardware was used and there is **no claim about
physical colour, real controllers or firmware animation**.

## Scenario to test map

All tests are in `tests/test_layout_preview.py` unless named otherwise.

| Scenario | Evidence |
| --- | --- |
| Exact output does not drift | `test_one_golden_svg_catches_accidental_output_drift` |
| Element/attribute allowlist, no script/style/image/animation | `check_safe`, applied by every render test and `test_every_output_is_script_free_namespaced_and_parseable` |
| Sparse IDs, unsorted input, adjacent segments, exclusive ends, scale text | `test_sparse_ids_unsorted_input_and_exclusive_ends_are_labelled`, `test_the_scale_is_stated_for_small_and_large_strips` and one more |
| Gaps at start, middle and end; empty layout; overlaps | `test_gaps_at_the_start_middle_and_end_and_for_an_empty_layout`, `test_overlaps_are_reported_and_marked_in_text`; tool level `test_sparse_ids_gaps_and_overlaps_of_the_observed_layout_are_reported` |
| Large strips and bounds | `test_a_large_strip_with_many_lanes_and_samples_stays_bounded` (100,000 LEDs, 64 lanes, under 48 KiB), `test_more_than_the_lane_limit_reports_omitted_segments`, `test_an_output_over_the_size_cap_fails_safely_instead_of_truncating` (`INVALID_RESPONSE`) and two more |
| Escaped labels and hostile strings | `test_hostile_names_never_become_markup_and_are_truncated`, `test_the_text_sanitiser_collapses_drops_and_truncates`, `test_a_hostile_live_colour_cannot_reach_an_attribute` and one more |
| Colour approximations, never an effect claim | `test_rgb_is_used_as_is_and_rgbw_adds_white_with_a_clamp_and_a_label`, `test_missing_colours_are_neutral_with_a_note_and_never_claim_a_simulation` and two more |
| Missing and unsupported geometry | `test_an_unknown_led_count_is_labelled_and_scaled_to_the_highest_end`, `test_segments_beyond_the_led_count_are_clipped_and_marked_never_invented`; tool level `test_a_matrix_device_is_refused_and_nothing_is_drawn` |
| Invalid plans: no SVG, no write | `test_an_invalid_proposal_is_the_planner_error_envelope_with_no_svg` and two more |
| Observed versus proposed, source label | `test_the_observed_preview_reads_state_and_info_only_and_has_the_documented_shape`, `test_a_valid_proposal_is_validated_by_the_planner_and_never_written` and three more |
| Zone overlay (#27) | `test_a_zone_is_overlaid_by_id_or_name_with_reversed_as_text_only`, `test_a_zone_without_a_part_for_the_device_is_refused_before_any_device_read` and three more |
| Live samples (#150), unavailable endpoint | `test_live_samples_are_read_last_and_colour_the_lanes`, `test_a_missing_live_endpoint_keeps_the_preview_with_state_colours` (404 and 501), `test_an_offline_device_gives_the_unreachable_envelope_without_a_drawing` and three more |
| Read-only, restrictions, no private data | `test_the_adapter_holds_no_write_path`, `test_the_tool_is_served_in_a_read_only_profile_and_for_a_read_capped_device`, `test_the_output_contains_none_of_the_devices_private_identifiers`; `tests/test_access_profiles.py` and `tests/test_tool_contract.py` |
| Identical delivery on stdio and HTTP | `tests/test_acceptance_parity.py` cases `preview_observed`, `preview_proposed`, `preview_unknown_device` (zero POST, identical envelopes after masking) and `test_the_layout_preview_svg_is_identical_plain_data_on_both_transports` |
| Determinism | `test_two_renders_of_one_model_are_byte_identical` |

## Limits

- Mock and fixture evidence only. No hardware check was run, authorized or required: the preview adds no
  endpoint beyond `/json/state`, `/json/info` and optionally `/json/live`, exercised by earlier records
  ([#150](issue-150.md), [#30](issue-30.md)).
- The SVG was checked structurally and by one golden string; it was not viewed in every browser, and the
  picture is not a statement about how the LEDs look.
- Colours approximate the first colour slot or sampled live colours; effects, palettes and animation are
  not simulated. 2D and matrix devices are refused, not drawn.
- Carried: an optional 2D preview over declared matrix geometry (candidate Backlog).
