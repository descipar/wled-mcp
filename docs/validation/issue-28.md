# Issue #28 validation: temporary signals with conflict-aware restoration

Evidence for [#28](https://github.com/descipar/wled-mcp/issues/28) (acceptance scenario S3-T02,
requirements S3-SIGNAL-01 and S3-SIGNAL-02); contract in [contract/signals.md](../contract/signals.md),
decisions in [ISSUE-28-DEC-001 and -002](../decisions/issue-28.md).

**Status: software evidence complete; live evidence recorded below** (two runs on the one selected
test controller under ISSUE-28-DEC-001, on candidate `0b3e6c688abda967b64212a6449097cd157ef258`;
the later commits of the pull request change documentation only).

## Software evidence (mock, fixture and loopback only)

All timing is driven by a controlled clock: the manager's wait is an overridable attribute that the
tests replace with a manual timer on the existing `FakeClock` (`tests/signal_support.py`), so no
test waits in real time. The device is a stateful mock controller behind `httpx.MockTransport`
that applies POST bodies, so a restore is observable, and that can be edited externally, taken
offline or made to drop, ignore or not answer a write. The console test uses the loopback fake of
`tests/acceptance_support.py` on `127.0.0.1`. Every other host is `*.invalid`. No LAN device and no
real data directory was used. Per-operation deadlines stay real and fast with mocks, as in the other
write tests.

### Scenario to test map

| Scenario | Evidence |
| --- | --- |
| T28-01 Plan, owned fields, rejections, dry run | `tests/test_signals.py`: `test_the_owned_fields_are_exactly_the_written_ones`, `test_the_colour_follows_the_channel_width_of_the_segment`, `test_unsupported_states_are_refused_before_any_write_with_a_stable_reason` (one case per `data.reason`), `test_a_master_that_is_off_cannot_isolate_a_target_next_to_a_visible_segment`, `test_a_running_preset_is_allowed_with_a_warning`; `tests/test_signal_tools.py` `test_dry_run_returns_the_real_plan_and_reserves_nothing`, `test_profiles_and_ceilings_gate_start_and_cancel_but_not_the_status` (dry run `ACCESS_DENIED` for a capped device) |
| T28-02 Expiry with unchanged state | `tests/test_signal_manager.py` `test_expiry_restores_only_the_owned_fields` (two POSTs, restore body only owned keys, unowned external edits survive, wall timestamps from the clock) |
| T28-03 Cancel, idempotence, race with expiry | `test_cancel_restores_at_once_is_idempotent_and_races_expiry_once` |
| T28-04 Overlap and limits | `test_overlap_is_rejected_deterministically_and_limits_hold` (second start refused also while restoring, concurrent starts, other device allowed, ninth refused, slot freed after a terminal result and after a failed start) |
| T28-05 Intervening external edit | `test_an_intervening_edit_is_a_conflict_and_nothing_is_overwritten` (nine cases: colour, effect, master power, segment power, resized, removed, playlist, nightlight, realtime), `test_cancel_after_an_external_edit_reports_the_conflict_as_success`; `tests/test_signals.py` `test_compare_agrees_with_the_verification_functions_and_names_each_difference`, `test_the_number_of_reported_differences_is_bounded` |
| T28-06 Offline at expiry | `test_offline_at_expiry_retries_once_after_a_pause_and_never_replays`, `test_a_second_attempt_that_succeeds_is_reported_as_restored_with_a_warning`, `test_cancel_offline_makes_one_attempt_and_reports_uncertain` |
| T28-07 Indeterminate restore POST | `test_an_unverified_restore_is_uncertain_and_never_retried` (unreadable readback and mismatch) |
| T28-08 Failed or uncertain apply | `test_a_failed_start_leaves_no_record_and_an_uncertain_one_is_never_restored` |
| T28-09 Lost connection / cancelled caller | `test_a_cancelled_start_request_still_registers_and_restores_at_expiry`; HTTP leg in `tests/test_signal_tools.py` `test_in_process_and_loopback_http_share_the_manager_and_survive_a_dropped_client` |
| T28-10 Shutdown | `test_orderly_shutdown_restores_every_active_signal_once_with_the_control_class`, `test_shutdown_refuses_new_signals_and_abandons_work_beyond_its_budget` |
| T28-11 Restart, no persistence | `test_nothing_is_persisted_or_recovered_after_a_restart` (data directory tree unchanged, zero POSTs at startup, old IDs unknown, crash simulated without the orderly shutdown) |
| T28-12 Access contexts, both cases | `test_delayed_restores_run_as_control_under_a_restricted_deployment` ((a) timer, cancel and shutdown restores under a `control` profile with a `control` device cap, every POST seen with class `control`; (b) the same policy refuses a write without a class, and a start from a caller whose ambient class is `read` still works); `tests/test_signal_tools.py` `test_profiles_and_ceilings_gate_start_and_cancel_but_not_the_status` (`read`-capped device, `read-only` profile) |
| T28-13 Bounded cleanup | `test_ended_records_are_bounded_and_no_task_or_waiter_is_left`; schema bounds in `test_the_start_schema_enforces_every_bound` |
| T28-14 Registry and contract | `tests/tool_contract.py` entries, `tests/test_tool_contract.py`, `tests/test_access_profiles.py` (registry-driven profile, ceiling and no-POST tests), `tests/test_signal_tools.py` `test_descriptions_state_the_limits_and_every_property_is_described` |
| T28-15 Both transports share the manager | `test_in_process_and_loopback_http_share_the_manager_and_survive_a_dropped_client` (one tool list and schema set over the in-memory client and loopback Streamable HTTP, start on one HTTP client, status on another, restore at expiry); `tests/test_acceptance_parity.py` `test_a_signal_start_status_cancel_gives_identical_results_over_stdio_and_http` (installed console over stdio and over protected loopback HTTP, start with 300 s, status, cancel, status, equal after masking, exactly two POSTs) |
| T28-16 Privacy and logs (Should) | `test_ended_records_are_bounded_and_no_task_or_waiter_is_left` (log lines carry no address or colour, the configured device ID only) |
| T28-17 Feeds the explanation evidence (Should) | the same test: after a restore `last_control` shows `wled_signal_restore` with applied and verified |

