# Issue #27 validation: named physical lighting zones

Evidence for [#27](https://github.com/descipar/wled-mcp/issues/27); contract in
[contract/zones.md](../contract/zones.md), decisions in
[ISSUE-27-DEC-001](../decisions/issue-27.md).

**All evidence is mock evidence.** Tests use the synthetic fleet of `tests/scene_support.py` (stateful
`FakeWLED` devices) and the loopback fake of `tests/acceptance_support.py`; stores use pytest
`tmp_path`. No LAN device, real data directory or hardware was used; no claim about real controllers.

## Scenario to test map

Tests are in `tests/test_zones.py` and `tests/test_zone_tools.py` unless named otherwise.

| Scenario | Evidence |
| --- | --- |
| Reversed ordering | `test_reversed_ordering_lists_the_high_range_first_in_descending_segment_order`; `test_apply_changes_only_the_segments_inside_the_zone` |
| Multiple spans and devices | `test_several_spans_and_devices_give_one_target_per_device_in_logical_order`, `test_a_zone_over_two_devices_writes_each_device_once_and_verifies` and one more |
| Layout change between preview and write: nothing sent | `test_a_layout_change_between_preview_and_write_sends_nothing`, `test_a_resolution_that_still_works_but_differs_also_fails_the_write` |
| Explicit layout change makes the zone resolve; the zone tool never writes geometry | `test_an_explicit_layout_change_makes_the_zone_resolve_and_the_zone_never_writes_it` |
| Zone crossing an unsupported segment boundary | `test_a_zone_that_does_not_tile_onto_inner_segments_needs_a_layout_change` (six shapes), `test_uncovered_leds_are_refused_not_lit` |
| Missing device | `test_a_missing_device_blocks_strict_and_is_skipped_in_best_effort` |
| Ambiguous name | `test_an_ambiguous_name_is_refused_with_candidates_and_the_id_still_works` and two more |
| Stale topology | `test_a_stale_led_count_is_refused_per_device_with_nothing_sent`, `test_the_segment_hint_must_match_but_does_not_replace_the_range` |
| Duplicate and overlapping mappings | parser tests, `test_document_warnings_name_name_collisions_and_duplicate_mappings`, `test_partial_overlap_across_zones_is_information_not_an_error` and one more |
| Profile and device restrictions on resolved targets, both transports | `tests/test_zone_parity.py` (installed console on stdio and loopback HTTP, `control` profile, `desk` capped at `read`: identical envelopes, `ACCESS_DENIED` before any read, plan still previews, `best_effort` writes only the permitted device); `test_a_read_capped_device_of_a_zone_is_refused_before_any_read_but_still_previews`; `tests/test_access_profiles.py` |
| Master and geometry fields refused | `test_geometry_and_unknown_fields_are_refused_before_any_io`, `test_the_request_schema_has_no_master_state_and_needs_one_field_object` |
| `dry_run` equals the plan, no write | `test_dry_run_returns_exactly_the_plan_and_sends_no_write` |
| Uncertain write never retried | `test_an_unverified_write_is_unknown_and_never_retried` (one POST, `WRITE_OUTCOME_UNKNOWN`) |
| Strict parser | `tests/test_zones.py` (versions, unknown keys incl. `start_y`, bounds, strict JSON, size) |
| Scenes unchanged | existing scene tests pass unchanged (`bind` defaults to `None`) |

## Limits

Mock evidence only; no hardware check was run (none authorized). Zone targets in scenes and groups, a
zone save or delete tool and a layout proposal are not delivered (carried).
