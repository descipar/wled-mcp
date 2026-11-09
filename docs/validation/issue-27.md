# Issue #27 validation: named physical lighting zones

Evidence for [#27](https://github.com/descipar/wled-mcp/issues/27); contract in
[contract/zones.md](../contract/zones.md), decisions in
[ISSUE-27-DEC-001](../decisions/issue-27.md).

**All evidence is mock evidence.** Tests use the synthetic fleet of `tests/scene_support.py`
(stateful `FakeWLED` devices) and the loopback fake of `tests/acceptance_support.py` on
`127.0.0.1`; stores use pytest `tmp_path`. No LAN device, no real data directory and no
hardware was used; no claim about real controllers is made.

## Scenario to test map

| Scenario | Evidence |
| --- | --- |
| Reversed ordering | `tests/test_zones.py` `test_reversed_ordering_lists_the_high_range_first_in_descending_segment_order`; `tests/test_zone_tools.py` `test_apply_changes_only_the_segments_inside_the_zone` (high half, only its segments in the POST) |
| Multiple spans and devices | `test_a_span_tiled_by_several_segments...`, `test_several_spans_and_devices_give_one_target_per_device_in_logical_order`, `test_a_zone_over_two_devices_writes_each_device_once_and_verifies` |
| Layout change between preview and write: nothing sent | `test_a_layout_change_between_preview_and_write_sends_nothing`, `test_a_resolution_that_still_works_but_differs_also_fails_the_write` (renumbered segment) |
| Explicit layout change makes the zone resolve; the zone tool never writes geometry | `test_an_explicit_layout_change_makes_the_zone_resolve_and_the_zone_never_writes_it`; POST bodies of the apply contain no `start`/`stop`/master keys |
| Zone crossing an unsupported segment boundary | `test_a_zone_that_does_not_tile_onto_inner_segments_needs_a_layout_change` (six shapes), `test_a_zone_that_does_not_fit_the_live_segments_changes_no_led`, `test_uncovered_leds_are_refused_not_lit` (zero POST, state unchanged) |
| Missing device | `test_a_missing_device_blocks_strict_and_is_skipped_in_best_effort` (no I/O for the device) |
| Ambiguous name | `test_an_ambiguous_name_is_refused_with_candidates_and_the_id_still_works`, `test_a_shared_name_is_ambiguous_with_bounded_candidates...`, `test_an_id_wins_over_another_zones_name_with_a_warning` |
| Stale topology | `test_a_stale_led_count_is_refused_per_device_with_nothing_sent`, `test_the_segment_hint_must_match_but_does_not_replace_the_range` |
| Duplicate and overlapping mappings | parser tests (overlapping spans, device twice), `test_document_warnings_name_name_collisions_and_duplicate_mappings`, `test_partial_overlap_across_zones_is_information_not_an_error`, `test_the_plan_reports_overlapping_zones_and_groups_as_information` |
| Profile and device restrictions on resolved targets, both transports | `tests/test_zone_parity.py` (installed console on stdio and loopback HTTP, `control` profile, `desk` capped at `read`: identical envelopes, `ACCESS_DENIED` before any read, plan still previews, `best_effort` writes only the permitted device); `tests/test_zone_tools.py` `test_a_read_capped_device_of_a_zone_is_refused_before_any_read_but_still_previews`, `test_a_read_only_profile_serves_the_plan_but_not_the_apply`; the registry-driven `tests/test_access_profiles.py` profile tests (stdio and HTTP) cover registration of the three tools |
| Master and geometry fields refused | `test_geometry_and_unknown_fields_are_refused_before_any_io`, `test_the_request_schema_has_no_master_state_and_needs_one_field_object` |
| `dry_run` equals the plan, no write | `test_dry_run_returns_exactly_the_plan_and_sends_no_write` |
| Uncertain write never retried | `test_an_unverified_write_is_unknown_and_never_retried` (lost readback: one POST, `WRITE_OUTCOME_UNKNOWN`) |
| Strict parser | `tests/test_zones.py` (versions, unknown keys incl. `start_y`, bounds, strict JSON, size) |
| Scenes unchanged | the existing scene tests pass unchanged (`bind` defaults to `None`) |

## Limits

Mock evidence only. No hardware check was run (none is authorized). Zone targets in scenes
and groups, a zone save or delete tool and a layout proposal are not delivered (carried).