## Live evidence (ISSUE-28-DEC-001)

One owner-authorized hardware session on 2026-11-12, run by the coordinator through an actual MCP
stdio client against a local build of the candidate (access profile `full`, throw-away data
directory that was removed afterwards; no snapshot was created on the hub and the hub service was not
touched). Scope and limits: [ISSUE-28-DEC-001](../decisions/issue-28.md). The controller is the test
controller of the earlier runs: WLED 16.0.1, ESP32-C3, 133 LEDs, one RGB segment, 37 tools served.

**Baseline** (read-only, saved before the first write): master off, brightness 47, transition 7, no
playlist, preset or nightlight, segment 0 on (0 to 133), colour slot 0 `[138,189,255]`, effect 0
(Solid), speed 128, intensity 128, palette 11; the preset list held exactly slot 1. The read-only
dry run of `wled_start_signal` returned `ok`, no write, and the owned fields master `on`, segment
colour slot 0 and `fx`; the device state and the preset list were unchanged afterwards.

| Step | Result |
| --- | --- |
| Run A: start, segment 0, green, 10 s | `applied`/`verified`. The state readback showed master on, brightness still 47, slot 0 green, effect Solid, speed, intensity and palette unchanged. Status `active` with a falling `remaining_seconds`. |
| Run A: expiry | Status went `restoring` then `restored`, `ended_by` `expired`. The verified restore ended 10.36 s after the start (best effort, not shorter than requested). The state readback equalled the baseline on every compared field (master off, brightness 47, transition 7, segment fields) and the preset list equalled the baseline. |
| Run B: start, 60 s; external `wled_patch_segments` (slot 0 to blue) 3 s later | Start `applied`/`verified`; the patch `applied`/`verified`. |
| Run B: `wled_cancel_signal` | `ok`, status `skipped_conflict`, `ended_by` `cancelled`; no restore write: the readback after the cancel still showed the external blue colour with the master on. |
| Run B: baseline restoration by the coordinator | Explicit `wled_patch_segments` (slot 0 to the captured value) and `wled_set_state` (`on` false), both `applied`/`verified`; the state readback equalled the baseline and the preset list was unchanged. |

No write failed, no write was retried and nothing outside the authorized scope was touched: no
reboot, firmware, settings or preset change. The final state equals the recorded baseline.
Differences from the mock assumptions: none observed. The firmware kept speed, intensity and
palette across the effect change; the baseline had no running preset marker, so the clearing of
that marker was not exercised.

## Limits

- Not exercised on hardware (mock evidence only): an offline or timing-out controller during the
  restore, the shutdown restore, restart and crash behavior, a non-Solid prior effect (if the
  baseline effect is Solid), RGBW and multi-segment devices, the HTTP transport or stdio (whichever
  the live run does not use) and any controller other than the selected one.
- Not confirmed on a controller: that a state write clears the running preset marker (the baseline
  had none).
- Nothing is persisted. A crash, kill or power loss leaves an active signal applied and its ID
  unknown afterwards ([contract](../contract/signals.md#shutdown-and-restart)).
- Timing is best effort; no exact duration is claimed, in particular not across an outage.
- A write by another client between the comparison read and the restore POST is not detected.
- The console parity test runs one scenario (start, status, cancel, status); the timer-driven
  paths, the failure paths and the shutdown are tested in process with the controlled clock.
