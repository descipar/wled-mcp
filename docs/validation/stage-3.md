# Validation: stage 3 features (issues #27 to #30)

## Issue #27 validation: named physical lighting zones

Evidence for [#27](https://github.com/descipar/wled-mcp/issues/27); contract in
[contract/zones.md](../contract/zones.md), decisions in
[ISSUE-27-DEC-001](../decisions/stage-3.md).

**All evidence is mock evidence.** Tests use the synthetic fleet of `tests/scene_support.py` (stateful
`FakeWLED` devices) and the loopback fake of `tests/acceptance_support.py`; stores use pytest
`tmp_path`. No LAN device, real data directory or hardware was used; no claim about real controllers.

### Scenario to test map

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

### Limits

Mock evidence only; no hardware check was run (none authorized). Zone targets in scenes and groups, a
zone save or delete tool and a layout proposal are not delivered (carried).

## Issue #28 validation: temporary signals with conflict-aware restoration

Evidence for [#28](https://github.com/descipar/wled-mcp/issues/28) (acceptance scenario S3-T02,
requirements S3-SIGNAL-01 and S3-SIGNAL-02); contract in [contract/signals.md](../contract/signals.md),
decisions in [ISSUE-28-DEC-001 and -002](../decisions/stage-3.md).

**Status: software evidence complete; live evidence recorded below** (two runs on the one selected
test controller under ISSUE-28-DEC-001, on candidate `0b3e6c688abda967b64212a6449097cd157ef258`;
later commits of the pull request change documentation only).

### Software evidence (mock, fixture and loopback only)

Timing is driven by a controlled clock (`FakeClock`, `tests/signal_support.py`); no test waits in
real time. The device is a stateful mock controller behind `httpx.MockTransport` that applies POST
bodies and can be edited externally, taken offline or made to drop, ignore or not answer a write.
The console test uses the loopback fake of `tests/acceptance_support.py` on `127.0.0.1`. No LAN
device and no real data directory was used.

#### Scenario to test map

| Scenario | Evidence |
| --- | --- |
| T28-01 Plan, owned fields, rejections, dry run | `tests/test_signals.py`: `test_the_owned_fields_are_exactly_the_written_ones`, `test_unsupported_states_are_refused_before_any_write_with_a_stable_reason`; `tests/test_signal_tools.py` `test_dry_run_returns_the_real_plan_and_reserves_nothing`, `test_profiles_and_ceilings_gate_start_and_cancel_but_not_the_status` |
| T28-02 Expiry with unchanged state | `tests/test_signal_manager.py` `test_expiry_restores_only_the_owned_fields` |
| T28-03 Cancel, idempotence, race with expiry | `test_cancel_restores_at_once_is_idempotent_and_races_expiry_once` |
| T28-04 Overlap and limits | `test_overlap_is_rejected_deterministically_and_limits_hold` |
| T28-05 Intervening external edit | `test_an_intervening_edit_is_a_conflict_and_nothing_is_overwritten` (nine cases), `test_cancel_after_an_external_edit_reports_the_conflict_as_success`; `tests/test_signals.py` compare tests |
| T28-06 Offline at expiry | `test_offline_at_expiry_retries_once_after_a_pause_and_never_replays`, `test_cancel_offline_makes_one_attempt_and_reports_uncertain` |
| T28-07 Indeterminate restore POST | `test_an_unverified_restore_is_uncertain_and_never_retried` |
| T28-08 Failed or uncertain apply | `test_a_failed_start_leaves_no_record_and_an_uncertain_one_is_never_restored` |
| T28-09 Lost connection / cancelled caller | `test_a_cancelled_start_request_still_registers_and_restores_at_expiry`; HTTP leg in `tests/test_signal_tools.py` |
| T28-10 Shutdown | `test_orderly_shutdown_restores_every_active_signal_once_with_the_control_class`, `test_shutdown_refuses_new_signals_and_abandons_work_beyond_its_budget` |
| T28-11 Restart, no persistence | `test_nothing_is_persisted_or_recovered_after_a_restart` |
| T28-12 Access contexts, both cases | `test_delayed_restores_run_as_control_under_a_restricted_deployment`; `tests/test_signal_tools.py` ceiling test |
| T28-13 Bounded cleanup | `test_ended_records_are_bounded_and_no_task_or_waiter_is_left`, `test_the_start_schema_enforces_every_bound` |
| T28-14 Registry and contract | `tests/tool_contract.py`, `tests/test_tool_contract.py`, `tests/test_access_profiles.py`, `test_descriptions_state_the_limits_and_every_property_is_described` |
| T28-15 Both transports share the manager | `test_in_process_and_loopback_http_share_the_manager_and_survive_a_dropped_client`; `tests/test_acceptance_parity.py::test_a_signal_start_status_cancel_gives_identical_results_over_stdio_and_http` (exactly two POSTs) |
| T28-16 Privacy and logs (Should) | `test_ended_records_are_bounded_and_no_task_or_waiter_is_left` (log lines carry no address or colour) |
| T28-17 Feeds the explanation evidence (Should) | same test: after a restore `last_control` shows `wled_signal_restore` applied and verified |

### Live evidence (ISSUE-28-DEC-001)

One owner-authorized session on 2026-11-12, through an actual MCP stdio client against a local build
of the candidate (profile `full`, throw-away data directory removed afterwards; hub not touched).
Scope and limits: [ISSUE-28-DEC-001](../decisions/stage-3.md). Controller: the test controller of the
earlier runs, WLED 16.0.1, ESP32-C3, 133 LEDs, one RGB segment, 37 tools served.

Baseline (read-only, saved before the first write): master off, brightness 47, transition 7, no
playlist, preset or nightlight, segment 0 on, colour slot 0 `[138,189,255]`, effect Solid, speed 128,
intensity 128, palette 11; preset list held exactly slot 1. The read-only dry run returned `ok`
without a write.

| Step | Result |
| --- | --- |
| Run A: start, segment 0, green, 10 s | `applied`/`verified`; readback showed master on, brightness 47, slot 0 green, other fields unchanged; status `active`. |
| Run A: expiry | `restoring` then `restored`, `ended_by` `expired`, verified 10.36 s after start. Readback and preset list equalled the baseline. |
| Run B: start, 60 s; external `wled_patch_segments` (slot 0 to blue) 3 s later | Both `applied`/`verified`. |
| Run B: `wled_cancel_signal` | `ok`, `skipped_conflict`, `ended_by` `cancelled`; no restore write, the external blue colour stayed. |
| Run B: baseline restoration by the coordinator | Explicit `wled_patch_segments` and `wled_set_state` (`on` false), both `applied`/`verified`; readback equalled the baseline. |

No write failed or was retried; no reboot, firmware, settings or preset change. Final state equals
the baseline. No difference from the mock assumptions was observed. The baseline effect was already
Solid and had no running preset marker, so an effect change and the clearing of that marker were not
exercised.

### Limits

- Mock evidence only: offline or timing-out controller during restore, shutdown restore, restart and
  crash behavior, a non-Solid prior effect, RGBW and multi-segment devices, the HTTP transport (the
  live run used stdio) and any other controller.
- Not confirmed on a controller: that speed, intensity and palette survive a real effect change, and
  that a state write clears the running preset marker.
- Nothing is persisted: a crash, kill or power loss leaves an active signal applied and its ID unknown
  ([contract](../contract/signals.md#shutdown-and-restart)).
- Timing is best effort; no exact duration is claimed, in particular not across an outage.
- A write by another client between the comparison read and the restore POST is not detected.
- The console parity test runs one scenario; timer-driven, failure and shutdown paths are tested in
  process with the controlled clock.

## Issue #29 validation: static SVG layout preview

Evidence for [#29](https://github.com/descipar/wled-mcp/issues/29) (acceptance scenario S3-T03,
requirements S3-PREVIEW-01 and S3-PREVIEW-02); contract in
[contract/layout-preview.md](../contract/layout-preview.md), decisions in
[ISSUE-29-DEC-001](../decisions/stage-3.md).

**All evidence is mock and fixture evidence.** The pure renderer is tested with synthetic models; the
tool runs against the GET-only mock router of `tests/state_catalog_support.py` (any other method fails,
so every test also shows nothing was written) and the loopback fake of `tests/acceptance_support.py`;
zone files use pytest `tmp_path`. No LAN device or hardware was used and there is **no claim about
physical colour, real controllers or firmware animation**.

### Scenario to test map

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

### Limits

- Mock and fixture evidence only. No hardware check was run, authorized or required: the preview adds no
  endpoint beyond `/json/state`, `/json/info` and optionally `/json/live`, exercised by earlier records
  ([#150](m3-m6.md), [#30](stage-3.md)).
- The SVG was checked structurally and by one golden string; it was not viewed in every browser, and the
  picture is not a statement about how the LEDs look.
- Colours approximate the first colour slot or sampled live colours; effects, palettes and animation are
  not simulated. 2D and matrix devices are refused, not drawn.
- Carried: an optional 2D preview over declared matrix geometry (candidate Backlog).

## Issue #30 - lighting explanation

Requirements: S3-EXPLAIN-01, S3-EXPLAIN-02; scenarios X30-1 to X30-8 of the approved work
packet. Contract: [contract/explain.md](../contract/explain.md).

Synthetic tests in `tests/test_explain.py` cover: competing explanations with capped confidence and no
actor (X30-1); missing firmware indicators including `ver` (X30-2); stale and absent process memory
(X30-3); an unattributable mismatch (X30-4); separate categories for unreachable, timeout, out-of-range
effect/palette, white on an RGB segment, verification mismatch and a clean device (X30-5); exactly two
GETs and no POST (X30-6); registration in every profile with advisory annotations (X30-7); redaction
sentinels, output and cause caps, and the dispatcher hook recording only allowlisted fields from a real
control outcome (X30-8). `tests/test_diagnostics.py` covers the evidence store,
`tests/test_access_profiles.py` and `tests/tool_contract.py` the READ tool, and
`tests/test_acceptance_parity.py` runs it through the stdio console and a protected loopback HTTP
console before and after an uncertain write. No ordinary test contacts a LAN device.

### Deviations from the work packet

- The evidence store is a class in `diagnostics.py` carried as `ServiceMonitor.last_control`
  (`create_server` receives only the monitor and `cli.py` was outside the authorized paths).
- `info.lm`/`info.ver` use a stricter character allowlist than "32 printable characters", so address-
  or MAC-like text becomes `other`.
- `docs/WLED-COVERAGE.md` gained a server-only entry (required by check C7).
- Every call counts as a reported ineffective change, so a device without an explaining indicator still
  returns `UNATTRIBUTED_MISMATCH` and `INSUFFICIENT_EVIDENCE`; `SYNC_RECEIVE_ENABLED` (a firmware
  default) neither suppresses those codes nor lifts the conclusion above `insufficient_evidence`.
- `lor` greater than zero is contradicting evidence for a realtime candidate.

### Hardware

None as part of the implementation. The M2 read-only live run followed separately.

#### Live read-only run (M2 exit, ISSUE-30-DEC-001)

On 2026-11-11 the coordinator ran the merged software (content identical to `main` at the squash commit
of PR #175) through an MCP stdio client with the `read-only` profile against one owner-selected test
controller: exactly one `wled_explain_lighting` call (one `GET /json/state`, one `GET /json/info`).

| Field | Observed result |
| --- | --- |
| Envelope `ok` / `application` / `verification` | true / `not_attempted` / `not_requested` |
| Firmware | WLED 16.0.1, build 2606300, 133 LEDs, 220 effects, 72 palettes |
| Master power / brightness | off / 47 |
| Playlist `pl` / preset `ps` | -1 / -1 (none active) |
| Nightlight / realtime `lor` / `live` / `lm` | off / 0 / false / empty |
| Sync receive `udpn.recv` | true |
| Last control (process memory) | unknown, no write in this process |
| Inferred causes | `MASTER_OFF_OR_ZERO_BRIGHTNESS` (high, observed); `SYNC_RECEIVE_ENABLED` (low, possibility only) |
| Conclusion | `observed_blocker` |

Result: the tool works against real firmware over the real transport, every allowlisted indicator was
present, and the result stayed within the documented limits (no actor named, sync cause marked as a
possibility). It confirms that sync receive is enabled on a default controller. Not checked on hardware:
writes, other devices, repeated or stale-evidence behavior, playback/realtime override and
unattributed-mismatch paths (master was off); those are mock-only. No physical write, configuration or
firmware change, deployment or discovery occurred.
