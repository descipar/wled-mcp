# Issue #29 validation: static SVG layout preview

Evidence for [#29](https://github.com/descipar/wled-mcp/issues/29) (acceptance scenario S3-T03,
requirements S3-PREVIEW-01 and S3-PREVIEW-02); contract in
[contract/layout-preview.md](../contract/layout-preview.md), decisions in
[ISSUE-29-DEC-001](../decisions/issue-29.md).

**All evidence is mock and fixture evidence.** The pure renderer is tested with synthetic models
only; the tool is tested against the GET-only mock router of `tests/state_catalog_support.py`
(any other method fails the request, so every test also shows that nothing was written) and
against the loopback fake of `tests/acceptance_support.py` on `127.0.0.1`; zone files use pytest
`tmp_path`. No LAN device, no real data directory and no hardware was used. There is **no claim
about physical colour, real controllers or firmware animation**.

## Scenario to test map

| Scenario | Evidence |
| --- | --- |
| Exact output does not drift | `tests/test_layout_preview.py` `test_one_golden_svg_catches_accidental_output_drift` (one golden SVG, a three-segment 60-LED model) |
| Element/attribute allowlist, one URL-shaped string, no script/style/image/animation | `check_safe` in `tests/test_layout_preview.py`, applied by every render test and by `test_every_output_is_script_free_namespaced_and_parseable` (parse with the standard library) |
| Sparse IDs, unsorted input, adjacent segments, exclusive ends, scale text | `test_sparse_ids_unsorted_input_and_exclusive_ends_are_labelled`, `test_the_scale_is_stated_for_small_and_large_strips`, `test_the_axis_has_a_bounded_number_of_labelled_round_ticks` |
| Gaps at start, middle and end; empty layout; overlaps | `test_gaps_at_the_start_middle_and_end_and_for_an_empty_layout`, `test_overlaps_are_reported_and_marked_in_text`; tool level `test_sparse_ids_gaps_and_overlaps_of_the_observed_layout_are_reported` |
| Large strips and bounds | `test_a_large_strip_with_many_lanes_and_samples_stays_bounded` (100,000 LEDs, 64 lanes, run budget, no per-LED element, under 48 KiB), `test_the_worst_case_names_on_a_small_strip_still_fit_the_cap`, `test_more_than_the_lane_limit_reports_omitted_segments`, `test_colour_rectangles_are_budgeted_across_all_lanes`; `test_an_output_over_the_size_cap_fails_safely_instead_of_truncating` (`INVALID_RESPONSE`) |
| Escaped labels and hostile strings | `test_hostile_names_never_become_markup_and_are_truncated` (markup injection, attribute breakout, entities, `]]>`, control characters, bidirectional controls, surrogate and non-character code points, 10 kB strings), `test_the_text_sanitiser_collapses_drops_and_truncates`, `test_a_hostile_device_name_is_sanitised_in_the_title_and_header`, `test_a_hostile_live_colour_cannot_reach_an_attribute` |
| Colour approximations, never an effect claim | `test_rgb_is_used_as_is_and_rgbw_adds_white_with_a_clamp_and_a_label`, `test_cct_only_segments_are_neutral_grey_with_the_value_and_a_flag`, `test_an_off_segment_is_outline_only_and_brightness_is_only_an_opacity_with_a_floor`, `test_missing_colours_are_neutral_with_a_note_and_never_claim_a_simulation` |
| Missing and unsupported geometry | `test_an_unknown_led_count_is_labelled_and_scaled_to_the_highest_end`, `test_segments_beyond_the_led_count_are_clipped_and_marked_never_invented`, `test_zero_length_segments_are_omitted_and_an_empty_layout_has_a_scale`; tool level `test_a_matrix_device_is_refused_and_nothing_is_drawn` (two matrix shapes, observed and proposed), `test_an_unknown_led_count_is_drawn_with_a_label_and_a_limit` |
| Invalid plans: no SVG, no write | `test_an_invalid_proposal_is_the_planner_error_envelope_with_no_svg` (stop beyond count, duplicate IDs, overlap, new ID without colours, ID beyond the maximum), `test_the_planner_limits_unknown_counts_and_maximum_segments`, `test_option_combinations_that_do_not_apply_are_rejected_before_any_read` |
| Observed versus proposed, source label | `test_the_observed_preview_reads_state_and_info_only_and_has_the_documented_shape`, `test_a_valid_proposal_is_validated_by_the_planner_and_never_written`, `test_an_unchanged_segment_is_marked_unchanged`, `test_a_proposed_layout_marks_changes_removals_and_its_basis`, `test_effect_and_palette_names_are_accepted_but_dropped_with_a_warning` |
| Zone overlay (#27) | `test_a_zone_is_overlaid_by_id_or_name_with_reversed_as_text_only`, `test_an_ambiguous_zone_name_lists_candidates_and_a_missing_zone_is_refused`, `test_a_zone_without_a_part_for_the_device_is_refused_before_any_device_read`, `test_a_zone_with_a_stale_led_count_is_not_drawn`, renderer `test_a_zone_overlay_draws_bands_and_a_stale_zone_is_not_drawn` |
| Live samples (#150), unavailable endpoint | renderer tests for step 1, step 3, merged runs and the unavailable fallback; tool level `test_live_samples_are_read_last_and_colour_the_lanes`, `test_a_downsampled_live_read_says_that_the_unsampled_leds_are_unknown`, `test_a_missing_live_endpoint_keeps_the_preview_with_state_colours` (404 and 501), `test_other_live_failures_keep_the_existing_safe_error_envelope`, `test_an_offline_device_gives_the_unreachable_envelope_without_a_drawing` |
| Read-only, restrictions, no private data | `test_the_adapter_holds_no_write_path` (no write function or `dry_run` field), `test_the_tool_is_served_in_a_read_only_profile_and_for_a_read_capped_device`, `test_the_output_contains_none_of_the_devices_private_identifiers`; the registry-driven tests of `tests/test_access_profiles.py` (`READ_CALLS`, read tools send no POST, read-capped device) and `tests/test_tool_contract.py` |
| Identical delivery on stdio and HTTP | `tests/test_acceptance_parity.py` cases `preview_observed`, `preview_proposed`, `preview_unknown_device` (installed console over stdio and loopback Streamable HTTP, zero POST, identical envelopes after masking the correlation ID and capture time) and `test_the_layout_preview_svg_is_identical_plain_data_on_both_transports` |
| Determinism | `test_two_renders_of_one_model_are_byte_identical` |

## Limits

- Mock and fixture evidence only. No hardware check was run, none was authorized or is required:
  the preview adds no device endpoint beyond `/json/state`, `/json/info` and optionally
  `/json/live`, which earlier records exercised ([#150](issue-150.md), [#30](issue-30.md)).
- The SVG was checked structurally and by one golden string; it was not viewed in every browser or
  viewer, and the picture is not a statement about how the LEDs look.
- Colours are approximations of the first colour slot or of sampled live colours; effects,
  palettes and animation are not simulated. 2D and matrix devices are refused, not drawn.
- Carried, not created: an optional 2D preview over declared matrix geometry (candidate milestone
  Backlog).
